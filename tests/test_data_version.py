# -*- coding: utf-8 -*-
"""数据版次台账与输入护栏回归：线型标注、抓取日期、版次告警、摩尔分数范围。

全部离线：不联网、不加载谱线表，只测纯函数与常量，可在 CI 任意机器跑。
"""
import unittest

import tools.hitran as ht
import tools.hitran_mcp as hm


class ProvenanceTests(unittest.TestCase):
    def test_profile_not_hardcoded_as_voigt(self):
        stamp = ht.provenance("CO", 2109.0, 2111.0, 296, 1.01325, profile="sdvoigt")
        self.assertIn("profile=sdvoigt", stamp)
        self.assertNotIn("profile=Voigt", stamp)

    def test_default_profile_is_lowercase_voigt(self):
        stamp = ht.provenance("CO", 2109.0, 2111.0, 296, 1.01325, profile="voigt")
        self.assertIn("profile=voigt", stamp)

    def test_edition_and_fetch_date_are_written(self):
        stamp = ht.provenance("CO", 2109.0, 2111.0, 296, 1.01325,
                              fetch_dates={"CO_5_1_2109_2111": "2026-11-01"})
        self.assertIn("HITRAN2024", stamp)
        self.assertIn("table fetched CO_5_1_2109_2111@2026-11-01", stamp)
        self.assertNotIn("# WARN:", stamp)

    def test_stale_table_carries_warning(self):
        stamp = ht.provenance("CO", 2109.0, 2111.0, 296, 1.01325,
                              fetch_dates={"CO_5_1_2109_2111": "2026-03-01"})
        self.assertIn("# WARN:", stamp)
        self.assertIn(ht.latest_update()[0], stamp)

    def test_unknown_date_is_not_guessed(self):
        self.assertIsNone(ht.stale_data_warning({}, "voigt"))
        self.assertIsNone(ht.stale_data_warning({"t": None}, "voigt"))
        self.assertIsNone(ht.stale_data_warning({"t": "2026-11-01"}, "voigt"))
        self.assertIsNotNone(ht.stale_data_warning({"t": "2026-01-01"}, "voigt"))

    def test_update_ledger_is_ascending(self):
        dates = [d for d, _ in ht.HITRAN_UPDATES]
        self.assertEqual(dates, sorted(dates))
        self.assertIn(ht.HITRAN_EDITION_BASE, dates)

    def test_ht_profile_is_actual_not_hardcoded(self):
        stamp = ht.provenance("CO", 2109.0, 2111.0, 296, 1.01325, profile="HT")
        self.assertIn("profile=ht", stamp)

    def test_window_suffixed_table_is_reported(self):
        # 静态推导只对基础表成立；带窗口后缀的表必须按实参写入，否则产物指向不存在的缓存名
        stamp = ht.provenance("CH4", 2968.0, 2970.0, 296, 1.01325,
                              tables="CH4_6_1_2968_2970")
        self.assertIn("table=CH4_6_1_2968_2970", stamp)

    def test_units_switch_in_watermark(self):
        self.assertIn("cm2/molecule",
                      ht.provenance("CO", 2109.0, 2111.0, 296, 1.01325, hitran_units=True))
        self.assertIn("cm-1",
                      ht.provenance("CO", 2109.0, 2111.0, 296, 1.01325, hitran_units=False))


class SpecsGuardTests(unittest.TestCase):
    def test_parse_normal(self):
        out = hm._parse_specs_csv("CH4:0.01,C2H6:1e-5")
        # mole_frac_given 是下游 needs_confirm 判据，必须随解析结果一并带回
        self.assertEqual({k: out[0][k] for k in ("name", "mole_frac", "mole_frac_given")},
                         {"name": "CH4", "mole_frac": 0.01, "mole_frac_given": True})
        self.assertAlmostEqual(out[1]["mole_frac"], 1e-5)
        self.assertEqual(hm._parse_specs_csv("CO,N2O")[1],
                         {"name": "N2O", "mole_frac_given": False})

    def test_parse_rejects_out_of_range(self):
        for bad in ("CH4:0", "CH4:-0.5", "CH4:5", "CH4:1e3", "CH4:", "CH4:abc",
                    ":0.01"):
            with self.assertRaises(ValueError, msg=bad):
                hm._parse_specs_csv(bad)

    def test_norm_rejects_out_of_range(self):
        for bad in (-1, 0, 3.0, "abc"):
            with self.assertRaises(ValueError, msg=str(bad)):
                hm._norm_specs([{"name": "CH4", "mole_frac": bad}])

    def test_norm_defaults_to_pure_gas(self):
        out = hm._norm_specs([{"name": "ch4"}])
        self.assertEqual(out[0]["mole_frac"], 1.0)
        self.assertFalse(out[0]["mole_frac_given"])


class ProfileSupportTests(unittest.TestCase):
    def test_unavailable_profiles_are_not_selectable(self):
        for p in hm.UNAVAILABLE_PROFILES:
            self.assertNotIn(p, hm.PROFILES)
            self.assertTrue(hm.UNAVAILABLE_PROFILES[p], "必须给出可操作原因")

    def test_selectable_profiles_map_to_official_hapi(self):
        for name, fn in hm.PROFILES.items():
            self.assertTrue(fn.startswith("absorptionCoefficient_"), name)


if __name__ == "__main__":
    unittest.main()
