import asyncio
import queue
import socket

import bitstring
from bitstring import BitArray # docs: https://bitstring.readthedocs.io/en/latest/
import Parallel_Download_Manager as PMD
import collections # https://docs.python.org/3/library/collections.html
import logging
import numpy as np


PROTOCOL_IDENTIFIER = "BitTorrent protocol"
REQUEST_MESSAGE_ID = (6).to_bytes(1, 'big')
REQUEST_MESSAGE_LENGTH = (13).to_bytes(4, 'big')

PIECE_MESSAGE_BASE_LENGTH = 9
PIECE_MESSAGE_ID = (7).to_bytes(1, 'big')

HAVE_MESSAGE_LENGTH = (5).to_bytes(4, 'big')
HAVE_MESSAGE_ID = (4).to_bytes(1, 'big')

BITFIELD_MESSAGE_BASE_LENGTH = 1
BITFIELD_MESSAGE_ID = (5).to_bytes(1, 'big')

CHOKE_MESSAGE_LENGTH = (1).to_bytes(4, 'big')

INTERESTED_MESSAGE_LENGTH = (1).to_bytes(4, 'big')

# EXPAND: determine dynamically
DEFAULT_BLOCK_LEN = 16000
PENDING_REQUEST_MAXIMUM = 5


logging.getLogger("asyncio").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


