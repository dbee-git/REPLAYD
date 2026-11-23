"""Measure whether suggestions are near known goal timestamps (not goal recognition).

Example:
  python scripts/check_goal_coverage.py /path/to/match.mp4 02:12 05:38 09:10
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from replayd.core import analyze_video


def parse_timecode(value):
    parts=value.split(':')
    if len(parts) not in (2,3):
        raise argparse.ArgumentTypeError('Use MM:SS or HH:MM:SS')
    if not re.fullmatch(r'\d+(?::\d{1,2}){1,2}',value):
        raise argparse.ArgumentTypeError('Use MM:SS or HH:MM:SS')
    numbers=list(map(int,parts))
    if numbers[-1]>=60 or (len(parts)==3 and numbers[-2]>=60):
        raise argparse.ArgumentTypeError('Seconds and intermediate minutes must be below 60')
    return numbers[0]*3600+numbers[1]*60+numbers[2] if len(parts)==3 else numbers[0]*60+numbers[1]


def main():
    parser=argparse.ArgumentParser(description='Check REPLAYD proposal coverage of known goal timestamps')
    parser.add_argument('video',type=Path)
    parser.add_argument('goals',nargs='+',type=parse_timecode,help='Known goals as MM:SS (relative to the source video, not match clock)')
    parser.add_argument('--threshold',type=float,default=.20)
    parser.add_argument('--tolerance',type=float,default=10.0)
    parser.add_argument('--mode',choices=['compilation','full_match'],default='compilation')
    args=parser.parse_args()
    if not 0.05<=args.threshold<=0.95:parser.error('Threshold must be between 0.05 and 0.95')
    if args.tolerance<=0:parser.error('Tolerance must be positive')
    result=analyze_video(args.video,args.threshold,30,args.mode)
    predictions=[p.timestamp for p in result['candidates']]
    found=sum(any(abs(goal-p)<=args.tolerance for p in predictions) for goal in args.goals)
    print('Footage:',args.video.name,'|',round(result['duration_sec'],1),'seconds')
    print('Shot transitions:',len(result['cuts']),'| candidates:',len(predictions))
    print('Candidates:',', '.join(f'{p/60:05.2f}m' for p in predictions) or '(none)')
    print(f'KNOWN GOALS NEAR A SUGGESTION: {found} / {len(args.goals)} within ±{args.tolerance:g}s')
    print('Caution: this is coverage of labeled goals, NOT verified goal classification or precision.')

if __name__=='__main__':main()
