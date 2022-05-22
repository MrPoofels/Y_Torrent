from kivy.clock import Clock
from kivy.uix.image import Image
from kivy.properties import NumericProperty
from kivy.uix.label import Label
from functools import partial


class ScalingText(Label):
    text_height_multiplier = NumericProperty(0.7)

    def __init__(self, **kwargs):
        super(ScalingText, self).__init__(**kwargs)
        Clock.schedule_once(partial(self.on_width, self))

    def on_width(self, widget, width):
        self.texture_update()
        if self.texture_size[0] == 100 or self.size[0] == 0: #or self.size[1] != [42.0]:
            return
        # for long names, reduce font size until it fits in its self
        m = self.text_height_multiplier
        self.font_size = self.height * m
        print(f"font size: {self.font_size}, texture size: {self.texture_size},size: {self.size}, m: {m}")
        self.texture_update()
        while m > 0.3 and self.texture_size[0] > self.width:
            m = m - 0.05
            self.font_size = self.height * m
            self.texture_update()
        print(f"new font size: {self.font_size}, texture size: {self.texture_size}, size: {self.size}, m: {m}")
        # self.text_size = self.size
