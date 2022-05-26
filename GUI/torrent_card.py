import kivy.uix.progressbar
from kivy.graphics.texture import texture_create_from_data
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.stacklayout import StackLayout
from kivy.properties import NumericProperty, StringProperty, ObjectProperty, AliasProperty
from kivy.graphics import *
from GUI import ScalingText
from Parallel_Download_Manager import DownloadManager


class TorrentCard(StackLayout):
    download_manager: DownloadManager
    # download_manager = ObjectProperty()
    # test = AliasProperty(se)
    name = StringProperty('[anchor=Start]Spirited Away (1080p)[anchor=End]')
    eta = StringProperty('[anchor=Start]ETA: 2D 7H 30M[anchor=End]')
    progress_bar = ObjectProperty()
    download_speed = NumericProperty(0)
    upload_speed = NumericProperty(0)
    peers = NumericProperty(0)
    seeds = NumericProperty(0)

    def __init__(self, download_manager, **kwargs):
        super(TorrentCard, self).__init__(**kwargs)
        self.download_manager = download_manager
        self.test = AliasProperty(self.get_name, self.set_name, bind=['name'])
        
    def get_name(self):
        return f"[anchor=Start]{self.download_manager.meta_info.name}[anchor=End]"
        
    def set_name(self, value):
        return True
