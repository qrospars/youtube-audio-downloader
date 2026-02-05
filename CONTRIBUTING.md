# Contributing

Thanks for your interest in contributing! Here's how to set up the development environment and test your changes.

## Development Setup

### 1. Clone and Install

```bash
git clone https://github.com/qrospars/youtube-audio-downloader.git
cd youtube-audio-downloader
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
pip install pytest yt-dlp
```

### 2. Branching Strategy

This project uses Git Flow:
- **`develop`** - Integration branch for features
- **`main`** - Production releases (automatically triggers builds)
- **`feature/*`** - Feature branches (branch from `develop`)
- **`hotfix/*`** - Emergency fixes (branch from `main`)

See [BRANCHING.md](BRANCHING.md) for detailed workflow.

## Testing

### Unit Tests (No Network Required)

Fast tests that don't need YouTube or ffmpeg:

```bash
pytest tests/test_unit.py -v
```

Covers:
- String truncation, settings persistence
- Thread safety (concurrent settings access)
- Progress clamping to [0, 100%]
- Exception handling
- Download task state management

### Integration Tests (Requires Network + FFmpeg)

Full end-to-end tests:

```bash
# All integration tests
pytest tests/test_integration.py -v

# Only specific tests
pytest tests/test_integration.py::TestExtractPlaylistInfo -v
pytest tests/test_integration.py::TestDownloadSingle -v
pytest tests/test_integration.py::TestDownloadParallel -v

# Skip slow cancel test
pytest tests/test_integration.py -v -k "not cancel"
```

**Requirements:**
- `ffmpeg` installed (`brew install ffmpeg` on macOS)
- Working internet connection
- ~60 seconds for full test suite
- ~50 MB disk space (temporary, cleaned up automatically)

**Note:** Test downloads use pytest's temporary directories, automatically cleaned up after tests complete. No disk space is permanently used.

Covers:
- Playlist extraction and parsing
- Single/parallel video downloads
- Skipping already-downloaded videos
- Cancel functionality

### Running the GUI

```bash
python3 youtube_mp3_downloader.pyw
```

Useful for manual testing:
1. Try single videos and playlists
2. Test cancel functionality mid-download
3. Verify error handling (invalid URLs, network issues)
4. Check dark mode UI rendering

## Building Executables

### Local Build (macOS)

```bash
pip install pyinstaller
python3 -m PyInstaller --noconfirm youtube_mp3_downloader.spec
```

Output: `dist/youtube_mp3_downloader.app`

### Local Build (Windows)

```bash
pip install pyinstaller
py -3 -m PyInstaller --noconfirm youtube_mp3_downloader.spec
```

Output: `dist\youtube_mp3_downloader.exe`

The spec file automatically bundles ffmpeg/ffprobe from your PATH.

## Code Quality

### Linting (Optional)

```bash
pip install pylint
pylint youtube_mp3_downloader.pyw
```

### Type Hints

The codebase uses type hints. When adding new functions, include them:

```python
def my_function(url: str, count: int = 5) -> list[dict]:
    """Extract video info from URL."""
    return []
```

## Common Issues

**`pytest: command not found`**
```bash
pip install pytest
```

**`ffmpeg: command not found`**
```bash
# macOS
brew install ffmpeg

# Windows - download from https://www.gyan.dev/ffmpeg/builds/
# then add to PATH

# Linux
sudo apt install ffmpeg
```

**`yt-dlp` import errors**
```bash
pip install -U yt-dlp
```

**Tests hang/timeout**
- Check internet connection
- YouTube may be rate-limiting (try again later)
- Kill the process: `Ctrl+C`

## Submitting Changes

1. Create a feature branch:
   ```bash
   git checkout develop
   git checkout -b feature/my-feature
   ```

2. Make changes and test:
   ```bash
   pytest tests/test_unit.py -v
   pytest tests/test_integration.py -v
   ```

3. Use conventional commits:
   ```
   feat: add batch download support
   fix: handle network timeouts gracefully
   docs: update README with examples
   ```

4. Push and create a Pull Request to `develop`

5. When ready for release, maintainer creates PR: `develop` → `main`
   - GitHub Actions automatically builds Windows + macOS releases
   - Creates a GitHub Release with both binaries

## Release Process

Releases are automated via GitHub Actions:

1. Merge `develop` → `main`
2. GitHub Actions:
   - Builds Windows `.exe` on Windows runner
   - Builds macOS `.dmg` on macOS runner
   - Generates changelog from commits
   - Creates GitHub Release with both binaries
3. Users download from [Releases](../../releases) page

## Questions?

Open an issue on GitHub or check [BRANCHING.md](BRANCHING.md) for workflow details.
