########################################
# Pinout image builder - Pin class
# Louis Barbier
# MIT License
########################################

class Pin:

    def __init__(self, cx, cy, r, number, side, displayed = True):
        self.cx = cx
        self.cy = cy
        self.r = r
        self.number = number
        self.side = side
        self.displayed = displayed
        self.functions = []

    def add_function(self, name, color):
        self.functions.append({
            'name': name,
            'color': color
        })
