# YouTube→MP3 Downloader

A cross-platform, standalone Tkinter GUI application for downloading single YouTube videos or entire playlists as 320 kbps MP3 files with embedded metadata and thumbnail art.

---

## Features

* **Single video or playlist** support
* **Automatic skipping** of previously downloaded items
* **Clear, dark-mode UI** with live, per-item progress
* **Embedded metadata**: title, artist (uploader), album (playlist title)
* **Embedded thumbnail** as cover art
* **Standalone bundling** via PyInstaller (no Python or FFmpeg install required)

---

## Table of Contents

- [YouTube→MP3 Downloader](#youtubemp3-downloader)
  - [Features](#features)
  - [Table of Contents](#table-of-contents)
  - [Requirements](#requirements)
  - [Installation \& Setup](#installation--setup)
  - [Running the App](#running-the-app)
  - [Building a Standalone Executable](#building-a-standalone-executable)
    - [Windows (PyInstaller)](#windows-pyinstaller)
    - [macOS (PyInstaller)](#macos-pyinstaller)
  - [Troubleshooting](#troubleshooting)
  - [Future Changes \& Contribution](#future-changes--contribution)

---

## Requirements

* Python 3.8+
* `yt-dlp` Python module
* TKinter (included in most Python installs)
* FFmpeg (bundled or system)

---

## Installation & Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourname/youtube-audio-downloader.git
   cd youtube-audio-downloader
   ```

2. **Install Python dependencies**

   ```bash
   pip install yt-dlp
   ```

3. **Obtain FFmpeg**

   * **Windows**: Download the Essentials build from [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/), unzip, and copy **`ffmpeg.exe`** into this project folder.
   * **macOS/Linux**: Either install via Homebrew/apt/pacman (`brew install ffmpeg`) or drop a static `ffmpeg` binary beside the script.

---

## Running the App

Double‑click **`youtube_mp3_downloader.pyw`** (Windows) or run:

```bash
python youtube_mp3_downloader.pyw
```

1. Paste a **YouTube video URL** or **playlist URL**.
2. Click **Browse…** to choose (or type) an output folder.
3. Hit **Download** and watch the log for progress:

   * ▶ Downloading **X/Y: Title**
   * ⏭️ Skipped if already present
   * 🔄 Converting → 📝 Metadata → 🖼 Thumbnail
   * ✅ Done or ❌ Failed

---

## Building a Standalone Executable

Produces a single double‑clickable file—no Python or FFmpeg install needed.

### Windows (PyInstaller)

1. **Install PyInstaller**

   ```bash
   pip install pyinstaller
   ```

2. **Bundle**

   ```powershell
   py -3 -m PyInstaller \
     --noconfirm \
     --onefile \
     --windowed \
     --add-binary "ffmpeg.exe;." \
     --name youtube_mp3_downloader \
     youtube_mp3_downloader.pyw
   ```

3. **Distribute** the generated `dist\youtube_mp3_downloader.exe`.

### macOS (PyInstaller)

1. **Install** and place a static `ffmpeg` binary beside the script.
2. **Bundle**

   ```bash
   python3 -m PyInstaller \
     --noconfirm \
     --onefile \
     --windowed \
     --add-binary "ffmpeg:." \
     --name youtube_mp3_downloader \
     youtube_mp3_downloader.pyw
   ```
3. **Optionally** wrap into a `.app` bundle or distribute the `dist/youtube_mp3_downloader` binary.

---

## Troubleshooting

* **App doesn’t launch**: Ensure the file has `.pyw` extension on Windows or is opened with `pythonw` to suppress the console.
* **FFmpeg not found**: Verify `ffmpeg.exe` (Windows) or `ffmpeg` (macOS/Linux) is present beside the script or on the PATH.
* **`yt_dlp` errors**: Run `pip install yt-dlp` in the same Python environment.

---

## Future Changes & Contribution

* **Improvements**: support drag‑and‑drop URLs, custom audio bitrates, multi‑threaded downloads
* **Bug fixes**: edge cases in URL parsing, more robust FFmpeg embedding
* **Contribute**: fork the repo, implement a feature, and submit a pull request. Please adhere to the existing code style and dark‑mode UI conventions.

---

*Generated and maintained to keep your YouTube→MP3 workflow as simple and reliable as possible.*
