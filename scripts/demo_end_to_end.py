#!/usr/bin/env python3
"""Demonstrate actual REPLAYD analysis and MP4 rendering on synthetic fixture.

No external match rights, social APIs or paid keys required.
Run from the repository root: python scripts/demo_end_to_end.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replayd.core import analyze_video
from replayd.export import render_clip

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=Path('demo_output'))
    args=parser.parse_args()
    source=ROOT/'data/DEMO_synthetic.mp4'
    output=args.output_dir
    output.mkdir(parents=True,exist_ok=True)
    result=analyze_video(source,min_audio_score=.20,max_candidates=10,mode='compilation')
    candidates=result['candidates']
    if not candidates:
        raise RuntimeError('Synthetic fixture returned zero candidates: regression')
    chosen=candidates[0]
    target=output/'REPLAYD_synthetic_clip_9x16.mp4'
    render_clip(source,target,chosen.start,chosen.end,'Portrait 9:16 — keep full frame')
    summary={
        'source_file':source.name,'synthetic_demo':True,
        'duration_seconds':result['duration_sec'],
        'candidate_count':len(candidates),
        'selected_candidate_time_seconds':chosen.timestamp,
        'suggested_start_seconds':chosen.start,
        'suggested_end_seconds':chosen.end,
        'clip_file':target.name,
        'disclaimer':'Synthetic signals demonstrate working video processing and clipping, NOT football goal recognition or model accuracy.'
    }
    (output/'synthetic_demo_manifest.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print('Rendered:',target.resolve())
    print('Candidates:',len(candidates),'| selected time:',chosen.timestamp,'s')
    print(summary['disclaimer'])


if __name__=='__main__':main()
