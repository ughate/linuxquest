#!/usr/bin/env python3
"""
LinuxQuest - learn Linux commands and basic networking by playing a
story-driven CLI game. Runs anywhere Python 3 runs (Linux, macOS, Windows).
Nothing in this game touches your real filesystem or network - it's all
simulated, so it's completely safe to run.
"""

import sys

from engine import ui, save
from engine.missions import build_game, MissionManager
from engine.shell import Shell


def main():
    print(ui.banner())

    state = save.load()
    if "--reset" in sys.argv:
        save.reset()
        state = save.load()
        ui.info("Progress reset. Starting fresh.\n")

    vnet, local_vfs, local_host, missions = build_game(state)
    mission_mgr = MissionManager(missions, state)
    shell = Shell(vnet, mission_mgr, local_vfs, local_host)

    print(f"Type {ui.color('help', ui.C.YELLOW)} for a command list, "
          f"{ui.color('mission', ui.C.YELLOW)} to reread your briefing, "
          f"{ui.color('hint', ui.C.YELLOW)} if stuck, "
          f"{ui.color('quit', ui.C.YELLOW)} to leave.\n")
    mission_mgr.print_current()
    print()

    while shell.running:
        try:
            line = input(shell.prompt())
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print("\n(use 'quit' to exit)")
            continue
        shell.run_line(line)

    print(ui.color("\nProgress saved. See you next time, recruit.\n", ui.C.CYAN))


if __name__ == "__main__":
    main()
