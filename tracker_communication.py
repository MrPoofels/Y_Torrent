from typing import Iterable, Any, List

import bencodepy
import asyncio
import Parallel_Download_Manager as PMD
import torf
import random
import socket

PROTOCOL_ID = (0x41727101980).to_bytes(8, 'big', signed=False)


class TrackerCommunication:
	def __init__(self, trackers):
		"""

		Args:
			trackers (torf._utils.URL):
		
		"""
		super().__init__()
		# for tracker in trackers:
		# 	if tracker[0].scheme == 'udp':
		# 		self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		# 		self.socket.connect((tracker[0].hostname, tracker[0].port))
		# 		self.port = tracker[0].port
		# 		break
		self.seeders = 0
		self.leechers = 0
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.socket.connect((trackers[1][0].hostname, trackers[1][0].port))
		self.port = trackers[1][0].port
		self.connection_id = None
		self.socket.settimeout(15)
	
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
	
	def announce(self, download_manager, event, retries=0):
		"""

		Args:
			download_manager (PMD.DownloadManager):
		"""
		self.socket.settimeout(15 * (2 ^ retries))
		transaction_id = (random.getrandbits(32)).to_bytes(4, 'big', signed=False)
		num_want = 50
		msg = bytearray()
		msg.extend(
			self.connection_id.to_bytes(8, 'big', signed=False)
			+ (1).to_bytes(4, 'big', signed=False)
			+ transaction_id + bytes.fromhex(download_manager.meta_info.infohash)
			+ download_manager.client_id.encode()
			+ download_manager.bytes_downloaded.to_bytes(8, 'big', signed=False)
			+ (download_manager.meta_info.size - download_manager.bytes_downloaded).to_bytes(8, 'big', signed=False)
			+ download_manager.bytes_uploaded.to_bytes(8, 'big', signed=False)
			+ event.to_bytes(4, 'big', signed=False) + (0).to_bytes(4, 'big', signed=False)
			+ (0).to_bytes(4, 'big', signed=False) + num_want.to_bytes(4, 'big', signed=False)
			+ self.port.to_bytes(2, 'big', signed=False))
		self.socket.send(msg)
		try:
			response = self.socket.recv(20 + 6 * num_want)
			if int.from_bytes(response[:4], 'big', signed=False) == 1:
				if response[4:8] == transaction_id:
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
					return peer_info_list
		except socket.timeout:
			if retries == 8:
				raise BaseException
			self.announce(download_manager, event, retries + 1)
