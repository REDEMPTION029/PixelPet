"""Reproducible Windows one-file build using the current Python interpreter."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "PixelPet-v0.7.0"


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts/build_icon.py")], cwd=ROOT, check=True)
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", APP_NAME, "--icon", str(ROOT / "assets/app.ico"),
            "--version-file", str(ROOT / "scripts/version_info.txt"),
            "--distpath", str(ROOT / "release"), "--workpath", str(ROOT / "build/pyinstaller"),
            "--specpath", str(ROOT / "build"), "--exclude-module", "PyQt6", "--exclude-module", "tkinter"]
    for action in ("idle", "walk", "headClick", "bodyClick", "sleep", "happy", "sitTransition", "adjustGlasses", "peek"):
        args += ["--add-data", f"{ROOT / 'assets' / action}:assets/{action}"]
    for name in ("frame_meta.json", "app.ico", "companion.json"):
        args += ["--add-data", f"{ROOT / 'assets' / name}:assets"]
    args.append(str(ROOT / "pet.py"))
    subprocess.run(args, cwd=ROOT, check=True)
    print(f"Built {ROOT / 'release' / (APP_NAME + '.exe')}")


if __name__ == "__main__":
    main()
