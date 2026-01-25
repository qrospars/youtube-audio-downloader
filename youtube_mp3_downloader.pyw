"""
youtube_mp3_downloader.pyw – Tkinter GUI to download a YouTube URL
(video or playlist) as 320 kbps MP3, in dark mode without a console window.
Handles various download scenarios with clear logging.
"""

import sys
import subprocess
import re
import threading
import time
import shutil
import importlib.util
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, scrolledtext

# Helper to check yt_dlp module
import importlib.util


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


# Build yt-dlp command


def build_cmd(url: str, outdir: Path) -> list[str]:
    flag = "--yes-playlist" if "list=" in url else "--no-playlist"
    tpl = str(outdir / "%(title)s.%(ext)s")
    return [
        sys.executable,
        "-m",
        "yt_dlp",
        flag,
        "--ignore-errors",
        "--continue",
        "--no-overwrites",
        "--no-post-overwrites",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "320K",
        "--add-metadata",
        "--embed-thumbnail",
        "--no-warnings",
        "--newline",
        "--output",
        tpl,
        url,
    ]


class App:
    def __init__(self, root: tk.Tk):
        root.title("YouTube → MP3")
        root.geometry("620x420")
        root.configure(bg="#121212")

        # URL label & entry
        tk.Label(root, text="YouTube URL:", bg="#121212", fg="#e0e0e0").pack(
            anchor="w", padx=12, pady=(12, 4)
        )
        self.url_var = tk.StringVar()
        tk.Entry(
            root,
            textvariable=self.url_var,
            bg="#2c2c2c",
            fg="#e0e0e0",
            insertbackground="#e0e0e0",
            bd=0,
            highlightthickness=1,
            highlightbackground="#444",
            highlightcolor="#777",
            font=("Segoe UI", 10),
        ).pack(fill="x", padx=12)

        # Folder label & picker
        tk.Label(root, text="Output folder:", bg="#121212", fg="#e0e0e0").pack(
            anchor="w", padx=12, pady=(10, 4)
        )
        row = tk.Frame(root, bg="#121212")
        row.pack(fill="x", padx=12)
        self.outdir_var = tk.StringVar(value="F:/")
        tk.Entry(
            row,
            textvariable=self.outdir_var,
            bg="#2c2c2c",
            fg="#e0e0e0",
            insertbackground="#e0e0e0",
            bd=0,
            highlightthickness=1,
            highlightbackground="#444",
            highlightcolor="#777",
            font=("Segoe UI", 10),
        ).pack(side="left", fill="x", expand=True)
        btn = tk.Button(
            row,
            text="Browse…",
            command=self.choose_folder,
            bg="#3c3c3c",
            fg="#e0e0e0",
            activebackground="#505050",
            activeforeground="#e0e0e0",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        btn.pack(side="left", padx=(6, 0))

        # Download button
        dbtn = tk.Button(
            root,
            text="Download",
            command=self.start_download,
            bg="#3c3c3c",
            fg="#e0e0e0",
            activebackground="#505050",
            activeforeground="#e0e0e0",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        dbtn.pack(fill="x", padx=12, pady=12)

        # Log area
        self.log = scrolledtext.ScrolledText(
            root,
            height=12,
            bg="#1e1e1e",
            fg="#e0e0e0",
            insertbackground="#e0e0e0",
            font=("Consolas", 10),
            bd=0,
            highlightthickness=1,
            highlightbackground="#333",
            highlightcolor="#555",
        )
        self.log.configure(state="disabled")
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def choose_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.outdir_var.set(path)

    def start_download(self):
        url = self.url_var.get().strip()
        outdir = (
            Path(self.outdir_var.get().strip() or "downloads").expanduser().resolve()
        )
        try:
            outdir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._log(f"Error: Cannot create output folder: {e}", error=True)
            return

        if not url:
            self._log("Error: Please enter a YouTube URL.", error=True)
            return
        if not shutil.which("ffmpeg"):
            self._log("Error: ffmpeg not on PATH.", error=True)
            return
        if not module_available("yt_dlp"):
            self._log("Error: yt-dlp module missing. pip install yt-dlp", error=True)
            return

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        threading.Thread(
            target=self._download_thread, args=(url, outdir), daemon=True
        ).start()

    def _download_thread(self, url: str, outdir: Path):
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            self._log(
                "Starting download..."
                if attempt == 1
                else f"Retrying ({attempt}/{max_attempts})..."
            )
            try:
                proc = subprocess.Popen(
                    build_cmd(url, outdir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except Exception as e:
                self._log(f"Launch error: {e}", error=True)
                return

            current = total = None
            seen_titles = set()
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                m = re.match(r"\[download\] Downloading item (\d+) of (\d+)", line)
                if m:
                    current, total = map(int, m.groups())
                    continue
                d = re.match(r"\[download\] Destination: (.+)\.(?:mp3|webm)", line)
                if d and current and total:
                    title = Path(d.group(1)).name
                    if title not in seen_titles:
                        seen_titles.add(title)
                        self._log(f"▶ Downloading {current}/{total}: {title}")
                    continue
                if "already been downloaded" in line or "[download] Skipping" in line:
                    if current and total:
                        self._log(f"⏭️ Skipped {current}/{total}")
                    continue
                if "[ExtractAudio] Destination:" in line:
                    self._log("🔄 Converting to MP3")
                    continue
                if "[Metadata] Adding metadata" in line:
                    self._log("📝 Adding metadata")
                    continue
                if "[EmbedThumbnail]" in line:
                    self._log("🖼 Embedding thumbnail")
                    continue
                # Surface unhandled yt-dlp output so failures are visible in the UI.
                self._log(f"yt-dlp: {line}")
            proc.wait()
            if proc.returncode == 0:
                self._log("✅ Done!")
                return
            self._log(f"❌ Failed. (exit code {proc.returncode})", error=True)
            if attempt < max_attempts:
                time.sleep(2)

    def _log(self, text: str, error: bool = False):
        self.log.configure(state="normal")
        tag = ("error",) if error else ()
        self.log.insert("end", text + "\n", tag)
        if error:
            self.log.tag_config("error", foreground="#ff5555")
        self.log.see("end")
        self.log.configure(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
