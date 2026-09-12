#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HITRAN MCP Server —— 把 tools/hitran.py 的取数与绘图能力暴露成 AI 可直接调用的工具。

设计取向（功能齐全前提下的简约）：
  · 纯标准库实现的 stdio JSON-RPC（MCP 2024-11-05），零新增依赖；
    HAPI / matplotlib 惰性加载，空闲时不占用内存。
  · 所有 print 被捕获为 log 字段返回，绝不污染 stdout 协议流。
  · 9 个工具覆盖全链路：物种查询 / 线表抓取 / 强线列表 / 吸收·透过率谱（可混合气，多物种字符串）
    / 谱图绘制 / 配分函数 / 截面文件（HOTW）读入分析 / 截面子库在线探测 / 运行状态。
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
import threading
import traceback
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent   # 冻结(exe)模式：数据/缓存/产物与 exe 同级
else:
    ROOT = Path(__file__).resolve().parent.parent
if not getattr(sys, "frozen", False) and str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))          # 保证 tools 包可导入（自包含）；冻结模式跳过，避免同目录 .py 影子覆盖

OUT_DIR = ROOT / "tmp" / "mcp_out"         # 产物区（tmp/ 已 gitignore）
XSC_DIR = ROOT / "xsc_data"                # 用户下载的截面文件目录（gitignore，个人数据不入库）
PROTOCOL_VERSION = "2024-11-05"
VERSION = "1.5.2"  # 单一版本号源：桌面 APP_VERSION 引用此值，发布时只改这里
SERVER_INFO = {"name": "hitran", "version": VERSION}

_HT = None          # 惰性加载的 tools.hitran 模块（含 hapi，重）
_NP = None
_FETCH_LOCK = threading.RLock()   # hapi.fetch 串行化，防 .data 并发写（TOCTOU）


def _check_network(timeout=3):
    """检测是否能访问 HITRAN 服务器（hitran.org:443）。返回 True/False。

    断网时 3 秒内返回，避免用户在 hapi.fetch 超时前干等几十秒。
    """
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(("hitran.org", 443))
        s.close()
        return True
    except Exception:
        return False


@contextlib.contextmanager
def _quiet():
    """把 print 收进缓冲区：HAPI/matplotlib 的刷屏不能进 stdout 协议流。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf


def _api_key():
    """读取本机 HITRAN API key（文件已 gitignore，不入库；优先读环境变量）。

    该 key **已经生效**，有两处用途：
      ① 线表下载：经 tools/hitran.py 的 HAPI2 接入走 HITRAN 官方 v2 API（URL 携带 key）；
      ② 截面清单/下载：hitran_xsc_files / hitran_xsc_download 同样走官方 v2 API。
    仅当回退到 HAPI 1.x 旧接口（官方 API 不可用时）key 才不参与 —— 旧接口不校验 key。
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
        # 库层已改为惰性建目录：此处统一触发 db_begin，
        # 保证 _ensure_table_for 直调 hapi.fetch 时缓存落在 CACHE_ROOT 而非 HAPI 默认目录
        m._init_cache()
        key = _api_key()                     # 官方 v2 API（线表/截面下载）需要它
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

def _parse_specs_csv(specs_csv):
    """多物种字符串参数：'CH4:0.01,C2H6:1e-5' 或 'CO,N2O' → specs 列表。

    客户端 schema 扁平化后无法传 specs 数组，用字符串逗号分隔补上多物种能力；
    浓度缺省 = 纯气体（调用方仍需按 assumed_defaults 向用户确认）。
    """
    out = []
    for item in str(specs_csv or "").split(","):
        s = item.strip()
        if not s:
            continue
        if ":" in s:
            nm, _, x = s.partition(":")
            out.append({"name": nm.strip(), "mole_frac": float(x.strip())})
        else:
            out.append({"name": s})
    if not out:
        raise ValueError(
            "[hitran] specs_csv 解析为空。格式：'CH4:0.01,C2H6:1e-5'（冒号后为摩尔分数，"
            "缺省=1 纯气体；物种间用英文逗号分隔）。")
    return out


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
    # 先走别名表规范化（NO+ → NOP 等），未知物种保持原值继续查官方表
    try:
        s = _hitran()._canonical(s)
    except KeyError:
        pass
    if s in idx:
        return s, idx[s]["M"]
    for f, e in idx.items():                          # 容错：大小写/简写
        if f.replace("(", "").replace(")", "") == s.replace("(", "").replace(")", ""):
            return f, e["M"]
    raise ValueError(
        f"[hitran] 未知物种 '{name}'（HITRAN 逐线库官方表无此分子）。"
        f"可调 hitran_species 不传 name 获取官方全表；共 {len(idx)} 个分子。"
        f"若该分子属于截面子库（hitran.org/xsc，600+ 重分子，网页登录下载、无在线 API）"
        f"而非逐线库，请用 hitran_cross_section 读入本地下载的截面文件。")

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


def _load_local_table(table):
    """本地已落盘的线表直接载入内存，返回 coverage；文件缺失/损坏返回 None。

    HAPI 的 fetch 只检查内存 tableList()，**不查磁盘** —— 于是"表早就下载过"在
    新开的进程里仍会重新联网抓取（实测同一 1000 cm-1 窗口白等近 10 s）。
    这里补上"先读磁盘"这一步：有 .data/.header 就 storage2cache 载入，零联网。
    """
    import hapi
    root = _hitran().CACHE_ROOT
    data_path = root / f"{table}.data"
    header_path = root / f"{table}.header"
    if not data_path.exists() or not header_path.exists():
        return None
    # 完整性校验（第一道）：明显残缺的残骸直接丢弃（历史上出现过 161 字节的文件）。
    # 注意这里只能挡住"极小残骸"：若下载在**行边界**被截断，文件语法依旧完整，
    # HAPI 仍会将其当作合法表读入（实测 flag_EOF 仍为 True），读取侧无法识别；
    # 该类情况改由 _absorption 的「覆盖率合理性检查」给出告警。
    if data_path.stat().st_size < 1024:
        return None
    if table not in hapi.tableList():
        try:
            with _quiet():
                hapi.storage2cache(table)
        except Exception:
            return None
    return _coverage(table)


def _ensure_table_for(M, I, numin, numax, force=False):
    """保证拿到一张**真正覆盖** [numin,numax] 的线表。

    修掉的坑：hapi/ht.fetch 看到同名表已存在就跳过下载，于是请求新窗口时
    仍用旧线表 → 谱线静默缺失 → 被误读成"该气体无干扰"。
    策略：先查覆盖区间（内存 + 本地磁盘），未覆盖则用带窗口后缀的表名重抓（互不污染）。
    返回 (table, coverage, refetched)。
    """
    with _FETCH_LOCK:
        import hapi
        formula = _formula(M)
        base = f"{formula}_{M}_{I}"
        wtable = f"{base}_{_wnum(numin)}_{_wnum(numax)}"

        if not force:
            # 1) 精确窗口表（内存或本地磁盘）→ 直接复用（谱线位置≠窗口边界，勿再查覆盖）
            cov = _coverage(wtable)
            if cov is None:
                cov = _load_local_table(wtable)
            if cov is not None:
                return wtable, cov, False
            # 2) 基础表覆盖足够 → 复用
            cov = _coverage(base)
            if cov is None:
                cov = _load_local_table(base)
            if cov and cov[0] <= numin and cov[1] >= numax:
                return base, cov, False

        table = wtable
        # 联网检测：断网且数据未缓存时立即报错，不让用户干等超时
        if not _check_network():
            raise RuntimeError(
                f"[hitran][离线] 当前无法访问 hitran.org（网络检测超时），"
                f"且 {formula}(M={M},I={I}) 于 {numin}-{numax} cm-1 的线表未在本地缓存。"
                f"请检查网络连接后重试，或选择已缓存的分子/窗口。")
        # 下载线表：优先走 HAPI2 官方 API（带 api_key；其产物就是 HAPI 1.x 格式，
        # 计算层完全不感知）；HAPI2 不可用或失败时回退 HAPI 1.x 的旧下载接口。
        ht = _hitran()
        fetch_err = None
        h2_msg = "HAPI2 未启用"
        try:
            h2_ok, h2_msg = ht.hapi2_fetch_table(M, I, numin, numax, table)
        except Exception as e:                    # 接入层异常绝不阻断主流程
            h2_ok, h2_msg = False, f"接入异常 {type(e).__name__}: {e}"
        if h2_ok:
            try:
                with _quiet():
                    if table not in hapi.tableList():
                        hapi.storage2cache(table)   # HAPI2 产物已在 CACHE_ROOT
            except Exception as e:
                # 产物载入失败（格式异常等）→ 退回 HAPI 1.x 重下，不留半截状态
                h2_ok = False
                h2_msg = f"HAPI2 产物载入失败：{type(e).__name__}: {e}"
        if not h2_ok:
            with _quiet():                        # HAPI 下载日志不能进协议流
                try:
                    hapi.fetch(table, M, I, numin, numax)
                except Exception as e:
                    fetch_err = e
        if fetch_err is not None:
            hint = ""
            if "daily limit" in str(fetch_err).lower() or "exceeded" in str(fetch_err).lower():
                hint = ("（HITRAN 官方每日抓取配额已超限：今日请勿再 force 重抓，"
                        "尽量复用缓存；确认已配置 API key：tools/hitran_api_key.txt）")
            raise RuntimeError(
                f"[hitran][防呆] 抓取 {formula}(M={M},I={I}) 于 {numin}-{numax} cm-1 失败：{fetch_err}。"
                f"常见原因：该窗口无 HITRAN 收录线 / 分子号或同位素不存在 / 无网络 / 官方每日配额超限{hint}。"
                f"（HAPI2 通道：{h2_msg}）"
                f"严禁把失败当作'无干扰'。") from fetch_err
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



