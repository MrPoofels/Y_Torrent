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
from kivy.graphics import Color, Rectangle


class HomeScreen(BoxLayout):
    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.layout_content.bind(minimum_height=self.layout_content.setter('height'))
    # with StackLayout.canvas.before:
    #     Color(0, 1, 0, 1)  # green; colors range from 0-1 instead of 0-255
    #     self.rect = Rectangle(size=StackLayout.size, pos=StackLayout.pos)
    #
    # def update_rect(self, instance, value):
    #     instance.rect.pos = instance.pos
    #     instance.rect.size = instance.size
    #
    # # listen to size and position changes
    # StackLayout.bind(pos=update_rect, size=update_rect)


class YTorrentApp(App):
    tasks: list[asyncio.Task] = list()

    def build(self):
        return HomeScreen()

    def app_func(self):
        """This will run methods asynchronously and then block until they
        are finished
        """
        self.tasks.append(asyncio.create_task(self.waste_time_freely()))

        async def run_wrapper():
            await self.async_run(async_lib='asyncio')
            print('App done')
            for task in self.tasks:
                task.cancel()

        return asyncio.gather(run_wrapper(), *self.tasks)


if __name__ == '__main__':
    Builder.load_file('C:\\Users\\Yahav\\PycharmProjects\\Y_Torrent\\GUI\\ytorrent.kv')
    YTorrentApp().run()
    # asyncio.run(YTorrentApp().app_func(), debug=2)
