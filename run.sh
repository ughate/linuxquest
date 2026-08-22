#!/usr/bin/env bash
# Launcher for LinuxQuest on Linux / macOS.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if ! command -v python3 &> /dev/null; then
    echo "python3 was not found. Install it with your distro's package manager,"
    echo "e.g. 'sudo apt install python3 python3-pip' on Ubuntu/Debian."
    exit 1
fi

python3 -c "import colorama" 2>/dev/null || pip3 install -r requirements.txt --quiet --break-system-packages 2>/dev/null || pip3 install -r requirements.txt --quiet --user

python3 main.py "$@"
