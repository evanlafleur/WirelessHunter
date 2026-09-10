# --- oui.py ---
# Parses the Wireshark-format manuf file into a MAC-prefix -> vendor lookup.
# File format lines look like:  "AC:DE:48\tAppleInc\tApple, Inc."  (tabs, some comments with '#')

import re

class OuiLookup:
    def __init__(self, path):
        self.table = {}
        self._load(path)

    def _load(self, path):
        with open(path, "r", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) < 2:
                    continue
                prefix_raw = parts[0].strip()
                vendor = parts[-1].strip()
                # Most entries are a plain 3-octet prefix like AC:DE:48.
                # Some are longer masks (AC:DE:48:00:00:00/28) - just take the base prefix.
                prefix_raw = prefix_raw.split("/")[0]
                prefix = re.sub(r"[^0-9A-Fa-f:]", "", prefix_raw).upper()
                octets = prefix.split(":")
                if len(octets) < 3:
                    continue
                key = ":".join(octets[:3])
                self.table[key] = vendor

    def lookup(self, mac):
        """mac like 'A4:83:E7:2C:19:0B' -> vendor string or 'Unknown'"""
        if not mac:
            return "Unknown"
        key = ":".join(mac.upper().split(":")[:3])
        return self.table.get(key, "Unknown")


if __name__ == "__main__":
    # quick self-test
    import config
    db = OuiLookup(config.MANUF_FILE)
    print(f"Loaded {len(db.table)} vendor prefixes")
    print("A4:83:E7:2C:19:0B ->", db.lookup("A4:83:E7:2C:19:0B"))
