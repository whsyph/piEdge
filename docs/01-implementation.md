# Implementation / technical analysis

## Boundary and rationale

Measured direct DRM/drmprime-overlay presentation outperformed the preserved
GPU/Wayland path on this Pi4. The user visually confirmed smooth playback and
explicitly authorized permanent integration. The implementation extends the
captured Pi4 control/schedule/audio code rather than replacing it with Pi5 code.

## Seven live targets

1. `/opt/pi5-signage/signage.py`: direct hardware-plane mpv argv, existing CMS
   playlist/schedule/boot-scoped operation-mode bridge, audio preferences and IPC.
2. `/opt/pi5-signage/drm_power.py`: standard-library ctypes wrapper for the stable
   libdrm connector-property ABI; no dependency/package installation.
3. `/opt/pi5-signage/drm_splash.py`: finite direct-DRM software-image splash.
4. `/opt/pi5-signage/splash.sh`: LF-only, non-fatal launcher.
5. `/etc/systemd/system/pi5-signage.service`: compositor-free VT8 ownership.
6. `/etc/pi5-signage.json`: existing settings retained plus renderer=drm-overlay,
   drm_device=/dev/dri/card1, drm_mode=1920x1080@60 and splash_seconds=3.
7. `/home/pi/museum_signage/server.py`: native-profile-only safe preview notice.

## Render ownership

mpv runs as pi, with GPU context DRM, hwdec DRM and drmprime-overlay interop.
The primary plane presents decoded P030/NV12 video; the overlay plane handles
OSD/drawing at 1920x1080. This avoids sampling tiled video through labwc's GPU
compositing path. No compositor is running on the same connector.

The systemd service retains its historical name for API/sudo compatibility.
It conflicts with labwc, legacy players and getty@tty8, owns tty8, and has a
literal privileged chvt pre-step. The player/splash themselves run as pi with
video/render/audio groups. PAM creates the user runtime directory/TTY session.
The mpv child retains the service's session/controlling VT rather than detaching
into a new session. No new general sudo grant was added.

## Native sleep / wake

A one-shot DPMS Off write is insufficient: final DRM-client close can restore
the console and turn the output back on. A live hardware probe demonstrated that
failure mode. The supervisor now retains a PowerLease/DRM-master FD throughout
sleep. Independent status queries repeatedly confirmed DPMS=3 while held.
On wake it sets DPMS On and releases the lease before mpv opens the device.
On stop/restart it closes the lease safely. There is no wlr-randr dependency.

## Splash

The splash uses the direct drawing plane with hardware decode/interop disabled
for the PPM image; playback is finite and any image/init failure is non-fatal.
An initial Windows CRLF shebang caused 203/EXEC; it was repaired atomically with
hash guards and a regression test. Final logs confirmed actual `DRM splash
finished; exit=0`, not just a wrapper hiding a failed child. AUTO sleep skips it.

## Audio, playlist and operation controls

The same private socket `/run/user/1000/capibarra-mpv.sock` keeps existing CMS
mute/device/channel/readback controls working. Global and per-clip audio settings
are reconstructed at each file launch. Existing AUTO/ON/OFF records remain
boot-scoped. The supervisor loops the assigned CMS playlist and rejects media
that ffprobe does not identify as HEVC, avoiding silent 4K H.264 software fallback.
Main10 was directly tested; file transitions create a new renderer and are not
claimed to be gapless.

## Preview trade-off

After reboot the final probe initially showed 130 drops. The mpv log correlated
an audio underrun with CMS screenshot capture. Native-profile screenshot handling
now returns an explicit SVG explanation with X-Preview-Available=false and never
issues a screenshot-to-file command. Repeated requests no longer interrupt the
measured presentation. No stale frame is presented as live. Non-native profiles
retain the old preview code, so the prior Wayland profile remains compatible.

The CMS source was updated as its existing owner pi and restarted by terminating
only its verified MainPID after checking Restart=always. A new PID and the HTTP
response were read back. There was no root credential or sudoers workaround.

## User data / isolation

Playlist, schedules and audio-config byte hashes were identical before/after.
Operation mode changed only for tests/reboot association and was left ON as the
operator had it. Pi5, LAN/Wi-Fi, media files and unrelated local Git work were not
changed. Source snapshot publication/merging is a separate future user decision.
