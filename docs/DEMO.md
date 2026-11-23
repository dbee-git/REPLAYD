# REPLAYD portfolio demo storyboard (60–90 seconds)

**Recording rule:** Capture the local app with synthetic footage and synthetic analytics. Never show private campaign details, browser personal tabs, account emails or copyrighted broadcast clips in a public demonstration.

| Time | Screen | Narration (adapt to what actually appears) |
|---|---|---|
| 0–10 s | Landing page, Launch Studio | "REPLAYD is a local-first assistant for football creators, built with Python, FastAPI and FFmpeg." |
| 10–25 s | Select included synthetic test video, Analyze | "It proposes interesting time windows from audio activity and video scene transitions." |
| 25–43 s | Select candidate and review start/end timecodes | "The creator checks the suggestion and edits exact MM:SS clip boundaries before export." |
| 43–55 s | Choose 9:16 full-frame and export sample MP4 | "FFmpeg renders a platform-ready clip locally without a paid API key." |
| 55–70 s | Analytics with labeled synthetic data | "Creators can import incomplete post metrics and compare save rates across types and platforms." |
| 70–85 s | Campaigns with fictional rate and status | "Campaigns track RPM, eligible views, approvals and recorded settlements separately." |

**Closing line:** "It's an end-to-end creator workflow, not an autonomous goal classifier. The next technical step is benchmarking on labeled, unseen football footage."

## Capture checklist

- Use browser at 100% zoom, close unrelated tabs/notifications, and crop out account identifiers.
- Show the actual running app, not a Figma mockup or fake animations.
- Label synthetic footage and fictional analytics as **DEMO DATA** in the video or description.
- Show a real MP4 export action, not merely a static status screen.
- If you publish accuracy numbers later, accompany them with protocol and per-video measurements.
- Prefer a 1080p screen recording with voice-over; optional captions are useful for muted viewing.

## README / application links

Once the public repository exists, add the real project URL and a viewable demo link to the README. No hosted REPLAYD demo is supplied because this version is not hardened for public multi-user deployment.

## Automated pipeline demo (no screen recording)

Run `python scripts/demo_end_to_end.py` to analyze the included 45-second **synthetic** video and export a real 9:16 MP4 to `demo_output/`, together with a short manifest. This verifies the processing/export pipeline but does not showcase goal recognition or prove football accuracy. For your portfolio, record the actual app UI using the storyboard above.
