# -*- coding: utf-8 -*-
"""
hitran — HITRAN 数据库调取与谱计算的统一薄壳（跨项目通用）

设计原则（KISS）：只做"调用官方 HAPI + 统一缓存 + 常用谱计算"三件事，
不重复造轮子，不硬编码任何单次实验参数。

职责边界
  1. 统一缓存目录，模块加载即 db_begin，fetch 自动落盘，避免缓存散落各 CWD。
  2. 把 HAPI 的三段式（fetch → table → absorption）封成 3 个常用函数。
  3. 谱计算统一收敛于 absorption()（吸收系数）；其余按需求由调用方基于 HAPI 直接组合，避免推测性泛化。
  4. 版本与引用口径：HITRAN2024 + TIPS-2025（HAPI 1.3.0.0 自带）。
  5. 防造假护栏：fetch 后强制校验线数（读磁盘 .data 物理行），空表一律硬报错，
     杜绝"无收录线被静默当成平谱"；provenance()/save_spectrum_csv() 给产物打官方溯源烙印，
     任何 CSV/图都能追到 HITRAN2024，不留孤儿数据。
6. 防呆双保险（本文件第 2 版新增）：
   - 第 1 层 _validate_params()：提问者/操作者把参数填错（波数颠倒、温度用成摄氏度、
     ppm 当成摩尔分数、步长大于窗口等）时，提前硬报错或给"输入提示"，绝不让垃圾输入
     流进 HAPI 算出看似合理的假谱。
   - 第 2 层 check_spectrum()（轮询）：算出谱之后 AI/用户都应调一次做"二次确认"。
     它像轮询器一样扫描结果（NaN/非单调/全零/量级离谱/窗口未覆盖），任何可疑都打印
     [结果轮询] 提示，避免"我自己把错当对"。save_spectrum_csv 落盘时自动轮询一次。

依赖：HAPI 1.3.0.0（pip install hitran-api）；Python 3.9+
"""
import os
import sys
from pathlib import Path

import hapi
from hapi import (db_begin, tableList, absorptionCoefficient_Voigt)
import numpy as np

# ---- 统一缓存目录：HITRAN 线表落盘处（fetch 自动写此目录）----
# 兼容源码运行与 PyInstaller 打包：冻结模式下用 exe 所在目录，源码模式用仓库根目录
if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).resolve().parent
else:
    _ROOT = Path(__file__).resolve().parent.parent
CACHE_ROOT = _ROOT / "Hitran_Data"

_CACHE_READY = False


def _init_cache():
    """惰性建缓存目录并 db_begin。目录只读/受限时给明确报错，而非 import 期 ImportError。

    幂等：多次调用只生效一次。任何取数入口（fetch/absorption）都先调它。
    """
    global _CACHE_READY
    if _CACHE_READY:
        return
    try:
        CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise RuntimeError(
            f"[hitran][防呆] 无法创建线表缓存目录 {CACHE_ROOT}：{e}。"
            f"请确认该路径可写（或把程序放到有写权限的目录）。") from e
    db_begin(str(CACHE_ROOT))  # 决定 .data/.header 落盘位置，必须在 fetch 前调用
    _CACHE_READY = True


# ---- 物种/同位素速查（全部由 HAPI 官方 ISO 表派生，不硬编码编号）----
# 表名一律用官方分子式（大写）：与 hitran_mcp 层 _formula(M) 完全一致，
# 杜绝"CSV 溯源水印里的表名和磁盘上真实缓存文件名对不上"。
def _build_species():
    """从 hapi.ISO 构建 {官方分子式: M} 与 {官方分子式: 主同位素 I}。

    主同位素 = 自然丰度最大者（官方口径），取代原先只覆盖 18 种的 ISO_ID 硬编码。
    """
    sp, iso_id = {}, {}
    best = {}                                    # M -> (abundance, I)
    formula_of = {}                              # M -> 官方分子式
    for (M, I), rec in hapi.ISO.items():
        f = str(rec[4]).upper()
        sp[f] = M
        formula_of[M] = f
        ab = float(rec[2])
        if M not in best or ab > best[M][0]:
            best[M] = (ab, I)
    for M, (_, I) in best.items():
        iso_id[formula_of[M]] = I
    return sp, iso_id


SPECIES, ISO_ID = _build_species()

