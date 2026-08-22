
# Browser adapter for LinuxQuest.
#
# This adapter intentionally avoids touching the real filesystem/network.
# It uses the game's existing modules where possible and translates the
# terminal interaction into a browser-driven command loop.

import os, sys, traceback, importlib

# The browser build is expected to preserve the original engine package.
# Try the original main module first. If its CLI is interactive, we expose
# a compatible command processor by importing the engine components.
try:
    import engine.shell as shell_mod
    import engine.vfs as vfs_mod
    import engine.vnet as vnet_mod
except Exception as exc:
    _import_error = exc
else:
    _import_error = None

_state = {}

def _find_class(mod, names):
    for n in names:
        obj = getattr(mod, n, None)
        if obj is not None:
            return obj
    return None

def _init():
    if _import_error:
        return
    # Keep initialization deliberately conservative: existing game modules
    # may expose different APIs. We instantiate the common shell if present.
    Shell = _find_class(shell_mod, ["Shell", "LinuxShell", "CommandShell"])
    VFS = _find_class(vfs_mod, ["VirtualFileSystem", "VFS", "FileSystem"])
    VNet = _find_class(vnet_mod, ["VirtualNetwork", "VNet", "Network"])

    _state["vfs"] = VFS() if VFS else None
    _state["vnet"] = VNet() if VNet else None
    _state["shell"] = None
    if Shell:
        for args in [
            (_state["vfs"], _state["vnet"]),
            (_state["vfs"],),
            ()
        ]:
            try:
                _state["shell"] = Shell(*args)
                break
            except Exception:
                pass

_init()

def browser_process_one():
    # Retrieve the queued line.
    if not _browser_input:
        return ""
    line = _browser_input.pop(0)

    if _import_error:
        return "Browser adapter could not import the existing engine: %s" % _import_error

    sh = _state.get("shell")
    if sh is None:
        return ("The existing LinuxQuest shell could not be instantiated automatically. "
                "The original engine API needs a small browser adapter.")

    # Try common method names used by CLI shell implementations.
    for name in ("execute", "run_command", "handle_command", "process_command", "command"):
        fn = getattr(sh, name, None)
        if callable(fn):
            try:
                out = fn(line)
                return "" if out is None else str(out)
            except TypeError:
                continue
            except Exception:
                return traceback.format_exc()

    return "No compatible command execution method was found in engine.shell."
