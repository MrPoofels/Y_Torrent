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

# TODO: implement peer interest algorithm


PEER_ID_INDEX = 0
PEER_IP_INDEX = 1
PEER_PORT_INDEX = 2


logging.getLogger("asyncio").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


@PMD.Async_init
class DownloadManager:
    peer_list: list[PMD.Peer]
    bitfield: BitArray

    async def __init__(self, ip, client_id, torrent_path = None, path = None, peer_info_list = None):
        self.client_id = client_id

        self.meta_info = Torrent.read(torrent_path)

        self.piece_list = [PMD.Piece(index, self.meta_info.piece_size) for index in range(len(self.meta_info.hashes) - 1)]
        self.piece_list.append(PMD.Piece(self.meta_info.pieces - 1, self.meta_info.files[0].size % self.meta_info.piece_size))
        self.bitfield = BitArray(uint=0, length=self.meta_info.pieces)

        self.bytes_downloaded = 0
        self.bytes_uploaded = 0

        self.priority_list = [piece for piece in self.piece_list]
        self.priority_list.sort()

        try:
            self.file = open(path, 'xb+')
        except FileExistsError:
            self.file = open(path, 'rb+')
            self.file.seek(0)
            for piece in self.piece_list:
                if piece.piece_index == (self.meta_info.pieces - 1):
                    piece_size = self.meta_info.files[0].size % self.meta_info.piece_size
                else:
                    piece_size = self.meta_info.piece_size
                file_piece = self.file.read(self.meta_info.piece_size)
                curr_hash = sha1(file_piece).digest()
                if curr_hash == self.meta_info.hashes[piece.piece_index]:
                    self.priority_list.remove(piece)
                    self.bitfield[piece.piece_index] = '0b1'
                    piece.blocks_to_request = None
                    piece.bytes_downloaded = piece_size
                    self.bytes_downloaded += piece_size
        if not self.file.seek(0, 2) == self.meta_info.files[0].size:
            self.file.seek(self.meta_info.files[0].size - 1)
            self.file.write(b"\0")
            self.file.seek(0)
        if self.priority_list:
            self.seeder_mode = False
        else:
            self.seeder_mode = True

        # self.tracker_communication = await tracker_communication.TrackerCommunication(self.meta_info.trackers[0][0], self.meta_info.infohash, self.client_id, ip)
        # await self.tracker_communication.http_GET(self.bytes_uploaded, self.bytes_downloaded, self.meta_info.files[0].size - self.bytes_downloaded, "started")
        # peer_info_list = await self.tracker_communication.tracker_response()

        self.peer_list = await asyncio.gather(*[PMD.Peer(self, peer_info[PEER_ID_INDEX], peer_info[PEER_IP_INDEX], peer_info[PEER_PORT_INDEX]) for peer_info in peer_info_list])
        self.peer_list.sort(reverse=True)

        self.downloaders = []
        self.optimistic_unchoke_timer_task = asyncio.create_task(self.optimistic_unchoke_timer())
        self.choking_algorithm_task = asyncio.create_task(self.choking_algorithm())


    async def extend_peer_list(self, peer_info_list):
        self.peer_list.extend(await asyncio.gather(*[PMD.Peer(self, peer_info[PEER_ID_INDEX], peer_info[PEER_IP_INDEX], peer_info[PEER_PORT_INDEX]) for peer_info in peer_info_list]))


    async def write_to_file(self, block, data, piece_index):
        curr_piece = self.piece_list[piece_index]
        await curr_piece.update_progress(len(data))
        self.bytes_downloaded += len(data)
        curr_piece.blocks_to_request.remove(block)
        self.file.seek((piece_index * self.meta_info.piece_size) + block.begin)
        self.file.write(data)
        logging.debug("wrote some data to file")
        await self.determine_piece_complete(curr_piece, (piece_index * self.meta_info.piece_size))


    async def determine_piece_complete(self, piece, file_pos):
        if piece.piece_index == (self.meta_info.pieces - 1):
            piece_size = self.meta_info.files[0].size % self.meta_info.piece_size
        else:
            piece_size = self.meta_info.piece_size
        if piece.bytes_downloaded == piece_size:
            self.file.seek(file_pos)
            curr_hash = sha1(self.file.read(piece_size)).digest()
            if curr_hash == self.meta_info.hashes[piece.piece_index]:
                logging.debug(f"Piece number {piece.piece_index} has been downloaded and verified")
                self.bitfield[piece.piece_index] = 1
                self.priority_list.remove(piece)
                if not self.priority_list:
                    self.seeder_mode = True
                await asyncio.gather(*[peer.send_have_msg(piece.piece_index) for peer in self.peer_list])
            else:
                piece.bytes_downloaded = 0
                piece.blocks_to_download_counter = 0
                piece.initiate_block_list(self.meta_info.piece_size)
                self.bytes_downloaded -= piece_size
                logging.debug(f"Piece number {piece.piece_index} did not pass verification")


    async def read_from_file(self, piece_index, block):
        self.file.seek((piece_index * self.meta_info.piece_size) + block.begin)
        data = self.file.read(block.length)
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
