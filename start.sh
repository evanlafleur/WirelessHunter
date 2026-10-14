#!/bin/bash
# --- start.sh ---
# Launches WiFi Hunter. Run with: sudo ./start.sh
#
# Monitor mode is set up by the app itself now (see Tracker in sniffer.py)
# for whichever antenna is selected in Settings > Scan Antenna, so there's
# nothing interface-specific to configure here. The app also starts fine
# with no adapter plugged in, so you can pick one from the touchscreen.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec "$SCRIPT_DIR/venv/bin/python3" "$SCRIPT_DIR/main.py"
