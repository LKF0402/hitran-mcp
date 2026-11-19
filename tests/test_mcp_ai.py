"""MCP 面向 AI 调用契约的离线测试：错误码、曲线采样、report 组装。全部不联网。"""
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
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
        self.assertEqual(len(names), 14)
        self.assertIn("hitran_report", names)
        self.assertIs(m.DISPATCH["hitran_report"], m.t_report)
        self.assertIn("hitran_interference", names)
        self.assertIs(m.DISPATCH["hitran_interference"], m.t_interference)

    def test_interference_schema(self):
        tool = next(t for t in m.TOOLS if t["name"] == "hitran_interference")
        self.assertEqual(tool["inputSchema"]["required"],
                         ["name", "interferers_csv", "numin", "numax"])
        self.assertIn("line_index", tool["inputSchema"]["properties"])

    def test_report_schema(self):
        tool = next(t for t in m.TOOLS if t["name"] == "hitran_report")
        self.assertEqual(tool["inputSchema"]["required"], ["numin", "numax"])
        self.assertIn("sample_points", tool["inputSchema"]["properties"])

    def test_descriptions_carry_usage(self):
        for name in ("hitran_report", "hitran_spectrum", "hitran_lines", "hitran_plot"):
            tool = next(t for t in m.TOOLS if t["name"] == name)
            self.assertGreater(len(tool["description"]), 40, name)


class InterferenceTests(unittest.TestCase):
    """干扰量化：用替代 _compute 做纯逻辑验证（不联网、不依赖真实线表）。"""

    NU0 = 2968.73
    PURE_AMP = {"CH4": 1.0, "H2O": 0.5}

    def _fake_compute(self, specs, numin, numax, T, P, step, wingHW, mode, pl, hu,
                      profile, diluent):
        import numpy as np
        sp = specs[0]
        if sp["name"] == "CO2":                     # 模拟"线表未覆盖"失败
            raise ValueError("[hitran] CO2 线表未覆盖该窗口")
        nu = np.linspace(numin, numax, 101)
        x = sp["mole_frac"]
        amp = self.PURE_AMP.get(sp["name"], 0.0)
        y = amp * x * (1.0 - abs(2968.73 - nu))     # 线心附近近似三角形，便于取点
        label = sp["name"] if x == 1 else f"{sp['name']}@{x:g}"
        return {"nu": nu, "per": {label: y}, "warnings": [], "tables": {}}

    def _fake_lines(self, *a, **kw):
        return {"lines": [{"nu_cm-1": self.NU0, "S_cm_per_molecule": 1e-19,
                           "gamma_air": 0.05}]}

    def test_dominant_interferer(self):
        with mock.patch.object(m, "t_lines", self._fake_lines), \
                mock.patch.object(m, "_compute", self._fake_compute):
            out = m.t_interference(name="CH4", interferers_csv="H2O:1e-5",
                                   numin=2968, numax=2970, mole_frac=1e-6,
                                   T=296, P=1.01325)
        # α_i/α_t = (0.5·1e-5)/(1.0·1e-6) = 5
        self.assertAlmostEqual(out["interferers"][0]["ratio_to_target"], 5.0, delta=0.3)
        self.assertEqual(out["verdict"]["level"], "dominant")
        self.assertTrue(any("2f" in w for w in out["warnings"]))
        self.assertFalse(out["needs_confirm"])

    def test_negligible_interferer(self):
        with mock.patch.object(m, "t_lines", self._fake_lines), \
                mock.patch.object(m, "_compute", self._fake_compute):
            out = m.t_interference(name="CH4", interferers_csv="H2O:1e-9",
                                   numin=2968, numax=2970, mole_frac=1e-6,
                                   T=296, P=1.01325)
        self.assertAlmostEqual(out["interferers"][0]["ratio_to_target"], 5e-4, delta=5e-5)
        self.assertEqual(out["verdict"]["level"], "negligible")

    def test_skipped_component_reported(self):
        with mock.patch.object(m, "t_lines", self._fake_lines), \
                mock.patch.object(m, "_compute", self._fake_compute):
            out = m.t_interference(name="CH4", interferers_csv="H2O:1e-5,CO2:4e-4",
                                   numin=2968, numax=2970, mole_frac=1e-6,
                                   T=296, P=1.01325)
        self.assertEqual(len(out["interferers"]), 1)
        self.assertEqual(out["skipped"][0]["name"], "CO2")
        self.assertTrue(any("skipped" in a for a in out["next_actions"]))

    def test_no_target_line_raises(self):
        with mock.patch.object(m, "t_lines", lambda *a, **kw: {"lines": []}):
            with self.assertRaises(ValueError):
                m.t_interference(name="CH4", interferers_csv="H2O:1e-5",
                                 numin=2968, numax=2970)

    def test_specs_csv_tracks_given_fraction(self):
        """带浓度的片段必须标 mole_frac_given=True，否则会被误报"未给浓度"。"""
        given = m._parse_specs_csv("CH4:0.01,C2H6:1e-5")
        default = m._parse_specs_csv("CO,N2O")
        self.assertTrue(all(s["mole_frac_given"] for s in given))
        self.assertFalse(any(s["mole_frac_given"] for s in default))


