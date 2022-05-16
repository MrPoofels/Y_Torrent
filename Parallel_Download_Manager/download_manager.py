import asyncio
import collections
import random
from typing import Tuple, Any, List
import os
import torf
from bitstring import BitArray
import Parallel_Download_Manager as PMD
from torf import Torrent # https://torf.readthedocs.io/en/stable/
from hashlib import sha1
import logging
import random
import tracker_communication
import concurrent.futures
import math


PEER_ID_INDEX = 0
PEER_IP_INDEX = 1
PEER_PORT_INDEX = 2


logging.getLogger("asyncio").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


@PMD.Async_init
class DownloadManager:
    peer_list: list[PMD.Peer]
    bitfield: BitArray

    async def __init__(self, ip, client_id, content_path, torrent_path = None):
        self.client_id = client_id

        self.meta_info = Torrent.read(torrent_path)

        self.file_list = list()
        hash_list_index = 0
        for file in self.meta_info.files:
            file_hash_list_len = math.ceil(file.size / self.meta_info.piece_size)
            self.file_list.append(PMD.FileManager(os.path.join(content_path, file.path), file.size, self, self.meta_info.hashes[hash_list_index:file_hash_list_len], hash_list_index))
            hash_list_index += file_hash_list_len

        self.piece_list = [PMD.Piece(index, self.meta_info.piece_size) for index in range(self.meta_info.pieces)]
        if self.meta_info.size % self.meta_info.piece_size != 0:
            self.piece_list[self.meta_info.pieces - 1] = (PMD.Piece(self.meta_info.pieces - 1, self.meta_info.size % self.meta_info.piece_size))
        self.bitfield = BitArray(uint=0, length=self.meta_info.pieces)

        self.bytes_downloaded = 0
        self.bytes_uploaded = 0

        self.priority_list = list()
        for file in self.file_list:
            for piece in file.piece_list:
                self.priority_list.append(piece)
        self.priority_list.sort()

        self.tracker_communication = await tracker_communication.TrackerCommunication(self.meta_info.trackers[0][0], self.meta_info.infohash, self.client_id, ip, self)
        await self.tracker_communication.http_GET(self.bytes_uploaded, self.bytes_downloaded, self.meta_info.size - self.bytes_downloaded, "started")
        peer_info_list, interval = await self.tracker_communication.interpret_tracker_response()
        self.tracker_communication.periodic_GET_task = asyncio.create_task(self.tracker_communication.periodic_GET(interval))

        self.peer_list = list()
        await self.extend_peer_list(peer_info_list)
        self.peer_list.sort(reverse=True)

        self.downloaders = []
        self.optimistic_unchoke_timer_task = asyncio.create_task(self.optimistic_unchoke_timer())
        self.choking_algorithm_task = asyncio.create_task(self.choking_algorithm())


    async def extend_peer_list(self, peer_info_list):
        self.peer_list.extend(await asyncio.gather(*[PMD.Peer(self, peer_info[PEER_ID_INDEX], peer_info[PEER_IP_INDEX], peer_info[PEER_PORT_INDEX]) for peer_info in peer_info_list]))


    async def determine_file(self, global_piece_index):
        for file in self.file_list:
            if global_piece_index >= file.global_piece_index_start:
                curr_file = file
                internal_piece_index = (global_piece_index - file.global_piece_index_start)
        return curr_file, internal_piece_index


    async def write_to_file(self, block, data, piece_index):
        curr_file, internal_piece_index = (await self.determine_file(piece_index))
        await curr_file.write_to_file(block, data, internal_piece_index)


    async def read_from_file(self, piece_index, block):
        curr_file, internal_piece_index = (await self.determine_file(piece_index))
        data = curr_file.read_from_file(internal_piece_index, block)
        return data


    async def add_peer(self, reader, writer, peer_id):
        self.peer_list.append(await PMD.Peer(self, peer_id, reader=reader, writer=writer))


    def sort_priority_list(self):
        self.priority_list.sort()


    def decrease_piece_priority(self, piece):
        priority_list_index = self.priority_list.index(piece)
        self.priority_list.pop(priority_list_index)
        while piece.amount_in_swarm > self.priority_list[priority_list_index].amount_in_swarm and \
                priority_list_index < len(self.priority_list): # doesn't compare to index +1 because og piece was popped
            priority_list_index  += 1
        self.priority_list.insert(priority_list_index, piece)


    def increase_piece_priority(self, piece):
        priority_list_index = self.priority_list.index(piece)
        self.priority_list.pop(priority_list_index)
        while piece.amount_in_swarm < self.priority_list[priority_list_index - 1].amount_in_swarm and \
                priority_list_index > 0:
            priority_list_index  -= 1
        self.priority_list.insert(priority_list_index, piece)


    async def choking_algorithm(self):
        while True:
            if self.peer_list:
                break
            await asyncio.sleep(0.1)
        while True:
            self.peer_list.sort(reverse=True)
            new_downloaders_count = 0
            self.downloaders.append(self.peer_list[0])

            for peer in self.peer_list:

                if peer >= self.downloaders[0]:
                    await peer.change_am_choking_state(False)
                    if peer._peer_interested:
                        new_downloaders_count += 1
                        if peer not in self.downloaders:
                            self.downloaders.append(peer)
                            if len(self.downloaders) > 4:
                                await self.downloaders[0].change_am_choking_state(True)
                                self.downloaders.pop(0)
                            self.downloaders.sort(reverse=True)
                else:
                    await peer.change_am_choking_state(True)
                if self.seeder_mode:
                    if peer.client_upload_rate == 0:
                        break
                else:
                    if peer.client_download_rate == 0:
                        break
                if new_downloaders_count == 4:
                    break

            if len(self.peer_list) < 4:
                number_of_peers = len(self.peer_list)
            else:
                number_of_peers = 4
            while new_downloaders_count < number_of_peers:
                peer = await self.unchoke_random_peer()
                if peer is None:
                    break
                self.downloaders.append(peer)
                if len(self.downloaders) > 4:
                    await self.downloaders[0].change_am_choking_state(True)
                    self.downloaders.pop(0)
                self.downloaders.sort(reverse=True)
                new_downloaders_count += 1
            await asyncio.sleep(2)


    async def unchoke_random_peer(self):
        weight_list = [peer.optimistic_unchoke_weight for peer in self.peer_list]
        try:
            curr_peer = random.choices(self.peer_list, weights=weight_list, k=1)[0]
        except ValueError:
            return None
        await curr_peer.change_am_choking_state(False)
        return curr_peer


    async def optimistic_unchoke_timer(self):
        while True:
            if len(self.peer_list) > 1:
                break
            await asyncio.sleep(0.1)
        while True:
            curr_peer = await self.unchoke_random_peer()
            await asyncio.sleep(30)
            await curr_peer.change_am_choking_state(True)
