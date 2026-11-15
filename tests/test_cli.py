# -*- coding: utf-8 -*-
"""命令行入口的离线回归测试（不联网、不触发真实计算）。"""
import contextlib
import io
import unittest

from tools.hitran_cli import _NAME_MAP, _coerce, _parse_kwargs, main


class CoerceTests(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(_coerce("296"), 296)
        self.assertEqual(_coerce("0.002"), 0.002)
        self.assertEqual(_coerce("2950.5"), 2950.5)

    def test_bools_and_null(self):
        self.assertIs(_coerce("true"), True)
        self.assertIs(_coerce("FALSE"), False)
        self.assertIsNone(_coerce("null"))

    def test_strings_and_json(self):
        self.assertEqual(_coerce("CH4"), "CH4")
        self.assertEqual(_coerce('["CH4:0.002","H2O:0.01"]'), ["CH4:0.002", "H2O:0.01"])

    def test_broken_json_falls_back_to_string(self):
        self.assertEqual(_coerce("[not json"), "[not json")


class KwargTests(unittest.TestCase):
    def test_pairs(self):
        self.assertEqual(
            _parse_kwargs(["--name", "CH4", "--numin", "2950", "--force"]),
            {"name": "CH4", "numin": 2950, "force": True},
        )

    def test_dash_becomes_underscore(self):
        self.assertEqual(_parse_kwargs(["--top-n", "5"]), {"top_n": 5})

    def test_bare_token_rejected(self):
        with self.assertRaises(SystemExit):
            _parse_kwargs(["CH4"])


class DispatchTests(unittest.TestCase):
    def test_all_mcp_tools_mapped(self):
        self.assertIn("hitran_spectrum", _NAME_MAP)
        self.assertEqual(_NAME_MAP["hitran_spectrum"], "t_spectrum")
        self.assertEqual(_NAME_MAP["t_spectrum"], "t_spectrum")
        self.assertEqual(len(_NAME_MAP), 24)  # 12 个工具，两种写法

    def test_list_runs_offline(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(["--list"]), 0)
        out = buf.getvalue()
        self.assertIn("hitran_spectrum", out)
        self.assertIn("hitran_xsc_download", out)

    def test_unknown_tool(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["t_not_a_tool"]), 2)


if __name__ == "__main__":
    unittest.main()
