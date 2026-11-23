from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import math
import shutil
import subprocess
import tempfile
import wave

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ClipCandidate:
    timestamp: float
    start: float
    end: float
    audio_score: float
    visual_score: float
    fused_score: float
    evidence: str


def require_ffmpeg() -> None:
    for exe in ("ffmpeg", "ffprobe"):
        if shutil.which(exe) is None:
            raise RuntimeError(f"{exe} not found. Install FFmpeg and add it to PATH.")


def probe_duration(video: str | Path) -> float:
    require_ffmpeg()
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    duration = float(json.loads(result.stdout)["format"]["duration"])
    if not np.isfinite(duration) or duration <= 0:
        raise ValueError("Could not establish a positive video duration")
    return duration


def _extract_audio(video: Path, out_wav: Path) -> None:
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(out_wav)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("Could not extract audio. This MVP requires a video with an audio track. " + result.stderr[-400:])


def _load_audio(wav_path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(wav_path), "rb") as handle:
        sr = handle.getframerate()
        if handle.getsampwidth() != 2 or handle.getnchannels() != 1:
            raise ValueError("Expected 16-bit mono PCM audio")
        audio = np.frombuffer(handle.readframes(handle.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    return audio, sr


def audio_scores(audio: np.ndarray, sr: int, interval: float = 0.5) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Combine instantaneous surges and sustained loudness above the local baseline.

    These are *sound activity* measures, not semantic recognition of goals or cheers.
    """
    n = max(1, round(sr * interval))
    count = len(audio) // n
    if count == 0:
        raise ValueError("Audio too short to analyse")
    blocks = audio[:count*n].reshape(count, n)
    rms = np.sqrt(np.mean(blocks.astype(np.float64)**2, axis=1))
    db = 20.0 * np.log10(np.maximum(rms, 1e-7))
    series = pd.Series(db)
    local_baseline = series.rolling(window=max(5, int(21/interval) | 1), center=True, min_periods=1).median().to_numpy()
    surge = np.clip((np.maximum(0, db - local_baseline) - 2.0) / 14.0, 0, 1)
    surge = pd.Series(surge).rolling(window=3, center=True, min_periods=1).mean().to_numpy()
    # A goal call can be sustained rather than a single spike. Compare a short
    # moving average against a longer baseline to retain that signal.
    fast = series.rolling(window=max(3, int(4/interval) | 1), center=True, min_periods=1).mean().to_numpy()
    slow = series.rolling(window=max(15, int(45/interval) | 1), center=True, min_periods=1).median().to_numpy()
    sustained = np.clip((fast - slow - 1.0)/11.0, 0, 1)
    strength = np.clip(np.maximum(surge, 0.8*sustained), 0, 1)
    times = np.arange(count, dtype=float) * interval + interval/2
    return times, strength, db


def visual_cut_times(video: str | Path, duration: float, fps: float = 2.0) -> list[float]:
    """Detect likely shot transitions at 2 fps (not football event recognition)."""
    w, h = 160, 90
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={w}:{h},format=gray", "-an", "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    previous = None
    cuts = []
    changes = []
    idx = 0
    while True:
        raw = process.stdout.read(w*h)
        if len(raw) != w*h:
            break
        frame = np.frombuffer(raw, dtype=np.uint8)
        if previous is not None:
            change = float(np.mean(np.abs(frame.astype(np.int16)-previous.astype(np.int16))) / 255.0)
            local_background = float(np.median(changes[-12:])) if changes else 0.0
            if change >= 0.16 and change > local_background*1.6 + 0.012:
                t = idx/fps
                if t <= duration and (not cuts or t-cuts[-1]>=0.8):
                    cuts.append(round(t, 2))
            changes.append(change)
        previous = frame.copy()
        idx += 1
    process.stdout.close()
    stderr = process.stderr.read().decode(errors="ignore") if process.stderr else ""
    if process.wait() != 0:
        raise RuntimeError("Visual sampling failed: " + stderr[-400:])
    return cuts


def suggest_bounds(timestamp: float, cuts: list[float], duration: float,
                   mode: str = "compilation", pre_seconds: float | None = None,
                   post_seconds: float = 18.0) -> tuple[float, float]:
    """Propose an editable clip around a candidate, avoiding long pre-surge buildup.

    Start about five seconds before the candidate (six for continuous matches),
    and preserve approximately 18 seconds after it. Only snap to *nearby*
    scene cuts so distant transitions cannot pull the start backwards or
    end the moment prematurely. These are editing hints, not goal boundaries.
    """
    if mode not in ("compilation", "full_match"):
        raise ValueError("Unknown footage mode")
    if not math.isfinite(timestamp) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Expected finite timestamp and positive duration")
    pre = float(pre_seconds) if pre_seconds is not None else (5.0 if mode == "compilation" else 6.0)
    post = float(post_seconds)
    if not (4.0 <= pre <= 6.0) or not (post > 0 and math.isfinite(post)):
        raise ValueError("Pre-roll must be 4–6 seconds and post-roll must be positive")
    t = min(max(0.0, timestamp), duration)
    target_start = max(0.0, t - pre)
    target_end = min(duration, t + post)

    # Never seek backwards into a different preceding scene by more than 6 s.
    before = [c for c in cuts if max(0.0, t - 6.0) <= c <= t - 4.0]
    # Keep the reaction, replay or commentary after the peak. A camera cut
    # immediately after a goal is *not* necessarily the end of the moment.
    after = [c for c in cuts if t + max(12.0, post - 3.0) <= c <= t + post + 2.0 and c <= duration]
    start = min(before, key=lambda c: abs(c - target_start)) if before else target_start
    end = min(after, key=lambda c: abs(c - target_end)) if after else target_end
    return round(start, 2), round(max(start + min(1.0, duration - start), end), 2)


def propose_candidates(
    times: np.ndarray, strengths: np.ndarray, cuts: list[float], duration: float,
    min_audio_score: float = 0.32, min_gap_sec: float = 9.0, max_candidates: int = 10,
    pre_seconds: float | None = None, post_seconds: float = 18.0,
    mode: str = "compilation",
) -> list[ClipCandidate]:
    """Audio peaks PLUS independent visual-cut clusters, ranked with minimum spacing.

    Visual-only proposals are intentionally shown as review suggestions, never
    assigned a football event label. Footage can yield false positives.
    """
    if len(times) != len(strengths):
        raise ValueError("Audio time and score arrays differ in length")
    if not len(times):
        return []
    if mode not in ("compilation", "full_match"):
        raise ValueError("Unknown footage mode")
    times=np.asarray(times, dtype=float)
    strengths=np.asarray(strengths, dtype=float)
    cuts=sorted(float(c) for c in cuts if 0 <= c <= duration)
    proposals=[]

    def add(t: float, s: float, source: str):
        if not (0 <= t <= duration):
            return
        cut_count = sum(abs(t-c)<=6.0 for c in cuts)
        visual = min(1.0,cut_count/3.0)
        # Visual-only segments can rank even when audio has no distinct peak.
        fused = min(1.0, 0.65*s+0.35*visual+(0.07 if source=='visual' and cut_count>=2 else 0.0))
        if source=='audio':
            evidence=f"Audio activity; {cut_count} nearby shot transitions"
        else:
            evidence=f"Visual-only suggestion; {cut_count} nearby shot transitions (verify manually)"
        start,end=suggest_bounds(t,cuts,duration,mode, pre_seconds=pre_seconds, post_seconds=post_seconds)
        proposals.append(ClipCandidate(round(t,2),start,end,round(float(s),3),round(visual,3),round(fused,3),evidence))

    # 1. Local audio maxima, without requiring frame cuts.
    for i,(t,s) in enumerate(zip(times,strengths)):
        s=float(s)
        if s < min_audio_score:
            continue
        left=float(strengths[i-1]) if i else -1
        right=float(strengths[i+1]) if i+1<len(strengths) else -1
        if s>=left and s>=right:
            add(float(t),s,'audio')

    # 2. Scene-change clusters independent of the loudness threshold.
    # Repeated cut clusters often accompany replays and celebrations, though
    # they can also be ordinary edits; creators must review these suggestions.
    for cut in cuts:
        nearby=[c for c in cuts if abs(c-cut)<=6.0]
        if len(nearby)<2:
            continue
        t=float(np.median(nearby))
        indexes=np.flatnonzero(np.abs(times-t)<=4.0)
        if len(indexes):
            best_idx=indexes[np.argmax(strengths[indexes])]
            s=float(strengths[best_idx])
            if s>=min_audio_score*0.7:
                t=float(times[best_idx])
        else:
            s=0.0
        add(t,s,'visual')

    selected=[]
    for cand in sorted(proposals,key=lambda item:item.fused_score,reverse=True):
        if all(abs(cand.timestamp-other.timestamp)>=min_gap_sec for other in selected):
            selected.append(cand)
        if len(selected)>=max_candidates:
            break
    return sorted(selected,key=lambda item:item.timestamp)


def analyze_video(video: str | Path, min_audio_score: float = 0.25, max_candidates: int = 10, mode: str = "compilation") -> dict:
    video = Path(video).resolve()
    if not video.is_file():
        raise FileNotFoundError(video)
    duration = probe_duration(video)
    with tempfile.TemporaryDirectory(prefix="replayd_") as workdir:
        audio_path = Path(workdir) / "audio.wav"
        _extract_audio(video, audio_path)
        audio, sr = _load_audio(audio_path)
        times, strengths, db = audio_scores(audio, sr)
    cuts = visual_cut_times(video, duration)
    candidates = propose_candidates(times, strengths, cuts, duration, min_audio_score=min_audio_score,
                                    min_gap_sec=9.0 if mode=='compilation' else 15.0,
                                    max_candidates=max_candidates,mode=mode)
    signals = pd.DataFrame({"time_sec":times,"audio_score":strengths,"loudness_dbfs":db})
    return {"duration_sec":duration,"candidates":candidates,"signals":signals,"cuts":cuts,"mode":mode}


def create_clips(video: str | Path, candidates: list[ClipCandidate], output_dir: str | Path) -> list[Path]:
    require_ffmpeg()
    video = Path(video)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, cand in enumerate(candidates, 1):
        if cand.end <= cand.start:
            continue
        path = output_dir / f"replayd_{index:02d}_{int(cand.timestamp)}s.mp4"
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", str(cand.start), "-i", str(video),
               "-t", str(cand.end-cand.start), "-map", "0:v:0", "-map", "0:a?",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
               "-c:a", "aac", "-movflags", "+faststart", str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("Clip render failed: " + result.stderr[-500:])
        paths.append(path)
    manifest = [asdict(cand) for cand in candidates]
    (output_dir / "candidates.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    pd.DataFrame(manifest).to_csv(output_dir / "candidates.csv", index=False)
    return paths
