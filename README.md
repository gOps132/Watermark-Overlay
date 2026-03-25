# Watermark Overlay

Desktop utility for applying the same overlay or watermark image to a batch of photos.

## What It Does

- Select one overlay image.
- Add many source images by file picker or drag and drop when available.
- Choose overlay position, scale, and padding.
- Export processed images as PNG files.

## Recommended Setup

Create a fresh virtual environment for your current platform. The checked-in `.venv` in this repo was created on Windows and should not be reused on macOS or Linux.

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

On this Mac, `/usr/bin/python3` is linked against an older Tk 8.5 runtime that launches `Python.app` without a usable visible window. The verified working run path is:

```bash
./.venv-local312-uv/bin/python main.py
```

## macOS Notes

- On macOS with older Tk builds, the app automatically switches to a standard `tkinter` compatibility UI instead of `CustomTkinter`.
- On this machine, the system Python at `/usr/bin/python3` is not usable for Tk apps. Use the local Python 3.12 + Tk 8.6 environment shown above.
- The app now falls back to file selection if drag and drop is unavailable on your Python or Tk build.
- If you still see startup or rendering issues on macOS, use a Python build linked against Tk 8.6 or newer.
- The app displays a compatibility note when it detects an older Tk runtime.

## Packaging

Build a standalone app with PyInstaller:

```bash
python -m pip install pyinstaller
pyinstaller main.spec
```

The repo includes `hook-tkinterdnd2.py` so the TkDnD runtime files are bundled with the packaged app.
