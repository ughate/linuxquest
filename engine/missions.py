from . import ui, save
from .vfs import VFS
from .vnet import VNet, Host


def _node(vfs, path_parts):
    node = vfs.root
    for p in path_parts:
        if not node.is_dir or p not in node.children:
            return None
        node = node.children[p]
    return node


class Mission:
    def __init__(self, key, title, briefing, check, hints=None, points=100):
        self.key = key
        self.title = title
        self.briefing = briefing
        self.check = check
        self.hints = hints or []
        self.points = points


class MissionManager:
    def __init__(self, missions, state):
        self.missions = missions
        self.state = state
        self.idx = min(state.get("current_mission", 0), len(missions))
        self.hint_idx = 0

    def current(self):
        if self.idx >= len(self.missions):
            return None
        return self.missions[self.idx]

    def print_current(self):
        m = self.current()
        if m is None:
            ui.title("Campaign complete")
            print("You've finished every mission. Type 'status' to see your score, or 'quit' to exit.")
            return
        ui.title(f"Mission {self.idx + 1}/{len(self.missions)}: {m.title}")
        print(m.briefing.strip())
        print(ui.color("\n(type 'hint' if you get stuck, 'status' to see progress, 'mission' to reread this)", ui.C.DIM))

    def give_hint(self):
        m = self.current()
        if m is None:
            print("No active mission.")
            return
        if not m.hints:
            print("No hints available for this mission - you've got this.")
            return
        hint = m.hints[min(self.hint_idx, len(m.hints) - 1)]
        ui.info(f"Hint: {hint}")
        self.hint_idx = min(self.hint_idx + 1, len(m.hints) - 1)
        self.state["hints_used"] = self.state.get("hints_used", 0) + 1
        save.save(self.state)

    def print_status(self):
        ui.title("Progress")
        print(f"Score: {self.state.get('score', 0)}")
        completed = self.state.get("completed", [])
        print(f"Missions completed: {len(completed)}/{len(self.missions)}")
        for i, m in enumerate(self.missions):
            if m.key in completed:
                mark = ui.color("x", ui.C.GREEN)
            elif i == self.idx:
                mark = ui.color(">", ui.C.YELLOW)
            else:
                mark = " "
            print(f" [{mark}] {i + 1}. {m.title}")

    def on_command(self, shell, cmd, args, line):
        m = self.current()
        if m is None:
            return
        try:
            done = bool(m.check(shell))
        except Exception:
            done = False
        if done and m.key not in self.state.get("completed", []):
            self.state.setdefault("completed", []).append(m.key)
            self.state["score"] = self.state.get("score", 0) + m.points
            print()
            ui.ok(f"Mission complete: {m.title}  (+{m.points} points)")
            self.idx += 1
            self.hint_idx = 0
            self.state["current_mission"] = self.idx
            save.save(self.state)
            print()
            self.print_current()


