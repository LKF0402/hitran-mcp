#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HITRAN MCP Server —— 把 tools/hitran.py 的取数与绘图能力暴露成 AI 可直接调用的工具。

设计取向（功能齐全前提下的简约）：
  · 纯标准库实现的 stdio JSON-RPC（MCP 2024-11-05），零新增依赖；
    HAPI / matplotlib 惰性加载，空闲时不占用内存。
  · 所有 print 被捕获为 log 字段返回，绝不污染 stdout 协议流。
  · 7 个工具覆盖全链路：物种查询 / 线表抓取 / 强线列表 / 吸收·透过率谱（可混合气）
    / 谱图绘制 / 配分函数 / 截面文件（HOTW）读入分析。
  · 产物统一落 tmp/mcp_out/（gitignore 区），CSV 自带 HITRAN 溯源水印。
  · 物理纪律沿用 tools/hitran.py：输入护栏 + 结果轮询 + 混合气 α = x·α_pure(T,P,空气浴)。

启动（由 MCP 客户端拉起）：  python tools/hitran_mcp.py
自测：                        python tools/hitran_mcp.py --selftest
"""
import contextlib
import io
import json
import os
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))          # 保证 tools 包可导入（自包含）

OUT_DIR = ROOT / "tmp" / "mcp_out"         # 产物区（tmp/ 已 gitignore）
PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "hitran", "version": "1.1.0"}

_HT = None          # 惰性加载的 tools.hitran 模块（含 hapi，重）
_NP = None


# ───────────────────────── 基础设施 ─────────────────────────

@contextlib.contextmanager
def _quiet():
    """把 print 收进缓冲区：HAPI/matplotlib 的刷屏不能进 stdout 协议流。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf


def _api_key():
    """读取本机 HITRAN API key（文件已 gitignore，不入库；优先读环境变量）。

    注意：HAPI 1.3.0.0 官方代码的 getLinelist() 接收 api_key 但并未使用，
    下载走旧接口不校验 key；此 key 属"预置"——升级到支持 key 的 HAPI/官方 API
    版本时自动生效，同时便于官方配额问题的排查与登记。
    """
    env = os.environ.get("HITRAN_API_KEY", "").strip()
    if env:
        return env
    for p in (ROOT / "tools" / "hitran_api_key.txt",
              ROOT / "Hitran_Data" / "hitran_api_key.txt"):
        try:
            if p.exists():
                k = p.read_text(encoding="utf-8").strip()
                if k:
                    return k
        except Exception:
            pass
    return ""


def _hitran():
    global _HT
    if _HT is None:
        with _quiet():
            import tools.hitran as m
            import hapi
        _HT = m
        key = _api_key()                     # 预置 key：未来版本 HAPI 自动生效
        if key:
            try:
                if not getattr(hapi, "API_KEY", None):
                    hapi.API_KEY = key
            except Exception:
                pass
    return _HT


def _np():
    global _NP
    if _NP is None:
        import numpy as np
        _NP = np
    return _NP


def _jsonable(o):
    """numpy / Path 等转成可 JSON 序列化的原生类型。"""
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (str, bool, int, float)) or o is None:
        return o
    if isinstance(o, Path):
        return str(o)
    if hasattr(o, "tolist"):
        try:
            return _jsonable(o.tolist())
        except Exception:
            pass
    if hasattr(o, "item"):
        try:
            return _jsonable(o.item())
        except Exception:
            pass
    return str(o)


def _slug(*parts):
    s = "_".join(str(p) for p in parts)
    return re.sub(r"[^0-9A-Za-z._-]+", "-", s)


# ───────────────────────── 核心计算（取数） ─────────────────────────

def _norm_specs(specs, name=None, mole_frac=None, iso=None):
    """统一成 [{name, iso, mole_frac}]；兼容单分子的简写调用。"""
    if not specs:
        if not name:
            raise ValueError("必须给出 specs 列表或 name（单分子简写）")
        specs = [{"name": name, "mole_frac": 1.0 if mole_frac is None else mole_frac,
                  **({"iso": iso} if iso is not None else {})}]
    out = []
    for sp in specs:
        nm = str(sp.get("name", "")).strip().upper()
        if not nm:
            raise ValueError(f"specs 元素缺少 name: {sp}")
        x = sp.get("mole_frac")
        out.append({"name": nm,
                    "iso": sp.get("iso"),
                    "mole_frac": 1.0 if x is None else float(x),
                    "mole_frac_given": x is not None})
    return out


def _wnum(v):
    """窗口数字 → 表名片段：2172.5 -> 2172p5。"""
    return f"{float(v):g}".replace(".", "p").replace("-", "m")


def _coverage(table):
    """已加载表的实际覆盖区间 (nu_min, nu_max, n_lines)；不可用返回 None。"""
    try:
        import hapi
        if table not in hapi.tableList():
            return None
        nu = _np().asarray(hapi.getColumn(table, "nu"), dtype=float)
        return (float(nu.min()), float(nu.max()), int(nu.size)) if nu.size else None
    except Exception:
        return None


# ───────── 官方物种解析（不硬编码，全部来自 HAPI 自带 ISO 表）─────────
_SPECIES_CACHE = None


def _official_species():
    """从 HAPI 官方 ISO 表构建物种索引。

    hapi.ISO[(M,I)] = [M, 同位素名, 自然丰度, 质量, 分子式]
    覆盖 HITRAN 全部分子与同位素，取代任何本地硬编码字典。
    """
    global _SPECIES_CACHE
    if _SPECIES_CACHE is None:
        import hapi
        idx = {}
        for (M, I), rec in hapi.ISO.items():
            formula = str(rec[4]).upper()
            e = idx.setdefault(formula, {"M": M, "isotopologues": []})
            e["isotopologues"].append({"I": I, "abundance": float(rec[2]),
                                       "name": rec[1], "mass": float(rec[3])})
        for e in idx.values():
            e["isotopologues"].sort(key=lambda d: -d["abundance"])
            e["main_iso"] = e["isotopologues"][0]["I"]
        _SPECIES_CACHE = idx
    return _SPECIES_CACHE


def _formula(M):
    """HITRAN 分子号 → 分子式（官方表）。"""
    idx = _official_species()
    for f, e in idx.items():
        if e["M"] == M:
            return f
    import hapi
    return str(hapi.moleculeName(M)).upper()


