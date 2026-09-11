#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一键构建发布产物：打包 exe → 发布到 dist → 生成 zip → 校验一致性。

**为什么需要它**：发布时要交付两样东西 —— `dist/HitranLab/`（绿色目录）与
GitHub release 资产 `dist/HitranLab-windows-x64.zip`。这两步分开做时，zip 极易被
遗漏，导致"用户下载到的仍是旧版本"（本项目真实发生过：zip 停留在旧 exe）。
本脚本把两步绑定为原子操作，并在最后**校验 zip 内的 HitranLab.exe 与 dist 下的
exe 大小 + CRC32 完全一致**，不一致直接以非 0 退出 —— 从结构上消除"忘记重建 zip"。

用法::

    python tools/build_release.py              # 完整构建（打包 + 发布 + 自检 + zip + 校验）
    python tools/build_release.py --zip-only   # 只重建 zip（沿用现有 dist）
    python tools/build_release.py --no-selftest

退出码：0 = 成功；非 0 = 构建或校验失败（含"dist 被运行中的程序占用"）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path

# Windows 控制台默认 GBK 代码页，本脚本输出含中文，统一切到 UTF-8 并容错，
# 避免 UnicodeEncodeError 直接中断构建。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
APP_DIR = DIST / "HitranLab"
EXE = APP_DIR / "HitranLab.exe"
ZIP = DIST / "HitranLab-windows-x64.zip"
DIST_NEW = ROOT / "dist_new"
BUILD_NEW = ROOT / "build_new"
CACHE_BAK = ROOT / "tmp" / "_release_cache_bak"
SELFTEST_OUT = ROOT / "tmp" / "_release_selftest.json"


def log(msg: str) -> None:
    print(f"[release] {msg}", flush=True)


def die(msg: str, code: int = 1):
    print(f"[release] FAIL: {msg}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def read_version() -> str:
    src = (ROOT / "tools" / "hitran_mcp.py").read_text(encoding="utf-8")
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', src, re.M)
    if not m:
        die("无法从 tools/hitran_mcp.py 读取 VERSION")
    return m.group(1)


def git_dirty() -> bool:
    try:
        r = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return bool(r.stdout.strip())
    except Exception:
        return False


def git_head() -> str:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%h %s"], cwd=str(ROOT),
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return r.stdout.strip()
    except Exception:
        return "?"


# ───────────────────────── 构建 ─────────────────────────

def build_exe() -> None:
    log("PyInstaller 打包中（约 40 秒）…")
    code = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm",
         "--distpath", "dist_new", "--workpath", "build_new", "HitranLab.spec"],
        cwd=str(ROOT)).returncode
    if code != 0:
        die("PyInstaller 打包失败")
    if not (DIST_NEW / "HitranLab" / "HitranLab.exe").exists():
        die("打包产物缺失：dist_new/HitranLab/HitranLab.exe")


def publish() -> None:
    """用重命名方式原子替换 dist/HitranLab，并保留 exe 侧缓存与 API key。"""
    cache_src = APP_DIR / "Hitran_Data"
    if cache_src.exists():
        shutil.rmtree(CACHE_BAK, ignore_errors=True)
        CACHE_BAK.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(cache_src, CACHE_BAK)
        log(f"已备份 exe 侧缓存（含 API key）：{CACHE_BAK.name}")

    old = DIST / "_old_release"
    shutil.rmtree(old, ignore_errors=True)
    if APP_DIR.exists():
        try:
            APP_DIR.rename(old)
        except OSError as e:
            die(f"无法替换 dist\\HitranLab —— 多半是 HitranLab 正在运行占用了文件：{e}\n"
                f"          请关闭所有 HitranLab 窗口后重试。")
    (DIST_NEW / "HitranLab").rename(APP_DIR)

    if CACHE_BAK.exists():
        (APP_DIR / "Hitran_Data").mkdir(parents=True, exist_ok=True)
        for item in CACHE_BAK.iterdir():
            dst = APP_DIR / "Hitran_Data" / item.name
            try:
                if item.is_dir():
                    shutil.copytree(item, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dst)
            except OSError as e:
                log(f"[warn] 恢复缓存项失败（不影响运行）：{item.name}: {e}")

    shutil.rmtree(old, ignore_errors=True)
    shutil.rmtree(CACHE_BAK, ignore_errors=True)
    shutil.rmtree(DIST_NEW, ignore_errors=True)
    shutil.rmtree(BUILD_NEW, ignore_errors=True)
    log("已发布到 dist/HitranLab（缓存与 key 已恢复）")


