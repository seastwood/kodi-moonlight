"""Finding Moonlight, installing it, and getting it in front of Kodi.

Nothing real is touched: `sh`, `popen` and `exists` are the only three ways
moonlight_core reaches the outside world, and all three are replaced here.
That matters more than usual for this add-on -- the code under test can start
a download and a program that takes over the screen.

The decision worth writing down is the install route. Steam's add-on prefers a
native package because Ubuntu and Mint package Steam; neither packages
Moonlight. The only `moonlight` in their archives is a Discord mod and the
only related thing is `sunshine`, which is the host half, not the client. So
Flathub it is -- for one user, needing no root, and therefore no privileged
helper anywhere in this add-on. A machine that already has a moonlight binary,
installed any other way, is left alone and used as it is.
"""
import importlib.machinery
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ldr = importlib.machinery.SourceFileLoader(
    "moonlight_core", os.path.join(os.path.dirname(HERE), "moonlight_core.py"))
core = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("moonlight_core", ldr))
ldr.exec_module(core)

fails = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


class FakeShutil:
    def __init__(self, present):
        self.present = set(present)

    def which(self, name):
        return "/usr/bin/" + name if name in self.present else None


def stub(present=(), output=None, files=()):
    core.shutil = FakeShutil(present)
    table = output or {}
    wanted = set(files)
    core.exists = lambda path: path in wanted
    calls = []

    def fake_sh(*argv, **kw):
        calls.append(list(argv))
        for key, value in table.items():
            if key in argv:
                return value
        return ""

    core.sh = fake_sh
    return calls


print("which Moonlight is here")
stub(present=["moonlight-qt"])
check(core.launch_argv() == ["/usr/bin/moonlight-qt"],
      "a packaged moonlight-qt is started straight")
stub(present=["moonlight"])
check(core.launch_argv() == ["/usr/bin/moonlight"],
      "and so is a plain `moonlight`, which is what the snap and most "
      "distributions call it")
stub(present=["flatpak"], output={"list": "org.videolan.VLC\n"})
check(core.launch_argv() is None,
      "flatpak being installed is not Moonlight being installed")
stub(present=["flatpak"],
     output={"list": "com.moonlight_stream.Moonlight\norg.videolan.VLC\n"})
check(core.launch_argv() ==
      ["flatpak", "run", "com.moonlight_stream.Moonlight"],
      "the Flatpak is used when there is no binary")
stub(present=["moonlight", "flatpak"],
     output={"list": "com.moonlight_stream.Moonlight\n"})
check(core.launch_argv()[0] == "/usr/bin/moonlight",
      "and a machine that already has one is left alone rather than given "
      "a second copy")
stub(present=[])
check(core.launch_argv() is None and core.installed() is False,
      "a machine with neither has neither")

print("how it would be installed, on a machine that already knows Flathub")
stub(present=["flatpak"], output={"remotes": "flathub\n"})
steps = core.install_argv()
check(len(steps) == 1, "one command, got %d" % len(steps))
argv = steps[-1]
check(argv[:3] == ["flatpak", "install", "--user"],
      "Flathub, for this user -- so nothing in this add-on needs root")
check("--noninteractive" in argv and "--assumeyes" in argv,
      "and nothing that stops to ask a question nobody can answer from a sofa")
check(argv[-1] == core.FLATPAK_APP, "naming the application, not a search")

# The state every freshly installed Mint is in. Flathub is added to the system
# installation by the distribution, and this add-on installs into the user
# one, which is a separate world with no remotes in it at all. Asking anyway
# fails with "No remote refs found for 'flathub'", which sounds like Flathub
# is empty rather than like a remote nobody added. It was invisible on the
# machine this was written on, where something had added the user remote years
# earlier, and it broke on the first console installed from scratch.
print("\nand on one that does not")
calls = stub(present=["flatpak"])                # `flatpak remotes` says nothing
steps = core.install_argv()
check(any("remotes" in call and "--user" in call for call in calls),
      "it asks the *user* installation what remotes it has, not the system one")
check(len(steps) == 2, "two commands, got %d" % len(steps))
check(steps[0][:4] == ["flatpak", "remote-add", "--user", "--if-not-exists"],
      "the first adds Flathub for this user, and does not mind it being there "
      "already; got %s" % (steps[0][:4],))
check(steps[0][-1] == core.FLATHUB_REPO,
      "from Flathub's own description of itself")
check(steps[1][-1] == core.FLATPAK_APP, "and the second installs Moonlight")

stub(present=[])
check(core.install_argv() is None,
      "a machine with no flatpak says so rather than guessing")

print("whether it is already running")
stub(output={"comm": "systemd\nkodi.bin\nmoonlight-qt\n"})
check(core.running() is True, "it is up")
stub(output={"comm": "systemd\nkodi.bin\n"})
check(core.running() is False, "and here it is not")

print("which window to raise")
WINDOWS = (
    "0x03000001  0 100 100  1    1    retro Moonlight\n"
    "0x03000007  0 0   0    1920 1080 retro Moonlight\n"
    "0x02000003  0 0   0    1920 1080 retro Kodi\n")
stub(output={"-lG": WINDOWS})
check(core.window() == "0x03000007",
      "the big one, not the first: a 1x1 window raises fine and shows nothing")
stub(output={"-lG": "0x02000003  0 0 0 1920 1080 retro Kodi\n"})
check(core.window() is None, "and Kodi's own window is not Moonlight's")

