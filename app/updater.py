# -*- coding: utf-8 -*-
"""HitranLab 自动更新安全原语（纯标准库，便于离线单测）。

设计目标：
- 更新包 URL 只能指向本仓库的 GitHub Release，拒绝任意 https 主机；
- 下载后必须校验 GitHub API 提供的 SHA-256 摘要；
- 解压时拒绝绝对路径、`..`、符号链接、加密条目与超限 zip（防 zip slip / zip bomb）；
- 解压后只允许发布白名单中的顶层条目。
"""
from __future__ import annotations

import hashlib
import hmac
import re
import shutil
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

REPO = "LKF0402/hitran-mcp"
UPDATE_HOST = "github.com"
UPDATE_ASSET = "HitranLab-windows-x64.zip"
MAX_UPDATE_BYTES = 300 * 1024 * 1024          # 单包上限 300 MB
MAX_EXTRACT_BYTES = 700 * 1024 * 1024         # 解压总量上限 700 MB
MAX_ENTRIES = 20_000
EXE_NAME = "HitranLab.exe"
ALLOWED_TOP_LEVEL = {EXE_NAME, "_internal"}


def release_asset_url(tag, asset=UPDATE_ASSET):
    """构造固定仓库 + 固定资产名的 Release 下载地址；tag 仅允许版本号字符。"""
    tag = str(tag or "").strip()
    if not re.fullmatch(r"v?\d+(?:\.\d+){1,3}(?:[-+._A-Za-z0-9]*)?", tag):
        raise ValueError(f"非法 Release tag: {tag!r}")
    asset = Path(str(asset or UPDATE_ASSET)).name
    if asset != UPDATE_ASSET:
        raise ValueError(f"非法更新资产名: {asset!r}")
    return f"https://{UPDATE_HOST}/{REPO}/releases/download/{tag}/{asset}"


def validate_update_url(url):
    """只允许本仓库 GitHub Release 的 https 地址。"""
    p = urlsplit(str(url or ""))
    if p.scheme.lower() != "https":
        raise ValueError("更新包地址不是 https")
    if (p.hostname or "").lower() != UPDATE_HOST:
        raise ValueError(f"更新包主机不在白名单: {p.hostname!r}")
    if not p.path.startswith(f"/{REPO}/releases/download/"):
        raise ValueError(f"更新包路径不在本仓库 Release: {p.path!r}")
    if ".." in p.path.split("/"):
        raise ValueError("更新包地址含路径穿越")
    if p.query or p.fragment:
        raise ValueError("更新包地址不应带 query/fragment")
    return True


def sha256_file(path, chunk_size=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path, expected):
    """校验文件 SHA-256；expected 支持 `sha256:<hex>` 或裸 hex。"""
    digest = str(expected or "").strip().lower()
    if digest.startswith("sha256:"):
        digest = digest[7:]
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("更新包缺少合法的 SHA-256 摘要")
    actual = sha256_file(path)
    if not hmac.compare_digest(actual, digest):
        raise ValueError("更新包 SHA-256 校验失败")
    return actual


def _member_name(name):
    """把 zip 条目名规范化为相对路径；拒绝绝对路径、盘符与 `..`。"""
    raw = str(name or "").replace("\\", "/")
    if not raw or raw.startswith("/"):
        raise ValueError(f"非法 zip 条目: {name!r}")
    if re.match(r"^[A-Za-z]:", raw):
        raise ValueError(f"非法 zip 条目（盘符）: {name!r}")
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise ValueError(f"非法 zip 条目（路径穿越）: {name!r}")
    if not parts:
        raise ValueError(f"非法 zip 条目（空路径）: {name!r}")
    return Path(*parts)


def safe_extract_zip(zip_path, dest, max_total=MAX_EXTRACT_BYTES, max_entries=MAX_ENTRIES):
    """安全解压到 dest；返回解压后的文件数。失败抛 ValueError。"""
    dest = Path(dest).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    files = 0
    with zipfile.ZipFile(zip_path) as zf:
        infos = zf.infolist()
        if len(infos) > max_entries:
            raise ValueError(f"zip 条目过多: {len(infos)} > {max_entries}")
        for info in infos:
            name = _member_name(info.filename)
            target = (dest / name).resolve()
            if not target.is_relative_to(dest):
                raise ValueError(f"zip 条目越界: {info.filename!r}")
            if info.flag_bits & 0x1:
                raise ValueError(f"zip 含加密条目: {info.filename!r}")
            mode = (info.external_attr >> 16) & 0xF000
            if mode == 0xA000:
                raise ValueError(f"zip 含符号链接: {info.filename!r}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            total += int(info.file_size)
            if total > max_total:
                raise ValueError(f"zip 解压总量超限: > {max_total} 字节")
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "xb") as out:
                shutil.copyfileobj(src, out, length=1 << 20)
            files += 1
    return files


def validate_update_layout(root):
    """更新包解压目录只允许 exe 与 _internal，且 exe 必须存在。"""
    root = Path(root)
    if not (root / EXE_NAME).is_file():
        raise ValueError(f"更新包结构不符合预期：缺少 {EXE_NAME}")
    extra = sorted(p.name for p in root.iterdir() if p.name not in ALLOWED_TOP_LEVEL)
    if extra:
        raise ValueError(f"更新包含白名单外条目: {extra}")
    return root
