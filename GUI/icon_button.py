from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior


class IconButton(ButtonBehavior, Image):
	def __init__(self, **kwargs):
		super(IconButton, self).__init__(**kwargs)
