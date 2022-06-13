import logging
from typing import Iterable, Any, List

import bencodepy
import asyncio
import Parallel_Download_Manager as PMD
import torf
import random
import socket

PROTOCOL_ID = (0x41727101980).to_bytes(8, 'big', signed=False)


class TrackerCommunication:
	def __init__(self, trackers, download_manager):
		"""

		Args:
			trackers (torf._utils.URL):
		
		"""
		super().__init__()
		self.download_manager = download_manager
		self.seeders = 0
		self.leechers = 0
		self.interval = 10
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.socket.connect((trackers[3][0].hostname, trackers[3][0].port))
		self.port = trackers[3][0].port
		self.connection_id = None
		self.socket.settimeout(15)
		self.connection_cycle_task = asyncio.create_task(self.connection_cycle())
		self.announce_cycle_task = asyncio.create_task(self.announce_cycle())
	
	async def connect(self, retries=0):
		self.socket.settimeout(15 * (2 ^ retries))
		transaction_id = (random.getrandbits(32))
		transaction_id = transaction_id.to_bytes(4, 'big', signed=False)
		msg = PROTOCOL_ID + (0).to_bytes(4, 'big', signed=False) + transaction_id
		self.socket.send(msg)
		try:
			response = self.socket.recv(16)
			if int.from_bytes(response[:4], 'big', signed=False) == 0:
				if response[4:8] == transaction_id:
					self.connection_id = int.from_bytes(response[8:], 'big', signed=False)
				else:
					print(':(')
		except socket.timeout:
			print('timeout')
			if retries == 8:
				raise BaseException
			await self.connect(retries + 1)
	
	def announce(self, event, retries=0):
		"""

		Args:
			download_manager (PMD.DownloadManager):
		"""
		self.socket.settimeout(15 * (2 ^ retries))
		transaction_id = (random.getrandbits(32)).to_bytes(4, 'big', signed=False)
		num_want = 25
		msg = bytearray()
		msg.extend(
			self.connection_id.to_bytes(8, 'big', signed=False)
			+ (1).to_bytes(4, 'big', signed=False)
			+ transaction_id + bytes.fromhex(self.download_manager.meta_info.infohash)
			+ self.download_manager.client_id.encode()
			+ self.download_manager.bytes_downloaded.to_bytes(8, 'big', signed=False)
			+ (self.download_manager.meta_info.size - self.download_manager.bytes_downloaded).to_bytes(8, 'big', signed=False)
			+ self.download_manager.bytes_uploaded.to_bytes(8, 'big', signed=False)
			+ event.to_bytes(4, 'big', signed=False) + (0).to_bytes(4, 'big', signed=False)
			+ (0).to_bytes(4, 'big', signed=False) + num_want.to_bytes(4, 'big', signed=False)
			+ self.port.to_bytes(2, 'big', signed=False))
		self.socket.send(msg)
		try:
			response = self.socket.recv(20 + 6 * num_want)
			if int.from_bytes(response[:4], 'big', signed=False) == 1:
				if response[4:8] == transaction_id:
					self.interval = int.from_bytes(response[8:12], 'big', signed=False)
					self.leechers = int.from_bytes(response[12:16], 'big', signed=False)
					self.seeders = int.from_bytes(response[16:20], 'big', signed=False)
					peer_info_list = list()
					response = response.removeprefix(response[:20])
					peers = [response[6*i:6*i+6] for i in range(self.leechers + self.seeders)]
					for peer in peers:
						if len(peer) < 6:
							continue
						ip = '.'.join([str(num) for num in peer[:4:1]])
						port = int.from_bytes(peer[4:6], 'big', signed=False)
						peer_info_list.append((ip, port))
					logging.info(f"received announce response")
					return peer_info_list
		except socket.timeout:
			if retries == 8:
				raise BaseException
			self.announce(event, retries + 1)
			
	async def announce_cycle(self):
		while True:
			peer_info_list = self.announce(0)
			await self.download_manager.extend_peer_list(peer_info_list)
			await asyncio.sleep(self.interval)
	
	async def connection_cycle(self):
		while True:
			await self.connect()
			await asyncio.sleep(60)
