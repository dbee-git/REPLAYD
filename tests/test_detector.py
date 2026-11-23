import numpy as np
import pandas as pd
import pytest

from replayd.core import audio_scores, propose_candidates
from replayd.analytics import analyze_engagement
from replayd.evaluation import event_metrics


def test_peak_detected_at_expected_time():
    sr = 16000
    audio = np.full(sr * 50, 0.003, dtype=np.float32)
    # Lower and higher amplitude constant sections simulate a sudden audio surge.
    audio[30*sr:33*sr] = 0.10
    times, scores, _ = audio_scores(audio, sr)
    peaks = propose_candidates(times, scores, [], 50, min_audio_score=0.30)
    assert any(29 <= c.timestamp <= 34 for c in peaks)


def test_no_peak_from_constant_audio():
    sr = 16000
    audio = np.full(sr * 12, 0.01, dtype=np.float32)
    times, scores, _ = audio_scores(audio, sr)
    assert propose_candidates(times, scores, [], 12) == []


def test_visual_evidence_changes_ranking():
    t = np.array([1., 2., 3., 4., 5.])
    s = np.array([0., 0., 0.7, 0., 0.])
    base = propose_candidates(t, s, [], 10, min_audio_score=.3)[0]
    fused = propose_candidates(t, s, [2., 3., 4.], 10, min_audio_score=.3)[0]
    assert fused.fused_score > base.fused_score


def test_event_matching_is_one_to_one():
    results = event_metrics([100, 101, 250], [100.4, 300], 5)
    assert (results["true_positives"], results["false_positives"], results["false_negatives"]) == (1, 2, 1)


def test_engagement_is_descriptive():
    df = pd.DataFrame([dict(clip_id="a", views=100, likes=10, comments=5, shares=2, saves=3)])
    result = analyze_engagement(df)
    assert result.iloc[0]["interactions_per_100_views"] == 20
    assert result.iloc[0]["shares_per_1000_views"] == 20


def test_missing_engagement_fields_are_optional():
    result=analyze_engagement(pd.DataFrame([{"views": 10}]))
    assert result.iloc[0]["views"] == 10
    assert pd.isna(result.iloc[0]["shares_per_1000_views"])
