# Limitations and responsible portfolio claims

## What is *not* implemented

- No trained neural football goal, card or save classifier; the analysis uses audio surges plus simple frame-change proposals.
- No guarantee a loud moment is a goal, or that a goal has sufficiently loud audio to be proposed.
- No player or ball tracking, scoreboard OCR, automatic copyright clearance or upload to social platforms.
- No causal analytics or reliable viral-reach prediction; observed save/share rates are descriptive.
- No automatic logo/music application to exported campaign clips; campaigns record these as requirements.
- No internet-facing production hardening or account system.

## Sources of error

- Long crowd cheering, aggressive commentary, whistles and advertising can trigger audio candidates.
- Rapid replays and edit transitions can trigger visual candidates independent of meaningful actions.
- Camera/scoreboard overlays, audio mixing, muted commentary and low-resolution footage change detector behavior.
- Clip start/end proposals are heuristics; creators must verify the narrative build-up and celebration.
- Smaller candidate budgets trade higher precision-like user convenience for possible misses.

## Rights and data ethics

Only upload footage you are authorized to process, and respect platform and league restrictions. Do not commit creator payment data, customer information, real footage or private campaign notes. Synthetic analytics CSV values and demo assets are *not* evidence of product impact.

## Correct resume language

Suitable: "Built a local-first Python/FastAPI football highlight suggestion and editing platform using audio/scene-change heuristics, FFmpeg exports, SQLite and descriptive creator analytics; implemented automated tests and a reproducible evaluation protocol."

Only after independent measurement: add real precision, recall, goal-coverage and time-saving numbers, with test footage counts and scope. Avoid saying "trained football goal recognition AI" or claiming specific accuracy without a labeled benchmark.
