# -*- mode: python ; coding: utf-8 -*-
import os
import sys

_SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
if _SPEC_DIR not in sys.path:
    sys.path.insert(0, _SPEC_DIR)

from pyinstaller_common import make_spec_config


_spec = make_spec_config(_SPEC_DIR, "main.py", [_SPEC_DIR])
if sys.platform == 'darwin':
    _spec["exe"]["icon"] = None

a = Analysis(**_spec["analysis"])
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    **_spec["exe"],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    **_spec["collect"],
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='YTDownloaderPro.app',
        icon=None,
        bundle_identifier='com.tahsan.ytdownloaderpro',
    )
