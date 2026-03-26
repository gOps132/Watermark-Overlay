#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CX_WINE_BIN = Path(
    "/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/CrossOver-Hosted Application/wine"
)
PYINSTALLER_CONFIG_DIR = REPO_ROOT / ".pyinstaller"
MACOS_SPEC = REPO_ROOT / "packaging" / "macos.spec"
WINDOWS_SPEC = REPO_ROOT / "packaging" / "windows.spec"
REQUIREMENTS_FILE = REPO_ROOT / "requirements.txt"


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, cwd=REPO_ROOT, env=env)


def check(cmd: list[str], *, env: dict[str, str] | None = None) -> bool:
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def candidate_pythons() -> list[str]:
    candidates: list[str] = []

    env_python = os.environ.get("PYTHON_BIN")
    if env_python:
        candidates.append(env_python)

    local_candidates = [
        REPO_ROOT / ".venv-local312-uv" / "bin" / "python",
        REPO_ROOT / ".venv-local312" / "bin" / "python",
        REPO_ROOT / ".venv-local" / "bin" / "python",
    ]
    candidates.extend(str(path) for path in local_candidates)

    if sys.executable:
        candidates.append(sys.executable)

    python3 = shutil.which("python3")
    if python3:
        candidates.append(python3)

    deduped: list[str] = []
    for candidate in candidates:
        if candidate not in deduped:
            deduped.append(candidate)
    return deduped


def resolve_python(explicit_python: str | None) -> str:
    if explicit_python:
        if not check([explicit_python, "-c", "import sys"]):
            raise SystemExit(f"Python interpreter is not usable: {explicit_python}")
        return explicit_python

    for candidate in candidate_pythons():
        if check([candidate, "-c", "import sys"]):
            return candidate

    raise SystemExit(
        "No usable Python interpreter found. "
        "Pass --python or set PYTHON_BIN to a working environment."
    )


def bootstrap_pip(python_bin: str) -> None:
    if check([python_bin, "-m", "pip", "--version"]):
        return

    print(f"Bootstrapping pip for {python_bin}", flush=True)
    run([python_bin, "-m", "ensurepip", "--upgrade"])


def ensure_local_build_dependencies(python_bin: str) -> None:
    imports = "import PyInstaller, customtkinter, PIL, tkinterdnd2"
    if check([python_bin, "-c", imports]):
        return

    bootstrap_pip(python_bin)
    print(f"Installing local build dependencies for {python_bin}", flush=True)
    run([python_bin, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE), "pyinstaller"])


def ensure_windows_build_dependencies(
    cx_wine_bin: str, cx_bottle: str, win_python: str, pyinstaller_config_dir: str
) -> None:
    imports = "import PyInstaller, customtkinter, PIL, tkinterdnd2"
    probe_cmd = [
        cx_wine_bin,
        "--bottle",
        cx_bottle,
        "--workdir",
        str(REPO_ROOT),
        "--env",
        f"PYINSTALLER_CONFIG_DIR={pyinstaller_config_dir}",
        win_python,
        "-c",
        imports,
    ]
    if check(probe_cmd):
        return

    print(f"Installing Windows build dependencies in CrossOver bottle '{cx_bottle}'", flush=True)
    run(
        [
            cx_wine_bin,
            "--bottle",
            cx_bottle,
            "--workdir",
            str(REPO_ROOT),
            "--env",
            f"PYINSTALLER_CONFIG_DIR={pyinstaller_config_dir}",
            win_python,
            "-m",
            "pip",
            "install",
            "-r",
            "requirements.txt",
            "pyinstaller",
        ]
    )


def repo_path_to_windows(path: Path) -> str:
    return "Z:" + str(path).replace("/", "\\")


def ensure_windows_python_available(
    cx_wine_bin: str, cx_bottle: str, win_python: str, pyinstaller_config_dir: str
) -> None:
    probe_cmd = [
        cx_wine_bin,
        "--bottle",
        cx_bottle,
        "--workdir",
        str(REPO_ROOT),
        "--env",
        f"PYINSTALLER_CONFIG_DIR={pyinstaller_config_dir}",
        win_python,
        "--version",
    ]
    if check(probe_cmd):
        return

    raise SystemExit(
        f"Windows Python executable '{win_python}' is not runnable in CrossOver bottle '{cx_bottle}'. "
        "Install Windows Python in that bottle first, or pass --win-python with the correct executable name."
    )


def build_macos(python_bin: str) -> None:
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(PYINSTALLER_CONFIG_DIR)

    ensure_local_build_dependencies(python_bin)

    print(f"Building macOS app with {python_bin}", flush=True)
    run(
        [
            python_bin,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(REPO_ROOT / "dist" / "macos"),
            "--workpath",
            str(REPO_ROOT / "build" / "macos"),
            str(MACOS_SPEC),
        ],
        env=env,
    )
    print(f"Build complete: {REPO_ROOT / 'dist' / 'macos' / 'Watermark Overlay.app'}", flush=True)


