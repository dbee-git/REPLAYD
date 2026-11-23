#!/usr/bin/env python3
"""Evaluate the unchanged REPLAYD detector against human-labeled football footage.

Run from the repository root:
 python scripts/evaluate_portfolio.py --annotations evaluation/labels.csv --media-root /path/to/authorized/videos --out evaluation/results

Source footage and private labels MUST NOT be committed to a public repository.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from replayd.core import analyze_video, propose_candidates
from replayd.evaluation import event_metrics, match_events

REQUIRED = {'video_id', 'video_file', 'event_time', 'event_type'}


def time_to_seconds(value: str) -> float:
    value = str(value).strip()
    if not value:
        raise ValueError('Empty timestamp')
    units = value.split(':')
    if len(units) > 3:
        raise ValueError(f'Invalid timestamp {value!r}')
    try:
        numbers = [float(part) for part in units]
    except ValueError as exc:
        raise ValueError(f'Invalid timestamp {value!r}') from exc
    if any(not math.isfinite(n) or n < 0 for n in numbers):
        raise ValueError('Timestamps must be nonnegative and finite')
    if len(numbers) > 1 and any(n >= 60 for n in numbers[1:]):
        raise ValueError('Minutes (when internal) and seconds must be below 60')
    return sum(n * 60**idx for idx, n in enumerate(reversed(numbers)))


def read_annotations(path: Path) -> dict[str, dict]:
    grouped = {}
    with path.open('r', encoding='utf-8-sig', newline='') as fp:
        reader = csv.DictReader(fp)
        if not reader.fieldnames or not REQUIRED.issubset(set(reader.fieldnames)):
            raise ValueError('Annotations CSV requires columns: ' + ', '.join(sorted(REQUIRED)))
        for line_number, row in enumerate(reader, 2):
            if not any((v or '').strip() for v in row.values()):
                continue
            video_id = (row['video_id'] or '').strip()
            video_file = (row['video_file'] or '').strip()
            event_type = (row['event_type'] or '').strip().lower()
            if not video_id or not video_file or not event_type:
                raise ValueError(f'Line {line_number}: video_id, video_file and event_type required')
            t = time_to_seconds(row['event_time'])
            if video_id not in grouped:
                grouped[video_id] = {'file': video_file, 'events': []}
            if grouped[video_id]['file'] != video_file:
                raise ValueError(f'Line {line_number}: same video_id has inconsistent file names')
            grouped[video_id]['events'].append({'time':t, 'type':event_type, 'notes':(row.get('notes') or '').strip()})
    if not grouped:
        raise ValueError('Annotations CSV has no labeled events. Record events before evaluation.')
    return grouped


def summary_for_candidates(candidates, labels, tolerance):
    points = [c.timestamp for c in candidates]
    targets = [event['time'] for event in labels]
    all_metrics = event_metrics(points, targets, tolerance)
    goal_points = [event['time'] for event in labels if event['type'] == 'goal']
    goal_hits = sum(any(abs(p - t) <= tolerance for p in points) for t in goal_points)
    clip_hits = sum(any(c.start <= t <= c.end for c in candidates) for t in targets)
    errors = [round(delta, 3) for _, _, delta in match_events(points, targets, tolerance)]
    return {
        **all_metrics,
        'goals_labeled':len(goal_points), 'goals_near_candidate':goal_hits,
        'events_inside_suggested_clips':clip_hits,
        'labels':len(targets), 'candidates':len(points),
        'mean_match_error_sec':round(sum(errors)/len(errors),3) if errors else None,
        'average_suggested_clip_sec':round(sum(c.end-c.start for c in candidates)/len(candidates),2) if candidates else None,
    }


def micro_average(rows, prefix):
    tp=sum(r[f'{prefix}_true_positives'] for r in rows)
    fp=sum(r[f'{prefix}_false_positives'] for r in rows)
    fn=sum(r[f'{prefix}_false_negatives'] for r in rows)
    precision=tp/(tp+fp) if tp+fp else 0.0
    recall=tp/(tp+fn) if tp+fn else 0.0
    f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
    goals=sum(r[f'{prefix}_goals_labeled'] for r in rows)
    hits=sum(r[f'{prefix}_goals_near_candidate'] for r in rows)
    return {
        'true_positives':tp,'false_positives':fp,'false_negatives':fn,
        'precision':round(precision,4),'recall':round(recall,4),'f1':round(f1,4),
        'goals_labeled':goals,'goals_near_candidate':hits,
        'goal_coverage':round(hits/goals,4) if goals else None,
        'events_inside_suggested_clips':sum(r[f'{prefix}_events_inside_suggested_clips'] for r in rows),
    }


def evaluate(annotations: Path, media_root: Path, out_dir: Path,
             threshold: float, max_candidates: int, tolerance: float, mode: str):
    if not (0.05 <= threshold <= 0.95):
        raise ValueError('Threshold must be 0.05–0.95')
    if not 1 <= max_candidates <= 30:
        raise ValueError('Max candidates must be 1–30')
    if tolerance <= 0 or not math.isfinite(tolerance):
        raise ValueError('Tolerance must be positive and finite')
    media_root=media_root.resolve()
    annotations_data=read_annotations(annotations)
    records=[]
    detailed=[]
    for video_id, record in annotations_data.items():
        path=(media_root/record['file']).resolve()
        if not path.is_relative_to(media_root):
            raise ValueError(f'Video file path escapes --media-root: {record["file"]}')
        if not path.is_file():
            raise FileNotFoundError(f'{video_id}: missing video at {path}')
        started=time.perf_counter()
        result=analyze_video(path, min_audio_score=threshold, max_candidates=max_candidates, mode=mode)
        duration=time.perf_counter()-started
        labels=record['events']
        for e in labels:
            if e['time'] > result['duration_sec']:
                raise ValueError(f'{video_id}: labeled event {e["time"]}s exceeds clip duration')
        # Proper audio-only ablation: same loudness features and selection budget,
        # but NO independent visual candidates and NO scene-cut fusion.
        signal=result['signals']
        audio_only=propose_candidates(
            signal['time_sec'].to_numpy(), signal['audio_score'].to_numpy(),
            [], result['duration_sec'], min_audio_score=threshold,
            min_gap_sec=9.0 if mode=='compilation' else 15.0,
            max_candidates=max_candidates, mode=mode)
        record_out={'video_id':video_id, 'video_file':record['file'],
                    'duration_sec':round(result['duration_sec'],2),
                    'analysis_elapsed_sec':round(duration,2),
                    'annotated_events':len(labels),
                    'annotated_goals':sum(e['type']=='goal' for e in labels)}
        for prefix,candidates in [('audiovisual',result['candidates']),('audio_only',audio_only)]:
            measurement=summary_for_candidates(candidates,labels,tolerance)
            record_out.update({f'{prefix}_{k}':v for k,v in measurement.items()})
            for candidate in candidates:
                detailed.append({'video_id':video_id,'model':prefix,
                                 'candidate_time_sec':candidate.timestamp,
                                 'suggested_start_sec':candidate.start,
                                 'suggested_end_sec':candidate.end,
                                 'score':candidate.fused_score,
                                 'audio_score':candidate.audio_score,
                                 'visual_score':candidate.visual_score,
                                 'evidence':candidate.evidence})
        records.append(record_out)
        print(f'{video_id}: {len(labels)} labels; audiovisual {record_out["audiovisual_true_positives"]} matches; '
              f'audio-only {record_out["audio_only_true_positives"]}; {duration:.1f}s processing')
    out_dir.mkdir(parents=True,exist_ok=True)
    result_summary={
        'evaluation_version':'REPLAYD-v1.0-portfolio',
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'annotation_file':annotations.name,
        'settings':{'threshold':threshold,'max_candidates':max_candidates,'tolerance_seconds':tolerance,'mode':mode},
        'footage_count':len(records),
        'labeled_events':sum(row['annotated_events'] for row in records),
        'labeled_goals':sum(row['annotated_goals'] for row in records),
        'analysis_elapsed_seconds':round(sum(row['analysis_elapsed_sec'] for row in records),2),
        'audiovisual':micro_average(records,'audiovisual'),
        'audio_only':micro_average(records,'audio_only'),
        'warning':'Heuristic candidate spotting, not verified semantic goal classification. Evaluate unseen footage; no predictions of social media engagement.',
    }
    with (out_dir/'per_video.csv').open('w',encoding='utf-8',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    with (out_dir/'candidates.csv').open('w',encoding='utf-8',newline='') as fp:
        writer=csv.DictWriter(fp,fieldnames=list(detailed[0]) if detailed else [
            'video_id','model','candidate_time_sec','suggested_start_sec',
            'suggested_end_sec','score','audio_score','visual_score','evidence'])
        writer.writeheader()
        writer.writerows(detailed)
    (out_dir/'summary.json').write_text(json.dumps(result_summary,indent=2)+'\n',encoding='utf-8')
    print('\nEvaluation results:', out_dir)
    for key in ('audiovisual','audio_only'):
        s=result_summary[key]
        print(f'{key}: precision {s["precision"]:.3f}, recall {s["recall"]:.3f}, F1 {s["f1"]:.3f}, goals near suggestions {s["goals_near_candidate"]}/{s["goals_labeled"]}')
    print('Note: do not use synthetic video to claim football event accuracy.')
    return result_summary


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--annotations',type=Path,required=True)
    parser.add_argument('--media-root',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path('evaluation/results'))
    parser.add_argument('--threshold',type=float,default=0.20)
    parser.add_argument('--max-candidates',type=int,default=10)
    parser.add_argument('--tolerance',type=float,default=5.0)
    parser.add_argument('--mode',choices=['compilation','full_match'],default='compilation')
    args=parser.parse_args()
    try:
        evaluate(args.annotations,args.media_root,args.out,args.threshold,args.max_candidates,args.tolerance,args.mode)
    except (ValueError,FileNotFoundError) as exc:
        parser.error(str(exc))


if __name__=='__main__':
    main()
