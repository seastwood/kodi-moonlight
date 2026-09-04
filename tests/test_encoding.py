"""Reading the output of a command that says something not in ASCII.

This crashed a console the first time somebody installed Steam on it. `sh`
ran `wmctrl -lG` to find the window to bring forward, subprocess decoded the
output with text=True, and text=True means "the locale's encoding" -- which
inside Kodi is ASCII. The window list had one title with a non-breaking space
in it, and the add-on went down with

    UnicodeDecodeError: 'ascii' codec can't decode byte 0xc2

after installing Steam successfully. Nothing about the failure said anything
about text encodings; it read as the add-on being broken.

Window titles are somebody else's text -- a game's, a launcher's, whatever is
open -- so they are exactly the input this cannot afford to be strict about.
UTF-8 with errors="replace": a title we cannot read should cost us that title,
not the launcher.

This drives the real function with a real subprocess and a real non-ASCII
byte, under a C locale, which is the machine that broke.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import moonlight_core as core                                             # noqa: E402

fails = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


print("a command whose output is not ASCII")
# A non-breaking space (U+00A0) is 0xc2 0xa0 -- the exact byte that broke it,
# and the kind of thing that turns up in a window title without anybody
# meaning it to.
SAYS = "Steam\u00a0Big Picture \u00a9 Valve"

# The locale Kodi's own process runs under, which is where text=True went
# looking for its encoding.
os.environ["LC_ALL"] = "C"
os.environ["LANG"] = "C"

out = core.sh(sys.executable, "-c",
              "import sys; sys.stdout.buffer.write(%r.encode('utf-8'))" % SAYS)
check(out != "", "it comes back at all, rather than taking the add-on down "
                 "with a UnicodeDecodeError")
check("Steam" in out and "Valve" in out,
      "and the parts that are ASCII are intact, which is what any of this is "
      "read for; got %r" % out[:60])

print("\nand one that is not valid UTF-8 either")
out = core.sh(sys.executable, "-c",
              "import sys; sys.stdout.buffer.write(b'good \\xff\\xfe bad')")
check("good" in out and "bad" in out,
      "the readable parts survive and the rest is replaced, rather than the "
      "whole line being lost; got %r" % out[:40])

print("\nand a command that is not there is still not an exception")
check(core.sh("this-command-does-not-exist-anywhere") == "",
      "which is the behaviour everything calling this relies on")

print()
if fails:
    print("FAILED: %d" % len(fails))
    for line in fails:
        print("  " + line)
    sys.exit(1)
print("test_encoding: all ok")
