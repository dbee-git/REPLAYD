"""Durable, single-user local analytics storage with per-post upsert semantics."""
from __future__ import annotations

import json
import uuid

from replayd.analytics import FIELDS, normalize_row


def setup(db):
    db.execute('''CREATE TABLE IF NOT EXISTS creator_posts (
        id TEXT PRIMARY KEY, platform TEXT NOT NULL, clip_id TEXT NOT NULL,
        payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(platform,clip_id)
    )''')


def all_posts(db):
    return [dict(json.loads(row['payload']),id=row['id']) for row in db.execute('SELECT * FROM creator_posts ORDER BY updated_at DESC,rowid DESC LIMIT 5000').fetchall()]


def upsert(db, data, merge_missing=True):
    values=normalize_row(data, fallback_id='manual-'+uuid.uuid4().hex[:12])
    existing=db.execute('SELECT * FROM creator_posts WHERE platform=? AND clip_id=?',(values['platform'],values['clip_id'])).fetchone()
    if existing:
        old=json.loads(existing['payload'])
        if merge_missing:
            for field in FIELDS:
                if values.get(field) is None:values[field]=old.get(field)
        db.execute('UPDATE creator_posts SET payload=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(json.dumps(values),existing['id']))
        return existing['id'],False
    identifier=uuid.uuid4().hex
    db.execute('INSERT INTO creator_posts (id,platform,clip_id,payload) VALUES (?,?,?,?)',(identifier,values['platform'],values['clip_id'],json.dumps(values)))
    return identifier,True


def remove(db, identifier):
    return db.execute('DELETE FROM creator_posts WHERE id=?',(identifier,)).rowcount > 0
