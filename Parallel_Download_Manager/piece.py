import asyncio
import Parallel_Download_Manager as PMD


class Piece:
    def __init__(self, piece_index, piece_len):
        self.amount_in_swarm = 0

        self.piece_index = piece_index

        self.bytes_downloaded = 0

        self.blocks_to_request = None
        self.initiate_block_list(piece_len)

    def initiate_block_list(self, piece_len):
        full_blocks_amount, last_block_len = divmod(piece_len, 16000)
        self.blocks_to_request = [PMD.Block(i * 16000, 16000) for i in range(full_blocks_amount)]
        if not last_block_len == 0:
            self.blocks_to_request.append(PMD.Block(piece_len - last_block_len, last_block_len))

    async def update_progress(self, length):
        self.bytes_downloaded += length

    async def select_block(self):
        return self.blocks_to_request.pop(0)

    async def return_block(self, block):
        self.blocks_to_request.append(block)

    def __lt__(self, other):
        return self.amount_in_swarm < other.amount_in_swarm

