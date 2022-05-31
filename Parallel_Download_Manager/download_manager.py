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


PEER_IP_INDEX = 0
PEER_PORT_INDEX = 1


logging.getLogger("asyncio").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


@PMD.Async_init
class DownloadManager:
    peer_list: list[PMD.Peer]
    bitfield: BitArray

    async def __init__(self, client_id, content_path, torrent_path = None):
        self.domination = 0
        self.client_id = client_id
    
        self.meta_info = Torrent.read(torrent_path)
    
        self.piece_list = [PMD.Piece(index, self.meta_info.piece_size) for index in range(self.meta_info.pieces)]
        if self.meta_info.size % self.meta_info.piece_size != 0:
            self.piece_list[self.meta_info.pieces - 1] = (PMD.Piece(self.meta_info.pieces - 1, self.meta_info.size % self.meta_info.piece_size))
        self.bitfield = BitArray(uint=0, length=self.meta_info.pieces)
    
        self.bytes_downloaded = 0
        self.bytes_uploaded = 0
    
        self.file_list = list()
        start_byte_index = 0
        for file in self.meta_info.files:
            absolute_path = os.path.join(content_path, file)
            os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
            self.file_list.append(PMD.FileManager(absolute_path, file.size, self, start_byte_index))
            start_byte_index += file.size
    
        self.priority_list = list()
        for piece in self.piece_list:
            if self.bitfield[piece.piece_index] != '0b1':
                self.priority_list.append(piece)
        self.priority_list.sort()
        
        for piece in self.piece_list:
            await self.verify_piece(piece, self.get_piece_size(piece.piece_index))
    
        if self.priority_list:
            self.seeder_mode = False
        else:
            self.seeder_mode = True
        self.tracker_communication = tracker_communication.TrackerCommunication(self.meta_info.trackers)
        await self.tracker_communication.connect()
        peer_info_list = self.tracker_communication.announce(self, 2)
    
        self.peer_list = [PMD.Peer(self, peer_info[PEER_IP_INDEX], peer_info[PEER_PORT_INDEX]) for peer_info in peer_info_list]
        try:
            await asyncio.gather(*[peer.initiate_peer() for peer in self.peer_list])
        except asyncio.CancelledError:
            logging.warning(f'peer was cancelled')
        self.peer_list.sort(reverse=True)
    
        self.downloaders = []
        self.optimistic_unchoke_timer_task = asyncio.create_task(self.optimistic_unchoke_timer())
        self.choking_algorithm_task = asyncio.create_task(self.choking_algorithm())
    
    async def add_peer(self, reader, writer, peer_id):
        peer = PMD.Peer(self, peer_id, reader=reader, writer=writer)
        self.peer_list.append(peer)
        await peer.initiate_peer()
        
        
    async def write_data(self, piece_index, data, length, begin):
        """

        Args:
            piece_index:
            data (bytearray):
            length:
            begin:
        """
        file_index, file_respective_begin = self.get_file_pos(piece_index, begin)
        while len(data) > 0:
            data = await self.file_list[file_index].write_to_file(file_respective_begin, data)
            file_index += 1
            file_respective_begin = 0
        self.piece_list[piece_index].block_done(PMD.Block(begin, length))
        self.bytes_downloaded += length
        await self.determine_piece_complete(self.piece_list[piece_index])
        

    async def read_data(self, piece_index, length, begin):
        file_index, file_respective_begin = self.get_file_pos(piece_index, begin)
        data = bytearray()
        while len(data) < length:
            data.extend(await self.file_list[file_index].read_from_file(file_respective_begin, length - len(data)))
            file_index += 1
            file_respective_begin = 0
        return data


    def get_piece_size(self, piece_index):
        if piece_index == (len(self.piece_list) - 1):
            return self.meta_info.size % self.meta_info.piece_size
        else:
            return self.meta_info.piece_size


    def get_file_pos(self, piece_index, begin):
        """

        Args:
            begin:
            piece_index:
        """
        global_block_begin = (piece_index * self.meta_info.piece_size) + begin
        for file in self.file_list:
            if global_block_begin >= file.start_byte:
                curr_file = file
                file_respective_begin = (global_block_begin - file.start_byte)
            else:
                break
        file_index = self.file_list.index(curr_file)
        return file_index, file_respective_begin
    
    
    async def determine_piece_complete(self, piece):
        piece_size = self.get_piece_size(piece.piece_index)
        if piece.bytes_downloaded == piece_size:
            if await self.verify_piece(piece, piece_size):
                await asyncio.gather(*[peer.send_have_msg(piece.piece_index) for peer in self.peer_list])
            
            
    async def verify_piece(self, piece, piece_size):
        curr_hash = sha1(await self.read_data(piece.piece_index, piece_size, 0)).digest()
        if curr_hash == self.meta_info.hashes[piece.piece_index]:
            logging.info(
                f"Piece number {piece.piece_index} has been downloaded and verified")
            self.bitfield.set(True, piece.piece_index)
            self.priority_list.remove(piece)
            if not self.priority_list:
                self.seeder_mode = True
            return True
        else:
            if piece.bytes_downloaded > 0:
                self.bytes_downloaded -= piece_size
            piece.bytes_downloaded = 0
            piece.initiate_block_list(piece_size)
            logging.warning(
                f"Piece number {piece.piece_index} did not pass verification")
            return False

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
            
            
    async def pause_all(self):
        self.choking_algorithm_task.cancel()
        self.optimistic_unchoke_timer_task.cancel()
        for peer in self.peer_list:
            await peer.change_am_choking_state(True)
            await peer.change_am_interested_state(False)
            
            
    async def unpause_all(self):
        self.downloaders = []
        self.optimistic_unchoke_timer_task = asyncio.create_task(self.optimistic_unchoke_timer())
        self.choking_algorithm_task = asyncio.create_task(self.choking_algorithm())
        for peer in self.peer_list:
            if peer.select_piece() is not None:
                await peer.change_am_interested_state(True)
