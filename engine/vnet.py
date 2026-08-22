"""
A tiny virtual network: a handful of simulated hosts with IPs, open ports,
banners, HTTP content, and (for one or two of them) SSH credentials.
Nothing here makes a real network connection.
"""

from .vfs import VFS


class Host:
    def __init__(self, hostname, ip, os_name="Linux 6.2.0-x86_64"):
        self.hostname = hostname
        self.ip = ip
        self.os_name = os_name
        self.ports = {}          # port -> {"service": str, "banner": str}
        self.http = {}           # path -> content (served on port 80/443)
        self.ssh_users = {}      # username -> password
        self.vfs = VFS()         # filesystem visible once you ssh in
        self.up = True
        self.latency_ms = 12

    def add_port(self, port, service, banner=""):
        self.ports[port] = {"service": service, "banner": banner}
        return self

    def add_http(self, path, content):
        self.http[path] = content
        return self

    def add_ssh_user(self, username, password):
        self.ssh_users[username] = password
        return self


class VNet:
    def __init__(self):
        self.hosts = {}   # key can be hostname or ip -> Host
        self.dns = {}      # domain name -> ip

    def add_host(self, host: Host):
        self.hosts[host.hostname] = host
        self.hosts[host.ip] = host
        return host

    def resolve(self, target):
        """Accept hostname, domain (via dns), or ip; return Host or None."""
        if target in self.hosts:
            return self.hosts[target]
        if target in self.dns:
            ip = self.dns[target]
            return self.hosts.get(ip)
        return None

    def add_dns(self, domain, ip):
        self.dns[domain] = ip
