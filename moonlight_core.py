"""Finding Moonlight, installing it if it is not here, and putting it on screen.

Moonlight is the client half of game streaming: it plays a game running on
another machine. On this one it sits beside the emulators as another way to
start something, which is why it is a Kodi add-on at all.

Nothing here imports Kodi. Everything is paths and subprocesses, so the tests
run on a laptop with neither Kodi nor Moonlight -- and every command goes
through `sh()`, one function to stub, so no test can start a download or a
program that takes over the screen by accident.

Flatpak, and only Flatpak, which is a different answer from the one the Steam
add-on gives. Steam is packaged by Ubuntu and Mint, so there a native package
is available and worth preferring. Moonlight is not packaged by either -- the
only `moonlight` in their archives is a Discord mod, and the only related
thing is `sunshine`, which is the *host* half. Upstream ships a Flathub build
and an apt repository of their own, and adding somebody's apt repository and
signing key to a machine is a larger and more permanent thing to do to it than
installing an application. So: Flathub, for this user, needing no root at
all -- and a native binary is still used if the machine already has one, for
anybody who installed it their own way.
"""

import glob
import os
import shutil
import subprocess
import time

FLATPAK_APP = "com.moonlight_stream.Moonlight"
# Where Flathub describes itself. Needed because this installs into the
# per-user flatpak installation, which on most machines has no remotes at all.
FLATHUB_REPO = "https://dl.flathub.org/repo/flathub.flatpakrepo"

# Whoever packaged it. moonlight-qt is the name upstream's own packages use;
# `moonlight` is what the Flatpak's wrapper and most distributions call it.
NATIVE_NAMES = ("moonlight-qt", "moonlight")

# Moonlight opens on its list of machines, which is a menu and not a stream:
# it appears at once, unlike a client that has to talk to a server first.
WAIT_FOR_WINDOW = 30.0
POLL = 0.5
# Kodi runs fullscreen and takes the foreground back for a moment after losing
# it, which is why this raises more than once. The same finding
# pcgame_launch.py was written around on this machine.
RAISE_TRIES = 8
RAISE_GAP = 0.7

# Where Moonlight's own icon is once it is installed, and it is not one place.
#
# The Flathub build exports exactly one icon and it is an SVG, which Kodi
# cannot draw at all -- so the first thing this looked for, a 256-pixel PNG in
# the application's own export directory, does not exist and never did. What
# there is besides that is the catalogue icon flatpak keeps in its appstream
# cache, which is the same logo as a real PNG at 128 and 64 pixels.
#
# So: the SVG when something on this machine can turn it into a picture, and
# the largest real PNG otherwise. Both are Moonlight's own; the difference is
# only how crisp it is on a television.
APP_ICON_DIRS = (
    "~/.local/share/flatpak/exports/share/icons/hicolor",
    "/var/lib/flatpak/exports/share/icons/hicolor",
    "/usr/share/icons/hicolor",
    # Where snapd exports a snap's icons, which is how the laptop this was
    # written on has Moonlight.
    "/var/lib/snapd/desktop/icons",
)
# Biggest first: a tile is drawn at a few hundred pixels and scaling one up
# from 64 shows.
# Biggest first, and "@2" means double: 128x128@2 is a real 256-pixel file,
# which is why it sorts with 256x256 rather than with 128x128. On a Flathub
# install that entry is the whole reason this works without anything extra
# installed -- it is the same 256 pixels the SVG would have been rendered at.
ICON_SIZES = ("512x512", "384x384", "256x256", "128x128@2", "192x192",
              "128x128", "64x64@2", "96x96", "64x64", "48x48")
ICON_NAMES = (FLATPAK_APP, "moonlight", "moonlight-qt")
# Flatpak's own catalogue art, which is where the only PNGs on a Flathub
# install actually live. `active` is the symlink flatpak keeps pointing at the
# current copy, so this does not go stale when the catalogue updates.
APPSTREAM_DIRS = (
    "~/.local/share/flatpak/appstream/*/*/active/icons",
    "/var/lib/flatpak/appstream/*/*/active/icons",
    # And the copy inside the installed application itself. The two above are
    # flatpak's catalogue of a *remote*, which a machine that has only ever
    # installed one thing may never have fetched -- on a console installed
    # this morning they were empty, so the only icon found was the SVG, and
    # with nothing on the machine able to draw an SVG the menu kept the
    # drawing this add-on ships. These exist the moment the application does.
    "~/.local/share/flatpak/app/*/current/active/files/share/app-info/icons/flatpak",
    "/var/lib/flatpak/app/*/current/active/files/share/app-info/icons/flatpak",
)
# What can turn an SVG into a picture, if anything here can. None of these is
# a dependency: without one, a real PNG is used instead and the only loss is
# sharpness.
RASTERISERS = (
    ("rsvg-convert", ["-w", "256", "-h", "256", "-o"]),
    ("inkscape", ["--export-type=png", "--export-width=256",
                  "--export-filename"]),
    ("magick", None),
    ("convert", None),
)


