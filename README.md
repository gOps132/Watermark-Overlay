# Watermark Overlay

Desktop utility for applying the same overlay or watermark image to a batch of photos.

## What It Does

- Select one overlay image.
- Add many source images by file picker or drag and drop when available.
- Choose overlay position, scale, and padding.
- Export processed images as PNG files.

## Recommended Setup

Create a fresh virtual environment for your current platform.

```bash
python3 -m venv .venv-local
source .venv-local/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run The App

```bash
python main.py
```

## Build Packages

```bash
python3 scripts/build.py --help
```

See [docs/BUILD.md](/Users/giancedrick/dev/repo/Watermark-Overlay/docs/BUILD.md) for macOS, Windows, and CrossOver build instructions.

See [docs/PLATFORM.md](/Users/giancedrick/dev/repo/Watermark-Overlay/docs/PLATFORM.md) for platform-specific runtime notes.
