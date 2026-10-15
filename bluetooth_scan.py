# --- bluetooth_scan.py ---
# Bluetooth Low Energy scanner for the Pi's built-in Bluetooth. Uses `bleak`
# (which talks to BlueZ over D-Bus) on a private asyncio thread and keeps a
# live table of everything it hears: name, manufacturer, signal strength,
# what kind of device it looks like (see btid.py). Scanning only runs
# between start() and stop() - the Bluetooth app starts it when opened.
#
# Notes: this sees BLE advertisements (phones, wearables, trackers, most
# IoT) but not classic Bluetooth devices, which only answer inquiries while
# in pairing mode. Many phones randomise their address, so a device can
# appear under a new address every few minutes.

import asyncio
import re
import threading
import time
from collections import deque

import btid
import system

ALIVE_SEC = 30        # "live" if heard this recently
FORGET_SEC = 300      # dropped from the table after this long unheard
MAX_DEVICES = 600
HISTORY_LEN = 40

_ALIAS_RE = re.compile(r"^([0-9A-Fa-f]{2}[-:]){5}[0-9A-Fa-f]{2}$")   # BlueZ's placeholder "name"

def friendly_error(exc):
    text = str(exc) or exc.__class__.__name__
    low = text.lower()
    if "no bluetooth adapter" in low or "no adapters" in low:
        return "No Bluetooth adapter found."
    if "not ready" in low or "not powered" in low or "powered off" in low or "rfkill" in low:
        return "Bluetooth is switched off. Try: sudo rfkill unblock bluetooth"
    if "org.bluez" in low or "serviceunknown" in low or "dbus" in low:
        return "The Bluetooth service isn't running. Try: sudo systemctl start bluetooth"
    if "permission" in low or "access denied" in low:
        return "Not allowed to use Bluetooth - the app must run as root."
    return text.splitlines()[0][:120]


class BleScanner:
    def __init__(self):
        self.status = "Bluetooth is off"
        self._devices = {}
        self._mfr = {}          # address -> {company id: latest manufacturer data}
        self._history = {}
        self._lock = threading.Lock()
        self._thread = None
        self._loop = None
        self._stop_event = None

    # --- lifecycle ---
    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.running:
            return
        self.status = "Starting Bluetooth…"
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def stop(self):
        loop, event, thread = self._loop, self._stop_event, self._thread
        if loop is not None and event is not None:
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:
                pass
        if thread is not None:
            thread.join(timeout=4)
        self._thread = None
        self.status = "Bluetooth is off"

    def _thread_main(self):
        try:
            asyncio.run(self._main())
        except Exception as e:              # never let the thread die silently
            self.status = friendly_error(e)

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()
        try:
            from bleak import BleakScanner
        except ImportError:
            self.status = "The 'bleak' library isn't installed - run: pip install -r requirements.txt"
            return
        # the radio is often soft-blocked or powered down after boot
        system.run(["rfkill", "unblock", "bluetooth"], timeout=5)
        system.run(["bluetoothctl", "power", "on"], timeout=8)
        try:
            try:
                # report every advertisement, not just changes, so RSSI keeps updating while tracking
                scanner = BleakScanner(detection_callback=self._on_advertisement,
                                       bluez={"filters": {"DuplicateData": True}})
            except TypeError:
                scanner = BleakScanner(detection_callback=self._on_advertisement)
            async with scanner:
                self.status = "Scanning"
                await self._stop_event.wait()
        except Exception as e:
            self.status = friendly_error(e)

    # --- advertisements ---
    def _on_advertisement(self, device, adv):
        address = (device.address or "").upper()
        if not address:
            return
        now = time.time()
        rssi = getattr(adv, "rssi", None)
        name = adv.local_name or getattr(device, "name", None)
        if name and _ALIAS_RE.match(name):
            name = None
        details = getattr(device, "details", None)
        props = details.get("props", {}) if isinstance(details, dict) else {}
        with self._lock:
            entry = self._devices.get(address)
            if entry is None:
                if len(self._devices) >= MAX_DEVICES:
                    oldest = min(self._devices, key=lambda a: self._devices[a]["last_seen"])
                    del self._devices[oldest], self._mfr[oldest]
                    self._history.pop(oldest, None)
                entry = self._devices[address] = {"address": address, "first_seen": now, "adverts": 0, "services": []}
                self._mfr[address] = {}
            mfr = self._mfr[address]
            mfr.update(adv.manufacturer_data or {})
            services = list(dict.fromkeys(entry["services"] + [s.lower() for s in (adv.service_uuids or [])]
                                          + [s.lower() for s in (adv.service_data or {})]))
            kind, tracker = btid.classify(mfr, services, adv.service_data, name)
            company_id = next(iter(mfr), None)
            entry.update({
                "name": name or entry.get("name"),
                "rssi": rssi if rssi is not None else entry.get("rssi"),
                "rssi_max": max(entry.get("rssi_max", rssi), rssi) if rssi is not None else entry.get("rssi_max"),
                "kind": kind,
                "tracker": tracker or entry.get("tracker", False),
                "company": btid.company_name(company_id) if company_id is not None else entry.get("company", ""),
                "services": services,
                "tx_power": adv.tx_power if getattr(adv, "tx_power", None) is not None else entry.get("tx_power"),
                "address_type": props.get("AddressType") or entry.get("address_type"),
                "last_seen": now,
                "adverts": entry["adverts"] + 1,
            })
            if rssi is not None:
                self._history.setdefault(address, deque(maxlen=HISTORY_LEN)).append(rssi)

    # --- reading the table ---
    def snapshot(self):
        """Devices heard recently, strongest first, with an 'alive' flag."""
        now = time.time()
        with self._lock:
            for address in [a for a, e in self._devices.items() if now - e["last_seen"] > FORGET_SEC]:
                del self._devices[address], self._mfr[address]
                self._history.pop(address, None)
            out = []
            for entry in self._devices.values():
                e = dict(entry)
                e["alive"] = now - e["last_seen"] < ALIVE_SEC
                out.append(e)
        out.sort(key=lambda e: (not e["alive"], -(e["rssi"] if e.get("rssi") is not None else -999)))
        return out

    def get_history(self, address):
        with self._lock:
            return list(self._history.get(address, []))
