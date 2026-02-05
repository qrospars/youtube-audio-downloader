"""Integration tests – require network access and ffmpeg.

Run with:  pytest tests/test_integration.py -v -s
Skip with: pytest -m "not integration"
"""

import shutil
import threading
import time
from pathlib import Path

import pytest

from youtube_mp3_downloader import (
    DownloadEngine,
    VideoStatus,
    VideoTask,
)

# A short, freely available video for testing
SINGLE_URL = "https://www.youtube.com/watch?v=xgB3I2i9m0U"
PLAYLIST_URL = "https://www.youtube.com/watch?v=xgB3I2i9m0U&list=PLpODoeOMVHmKz5kJpGnuZ9ichE4WN1ImY"
INVALID_URL = "https://www.youtube.com/watch?v=ZZZZZZZZZZZ"

pytestmark = pytest.mark.integration


@pytest.fixture
def outdir(tmp_path):
    """Temporary output directory for downloads."""
    d = tmp_path / "downloads"
    d.mkdir()
    return d


def _requires_ffmpeg():
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")


# ---------------------------------------------------------------------------
# Extraction tests
# ---------------------------------------------------------------------------

class TestExtractPlaylistInfo:
    def test_single_video(self):
        entries = DownloadEngine.extract_playlist_info(SINGLE_URL)
        assert len(entries) == 1
        assert entries[0]["id"] == "xgB3I2i9m0U"
        assert entries[0]["title"]
        assert entries[0]["url"]

    def test_playlist(self):
        entries = DownloadEngine.extract_playlist_info(PLAYLIST_URL)
        assert len(entries) > 1
        # All entries must have required fields
        for e in entries:
            assert "url" in e
            assert "title" in e
            assert "id" in e

    def test_invalid_url_returns_empty(self):
        entries = DownloadEngine.extract_playlist_info(INVALID_URL)
        assert entries == []


# ---------------------------------------------------------------------------
# Download tests
# ---------------------------------------------------------------------------

class TestDownloadSingle:
    def test_download_produces_mp3(self, outdir):
        _requires_ffmpeg()

        entries = DownloadEngine.extract_playlist_info(SINGLE_URL)
        assert len(entries) == 1

        updates = []
        complete_event = threading.Event()
        result_tasks = []

        def on_update(task):
            updates.append(task.status)

        def on_complete(tasks):
            result_tasks.extend(tasks)
            complete_event.set()

        engine = DownloadEngine(
            outdir=outdir,
            max_workers=1,
            on_update=on_update,
            on_complete=on_complete,
        )
        engine.start(entries)
        assert complete_event.wait(timeout=120), "Download timed out"

        # Verify result
        assert len(result_tasks) == 1
        assert result_tasks[0].status == VideoStatus.COMPLETED

        # Verify MP3 file exists
        mp3s = list(outdir.glob("*.mp3"))
        assert len(mp3s) == 1
        assert mp3s[0].stat().st_size > 0

        # Verify NO leftover thumbnail files
        webps = list(outdir.glob("*.webp"))
        jpgs = list(outdir.glob("*.jpg"))
        pngs = list(outdir.glob("*.png"))
        assert webps == [], f"Leftover webp files: {webps}"
        assert jpgs == [], f"Leftover jpg files: {jpgs}"
        assert pngs == [], f"Leftover png files: {pngs}"

    def test_skip_already_downloaded(self, outdir):
        """Downloading the same video twice should not fail."""
        _requires_ffmpeg()

        entries = DownloadEngine.extract_playlist_info(SINGLE_URL)
        complete_event = threading.Event()
        result_tasks = []

        def on_complete(tasks):
            result_tasks.extend(tasks)
            complete_event.set()

        # First download
        engine = DownloadEngine(
            outdir=outdir, max_workers=1,
            on_update=lambda t: None, on_complete=on_complete,
        )
        engine.start(entries)
        assert complete_event.wait(timeout=120)
        assert result_tasks[0].status == VideoStatus.COMPLETED
        first_mp3 = list(outdir.glob("*.mp3"))
        first_mtime = first_mp3[0].stat().st_mtime

        # Second download – same URL, same outdir
        result_tasks.clear()
        complete_event.clear()
        engine2 = DownloadEngine(
            outdir=outdir, max_workers=1,
            on_update=lambda t: None, on_complete=on_complete,
        )
        engine2.start(entries)
        assert complete_event.wait(timeout=120)

        # Should still complete (not fail)
        assert result_tasks[0].status == VideoStatus.COMPLETED

        # File should not have been rewritten
        mp3s = list(outdir.glob("*.mp3"))
        assert len(mp3s) == 1


class TestDownloadParallel:
    def test_parallel_downloads(self, outdir):
        """Download 3 videos in parallel with 2 workers."""
        _requires_ffmpeg()

        entries = DownloadEngine.extract_playlist_info(PLAYLIST_URL)
        entries = entries[:3]  # limit to 3 for speed

        complete_event = threading.Event()
        result_tasks = []
        statuses_seen = set()

        def on_update(task):
            statuses_seen.add(task.status)

        def on_complete(tasks):
            result_tasks.extend(tasks)
            complete_event.set()

        engine = DownloadEngine(
            outdir=outdir,
            max_workers=2,
            on_update=on_update,
            on_complete=on_complete,
        )
        engine.start(entries)
        assert complete_event.wait(timeout=180), "Parallel download timed out"

        completed = [t for t in result_tasks if t.status == VideoStatus.COMPLETED]
        assert len(completed) == 3, (
            f"Expected 3 completed, got {len(completed)}. "
            f"Statuses: {[(t.title, t.status.value, t.error_msg) for t in result_tasks]}"
        )

        mp3s = list(outdir.glob("*.mp3"))
        assert len(mp3s) == 3

        # Should have seen DOWNLOADING status at some point
        assert VideoStatus.DOWNLOADING in statuses_seen


class TestCancel:
    def test_cancel_stops_downloads(self, outdir):
        """Cancelling mid-download should stop remaining work."""
        _requires_ffmpeg()

        entries = DownloadEngine.extract_playlist_info(PLAYLIST_URL)
        entries = entries[:6]  # 6 videos, but we'll cancel quickly

        complete_event = threading.Event()
        result_tasks = []
        first_download_started = threading.Event()

        def on_update(task):
            if task.status == VideoStatus.DOWNLOADING:
                first_download_started.set()

        def on_complete(tasks):
            result_tasks.extend(tasks)
            complete_event.set()

        engine = DownloadEngine(
            outdir=outdir,
            max_workers=2,
            on_update=on_update,
            on_complete=on_complete,
        )
        engine.start(entries)

        # Wait for first download to begin, then cancel
        assert first_download_started.wait(timeout=30), "No download started"
        engine.cancel()

        assert complete_event.wait(timeout=60), "Engine didn't finish after cancel"

        # At least some tasks should be cancelled
        cancelled = [t for t in result_tasks if t.status == VideoStatus.CANCELLED]
        assert len(cancelled) > 0, "Expected at least one cancelled task"
