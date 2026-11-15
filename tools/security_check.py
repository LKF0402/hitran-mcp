#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前敏感信息/安全基线检查（纯标准库，CI 可离线运行）。

检查项：
1. Git 跟踪文件中不得出现密钥、Token、私钥、真实用户目录或邮箱；
2. Git 历史中不得出现敏感文件名或当前 HITRAN API key 明文；
3. Python 源码不得出现 shell=True / os.system / eval / exec / extractall 等危险调用；
4. requirements.txt 直接依赖必须锁定版本；
5. Release zip（若存在）顶层只允许 exe/_internal，且不含缓存、key、config、日志；
6. 报告本机敏感文件（key/config/log）是否存在，但只作为提示，不判失败。

用法：python tools/security_check.py
退出码 0 = 通过；1 = 有阻断项。
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".spec", ".toml",
                 ".cfg", ".ini", ".bat", ".ps1", ".sh"}
SECRET_PATTERNS = {
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "aws_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "google_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
}
PII_PATTERNS = {
    "windows_user_path": re.compile(r"[A-Za-z]:\\Users\\(?![<你])[^\\\s\"']+", re.I),
    "unix_user_path": re.compile(r"/Users/(?![<你])[^/\s\"']+"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}
SENSITIVE_NAME = re.compile(
    r"(^|/)(config\.json|hitran_api_key\.txt|local|hapi2\.db|"
    r"\.env(?:\.\*)?|.*\.(?:pem|key|p12|pfx)|id_rsa.*)$", re.I)
RELEASE_SENSITIVE = re.compile(
    r"(^|/)(Hitran_Data|config\.json|hitran_api_key\.txt|local|"
    r"[^/]*\.log|_update)(/|$)", re.I)
DANGEROUS_CALLS = {"eval", "exec", "compile", "__import__"}


def run(args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def fail(issues, label, kind, detail):
    issues.append({"source": label, "kind": kind, "detail": detail})


def read_key():
    for p in (ROOT / "Hitran_Data" / "hitran_api_key.txt",
              ROOT / "tools" / "hitran_api_key.txt"):
        if p.is_file():
            return p.read_text(encoding="utf-8", errors="ignore").strip()
    try:
        cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
        return str(cfg.get("api_key") or "").strip()
    except Exception:
        return ""


def scan_text(issues, label, text, key):
    if key and len(key) >= 8 and key in text:
        fail(issues, label, "api_key_value", "HITRAN API key value outside its key file")
    for name, pat in SECRET_PATTERNS.items():
        if pat.search(text):
            fail(issues, label, name, "credential-like token pattern")
    for name, pat in PII_PATTERNS.items():
        for m in pat.finditer(text):
            s = m.group(0)
            # 文档里的通用占位符不是个人信息
            if any(x in s for x in ("<build-user>", "<本机用户名>", "<构建者>", "你")):
                continue
            fail(issues, label, name, s[:120])


def scan_python(issues, rel, path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception as e:
        fail(issues, rel, "parse_error", f"{type(e).__name__}: {e}")
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else (
            fn.attr if isinstance(fn, ast.Attribute) else "")
        if isinstance(fn, ast.Name) and name in DANGEROUS_CALLS:
            fail(issues, rel, "dangerous_call", f"{name}() at line {node.lineno}")
        if name == "system" and isinstance(fn, ast.Attribute) and \
                isinstance(fn.value, ast.Name) and fn.value.id == "os":
            fail(issues, rel, "dangerous_call", f"os.system() at line {node.lineno}")
        if name == "extractall":
            fail(issues, rel, "zip_extractall", f"extractall() at line {node.lineno}")
        for kw in node.keywords:
            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                fail(issues, rel, "dangerous_call", f"shell=True at line {node.lineno}")
            if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                fail(issues, rel, "tls_verify_disabled", f"verify=False at line {node.lineno}")


def check_tracked(issues, key):
    r = run(["git", "ls-files"])
    tracked = [x for x in r.stdout.splitlines() if x.strip()]
    for rel in tracked:
        p = ROOT / rel
        if SENSITIVE_NAME.search(rel):
            fail(issues, rel, "sensitive_filename", "sensitive file is tracked")
        if p.suffix.lower() in TEXT_SUFFIXES and p.is_file() and p.stat().st_size < 5_000_000:
            scan_text(issues, f"tracked:{rel}", p.read_text(encoding="utf-8", errors="replace"), key)
        if p.suffix.lower() == ".py" and p.is_file():
            scan_python(issues, f"tracked:{rel}", p)
    return tracked


def check_requirements(issues):
    p = ROOT / "requirements.txt"
    if not p.is_file():
        fail(issues, "requirements.txt", "missing", "requirements.txt not found")
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "==" not in s:
            fail(issues, "requirements.txt", "unpinned_dependency", s)


def check_ignore(issues):
    p = ROOT / ".gitignore"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    for pattern in ("Hitran_Data/", "tmp/", "hitran_prefs.json", "_update/",
                    "hitran_api_key.txt", "config.json", "local", "dist/", "*.log"):
        if pattern not in text:
            fail(issues, ".gitignore", "missing_ignore", pattern)


def check_history(issues, key):
    r = run(["git", "log", "--all", "--name-only", "--pretty=format:"])
    hist_names = {x.strip() for x in r.stdout.splitlines() if x.strip()}
    bad = sorted(x for x in hist_names if SENSITIVE_NAME.search(x))
    for x in bad:
        fail(issues, "git-history", "sensitive_filename", x)
    if key and len(key) >= 8:
        r = run(["git", "log", "--all", "-S", key, "--oneline", "--"])
        if r.returncode == 0 and r.stdout.strip():
            fail(issues, "git-history", "api_key_value",
                 "key appears in history: " + ", ".join(r.stdout.splitlines()[:5]))


def check_release(issues, key):
    dist = ROOT / "dist"
    home = str(Path.home())
    builder_user = Path.home().name
    builder_markers = [home.encode("utf-8", "ignore")]
    if builder_user:
        builder_markers.append(f"C:\\Users\\{builder_user}".encode("utf-8", "ignore"))
    for z in sorted(dist.glob("*.zip")) if dist.is_dir() else []:
        try:
            with zipfile.ZipFile(z) as zf:
                names = zf.namelist()
                tops = {Path(n).parts[0] for n in names if n and not n.startswith("/")}
                allowed = {"HitranLab.exe", "_internal"}
                if not tops.issubset(allowed):
                    fail(issues, f"release:{z.name}", "unexpected_top_level", str(sorted(tops - allowed)))
                for n in names:
                    if RELEASE_SENSITIVE.search(n):
                        fail(issues, f"release:{z.name}", "sensitive_entry", n)
                if key and len(key) >= 8:
                    for n in names:
                        if n.endswith("/"):
                            continue
                        try:
                            data = zf.read(n)
                        except Exception:
                            continue
                        if key.encode("utf-8", errors="ignore") in data:
                            fail(issues, f"release:{z.name}", "api_key_value", n)
                        if any(marker in data for marker in builder_markers):
                            fail(issues, f"release:{z.name}", "builder_path", n)
        except Exception as e:
            fail(issues, f"release:{z.name}", "zip_error", f"{type(e).__name__}: {e}")


def local_sensitive_report():
    out = []
    for rel in ("config.json", "Hitran_Data/hitran_api_key.txt",
                "Hitran_Data/error.log", "hitran_prefs.json", "local"):
        p = ROOT / rel
        if p.is_file():
            out.append({"path": rel, "bytes": p.stat().st_size, "ignored": True})
    return out


def main():
    issues = []
    key = read_key()
    tracked = check_tracked(issues, key)
    check_requirements(issues)
    check_ignore(issues)
    check_history(issues, key)
    check_release(issues, key)
    result = {
        "ok": not issues,
        "tracked_files": len(tracked),
        "api_key_in_scope": bool(key),
        "issues": issues,
        "local_sensitive_files": local_sensitive_report(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