print("the icon on the menu tile")
# What a Flathub install actually has: one SVG, which Kodi cannot draw, and
# the catalogue PNGs flatpak keeps in its appstream cache. The first version
# of this looked for a 256-pixel PNG in the app's own export directory, which
# does not exist and never did -- so the tile stayed as the drawing.
svg = os.path.expanduser(
    "~/.local/share/flatpak/exports/share/icons/hicolor/scalable/apps/"
    + core.FLATPAK_APP + ".svg")
png128 = os.path.expanduser(
    "/usr/share/icons/hicolor/128x128/apps/moonlight.png")
png256 = os.path.expanduser(
    "/usr/share/icons/hicolor/256x256/apps/moonlight.png")

stub(present=["rsvg-convert"], files=[svg, png128])
check(core.best_icon() == (svg, "svg"),
      "the SVG wins where something can draw it: it is 256 pixels of shapes "
      "and every PNG on a Flathub install is 128 or smaller")
stub(present=[], files=[svg, png128])
check(core.best_icon() == (png128, "png"),
      "and where nothing can, a real PNG is used -- a soft tile beats a blank "
      "one, which is what writing an SVG Kodi cannot draw would give")
stub(present=[], files=[png128, png256])
check(core.best_icon() == (png256, "png"), "the biggest PNG, not the first")
stub(present=[], files=[])
check(core.best_icon() is None,
      "and nothing at all before Moonlight is installed, so the drawing "
      "shipped here is what the tile gets until then")
check(any("appstream" in d for d in core.APPSTREAM_DIRS),
      "flatpak's catalogue art is looked at, because on a Flathub install it "
      "is where the only PNGs are")

# The state a console is actually in the morning it is installed. flatpak's
# catalogue of the remote has never been fetched, so those directories are
# empty; the only icon anywhere is the SVG, and a fresh Mint has nothing that
# can draw one -- no rsvg-convert, no inkscape, no ImageMagick. So the menu
# kept the drawing shipped here even though Moonlight was installed and had
# an icon of its own all along. It was inside the application, not in the
# catalogue.
import fnmatch                                                  # noqa: E402


class FakeGlob:
    """Only the paths this machine is pretending to have."""

    def __init__(self, paths):
        self.paths = list(paths)

    def glob(self, pattern):
        return [p for p in self.paths if fnmatch.fnmatch(p, pattern)]


real_glob = core.glob
app_png = os.path.expanduser(
    "~/.local/share/flatpak/app/" + core.FLATPAK_APP
    + "/current/active/files/share/app-info/icons/flatpak/128x128@2/"
    + core.FLATPAK_APP + ".png")
app_png_small = app_png.replace("128x128@2", "64x64")
stub(present=[], files=[svg, app_png, app_png_small])
core.glob = FakeGlob([app_png, app_png_small])
check(core.best_icon() == (app_png, "png"),
      "with no catalogue and nothing to draw an SVG, the application's own "
      "PNG is found -- which is the difference between the real icon and the "
      "drawing on a console installed this morning")
check("@2" in core.best_icon()[0],
      "and the doubled one, because 128x128@2 is a real 256-pixel file and "
      "the plain 128 beside it is not")
core.glob = real_glob

print("installing, out loud")


class FakeProc:
    def __init__(self, lines, code):
        self.stdout = iter(lines)
        self.code = code

    def wait(self):
        return self.code


seen = []
core.popen = lambda argv, **kw: FakeProc(["Installing...", "Now at 6.1.0"], 0)
ok, tail = core.install(["flatpak", "install"], seen.append)
check(ok is True and seen[0] == "Installing...",
      "a clean run succeeds, and every line is offered as it arrives")
core.popen = lambda argv, **kw: FakeProc(["error: no remote flathub"], 1)
ok, tail = core.install(["flatpak", "install"], None)
check(ok is False and "no remote flathub" in tail,
      "and a failure comes back with what was said, which is the useful part")


def refuse(argv, **kw):
    raise OSError("No such file or directory: 'flatpak'")


core.popen = refuse
ok, tail = core.install(["flatpak", "install"], None)
check(ok is False and "No such file" in tail,
      "a command that cannot start is a failure, not a traceback")

print("the display")
os.environ.pop("DISPLAY", None)
check(core.environment()["DISPLAY"] == ":0",
      "a program started from Kodi is told which screen to use")
os.environ["DISPLAY"] = ":1"
check(core.environment()["DISPLAY"] == ":1",
      "and one that is already set is left alone")

print("\na step that fails stops the ones after it")
core.popen = lambda argv, **kw: FakeProc(
    ["error: No remote refs found for flathub"], 1)
ran = []


def counting(argv, **kw):
    ran.append(argv)
    return FakeProc(["error: No remote refs found for flathub"], 1)


core.popen = counting
ok, tail = core.install([["flatpak", "remote-add"], ["flatpak", "install"]])
check(ok is False, "it reports failure")
check("No remote refs" in tail,
      "and hands back what flatpak said, which is the only thing that "
      "explains it")
check(len(ran) == 1,
      "and it stopped: there is no point downloading a gigabyte from a remote "
      "that could not be added, got %d command(s)" % len(ran))

print()
if fails:
    print("FAILED: %d" % len(fails))
    for line in fails:
        print("  " + line)
    sys.exit(1)
print("all good")
