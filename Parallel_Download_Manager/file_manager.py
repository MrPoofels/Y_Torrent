import asyncio
from bitstring import BitArray
import Parallel_Download_Manager as PMD
from hashlib import sha1
import logging


PEER_ID_INDEX = 0
PEER_IP_INDEX = 1
PEER_PORT_INDEX = 2


logging.getLogger("asyncio").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


class FileManager:
    def __init__(self, file_path, file_size, download_manager, hash_list, global_piece_index_start):
        self.download_manager = download_manager
        self.file_size = file_size
        self.hash_list = hash_list
        self.piece_list = [PMD.Piece(index, self.download_manager.meta_info.piece_size) for index in range(len(hash_list) - 1)]
        self.piece_list.append(PMD.Piece(len(hash_list) - 1, self.file_size % self.download_manager.meta_info.piece_size))
        self.bitfield = BitArray(uint=0, length=len(hash_list))
        self.global_piece_index_start = global_piece_index_start

        try:
            self.file = open(file_path, 'xb+')
        except FileExistsError or FileNotFoundError:
            self.file = open(file_path, 'rb+')
            self.file.seek(0)
            curr_internal_piece_index = 0
            for piece in self.piece_list:
                if curr_internal_piece_index == (len(self.piece_list) - 1):
                    piece_size = self.file_size % self.download_manager.meta_info.piece_size
                else:
                    piece_size = self.download_manager.meta_info.piece_size
                file_piece = self.file.read(self.download_manager.meta_info.piece_size)
                curr_hash = sha1(file_piece).digest()
                if curr_hash == self.hash_list[curr_internal_piece_index]:
                    self.bitfield[curr_internal_piece_index] = '0b1'
                    piece.blocks_to_request = None
                    piece.bytes_downloaded = piece_size
                    self.download_manager.bytes_downloaded += piece_size
                curr_internal_piece_index += 1
        if not self.file.seek(0, 2) == self.file_size:
            self.file.seek(self.file_size - 1)
            self.file.write(b"\0")
            self.file.seek(0)


    async def write_to_file(self, block, data, internal_piece_index):
        curr_piece = self.piece_list[internal_piece_index]
        await curr_piece.update_progress(len(data))
        self.download_manager.bytes_downloaded += len(data)
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
            if curr_hash == self.hash_list[internal_piece_index]:
                logging.info(f"Piece number {piece.piece_index} in file {self.file.name} (internal index: {internal_piece_index}) has been downloaded and verified")
                self.bitfield[internal_piece_index] = 1
                self.download_manager.priority_list.remove(piece)
                if not self.download_manager.priority_list:
                    self.download_manager.seeder_mode = True
                await asyncio.gather(*[peer.send_have_msg(piece.piece_index) for peer in self.download_manager.peer_list])
            else:
                piece.bytes_downloaded = 0
                piece.blocks_to_download_counter = 0
                piece.initiate_block_list(self.download_manager.meta_info.piece_size)
                self.download_manager.bytes_downloaded -= piece_size
                logging.warning(f"Piece number {piece.piece_index} in file {self.file.name} (internal index: {internal_piece_index}) did not pass verification")


    async def read_from_file(self, internal_piece_index, block):
        self.file.seek((internal_piece_index * self.download_manager.meta_info.piece_size) + block.begin)
        data = self.file.read(block.length)
        return data
