# WiFi Hunter — Pi 3B + Alfa AWUS036ACH + Adafruit 2.8" Resistive PiTFT

No GPS yet — this build tracks SSIDs/BSSIDs/vendors and shows a live list +
detail screen on the touchscreen. Direction-finding compass math from the
earlier prototype can be added as a second screen once this base is working.

## 1. Flash the OS

Use **Raspberry Pi OS Lite (32-bit / Bullseye or Bookworm)** — Lite because
you don't need a desktop, you're driving the framebuffer directly. Enable
SSH during imaging (Raspberry Pi Imager's gear icon) so you can work headless.

## 2. Enable SPI

```
sudo raspi-config
# Interface Options -> SPI -> Enable -> reboot
```

## 3. Install the Adafruit PiTFT resistive driver

```
sudo apt update && sudo apt install -y git python3-pip
cd ~
git clone https://github.com/adafruit/Raspberry-Pi-Installer-Scripts.git
cd Raspberry-Pi-Installer-Scripts
sudo python3 adafruit-pitft.py --display=28r --rotation=90 --install-type=fbcp
```
(`28r` = 2.8" resistive. Adafruit's script asks a couple of interactive
questions — choose "console" = no if you don't want a text console on the
screen, since our app will own the display directly.) Reboot when it finishes.

This gives you `/dev/fb1` (the TFT) and a touch input device.

## 4. Test the onboard buttons (no touch/tslib needed)

Navigation uses the PiTFT's 4 built-in tactile buttons instead of touch —
they're wired to GPIO 17/22/23/27, no driver or calibration required, just
read directly via `gpiozero`:

```
python3 buttons.py
```
Press each button and confirm the right label (UP/DOWN/SELECT/BACK) prints.
If a button prints the wrong label, or does nothing, physically check which
button is on which GPIO for your specific board and adjust the `PIN_*`
constants at the top of `buttons.py` to match.

## 5. Alfa AWUS036ACH driver

Check which chipset your unit actually shipped with:
```
lsusb
```
- If it shows a **Realtek** ID (0bda:...): you need the `rtl8812au` driver
  (aircrack-ng's community fork has the most current one):
  ```
  sudo apt install -y dkms build-essential
  git clone https://github.com/aircrack-ng/rtl8812au.git
  cd rtl8812au && sudo make dkms-install
  ```
- If it shows a **MediaTek** ID (0e8d:...): you're likely already covered —
  `mt76` is in mainline kernel since ~5.x, no extra driver needed.

Then bring up monitor mode (adjust `wlan1` to whatever `iw dev` shows for
the Alfa adapter — the Pi's onboard wifi is usually `wlan0`):
```
sudo ip link set wlan1 down
sudo iw dev wlan1 set type monitor
sudo ip link set wlan1 up
iw dev   # confirm it now shows "type monitor" and note the interface name
```
Update `IFACE` in `config.py` to match (e.g. `wlan1`, not `wlan1mon` unless
your setup renames it — `iw`-based monitor mode keeps the same name, only
`airmon-ng` renames to `wlan1mon`).

## 6. Project setup

Copy this whole folder to the Pi, then:
```
cd wifi-hunter
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install -r requirements.txt
```
`--system-site-packages` matters — pygame's SDL framebuffer/tslib integration
is easiest to get working using the apt-installed SDL libs rather than pip's.

## 7. Run it

The easiest way — one script sets the adapter to monitor mode and launches
the app:
```
sudo ./start.sh
```
Before first use, open `start.sh` and confirm the `IFACE="wlan1"` line
matches your Alfa adapter's actual name (check with `iw dev` while it's
still in managed mode) — and make sure it matches `IFACE` in `config.py`
too, since that's what the sniffer actually reads from.

Or run the two steps manually if you want more control:
```
sudo ip link set wlan1 down
sudo iw dev wlan1 set type monitor
sudo ip link set wlan1 up
sudo -E venv/bin/python3 main.py
```
No `SDL_FBDEV`/`SDL_VIDEODRIVER` needed — the app draws to an in-memory
surface and writes pixels directly into `/dev/fb1` itself (see
`fb_output.py`), bypassing SDL's display drivers entirely. This was
necessary because current SDL2/pygame builds don't reliably support
`fbcon` (deprecated) or `kmsdrm` (wrong driver type for a plain SPI
framebuffer like this one) on this hardware.

`sudo` is still required for monitor-mode packet capture, channel
hopping, and GPIO button access.

### Quick isolated tests, if something looks wrong later
```
sudo -E venv/bin/python3 fb_output.py    # cycles red/green/blue on the screen
python3 buttons.py                        # press each button, confirm labels
```

## What's included

- `sniffer.py` — Scapy-based beacon/probe-response capture, hops across a
  channel list covering both 2.4G and 5G, tracks last-seen time per BSSID
- `oui.py` — offline MAC vendor lookup using a bundled Wireshark-format
  `manuf.raw` (snapshot included; refresh anytime from Wireshark's repo for
  newer vendor allocations)
- `buttons.py` — reads the PiTFT's 4 onboard tactile buttons via GPIO
- `fb_output.py` — packs pygame surface pixels into 16-bit RGB565 and
  writes them directly into `/dev/fb1`, bypassing SDL's display drivers
- `ui.py` / `main.py` — three screens navigated with UP/DOWN/SELECT/BACK:
  - **List**: cursor + UP/DOWN scroll, SELECT opens a network's detail
  - **Detail**: SSID/BSSID/vendor/band/RSSI, SELECT starts tracking,
    BACK returns to the list
  - **Tracking**: locks the channel hopper onto that one BSSID's channel
    (so you get frequent, uninterrupted readings instead of a hop-diluted
    one), shows a big live RSSI number, a peak-hold marker, a bar meter,
    and a recent-history trend graph. BACK stops tracking (resumes normal
    hopping) and returns to detail.

### Using the tracking screen to hunt down a signal

Point your directional antenna, walk the cursor to the target SSID, SELECT
into detail, SELECT again to start tracking. Then slowly rotate/walk with
the antenna and watch the big RSSI number and the peak-hold line (yellow)
on the bar — RSSI gets less negative (closer to 0) as you point toward or
move closer to the source. This is the same "hotter/colder" method used in
classic radio direction finding, just without a magnetometer for an actual
compass bearing yet — GPS/magnetometer-based bearing estimation can be
added on top of this later using the same technique from the interactive
compass prototype earlier in this build.

## Known rough edges to expect

- `CHANNELS_5` in `config.py` covers common channels but not every regulatory
  domain's full list — expand it if you're missing APs on unusual channels
- Channel hopping means you'll see each AP's beacon only briefly per sweep —
  fine for building the list, but for the direction-finding phase later
  you'll want to **lock to one channel** (skip hopping) once you've picked
  a target BSSID, so RSSI readings aren't interrupted by the hop
- RSSI on some Realtek monitor-mode drivers is less reliable than on `mt76`
  chips — validate against `airodump-ng` on the same adapter if numbers look off