def _resolve_M(name):
    """分子式 / HITRAN 编号 → (formula, M)。全部走官方表。"""
    idx = _official_species()
    s = str(name).strip().upper()
    if s.isdigit():                                   # 直接给 HITRAN 分子号
        M = int(s)
        import hapi
        return str(hapi.moleculeName(M)).upper(), M
    if s in idx:
        return s, idx[s]["M"]
    for f, e in idx.items():                          # 容错：大小写/简写
        if f.replace("(", "").replace(")", "") == s.replace("(", "").replace(")", ""):
            return f, e["M"]
    raise ValueError(
        f"[hitran] 未知物种 '{name}'（HITRAN 逐线库官方表无此分子）。"
        f"可调 hitran_species 不传 name 获取官方全表；共 {len(idx)} 个分子。"
        f"若该分子为丙烷/丁烷/VOC 等重分子：HITRAN2024 采用双库架构，它可能收录于"
        f"截面子库（hitran.org/xsc，600+ 分子，网页登录下载、无在线 API）——"
        f"请用 hitran_cross_section 读入本地下载的截面文件。")

def _isotopologues(M, iso, min_abundance=1e-4, max_n=6):
    """返回 [(I, 自然丰度)]。
    iso=None → 官方主同位素（丰度最大）；iso='all' → 按丰度取前 N 个（全同位素近似）；
    iso=int   → 指定同位素。
    """
    idx = _official_species()
    formula = next(f for f, e in idx.items() if e["M"] == M)
    avail = [(d["I"], d["abundance"]) for d in idx[formula]["isotopologues"]]
    if not avail:
        return [(1, 1.0)]
    if iso is None:
        return [max(avail, key=lambda t: t[1])]
    if isinstance(iso, str) and iso.strip().lower() in ("all", "全部", "full"):
        sel = [a for a in avail if a[1] >= float(min_abundance)][:int(max_n)]
        return sel or [max(avail, key=lambda t: t[1])]
    I = int(iso)
    return [(I, dict(avail).get(I, 1.0))]


def _ensure_table_for(M, I, numin, numax, force=False):
    """保证拿到一张**真正覆盖** [numin,numax] 的线表。

    修掉的坑：hapi/ht.fetch 看到同名表已存在就跳过下载，于是请求新窗口时
    仍用旧线表 → 谱线静默缺失 → 被误读成"该气体无干扰"。
    策略：先查覆盖区间，未覆盖则用带窗口后缀的表名重抓（互不污染）。
    返回 (table, coverage, refetched)。
    """
    import hapi
    formula = _formula(M)
    base = f"{formula}_{M}_{I}"
    wtable = f"{base}_{_wnum(numin)}_{_wnum(numax)}"
    if not force:
        if _coverage(wtable) is not None:      # 之前已按此精确窗口抓过 → 直接复用
            return wtable, _coverage(wtable), False   # （谱线位置≠窗口边界，勿再查覆盖）
        cov = _coverage(base)
        if cov and cov[0] <= numin and cov[1] >= numax:
            return base, cov, False
    table = wtable
    if force or _coverage(table) is None:
        with _quiet():                       # HAPI 下载日志不能进协议流
            try:
                hapi.fetch(table, M, I, numin, numax)
            except Exception as e:
                hint = ""
                if "daily limit" in str(e).lower() or "exceeded" in str(e).lower():
                    hint = ("（HITRAN 官方每日抓取配额已超限：今日请勿再 force 重抓，"
                            "尽量复用缓存；确认已配置 API key：tools/hitran_api_key.txt）")
                raise RuntimeError(
                    f"[hitran][防呆] 抓取 {formula}(M={M},I={I}) 于 {numin}-{numax} cm-1 失败：{e}。"
                    f"常见原因：该窗口无 HITRAN 收录线 / 分子号或同位素不存在 / 无网络 / 官方每日配额超限{hint}。"
                    f"严禁把失败当作'无干扰'。") from e
    cov = _coverage(table)
    if cov is None:
        raise RuntimeError(f"[hitran][防呆] 抓取失败：{formula} 在 {numin}-{numax} cm-1 无线表")
    if cov[2] == 0:
        raise RuntimeError(
            f"[hitran][防呆] 表 '{table}' 在 {numin}-{numax} cm-1 返回 0 条谱线。"
            f"该分子/同位素在此窗口无 HITRAN 收录线，严禁当作'无干扰/平谱'使用。")
    return table, cov, True


PROFILES = {                      # 官方 HAPI 谱函数（同名直调，不自己造线型）
    "voigt": "absorptionCoefficient_Voigt",
    "lorentz": "absorptionCoefficient_Lorentz",
    "gauss": "absorptionCoefficient_Gauss",
    "doppler": "absorptionCoefficient_Doppler",
    "ht": "absorptionCoefficient_HT",           # Hartmann-Tran（官方旗舰线型）
    "sdvoigt": "absorptionCoefficient_SDVoigt", # speed-dependent Voigt
}


def _diluent_dict(diluent):
    """展宽浴：None/空 → {'air':1.0}；'self' → {'self':1.0}；也可给 dict。"""
    if not diluent:
        return {"air": 1.0}
    if isinstance(diluent, str):
        return {diluent.strip(): 1.0}
    return {str(k): float(v) for k, v in dict(diluent).items()}


def _absorption(name, iso, numin, numax, T, P, step, wingHW, hitran_units,
                force=False, min_abundance=1e-4, profile="voigt", diluent=None):
    """窗口安全的吸收谱计算（绕开 ht.absorption 的表名复用问题）。

    同位素口径（需在结论中显式声明主同位素近似或全同位素近似）：
      iso=None  → 主同位素近似：Components=[(M, I, 1.0)]，即纯主同位素的 α_pure
      iso='all' → 全同位素近似：各同位素按官方自然丰度加权求和
    单同位素时权重必须是 1.0（纯气体），不可误传自然丰度，否则 α 会凭空少 1%~2%。
    """
    ht, np = _hitran(), _np()
    import hapi
    from hapi import absorptionCoefficient_Voigt
    formula, M = _resolve_M(name)
    isos = _isotopologues(M, iso, min_abundance)
    full = len(isos) > 1

    entries, skipped = [], []
    for I, ab in isos:
        try:
            table, cov, refetched = _ensure_table_for(M, I, numin, numax, force)
        except Exception as e:                 # 稀有同位素抓不到 → 跳过并报告，不拖垮整体
            skipped.append({"I": I, "abundance": ab, "reason": str(e)[:160]})
            continue
        nu_all = np.asarray(hapi.getColumn(table, "nu"), dtype=float)
        entries.append({"table": table, "I": I, "ab": ab, "cov": cov,
                        "refetched": refetched,
                        "n_in": int(((nu_all >= numin) & (nu_all <= numax)).sum())})
    if not entries:
        raise RuntimeError(f"[hitran][防呆] {formula} 的所有同位素在 {numin}-{numax} cm-1 均抓取失败：{skipped}")

    pkey = str(profile or "voigt").strip().lower()
    if pkey not in PROFILES:
        raise ValueError(f"[hitran] 未知线型 '{profile}'，官方可选: {sorted(PROFILES)}")
    bath = _diluent_dict(diluent)
    nu, coef = getattr(hapi, PROFILES[pkey])(
        Components=[(M, e["I"], e["ab"] if full else 1.0) for e in entries],
        SourceTables=[e["table"] for e in entries],
        WavenumberRange=(float(numin), float(numax)), WavenumberStep=float(step),
        WavenumberWingHW=float(wingHW), HITRAN_units=bool(hitran_units),
        Environment={"T": float(T), "p": float(P), "Diluent": bath})
    tinfo = {"molecule": formula, "M": M, "profile": pkey, "diluent": bath,
             "isotope_mode": "all(自然丰度加权)" if full else f"single(I={entries[0]['I']})",
             "table": ",".join(e["table"] for e in entries),
             "coverage_cm-1": [round(min(e["cov"][0] for e in entries), 3),
                               round(max(e["cov"][1] for e in entries), 3)],
             "n_lines_table": sum(e["cov"][2] for e in entries),
             "n_lines_in_window": sum(e["n_in"] for e in entries),
             "refetched": any(e["refetched"] for e in entries),
             "components": [{"I": e["I"], "abundance": e["ab"], "table": e["table"]}
                            for e in entries]}
    if skipped:
        tinfo["skipped_isotopologues"] = skipped
    return np.asarray(nu, dtype=float), np.asarray(coef, dtype=float), tinfo


