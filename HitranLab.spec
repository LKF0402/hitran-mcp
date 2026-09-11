# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = ['hapi']
tmp_ret = collect_all('matplotlib')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app/hitran_app.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pandas', 'lxml', 'scipy',
              # 以下依赖未被实际使用，仅为间接依赖，排除以减小体积
              'numba', 'llvmlite',          # Numba 仅做能力检测，未实际使用
              'jedi', 'IPython',            # 自动补全/交互环境，不需要
              'cryptography',               # 加密库，urllib 不需要
              'zmq',                        # ZeroMQ 消息队列，不需要
              'win32com', 'win32', 'pythonwin', 'pywin32_system32',  # pywin32 组件，用 ctypes 替代
              'tkinter.test', 'test',       # 测试模块
              'unittest',                   # 单元测试框架
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
    name='HitranLab',
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
    icon=['app/hitranlab.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HitranLab',
)
