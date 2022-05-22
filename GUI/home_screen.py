from kivy.uix.widget import Widget
from kivy.uix.boxlayout import BoxLayout
from GUI import TorrentCard


class HomeScreen(BoxLayout):
    def __init__(self, **kwargs):
        super(HomeScreen, self).__init__(**kwargs)
        self.cards_list_content.bind(minimum_height=self.cards_list_content.setter('height'))
        # self.cards_list_content.add_widget(TorrentCard())
        # self.cards_list_content.add_widget(TorrentCard())