DEFAULTS = {"T": 296.0, "P": 1.01325, "step": 0.01, "wingHW": 50.0, "mode": "alpha"}


def _resolve_defaults(kw, strict=False):
    """把未给的参数换成默认值，并如实列出"哪些是默认的"。

    strict=True 时 T / P 必须显式给出 → 直接报错，强制调用方（AI）回头向用户确认，
    而不是默默用 296 K / 1 atm 算出一个"看起来对"的谱。
    """
    assumed = []
    if strict and (kw.get("T") is None or kw.get("P") is None):
        raise ValueError(
            "[需确认] strict 模式：T（温度 K）与 P（气压 atm）必须由用户明确给出。"
            "不同 T/P 下截面差异极大，禁止用默认值代替——请先向用户确认工况。")
    for k, v in DEFAULTS.items():
        if kw.get(k) is None:
            kw[k] = v
            assumed.append(f"{k}={v}")
    return kw, assumed


def _compute(specs, numin, numax, T=296.0, P=1.01325, step=0.01, wingHW=50.0,
             mode="alpha", path_length_cm=None, hitran_units=False,
             profile="voigt", diluent=None, min_abundance=1e-4):
    """算谱核心：返回 dict(nu, per{label:coef}, total, trans, meta)。

    混合气纪律（物理正确性要求）：α_i = x_i · α_pure_i(T, P, 空气浴)，
    绝不用 x·P 当分压；截面模式（hitran_units=True）不按摩尔分数缩放。
    窗口纪律：线表必须真正覆盖请求窗口，否则自动按窗口重抓（见 _ensure_table）。
    """
    ht, np = _hitran(), _np()
    specs = _norm_specs(specs)
    numin, numax, T, P, step, wingHW = (float(numin), float(numax), float(T),
                                        float(P), float(step), float(wingHW))
    if mode not in ("alpha", "transmittance", "both"):
        raise ValueError(f"mode 必须是 alpha / transmittance / both，收到 {mode!r}")

    nu = None
    per, peaks, tables, warnings = {}, {}, {}, []
    for sp in specs:
        name, iso, x = sp["name"], sp["iso"], sp["mole_frac"]
        # 输入护栏（沿用 hitran.py 第一层防呆）；纯气体 x=1 不传，免"是否主成分"噪声提示
        with _quiet() as gbuf:
            # 护栏沿用 hitran.py；但它的分子白名单是本地字典，官方表里有的分子可能不在其中，
            # 此时用合法占位名只走数值校验（分子合法性已由官方 ISO 表确认）。
            ht._validate_params(name if name in ht.SPECIES else "CO",
                                numin, numax, T, P, step,
                                mole_frac=None if abs(x - 1.0) < 1e-12 else x)
        for ln in gbuf.getvalue().splitlines():      # 软警告也要进 warnings，AI 才看得见
            if "[输入提示]" in ln:
                warnings.append(ln.strip())
        nu_i, coef, tinfo = _absorption(name, iso, numin, numax, T, P, step,
                                        wingHW, hitran_units, sp.get("force", False),
                                        min_abundance, profile, diluent)
        nu_i = np.asarray(nu_i, dtype=float)
        coef = np.asarray(coef, dtype=float)
        if not hitran_units:
            coef = coef * x                      # 混合气缩放（物理正确）
        if nu is None:
            nu = nu_i
        label = name if abs(x - 1.0) < 1e-12 else f"{name}@{x:g}"
        per[label] = coef
        tables[label] = tinfo
        peaks[label] = {"peak_value": float(coef.max()),
                        "peak_nu": float(nu_i[int(coef.argmax())]),
                        "integral": float(np.trapezoid(coef, nu_i)) if hasattr(np, "trapezoid")
                        else float(np.trapz(coef, nu_i))}
        # 单组分空谱护栏：严禁把"线表未覆盖/无收录线"静默当成"无干扰"
        if coef.size and float(coef.max()) == 0.0:
            warnings.append(
                f"[{label}] 窗口 {numin}–{numax} cm-1 内吸收恒为 0："
                f"线表 {tinfo['table']} 覆盖 {tinfo['coverage']}，"
                f"窗口内线数 {tinfo['n_lines_in_window']}。"
                f"不得据此判定'无干扰'——请先确认分子/同位素或窗口。")

    total = sum(per.values()) if per else None
    # 结果轮询（第二层防呆）：异常结果以 warnings 返回而非静默放过
    tag = "+".join(per) if len(per) > 1 else (list(per)[0] if per else "")
    warnings += list(ht.check_spectrum(nu, total, tag, numin=numin, numax=numax,
                                       T=T, P=P, hitran_units=hitran_units) or [])

    trans = None
    if mode in ("transmittance", "both"):
        L = float(path_length_cm if path_length_cm is not None else 1.0)
        trans = np.exp(-total * L)

    return {"nu": nu, "per": per, "total": total, "trans": trans,
            "peaks": peaks, "warnings": warnings, "tables": tables, "specs": specs,
            "numin": numin, "numax": numax, "T": T, "P": P, "step": step,
            "wingHW": wingHW, "mode": mode, "hitran_units": bool(hitran_units),
            "profile": profile, "diluent": _diluent_dict(diluent),
            "path_length_cm": path_length_cm}


