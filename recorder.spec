# -*- mode: python ; coding: utf-8 -*-
import os

# Build a simple binaries list
binaries_list = []

# Add bash binary if it exists
if os.path.exists('/bin/bash'):
    binaries_list.append(('/bin/bash', 'bin'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries_list,
    datas=[],
    hiddenimports=[
        'subprocess',
        'shlex',
        'threading',
        'signal',
        'os',
        'sys'
    ],
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
    name='recorder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)