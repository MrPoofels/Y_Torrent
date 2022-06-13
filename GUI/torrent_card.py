import logging

import kivy.uix.progressbar
from kivy.graphics.texture import texture_create_from_data
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.stacklayout import StackLayout
from kivy.properties import NumericProperty, StringProperty, ObjectProperty, AliasProperty
from kivy.graphics import *
from GUI import ScalingText
from Parallel_Download_Manager import DownloadManager
import asyncio
import datetime


def initialize_card(ins):
	ins.name = f"[anchor=Start]{ins.download_manager.meta_info.name}[anchor=End]"
	download_speed = 0
	upload_speed = 0
	for peer in ins.download_manager.peer_list:
		download_speed += peer.client_download_rate
		upload_speed += peer.client_upload_rate
	ins.download_speed = f"[anchor=Start]Download speed: {int(download_speed/1000)} kb/s[anchor=End]"
	ins.upload_speed = f"[anchor=Start]Upload speed: {int(upload_speed/1000)} kb/s[anchor=End]"
	if download_speed == 0:
		ins.eta = f'[anchor=Start]ETA: N/A'
	else:
		ins.eta = f'[anchor=Start]ETA: {datetime.timedelta(seconds=int(ins.download_manager.meta_info.size / download_speed))}[anchor=End]'
	ins.leechers = f"[anchor=Start]Leechers: {ins.download_manager.tracker_communication.leechers}[anchor=End]"
	ins.seeders = f"[anchor=Start]Seeders: {ins.download_manager.tracker_communication.seeders}[anchor=End]"
	ins.percent = f"[anchor=Start]{int(ins.download_manager.bytes_downloaded / ins.download_manager.meta_info.size * 100)}%[anchor=End]"


class TorrentCard(StackLayout):
	download_manager: DownloadManager
	name = StringProperty()
	eta = StringProperty()
	download_speed = StringProperty()
	upload_speed = StringProperty()
	leechers = StringProperty()
	seeders = StringProperty()
	percent = StringProperty()
	
	def __init__(self, download_manager, **kwargs):
		self.download_manager = download_manager
		initialize_card(self)
		super(TorrentCard, self).__init__(**kwargs)
		self.update_card_task = asyncio.create_task(update_card(self))


async def update_card(card):
	while True:
		await asyncio.sleep(2)
		card.name = f"[anchor=Start]{card.download_manager.meta_info.name}[anchor=End]"
		download_speed = 0
		upload_speed = 0
		for peer in card.download_manager.peer_list:
			download_speed += peer.client_download_rate
			upload_speed += peer.client_upload_rate
		card.download_speed = f"[anchor=Start]Download speed: {int(download_speed/1000)} kb/s[anchor=End]"
		card.upload_speed = f"[anchor=Start]Upload speed: {int(upload_speed/1000)} kb/s[anchor=End]"
		if download_speed == 0:
			card.eta = f'[anchor=Start]ETA: N/A[anchor=End]'
		else:
			card.eta = f'[anchor=Start]ETA: {datetime.timedelta(seconds=int(card.download_manager.meta_info.size / download_speed))}[anchor=End]'
		card.leechers = f"[anchor=Start]Leechers: {card.download_manager.tracker_communication.leechers}[anchor=End]"
		card.seeders = f"[anchor=Start]Seeders: {card.download_manager.tracker_communication.seeders}[anchor=End]"
		card.percent = f"[anchor=Start]{int(card.download_manager.bytes_downloaded / card.download_manager.meta_info.size * 100)}%[anchor=End]"
		logging.info(f"updated card of {card.download_manager.meta_info.name}")
		download_speed = 0
		upload_speed = 0
		for peer in card.download_manager.peer_list:
			download_speed += peer.client_download_rate
			upload_speed += peer.client_upload_rate
		logging.debug(f"download speed: {download_speed}")
