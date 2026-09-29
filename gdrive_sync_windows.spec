# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets')]
binaries = []
hiddenimports = [
    'gdrive_sync',
    'gdrive_sync.auth',
    'gdrive_sync.auth.oauth',
    'gdrive_sync.auth.token_storage',
    'gdrive_sync.config',
    'gdrive_sync.database',
    'gdrive_sync.database.manager',
    'gdrive_sync.database.models',
    'gdrive_sync.database.schema',
    'gdrive_sync.drive',
    'gdrive_sync.drive.client',
    'gdrive_sync.engine',
    'gdrive_sync.engine.poller',
    'gdrive_sync.engine.queue',
    'gdrive_sync.engine.reconciler',
    'gdrive_sync.engine.sync_service',
    'gdrive_sync.engine.utils',
    'gdrive_sync.engine.watcher',
    'gdrive_sync.integrations',
    'gdrive_sync.integrations.autostart',
    'gdrive_sync.ui',
    'gdrive_sync.ui.activity_dialog',
    'gdrive_sync.ui.icons',
    'gdrive_sync.ui.preferences_dialog',
    'gdrive_sync.ui.selective_sync_dialog',
    'gdrive_sync.ui.tray',
    'watchdog',
    'keyring',
    'keyring.backends',
    'keyring.backends.Windows',
    'googleapiclient',
    'google_auth_oauthlib',
]

tmp_ret = collect_all('googleapiclient')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pytest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MyGDriveSync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/gdrive-sync.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MyGDriveSync',
)
