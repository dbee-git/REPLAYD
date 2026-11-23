# Practical football highlight evaluation protocol

**Goal:** establish whether REPLAYD helps a creator find useful moments and whether independent visual candidates improve over audio-only proposals.

This is an evaluation of a **heuristic candidate detector**, not a trained model's semantic goal/card classification.

## Test material

Use four authorized videos with diverse commentary, editing speed and audio levels. For example: one calibration compilation (A), plus **three previously unseen** test videos (B–D), each about 5–10 minutes. Never publish third-party broadcast footage without permission.

Use **A for settings calibration only**. Freeze `compilation` mode, threshold `0.20`, max candidates `10`, and localization tolerance `±5 seconds` (or explicitly document chosen settings) **before running B–D**. If you tune the detector using B–D, you need new hold-out recordings.

## Labeling

Annotate **every** genuinely useful highlight (e.g., goal, major chance, exceptional save, dismissal) relative to the time inside the uploaded *source video*, not its scoreboard match clock.

- Use event time at the critical action, not the commentator's later reaction.
- Label meaningful actions consistently in all four videos, including quiet moments. Otherwise precision becomes misleading.
- Use one CSV row per event; the `event_type` is descriptive metadata, not a prediction from the algorithm.
- Keep at least a short description explaining ambiguous labels.
- Keep exact audio and video files private or licensed; don't commit them to GitHub.

Copy `evaluation/annotations_template.csv` to your private location and complete it:

```csv
video_id,video_file,event_time,event_type,notes
match_B,match_B.mp4,01:30,goal,first goal in this source clip
match_B,match_B.mp4,04:12.5,save,difficult goalkeeper save
match_C,match_C.mp4,02:20,chance,shot off the post
```

The three rows above are **format examples**, not actual observations or test results.

## Running the benchmark

```bash
python scripts/evaluate_portfolio.py \
  --annotations /path/to/your_private_labels.csv \
  --media-root /path/to/your_authorized_videos \
  --mode compilation \
  --threshold 0.20 \
  --max-candidates 10 \
  --tolerance 5 \
  --out /path/to/private_replayd_eval_results
```

The script runs the unchanged detector once per source and reuses the extracted audio scores for the audio-only ablation. It writes `summary.json`, `per_video.csv` and `candidates.csv`.

**Interpretation:**

- **Precision @ ±5 s:** matched candidate timestamps / all suggested candidate timestamps. Only meaningful if *all* relevant events were labeled.
- **Recall @ ±5 s:** labeled events with a one-to-one candidate match / all labeled events.
- **F1 @ ±5 s:** harmonic mean of precision and recall.
- **Goal coverage @ ±5 s:** number of labeled goals within ±5 s of any suggestion / labeled goals. It does **not** mean REPLAYD knows that they are goals.
- **Clip coverage:** labeled event timestamps falling inside at least one suggested start/end window. This can be high even if clips are too long.
- **Mean matched error:** average absolute timestamp difference for matched pairs only; report alongside recall to avoid hiding misses.
- **Processing time:** elapsed source analysis time; note computer, source duration/resolution and settings.

One-to-one matching prevents a single proposed timestamp from counting as many detected events. Matching maximizes the number of matched pairs within tolerance.

### Editing-time comparison

Use the same raw recording to compare **manual search and edit** against **REPLAYD-assisted search and edit**. Use comparable tasks and record total human time, including review, adjustments and export. Counterbalance order across several clips to reduce learning effects. Log using `evaluation/manual_time_template.csv`. Compute `(manual_total - assisted_total) / manual_total × 100`, reporting negative values if REPLAYD takes longer. This measurement is separate from machine processing time.

### Reporting quality

Write measured values and show video count, number of labeled events, tolerance, candidate budget, settings, hardware and whether footage was held out. Include false-positive examples and events missed. Do not present one successful demo, synthetic assets or selectively tuned video as a general accuracy guarantee.

### When only goals are annotated

Report **goal coverage only** and candidate counts. **Do not** call the resulting precision/recall an overall highlight-detection score; saves and chances would be wrongly counted as false positives. The script computes general event metrics mechanically; their interpretation depends on complete labeling.
