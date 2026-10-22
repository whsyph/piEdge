# Pi5 single-HDMI deployment snapshot

This branch records the player source running on pi-b, paired with the CMS branch
`fix/pi5-cms-audio-stable` in the same repository. It is not a replacement for the
separate Pi4/multi-model packaging work.

## Runtime contract

- Target: Pi5, single HDMI-A-1, HEVC/H.265 4K60, mpv + labwc/Wayland.
- Player: `/opt/pi5-signage/signage.py`, service `pi5-signage.service`.
- Existing deployment runs as `pi` (UID 1000), with
  `XDG_RUNTIME_DIR=/run/user/1000`, and uses
  `/run/user/1000/capibarra-mpv.sock` for JSON IPC. This socket path is specific
  to that deployment; do not assume the standalone installer creates the same
  service/user layout.
- CMS playlists, schedules and audio settings live under
  `/home/pi/museum_signage/public/`. Media stays outside Git.
- For HDMI audio, configure `/etc/pi5-signage.json` with `"audio": true` and
  `"audio_device": "alsa/sysdefault:CARD=vc4hdmi0"`. The repository config retains
  its conservative muted default. Do not overwrite a deployed config blindly.
- CMS global mute and per-clip mute are combined; either one mutes playback.
  Player-level `audio=false` remains a safety override.
- `auto` follows schedules. Manual `on`/`off` overrides are boot-scoped and are
  read from `operation_mode.json`; there is no automatic expiry timer.

## Changes

- Correct mpv audio argument to one `--audio-device=<value>` argv element.
- Add the private runtime IPC socket shared with the paired CMS.
- Read global/per-clip mute on every renderer launch.
- Preserve the deployed boot-scoped operation modes and output-power retry/logging.
- Preserve this Pi5's working `dmabuf-wayland` renderer. Do not deploy this branch
  onto a unit requiring `gpu --gpu-context=wayland` without hardware testing.

## Verification

- `python -m unittest discover -s tests -v`: **11 tests passed**.
- `git diff --check`: passed.
- On Pi5: HEVC 3840x2160 ~60 fps initialized hardware DRM decoding and
  dmabuf-wayland output; ALSA HDMI initialized stereo 48 kHz.
- Live audio API mute/unmute, saved state and actual mpv mute properties were
  verified. Mute survived a service restart; playback time advanced 6.7 -> 8.8 s.
- Real CMS button clicks were exercised and returned `applied=true` for both
  mute and unmute. The operator confirmed audible HDMI sound.
- The operator reported stable playback overnight. At the publication check,
  Pi uptime was 10h02m, player/CMS were active and temperature was 37.3 C. This is
  not an instrumented zero-dropped-frame or full hardware compatibility claim.

## Known boundaries and deployment

H.264 content failed the current dmabuf output chain; successful full-file software
decode showed that this did not establish an upload-corruption problem. No generic
renderer fallback is included. Other boards, dual output, reboot/schedule boundary
regressions and left/right-channel persistence have not been requalified here.

This publication does not restart or redeploy the Pi. To deploy elsewhere, inspect
its service/user/runtime directory first and preserve all mutable JSON and media.
Keep the CMS and player socket contracts paired. Back up the active source and
config before replacing anything; rollback requires restoring both matching CMS
and player code, not discarding operator playlists or schedules.
