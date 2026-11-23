"""Input metadata checks before expensive analysis or video export."""
from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import subprocess


def probe_media(source: str | Path) -> dict:
    if shutil.which("ffprobe") is None:
        raise RuntimeError("FFprobe is required. Install FFmpeg.")
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(source)
    proc = subprocess.run([
        "ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(source)
    ], capture_output=True, text=True, check=True)
    raw = json.loads(proc.stdout)
    streams = raw.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not v:
        raise ValueError("The selected file has no video stream")
    try:
        duration = float(raw["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Could not read video duration") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Video duration must be positive")
    return {
        "duration_sec": duration,
        "width": int(v.get("width", 0)),
        "height": int(v.get("height", 0)),
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        "container": raw.get("format", {}).get("format_name", "unknown"),
    }
