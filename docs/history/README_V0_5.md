# REPLAYD v0.5 — Studio Detection & Creator Analytics

This is an upgrade of the existing local-first REPLAYD application. It preserves Studio, Features, How It Works, Library, Campaigns, and the premium dark/lime visual design. No paid or external API keys are required.

## What changed

**Studio detection (experimental)**

- Independently proposes candidate moments using audio activity **or** clusters of shot changes. Previously, video changes could only re-rank audio-selected moments.
- Shorter scene-aware suggestions replace unconditional 30-second windows. They are editable and **not guaranteed** to be the perfect football action boundaries.
- `Edited highlights / compilation` and `Long match / continuous footage` modes.
- 12 / 24 / 40 maximum suggestion choices; shorter suppression windows for edited footage.
- Sound activity includes short surges and sustained loudness relative to the local baseline. A low audio threshold does not guarantee detecting goals.
- Visual-only candidates are labeled as review suggestions, not recognized goals or probabilities.

**Clip editor**

- Start/end entry is now `MM:SS` or `MM:SS.xx`, such as `03:45.25` and `04:15.25`.
- The app converts these to exact numeric seconds before calling the existing, tested FFmpeg exporter.
- Export formats and working Campaigns/Library functionality are preserved. 1:1 format has not been added yet.

**Creator analytics**

- More football-native, plain-English headings; less jargon such as “content mix” or “day-of-week patterns”.
- Saves **per 1,000 views** is now the default comparison metric; shares remain available as a secondary metric.
- Main comparisons: football category, platform, clip length, most saved individual Reels (where views >= 1,000).
- Missing saves remain unknown, never zero; some platforms don't provide save metrics.
- Analytics still imports CSV/paste/manual data and preserves prior saved posts.

## macOS upgrade without updating pip

1. Stop the v0.4 server using **Control+C**.
2. Unzip `REPLAYD_v0.5_Detection_Upgrade.zip` alongside your existing version folders in `~/Downloads`. Keep old folders for local video/database paths.
3. Back up the old `.local_data` folder before significant changes (some older versions keep data under v0.3 or v0.2).
4. In Terminal:

```bash
cd ~/Downloads/REPLAYD_v0_5
source ../REPLAYD_v0_2/.venv/bin/activate
python run.py
```

If that v0.2 virtualenv is missing, create a new virtualenv and install `requirements.txt` with your existing pip. No pip upgrade is required.

Browse to http://127.0.0.1:8000. The app discovers an existing database in sibling v0.4, v0.3, v0.2, or v0.1 folders, if available; it does not intentionally reset those records. Keep source folders intact because old video paths are absolute.

## Test it on the same 10-minute 2–1 video

- Reopen the source in My Library and click **Analyze moments again**; old saved v0.4 suggestions aren't automatically upgraded.
- Select **Edited highlights / compilation**, threshold **0.20**, maximum suggestions **24**.
- Inspect visual-only suggestions and the shorter proposed cuts. Then test **0.15** and 40 suggestions, if needed.
- Record actual source-video timestamps for all three goals (not their in-game match clock). Compare which are near suggestions. Use the manual editor to correct any boundaries.
- For transparent evidence, run (with your own goal times):

```bash
python scripts/check_goal_coverage.py ~/Downloads/my-match.mp4 02:12 05:38 09:10
```

These are example timestamps only. The script measures whether a suggestion falls near an annotated goal; it **does not identify goals** by itself.

You can also upload `data/DEMO_scene_changes.mp4`, a synthetic 20-second video with constant audio and changing visual scenes. At high threshold, the improved detector should still show a visual-only proposal. This tests independent visual suggestions, not match accuracy.

## Limits and engineering honesty

- No training/inference of a football-event classifier yet, no scoreboard OCR, and no verified goal probabilities. Camera cuts may be ordinary edits and generate false positives.
- Precise clip boundaries and reliable goal recall on real footage are **not yet established**. Both require human labels and evaluation across multiple different videos.
- Still a local single-user application; do not deploy publicly without authentication, upload protections, and media-processing hardening.
- Existing v0.4 README is retained as `README.md` for prior platform features.

## Tests

```bash
python -m pytest -q
```

The regression suite includes silent-audio visual candidates, tighter scene-aware windows, 24-candidate recall behavior, metric missingness, and prior video export/campaign/business tests. Manual browser acceptance on the Mac remains necessary.
