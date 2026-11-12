"""Build the DriveAutomation installer chain.

1. Zip the one-directory app build  -> payload for the setup exe
2. Build the uninstaller executable  -> shipped inside the install folder
3. Build DriveAutomation-Setup.exe  -> user-facing installer

Run:  python tools/build_installer.py
"""
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "dist", "DriveAutomation")
PAYLOAD_DIR = os.path.join(ROOT, "build", "payload")
PAYLOAD_ZIP = os.path.join(PAYLOAD_DIR, "payload.zip")
UNINSTALL_DIST = os.path.join(ROOT, "dist_uninstall")
UNINSTALL_WORK = os.path.join(ROOT, "build_uninstall")
SETUP_DIST = os.path.join(ROOT, "release")
SETUP_WORK = os.path.join(ROOT, "build_setup")
ICON = os.path.join(ROOT, "assets", "DriveAutomation.ico")


def run(args):
    print("$", " ".join(args), flush=True)
    result = subprocess.run(args, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(args)}")


def make_payload():
    if not os.path.isdir(APP_DIR):
        raise SystemExit(f"app build missing: {APP_DIR} (run PyInstaller DriveAutomation.spec first)")
    os.makedirs(PAYLOAD_DIR, exist_ok=True)
    if os.path.exists(PAYLOAD_ZIP):
        os.remove(PAYLOAD_ZIP)
    count = 0
    with zipfile.ZipFile(PAYLOAD_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for base, _dirs, files in os.walk(APP_DIR):
            for name in files:
                full = os.path.join(base, name)
                zf.write(full, os.path.relpath(full, APP_DIR))
                count += 1
    size = os.path.getsize(PAYLOAD_ZIP)
    print(f"payload: {count} files -> {PAYLOAD_ZIP} ({size/1024/1024:.1f} MB)", flush=True)


def build_uninstaller():
    run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", "DriveAutomation_Uninstall",
        "--icon", ICON,
        "--version-file", os.path.join(ROOT, "version_info_uninstall.txt"),
        "--distpath", UNINSTALL_DIST,
        "--workpath", UNINSTALL_WORK,
        "--specpath", UNINSTALL_WORK,
        os.path.join("tools", "uninstaller.py"),
    ])


def build_setup():
    run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", "DriveAutomation-Setup",
        "--icon", ICON,
        "--version-file", os.path.join(ROOT, "version_info_setup.txt"),
        f"--add-data={PAYLOAD_ZIP}:.",
        f"--add-data={os.path.join(UNINSTALL_DIST, 'DriveAutomation_Uninstall.exe')}:uninstaller",
        "--distpath", SETUP_DIST,
        "--workpath", SETUP_WORK,
        "--specpath", SETUP_WORK,
        os.path.join("tools", "setup_installer.py"),
    ])


def main():
    make_payload()
    build_uninstaller()
    build_setup()
    setup = os.path.join(SETUP_DIST, "DriveAutomation-Setup.exe")
    print(f"\nSetup ready: {setup} ({os.path.getsize(setup)/1024/1024:.1f} MB)")


if __name__ == "__main__":
    main()
