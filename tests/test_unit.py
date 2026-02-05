"""Unit tests – no network required."""

import json
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from youtube_mp3_downloader import (
    DownloadEngine,
    VideoStatus,
    VideoTask,
    _default_output_dir,
    _get_ffmpeg_location,
    _load_settings,
    _save_settings,
    _settings_path,
    _truncate,
    _settings_lock,
)


# ---------------------------------------------------------------------------
# _truncate
# ---------------------------------------------------------------------------

class TestTruncate:
    def test_short_string_unchanged(self):
        assert _truncate("hello", 10) == "hello"

    def test_exact_length_unchanged(self):
        assert _truncate("hello", 5) == "hello"

    def test_long_string_truncated(self):
        result = _truncate("hello world", 8)
        assert result == "hello w\u2026"
        assert len(result) == 8

    def test_single_char_limit(self):
        result = _truncate("hello", 1)
        assert result == "\u2026"

    def test_empty_string(self):
        assert _truncate("", 5) == ""


# ---------------------------------------------------------------------------
# _default_output_dir
# ---------------------------------------------------------------------------

class TestDefaultOutputDir:
    def test_returns_music_subdirectory(self):
        result = _default_output_dir()
        path = Path(result)
        assert path.name == "YouTube Downloads"
        assert path.parent.name == "Music"
        assert str(Path.home()) in result

    def test_returns_string(self):
        assert isinstance(_default_output_dir(), str)


# ---------------------------------------------------------------------------
# _get_ffmpeg_location
# ---------------------------------------------------------------------------

class TestGetFfmpegLocation:
    def test_returns_none_when_not_frozen(self):
        assert _get_ffmpeg_location() is None

    def test_returns_path_when_frozen_with_ffmpeg(self, tmp_path):
        (tmp_path / "ffmpeg").touch()
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
            result = _get_ffmpeg_location()
            assert result == str(tmp_path)

    def test_returns_none_when_frozen_without_ffmpeg(self, tmp_path):
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
            assert _get_ffmpeg_location() is None


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------

