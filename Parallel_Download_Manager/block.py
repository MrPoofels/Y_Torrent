class Block:
    def __init__(self, begin, length):
        self.begin = begin
        self.length = length
        self.requested = False

    def __eq__(self, other):
        return self.begin == other.begin and self.length == other.length
