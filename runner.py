
import sys, io, json, traceback
from js import localStorage

from engine import save
from engine.missions import build_game, MissionManager
from engine.shell import Shell, Session
from engine import ui

# ---- Browser persistence -------------------------------------------------
def browser_load():
    raw = localStorage.getItem("linuxquest_save")
    if not raw:
        return {}
    try:
        return json.loads(str(raw))
    except Exception:
        return {}

def browser_save(state):
    localStorage.setItem("linuxquest_save", json.dumps(state))

def browser_reset():
    localStorage.removeItem("linuxquest_save")

save.load = browser_load
save.save = browser_save
save.reset = browser_reset

# ---- Output capture ------------------------------------------------------
class Capture:
    def __init__(self):
        self.buf = io.StringIO()
    def write(self, s):
        self.buf.write(str(s))
        return len(str(s))
    def flush(self):
        pass
    def get(self):
        return self.buf.getvalue()

_capture = Capture()

# ---- Browser-friendly shell ---------------------------------------------
class BrowserShell(Shell):
    def __init__(self, *args):
        super().__init__(*args)
        self.pending_password = None

    def browser_run_line(self, line):
        line = line.strip()

        # SSH password is collected by the browser as a second input.
        if self.pending_password is not None:
            host, user = self.pending_password
            self.pending_password = None
            if host.ssh_users.get(user) != line:
                ui.err("Permission denied, please try again.")
                return
            ui.ok(f"Welcome to {host.hostname} ({host.os_name})")
            new_procs = [
                {"pid": 1, "user": "root", "cmd": "systemd"},
                {"pid": 87, "user": "root", "cmd": "sshd"},
                {"pid": 150, "user": user, "cmd": "bash"},
            ]
            new_session = Session(host.hostname, host.ip, host.vfs,
                                  user=user, processes=new_procs)
            if host.vfs.get_node(["home", user]) is not None:
                new_session.cwd = ["home", user]
            self.stack.append(new_session)
            self.flags.add(f"ssh:{host.hostname}:{user}")
            self.mission_mgr.on_command(self, "ssh", [f"{user}@{host.hostname}"],
                                         f"ssh {user}@{host.hostname}")
            return

        # Browser implementation of ssh because getpass() cannot provide
        # an asynchronous browser prompt.
        if line.startswith("ssh "):
            import shlex
            try:
                parts = shlex.split(line)
            except ValueError as e:
                ui.err(f"parse error: {e}")
                return
            if len(parts) < 2:
                ui.err("ssh: usage: ssh user@host")
                return
            target = parts[1]
            if "@" in target:
                user, hostname = target.split("@", 1)
            else:
                user, hostname = self.sess.user, target
            host = self.vnet.resolve(hostname)
            if host is None:
                ui.err(f"ssh: Could not resolve hostname {hostname}")
                return
            if 22 not in host.ports:
                ui.err(f"ssh: connect to host {hostname} port 22: Connection refused")
                return
            if user not in host.ssh_users:
                ui.err("Permission denied (publickey,password).")
                return
            self.pending_password = (host, user)
            print(f"{user}@{hostname}'s password: ", end="")
            return

        # Everything else uses the original LinuxQuest shell.
        super().run_line(line)

# ---- Build the exact original game --------------------------------------
state = browser_load()
vnet, local_vfs, local_host, missions = build_game(state)
shell = BrowserShell(vnet, MissionManager(missions, state),
                     local_vfs, local_host)

# Initial screen.
def browser_start():
    out = Capture()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout = out
        sys.stderr = out
        print(ui.banner())
        print("Type help for a command list, mission to reread your briefing,")
        print("hint if stuck, status to see progress, or quit to leave.\n")
        shell.mission_mgr.print_current()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return out.get()

def browser_command(line):
    out = Capture()
    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout = out
        sys.stderr = out
        shell.browser_run_line(line)
        # Save after each command so browser refreshes retain progress.
        browser_save(shell.mission_mgr.state)
    except Exception:
        traceback.print_exc()
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return out.get()

def browser_prompt():
    return shell.prompt()

def browser_is_running():
    return shell.running