def build_windows_native(python_bin: str) -> None:
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(PYINSTALLER_CONFIG_DIR)

    ensure_local_build_dependencies(python_bin)

    print(f"Building Windows executable with {python_bin}", flush=True)
    run(
        [
            python_bin,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(REPO_ROOT / "dist" / "windows"),
            "--workpath",
            str(REPO_ROOT / "build" / "windows"),
            str(WINDOWS_SPEC),
        ],
        env=env,
    )
    print(f"Build complete: {REPO_ROOT / 'dist' / 'windows' / 'WatermarkOverlay.exe'}", flush=True)


def build_windows_crossover(cx_wine_bin: str, cx_bottle: str, win_python: str) -> None:
    if not Path(cx_wine_bin).is_file():
        raise SystemExit(f"CrossOver wine binary not found: {cx_wine_bin}")

    pyinstaller_config_dir = repo_path_to_windows(PYINSTALLER_CONFIG_DIR)
    ensure_windows_python_available(cx_wine_bin, cx_bottle, win_python, pyinstaller_config_dir)
    ensure_windows_build_dependencies(cx_wine_bin, cx_bottle, win_python, pyinstaller_config_dir)

    print(f"Building Windows executable from CrossOver bottle '{cx_bottle}'", flush=True)
    run(
        [
            cx_wine_bin,
            "--bottle",
            cx_bottle,
            "--workdir",
            str(REPO_ROOT),
            "--env",
            f"PYINSTALLER_CONFIG_DIR={pyinstaller_config_dir}",
            win_python,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            "dist/windows",
            "--workpath",
            "build/windows",
            "packaging/windows.spec",
        ]
    )
    print(f"Build complete: {REPO_ROOT / 'dist' / 'windows' / 'WatermarkOverlay.exe'}", flush=True)


def build_windows(python_bin: str | None, cx_wine_bin: str, cx_bottle: str | None, win_python: str) -> None:
    if os.name == "nt":
        build_windows_native(resolve_python(python_bin))
        return

    if not cx_bottle:
        raise SystemExit("--cx-bottle is required for the Windows build on non-Windows hosts")

    build_windows_crossover(cx_wine_bin, cx_bottle, win_python)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build package artifacts for this repo. "
            "Use 'macos' for the .app bundle, 'windows' for the .exe, "
            "or 'all' to build both on macOS."
        )
    )
    subparsers = parser.add_subparsers(dest="target", required=True)

    macos_parser = subparsers.add_parser(
        "macos",
        help="Build the macOS .app bundle",
        description="Build the unsigned macOS .app bundle with a local Python environment.",
    )
    macos_parser.add_argument("--python", help="Python interpreter to use for the macOS build")

    windows_parser = subparsers.add_parser(
        "windows",
        help="Build the Windows .exe",
        description=(
            "Build the Windows .exe. On Windows, this runs a native PyInstaller build. "
            "On non-Windows hosts, it uses CrossOver and requires --cx-bottle."
        ),
    )
    windows_parser.add_argument(
        "--cx-bottle",
        default=os.environ.get("CX_BOTTLE"),
        help="CrossOver bottle name for non-Windows hosts",
    )
    windows_parser.add_argument(
        "--cx-wine-bin",
        default=os.environ.get("CX_WINE_BIN", str(DEFAULT_CX_WINE_BIN)),
        help="Path to CrossOver's wine helper binary for non-Windows hosts",
    )
    windows_parser.add_argument(
        "--win-python",
        default=os.environ.get("WIN_PYTHON", "python.exe"),
        help=(
            "Windows Python executable inside the CrossOver bottle. "
            "Prefer the full Windows path if python.exe is not on PATH."
        ),
    )
    windows_parser.add_argument(
        "--python",
        help="Native Python interpreter to use when running on Windows",
    )

    all_parser = subparsers.add_parser(
        "all",
        help="Build both macOS and Windows artifacts on macOS",
        description=(
            "Build both artifacts from macOS: the native macOS .app and the "
            "CrossOver-based Windows .exe."
        ),
    )
    all_parser.add_argument("--python", help="Python interpreter to use for the macOS build")
    all_parser.add_argument(
        "--cx-bottle",
        default=os.environ.get("CX_BOTTLE"),
        help="CrossOver bottle name for the Windows build",
    )
    all_parser.add_argument(
        "--cx-wine-bin",
        default=os.environ.get("CX_WINE_BIN", str(DEFAULT_CX_WINE_BIN)),
        help="Path to CrossOver's wine helper binary",
    )
    all_parser.add_argument(
        "--win-python",
        default=os.environ.get("WIN_PYTHON", "python.exe"),
        help="Windows Python executable inside the CrossOver bottle",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.target == "macos":
        build_macos(resolve_python(args.python))
        return 0

    if args.target == "windows":
        build_windows(args.python, args.cx_wine_bin, args.cx_bottle, args.win_python)
        return 0

    if os.name == "nt":
        raise SystemExit("The 'all' build is only supported on macOS because it includes the macOS app build")

    if not args.cx_bottle:
        raise SystemExit("--cx-bottle is required for the 'all' build")

    build_macos(resolve_python(args.python))
    build_windows(args.cx_wine_bin, args.cx_bottle, args.win_python)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
