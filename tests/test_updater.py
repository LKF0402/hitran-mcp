# -*- coding: utf-8 -*-
"""自动更新安全原语的离线回归测试（不联网、不触碰真实安装目录）。"""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from app.updater import (
    ALLOWED_TOP_LEVEL,
    release_asset_url,
    safe_extract_zip,
    sha256_file,
    validate_update_layout,
    validate_update_url,
    verify_sha256,
)


class UpdateUrlTests(unittest.TestCase):
    def test_accepts_repo_release(self):
        url = release_asset_url("v1.6.1")
        self.assertEqual(
            url, "https://github.com/LKF0402/hitran-mcp/releases/download/v1.6.1/"
                 "HitranLink-windows-x64.zip")
        self.assertTrue(validate_update_url(url))

    def test_rejects_non_https_or_foreign_host(self):
        for bad in (
            "http://github.com/LKF0402/hitran-mcp/releases/download/v1.6.1/x.zip",
            "https://evil.example/LKF0402/hitran-mcp/releases/download/v1.6.1/x.zip",
            "https://github.com/other/repo/releases/download/v1.6.1/x.zip",
            "https://github.com/LKF0402/hitran-mcp/releases/download/v1.6.1/x.zip?x=1",
            "https://github.com/LKF0402/hitran-mcp/releases/download/../evil",
        ):
            with self.assertRaises(ValueError):
                validate_update_url(bad)

    def test_rejects_malformed_tag(self):
        for bad in ("v1.6.1/../x", "v1.6.1?x=1", "v1.6.1\\x", "latest"):
            with self.assertRaises(ValueError):
                release_asset_url(bad)


class DigestTests(unittest.TestCase):
    def test_sha256_and_verify(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.bin"
            p.write_bytes(b"hitranlink")
            digest = hashlib.sha256(b"hitranlink").hexdigest()
            self.assertEqual(sha256_file(p), digest)
            self.assertEqual(verify_sha256(p, digest), digest)
            self.assertEqual(verify_sha256(p, "sha256:" + digest), digest)
            with self.assertRaises(ValueError):
                verify_sha256(p, "0" * 64)
            with self.assertRaises(ValueError):
                verify_sha256(p, "not-a-digest")


class SafeZipTests(unittest.TestCase):
    def _zip(self, td, entries):
        path = Path(td) / "update.zip"
        with zipfile.ZipFile(path, "w") as zf:
            for name, data in entries:
                zf.writestr(name, data)
        return path

    def test_extracts_whitelisted_layout(self):
        with tempfile.TemporaryDirectory() as td:
            z = self._zip(td, [("HitranLink.exe", b"exe"), ("_internal/a.txt", b"a")])
            out = Path(td) / "out"
            self.assertEqual(safe_extract_zip(z, out), 2)
            self.assertTrue((out / "HitranLink.exe").is_file())
            self.assertEqual(validate_update_layout(out), out)

    def test_rejects_traversal_and_absolute_paths(self):
        for name in ("../evil.txt", "..\\evil.txt", "/evil.txt", "C:/evil.txt"):
            with tempfile.TemporaryDirectory() as td:
                z = self._zip(td, [("HitranLink.exe", b"exe"), (name, b"x")])
                with self.assertRaises(ValueError):
                    safe_extract_zip(z, Path(td) / "out")

    def test_rejects_size_bomb(self):
        with tempfile.TemporaryDirectory() as td:
            z = self._zip(td, [("HitranLink.exe", b"x" * 32)])
            with self.assertRaises(ValueError):
                safe_extract_zip(z, Path(td) / "out", max_total=8)

    def test_rejects_symlink_entry(self):
        with tempfile.TemporaryDirectory() as td:
            z = Path(td) / "update.zip"
            with zipfile.ZipFile(z, "w") as zf:
                info = zipfile.ZipInfo("link")
                info.external_attr = (0o120777 << 16) | 0o777
                zf.writestr(info, "target")
            with self.assertRaises(ValueError):
                safe_extract_zip(z, Path(td) / "out")

    def test_validate_layout_rejects_extra_top_level(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "HitranLink.exe").write_bytes(b"exe")
            (root / "extra.txt").write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_update_layout(root)
            self.assertEqual(ALLOWED_TOP_LEVEL, {"HitranLink.exe", "_internal"})


if __name__ == "__main__":
    unittest.main()
