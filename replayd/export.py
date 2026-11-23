"""Safe, local FFmpeg exports for creator-selected highlight boundaries.

The default vertical mode preserves the whole landscape frame with padding.
Center-crop is optional because blindly cropping may remove the ball/players.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


LAYOUTS = {
    "Original aspect ratio": None,
    "Portrait 9:16 — keep full frame": (
        "scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2,setsar=1"
    ),
    "Portrait 9:16 — center crop": (
        "scale=720:1280:force_original_aspect_ratio=increase,"
        "crop=720:1280,setsar=1"
    ),
}


def render_clip(
    source: str | Path,
    target: str | Path,
    start: float,
    end: float,
    layout: str = "Original aspect ratio",
) -> Path:
    """Render one clip using re-encoding for reliably accurate boundaries.

    `start` and `end` are source-video seconds, not relative offsets.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("FFmpeg is required. On macOS run: brew install ffmpeg")
    if layout not in LAYOUTS:
        raise ValueError("Unknown export layout")
    source, target = Path(source), Path(target)
    if not source.is_file():
        raise FileNotFoundError(source)
    if not (0 <= start < end):
        raise ValueError("Clip must have 0 <= start < end")
    if end - start < 1.0:
        raise ValueError("Clip must be at least one second long")
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-nostdin", "-y", "-hide_banner", "-v", "error",
        "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{end-start:.3f}",
        "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
    ]
    if LAYOUTS[layout] is not None:
        command += ["-vf", LAYOUTS[layout]]
    command += ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(target)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        target.unlink(missing_ok=True)
        raise RuntimeError("FFmpeg export failed: " + result.stderr[-1000:])
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError("Export did not create a nonempty video")
    return target