def _csv_path(res, extra=""):
    names = "+".join(s["name"] for s in res["specs"])[:40]
    return OUT_DIR / _slug(f"{names}_{res['numin']}-{res['numax']}cm-1_"
                           f"{res['T']}K_{res['P']}atm{extra}.csv")


def _save_csv(res):
    """落盘 CSV（含溯源水印）。单分子走 hitran.save_spectrum_csv 复用其表头。"""
    ht, np = _hitran(), _np()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = _csv_path(res)
    cols, labels = [res["nu"]], ["wavenumber_cm-1"]
    unit = "sigma_cm2_per_molecule" if res["hitran_units"] else "alpha_cm-1"
    for label, c in res["per"].items():
        cols.append(c)
        labels.append(f"{unit}_{_slug(label)}")
    if len(res["per"]) > 1:
        cols.append(res["total"]); labels.append(f"{unit}_TOTAL")
    if res["trans"] is not None:
        cols.append(res["trans"]); labels.append("transmittance")

    dil = "+".join(f"{k}:{v:g}" for k, v in res["diluent"].items())
    if len(res["per"]) == 1:
        sp = res["specs"][0]
        head = ht.provenance(sp["name"], res["numin"], res["numax"], res["T"],
                             res["P"], sp["iso"], res["hitran_units"])
        head += (f"\n# ACTUAL condition: diluent={dil}, profile={res['profile']}, "
                 f"step={res['step']}, wingHW={res['wingHW']}")
        if sp["mole_frac"] != 1.0:
            head += f"\n# mole_frac={sp['mole_frac']:g} (alpha = x * alpha_pure@T,P,{dil} bath)"
    else:
        head = "\n".join([
            "# ===== HITRAN mixed spectrum provenance =====",
            ht.CITATION,
            "# " + "; ".join(f"{s['name']}(iso={s['iso'] or 'default'}, x={s['mole_frac']:g})"
                             for s in res["specs"]),
            f"# condition: T={res['T']} K, P={res['P']} atm, diluent={dil}, "
            f"profile={res['profile']}, step={res['step']}, wingHW={res['wingHW']}",
            f"# units: {unit};  mixing rule: alpha_i = x_i * alpha_pure_i(T,P,{dil} bath)",
            "# ===========================================",
        ])
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n")
        f.write(",".join(labels) + "\n")
        np.savetxt(f, np.column_stack(cols), delimiter=",", fmt="%.6e")
    return path


# ───────────────────────── 工具实现 ─────────────────────────

def t_species(name=None, with_isotopologues=False):
    """物种/同位素速查（**全部来自 HAPI 官方 ISO 表**，无本地硬编码）。

    name 可以是分子式（CO）或 HITRAN 分子号（5）；省略则返回官方全表。
    """
    ht = _hitran()
    idx = _official_species()
    if name:
        f, M = _resolve_M(name)
        e = idx[f]
        out = {"molecule": f, "M": M,
               "main_iso": e["main_iso"],
               "n_isotopologues": len(e["isotopologues"]), "citation": ht.CITATION}
        if with_isotopologues:
            out["isotopologues"] = e["isotopologues"]
        return out
    return {"count": len(idx), "source": "HAPI official ISO table (HITRAN2024)",
            "species": {f: {"M": e["M"], "main_iso": e["main_iso"]}
                        for f, e in sorted(idx.items())},
            "citation": ht.CITATION}


def t_fetch(name, numin, numax, iso=None, force=False):
    """抓取线表到统一缓存 Hitran_Data/，返回表名、覆盖区间与窗口内线数。

    关键：窗口未被缓存表覆盖时自动重抓，并如实报告"是否覆盖请求窗口"，
    避免历史上"fetch 返回 194 条线（其实是旧表行数）"的误导。
    """
    ht = _hitran()
    formula, M = _resolve_M(name)
    I = _isotopologues(M, iso)[0][0]
    table, cov, refetched = _ensure_table_for(M, I, float(numin), float(numax), bool(force))
    np = _np()
    import hapi
    nu = np.asarray(hapi.getColumn(table, "nu"), dtype=float)
    n_in = int(((nu >= float(numin)) & (nu <= float(numax))).sum())
    out = {"molecule": formula, "M": M, "iso": I,
           "table": table, "n_lines_table": int(cov[2]), "n_lines_in_window": n_in,
           "coverage_cm-1": [round(cov[0], 3), round(cov[1], 3)],
           "requested_window_cm-1": [float(numin), float(numax)],
           "covers_request": bool(cov[0] <= numin and cov[1] >= numax),
           "refetched": refetched, "cache_dir": str(ht.CACHE_ROOT)}
    if n_in == 0:
        out["warning"] = (f"{name} 在 {numin}-{numax} cm-1 内 0 条收录线；"
                          f"严禁据此判定'无干扰'，请确认分子/同位素/窗口。")
    return out


def t_lines(name, numin, numax, iso=None, top_n=10, min_intensity=None, force=False):
    """窗口内最强 N 条线（选线/干扰分析用）：位置、线强、空气展宽、低态能量。

    线表按窗口自动校正（见 _ensure_table）；窗口内 0 条线时给出显式 warning。
    """
    ht, np = _hitran(), _np()
    import hapi
    numin, numax = float(numin), float(numax)
    formula, M = _resolve_M(name)
    I = _isotopologues(M, iso)[0][0]
    table, cov, refetched = _ensure_table_for(M, I, numin, numax, bool(force))
    nu = np.asarray(hapi.getColumn(table, "nu"), dtype=float)
    sw = np.asarray(hapi.getColumn(table, "sw"), dtype=float)
    try:
        ga = np.asarray(hapi.getColumn(table, "gamma_air"), dtype=float)
        el = np.asarray(hapi.getColumn(table, "elower"), dtype=float)
    except Exception:                       # 老表可能缺列，降级为只给位置/强度
        ga = np.zeros_like(nu); el = np.zeros_like(nu)
    m = (nu >= numin) & (nu <= numax)
    if min_intensity is not None:
        m &= sw >= float(min_intensity)
    idx = np.where(m)[0]
    idx = idx[np.argsort(sw[idx])[::-1]][: int(top_n)]
    out = {"molecule": formula, "M": M, "iso": I,
           "table": table, "coverage_cm-1": [round(cov[0], 3), round(cov[1], 3)],
           "n_lines_table": int(cov[2]), "n_in_window": int(m.sum()),
           "refetched": refetched,
           "lines": [{"nu_cm-1": float(nu[i]), "S_cm_per_molecule": float(sw[i]),
                      "gamma_air": float(ga[i]), "E_lower_cm-1": float(el[i])}
                     for i in idx]}
    if int(m.sum()) == 0:
        out["warning"] = (f"{name} 在 {numin}-{numax} cm-1 内 0 条收录线"
                          f"（线表覆盖 {round(cov[0],2)}–{round(cov[1],2)} cm-1），"
                          f"严禁据此判定'无干扰'。")
    return out


