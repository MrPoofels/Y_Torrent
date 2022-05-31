import asyncio
import torf
from torf import Torrent
import Torrents_Manager
import socket
import _sha1
import logging
import collections
import bencodepy
import kivy
from kivy.config import Config
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.lang.builder import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.stacklayout import StackLayout
from kivy.graphics import Color, Rectangle, PushMatrix, PopMatrix, Scale
from kivy.uix.image import Image
from GUI import HomeScreen
from GUI import TorrentCard
from GUI import IconButton
from kivy.uix.label import Label

logging.getLogger("asyncio").setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


class YTorrentApp(App):
	tasks: list[asyncio.Task] = list()
	
	
	def build(self):
		return HomeScreen()
	
	def app_func(self, *starting_tasks):
		"""This will run methods asynchronously and then block until they
		are finished
		"""
		for task in starting_tasks:
			self.tasks.append(task)
		
		async def run_wrapper():
			await self.async_run(async_lib='asyncio')
			print('App done')
			for task in self.tasks:
				task.cancel()
		
		return asyncio.gather(run_wrapper(), *self.tasks)
	
	def schedule_task(self, coroutine):
		self.tasks.append(asyncio.create_task(coroutine))
	
	async def add_torrent(self):
		print('blah')
		download_manager = await Torrents_Manager.create_new_torrent('-YT0015-547297019273', 'C:\\Users\\Yahav\\PycharmProjects\\Y_Torrent\\Test_files\\Morbius [2022] YG.torrent', 'C:\\Users\\Yahav\\Desktop')
		self.root.cards_list_content.add_widget(TorrentCard(download_manager))
	
	async def pause_all(self):
		await asyncio.gather(*[torrent.pause_all() for torrent in Torrents_Manager.torrents_list])
		
	async def unpause_all(self):
		await asyncio.gather(*[torrent.unpause_all() for torrent in Torrents_Manager.torrents_list])
		

if __name__ == '__main__':
	# asyncio.run(temp_start(), debug=2)
	Builder.load_file('C:\\Users\\Yahav\\PycharmProjects\\Y_Torrent\\GUI\\ytorrent.kv')
	app = YTorrentApp()
	loop = asyncio.get_event_loop()
	loop.run_until_complete(YTorrentApp().app_func(Torrents_Manager.__start()))
