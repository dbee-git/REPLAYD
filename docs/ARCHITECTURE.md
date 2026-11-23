# Architecture and implementation notes

## Summary

REPLAYD is a local single-user Python FastAPI app with a static browser front end and a local SQLite record store. It does not require account registration, paid AI inference endpoints or platform access tokens. The app listens on `127.0.0.1:8000` by default.

## Flow of a source video

1. **Upload and validation:** `/api/projects` saves the source using a generated ID, checks the file extension, probes metadata with FFprobe, and rejects files exceeding the local size/duration limits.
2. **Audio processing:** FFmpeg extracts mono PCM WAV; the detector computes frame-wise RMS loudness, rolling background medians, short activity increases and sustained intensity.
3. **Visual proposals:** FFmpeg samples resized grayscale frames (2 fps), and frame differences approximate scene transitions. Clusters of transitions can create candidates even when there is no substantial audio peak.
4. **Candidate ranking:** Audio strength and nearby scene-cut density contribute to a heuristic score. Candidates are separated by a minimum time gap and limited to a creator-selected count.
5. **Suggested boundaries:** Typically 5 s before a detected candidate (6 s for continuous footage) and ~18 s after it, with small adjustments to nearby transitions. They are editable suggestions, not semantic action intervals.
6. **Manual review and export:** The browser shows audio activity and candidate timestamps. The user adjusts boundaries in `MM:SS`, chooses a layout, and the server re-encodes MP4 via FFmpeg. Full-frame 9:16 padding avoids cropping away the ball by default.

## Backend modules

- `replayd/core.py`: signal features, scene changes, candidate ranking and scene-aware boundary suggestions
- `replayd/media.py`: FFprobe metadata
- `replayd/export.py`: video rendering, validation and output layouts
- `replayd/web.py`: FastAPI routes, local project persistence, data import, campaigns and downloads
- `replayd/analytics.py`, `replayd/analytics_store.py`: normalization, partial CSV/TSV imports and descriptive metrics
- `replayd/campaigns.py`: campaign setup, submission lifecycle, approved-view accounting and settlement ledger
- `replayd/evaluation.py`: one-to-one temporal matching and precision / recall / F1

## Dataset and record boundaries

- `data/*.mp4` and `data/*.csv` are small **synthetic** assets for demo and regression tests.
- Source footage, SQL databases, output media and private analytics are saved to `.local_data/` (or `REPLAYD_DATA_DIR`) and must never be committed.
- The portfolio evaluation CLI loads human annotations and user-owned media separately from the product database.

## Deployment boundary

The current app has no login system, background job queue, quotas, sandboxed FFmpeg workers or multi-user privacy boundaries. It should be run on the developer's machine, **not** deployed as-is to a public internet-facing server. A public product would require proper access controls, resource limits, job isolation and security testing.
