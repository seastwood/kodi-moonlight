#!/usr/bin/env python3
"""Draw the menu tile this add-on shows before its application is installed.

The real icon belongs to whoever makes the application and is not
redistributed here, the same rule the rest of this console follows for box art
and console logos: it is copied off your own machine once the application that
owns it is installed. Until then the menu still needs something, and that is
what this draws.

Matched to the icons kodi-retrobox ships rather than invented: 256 square, a
filled disc of #121634 inside a #46E8F4 ring, outer radius 120 and the ring 24
thick, hard edges and no anti-aliasing -- two colours and transparency, which
is what every other tile on that menu is made of.

Run it with the name of what to draw. It is here so the artwork can be redrawn
rather than only inherited.
"""
import sys

from PIL import Image

SIZE = 256
MID = SIZE // 2
OUTER = 120
RING = 24
CYAN = (70, 232, 244, 255)
DARK = (18, 22, 52, 255)
CLEAR = (0, 0, 0, 0)


def disc():
    """The ring and its dark middle, which every tile starts from."""
    image = Image.new("RGBA", (SIZE, SIZE), CLEAR)
    pixels = image.load()
    for y in range(SIZE):
        for x in range(SIZE):
            # Pixel centres, so the circle is symmetric about the middle
            # rather than a pixel wider on one side.
            dx, dy = x - MID + 0.5, y - MID + 0.5
            away = (dx * dx + dy * dy) ** 0.5
            if away <= OUTER - RING:
                pixels[x, y] = DARK
            elif away <= OUTER:
                pixels[x, y] = CYAN
    return image


def moon(image):
    """A crescent: one disc with another taken out of it, offset.

    Moonlight's own idea of itself, drawn here rather than copied. The old
    tile put this over a dark rectangle that was invisible against a dark
    menu, and outside the ring every other tile has.
    """
    pixels = image.load()
    for y in range(SIZE):
        for x in range(SIZE):
            dx, dy = x - MID + 0.5, y - MID + 0.5
            if (dx * dx + dy * dy) ** 0.5 > OUTER - RING - 4:
                continue
            full = (dx * dx + (dy + 4) * (dy + 4)) ** 0.5 <= 66
            bite = ((dx - 30) ** 2 + (dy + 16) ** 2) ** 0.5 <= 58
            if full and not bite:
                pixels[x, y] = CYAN
    return image


def download(image):
    """An arrow onto a line: this is here, and not installed yet.

    Deliberately not a logo. What it replaced was a speedometer, which says
    nothing about Steam to anybody, and the tile it stands in for is one the
    add-on overwrites with Valve's own icon the moment Steam is installed.
    """
    pixels = image.load()

    def block(x0, y0, x1, y1):
        for y in range(max(0, y0), min(SIZE, y1)):
            for x in range(max(0, x0), min(SIZE, x1)):
                pixels[x, y] = CYAN

    block(MID - 14, 62, MID + 14, 130)          # the shaft
    for step in range(38):                       # the head
        block(MID - 38 + step, 130 + step, MID + 38 - step, 131 + step)
    block(MID - 54, 186, MID + 54, 202)          # what it lands on
    return image


DRAWINGS = {"moonlight": moon, "steam": download}

if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in DRAWINGS:
        sys.exit("usage: make_icon.py {%s} <output.png>"
                 % "|".join(sorted(DRAWINGS)))
    DRAWINGS[sys.argv[1]](disc()).save(sys.argv[2])
    print("wrote %s" % sys.argv[2])
