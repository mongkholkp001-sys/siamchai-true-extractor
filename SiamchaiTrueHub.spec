# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all

ROOT_DIR = os.path.dirname(os.path.abspath(SPEC)) if 'SPEC' in locals() else r"C:\Users\comk25\.gemini\antigravity\scratch\siamchai_true_hub"

datas = [
    (os.path.join(ROOT_DIR, 'static'), 'static'),
    (os.path.join(ROOT_DIR, 'data'), 'data'),
]
binaries = []
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'fastapi.staticfiles',
    'fastapi.middleware.cors',
    'starlette.routing',
    'pydantic',
    'openpyxl',
    'pandas',
    'multipart',
    'python_multipart',
    'PIL',
    'requests',
    'websockets',
    'backend.license_manager',
    'backend.browser_factory',
    'webdriver_manager',
    'webdriver_manager.chrome',
    'webdriver_manager.microsoft',
]

# Collect all resources from selenium & uvicorn to ensure nothing is missed
for pkg in ['selenium', 'uvicorn', 'fastapi', 'webdriver_manager']:
    tmp_datas, tmp_binaries, tmp_hidden = collect_all(pkg)
    datas.extend(tmp_datas)
    binaries.extend(tmp_binaries)
    hiddenimports.extend(tmp_hidden)

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'torch', 'cv2', 'pytest'],
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
    name='SiamchaiTrueHub',
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