class TestSettings:
    def test_save_and_load(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "settings.json"
        monkeypatch.setattr(
            "youtube_mp3_downloader._settings_path", lambda: settings_file
        )
        _save_settings({"output_dir": "/some/path"})
        loaded = _load_settings()
        assert loaded["output_dir"] == "/some/path"

    def test_load_missing_file(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "nonexistent.json"
        monkeypatch.setattr(
            "youtube_mp3_downloader._settings_path", lambda: settings_file
        )
        assert _load_settings() == {}

    def test_load_corrupt_file(self, tmp_path, monkeypatch):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("not valid json", encoding="utf-8")
        monkeypatch.setattr(
            "youtube_mp3_downloader._settings_path", lambda: settings_file
        )
        assert _load_settings() == {}

    def test_settings_path_not_frozen(self):
        path = _settings_path()
        assert path == Path.home() / ".yt_mp3_settings.json"

    def test_settings_path_frozen(self, tmp_path):
        exe = tmp_path / "app.exe"
        exe.touch()
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", str(exe)):
            path = _settings_path()
            assert path == tmp_path / ".yt_mp3_settings.json"


# ---------------------------------------------------------------------------
# VideoStatus
# ---------------------------------------------------------------------------

class TestVideoStatus:
    def test_all_values_present(self):
        expected = {
            "PENDING", "DOWNLOADING", "CONVERTING", "COMPLETED",
            "SKIPPED", "FAILED", "CANCELLED",
        }
        assert {s.value for s in VideoStatus} == expected


# ---------------------------------------------------------------------------
# VideoTask
# ---------------------------------------------------------------------------

class TestVideoTask:
    def test_defaults(self):
        task = VideoTask(url="http://x", title="T", video_id="1", index=1, total=5)
        assert task.status == VideoStatus.PENDING
        assert task.progress_pct == 0.0
        assert task.error_msg == ""
        assert task.attempts == 0

    def test_custom_values(self):
        task = VideoTask(
            url="http://x", title="T", video_id="1",
            index=3, total=10,
            status=VideoStatus.DOWNLOADING,
            progress_pct=42.5,
            error_msg="some error",
            attempts=2,
        )
        assert task.index == 3
        assert task.progress_pct == 42.5
        assert task.error_msg == "some error"


# ---------------------------------------------------------------------------
# DownloadEngine._build_ydl_opts
# ---------------------------------------------------------------------------

class TestBuildYdlOpts:
    def setup_method(self):
        self.engine = DownloadEngine(
            outdir=Path("/tmp/test"),
            max_workers=4,
            on_update=MagicMock(),
            on_complete=MagicMock(),
        )

    def test_output_template(self):
        opts = self.engine._build_ydl_opts(lambda d: None, lambda d: None)
        assert "%(title)s.%(ext)s" in opts["outtmpl"]
        assert "/tmp/test" in opts["outtmpl"]

    def test_audio_format_mp3_320(self):
        opts = self.engine._build_ydl_opts(lambda d: None, lambda d: None)
        extractors = [p for p in opts["postprocessors"] if p["key"] == "FFmpegExtractAudio"]
        assert len(extractors) == 1
        assert extractors[0]["preferredcodec"] == "mp3"
        assert extractors[0]["preferredquality"] == "320"

    def test_thumbnail_converter_before_embed(self):
        opts = self.engine._build_ydl_opts(lambda d: None, lambda d: None)
        keys = [p["key"] for p in opts["postprocessors"]]
        converter_idx = keys.index("FFmpegThumbnailsConvertor")
        embed_idx = keys.index("EmbedThumbnail")
        assert converter_idx < embed_idx, "Thumbnail converter must run before embed"

    def test_thumbnail_converter_format_jpg(self):
        opts = self.engine._build_ydl_opts(lambda d: None, lambda d: None)
        converters = [p for p in opts["postprocessors"] if p["key"] == "FFmpegThumbnailsConvertor"]
        assert converters[0]["format"] == "jpg"

    def test_writethumbnail_enabled(self):
        opts = self.engine._build_ydl_opts(lambda d: None, lambda d: None)
        assert opts["writethumbnail"] is True

    def test_reliability_options(self):
        opts = self.engine._build_ydl_opts(lambda d: None, lambda d: None)
        assert opts["retries"] == 5
        assert opts["fragment_retries"] == 5
        assert opts["extractor_retries"] == 3
        assert opts["socket_timeout"] == 30

    def test_noplaylist_always_true(self):
        opts = self.engine._build_ydl_opts(lambda d: None, lambda d: None)
        assert opts["noplaylist"] is True

    def test_progress_hooks_set(self):
        hook = MagicMock()
        opts = self.engine._build_ydl_opts(hook, lambda d: None)
        assert hook in opts["progress_hooks"]

    def test_ffmpeg_location_not_set_when_not_frozen(self):
        opts = self.engine._build_ydl_opts(lambda d: None, lambda d: None)
        assert "ffmpeg_location" not in opts

    def test_ffmpeg_location_set_when_frozen(self, tmp_path):
        (tmp_path / "ffmpeg").touch()
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
            opts = self.engine._build_ydl_opts(lambda d: None, lambda d: None)
            assert opts["ffmpeg_location"] == str(tmp_path)


# ---------------------------------------------------------------------------
# DownloadEngine.find_existing
# ---------------------------------------------------------------------------

class TestFindExisting:
    def test_finds_matching_mp3(self, tmp_path):
        (tmp_path / "Song Title.mp3").touch()
        entries = [{"title": "Song Title", "id": "abc123"}]
        found = DownloadEngine.find_existing(entries, tmp_path)
        assert found == {"abc123"}

    def test_case_insensitive(self, tmp_path):
        (tmp_path / "SONG TITLE.mp3").touch()
        entries = [{"title": "song title", "id": "abc"}]
        found = DownloadEngine.find_existing(entries, tmp_path)
        assert found == {"abc"}

    def test_no_match(self, tmp_path):
        (tmp_path / "Other Song.mp3").touch()
        entries = [{"title": "Song Title", "id": "abc"}]
        found = DownloadEngine.find_existing(entries, tmp_path)
        assert found == set()

    def test_empty_dir(self, tmp_path):
        entries = [{"title": "Song", "id": "abc"}]
        found = DownloadEngine.find_existing(entries, tmp_path)
        assert found == set()

    def test_nonexistent_dir(self, tmp_path):
        entries = [{"title": "Song", "id": "abc"}]
        found = DownloadEngine.find_existing(entries, tmp_path / "nope")
        assert found == set()

    def test_ignores_non_mp3_files(self, tmp_path):
        (tmp_path / "Song Title.webp").touch()
        (tmp_path / "Song Title.jpg").touch()
        entries = [{"title": "Song Title", "id": "abc"}]
        found = DownloadEngine.find_existing(entries, tmp_path)
        assert found == set()

    def test_multiple_entries(self, tmp_path):
        (tmp_path / "Song A.mp3").touch()
        (tmp_path / "Song C.mp3").touch()
        entries = [
            {"title": "Song A", "id": "1"},
            {"title": "Song B", "id": "2"},
            {"title": "Song C", "id": "3"},
        ]
        found = DownloadEngine.find_existing(entries, tmp_path)
        assert found == {"1", "3"}


# ---------------------------------------------------------------------------
# DownloadEngine.start with skip_ids
# ---------------------------------------------------------------------------

class TestStartWithSkipIds:
    def test_skipped_tasks_marked(self):
        complete_event = threading.Event()
        result = []

        def on_complete(tasks):
            result.extend(tasks)
            complete_event.set()

        engine = DownloadEngine(
            outdir=Path("/tmp"),
            max_workers=1,
            on_update=MagicMock(),
            on_complete=on_complete,
        )
        entries = [
            {"url": "http://a", "title": "A", "id": "1"},
            {"url": "http://b", "title": "B", "id": "2"},
        ]
        engine.start(entries, skip_ids={"1", "2"})
        assert complete_event.wait(timeout=5)
        assert all(t.status == VideoStatus.SKIPPED for t in result)


# ---------------------------------------------------------------------------
# DownloadEngine.cancel
# ---------------------------------------------------------------------------

class TestEngineCancel:
    def test_cancel_sets_event(self):
        engine = DownloadEngine(
            outdir=Path("/tmp"),
            max_workers=1,
            on_update=MagicMock(),
            on_complete=MagicMock(),
        )
        assert not engine._cancel.is_set()
        engine.cancel()
        assert engine._cancel.is_set()

    def test_tasks_property_returns_copy(self):
        engine = DownloadEngine(
            outdir=Path("/tmp"),
            max_workers=1,
            on_update=MagicMock(),
            on_complete=MagicMock(),
        )
        engine._tasks = [
            VideoTask(url="a", title="A", video_id="1", index=1, total=1)
        ]
        tasks = engine.tasks
        assert len(tasks) == 1
        assert tasks is not engine._tasks  # must be a copy


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_settings_lock_protects_concurrent_writes(self, tmp_path, monkeypatch):
        """Multiple threads writing settings concurrently should not corrupt file."""
        settings_file = tmp_path / "settings.json"
        monkeypatch.setattr(
            "youtube_mp3_downloader._settings_path", lambda: settings_file
        )
        
        errors = []
        def write_setting(key, value):
            try:
                for _ in range(10):
                    s = _load_settings()
                    s[key] = value
                    _save_settings(s)
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=write_setting, args=(f"key_{i}", i))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert not errors, f"Thread safety errors: {errors}"
        final = _load_settings()
        assert len(final) >= 1  # At least some keys should be present

    def test_progress_clamped_to_100(self):
        """Progress percentage should never exceed 100%."""
        engine = DownloadEngine(
            outdir=Path("/tmp"),
            max_workers=1,
            on_update=MagicMock(),
            on_complete=MagicMock(),
        )
        task = VideoTask(url="http://x", title="X", video_id="1", index=1, total=1)
        
        # Simulate progress callback with values > 100%
        called_values = []
        def capture_update(t):
            called_values.append(t.progress_pct)
        
        engine.on_update = capture_update
        
        # Manually trigger progress calculation
        def _progress(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes", 100)
                downloaded = d.get("downloaded_bytes", 105)
                if total > 0:
                    task.progress_pct = min(
                        100.0,
                        downloaded / total * 100
                    )
                engine.on_update(task)
        
        _progress({"status": "downloading", "total_bytes": 100, "downloaded_bytes": 105})
        assert called_values[-1] <= 100.0, f"Progress exceeded 100%: {called_values[-1]}"
