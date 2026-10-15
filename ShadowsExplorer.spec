# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build for Shadows File Explorer.

    pip install pyinstaller
    pyinstaller ShadowsExplorer.spec

The app ends up in dist/ShadowsExplorer/ (on macOS also as
dist/Shadows Explorer.app). It is a folder build, not a single file: a
single-file exe unpacks all of Qt to a temporary folder on every launch,
which adds seconds to start-up.

Everything in resources/ (such as the start-up splash video) is bundled as
resources/ next to the code; at run time it is found under sys._MEIPASS.
"""
import os
import re
import sys

ROOT = os.path.abspath(SPECPATH)
NAME = "ShadowsExplorer"

with open(os.path.join(ROOT, "shadows_explorer", "__init__.py"), encoding="utf-8") as f:
    VERSION = re.search(r'__version__\s*=\s*["\']([^"\']+)', f.read()).group(1)

datas = []
if os.path.isdir(os.path.join(ROOT, "resources")):
    datas.append((os.path.join(ROOT, "resources"), "resources"))

# Optional icon for the exe and the macOS app, used when present
ICON = os.path.join(ROOT, "resources", "icons", "app.icns" if sys.platform == "darwin" else "app.ico")
if not os.path.exists(ICON):
    ICON = None

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Loaded on first use, or only when installed; listed so they are bundled
        "PyQt6.QtPdf",
        "PyQt6.QtMultimedia",  # Splash video
        "PyQt6.QtMultimediaWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Not used; keeps the bundle smaller. Pygments' image formatter would
        # otherwise pull in Pillow and NumPy when they are installed.
        "tkinter",
        "PIL",
        "numpy",
        "charset_normalizer",
        "PyQt6.QtQml",
        "PyQt6.QtQuick",
        "PyQt6.QtQuick3D",
        "PyQt6.QtQuickWidgets",
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtDesigner",
        "PyQt6.Qt3DCore",
        "PyQt6.QtBluetooth",
        "PyQt6.QtSensors",
        "PyQt6.QtSerialPort",
        "PyQt6.QtTest",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-packed Qt libraries load slower and can trip antivirus
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Shadows Explorer.app",
        icon=ICON,
        bundle_identifier="com.shadowsexplorer.app",
        version=VERSION,
        info_plist={"NSHighResolutionCapable": True},
    )
