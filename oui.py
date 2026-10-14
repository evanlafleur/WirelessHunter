# --- oui.py ---
# MAC address -> manufacturer, from a Wireshark-format "manuf" file
# (manuf.raw, regenerated from the IEEE registry; refresh it any time from
# https://www.wireshark.org/download/automated/data/manuf). Lines are
#   prefix <tab> short name <tab> full name
# where the prefix is a plain 3-byte OUI ("24:F5:A2") or a sub-range of one
# ("00:1B:C5:00:10/36" - the IEEE hands out 28- and 36-bit blocks too).

import re
import threading

_LOCALLY_ADMINISTERED = 0x02 << 40   # bit 1 of the first byte, in a 48-bit address

# Trailing legal-entity words are noise on a 480px screen ("Belkin
# International Inc." -> "Belkin International").
_LEGAL_SUFFIX = re.compile(
    r"[,\s]+(inc|incorporated|llc|l\.l\.c|ltd|limited|co|corp|corporation|company|gmbh|s\.a|sa|"
    r"s\.p\.a|spa|b\.v|bv|n\.v|nv|ag|plc|oy|ab|a/s|pte|sdn|bhd|kg|s\.r\.l|srl)\.?$", re.I)

def tidy_name(name):
    name = name.strip()
    for _ in range(4):
        shorter = _LEGAL_SUFFIX.sub("", name).rstrip(" ,.")
        if shorter == name or not shorter:
            break
        name = shorter
    return name


class OuiLookup:
    def __init__(self, path, background=False):
        self._tables = {24: {}, 28: {}, 36: {}}   # bits -> {prefix value: name}
        self._cache = {}
        self.ready = threading.Event()
        if background:
            threading.Thread(target=self._load, args=(path,), daemon=True).start()
        else:
            self._load(path)

    @property
    def size(self):
        return sum(len(t) for t in self._tables.values())

    def _load(self, path):
        with open(path, "r", errors="ignore") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 2:
                    continue
                prefix = parts[0].strip()
                name = (parts[2] if len(parts) > 2 and parts[2].strip() else parts[1]).strip()
                bits = 24
                if "/" in prefix:
                    prefix, mask = prefix.split("/", 1)
                    if not mask.isdigit():
                        continue
                    bits = int(mask)
                if bits not in self._tables:
                    continue
                try:
                    octets = [int(o, 16) for o in prefix.split(":")]
                except ValueError:
                    continue
                if not 3 <= len(octets) <= 6:
                    continue
                value = 0
                for o in octets + [0] * (6 - len(octets)):
                    value = (value << 8) | o
                self._tables[bits][value >> (48 - bits)] = name
        self.ready.set()

    def _find(self, value):
        for bits in (36, 28, 24):   # most specific block first
            name = self._tables[bits].get(value >> (48 - bits))
            if name:
                return name
        return None

    def lookup(self, mac):
        """'24:F5:A2:AD:72:7F' -> 'Belkin International'; '' if unknown (or
        the database is still loading)."""
        if not self.ready.is_set() or not mac:
            return ""
        cached = self._cache.get(mac)
        if cached is not None:
            return cached
        try:
            value = int(mac.replace(":", ""), 16)
        except ValueError:
            return ""
        name = self._find(value)
        if name is None and value & _LOCALLY_ADMINISTERED:
            # Randomised / virtual-AP address: the real vendor's address
            # often differs only in this bit.
            name = self._find(value & ~_LOCALLY_ADMINISTERED)
        result = tidy_name(name) if name else ""
        self._cache[mac] = result
        return result


if __name__ == "__main__":
    # quick self-test
    import config
    db = OuiLookup(config.MANUF_FILE)
    print(f"Loaded {db.size} vendor prefixes")
    print("24:F5:A2:AD:72:7F ->", db.lookup("24:F5:A2:AD:72:7F"))
