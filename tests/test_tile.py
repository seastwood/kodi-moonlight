"""The tile this add-on shows before its application is installed.

The real icon belongs to whoever makes the application and is not
redistributed here; it is copied off this machine once that application exists,
which is the same rule the console follows for box art and console logos. So
there is a gap -- between installing the add-on and installing the
application -- where the menu shows something of ours, and on a machine
installed ten minutes ago that gap is the whole of what anybody sees.

It got there by being wrong. The tile shipped for Steam was a speedometer,
which means nothing to anybody looking for Steam, and it was noticed on the
console only because Steam had been installed and Valve's own icon had quietly
replaced it. A fresh install put it straight back.

So this holds the tile to the set it sits in: 256 square, two colours and
transparency, the same disc and ring as every other icon on that menu. And it
holds the file to the generator that claims to draw it, because a PNG nobody
can regenerate is a PNG nobody can correct.
"""
import os
import subprocess
import sys

NAME = "_moonlight.png"
DRAWING = "moonlight"

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

fails = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


try:
    from PIL import Image
except ImportError:
    print("SKIPPED: Pillow is not installed, and the tile is a PNG")
    sys.exit(0)

# The palette kodi-retrobox's own menu icons are made of.
CYAN = (70, 232, 244, 255)
DARK = (18, 22, 52, 255)
OUTER, RING = 120, 24

tile = os.path.join(ROOT, "media", NAME)
generator = os.path.join(ROOT, "tools", "make_icon.py")

print("the tile itself")
check(os.path.exists(tile), "%s is shipped" % NAME)
if not os.path.exists(tile):
    sys.exit(1)
image = Image.open(tile).convert("RGBA")
check(image.size == (256, 256), "it is 256 square, got %s" % (image.size,))

pixels = list(image.getdata())
colours = {p for p in pixels if p[3] > 20}
check(colours <= {CYAN, DARK},
      "it uses the two colours the other tiles use and nothing else, got %s"
      % sorted(colours))
check(any(p[3] < 20 for p in pixels),
      "and it is transparent outside the disc, not square on a background")

print("\nthe same disc and ring as the icons beside it")
middle = [image.getpixel((x, 128)) for x in range(256)]
solid = [x for x, p in enumerate(middle) if p[3] > 20]
check(solid and solid[0] == 128 - OUTER and solid[-1] == 128 + OUTER - 1,
      "the disc is %d across, from %s to %s"
      % (OUTER * 2, solid[0] if solid else None, solid[-1] if solid else None))
left_ring = 0
for x in range(solid[0] if solid else 0, 256):
    if image.getpixel((x, 128))[:4] != CYAN:
        break
    left_ring += 1
check(left_ring == RING, "the ring is %d thick, got %d" % (RING, left_ring))

print("\nand it is what the generator draws")
check(os.path.exists(generator), "tools/make_icon.py is shipped beside it")
if os.path.exists(generator):
    made = os.path.join(HERE, "_tile-check.png")
    run = subprocess.run([sys.executable, generator, DRAWING, made],
                         capture_output=True, text=True)
    check(run.returncode == 0, "it runs: %s" % (run.stderr.strip()[-200:] or "ok"))
    if run.returncode == 0:
        check(open(made, "rb").read() == open(tile, "rb").read(),
              "and draws exactly the file that is shipped, so the artwork can "
              "be corrected rather than only inherited")
        os.remove(made)

# --- and what happens to it once the real application arrives -----------------
#
# The tile was drawn once at install time and then only ever rewritten by an
# install this add-on performed itself. Install the application any other way
# -- apt, a software centre, somebody's own build -- and the menu kept the
# drawing for ever, because nothing else looked. That is what "I installed it
# and the icon did not change" was.
#
# The other half was Kodi. It caches every image it draws, keyed by path, and
# the tile keeps its path: replacing the file underneath that key changes
# nothing on screen, and neither does reloading the skin. Verified on the
# console -- with the cached copy removed the real icon appeared, and with it
# there no amount of rewriting the file did anything.

import shutil
import tempfile

sys.path.insert(0, ROOT)
import moonlight_core as core                                            # noqa: E402

print("\ntaking the real icon once the application is installed")
folder = tempfile.mkdtemp()
core.TILE = os.path.join(folder, "tile.png")
theirs = os.path.join(folder, "theirs.png")
with open(theirs, "wb") as writing:
    writing.write(b"the application's own icon")

core.best_icon = lambda: None
used = core.refresh_tile(fallback=tile)
check(used == tile, "before it is installed the drawing shipped here is used")
check(open(core.TILE, "rb").read() == open(tile, "rb").read(),
      "and that is what lands on the menu")

# best_icon() here answers (path, kind), because on a Flathub install what
# exists may be an SVG that has to be drawn rather than copied.
core.best_icon = lambda: (theirs, "png")
used = core.refresh_tile()
check(used == theirs, "once it is installed its own icon wins")
check(open(core.TILE, "rb").read() == b"the application's own icon",
      "and replaces what was there")

before = open(core.TILE, "rb").read()
core.refresh_tile()
check(open(core.TILE, "rb").read() == before,
      "asking again changes nothing, so a launch that has nothing to do "
      "leaves Kodi's cache alone")
shutil.rmtree(folder, ignore_errors=True)

print("\nand the menu is checked on every launch, not only after an install")
main = open(os.path.join(ROOT, "main.py")).read()
entry_at = main.index('if __name__ == "__main__":')
launch = main[entry_at:]
check("take_its_icon()" in launch,
      "the tile is refreshed from the entry point, so an application "
      "installed by any other route still corrects the menu")
check(launch.index("take_its_icon()") < launch.index("start_moonlight()"),
      "and before the application is started, not after")
check("Textures.RemoveTexture" in main,
      "Kodi is told to forget the cached copy, which is the only thing that "
      "makes a replaced tile appear")

print()
if fails:
    print("FAILED: %d" % len(fails))
    for line in fails:
        print("  " + line)
    sys.exit(1)
print("test_tile: all ok")
