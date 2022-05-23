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
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.lang.builder import Builder
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.stacklayout import StackLayout
from kivy.graphics import Color, Rectangle, PushMatrix, PopMatrix, Scale
from kivy.uix.image import Image
from GUI import HomeScreen
from GUI import TorrentCard
from kivy.uix.label import Label


async def temp_start():
    await Torrents_Manager.create_new_torrent('Poofels',
                                              'C:\\Users\\Yahav\\Desktop\\Morbius.2022.1080p.WEB-DL.x264.AAC-EVO [IPT].torrent',
                                              'C:\\Users\\Yahav\\Desktop')
    await Torrents_Manager.__start()


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


if __name__ == '__main__':
    asyncio.run(temp_start())
    # Builder.load_file('C:\\Users\\Yahav\\PycharmProjects\\Y_Torrent\\GUI\\ytorrent.kv')
    # YTorrentApp().run()
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(YTorrentApp().app_func())