def build_game(state):
    """Build the virtual world (filesystem + network) and the mission list.
    Returns (vnet, local_vfs, local_host, missions)."""

    local_vfs = VFS()

    local_vfs.write_file("/home/player/welcome.txt",
        "Welcome to LinuxQuest, recruit.\n"
        "You've just been onboarded to the Aegis Corp security team.\n"
        "Look around your home directory to get your bearings. Your\n"
        "supervisor left something for you in the notes/ folder.\n")
    local_vfs.write_file("/home/player/notes/secret.txt",
        "Nice work finding this.\nYour temporary access code is: A1B2-C3D4\n"
        "Keep exploring - there's more to do.\n")

    local_vfs.write_file("/home/player/inbox/report1.txt", "Q1 findings: all systems nominal.\n")
    local_vfs.write_file("/home/player/inbox/report2.txt", "Q2 findings: minor anomalies logged.\n")
    local_vfs.write_file("/home/player/inbox/spam1.txt", "You won a free cruise!!! click now\n")
    local_vfs.write_file("/home/player/inbox/spam2.txt", "Re: Re: Re: hot singles near you\n")

    local_vfs.write_file("/home/player/locked.txt", "TOP SECRET: launch codes are 00000.\n",
                          owner="root")
    _node(local_vfs, ["home", "player", "locked.txt"]).mode = "rw-------"
    local_vfs.write_file("/home/player/script.sh", "#!/bin/bash\necho 'deploying build...'\n")
    _node(local_vfs, ["home", "player", "script.sh"]).mode = "rw-r--r--"

    local_vfs.write_file("/var/log/app.log",
        "2026-01-04 10:02:11 INFO  app started\n"
        "2026-01-04 10:02:14 INFO  connected to db\n"
        "2026-01-04 10:03:45 ERROR failed to reach payment gateway\n"
        "2026-01-04 10:03:46 INFO  retrying...\n"
        "2026-01-04 10:04:02 ERROR timeout contacting db-host on port 22\n"
        "2026-01-04 10:05:00 INFO  recovered\n")
    local_vfs.write_file("/etc/app/app.conf",
        "# Aegis Corp service configuration\n"
        "service.name=aegis-api\n"
        "service.port=8080\n"
        "# TODO: rotate these before prod! -ops team\n"
        "db.host=db-host\n"
        "db.ssh_user=dbadmin\n"
        "db.ssh_pass=Tr0ub4dor&3\n")

    local_host = Host("recruit-pc", "10.0.0.5")
    local_host.add_port(22, "ssh")

    vnet = VNet()
    vnet.add_host(local_host)

    web = Host("webserver", "203.0.113.10")
    web.add_port(80, "http")
    web.add_http("/", "Welcome to the Aegis Corp internal portal.\nAll systems: OK\n")
    web.add_http("/status.json",
        '{"service": "aegis-api", "status": "degraded", '
        '"hint": "the database host has been acting up - dig in"}\n')
    vnet.add_host(web)
    vnet.add_dns("aegis-corp.local", web.ip)

    db = Host("db-host", "203.0.113.20")
    db.add_port(22, "ssh")
    db.add_port(5432, "postgresql")
    db.add_ssh_user("dbadmin", "Tr0ub4dor&3")
    db.vfs.write_file("/home/dbadmin/flag.txt", "CTF{welcome_to_the_network}\n"
                       "Congratulations, you've completed LinuxQuest!\n")
    vnet.add_host(db)

    def has_flag(shell, prefix):
        return any(f.startswith(prefix) for f in shell.flags)

    missions = [
        Mission(
            key="orientation",
            title="Orientation",
            briefing="""
Your supervisor's note is in your home directory.

  1. List the contents of your home directory (ls).
  2. Read welcome.txt (cat welcome.txt).
  3. Explore the notes/ folder and read what's inside.

Find your access code to complete this mission.
""",
            check=lambda shell: "read:/home/player/notes/secret.txt" in shell.flags,
            hints=[
                "Try 'ls' to see what's in your home directory.",
                "Use 'cd notes' then 'ls' to look inside that folder.",
                "Use 'cat secret.txt' while inside the notes/ folder.",
            ],
            points=50,
        ),
        Mission(
            key="organize",
            title="Getting Organized",
            briefing="""
Your inbox is a mess. Aegis Corp policy: keep reports, delete spam.

  1. Create a directory called 'archive' in your home folder.
  2. Move both report*.txt files from inbox/ into archive/.
  3. Delete both spam*.txt files from inbox/.
""",
            check=lambda shell: (
                (lambda archive, inbox: bool(
                    archive and inbox and
                    {"report1.txt", "report2.txt"} <= set(archive.children.keys()) and
                    "spam1.txt" not in inbox.children and
                    "spam2.txt" not in inbox.children
                ))(
                    _node(local_vfs, ["home", "player", "archive"]),
                    _node(local_vfs, ["home", "player", "inbox"]),
                )
            ),
            hints=[
                "Use 'mkdir archive' from your home directory.",
                "Use 'mv inbox/report1.txt archive/' (repeat for report2.txt).",
                "Use 'rm inbox/spam1.txt inbox/spam2.txt' to delete the spam.",
            ],
            points=75,
        ),
        Mission(
            key="permissions",
            title="Permissions & Ownership",
            briefing="""
Two files need attention:

  1. locked.txt is owned by root and you can't read it normally.
     Use 'sudo cat locked.txt' to read it as root.
  2. script.sh needs to become executable. Give the owner execute
     permission with 'chmod +x script.sh'.
""",
            check=lambda shell: (
                "read:/home/player/locked.txt" in shell.flags and
                any(f.startswith("chmod:/home/player/script.sh:") and f.split(":")[-1][2] == "x"
                    for f in shell.flags)
            ),
            hints=[
                "Prefix any command with 'sudo' to run it as root.",
                "'sudo cat locked.txt' reads the root-owned file.",
                "'chmod +x script.sh' adds execute permission for the owner.",
            ],
            points=100,
        ),
        Mission(
            key="search",
            title="Search & Destroy",
            briefing="""
Something's wrong with the app. Investigate the logs and config:

  1. Search /var/log/app.log for lines containing 'ERROR'
     (grep -n ERROR /var/log/app.log).
  2. Find the config file under /etc (find /etc -name "*.conf").
  3. Read that config file with cat.
""",
            check=lambda shell: (
                has_flag(shell, "grepped:ERROR") and
                has_flag(shell, "found:*.conf") and
                "read:/etc/app/app.conf" in shell.flags
            ),
            hints=[
                "Try: grep -n ERROR /var/log/app.log",
                "Try: find /etc -name \"*.conf\"",
                "Once you know the path, 'cat' it to read the contents.",
            ],
            points=100,
        ),
        Mission(
            key="processes",
            title="Rogue Process",
            briefing="""
Something is hammering the CPU on this machine. Use 'ps' or 'top' to
list running processes, spot the suspicious one, and kill it by PID.
""",
            check=lambda shell: has_flag(shell, "killed:999"),
            hints=[
                "Run 'ps' and look for a process that doesn't belong.",
                "A cryptominer process is running as user 'nobody'.",
                "Use 'kill <pid>' with that process's PID (it's 999).",
            ],
            points=100,
        ),
        Mission(
            key="recon",
            title="Network Reconnaissance",
            briefing="""
Time to look outward. Check your own network interface, then see if
you can reach the Aegis Corp web server at 'aegis-corp.local'.

  1. Run 'ifconfig' (or 'ip a') to see your own IP address.
  2. 'ping aegis-corp.local' to check it's reachable.
""",
            check=lambda shell: has_flag(shell, "pinged:aegis-corp.local") or has_flag(shell, "pinged:203.0.113.10"),
            hints=[
                "Try 'ifconfig' first just to see your own network info.",
                "Then try: ping aegis-corp.local",
            ],
            points=75,
        ),
        Mission(
            key="scanning",
            title="Port Scanning",
            briefing="""
Reachability isn't enough - find out what services are actually
running.

  1. Scan the web server: nmap aegis-corp.local
  2. Check what's listening locally on this machine: netstat -tulnp
""",
            check=lambda shell: has_flag(shell, "nmapped:aegis-corp.local") or has_flag(shell, "nmapped:203.0.113.10"),
            hints=[
                "Try: nmap aegis-corp.local",
                "Then try: netstat -tulnp   (or 'ss -tulnp')",
            ],
            points=100,
        ),
        Mission(
            key="webrecon",
            title="Web Recon",
            briefing="""
The web server is up. Dig a little deeper into what it's serving.

  1. Resolve its domain name: dig aegis-corp.local
  2. Fetch its status page: curl http://aegis-corp.local/status.json
""",
            check=lambda shell: (
                has_flag(shell, "digged:aegis-corp.local") and
                has_flag(shell, "curled:aegis-corp.local")
            ),
            hints=[
                "Try: dig aegis-corp.local",
                "Try: curl http://aegis-corp.local/status.json",
            ],
            points=100,
        ),
        Mission(
            key="capstone",
            title="Breach the Vault (Capstone)",
            briefing="""
You found database credentials earlier in /etc/app/app.conf. Use
them to SSH into db-host and retrieve the flag file from the admin's
home directory.

  1. ssh dbadmin@db-host
  2. When prompted, enter the password you found in app.conf.
  3. Once connected, use 'ls' and 'cat flag.txt' to grab the flag.
  4. Type 'exit' to log out of the remote host when you're done.
""",
            check=lambda shell: (
                has_flag(shell, "ssh:db-host:dbadmin") and
                "read:/home/dbadmin/flag.txt" in shell.flags
            ),
            hints=[
                "Try: ssh dbadmin@db-host",
                "The password is in /etc/app/app.conf (db.ssh_pass).",
                "Once logged in: ls, then cat flag.txt",
            ],
            points=200,
        ),
    ]

    return vnet, local_vfs, local_host, missions