def t_spectrum(specs=None, name=None, mole_frac=None, iso=None, numin=None, numax=None,
               T=None, P=None, step=None, wingHW=None, mode=None,
               path_length_cm=None, hitran_units=False, save=True, force=False,
               strict=False, min_abundance=1e-4, profile="voigt", diluent=None):
    """吸收/透过率谱（支持混合气），返回 CSV 路径 + 峰值/积分 + 线表信息 + 告警。

    未给出的参数会用默认值，但**如实列在 assumed_defaults 里**，调用方应据此向用户确认
    （尤其是 T / P / 各组分摩尔分数）。strict=True 时 T、P 未给直接报错，强制先确认。
    """
    sp_list = _norm_specs(specs, name, mole_frac, iso)
    if force:
        for s in sp_list:
            s["force"] = True
    kw, assumed = _resolve_defaults({"T": T, "P": P, "step": step,
                                     "wingHW": wingHW, "mode": mode}, strict)
    T, P, step, wingHW, mode = (kw["T"], kw["P"], kw["step"], kw["wingHW"], kw["mode"])
    for s in sp_list:                        # 浓度未给 = 假设纯气体，必须回问用户
        if not s.get("mole_frac_given"):
            assumed.append(f"{s['name']}.mole_frac=1 (纯气体)")
    if mode in ("transmittance", "both") and path_length_cm is None:
        assumed.append("path_length_cm=1 (默认光程)")

    res = _compute(sp_list, numin, numax, T, P, step, wingHW, mode,
                   path_length_cm, hitran_units, profile, diluent, min_abundance)
    warnings = list(res["warnings"])
    if len(sp_list) > 1 and any(not s.get("mole_frac_given") for s in sp_list):
        warnings.append(
            "多组分但未提供摩尔分数 → 已按纯气体 x=1 计算，物理上不成立。"
            "请向用户确认各组分浓度（混合气 α_i = x_i·α_pure_i(T,P,空气浴)）。")
    out = {"peaks": res["peaks"], "warnings": warnings,
           "tables": res["tables"],
           "assumed_defaults": assumed, "needs_confirm": bool(assumed),
           "units": "cm2/molecule" if hitran_units else "cm-1",
           "n_points": int(len(res["nu"])), "csv": None}
    if res["trans"] is not None:                 # 透过率摘要（谷值与位置）
        i = int(_np().asarray(res["trans"]).argmin())
        out["transmittance"] = {"min": float(res["trans"][i]),
                                "at_nu_cm-1": float(res["nu"][i]),
                                "path_length_cm": float(path_length_cm or 1.0)}
    if len(res["per"]) > 1:
        np = _np()
        out["total_peak"] = {"peak_value": float(res["total"].max()),
                             "peak_nu": float(res["nu"][int(res["total"].argmax())]),
                             "integral": float(np.trapezoid(res["total"], res["nu"]))
                             if hasattr(np, "trapezoid") else float(np.trapz(res["total"], res["nu"]))}
    if save:
        out["csv"] = str(_save_csv(res))
    return out


def t_plot(specs=None, name=None, mole_frac=None, iso=None, numin=None, numax=None,
           T=None, P=None, step=None, wingHW=None, mode=None,
           path_length_cm=None, hitran_units=False, title=None, ylog=False,
           dpi=160, save_csv=True, force=False, strict=False,
           profile="voigt", diluent=None, min_abundance=1e-4):
    """绘制谱图 PNG（多物种叠加 + 总谱），返回 PNG/CSV 路径。参数口径同 hitran_spectrum。"""
    sp_list = _norm_specs(specs, name, mole_frac, iso)
    if force:
        for s in sp_list:
            s["force"] = True
    kw, assumed = _resolve_defaults({"T": T, "P": P, "step": step,
                                     "wingHW": wingHW, "mode": mode}, strict)
    T, P, step, wingHW, mode = (kw["T"], kw["P"], kw["step"], kw["wingHW"], kw["mode"])
    for s in sp_list:
        if not s.get("mole_frac_given"):
            assumed.append(f"{s['name']}.mole_frac=1 (纯气体)")
    res = _compute(sp_list, numin, numax, T, P, step, wingHW, mode,
                   path_length_cm, hitran_units, profile, diluent, min_abundance)
    warnings = list(res["warnings"])
    if len(sp_list) > 1 and any(not s.get("mole_frac_given") for s in sp_list):
        warnings.append(
            "多组分但未提供摩尔分数 → 已按纯气体 x=1 计算，物理上不成立。"
            "请向用户确认各组分浓度（混合气 α_i = x_i·α_pure_i(T,P,空气浴)）。")

    os.environ.setdefault("MPLBACKEND", "Agg")
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    nu, per, total = res["nu"], res["per"], res["total"]
    show_t = mode == "transmittance" and res["trans"] is not None
    fig, ax = plt.subplots(figsize=(9.2, 5.0), dpi=int(dpi))
    if show_t:
        ax.plot(nu, res["trans"], color="#1f4e79", lw=1.1, label="transmittance")
        ylab = f"Transmittance (L={res['path_length_cm'] or 1.0:g} cm)"
    else:
        for label, c in per.items():
            ax.plot(nu, c, lw=0.9, alpha=0.75, label=label)
        if len(per) > 1:
            ax.plot(nu, total, color="k", lw=1.3, label="TOTAL")
        ylab = ("Cross section σ (cm²/molecule)" if hitran_units
                else "Absorption coefficient α (cm⁻¹)")
    if ylog:
        ax.set_yscale("log")

    ax.set_xlabel("Wavenumber (cm⁻¹)")
    ax.set_ylabel(ylab)
    ax.set_title(title or f"{'+'.join(per)}  {res['numin']}–{res['numax']} cm⁻¹"
                          f"  T={res['T']:g} K  P={res['P']:g} atm")
    ax.grid(alpha=0.25, lw=0.6)
    ax.legend(fontsize=8, framealpha=0.9)
    if not ylog:                      # ticklabel_format 只支持线性轴（对数轴会抛异常）
        ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
    fig.text(0.01, 0.01, "HITRAN2024 via HAPI 1.3.0.0 · TIPS-2025 · Voigt/air",
             fontsize=6.5, color="#666666")
    fig.tight_layout(rect=(0, 0.02, 1, 1))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / _slug(f"{'+'.join(per)[:40]}_{res['numin']}-{res['numax']}cm-1_"
                          f"{res['T']}K_{res['P']}atm.png")
    fig.savefig(png, dpi=int(dpi))
    plt.close(fig)

    out = {"png": str(png), "peaks": res["peaks"], "warnings": warnings,
           "tables": res["tables"],
           "assumed_defaults": assumed, "needs_confirm": bool(assumed),
           "n_points": int(len(nu))}
    if save_csv:
        out["csv"] = str(_save_csv(res))
    return out


