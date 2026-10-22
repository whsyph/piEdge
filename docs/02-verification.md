# Executed verification

## Automated / build

- 14 unit/contract tests passed locally and on Pi4. Tests include direct argv,
  audio/filter/device construction, retained lease lifecycle, error cleanup,
  operation overrides, HEVC acceptance/H.264 rejection, connector validation,
  compositor-free unit contract, finite splash, LF shebang and preview no-capture.
- Python source compile checks passed. Expected simulated DRM failures are logged
  by the failure-path unit test; those test traces are not live device failures.
- systemd-analyze verify passed for the candidate service.
- All seven final live source/config/unit SHA256 values matched manifest.json.

## Native power / modes / controls

- One-shot DPMS probe exposed automatic On restoration after last-close.
- Revised retained-lease probe: independent clients read DPMS=3 repeatedly during
  sleep; DPMS=0 after wake/release.
- Actual HTTP ON/OFF/AUTO: ON started one direct renderer, OFF stopped it and
  retained DPMS Off, AUTO outside schedule stayed asleep.
- Actual CMS HTTP restart returned success and launched a new direct renderer.
- Restart while AUTO/outside hours stayed asleep, with no compositor revival.
- Mute/unmute readback matched actual mpv and persisted CMS state. Mute survived
  an OFF->ON renderer restart; original global audio settings were restored.
- EOF seek exercised the supervisor's next playlist cycle, with a new renderer
  and the assigned file retained. No playlist JSON was modified for this test.
- Browser: real mute/unmute clicks returned applied=true and labels changed;
  real OFF/ON selection writes succeeded, native DPMS Off was read back, and the
  restart click showed success with backend restart independently confirmed.
  The browser harness's five-second response timeout occurred on the restart
  wait, not a failed service restart; later UI toast/state readback confirmed it.

## Reboot

Real reboot performed at 2026-10-23 02:40 WIB.
Old boot ID: 2153598b-555c-499c-8149-41ea0b6784d7.
New boot ID: 9cb330ab-9db9-40f8-82b0-0e413894a326.
Authenticated SSH returned at 02:40:39, with CMS/player active, labwc inactive,
AUTO reset and DPMS Off. No failed units. ON was then restored for testing.
The later CMS preview guard was separately restarted/HTTP-tested after reboot;
a second full reboot after that small CMS-only change was not performed.

## Performance / screenshot regression

- Initial installed profile: 30.173 seconds wall / 30.180 seconds video, zero
  additional drops, A/V near zero.
- First post-reboot run, before preview fix: 130 additional drops; mpv log showed
  audio underrun at 02:42:23 and screenshot at 02:42:24, matching a CMS request.
- Final run after preview fix, same process/file throughout:
  - Wall interval: 61.009635003 seconds.
  - Video progress: 61.044317 seconds.
  - Drops: 7 -> 7, **zero additional**; seven startup drops predated the interval.
  - Decoder drops: 0 throughout.
  - Maximum sampled absolute A/V offset: 0.000333 seconds.
  - Seven screenshot HTTP requests returned the explicit no-capture SVG notice.
  - DRM decode active, audio unmuted.
- Final status at 02:52:49: player/CMS active and enabled; labwc disabled/inactive;
  legacy players inactive; no failed units or pending recovery timers;
  HDMI DPMS On; operation ON; temperature 43.8 C; throttled=0x0.

## Preserved data hashes

- playlists.json: 39c1a787b6d5cc23940bc5fa0a300e5ad538c49e23b78b2180ca9b25e6746861
- schedules.json: 8291b5af2b840bf36cfc82f822ad452338e4a490f9fc8d70370e53ace75722fc
- audio_config.json: f1a02ed7b14b093fe9687272e8dbdcb7ddebbd896eb1705a7bb1889e41b2427f

These exactly match the pre-cutover readings. Raw JSON evidence is kept in the separate deployment handoff directory; it is
summarized here rather than committed with operator/runtime records.

## Remaining limits

User visually confirmed the preceding direct-DRM experiment. Final permanent
profile has the above measurements; long visual/burn-in confirmation is still
useful. No 2160p60 HDMI output, real 07:30/21:30 boundary, overnight runtime,
analog audio, alternative monitor, HDR/color accuracy or gapless transition claim.
Live HDMI capture is intentionally unavailable; a non-blocking preview design is
future work, not a hidden completed capability.
