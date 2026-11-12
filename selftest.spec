# -*- mode: python ; coding: utf-8 -*-
"""Frozen-build smoke test: verifies the Excel report + parsing in a bundle."""
import os

from PyInstaller.utils.hooks import collect_all

ROOT = os.path.dirname(os.path.abspath(SPEC))

datas = []
binaries = []
hiddenimports = []
d, b, h = collect_all("playwright")
datas += d
binaries += b
hiddenimports += h

a = Analysis(
    ["tools/selftest_playwright.py"],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="selftest", console=True)
