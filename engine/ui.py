"""
Cross-platform coloured output. Uses colorama on Windows so ANSI codes work
in cmd.exe / PowerShell too. Falls back to plain text if colorama isn't
installed (game still works, just without colour).
"""

import sys

try:
    import colorama
    colorama.init()
    HAVE_COLOR = True
except Exception:
    HAVE_COLOR = False


class C:
    RESET = "\033[0m" if HAVE_COLOR else ""
    BOLD = "\033[1m" if HAVE_COLOR else ""
    DIM = "\033[2m" if HAVE_COLOR else ""
    RED = "\033[31m" if HAVE_COLOR else ""
    GREEN = "\033[32m" if HAVE_COLOR else ""
    YELLOW = "\033[33m" if HAVE_COLOR else ""
    BLUE = "\033[34m" if HAVE_COLOR else ""
    MAGENTA = "\033[35m" if HAVE_COLOR else ""
    CYAN = "\033[36m" if HAVE_COLOR else ""
    WHITE = "\033[37m" if HAVE_COLOR else ""


def color(text, c):
    return f"{c}{text}{C.RESET}"


def banner():
    return color(r"""
 _     _                 ___                  _
| |   (_)_ __  _   ___  / _ \_   _  ___  ___ | |_
| |   | | '_ \| | | \ \/ /_\/ | | |/ _ \/ __|| __|
| |___| | | | | |_| |>  <\ \_| |_| |  __/\__ \| |_
|_____|_|_| |_|\__,_/_/\_\\___/\__,_|\___||___/\__|

        Learn Linux & Networking by hacking a story.
""", C.CYAN)


def hr(char="-", width=60):
    return char * width


def ok(msg):
    print(color("✔ " + msg, C.GREEN))


def err(msg):
    print(color("✘ " + msg, C.RED))


def info(msg):
    print(color(msg, C.YELLOW))


def title(msg):
    print(color(f"\n=== {msg} ===", C.MAGENTA + C.BOLD))