# 常见别名 → 官方分子式（官方把 NO⁺ 记作 NOP，用户/旧代码惯写 NO+）
_ALIASES = {
    "NO+": "NOP", "NOP+": "NOP", "NOPLUS": "NOP",
}

# 名称归一化表：大写输入 → 官方分子式（唯一真源，_resolve 与 _validate_params 共用）
_NAME_MAP = {f: f for f in SPECIES}
for _alias, _official in _ALIASES.items():
    _NAME_MAP[_alias.upper()] = _official


def _canonical(name):
    """任意大小写/别名 → 官方分子式。未知物种抛 KeyError（消息不再罗列全表）。"""
    s = str(name).strip().upper()
    if s in _NAME_MAP:
        return _NAME_MAP[s]
    raise KeyError(
        f"[hitran] 未知物种 '{name}'（HITRAN 逐线库官方表无此分子，共 {len(SPECIES)} 种）。"
        f"若属截面子库（600+ 重分子）请用 hitran_cross_section 读本地文件。")


CITATION = (
    "HITRAN2024: Gordon et al., J. Quant. Spectrosc. Radiat. Transfer (2026), "
    "doi:10.1016/j.jqsrt.2026.109807. "
    "HAPI: Kochanov et al., JQSRT 177, 15-30 (2016). "
    "Partition sums: TIPS-2025."
)


def _resolve(name, iso):
    """返回 (M, I, table_name)。iso=None 时取官方主同位素（丰度最大者）。

    表名 = 官方分子式_M_I，与 hitran_mcp._ensure_table_for 生成的名字逐字符一致，
    保证 CSV 溯源水印指向真实缓存文件。
    """
    canonical = _canonical(name)
    M = SPECIES[canonical]
    I = int(iso) if iso is not None else ISO_ID.get(canonical, 1)
    return M, I, f"{canonical}_{M}_{I}"


# ---- 防呆第 1 层：输入参数校验（防止提问者/操作者把参数填错）----
_HITRAN_NU_MAX = 50000.0  # cm^-1，HITRAN 实际收录上限量级，超出强烈提示

def _validate_params(name, numin, numax, T, P, step, *, mole_frac=None):
    """输入护栏：任何明显填错的参数都提前报错或警告，避免"提问者犯蠢"式垃圾输入。

    硬错（raise ValueError）会阻断计算；软警告（print）仅提示可疑值，不阻断。
    """
    errs, warns = [], []

    # 名称校验与 _resolve 共用 _canonical（同一真源），大小写/别名口径完全一致
    if not isinstance(name, str):
        errs.append(f"分子名必须是字符串，收到 {name!r}")
    else:
        try:
            _canonical(name)
        except KeyError:
            errs.append(f"分子名 '{name}' 不在 HITRAN 逐线库官方表中（共 {len(SPECIES)} 种）")

    try:
        numin_f, numax_f = float(numin), float(numax)
    except (TypeError, ValueError):
        errs.append(f"波数窗口必须是数字，收到 numin={numin!r}, numax={numax!r}")
        numin_f = numax_f = None

    if numin_f is not None:
        if numin_f <= 0:
            warns.append(f"numin={numin_f} <= 0，波数应 > 0 cm-1")
        if numax_f is not None:
            if numax_f <= numin_f:
                errs.append(f"波数窗口颠倒/退化：numin({numin_f}) >= numax({numax_f})")
            if numax_f > _HITRAN_NU_MAX:
                warns.append(f"numax={numax_f} > HITRAN 常用上限 ~{int(_HITRAN_NU_MAX)} cm-1，可能无收录线")
            if (numax_f - numin_f) > 5000:
                warns.append(f"窗口宽 {numax_f-numin_f:.0f} cm-1 很宽，抓取/计算可能很慢，确认是否必要")

    try:
        T_f = float(T)
    except (TypeError, ValueError):
        errs.append(f"温度 T={T!r} 必须是数字(K)")
        T_f = None
    if T_f is not None:
        if T_f <= 0:
            errs.append(f"温度 T={T_f} K 必须 > 0（开尔文，不是摄氏度）")
        elif T_f < 100:
            warns.append(f"T={T_f} K 偏低（<100K），是否误把摄氏度当开尔文？273K=0°C")
        elif T_f > 1500:
            warns.append(f"T={T_f} K 偏高（>1500K），确认是否真实工况")

    try:
        P_f = float(P)
    except (TypeError, ValueError):
        errs.append(f"气压 P={P!r} 必须是数字(atm)")
        P_f = None
    if P_f is not None:
        if P_f <= 0:
            errs.append(f"气压 P={P_f} atm 必须 > 0")
        elif P_f > 100:
            warns.append(f"P={P_f} atm 偏高（>100atm），确认是否真实工况")

    try:
        step_f = float(step)
    except (TypeError, ValueError):
        errs.append(f"步长 step={step!r} 必须是正数字")
        step_f = None
    if step_f is not None:
        if step_f <= 0:
            errs.append(f"步长 step={step_f} 必须 > 0")
        elif numin_f is not None and numax_f is not None and step_f > (numax_f - numin_f):
            errs.append(f"步长 step={step_f} > 窗口宽 {numax_f-numin_f:.3f}，只能采样 1 个点，确认步长单位")

    if mole_frac is not None:
        try:
            x_f = float(mole_frac)
        except (TypeError, ValueError):
            errs.append(f"摩尔分数 mole_frac={mole_frac!r} 必须是 0~1 的数")
        else:
            if x_f < 0 or x_f > 1:
                errs.append(f"摩尔分数 mole_frac={x_f} 应在 [0,1]；>1 说明单位弄错(用了百分比或少除了 100)")
            elif x_f > 0.5:
                warns.append(f"mole_frac={x_f} 很大(>0.5)，确认是否真的是主成分而非 ppm 量级")

    for w in warns:
        print(f"[hitran][输入提示] {w}")
    if errs:
        raise ValueError("[hitran][防呆] 输入参数非法，已阻断计算：\n  - " + "\n  - ".join(errs))


