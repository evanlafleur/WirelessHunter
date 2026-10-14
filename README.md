# WiFi Hunter — Pi 3B+ + Alfa AWUS036ACH + Hosyond 7" DSI Touchscreen

Launches into a phone-style home screen with app icons. Currently:
**WiFi Scanner** (tracks SSIDs/BSSIDs/vendors, live list + detail +
direction-finding tracking screen), **Radar** (manual-sweep polar RSSI
plot - no magnetometer needed, see below), and **Settings** (Wi-Fi
connection for updates, SSID whitelist editor, scan-antenna picker,
shutdown/reboot). More apps get added the same way.

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

You don't need to put the adapter into monitor mode by hand — the app
does that itself at startup (and again whenever you switch antennas).
Check what the adapter is called with `iw dev` (the Pi's onboard wifi is
usually `wlan0`, the Alfa usually `wlan1`). The app scans on `wlan1` by
default; to use a different interface, pick it on the touchscreen under
**Settings > Scan Antenna** (saved to `settings.json`, which is
gitignored). Note `iw`-based monitor mode keeps the interface name, so
it's `wlan1`, not `wlan1mon` (only `airmon-ng` renames it).

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
`.env` is gitignored so it stays local. You can also edit the list from
the touchscreen (**Settings > SSID Whitelist**: type a name, pick from
networks currently in range, or delete entries) - changes are saved back
to `.env`. In the WiFi Scanner app, flip the **Hide** switch in the top-right
of the network list to turn hide mode on/off.

Hide mode removes the whole access point, not just rows carrying the
whitelisted name: a router also broadcasts nameless "(hidden)" twins whose
MAC differs only in the first or last byte (e.g. `24:f5:a2:ad:72:7f` and
`2a:f5:a2:ad:72:7f`), so those are hidden along with the named entry (see
`hiding.py`). The one catch: a different device whose MAC happens to
differ from yours only in the last byte (e.g. one built right after yours)
gets hidden too.

## 6. Run it

```
sudo ./start.sh
```
(or `sudo -E venv/bin/python3 main.py` directly - `start.sh` just does
that from the right directory). The app puts the selected scan antenna
into monitor mode itself, and starts fine even if the adapter isn't
plugged in yet: the scanner list shows what it's waiting on, and you can
pick a different antenna in Settings.

`sudo` is required for monitor-mode packet capture and channel hopping.

### Start automatically on boot

The app already tells NetworkManager to leave the scan antenna alone
whenever it enables monitor mode. For extra safety against boot-time
races (on Bookworm NetworkManager grabs new wifi adapters as they come
up, which silently undoes monitor mode and leaves the list empty), you
can also mark `wlan1` unmanaged permanently:
```
sudo tee /etc/NetworkManager/conf.d/99-wlan1-unmanaged.conf <<'EOF'
[keyfile]
unmanaged-devices=interface-name:wlan1
EOF
sudo systemctl restart NetworkManager
```

`wifi-hunter.service` is a systemd unit that runs `start.sh` at boot
(after NetworkManager, restarting the app if it crashes). It assumes the repo lives at `/home/ncdc/WirelessHunter` — edit
the paths in the file if yours differs. Install it once:
```
chmod +x start.sh
sudo cp wifi-hunter.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wifi-hunter
```
Then check on it with `systemctl status wifi-hunter` or watch live output
with `journalctl -u wifi-hunter -f`. To stop it temporarily (e.g. to run
`start.sh` by hand while debugging): `sudo systemctl stop wifi-hunter`; to
turn autostart off: `sudo systemctl disable wifi-hunter`.

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
- `launcher.py` — the home screen, iOS springboard style: gradient
  wallpaper, a status bar (clock + capture indicator), and a grid of
  squircle app icons - tap one to launch it. Add an entry to
  `launcher.py`'s `APPS` list (and wire it up in `main.py`) to add a new app
- `theme.py` — the iOS-style design tokens: dark-mode system colors, type
  scale, layout metrics, and the font loader. Everything is drawn in the
  bundled **Inter** typeface (`fonts/`, SIL Open Font License - see
  `fonts/Inter-LICENSE.txt`), the closest open match to Apple's SF Pro, so
  the Pi looks the same regardless of installed system fonts
- `icons.py` — vector glyphs (wifi, gear, radar, antenna, chevrons, ...)
  and the gradient app icons, drawn with pygame primitives at 4x and
  smooth-scaled for anti-aliased edges, then cached - no image assets
