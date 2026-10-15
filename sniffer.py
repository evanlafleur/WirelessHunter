# --- sniffer.py ---
# Passive 802.11 beacon/probe-response sniffer. Requires the interface to
# already be in monitor mode (see README). Maintains a live dict of seen APs.

import os
import time
import threading
from collections import deque
from scapy.all import AsyncSniffer, Dot11, Dot11Beacon, Dot11ProbeResp, RadioTap

import beacon
import config
import system
from apgroup import inherit_vendors
from oui import OuiLookup

HISTORY_LEN = 40   # ~ last 40 readings for the tracking screen's mini-graph

class Tracker:
    def __init__(self, iface, manuf_path):
        self.iface = iface
        self.oui = OuiLookup(manuf_path, background=True)   # 3 MB database: don't delay startup
        self.lock = threading.Lock()
        self.networks = {}   # bssid -> dict(ssid, vendor, band, channel, rssi, last_seen)
        self.history = {}    # bssid -> deque of recent rssi readings
        self._stop = False
        self._locked_channel = None   # set to a channel number to stop hopping
        self.status = "starting..."   # shown on the list screen while it's empty
        self._sniffer = None          # scapy AsyncSniffer, None when not capturing
        self._ctl_lock = threading.Lock()   # serializes start/switch of capture
        self._hop_paused = False

    def lock_channel(self, channel):
        """Stop hopping and sit on one channel - use while tracking a target."""
        self._locked_channel = channel
        os.system(f"iw dev {self.iface} set channel {channel} > /dev/null 2>&1")

    def unlock_channel(self):
        """Resume normal channel hopping."""
        self._locked_channel = None

    # ---- channel hopping ----
    def _hop_channels(self):
        all_channels = [(c, "2.4G") for c in config.CHANNELS_24] + \
                       [(c, "5G") for c in config.CHANNELS_5]
        i = 0
        while not self._stop:
            if self._sniffer is None or self._hop_paused:
                time.sleep(0.2)
                continue
            if self._locked_channel is not None:
                # stay put; just re-assert the channel occasionally in case
                # the driver drifts, then sleep without advancing the hop index
                os.system(f"iw dev {self.iface} set channel {self._locked_channel} > /dev/null 2>&1")
                time.sleep(config.HOP_INTERVAL_SEC)
                continue
            ch, band = all_channels[i % len(all_channels)]
            os.system(f"iw dev {self.iface} set channel {ch} > /dev/null 2>&1")
            time.sleep(config.HOP_INTERVAL_SEC)
            i += 1

    # ---- packet handling ----
    def _handle(self, pkt):
        if not pkt.haslayer(Dot11):
            return
        if not (pkt.haslayer(Dot11Beacon) or pkt.haslayer(Dot11ProbeResp)):
            return

        bssid = pkt[Dot11].addr3
        if not bssid:
            return

        info = beacon.parse(pkt)
        try:
            rssi = pkt[RadioTap].dBm_AntSignal
        except Exception:
            rssi = None

        vendor = self.oui.lookup(bssid)
        now = time.time()

        with self.lock:
            entry = self.networks.get(bssid, {})
            entry.update({
                "bssid": bssid,
                "ssid": info["ssid"],   # None => hidden
                "vendor": vendor,
                "rssi": rssi if rssi is not None else entry.get("rssi"),
                "last_seen": now,
                "first_seen": entry.get("first_seen", now),
                "beacons": entry.get("beacons", 0) + 1,
                "wps": entry.get("wps", False) or info["wps"],
            })
            # keep what we already knew when this particular frame doesn't carry a field
            for key in ("channel", "band", "security", "standard", "country", "interval"):
                value = info[key]
                if value is None:
                    continue
                if key == "security" and value in ("Open", "WEP") and entry.get("security") not in (None, "Open", "WEP"):
                    continue   # a frame that merely lacks the RSN element isn't evidence the AP dropped its encryption
                entry[key] = value
            entry.setdefault("band", "5G")
            if rssi is not None:
                entry["rssi_max"] = max(entry.get("rssi_max", rssi), rssi)
            self.networks[bssid] = entry

            if rssi is not None:
                hist = self.history.setdefault(bssid, deque(maxlen=HISTORY_LEN))
                hist.append(rssi)

    def get_history(self, bssid):
        with self.lock:
            hist = self.history.get(bssid)
            return list(hist) if hist else []

    # ---- capture lifecycle ----
    def start(self):
        threading.Thread(target=self._hop_channels, daemon=True).start()
        threading.Thread(target=self._initial_capture, daemon=True).start()

    def _initial_capture(self):
        # Runs off the main thread so the UI comes up immediately even if
        # the adapter is slow to appear (or missing - Settings > Scan
        # Antenna can then pick a different one).
        with self._ctl_lock:
            iface = self.iface
            self.status = f"waiting for {iface}..."
            if not system.wait_for_interface(iface, 60):
                self.status = f"{iface} not found - pick another in Settings > Scan Antenna"
                return
            self.status = f"enabling monitor mode on {iface}..."
            ok, err = system.enable_monitor(iface)
            if not ok:
                self.status = f"monitor mode failed on {iface}: {err}"
                return
            self._begin_capture(iface)

    def _begin_capture(self, iface):
        """Starts sniffing on an interface that's already in monitor mode.
        Returns True on success; sets self.status either way."""
        sniffer = AsyncSniffer(iface=iface, prn=self._handle, store=False)
        sniffer.start()
        time.sleep(1.0)  # give it a moment to open the socket (or fail)
        exc = getattr(sniffer, "exception", None)
        if exc is not None or not getattr(sniffer, "running", True):
            self.status = f"capture failed on {iface}: {exc or 'sniffer did not start'}"
            return False
        self._sniffer = sniffer
        self.status = f"capturing on {iface} - waiting for beacons..."
        return True

    def _stop_capture(self):
        sniffer, self._sniffer = self._sniffer, None
        if sniffer is not None:
            try:
                if getattr(sniffer, "running", False):
                    sniffer.stop()
            except Exception:
                pass

    def switch_interface(self, new_iface):
        """Moves scanning to a different antenna. Blocking (several seconds) -
        run it from a BackgroundTask. Returns (ok, error_message). On
        failure the old antenna keeps scanning."""
        with self._ctl_lock:
            old = self.iface
            if new_iface == old and self._sniffer is not None:
                return True, ""
            self._hop_paused = True
            try:
                self._stop_capture()
                self._locked_channel = None
                ok, err = system.enable_monitor(new_iface)
                if not ok:
                    # old antenna is still in monitor mode - just resume it
                    self._begin_capture(old)
                    return False, err
                if old != new_iface:
                    system.restore_managed(old)
                with self.lock:
                    self.networks.clear()
                    self.history.clear()
                self.iface = new_iface
                if not self._begin_capture(new_iface):
                    return False, self.status
                return True, ""
            finally:
                self._hop_paused = False

    def stop(self):
        self._stop = True
        self._stop_capture()

    def snapshot(self):
        """Returns a list of network dicts with a computed 'alive' flag."""
        now = time.time()
        with self.lock:
            out = []
            for entry in self.networks.values():
                e = dict(entry)
                e["alive"] = (now - e["last_seen"]) < config.GONE_AFTER_SEC
                out.append(e)
        inherit_vendors(out)   # nameless twins borrow their router's manufacturer
        # strongest / most recently seen first
        out.sort(key=lambda e: (not e["alive"], -(e["rssi"] or -999)))
        return out


if __name__ == "__main__":
    # quick manual test: run as root with the interface already in monitor mode
    t = Tracker(config.IFACE, config.MANUF_FILE)
    t.start()
    try:
        while True:
            time.sleep(2)
            os.system("clear")
            for n in t.snapshot()[:15]:
                name = n["ssid"] or "(hidden)"
                print(f"{name:24.24} {n['bssid']} {n['vendor']:20.20} "
                      f"{n['band']:5} ch{n['channel']} {n['rssi']}dBm "
                      f"{'live' if n['alive'] else 'gone'}")
    except KeyboardInterrupt:
        t.stop()