def _table_coverage(table):
    """已加载表的实际覆盖区间 (nu_min, nu_max, n_lines)；表未加载或无线返回 None。"""
    try:
        if table not in tableList():
            return None
        nu = np.asarray(hapi.getColumn(table, "nu"), dtype=float)
        if nu.size == 0:
            return None
        return float(nu.min()), float(nu.max()), int(nu.size)
    except Exception:
        return None


def _wnum(v):
    """窗口数字 → 表名片段：2172.5 -> 2172p5（与 hitran_mcp 完全一致）。"""
    return f"{float(v):g}".replace(".", "p").replace("-", "m")


def fetch(name, numin, numax, iso=None, force=False):
    """抓取并注册某物种在 [numin, numax] cm-1 的线表，返回可用于计算的表名。

    窗口安全（与 hitran_mcp._ensure_table_for 同口径）：已缓存表若不覆盖请求窗口，
    改用带窗口后缀的表名重抓 —— 杜绝历史坑"同名表静默复用旧窗口 → 谱线缺失被误读为无干扰"。
    防呆：先校验输入窗口（_validate_params），抓取/加载后强制校验线数，空表直接报错（见 _guard_nonempty）。
    """
    _validate_params(name, numin, numax, 296.0, 1.01325, 0.01)  # 仅校验分子/窗口，T/P/step 用占位合法值
    _init_cache()
    numin, numax = float(numin), float(numax)
    M, I, base = _resolve(name, iso)

    cov = None if force else _table_coverage(base)
    if cov is not None and cov[0] <= numin and cov[1] >= numax:
        table = base
        print(f"[hitran] cached+loaded: {table}  ({numin}-{numax} cm-1)")
    else:
        table = f"{base}_{_wnum(numin)}_{_wnum(numax)}"
        if force or _table_coverage(table) is None:
            print(f"[hitran] fetch: {name} (M={M}, I={I})  {numin}-{numax} cm-1")
            hapi.fetch(table, M, I, numin, numax)
        else:
            print(f"[hitran] cached+loaded: {table}  ({numin}-{numax} cm-1)")
    _guard_nonempty(table, name, numin, numax)
    return table


