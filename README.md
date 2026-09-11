# WiFi Hunter — Pi 3B+ + Alfa AWUS036ACH + Hosyond 7" DSI Touchscreen

Launches into a phone-style home screen with app icons. Currently:
**WiFi Scanner** (tracks SSIDs/BSSIDs/vendors, live list + detail +
direction-finding tracking screen), **Radar** (manual-sweep polar RSSI
plot - no magnetometer needed, see below), and **Settings** (shutdown/
reboot for now, more settings later). More apps get added the same way.

This build replaced an earlier Adafruit 2.8" resistive PiTFT (broken touch
controller, SPI framebuffer, 4 physical buttons) with a 7" DSI capacitive
touchscreen. The DSI panel is a real DRM/KMS display, so the app draws
through a normal SDL window instead of writing raw pixels into a
framebuffer device, and navigation is touch-only.

## 1. Flash the OS

**Raspberry Pi OS Lite (32-bit, Bookworm)**. Enable SSH during imaging
(Raspberry Pi Imager's gear icon) so you can work headless.

## 2. Enable the DSI display

The Hosyond panel is DSI/driver-free — Raspberry Pi OS's mainline `vc4-kms-v3d`
driver handles it directly, no vendor install script needed. In
`/boot/firmware/config.txt`, make sure:
```
dtoverlay=vc4-kms-v3d
```
is **enabled** (uncommented). (The old PiTFT setup needed this commented
*out* to avoid conflicting with the SPI framebuffer console — that
conflict doesn't apply here since there's no SPI framebuffer anymore.)
Reboot after changing it.

If the picture comes up sideways or upside-down (the app draws portrait
and rotates it onto the panel's native landscape resolution in software —
see `display.py`), change `SCREEN_ROTATE` in `config.py` between `90` and
`270` (they're 180 degrees apart, so that's the whole adjustment range).
Touch coordinates follow automatically since `display.py` derives the
inverse mapping from that same value.

## 3. Alfa AWUS036ACH driver

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

## 4. Project setup

Copy this whole folder to the Pi, then:
```
cd wifi-hunter
python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install -r requirements.txt
```
`--system-site-packages` matters — pygame's SDL integration is easiest to
get working using the apt-installed SDL libs rather than pip's.

## 5. Hide specific SSIDs (optional)

Copy `.env.example` to `.env` and list SSIDs you don't want shown:
```
cp .env.example .env
```
Edit `.env`:
```
HIDDEN_SSIDS=MyHomeNetwork,MyOtherNetwork
```
`.env` is gitignored so it stays local. In the WiFi Scanner app, tap the
small icon in the top-right of the list screen's header to toggle hide
mode on/off.

## 6. Run it

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

`sudo` is required for monitor-mode packet capture and channel hopping.

### Quick isolated test, if the screen looks wrong later
```
sudo -E venv/bin/python3 test_display.py    # cycles red/green/blue + text
```

## What's included

- `main.py` — entry point; owns which "app" is currently showing (`home`,
  `wifi`, `settings`, ...) and routes touch/draw calls to it. Every app is
  created once at startup and stays alive in the background (so e.g. the
  WiFi scanner's scroll position survives a trip back to the launcher);
  the sniffer keeps capturing regardless of which app is on screen
- `launcher.py` — the home screen: a grid of app icons, tap one to launch
  it. Add an entry to `launcher.py`'s `APPS` list (and wire it up in
  `main.py`) to add a new app
- `theme.py` — shared colors and touch-target sizing used by every app,
  so they look consistent
- `ui.py` — the **WiFi Scanner** app, three screens navigated entirely by
  touch:
  - **List**: tap a row to open its detail screen, swipe up/down to
    scroll, tap the icon top-left to return to the launcher, tap the
    icon top-right to toggle SSID hide mode
  - **Detail**: SSID/BSSID/vendor/band/RSSI; tap **TRACK** to start
    tracking, **BACK** to return to the list
  - **Tracking**: locks the channel hopper onto that one BSSID's channel
    (so you get frequent, uninterrupted readings instead of a hop-diluted
    one), shows a big live RSSI number, a peak-hold marker, a bar meter,
    and a recent-history trend graph. Tap **STOP** to resume normal
    hopping and return to detail.
- `radar_app.py` — the **Radar** app. Pick a target network, then
  physically rotate your directional antenna while dragging a finger
  around the on-screen dial to match your heading - the app samples live
  RSSI at the current angle and plots a blip (closer to center = stronger
  signal). Sweep a full circle and the blip closest to center marks your
  best bearing. There's no magnetometer/gyro on this build, so the angle
  is relative to wherever you started the drag, not true north - you're
  the sensor, syncing the needle to your own rotation. Tap **BACK** to
  stop and pick a different target, **RESET** to clear the sweep and
  start over on the same one
- `settings_app.py` — the **Settings** app. Currently: **Shut Down** and
  **Reboot**, each behind a confirm screen (a touchscreen mis-tap
  shouldn't be able to power the device off). More settings (hidden
  SSIDs, refresh intervals, etc.) get added here later
- `widgets.py` — small drawing helpers (currently just the bottom
  button-bar widget) shared by the WiFi Scanner, Radar, and Settings apps
- `sniffer.py` — Scapy-based beacon/probe-response capture, hops across a
  channel list covering both 2.4G and 5G, tracks last-seen time per BSSID
- `oui.py` — offline MAC vendor lookup using a bundled Wireshark-format
  `manuf.raw` (snapshot included; refresh anytime from Wireshark's repo for
  newer vendor allocations)
- `display.py` — opens the DSI panel as a normal SDL window and rotates
  the app's portrait UI onto its native landscape resolution each frame,
  converting touch coordinates back the other way

### Using the tracking screen to hunt down a signal

Point your directional antenna, tap the target SSID to open its detail
screen, tap TRACK. Then slowly rotate/walk with the antenna and watch the
big RSSI number and the peak-hold line (yellow) on the bar — RSSI gets
less negative (closer to 0) as you point toward or move closer to the
source. This is the same "hotter/colder" method used in classic radio
direction finding, just without a magnetometer for an actual compass
bearing yet — GPS/magnetometer-based bearing estimation can be added on
top of this later using the same technique from the interactive compass
prototype earlier in this build.

## Known rough edges to expect

- `CHANNELS_5` in `config.py` covers common channels but not every regulatory
  domain's full list — expand it if you're missing APs on unusual channels
- Channel hopping means you'll see each AP's beacon only briefly per sweep —
  fine for building the list, but for the direction-finding phase later
  you'll want to **lock to one channel** (skip hopping) once you've picked
  a target BSSID, so RSSI readings aren't interrupted by the hop
- RSSI on some Realtek monitor-mode drivers is less reliable than on `mt76`
  chips — validate against `airodump-ng` on the same adapter if numbers look off
- `main.py` handles both `MOUSEBUTTONDOWN/UP` and `FINGERDOWN/UP` events
  (now also `MOUSEMOTION`/`FINGERMOTION` for the Radar app's drag) since
  it's untested which ones SDL emits for this panel's touch driver — if
  taps or the radar needle don't register, check which event type
  actually fires (add a quick `print(event)` in the loop) and let me know
- The Alfa adapter can only sit on one channel at a time. WiFi Scanner's
  Tracking screen and Radar's sweep both lock the channel while active -
  if you start one while the other is also active, whichever locks/
  unlocks last wins. Not a bug, just don't run both trackers at once
