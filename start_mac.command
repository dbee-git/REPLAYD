#!/bin/bash
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then echo 'Install Python 3.9+ from python.org'; read -r; exit 1; fi
if ! command -v ffmpeg >/dev/null 2>&1; then echo 'FFmpeg is missing. Install Homebrew, then: brew install ffmpeg'; read -r; exit 1; fi
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
