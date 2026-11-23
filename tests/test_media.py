from pathlib import Path
import shutil
import subprocess

import pandas as pd
import pytest

from replayd.analytics import analyze_engagement
from replayd.creators import compare_content_types
from replayd.export import LAYOUTS, render_clip
from replayd.media import probe_media


def test_layouts_available():
    assert len(LAYOUTS) == 3
    assert "Portrait 9:16 — keep full frame" in LAYOUTS


def test_content_type_recommendations_need_three_posts():
    data = analyze_engagement(pd.DataFrame([
        dict(clip_id=f"post-{i}", content_type="goal" if i < 3 else "save", views=1000,
             likes=50, comments=5, shares=10, saves=15)
        for i in range(5)
    ]))
    result = compare_content_types(data, min_posts=3)
    assert result["content_type"].tolist() == ["goal"]
    assert result["posts"].tolist() == [3]


def test_negative_and_fractional_engagement_rejected():
    sample = pd.DataFrame([dict(clip_id="a", views=100.5, likes=0, comments=0, shares=0, saves=0)])
    with pytest.raises(ValueError, match="whole number"):
        analyze_engagement(sample)


def test_export_requires_valid_boundaries(tmp_path):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"fake")
    with pytest.raises(ValueError):
        render_clip(source, tmp_path / "out.mp4", start=5.0, end=4.0)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg required")
def test_real_ffmpeg_portrait_export(tmp_path):
    source = tmp_path / "test_landscape.mp4"
    proc = subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000",
        "-t", "2", "-c:v", "mpeg4", "-c:a", "aac", str(source)
    ], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    metadata = probe_media(source)
    assert metadata["width"] == 320 and metadata["height"] == 180
    assert metadata["has_audio"]
    out = render_clip(source, tmp_path / "portrait.mp4", 0, 1.5, "Portrait 9:16 — keep full frame")
    assert out.stat().st_size > 0
    info = probe_media(out)
    assert (info["width"], info["height"]) == (720, 1280)
    assert 1.3 < info["duration_sec"] < 1.8
