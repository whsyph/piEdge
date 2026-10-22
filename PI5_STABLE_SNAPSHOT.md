# Pi5 CMS deployment snapshot

Pair this branch with `fix/pi5-player-audio-stable` in the same GitHub repository.
The CMS and standalone player have different source trees, so they are preserved
as separate reviewable branches rather than combined destructively into master.

## Scope

This snapshot copies the currently deployed `server.py`, `public/app.js`,
`public/app.css`, `public/index.html` and `public/operation-ui.js` from pi-b.
It deliberately excludes changed playlists, schedules, audio state, operation
mode, uploads/media, backup files and executable-bit-only changes on legacy
install scripts. Repository fixture/default JSON files are not a copy of the
operator's current data.

## Features captured

- Single-output Pi5 control targets `pi5-signage.service`, not the legacy player.
- Boot-scoped operation mode (`auto`, `on`, `off`) without permanent schedule edits.
- Scheduler leaves Pi5 playback/power decisions to its supervisor instead of
  restarting legacy renderers at schedule boundaries.
- Shared private IPC path `/run/user/1000/capibarra-mpv.sock` and matching request
  IDs for mpv replies, ignoring unsolicited events.
- Global mute checks the live mpv property before acknowledging an applied change;
  global/per-clip precedence is maintained. Settings are written atomically.
- Invalid boolean values, screen 2 and unsupported jack routing are rejected.
  Idle-player updates are explicitly reported as saved but not applied.
- Status polling no longer reapplies audio devices/filters on every read.
- UI audio failures are surfaced and the changed app.js URL is versioned.

## Verification

- `python -m unittest discover -s tests -v`: **7 handler tests passed**, isolated
  from server startup; these are mocked handler tests, not browser tests.
- `node --check public/app.js` and `node --check public/operation-ui.js`: passed.
- `git diff --check`: passed.
- Live API: mute/unmute applied and persisted, actual mpv properties matched,
  mute survived a service restart, invalid values received 400/409, playback
  time advanced from 6.7 to 8.8 seconds.
- Real browser clicks on the selected Pi5: mute and unmute returned
  `success=true, applied=true`, labels changed and the final state was unmuted.
- Operator confirmed audible HDMI sound and reported overnight stability.

## Deployment / limitations

This publication does not change running services or operator configuration.
Run CMS and the paired player as the existing Pi UID 1000 deployment, with the
same private runtime directory. Verify permissions before installing elsewhere.
For audio to be enabled, the player's config must use `audio=true` and a detected
backend-qualified HDMI device, such as `alsa/sysdefault:CARD=vc4hdmi0`.

The existing installer/service files and README describe older deployment paths;
do not treat checkout + installer as a verified fresh-install procedure for this
snapshot. Preserve current `/etc` config, media and CMS JSON. Back up source before
updates; rollback the paired CMS/player code together and retain mutable data.

This is a single-HDMI deployment, not a fleet-wide or dual-screen release.
Play/pause/next/prev controls remain explicitly rejected by the control handler.
Channel mode persistence, sleep/wake/reboot combinations, fresh installation,
authentication hardening and every legacy API were not requalified in this pass.
The process-detection status fallback is not proof of successful video rendering.
