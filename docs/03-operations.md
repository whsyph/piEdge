# Operations / deployment / rollback

## Live locations

Host pi-1, Wi-Fi 192.168.88.52, Tailscale last verified 100.67.29.36.
CMS remains port 8080 under /home/pi/museum_signage, service cms-signage.service.
Player remains /opt/pi5-signage, service pi5-signage.service, config
/etc/pi5-signage.json. Despite its historical name, this unit now describes Pi4
native DRM. Inspect actual source/profile before using Pi5 deployment tooling.

The runtime player is unprivileged pi on VT8. labwc is disabled and conflicts
with the direct player. Do not start it or old layar* players concurrently.
Remote graphical-desktop tools that require a compositor are not qualified;
SSH, Tailscale management and CMS HTTP remain available.

## Operator controls

Use the existing Control Screen mode and audio controls.
AUTO follows the unchanged daily 07:30–21:30 schedule; ON/OFF override until
cleared or a different boot ID. At final handoff ON is active for ongoing tests.
Return AUTO when finished. Sleep leaves SSH/CMS running and retains native DPMS
Off through the supervisor; it does not power off Pi.

Start/stop/restart API still targets the same service under the existing exact
NOPASSWD whitelist. No new sudo permissions were installed. Stop/restart changes
only the player, not the Pi. Live screenshot preview is explicitly unavailable
on this native profile; the endpoint returns a labeled SVG explanatory notice.

Only HEVC content is accepted by this hardware-plane profile. H.264 source files
are preserved in the library but skipped with an error instead of pretending to
provide smooth software-decoded 4K60. Main10 UHD/AAC was the tested content.

## Rollback

Original native-file/unit/config backup:
/home/pi/pi4-direct-drm-backups/20261023-023229

Original CMS source for the later preview guard:
/home/pi/pi4-direct-drm-stage/cms-preview-backup/server.py

Run in the operator's Pi4 SSH terminal:

```bash
sudo python3 /home/pi/pi4-direct-drm-stage/install.py --rollback /home/pi/pi4-direct-drm-backups/20261023-023229
```

The updated rollback entry point supports this initial six-file backup and the
separate guarded CMS preview backup. It stops the direct player, restores old
source/config/unit and original enable/active states, switches to the recorded
VT and starts the old Wayland stack. CMS rollback checks expected hashes and
will not overwrite later operator code edits blindly. It does not discard media,
playlists, schedules or CMS audio preferences. Keep a second SSH session open.

Native-cutover recovery timers were canceled after healthy smoke checks and no
recovery timers remained at handoff. A full post-acceptance rollback was not
executed, to avoid undoing the now-working installation. Backup/readback/guard
logic and the temporary-test restoration paths were exercised/inspected.

## Build / install artifact

This Git branch stores the final candidate payload, manifests, tests and guarded
installer. Private baseline captures and the generated direct-profile.tgz remain
in the separate deployment handoff directory, not in this commit. Original-source
guards intentionally prevent blind reinstallation over the already-patched Pi.
This is a deployment snapshot, not a universally validated clean-install release
for other boards/screens.

No boot firmware, network interface, media upload, disk layout, credentials or
sudoers change was made. The libdrm ABI was checked against its C headers; the
native power helper uses only standard Python ctypes plus the existing system
libdrm.so.2. No packages were installed.

Changing the screen or requesting actual 2160p60 HDMI needs mode discovery and a
new test before updating drm_mode. The current display advertises 1080p60, which
is the configured physical output. Avoid forcing unadvertised modes.
