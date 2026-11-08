# -*- mode: python ; coding: utf-8 -*-
#
# Build:  pyinstaller Chione.spec
#
# Choices made to avoid antivirus false positives:
#   * one-folder build (no self-extracting one-file exe)
#   * UPX compression disabled (packed executables are a classic AV trigger)
#   * version resource with real metadata (version_info.txt)
#   * CI builds the PyInstaller bootloader from source, so the exe does not
#     share the stock bootloader signature that malware also uses

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[],
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
    name='Chione',
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
    icon=['assets\\icon.ico'],
    manifest='chione.manifest',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Chione',
)
