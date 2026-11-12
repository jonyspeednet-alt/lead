# -*- mode: python ; coding: utf-8 -*-
"""Single-file portable build of the DriveAutomation app.

Produces dist/DriveAutomation.exe - one self-contained file that can be
copied to any Windows PC and run directly (no installation). Note that a
one-file bundle re-extracts to a temp folder on every launch, so the
installed (one-directory) build starts noticeably faster.
"""
import os

import playwright
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(os.path.abspath(SPEC))
ICON = os.path.join(ROOT, "assets", "DriveAutomation.ico")
VERSION = os.path.join(ROOT, "version_info.txt")

datas = []
binaries = []
hiddenimports = []

d, b, h = collect_all("playwright")
datas += d
binaries += b
hiddenimports += h

driver_dir = os.path.join(os.path.dirname(playwright.__file__), "driver")
datas += [(driver_dir, os.path.join("playwright", "driver"))]

a = Analysis(
    ["gmail_drive_login.py"],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DriveAutomation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
    version=VERSION,
)
