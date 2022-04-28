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


@PMD.Async_init
class FileManager:
    async def __init__(self, file_path, file_size, download_manager, hash_list):
        self.download_manager = download_manager
        self.file_size = file_size
        self.hash_list = hash_list
        self.piece_list = [PMD.Piece(index, self.download_manager.meta_info.piece_size) for index in range(len(hash_list) - 1)]
        self.piece_list.append(PMD.Piece(len(hash_list) - 1, self.file_size % self.download_manager.meta_info.piece_size))
        self.bitfield = BitArray(uint=0, length=len(hash_list))

        self.priority_list = [piece for piece in self.piece_list]
        self.priority_list.sort()

        try:
            self.file = open(file_path, 'xb+')
        except FileExistsError:
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
                    self.priority_list.remove(piece)
                    self.bitfield[curr_internal_piece_index] = '0b1'
                    piece.blocks_to_request = None
                    piece.bytes_downloaded = piece_size
                    self.bytes_downloaded += piece_size
                curr_internal_piece_index += 1
        if not self.file.seek(0, 2) == self.file_size:
            self.file.seek(self.file_size - 1)
            self.file.write(b"\0")
            self.file.seek(0)
        if self.priority_list:
            self.seeder_mode = False
        else:
            self.seeder_mode = True


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
                self.priority_list.remove(piece)
                if not self.priority_list:
                    self.seeder_mode = True
                await asyncio.gather(*[peer.send_have_msg(piece.piece_index) for peer in self.peer_list])
            else:
                piece.bytes_downloaded = 0
                piece.blocks_to_download_counter = 0
                piece.initiate_block_list(self.download_manager.meta_info.piece_size)
                self.bytes_downloaded -= piece_size
                logging.warning(f"Piece number {piece.piece_index} in file {self.file.name} (internal index: {internal_piece_index}) did not pass verification")


    async def read_from_file(self, piece_index, block):
        self.file.seek((piece_index * self.download_manager.meta_info.piece_size) + block.begin)
        data = self.file.read(block.length)
        return data


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