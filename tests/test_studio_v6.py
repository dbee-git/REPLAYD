"""Regressions for the creator's 10-minute edited-footage feedback."""
from pathlib import Path
import numpy as np

from replayd.core import propose_candidates, suggest_bounds
from replayd.web import app

ROOT=Path(__file__).resolve().parents[1]


def test_exact_five_seconds_before_audio_peak_eighteen_after():
    assert suggest_bounds(237, [], 606, "compilation") == (232, 255)
    assert suggest_bounds(237, [], 606, "full_match") == (231, 255)


def test_early_scene_cuts_dont_trim_goal_reaction():
    start, end=suggest_bounds(237,[225,229,232,238,240,245,247],606)
    assert 231 <= start <= 233
    assert end==255  # preserve 18s reaction when no late boundary


def test_late_scene_cut_can_align_end_and_no_unnecessary_pre_scene():
    start, end=suggest_bounds(237,[220,228,233,240,253,260],606)
    assert start == 233  # only four seconds before, never old unrelated scenes
    assert end == 253  # close cut, near the intended 18s after


def test_peak_candidate_uses_short_pre_and_long_post():
    times=np.arange(.25, 90, .5)
    audio=np.zeros(len(times))
    audio[np.argmin(abs(times-45.25))]=.9
    rows=propose_candidates(times,audio,[],90,min_audio_score=.2,max_candidates=10)
    assert len(rows)==1
    assert (rows[0].start,rows[0].end)==(40.25,63.25)


def test_last_seconds_clamped_and_no_invalid_window():
    assert suggest_bounds(3, [], 100)[0]==0
    s,e=suggest_bounds(99,[],100)
    assert 0<=s<e<=100


def test_page_lists_requested_candidate_limits_and_busts_old_js_cache():
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        page=client.get('/')
    assert page.status_code==200
    assert 'no-store' in page.headers.get('cache-control','')
    with TestClient(app) as client:
        asset=client.get('/static/app.js?v=0.6.0')
    assert asset.status_code==200
    assert 'no-store' in asset.headers.get('cache-control','')
    html=page.text
    for n in (5,10,20,30):
        assert f'<option value="{n}"' in html
    assert '<option value="40">40 moments' not in html
    assert '/static/app.js?v=0.6.0' in html
    assert '/static/styles.css?v=0.6.0' in html
    assert '<label for="clip-start">START / MM:SS</label>' in html
    assert 'type="text"' in html  # no number spinner for timecode


def test_legacy_data_migration_looks_at_previous_version():
    from replayd.web import DATA_CANDIDATES
    assert any(str(folder).endswith('REPLAYD_v0_5/.local_data') for folder in DATA_CANDIDATES)
