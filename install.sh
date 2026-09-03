#!/bin/sh
# Install the Moonlight add-on for the current user.
#
# Idempotent: safe to run again after a pull. This repository is the add-on, so
# the link points at the checkout itself and a pull is all an update takes.
#
# Moonlight itself is not installed here. The add-on does that, from the sofa,
# the first time somebody chooses it -- and it needs no password, because the
# Flathub build installs for one user. A machine that never wants Moonlight
# never downloads it.
set -eu

REPO="$(cd "$(dirname "$0")" && pwd)"

say() { printf '\n== %s\n' "$1"; }

say "the tests"
for t in "$REPO"/tests/test_*.py; do
  python3 "$t" >/dev/null || { echo "FAILED: $t"; exit 1; }
  echo "passed: $(basename "$t")"
done

say "window tools"
# The add-on raises Moonlight over Kodi with these. Without them it starts and
# stays behind the menu it was started from, which looks exactly like a launch
# that did nothing.
MISSING=""
for tool in wmctrl xdotool; do
  command -v "$tool" >/dev/null 2>&1 || MISSING="$MISSING $tool"
done
if [ -n "$MISSING" ]; then
  echo "installing:$MISSING"
  sudo apt-get update -qq
  # shellcheck disable=SC2086
  sudo apt-get install -y $MISSING
else
  echo "wmctrl and xdotool are here"
fi

say "flatpak"
# The one thing the add-on needs to be able to install Moonlight later. Not
# installed here: a machine that has Moonlight already, by any other means,
# needs none of it.
if command -v flatpak >/dev/null 2>&1; then
  if flatpak remotes | grep -q flathub; then
    echo "flatpak is here and knows flathub"
  else
    echo "flatpak is here but has no flathub remote; add one with:"
    echo "  flatpak remote-add --if-not-exists --user flathub \\"
    echo "    https://dl.flathub.org/repo/flathub.flatpakrepo"
  fi
elif command -v moonlight >/dev/null 2>&1 || command -v moonlight-qt >/dev/null 2>&1; then
  echo "no flatpak, but moonlight is already installed, which is what matters"
else
  echo "no flatpak and no moonlight: the add-on will say so rather than guess"
fi

say "the menu icon"
# kodi-retrobox builds its home menu from ~/.kodi/media/consoles and looks for
# _moonlight.png there. Which icon that is comes from moonlight_core.py rather
# than a list here, because the answer changes the moment Moonlight itself is
# installed: its own icon, and this repository's drawing only until then.
USED=$(python3 -c "import sys; sys.path.insert(0, '$REPO'); import moonlight_core; \
print(moonlight_core.refresh_tile('$REPO/media/_moonlight.png') or '')")
if [ -n "$USED" ]; then
  echo "menu tile from $USED"
else
  echo "no ~/.kodi/media/consoles; skipped (only kodi-retrobox uses it)"
fi

say "the Kodi add-on"
LINK="$HOME/.kodi/addons/script.moonlight"
if [ -d "$HOME/.kodi/addons" ]; then
  # Already where Kodi looks? Then there is nothing to link, and trying is
  # worse than doing nothing: `ln -sfn dir dir` puts a link *inside* the
  # directory rather than replacing it. kodi-retrobox clones this repository
  # straight into ~/.kodi/addons/script.moonlight, so that is the ordinary
  # case there rather than a corner of one.
  if [ "$(readlink -f "$REPO")" = "$(readlink -f "$LINK" 2>/dev/null)" ]; then
    echo "already in ~/.kodi/addons; nothing to link"
  else
    ln -sfn "$REPO" "$LINK"
    echo "linked into ~/.kodi/addons"
  fi
  if pgrep -x kodi.bin >/dev/null 2>&1 && [ -x /usr/bin/kodi-send ]; then
    kodi-send --action="UpdateLocalAddons" >/dev/null 2>&1 || true
    echo "asked the running Kodi to rescan its add-ons"
  fi
else
  echo "no ~/.kodi/addons yet; run Kodi once, then run this again"
fi

say "telling Kodi about it"
# Two things Kodi will not work out for itself. It registers an add-on it
# finds on disk with enabled=0 and then answers RunScript(script.moonlight)
# with "Not executing non-existing script" -- which reads as a broken add-on
# and is really a switch nobody has thrown. And it caches every image it draws
# by path, so a tile replaced at the same path leaves the old picture on the
# menu, which looks exactly like the copy having failed.
python3 - <<'TELL' || echo "could not finish; enable it in Settings -> Add-ons -> My add-ons -> Program add-ons -> Moonlight"
import base64, glob, json, os, re, sqlite3, subprocess, sys, time, urllib.request

ADDON = "script.moonlight"
TILE = "_moonlight.png"
home = os.path.expanduser("~")
addon_dbs = sorted(glob.glob(os.path.join(home, ".kodi/userdata/Database/Addons*.db")))
texture_dbs = sorted(glob.glob(os.path.join(home, ".kodi/userdata/Database/Textures*.db")))
running = subprocess.run(["pgrep", "-x", "kodi.bin"],
                         capture_output=True).returncode == 0
