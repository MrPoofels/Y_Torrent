class Block:
    def __init__(self, begin, length):
        self.begin = begin
        self.length = length

    def __eq__(self, other):
        return self.begin == other.begin and self.length == other.length
