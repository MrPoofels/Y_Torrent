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
    def __init__(self, file_path, file_size, download_manager, start_byte):
        self.download_manager = download_manager
        self.file_size = file_size
        self.start_byte = start_byte

        try:
            self.file = open(file_path, 'xb+')
        except FileExistsError or FileNotFoundError:
            self.file = open(file_path, 'rb+')
            self.file.seek(0)
        if not self.file.seek(0, 2) == self.file_size:
            self.file.seek(self.file_size - 1)
            self.file.write(b"\0")
            self.file.seek(0)

    async def write_to_file(self, begin, data):
        """

        Args:
            begin:
            data (bytearray):
        """
        self.file.seek(begin)
        file_data = data[:self.file_size]
        self.file.write(file_data)
        logging.info(f"wrote {len(file_data)} bytes to {self.file.name}")
        return data[len(file_data):]

    async def read_from_file(self, begin, length):
        self.file.seek(begin)
        data = self.file.read(length)
        return data