def selftest(timeout: int = 150) -> None:
    """对打包后的 exe 跑无界面自检。

    注意：Windows GUI 子系统进程不会阻塞父进程，`subprocess.run` 会立刻返回，
    因此这里用"轮询输出文件"的方式等待结果。
    """
    SELFTEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    if SELFTEST_OUT.exists():
        SELFTEST_OUT.unlink()
    subprocess.Popen([str(EXE), "--selftest", str(SELFTEST_OUT)], cwd=str(APP_DIR))
    t0 = time.time()
    while time.time() - t0 < timeout:
        if SELFTEST_OUT.exists():
            break
        time.sleep(0.5)
    if not SELFTEST_OUT.exists():
        die(f"自检超时（{timeout}s）未产出结果")
    try:
        data = json.loads(SELFTEST_OUT.read_text(encoding="utf-8"))
    except Exception as e:
        die(f"自检输出无法解析：{e}")
    finally:
        SELFTEST_OUT.unlink(missing_ok=True)

    if "error" in data:
        die(f"自检报错：{data['error'][:400]}")
    st = data.get("apikey_status", {})
    peaks = data.get("top_peaks") or [{}]
    log(f"自检通过：{data.get('species_count')} 物种 / {data.get('nu_points')} 点 / "
        f"峰值 {peaks[0].get('peak_value')} / warnings={data.get('warnings')}")
    log(f"         下载引擎 = {st.get('download_engine')}；hapi2 = "
        f"{st.get('hapi2_available')}/{st.get('hapi2_enabled')}")


# ───────────────────────── zip ─────────────────────────

def make_zip() -> None:
    """把 dist/HitranLab 打成 zip（条目以该目录为根，与既有资产结构一致）。"""
    if not EXE.exists():
        die("dist/HitranLab/HitranLab.exe 不存在，无法打包 zip")
    tmp = ZIP.with_name(ZIP.name + ".tmp")
    tmp.unlink(missing_ok=True)
    n = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(APP_DIR.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(APP_DIR).as_posix())
                n += 1
    os.replace(tmp, ZIP)
    log(f"zip 已生成：{ZIP.name}（{n} 个条目，{ZIP.stat().st_size / 1e6:.1f} MB）")


def verify_zip() -> None:
    """校验 zip 内的 exe 与 dist 下的 exe 大小 + CRC32 完全一致。"""
    if not ZIP.exists():
        die("zip 不存在")
    disk = EXE.stat()
    crc_disk = 0
    with open(EXE, "rb") as f:
        while True:
            chunk = f.read(1 << 20)
            if not chunk:
                break
            crc_disk = zlib.crc32(chunk, crc_disk)
    crc_disk &= 0xFFFFFFFF

    with zipfile.ZipFile(ZIP) as z:
        try:
            info = z.getinfo("HitranLab.exe")
        except KeyError:
            die("zip 内找不到 HitranLab.exe，资产结构异常")
        if info.file_size != disk.st_size or (info.CRC & 0xFFFFFFFF) != crc_disk:
            die(f"zip 内的 exe 与 dist 下的不一致！"
                f"（zip {info.file_size} B / CRC {info.CRC & 0xFFFFFFFF:08x}，"
                f"dist {disk.st_size} B / CRC {crc_disk:08x}）\n"
                f"          → zip 是过期资产，请重跑本脚本。")
    zt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.mktime(info.date_time + (0, 0, -1))))
    log(f"OK 校验通过：zip 内 exe == dist 下 exe（{info.file_size} B，打包于 {zt}）")


# ───────────────────────── 主流程 ─────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="一键构建发布产物（打包 + zip + 校验）")
    ap.add_argument("--zip-only", action="store_true", help="只重建 zip，沿用现有 dist")
    ap.add_argument("--no-selftest", action="store_true", help="跳过分自检")
    args = ap.parse_args()

    ver = read_version()
    log(f"VERSION = {ver}    HEAD = {git_head()}")
    if git_dirty():
        log("[warn] 工作区有未提交改动 —— 请确认这些改动确实要进产物")

    if not args.zip_only:
        build_exe()
        publish()
        if not args.no_selftest:
            selftest()
    else:
        log("--zip-only：沿用现有 dist/HitranLab")

    make_zip()
    verify_zip()

    log("")
    log(f"完成。发布资产：{ZIP.relative_to(ROOT)}")
    log("发布前请确认：")
    log(f"  1) tag 与 VERSION 一致（当前 VERSION = {ver}）")
    log(f"  2) git tag 后把上面这个 zip 上传为 release 资产")
    return 0


if __name__ == "__main__":
    sys.exit(main())
