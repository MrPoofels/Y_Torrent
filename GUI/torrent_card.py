import kivy.uix.progressbar
from kivy.graphics.texture import texture_create_from_data
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.stacklayout import StackLayout
from kivy.properties import NumericProperty, StringProperty, ObjectProperty
from kivy.graphics import *
from GUI import ScalingText


class TorrentCard(StackLayout):
    name = StringProperty('Spirited Away (1080p)')
    eta = StringProperty('ETA: 2D 7H 30M')
    progress_bar = ObjectProperty()
    download_speed = NumericProperty(0)
    upload_speed = NumericProperty(0)
    peers = NumericProperty(0)
    seeds = NumericProperty(0)

    def __init__(self, **kwargs):
        super(TorrentCard, self).__init__(**kwargs)
