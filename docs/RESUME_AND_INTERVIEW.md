# Portfolio and interview wording

## Resume-ready entry (accurate today)

**REPLAYD — Football Creator Studio**  
*Python, FastAPI, NumPy, pandas, FFmpeg, SQLite, HTML/CSS/JavaScript*

- Built a local-first football creator application that proposes highlight timestamps using audio activity and independent scene-change signals, then lets editors refine `MM:SS` cuts and export MP4 clips in original/9:16 formats.
- Implemented creator analytics with partial CSV/manual data imports and save-rate comparisons, plus campaign RPM, approved-view revenue, and partial-settlement tracking in SQLite; validated core functionality with **75 automated software tests**.

Once the independent evaluation is complete, replace generic descriptions with **measured** candidate coverage, matched precision/recall and editing-time improvement. Do not put any invented impact statistics on your resume.

## Interview questions to prepare for

**Why combine audio and video?** Because loudness can reflect missed chances or advertisements and some football events are relatively quiet. Independent visual proposals increase candidate diversity, while leaving semantic event labeling to the editor.

**How does your audio detector work?** Extract PCM mono audio; compute RMS loudness across short windows; compare to a rolling local baseline; combine sudden surges with sustained intensity; propose local maxima.

**How does video detection work?** Sample low-resolution grayscale frames at 2 fps, compare neighboring frames, identify abrupt changes and cluster nearby transitions into suggestions. It detects editing patterns, not a ball crossing a goal line.

**How do you decide clip boundaries?** Approximately 5–6 seconds of pre-event footage plus ~18 seconds afterward, with nearby cut adjustment. The creator can override both timecodes.

**What makes analytics credible?** Preserve unknown vs zero, compute normalized save/share rates only when numerator and denominator are available, and report category sample sizes. No causal viral-growth claims.

**How do campaign payments work?** Approved eligible views × USD RPM ÷ 1,000,000, with campaign caps. Public views are tracked separately; paid settlements and outstanding balances are distinct.

**What have you benchmarked?** The application has software regression tests. Real football detection accuracy must be reported after the held-out timestamp evaluation; synthetic fixture tests are not semantic goal-recognition evidence.

**What would you build next?** A football-specific event model, scoreboard OCR, asynchronous processing, rights-aware media handling and public-hosting security—but these are future extensions, not completed features.

## One-line pitch

"REPLAYD is a local-first football creator assistant: it finds likely highlights from audiovisual signals, helps produce clips, and connects content metrics with paid campaign tracking—all without paid API keys."
