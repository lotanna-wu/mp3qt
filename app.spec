# -*- mode: python ; coding: utf-8 -*-

import os

project_root = os.path.abspath(os.getcwd())
src_root = os.path.join(project_root, "src")

a = Analysis(
    [os.path.join(src_root, "main.py")],
    pathex=[src_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, "assets", "mp3-logo.png"), "assets"),
        (os.path.join(project_root, "themes"), "themes"),
    ],
    hiddenimports=[
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "pygame",
        "yt_dlp",
        "mutagen",
        "PIL",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="mp3-player",
    icon=os.path.join(project_root, "assets", "mp3-logo.png"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="mp3-player",
)
