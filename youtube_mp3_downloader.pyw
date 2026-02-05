"""
youtube_mp3_downloader.pyw – Tkinter GUI to download YouTube videos or
playlists as 320 kbps MP3 with embedded metadata and thumbnail art.

Features:
  - Parallel downloads via thread pool
  - Per-video retry with exponential backoff
  - Real-time progress bar and per-video status
  - Cancel support
  - Skip already-downloaded videos
  - Remembers output folder between sessions
  - Confirmation dialog for playlists
  - Portable: works in PyInstaller frozen builds
"""

import json
import sys
import shutil
import threading
import time
import concurrent.futures
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from queue import Queue, Empty
from typing import Optional, Callable

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# Global lock for thread-safe settings access
_settings_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_ffmpeg_location() -> Optional[str]:
    """Return the directory containing ffmpeg in a PyInstaller bundle, or None."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
        for name in ("ffmpeg.exe", "ffmpeg"):
            if (base / name).exists():
                return str(base)
    return None


def _default_output_dir() -> str:
    return str(Path.home() / "Music" / "YouTube Downloads")


def _settings_path() -> Path:
    """Return path to the persistent settings file."""
    if getattr(sys, "frozen", False):
        # Frozen build: store settings next to the executable
        return Path(sys.executable).parent / ".yt_mp3_settings.json"
    return Path.home() / ".yt_mp3_settings.json"


def _load_settings() -> dict:
    with _settings_lock:
        path = _settings_path()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return {}


def _save_settings(settings: dict) -> None:
    with _settings_lock:
        try:
            _settings_path().write_text(
                json.dumps(settings, indent=2), encoding="utf-8"
            )
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Download data types
# ---------------------------------------------------------------------------

class VideoStatus(Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    POSTPROCESSING = "CONVERTING"
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class VideoTask:
    url: str
    title: str
    video_id: str
    index: int          # 1-based
    total: int
    status: VideoStatus = VideoStatus.PENDING
    progress_pct: float = 0.0
    error_msg: str = ""
    attempts: int = 0


# ---------------------------------------------------------------------------
# Download engine
# ---------------------------------------------------------------------------

class DownloadEngine:
    MAX_RETRIES = 3
    BACKOFF_BASE = 2  # seconds

    def __init__(
        self,
        outdir: Path,
        max_workers: int,
        on_update: Callable[[VideoTask], None],
        on_complete: Callable[[list[VideoTask]], None],
    ):
        self.outdir = outdir
        self.max_workers = max_workers
        self.on_update = on_update
        self.on_complete = on_complete
        self._cancel = threading.Event()
        self._tasks: list[VideoTask] = []

    # -- public API ----------------------------------------------------------

    @staticmethod
    def extract_playlist_info(url: str) -> list[dict]:
        """Fetch video list without downloading.  Works for single videos too."""
        opts: dict = {
            "extract_flat": "in_playlist",
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "socket_timeout": 30,  # Prevent hanging on unresponsive connections
        }
        ffmpeg = _get_ffmpeg_location()
        if ffmpeg:
            opts["ffmpeg_location"] = ffmpeg

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info is None:
            return []

        if "entries" in info:
            entries = []
            for entry in info["entries"]:
                if entry is None:
                    continue
                vid_url = (
                    entry.get("url")
                    or entry.get("webpage_url")
                    or f"https://www.youtube.com/watch?v={entry['id']}"
                )
                entries.append({
                    "url": vid_url,
                    "title": entry.get("title", "Unknown"),
                    "id": entry.get("id", ""),
                })
            return entries

        return [{
            "url": info.get("webpage_url", url),
            "title": info.get("title", "Unknown"),
            "id": info.get("id", ""),
        }]

    @staticmethod
    def find_existing(entries: list[dict], outdir: Path) -> set[str]:
        """Return set of video IDs whose MP3 already exists in outdir."""
        if not outdir.exists():
            return set()
        existing_names = {f.stem.lower() for f in outdir.glob("*.mp3")}
        found = set()
        for entry in entries:
            title = entry.get("title", "")
            if title.lower() in existing_names:
                found.add(entry["id"])
        return found

    def start(self, entries: list[dict], skip_ids: Optional[set[str]] = None):
        skip_ids = skip_ids or set()
        total = len(entries)
        self._tasks = [
            VideoTask(
                url=e["url"],
                title=e["title"],
                video_id=e["id"],
                index=i + 1,
                total=total,
                status=(VideoStatus.SKIPPED if e["id"] in skip_ids
                        else VideoStatus.PENDING),
            )
            for i, e in enumerate(entries)
        ]
        self._cancel.clear()
        threading.Thread(target=self._run_pool, daemon=True).start()

    def cancel(self):
        self._cancel.set()

    @property
    def tasks(self) -> list[VideoTask]:
        return list(self._tasks)

    # -- internals -----------------------------------------------------------

    def _build_ydl_opts(self, progress_hook, postprocessor_hook) -> dict:
        opts: dict = {
            "outtmpl": str(self.outdir / "%(title)s.%(ext)s"),
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "320",
                },
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "FFmpegThumbnailsConvertor", "format": "jpg"},
                {"key": "EmbedThumbnail", "already_have_thumbnail": False},
            ],
            "writethumbnail": True,
            # reliability
            "retries": 5,
            "fragment_retries": 5,
            "extractor_retries": 3,
            "socket_timeout": 30,
            "ignoreerrors": False,
            "continuedl": True,
            "overwrites": False,
            "noplaylist": True,
            # progress
            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
            # output control
            "quiet": True,
            "no_warnings": True,
            "concurrent_fragment_downloads": 4,
        }
        ffmpeg = _get_ffmpeg_location()
        if ffmpeg:
            opts["ffmpeg_location"] = ffmpeg
        return opts

    def _run_pool(self):
        # Only submit tasks that need downloading
        downloadable = [t for t in self._tasks if t.status == VideoStatus.PENDING]
        # Mark skipped tasks immediately
        for t in self._tasks:
            if t.status == VideoStatus.SKIPPED:
                self.on_update(t)

        if not downloadable:
            self.on_complete(self._tasks)
            return

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as pool:
            futures = {
                pool.submit(self._download_one, task): task
                for task in downloadable
            }
            for future in concurrent.futures.as_completed(futures):
                task = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    task.status = VideoStatus.FAILED
                    task.error_msg = str(exc)
                    self.on_update(task)
        self.on_complete(self._tasks)

    def _download_one(self, task: VideoTask):
        for attempt in range(1, self.MAX_RETRIES + 1):
            if self._cancel.is_set():
                task.status = VideoStatus.CANCELLED
                self.on_update(task)
                return

            task.attempts = attempt
            task.status = VideoStatus.DOWNLOADING
            task.progress_pct = 0.0
            task.error_msg = ""
            self.on_update(task)

            try:
                def _progress(d, _t=task):
                    if self._cancel.is_set():
                        raise yt_dlp.utils.DownloadCancelled()
                    if d["status"] == "downloading":
                        total_bytes = d.get("total_bytes") or d.get(
                            "total_bytes_estimate"
                        )
                        if total_bytes and total_bytes > 0:
                            _t.progress_pct = min(
                                100.0,
                                d["downloaded_bytes"] / total_bytes * 100
                            )
                        self.on_update(_t)
                    elif d["status"] == "finished":
                        _t.progress_pct = 100.0
                        _t.status = VideoStatus.POSTPROCESSING
                        self.on_update(_t)

                def _postproc(_d, _t=task):
                    pass  # completion handled after ydl.download returns

                opts = self._build_ydl_opts(_progress, _postproc)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([task.url])

                task.status = VideoStatus.COMPLETED
                task.progress_pct = 100.0
                self.on_update(task)
                return

            except (yt_dlp.utils.DownloadCancelled, KeyboardInterrupt):
                task.status = VideoStatus.CANCELLED
                self.on_update(task)
                return

            except (yt_dlp.utils.DownloadError, OSError, IOError, TimeoutError) as e:
                # Retryable errors: network issues, file I/O, timeouts
                task.error_msg = str(e)
                if attempt < self.MAX_RETRIES:
                    task.status = VideoStatus.PENDING
                    self.on_update(task)
                    backoff = self.BACKOFF_BASE ** attempt
                    for _ in range(int(backoff * 10)):
                        if self._cancel.is_set():
                            task.status = VideoStatus.CANCELLED
                            self.on_update(task)
                            return
                        time.sleep(0.1)
                else:
                    task.status = VideoStatus.FAILED
                    self.on_update(task)
            except Exception as e:
                # Non-retryable errors: fail immediately
                task.status = VideoStatus.FAILED
                task.error_msg = f"Fatal: {str(e)}"
                self.on_update(task)


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

_BG = "#121212"
_BG2 = "#1e1e1e"
_FG = "#e0e0e0"
_ENTRY_BG = "#2c2c2c"
_BTN_BG = "#404040"
_BTN_ACTIVE = "#555555"
_BTN_FG = "#ffffff"
_ACCENT = "#4fc3f7"
_FONT = ("Segoe UI", 10)
_MONO = ("Consolas", 10)

_STATUS_COLORS = {
    VideoStatus.PENDING: "#888888",
    VideoStatus.DOWNLOADING: _ACCENT,
    VideoStatus.POSTPROCESSING: "#ffb74d",
    VideoStatus.COMPLETED: "#81c784",
    VideoStatus.SKIPPED: "#888888",
    VideoStatus.FAILED: "#ff5555",
    VideoStatus.CANCELLED: "#888888",
}


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("YouTube \u2192 MP3")
        root.geometry("700x500")
        root.configure(bg=_BG)
        root.minsize(500, 380)

        # Validate dependencies on startup
        self._validate_dependencies()

        self.engine: Optional[DownloadEngine] = None
        self._update_queue: Queue = Queue()

        # Load saved settings
        settings = _load_settings()
        saved_outdir = settings.get("output_dir", "")

        # -- URL row ---------------------------------------------------------
        tk.Label(root, text="YouTube URL:", bg=_BG, fg=_FG, font=_FONT).pack(
            anchor="w", padx=12, pady=(12, 4)
        )
        self.url_var = tk.StringVar()
        tk.Entry(
            root,
            textvariable=self.url_var,
            bg=_ENTRY_BG, fg=_FG, insertbackground=_FG,
            bd=0, highlightthickness=1,
            highlightbackground="#444", highlightcolor="#777",
            font=_FONT,
        ).pack(fill="x", padx=12)

        # -- Output folder row -----------------------------------------------
        tk.Label(root, text="Output folder:", bg=_BG, fg=_FG, font=_FONT).pack(
            anchor="w", padx=12, pady=(10, 4)
        )
        row = tk.Frame(root, bg=_BG)
        row.pack(fill="x", padx=12)
        self.outdir_var = tk.StringVar(value=saved_outdir or _default_output_dir())
        tk.Entry(
            row,
            textvariable=self.outdir_var,
            bg=_ENTRY_BG, fg=_FG, insertbackground=_FG,
            bd=0, highlightthickness=1,
            highlightbackground="#444", highlightcolor="#777",
            font=_FONT,
        ).pack(side="left", fill="x", expand=True)
        # Bind click event to Browse button
        browse_btn = tk.Label(
            row, text="Browse\u2026",
            bg=_BTN_BG, fg=_BTN_FG, font=_FONT, 
            relief=tk.RAISED, bd=1, padx=10, pady=4, cursor="hand2"
        )
        browse_btn.pack(side="left", padx=(6, 0))
        browse_btn.bind("<Button-1>", lambda e: self._choose_folder())

        # -- Controls row (workers + buttons) --------------------------------
        ctrl = tk.Frame(root, bg=_BG)
        ctrl.pack(fill="x", padx=12, pady=(10, 0))

        tk.Label(ctrl, text="Workers:", bg=_BG, fg=_FG, font=_FONT).pack(
            side="left"
        )
        self.workers_var = tk.StringVar(value="4")
        combo = ttk.Combobox(
            ctrl,
            textvariable=self.workers_var,
            values=["1", "2", "4", "8"],
            width=3,
            state="readonly",
        )
        combo.pack(side="left", padx=(4, 12))

        self.cancel_btn = tk.Button(
            ctrl, text="Cancel",
            bg=_BTN_BG, fg="#666666", font=_FONT, 
            relief=tk.RAISED, bd=1, padx=10, pady=4, cursor="hand2"
        )
        self.cancel_btn.pack(side="right")
        self.cancel_btn.bind("<Button-1>", lambda e: self._on_cancel() if self.cancel_btn_enabled else None)
        self.cancel_btn_enabled = False

        self.dl_btn = tk.Label(
            ctrl, text="Download",
            bg=_BTN_BG, fg=_BTN_FG, font=_FONT, 
            relief=tk.RAISED, bd=1, padx=10, pady=4, cursor="hand2"
        )
        self.dl_btn.pack(side="right", padx=(0, 8))
        self.dl_btn.bind("<Button-1>", lambda e: self._start_download() if self.dl_btn_enabled else None)
        self.dl_btn_enabled = True

        # -- Progress bar ----------------------------------------------------
        pbar_frame = tk.Frame(root, bg=_BG)
        pbar_frame.pack(fill="x", padx=12, pady=(10, 0))

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "custom.Horizontal.TProgressbar",
            troughcolor=_ENTRY_BG,
            background=_ACCENT,
            thickness=18,
        )
        self.pbar = ttk.Progressbar(
            pbar_frame,
            orient="horizontal",
            mode="determinate",
            style="custom.Horizontal.TProgressbar",
        )
        self.pbar.pack(side="left", fill="x", expand=True)
        self.pbar_label = tk.Label(
            pbar_frame, text="", bg=_BG, fg=_FG, font=_FONT, width=16,
            anchor="e",
        )
        self.pbar_label.pack(side="left", padx=(8, 0))

        # -- Log area --------------------------------------------------------
        self.log = scrolledtext.ScrolledText(
            root, height=12, bg=_BG2, fg=_FG, insertbackground=_FG,
            font=_MONO, bd=0, highlightthickness=1,
            highlightbackground="#333", highlightcolor="#555",
        )
        self.log.configure(state="disabled")
        self.log.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        # tag for each status colour
        for status, colour in _STATUS_COLORS.items():
            self.log.tag_configure(status.value, foreground=colour)
        self.log.tag_configure("error", foreground="#ff5555")
        self.log.tag_configure("info", foreground=_FG)

        # If no saved folder, prompt user on first launch
        if not saved_outdir:
            self.root.after(100, self._prompt_initial_folder)

    def _set_download_btn_state(self, enabled: bool):
        """Enable or disable the download button."""
        self.dl_btn.configure(
            fg=_BTN_FG if enabled else "#999999"
        )
        self.dl_btn_enabled = enabled

    def _set_cancel_btn_state(self, enabled: bool):
        """Enable or disable the cancel button."""
        self.cancel_btn.configure(
            fg=_BTN_FG if enabled else "#999999"
        )
        self.cancel_btn_enabled = enabled

    # -- validation

    def _validate_dependencies(self):
        """Check required dependencies on startup."""
        if yt_dlp is None:
            messagebox.showerror(
                "Missing Dependency",
                "yt-dlp module not found.\nInstall with: pip install yt-dlp"
            )
            self.root.after(100, self.root.quit)
            return

        if not _get_ffmpeg_location() and not shutil.which("ffmpeg"):
            result = messagebox.askyesno(
                "ffmpeg Not Found",
                "ffmpeg is not installed or not on PATH.\n\n"
                "This is required to convert audio to MP3.\n\n"
                "Install ffmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Windows: https://www.gyan.dev/ffmpeg/builds/\n"
                "  Linux: sudo apt install ffmpeg\n\n"
                "Continue anyway?"
            )
            if not result:
                self.root.after(100, self.root.quit)

    # -- folder chooser ------------------------------------------------------

    def _choose_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.outdir_var.set(path)
            self._persist_outdir(path)

    def _prompt_initial_folder(self):
        """Ask user to pick an output folder on first launch."""
        result = messagebox.askyesno(
            "Output Folder",
            f"Downloads will be saved to:\n\n{_default_output_dir()}\n\n"
            "Would you like to choose a different folder?",
        )
        if result:
            self._choose_folder()
        else:
            self._persist_outdir(self.outdir_var.get())

    def _persist_outdir(self, path: str):
        settings = _load_settings()
        settings["output_dir"] = path
        _save_settings(settings)

    # -- start / cancel ------------------------------------------------------

    def _start_download(self):
        url = self.url_var.get().strip()
        outdir = Path(
            self.outdir_var.get().strip() or _default_output_dir()
        ).expanduser().resolve()

        try:
            outdir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._append_log(f"Error: Cannot create output folder: {e}", error=True)
            return

        if not url:
            self._append_log("Error: Please enter a YouTube URL.", error=True)
            return

        if not _get_ffmpeg_location() and not shutil.which("ffmpeg"):
            self._append_log(
                "Error: ffmpeg not found. Install ffmpeg and add it to PATH.",
                error=True,
            )
            return

        if yt_dlp is None:
            self._append_log(
                "Error: yt-dlp module missing.  pip install yt-dlp", error=True
            )
            return

        # Persist the chosen output folder
        self._persist_outdir(str(outdir))

        workers = int(self.workers_var.get())

        # reset UI
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.pbar["value"] = 0
        self.pbar_label.configure(text="")
        self._set_download_btn_state(False)
        self._set_cancel_btn_state(True)

        self._append_log("Fetching video info\u2026")

        # fetch playlist info in a thread, then start engine
        def _fetch():
            try:
                entries = DownloadEngine.extract_playlist_info(url)
            except Exception as e:
                self.root.after(0, lambda: self._on_fetch_error(str(e)))
                return
            self.root.after(0, lambda: self._on_fetch_done(entries, outdir, workers))

        threading.Thread(target=_fetch, daemon=True).start()

    def _on_fetch_error(self, msg: str):
        self._append_log(f"Error: {msg}", error=True)
        self._set_download_btn_state(True)
        self._set_cancel_btn_state(False)

    def _on_fetch_done(self, entries: list[dict], outdir: Path, workers: int):
        if not entries:
            self._append_log("No downloadable videos found.", error=True)
            self._set_download_btn_state(True)
            self._set_cancel_btn_state(False)
            return

        # Check which videos are already downloaded
        already = DownloadEngine.find_existing(entries, outdir)
        new_count = len(entries) - len(already)

        # For playlists (>1 video), show confirmation dialog
        if len(entries) > 1:
            skip_msg = (
                f"\n\n({len(already)} already downloaded, will be skipped)"
                if already else ""
            )
            confirmed = messagebox.askyesno(
                "Confirm Download",
                f"Found {len(entries)} video(s) in playlist.\n"
                f"{new_count} new download(s) to start.{skip_msg}\n\n"
                "Proceed?",
            )
            if not confirmed:
                self._append_log("Download cancelled by user.")
                self._set_download_btn_state(True)
                self._set_cancel_btn_state(False)
                return

        if new_count == 0:
            self._append_log("All videos already downloaded.")
            self._set_download_btn_state(True)
            self._set_cancel_btn_state(False)
            return

        status_msg = f"Found {len(entries)} video(s)"
        if already:
            status_msg += f" ({len(already)} already downloaded)"
        self._append_log(f"{status_msg}. Starting download\u2026\n")

        # Pre-initialize task marks to prevent race condition
        self._task_marks: dict[int, str] = {}
        self.log.configure(state="normal")
        for i, entry in enumerate(entries, 1):
            mark = f"task_{i}"
            self._task_marks[i] = mark
            self.log.mark_set(mark, "end")
            self.log.mark_gravity(mark, "left")
            title = _truncate(entry["title"], 45)
            is_skip = entry["id"] in already
            status = "SKIPPED" if is_skip else "PENDING"
            tag = VideoStatus.SKIPPED.value if is_skip else VideoStatus.PENDING.value
            line = f"[{i:>{len(str(len(entries)))}}/{len(entries)}] {title:<48s} {status}"
            self.log.insert("end", line + "\n", tag)
        self.log.configure(state="disabled")

        self.pbar["maximum"] = len(entries)
        self.pbar["value"] = len(already)
        self.pbar_label.configure(text=f"{len(already)}/{len(entries)}")

        # Now create engine after all marks are set
        self.engine = DownloadEngine(
            outdir=outdir,
            max_workers=workers,
            on_update=self._schedule_update,
            on_complete=self._schedule_complete,
        )
        self.engine.start(entries, skip_ids=already)

    def _on_cancel(self):
        if self.engine:
            self.engine.cancel()
            # Clean up incomplete downloads
            self._cleanup_incomplete_downloads()
        self._set_cancel_btn_state(False)

    def _cleanup_incomplete_downloads(self):
        """Remove incomplete MP3 files that weren't fully downloaded."""
        if not hasattr(self, '_task_marks'):
            return
        
        outdir = Path(self.outdir_var.get())
        if not outdir.exists():
            return
        
        # Collect filenames that were successfully completed
        completed_files = set()
        for idx, mark_text in self._task_marks.items():
            # Mark text contains the filename if download completed
            # Format is typically "filename.mp3 ✓" for completed
            if "✓" in mark_text or "COMPLETED" in mark_text or "SKIPPED" in mark_text:
                # Extract filename from mark text (before the status indicator)
                filename = mark_text.split()[0] if mark_text else None
                if filename and filename.endswith(".mp3"):
                    completed_files.add(filename)
        
        # Remove all MP3 files not in completed list
        removed_count = 0
        for mp3_file in outdir.glob("*.mp3"):
            try:
                if mp3_file.name not in completed_files:
                    mp3_file.unlink()
                    removed_count += 1
            except OSError:
                pass
        
        if removed_count > 0:
            self._append_log(f"Cleaned up {removed_count} incomplete file(s).", info=True)

    # -- thread-safe GUI updates ---------------------------------------------

    def _schedule_update(self, task: VideoTask):
        self._update_queue.put(("update", task))
        self.root.after(0, self._drain_queue)

    def _schedule_complete(self, tasks: list[VideoTask]):
        self._update_queue.put(("complete", tasks))
        self.root.after(0, self._drain_queue)

    def _drain_queue(self):
        while True:
            try:
                kind, payload = self._update_queue.get_nowait()
            except Empty:
                break
            if kind == "update":
                self._render_task(payload)
                self._update_progress()
            elif kind == "complete":
                self._on_all_complete(payload)

    def _render_task(self, task: VideoTask):
        mark = self._task_marks.get(task.index)
        if not mark:
            return
        width = len(str(task.total))
        title = _truncate(task.title, 45)

        if task.status == VideoStatus.DOWNLOADING:
            status_text = f"DOWNLOADING {task.progress_pct:5.1f}%"
        elif task.status == VideoStatus.PENDING and task.attempts > 0:
            status_text = f"RETRY {task.attempts}/{DownloadEngine.MAX_RETRIES}"
        elif task.status == VideoStatus.FAILED and task.error_msg:
            short_err = _truncate(task.error_msg, 30)
            status_text = f"FAILED: {short_err}"
        else:
            status_text = task.status.value

        line = f"[{task.index:>{width}}/{task.total}] {title:<48s} {status_text}"

        self.log.configure(state="normal")
        try:
            start = self.log.index(mark)
            end = f"{start} lineend"
            self.log.delete(start, end)
            tag = task.status.value
            self.log.insert(start, line, tag)
        except tk.TclError:
            pass
        self.log.configure(state="disabled")

    def _update_progress(self):
        if not self.engine:
            return
        tasks = self.engine.tasks
        done = sum(
            1 for t in tasks
            if t.status in (
                VideoStatus.COMPLETED, VideoStatus.SKIPPED,
                VideoStatus.FAILED, VideoStatus.CANCELLED,
            )
        )
        total = len(tasks)
        self.pbar["value"] = done
        self.pbar_label.configure(text=f"{done}/{total}")

    def _on_all_complete(self, tasks: list[VideoTask]):
        completed = sum(1 for t in tasks if t.status == VideoStatus.COMPLETED)
        skipped = sum(1 for t in tasks if t.status == VideoStatus.SKIPPED)
        failed = sum(1 for t in tasks if t.status == VideoStatus.FAILED)
        cancelled = sum(1 for t in tasks if t.status == VideoStatus.CANCELLED)
        total = len(tasks)

        parts = []
        if completed:
            parts.append(f"{completed} completed")
        if skipped:
            parts.append(f"{skipped} skipped")
        if failed:
            parts.append(f"{failed} failed")
        if cancelled:
            parts.append(f"{cancelled} cancelled")
        summary = ", ".join(parts)

        self.pbar["value"] = total
        self.pbar_label.configure(text=f"{total}/{total}")

        if failed or cancelled:
            self._append_log(f"\nFinished: {summary}", error=True)
        else:
            self._append_log(f"\n\u2705 Done! {summary}")

        self._set_download_btn_state(True)
        self._set_cancel_btn_state(False)
        self.engine = None

    # -- simple append log ---------------------------------------------------

    def _append_log(self, text: str, error: bool = False):
        tag = "error" if error else "info"
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _truncate(text: str, maxlen: int) -> str:
    if len(text) <= maxlen:
        return text
    return text[: maxlen - 1] + "\u2026"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
