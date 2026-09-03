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

# Where Moonlight's own icon is once it is installed. Its own, rather than a
# drawing: it is the icon somebody is looking for on a menu.
ICON_PATHS = (
    "~/.local/share/flatpak/app/" + FLATPAK_APP + "/current/active/files/"
    "share/icons/hicolor/256x256/apps/" + FLATPAK_APP + ".png",
    "/var/lib/flatpak/app/" + FLATPAK_APP + "/current/active/files/"
    "share/icons/hicolor/256x256/apps/" + FLATPAK_APP + ".png",
    "/usr/share/icons/hicolor/256x256/apps/moonlight.png",
    "/usr/share/icons/hicolor/scalable/apps/moonlight.svg",
)

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


def install_argv():
    """How Moonlight could be installed here, or None.

    `--user` on purpose: it needs no root, so nothing about this add-on has to
    be privileged and there is no password to type at a television.
    """
    if not shutil.which("flatpak"):
        return None
    return ["flatpak", "install", "--user", "--assumeyes", "--noninteractive",
            "flathub", FLATPAK_APP]


def install(argv, on_line=None):
    """Run an install, feeding each line of output to `on_line`.

    Returns (ok, tail). The tail is the last few lines, because that is what a
    failure has to be explained with -- flatpak says why on the line before it
    stops, and a dialog reading "it failed" without that is a dead end.
    """
    try:
        proc = popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                     text=True, env=environment())
    except OSError as exc:
        return False, str(exc)
    tail = []
    for line in proc.stdout:
        line = line.rstrip()
        tail.append(line)
        del tail[:-6]
        if on_line:
            on_line(line)
    return proc.wait() == 0, "\n".join(tail)


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
    """Moonlight's own icon if this machine has one, else None."""
    for path in ICON_PATHS:
        full = os.path.expanduser(path)
        if exists(full):
            return full
    return None


def refresh_tile(fallback=None):
    """Put the best icon available on the menu tile. Returns what it used.

    Called at install time and again once Moonlight itself is installed,
    because its own icon does not exist until it does.
    """
    tile = os.path.expanduser(TILE)
    if not os.path.isdir(os.path.dirname(tile)):
        return None                   # no kodi-retrobox here; nothing reads it
    source = best_icon() or fallback
    if not source or not exists(source):
        return None
    try:
        with open(source, "rb") as reading:
            data = reading.read()
        if os.path.exists(tile):
            with open(tile, "rb") as existing:
                if existing.read() == data:
                    return tile       # already right; do not disturb the cache
        with open(tile, "wb") as writing:
            writing.write(data)
    except OSError:
        return None
    return source
