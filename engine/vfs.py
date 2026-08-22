"""
A tiny in-memory virtual filesystem, modelled loosely on a Linux ext4 tree.
Nothing here ever touches the real disk - it's all just nested Python objects,
which is what makes the game 100% safe to run anywhere (including Windows).
"""

import time


class Node:
    def __init__(self, name, is_dir, content="", mode=None, owner="player",
                 group="player"):
        self.name = name
        self.is_dir = is_dir
        self.content = content              # file contents (str)
        self.children = {} if is_dir else None
        self.mode = mode or ("rwxr-xr-x" if is_dir else "rw-r--r--")
        self.owner = owner
        self.group = group
        self.mtime = time.time()

    def perm_string(self):
        return ("d" if self.is_dir else "-") + self.mode

    def size(self):
        if self.is_dir:
            return 4096
        return len(self.content.encode("utf-8"))


class VFS:
    """A virtual filesystem with a single root, mounted per-host."""

    def __init__(self):
        self.root = Node("/", True, mode="rwxr-xr-x", owner="root", group="root")

    # ---------- path helpers ----------

    def _split(self, path):
        return [p for p in path.split("/") if p not in ("", ".")]

    def resolve(self, cwd_parts, path):
        """Return an absolute list-of-parts path for `path`, given cwd_parts."""
        if path.startswith("/"):
            parts = []
        else:
            parts = list(cwd_parts)
        for piece in path.split("/"):
            if piece in ("", "."):
                continue
            elif piece == "..":
                if parts:
                    parts.pop()
            else:
                parts.append(piece)
        return parts

    def get_node(self, parts):
        node = self.root
        for p in parts:
            if not node.is_dir or p not in node.children:
                return None
            node = node.children[p]
        return node

    def get_parent(self, parts):
        if not parts:
            return None
        parent = self.get_node(parts[:-1])
        return parent

    # ---------- mutation helpers used by mission setup code ----------

    def mkdir_p(self, path):
        parts = self._split(path)
        node = self.root
        for p in parts:
            if p not in node.children:
                node.children[p] = Node(p, True)
            node = node.children[p]
        return node

    def write_file(self, path, content, mode=None, owner="player"):
        parts = self._split(path)
        parent = self.mkdir_p("/".join(parts[:-1])) if len(parts) > 1 else self.root
        name = parts[-1]
        parent.children[name] = Node(name, False, content=content, mode=mode, owner=owner)
        return parent.children[name]

    def path_str(self, parts):
        return "/" + "/".join(parts)