def _line_count(table):
    """返回表内谱线条数：直接读磁盘 .data 物理行数（不依赖 HAPI 内存缓存，避免缓存未加载误判为空）。"""
    data_path = CACHE_ROOT / f"{table}.data"
    if not data_path.exists():
        return 0
    try:
        with open(data_path, "r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0


def _guard_nonempty(table, name, numin, numax):
    """防呆护栏：某分子/窗口返回 0 条线时一律硬报错。

    避免"无收录线"被静默当成一条平的假谱（误读为'无干扰'）。
    注：按整张表（即该表抓取窗口）计线数；若后续需按更窄子窗口判断，可在调用侧先行 re-fetch 对应窗口。
    """
    n = _line_count(table)
    if n == 0:
        raise RuntimeError(
            f"[hitran][防呆] 表 '{table}' 在 [{numin}, {numax}] cm-1 返回 0 条谱线。\n"
            f"  含义：该分子/同位素在此窗口无 HITRAN 收录线，无法合成吸收谱。\n"
            f"  严禁把空结果当作 '无干扰/平谱' 使用——请确认分子号、同位素，"
            f"或放宽波数窗口。如需声明'该窗口无收录线'，请在调用侧显式捕获此异常。")



# ---- 计算结果缓存（相同参数秒出，避免重复 HAPI 计算）----
_COMPUTE_CACHE = {}
_CACHE_MAX_ENTRIES = 200  # 最多缓存 200 组结果，防止内存膨胀
_CACHE_HITS = 0
_CACHE_MISSES = 0


def _cache_key(name, numin, numax, T, P, step, wingHW, iso, hitran_units, env):
    """生成可哈希的缓存键。env 字典转排序元组。"""
    env_items = tuple(sorted((k, str(v)) for k, v in (env or {}).items()))
    return (str(name).strip().upper(), float(numin), float(numax), float(T), float(P),
            float(step), float(wingHW), iso, bool(hitran_units), env_items)


def cache_stats():
    """返回缓存统计信息。"""
    return {"entries": len(_COMPUTE_CACHE), "max": _CACHE_MAX_ENTRIES,
            "hits": _CACHE_HITS, "misses": _CACHE_MISSES}


def cache_clear():
    """清空计算缓存。"""
    global _CACHE_HITS, _CACHE_MISSES
    _COMPUTE_CACHE.clear()
    _CACHE_HITS = 0
    _CACHE_MISSES = 0


def absorption(name, numin, numax, T=296.0, P=1.01325, step=0.01, wingHW=50.0,
               iso=None, hitran_units=False, poll=True, use_cache=True, **env):
    """返回 (nu, coef) —— 某物种在 [numin,numax] 的吸收系数谱。

    单位：hitran_units=False（默认）-> coef 单位 cm-1（吸收系数 α，已含数密度，
          1 atm 纯气体线中心峰值约 0.1~1 cm-1 量级）；
          hitran_units=True  -> coef 单位 cm2/molecule（分子吸收截面，峰值约 1e-20）。
    提示：step 太粗会让线中心欠采样（峰值被压低），弱线/精算用 step<=0.01。

    T,K; P,atm; step,cm-1; wingHW,cm-1(线翼半宽)。env 可覆盖 HAPI Environment
    其余字段(Diluent 等)。poll=True 时算完自动跑一次 check_spectrum 轮询自检。
    """
    global _CACHE_HITS, _CACHE_MISSES
    _validate_params(name, numin, numax, T, P, step)

    # 缓存查找
    if use_cache:
        key = _cache_key(name, numin, numax, T, P, step, wingHW, iso, hitran_units, env)
        if key in _COMPUTE_CACHE:
            _CACHE_HITS += 1
            nu, coef = _COMPUTE_CACHE[key]
            return nu.copy(), coef.copy()
        _CACHE_MISSES += 1

    table = fetch(name, numin, numax, iso=iso)
    M, I, _ = _resolve(name, iso)
    env0 = dict(Environment={"T": float(T), "p": float(P), "Diluent": {"air": 1.0}})
    env0.update(env)
    nu, coef = absorptionCoefficient_Voigt(
        Components=[(M, I, 1.0)],  # (M, I, relative_abundance)
        SourceTables=[table],
        WavenumberRange=(float(numin), float(numax)),
        WavenumberStep=float(step),
        WavenumberWingHW=float(wingHW),
        HITRAN_units=bool(hitran_units),
        **env0,
    )
    nu, coef = np.asarray(nu, dtype=float), np.asarray(coef, dtype=float)
    if poll:
        check_spectrum(nu, coef, name, numin=numin, numax=numax, T=T, P=P,
                       hitran_units=hitran_units)

    # 写入缓存（超限时清空一半旧缓存）
    if use_cache:
        if len(_COMPUTE_CACHE) >= _CACHE_MAX_ENTRIES:
            keys = list(_COMPUTE_CACHE.keys())
            for k in keys[:len(keys)//2]:
                del _COMPUTE_CACHE[k]
        _COMPUTE_CACHE[key] = (nu, coef)

    return nu, coef


# ----------------------------------------------------------------------------
# 防呆第 2 层：结果自检查 / 轮询（防止我自己/链路把"错"当"对"）
# ----------------------------------------------------------------------------
def check_spectrum(nu, coef, name=None, *, numin=None, numax=None,
                   T=None, P=None, hitran_units=False):
    """轮询式结果自检：返回 warnings 列表（空 = 通过）。

    设计目的（"你思考有问题时加轮询提示"）：每次算出谱之后，AI/用户都应调一次
    本函数做'二次确认'。它像轮询器一样扫描结果，任何物理上可疑的结果都打印
    [结果轮询] 提示并列入 warnings，而不是直接当成基线/噪声放过。
    典型可疑项：NaN/Inf、波数非单调、coef 全零（静默空谱）、峰值量级离谱、
    实际波数未覆盖请求窗口。
    """
    warns = []
    nu = np.asarray(nu, dtype=float)
    coef = np.asarray(coef, dtype=float)
    tag = f"[{name}] " if name else ""

    if nu.shape != coef.shape:
        w = f"形状不一致：nu{nu.shape} != coef{coef.shape}"
        print(f"[hitran][结果轮询] {tag}{w}")
        return warns + [w]
    if nu.size == 0:
        w = "谱为空（0 个点）—— 可能是窗口/网格填错"
        print(f"[hitran][结果轮询] {tag}{w}")
        return warns + [w]

    if not np.all(np.isfinite(nu)):
        warns.append("波数 nu 含 NaN/Inf —— 输入或计算异常")
    if not np.all(np.isfinite(coef)):
        warns.append("吸收系数 coef 含 NaN/Inf —— 可能浓度/压强非法或 HAPI 内部错误")

    dnu = np.diff(nu)
    if np.any(dnu < -1e-9):
        warns.append("波数非单调递增 —— 谱被异常排序，绘图/插值会错")
    elif np.any(dnu <= 0):
        warns.append("波数存在重复/零间隔点 —— 可能 step 与窗口不匹配")

    if np.all(np.abs(coef) < 1e-30):
        warns.append("coef 全部≈0 —— 可能是线表为空/未注册，或窗口内无该分子谱线（勿当'无干扰'）")
    else:
        peak = float(np.max(np.abs(coef)))
        if hitran_units:
            lo, hi = 1e-24, 1e-16        # cm^2/molecule 典型峰
        else:
            lo, hi = 1e-4, 1e3           # cm^-1 吸收系数（1atm 纯气典型 0.01~100）
        if peak < lo:
            warns.append(f"峰值 {peak:.2e} 偏小（<{lo:.0e}），可能步长太粗漏采样线中心，或压强/浓度过小")
        elif peak > hi:
            warns.append(f"峰值 {peak:.2e} 偏大（>{hi:.0e}），确认压强/浓度/单位是否填错（cm-1 vs cm2/mol）")

    if numin is not None and numax is not None:
        if nu.min() > float(numin) + 1e-6 or nu.max() < float(numax) - 1e-6:
            warns.append(f"实际波数范围 [{nu.min():.2f},{nu.max():.2f}] 未覆盖请求窗口 [{numin},{numax}]")

    for w in warns:
        print(f"[hitran][结果轮询] {tag}{w}")
    if not warns:
        print(f"[hitran][结果轮询] {tag}通过（{nu.size} 点，峰值 {np.max(np.abs(coef)):.2e}）")
    return warns


# ----------------------------------------------------------------------------
# 溯源与防呆输出：任何产物都要能追到官方库，不留孤儿数据
# ----------------------------------------------------------------------------
def provenance(name, numin, numax, T, P, iso=None, hitran_units=False):
    """返回溯源字符串（多行 '#' 注释），可写入 CSV 头或图注，防孤儿数据。"""
    M, I, table = _resolve(name, iso)
    unit = ("cm2/molecule (cross section σ)"
            if hitran_units else "cm-1 (absorption coeff α)")
    return "\n".join([
        "# ===== HITRAN spectrum provenance =====",
        "# source: HITRAN2024 (Gordon et al., JQSRT 2026, doi:10.1016/j.jqsrt.2026.109807)",
        f"# molecule={name} (M={M}, iso={I})  table={table}",
        f"# fetch window = {numin}–{numax} cm-1",
        f"# condition: T={T} K, P={P} atm, bath=air, profile=Voigt, wingHW default",
        f"# units: {unit}",
        "# engine: HAPI 1.3.0.0 (Kochanov et al., JQSRT 2016); partition sums TIPS-2025",
        "# ======================================",
    ])


def save_spectrum_csv(path, nu, coef, *, name, numin, numax, T, P,
                      iso=None, hitran_units=False, extra=None, extra_labels=None):
    """写谱数据 CSV，头部带 provenance 注释（防呆：任何产物都能追到官方库）。

    path: 输出文件；nu/coef: 波数/谱；extra: 额外列（元组/数组）；
    extra_labels: 对应列名。返回 path。
    """
    cols = [np.asarray(nu), np.asarray(coef)]
    labels = ["wavenumber_cm-1",
              "sigma_cm2_per_molecule" if hitran_units else "alpha_cm-1"]
    if extra:
        cols += [np.asarray(c) for c in extra]
        labels += list(extra_labels or [f"col{i}" for i in range(len(extra))])
    arr = np.column_stack(cols)
    # 落盘即轮询一次：防某次计算把错谱写成"可信产物"
    check_spectrum(nu, coef, name, numin=numin, numax=numax, T=T, P=P,
                   hitran_units=hitran_units)
    stamp = provenance(name, numin, numax, T, P, iso, hitran_units)
    with open(path, "w", encoding="utf-8") as f:
        f.write(stamp + "\n")
        f.write(",".join(labels) + "\n")
        np.savetxt(f, arr, delimiter=",", fmt="%.6e")
    print(f"[hitran] saved+watermarked: {path}")
    return path


if __name__ == "__main__":
    # 极简自测：验证整条链路（窄窗+细步长才能采样到线中心真实峰值）
    nu, coef = absorption("CO", 2109.0, 2111.0, T=296, P=1.01325, step=0.002)
    print(f"[hitran][self-test] CO absorption peak (cm-1): {coef.max():.3e}")

    # 防呆第 1 层（输入校验）自测：典型"提问者犯蠢"硬错须被拦截
    for bad in [
        dict(name="CO", numin=2111, numax=2109, T=296, P=1, step=0.01),   # 波数颠倒
        dict(name="CO", numin=2109, numax=2111, T=296, P=1, step=5),      # 步长>窗口
        dict(name="CO", numin=2109, numax=2111, T=296, P=1, step=0.01, mole_frac=500e-6/1e-6),  # 摩尔分数>1
    ]:
        try:
            _validate_params(**bad)
            raise SystemExit(f"[hitran][self-test] FAIL: 非法输入未触发护栏 -> {bad}")
        except ValueError as e:
            print(f"[hitran][self-test] input-guard OK -> {str(e).splitlines()[-1]}")
    # 软警告（不阻断）：疑似"摄氏度当开尔文"应给出提示但不报错
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        _validate_params("CO", 2109, 2111, 23, 1, 0.01)  # 23 K 像 -250°C? 实为疑似摄氏度
    assert "摄氏度" in buf.getvalue(), "[hitran][self-test] FAIL: 低温未给摄氏度提示"
    print("[hitran][self-test] input-guard OK -> 低温软警告已给出（不阻断）")

    # 防呆第 2 层（结果轮询）自测：全零谱须被轮询抓出
    _zero_warn = check_spectrum([2109.0, 2110.0, 2111.0], [0.0, 0.0, 0.0], "TEST")
    assert any("全部≈0" in w for w in _zero_warn), "[hitran][self-test] FAIL: 全零谱未触发轮询"
    print("[hitran][self-test] poll-guard OK -> 全零谱已标记")

    # 防呆护栏验证（直接测辅助：空表须硬报错，不覆盖良好缓存/不联网）
    try:
        _guard_nonempty("__no_such_table__", "X", 1.0, 2.0)
        raise SystemExit("[hitran][self-test] FAIL: 空表未触发护栏")
    except RuntimeError as e:
        print(f"[hitran][self-test] guard OK -> {str(e).splitlines()[0]}")
    # 溯源烙印验证
    print(provenance("CO", 2109.0, 2111.0, 296, 1.01325))
    print("[hitran][self-test] OK")
