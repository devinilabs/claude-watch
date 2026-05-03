import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "sample_10s.mp4"


@pytest.mark.integration
def test_watch_end_to_end_on_local_fixture(tmp_path):
    """`scripts/watch.py <fixture> --no-whisper --out-dir <tmp>` runs the full pipeline."""
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "watch.py"),
            str(FIXTURE),
            "--no-whisper",
            "--out-dir", str(tmp_path),
        ],
        capture_output=True, text=True, check=False, cwd=str(ROOT),
    )
    assert proc.returncode == 0, f"watch.py failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"

    # Library dir created
    library_dirs = list(tmp_path.glob("*"))
    assert len(library_dirs) == 1, f"expected one library dir, got {library_dirs}"
    lib = library_dirs[0]

    # Manifest exists and has the right shape
    manifest = json.loads((lib / "manifest.json").read_text())
    assert manifest["meta"]["title"]
    assert manifest["transcript_path"]
    # Should have detected at least t=0 anchor + the two cuts at t≈3 and t≈6
    assert len(manifest["frames"]) >= 3

    # All frame files exist
    for frame in manifest["frames"]:
        assert (lib / frame["path"]).exists()

    # Stdout should contain the structured manifest block
    assert "=== claude-watch manifest ===" in proc.stdout
    assert "library_dir:" in proc.stdout
