"""The packaging: that the pieces still call each other by the same names.

None of this is clever, and all of it has broken something before in projects
shaped like this one. An add-on id is written down in five places -- addon.xml,
the symlink install.sh makes, the RunScript() a menu entry carries, the log
lines, this suite -- and Kodi's answer to a mismatch is "you need to install
this add-on", which sounds like a packaging fault rather than a typo.

The other two are Kodi's own habits, both learned the hard way on the Steam
add-on next door: it registers an add-on it merely finds on disk as disabled,
and it caches every image it draws by path, so a tile replaced at the same
path leaves the old picture on the menu.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

fails = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


def read(name):
    with open(os.path.join(ROOT, name)) as handle:
        return handle.read()


ADDON_ID = "script.moonlight"

print("addon.xml")
root = ET.parse(os.path.join(ROOT, "addon.xml")).getroot()
check(root.get("id") == ADDON_ID, "the add-on is %s" % ADDON_ID)
script = root.find("./extension[@point='xbmc.python.script']")
check(script is not None and script.get("library") == "main.py",
      "and Kodi is pointed at main.py")
check(os.path.exists(os.path.join(ROOT, "main.py")), "which is there")
icon = root.find(".//icon")
check(icon is not None and os.path.exists(os.path.join(ROOT, icon.text)),
      "the icon named in the metadata exists")
check(root.find("./requires/import[@addon='xbmc.python']") is not None,
      "and it declares the Python it is written against")

print("install.sh")
install = read("install.sh")
check(".kodi/addons/" + ADDON_ID in install,
      "links the checkout in under the same id")
# kodi-retrobox clones this repository straight into ~/.kodi/addons/script.moonlight
# and then runs this script, so the link it wants to make is a link to the
# place it is already standing. `ln -sfn dir dir` puts a link inside that
# directory rather than replacing it, which is a mess to find later.
check("readlink -f" in install and "nothing to link" in install,
      "and notices when it is already there, rather than linking into itself")
check("tests/test_*.py" in install or "test_*.py" in install,
      "and runs this suite before it installs anything")
check("wmctrl" in install and "xdotool" in install,
      "makes sure the window tools are here, which the launch depends on")

print("Kodi is told it may run it")
# The fault this exists for: Kodi registered the add-on with enabled=0 and
# answered RunScript(script.moonlight) with "Not executing non-existing script",
# which reads as a broken add-on and is a switch nobody threw.
check("SetAddonEnabled" in install,
      "a running Kodi is asked through its own API, not edited underneath")
check("enabled=1" in install and "disabledReason=0" in install,
      "and a stopped one has its database written, the way kodi-retrobox does")
check("Not executing non-existing script" in install,
      "with the message it fixes written down beside it")
# The second thing Kodi will not work out: it caches images by path, and the
# tile is replaced at the same path every install.
check("Textures.RemoveTexture" in install,
      "the cached copy of the old tile is dropped from a running Kodi")
check("delete from texture where url like" in install,
      "and from the database of a stopped one, which is the same fault later")

print("nothing here needs root")
check("sudoers" not in install and "libexec" not in install,
      "no privileged helper anywhere: the Flathub build installs for one "
      "user, so there is no password to type at a television and no rule to "
      "write. The Steam add-on next door needs one; this does not, and the "
      "difference is which of the two the distribution packages")
check("--user" in read("moonlight_core.py"),
      "which is what makes that true -- the install is a --user one")

print("the menu icon")
check("refresh_tile" in install,
      "the tile comes from moonlight_core, which prefers Moonlight's own icon")
check("$REPO/media/_moonlight.png" in install,
      "and the drawing here is the fallback, not the preference: the real one "
      "does not exist until Moonlight does")
check(os.path.exists(os.path.join(ROOT, "media/_moonlight.png")),
      "the fallback tile is in the repository")

print("main.py talks to the outside world through moonlight_core")
main = read("main.py")
check("import moonlight_core" in main, "it imports the core")
check("subprocess" not in main,
      "and runs nothing itself: one file reaches the machine, and it is tested")
check('xbmc.log("script.moonlight' in main,
      "log lines carry the add-on id, so they can be found in kodi.log")

print()
if fails:
    print("FAILED: %d" % len(fails))
    for line in fails:
        print("  " + line)
    sys.exit(1)
print("all good")
