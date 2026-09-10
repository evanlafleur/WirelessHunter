#!/bin/bash
# --- start.sh ---
# Puts the Alfa adapter into monitor mode, then launches main.py.
# Run with: sudo ./start.sh
#
# IFACE below must match the physical interface name of your Alfa adapter
# (check with `iw dev` while it's still in managed mode) AND must match
# the IFACE value in config.py, since that's what the sniffer/main.py
# actually reads from.

set -e

IFACE="wlan1"   # <-- change this if your Alfa adapter shows a different name

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Setting $IFACE to monitor mode..."
ip link set "$IFACE" down
iw dev "$IFACE" set type monitor
ip link set "$IFACE" up

echo "Confirming monitor mode:"
iw dev "$IFACE" info | grep -E "Interface|type"

echo "Starting WiFi Hunter..."
exec "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/main.py"
