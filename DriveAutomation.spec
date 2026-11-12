# -*- mode: python ; coding: utf-8 -*-
"""One-directory build of the DriveAutomation app.

This is the payload used by DriveAutomation-Setup.exe: it starts instantly
(no temp extraction on every launch) and ships the Playwright Node driver so
the automation works on a machine that only has Google Chrome installed.

For a single-file portable build use DriveAutomationPortable.spec instead.
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

# Playwright ships a Node driver + JS package that must travel with the bundle.
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
    [],
    exclude_binaries=True,
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

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DriveAutomation",
)
