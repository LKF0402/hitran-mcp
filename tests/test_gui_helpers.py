# -*- coding: utf-8 -*-
"""GUI 侧纯函数回归：分子名解析 + 截面文件读取与 MCP 通道逐值一致。

这些函数不创建 Tk 窗口，可在 CI 无显示环境跑；覆盖 README 中"GUI 与 MCP
共用同一套引擎、结果一致"这一承诺里最容易走偏的读取环节。
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np

try:
    import app.hitran_app as gui
except Exception as exc:  # 无 tkinter 的精简环境：跳过整组，不算失败
    raise unittest.SkipTest(f"tkinter unavailable: {exc}")

import tools.hitran_mcp as hm


class MoleculeNameTests(unittest.TestCase):
    def test_display_name_known_and_unknown(self):
        self.assertEqual(gui.molecule_display_name("CH4"), "CH4 (Methane)")
        self.assertEqual(gui.molecule_display_name("XX9"), "XX9")

    def test_alias_resolution(self):
        self.assertEqual(gui.resolve_molecule_alias("water"), ("H2O", True))
        self.assertEqual(gui.resolve_molecule_alias("1"), ("H2O", True))
        self.assertEqual(gui.resolve_molecule_alias(" co2 "), ("CO2", True))
        self.assertEqual(gui.resolve_molecule_alias("xx9"), ("XX9", False))
        self.assertEqual(gui.resolve_molecule_alias(""), ("", False))


class CrossSectionParityTests(unittest.TestCase):
    """同一文件经 GUI 与 MCP 两条读取路径，数值必须逐点相同。"""

    def _native_file(self, d):
        npnts, numin, numax = 12, 1000.0, 1011.0
        head = ("C3H8".ljust(20) + f"{numin:10.4f}{numax:10.4f}{npnts:7d}"
                f"{296.0:7.1f}{760.0:6.1f}")
        vals = np.linspace(1e-21, 2e-21, npnts)
        p = Path(d) / "fake.xsc"
        p.write_text(
            head + "\n"
            + " ".join(f"{v:.4e}" for v in vals[:10]) + "\n"
            + " ".join(f"{v:.4e}" for v in vals[10:]) + "\n",
            encoding="utf-8")
        return p, numin, numax, npnts

    def test_native_xsc_matches_mcp_reader(self):
        with tempfile.TemporaryDirectory() as d:
            p, numin, numax, npnts = self._native_file(d)
            gnu, gcoef, _header, gskip = gui._read_hotw(p)
            mnu, mcoef, _mheader, mskip = hm._read_hotw_file(p)
        self.assertEqual(len(gnu), npnts)
        self.assertEqual(gskip, mskip)
        np.testing.assert_allclose(gnu, mnu, rtol=0, atol=1e-9)
        np.testing.assert_allclose(gcoef, mcoef, rtol=1e-12, atol=0)
        self.assertAlmostEqual(float(gnu[0]), numin, places=6)
        self.assertAlmostEqual(float(gnu[-1]), numax, places=6)

    def test_two_column_text_matches_mcp_reader(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "hotw.txt"
            p.write_text("# header\n1000.0 1.0e-21\n"
                         "garbage line\n1002.0 3.0e-21\n", encoding="utf-8")
            gnu, gcoef, gheader, gskip = gui._read_hotw(p)
            mnu, mcoef, mheader, mskip = hm._read_hotw_file(p)
        self.assertEqual(gskip, 1)
        self.assertEqual(mskip, 1)
        self.assertEqual(list(gnu), list(mnu))
        self.assertEqual(list(gcoef), list(mcoef))
        self.assertEqual(len(gheader), 1)


if __name__ == "__main__":
    unittest.main()
