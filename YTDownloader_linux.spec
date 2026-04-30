# -*- mode: python ; coding: utf-8 -*-
# YTDownloader_linux PyInstaller spec
# Generated for: Linux x86_64 / AppImage

import os
import sys
sys.path.insert(0, '.')
from pyinstaller_common import make_spec_config

SPEC_DIR = os.path.abspath('.')

cfg = make_spec_config(
    spec_dir=SPEC_DIR,
    entry_script='app.py',
    pathex=[SPEC_DIR],
)

a = Analysis(
    **cfg['analysis'],
)

# Prevent library conflicts with host GPU drivers by stripping bundled C++ stdlibs
a.binaries = [x for x in a.binaries if not x[0].startswith('libstdc++.so') and not x[0].startswith('libgcc_s.so')]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    **cfg['exe'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    **cfg['collect'],
)