def icon_pngs():
    """Every real PNG of Moonlight's icon on this machine, biggest first."""
    found = []
    for size in ICON_SIZES:
        for folder in APP_ICON_DIRS:
            for name in ICON_NAMES:
                path = os.path.expanduser(
                    os.path.join(folder, size, "apps", name + ".png"))
                if exists(path):
                    found.append(path)
        for pattern in APPSTREAM_DIRS:
            for name in ICON_NAMES:
                for path in sorted(glob.glob(os.path.expanduser(
                        os.path.join(pattern, size, name + ".png")))):
                    if exists(path):
                        found.append(path)
    return found


def icon_svg():
    """Moonlight's icon as an SVG, if it exported one."""
    for folder in APP_ICON_DIRS:
        for name in ICON_NAMES:
            path = os.path.expanduser(
                os.path.join(folder, "scalable", "apps", name + ".svg"))
            if exists(path):
                return path
    return None


def rasteriser():
    """A command that can turn an SVG into a PNG, or None."""
    for name, flags in RASTERISERS:
        if shutil.which(name):
            return name, flags
    return None


def render_svg(svg, into):
    """Draw an SVG at tile size. True if something on this machine could."""
    tool = rasteriser()
    if not tool:
        return False
    name, flags = tool
    if flags is None:                 # ImageMagick: -density then a resize
        argv = [name, "-background", "none", "-density", "384", svg,
                "-resize", "256x256", into]
    else:
        argv = [name, *flags[:-1], flags[-1], into, svg] if flags[-1].endswith(
            ("-o", "--export-filename")) else [name, *flags, into, svg]
    sh(*argv, timeout=30)
    return exists(into) and os.path.getsize(into) > 0


# Where kodi-retrobox's menu looks for the tile.
TILE = "~/.kodi/media/consoles/_moonlight.png"

# The two ways this module reaches the outside world, named so a test can
# replace them. Nothing else here calls subprocess or asks about a file.
popen = subprocess.Popen
exists = os.path.isfile


def sh(*argv, **kw):
    """Run a command and return its output, or "" if it could not be run."""
    timeout = kw.get("timeout", 20)
    try:
        done = subprocess.run(list(argv), capture_output=True, text=True,
                              timeout=timeout, env=environment())
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout


def environment():
    """The environment a program started from Kodi needs.

    Kodi's own has DISPLAY in it; a script run through kodi-send or a service
    may not, and a client that cannot find the display exits at once with
    nothing on screen to say why.
    """
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    return env


def native():
    """Moonlight from a package, if this machine has one."""
    for name in NATIVE_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def flatpak_app():
    """Whether the Flatpak is installed, for this user or system-wide."""
    if not shutil.which("flatpak"):
        return False
    listed = sh("flatpak", "list", "--app", "--columns=application")
    return any(line.strip() == FLATPAK_APP for line in listed.splitlines())


def launch_argv():
    """How to start Moonlight here, or None if it is not installed."""
    exe = native()
    if exe:
        return [exe]
    if flatpak_app():
        return ["flatpak", "run", FLATPAK_APP]
    return None


def installed():
    return launch_argv() is not None


def knows_flathub():
    """Whether the per-user flatpak installation has heard of Flathub.

    Mint and Ubuntu add Flathub to the *system* installation. This add-on
    installs into the user one, and those are separate worlds: a system remote
    is invisible to `--user`. Asking for it anyway fails with

        error: No remote refs found for 'flathub'

    which reads as Flathub being down, or empty, rather than as a remote
    nobody has added here. The machine this was written on had both remotes --
    something else had added the user one years ago -- so it worked there and
    failed on the first console that had only ever been installed once.
    """
    listed = sh("flatpak", "remotes", "--user", "--columns=name")
    return "flathub" in listed.split()


def install_argv():
    """The commands that would install Moonlight here, or None.

    A list of them, because on a machine that has never installed a user
    flatpak this takes two: teach the user installation about Flathub, then
    install from it.

    `--user` on purpose: it needs no root, so nothing about this add-on has to
    be privileged and there is no password to type at a television.
    """
    if not shutil.which("flatpak"):
        return None
    steps = []
    if not knows_flathub():
        # --if-not-exists so that two of these racing, or a second run after a
        # half-finished first, is not an error.
        steps.append(["flatpak", "remote-add", "--user", "--if-not-exists",
                      "flathub", FLATHUB_REPO])
    steps.append(["flatpak", "install", "--user", "--assumeyes",
                  "--noninteractive", "flathub", FLATPAK_APP])
    return steps


