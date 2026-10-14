# --- system.py ---
# Thin wrappers around the system tools this app shells out to (nmcli,
# iw, ip). Everything is passed as an argv list - never through a shell -
# so SSIDs/passwords typed on the touchscreen can't inject commands. The
# app runs as root (needed for monitor mode), so there's no sudo here.

import os
import subprocess
import threading
import time

def run(args, timeout=30):
    """Returns (returncode, stdout, stderr). Never raises."""
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"{args[0]}: command not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"{args[0]}: timed out"

def _last_line(stdout, stderr, default):
    text = (stderr or stdout or "").strip()
    return text.splitlines()[-1] if text else default


class BackgroundTask:
    """Runs fn(*args) on a thread; poll .done, then read .result / .error.
    Used so slow nmcli/iw calls never freeze the touch UI."""
    def __init__(self, fn, *args):
        self.done = False
        self.result = None
        self.error = None
        threading.Thread(target=self._run, args=(fn, args), daemon=True).start()

    def _run(self, fn, args):
        try:
            self.result = fn(*args)
        except Exception as e:
            self.error = str(e) or e.__class__.__name__
        self.done = True


# ---- wireless interfaces / monitor mode ----

def parse_iw_dev(text):
    ifaces, cur = [], None
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[0] == "Interface":
            cur = {"name": parts[1], "mac": "", "type": ""}
            ifaces.append(cur)
        elif cur is not None and parts[0] == "addr":
            cur["mac"] = parts[1]
        elif cur is not None and parts[0] == "type":
            cur["type"] = parts[1]
    return ifaces

def _driver(name):
    path = f"/sys/class/net/{name}/device/driver"
    return os.path.basename(os.path.realpath(path)) if os.path.exists(path) else ""

def list_wireless_interfaces():
    rc, out, _ = run(["iw", "dev"])
    ifaces = parse_iw_dev(out) if rc == 0 else []
    for iface in ifaces:
        iface["driver"] = _driver(iface["name"])
    return ifaces

def wait_for_interface(name, timeout):
    """USB adapters can enumerate a few seconds after boot."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(f"/sys/class/net/{name}"):
            return True
        time.sleep(1)
    return os.path.exists(f"/sys/class/net/{name}")

def enable_monitor(iface):
    """Puts iface in monitor mode and tells NetworkManager to leave it alone
    (otherwise it grabs the adapter back and silently undoes monitor mode).
    Returns (ok, error_message)."""
    run(["rfkill", "unblock", "wifi"])
    run(["nmcli", "device", "set", iface, "managed", "no"])
    steps = [
        ["ip", "link", "set", iface, "down"],
        ["iw", "dev", iface, "set", "type", "monitor"],
        ["ip", "link", "set", iface, "up"],
    ]
    for args in steps:
        rc, out, err = run(args)
        if rc != 0:
            run(["ip", "link", "set", iface, "up"])  # leave it usable
            return False, _last_line(out, err, f"{' '.join(args[:3])} failed")
    rc, out, _ = run(["iw", "dev", iface, "info"])
    if "type monitor" not in out:
        return False, "interface did not enter monitor mode"
    return True, ""

def restore_managed(iface):
    """Best-effort: hand iface back to NetworkManager as a normal client."""
    run(["ip", "link", "set", iface, "down"])
    run(["iw", "dev", iface, "set", "type", "managed"])
    run(["ip", "link", "set", iface, "up"])
    run(["nmcli", "device", "set", iface, "managed", "yes"])


# ---- wifi client (NetworkManager) ----

def split_terse(line):
    """Splits an `nmcli -t` line on unescaped colons."""
    fields, cur, esc = [], [], False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields

def parse_wifi_list(text, saved):
    best = {}
    for line in text.splitlines():
        f = split_terse(line)
        if len(f) < 4 or not f[1]:
            continue
        in_use, ssid, signal, security = f[0].strip() == "*", f[1], f[2], f[3].strip()
        try:
            sig = int(signal)
        except ValueError:
            sig = 0
        entry = {
            "ssid": ssid,
            "signal": sig,
            "security": "" if security == "--" else security,
            "in_use": in_use,
            "saved": ssid in saved,
        }
        old = best.get(ssid)
        if old is None or in_use or (not old["in_use"] and sig > old["signal"]):
            best[ssid] = entry
    return sorted(best.values(), key=lambda e: (not e["in_use"], -e["signal"]))

def wifi_saved_names():
    rc, out, _ = run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
    names = set()
    for line in out.splitlines():
        f = split_terse(line)
        if len(f) >= 2 and f[1] in ("802-11-wireless", "wifi"):
            names.add(f[0])
    return names

def wifi_scan(iface, rescan=True):
    """Raises RuntimeError on failure (BackgroundTask turns that into .error)."""
    args = ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi",
            "list", "ifname", iface, "--rescan", "yes" if rescan else "no"]
    rc, out, err = run(args, timeout=40)
    if rc != 0:
        raise RuntimeError(_last_line(out, err, "scan failed"))
    return parse_wifi_list(out, wifi_saved_names())

def wifi_status(iface):
    """{"state": "connected"/"disconnected"/"unmanaged"/..., "connection": name, "ip": addr}"""
    status = {"state": "unknown", "connection": "", "ip": ""}
    rc, out, _ = run(["nmcli", "-t", "-f", "DEVICE,STATE,CONNECTION", "device", "status"])
    for line in out.splitlines():
        f = split_terse(line)
        if len(f) >= 3 and f[0] == iface:
            status["state"], status["connection"] = f[1], f[2]
    if status["state"] == "connected":
        rc, out, _ = run(["nmcli", "-g", "IP4.ADDRESS", "device", "show", iface])
        first = out.strip().splitlines()[0] if out.strip() else ""
        status["ip"] = first.split("/")[0]
    return status

def wifi_connect(iface, ssid, password=None, forget_first=False):
    """Returns (ok, error_message). With no password, uses the saved profile
    if there is one (or joins an open network)."""
    if forget_first:
        run(["nmcli", "connection", "delete", "id", ssid])
    if password is None and ssid in wifi_saved_names():
        args = ["nmcli", "-w", "25", "connection", "up", "id", ssid, "ifname", iface]
    else:
        args = ["nmcli", "-w", "25", "device", "wifi", "connect", ssid, "ifname", iface]
        if password:
            args += ["password", password]
    rc, out, err = run(args, timeout=45)
    return (True, "") if rc == 0 else (False, _last_line(out, err, "connection failed"))

def wifi_disconnect(iface):
    rc, out, err = run(["nmcli", "device", "disconnect", iface])
    return (True, "") if rc == 0 else (False, _last_line(out, err, "disconnect failed"))
