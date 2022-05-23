from kivy.clock import Clock
from kivy.uix.image import Image
from kivy.properties import NumericProperty
from kivy.uix.label import Label
from functools import partial


class ScalingText(Label):
    text_height_multiplier = NumericProperty(0.7)

    def __init__(self, **kwargs):
        super(ScalingText, self).__init__(**kwargs)
        self.shorten = False

    def on_texture_size(self, widget, width):
        self.texture_update()
        # increase font size until it either reaches desired percentage of text height or can't fit in the boundaries
        m = 0.3
        self.font_size = self.height * m
        print(f"font size: {self.font_size}, texture size: {self.texture_size},size: {self.size}, m: {m}\n")
        self.texture_update()
        while (m < self.text_height_multiplier and self.texture_size[0] < self.width): # or self.anchors["Start"][1] != self.anchors["End"][1]:
            m = m + 0.05
            self.font_size = self.height * m
            self.texture_update()

        print(f"new font size: {self.font_size}, texture size: {self.texture_size}, size: {self.size}, m: {m}\n")