def _read_hotw_file(path):
    """读 HITRAN-on-the-Web 截面文件（两列：nu, coef[cm2/molecule]）。

    兼容：空行/注释行（# 开头）自动跳过；注释行前若干行收集为文件头（溯源用）。
    数据行必须恰好两列浮点；单列或多列行忽略并计数（异常太多则报错）。
    """
    path = Path(str(path))
    if not path.exists():
        raise ValueError(f"[hitran_cross_section] 截面文件不存在: {path}")
    if path.is_dir():
        raise ValueError(f"[hitran_cross_section] 给出的是目录而非文件: {path}")
    nu, coef, header, skipped = [], [], [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for ln in f:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("#"):
                if not nu:
                    header.append(s)
                continue
            parts = s.split()
            if len(parts) == 2:
                try:
                    nu.append(float(parts[0]))
                    coef.append(float(parts[1]))
                    continue
                except ValueError:
                    pass
            skipped += 1
            if not nu and skipped > 200:      # 头部垃圾行过多，疑似非截面文件
                break
    if not nu:
        raise ValueError(
            f"[hitran_cross_section] '{path.name}' 中未解析到两列数值数据（nu, coef）。"
            f"请确认是 hitran.org/xsc 下载的 HOTW 截面文件（形如 '2950.0000 1.23e-21'）。")
    return _np().asarray(nu, dtype=float), _np().asarray(coef, dtype=float), header, skipped


def t_cross_section(file_path=None, source_label=None, numin=None, numax=None,
                    title=None, ylog=False, dpi=160, save_csv=True):
    """读入本地 HOTW 截面文件（hitran.org/xsc 下载，两列 ν–σ）→ 截窗 → 绘图 PNG + 溯源 CSV。

    桥接 HITRAN 双库架构的截面通道：逐线库（61 分子）走 HAPI 在线 API；截面库
    （600+ 重分子，如丙烷/丁烷/VOC）只经 Web Portal 登录下载文件，无在线 API。
    本工具把下载的截面文件接入同一套产物链路（CSV/PNG 带溯源水印），
    实现截面分子"下载一次、缓存复用、随时叠加分析"。

    参数：file_path(必填, 本地 .txt 截面文件路径)；source_label(溯源标签，如
    "C3H8 PNNL 298.15K Sharpe2004"；默认取文件名)；numin/numax(截窗 cm-1，默认全谱)；
    title/ylog/dpi 同 hitran_plot。数据单位固定为 σ (cm²/molecule)。
    """
    if not file_path:
        raise ValueError("[hitran_cross_section] 必须提供 file_path（本地 HOTW 截面文件路径）")
    nu, coef, header, skipped = _read_hotw_file(file_path)
    label = str(source_label or Path(str(file_path)).name)
    win = [float(numin) if numin is not None else float(nu.min()),
           float(numax) if numax is not None else float(nu.max())]
    if not (win[0] <= win[1]):
        raise ValueError(f"[hitran_cross_section] 窗口非法: numin={win[0]} > numax={win[1]}")
    m = (nu >= win[0]) & (nu <= win[1])
    nu_w, coef_w = nu[m], coef[m]
    warnings = []
    if nu_w.size == 0:
        warnings.append(f"窗口 {win[0]:g}–{win[1]:g} cm-1 内 0 个数据点（文件覆盖 "
                        f"{float(nu.min()):g}–{float(nu.max()):g} cm-1），未截到数据。")
    if skipped:
        warnings.append(f"跳过 {skipped} 个非两列数据行（注释/表头已忽略）。")

    # —— 绘图（复用 hitran_plot 风格） ——
    os.environ.setdefault("MPLBACKEND", "Agg")
    import matplotlib
    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9.2, 5.0), dpi=int(dpi))
    if nu_w.size:
        ax.plot(nu_w, coef_w, lw=0.9, color="#1f4e79", label=label)
        ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
    ax.set_xlabel("Wavenumber (cm⁻¹)")
    ax.set_ylabel("Cross section σ (cm²/molecule)")
    ax.set_title(title or f"{label}  {win[0]:g}–{win[1]:g} cm⁻¹")
    ax.grid(alpha=0.25, lw=0.6)
    if nu_w.size:
        ax.legend(fontsize=8, framealpha=0.9)
    if ylog:
        ax.set_yscale("log")
    ax.set_xlim(win[0], win[1])
    fig.text(0.01, 0.01,
             f"HITRAN2024 cross-section file (HOTW) · source: {label}",
             fontsize=6.5, color="#666666")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / _slug(f"{label}_{win[0]}-{win[1]}cm-1_XSC.png")
    fig.savefig(png, dpi=int(dpi))
    plt.close(fig)

    # —— CSV（带溯源水印） ——
    csv = None
    if save_csv:
        src = label
        head = "\n".join([
            "# ===== HITRAN cross-section file (HOTW) =====",
            f"# source: {src}",
            f"# file: {Path(str(file_path)).resolve()}",
            f"# window_cm-1: {win[0]:g} - {win[1]:g};  units: sigma cm2/molecule",
            "# (data not from HITRAN2024 line list; cite the original reference"
            " embedded in the source file header)",
        ])
        if header:
            head += "\n# file_header:\n" + "\n".join(f"#   {h[:120]}" for h in header[:20])
        csv = OUT_DIR / _slug(f"{label}_{win[0]}-{win[1]}cm-1_XSC.csv")
        with open(csv, "w", encoding="utf-8") as f:
            f.write(head + "\nwavenumber_cm-1,sigma_cm2_per_molecule\n")
            _np().savetxt(f, _np().column_stack([nu, coef]), delimiter=",", fmt="%.6e")

    out = {"source": str(Path(str(file_path)).resolve()), "source_label": label,
           "file_header_lines": header[:20], "skipped_lines": skipped,
           "units": "sigma_cm2_per_molecule",
           "file_coverage_cm-1": [round(float(nu.min()), 4), round(float(nu.max()), 4)],
           "window_cm-1": [round(win[0], 4), round(win[1], 4)],
           "n_points_file": int(nu.size), "n_points_in_window": int(nu_w.size),
           "warnings": warnings, "png": str(png), "csv": str(csv) if csv else None}
    if nu_w.size:
        i = int(coef_w.argmax())
        out["peak"] = {"sigma_cm2_per_molecule": float(coef_w[i]),
                       "at_nu_cm-1": float(nu_w[i])}
    return out


