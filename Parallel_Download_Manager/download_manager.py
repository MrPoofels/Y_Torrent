import asyncio

import torf
from bitstring import BitArray
import Parallel_Download_Manager as PMD
from torf import Torrent # https://torf.readthedocs.io/en/stable/
from hashlib import sha1
import logging

# TODO: implement peer interest algorithm


PEER_ID_INDEX = 0
PEER_IP_INDEX = 1
PEER_PORT_INDEX = 2


logging.getLogger("asyncio").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


@PMD.Async_init
class DownloadManager:
    bitfield: BitArray

    async def __init__(self, torrent_path, path, peer_info_list, downloader_id):
        self.downloader_id = downloader_id

        self.meta_info = Torrent.read(torrent_path)

        self.piece_list = [PMD.Piece(index, self.meta_info.piece_size) for index in range(len(self.meta_info.hashes) - 1)]
        self.piece_list.append(PMD.Piece(self.meta_info.pieces - 1, self.meta_info.size % self.meta_info.piece_size))
        self.bitfield = BitArray(uint=0, length=self.meta_info.pieces)

        self.priority_list = [piece for piece in self.piece_list]
        self.priority_list.sort()
        self.priority_list_changes_counter = 0

        try:
            self.file = open(path, 'xb+')
        except FileExistsError:
            self.file = open(path, 'rb+')
            self.file.seek(0)
            for piece in self.piece_list:
                file_piece = self.file.read(self.meta_info.piece_size)
                curr_hash = sha1(file_piece).digest()
                if curr_hash == self.meta_info.hashes[piece.piece_index]:
                    self.priority_list.remove(piece)
                    self.bitfield[piece.piece_index] = '0b1'
                    piece.blocks_to_request = None
                    piece.bytes_downloaded = self.meta_info.piece_size
        if not self.file.seek(0, 2) == self.meta_info.size:
            self.file.seek(self.meta_info.size - 1)
            self.file.write(b"\0")
            self.file.seek(0)

        self.peer_list = list()
        asyncio.create_task(self.initialize_peer_list(peer_info_list))


    async def initialize_peer_list(self, peer_info_list):
        self.peer_list.extend(await asyncio.gather(*[PMD.Peer(self, peer_info[PEER_ID_INDEX], peer_info[PEER_IP_INDEX], peer_info[PEER_PORT_INDEX]) for peer_info in peer_info_list]))


    async def write_to_file(self, begin, data, piece_index):
        curr_piece = self.piece_list[piece_index]
        await curr_piece.update_progress(len(data))
        self.file.seek((piece_index * self.meta_info.piece_size) + begin)
        self.file.write(data)
        logging.debug("wrote some data to file")
        await self.determine_piece_complete(curr_piece, (piece_index * self.meta_info.piece_size))


    async def determine_piece_complete(self, piece, file_pos):
        if piece.piece_index == (self.meta_info.pieces - 1):
            piece_size = self.meta_info.size % self.meta_info.piece_size
        else:
            piece_size = self.meta_info.piece_size
        if piece.bytes_downloaded == piece_size:
            self.file.seek(file_pos)
            curr_hash = sha1(self.file.read(piece_size)).digest()
            if curr_hash == self.meta_info.hashes[piece.piece_index]:
                logging.debug(f"Piece number {piece.piece_index} has been downloaded and verified")
                self.bitfield[piece.piece_index] = 1
                logging.debug(f"Piece number {piece.piece_index} has been successfully downloaded")
                for peer in self.peer_list:
                    asyncio.create_task(peer.send_have_msg(piece.piece_index))
            else:
                piece.bytes_downloaded = 0
                piece.blocks_to_download_counter = 0
                piece.initiate_block_list(self.meta_info.piece_size)
                logging.debug(f"Piece number {piece.piece_index} did not pass verification")


    async def read_from_file(self, piece_index, block):
        self.file.seek((piece_index * self.meta_info.piece_size) + block.begin)
        data = self.file.read(block.length)
        return data


    async def add_peer(self, reader, writer):
        self.peer_list.append(await PMD.Peer(self, reader=reader,writer=writer))


    async def update_priority_list(self):
        # write in project file about using card sort instead of built in
        while True:
            if self.priority_list_changes_counter >= 5:
                self.priority_list.sort()
