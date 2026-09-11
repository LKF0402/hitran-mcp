# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, copy_metadata

datas = []
binaries = []
hiddenimports = ['hapi']
tmp_ret = collect_all('matplotlib')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# HAPI2 接入（官方 API 下载）：需要 hapi2 + sqlalchemy。
# 注意 hapi2.opacity.lbl 会无条件 import numba 版不透明度模块，
# 因此 numba / llvmlite 不能再排除（打包体积相应增加）。
# 注意：pyparsing 必须显式收集 —— hapi2.utils.__init__ 会 `from .formula import *`，
# 而 formula.py 顶层 `from pyparsing import ...`，PyInstaller 的静态分析追不到这条链。
for _pkg in ('sqlalchemy', 'hapi2', 'pyparsing'):
    _tmp = collect_all(_pkg)
    datas += _tmp[0]; binaries += _tmp[1]; hiddenimports += _tmp[2]

# 打入 dist-info，让 importlib.metadata.version() 在打包态可用 ——
# 这样能在**不真正 import** numba 的前提下报告版本号。
for _pkg in ('numba', 'llvmlite', 'sqlalchemy'):
    try:
        datas += copy_metadata(_pkg)
    except Exception:
        pass


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
              # 注意：numba / llvmlite 不可排除 —— HAPI2 的 opacity 子模块会
              # 无条件 import 它们（hapi2/opacity/lbl/__init__.py）。
              'jedi', 'IPython',            # 自动补全/交互环境，不需要
              'cryptography',               # 加密库，urllib 不需要
              'zmq',                        # ZeroMQ 消息队列，不需要
              'win32com', 'win32', 'pythonwin', 'pywin32_system32',  # pywin32 组件，用 ctypes 替代
              'tkinter.test', 'test',       # 测试模块
              # 注意：unittest 不可排除 —— hapi2.provenance.libra2 顶层 import 它，
              # 排除会让 `import hapi2` 在打包态抛 ModuleNotFoundError。
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