def t_partition_sum(name=None, M=None, I=None, T=296.0, tips_version=None):
    """配分函数 Q(T)，走官方 TIPS（2025/2021/2017/2011 可选，默认 HAPI 内置 2025）。"""
    ht = _hitran()
    import hapi
    if name:
        formula, M = _resolve_M(name)
        I0 = _isotopologues(M, I)[0][0]
    else:
        if M is None:
            raise ValueError("需给出 name 或 M")
        I0 = 1 if I is None else int(I)
        formula = _formula(int(M))
    kwargs = {} if tips_version is None else {"version": int(tips_version)}
    Q = hapi.partitionSum(int(M), int(I0), float(T), **kwargs)
    try:
        Q = float(_np().asarray(Q, dtype=float).ravel()[0])
    except Exception:
        Q = float(Q)
    return {"molecule": formula, "M": int(M), "I": int(I0), "T": float(T), "Q": Q,
            "tips_version": int(tips_version) if tips_version else 2025}


# ───────────────────────── MCP 协议层 ─────────────────────────

_CONFIRM_NOTE = ("注意：数据全部实时取自 HITRANonline（经 HAPI）。若用户未说明温度/气压/"
                 "波数范围/摩尔分数/线型/展宽气体，应先向用户确认再调用；"
                 "返回中的 assumed_defaults 列出了本次被迫使用的默认值，needs_confirm=true 时"
                 "必须向用户复核关键工况，不得把默认值当成用户的意图。")

# 2026-09-08 客户端兼容 workaround：豆包 MCP 客户端对 inputSchema 中的
# "数组 / 嵌套对象 / 联合类型" 参数定义解析失败（tools/list 里只暴露空对象，
# 导致参数无法传入、调用永远空参）。故全部工具 schema 一律改为扁平、单类型、
# 标量参数。服务器函数本体不改：specs 数组、diluent 字典等仍受内部支持，
# 只是不再向客户端广告。豆包客户端修复 schema 摄入后，可恢复丰富参数形式。
TOOLS = [
    {"name": "hitran_species",
     "description": "查询 HITRAN 官方分子表（HAPI ISO 表，覆盖全部分子与同位素）：分子号 M、主同位素、"
                    "各同位素自然丰度与质量；不传 name 返回官方全表。",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string", "description": "分子式（CO/H2O/CH4）或 HITRAN 分子号（5）"},
                                    "with_isotopologues": {"type": "boolean",
                                                           "description": "True 同时列出该分子全部同位素（含丰度）"}}}},
    {"name": "hitran_fetch",
     "description": "从 HITRANonline 抓取某物种在波数窗口内的线表到本地缓存 Hitran_Data/；"
                    "线表未覆盖请求窗口时自动按窗口重抓。0 线/抓取失败会报错，不静默返回空谱。",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string"},
                                    "numin": {"type": "number"}, "numax": {"type": "number"},
                                    "iso": {"type": "string", "description": "同位素号（如 1）或 'all'（全同位素）；默认主同位素"},
                                    "force": {"type": "boolean", "description": "True 强制重抓"}},
                     "required": ["name", "numin", "numax"]}},
    {"name": "hitran_lines",
     "description": "列出窗口内最强的 N 条谱线（波数、线强、空气展宽、低态能量），用于选线与干扰分析。",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string"},
                                    "numin": {"type": "number"}, "numax": {"type": "number"},
                                    "iso": {"type": "string", "description": "同位素号（如 1）或 'all'"},
                                    "top_n": {"type": "integer", "description": "返回条数，默认 10"},
                                    "min_intensity": {"type": "number"},
                                    "force": {"type": "boolean", "description": "True 强制按当前窗口重抓线表"}},
                     "required": ["name", "numin", "numax"]}},
    {"name": "hitran_spectrum",
     "description": "计算吸收系数 α / 透过率谱（单分子或全同位素），落盘带溯源水印的 CSV，"
                    "返回峰值、积分、线表信息与告警。多组分混合请分次调用后自行叠加。"
                    + _CONFIRM_NOTE,
     "inputSchema": {"type": "object",
                     "properties": {
                         "name": {"type": "string", "description": "分子式，如 CH4/CO2/H2O"},
                         "mole_frac": {"type": "number",
                                       "description": "摩尔分数 0~1；不填按纯气体 1 处理并在 assumed_defaults 里标记"},
                         "iso": {"type": "string", "description": "同位素号（如 1）或 'all'；默认主同位素"},
                         "numin": {"type": "number"}, "numax": {"type": "number",
                                                                 "description": "波数窗口 cm-1（必填，向用户确认）"},
                         "T": {"type": "number", "description": "温度 K（未给则用 296 并标记待确认）"},
                         "P": {"type": "number", "description": "气压 atm（未给则用 1.01325 并标记待确认）"},
                         "step": {"type": "number", "description": "波数步长 cm-1，默认 0.01"},
                         "wingHW": {"type": "number", "description": "线翼半宽 cm-1，默认 50"},
                         "mode": {"type": "string", "description": "alpha / transmittance / both"},
                         "path_length_cm": {"type": "number", "description": "光程 cm（透过率用，默认 1）"},
                         "hitran_units": {"type": "boolean", "description": "True 返回 cm2/molecule 截面（σ，不按 x 缩放）"},
                         "profile": {"type": "string",
                                     "description": "线型：voigt(默认)/lorentz/gauss/doppler/ht/sdvoigt（官方 HAPI 谱函数）"},
                         "diluent": {"type": "string", "description": "展宽浴：'air'(默认) 或 'self'"},
                         "min_abundance": {"type": "number", "description": "iso='all' 时的丰度下限，默认 1e-4"},
                         "strict": {"type": "boolean", "description": "True 时 T/P 未给则报错（强制先向用户确认）"},
                         "save": {"type": "boolean", "description": "是否落盘 CSV，默认 True"},
                         "force": {"type": "boolean", "description": "True 强制按当前窗口重抓线表"}},
                     "required": ["numin", "numax"]}},
    {"name": "hitran_plot",
     "description": "绘制谱图 PNG（单分子或全同位素），返回 PNG 与 CSV 路径。参数同 hitran_spectrum，另加 title/ylog/dpi。"
                    + _CONFIRM_NOTE,
     "inputSchema": {"type": "object",
                     "properties": {
                         "name": {"type": "string", "description": "分子式，如 CH4/CO2/H2O"},
                         "mole_frac": {"type": "number"},
                         "iso": {"type": "string"},
                         "numin": {"type": "number"}, "numax": {"type": "number"},
                         "T": {"type": "number"}, "P": {"type": "number"},
                         "step": {"type": "number"}, "wingHW": {"type": "number"},
                         "mode": {"type": "string"}, "path_length_cm": {"type": "number"},
                         "hitran_units": {"type": "boolean"},
                         "profile": {"type": "string"}, "diluent": {"type": "string"},
                         "min_abundance": {"type": "number"}, "strict": {"type": "boolean"},
                         "title": {"type": "string"}, "ylog": {"type": "boolean"},
                         "dpi": {"type": "integer"},
                         "force": {"type": "boolean", "description": "True 强制按当前窗口重抓线表"}},
                     "required": ["numin", "numax"]}},
    {"name": "hitran_partition_sum",
     "description": "配分函数 Q(T)，走官方 TIPS（2025 默认，可 2021/2017/2011），用于线强温度换算。",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string", "description": "分子式（与 M 二选一）"},
                                    "M": {"type": "integer", "description": "HITRAN 分子号"},
                                    "I": {"type": "integer", "description": "同位素号，默认主同位素"},
                                    "T": {"type": "number", "description": "温度 K，默认 296"},
                                    "tips_version": {"type": "integer",
                                                     "description": "TIPS 版本：2025/2021/2017/2011"}}}},
    {"name": "hitran_cross_section",
     "description": "读入本地 HOTW 截面文件（hitran.org/xsc 登录下载，两列 ν–σ，单位 cm²/molecule）"
                    "→ 截窗 → 绘图 PNG + 溯源 CSV。桥接 HITRAN2024 双库架构的截面通道："
                    "逐线库 61 分子走 HAPI 在线 API；截面库 600+ 重分子（丙烷/丁烷/VOC）"
                    "只经 Web Portal 下载文件、无在线 API。本工具把下载的截面文件接入同一套产物链路，"
                    "实现'下载一次、缓存复用、随时叠加分析'。",
     "inputSchema": {"type": "object",
                     "properties": {
                         "file_path": {"type": "string",
                                       "description": "必填：本地 HOTW 截面文件路径（两列：wavenumber_cm-1, sigma_cm2_per_molecule）"},
                         "source_label": {"type": "string",
                                          "description": "溯源标签，如 'C3H8 PNNL 298.15K Sharpe2004'；默认取文件名"},
                         "numin": {"type": "number", "description": "截窗下限 cm-1；默认全谱"},
                         "numax": {"type": "number", "description": "截窗上限 cm-1；默认全谱"},
                         "title": {"type": "string", "description": "图标题，默认 '<label>  <窗口> cm-1'"},
                         "ylog": {"type": "boolean", "description": "True 用对数坐标"},
                         "dpi": {"type": "integer", "description": "PNG 分辨率，默认 160"},
                         "save_csv": {"type": "boolean", "description": "是否落盘溯源 CSV，默认 True"}},
                     "required": ["file_path"]}},
]
DISPATCH = {
    "hitran_species": t_species,
    "hitran_fetch": t_fetch,
    "hitran_lines": t_lines,
    "hitran_spectrum": t_spectrum,
    "hitran_plot": t_plot,
    "hitran_partition_sum": t_partition_sum,
    "hitran_cross_section": t_cross_section,
}


