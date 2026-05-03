import pytest
from pathlib import Path

from scripts.scenes import (
    apply_coverage_floor,
    apply_budget_cap,
    detect_scenes,
    Scene,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_10s.mp4"


def test_apply_coverage_floor_inserts_at_max_gap_intervals():
    """One detected boundary at t=5 in a 60s video; max_gap_s=45 → floor at t=50."""
    scenes = [Scene(t=0.0, score=1.0, kind="detected"), Scene(t=5.0, score=0.9, kind="detected")]
    out = apply_coverage_floor(scenes, duration_s=60.0, max_gap_s=45.0)
    floor_times = [s.t for s in out if s.kind == "floor"]
    assert floor_times == [50.0]


def test_apply_coverage_floor_inserts_multiple_for_long_static_run():
    """Gap of 200s with max_gap=45 should insert floors at 5+45=50, 95, 140, 185."""
    scenes = [Scene(t=5.0, score=1.0, kind="detected")]
    out = apply_coverage_floor(scenes, duration_s=205.0, max_gap_s=45.0)
    floor_times = sorted(s.t for s in out if s.kind == "floor")
    assert floor_times == [50.0, 95.0, 140.0, 185.0]


def test_apply_coverage_floor_no_op_when_gaps_under_threshold():
    scenes = [Scene(t=0.0, score=1.0, kind="detected"), Scene(t=10.0, score=1.0, kind="detected")]
    out = apply_coverage_floor(scenes, duration_s=20.0, max_gap_s=45.0)
    assert all(s.kind == "detected" for s in out)


def test_apply_budget_cap_drops_lowest_scoring_detected_first():
    scenes = [Scene(t=float(i), score=float(i), kind="detected") for i in range(10)]
    out = apply_budget_cap(scenes, max_frames=4)
    assert len(out) == 4
    kept_scores = sorted(s.score for s in out)
    assert kept_scores == [6.0, 7.0, 8.0, 9.0]


def test_apply_budget_cap_preserves_floor_boundaries():
    """Floor boundaries are coverage guarantees; should never be dropped."""
    scenes = [
        Scene(t=0.0, score=1.0, kind="detected"),
        Scene(t=1.0, score=0.5, kind="floor"),
        Scene(t=2.0, score=0.9, kind="detected"),
        Scene(t=3.0, score=0.4, kind="detected"),
    ]
    out = apply_budget_cap(scenes, max_frames=2)
    assert len(out) == 2
    assert any(s.kind == "floor" and s.t == 1.0 for s in out), "floor must be preserved"


def test_apply_budget_cap_returns_sorted_by_time():
    scenes = [Scene(t=5.0, score=0.9, kind="detected"), Scene(t=1.0, score=0.8, kind="detected")]
    out = apply_budget_cap(scenes, max_frames=10)
    assert [s.t for s in out] == [1.0, 5.0]


@pytest.mark.integration
def test_detect_scenes_finds_known_cuts_in_fixture():
    """sample_10s.mp4 has hard cuts at t=3 and t=6 (red→white→blue;
    red and green share luma so the fixture uses white for the middle)."""
    scenes = detect_scenes(FIXTURE, threshold=0.30)
    detected = [s for s in scenes if s.kind == "detected"]
    times = [round(s.t, 1) for s in detected]
    # t=0 always present; the two real cuts at ~3.0 and ~6.0
    assert any(2.8 <= t <= 3.2 for t in times), f"missing cut near 3s; got {times}"
    assert any(5.8 <= t <= 6.2 for t in times), f"missing cut near 6s; got {times}"
