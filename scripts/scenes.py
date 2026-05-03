"""Scene-change detection (ffmpeg) + coverage floor + budget cap."""
from __future__ import annotations

import re
import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path

# `t` = seconds from start of clip. `score` = ffmpeg scene score (0..1).
# `kind` = "detected" (real cut) or "floor" (synthetic coverage boundary).
@dataclass(frozen=True)
class Scene:
    t: float
    score: float
    kind: str  # "detected" | "floor"


_SHOWINFO_RX = re.compile(r"pts_time:([\d.]+).*?scene:([\d.]+)", re.DOTALL)
# ffmpeg ≥ 7 emits scene score via metadata=print as lavfi.scene_score= on the line
# immediately after the pts_time: line; this regex matches that pair across newlines.
_METADATA_RX = re.compile(
    r"pts_time:([\d.]+)[^\n]*\n[^\n]*lavfi\.scene_score=([\d.]+)", re.MULTILINE
)


def detect_scenes(video: Path, threshold: float = 0.30) -> list[Scene]:
    """Run ffmpeg scene-detect filter, parse pts_time + scene scores from stderr.

    Always emits a synthetic Scene at t=0 (kind="detected", score=1.0) so the first
    section of the video is always represented even when ffmpeg's first reported cut
    is several seconds in.

    On non-zero ffmpeg exit, emits a warning but still returns the t=0 anchor; this
    lets the caller distinguish "video has no cuts" from "ffmpeg failed to run".
    """
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i", str(video),
        "-vf", f"select='gt(scene,{threshold})',showinfo,metadata=print",
        "-f", "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        warnings.warn(
            f"ffmpeg exited {proc.returncode} for {video}; scene list may be empty. "
            f"stderr tail: {proc.stderr[-200:]!r}",
            RuntimeWarning,
            stacklevel=2,
        )
    out = [Scene(t=0.0, score=1.0, kind="detected")]

    # Try the older inline format first (single-line pts_time + scene:).
    found: list[tuple[float, float]] = []
    for line in proc.stderr.splitlines():
        if "scene:" not in line or "pts_time:" not in line:
            continue
        m = _SHOWINFO_RX.search(line)
        if m:
            found.append((float(m.group(1)), float(m.group(2))))

    # Fall back to the newer two-line metadata=print format.
    if not found:
        for m in _METADATA_RX.finditer(proc.stderr):
            found.append((float(m.group(1)), float(m.group(2))))

    for t, score in found:
        if t > 0.0:  # skip exactly t=0.0 to avoid duplicating the synthetic anchor
            out.append(Scene(t=t, score=score, kind="detected"))
    out.sort(key=lambda s: s.t)
    return out


def apply_coverage_floor(
    scenes: list[Scene], duration_s: float, max_gap_s: float
) -> list[Scene]:
    """Insert synthetic floor boundaries every `max_gap_s` across long static gaps.

    Uses end-of-video as the right edge so a single boundary at t=5 in a 60s video
    with max_gap=45 yields one floor at t=50.
    """
    if not scenes:
        return [Scene(t=0.0, score=0.0, kind="floor")]
    sorted_scenes = sorted(scenes, key=lambda s: s.t)
    out: list[Scene] = []
    edges = [s.t for s in sorted_scenes] + [duration_s]
    for i, s in enumerate(sorted_scenes):
        out.append(s)
        next_edge = edges[i + 1]
        gap = next_edge - s.t
        if gap > max_gap_s:
            t = s.t + max_gap_s
            while t < next_edge:
                out.append(Scene(t=t, score=0.0, kind="floor"))
                t += max_gap_s
    out.sort(key=lambda s: s.t)
    return out


def apply_budget_cap(scenes: list[Scene], max_frames: int) -> list[Scene]:
    """Cap the scene list to roughly `max_frames` by dropping lowest-scoring `detected` scenes.

    Floor boundaries are always preserved (they're coverage guarantees). When the
    number of floor scenes alone exceeds `max_frames`, the cap becomes soft: all
    floors are returned and the result will exceed `max_frames`. Coverage trumps cap.

    Result is sorted by time.
    """
    if len(scenes) <= max_frames:
        return sorted(scenes, key=lambda s: s.t)
    floors = [s for s in scenes if s.kind == "floor"]
    detected = [s for s in scenes if s.kind == "detected"]
    keep_n = max_frames - len(floors)
    if keep_n <= 0:
        # Pathological: more floors than budget. Keep all floors anyway —
        # coverage trumps the cap.
        return sorted(floors, key=lambda s: s.t)
    detected.sort(key=lambda s: s.score, reverse=True)
    kept = floors + detected[:keep_n]
    kept.sort(key=lambda s: s.t)
    return kept
