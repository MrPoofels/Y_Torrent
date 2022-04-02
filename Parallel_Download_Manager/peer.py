import asyncio
import socket

import bitstring
from bitstring import BitArray # docs: https://bitstring.readthedocs.io/en/latest/
import Parallel_Download_Manager as PMD
import collections # https://docs.python.org/3/library/collections.html
import logging


PROTOCOL_IDENTIFIER = "BitTorrent protocol"
REQUEST_MESSAGE_ID = (6).to_bytes(1, 'big')
REQUEST_MESSAGE_LENGTH = (13).to_bytes(4, 'big')

PIECE_MESSAGE_BASE_LENGTH = 9
PIECE_MESSAGE_ID = (7).to_bytes(1, 'big')

HAVE_MESSAGE_LENGTH = (5).to_bytes(4, 'big')
HAVE_MESSAGE_ID = (4).to_bytes(1, 'big')

BITFIELD_MESSAGE_BASE_LENGTH = 1
BITFIELD_MESSAGE_ID = (5).to_bytes(1, 'big')

# EXPAND: determine dynamically
DEFAULT_BLOCK_LEN = 16000
PENDING_REQUEST_MAXIMUM = 5


logging.getLogger("asyncio").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


@PMD.Async_init
class Peer:
    async def __init__(self, download_manager, peer_id = None, peer_ip = None, peer_port = None, reader = None, writer = None):
        """
        The constructor for Peer

        :type download_manager: DownloadManager
        """
        self.download_manager = download_manager

        self.model = list()

        self.am_choking = False #this is set to false for testing purposes change to true later
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False

        self.curr_piece = None

        self.pending_requests = list()
        self.blocks_to_upload = collections.deque()

        self.reader = reader
        self.writer = writer

        if (reader, writer) == (None, None): # If this client is the initiator
            await self.initialize_connection(peer_ip, peer_port, self.download_manager.downloader_id, peer_id)
        else: # If this client is the recipient
            await self.send_handshake(self.download_manager.downloader_id)
        # await self.writer.drain()

        await self.send_bitfield_msg()

        self.receive_loop_task = asyncio.create_task(self.recv_loop())

        self.request_loop_task = None # will contain a task for request_loop when an un-choke happens
        self.upload_loop_task = None


    async def initialize_connection(self, peer_ip, peer_port, downloader_id, peer_id):
        await self.initialize_stream(peer_ip, peer_port)
        await self.send_handshake(downloader_id)
        await self.accept_handshake(peer_id)


    async def initialize_stream(self, peer_ip, peer_port):
        # creates an asynchronous connection
        self.reader, self.writer = await asyncio.open_connection(host=peer_ip, port=peer_port, limit=1)


    async def send_handshake(self, downloader_id):
        # begin handshake with format: <protocol str len> <protocol str> <8 bytes reserved> <info_hash> <my_id>
        handshake = len(PROTOCOL_IDENTIFIER).to_bytes(1, "big") + PROTOCOL_IDENTIFIER.encode() + bytes(8) + bytes.fromhex(self.download_manager.meta_info.infohash) + downloader_id.encode()
        self.writer.write(handshake)


    async def accept_handshake(self, peer_id):
        # receive and catalog recipient handshake
        len_protocol_str = int.from_bytes((await self.reader.read(1)), "big")
        protocol_str = (await self.reader.read(len_protocol_str)).decode()
        await self.reader.read(8)
        peer_info_hash = await self.reader.read(20)
        recv_peer_id = (await self.reader.read(20)).decode()
        if protocol_str == "BitTorrent protocol":
            if True:  # peer_info_hash == bytes.fromhex(self.download_manager.meta_info.infohash):
                if recv_peer_id == peer_id:
                    logging.debug(f"{self.download_manager.downloader_id} has accepted the handshake")
                    return
        self.writer.close()
        await self.writer.wait_closed()
        asyncio.current_task().cancel()


    async def message_handler(self, length, message_id, payload, q):
        match message_id:
            case 0: # "choke"
                self.peer_choking = True
                await self.return_pending_requests()
            case 1: # "un-choke"
                self.peer_choking = False
                self.request_loop_task = asyncio.create_task(self.request_loop())
            case 2: # "interested"
                self.peer_interested = True
            case 3: # "not interested"
                self.peer_interested = False
            case 4: # "have"
                if int.from_bytes(payload, "big") > (len(self.download_manager.piece_list) - 1):
                    pass # implement connection shutdown/ blacklist for malicious peers
                await self.update_model(self.download_manager.piece_list[int.from_bytes(payload, "big")])
                self.download_manager.priority_list_changes_counter += 1
            case 5: # "bitfield"
                flags = BitArray(bytes=payload, length=self.download_manager.meta_info.pieces)
                index = 0
                for flag in flags.bin:
                    if flag == '1':
                        await self.update_model(self.download_manager.piece_list[index])
                    index += 1
                self.download_manager.priority_list_changes_counter += len(flags)
                self.request_loop_task = asyncio.create_task(self.request_loop()) # This is temporary
                self.upload_loop_task = asyncio.create_task(self.upload_loop()) # This is temporary
            case 6: # "request"
                if not self.am_choking:
                    self.blocks_to_upload.append((int.from_bytes(payload[0:4], "big"), PMD.Block(int.from_bytes(payload[4:8], "big"), int.from_bytes(payload[8:], "big"))))
            case 7: # "block"
                piece_index = int.from_bytes(payload[0:4], "big")
                begin = int.from_bytes(payload[4:8], "big")
                data = payload[8:]
                block = PMD.Block(begin, (length - 8)) # minus 8 bits for the piece index and begin
                if not (piece_index, block) in self.pending_requests:
                    # TODO: implement strike system to disconnect from malicious peers
                    return
                await (self.download_manager.write_to_file(begin, data, piece_index))
                self.pending_requests.remove((piece_index, block))
            case 8: # "cancel"
                pass
                # TODO: handle close messages in uploader as separate task, should get request info from self.blocks_to_upload to cancel it
        await q.get()


    async def message_interpreter(self):
        length = (await self.reader.read(4))
        # while len(length) == 0:
        #     length = (await self.reader.read(4))
        #     await asyncio.sleep(0.1)
        length = int.from_bytes(length, 'big')
        if length == 0:
            message_id = "-1"
            payload = ""
        else:
            message_id = int.from_bytes(await self.reader.read(1), 'big')
            if length == 1:
                payload = ""
            else:
                payload = await self.reader.read(length - 1)

        return (length - 1), message_id, payload


    async def send_have_msg(self, piece_index):
        message = HAVE_MESSAGE_LENGTH + HAVE_MESSAGE_ID + piece_index.to_bytes(4, 'big')
        self.writer.write(message)
        await self.writer.drain()


    async def send_bitfield_msg(self):
        message = (BITFIELD_MESSAGE_BASE_LENGTH + len(self.download_manager.bitfield.tobytes())).to_bytes(4, 'big') + BITFIELD_MESSAGE_ID + self.download_manager.bitfield.tobytes()
        self.writer.write(message)
        await self.writer.drain()


    async def upload_loop(self):
        # TODO: un-assign and reassign task according to peer_interested and am_choking remember to clear blocks_to_upload on choke
        while True:
            while self.blocks_to_upload.__len__() == 0:
                await asyncio.sleep(0.5)
            (piece_index, block) = self.blocks_to_upload.popleft()
            message = (PIECE_MESSAGE_BASE_LENGTH + block.length).to_bytes(4, 'big') + PIECE_MESSAGE_ID + piece_index.to_bytes(4, 'big') + block.begin.to_bytes(4, 'big') + await self.download_manager.read_from_file(piece_index, block)
            self.writer.write(message)
            await self.writer.drain()


    async def request_loop(self):
        while True:
            self.curr_piece = await self.select_piece()
            if self.curr_piece is None:
                await asyncio.sleep(0.5)
                continue
            while self.curr_piece.remaining_blocks:
                curr_block = await self.curr_piece.select_block()
                while len(self.pending_requests) >= PENDING_REQUEST_MAXIMUM:
                    await asyncio.sleep(1)
                await self.request_block(curr_block)
            self.download_manager.priority_list.remove(self.curr_piece)
            

    async def request_block(self, block):
        message = REQUEST_MESSAGE_LENGTH + REQUEST_MESSAGE_ID + self.curr_piece.piece_index.to_bytes(4, 'big') + block.begin.to_bytes(4, 'big') + block.length.to_bytes(4, 'big')
        self.writer.write(message)
        await self.writer.drain()
        self.pending_requests.append((self.curr_piece.piece_index, block))


    async def select_piece(self):
        for piece in self.download_manager.priority_list:
            if piece in self.model:
                self.am_interested = True
                logging.debug(f"Piece number {piece.piece_index} has been selected")
                return piece
        return None


    async def return_pending_requests(self):
        for piece_index, block in self.pending_requests:
            curr_piece = self.download_manager.piece_list[piece_index]
            if not curr_piece.remaining_blocks:
                self.download_manager.priority_list.append(curr_piece)
            curr_piece.return_block(block)
        self.pending_requests.clear()


    async def recv_loop(self):
        q = asyncio.Queue(5)
        while True:
            length, message_id, payload = await self.message_interpreter()
            task = asyncio.create_task(self.message_handler(length, message_id, payload, q))
            await q.put(task)


    async def update_model(self, piece):
        if not piece in self.model:
            self.model.append(piece)
            piece.amount_in_swarm += 1
