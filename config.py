# --- config.py ---
IFACE = "wlan1mon"          # your Alfa adapter in monitor mode (check with `iw dev`)
MANUF_FILE = "manuf.raw"    # OUI vendor database shipped alongside this project
GONE_AFTER_SEC = 180        # mark an AP "gone" if not seen in this many seconds
CHANNELS_24 = [1, 6, 11]              # quick-hop set for 2.4GHz (expand as needed)
CHANNELS_5 = [36, 40, 44, 48, 149, 153, 157, 161]  # common 5GHz channels (region-dependent)
HOP_INTERVAL_SEC = 0.5      # how long to sit on each channel while scanning
SCREEN_SIZE = (240, 320)    # PiTFT 2.8" resolution, portrait (buttons at bottom)
FRAMEBUFFER = "/dev/fb1"    # the PiTFT's framebuffer device after driver install