# ---- 计算结果缓存（相同参数秒出，避免重复 HAPI 计算）----
_ABSORPTION_CACHE = {}
_ABS_CACHE_MAX = 200
_ABS_CACHE_HITS = 0
_ABS_CACHE_MISSES = 0

# ---- 计算缓存持久化（重启后秒出，避免重复 HAPI 计算）----
_PERSIST_CACHE_DIR = ROOT / "Hitran_Data" / "compute_cache"
_PERSIST_INDEX_FILE = _PERSIST_CACHE_DIR / "index.json"


def _cache_hash(key):
    """缓存键 -> 文件名（SHA256 前 16 位，避免特殊字符）"""
    import hashlib
    return hashlib.sha256(repr(key).encode("utf-8")).hexdigest()[:16]


def _tupleize(obj):
    """递归把 list 转成 tuple（JSON 反序列化后 diluent 等嵌套结构会变成 list，需转回 tuple 才可哈希）。"""
    if isinstance(obj, list):
        return tuple(_tupleize(x) for x in obj)
    return obj


def _load_persistent_cache():
    """启动时从磁盘加载缓存到内存。损坏的条目自动跳过。"""
    global _ABS_CACHE_HITS, _ABS_CACHE_MISSES
    if not _PERSIST_INDEX_FILE.exists():
        return
    try:
        import json
        index = json.loads(_PERSIST_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return  # 索引损坏，当作无缓存
    loaded = 0
    np = _np()  # 延迟导入 numpy
    for key_json, fname in index.items():
        fpath = _PERSIST_CACHE_DIR / fname
        if not fpath.exists():
            continue
        try:
            data = np.load(fpath, allow_pickle=False)
            nu = np.asarray(data["nu"], dtype=float)
            coef = np.asarray(data["coef"], dtype=float)
            tinfo = json.loads(str(data["tinfo_json"]))
            key = _tupleize(json.loads(key_json))
            _ABSORPTION_CACHE[key] = (nu, coef, tinfo)
            loaded += 1
        except Exception:
            continue  # 单个文件损坏不影响其他
    if loaded:
        _ABS_CACHE_HITS += loaded  # 从磁盘加载也算命中（避免重复计算）


def _save_cache_entry(key, nu, coef, tinfo):
    """写入内存缓存后同步落盘。失败静默（不影响计算结果）。"""
    try:
        import json
        np = _np()  # 延迟导入 numpy
        _PERSIST_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        fname = _cache_hash(key) + ".npz"
        fpath = _PERSIST_CACHE_DIR / fname
        np.savez_compressed(fpath, nu=nu, coef=coef,
                            tinfo_json=np.array(json.dumps(tinfo, ensure_ascii=False)))
        # 更新索引
        index = {}
        if _PERSIST_INDEX_FILE.exists():
            try:
                index = json.loads(_PERSIST_INDEX_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        index[json.dumps(list(key), ensure_ascii=False)] = fname
        _PERSIST_INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # 落盘失败不影响内存缓存和计算结果


def _clear_persistent_cache():
    """清理磁盘缓存。"""
    try:
        import shutil
        if _PERSIST_CACHE_DIR.exists():
            shutil.rmtree(_PERSIST_CACHE_DIR)
    except Exception:
        pass


# 模块加载时自动从磁盘恢复缓存
try:
    _load_persistent_cache()
except Exception:
    pass


# 缓存版本号：算法或结果格式发生变更时必须递增，否则旧缓存会被错误复用
# （例如网格点数规则修好后，命中旧缓存仍会返回修复前的点数）。
_CACHE_SCHEMA = 2


def _abs_cache_key(name, iso, numin, numax, T, P, step, wingHW, hitran_units,
                    profile, diluent, intensity_cutoff, min_abundance):
    """生成可哈希的缓存键。

    `force` 不影响结果、不纳入键；`_CACHE_SCHEMA` 也不影响物理结果，它用于在
    算法变更后让旧缓存自动失效。
    """
    dil_items = tuple(sorted((k, float(v)) for k, v in (diluent or {}).items())) if isinstance(diluent, dict) else str(diluent)
    return (_CACHE_SCHEMA, str(name).strip().upper(), str(iso), float(numin), float(numax), float(T), float(P),
            float(step), float(wingHW), bool(hitran_units), str(profile).lower(), dil_items,
            float(intensity_cutoff) if intensity_cutoff is not None else None,
            float(min_abundance))


def abs_cache_stats():
    """返回缓存统计。"""
    return {"entries": len(_ABSORPTION_CACHE), "max": _ABS_CACHE_MAX,
            "hits": _ABS_CACHE_HITS, "misses": _ABS_CACHE_MISSES}


def abs_cache_clear():
    """清空缓存（内存 + 磁盘）。"""
    global _ABS_CACHE_HITS, _ABS_CACHE_MISSES
    _ABSORPTION_CACHE.clear()
    _ABS_CACHE_HITS = 0
    _ABS_CACHE_MISSES = 0
    _clear_persistent_cache()


_CHUNK_POINTS = 4000     # 分块粒度：约 4 千点/块，兼顾进度平滑与单次调用开销


def _n_grid(numin, numax, step):
    """网格点数：**必须与 HAPI 的 hapi.arange_() 完全一致**。

    HAPI 的规则是 floor((upper-lower)/step) + 1，另有一个边界容差修正；
    旧实现用 round()，当 (numax-numin)/step 的小数部分 >= 0.5 时会多算 1 点，
    造成"分块计算(GUI)"与"整窗计算(MCP)"点数不一致，且分块结果末点会超出
    用户设定的波数上限。这里直接复用 HAPI 的实现，避免规则再次漂移。
    """
    import hapi
    return len(hapi.arange_(float(numin), float(numax), float(step)))


def _absorption(name, iso, numin, numax, T, P, step, wingHW, hitran_units,
                force=False, min_abundance=1e-4, profile="voigt", diluent=None,
                intensity_cutoff=None, progress=None):
    """窗口安全的吸收谱计算（绕开 ht.absorption 的表名复用问题）。

    同位素口径（需在结论中显式声明主同位素近似或全同位素近似）：
      iso=None  → 主同位素近似：Components=[(M, I, 1.0)]，即纯主同位素的 α_pure
      iso='all' → 全同位素近似：各同位素按官方自然丰度加权求和
    单同位素时权重必须是 1.0（纯气体），不可误传自然丰度，否则 α 会凭空少 1%~2%。
    """
    global _ABS_CACHE_HITS, _ABS_CACHE_MISSES
    ht, np = _hitran(), _np()
    import hapi
    from hapi import absorptionCoefficient_Voigt

    # 缓存查找（force 不影响结果，不纳入键）
    key = _abs_cache_key(name, iso, numin, numax, T, P, step, wingHW, hitran_units,
                          profile, diluent, intensity_cutoff, min_abundance)
    if key in _ABSORPTION_CACHE:
        _ABS_CACHE_HITS += 1
        nu, coef, tinfo = _ABSORPTION_CACHE[key]
        return nu.copy(), coef.copy(), dict(tinfo)
    _ABS_CACHE_MISSES += 1

    formula, M = _resolve_M(name)
    isos = _isotopologues(M, iso, min_abundance)
    full = len(isos) > 1

    # 进度规划：前半段按同位素上报"抓取"，后半段按波数分块上报"计算"
    n_pts = _n_grid(numin, numax, step)
    n_seg = max(0, n_pts - 1)
    n_chunks = max(1, (n_seg + _CHUNK_POINTS - 1) // _CHUNK_POINTS) if progress else 1
    total_steps = (len(isos) + n_chunks) if progress else 0
    steps_done = 0

    entries, skipped = [], []
    warn_msgs = []                         # 非致命问题（分块对齐 / 覆盖率可疑）如实上报
    for I, ab in isos:
        try:
            table, cov, refetched = _ensure_table_for(M, I, numin, numax, force)
        except Exception as e:                 # 稀有同位素抓不到 → 跳过并报告，不拖垮整体
            skipped.append({"I": I, "abundance": ab, "reason": str(e)[:160]})
            steps_done += 1
            if progress:
                progress(steps_done, total_steps, "抓取线表")
            continue
        nu_all = np.asarray(hapi.getColumn(table, "nu"), dtype=float)
        entries.append({"table": table, "I": I, "ab": ab, "cov": cov,
                        "refetched": refetched,
                        "n_in": int(((nu_all >= numin) & (nu_all <= numax)).sum())})
        steps_done += 1
        if progress:
            progress(steps_done, total_steps, "抓取线表")
    if not entries:
        raise RuntimeError(f"[hitran][防呆] {formula} 的所有同位素在 {numin}-{numax} cm-1 均抓取失败：{skipped}")

    # 覆盖率合理性检查：线表覆盖上界若明显低于请求上界，可能是"未下载完整"的表
    # （行边界截断在读取侧识别不了，只能靠这一层兜底提示）。阈值取窗口宽度的 10%，
    # 只告警不阻断，避免把"窗口上半段确实无谱线"误判为错误。
    try:
        _span = float(numax) - float(numin)
        _hi = float(numax)
        if _span > 0:
            for _e in entries:
                _cov = _e.get("cov")
                if _cov and float(_cov[1]) < _hi - 0.1 * _span:
                    warn_msgs.append(
                        f"[线表覆盖] '{_e['table']}' 覆盖上界 {float(_cov[1]):.3f} cm-1 明显低于请求上界 "
                        f"{_hi:.3f}；该表可能未下载完整，建议『工具 → 清理线表缓存』后重算。")
    except Exception:
        pass

    pkey = str(profile or "voigt").strip().lower()
    if pkey not in PROFILES:
        raise ValueError(f"[hitran] 未知线型 '{profile}'，官方可选: {sorted(PROFILES)}")
    bath = _diluent_dict(diluent)
    _hapi_kwargs = dict(
        Components=[(M, e["I"], e["ab"] if full else 1.0) for e in entries],
        SourceTables=[e["table"] for e in entries],
        WavenumberRange=(float(numin), float(numax)), WavenumberStep=float(step),
        WavenumberWingHW=float(wingHW), HITRAN_units=bool(hitran_units),
        Environment={"T": float(T), "p": float(P), "Diluent": bath})
    if intensity_cutoff is not None and float(intensity_cutoff) > 0:
        _hapi_kwargs["IntensityThreshold"] = float(intensity_cutoff)

    func = getattr(hapi, PROFILES[pkey])
    if not progress or n_chunks <= 1:
        nu, coef = func(**_hapi_kwargs)
    else:
        # 分块计算：把窗口按整点均分，逐块调用（物理上与整窗一次调用等价：
        # 同一批 SourceTables/Components，线翼仍由 WavenumberWingHW 控制），
        # 每块完成即回调一次，进度条才有真实推进。
        base_pts, extra = divmod(n_seg, n_chunks)
        nus, coefs, cursor = [], [], 0
        for k in range(n_chunks):
            pts = base_pts + (1 if k < extra else 0)
            i0, i1 = cursor, cursor + pts
            cursor = i1
            kw = dict(_hapi_kwargs)
            kw["WavenumberRange"] = (float(numin) + i0 * float(step),
                                     float(numin) + i1 * float(step))
            nu_k, coef_k = func(**kw)
            nu_k = np.asarray(nu_k, dtype=float)
            coef_k = np.asarray(coef_k, dtype=float)
            if k:                                  # 丢掉与前一块重复的边界点
                nu_k, coef_k = nu_k[1:], coef_k[1:]
            nus.append(nu_k)
            coefs.append(coef_k)
            steps_done += 1
            progress(steps_done, total_steps, "计算谱线")
        nu = np.concatenate(nus)
        coef = np.concatenate(coefs)
        # 分块拼接的点数应与整窗 HAPI 取点一致；修正 _n_grid 后正常不会走到这里。
        # 若仍不一致，说明分块边界/浮点处理有偏差 —— 如实告警，绝不静默改数据
        # （旧的静默截断/重复点补齐会污染结果且无人知晓）。
        expected = n_seg + 1
        if len(nu) != expected:
            warn_msgs.append(
                f"[分块对齐] 拼接点数 {len(nu)} 与预期 {expected} 不一致"
                f"（窗口 {float(numin):g}-{float(numax):g}, step={float(step):g}）；"
                f"已按预期点数对齐，末点附近可能存在 1 点偏差。")
            if len(nu) > expected:
                nu, coef = nu[:expected], coef[:expected]
            else:
                pad = expected - len(nu)
                nu = np.concatenate([nu, np.full(pad, nu[-1])])
                coef = np.concatenate([coef, np.full(pad, coef[-1])])
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
    if warn_msgs:
        tinfo["warnings"] = warn_msgs
    nu, coef = np.asarray(nu, dtype=float), np.asarray(coef, dtype=float)

    # 写入缓存（超限时清空一半旧缓存）
    if len(_ABSORPTION_CACHE) >= _ABS_CACHE_MAX:
        keys = list(_ABSORPTION_CACHE.keys())
        for k in keys[:len(keys)//2]:
            del _ABSORPTION_CACHE[k]
    _ABSORPTION_CACHE[key] = (nu, coef, tinfo)
    _save_cache_entry(key, nu, coef, tinfo)   # 持久化到磁盘，重启后秒出

    return nu, coef, tinfo


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
             profile="voigt", diluent=None, min_abundance=1e-4, intensity_cutoff=None,
             progress=None):
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
        # 库层 SPECIES 已与官方 ISO 表同源、名称归一化大小写不敏感，无需再用占位名绕过
        with _quiet() as gbuf:
            ht._validate_params(name, numin, numax, T, P, step,
                                mole_frac=None if abs(x - 1.0) < 1e-12 else x)
        for ln in gbuf.getvalue().splitlines():      # 软警告也要进 warnings，AI 才看得见
            if "[输入提示]" in ln:
                warnings.append(ln.strip())
        nu_i, coef, tinfo = _absorption(name, iso, numin, numax, T, P, step,
                                        wingHW, hitran_units, sp.get("force", False),
                                        min_abundance, profile, diluent, intensity_cutoff,
                                        progress=progress)
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
                f"线表 {tinfo['table']} 覆盖 {tinfo['coverage_cm-1']}，"
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


def t_spectrum(specs=None, name=None, mole_frac=None, iso=None, specs_csv=None,
               numin=None, numax=None,
               T=None, P=None, step=None, wingHW=None, mode=None,
               path_length_cm=None, hitran_units=False, save=True, force=False,
               strict=False, min_abundance=1e-4, profile="voigt", diluent=None):
    """吸收/透过率谱（支持混合气），返回 CSV 路径 + 峰值/积分 + 线表信息 + 告警。

    未给出的参数会用默认值，但**如实列在 assumed_defaults 里**，调用方应据此向用户确认
    （尤其是 T / P / 各组分摩尔分数）。strict=True 时 T、P 未给直接报错，强制先确认。
    """
    if specs_csv is not None:
        if specs or name:
            raise ValueError("[hitran] specs_csv 与 specs/name 互斥，请二选一。")
        sp_list = _parse_specs_csv(specs_csv)
    else:
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


def t_plot(specs=None, name=None, mole_frac=None, iso=None, specs_csv=None,
           numin=None, numax=None,
           T=None, P=None, step=None, wingHW=None, mode=None,
           path_length_cm=None, hitran_units=False, title=None, ylog=False,
           dpi=160, save_csv=True, force=False, strict=False,
           profile="voigt", diluent=None, min_abundance=1e-4):
    """绘制谱图 PNG（多物种叠加 + 总谱），返回 PNG/CSV 路径。参数口径同 hitran_spectrum。"""
    if specs_csv is not None:
        if specs or name:
            raise ValueError("[hitran] specs_csv 与 specs/name 互斥，请二选一。")
        sp_list = _parse_specs_csv(specs_csv)
    else:
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
        ylab = ("Cross section σ (cm$^2$/molecule)" if hitran_units
                else "Absorption coefficient α (cm$^{-1}$)")
    if ylog:
        ax.set_yscale("log")

    ax.set_xlabel("Wavenumber (cm$^{-1}$)")
    ax.set_ylabel(ylab)
    ax.set_title(title or f"{'+'.join(per)}  {res['numin']}–{res['numax']} cm$^{-1}$"
                          f"  T={res['T']:g} K  P={res['P']:g} atm")
    ax.grid(alpha=0.25, lw=0.6)
    ax.legend(fontsize=8, framealpha=0.9)
    if not ylog:                      # ticklabel_format 只支持线性轴（对数轴会抛异常）
        ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
    _prof = res.get("profile", "voigt")
    _dil = res.get("diluent") or {"air": 1.0}
    _dil_str = "+".join(f"{k}:{v:g}" for k, v in _dil.items())
    fig.text(0.01, 0.01, f"HITRAN2024 via HAPI 1.3.0.0 · TIPS-2025 · {_prof}/{_dil_str}",
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


def _looks_like_native_xsc(path):
    """首行是否为半 HITRAN 定宽头（即 hitran.org/data/xsec 那种原生 .xsc）。

    头格式：[0:20] 分子式 | [20:30] numin | [30:40] numax | [40:47] npnts
            | [47:54] T(K) | [54:60] p(Torr) | [60:] 参考/展宽气。
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            h = f.readline()
        if len(h) < 60:
            return False
        float(h[20:30]); float(h[30:40]); int(h[40:47])
        float(h[47:54]); float(h[54:60])
        return True
    except Exception:
        return False


def _read_xsc_native(path):
    """读 HITRAN 原生 .xsc（半 HITRAN 格式）：1 行定宽头 + 每行 10 个 σ 值。

    与两列 HOTW 文本的区别：文件只存 σ（cm²/molecule），波数网格由头部
    numin/numax/npnts 重建（官方文件按等间隔生成）。hitran_xsc_download
    下到的正是这种文件，故读入侧必须支持。
    """
    path = Path(str(path))
    with open(path, encoding="utf-8", errors="replace") as f:
        h = f.readline()
        try:
            formula = h[0:20].strip()
            numin, numax = float(h[20:30]), float(h[30:40])
            npnts = int(h[40:47])
            temp, pres = float(h[47:54]), float(h[54:60])
        except Exception as e:
            raise ValueError(f"[hitran_cross_section] '{path.name}' 头部不是合法的 HITRAN 原生 "
                             f".xsc 格式：{e}") from e
        vals = []
        for ln in f:
            for s in ln.split():
                try:
                    vals.append(float(s))
                except ValueError:
                    pass
            if len(vals) >= npnts:
                break
    if len(vals) < npnts:
        raise ValueError(f"[hitran_cross_section] '{path.name}' 头部声明 {npnts} 点、"
                         f"实读 {len(vals)} 点（文件可能被截断或格式不符）。")
    npx = _np()
    coef = npx.asarray(vals[:npnts], dtype=float)
    nu = npx.linspace(numin, numax, npnts)
    # [60:] 为附加区：新式文件含 sigma_max/分辨率/分子名([75:90])/展宽气([90:100])，
    # 老式文件此处是参考文献 —— 故不硬标为"参考文献"，能认出的字段分开列出。
    extra = h[60:].strip()
    name = h[75:90].strip()
    bits = [f"# HITRAN native .xsc | {formula}"]
    if name and name != formula:
        bits.append(f"name={name}")
    bits += [f"nu {numin:g}-{numax:g} cm-1", f"T={temp:g} K",
             f"p={pres:g} Torr", f"npts={npnts}"]
    if extra:
        bits.append(f"extra='{extra}'")
    header = [" | ".join(bits)]
    return nu, coef, header, 0


def _read_hotw_file(path):
    """读 HITRAN-on-the-Web 截面文件（两列：nu, coef[cm2/molecule]）。

    兼容：空行/注释行（# 开头）自动跳过；注释行前若干行收集为文件头（溯源用）。
    分隔符兼容空格/制表符/英文逗号（与 GUI 侧 _read_hotw 同口径）——HOTW 官方为空格，
    但用户常另存为 .csv，若只认空格会把 .csv 判成"无不数值数据"。
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
            parts = s.replace(",", " ").replace("\t", " ").split()
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
        if _looks_like_native_xsc(path):        # hitran_xsc_download 下到的原生 .xsc
            return _read_xsc_native(path)
        raise ValueError(
            f"[hitran_cross_section] '{path.name}' 中未解析到两列数值数据（nu, coef）。"
            f"请确认是 hitran.org/xsc 下载的 HOTW 截面文件（形如 '2950.0000 1.23e-21'），"
            f"或本工具 hitran_xsc_download 下载的 HITRAN 原生 .xsc。")
    return _np().asarray(nu, dtype=float), _np().asarray(coef, dtype=float), header, skipped


def _list_xsc_files():
    """列出 xsc_data/ 下已下载的截面文件（个人数据，不入库）。"""
    if not XSC_DIR.exists():
        return []
    out = []
    for p in sorted(XSC_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in (".txt", ".dat", ".csv"):
            out.append({"file": str(p), "name": p.name,
                        "size_bytes": p.stat().st_size,
                        "mtime": p.stat().st_mtime})
    return out


def t_cross_section(file_path=None, source_label=None, numin=None, numax=None,
                    title=None, ylog=False, dpi=160, save_csv=True):
    """读入本地截面文件（HITRAN 原生 .xsc 或两列 ν–σ 文本）→ 截窗 → 绘图 PNG + 溯源 CSV。

    桥接 HITRAN 双库架构的截面通道：逐线库（61 分子）走 HAPI 在线 API；截面库
    （600+ 重分子）没有在线计算接口，只能读文件。本工具把截面文件接入同一套
    产物链路（CSV/PNG 带溯源水印）。

    两类文件自动识别：
      ① HITRAN 原生 .xsc（1 行定宽头 + 每行 10 个 σ 值）—— hitran_xsc_download 下到的就是它；
      ② 两列 ν–σ 文本（HOTW 导出 / CSV）。
    文件可放在 xsc_data/（gitignore 区，hitran_xsc_download 的默认落点）；file_path 缺省时
    列出该目录可用文件供选择。数据单位固定为 σ (cm²/molecule)。
    """
    if not file_path:
        avail = _list_xsc_files()
        if not avail:
            return {"available_files": [], "hint": (
                "xsc_data/ 下暂无截面文件。请到 hitran.org/xsc 登录后搜索分子、勾选目标 T/P 文件"
                "下载 .txt 放入仓库 xsc_data/ 目录（可先用 hitran_xsc_search 在线查该分子的截面文件清单），"
                "然后传入 file_path 调用本工具。")}
        return {"available_files": avail, "hint": (
            "请从 above 列表选择一个文件，用 file_path 参数传入（可附 source_label 溯源标签）")}
    # 防路径穿越：只允许从 xsc_data/ 目录读取
    xsc_dir = XSC_DATA_DIR.resolve()
    user_path = Path(str(file_path)).resolve()
    if not str(user_path).startswith(str(xsc_dir)):
        avail = _list_xsc_files()
        hint = "；xsc_data/ 下现有: " + ", ".join(a["name"] for a in avail[:10]) if avail else ""
        raise ValueError(f"[hitran_cross_section] 非法路径: 只允许从 xsc_data/ 目录读取截面文件{hint}")
    if not user_path.exists():
        avail = _list_xsc_files()
        hint = ""
        if avail:
            hint = "；xsc_data/ 下现有: " + ", ".join(a["name"] for a in avail[:10])
        raise ValueError(f"[hitran_cross_section] 截面文件不存在: {file_path}{hint}")
    nu, coef, header, skipped = _read_hotw_file(str(user_path))
    label = str(source_label or user_path.name)
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
    ax.set_xlabel("Wavenumber (cm$^{-1}$)")
    ax.set_ylabel("Cross section σ (cm$^2$/molecule)")
    ax.set_title(title or f"{label}  {win[0]:g}–{win[1]:g} cm$^{-1}$")
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
            _np().savetxt(f, _np().column_stack([nu_w, coef_w]), delimiter=",", fmt="%.6e")

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


def _http_get_text(url, timeout=60):
    """通用 HTTP GET（带浏览器 UA；hitran.org 静态/接口面不要求登录）。"""
    import urllib.request, ssl, urllib.parse
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read().decode("utf-8", "replace")


def t_xsc_search(name=None):
    """在线探测 HITRAN 截面子库某分子的截面文件清单（免登录，只读）。

    走 hitran.org/xsc 的公开查询接口（get-molecule → get-meta），返回分子号、
    常用名、分子式与全部截面文件元数据（ν 范围 / 温度 / 压力 / 分辨率 / 点数 / 展宽气）。
    用于下载前判断该选哪个 T–P 文件；实际下载仍需登录 Portal，文件放入 xsc_data/ 后
    由 hitran_cross_section 读入。若返回 0 文件，说明该分子不在截面子库（也未收录逐线库）。
    """
    import urllib.parse
    if not name:
        raise ValueError("[hitran_xsc_search] 必须提供 name（hitran.org/xsc 上显示的分子名，"
                         "如 Propane / Ethane / Acetone）。")
    q = urllib.parse.quote(str(name).strip())
    try:
        mid = _http_get_text(f"https://hitran.org/xsc/get-molecule?molecule_name={q}").strip()
    except Exception as e:
        raise RuntimeError(f"[hitran_xsc_search] 无法访问 hitran.org（{type(e).__name__}: {e}）。"
                           f"本工具需能直连 hitran.org 的查询接口（免登录）。") from e
    if not mid.isdigit():
        return {"query": str(name).strip(), "found": False, "hint": (
            f"截面子库未找到 '{name}'。可能：① 名称不是 Portal 页面显示的英文名；"
            f"② 该分子未收录于截面子库（也即 HITRAN 全库无此分子数据）。")}
    meta = json.loads(_http_get_text(
        f"https://hitran.org/xsc/get-meta?molecule_id={mid}"))
    html = meta.get("html", "")
    nm = re.search(r"<h3>([^:<]+)", html)
    rows = re.findall(r'class="xsec-(\d+)"[^>]*>(.*?)</tr>', html, re.S)
    files = []
    for xid, body in rows:
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<td>(.*?)</td>", body, re.S)]
        # 首列为 checkbox 占位（'&nbsp;'），滤掉后 6 列即：range/T/p/resolution/npts/broadener
        vals = [c for c in cells if c and c != "&nbsp;"]
        vals = (vals + [""] * 6)[:6]
        files.append({"id": int(xid), "nu_range_cm-1": vals[0], "T_K": vals[1],
                      "p_Torr": vals[2], "resolution": vals[3],
                      "n_points": vals[4], "broadener": vals[5]})
    return {"query": str(name).strip(), "found": True, "molecule_id": int(mid),
            "common_name": nm.group(1).strip() if nm else str(name).strip(),
            "n_files": len(files),
            "files": files,
            "hint": ("可先用 hitran_xsc_files 列出**可直接下载**的文件名（需 API key），"
                     "再用 hitran_xsc_download 一键下载到 xsc_data/，"
                     "最后 hitran_cross_section(file_path=...) 读入分析。")}


# ─────────────── 截面文件：官方 API 清单与一键下载（免 Portal 登录） ───────────────
# 截面子库（600+ 重分子）没有 HAPI 在线计算接口，但 hitran.org 官方 API
# /api/v2/<key>/cross-sections 能列出**可直接下载的文件名**，数据文件位于公开路径
# /data/xsec/ 下（实测 HTTP 200，无需登录）。故"搜索 → 勾选 → 下载"无需 HAPI2。

XSC_DL_LIMIT_MB = 300                # 单次批量下载总体积上限（防手抖把整个分子全下）
_XSC_BYTES_PER_POINT = 10.1          # HOTW 两列文本实测 ~10.1 B/点（43145 点 → 435915 B）


# 中文名 → HITRAN 英文关键词。截面库只认英文名，中文用户无从下手，故内置常用气体对照；
# 命中后按"关键词"做模糊匹配（不要求与 HITRAN 命名逐字相同），容错交给匹配打分。
_MOL_ZH = {
    "水": "Water", "水蒸气": "Water", "水汽": "Water",
    "二氧化碳": "Carbon Dioxide", "一氧化碳": "Carbon Monoxide",
    "一氧化氮": "Nitric Oxide", "二氧化氮": "Nitrogen Dioxide",
    "一氧化二氮": "Nitrous Oxide", "笑气": "Nitrous Oxide",
    "氨": "Ammonia", "氨气": "Ammonia", "硫化氢": "Hydrogen Sulfide",
    "二氧化硫": "Sulfur Dioxide", "三氧化硫": "Sulfur Trioxide", "臭氧": "Ozone",
    "氧气": "Oxygen", "氮气": "Nitrogen", "氢气": "Hydrogen",
    "氯化氢": "Hydrogen Chloride", "氟化氢": "Hydrogen Fluoride",
    "溴化氢": "Hydrogen Bromide", "碘化氢": "Hydrogen Iodide",
    "氯气": "Chlorine", "氟气": "Fluorine", "磷化氢": "Phosphine",
    "六氟化硫": "Sulfur Hexafluoride", "羰基硫": "Carbonyl Sulfide",
    "氧硫化碳": "Carbonyl Sulfide", "二硫化碳": "Carbon Disulfide",
    "氰化氢": "Hydrogen Cyanide", "氢氰酸": "Hydrogen Cyanide",
    "甲烷": "Methane", "乙烷": "Ethane", "丙烷": "Propane",
    "正丁烷": "n-Butane", "丁烷": "Butane", "异丁烷": "Isobutane",
    "正戊烷": "n-Pentane", "戊烷": "Pentane", "异戊烷": "Isopentane",
    "己烷": "n-Hexane", "庚烷": "n-Heptane", "辛烷": "n-Octane",
    "环丙烷": "Cyclopropane", "环己烷": "Cyclohexane",
    "乙烯": "Ethylene", "丙烯": "Propylene", "丁烯": "Butene",
    "异丁烯": "Isobutene", "乙炔": "Acetylene", "丙炔": "Propyne",
    "丁二烯": "Butadiene", "异戊二烯": "Isoprene",
    "苯": "Benzene", "甲苯": "Toluene", "二甲苯": "Xylene",
    "苯乙烯": "Styrene", "苯酚": "Phenol", "乙苯": "Ethylbenzene",
    "甲醛": "Formaldehyde", "乙醛": "Acetaldehyde", "丙烯醛": "Acrolein",
    "甲醇": "Methanol", "乙醇": "Ethanol", "丙醇": "Propanol",
    "异丙醇": "Isopropanol", "丁醇": "Butanol",
    "丙酮": "Acetone", "丁酮": "Methyl Ethyl Ketone",
    "甲酸": "Formic Acid", "乙酸": "Acetic Acid", "醋酸": "Acetic Acid",
    "丙烯酸": "Acrylic Acid", "乙酸乙酯": "Ethyl Acetate",
    "环氧乙烷": "Ethylene Oxide", "环氧丙烷": "Propylene Oxide",
    "甲醚": "Dimethyl Ether", "乙醚": "Diethyl Ether",
    "四氢呋喃": "Tetrahydrofuran", "碳酸二甲酯": "Dimethyl Carbonate",
    "甲胺": "Methylamine", "二甲胺": "Dimethylamine", "三甲胺": "Trimethylamine",
    "乙腈": "Acetonitrile", "丙烯腈": "Acrylonitrile",
    "硝基甲烷": "Nitromethane", "苯胺": "Aniline", "吡啶": "Pyridine",
    "氯甲烷": "Methyl Chloride", "一氯甲烷": "Methyl Chloride",
    "二氯甲烷": "Dichloromethane", "三氯甲烷": "Chloroform", "氯仿": "Chloroform",
    "四氯化碳": "Carbon Tetrachloride", "氯乙烷": "Ethyl Chloride",
    "氯乙烯": "Vinyl Chloride", "三氯乙烯": "Trichloroethylene",
    "四氯乙烯": "Tetrachloroethylene", "溴甲烷": "Methyl Bromide",
    "氟利昂11": "CFC-11", "氟利昂12": "CFC-12",
    "氟利昂113": "CFC-113", "氟利昂114": "CFC-114",
    "四氟化碳": "Carbon Tetrafluoride", "六氟乙烷": "Hexafluoroethane",
    "甲硫醇": "Methyl Mercaptan", "甲硫醚": "Dimethyl Sulfide",
    "乙硫醇": "Ethyl Mercaptan", "四甲基硅烷": "Tetramethylsilane",
}
# Unicode 下标 → 普通数字（用户可能输入 CH₄ 这种写法）
_SUB_DIGITS = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_MOL_CACHE = ROOT / "Hitran_Data" / "hitran_molecules.json"


def _molecules_index(force=False):
    """HITRAN 全部分子索引（约 670 条：id / 常用名 / 化学式 / 全部别名），本地缓存 30 天。

    数据源是官方 API /molecules —— 它的 id 与截面库 molecule_id 同一体系（已实测
    Propane 两边都是 137），因此可以直接用它把"用户输入的名字"翻译成 molecule_id。
    """
    import time as _t
    if not force and _MOL_CACHE.exists():
        try:
            if _t.time() - _MOL_CACHE.stat().st_mtime < 30 * 86400:
                return json.loads(_MOL_CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    key = _api_key()
    if not key:
        return []
    try:
        raw = _xsc_retry(lambda: _http_get_text(
            f"https://hitran.org/api/v2/{key}/molecules", timeout=90), tries=3, delay=2.0)
        mols = (json.loads(raw).get("content") or {}).get("data") or []
    except Exception:
        try:                                    # 拉取失败就用旧缓存兜底
            return json.loads(_MOL_CACHE.read_text(encoding="utf-8"))
        except Exception:
            return []
    if mols:
        try:
            _MOL_CACHE.parent.mkdir(parents=True, exist_ok=True)
            _MOL_CACHE.write_text(json.dumps(mols, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return mols


def _molid_brief(m):
    """分子记录 → 面向用户的精简结构。"""
    return {"id": m.get("id"),
            "name": m.get("common_name"),
            "formula": m.get("ordinary_formula") or m.get("stoichiometric_formula"),
            "aliases": [a.get("alias") for a in (m.get("aliases") or []) if a.get("alias")][:10]}


def _xsc_molecule_search(query, limit=40):
    """按 中文名 / 化学式 / 英文名 / 俗名 模糊搜索 HITRAN 分子，返回候选（含 id）。

    打分：精确命中名字或别名 100 > 精确化学式 95 > 前缀命中 70 > 包含 40。
    中文输入先查内置对照表（_MOL_ZH）换成英文关键词再匹配。
    """
    q = str(query or "").strip().translate(_SUB_DIGITS)
    if not q:
        return []
    kw = _MOL_ZH.get(q) or _MOL_ZH.get(q.rstrip("气")) or q
    k = kw.strip().lower()
    if not k:
        return []
    out = []
    for m in _molecules_index():
        nm = (m.get("common_name") or "").lower()
        fm = (m.get("ordinary_formula") or "").lower()
        al = [(a.get("alias") or "").lower() for a in (m.get("aliases") or [])]
        # 分档：常用名优先于别名/化学式，精确 > 前缀 > 包含。
        # （否则如 "prop" 会因某别名含 prop 而把 HFC 类分子排到 Propane 前面）
        if k == nm:
            score = 100
        elif fm and k == fm:
            score = 95
        elif k in al:
            score = 90
        elif nm.startswith(k):
            score = 80
        elif fm and fm.startswith(k):
            score = 75
        elif any(x.startswith(k) for x in al):
            score = 60
        elif k in nm:
            score = 50
        elif fm and k in fm:
            score = 40
        elif any(k in x for x in al):
            score = 30
        else:
            score = 0
        if score:
            out.append((score, m))
    out.sort(key=lambda t: (-t[0], (t[1].get("common_name") or "").lower()))
    return [dict(_molid_brief(m), score=s) for s, m in out[:limit]]


def _xsc_should_retry(e):
    """是否值得重试：网络抖动/超时/5xx 值得；4xx（404/403 等）不值得。"""
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        return e.code in (408, 429, 500, 502, 503, 504)
    return True


def _xsc_retry(fn, tries=3, delay=1.5):
    """网络抖动重试。实测 hitran.org 偶发 URLError（约 1/8），重试即成功。"""
    import time
    last = None
    for i in range(max(1, int(tries))):
        try:
            return fn()
        except Exception as e:
            last = e
            if i >= tries - 1:
                break
            if not _xsc_should_retry(e):
                raise
            time.sleep(delay * (i + 1))
    raise last


def _xsc_molecule_id(name):
    """分子名 → molecule_id：先查本地索引（名/化学式/别名精确匹配），未命中再走在线接口。

    本地索引带来两点好处：① 支持化学式与别名（C3H8 / CH3CH2CH3 / 74-98-6 都能认）；
    ② 命中即时返回，省一次网络往返。索引未命中时仍回退原免登录精确接口。
    """
    s0 = str(name or "").strip().translate(_SUB_DIGITS)
    if s0 in _MOL_ZH or s0.rstrip("气") in _MOL_ZH:      # 中文名先换成英文关键词
        s0 = _MOL_ZH.get(s0) or _MOL_ZH.get(s0.rstrip("气"))
    s = s0.lower()
    if s:
        for m in _molecules_index():
            nm = (m.get("common_name") or "").lower()
            fm = (m.get("ordinary_formula") or "").lower()
            if s == nm or (fm and s == fm) or \
                    any(s == (a.get("alias") or "").lower() for a in (m.get("aliases") or [])):
                return int(m["id"])
    import urllib.error
    import urllib.parse
    q = urllib.parse.quote(str(name).strip())
    try:
        mid = _xsc_retry(
            lambda: _http_get_text(
                f"https://hitran.org/xsc/get-molecule?molecule_name={q}").strip(),
            tries=3, delay=1.5)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None                     # 该名在截面库查无此分子（正常情况，交由上层提示）
        return None
    except Exception:
        return None                         # 网络异常同样不抛，避免调用方崩溃
    return int(mid) if mid.isdigit() else None


def _xsc_api_records(molecule_id, timeout=90):
    """官方 API 拉取某分子的截面元数据列表（含可直接下载的 filename）。"""
    key = _api_key()
    if not key:
        raise RuntimeError(
            "[hitran_xsc_files] 未配置 HITRAN API key：清单接口 /api/v2/<key>/cross-sections "
            "需要它。请先在界面「API Key」中填写，或设置环境变量 HITRAN_API_KEY。")
    url = (f"https://hitran.org/api/v2/{key}/cross-sections"
           f"?molecule_id__in={int(molecule_id)}")
    try:
        data = _xsc_retry(lambda: json.loads(_http_get_text(url, timeout=timeout)),
                          tries=3, delay=1.5)
    except Exception as e:
        raise RuntimeError(f"[hitran_xsc_files] 查询失败（{type(e).__name__}: {e}）；"
                           f"请确认可直连 hitran.org 且 API key 有效。") from e
    if str(data.get("status", "")).upper() != "OK":
        raise RuntimeError(f"[hitran_xsc_files] API 返回异常："
                           f"{data.get('message') or data.get('status')}")
    return (data.get("content") or {}).get("data") or []


def _xsc_normalize(rec):
    """API 记录 → 统一字段（含体积估算、下载地址、本地路径）。"""
    npts = int(rec.get("npnts") or 0)
    fname = str(rec.get("filename") or "")
    return {
        "id": rec.get("id"),
        "filename": fname,
        "molecule": rec.get("molecule_alias") or "",
        "status": rec.get("status") or "",
        "T_K": rec.get("temperature"),
        "p_Torr": rec.get("pressure"),
        "nu_min_cm-1": rec.get("numin"),
        "nu_max_cm-1": rec.get("numax"),
        "resolution_cm-1": rec.get("resolution"),
        "broadener": rec.get("broadener"),
        "n_points": npts,
        "est_size_mb": round(npts * _XSC_BYTES_PER_POINT / 1e6, 2) if npts else None,
        "download_url": f"https://hitran.org/data/xsec/{fname}" if fname else "",
        "local_path": str(XSC_DIR / fname) if fname else "",
        "downloaded": bool(fname) and (XSC_DIR / fname).exists(),
    }


def _xsc_http_open(url, timeout, method="GET"):
    """带浏览器 UA 打开 hitran.org（截面数据路径公开，无需登录）。"""
    import urllib.request
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    return urllib.request.urlopen(req, timeout=timeout)


def _xsc_head_size(filename, timeout=30):
    """HEAD 取文件大小（仅"只给文件名"时用于估算总体积；失败返回 0）。"""
    import urllib.parse
    fname = Path(str(filename)).name

    def _head():
        with _xsc_http_open(f"https://hitran.org/data/xsec/{urllib.parse.quote(fname)}",
                            timeout, method="HEAD") as r:
            return int(r.headers.get("Content-Length") or 0)

    try:
        return _xsc_retry(_head, tries=2, delay=1.0)
    except Exception:
        return 0


def _xsc_download_one(filename, dest_dir, timeout=900):
    """下载单个截面文件（.part 临时文件 + 原子重命名，避免半截文件被当好的用）。"""
    import shutil
    import urllib.parse
    safe = Path(str(filename)).name                 # 防路径穿越
    if not safe:
        raise ValueError("空文件名")
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    tmp = dest / (safe + ".part")

    def _fetch():
        with _xsc_http_open(f"https://hitran.org/data/xsec/{urllib.parse.quote(safe)}",
                            timeout) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, length=1 << 20)
        n = tmp.stat().st_size
        if n < 1024:                                # 与线表同一判据：过小视为残骸
            raise RuntimeError(f"下载内容异常（{n} 字节）")
        os.replace(tmp, dest / safe)                # 原子落盘
        return n

    try:
        return _xsc_retry(_fetch, tries=2, delay=2.0)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def t_xsc_molecules(query=None, limit=40):
    """检索 HITRAN 分子（中文名 / 化学式 / 英文名 / 俗名都能搜），用于挑截面分子。

    为什么要它：截面库只认 HITRAN 页面上的英文名（如 Propane），中文用户常常不知道
    该输入什么。本工具先用内置中文对照表翻译（丙烷 → Propane），再对约 670 个分子的
    常用名 / 化学式 / 全部别名做模糊匹配（精确 > 化学式 > 前缀 > 包含），返回候选及 id。
    把 id 交给 hitran_xsc_files(molecule_id=...) 即可列出可下载文件。

    query 为空则列出全部分子（按名排序，最多 limit 条）。
    """
    mols = _molecules_index()
    if not mols:
        return {"n": 0, "molecules": [], "error": (
            "无法获取分子索引：需要有效的 HITRAN API key 与网络（索引一次拉取后缓存 30 天）。")}
    limit = max(1, int(limit))
    if not query:
        items = sorted(mols, key=lambda m: (m.get("common_name") or "").lower())
        return {"n": len(items), "molecules": [_molid_brief(m) for m in items[:limit]],
                "hint": "传入 query 可检索，如 query='丙烷' / 'C3H8' / 'propane' / 'prop'。"}
    hits = _xsc_molecule_search(query, limit=limit)
    out = {"query": str(query).strip(), "n": len(hits), "molecules": hits,
           "hint": ("把选中项的 id 传给 hitran_xsc_files(molecule_id=...) 列文件，"
                    "或直接用 hitran_xsc_download(name=...) 下载。")}
    if not hits:
        out["hint"] = (f"未匹配到 '{query}'。可换化学式（如 C3H8）或英文名试试；"
                       f"不传 query 可列出全部分子。")
    return out


def t_xsc_files(name=None, include_all=False, molecule_id=None):
    """列出某截面分子**可下载**的截面文件清单（需 HITRAN API key，免 Portal 登录）。

    分子可以三种方式给出：name（英文名/化学式/中文名，如 Propane / C3H8 / 丙烷）、
    molecule_id（由 hitran_xsc_molecules 检索得到，最稳）。名字认不出时，返回里会附
    candidates 候选列表供选择 —— 截面库只收录重分子，逐线库的分子查不到属正常。

    与 hitran_xsc_search 的分工：本工具走官方 API（/api/v2/<key>/cross-sections），
    返回**可直接下载的文件名 filename** 与体积估算；hitran_xsc_search 走免登录页面接口，
    无 key 时也能探到条目但没有文件名。

    典型链条：hitran_xsc_molecules 找分子 → hitran_xsc_files 列清单 →
    挑 filenames → hitran_xsc_download 下载 → hitran_cross_section 读入绘图。
    """
    if molecule_id is None and not name:
        raise ValueError("[hitran_xsc_files] 必须提供 name（分子名/化学式/中文名，"
                         "如 Propane / C3H8 / 丙烷）或 molecule_id（用 hitran_xsc_molecules 检索）。")
    try:
        mid = int(molecule_id) if molecule_id is not None else _xsc_molecule_id(name)
    except Exception as e:
        return {"query": str(name).strip(), "found": False, "files": [],
                "error": f"名称解析失败（{type(e).__name__}: {e}）。请检查网络，或改用 molecule_id。"}
    if mid is None:
        return {"query": str(name).strip(), "found": False, "files": [],
                "candidates": _xsc_molecule_search(name, limit=8),
                "hint": (f"未找到 '{name}'。可先用 hitran_xsc_molecules(query=...) 检索；"
                         f"若该分子不在截面子库（截面库只含重分子），请改用逐线库工具计算。")}
    items = [_xsc_normalize(r) for r in _xsc_api_records(mid)]
    n_all = len(items)
    if not include_all:
        mains = [it for it in items if it["status"] in ("main", "")]
        if mains:
            items = mains
    return {"query": str(name).strip(), "found": True, "molecule_id": mid,
            "n_files": len(items), "n_files_all": n_all,
            "total_est_mb": round(sum((it["est_size_mb"] or 0) for it in items), 1),
            "files": items,
            "hint": ("选定 filenames 后调 "
                     "hitran_xsc_download(name=..., filenames=[...]) 下载到 xsc_data/，"
                     "再 hitran_cross_section(file_path=...) 读入绘图。")}


def t_xsc_download(name=None, filenames=None, ids=None, molecule_id=None, max_total_mb=None,
                   dry_run=False, overwrite=False, progress=None, cancel=None):
    """把选定的截面文件下载到 xsc_data/（官方 API 列清单 + 公开路径取文件，无需 Portal 登录）。

    选择方式二选一（可混用）：filenames=[...] 与 ids=[...]，均取自 hitran_xsc_files。
    强烈建议带上 name：这样才能拿到 T/p/点数并校验总体积；只给 filenames 时逐个用
    HEAD 估重，达不到限流保护的效果。

    dry_run=True 只报告将下载什么（含总体积），不实际下载。
    下载完成的文件会出现在 hitran_cross_section 的可用清单里，可直接读入绘图。
    """
    filenames = [str(x).strip() for x in (filenames or []) if str(x).strip()]
    ids = [int(x) for x in (ids or [])]
    if not filenames and not ids:
        raise ValueError("[hitran_xsc_download] 必须给出 filenames=[...] 或 ids=[...]"
                         "（可用 hitran_xsc_files 获取）。")
    limit_mb = XSC_DL_LIMIT_MB if max_total_mb is None else float(max_total_mb)

    # ── 解析目标 ──
    targets, missing = [], []
    pool = []
    if molecule_id is not None or name:
        listing = (t_xsc_files(molecule_id=int(molecule_id), include_all=True)
                   if molecule_id is not None else t_xsc_files(name=name, include_all=True))
        if not listing.get("found"):
            return {"downloaded": [], "skipped": [], "failed": [], "missing": missing,
                    "hint": listing.get("hint")}
        pool = listing["files"]
    by_fname = {it["filename"]: it for it in pool}
    for f in filenames:
        it = by_fname.get(f)
        if it is None:
            if name:
                missing.append(f)                    # 有清单但对不上 → 报告，不猜
                continue
            it = {"id": None, "filename": f, "molecule": "", "T_K": None, "p_Torr": None,
                  "nu_min_cm-1": None, "nu_max_cm-1": None, "resolution_cm-1": None,
                  "broadener": None, "n_points": None, "est_size_mb": None}
            size = _xsc_head_size(f)
            if size:
                it["est_size_mb"] = round(size / 1e6, 2)
        targets.append(it)
    if ids:
        want = set(ids)
        for it in pool:
            if it.get("id") in want and it not in targets:
                targets.append(it)
        if name:
            have = {it.get("id") for it in pool}
            missing += [f"id={i}" for i in sorted(want - have)]

    est_total = round(sum((it.get("est_size_mb") or 0) for it in targets), 1)
    plan = {"n_files": len(targets), "est_total_mb": est_total, "limit_mb": limit_mb,
            "files": [it["filename"] for it in targets], "missing": missing}
    if missing:
        plan["hint_missing"] = (f"以下条目在 '{name}' 的清单里不存在（名称需完全一致，"
                                f"请直接用 hitran_xsc_files 返回的 filename）：{missing}")
    if limit_mb and est_total > limit_mb:
        return {"error": f"[hitran_xsc_download] 选中 {len(targets)} 个文件、预计 {est_total} MB，"
                         f"超过上限 {limit_mb} MB；请减少选择或调大 max_total_mb。",
                "plan": plan}
    if dry_run:
        return {"dry_run": True, "plan": plan,
                "hint": "确认无误后以 dry_run=False 实下载。"}
    if not targets:
        return {"error": "[hitran_xsc_download] 没有匹配到任何文件。", "plan": plan}

    # ── 逐个下载（串行，避免触发站点限流） ──
    XSC_DIR.mkdir(parents=True, exist_ok=True)
    downloaded, skipped, failed = [], [], []
    done_bytes = 0
    for i, it in enumerate(targets):
        fname = it["filename"]
        dest = XSC_DIR / Path(fname).name
        if dest.exists() and not overwrite:
            skipped.append({"filename": fname, "reason": "已存在（overwrite=False 时跳过）",
                            "path": str(dest)})
            continue
        if cancel and cancel():
            failed.append({"filename": fname, "error": "已取消"})
            break
        if progress:
            try:
                progress(i, len(targets), fname, done_bytes)
            except Exception:
                pass
        try:
            n = _xsc_download_one(fname, XSC_DIR)
        except Exception as e:
            failed.append({"filename": fname, "error": f"{type(e).__name__}: {e}"})
            continue
        done_bytes += n
        downloaded.append({"filename": fname, "path": str(dest),
                           "size_mb": round(n / 1e6, 2),
                           "T_K": it.get("T_K"), "p_Torr": it.get("p_Torr")})
        if limit_mb and done_bytes / 1e6 > limit_mb:
            failed.append({"filename": "(后续已停止)",
                           "error": f"累计 {done_bytes / 1e6:.0f} MB 已超上限 {limit_mb} MB"})
            break
    out = {"downloaded": downloaded, "skipped": skipped, "failed": failed,
           "n_downloaded": len(downloaded), "total_mb": round(done_bytes / 1e6, 2),
           "dest_dir": str(XSC_DIR), "plan": plan}
    if downloaded:
        out["next_step"] = (f"用 hitran_cross_section(file_path=\"{downloaded[0]['path']}\", "
                            f"numin=..., numax=...) 读入绘图。")
    return out


def t_apikey_status(probe=False):
    """HITRAN API key / 缓存 / 产物 / 截面文件状态速查（排障用，只读）。

    工具包不含任何数据：所有缓存与个人文件都在运行期目录（gitignore 区）。

    probe=True 会额外做一次 HAPI2 初始化探测（连带加载 sqlalchemy/numba，
    约 +100MB 内存）—— 仅供自检使用；GUI 状态面板不要开，否则拖慢启动。
    """
    key = _api_key()
    cache_n, cache_bytes, xsc_n, out_n = 0, 0, 0, 0
    for d in (ROOT / "Hitran_Data", XSC_DIR, OUT_DIR):
        n, b = 0, 0
        if d.exists():
            for p in d.iterdir():
                if p.is_file():
                    n += 1
                    b += p.stat().st_size
        if d == ROOT / "Hitran_Data":
            cache_n, cache_bytes = n, b
        elif d == XSC_DIR:
            xsc_n = n
        else:
            out_n = n
    from tools import hitran as ht
    caps = ht.get_capabilities()
    h2 = ht.hapi2_status()
    # 仅在显式探测时初始化 HAPI2（会连带加载 numba，代价较大）。
    if probe and h2["installed"] and h2["api_key_present"] and not h2["enabled"]:
        try:
            ht.hapi2_bootstrap(force=True)     # 强制重试：本次会话未成功也再试一次
            h2 = ht.hapi2_status()
        except Exception:
            pass
    return {"api_key_configured": bool(key), "api_key_source":
            "env(HITRAN_API_KEY)" if os.environ.get("HITRAN_API_KEY", "").strip()
            else "tools/hitran_api_key.txt" if key else "未配置",
            "line_cache_files": cache_n, "line_cache_MB": round(cache_bytes / 1e6, 2),
            "xsc_data_files": xsc_n, "output_files": out_n,
            "hapi_version": caps["hapi_version"],
            "hapi2_available": caps["hapi2_available"],
            "hapi2_version": h2["version"] or caps["hapi2_version"],
            "hapi2_enabled": h2["enabled"],
            "hapi2_import_error": h2.get("import_error"),
            "hapi2_last_error": h2["last_error"],
            "download_engine": ("HAPI2 官方 API（带 api_key）" if h2["enabled"]
                                else "HAPI2 官方 API（首次下载时自动启用）"
                                if (h2["installed"] and h2["api_key_present"])
                                else "HAPI 1.x 旧下载接口（回退）"),
            "numba_available": caps["numba_available"],
            "numba_version": caps["numba_version"],
            "numpy_version": caps["numpy_version"],
            "note": ("key 已生效：线表与截面下载均经官方 v2 API（URL 携带 key）；仅当回退到 "
                     "HAPI 1.x 旧接口时才不校验 key。官方每日抓取配额超限会 403，缓存未删的前提下"
                     "无需重复抓取。HAPI2/Numba 为可选加速引擎，检测到可用时自动提示。")}


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

_CONFIRM_NOTE = ("数据实时取自 HITRANonline。"
                 "【必填】波数范围 numin/numax（未提供必须主动询问用户，不得猜测）。"
                 "【可选默认】T=296K, P=1atm, mole_frac=1.0, step=0.01cm-1；"
                 "使用默认值时需在结果中告知用户。"
                 "【混合气】specs_csv 格式：'CH4:0.01,C2H6:1e-5'。")

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
                     "properties": {"name": {"type": "string", "description": "分子式，如 CH4/CO2/H2O"},
                                    "numin": {"type": "number", "description": "波数下限 cm-1（必填）"},
                                    "numax": {"type": "number", "description": "波数上限 cm-1（必填）"},
                                    "iso": {"type": "string", "description": "同位素号（如 1）或 'all'（全同位素）；默认主同位素"},
                                    "force": {"type": "boolean", "description": "True 强制重抓"}},
                     "required": ["name", "numin", "numax"]}},
    {"name": "hitran_lines",
     "description": "列出窗口内最强的 N 条谱线（波数、线强、空气展宽、低态能量），用于选线与干扰分析。",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string", "description": "分子式，如 CH4/CO2/H2O"},
                                    "numin": {"type": "number", "description": "波数下限 cm-1（必填）"},
                                    "numax": {"type": "number", "description": "波数上限 cm-1（必填）"},
                                    "iso": {"type": "string", "description": "同位素号（如 1）或 'all'"},
                                    "top_n": {"type": "integer", "description": "返回条数，默认 10"},
                                    "min_intensity": {"type": "number", "description": "最小线强阈值"},
                                    "force": {"type": "boolean", "description": "True 强制按当前窗口重抓线表"}},
                     "required": ["name", "numin", "numax"]}},
    {"name": "hitran_spectrum",
     "description": "计算吸收系数 α / 透过率谱（单分子或全同位素），落盘带溯源水印的 CSV，"
                    "返回峰值、积分、线表信息与告警。多组分混合请分次调用后自行叠加。"
                    + _CONFIRM_NOTE,
     "inputSchema": {"type": "object",
                     "properties": {
                         "name": {"type": "string", "description": "分子式，如 CH4/CO2/H2O"},
                         "specs_csv": {"type": "string",
                                       "description": "多物种一次叠加：'CH4:0.01,C2H6:1e-5'（冒号后摩尔分数，缺省=1 纯气体），与 name 二选一"},
                         "mole_frac": {"type": "number",
                                       "description": "摩尔分数 0~1；不填按纯气体 1 处理并在 assumed_defaults 里标记"},
                         "iso": {"type": "string", "description": "同位素号（如 1）或 'all'；默认主同位素"},
                         "numin": {"type": "number", "description": "波数下限 cm-1（必填）"},
                         "numax": {"type": "number", "description": "波数上限 cm-1（必填）"},
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
                         "specs_csv": {"type": "string",
                                       "description": "多物种一次叠加：'CH4:0.01,C2H6:1e-5'，与 name 二选一"},
                         "mole_frac": {"type": "number"},
                         "iso": {"type": "string"},
                         "numin": {"type": "number", "description": "波数下限 cm-1（必填）"},
                         "numax": {"type": "number", "description": "波数上限 cm-1（必填）"},
                         "T": {"type": "number", "description": "温度 K"},
                         "P": {"type": "number", "description": "压力 atm"},
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
                    "逐线库 61 分子走 HAPI 在线 API；截面库 600+ 重分子"
                    "只经 Web Portal 下载文件、无在线 API。本工具把下载的截面文件接入同一套产物链路，"
                    "用于截面分子的谱线叠加与干扰分析。",
     "inputSchema": {"type": "object",
                     "properties": {
                         "file_path": {"type": "string",
                                       "description": "必填：本地 HOTW 截面文件路径（两列：wavenumber_cm-1, sigma_cm2_per_molecule）"},
                         "source_label": {"type": "string",
                                          "description": "溯源标签，如 '<分子名> <温度>K <数据源>'；默认取文件名"},
                         "numin": {"type": "number", "description": "截窗下限 cm-1；默认全谱"},
                         "numax": {"type": "number", "description": "截窗上限 cm-1；默认全谱"},
                         "title": {"type": "string", "description": "图标题，默认 '<label>  <窗口> cm-1'"},
                         "ylog": {"type": "boolean", "description": "True 用对数坐标"},
                         "dpi": {"type": "integer", "description": "PNG 分辨率，默认 160"},
                         "save_csv": {"type": "boolean", "description": "是否落盘溯源 CSV，默认 True"}},
                     "required": ["file_path"]}},
    {"name": "hitran_xsc_search",
     "description": "在线探测 HITRAN 截面子库某分子的截面文件清单（免登录只读）：分子号、常用名、"
                    "全部文件元数据（ν 范围/T/p/分辨率/点数/展宽气）。用于下载前判断该选哪个 T–P 文件；"
                    "实际下载需登录 hitran.org/xsc，文件放入 xsc_data/ 后由 hitran_cross_section 读入。",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string",
                                             "description": "hitran.org/xsc 上显示的分子名，如 Propane / Ethane / Acetone"}},
                     "required": ["name"]}},
    {"name": "hitran_apikey_status",
     "description": "HITRAN API key / 线表缓存 / 产物 / 截面文件状态速查（只读，排障用）。"
                    "工具包不含任何数据：缓存与个人文件均在运行期 gitignore 目录。",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "hitran_xsc_molecules",
     "description": "检索 HITRAN 分子（中文名/化学式/英文名/俗名都能搜），用于挑截面分子。"
                    "截面库只认英文名（如 Propane），本工具先查内置中文对照（丙烷→Propane），"
                    "再对约 670 个分子的名/化学式/别名做模糊匹配，返回候选与 id；query 留空列出全部。"
                    "把 id 传给 hitran_xsc_files(molecule_id=...) 即可列出可下载的截面文件。",
     "inputSchema": {"type": "object",
                     "properties": {
                         "query": {"type": "string",
                                   "description": "检索词：中文名（丙烷）/化学式（C3H8）/英文名（propane）/俗名；留空列全部"},
                         "limit": {"type": "integer", "description": "最多返回条数，默认 40"}},
                     "required": []}},
    {"name": "hitran_xsc_files",
     "description": "列出某截面分子在 hitran.org 上**可直接下载**的截面文件清单（温度/压力/波数范围/"
                    "分辨率/点数/体积估算/filename；需本机 HITRAN API key，免 Portal 登录）。"
                    "分子可用 name（英文名/化学式/中文名）或 molecule_id（推荐，先经 hitran_xsc_molecules 检索）。",
     "inputSchema": {"type": "object",
                     "properties": {
                         "name": {"type": "string",
                                  "description": "分子名/化学式/中文名，如 Propane / C3H8 / 丙烷"},
                         "molecule_id": {"type": "integer",
                                         "description": "分子号（由 hitran_xsc_molecules 得到；与 name 二选一即可）"},
                         "include_all": {"type": "boolean",
                                         "description": "是否含非 main 的旧版本记录（默认 False 只列在用版本）"}},
                     "required": []}},
    {"name": "hitran_xsc_download",
     "description": "把选定的截面文件下载到 xsc_data/（官方 API + 公开数据路径，无需 Portal 登录）。"
                    "filenames/ids 取自 hitran_xsc_files；建议带上 name 以校验总体积（默认上限 300 MB）。"
                    "dry_run=True 只返回将下载的清单与体积。下载后可用 hitran_cross_section(file_path=...) 读入绘图。",
     "inputSchema": {"type": "object",
                     "properties": {
                         "name": {"type": "string", "description": "分子名（同 hitran_xsc_files）"},
                         "filenames": {"type": "array", "items": {"type": "string"},
                                       "description": "要下载的文件名列表（hitran_xsc_files 返回的 filename）"},
                         "ids": {"type": "array", "items": {"type": "integer"},
                                 "description": "要下载的记录 id 列表（与 filenames 二选一或混用）"},
                         "max_total_mb": {"type": "number", "description": "总体积上限（MB），默认 300"},
                         "dry_run": {"type": "boolean", "description": "只报告不下载（默认 False）"},
                         "overwrite": {"type": "boolean", "description": "已存在文件是否覆盖（默认 False 跳过）"}},
                     "required": []}},
]
DISPATCH = {
    "hitran_species": t_species,
    "hitran_fetch": t_fetch,
    "hitran_lines": t_lines,
    "hitran_spectrum": t_spectrum,
    "hitran_plot": t_plot,
    "hitran_partition_sum": t_partition_sum,
    "hitran_cross_section": t_cross_section,
    "hitran_xsc_search": t_xsc_search,
    "hitran_xsc_files": t_xsc_files,
    "hitran_xsc_molecules": t_xsc_molecules,
    "hitran_xsc_download": t_xsc_download,
    "hitran_apikey_status": t_apikey_status,
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


def _iter_requests():
    """自适应读取：同时支持标准 MCP（Content-Length framing）与裸 JSON 行协议。

    逐条产生 (raw_text, use_framing)。use_framing=True 表示客户端走标准 framing，
    响应必须用同样的 framing 回写，否则严格客户端解析不到响应 —— 这是能否接入
    标准 MCP 客户端（WorkBuddy / Claude Desktop 等）的关键。
    """
    stdin = sys.stdin.buffer
    while True:
        first = stdin.readline()
        if not first:
            return
        if first.lstrip().lower().startswith(b"content-length"):
            headers, line = {}, first
            while line and line not in (b"\r\n", b"\n"):
                k, _, v = line.decode("utf-8", "replace").partition(":")
                headers[k.strip().lower()] = v.strip()
                line = stdin.readline()
            n = int(headers.get("content-length") or 0)
            body = stdin.read(n) if n > 0 else b""
            yield body.decode("utf-8", "replace"), True
        else:
            yield first.decode("utf-8", "replace"), False


def _write_response(out, use_framing):
    """按客户端所用 framing 回写：标准客户端要 Content-Length 头，旧客户端要裸 JSON 行。"""
    data = json.dumps(out, ensure_ascii=False).encode("utf-8")
    if use_framing:
        sys.stdout.buffer.write(b"Content-Length: %d\r\n\r\n" % len(data) + data)
    else:
        sys.stdout.buffer.write(data + b"\n")
    sys.stdout.buffer.flush()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    for raw, use_framing in _iter_requests():
        raw = raw.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
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
        _write_response(out, use_framing)


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
    # 截面链路自测：合成 HOTW 截面文件（两列 ν–σ，高斯峰模拟截面谱）
    import numpy as _np2
    nu_s = _np2.linspace(2800, 3100, 1501)
    sig = 1.6e-18 * _np2.exp(-((nu_s - 2967.0) / 8.0) ** 2)
    demo = OUT_DIR / "_demo_c3h8_pnnl.txt"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(demo, "w", encoding="utf-8") as f:
        f.write("# synthetic demo cross-section (not real data)\n")
        for a, b in zip(nu_s, sig):
            f.write(f"{a:.4f} {b:.6e}\n")
    xs = t_cross_section(file_path=str(demo), source_label="demo xsc",
                         numin=2900, numax=3000)
    print("— xsc    :", {k: xs[k] for k in ("n_points_file", "n_points_in_window", "peak")},
          "png:", xs["png"])
    # specs_csv 多物种叠加（复用缓存）
    mix2 = t_plot(specs_csv="CO:0.0001,H2O:0.02", numin=2140, numax=2146,
                  T=296, P=1.0, step=0.01)
    print("— mix2   :", mix2["png"], "| per:", list(mix2["peaks"].keys()))
    # 截面目录列出（个人数据目录，可能为空）
    lst = t_cross_section()
    print("— xscdir :", len(lst["available_files"]), "files ->", lst["hint"][:60])
    # 在线探测截面子库（真实网络）
    try:
        sr = t_xsc_search("Propane")
        print("— xsearch:", "found" if sr["found"] else "NOT FOUND",
              "| id:", sr.get("molecule_id"), "| n_files:", sr.get("n_files"))
    except Exception as e:
        print("— xsearch: ERR", str(e)[:100])
    # 运行状态
    st = t_apikey_status(probe=True)
    print("— status :", {k: st[k] for k in ("api_key_configured", "line_cache_files",
                                            "xsc_data_files", "output_files")})


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