def install(steps, on_line=None):
    """Run each step in order, feeding every line of output to `on_line`.

    Returns (ok, tail). The tail is the last few lines, because that is what a
    failure has to be explained with -- flatpak says why on the line before it
    stops, and a dialog reading "it failed" without that is a dead end.

    Stops at the first step that fails. There is no point downloading a
    gigabyte from a remote that could not be added.
    """
    # One command is still accepted, so a caller with a single argv -- and
    # every test that passed one -- keeps working.
    if steps and isinstance(steps[0], str):
        steps = [steps]
    tail = []
    for argv in steps:
        try:
            proc = popen(argv, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True,
                         env=environment())
        except OSError as exc:
            tail.append(str(exc))
            return False, "\n".join(tail[-6:])
        for line in proc.stdout:
            line = line.rstrip()
            tail.append(line)
            del tail[:-6]
            if on_line:
                on_line(line)
        if proc.wait() != 0:
            return False, "\n".join(tail)
    return True, "\n".join(tail)


def running():
    """Whether Moonlight is already up.

    By process name rather than by window: it can be running with no window
    worth finding -- starting, or on another workspace -- and a second copy
    fights the first for the display and the pad.
    """
    names = {line.strip() for line in sh("ps", "-eo", "comm").splitlines()}
    return bool(names & {"moonlight", "moonlight-qt"})


def window():
    """The largest window that looks like Moonlight, or None.

    Largest rather than first, for the reason pcgame_launch.py found the hard
    way: a program maps small helper windows beside the one worth looking at,
    and raising a 1x1 window reports success and shows nothing.
    """
    best, best_area = None, -1
    for line in sh("wmctrl", "-lG").splitlines():
        parts = line.split(None, 7)
        if len(parts) < 8 or "moonlight" not in parts[7].lower():
            continue
        try:
            area = int(parts[4]) * int(parts[5])
        except ValueError:
            continue
        if area > best_area:
            best, best_area = parts[0], area
    return best


def raise_window(wid):
    """Put a window in front of Kodi and make it fill the screen."""
    sh("wmctrl", "-i", "-a", wid)
    sh("wmctrl", "-i", "-b", "add,fullscreen", wid)
    try:
        sh("xdotool", "windowactivate", "--sync", str(int(wid, 16)))
    except ValueError:
        pass


def start(argv):
    """Start Moonlight and leave it running after this script exits."""
    try:
        popen(argv, env=environment(), stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as exc:
        return str(exc)
    return ""


def bring_forward(deadline=None):
    """Wait for Moonlight's window and hold it in front of Kodi."""
    stop = (time.time() + WAIT_FOR_WINDOW) if deadline is None else deadline
    wid = None
    while time.time() < stop:
        wid = window()
        if wid:
            break
        time.sleep(POLL)
    if not wid:
        return False
    for _ in range(RAISE_TRIES):
        raise_window(wid)
        time.sleep(RAISE_GAP)
    return True


def best_icon():
    """The best picture of Moonlight's own icon, as (path, kind), or None.

    The SVG wins where it can be drawn, because it is 256 pixels of plain
    shapes and every PNG on a Flathub install is 128 or smaller. Where it
    cannot, the largest PNG is used and the tile is a little soft, which is a
    far better answer than a drawing that is not Moonlight's icon at all.
    """
    svg = icon_svg()
    if svg and rasteriser():
        return svg, "svg"
    pngs = icon_pngs()
    if pngs:
        return pngs[0], "png"
    return (svg, "svg") if svg else None


def _same_file(path, data):
    """Whether the tile already holds exactly this, so the cache is left be."""
    try:
        with open(path, "rb") as existing:
            return existing.read() == data
    except OSError:
        return False


def refresh_tile(fallback=None):
    """Put the best icon available on the menu tile. Returns what it used.

    Called at install time and again once Moonlight itself is installed,
    because its own icon does not exist until it does -- and on a Flathub
    install what exists then is an SVG, which is why this may have to draw it
    rather than copy it.
    """
    tile = os.path.expanduser(TILE)
    if not os.path.isdir(os.path.dirname(tile)):
        return None                   # no kodi-retrobox here; nothing reads it

    best = best_icon()
    if best and best[1] == "svg":
        source, _kind = best
        drawn = tile + ".new"
        if render_svg(source, drawn):
            try:
                with open(drawn, "rb") as reading:
                    data = reading.read()
                if _same_file(tile, data):
                    os.remove(drawn)
                    return tile
                os.replace(drawn, tile)     # never a half-written tile
            except OSError:
                return None
            return source
        # Nothing here could draw it. Fall through to a real PNG rather than
        # writing an SVG that Kodi will not display -- a blank tile is worse
        # than a soft one.
        pngs = icon_pngs()
        best = (pngs[0], "png") if pngs else None

    source = best[0] if best else fallback
    if not source or not exists(source):
        return None
    try:
        with open(source, "rb") as reading:
            data = reading.read()
        if _same_file(tile, data):
            return tile
        with open(tile, "wb") as writing:
            writing.write(data)
    except OSError:
        return None
    return source
