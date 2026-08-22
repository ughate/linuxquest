import fnmatch
import getpass
import os
import shlex
import time

from . import ui
from .manpages import MAN_PAGES
from .vfs import Node

PERM_INDEX = {"r": 0, "w": 1, "x": 2}


class Session:
    """One 'machine' the player is currently sitting at (local box or an
    ssh'd-into remote host)."""

    def __init__(self, hostname, ip, vfs, user="player", processes=None):
        self.hostname = hostname
        self.ip = ip
        self.vfs = vfs
        self.user = user
        self.cwd = []  # list of path components, [] == "/home/player" root-ish
        self.processes = processes or []


class Shell:
    def __init__(self, vnet, mission_mgr, local_vfs, local_host):
        self.vnet = vnet
        self.mission_mgr = mission_mgr
        self.local_host = local_host
        self.history = []
        default_procs = [
            {"pid": 101, "user": "root", "cmd": "systemd"},
            {"pid": 202, "user": "root", "cmd": "sshd"},
            {"pid": 340, "user": "player", "cmd": "bash"},
            {"pid": 512, "user": "root", "cmd": "cron"},
            {"pid": 999, "user": "nobody", "cmd": "xmrig-miner"},
        ]
        self.stack = [Session(local_host.hostname, local_host.ip, local_vfs,
                               user="player", processes=list(default_procs))]
        self.stack[0].cwd = ["home", "player"]
        self.running = True
        self.sudo_next = False
        self.flags = set()  # breadcrumbs that mission checks can look for,
                             # e.g. "read:/home/player/notes/secret.txt"

    # ------------------------------------------------------------------
    @property
    def sess(self):
        return self.stack[-1]

    def prompt(self):
        cwd = self.sess.vfs.path_str(self.sess.cwd)
        user = self.sess.user
        host = self.sess.hostname
        marker = "#" if user == "root" else "$"
        return f"{ui.color(user, ui.C.GREEN)}@{ui.color(host, ui.C.CYAN)}:{ui.color(cwd, ui.C.BLUE)}{marker} "

    # ------------------------------------------------------------------
    def run_line(self, line):
        line = line.strip()
        if not line:
            return
        self.history.append(line)

        as_root = False
        if line.startswith("sudo "):
            as_root = True
            line = line[len("sudo "):]

        try:
            parts = shlex.split(line)
        except ValueError as e:
            ui.err(f"parse error: {e}")
            return
        if not parts:
            return
        cmd, args = parts[0], parts[1:]
        handler = getattr(self, f"cmd_{cmd}", None)
        if handler is None:
            ui.err(f"{cmd}: command not found")
            return
        effective_user = "root" if as_root else self.sess.user
        try:
            handler(args, effective_user=effective_user)
        except PermissionError as e:
            ui.err(str(e))
        except Exception as e:
            ui.err(f"{cmd}: {e}")

        # let the active mission check whether this action completed an objective
        self.mission_mgr.on_command(self, cmd, args, line)

    # ------------------------------------------------------------------
    # permission helpers
    def _perms_for(self, node, user):
        if user == "root":
            return "rwx"
        mode = node.mode
        if user == node.owner:
            return mode[0:3]
        return mode[6:9]

    def _check(self, node, user, action):
        perms = self._perms_for(node, user)
        if perms[PERM_INDEX[action]] == "-":
            kind = "directory" if node.is_dir else "file"
            raise PermissionError(f"permission denied: {kind} '{node.name}' is not {action}-able by {user}")

    def _resolve_node(self, path):
        parts = self.sess.vfs.resolve(self.sess.cwd, path)
        return parts, self.sess.vfs.get_node(parts)

    # ------------------------------------------------------------------
    # filesystem commands
    def cmd_pwd(self, args, effective_user):
        print(self.sess.vfs.path_str(self.sess.cwd))

    def cmd_ls(self, args, effective_user):
        show_all = "-a" in args or "-la" in args or "-al" in args
        long_fmt = "-l" in args or "-la" in args or "-al" in args
        targets = [a for a in args if not a.startswith("-")]
        path = targets[0] if targets else "."
        parts, node = self._resolve_node(path)
        if node is None:
            ui.err(f"ls: cannot access '{path}': No such file or directory")
            return
        if not node.is_dir:
            if long_fmt:
                print(f"{node.perm_string()} {node.owner:<8}{node.group:<8}{node.size():>6} {node.name}")
            else:
                print(node.name)
            return
        self._check(node, effective_user, "r")
        names = sorted(node.children.keys())
        if not show_all:
            names = [n for n in names if not n.startswith(".")]
        if long_fmt:
            for n in names:
                c = node.children[n]
                print(f"{c.perm_string()} {c.owner:<8}{c.group:<8}{c.size():>6} {n}{'/' if c.is_dir else ''}")
        else:
            print("  ".join(n + ("/" if node.children[n].is_dir else "") for n in names))

    def cmd_cd(self, args, effective_user):
        path = args[0] if args else "/"
        parts = self.sess.vfs.resolve(self.sess.cwd, path)
        node = self.sess.vfs.get_node(parts)
        if node is None:
            ui.err(f"cd: no such directory: {path}")
            return
        if not node.is_dir:
            ui.err(f"cd: not a directory: {path}")
            return
        self._check(node, effective_user, "x")
        self.sess.cwd = parts

    def cmd_cat(self, args, effective_user):
        if not args:
            ui.err("cat: missing file operand")
            return
        for path in args:
            parts, node = self._resolve_node(path)
            if node is None:
                ui.err(f"cat: {path}: No such file or directory")
                continue
            if node.is_dir:
                ui.err(f"cat: {path}: Is a directory")
                continue
            self._check(node, effective_user, "r")
            print(node.content, end="" if node.content.endswith("\n") else "\n")
            self.flags.add(f"read:{self.sess.vfs.path_str(parts)}")

    def cmd_mkdir(self, args, effective_user):
        args = [a for a in args if a != "-p"]
        if not args:
            ui.err("mkdir: missing operand")
            return
        for path in args:
            parts = self.sess.vfs.resolve(self.sess.cwd, path)
            parent = self.sess.vfs.get_node(parts[:-1])
            if parent is None:
                ui.err(f"mkdir: cannot create directory '{path}': No such parent directory")
                continue
            self._check(parent, effective_user, "w")
            name = parts[-1]
            if name in parent.children:
                ui.err(f"mkdir: cannot create directory '{path}': File exists")
                continue
            parent.children[name] = Node(name, True, owner=effective_user)

    def cmd_touch(self, args, effective_user):
        if not args:
            ui.err("touch: missing operand")
            return
        for path in args:
            parts = self.sess.vfs.resolve(self.sess.cwd, path)
            parent = self.sess.vfs.get_node(parts[:-1])
            if parent is None:
                ui.err(f"touch: cannot touch '{path}': No such directory")
                continue
            self._check(parent, effective_user, "w")
            name = parts[-1]
            if name in parent.children:
                parent.children[name].mtime = time.time()
            else:
                parent.children[name] = Node(name, False, owner=effective_user)

    def cmd_rm(self, args, effective_user):
        recursive = "-r" in args or "-rf" in args
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            ui.err("rm: missing operand")
            return
        for path in targets:
            parts = self.sess.vfs.resolve(self.sess.cwd, path)
            node = self.sess.vfs.get_node(parts)
            parent = self.sess.vfs.get_node(parts[:-1])
            if node is None or parent is None:
                ui.err(f"rm: cannot remove '{path}': No such file or directory")
                continue
            if node.is_dir and node.children and not recursive:
                ui.err(f"rm: cannot remove '{path}': Is a directory (use -r)")
                continue
            self._check(parent, effective_user, "w")
            del parent.children[parts[-1]]

    def cmd_cp(self, args, effective_user):
        args = [a for a in args if a != "-r"]
        if len(args) < 2:
            ui.err("cp: missing file operand")
            return
        src, dst = args[0], args[1]
        _, snode = self._resolve_node(src)
        if snode is None:
            ui.err(f"cp: cannot stat '{src}': No such file or directory")
            return
        self._check(snode, effective_user, "r")
        dparts = self.sess.vfs.resolve(self.sess.cwd, dst)
        dnode = self.sess.vfs.get_node(dparts)
        if dnode is not None and dnode.is_dir:
            dparent, dname = dnode, snode.name
        else:
            dparent, dname = self.sess.vfs.get_node(dparts[:-1]), dparts[-1]
        if dparent is None:
            ui.err("cp: target directory does not exist")
            return
        self._check(dparent, effective_user, "w")
        import copy
        newnode = copy.deepcopy(snode)
        newnode.name = dname
        newnode.owner = effective_user
        dparent.children[dname] = newnode

    def cmd_mv(self, args, effective_user):
        if len(args) < 2:
            ui.err("mv: missing file operand")
            return
        src, dst = args[0], args[1]
        sparts = self.sess.vfs.resolve(self.sess.cwd, src)
        snode = self.sess.vfs.get_node(sparts)
        sparent = self.sess.vfs.get_node(sparts[:-1])
        if snode is None:
            ui.err(f"mv: cannot stat '{src}': No such file or directory")
            return
        self._check(sparent, effective_user, "w")
        dparts = self.sess.vfs.resolve(self.sess.cwd, dst)
        dnode = self.sess.vfs.get_node(dparts)
        if dnode is not None and dnode.is_dir:
            dparent, dname = dnode, snode.name
        else:
            dparent, dname = self.sess.vfs.get_node(dparts[:-1]), dparts[-1]
        if dparent is None:
            ui.err("mv: target directory does not exist")
            return
        self._check(dparent, effective_user, "w")
        del sparent.children[sparts[-1]]
        snode.name = dname
        dparent.children[dname] = snode

    def cmd_chmod(self, args, effective_user):
        if len(args) < 2:
            ui.err("chmod: missing operand")
            return
        mode_arg, path = args[0], args[1]
        parts, node = self._resolve_node(path)
        if node is None:
            ui.err(f"chmod: cannot access '{path}': No such file or directory")
            return
        if effective_user != "root" and node.owner != effective_user:
            raise PermissionError(f"chmod: changing permissions of '{path}': Operation not permitted")
        if mode_arg.isdigit() and len(mode_arg) == 3:
            def octal_to_rwx(d):
                d = int(d)
                return ("r" if d & 4 else "-") + ("w" if d & 2 else "-") + ("x" if d & 1 else "-")
            node.mode = "".join(octal_to_rwx(d) for d in mode_arg)
        elif mode_arg in ("+x", "-x", "+w", "-w", "+r", "-r"):
            sign, letter = mode_arg[0], mode_arg[1]
            mode = list(node.mode)
            for scope_start in (0, 3, 6):
                idx = scope_start + PERM_INDEX[letter]
                mode[idx] = letter if sign == "+" else "-"
            node.mode = "".join(mode)
        else:
            ui.err(f"chmod: invalid mode: '{mode_arg}' (try 3-digit octal like 755, or +x/-x)")
            return
        self.flags.add(f"chmod:{self.sess.vfs.path_str(parts)}:{node.mode}")

    def cmd_chown(self, args, effective_user):
        if len(args) < 2:
            ui.err("chown: missing operand")
            return
        if effective_user != "root":
            raise PermissionError("chown: Operation not permitted (try sudo)")
        new_owner, path = args[0], args[1]
        parts, node = self._resolve_node(path)
        if node is None:
            ui.err(f"chown: cannot access '{path}': No such file or directory")
            return
        node.owner = new_owner

    def cmd_find(self, args, effective_user):
        path = "."
        pattern = "*"
        i = 0
        rest = list(args)
        if rest and not rest[0].startswith("-"):
            path = rest.pop(0)
        if "-name" in rest:
            idx = rest.index("-name")
            pattern = rest[idx + 1]
        parts, node = self._resolve_node(path)
        if node is None:
            ui.err(f"find: '{path}': No such file or directory")
            return

        found_any = False

        def walk(n, cur_parts):
            nonlocal found_any
            full = self.sess.vfs.path_str(cur_parts) if cur_parts else "/"
            if fnmatch.fnmatch(n.name, pattern) or (not cur_parts and pattern in ("*", "")):
                if cur_parts:
                    print(full)
                    found_any = True
            if n.is_dir:
                for name, child in sorted(n.children.items()):
                    walk(child, cur_parts + [name])

        walk(node, parts)
        if found_any:
            self.flags.add(f"found:{pattern}")

    def cmd_grep(self, args, effective_user):
        recursive = "-r" in args
        icase = "-i" in args
        show_lines = "-n" in args
        rest = [a for a in args if a not in ("-r", "-i", "-n")]
        if len(rest) < 2:
            ui.err("grep: usage: grep [-rin] pattern path")
            return
        pattern, path = rest[0], rest[1]
        parts, node = self._resolve_node(path)
        if node is None:
            ui.err(f"grep: {path}: No such file or directory")
            return

        found_any = [False]

        def search_file(n, label):
            lines = n.content.split("\n")
            for i, line in enumerate(lines, start=1):
                hay, needle = (line.lower(), pattern.lower()) if icase else (line, pattern)
                if needle in hay:
                    found_any[0] = True
                    prefix = f"{label}:" if recursive else ""
                    lineno = f"{i}:" if show_lines else ""
                    print(f"{prefix}{lineno}{line}")

        if node.is_dir:
            if not recursive:
                ui.err(f"grep: {path}: Is a directory")
                return

            def walk(n, cur_parts):
                full = self.sess.vfs.path_str(cur_parts)
                if n.is_dir:
                    for name, child in sorted(n.children.items()):
                        walk(child, cur_parts + [name])
                else:
                    search_file(n, full)

            walk(node, parts)
        else:
            search_file(node, path)

        if found_any[0]:
            self.flags.add(f"grepped:{pattern}")

    def cmd_echo(self, args, effective_user):
        if ">>" in args:
            idx = args.index(">>")
            text = " ".join(args[:idx])
            target = args[idx + 1]
            append = True
        elif ">" in args:
            idx = args.index(">")
            text = " ".join(args[:idx])
            target = args[idx + 1]
            append = False
        else:
            print(" ".join(args))
            return
        parts = self.sess.vfs.resolve(self.sess.cwd, target)
        parent = self.sess.vfs.get_node(parts[:-1])
        if parent is None:
            ui.err("echo: no such directory")
            return
        name = parts[-1]
        if name in parent.children:
            node = parent.children[name]
            self._check(node, effective_user, "w")
            node.content = (node.content + text + "\n") if append else (text + "\n")
        else:
            self._check(parent, effective_user, "w")
            parent.children[name] = Node(name, False, content=text + "\n", owner=effective_user)

    def cmd_head(self, args, effective_user):
        self._head_tail(args, effective_user, from_end=False)

    def cmd_tail(self, args, effective_user):
        self._head_tail(args, effective_user, from_end=True)

    def _head_tail(self, args, effective_user, from_end):
        n = 10
        if "-n" in args:
            idx = args.index("-n")
            n = int(args[idx + 1])
            args = args[:idx] + args[idx + 2:]
        if not args:
            ui.err("missing file operand")
            return
        _, node = self._resolve_node(args[0])
        if node is None or node.is_dir:
            ui.err(f"{args[0]}: No such file")
            return
        self._check(node, effective_user, "r")
        lines = node.content.split("\n")
        chunk = lines[-n:] if from_end else lines[:n]
        print("\n".join(chunk))

    def cmd_wc(self, args, effective_user):
        lines_only = "-l" in args
        targets = [a for a in args if not a.startswith("-")]
        if not targets:
            ui.err("wc: missing file operand")
            return
        _, node = self._resolve_node(targets[0])
        if node is None or node.is_dir:
            ui.err(f"wc: {targets[0]}: No such file")
            return
        self._check(node, effective_user, "r")
        content = node.content
        lc = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        wc_ = len(content.split())
        cc = len(content)
        if lines_only:
            print(f"{lc} {targets[0]}")
        else:
            print(f"{lc} {wc_} {cc} {targets[0]}")

    def cmd_whoami(self, args, effective_user):
        print(self.sess.user)

    def cmd_id(self, args, effective_user):
        u = self.sess.user
        uid = 0 if u == "root" else 1000
        print(f"uid={uid}({u}) gid={uid}({u}) groups={uid}({u})")

    def cmd_clear(self, args, effective_user):
        os.system("cls" if os.name == "nt" else "clear")

    def cmd_history(self, args, effective_user):
        for i, h in enumerate(self.history, start=1):
            print(f"{i:>4}  {h}")

    def cmd_man(self, args, effective_user):
        if not args:
            ui.err("man: what manual page do you want?")
            return
        page = MAN_PAGES.get(args[0])
        print(page if page else f"No manual entry for {args[0]}")

    def cmd_help(self, args, effective_user):
        print(ui.color("Filesystem: ", ui.C.YELLOW) + "ls cd pwd cat mkdir touch rm cp mv chmod chown find grep echo head tail wc")
        print(ui.color("System:     ", ui.C.YELLOW) + "whoami id ps top kill df du sudo history clear man")
        print(ui.color("Networking: ", ui.C.YELLOW) + "ifconfig ping netstat curl wget dig traceroute nmap ssh exit")
        print(ui.color("Game:       ", ui.C.YELLOW) + "mission (m), hint (h), status (st), quit")

    def cmd_df(self, args, effective_user):
        print("Filesystem     1K-blocks     Used Available Use% Mounted on")
        print("/dev/sda1       20480000  4821312  14612000  25% /")

    def cmd_du(self, args, effective_user):
        path = args[0] if args and not args[0].startswith("-") else "."
        _, node = self._resolve_node(path)
        if node is None:
            ui.err(f"du: {path}: No such file or directory")
            return

        def total(n):
            if not n.is_dir:
                return n.size()
            return sum(total(c) for c in n.children.values()) + 4096

        print(f"{total(node) // 1024}K\t{path}")

    def cmd_ps(self, args, effective_user):
        print(f"{'PID':>6} {'USER':<10}{'CMD'}")
        for p in self.sess.processes:
            print(f"{p['pid']:>6} {p['user']:<10}{p['cmd']}")

    def cmd_top(self, args, effective_user):
        print("top - load average: 0.15, 0.09, 0.05")
        print(f"Tasks: {len(self.sess.processes)} total")
        print(f"{'PID':>6} {'USER':<10}{'%CPU':>6} {'%MEM':>6} {'CMD'}")
        for p in self.sess.processes:
            print(f"{p['pid']:>6} {p['user']:<10}{'0.3':>6} {'1.2':>6} {p['cmd']}")

    def cmd_kill(self, args, effective_user):
        if not args:
            ui.err("kill: usage: kill <pid>")
            return
        try:
            pid = int(args[-1])
        except ValueError:
            ui.err("kill: pid must be a number")
            return
        proc = next((p for p in self.sess.processes if p["pid"] == pid), None)
        if proc is None:
            ui.err(f"kill: ({pid}) - No such process")
            return
        if proc["user"] == "root" and effective_user != "root":
            raise PermissionError(f"kill: ({pid}) - Operation not permitted")
        self.sess.processes.remove(proc)
        ui.ok(f"process {pid} ({proc['cmd']}) terminated")
        self.flags.add(f"killed:{pid}")

    # ------------------------------------------------------------------
    # networking commands
    def cmd_ifconfig(self, args, effective_user):
        h = self.local_host if len(self.stack) == 1 else self.vnet.resolve(self.sess.hostname)
        ip = self.sess.ip
        print("eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500")
        print(f"      inet {ip}  netmask 255.255.255.0")
        print("lo:   flags=73<UP,LOOPBACK,RUNNING>  mtu 65536")
        print("      inet 127.0.0.1  netmask 255.0.0.0")

    cmd_ip = cmd_ifconfig  # `ip a` alias (simplified, ignores the 'a' arg)

    def cmd_ping(self, args, effective_user):
        if not args:
            ui.err("ping: usage: ping <host>")
            return
        target = args[-1]
        host = self.vnet.resolve(target)
        if host is None or not host.up:
            print(f"ping: {target}: Name or service not known" if host is None else
                  f"connect: Network is unreachable")
            return
        print(f"PING {target} ({host.ip}) 56(84) bytes of data.")
        for i in range(4):
            print(f"64 bytes from {host.ip}: icmp_seq={i+1} ttl=64 time={host.latency_ms + i*0.3:.1f} ms")
        print(f"\n--- {target} ping statistics ---")
        print("4 packets transmitted, 4 received, 0% packet loss")
        self.flags.add(f"pinged:{target}")

    def cmd_netstat(self, args, effective_user):
        host = self.vnet.resolve(self.sess.hostname) or self.local_host
        print("Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program")
        for port, info in sorted(host.ports.items()):
            print(f"tcp        0      0 0.0.0.0:{port:<15}0.0.0.0:*               LISTEN      -/{info['service']}")

    cmd_ss = cmd_netstat

    def cmd_curl(self, args, effective_user):
        args = [a for a in args if not a.startswith("-")]
        if not args:
            ui.err("curl: try 'curl <url>'")
            return
        url = args[0]
        target, path = self._split_url(url)
        host = self.vnet.resolve(target)
        if host is None:
            ui.err(f"curl: (6) Could not resolve host: {target}")
            return
        if 80 not in host.ports and 443 not in host.ports:
            ui.err("curl: (7) Failed to connect: Connection refused")
            return
        content = host.http.get(path)
        if content is None:
            print("HTTP/1.1 404 Not Found")
            return
        print(content)
        self.flags.add(f"curled:{target}{path}")

    cmd_wget = cmd_curl

    def _split_url(self, url):
        url = url.replace("http://", "").replace("https://", "")
        if "/" in url:
            target, path = url.split("/", 1)
            path = "/" + path
        else:
            target, path = url, "/"
        return target, path

    def cmd_dig(self, args, effective_user):
        if not args:
            ui.err("dig: usage: dig <domain>")
            return
        domain = args[0]
        ip = self.vnet.dns.get(domain)
        print(f"; <<>> DigSim 1.0 <<>> {domain}")
        if ip:
            print(f"{domain}.\t\t300\tIN\tA\t{ip}")
            self.flags.add(f"digged:{domain}")
        else:
            print(f";; connection timed out; no servers could be reached (NXDOMAIN)")

    cmd_nslookup = cmd_dig

    def cmd_traceroute(self, args, effective_user):
        if not args:
            ui.err("traceroute: usage: traceroute <host>")
            return
        target = args[0]
        host = self.vnet.resolve(target)
        if host is None:
            ui.err(f"traceroute: unknown host {target}")
            return
        print(f"traceroute to {target} ({host.ip}), 30 hops max")
        print(f" 1  gateway (10.0.0.1)  1.102 ms")
        print(f" 2  isp-core (172.16.0.1)  8.311 ms")
        print(f" 3  {host.hostname} ({host.ip})  {host.latency_ms:.3f} ms")

    def cmd_nmap(self, args, effective_user):
        if not args:
            ui.err("nmap: usage: nmap <host>")
            return
        target = args[-1]
        host = self.vnet.resolve(target)
        if host is None:
            ui.err(f"nmap: could not resolve {target}")
            return
        print(f"Starting Nmap scan report for {host.hostname} ({host.ip})")
        print("Host is up.")
        print(f"{'PORT':<12}{'STATE':<10}SERVICE")
        for port, info in sorted(host.ports.items()):
            print(f"{str(port)+'/tcp':<12}{'open':<10}{info['service']}")
        self.flags.add(f"nmapped:{target}")

    def cmd_ssh(self, args, effective_user):
        if not args:
            ui.err("ssh: usage: ssh user@host")
            return
        target = args[0]
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
            ui.err(f"Permission denied (publickey,password).")
            return
        try:
            pw = getpass.getpass(f"{user}@{hostname}'s password: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if host.ssh_users[user] != pw:
            ui.err("Permission denied, please try again.")
            return
        ui.ok(f"Welcome to {host.hostname} ({host.os_name})")
        new_procs = [
            {"pid": 1, "user": "root", "cmd": "systemd"},
            {"pid": 87, "user": "root", "cmd": "sshd"},
            {"pid": 150, "user": user, "cmd": "bash"},
        ]
        new_session = Session(host.hostname, host.ip, host.vfs, user=user, processes=new_procs)
        if host.vfs.get_node(["home", user]) is not None:
            new_session.cwd = ["home", user]
        self.stack.append(new_session)
        self.flags.add(f"ssh:{host.hostname}:{user}")

    def cmd_exit(self, args, effective_user):
        if len(self.stack) > 1:
            self.stack.pop()
            print("logout")
        else:
            self.running = False

    cmd_logout = cmd_exit

    # ------------------------------------------------------------------
    # game meta-commands
    def cmd_mission(self, args, effective_user):
        self.mission_mgr.print_current()

    cmd_m = cmd_mission

    def cmd_hint(self, args, effective_user):
        self.mission_mgr.give_hint()

    cmd_h = cmd_hint

    def cmd_status(self, args, effective_user):
        self.mission_mgr.print_status()

    cmd_st = cmd_status

    def cmd_quit(self, args, effective_user):
        self.running = False

    cmd_q = cmd_quit
