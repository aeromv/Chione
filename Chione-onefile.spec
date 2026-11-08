# -*- mode: python ; coding: utf-8 -*-
#
# Single-file build: one Chione.exe that runs with a double click.
# Build:  pyinstaller --workpath build/onefile Chione-onefile.spec
#
# Same false-positive precautions as Chione.spec (no UPX, version metadata,
# bootloader compiled from source in CI).

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
    a.binaries,
    a.datas,
    [],
    name='Chione',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
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
