# REPLAYD v0.6 — Timecode & Shorter Pre-Surge Cuts

This update responds to real football creator testing. **It is an upgrade, not a redesign.** Features, How It Works, Analytics, Campaigns, Library, Studio styling, the SQLite database and rendered video functionality are preserved.

## Changed

- **Clip editor:** all automatically populated Start and End fields use readable `MM:SS` timecodes such as `01:30` (90 seconds), `03:50.50` (230.5 seconds), or `04:15.25` (255.25 seconds). Old raw-second input is accepted and normalized on blur, but the app no longer pre-fills raw seconds. FFmpeg still receives correct numeric seconds.
- **Browser cache:** frontend assets have a v0.6 cache-busting version and explicit `no-store` response headers, preventing Safari from silently reusing old JavaScript between version folders.
- **Candidate count:** 5, 10 (default), 20 or 30; previous 12/24/40 choices removed. The API also caps requests at 30.
- **Clip timing:** suggested clips begin approximately **5 seconds before** candidate peaks in edited compilations (**6 seconds** for continuous match recordings), and retain about **18 seconds after** the peak. A nearby shot transition may snap the beginning within 4–6 seconds before the peak, or the end within the final few seconds around the target. An early cut after a goal no longer prematurely truncates the reaction.
- **No change to trained recognition:** audio and visual change heuristics still only propose moments for review, not confirmed football goals.

## Run on macOS (without upgrading pip)

1. Stop the old server with Control+C.
2. Keep v0.5 and earlier folders for your existing local data. Back up any old `.local_data` folders first.
3. Extract this ZIP into `~/Downloads/REPLAYD_v0_6` alongside your earlier folders.
4. In Terminal:

```bash
cd ~/Downloads/REPLAYD_v0_6
source ../REPLAYD_v0_2/.venv/bin/activate
python run.py
```

If the v0.2 environment is not present, activate any working REPLAYD virtual environment, or create one in this folder and install `requirements.txt`. Open http://127.0.0.1:8000. You do **not** need to update pip just for this release.

## Verify the specific feedback

1. Open your existing 10-minute recording from My Library. Re-run Analyze Moments; previously saved suggestions retain their earlier bounds until you analyze again.
2. Select **Edited highlights**, sensitivity **0.20**, and 10 suggestions initially; compare 20 if important moments are missing.
3. Select a candidate near `03:57`: without overriding scene cuts, typical suggested bounds are `03:52` to `04:15`, not raw seconds.
4. For `90` seconds, the editor displays `01:30` after leaving the field. For fractional inputs, `230.5` becomes `03:50.50`.
5. Preview and export one clip. FFmpeg still trims accurately; check that the goal build-up and reaction remain in the clip.

## Quality checks

```bash
python -m pytest -q
```

Automated regressions cover timecode HTML and asset-cache controls, five-second pre-roll, eighteen-second post-roll, prevention of early post-peak cuts, and previous API/campaign/export functionality. JavaScript was also tested in headless Chromium with mock API responses. Real goal recall still needs evaluation against your own annotated footage; this patch intentionally does not claim perfect goal detection.
