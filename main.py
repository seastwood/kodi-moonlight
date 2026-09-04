"""Moonlight on the television, from the Kodi menu.

One entry, one thing: choosing MOONLIGHT starts it and gets out of the way.
There is no listing to browse here, because Moonlight has one of its own --
its list of machines and their games is built for a controller, and a second
menu in front of it would only be a worse copy.

What this does have to handle is the machine that has not got Moonlight, which
is every machine somebody has just built. It offers to install it, says what
that costs before starting, and opens it when it is done.
"""

import json
import sys

import xbmc
import xbmcaddon
import xbmcgui

sys.path.insert(0, xbmcaddon.Addon().getAddonInfo("path"))

import moonlight_core

TITLE = "Moonlight"

# What Flathub pulls down for it, runtime and all. Said out loud in the
# question: "install Moonlight?" on a television reads as an instant thing.
DOWNLOAD_SIZE = "a few hundred MB"


def notify(message, icon=xbmcgui.NOTIFICATION_INFO, ms=4000):
    xbmcgui.Dialog().notification(TITLE, message, icon, ms)


def log(message, level=xbmc.LOGINFO):
    xbmc.log("script.moonlight: %s" % message, level)


def start_moonlight():
    """Start Moonlight, then hold it in front of Kodi until it settles.

    Kodi runs fullscreen and does not step aside for something started
    underneath it, and it reclaims the foreground for a few seconds after
    losing it -- so the window is raised repeatedly rather than once. The same
    arrangement RetroArch, the PC games and Steam already use here.
    """
    argv = moonlight_core.launch_argv()
    if not argv:
        return offer_install()

    if moonlight_core.running():
        # Not an error and not a reason to start a second copy: it is already
        # here, it is only behind Kodi.
        notify("Already running -- bringing it forward")
    else:
        problem = moonlight_core.start(argv)
        if problem:
            log("could not start %s: %s" % (" ".join(argv), problem),
                xbmc.LOGERROR)
            xbmcgui.Dialog().ok(TITLE, "Moonlight would not start.\n\n" + problem)
            return
        log("started %s" % " ".join(argv))
        notify("Starting Moonlight...")

    progress = xbmcgui.DialogProgressBG()
    progress.create(TITLE, "Waiting for Moonlight...")
    try:
        found = moonlight_core.bring_forward()
    finally:
        progress.close()

    if not found:
        log("no Moonlight window appeared within %ss"
            % moonlight_core.WAIT_FOR_WINDOW, xbmc.LOGWARNING)
        xbmcgui.Dialog().ok(
            TITLE,
            "Moonlight was started but has not shown a window.\n\n"
            "Choose it again in a moment, and if it still does not appear, "
            "check the Kodi log for what it said.")


def offer_install():
    """Moonlight is not here. Offer to fetch it, and say what that involves."""
    steps = moonlight_core.install_argv()
    if not steps:
        xbmcgui.Dialog().ok(
            TITLE,
            "Moonlight is not installed, and this machine has no Flatpak to "
            "install it with.\n\n"
            "Install flatpak, or install Moonlight your own way -- anything "
            "called moonlight or moonlight-qt on the path is used as it is.")
        return

    if not xbmcgui.Dialog().yesno(
            TITLE,
            "Moonlight is not installed on this machine.\n\n"
            "Install it from Flathub now? It downloads " + DOWNLOAD_SIZE +
            " and needs no password. You can keep using Kodi while it runs.",
            nolabel="Not now", yeslabel="Install Moonlight"):
        return

    progress = xbmcgui.DialogProgressBG()
    progress.create(TITLE, "Installing Moonlight...")

    def line(text):
        text = text.strip()
        if text:
            progress.update(50, TITLE, text[:60])

    # Each step on its own line: on a machine that has never installed a user
    # flatpak the first one adds the Flathub remote, and knowing whether that
    # ran is the difference between "Flathub is down" and "nothing had told
    # this installation about Flathub".
    log("installing:\n  %s" % "\n  ".join(" ".join(step) for step in steps))
    try:
        ok, tail = moonlight_core.install(steps, line)
    finally:
        progress.close()

    if not ok:
        log("install failed: %s" % tail, xbmc.LOGERROR)
        xbmcgui.Dialog().ok(TITLE, "Moonlight could not be installed.\n\n"
                            + tail[:200])
        return
    if not moonlight_core.installed():
        xbmcgui.Dialog().ok(
            TITLE,
            "The install finished but Moonlight still cannot be found.\n\n"
            "Check the Kodi log for what the installer said.")
        return

    notify("Moonlight installed")
    take_its_icon()
    # Straight into it: somebody who just waited through a download asked for
    # Moonlight, not for a confirmation that Moonlight exists.
    start_moonlight()


def take_its_icon():
    """Put Moonlight's own icon on the menu tile, now that there is one.

    The tile is written at install time, when the only picture available is
    the drawing this add-on ships -- the real one arrives with the program.
    So it is written again here, and Kodi is told to forget what it had: it
    caches images by path, the tile keeps its path, and a file replaced
    underneath that key is not something Kodi goes looking for.
    """
    used = moonlight_core.refresh_tile()
    if not used:
        return
    log("menu tile now %s" % used)
    try:
        found = json.loads(xbmc.executeJSONRPC(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "Textures.GetTextures",
            "params": {"filter": {"field": "url", "operator": "contains",
                                  "value": "_moonlight.png"},
                       "properties": ["url"]}})))
        for texture in found.get("result", {}).get("textures", []):
            xbmc.executeJSONRPC(json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "Textures.RemoveTexture",
                "params": {"textureid": texture["textureid"]}}))
    except Exception as exc:          # noqa: BLE001 - a stale icon is not fatal
        log("could not clear the cached tile: %s" % exc, xbmc.LOGWARNING)


if __name__ == "__main__":
    start_moonlight()
