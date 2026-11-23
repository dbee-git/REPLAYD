"""Regression tests based on creator reports: low-audio edited footage, long trims, save-first analytics."""
import numpy as np
from replayd.core import propose_candidates, suggest_bounds, audio_scores
from replayd.analytics import dashboard


def test_visual_candidates_survive_when_audio_threshold_is_not_met():
    times=np.arange(0.25, 120, 0.5)
    silent_strength=np.zeros(len(times))
    # Three different edited sequences with multiple scene cuts but no audio peaks.
    result=propose_candidates(times,silent_strength,[20,22,24,60,62,64,100,103,105],120,
                              min_audio_score=0.8,min_gap_sec=8,max_candidates=24)
    assert any(18 <= p.timestamp <= 26 for p in result)
    assert any(58 <= p.timestamp <= 66 for p in result)
    assert any(98 <= p.timestamp <= 107 for p in result)
    assert all('Visual-only' in p.evidence for p in result)


def test_scene_aware_boundaries_are_short_and_valid():
    start,end=suggest_bounds(200,[190,194,208,212],600,'compilation')
    assert start < 200 < end
    assert (end-start) < 30
    assert start==194
    # Preserve the reaction instead of snapping to an early post-goal replay cut.
    assert end==218
    a,b=suggest_bounds(3,[],600,'compilation')
    assert 0 <= a < 3 < b < 30
    a,b=suggest_bounds(599,[],600,'compilation')
    assert 0 <= a < b <= 600


def test_increased_candidate_limit_keeps_distinct_edited_sequences():
    times=np.arange(0.25, 600, .5)
    audio=np.zeros(len(times))
    cuts=[x for t in range(10,580,22) for x in (t,t+1.5,t+3)]
    rows=propose_candidates(times,audio,cuts,600,min_audio_score=.95,min_gap_sec=8,max_candidates=24)
    assert len(rows)>12
    assert len(rows)<=24
    assert all(0<=row.start<row.end<=600 for row in rows)


def test_static_audio_does_not_create_phantom_audio_event():
    audio=np.full(16000*20,.05,dtype=np.float32)
    times,score,_=audio_scores(audio,16000)
    assert np.max(score)<.01


def test_save_rate_summary_handles_missing_data():
    rows=[{'clip_id':'goal1','views':1000,'saves':50,'shares':None,'content_type':'goal'},
          {'clip_id':'goal2','views':2000,'saves':None,'shares':10,'content_type':'goal'}]
    d=dashboard(rows)
    assert d['summary']['median_saves_1000']==50
    assert d['summary']['median_shares_1000']==5
    assert d['coverage']['saves']==1
