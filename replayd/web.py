"""REPLAYD local-first web API: real video analysis, clip export, CSV insights.

This MVP is meant for a single trusted local user. It is NOT a public multi-user SaaS:
no auth, no job queue, no cloud storage, and no rate limiting.
"""
from __future__ import annotations

from dataclasses import asdict
import io
import csv
import json
import math
import os
from pathlib import Path
import sqlite3
import uuid

from contextlib import contextmanager

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import date
from decimal import Decimal
from replayd import campaigns, analytics_store

from replayd.analytics import analyze_engagement, parse_csv, dashboard
from replayd.core import analyze_video, require_ffmpeg
from replayd.creators import compare_content_types
from replayd.export import LAYOUTS, render_clip
from replayd.media import probe_media

ROOT = Path(__file__).resolve().parent.parent
# Upgrades must keep the creator's existing videos, campaigns, payments and SQLite DB.
# v0.2 might store data in v0_1 (its legacy fallback) or its own folder.
# An explicit REPLAYD_DATA_DIR always wins. New deployments create their own folder.
LEGACY_V05 = ROOT.parent / "REPLAYD_v0_5" / ".local_data"
LEGACY_V04 = ROOT.parent / "REPLAYD_v0_4" / ".local_data"
LEGACY_V03 = ROOT.parent / "REPLAYD_v0_3" / ".local_data"
LEGACY_V02 = ROOT.parent / "REPLAYD_v0_2" / ".local_data"
LEGACY_V01 = ROOT.parent / "REPLAYD_v0_1" / ".local_data"
DEFAULT_DATA = ROOT / ".local_data"
# Prefer folders with a real database, not an empty .local_data directory.
# The latter can be created by an interrupted run and should not hide older records.
DATA_CANDIDATES = (DEFAULT_DATA, LEGACY_V05, LEGACY_V04, LEGACY_V03, LEGACY_V02, LEGACY_V01)
DEFAULT_LOCATION = next(
    (folder for folder in DATA_CANDIDATES if (folder / "replayd.sqlite3").is_file()),
    DEFAULT_DATA,
)
DATA = Path(os.getenv("REPLAYD_DATA_DIR", str(DEFAULT_LOCATION))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / "replayd.sqlite3"
MAX_UPLOAD = 350 * 1024 * 1024  # 350MB for short local demo recordings
MAX_DURATION = 20 * 60  # first version: short source videos, not full matches
ALLOWED_EXTS = {".mp4", ".mov", ".mkv", ".webm"}

app = FastAPI(title="REPLAYD", version="1.0.0", docs_url="/api/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.middleware("http")
async def prevent_stale_local_frontend(request: Request, call_next):
    """Local development UI: avoid stale Safari/Chrome JS between release folders."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@contextmanager
def connect():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("""CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, filename TEXT NOT NULL,
      duration REAL NOT NULL, width INTEGER, height INTEGER,
      has_audio INTEGER NOT NULL, analysis_json TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS clips (
      id TEXT PRIMARY KEY, project_id TEXT NOT NULL, start REAL NOT NULL, end REAL NOT NULL,
      layout TEXT NOT NULL, filename TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(project_id) REFERENCES projects(id)
    )""")
    campaigns.setup(db)
    analytics_store.setup(db)
    db.commit()
    try:
        yield db
        db.commit()
    finally:
        db.close()


def get_project(project_id: str) -> dict:
    with connect() as db:
        row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Project not found")
    return dict(row)


def get_clip(clip_id: str) -> dict:
    with connect() as db:
        row = db.execute("SELECT * FROM clips WHERE id=?", (clip_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Clip not found")
    return dict(row)


def project_payload(record: dict, include_analysis: bool = True) -> dict:
    fields = {k: record[k] for k in ["id", "name", "duration", "width", "height", "has_audio", "created_at"]}
    fields["has_audio"] = bool(fields["has_audio"])
    fields["preview_url"] = f"/api/projects/{record['id']}/video"
    fields["analyzed"] = record["analysis_json"] is not None
    if include_analysis and record["analysis_json"]:
        fields["analysis"] = json.loads(record["analysis_json"])
    return fields


@app.get("/")
async def home():
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-store, max-age=0"})


@app.get("/api/health")
async def health():
    import shutil
    return {"status": "ok", "version": "1.0.0", "ffmpeg_available": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")), "mode": "local"}


@app.get("/api/projects")
async def list_projects():
    with connect() as db:
        rows = db.execute("SELECT * FROM projects ORDER BY created_at DESC, rowid DESC LIMIT 25").fetchall()
    return [project_payload(dict(r), False) for r in rows]


@app.post("/api/projects", status_code=201)
async def upload_project(file: UploadFile = File(...)):
    # Never trust user filenames as paths. All writes use random IDs.
    name = Path(file.filename or "source.mp4").name[:120]
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, "Upload an MP4, MOV, MKV or WebM video")
    project_id = uuid.uuid4().hex
    folder = DATA / "projects" / project_id
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / ("source" + ext)
    total = 0
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_UPLOAD:
                    raise HTTPException(413, "Video exceeds the 350MB local MVP limit")
                out.write(chunk)
        if total == 0:
            raise HTTPException(400, "Video file is empty")
        info = await run_in_threadpool(probe_media, dest)
        if info["duration_sec"] > MAX_DURATION:
            raise HTTPException(400, "The first release supports footage up to 20 minutes. Full matches are planned later.")
        with connect() as db:
            db.execute("INSERT INTO projects(id,name,filename,duration,width,height,has_audio) VALUES(?,?,?,?,?,?,?)", (
                project_id, name, str(dest), info["duration_sec"], info["width"], info["height"], int(info["has_audio"])))
            db.commit()
    except HTTPException:
        dest.unlink(missing_ok=True)
        try: folder.rmdir()
        except OSError: pass
        raise
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"Could not read video: {str(exc)[:180]}") from exc
    finally:
        await file.close()
    return project_payload(get_project(project_id))


@app.get("/api/projects/{project_id}")
async def project_detail(project_id: str):
    return project_payload(get_project(project_id))


@app.get("/api/projects/{project_id}/video")
async def source_video(project_id: str):
    item = get_project(project_id)
    return FileResponse(item["filename"], media_type="video/mp4" if item["filename"].endswith(".mp4") else None)


@app.post("/api/projects/{project_id}/analyze")
async def analyze_project(project_id: str,
                          threshold: float = Query(default=0.25, ge=0.05, le=0.95),
                          max_candidates: int = Query(default=10, ge=1, le=30),
                          mode: str = Query(default="compilation", pattern="^(compilation|full_match)$")):
    item = get_project(project_id)
    if not item["has_audio"]:
        raise HTTPException(422, "Audio track required for the baseline detector")
    try:
        result = await run_in_threadpool(analyze_video, item["filename"], threshold, max_candidates, mode)
    except Exception as exc:
        raise HTTPException(422, f"Analysis failed: {str(exc)[:240]}") from exc
    signals = result["signals"]
    # Downsample visual waveform to a manageable number of browser points.
    step = max(1, math.ceil(len(signals) / 420))
    series = [{"time": round(float(row.time_sec), 2), "score": round(float(row.audio_score), 3)}
              for row in signals.iloc[::step].itertuples()]
    payload = {
        "duration": round(result["duration_sec"], 2),
        "candidates": [asdict(c) for c in result["candidates"]],
        "waveform": series,
        "method": "Audio activity + independent scene-change candidates (heuristic baseline)",
        "mode": mode,
        "shot_transitions": len(result["cuts"]),
        "disclaimer": "Suggested moments are not verified goals or probabilities. Visual-only candidates require review.",
    }
    with connect() as db:
        db.execute("UPDATE projects SET analysis_json=? WHERE id=?", (json.dumps(payload), project_id))
        db.commit()
    return payload


class ClipRequest(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    layout: str = "Portrait · contain"


LAYOUT_MAP = {
    "Original": "Original aspect ratio",
    "Portrait · contain": "Portrait 9:16 — keep full frame",
    "Portrait · crop": "Portrait 9:16 — center crop",
}


@app.post("/api/projects/{project_id}/clips", status_code=201)
async def make_clip(project_id: str, spec: ClipRequest):
    item = get_project(project_id)
    if spec.layout not in LAYOUT_MAP:
        raise HTTPException(400, "Unknown layout")
    if not (spec.start < spec.end <= item["duration"] + 0.01):
        raise HTTPException(400, "Clip start/end must be inside the source video")
    if spec.end - spec.start < 1 or spec.end - spec.start > 90:
        raise HTTPException(400, "Clip length must be between 1 and 90 seconds")
    clip_id = uuid.uuid4().hex
    folder = DATA / "clips"
    folder.mkdir(exist_ok=True)
    target = folder / (clip_id + ".mp4")
    try:
        await run_in_threadpool(render_clip, item["filename"], target, spec.start, spec.end, LAYOUT_MAP[spec.layout])
    except Exception as exc:
        raise HTTPException(422, f"Export failed: {str(exc)[:240]}") from exc
    with connect() as db:
        db.execute("INSERT INTO clips(id,project_id,start,end,layout,filename) VALUES(?,?,?,?,?,?)",
                   (clip_id, project_id, spec.start, spec.end, spec.layout, str(target)))
        db.commit()
    return {"id": clip_id, "project_id": project_id, "start": spec.start, "end": spec.end,
            "layout": spec.layout, "url": f"/api/clips/{clip_id}/download"}


@app.get("/api/clips")
async def list_clips():
    with connect() as db:
        rows = db.execute("SELECT id,project_id,start,end,layout,created_at FROM clips ORDER BY created_at DESC,rowid DESC LIMIT 40").fetchall()
    return [{**dict(row), "url": f"/api/clips/{row['id']}/download"} for row in rows]


@app.get("/api/clips/{clip_id}/download")
async def download_clip(clip_id: str):
    clip = get_clip(clip_id)
    return FileResponse(clip["filename"], media_type="video/mp4", filename="REPLAYD_" + clip_id[:8] + ".mp4")


@app.post("/api/analytics")
async def analyze_csv(file: UploadFile = File(...)):
    """Legacy non-persistent preview API; accepts partial data in v0.3."""
    data = await _read_analytics_file(file)
    try:
        rows, meta=parse_csv(io.BytesIO(data),file.filename or 'analytics.csv')
        result=dashboard(rows)
        result['import_info']=meta
        return JSONResponse(result)
    except ValueError as exc: raise HTTPException(422,str(exc)[:260]) from exc


async def _read_analytics_file(file):
    if Path(file.filename or '').suffix.lower() not in ('.csv','.tsv'):
        raise HTTPException(400,'Select a CSV or TSV file')
    data=await file.read(3*1024*1024+1)
    await file.close()
    if len(data)>3*1024*1024: raise HTTPException(413,'Analytics import exceeds 3MB')
    return data


@app.get('/api/analytics/overview')
async def analytics_overview():
    with connect() as db:posts=analytics_store.all_posts(db)
    return dashboard(posts)


@app.post('/api/analytics/import')
async def import_analytics(file: UploadFile = File(...)):
    data=await _read_analytics_file(file)
    try: rows,meta=parse_csv(io.BytesIO(data),file.filename or 'analytics.csv')
    except ValueError as exc:raise HTTPException(422,str(exc)[:260]) from exc
    counts={'new':0,'updated':0}
    is_demo='synthetic' in (file.filename or '').lower() or 'simulated' in (file.filename or '').lower()
    with connect() as db:
        for row in rows:
            if is_demo: row['is_demo']=True
            _,created=analytics_store.upsert(db,row)
            counts['new' if created else 'updated']+=1
        result=dashboard(analytics_store.all_posts(db))
    result['import_info']={**meta,**counts}
    return result


class ManualAnalyticsInput(BaseModel):
    clip_id: Optional[str] = None
    platform: Optional[str] = None
    content_type: Optional[str] = None
    views: Optional[int] = Field(default=None,ge=0)
    likes: Optional[int] = Field(default=None,ge=0)
    comments: Optional[int] = Field(default=None,ge=0)
    shares: Optional[int] = Field(default=None,ge=0)
    saves: Optional[int] = Field(default=None,ge=0)
    reach: Optional[int] = Field(default=None,ge=0)
    published_at: Optional[str] = None
    duration_sec: Optional[float] = Field(default=None,ge=0)
    avg_watch_sec: Optional[float] = Field(default=None,ge=0)
    followers_at_post: Optional[int] = Field(default=None,ge=0)
    post_url: Optional[str] = None


@app.post('/api/analytics/manual',status_code=201)
async def manual_analytics(spec:ManualAnalyticsInput):
    try:
        with connect() as db:
            identifier,created=analytics_store.upsert(db,spec.model_dump())
        return {'id':identifier,'created':created}
    except ValueError as exc: raise HTTPException(422,str(exc)[:240]) from exc


@app.delete('/api/analytics/posts/{identifier}',status_code=204)
async def remove_analytics_post(identifier:str):
    with connect() as db:
        if not analytics_store.remove(db,identifier):raise HTTPException(404,'Post not found')
    return Response(status_code=204)


@app.get('/api/sample-analytics')
async def sample_analytics():
    return FileResponse(ROOT/'data'/'REPLAYD_SYNTHETIC_144_posts.csv',media_type='text/csv',filename='REPLAYD_SYNTHETIC_144_posts.csv')


@app.get("/api/demo-video")
async def demo_video():
    return FileResponse(ROOT / "data" / "DEMO_synthetic.mp4", media_type="video/mp4", filename="REPLAYD_synthetic_demo.mp4")


# -------- Paid Campaigns: creator-owned, local-only management and ledger --------
class CampaignInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    brand: str = Field(min_length=1, max_length=120)
    source_platform: Literal['Whop','Content Rewards','CLIPPING','Clipster','Spade','Starlet','Vyro','Clipur','Discord','Direct','Other'] = 'Direct'
    requirement_type: Literal['logo','music','both'] = 'logo'
    rpm_usd: Decimal = Field(gt=0, le=100000)
    min_duration_sec: int = Field(default=15, ge=1, le=3600)
    max_duration_sec: int = Field(default=60, ge=1, le=3600)
    payout_cap_usd: Optional[Decimal] = Field(default=None, ge=0, le=1000000)
    notes: str = Field(default='', max_length=1500)


class CampaignPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    brand: Optional[str] = Field(default=None, min_length=1, max_length=120)
    source_platform: Optional[Literal['Whop','Content Rewards','CLIPPING','Clipster','Spade','Starlet','Vyro','Clipur','Discord','Direct','Other']] = None
    requirement_type: Optional[Literal['logo','music','both']] = None
    rpm_usd: Optional[Decimal] = Field(default=None, gt=0, le=100000)
    min_duration_sec: Optional[int] = Field(default=None, ge=1, le=3600)
    max_duration_sec: Optional[int] = Field(default=None, ge=1, le=3600)
    payout_cap_usd: Optional[Decimal] = Field(default=None, ge=0, le=1000000)
    status: Optional[Literal['active','paused','completed']] = None
    notes: Optional[str] = Field(default=None, max_length=1500)


class SubmissionInput(BaseModel):
    title: str = Field(min_length=1,max_length=150)
    platform: str = Field(min_length=1,max_length=50)
    clip_id: Optional[str] = None
    post_url: str = Field(default='',max_length=1000)
    posted_on: Optional[date] = None
    duration_sec: Optional[int] = Field(default=None,ge=1,le=3600)
    public_views: Optional[int] = Field(default=None,ge=0,le=100000000000)
    eligible_views: int = Field(default=0,ge=0,le=100000000000)
    status: Literal['draft','submitted','approved','rejected'] = 'submitted'
    edit_minutes: Optional[int] = Field(default=None,ge=0,le=100000)
    notes: str = Field(default='',max_length=1500)


class SubmissionPatch(BaseModel):
    title: Optional[str] = Field(default=None,min_length=1,max_length=150)
    platform: Optional[str] = Field(default=None,min_length=1,max_length=50)
    post_url: Optional[str] = Field(default=None,max_length=1000)
    posted_on: Optional[date] = None
    duration_sec: Optional[int] = Field(default=None,ge=1,le=3600)
    public_views: Optional[int] = Field(default=None,ge=0,le=100000000000)
    eligible_views: Optional[int] = Field(default=None,ge=0,le=100000000000)
    status: Optional[Literal['draft','submitted','approved','rejected']] = None
    edit_minutes: Optional[int] = Field(default=None,ge=0,le=100000)
    notes: Optional[str] = Field(default=None,max_length=1500)


class PaymentInput(BaseModel):
    amount_usd: Decimal = Field(gt=0,le=1000000)
    paid_on: date
    reference: str = Field(default='',max_length=150)
    notes: str = Field(default='',max_length=1000)


def _get_campaign(db, campaign_id):
    rec = campaigns._campaign_row(db,campaign_id)
    if not rec:raise HTTPException(404,'Campaign not found')
    return rec


def _bad_input(exc: Exception):
    raise HTTPException(422,str(exc)[:250]) from exc


@app.get('/api/campaigns')
async def list_campaigns():
    with connect() as db:
        records=[dict(r) for r in db.execute('SELECT * FROM campaigns ORDER BY created_at DESC,rowid DESC').fetchall()]
        return [campaigns.summary(db,r,False) for r in records]


@app.post('/api/campaigns', status_code=201)
async def new_campaign(spec: CampaignInput):
    try:
        with connect() as db:
            cid=campaigns.create_campaign(db,**spec.model_dump())
            return campaigns.summary(db,_get_campaign(db,cid))
    except ValueError as exc:_bad_input(exc)


@app.get('/api/campaigns/{campaign_id}')
async def campaign_details(campaign_id: str):
    with connect() as db:return campaigns.summary(db,_get_campaign(db,campaign_id))


@app.patch('/api/campaigns/{campaign_id}')
async def edit_campaign(campaign_id: str, patch: CampaignPatch):
    changes=patch.model_dump(exclude_unset=True)
    try:
        with connect() as db:
            current=_get_campaign(db,campaign_id)
            updated={**current}
            mapped={}
            for key,value in changes.items():
                if key in ('rpm_usd','payout_cap_usd'):
                    mapped['rpm_cents' if key=='rpm_usd' else 'payout_cap_cents'] = campaigns.dollars_to_cents(value) if value is not None else None
                elif value is not None or key == 'payout_cap_usd':mapped[key]=value
            updated.update(mapped)
            if updated['min_duration_sec']>updated['max_duration_sec']:
                raise ValueError('Min duration must not exceed max duration')
            if mapped:
                query=','.join(k+'=?' for k in mapped)
                db.execute(f'UPDATE campaigns SET {query} WHERE id=?',(*mapped.values(),campaign_id))
            return campaigns.summary(db,_get_campaign(db,campaign_id))
    except ValueError as exc:_bad_input(exc)


@app.post('/api/campaigns/{campaign_id}/submissions',status_code=201)
async def new_campaign_submission(campaign_id: str,spec: SubmissionInput):
    values=spec.model_dump()
    if values.get('posted_on'):values['posted_on']=values['posted_on'].isoformat()
    try:
        with connect() as db:
            sid=campaigns.add_submission(db,campaign_id,**values)
            out=campaigns.summary(db,_get_campaign(db,campaign_id))
            out['new_submission_id']=sid
            return out
    except (ValueError,LookupError) as exc:_bad_input(exc)


@app.patch('/api/campaigns/{campaign_id}/submissions/{submission_id}')
async def update_campaign_submission(campaign_id: str,submission_id: str,patch: SubmissionPatch):
    updates=patch.model_dump(exclude_unset=True)
    if updates.get('posted_on'): updates['posted_on']=updates['posted_on'].isoformat()
    try:
        with connect() as db:
            _get_campaign(db,campaign_id)
            campaigns.update_submission(db,campaign_id,submission_id,updates)
            return campaigns.summary(db,_get_campaign(db,campaign_id))
    except LookupError: raise HTTPException(404,'Submission not found')
    except ValueError as exc:_bad_input(exc)


@app.post('/api/campaigns/{campaign_id}/payments',status_code=201)
async def record_payment(campaign_id: str,spec: PaymentInput):
    try:
        with connect() as db:
            campaigns.add_payment(db,campaign_id,amount_usd=spec.amount_usd,paid_on=spec.paid_on.isoformat(),reference=spec.reference,notes=spec.notes)
            return campaigns.summary(db,_get_campaign(db,campaign_id))
    except (ValueError,LookupError) as exc:_bad_input(exc)


@app.get('/api/campaigns/{campaign_id}/view-history/{submission_id}')
async def submission_view_history(campaign_id: str,submission_id: str):
    with connect() as db:
        _get_campaign(db,campaign_id)
        s=campaigns._submission_row(db,submission_id)
        if not s or s['campaign_id']!=campaign_id: raise HTTPException(404,'Submission not found')
        return [dict(x) for x in db.execute('SELECT public_views,eligible_views,recorded_at FROM campaign_view_history WHERE submission_id=? ORDER BY rowid',(submission_id,))]


class VoidPaymentRequest(BaseModel):
    reason: str = Field(min_length=3,max_length=500)


@app.post('/api/campaigns/{campaign_id}/payments/{payment_id}/void')
async def void_campaign_payment(campaign_id: str,payment_id: str,spec: VoidPaymentRequest):
    try:
        with connect() as db:
            campaigns.void_payment(db,campaign_id,payment_id,spec.reason)
            return campaigns.summary(db,_get_campaign(db,campaign_id))
    except LookupError: raise HTTPException(404,'Payment or campaign not found')
    except ValueError as exc:_bad_input(exc)


@app.get('/api/campaign-reports/summary.csv')
async def download_campaign_report():
    """Export the creator's own local business ledger, never a third-party platform feed."""
    output=io.StringIO()
    writer=csv.writer(output)
    cols=[('id','Campaign ID'),('title','Campaign'),('brand','Brand'),('source_platform','Marketplace'),
          ('requirement_type','Placement'),('status','Status'),('rpm_usd','RPM USD / 1M'),
          ('min_duration_sec','Min seconds'),('max_duration_sec','Max seconds'),('payout_cap_usd','Cap USD'),
          ('submission_count','Reels'),('approved_eligible_views','Approved eligible views'),
          ('pending_eligible_views','Pending eligible views'),('confirmed_earnings_usd','Confirmed USD'),
          ('additional_pending_usd','Additional pending estimate USD'),('settled_usd','Payments USD'),
          ('outstanding_usd','Outstanding USD'),('advance_usd','Advance / excess USD'),
          ('editing_minutes','Editing minutes'),('earned_usd_per_edit_hour','Earnings per edit hour USD')]
    writer.writerow([label for _,label in cols])
    with connect() as db:
        for rec in db.execute('SELECT * FROM campaigns ORDER BY created_at DESC,rowid DESC').fetchall():
            data=campaigns.summary(db,dict(rec),False)
            writer.writerow([data[k] if data[k] is not None else '' for k,_ in cols])
    return Response(content='\ufeff'+output.getvalue(),media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition':'attachment; filename="REPLAYD_campaigns_summary.csv"'})
