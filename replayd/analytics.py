"""Robust, honest, API-independent creator engagement analysis.

Missing fields remain unknown, never converted into zero. Every rate has a
well-defined denominator. Data is descriptive: no social-media API or prediction.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
from datetime import datetime
from statistics import median

import pandas as pd

FIELDS = (
    'clip_id', 'platform', 'content_type', 'published_at', 'captured_at',
    'views', 'likes', 'comments', 'shares', 'saves', 'reach',
    'duration_sec', 'avg_watch_sec', 'followers_at_post', 'age_hours',
    'caption', 'post_url', 'is_demo',
)
COUNT_FIELDS = ('views', 'likes', 'comments', 'shares', 'saves', 'reach', 'followers_at_post')
NUMERIC_FIELDS = COUNT_FIELDS + ('duration_sec', 'avg_watch_sec', 'age_hours')
ALIASES = {
    'clip_id': ('clip id', 'clip_id','post id','post_id','reel id','reel_id','video id','video_id','id'),
    'platform': ('platform','posted site','posted_site','site','network','social platform'),
    'content_type': ('content type','content_type','category','genre','video type','topic'),
    'published_at': ('published at','published_at','posted at','posted_at','posted on','post date','publish date','date posted','date'),
    'captured_at': ('captured at','captured_at','snapshot at','snapshot_at','insights date','measured at'),
    'views': ('views','view count','view_count','plays','video views','total views','views count'),
    'likes': ('likes','like count','like_count','hearts'),
    'comments': ('comments','comment count','comments count'),
    'shares': ('shares','share count','share_count','sends'),
    'saves': ('saves','save count','save_count','bookmarks'),
    'reach': ('reach','accounts reached','unique reach'),
    'duration_sec': ('duration sec','duration_sec','video duration','length seconds','duration','video length'),
    'avg_watch_sec': ('avg_watch_sec','average watch time','average view duration','avg watch time','avg view duration','watch time sec'),
    'followers_at_post': ('followers at post','followers_at_post','followers','follower count'),
    'age_hours': ('age_hours','age hours','post age hours'),
    'caption': ('caption','description','title'),
    'post_url': ('post url','post_url','reel url','video url','link','url'),
    'is_demo': ('is_demo','synthetic','demo'),
}


def _key(value):
    return re.sub(r'[^a-z0-9]', '', str(value).strip().lower())


def _empty(value):
    if value is None: return True
    if isinstance(value, float) and math.isnan(value): return True
    return str(value).strip().lower() in ('', 'nan', 'none', 'null', 'n/a', 'na', '-')


def _parse_number(value, name):
    if _empty(value): return None
    raw = str(value).strip().replace(',', '').replace('_','')
    try: number = float(raw)
    except (TypeError, ValueError): raise ValueError('{} must be a non-negative number'.format(name))
    if not math.isfinite(number) or number < 0: raise ValueError('{} must be a non-negative number'.format(name))
    if name in COUNT_FIELDS and not number.is_integer(): raise ValueError('{} must be a whole number'.format(name))
    if name in COUNT_FIELDS: return int(number)
    return round(number, 3)


def normalize_row(values, fallback_id=None):
    """Accept partial manual or CSV rows. At least one engagement count required."""
    norm = {field: None for field in FIELDS}
    for field in FIELDS:
        if field=='is_demo':
            norm[field]=str(values.get(field,'')).strip().lower() in ('1','true','yes','y')
            continue
        value = values.get(field)
        if field in NUMERIC_FIELDS:
            norm[field] = _parse_number(value, field)
        elif not _empty(value):
            norm[field] = str(value).strip()[:1200]
    if not any(norm[field] is not None for field in ('views','likes','comments','shares','saves','reach')):
        raise ValueError('Enter at least one metric (views, likes, shares, comments, saves or reach).')
    if not norm['clip_id']:
        norm['clip_id'] = fallback_id or 'manual-' + hashlib.sha256(json.dumps(norm,sort_keys=True).encode()).hexdigest()[:12]
    if len(norm['clip_id']) > 160: raise ValueError('clip_id exceeds 160 characters')
    if not norm['platform']: norm['platform'] = 'unspecified'
    norm['platform'] = norm['platform'].strip().lower()
    if norm['published_at']:
        # Don't convert timezones or silently fabricate published times.
        value=norm['published_at']
        try: datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError: raise ValueError('published_at must be YYYY-MM-DD or ISO datetime')
    if norm['captured_at']:
        try: datetime.fromisoformat(norm['captured_at'].replace('Z','+00:00'))
        except ValueError: raise ValueError('captured_at must be YYYY-MM-DD or ISO datetime')
    return norm


def parse_csv(csv_or_frame, source='analytics.csv'):
    """Parse 1..5000 rows with common Instagram/YouTube/CSV column aliases."""
    if isinstance(csv_or_frame,pd.DataFrame): df = csv_or_frame.copy()
    else:
        try:
            head = csv_or_frame.read(2048)
            csv_or_frame.seek(0)
            heading = head.decode('utf-8-sig',errors='ignore').splitlines()[0] if isinstance(head,bytes) else str(head).splitlines()[0]
            delimiter = '\t' if '\t' in heading else ';' if ';' in heading and ',' not in heading else ','
            df = pd.read_csv(csv_or_frame, sep=delimiter, engine='python',dtype=str,keep_default_na=False,encoding='utf-8-sig')
        except (UnicodeError, pd.errors.ParserError) as exc: raise ValueError('Cannot read CSV. Export as UTF-8 CSV.') from exc
    if len(df)==0: raise ValueError('CSV is empty')
    if len(df)>5000: raise ValueError('Import at most 5,000 rows at a time')
    lookup={_key(a):field for field, aliases in ALIASES.items() for a in aliases}
    mapped={}
    for original in df.columns:
        field=lookup.get(_key(original))
        if field and field not in mapped: mapped[field]=original
    if not any(name in mapped for name in ('views','likes','comments','shares','saves','reach')):
        raise ValueError('No engagement columns found. Include views or another count such as likes/shares.')
    records=[]
    for idx, row in enumerate(df.to_dict(orient='records'), start=2):
        values={field:row[col] for field,col in mapped.items()}
        fingerprint=hashlib.sha256(json.dumps(values,sort_keys=True,default=str).encode('utf-8')).hexdigest()[:13]
        try: records.append(normalize_row(values,fallback_id='import-'+fingerprint))
        except ValueError as exc: raise ValueError('Row {}: {}'.format(idx,exc)) from exc
    return records, {'matched_columns':list(mapped.keys()), 'ignored_columns':[str(c) for c in df.columns if c not in mapped.values()], 'rows':len(records)}


def _rate(numerator, denominator, multiplier=1):
    return round(numerator / denominator * multiplier, 2) if numerator is not None and denominator is not None and denominator>0 else None


def enrich(post):
    post=dict(post)
    for key in NUMERIC_FIELDS:
        if key not in post: post[key]=None
    views=post.get('views')
    post['shares_per_1000_views']=_rate(post.get('shares'),views,1000)
    post['likes_per_100_views']=_rate(post.get('likes'),views,100)
    post['saves_per_1000_views']=_rate(post.get('saves'),views,1000)
    components=[post.get(key) for key in ('likes','comments','shares','saves')]
    post['interactions_per_100_views']=_rate(sum(components),views,100) if all(x is not None for x in components) else None
    post['average_watch_to_length_pct']=_rate(post.get('avg_watch_sec'),post.get('duration_sec'),100)
    post['views_per_1000_followers']=_rate(views,post.get('followers_at_post'),1000)
    return post


def _mid(values):
    return round(float(median(values)),2) if values else None


def _groups(posts, field, min_posts=3):
    names=sorted(set(str(p.get(field) or '').strip() for p in posts))
    output=[]
    for name in names:
        if not name or name=='unspecified':continue
        rows=[p for p in posts if str(p.get(field) or '').strip()==name]
        shares=[p['shares_per_1000_views'] for p in rows if p['shares_per_1000_views'] is not None]
        saves=[p['saves_per_1000_views'] for p in rows if p['saves_per_1000_views'] is not None]
        views=[p['views'] for p in rows if p['views'] is not None]
        output.append({'name':name, 'posts':len(rows), 'share_posts':len(shares), 'median_shares_1000':_mid(shares) if len(shares)>=min_posts else None,
                       'median_saves_1000':_mid(saves) if len(saves)>=min_posts else None,
                       'median_views':_mid(views) if len(views)>=min_posts else None,
                       'limited':len(rows)<min_posts, 'sharing_limited':len(shares)<min_posts})
    return sorted(output,key=lambda x: (x['median_saves_1000'] is not None,x['median_saves_1000'] or 0,x['posts']),reverse=True)


def _duration_bucket(value):
    if value is None or value<=0:return None
    if value<15:return '<15s'
    if value<=30:return '15–30s'
    if value<=60:return '31–60s'
    return '>60s'


def dashboard(records):
    """Aggregate descriptive, coverage-aware analytics for persisted creator posts."""
    posts=[enrich(p) for p in records]
    coverage={field:sum(p.get(field) is not None for p in posts) for field in ('views','likes','comments','shares','saves','reach','duration_sec','avg_watch_sec','followers_at_post','published_at','content_type')}
    def known_sum(field):
        values=[p[field] for p in posts if p.get(field) is not None]
        return sum(values) if values else None
    shares=[p['shares_per_1000_views'] for p in posts if p['shares_per_1000_views'] is not None]
    likes=[p['likes_per_100_views'] for p in posts if p['likes_per_100_views'] is not None]
    interactions=[p['interactions_per_100_views'] for p in posts if p['interactions_per_100_views'] is not None]
    grouped_types=_groups(posts,'content_type')
    platform_groups=_groups(posts,'platform')
    duration_records=[{**p,'duration_bucket':_duration_bucket(p.get('duration_sec'))} for p in posts]
    duration_groups=_groups(duration_records,'duration_bucket')
    weekday_records=[]
    for p in posts:
        if p.get('published_at'):
            try:
                weekday=datetime.fromisoformat(p['published_at'].replace('Z','+00:00')).strftime('%a')
                weekday_records.append({**p,'weekday':weekday})
            except ValueError:pass
    weekday_groups=_groups(weekday_records,'weekday')
    insights=[]
    eligible=[g for g in grouped_types if g['median_saves_1000'] is not None]
    if len(eligible)>=2:
        best=eligible[0];insights.append({'kind':'signal','title':'Most saved football category','body':"{} has the highest median saves per 1,000 views ({}) among categories with at least 3 measurable posts. This is an observed pattern, not proof of cause.".format(best['name'].title(),best['median_saves_1000'])})
    if coverage['saves']<len(posts):insights.append({'kind':'quality','title':'Saves are partially missing','body':'Save-rate comparisons only use posts with views and saves. Missing saves are not treated as zero.'})
    if coverage['avg_watch_sec']<3 or coverage['duration_sec']<3:insights.append({'kind':'opportunity','title':'Add viewing-depth metrics','body':'Import duration and average watch time on at least 3 posts to explore viewing depth by clip length.'})
    if len(posts)>0 and len(weekday_groups)<2:insights.append({'kind':'opportunity','title':'Posting patterns need more history','body':'Add publication dates to compare weekday cohorts. Lifetime views are not normalized to the same post age.'})
    if not insights and posts:insights.append({'kind':'note','title':'Use as directional evidence','body':'Correlations can suggest experiments. They do not establish causation or forecast viral reach.'})
    return {'summary':{'posts':len(posts),'views':known_sum('views'),'likes':known_sum('likes'), 'shares':known_sum('shares'), 'saves':known_sum('saves'),
                       'median_shares_1000':_mid(shares),'median_saves_1000':_mid([p['saves_per_1000_views'] for p in posts if p['saves_per_1000_views'] is not None]),'median_likes_100':_mid(likes),'median_interactions_100':_mid(interactions)},
            'coverage':coverage, 'demo_posts':sum(bool(p.get('is_demo')) for p in posts), 'posts':posts, 'content_types':grouped_types,'platforms':platform_groups,'durations':duration_groups,'weekdays':weekday_groups,
            'insights':insights, 'minimum_group_size':3, 'disclaimer':'Descriptive historical metrics only. No forecasts, causation, or invented counts.'}


def analyze_engagement(csv_or_frame) -> pd.DataFrame:
    """Compatibility convenience: accepts incomplete inputs and returns metrics."""
    rows,_=parse_csv(csv_or_frame)
    return pd.DataFrame([enrich(r) for r in rows])
