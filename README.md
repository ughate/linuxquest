# LinuxQuest

A story-driven, command-line game for learning **Linux commands** and
**basic networking** — no real system access required. Everything (the
filesystem, the processes, the other "machines" on the network) is
simulated in memory, so it's completely safe to play: there is nothing
you can break.

You play a new recruit at "Aegis Corp" working through 9 missions that
take you from basic navigation (`ls`, `cd`, `cat`) all the way to
scanning a simulated network and SSHing into a remote box to grab a
flag — CTF-style.

## Requirements

- Python 3.8 or newer
- (Optional but recommended) the `colorama` package, for colored output

## Running on Ubuntu / other Linux distros / macOS

```bash
# 1. Get the files onto your machine and cd into the folder, then:
chmod +x run.sh
./run.sh
```

Or manually:

```bash
python3 -m pip install -r requirements.txt --break-system-packages
python3 main.py
```

(`--break-system-packages` is only needed on newer Debian/Ubuntu where
pip refuses system-wide installs; a virtualenv works too — see below.)

### Using a virtual environment (recommended if you hit pip errors)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Running on Windows

**Yes, this works on Windows** — it's pure Python with no OS-specific
code, and colors are handled through `colorama` so they render
correctly in `cmd.exe`, PowerShell, and Windows Terminal.

1. Install Python from [python.org](https://python.org) (tick **"Add
   python.exe to PATH"** during setup).
2. Double-click `run.bat`, **or** open PowerShell/cmd in the project
   folder and run:

```bat
pip install -r requirements.txt
python main.py
```

## Playing the game

Once started you'll see your first mission briefing. Useful meta-commands:

| Command | Alias | What it does |
|---|---|---|
| `help` | | List all available in-game commands |
| `mission` | `m` | Re-read the current mission briefing |
| `hint` | `h` | Get a progressively more specific hint |
| `status` | `st` | Show your score and mission checklist |
| `quit` | `q` | Save and exit |

Your progress is saved automatically after every completed mission, to
`~/.linuxquest/save.json` (Linux/macOS) or
`C:\Users\<you>\.linuxquest\save.json` (Windows). Run with `--reset` to
wipe progress and start over:

```bash
python3 main.py --reset
```

## What you'll practice

- **Filesystem & files:** `ls`, `cd`, `pwd`, `cat`, `mkdir`, `touch`,
  `rm`, `cp`, `mv`, `find`, `grep`, `echo`, `head`, `tail`, `wc`
- **Permissions & users:** `chmod`, `chown`, `sudo`, `whoami`, `id`
- **Processes:** `ps`, `top`, `kill`
- **Networking:** `ifconfig`/`ip`, `ping`, `netstat`/`ss`, `curl`/`wget`,
  `dig`/`nslookup`, `traceroute`, `nmap`, `ssh`

## The 9 missions

1. **Orientation** — navigation basics
2. **Getting Organized** — creating, moving, and deleting files
3. **Permissions & Ownership** — `chmod`, `sudo`
4. **Search & Destroy** — `grep`, `find`
5. **Rogue Process** — `ps`/`top`/`kill`
6. **Network Reconnaissance** — `ifconfig`, `ping`
7. **Port Scanning** — `nmap`, `netstat`
8. **Web Recon** — `dig`, `curl`
9. **Breach the Vault (Capstone)** — tie it all together with `ssh`

## Project structure

```
linuxquest/
├── main.py              # entry point / game loop
├── engine/
│   ├── vfs.py            # virtual filesystem
│   ├── vnet.py           # virtual network (hosts, ports, DNS)
│   ├── shell.py          # command interpreter (the "bash" layer)
│   ├── missions.py       # mission definitions, world setup, progress
│   ├── save.py           # save/load progress to disk
│   ├── ui.py             # colored terminal output helpers
│   └── manpages.py       # text for the built-in `man` command
├── run.sh                # Linux/macOS launcher
├── run.bat               # Windows launcher
└── requirements.txt
```

## Extending it

Everything is data-driven in `engine/missions.py` — `build_game()` sets
up the virtual filesystem and network, and returns a list of `Mission`
objects. Each mission has a `briefing`, optional `hints`, and a
`check(shell)` function that returns `True` once the objective is met
(it can inspect the virtual filesystem directly, or look at
`shell.flags`, a set of breadcrumbs like `"read:/etc/app/app.conf"` or
`"pinged:aegis-corp.local"` that commands drop as they run). Adding a
new mission is just adding a new `Mission(...)` entry to the list.
