# kodi-moonlight

[Moonlight](https://github.com/moonlight-stream/moonlight-qt) on the Kodi home
menu, driven with the controller you are already holding. It installs Moonlight
for you if the machine has not got it.

Moonlight is the client half of game streaming: it plays a game running on
another machine — a gaming PC upstairs, a Steam machine, anything running
Sunshine or GeForce Experience. On a Kodi machine used as a games console it
belongs beside the emulators, as one more way to start something.

Built to sit next to
[kodi-retrobox](https://github.com/seastwood/kodi-retrobox), which puts the
entry on the home screen when this add-on is installed, and works on any Kodi
without it.

## What it does

- **Opens Moonlight** and holds it in front of Kodi. That second half is easy
  to miss: Kodi runs fullscreen and does not step aside for something started
  underneath it, so a launch without it looks exactly like a launch that did
  nothing.
- **Installs Moonlight if it is missing** — the first time somebody chooses it
  on a machine without it, from the sofa, with no password.
- **Comes back** — quit Moonlight and Kodi is where you left it, because it
  never went anywhere.
- **Does not start a second copy** — choosing it while it is running brings
  the one that is already here forward.

## Installing

```sh
git clone git@github.com:seastwood/kodi-moonlight.git
cd kodi-moonlight
./install.sh
```

`install.sh` links the checkout into `~/.kodi/addons/script.moonlight`, makes
sure `wmctrl` and `xdotool` are present, puts the menu tile where kodi-retrobox
looks for it, and tells Kodi it may run the add-on.

That last step is not a formality. Kodi registers an add-on it finds on disk
with `enabled=0`, and then answers `RunScript(script.moonlight)` with *"Not
executing non-existing script"* — which reads as a broken add-on and is really
a switch nobody has thrown. A running Kodi is asked through its own JSON-RPC,
because it holds that state in memory and writes it back on the way out; a
stopped one has its database written directly.

A pull is all an update takes: the repository *is* the add-on.

## Why Flathub, when the Steam add-on prefers a package

Because of what is packaged, not because of a preference. Ubuntu and Mint
package Steam, so there a native package is available and worth having — the
Flatpak sandbox sits between an application and the machine's controllers,
which a games console cannot afford. Neither distribution packages Moonlight:
the only `moonlight` in their archives is a Discord mod, and the only related
thing is `sunshine`, which is the *host* half rather than the client.

Upstream ships a Flathub build and an apt repository of their own. Adding
somebody's apt repository and signing key to a machine is a larger and more
permanent thing to do to it than installing an application, so this uses
Flathub — `--user`, needing no root, which is also why there is no privileged
helper anywhere in this add-on.

A machine that already has `moonlight` or `moonlight-qt` on the path is left
alone and used as it is, however it was installed. The laptop this was written
on has the snap; that works without changing anything.

## The menu icon

Moonlight's own, copied from its installation once it exists. The drawing in
this repository — a moon over a screen — is the fallback for a machine that
has not got Moonlight yet, and is replaced the moment the real one is there.

Kodi is told to forget the cached copy at the same time. It caches images by
path, the tile keeps its path, and a file replaced underneath that key is not
something Kodi goes looking for — which makes a successful copy and a silently
failed one look identical on the menu.

## Running the tests

```sh
python3 tests/test_moonlight.py
python3 tests/test_addon.py
```

Neither touches a real Moonlight, a real flatpak or a real screen: `sh`,
`popen` and `exists` are the only three ways `moonlight_core.py` reaches the
outside world, and all three are stubbed.

## Licence

MIT. See [LICENSE](LICENSE).