settings = os.path.join(home, ".kodi/userdata/guisettings.xml")
text = open(settings, encoding="utf-8").read() if os.path.exists(settings) else ""


def setting(name, default=""):
    found = re.search(r'<setting id="%s"[^>]*>([^<]*)</setting>' % name, text)
    return found.group(1) if found else default


def call(method, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    url = "http://127.0.0.1:%s/jsonrpc" % setting("services.webserverport", "8080")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"})
    if setting("services.webserverauthentication", "true") == "true":
        pair = "%s:%s" % (setting("services.webserverusername", "kodi"),
                          setting("services.webserverpassword"))
        request.add_header("Authorization",
                           "Basic " + base64.b64encode(pair.encode()).decode())
    return json.load(urllib.request.urlopen(request, timeout=15))


def enabled_in_db():
    if not addon_dbs:
        return None
    con = sqlite3.connect("file:%s?mode=ro" % addon_dbs[-1], uri=True)
    try:
        row = con.execute("select enabled from installed where addonID=?",
                          (ADDON,)).fetchone()
    finally:
        con.close()
    return None if row is None else bool(row[0])


def forget_tile_running():
    got = call("Textures.GetTextures",
               {"filter": {"field": "url", "operator": "contains", "value": TILE},
                "properties": ["url"]})
    cached = got.get("result", {}).get("textures", [])
    for one in cached:
        call("Textures.RemoveTexture", {"textureid": one["textureid"]})
    return len(cached)


def forget_tile_stopped():
    if not texture_dbs:
        return 0
    con = sqlite3.connect(texture_dbs[-1])
    with con:
        rows = list(con.execute("select id, cachedurl from texture "
                                "where url like ?", ("%" + TILE + "%",)))
        for _id, cachedurl in rows:
            try:
                os.remove(os.path.join(home, ".kodi/userdata/Thumbnails", cachedurl))
            except OSError:
                pass
        con.execute("delete from texture where url like ?", ("%" + TILE + "%",))
    con.close()
    return len(rows)


if running:
    if setting("services.webserver") != "true":
        print("Kodi is running and its web service is off, so it cannot be "
              "asked to enable the add-on or to forget the old tile.")
        print("Either turn on Settings -> Services -> Control -> Allow remote "
              "control via HTTP, or close Kodi and run this again.")
        sys.exit(1)
    if enabled_in_db():
        print("already enabled")
    else:
        # Through Kodi itself, because it holds this in memory while it runs
        # and writes it back on the way out: an edit made underneath a running
        # Kodi is undone at the next shutdown, silently.
        #
        # Retried, because on a fresh install this runs seconds after the
        # directory appeared and Kodi answers "Invalid params" for an add-on
        # it has not noticed yet -- which reads like a bad request and is
        # really a race with its own rescan. The rescan was asked for above;
        # this waits for it to land.
        answer = {}
        for attempt in range(12):
            answer = call("Addons.SetAddonEnabled",
                          {"addonid": ADDON, "enabled": True})
            if answer.get("result") == "OK":
                break
            time.sleep(1)
        if answer.get("result") != "OK":
            # Its own list is what Kodi reads at startup, so writing the row
            # is not nothing -- it is the difference between "enable it by
            # hand" and "restart Kodi once".
            if addon_dbs:
                con = sqlite3.connect(addon_dbs[-1])
                with con:
                    con.execute(
                        "insert or replace into installed"
                        "(addonID, enabled, installDate) values(?, 1, ?)",
                        (ADDON, time.strftime("%Y-%m-%d %H:%M:%S")))
                con.close()
                print("Kodi has not noticed the add-on yet (%s)."
                      % answer.get("error", answer))
                print("Written into its database instead: restart Kodi once "
                      "and it will be there.")
                sys.exit(0)
            print("Kodi would not enable it: %s" % answer)
            sys.exit(1)
        print("enabled")
    print("dropped %d cached copy(ies) of the menu tile" % forget_tile_running())
    sys.exit(0)

if not addon_dbs:
    print("no add-on database yet; run Kodi once, then run this again")
    sys.exit(1)
con = sqlite3.connect(addon_dbs[-1])
now = time.strftime("%Y-%m-%d %H:%M:%S")
with con:
    if enabled_in_db() is None:
        con.execute("insert into installed(addonID, enabled, installDate) "
                    "values(?, 1, ?)", (ADDON, now))
    else:
        con.execute("update installed set enabled=1, disabledReason=0 "
                    "where addonID=?", (ADDON,))
con.close()
print("enabled in %s" % os.path.basename(addon_dbs[-1]))
print("dropped %d cached copy(ies) of the menu tile" % forget_tile_stopped())
TELL

say "done"
echo "Open it from Kodi: Programs -> Moonlight, or RunScript(script.moonlight)."
