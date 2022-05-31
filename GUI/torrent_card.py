import kivy.uix.progressbar
from kivy.graphics.texture import texture_create_from_data
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.stacklayout import StackLayout
from kivy.properties import NumericProperty, StringProperty, ObjectProperty, AliasProperty
from kivy.graphics import *
from GUI import ScalingText
from Parallel_Download_Manager import DownloadManager
import numpy as np


class TorrentCard(StackLayout):
    download_manager: DownloadManager
    name = StringProperty()
    eta = StringProperty()
    download_speed = NumericProperty(0)
    upload_speed = NumericProperty(0)
    leechers = NumericProperty(0)
    seeders = NumericProperty(0)
    percent = NumericProperty(0)

    def __init__(self, download_manager, **kwargs):
        super(TorrentCard, self).__init__(**kwargs)
        self.download_manager = download_manager
        self.name = f"[anchor=Start]{self.download_manager.meta_info.name}[anchor=End]"
        self.download_speed = np.sum([peer.client_download_rate for peer in self.download_manager.peer_list])
        self.upload_speed = np.sum([peer.client_upload_rate for peer in self.download_manager.peer_list])
        self.eta = f'[anchor=Start]ETA: {self.download_manager.meta_info.size / self.download_speed}[anchor=End]'
        self.leechers = self.download_manager.tracker_communication.leechers
        self.seeders = self.download_manager.tracker_communication.seeders
        self.percent = self.download_manager.bytes_downloaded / self.download_manager.meta_info.size
    
    def pause(self):
        self.download_manager.pause_all()
        
    def unpause(self):
        self.download_manager.unpause_all()
