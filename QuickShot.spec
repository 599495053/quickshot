# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

spec_dir = Path(globals().get('SPECPATH', Path.cwd())).resolve()
sys.path.insert(0, str(spec_dir))

from build_config import EXCLUDED_MODULES, filter_binaries


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[
        'winreg',
        'quickshot',
        'quickshot.config',
        'quickshot.dialogs',
        'quickshot.history',
        'quickshot.hotkey',
        'quickshot.hotkey_util',
        'quickshot.manager',
        'quickshot._manager_delegates',
        'quickshot._manager_history',
        'quickshot._manager_pin',
        'quickshot.ocr',
        'quickshot.overlay',
        'quickshot.pin',
        'quickshot.pipeline',
        'quickshot.preview_scaler',
        'quickshot.screenshot',
        'quickshot.secrets',
        'quickshot.settings',
        'quickshot.theme',
        'quickshot.translator',
        'quickshot.ui',
        'quickshot.uploader',
        'quickshot.utils',
        'quickshot.main',
        'keyring',
        'keyring.backends',
        'keyring.backends.Windows',
        'keyring.backends.fail',
        'keyring.backends.null',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_MODULES,
    noarchive=False,
    optimize=1,
)
a.binaries = filter_binaries(a.binaries)
a.datas = filter_binaries(a.datas)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='QuickShot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
