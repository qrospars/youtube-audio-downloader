# YouTube → MP3 Downloader

A cross-platform, standalone Tkinter GUI application for downloading single YouTube videos or entire playlists as 320 kbps MP3 files with embedded metadata and thumbnail art.

---

## Features

* **Single video or playlist** support (auto-detected)
* **Parallel downloads** – configurable worker count (1, 2, 4, or 8 concurrent downloads)
* **Real-time progress** – overall progress bar + per-video status with percentage
* **Per-video retry** with exponential backoff (3 attempts per video)
* **Cancel** ongoing downloads cleanly
* **Automatic skipping** of previously downloaded items
* **Dark-mode UI** with color-coded status indicators
* **Embedded metadata**: title, artist (uploader), album (playlist title)
* **Embedded thumbnail** as cover art
* **Standalone bundling** via PyInstaller (no Python or FFmpeg install required)
* **Cross-platform** releases for Windows and macOS via GitHub Actions

---

## Requirements

For running from source:

* Python 3.8+
* `yt-dlp` Python module
* Tkinter (included in most Python installs)
* FFmpeg on PATH

For the standalone build: no dependencies – everything is bundled.

---

## Installation & Setup

### Option 1: Download a release (recommended)

Download the latest release from the [Releases](../../releases) page:

* **Windows**: `youtube_mp3_downloader_windows.zip` – extract and run the `.exe`
* **macOS**: `youtube_mp3_downloader_macos.zip` – extract and run the binary
  * On first launch you may need to right-click → Open to bypass Gatekeeper

### Option 2: Run from source

1. **Clone the repository**

   ```bash
   git clone https://github.com/qrospars/youtube-audio-downloader.git
   cd youtube-audio-downloader
   ```

2. **Install Python dependencies**

   ```bash
   pip install yt-dlp
   ```

3. **Install FFmpeg**

   * **macOS**: `brew install ffmpeg`
   * **Windows**: Download from [gyan.dev/ffmpeg](https://www.gyan.dev/ffmpeg/builds/) and add to PATH
   * **Linux**: `sudo apt install ffmpeg` (or your distro's package manager)

4. **Run**

   ```bash
   python youtube_mp3_downloader.pyw
   ```

---

## Usage

1. Paste a **YouTube video URL** or **playlist URL**
2. Choose an output folder (defaults to `~/Music/YouTube Downloads`)
3. Select the number of **parallel workers** (1–8)
4. Click **Download** and watch the progress:

   * Per-video status lines update in real-time with download percentage
   * Overall progress bar shows how many videos are complete
   * Failed videos are retried automatically (up to 3 times with backoff)
   * Click **Cancel** to stop all downloads

---

## Building a Standalone Executable

### Windows (PyInstaller)

```bash
pip install pyinstaller yt-dlp

# Make sure ffmpeg.exe is on PATH or in the current directory
py -3 -m PyInstaller --noconfirm --onefile --windowed \
  --add-binary "$(which ffmpeg);." \
  --add-binary "$(which ffprobe);." \
  --name youtube_mp3_downloader \
  youtube_mp3_downloader.pyw
```

### macOS (PyInstaller)

```bash
pip install pyinstaller yt-dlp
brew install ffmpeg

python3 -m PyInstaller \
  --noconfirm \
  --onefile \
  --windowed \
  --add-binary "$(which ffmpeg):." \
  --add-binary "$(which ffprobe):." \
  --name youtube_mp3_downloader \
  youtube_mp3_downloader.pyw
```

The generated executable is in `dist/`.

---

## Troubleshooting

* **FFmpeg not found**: Ensure `ffmpeg` is on your PATH, or place the binary next to the script.
* **`yt-dlp` errors**: Run `pip install -U yt-dlp` to update to the latest version.
* **macOS Gatekeeper block**: Right-click the app → Open → Open to allow it through.
* **Download fails repeatedly**: YouTube may be rate-limiting. Try reducing the worker count to 1 or 2.

---

## About Antivirus Warnings

When downloading the executable from GitHub Releases, your antivirus software may flag it as a potential threat. This is a **false positive** caused by:

- **PyInstaller pattern**: The executable bundles Python, libraries, and dependencies into a single file. Antivirus software is unfamiliar with this packaging and treats it suspiciously.
- **Legitimate files**: All releases are built automatically from the public source code in this repository.

### Verify the Download is Safe

**Option 1: Scan with VirusTotal (recommended)**

1. Download the executable from [Releases](../../releases)
2. Visit [VirusTotal.com](https://www.virustotal.com/)
3. Upload the `.exe` or `.dmg` file
4. Wait for the scan (~1 minute)
5. Review results: Should show 0 or minimal detections from obscure vendors

**Option 2: Build Locally**

Avoid downloads entirely by building from source:

```bash
git clone https://github.com/qrospars/youtube-audio-downloader.git
cd youtube-audio-downloader
pip install -r requirements.txt
pyinstaller youtube_mp3_downloader.spec
# Executable is in dist/
```

**Option 3: Trust the GitHub Release**

Downloads from official GitHub Releases are built automatically by GitHub Actions from the verified source code. If you trust this repository, the executable is safe.

---

## Contributing

Fork the repo, implement a feature, and submit a pull request. Please adhere to the existing code style and dark-mode UI conventions.

For development setup and testing instructions, see [CONTRIBUTING.md](CONTRIBUTING.md).
