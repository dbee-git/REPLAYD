"""Local campaign ledger for sponsored clipping work.

No platform integrations, no speculative views, and no claims about platform payout
policies. Campaign rates are in USD per MILLION approved, eligible views.
Currency is stored in whole cents to avoid floating-point settlement errors.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import sqlite3
import uuid


def dollars_to_cents(amount) -> int:
    try:
        value = Decimal(str(amount))
        if not value.is_finite() or value < 0 or value > Decimal("1000000"):
            raise ValueError("Amount must be between $0 and $1,000,000")
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Use at most two decimal places for USD amounts")
        return int(value * 100)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid USD amount") from exc


def usd(cents: int) -> str:
    return str((Decimal(int(cents)) / Decimal(100)).quantize(Decimal(".01")))


def payout_cents(eligible_views: int, rpm_cents: int, cap_cents: int | None = None) -> int:
    amount = (Decimal(int(eligible_views)) * Decimal(int(rpm_cents)) / Decimal(1_000_000)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    cents = int(amount)
    return min(cents, cap_cents) if cap_cents is not None else cents


def setup(db: sqlite3.Connection):
    db.execute("""CREATE TABLE IF NOT EXISTS campaigns (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, brand TEXT NOT NULL,
      source_platform TEXT NOT NULL DEFAULT 'Direct',
      requirement_type TEXT NOT NULL CHECK(requirement_type IN ('logo','music','both')),
      rpm_cents INTEGER NOT NULL CHECK(rpm_cents > 0),
      min_duration_sec INTEGER NOT NULL CHECK(min_duration_sec > 0),
      max_duration_sec INTEGER NOT NULL CHECK(max_duration_sec >= min_duration_sec),
      payout_cap_cents INTEGER CHECK(payout_cap_cents >= 0),
      status TEXT NOT NULL CHECK(status IN ('active','paused','completed')) DEFAULT 'active',
      notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS campaign_submissions (
      id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id),
      clip_id TEXT REFERENCES clips(id), title TEXT NOT NULL,
      platform TEXT NOT NULL, post_url TEXT NOT NULL DEFAULT '', posted_on TEXT,
      duration_sec INTEGER, public_views INTEGER CHECK(public_views >= 0),
      eligible_views INTEGER NOT NULL DEFAULT 0 CHECK(eligible_views >= 0),
      status TEXT NOT NULL CHECK(status IN ('draft','submitted','approved','rejected')) DEFAULT 'submitted',
      edit_minutes INTEGER CHECK(edit_minutes >= 0), notes TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS campaign_view_history (
      id TEXT PRIMARY KEY, submission_id TEXT NOT NULL REFERENCES campaign_submissions(id),
      public_views INTEGER, eligible_views INTEGER NOT NULL,
      recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS campaign_payments (
      id TEXT PRIMARY KEY, campaign_id TEXT NOT NULL REFERENCES campaigns(id),
      amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
      paid_on TEXT NOT NULL, reference TEXT NOT NULL DEFAULT '',
      notes TEXT NOT NULL DEFAULT '', voided_at TEXT, void_reason TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_submissions_campaign ON campaign_submissions(campaign_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_payments_campaign ON campaign_payments(campaign_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_view_history_submission ON campaign_view_history(submission_id)")


def row(db, sql, args=()):
    item = db.execute(sql, args).fetchone()
    return dict(item) if item else None


def _campaign_row(db, campaign_id):
    return row(db, "SELECT * FROM campaigns WHERE id=?", (campaign_id,))


def _submission_row(db, submission_id):
    return row(db, "SELECT * FROM campaign_submissions WHERE id=?", (submission_id,))


def _as_submission(rec, campaign):
    v = rec.get('eligible_views') or 0
    duration = rec.get('duration_sec')
    in_range = None if duration is None else campaign['min_duration_sec'] <= duration <= campaign['max_duration_sec']
    return {
        **rec,
        "duration_within_preference": in_range,
        "estimated_usd": usd(payout_cents(v, campaign['rpm_cents'])),
        "last_updated": rec['updated_at'],
    }


def summary(db, record, include_details=True):
    cid = record['id']
    submissions = [dict(r) for r in db.execute(
        "SELECT * FROM campaign_submissions WHERE campaign_id=? ORDER BY created_at DESC, rowid DESC", (cid,)).fetchall()]
    payments = [dict(r) for r in db.execute(
        "SELECT * FROM campaign_payments WHERE campaign_id=? ORDER BY paid_on DESC,created_at DESC,rowid DESC", (cid,)).fetchall()]
    approved = sum(s['eligible_views'] for s in submissions if s['status'] == 'approved')
    pending = sum(s['eligible_views'] for s in submissions if s['status'] == 'submitted')
    # Apply cap to the TOTAL campaign payout, not once per individual submission.
    gross = payout_cents(approved, record['rpm_cents'], record['payout_cap_cents'])
    projected = payout_cents(approved + pending, record['rpm_cents'], record['payout_cap_cents'])
    settled = sum(p['amount_cents'] for p in payments if p['voided_at'] is None)
    eligible_all = sum(s['eligible_views'] for s in submissions if s['status'] != 'rejected')
    total_public = sum(s['public_views'] for s in submissions if s['public_views'] is not None)
    editing_minutes = sum(s['edit_minutes'] for s in submissions if s['edit_minutes'] is not None)
    out = {
        'id':cid, 'title':record['title'], 'brand':record['brand'], 'source_platform':record['source_platform'],
        'requirement_type':record['requirement_type'], 'rpm_usd':usd(record['rpm_cents']),
        'min_duration_sec':record['min_duration_sec'], 'max_duration_sec':record['max_duration_sec'],
        'payout_cap_usd':usd(record['payout_cap_cents']) if record['payout_cap_cents'] is not None else None,
        'status': record['status'], 'notes':record['notes'], 'created_at':record['created_at'],
        'submission_count':len(submissions), 'approved_count':sum(s['status']=='approved' for s in submissions),
        'approved_eligible_views':approved, 'pending_eligible_views':pending,
        'tracked_eligible_views':eligible_all, 'tracked_public_views':total_public,
        'confirmed_earnings_usd':usd(gross), 'potential_total_usd':usd(projected),
        'additional_pending_usd':usd(max(0, projected-gross)),
        'settled_usd':usd(settled), 'outstanding_usd':usd(max(0,gross-settled)),
        'advance_usd':usd(max(0,settled-gross)),
        'editing_minutes':editing_minutes,
        'earned_usd_per_edit_hour': usd((Decimal(gross)*60 / Decimal(editing_minutes)).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if editing_minutes else None,
    }
    if include_details:
        out['submissions']=[_as_submission(s,record) for s in submissions]
        out['payments']=[{**p,'amount_usd':usd(p['amount_cents'])} for p in payments]
    return out


def create_campaign(db, *, title, brand, requirement_type, rpm_usd, min_duration_sec, max_duration_sec, source_platform='Direct', payout_cap_usd=None, notes=''):
    if not title.strip() or not brand.strip(): raise ValueError('Campaign name and brand are required')
    if source_platform not in ('Whop','Content Rewards','CLIPPING','Clipster','Spade','Starlet','Vyro','Clipur','Discord','Direct','Other'):raise ValueError('Unknown campaign marketplace')
    if requirement_type not in ('logo','music','both'):
        raise ValueError('Requirement must be logo, music, or both')
    if not 1 <= min_duration_sec <= max_duration_sec <= 3600:
        raise ValueError('Preferred duration should be 1–3600 seconds with min ≤ max')
    rpm = dollars_to_cents(rpm_usd)
    if rpm <= 0: raise ValueError('RPM must be greater than zero')
    cap = dollars_to_cents(payout_cap_usd) if payout_cap_usd is not None else None
    cid=uuid.uuid4().hex
    db.execute('''INSERT INTO campaigns(id,title,brand,source_platform,requirement_type,rpm_cents,min_duration_sec,max_duration_sec,payout_cap_cents,notes)
              VALUES(?,?,?,?,?,?,?,?,?,?)''', (cid,title.strip(),brand.strip(),source_platform,requirement_type,rpm,min_duration_sec,max_duration_sec,cap,notes.strip()))
    return cid


def add_submission(db,campaign_id,*,title,platform,clip_id=None,post_url='',posted_on=None,duration_sec=None,public_views=None,eligible_views=0,status='submitted',edit_minutes=None,notes=''):
    if not _campaign_row(db,campaign_id):raise LookupError('Campaign not found')
    if not title.strip() or not platform.strip(): raise ValueError('Submission name and platform are required')
    if post_url and not post_url.startswith(('http://','https://')):raise ValueError('Post URL must start with http:// or https://')
    if status not in ('draft','submitted','approved','rejected'):raise ValueError('Invalid submission status')
    if public_views is not None and eligible_views > public_views:raise ValueError('Eligible views cannot exceed supplied public views')
    if clip_id and not row(db,'SELECT id FROM clips WHERE id=?',(clip_id,)):raise ValueError('Linked clip does not exist in the local library')
    if duration_sec is not None and not 1 <= duration_sec <= 3600:raise ValueError('Duration must be 1–3600 seconds')
    if posted_on:date.fromisoformat(posted_on)
    sid=uuid.uuid4().hex
    db.execute('''INSERT INTO campaign_submissions(id,campaign_id,clip_id,title,platform,post_url,posted_on,duration_sec,public_views,eligible_views,status,edit_minutes,notes)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (sid,campaign_id,clip_id or None,title.strip(),platform.strip(),post_url.strip(),posted_on,duration_sec,public_views,eligible_views,status,edit_minutes,notes.strip()))
    _append_snapshot(db,sid,public_views,eligible_views)
    return sid


def _append_snapshot(db,sid,public_views,eligible_views):
    db.execute('INSERT INTO campaign_view_history(id,submission_id,public_views,eligible_views) VALUES(?,?,?,?)',
               (uuid.uuid4().hex,sid,public_views,eligible_views))


def update_submission(db, campaign_id, submission_id, updates):
    current=_submission_row(db,submission_id)
    if not current or current['campaign_id'] != campaign_id:raise LookupError('Submission not found')
    fields={'title','platform','post_url','posted_on','duration_sec','public_views','eligible_views','status','edit_minutes','notes'}
    changes={k:v for k,v in updates.items() if k in fields}
    if not changes:return
    candidate={**current,**changes}
    if not candidate['title'] or not candidate['title'].strip():raise ValueError('Submission title must not be blank')
    if candidate['post_url'] and not candidate['post_url'].startswith(('http://','https://')):raise ValueError('Invalid post URL')
    if candidate['eligible_views'] is None:raise ValueError('Eligible views must be provided')
    if candidate['status'] not in ('draft','submitted','approved','rejected'):raise ValueError('Invalid status')
    if candidate['public_views'] is not None and candidate['eligible_views']>candidate['public_views']:
        raise ValueError('Eligible views cannot exceed supplied public views')
    if candidate['posted_on']:date.fromisoformat(candidate['posted_on'])
    if candidate['duration_sec'] is not None and not 1<=candidate['duration_sec']<=3600:raise ValueError('Duration must be 1–3600 seconds')
    query=','.join(k+'=?' for k in changes)
    db.execute(f"UPDATE campaign_submissions SET {query},updated_at=CURRENT_TIMESTAMP WHERE id=?",(*changes.values(),submission_id))
    if ('public_views' in changes and changes['public_views'] != current['public_views']) or ('eligible_views' in changes and changes['eligible_views'] != current['eligible_views']):
        _append_snapshot(db,submission_id,candidate['public_views'],candidate['eligible_views'])


def add_payment(db,campaign_id,*,amount_usd,paid_on,reference='',notes=''):
    if not _campaign_row(db,campaign_id):raise LookupError('Campaign not found')
    cents=dollars_to_cents(amount_usd)
    if cents<=0:raise ValueError('Payment must be greater than zero')
    date.fromisoformat(paid_on)
    pid=uuid.uuid4().hex
    db.execute('INSERT INTO campaign_payments(id,campaign_id,amount_cents,paid_on,reference,notes) VALUES(?,?,?,?,?,?)',
               (pid,campaign_id,cents,paid_on,reference.strip(),notes.strip()))
    return pid


def void_payment(db,campaign_id,payment_id,reason):
    if not _campaign_row(db,campaign_id):raise LookupError('Campaign not found')
    entry=row(db,'SELECT * FROM campaign_payments WHERE id=? AND campaign_id=?',(payment_id,campaign_id))
    if not entry:raise LookupError('Payment not found')
    if entry['voided_at'] is not None:raise ValueError('Payment has already been voided')
    if not reason.strip():raise ValueError('Explain why the entry is being voided')
    db.execute('UPDATE campaign_payments SET voided_at=CURRENT_TIMESTAMP,void_reason=? WHERE id=?',
               (reason.strip(),payment_id))