@PMD.Async_init
class Peer:
    upload_loop_task: asyncio.Task
    reader: asyncio.streams.StreamReader

    async def __init__(self, download_manager, peer_id, peer_ip = None, peer_port = None, reader = None, writer = None):
        """
        The constructor for Peer

        :type download_manager: DownloadManager
        """
        self.peer_id = peer_id

        self.download_manager = download_manager

        self.model = list()

        self._am_choking = True
        self._am_interested = False
        self._peer_choking = True
        self._peer_interested = False

        self.client_upload_rate = 0
        self.upload_rolling_window = collections.deque([0,0], maxlen=2)
        self.client_download_rate = 0
        self.download_rolling_window = collections.deque([0,0], maxlen=2)

        self.pending_requests = list()
        self.blocks_to_upload = collections.deque()

        self.optimistic_unchoke_weight = 0

        self.reader = reader
        self.writer = writer

        if (reader, writer) == (None, None): # If this client is the initiator
            await self.initialize_connection(peer_ip, peer_port, peer_id)
        else: # If this client is the recipient
            await self.send_handshake()
        # await self.writer.drain()

        await self.send_bitfield_msg()

        self.receive_loop_task = asyncio.create_task(self.recv_loop())
        self.request_loop_task = None # will contain a task for request_loop when an un-choke happens
        self.upload_loop_task = None

        self.average_rate_task = asyncio.create_task(self.average_up_dw_rate())


    async def initialize_connection(self, peer_ip, peer_port, peer_id):
        await self.initialize_stream(peer_ip, peer_port)
        await self.send_handshake()
        await self.accept_handshake(peer_id)


    async def initialize_stream(self, peer_ip, peer_port):
        # creates an asynchronous connection
        self.reader, self.writer = await asyncio.open_connection(host=peer_ip, port=peer_port, limit=1)


    async def send_handshake(self):
        # begin handshake with format: <protocol str len> <protocol str> <8 bytes reserved> <info_hash> <my_id>
        handshake = len(PROTOCOL_IDENTIFIER).to_bytes(1, "big") + PROTOCOL_IDENTIFIER.encode() + bytes(8) + bytes.fromhex(self.download_manager.meta_info.infohash) + self.download_manager.client_id.encode()
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
                    logging.debug(f"{self.download_manager.client_id} has accepted the handshake")
                    return
        self.writer.close()
        await self.writer.wait_closed()
        asyncio.current_task().cancel()


    async def message_handler(self, length, message_id, payload, q):
        match message_id:
            case 0: # "choke"
                await self.change_peer_choking_state(True)
                await self.return_pending_requests()
            case 1: # "un-choke"
                await self.change_peer_choking_state(False)
            case 2: # "interested"
                await self.change_peer_interested_state(True)
            case 3: # "not interested"
                await self.change_peer_interested_state(False)
            case 4: # "have"
                piece_index = int.from_bytes(payload, "big")
                if piece_index > (len(self.download_manager.piece_list) - 1):
                    return # implement connection shutdown/ blacklist for malicious peers
                await self.update_model(self.download_manager.piece_list[piece_index])
                if self.download_manager.piece_list[piece_index] in self.download_manager.priority_list:
                    self.download_manager.decrease_piece_priority(self.download_manager.piece_list[piece_index])
                if await self.select_piece() is not None:
                    await self.change_am_interested_state(True)
            case 5: # "bitfield"
                flags = BitArray(bytes=payload, length=self.download_manager.meta_info.pieces)
                index = 0
                for flag in flags.bin:
                    if flag == '1':
                        await self.update_model(self.download_manager.piece_list[index])
                    index += 1
                self.download_manager.sort_priority_list()
                if await self.select_piece() is not None:
                    await self.change_am_interested_state(True)
            case 6: # "request"
                if not self._am_choking:
                    self.blocks_to_upload.append((int.from_bytes(payload[0:4], "big"), PMD.Block(int.from_bytes(payload[4:8], "big"), int.from_bytes(payload[8:], "big"))))
            case 7: # "block"
                piece_index = int.from_bytes(payload[0:4], "big")
                begin = int.from_bytes(payload[4:8], "big")
                data = payload[8:]
                block = PMD.Block(begin, (length - 8)) # minus 8 bits for the piece index and begin
                for request in self.pending_requests:
                    if (piece_index, block) == request:
                        block = request[1]
                        break
                else:
                    block = None
                if block is None:
                    pass
                    #strike system goes here too
                elif block.length != len(data):
                    block.requested = False
                    self.pending_requests.remove((piece_index, block))
                    # TODO: implement strike system to disconnect from malicious peers
                else:
                    self.pending_requests.remove((piece_index, block))
                    self.download_rolling_window[0] += block.length
                    q.append(asyncio.create_task(self.download_manager.write_to_file(block, data, piece_index)))
            case 8: # "cancel"
                pass
                # TODO: handle close messages in uploader as separate task, should get request info from self.blocks_to_upload to cancel it


    async def message_interpreter(self):
        msg = await self.reader.read(4)
        length = int.from_bytes(msg, 'big')
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


    async def change_peer_interested_state(self, state):
        if state == self._peer_interested:
            return
        self._peer_interested = state
        if self._peer_interested:
            if self._am_choking:
                self.optimistic_unchoke_weight = 1 if self.model else 3
        else:
            self.optimistic_unchoke_weight = 0


    async def change_peer_choking_state(self, state):
        if state == self._peer_choking:
            return
        self._peer_choking = state
        if not self._peer_choking:
            if self._am_interested:
                self.request_loop_task = asyncio.create_task(self.request_loop())
        else:
            self.request_loop_task.cancel()


    async def change_am_interested_state(self, state):
        if state == self._am_interested:
            return
        self._am_interested = state
        if self._am_interested:
            if not self._peer_choking:
                self.request_loop_task = asyncio.create_task(self.request_loop())
        else:
            self.request_loop_task.cancel()
        message = INTERESTED_MESSAGE_LENGTH + (2 if self._am_interested else 3).to_bytes(1, 'big')
        self.writer.write(message)


    async def change_am_choking_state(self, state):
        self._am_choking = state
        if not self._am_choking:
            self.optimistic_unchoke_weight = 0
            if self._peer_interested:
                if self.upload_loop_task is None or self.upload_loop_task.cancelled():
                    self.upload_loop_task = asyncio.create_task(self.upload_loop())
        else:
            if not (self.upload_loop_task.cancelled() or self.upload_loop_task is None):
                self.upload_loop_task.cancel()
                self.blocks_to_upload.clear()
            if self._peer_interested:
                self.optimistic_unchoke_weight = 1 if self.model else 3
        message = CHOKE_MESSAGE_LENGTH + (0 if self._am_choking else 1).to_bytes(1, 'big')
        self.writer.write(message)


    async def upload_loop(self):
        while True:
            while len(self.blocks_to_upload) == 0:
                await asyncio.sleep(0.5)
            (piece_index, block) = self.blocks_to_upload.popleft()
            message = (PIECE_MESSAGE_BASE_LENGTH + block.length).to_bytes(4, 'big') + PIECE_MESSAGE_ID + piece_index.to_bytes(4, 'big') + block.begin.to_bytes(4, 'big') + await self.download_manager.read_from_file(piece_index, block)
            self.writer.write(message)
            self.upload_rolling_window[0] += len(message)
            self.download_manager.bytes_uploaded += block.length
            await self.writer.drain()


    async def request_loop(self):
        while True:
            curr_piece = await self.select_piece()
            if curr_piece is None:
                uninterested = asyncio.create_task(self.change_am_interested_state(False))
                await uninterested
            logging.debug(f"Piece number {curr_piece.piece_index} has been selected")
            while True:
                while len(self.pending_requests) >= PENDING_REQUEST_MAXIMUM:
                    await asyncio.sleep(1)
                curr_block = curr_piece.select_block()
                if curr_block is None:
                    break
                await self.request_block(curr_piece, curr_block)
            

    async def request_block(self, curr_piece, block):
        message = REQUEST_MESSAGE_LENGTH + REQUEST_MESSAGE_ID + curr_piece.piece_index.to_bytes(4, 'big') + block.begin.to_bytes(4, 'big') + block.length.to_bytes(4, 'big')
        self.pending_requests.append((curr_piece.piece_index, block))
        block.requested = True
        self.writer.write(message)
        await self.writer.drain()


    async def select_piece(self):
        for piece in self.download_manager.priority_list:
            if piece.select_block() is not None:
                if piece in self.model:
                    return piece
        return None


    async def return_pending_requests(self):
        for piece_index, block in self.pending_requests:
            block.requested = False
        self.pending_requests.clear()


    async def recv_loop(self):
        q = list()
        q.append(asyncio.create_task(self.recv_tasks_cleanup(q)))
        while True:
            length, message_id, payload = await self.message_interpreter()
            await self.message_handler(length, message_id, payload, q)


    async def recv_tasks_cleanup(self, q):
        while True:
            await asyncio.sleep(0.3)
            for task in q:
                if task.done():
                    q.remove(task)


    async def update_model(self, piece):
        if not self.model:
            self.optimistic_unchoke_weight = 1
        if not piece in self.model:
            self.model.append(piece)
            piece.amount_in_swarm += 1


    async def average_up_dw_rate(self):
        while True:
            await asyncio.sleep(10)
            self.client_download_rate = np.average(self.download_rolling_window)
            self.client_upload_rate = np.average(self.upload_rolling_window)
            self.upload_rolling_window.appendleft(0)
            self.download_rolling_window.appendleft(0)


    def __lt__(self, other):
        if self.download_manager.seeder_mode:
            return self.client_upload_rate < other.client_upload_rate
        else:
            return self.client_download_rate < other.client_download_rate


    def __eq__(self, other):
        if self.download_manager.seeder_mode:
            return self.client_upload_rate == other.client_upload_rate
        else:
            return self.client_download_rate == other.client_download_rate


    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)


    def __ge__(self, other):
        return not self.__lt__(other) or self.__eq__(other)
