"""MCP 面向 AI 调用契约的离线测试：错误码、曲线采样、report 组装。全部不联网。"""
import json
import unittest
from unittest import mock

import tools.hitran_mcp as m


class ErrorContractTests(unittest.TestCase):
    def _call(self, name, args):
        _, payload, error = m.handle({"jsonrpc": "2.0", "id": "t", "method": "tools/call",
                                      "params": {"name": name, "arguments": args}})
        self.assertIsNone(error)
        self.assertTrue(payload["isError"])
        return json.loads(payload["content"][0]["text"])["error"]

    def test_bad_args_is_machine_readable(self):
        err = self._call("hitran_spectrum",
                         {"name": "CH4", "specs_csv": "CO:0.01", "numin": 2968, "numax": 2970})
        self.assertEqual(err["code"], "E_BAD_ARGS")
        self.assertTrue(err["hint"])

    def test_strict_without_tp(self):
        err = self._call("hitran_spectrum",
                         {"name": "CH4", "numin": 2968, "numax": 2970, "strict": True})
        self.assertEqual(err["code"], "E_STRICT")

    def test_missing_file(self):
        err = self._call("hitran_cross_section", {"file_path": "xsc_data/nope.xsc"})
        self.assertEqual(err["code"], "E_MISSING_FILE")

    def test_path_jail(self):
        err = self._call("hitran_cross_section", {"file_path": "C:/Windows/system.ini"})
        self.assertEqual(err["code"], "E_BAD_ARGS")

    def test_unknown_tool(self):
        err = self._call("hitran_nonexistent", {})
        self.assertEqual(err["code"], "E_UNKNOWN_TOOL")

    def test_every_code_has_hint(self):
        for code, hint in m._ERROR_HINTS.items():
            self.assertTrue(hint, code)


class CurveSampleTests(unittest.TestCase):
    def test_shape_and_endpoints(self):
        nu = [2968.0 + i * 1e-3 for i in range(501)]
        y = [1.0 if i == 250 else 0.0 for i in range(501)]
        c = m._downsample(nu, y, 64)
        self.assertEqual(len(c["nu_cm-1"]), 64)
        self.assertEqual(len(c["value"]), 64)
        self.assertEqual(c["n_total"], 501)
        self.assertAlmostEqual(c["nu_cm-1"][0], 2968.0, places=6)
        self.assertAlmostEqual(c["nu_cm-1"][-1], 2968.5, places=6)
        self.assertTrue(all(b >= a for a, b in zip(c["nu_cm-1"], c["nu_cm-1"][1:])))

    def test_cap_and_min(self):
        nu = list(range(2000))
        self.assertEqual(len(m._downsample(nu, nu, 500)["nu_cm-1"]), 200)
        self.assertEqual(len(m._downsample(nu, nu, 1)["nu_cm-1"]), 2)

    def test_no_interpolation_peak_survives(self):
        """抽样点必须是原始数据点（不插值），否则尖峰会被削低。"""
        nu = [float(i) for i in range(100)]
        y = [0.0] * 100
        y[37] = 1.0
        c = m._downsample(nu, y, 50)
        picked = dict(zip(c["nu_cm-1"], c["value"]))
        for v in picked.values():
            self.assertIn(v, (0.0, 1.0))


class ReportAssemblyTests(unittest.TestCase):
    def test_one_call_shape(self):
        fake_spec = {"peaks": {"CH4@1e-06": {"peak_value": 1.3e-5, "peak_nu": 2968.7, "integral": 6e-6}},
                     "curve": m._downsample([2968, 2970], [0, 0], 8),
                     "csv": "tmp/ch4.csv",
                     "tables": {"CH4@1e-06": {"table": "CH4_6_1_2968_2970",
                                              "table_fetched_at": {"CH4_6_1_2968_2970": "2026-09-13"}}},
                     "warnings": ["w1"], "assumed_defaults": ["T=296.0", "P=1.01325"],
                     "needs_confirm": True}
        fake_lines = {"lines": [{"nu_cm-1": 2968.73}], "n_in_window": 410}
        with mock.patch.object(m, "t_spectrum", return_value=fake_spec), \
                mock.patch.object(m, "t_lines", return_value=fake_lines), \
                mock.patch.object(m, "t_plot", return_value={"png": "tmp/ch4.png"}):
            out = m.t_report(name="CH4", mole_frac=1e-6, numin=2968, numax=2970)
        for key in ("species", "window_cm-1", "conditions", "peaks", "curve", "top_lines",
                    "png", "csv", "tables", "data", "warnings", "assumed_defaults",
                    "needs_confirm", "next_actions"):
            self.assertIn(key, out)
        self.assertEqual(out["png"], "tmp/ch4.png")
        self.assertTrue(out["next_actions"])
        self.assertIn("HITRAN", out["data"]["edition"])

    def test_multi_species_skips_lines(self):
        fake_spec = {"peaks": {}, "curve": None, "csv": None, "tables": None,
                     "warnings": [], "assumed_defaults": [], "critical_defaults": [],
                     "needs_confirm": False}
        with mock.patch.object(m, "t_spectrum", return_value=fake_spec), \
                mock.patch.object(m, "t_plot", return_value={"png": "tmp/x.png"}):
            out = m.t_report(specs_csv="CH4:1e-6,C2H6:1e-6", numin=2968, numax=2970)
        self.assertIsNone(out["top_lines"])
        self.assertTrue(any("hitran_lines" in a for a in out["next_actions"]))

    def test_no_confirm_when_conditions_given(self):
        """T/P/浓度都给齐时不得报 needs_confirm（否则 AI 会无谓回问用户）。"""
        fake_spec = {"peaks": {}, "curve": None, "csv": None, "tables": None,
                     "warnings": [], "assumed_defaults": ["step=0.01", "mode=alpha"],
                     "critical_defaults": [], "needs_confirm": False}
        with mock.patch.object(m, "t_spectrum", return_value=fake_spec), \
                mock.patch.object(m, "t_lines", return_value={"lines": []}), \
                mock.patch.object(m, "t_plot", return_value={"png": None}):
            out = m.t_report(name="CH4", mole_frac=1e-6, numin=2968, numax=2970,
                             T=296, P=1.01325)
        self.assertFalse(out["needs_confirm"])
        self.assertFalse(any("confirm" in a.lower() or "确认" in a for a in out["next_actions"]))


class ContractSurfaceTests(unittest.TestCase):
    def test_report_registered(self):
        names = [t["name"] for t in m.TOOLS]
        self.assertEqual(len(names), 13)
        self.assertIn("hitran_report", names)
        self.assertIs(m.DISPATCH["hitran_report"], m.t_report)

    def test_report_schema(self):
        tool = next(t for t in m.TOOLS if t["name"] == "hitran_report")
        self.assertEqual(tool["inputSchema"]["required"], ["numin", "numax"])
        self.assertIn("sample_points", tool["inputSchema"]["properties"])

    def test_descriptions_carry_usage(self):
        for name in ("hitran_report", "hitran_spectrum", "hitran_lines", "hitran_plot"):
            tool = next(t for t in m.TOOLS if t["name"] == name)
            self.assertGreater(len(tool["description"]), 40, name)


if __name__ == "__main__":
    unittest.main()
