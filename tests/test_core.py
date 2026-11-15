# -*- coding: utf-8 -*-
"""核心纯函数回归：凭据脱敏、输出文件名防穿越、状态字段契约。"""
import unittest
from pathlib import Path

import tools.hitran as ht
import tools.hitran_mcp as hm


class RedactionTests(unittest.TestCase):
    def test_key_value_and_api_path_are_redacted(self):
        text = ("GET https://hitran.org/api/v2/SECRET-KEY-123/cross-sections "
                "?api_key=SECRET-KEY-123 Bearer abcdef123456")
        out = ht.redact_secrets(text)
        self.assertNotIn("SECRET-KEY-123", out)
        self.assertNotIn("abcdef123456", out)
        self.assertIn("***", out)

    def test_none_is_safe(self):
        self.assertEqual(ht.redact_secrets(None), "")


class FilenameTests(unittest.TestCase):
    def test_slug_cannot_escape_directory(self):
        for raw in ("../../evil", "..\\..\\evil", "C:\\Windows\\evil", "/tmp/evil"):
            slug = hm._slug(raw)
            self.assertNotIn("/", slug)
            self.assertNotIn("\\", slug)
            self.assertFalse(Path(slug).is_absolute())

    def test_apikey_status_has_diagnostic_fields(self):
        st = hm.t_apikey_status(probe=False)
        for key in ("api_key_configured", "api_key_source", "cache_root",
                    "cache_root_source", "proxy", "line_cache_files",
                    "xsc_data_files", "output_files", "download_engine"):
            self.assertIn(key, st)


if __name__ == "__main__":
    unittest.main()
