import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.resolve import resolve_source, is_url, hash_source

FIXTURE = Path(__file__).parent / "fixtures" / "sample_10s.mp4"


def test_is_url_recognizes_http_and_https():
    assert is_url("https://youtu.be/abc")
    assert is_url("http://example.com/v.mp4")


def test_is_url_rejects_paths():
    assert not is_url("/tmp/x.mp4")
    assert not is_url("./video.mp4")
    assert not is_url("video.mp4")


def test_hash_source_is_stable():
    assert hash_source("https://x") == hash_source("https://x")


def test_hash_source_differs_for_different_inputs():
    assert hash_source("a") != hash_source("b")


@pytest.mark.integration
def test_resolve_local_file_uses_ffprobe(tmp_path):
    meta = resolve_source(str(FIXTURE), focus_range=None)
    assert 9.5 < meta["duration_s"] < 10.5
    assert meta["title"]  # filename-derived
    assert meta["source"] == str(FIXTURE)
    assert meta["is_url"] is False


@patch("scripts.resolve.subprocess.run")
def test_resolve_url_calls_yt_dlp_dump_json(mock_run):
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({"title": "Lecture 3", "duration": 47.0, "id": "abc"}),
    )
    meta = resolve_source("https://youtu.be/abc", focus_range=None)
    assert meta["title"] == "Lecture 3"
    assert meta["duration_s"] == 47.0
    assert meta["is_url"] is True
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "yt-dlp"
    assert "-j" in cmd or "--dump-json" in cmd
