from pathlib import Path
import csv
import pytest
from replayd.evaluation import match_events, event_metrics
from scripts.evaluate_portfolio import read_annotations, time_to_seconds, summary_for_candidates
from replayd.core import ClipCandidate


def test_greedy_matching_can_miss_valid_second_pair():
    # Greedy local matching may produce 1 TP here; max-cardinality gives 2.
    matches=match_events([0,2],[1,-1.5],2)
    assert len(matches)==2
    assert event_metrics([0,2],[1,-1.5],2)['recall']==1.0


def test_simple_perfect_matching():
    m=event_metrics([10,45],[12,44],5)
    assert (m['true_positives'],m['false_positives'],m['false_negatives'])==(2,0,0)
    assert m['f1']==1.0


def test_metrics_do_not_allow_duplicate_match():
    m=event_metrics([10,10.1],[10],5)
    assert m['true_positives']==1
    assert m['false_positives']==1


@pytest.mark.parametrize('value,seconds',[
    ('90',90.0),('01:30',90.0),('03:45.25',225.25),('01:02:03',3723.0)])
def test_timecodes(value,seconds):
    assert time_to_seconds(value)==seconds


def test_bad_timecodes():
    for bad in ['03:60','-1','nope','01:04:79', 'nan']:
        with pytest.raises(ValueError):time_to_seconds(bad)


def test_read_annotations(tmp_path):
    fp=tmp_path/'labels.csv'
    fp.write_text('video_id,video_file,event_time,event_type,notes\nvid1,sample.mp4,01:30.5,goal,opening goal\n')
    labels=read_annotations(fp)
    assert labels['vid1']['events'][0]['time']==90.5
    assert labels['vid1']['events'][0]['type']=='goal'


def test_empty_annotations_rejected(tmp_path):
    fp=tmp_path/'labels.csv'
    fp.write_text('video_id,video_file,event_time,event_type,notes\n')
    with pytest.raises(ValueError,match='no labeled events'):read_annotations(fp)


def test_candidate_clip_coverage_and_goal_count():
    candidates=[ClipCandidate(timestamp=10,start=5,end=28,audio_score=.7,visual_score=.2,fused_score=.6,evidence='demo')]
    labels=[{'time':12,'type':'goal'},{'time':35,'type':'save'}]
    result=summary_for_candidates(candidates,labels,5)
    assert result['goals_labeled']==1
    assert result['goals_near_candidate']==1
    assert result['events_inside_suggested_clips']==1
    assert result['true_positives']==1