- `ui.py` — the **WiFi Scanner** app, three screens navigated entirely by
  touch, with press highlights and momentum scrolling:
  - **Networks**: large-title list with a signal glyph, RSSI and band per
    row. Drag to scroll (it coasts when you flick), tap a row to open it,
    flip the **Hide** switch to hide whitelisted networks, **Home** goes
    back to the launcher
  - **Detail**: info card (vendor, band, channel, signal, status) and a
    **Track Signal** button
  - **Tracking**: locks the channel hopper onto that one BSSID's channel
    (so you get frequent, uninterrupted readings instead of a hop-diluted
    one), shows a big live RSSI number, a capsule gauge with a peak-hold
    tick, and a signal-trend graph. **Stop Tracking** (or **Back**)
    resumes normal hopping
- `radar_app.py` — the **Radar** app. Pick a target network, then
  physically rotate your directional antenna while dragging a finger
  around the on-screen dial to match your heading - the app samples live
  RSSI at the current angle and plots a blip (closer to center = stronger
  signal). Sweep a full circle and the blip closest to center marks your
  best bearing. There's no magnetometer/gyro on this build, so the angle
  is relative to wherever you started the drag, not true north - you're
  the sensor, syncing the needle to your own rotation. Tap **Targets** to
  stop and pick a different target, **Reset** to clear the sweep and
  start over on the same one
- `settings_app.py` — the **Settings** app: a main menu that pushes
  sub-screens onto a stack. To add a setting, write a `SettingsScreen`
  (`settings_base.py`) and add a row to the menu:
  - **Wi-Fi** (`settings_wifi.py`): scan, join, and disconnect networks on
    the Pi's onboard wifi (`NET_IFACE`, `wlan0`) via NetworkManager, for
    updates and the like. Tap a network; secured ones open the on-screen
    keyboard for the password, saved ones reconnect directly (and ask for
    a new password if the saved one fails). Unavailable while `wlan0` is
    itself the scanning antenna
  - **SSID Whitelist** (`settings_whitelist.py`): edit the list hidden in
    hide mode - type a name, pick from networks currently in range, or
    delete; saved to `.env`
  - **Scan Antenna** (`settings_antenna.py`): choose which wireless
    interface scans. Switching puts the new one in monitor mode, tells
    NetworkManager to leave it alone, hands the old one back to
    NetworkManager, restarts the capture, and rolls back to the old
    antenna if the switch fails. Saved to `settings.json`
  - **Shut Down** / **Reboot**, each behind a confirm alert (a
    touchscreen mis-tap shouldn't be able to power the device off)
- `keyboard.py` — the on-screen keyboard (letters, shift, numbers,
  symbols, show/hide for passwords) used for Wi-Fi passwords and typed
  SSIDs, since there's no physical keyboard
- `system.py` — wrappers around `nmcli` / `iw` / `ip` (all run as argv
  lists, never through a shell, so typed SSIDs/passwords can't inject
  commands) plus `BackgroundTask`, which runs slow calls off the UI thread
- `widgets.py` — the UI toolkit every app draws with: anti-aliased
  rounded shapes, touch `Gesture` tracking (tap vs drag, fling velocity),
  the momentum-scrolling `ListView`, and the iOS components built on them
  (navigation bar, toolbar, filled buttons, switch, alerts, spinner HUD).
  Tap targets come from plain geometry functions so drawing and
  hit-testing can't drift apart
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
screen, tap Track Signal. Then slowly rotate/walk with the antenna and watch the
big RSSI number and the peak-hold tick (white) on the gauge — RSSI gets
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
- The onboard `wlan0` (Broadcom) generally can't do monitor mode with the
  stock firmware, so picking it as the scan antenna will usually just
  fail - the app rolls back to the previous antenna and shows the error.
  Wi-Fi connection and scanning on separate radios (`wlan0` + the Alfa) is
  the intended setup
- Wi-Fi passwords are passed to `nmcli` as an argument, so they're briefly
  visible in the process list on the Pi while connecting. Fine for a
  single-user device; don't use this scheme on a shared machine
- SSIDs containing commas can't be whitelisted (the `.env` format is
  comma-separated)
- The Alfa adapter can only sit on one channel at a time. WiFi Scanner's
  Tracking screen and Radar's sweep both lock the channel while active -
  if you start one while the other is also active, whichever locks/
  unlocks last wins. Not a bug, just don't run both trackers at once