class _FakeAbsorption:
    """把 _absorption 换成常数谱：只用 iso 决定幅度（1→2.0, 2→4.0），隔离 HITRAN 取数。"""

    _DUMMY_HT = types.SimpleNamespace(
        _validate_params=lambda *a, **k: None,
        check_spectrum=lambda *a, **k: [])

    @staticmethod
    def fake_abs(name, iso, numin, numax, *a, **k):
        import numpy as np
        nu = np.linspace(float(numin), float(numax), 21)
        amp = 4.0 if iso == 2 else 2.0
        return nu, np.full_like(nu, amp), {"table": "T", "coverage_cm-1": [numin, numax],
                                           "n_lines_in_window": 1, "n_lines_table": 1,
                                           "table_fetched_at": {}}


class ChromaticBugTests(unittest.TestCase):
    """针对实测复现的 5 个 bug 的回归锁定（全部离线）。"""

    def _compute(self, specs, **kw):
        with mock.patch.object(m, "_hitran", lambda: _FakeAbsorption._DUMMY_HT), \
                mock.patch.object(m, "_absorption", _FakeAbsorption.fake_abs):
            return m._compute(specs, 2143.0, 2147.0, T=kw.pop("T", 296.0),
                              P=kw.pop("P", 1.0), **kw)

    def _spec(self, name="CO", iso=None, x=1.0):
        return {"name": name, "iso": iso, "mole_frac": x}

    def test_duplicate_species_labels_do_not_collide(self):
        """① 同一分子不同同位素：旧实现标签撞车，后一个覆盖前一个且无告警。"""
        res = self._compute([self._spec(iso=1), self._spec(iso=2)])
        self.assertEqual(len(res["per"]), 2, res["per"].keys())
        labels = sorted(res["per"].keys())
        self.assertIn("CO[I=1]", labels)
        self.assertIn("CO[I=2]", labels)
        import numpy as np
        self.assertAlmostEqual(float(res["total"][0]), 6.0)     # 2.0 + 4.0，不再被覆盖
        self.assertTrue(any("同位素" in w for w in res["warnings"]))

    def test_sigma_mode_respects_mole_fraction(self):
        """② σ 口径也要按 x 加权：混合物 total = Σ x_i·σ_i（旧实现直接加纯气体 σ）。"""
        res = self._compute([self._spec(iso=1, x=0.5), self._spec(name="CH4", x=0.5)],
                            hitran_units=True)
        self.assertAlmostEqual(float(res["total"][0]), 0.5 * 2.0 + 0.5 * 2.0)
        self.assertTrue(any("摩尔分数" in w for w in res["warnings"]))

    def test_transmittance_sigma_uses_number_density(self):
        """② σ + 透过率：必须 τ=exp(-σ·N·L)，旧实现量纲不成立、τ 恒为 1.0。"""
        res = self._compute([self._spec(x=1e-6)], hitran_units=True,
                            mode="transmittance", path_length_cm=100.0)
        import numpy as np
        n_exp = 1.0 * 101325.0 / (1.380649e-23 * 296.0)
        self.assertAlmostEqual(res["number_density_cm-3"], n_exp, delta=abs(n_exp) * 1e-6)
        tau_exp = float(np.exp(-2.0 * 1e-6 * n_exp * 100.0))
        self.assertAlmostEqual(float(res["trans"][0]), tau_exp, places=12)
        self.assertLess(float(res["trans"][0]), 1.0)

    def test_native_xsc_not_eaten_by_two_column_parser(self):
        """③ npnts % 10 == 2 时，末行 2 个数会被两列解析吞成假数据点（旧顺序的错）。"""
        import numpy as np
        npnts, numin, numax = 12, 1000.0, 1011.0
        head = ("C3H8".ljust(20) + f"{numin:10.4f}{numax:10.4f}{npnts:7d}"
                f"{296.0:7.1f}{760.0:6.1f}")
        vals = np.linspace(1e-21, 2e-21, npnts)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fake.xsc"
            p.write_text(head + "\n" + " ".join(f"{v:.4e}" for v in vals[:10]) + "\n"
                         + " ".join(f"{v:.4e}" for v in vals[10:]) + "\n", encoding="utf-8")
            nu, coef, header, skipped = m._read_hotw_file(p)
        self.assertEqual(len(nu), npnts)
        self.assertEqual(len(coef), npnts)
        self.assertAlmostEqual(float(nu[0]), numin, places=6)
        self.assertAlmostEqual(float(nu[-1]), numax, places=6)
        self.assertGreater(float(coef.max()), 1e-21)

    def test_compute_cache_follows_data_dir(self):
        """④ 计算缓存必须与线表缓存同根（HITRAN_DATA_DIR 只生效一半是 bug）。"""
        self.assertEqual(m._PERSIST_CACHE_DIR, m.DATA_ROOT / "compute_cache")

    def test_xsc_listing_includes_native_suffix(self):
        """⑤ 下载的原生 .xsc 必须出现在可用清单里。"""
        with tempfile.TemporaryDirectory() as d:
            Path(d, "demo.xsc").write_text("x", encoding="utf-8")
            Path(d, "demo2.txt").write_text("x", encoding="utf-8")
            with mock.patch.object(m, "XSC_DIR", Path(d)):
                names = [f["name"] for f in m._list_xsc_files()]
        self.assertIn("demo.xsc", names)
        self.assertIn("demo2.txt", names)

    def test_invalid_window_and_step_rejected(self):
        """窗口反向 / 步长为 0 / 气压为 0 必须显式报错，不得退化成空谱或抛 numpy 除零。"""
        for kw in ({"numin": 2147.0, "numax": 2143.0},
                   {"step": 0.0}, {"P": 0.0}, {"T": 0.0}):
            args = dict(specs=[self._spec()], numin=2143.0, numax=2147.0)
            args.update(kw)
            with self.assertRaises(ValueError):
                with mock.patch.object(m, "_hitran", lambda: _FakeAbsorption._DUMMY_HT), \
                        mock.patch.object(m, "_absorption", _FakeAbsorption.fake_abs):
                    m._compute(**args)

    def test_lines_rejects_zero_top_n(self):
        """top_n=0 旧实现静默返回空列表（看起来像"窗口无收录线"）。"""
        with self.assertRaises(ValueError):
            m.t_lines("CO", 2143, 2147, top_n=0)
        with self.assertRaises(ValueError):
            m.t_lines("CO", 2147, 2143, top_n=3)

    def test_native_header_detection_requires_consistent_header(self):
        """长首行两列文本不得被误判为原生 .xsc（头部 numin/numax 反了就必须拒绝）。"""
        head = ("C3H8".ljust(20) + f"{1100.0:10.4f}{1000.0:10.4f}{12:7d}"
                f"{296.0:7.1f}{760.0:6.1f}")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.xsc"
            p.write_text(head + "\n", encoding="utf-8")
            self.assertFalse(m._looks_like_native_xsc(p))


if __name__ == "__main__":
    unittest.main()