def handle(req):
    """处理一条 JSON-RPC 请求 → (id, result, error)。通知类返回 (None, None, None)。"""
    method, rid = req.get("method"), req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        return rid, {"protocolVersion": PROTOCOL_VERSION,
                     "capabilities": {"tools": {"listChanged": False}},
                     "serverInfo": SERVER_INFO}, None
    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None, None, None
    if method == "ping":
        return rid, {}, None
    if method == "tools/list":
        return rid, {"tools": TOOLS}, None
    if method == "resources/list":
        return rid, {"resources": []}, None
    if method == "prompts/list":
        return rid, {"prompts": []}, None
    if method == "tools/call":
        tname = params.get("name")
        args = dict(params.get("arguments") or {})
        fn = DISPATCH.get(tname)
        if fn is None:
            return rid, {"content": [{"type": "text", "text": f"未知工具: {tname}"}],
                         "isError": True}, None
        try:
            with _quiet() as buf:                 # 捕获 HAPI 等所有 print
                result = fn(**args)
            log = buf.getvalue().strip()
            payload = _jsonable(result)
            if log:
                payload = dict(payload) if isinstance(payload, dict) else {"result": payload}
                payload.setdefault("log", log[-4000:])
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            return rid, {"content": [{"type": "text", "text": text}], "isError": False}, None
        except Exception as e:
            msg = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"
            return rid, {"content": [{"type": "text", "text": msg}], "isError": True}, None
    if rid is None:                                # 未知通知：忽略
        return None, None, None
    return rid, None, {"code": -32601, "message": f"method not found: {method}"}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        try:
            rid, result, error = handle(req)
        except Exception as e:                     # 协议层兜底，绝不崩
            rid, result, error = req.get("id"), None, {"code": -32603, "message": str(e)}
        if rid is None and error is None:
            continue
        out = {"jsonrpc": "2.0", "id": rid}
        if error is not None:
            out["error"] = error
        else:
            out["result"] = result
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def selftest():
    """冒烟自测（直接函数调用，不走协议）。"""
    print("— species:", t_species("CO")["M"])
    print("— lines  :", t_lines("CO", 2109, 2112, top_n=3)["lines"][0])
    print("— spec   :", {k: v for k, v in t_spectrum(name="CO", numin=2140, numax=2146,
                                                     T=296, P=1.0, step=0.01).items()
                         if k != "peaks"})
    mix = t_plot(specs=[{"name": "CO", "mole_frac": 100e-6}, {"name": "H2O", "mole_frac": 0.02}],
                 numin=2140, numax=2146, T=296, P=1.0, step=0.01)
    print("— plot   :", mix["png"])
    # 截面链路自测：合成 HOTW 截面文件（两列 ν–σ，高斯峰 @2967 cm-1 模拟 C3H8）
    import numpy as _np2
    nu_s = _np2.linspace(2800, 3100, 1501)
    sig = 1.6e-18 * _np2.exp(-((nu_s - 2967.0) / 8.0) ** 2)
    demo = OUT_DIR / "_demo_c3h8_pnnl.txt"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(demo, "w", encoding="utf-8") as f:
        f.write("# synthetic demo cross-section (not real data)\n")
        for a, b in zip(nu_s, sig):
            f.write(f"{a:.4f} {b:.6e}\n")
    xs = t_cross_section(file_path=str(demo), source_label="C3H8 demo",
                         numin=2900, numax=3000)
    print("— xsc    :", {k: xs[k] for k in ("n_points_file", "n_points_in_window", "peak")},
          "png:", xs["png"])


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
