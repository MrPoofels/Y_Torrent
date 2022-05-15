import asyncio
import collections
import random
from typing import Tuple, Any, List
import os
import torf
from torf import Magnet
from bitstring import BitArray
import Parallel_Download_Manager as PMD
from torf import Torrent # https://torf.readthedocs.io/en/stable/
from hashlib import sha1
import logging
import random
import tracker_communication
import concurrent.futures
import math
import socket

PEER_ID_INDEX = 0
PEER_IP_INDEX = 1
PEER_PORT_INDEX = 2

@PMD.Async_init
class MagnetLinkHandler(PMD.DownloadManager):
    async def __init__(self, ip, client_id, content_path, torrent_path, magnet_uri):
        magnet = Magnet.from_string(magnet_uri)
        self.meta_info = Torrent(trackers=[tracker for tracker in magnet.tr if tracker[:4] == 'http'])
        self.meta_info._infohash = magnet.infohash
        tracker_connection = await tracker_communication.TrackerCommunication(self.meta_info.trackers[0], bytes.fromhex(magnet.infohash), 'test', socket.gethostname(), None)
        await tracker_connection.http_GET(0, 0, event="started")
        peer_info_list, interval = await tracker_connection.interpret_tracker_response()
        peer = PMD.Peer(self, peer_info_list[PEER_ID_INDEX], peer_info_list[PEER_IP_INDEX], peer_info_list[PEER_PORT_INDEX])
        while self.meta_info.size == 0:
            await asyncio.sleep(0.5)
        self.meta_info.files = torf.File(torrent_path, self.meta_info.size)
        await PMD.DownloadManager.__init__(self, ip, client_id, content_path, block_len=16384)
        # self.client_id = client_id
        #
        # self.magnet_uri = Magnet.from_string(magnet_uri)
        #
        # self.file = open(torrent_path, 'xb+')
        #
        # self.piece_list = None
        # self.priority_list = list()
        #
        # self.bytes_downloaded = 0
        # self.bytes_uploaded = 0
        #
        # for tracker in self.magnet_uri.tr:
        #     if tracker[:4] == 'http':
        #         chosen_tr = tracker
        #
        # self.tracker_communication = await tracker_communication.TrackerCommunication(chosen_tr, self.magnet_uri.tr, self.client_id, ip, self)
        # await self.tracker_communication.http_GET(self.bytes_uploaded, self.bytes_downloaded, 0, "started")
        # peer_info_list, interval = await self.tracker_communication.interpret_tracker_response()
        # self.tracker_communication.periodic_GET_task = asyncio.create_task(self.tracker_communication.periodic_GET(interval))
        #
        # self.peer_list = list()
        # await self.extend_peer_list(peer_info_list)
        # self.peer_list.sort(reverse=True)
        #
        # self.downloaders = []
        # self.optimistic_unchoke_timer_task = asyncio.create_task(self.optimistic_unchoke_timer())
        # self.choking_algorithm_task = asyncio.create_task(self.choking_algorithm())

    async def initiate_piece_and_priority_lists(self):
        self.piece_list = [PMD.Piece(index, 16384, 16384) for index in range(len(self.meta_info.hashes) - 1)]
        self.piece_list.append(PMD.Piece(self.meta_info.pieces - 1, self.meta_info.files[0].size % self.meta_info.piece_size))
        for piece in self.piece_list:
            self.priority_list.append(piece)
        self.priority_list.sort()

    async def write_to_file(self, block, data, internal_piece_index):
        curr_piece = self.piece_list[internal_piece_index]
        await curr_piece.update_progress(len(data))
        curr_piece.blocks_to_request.remove(block)
        self.file.seek((internal_piece_index * self.download_manager.meta_info.piece_size) + block.begin)
        self.file.write(data)
        logging.debug(f"wrote some data to {self.file.name}")
        await self.determine_piece_complete(curr_piece, internal_piece_index)


    async def determine_piece_complete(self, piece, internal_piece_index):
        if internal_piece_index == (len(self.piece_list) - 1):
            piece_size = self.file_size % self.download_manager.meta_info.piece_size
        else:
            piece_size = self.download_manager.meta_info.piece_size
        if piece.bytes_downloaded == piece_size:
            self.file.seek((internal_piece_index * self.download_manager.meta_info.piece_size))
            curr_hash = sha1(self.file.read(piece_size)).digest()
            if curr_hash == self.meta_info.infohash:
                logging.info(f"Piece number {piece.piece_index} in file {self.file.name} (internal index: {internal_piece_index}) has been downloaded and verified")
                self.bitfield[internal_piece_index] = 1
                self.download_manager.priority_list.remove(piece)
                if not self.download_manager.priority_list:
                    self.download_manager.seeder_mode = True
            else:
                piece.bytes_downloaded = 0
                piece.blocks_to_download_counter = 0
                piece.initiate_block_list(self.download_manager.meta_info.piece_size)
                self.download_manager.bytes_downloaded -= piece_size
                logging.warning(f"Piece number {piece.piece_index} in file {self.file.name} (internal index: {internal_piece_index}) did not pass verification")
