# REPLAYD v0.5 — Read `README_V0_5.md` for the latest changes and Mac setup

# REPLAYD — Studio · Intelligence · Paid Campaigns

**Version 0.5.0 — working local-first portfolio software (Python + FastAPI + SQLite + FFmpeg).**

This is an upgrade of REPLAYD v0.2, not a replacement or a cloud service. No external AI or paid social-media API keys are required. **The existing video editor, media library, campaigns, approved view counts and payment tracking are preserved.**

## Run on your Mac without updating pip

1. Stop the old server using **Ctrl+C** in its Terminal.
2. Unzip v0.4 into `~/Downloads/REPLAYD_v0_4`, alongside your old v0.2 folder.
3. Reuse the v0.2 virtual environment if it's still there:

```bash
cd ~/Downloads/REPLAYD_v0_4
source ../REPLAYD_v0_2/.venv/bin/activate
python run.py
```

4. Visit **http://127.0.0.1:8000** and open **Analytics** or **Campaigns**.

If v0.2's environment is missing, create a fresh one:

```bash
cd ~/Downloads/REPLAYD_v0_4
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

FFmpeg is the only system dependency (`brew install ffmpeg`), already installed if v0.2 worked. **No pip upgrade is necessary.**

## Analytics inherited from v0.3

### Intelligence (major redesign)

- **Three ways to enter insights:** quick manual form (only one engagement field required), flexible CSV/TSV import, and pasted CSV/tab-separated spreadsheet data.
- **Partial data is expected:** omitted likes/comments/shares/saves/watch metrics remain unknown, not zero; irrelevant extra columns are ignored and recognized column aliases are mapped.
- **Local persistence:** imported posts are saved in the same local SQLite database, survive restarts, and may be individually deleted.
- **Duplicate prevention:** reimporting an existing `platform + clip_id` updates it, preserving existing known fields when incoming values are blank. If `clip_id` is missing, REPLAYD generates a stable row fingerprint; identical rows deduplicate, but changing a row without an explicit ID can result in a new record.
- **Real comparisons:** post totals, median share/save/like rates, content category comparisons, platform breakdown, duration brackets and weekday patterns.
- **Qualifiers:** category-level comparisons require at least 3 measurable posts; displays reveal data coverage, limit weak recommendations and note that lifetime views are not age-matched.
- **Average watch vs length:** optional viewing-depth proxy when data is present; it is not a platform-defined completion rate and can exceed 100% with replays.
- **Synthetic demo:** a separately labeled 144-post file is included and can be loaded from the UI; do not mix demo rows with real records when drawing conclusions.

### Campaigns (expanded discovery, calmer visual design)

- A compact explainer for clipping, discovering opportunities on Discord/community platforms, and eight independently linked sources: Whop, Content Rewards, Clipster, Spade, CLIPPING, Starlet, Vyro, Clipur; plus two publicly listed Discord communities.
- Whop and Content Rewards are separate services. Brand links are informational and not partnerships or API integrations. Review eligibility, payment rules, IP ownership, and campaign requirements before participating.
- The original Campaign Hub, settlement ledger, exports and editor remain intact.

### Color design

Neutral near-black backgrounds and white typography; lime remains the flagship REPLAYD accent, Intelligence now matches the mature slate-and-sage palette. Supporting charts use muted cool blue, olive, and amber; Discord alone retains a subtle brand-specific blue-violet. Studio, Library, Features, and Workflow styling is unchanged.

## Technical limitations and integrity

- The existing Studio uses **audiovisual heuristics**, not a trained goal/card recognition model. Its scores are not probabilities.
- No automated social insight harvesting, Instagram login, TikTok/Discord scraping, OCR screenshot imports, or connected paid campaigns. Analytics is creator-entered or creator-imported.
- Supports common CSV/TSV column names, **not every native export layout**. `views`, `likes`, `comments`, `shares`, `saves`, and `reach` can be partial; no invented zeroes.
- For CSV imports: max 3 MB and 5,000 rows; raw UTF-8 CSV/TSV recommended. Posts are single snapshots, not growth histories. Comparing results at equal post ages needs repeated snapshots, a future improvement.
- App runs for a **single trusted local user**, bound to 127.0.0.1. Do not publicly host it without authentication and security hardening.
- Source football videos should be owned or licensed; public availability does not grant commercial reuse rights.

## Backups and existing data

The app automatically chooses the first folder **containing `replayd.sqlite3`** in this order: `REPLAYD_v0_4/.local_data`, `REPLAYD_v0_3/.local_data`, `REPLAYD_v0_2/.local_data`, `REPLAYD_v0_1/.local_data`. If none exists, it creates `REPLAYD_v0_4/.local_data`.

**Keep your old v0.1/v0.2 directories in place for now.** They may contain `.local_data` with absolute video paths. Back up `.local_data` before important changes. You can manually set a location with `REPLAYD_DATA_DIR`.

SQLite migration adds only the `creator_posts` table for Analytics; existing Campaigns, videos and settlements are not reset. API documentation is available at `/api/docs`.

## Tests

```bash
python -m pytest -q
```

The repository includes unit and API tests for media export, campaign calculations, payment auditing, flexible analytics imports and persistence. Mocked-browser visual tests were additionally run during development; live visual acceptance on your Mac is still required.

## Architecture

- `replayd/web.py` — local FastAPI routes and database initialization
- `replayd/core.py`, `replayd/export.py` — highlight candidate detection and MP4 export
- `replayd/campaigns.py` — campaign records, view snapshots and payment ledger
- `replayd/analytics.py` — partial-data ingestion, derived metrics and group summaries
- `replayd/analytics_store.py` — durable, deduplicated creator-post records
- `static/index.html`, `static/styles.css`, `static/app.js`, `static/campaigns.js`, `static/analytics.js` — custom website
- `data/REPLAYD_SYNTHETIC_144_posts.csv` — 144 fictional complete demo posts
- `data/REPLAYD_SYNTHETIC_PARTIAL_24_posts.csv` — 24 fictional posts with missing metrics for fallback testing


## v0.4 additions (focused upgrade)

- **Campaign discovery:** concise primer on clipping, an expanded Discord explainer (how briefs and submissions work), and two discoverable communities listed on Discord's own directory. These are third-party references, not verified offers or endorsements.
- **Eight independently verified platform links:** Whop, Content Rewards, Clipster, Spade, CLIPPING, Starlet, Vyro, Clipur. Four show initially and four are in a disclosure so the page remains easy to scan. Brand-shaped monograms are UI approximations, not official platform logos.
- **Campaign source dropdown:** add those sources plus Discord community, while retaining Direct / Other and all existing campaign ledger features and database schema.
- **Analytics demo CSVs:** one fully synthetic dataset with 144 posts, another deliberately incomplete 24-post sample. Both have `is_demo=1`, retained on import, so demo rows are visibly distinguished from genuine records.
- **No fabricated platform access:** the opportunity directory links to official websites but never scrapes campaigns or infers availability, membership or payment guarantees.
- The site remains local-first; brand badges are text/CSS with no image hotlinks or API keys.

### Upgrading from v0.3 (keep your data)

The auto-detection checks for an existing SQLite database in this order: `REPLAYD_v0_4/.local_data`, `REPLAYD_v0_3/.local_data`, `REPLAYD_v0_2/.local_data`, `REPLAYD_v0_1/.local_data`. Keep your current folders next to the new one and back up `.local_data` before changes. Reuse v0.3's (or v0.2's) virtualenv and run `python run.py`.

The additional directory options do not represent platform integrations, promises of active jobs, or legal advice. Rights and promotional restrictions vary by jurisdiction and platform.

### Visual design decision
The earlier heavily magenta Intelligence theme has been rolled back. REPLAYD retains its recognizable lime identity but uses near-black surfaces, soft sage chart accents, steel blue, warm muted yellow, and selective Discord indigo. Existing Features / How it Works / My Library pages have not been redesigned.

### Testing the sample files
- Open Analytics → **Try demo insights** to import the bundled **144 fully synthetic posts**.
- Import `data/REPLAYD_SYNTHETIC_PARTIAL_24_posts.csv` through **CSV import** to test missing fields. Empty cells stay unknown and do not become zero.
- Do not interpret simulated metrics as actual creator campaign results.
- If you already imported the old 60-post example, the new data uses the same demo ID prefix and will update the corresponding 60 entries rather than duplicating them; the additional 84 posts are new.
