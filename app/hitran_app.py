#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HitranLab —— HITRAN 光谱分析桌面工作站（Windows）。

复用 tools/hitran_mcp.py 的取数/计算引擎（同一套物理纪律与防呆），
提供本地 GUI：多组分吸收谱 / 透过率 / 截面谱计算与绘图、强线列表、
配分函数、截面文件（HOTW）导入、CSV/PNG 导出。

运行:  python app/hitran_app.py
打包:  PyInstaller（见 README 或本文件底部注释）
"""
APP_VERSION = "1.4.0"
APP_REPO = "https://github.com/LKF0402/hitran-mcp"
import os
import queue
import sys
import threading
import time
import traceback
import ctypes
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent
if not getattr(sys, "frozen", False) and str(ROOT) not in sys.path:
    # 源码模式：保证 tools 包可导入；冻结模式跳过，避免 exe 同目录 .py 影子覆盖打包内模块
    sys.path.insert(0, str(ROOT))

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# matplotlib 嵌入式后端必须最先设置
import matplotlib
matplotlib.use("TkAgg", force=True)
import matplotlib as mpl
mpl.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from tools import hitran_mcp as hm          # 复用服务器引擎（含 HAPI 惰性加载）

APP_TITLE = "HitranLab · HITRAN 光谱分析工作站"
PROFILES = ["voigt", "lorentz", "gauss", "doppler", "ht", "sdvoigt"]

# 叠加模式的颜色循环（柔和配色，不刺眼）
OVERLAY_COLORS = ["#E07A7A", "#6B8FD4", "#7BC47F", "#D4A86B", "#A88BD4", "#6BB8D4", "#D4936B", "#6BB8A8"]

# 分子别名表：别名（小写） -> 标准分子式
# 包含常见英文名、中文名、HITRAN M 编号
MOLECULE_ALIASES = {
    # M=1..10
    "water": "H2O", "h2o": "H2O", "1": "H2O",
    "carbon dioxide": "CO2", "co2": "CO2", "2": "CO2",
    "ozone": "O3", "o3": "O3", "3": "O3",
    "nitrous oxide": "N2O", "n2o": "N2O", "4": "N2O",
    "carbon monoxide": "CO", "co": "CO", "5": "CO",
    "methane": "CH4", "ch4": "CH4", "6": "CH4",
    "oxygen": "O2", "o2": "O2", "7": "O2",
    "nitric oxide": "NO", "no": "NO", "8": "NO",
    "sulfur dioxide": "SO2", "so2": "SO2", "9": "SO2",
    "nitrogen dioxide": "NO2", "no2": "NO2", "10": "NO2",
    # M=11..20
    "ammonia": "NH3", "nh3": "NH3", "11": "NH3",
    "nitric acid": "HNO3", "hno3": "HNO3", "12": "HNO3",
    "hydroxyl": "OH", "oh": "OH", "13": "OH",
    "hydrogen fluoride": "HF", "hf": "HF", "14": "HF",
    "hydrogen chloride": "HCl", "hcl": "HCl", "15": "HCl",
    "hydrogen bromide": "HBr", "hbr": "HBr", "16": "HBr",
    "hydrogen iodide": "HI", "hi": "HI", "17": "HI",
    "chlorine monoxide": "ClO", "clo": "ClO", "18": "ClO",
    "carbonyl sulfide": "OCS", "ocs": "OCS", "19": "OCS",
    "formaldehyde": "H2CO", "h2co": "H2CO", "20": "H2CO",
    # M=21..30
    "hypochlorous acid": "HOCl", "hocl": "HOCl", "21": "HOCl",
    "nitrogen": "N2", "n2": "N2", "22": "N2",
    "hydrogen cyanide": "HCN", "hcn": "HCN", "23": "HCN",
    "methyl chloride": "CH3Cl", "ch3cl": "CH3Cl", "24": "CH3Cl",
    "hydrogen peroxide": "H2O2", "h2o2": "H2O2", "25": "H2O2",
    "acetylene": "C2H2", "c2h2": "C2H2", "26": "C2H2",
    "ethane": "C2H6", "c2h6": "C2H6", "27": "C2H6",
    "phosphine": "PH3", "ph3": "PH3", "28": "PH3",
    "carbonyl fluoride": "COF2", "cof2": "COF2", "29": "COF2",
    "sulfur hexafluoride": "SF6", "sf6": "SF6", "30": "SF6",
    # M=31..40
    "hydrogen sulfide": "H2S", "h2s": "H2S", "31": "H2S",
    "formic acid": "HCOOH", "hcooh": "HCOOH", "32": "HCOOH",
    "hydroperoxyl": "HO2", "ho2": "HO2", "33": "HO2",
    "oxygen atom": "O", "o": "O", "34": "O",
    "chlorine nitrate": "ClONO2", "clono2": "ClONO2", "35": "ClONO2",
    "nitric oxide cation": "NOP", "nop": "NOP", "no+": "NOP", "36": "NOP",
    "hypobromous acid": "HOBr", "hobr": "HOBr", "37": "HOBr",
    "ethylene": "C2H4", "c2h4": "C2H4", "38": "C2H4",
    "methanol": "CH3OH", "ch3oh": "CH3OH", "39": "CH3OH",
    "methyl bromide": "CH3Br", "ch3br": "CH3Br", "40": "CH3Br",
    # M=41..50
    "acetonitrile": "CH3CN", "ch3cn": "CH3CN", "41": "CH3CN",
    "carbon tetrafluoride": "CF4", "cf4": "CF4", "42": "CF4",
    "diacetylene": "C4H2", "c4h2": "C4H2", "43": "C4H2",
    "cyanoacetylene": "HC3N", "hc3n": "HC3N", "44": "HC3N",
    "hydrogen": "H2", "h2": "H2", "45": "H2",
    "carbon monosulfide": "CS", "cs": "CS", "46": "CS",
    "sulfur trioxide": "SO3", "so3": "SO3", "47": "SO3",
    "cyanogen": "C2N2", "c2n2": "C2N2", "48": "C2N2",
    "phosgene": "COCl2", "cocl2": "COCl2", "49": "COCl2",
    "sulfur monoxide": "SO", "so": "SO", "50": "SO",
    # M=51..61
    "methyl fluoride": "CH3F", "ch3f": "CH3F", "51": "CH3F",
    "germane": "GeH4", "geh4": "GeH4", "52": "GeH4",
    "carbon disulfide": "CS2", "cs2": "CS2", "53": "CS2",
    "methyl iodide": "CH3I", "ch3i": "CH3I", "54": "CH3I",
    "nitrogen trifluoride": "NF3", "nf3": "NF3", "55": "NF3",
}

# 反向别名表：标准分子式 -> 英文名（用于图例显示）
MOLECULE_NAMES = {
    "H2O": "Water", "CO2": "Carbon dioxide", "O3": "Ozone", "N2O": "Nitrous oxide",
    "CO": "Carbon monoxide", "CH4": "Methane", "O2": "Oxygen", "NO": "Nitric oxide",
    "SO2": "Sulfur dioxide", "NO2": "Nitrogen dioxide", "NH3": "Ammonia",
    "HNO3": "Nitric acid", "OH": "Hydroxyl", "HF": "Hydrogen fluoride",
    "HCl": "Hydrogen chloride", "HBr": "Hydrogen bromide", "HI": "Hydrogen iodide",
    "ClO": "Chlorine monoxide", "OCS": "Carbonyl sulfide", "H2CO": "Formaldehyde",
    "HOCl": "Hypochlorous acid", "N2": "Nitrogen", "HCN": "Hydrogen cyanide",
    "CH3Cl": "Methyl chloride", "H2O2": "Hydrogen peroxide", "C2H2": "Acetylene",
    "C2H6": "Ethane", "PH3": "Phosphine", "COF2": "Carbonyl fluoride",
    "SF6": "Sulfur hexafluoride", "H2S": "Hydrogen sulfide", "HCOOH": "Formic acid",
    "HO2": "Hydroperoxyl", "O": "Oxygen atom", "ClONO2": "Chlorine nitrate",
    "NOP": "NO+ cation", "HOBr": "Hypobromous acid", "C2H4": "Ethylene",
    "CH3OH": "Methanol", "CH3Br": "Methyl bromide", "CH3CN": "Acetonitrile",
    "CF4": "Carbon tetrafluoride", "C4H2": "Diacetylene", "HC3N": "Cyanoacetylene",
    "H2": "Hydrogen", "CS": "Carbon monosulfide", "SO3": "Sulfur trioxide",
    "C2N2": "Cyanogen", "COCl2": "Phosgene", "SO": "Sulfur monoxide",
    "CH3F": "Methyl fluoride", "GeH4": "Germane", "CS2": "Carbon disulfide",
    "CH3I": "Methyl iodide", "NF3": "Nitrogen trifluoride",
}

def molecule_display_name(formula):
    """返回分子式的显示名：'CH4 (Methane)'，无别名时返回原分子式。"""
    if formula in MOLECULE_NAMES:
        return f"{formula} ({MOLECULE_NAMES[formula]})"
    return formula

def resolve_molecule_alias(text):
    """将用户输入（别名/分子式/M编号）解析为标准 HITRAN 分子式。
    返回 (标准分子式, 是否匹配到别名)。未匹配返回 (原输入.upper(), False)。
    """
    if not text:
        return "", False
    key = text.strip().lower()
    if key in MOLECULE_ALIASES:
        return MOLECULE_ALIASES[key], True
    # 直接输入分子式（大写）
    return text.strip().upper(), False

MODES = {"吸收系数 α (cm⁻¹)": "alpha",
         "截面 σ (cm²/molecule)": "sigma",
         "线强 S(T) (cm/molecule)": "linestrength",
         "透过率 T": "transmittance"}
DEFAULT_W = 1280
DEFAULT_H = 880
PREFS_PATH = ROOT / "hitran_prefs.json"      # 首选项落盘（运行期文件，位于 .gitignore 区）
UPDATE_ASSET = "HitranLab-windows-x64.zip"   # Release 中的免安装包名
UPDATE_DIR = ROOT / "_update"                # 更新包下载/解压目录（gitignore 区）


def _set_dark_titlebar(hwnd):
    """Windows 10/11：通过 DWM 让标题栏跟随暗色主题。"""
    for attr in (20, 19):
        try:
            val = ctypes.c_int(1)
            r = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(val), ctypes.sizeof(val))
            if r == 0:
                return
        except Exception:
            continue


class RoundedButton(tk.Canvas):
    """iOS 风格圆角按钮：Canvas 绘制圆角矩形，支持悬停/禁用。"""

    def __init__(self, parent, text, command, bg="#6B8FD4", fg="#D8D8DE",
                 hover_bg="#8AAAE5", disabled_bg="#2F2F37", disabled_fg="#8A8A92",
                 radius=14, height=44, font=("Microsoft YaHei", 10, "bold"), **kwargs):
        # 取父容器背景色：ttk.Frame 没有 "bg" 选项（实测 cget 抛 TclError），
        # 逐级上溯到有 bg 的祖先（如左侧 Canvas），避免底板退化成纯黑与主题面板色不一致
        _pbg, _w = None, parent
        while _w is not None and _pbg is None:
            try:
                _pbg = _w.cget("bg")
            except Exception:
                _w = getattr(_w, "master", None)
        super().__init__(parent, bg=_pbg or "#0F0F12",
                         highlightthickness=0, height=height, **kwargs)
        self._text = text
        self._command = command
        self._bg = bg
        self._hover_bg = hover_bg
        self._disabled_bg = disabled_bg
        self._fg = fg
        self._disabled_fg = disabled_fg
        self._radius = radius
        self._height = height
        self._font = font
        self._enabled = True
        self._current_color = bg
        self.bind("<Configure>", self._on_resize)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_resize(self, event):
        self._width = event.width
        self._draw()

    def _draw(self):
        self.delete("all")
        w = getattr(self, "_width", self.winfo_width()) or 200
        h = self._height
        c = self._radius  # 倒角大小
        color = self._current_color if self._enabled else self._disabled_bg
        fg = self._fg if self._enabled else self._disabled_fg
        # 倒角矩形（8 个点的多边形，四角斜切）
        pts = [c, 1, w - c, 1, w - 1, c, w - 1, h - c, w - c, h - 1,
               c, h - 1, 1, h - c, 1, c]
        self.create_polygon(pts, smooth=False, fill=color, outline="")
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)

    def _on_enter(self, event):
        if self._enabled:
            self._current_color = self._hover_bg
            self._draw()

    def _on_leave(self, event):
        if self._enabled:
            self._current_color = self._bg
            self._draw()

    def _on_click(self, event):
        if self._enabled and self._command:
            self._command()

    def configure(self, **kwargs):
        # 支持颜色更新（用于主题切换）
        color_keys = ["bg", "fg", "hover_bg", "disabled_bg", "disabled_fg"]
        for key in color_keys:
            if key in kwargs:
                setattr(self, f"_{key}", kwargs[key])
        if "bg" in kwargs or "hover_bg" in kwargs or "disabled_bg" in kwargs:
            self._current_color = self._bg if self._enabled else self._disabled_bg
        if "state" in kwargs:
            self._enabled = (kwargs["state"] != "disabled")
            self._current_color = self._bg if self._enabled else self._disabled_bg
        if any(k in kwargs for k in color_keys + ["state"]):
            self._draw()
        if "text" in kwargs:
            self._text = kwargs["text"]
            self._draw()
        super().configure(**{k: v for k, v in kwargs.items() if k not in ("state", "text")})

    def config(self, **kwargs):
        self.configure(**kwargs)


class Worker:
    """后台线程：不阻塞 GUI。result_queue 收到 (tag, payload)。
    支持 busy 互斥（防止重复提交）与 cancel（长循环可中途退出）。"""

    def __init__(self):
        self.q = queue.Queue()
        self.cancel_event = threading.Event()
        self._busy = False
        self._lock = threading.Lock()
        self._gen = 0                    # 任务世代号：停止/新任务后，旧线程的结果一律作废

    @property
    def busy(self):
        return self._busy

    def run(self, fn, *args, **kw):
        """提交任务。已有任务在跑时返回 False（不提交）。"""
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            self._gen += 1               # 新世代：使仍在收尾的旧线程结果失效
            gen = self._gen
            self.cancel_event.clear()

        def target():
            try:
                result = fn(*args, **kw)
                with self._lock:
                    stale = (gen != self._gen) or self.cancel_event.is_set()
                if not stale:
                    self.q.put(("ok", result))
                else:
                    self.q.put(("ok", {"kind": "cancelled"}))
            except Exception as e:
                with self._lock:
                    stale = (gen != self._gen) or self.cancel_event.is_set()
                if not stale:
                    self.q.put(("err", f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}"))
                else:
                    self.q.put(("ok", {"kind": "cancelled"}))
            finally:
                with self._lock:
                    if gen == self._gen:   # 只由"当前世代"清 busy，避免旧线程抢清新任务
                        self._busy = False

        threading.Thread(target=target, daemon=True).start()
        return True

    def cancel(self):
        """取消当前任务的协作式退出（供 Q(T) 等长循环每步自检）。
        注意：run() 会 clear() 该 Event，故"停止计算"请用 force_reset()。"""
        self.cancel_event.set()

    def force_reset(self):
        """放弃当前任务并立即恢复 UI：递增世代号（旧线程结果/异常一律作废）、
        置 cancel_event、清空队列。旧线程仍可能在后台收尾，但不再影响 UI。"""
        with self._lock:
            self._gen += 1
            self._busy = False
            self.cancel_event.set()
        # 清空队列，丢弃旧线程可能已放入的结果
        try:
            while True:
                self.q.get_nowait()
        except queue.Empty:
            pass


class HitranLab(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{DEFAULT_W}x{DEFAULT_H}")
        self.minsize(1000, 680)
        _set_dark_titlebar(self.winfo_id())
        self.worker = Worker()

        self._species = {}
        self._last_fig_data = None      # {"kind","nu","per","total","trans","label","mode","meta"}
        self._overlay_count = 0          # 叠加次数（0=首次绘制会清空提示文字）
        self._overlay_data = []          # 所有叠加计算的数据（用于导出CSV）
        self._view_mode = "spectrum"     # 当前视图模式: spectrum / qcurve / xsc
        self._mix_rows = []             # [{"name","mole_frac"}]
        self._mix_unit = "摩尔分数"      # 混合气浓度输入单位：摩尔分数 / ppm / ppb
        self._prog = {"t0": 0.0, "done": 0, "total": 0}   # 进度/倒计时状态

        # 主题（深色/浅色），从首选项加载，默认深色
        self._theme = "dark"
        try:
            import json as _json
            _prefs_path = ROOT / "hitran_prefs.json"
            if _prefs_path.exists():
                _p = _json.loads(_prefs_path.read_text(encoding="utf-8"))
                if _p.get("theme") in ("dark", "light"):
                    self._theme = _p["theme"]
        except Exception:
            pass

        self._build_style()
        self._build_ui()
        self._load_prefs()               # 载入上次「首选项」（若有）
        self._on_mode_change()
        self._load_species()
        self.after(100, self._drain_queue)
        self._refresh_status()

    def _on_left_scroll(self, event):
        """全局鼠标滚轮回调：鼠标在左侧面板内时滚动左侧面板。"""
        try:
            x, y = self.winfo_pointerxy()
            widget = self.winfo_containing(x, y)
            if widget is not None:
                # 检查该控件是否在 left_cv 内
                w = widget
                while w is not None:
                    if w is self.left_cv:
                        self.left_cv.yview_scroll(int(-event.delta / 120), "units")
                        return
                    w = w.master
        except Exception:
            pass

    # ───────────────────────── UI 构建 ─────────────────────────

    @staticmethod
    def _get_colors(theme="dark"):
        """根据主题返回配色字典。浅色参考 iOS 系统语义色。"""
        if theme == "light":
            return {
                "BG": "#F2F2F7",        # iOS 系统背景
                "SURFACE": "#FFFFFF",    # 卡片/面板
                "SURFACE2": "#E5E5EA",   # 输入框/悬停
                "SURFACE3": "#D1D1D6",   # 按下/激活
                "ACCENT": "#007AFF",     # iOS 蓝
                "ACCENT_H": "#0A84FF",   # 悬停蓝
                "ACCENT_P": "#0056CC",   # 按下蓝
                "GREEN": "#34C759",      # iOS 绿
                "TEXT": "#000000",       # 主文本
                "TEXT_DIM": "#3C3C43",   # 次要文本（60%）
                "BORDER": "#C6C6C8",     # 分隔线
            }
        else:  # dark
            return {
                "BG": "#0F0F12",
                "SURFACE": "#1A1A1F",
                "SURFACE2": "#25252B",
                "SURFACE3": "#2F2F37",
                "ACCENT": "#6B8FD4",
                "ACCENT_H": "#8AAAE5",
                "ACCENT_P": "#5275B8",
                "GREEN": "#7BC47F",
                "TEXT": "#D8D8DE",
                "TEXT_DIM": "#8A8A92",
                "BORDER": "#2E2E35",
            }

    def _build_style(self):
        """iOS 风格深色主题：纯黑背景、大圆角、柔和层次、iOS 蓝强调色。"""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # 根据当前主题获取配色
        c = self._get_colors(self._theme)
        BG, SURFACE, SURFACE2, SURFACE3 = c["BG"], c["SURFACE"], c["SURFACE2"], c["SURFACE3"]
        ACCENT, ACCENT_H, ACCENT_P, GREEN = c["ACCENT"], c["ACCENT_H"], c["ACCENT_P"], c["GREEN"]
        TEXT, TEXT_DIM, BORDER = c["TEXT"], c["TEXT_DIM"], c["BORDER"]

        self._bg, self._surface, self._accent = BG, SURFACE, ACCENT
        self.configure(bg=BG)

        # 全局
        style.configure(".", background=BG, foreground=TEXT,
                        fieldbackground=SURFACE2, bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER,
                        font=("Microsoft YaHei", 10))

        # Frame / PanedWindow
        style.configure("TFrame", background=BG)
        style.configure("TPanedwindow", background=BG)

        # LabelFrame（卡片）- iOS 26 风格：柔和边框、充足内边距
        style.configure("TLabelframe", background=BG, bordercolor=BORDER,
                        relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=BG, foreground=TEXT_DIM,
                        font=("Microsoft YaHei", 11, "bold"), padding=(0, 0, 0, 8))

        # Label
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Dim.TLabel", background=BG, foreground=TEXT_DIM,
                        font=("Microsoft YaHei", 9))

        # 普通按钮 - iOS 26 风格：44pt 触控目标、大内边距、悬停高亮
        style.configure("TButton", background=SURFACE2, foreground=TEXT,
                        bordercolor=BORDER, focusthickness=0, padding=(16, 10),
                        font=("Microsoft YaHei", 10))
        style.map("TButton",
                  background=[("active", SURFACE2), ("pressed", SURFACE3)],
                  foreground=[("active", TEXT), ("pressed", TEXT_DIM)])

        # 主按钮（强调色）- iOS 风格：填充色、大圆角、白色文字
        style.configure("Accent.TButton", background=ACCENT, foreground="#D8D8DE",
                        bordercolor=ACCENT, padding=(16, 9),
                        font=("Microsoft YaHei", 10, "bold"))
        style.map("Accent.TButton",
                  background=[("active", ACCENT_H), ("pressed", ACCENT_P)],
                  foreground=[("active", "#D8D8DE")])

        # 危险按钮（停止）- iOS 红
        style.configure("Danger.TButton", background=SURFACE, foreground="#FF453A",
                        bordercolor=BORDER, padding=(14, 7),
                        font=("Microsoft YaHei", 10))
        style.map("Danger.TButton",
                  background=[("active", SURFACE2), ("pressed", SURFACE3)],
                  foreground=[("active", "#E07A7A"), ("pressed", "#D8D8DE")])

        # Entry - iOS 26 风格：大内边距、深灰背景
        style.configure("TEntry", fieldbackground=SURFACE2, foreground=TEXT,
                        insertcolor=TEXT, bordercolor=BORDER, padding=8)

        # Combobox - iOS 26 风格
        style.configure("TCombobox", fieldbackground=SURFACE2, foreground=TEXT,
                        background=SURFACE, arrowcolor=ACCENT, bordercolor=BORDER,
                        padding=8)
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE2),
                                                  ("active", SURFACE2)])

        # Notebook - iOS 26 风格：简洁标签、选中用深灰背景、大内边距
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG, foreground=TEXT_DIM,
                        padding=(20, 10), font=("Microsoft YaHei", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", SURFACE)],
                  foreground=[("selected", ACCENT)])

        # Treeview - iOS 26 风格：30pt 行高、柔和选中色、大内边距
        style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE,
                        foreground=TEXT, bordercolor=BORDER, rowheight=30)
        style.configure("Treeview.Heading", background=SURFACE2, foreground=TEXT_DIM,
                        font=("Microsoft YaHei", 9, "bold"), relief="flat", padding=(8, 6))
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#D8D8DE")])

        # Scrollbar - iOS 风格：细滚动条
        style.configure("Vertical.TScrollbar", background=SURFACE2, troughcolor=BG,
                        bordercolor=BG, arrowcolor=TEXT_DIM)
        style.configure("Horizontal.TScrollbar", background=SURFACE2, troughcolor=BG,
                        bordercolor=BG, arrowcolor=TEXT_DIM)

        # Checkbutton - iOS 风格
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)])

        # Progressbar - iOS 风格
        style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=SURFACE2,
                        bordercolor=BG, lightcolor=ACCENT, darkcolor=ACCENT)

        # matplotlib 柔和深色配色
        mpl.rcParams.update({
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "axes.edgecolor": BORDER,
            "axes.labelcolor": TEXT,
            "xtick.color": TEXT_DIM,
            "ytick.color": TEXT_DIM,
            "grid.color": BORDER,
            "grid.linestyle": "-",
            "grid.alpha": 0.4,
            "text.color": TEXT,
            "axes.titlecolor": TEXT,
            "legend.facecolor": SURFACE,
            "legend.edgecolor": BORDER,
            "legend.labelcolor": TEXT,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
        })

    def _style_toolbar(self):
        """matplotlib 工具栏（tk.Button）主题适配。"""
        c = self._get_colors(self._theme)
        self.toolbar_frame.configure(style="TFrame")
        for child in self.toolbar.winfo_children():
            if isinstance(child, tk.Button):
                child.configure(bg=c["SURFACE"], fg=c["ACCENT"],
                                activebackground=c["SURFACE2"], activeforeground=c["ACCENT_H"],
                                relief="flat", bd=0, padx=6, pady=3, highlightthickness=0,
                                cursor="hand2")
            elif isinstance(child, tk.Label):
                child.configure(bg="#1A1A1F", fg="#8A8A92")
        self.toolbar.configure(bg="#1A1A1F")

    def _build_ui(self):
        # ── 菜单栏 ──
        self._show_grid = True
        self._show_legend = True
        self._dark_theme = True
        menubar = tk.Menu(self)
        # 文件
        m_file = tk.Menu(menubar, tearoff=0)
        m_file.add_command(label="打开项目…", command=self._open_project, accelerator="Ctrl+O")
        m_file.add_command(label="保存项目…", command=self._save_project, accelerator="Ctrl+S")
        m_file.add_command(label="导入光谱数据…", command=self._import_spectrum)
        m_file.add_separator()
        m_file.add_command(label="退出", command=self._on_exit, accelerator="Alt+F4")
        menubar.add_cascade(label="文件", menu=m_file)
        # 编辑
        m_edit = tk.Menu(menubar, tearoff=0)
        m_edit.add_command(label="复制图像到剪贴板", command=self._copy_image)
        m_edit.add_command(label="复制数据到剪贴板", command=self._copy_data)
        m_edit.add_separator()
        m_edit.add_command(label="首选项…", command=self._show_preferences)
        menubar.add_cascade(label="编辑", menu=m_edit)
        # 视图
        m_view = tk.Menu(menubar, tearoff=0)
        self._var_grid = tk.BooleanVar(value=True)
        self._var_legend = tk.BooleanVar(value=True)
        self._var_theme = tk.StringVar(value=self._theme)
        m_view.add_checkbutton(label="显示网格", variable=self._var_grid, command=self._toggle_grid)
        m_view.add_checkbutton(label="显示图例", variable=self._var_legend, command=self._toggle_legend)
        m_view.add_separator()
        m_view.add_radiobutton(label="浅色模式", variable=self._var_theme, value="light", command=lambda: self._switch_theme("light"))
        m_view.add_radiobutton(label="深色模式", variable=self._var_theme, value="dark", command=lambda: self._switch_theme("dark"))
        menubar.add_cascade(label="视图", menu=m_view)
        # 工具
        m_tools = tk.Menu(menubar, tearoff=0)
        m_tools.add_command(label="波长 ↔ 波数换算器", command=self._show_converter)
        m_tools.add_command(label="HITRAN 分子表查询", command=self._show_molecule_table)
        m_tools.add_command(label="快捷键列表", command=self._show_shortcuts)
        m_tools.add_separator()
        m_tools.add_command(label="配置 API key…", command=self._show_api_key_config)
        m_tools.add_command(label="清理线表缓存…", command=self._clear_line_cache)
        menubar.add_cascade(label="工具", menu=m_tools)
        # 帮助
        m_help = tk.Menu(menubar, tearoff=0)
        m_help.add_command(label="使用说明", command=self._show_help)
        m_help.add_command(label="检查更新", command=self._check_update)
        m_help.add_separator()
        m_help.add_command(label="关于 HitranLab", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=m_help)
        self.config(menu=menubar)
        # 快捷键
        self.bind("<Control-s>", lambda e: self._save_project())
        self.bind("<Control-o>", lambda e: self._open_project())

        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        # ── 左：参数面板（可滚动） ──
        left = ttk.Frame(main, width=340)
        left.pack_propagate(False)
        main.add(left, weight=0)
        self.left_cv = tk.Canvas(left, width=340, highlightthickness=0, bg=self._bg)
        left_vsb = ttk.Scrollbar(left, orient="vertical", command=self.left_cv.yview)
        self.left_cv.configure(yscrollcommand=left_vsb.set)
        self.left_cv.pack(side="left", fill="both", expand=True)
        left_vsb.pack(side="right", fill="y")
        inner = ttk.Frame(self.left_cv)
        _win = self.left_cv.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: self.left_cv.configure(scrollregion=self.left_cv.bbox("all")))
        self.left_cv.bind("<Configure>", lambda e: self.left_cv.itemconfigure(_win, width=e.width))
        # 全局鼠标滚轮绑定（子控件也能触发，判断鼠标是否在左侧面板内）
        self.bind_all("<MouseWheel>", self._on_left_scroll)

        # 分子与窗口
        f0 = ttk.LabelFrame(inner, text="分子与波段", padding=8)
        f0.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f0, text="分子:").grid(row=0, column=0, sticky="w")
        self.mol_var = tk.StringVar()
        self.mol_cb = ttk.Combobox(f0, textvariable=self.mol_var, width=20)
        self.mol_cb.bind("<KeyRelease>", self._on_mol_search)
        self.mol_cb.bind("<Return>", self._on_mol_enter)
        self.mol_cb.grid(row=0, column=1, sticky="we", padx=(4, 0))
        self.mol_cb.bind("<MouseWheel>", lambda e: "break")
        ttk.Label(f0, text="窗口 ν (cm⁻¹):").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.numin_var, self.numax_var = tk.StringVar(value="2962.0"), tk.StringVar(value="2969.0")
        self.step_var = tk.StringVar(value="0.01")
        nu_frame = ttk.Frame(f0)
        nu_frame.grid(row=1, column=1, columnspan=3, sticky="w", padx=(4, 0), pady=(4, 0))
        ttk.Entry(nu_frame, textvariable=self.numin_var, width=8).pack(side="left")
        ttk.Label(nu_frame, text="—", foreground="#8A8A92").pack(side="left", padx=4)
        ttk.Entry(nu_frame, textvariable=self.numax_var, width=8).pack(side="left")
        ttk.Label(f0, text="步长:").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(f0, textvariable=self.step_var, width=8).grid(row=2, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        ttk.Label(f0, text="同位素:").grid(row=3, column=0, sticky="w", pady=(4, 0))
        self.iso_var = tk.StringVar(value="主同位素")
        self.iso_cb = ttk.Combobox(f0, textvariable=self.iso_var, width=20, state="readonly")
        self.iso_cb.grid(row=3, column=1, columnspan=3, sticky="we", padx=(4, 0), pady=(4, 0))
        self.iso_cb.bind("<MouseWheel>", lambda e: "break")
        self.mol_cb.bind("<<ComboboxSelected>>", lambda e: self._load_isotopologues())
        f0.columnconfigure(1, weight=1)

        # 工况
        f1 = ttk.LabelFrame(inner, text="工况", padding=8)
        f1.pack(fill=tk.X, pady=(0, 6))
        self.T_var = tk.StringVar(value="296.0")
        self.P_var = tk.StringVar(value="1.0")
        self.L_var = tk.StringVar(value="100.0")     # 光程 cm（透过率用）
        ttk.Label(f1, text="温度 T (K):").grid(row=0, column=0, sticky="w")
        ttk.Entry(f1, textvariable=self.T_var, width=10).grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Label(f1, text="压力 P (atm):").grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(f1, textvariable=self.P_var, width=10).grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        ttk.Label(f1, text="光程 L (cm):").grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.L_entry = ttk.Entry(f1, textvariable=self.L_var, width=10)
        self.L_entry.grid(row=2, column=1, sticky="w", padx=(4, 0), pady=(4, 0))

        # 计算选项
        f2 = ttk.LabelFrame(inner, text="计算选项", padding=8)
        f2.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f2, text="输出:").grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value="吸收系数 α (cm⁻¹)")
        self.mode_cb = ttk.Combobox(f2, textvariable=self.mode_var, values=list(MODES), width=20, state="readonly")
        self.mode_cb.grid(row=0, column=1, padx=(4, 0))
        self.mode_cb.bind("<MouseWheel>", lambda e: "break")
        self.mode_cb.bind("<<ComboboxSelected>>", lambda e: self._on_mode_change())
        ttk.Label(f2, text="线型:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.profile_var = tk.StringVar(value="voigt")
        self.profile_cb = ttk.Combobox(f2, textvariable=self.profile_var, values=PROFILES, width=20, state="readonly")
        self.profile_cb.grid(row=1, column=1, padx=(4, 0), pady=(4, 0))
        self.profile_cb.bind("<MouseWheel>", lambda e: "break")
        self.ylog_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f2, text="对数坐标", variable=self.ylog_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(f2, text="翼宽 (cm⁻¹):").grid(row=3, column=0, sticky="w", pady=(4, 0))
        self.winghw_var = tk.StringVar(value="50.0")
        ttk.Entry(f2, textvariable=self.winghw_var, width=10).grid(row=3, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        ttk.Label(f2, text="强度截断:").grid(row=4, column=0, sticky="w", pady=(4, 0))
        self.cutoff_var = tk.StringVar(value="")
        ttk.Entry(f2, textvariable=self.cutoff_var, width=10).grid(row=4, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        ttk.Label(f2, text="(单位 cm/molecule，如 1e-26；空=不截断)",
                  foreground="#8A8A92").grid(row=5, column=0, columnspan=2, sticky="w")

        # 高级选项
        f2b = ttk.LabelFrame(inner, text="辅助功能参数", padding=8)
        f2b.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f2b, text="强线数:").grid(row=0, column=0, sticky="w")
        self.topn_var = tk.StringVar(value="15")
        ttk.Entry(f2b, textvariable=self.topn_var, width=8).grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Label(f2b, text="Q(T) 温度范围:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        qframe = ttk.Frame(f2b)
        qframe.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        self.qtmin_var = tk.StringVar(value="200")
        self.qtmax_var = tk.StringVar(value="400")
        self.qtstep_var = tk.StringVar(value="20")
        ttk.Entry(qframe, textvariable=self.qtmin_var, width=6).pack(side="left")
        ttk.Label(qframe, text="–", foreground="#8A8A92").pack(side="left", padx=2)
        ttk.Entry(qframe, textvariable=self.qtmax_var, width=6).pack(side="left")
        ttk.Label(qframe, text="K  步长", foreground="#8A8A92").pack(side="left", padx=(4, 2))
        ttk.Entry(qframe, textvariable=self.qtstep_var, width=5).pack(side="left")

        # 混合气
        f3 = ttk.LabelFrame(inner, text="混合气（浓度留空=纯气体，总和可<1，不可>1）", padding=8)
        f3.pack(fill=tk.X, pady=(0, 6))
        mix_frame = ttk.Frame(f3)
        mix_frame.grid(row=0, column=0, columnspan=3, sticky="we")
        self.mix_tree = ttk.Treeview(mix_frame, columns=("name", "x"), show="headings", height=5)
        self.mix_tree.heading("name", text="分子"); self.mix_tree.column("name", width=120)
        self.mix_tree.heading("x", text="浓度"); self.mix_tree.column("x", width=110)
        self.mix_tree.pack(side="left", fill="both", expand=True)
        mix_vsb = ttk.Scrollbar(mix_frame, orient="vertical", command=self.mix_tree.yview)
        mix_vsb.pack(side="right", fill="y")
        self.mix_tree.configure(yscrollcommand=mix_vsb.set)
        self.frac_var = tk.StringVar(value="")
        frac_input = ttk.Frame(f3)
        frac_input.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.frac_var_entry = ttk.Entry(frac_input, textvariable=self.frac_var, width=10)
        self.frac_var_entry.pack(side="left")
        self.mix_unit_var = tk.StringVar(value="摩尔分数")
        self.mix_unit_cb = ttk.Combobox(frac_input, textvariable=self.mix_unit_var,
                                         values=["摩尔分数", "ppm", "ppb"], width=8, state="readonly")
        self.mix_unit_cb.pack(side="left", padx=(4, 0))
        self.mix_unit_cb.bind("<<ComboboxSelected>>", self._on_mix_unit_change)
        ttk.Button(f3, text="添加组分", command=self._add_mix).grid(row=1, column=1, padx=(4, 0), pady=(4, 0))
        ttk.Button(f3, text="删除选中", command=self._del_mix).grid(row=1, column=2, padx=(4, 0), pady=(4, 0))
        self.mix_sum_var = tk.StringVar(value="总和: 0")
        self.mix_sum_label = ttk.Label(f3, textvariable=self.mix_sum_var, foreground="#8A8A92")
        self.mix_sum_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        f3.columnconfigure(0, weight=1)

        # 动作按钮
        fb = ttk.Frame(inner)
        fb.pack(fill=tk.X, pady=(0, 6))
        self.btn_compute = RoundedButton(fb, text="▶  计算并绘图", command=self._compute_and_plot,
                                          bg="#6B8FD4", hover_bg="#8AAAE5", height=46, radius=10)
        self.btn_compute.pack(fill=tk.X, pady=(0, 6))
        self.btn_stop = RoundedButton(fb, text="■  停止计算", command=self._stop_compute,
                                       bg="#1A1A1F", fg="#E07A7A", hover_bg="#25252B",
                                       disabled_bg="#1A1A1F", disabled_fg="#5A5A62",
                                       height=40, radius=8, font=("Microsoft YaHei", 10))
        self.btn_stop.pack(fill=tk.X, pady=(0, 6))
        self.btn_stop.configure(state="disabled")
        fbg = ttk.Frame(fb)
        fbg.pack(fill=tk.X)
        acts = [("强线列表", self._lines), ("配分函数", self._partition),
                ("Q(T) 曲线", self._qcurve), ("导出 CSV", self._export_csv),
                ("导出 PNG", self._export_png), ("截面文件", self._pick_xsc),
                ("清空图", self._clear_plot), ("重置参数", self._reset_params)]
        for i, (txt, cmd) in enumerate(acts):
            ttk.Button(fbg, text=txt, command=cmd).grid(row=i // 2, column=i % 2,
                                                        sticky="we", padx=2, pady=2)
        fbg.columnconfigure(0, weight=1); fbg.columnconfigure(1, weight=1)

        # 截面导入
        f4 = ttk.LabelFrame(inner, text="截面文件 (HOTW)", padding=8)
        f4.pack(fill=tk.X, pady=(0, 6))
        self.xsc_var = tk.StringVar()
        ttk.Entry(f4, textvariable=self.xsc_var).pack(fill=tk.X)
        xr = ttk.Frame(f4)
        xr.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(xr, text="浏览…", command=self._pick_xsc).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ttk.Button(xr, text="导入并绘图", command=self._import_xsc).pack(side="left", fill="x", expand=True, padx=(2, 0))

        # ── 右：图谱 + 数据页 ──
        right = ttk.Frame(main)
        main.add(right, weight=1)

        self.fig = Figure(figsize=(9, 4.4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_xlabel("Wavenumber (cm$^{-1}$)")
        self.ax.set_ylabel("Absorption coefficient α (cm$^{-1}$)")
        self.ax.grid(alpha=0.4, lw=0.6)
        self.ax.text(0.5, 0.5, "设置参数后点击「计算并绘图」", ha="center", va="center",
                     transform=self.ax.transAxes, color="#8A8A92", fontsize=13)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().configure(bg=self._bg)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=(0, 0), pady=(0, 2))
        # 交互式数据探查：鼠标悬停显示精确波数/吸收系数
        self.canvas.mpl_connect("motion_notify_event", self._on_mouse_hover)
        self._hover_last_status = None  # 记录悬停前的状态栏文本，鼠标离开后恢复

        # matplotlib 导航工具栏（缩放/平移/取点/保存）
        self.toolbar_frame = ttk.Frame(right)
        self.toolbar_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 4))
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame)
        self.toolbar.update()
        self._style_toolbar()

        self.nb = ttk.Notebook(right)
        self.nb.pack(fill=tk.BOTH, expand=True)
        # 图层管理（曲线列表，可删除单条）
        self.layer_tab = ttk.Frame(self.nb)
        self.nb.add(self.layer_tab, text="图层管理")
        layer_top = ttk.Frame(self.layer_tab)
        layer_top.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(layer_top, text="已绘制曲线（双击或选中后点删除）：").pack(side="left")
        self.layer_list = tk.Listbox(self.layer_tab, font=("Consolas", 9),
                                      bg="#1A1A1F", fg="#D8D8DE", selectbackground="#6B8FD4",
                                      selectforeground="#FFFFFF", relief="flat", borderwidth=0,
                                      activestyle="none")
        self.layer_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))
        self.layer_list.bind("<Double-Button-1>", lambda e: self._remove_layer())
        layer_btn = ttk.Frame(self.layer_tab)
        layer_btn.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(layer_btn, text="删除选中", command=self._remove_layer).pack(side="left")
        ttk.Button(layer_btn, text="清空全部", command=self._clear_plot).pack(side="left", padx=(8, 0))
        # 峰统计
        self.peak_tab = ttk.Frame(self.nb)
        self.nb.add(self.peak_tab, text="峰 / 统计")
        peak_frame = ttk.Frame(self.peak_tab)
        peak_frame.pack(fill=tk.BOTH, expand=True)
        self.peak_text = tk.Text(peak_frame, height=7, font=("Consolas", 10),
                                  bg="#1A1A1F", fg="#D8D8DE", insertbackground="#D8D8DE",
                                  relief="flat", borderwidth=0, padx=8, pady=6)
        self.peak_text.pack(side="left", fill=tk.BOTH, expand=True)
        peak_vsb = ttk.Scrollbar(peak_frame, orient="vertical", command=self.peak_text.yview)
        peak_vsb.pack(side="right", fill="y")
        self.peak_text.configure(yscrollcommand=peak_vsb.set)
        self.peak_text.insert("1.0", "计算后显示峰值、窗口积分和警告信息。")
        # 强线
        self.line_tab = ttk.Frame(self.nb)
        self.nb.add(self.line_tab, text="强线列表")
        line_frame = ttk.Frame(self.line_tab)
        line_frame.pack(fill=tk.BOTH, expand=True)
        self.line_tree = ttk.Treeview(line_frame, columns=("mol", "nu", "S", "gair", "E"), show="headings", height=7)
        for c, t, w in (("mol", "分子", 70), ("nu", "ν (cm⁻¹)", 110), ("S", "S (cm/molecule)", 130),
                        ("gair", "γ_air", 90), ("E", "E″ (cm⁻¹)", 100)):
            self.line_tree.heading(c, text=t); self.line_tree.column(c, width=w)
        self.line_tree.pack(side="left", fill=tk.BOTH, expand=True)
        line_vsb = ttk.Scrollbar(line_frame, orient="vertical", command=self.line_tree.yview)
        line_vsb.pack(side="right", fill="y")
        self.line_tree.configure(yscrollcommand=line_vsb.set)
        line_btn = ttk.Frame(self.line_tab)
        line_btn.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(line_btn, text="导出完整线表 CSV", command=self._export_lines).pack(side="left")
        # 截面
        self.xsc_tab = ttk.Frame(self.nb)
        self.nb.add(self.xsc_tab, text="截面文件信息")
        xsc_frame = ttk.Frame(self.xsc_tab)
        xsc_frame.pack(fill=tk.BOTH, expand=True)
        self.xsc_text = tk.Text(xsc_frame, height=7, font=("Consolas", 10),
                                 bg="#1A1A1F", fg="#D8D8DE", insertbackground="#D8D8DE",
                                 relief="flat", borderwidth=0, padx=8, pady=6)
        self.xsc_text.pack(side="left", fill=tk.BOTH, expand=True)
        xsc_vsb = ttk.Scrollbar(xsc_frame, orient="vertical", command=self.xsc_text.yview)
        xsc_vsb.pack(side="right", fill="y")
        self.xsc_text.configure(yscrollcommand=xsc_vsb.set)
        self.xsc_text.insert("1.0", "导入截面文件（HOTW）后显示分子、波段、温度、压力等信息。")
        # 状态
        self.stat_tab = ttk.Frame(self.nb)
        self.nb.add(self.stat_tab, text="运行状态")
        stat_frame = ttk.Frame(self.stat_tab)
        stat_frame.pack(fill=tk.BOTH, expand=True)
        self.stat_text = tk.Text(stat_frame, height=7, font=("Consolas", 10),
                                  bg="#1A1A1F", fg="#D8D8DE", insertbackground="#D8D8DE",
                                  relief="flat", borderwidth=0, padx=8, pady=6)
        self.stat_text.pack(side="left", fill=tk.BOTH, expand=True)
        stat_vsb = ttk.Scrollbar(stat_frame, orient="vertical", command=self.stat_text.yview)
        stat_vsb.pack(side="right", fill="y")
        self.stat_text.configure(yscrollcommand=stat_vsb.set)
        self.stat_text.insert("1.0", "显示计算日志、线表下载状态和引擎警告。\n\n"
                                     "四个标签页用途：\n"
                                     "  峰/统计 — 计算后自动显示峰值、积分、警告\n"
                                     "  强线列表 — 点左侧「强线列表」后显示最强谱线\n"
                                     "  截面文件信息 — 导入 HOTW 截面文件后显示元数据\n"
                                     "  运行状态 — 计算日志和引擎状态")
        stat_btn = ttk.Frame(self.stat_tab)
        stat_btn.pack(fill=tk.X, padx=8, pady=(4, 8))
        ttk.Button(stat_btn, text="刷新状态", command=self._refresh_status).pack(side="left")

        # 底部状态栏（文字 + 进度条）
        sb = ttk.Frame(self)
        sb.pack(fill=tk.X, padx=10, pady=(0, 6))
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(sb, textvariable=self.status_var, anchor="w",
                                       style="Dim.TLabel")
        self.status_label.pack(side="left", fill=tk.X, expand=True)
        # 确定性进度条（原先 indeterminate 只会在两端来回滑动，看不出真实进度）
        self.progress = ttk.Progressbar(sb, mode="determinate", maximum=100, value=0, length=180)
        self.progress.pack(side="right", padx=(8, 0))
        self.eta_var = tk.StringVar(value="")
        ttk.Label(sb, textvariable=self.eta_var, style="Dim.TLabel").pack(side="right", padx=(0, 6))

        # 阻止 Combobox 鼠标滚轮误触改变选项
        def _cb_wheel(e):
            return "break"
        for w in self.winfo_children():
            for child in w.winfo_children():
                if isinstance(child, ttk.Combobox):
                    child.bind("<MouseWheel>", _cb_wheel)
                for sub in child.winfo_children():
                    if isinstance(sub, ttk.Combobox):
                        sub.bind("<MouseWheel>", _cb_wheel)

    # ───────────────────────── 数据加载 ─────────────────────────
    def _on_mol_search(self, event=None):
        """用户输入分子名时实时筛选下拉列表，并自动匹配别名。"""
        text = self.mol_var.get().strip()
        if not text:
            # 清空输入时恢复完整列表
            if hasattr(self, "_all_species"):
                self.mol_cb["values"] = self._all_species
            return
        # 先尝试别名匹配
        std, matched = resolve_molecule_alias(text)
        if matched and std in (self._all_species if hasattr(self, "_all_species") else []):
            # 匹配到别名且在分子表中，自动替换
            self.mol_var.set(std)
            self._load_isotopologues()
            return
        # 筛选包含输入文本的分子（不区分大小写）
        if hasattr(self, "_all_species"):
            filtered = [m for m in self._all_species if text.upper() in m]
            self.mol_cb["values"] = filtered
            if filtered:
                self.mol_cb.event_generate("<Down>")  # 展开下拉

    def _on_mol_enter(self, event=None):
        """回车时确认分子选择，加载同位素。"""
        text = self.mol_var.get().strip()
        if not text:
            return
        std, matched = resolve_molecule_alias(text)
        if std in (self._all_species if hasattr(self, "_all_species") else []):
            self.mol_var.set(std)
            self._load_isotopologues()
        else:
            # 不在分子表中，恢复完整列表
            if hasattr(self, "_all_species"):
                self.mol_cb["values"] = self._all_species

    def _load_species(self):
        def job():
            s = hm.t_species()["species"]
            return {"kind": "species", "data": {f: {"M": e["M"], "main_iso": e.get("main_iso", 1)} for f, e in s.items()}}
        self.status_var.set("加载官方分子表…")
        self.worker.run(job)

    def _load_isotopologues(self):
        """分子改变时加载该分子的同位素列表。默认选所有同位素（自然丰度）。"""
        name = self.mol_var.get().strip()
        if not name:
            self.iso_cb["values"] = []
            self.iso_var.set("")
            return
        try:
            info = hm.t_species(name, with_isotopologues=True)
            isos = info.get("isotopologues", [])
            labels = ["所有同位素（自然丰度）"]
            self._iso_map = {"所有同位素（自然丰度）": "all"}
            for iso in isos:
                label = f"{iso['name']} ({iso['abundance']*100:.2f}%)"
                labels.append(label)
                self._iso_map[label] = iso["I"]
            self.iso_cb["values"] = labels
            self.iso_var.set("所有同位素（自然丰度）")  # 默认所有同位素
        except Exception as e:
            self.iso_cb["values"] = []
            self.iso_var.set("")

    # ───────────────────────── 交互 ─────────────────────────
    def _frac_to_display(self, xf):
        """摩尔分数 -> 当前单位显示值。"""
        if xf is None:
            return "1 (纯)"
        unit = self.mix_unit_var.get()
        if unit == "ppm":
            return f"{xf * 1e6:.4g} ppm"
        elif unit == "ppb":
            return f"{xf * 1e9:.4g} ppb"
        return f"{xf:.6g}"

    def _display_to_frac(self, val_str):
        """当前单位输入值 -> 摩尔分数。返回 (xf, error_msg)。"""
        s = str(val_str).strip()
        if not s:
            return None, None
        try:
            v = float(s)
        except ValueError:
            return None, "浓度需为数字"
        unit = self.mix_unit_var.get()
        if unit == "ppm":
            xf = v / 1e6
        elif unit == "ppb":
            xf = v / 1e9
        else:
            xf = v
        if not (0 < xf <= 1):
            if unit == "ppm":
                return None, f"ppm 需在 (0, 1e6] 区间（当前 {v:g}）"
            elif unit == "ppb":
                return None, f"ppb 需在 (0, 1e9] 区间（当前 {v:g}）"
            return None, "摩尔分数需在 (0,1] 区间"
        return xf, None

    def _on_mix_unit_change(self, event=None):
        """单位切换时刷新表格所有行的显示值，并保存到首选项。"""
        self._mix_unit = self.mix_unit_var.get()
        # 保存到首选项（读-改-写，不影响其他键）
        try:
            import json as _json
            _merged = {}
            if PREFS_PATH.exists():
                try:
                    _merged = _json.loads(PREFS_PATH.read_text(encoding="utf-8"))
                except Exception:
                    pass
            _merged["mix_unit"] = self._mix_unit
            PREFS_PATH.write_text(_json.dumps(_merged, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass  # 保存失败不影响单位切换功能
        # 刷新表格显示（内部值通过 _params 时重新转换）
        for item in self.mix_tree.get_children():
            vals = self.mix_tree.item(item, "values")
            name = vals[0]
            # 从显示值解析回摩尔分数（尝试所有单位），再按新单位显示
            old_display = str(vals[1])
            xf = self._parse_any_frac(old_display)
            self.mix_tree.item(item, values=(name, self._frac_to_display(xf)))
        self._update_mix_sum()

    def _parse_any_frac(self, display_str):
        """从任意单位的显示字符串解析摩尔分数（用于单位切换时的转换）。"""
        s = str(display_str).strip()
        if "纯" in s:
            return None
        # 根据后缀判断单位
        unit = "摩尔分数"
        for suffix, u in [(" ppb", "ppb"), (" ppm", "ppm"), ("ppb", "ppb"), ("ppm", "ppm")]:
            if s.endswith(suffix):
                s = s[: -len(suffix)].strip()
                unit = u
                break
        try:
            v = float(s)
        except ValueError:
            try:
                return float(display_str)
            except ValueError:
                return 1.0
        # 按单位转换
        if unit == "ppm":
            return v / 1e6
        elif unit == "ppb":
            return v / 1e9
        # 无后缀：如果值 > 1，大概率是 ppm（旧格式兼容）
        if v > 1:
            if v > 1e4:
                return v / 1e9
            else:
                return v / 1e6
        return v

    def _update_mix_sum(self):
        """计算并显示所有组分的摩尔分数总和。"""
        total = 0.0
        for item in self.mix_tree.get_children():
            vals = self.mix_tree.item(item, "values")
            display_str = str(vals[1]) if vals[1] else ""
            if display_str and "纯" not in display_str:
                xf = self._parse_any_frac(display_str)
                if xf and 0 < xf <= 1:
                    total += xf
        unit = self.mix_unit_var.get()
        if unit == "ppm":
            self.mix_sum_var.set(f"总和: {total * 1e6:.4g} ppm（{total * 100:.4f}%）")
        elif unit == "ppb":
            self.mix_sum_var.set(f"总和: {total * 1e9:.4g} ppb（{total * 100:.4f}%）")
        else:
            self.mix_sum_var.set(f"总和: {total:.6g}（{total * 100:.4f}%）")
        # 总和 > 1 时红色警告
        if total > 1.0 + 1e-9:
            self.mix_sum_label.configure(foreground="#E07A7A")
        else:
            self.mix_sum_label.configure(foreground="#8A8A92")

    def _add_mix(self):
        name = self.mol_var.get().strip().upper()
        if not name:
            messagebox.showwarning("HitranLab", "请先选择分子")
            return
        x = self.frac_var.get().strip()
        xf, err = self._display_to_frac(x)
        if err:
            messagebox.showwarning("HitranLab", f"{err}，或留空（纯气体）")
            return
        # 总和校验：添加后总和不可 > 1
        current_total = 0.0
        for item in self.mix_tree.get_children():
            vals = self.mix_tree.item(item, "values")
            ds = str(vals[1]) if vals[1] else ""
            if ds and "纯" not in ds:
                x = self._parse_any_frac(ds)
                if x and 0 < x <= 1:
                    current_total += x
        if xf is not None and current_total + xf > 1.0 + 1e-9:
            messagebox.showwarning("HitranLab",
                f"添加后摩尔分数总和将为 {current_total + xf:.4g}（>1），物理上不可能。\n"
                f"当前总和: {current_total:.4g}，待添加: {xf:.4g}\n"
                f"请减少各组分浓度，或删除部分组分。")
            return
        self.mix_tree.insert("", "end", values=(name, self._frac_to_display(xf)))
        self.frac_var.set("")
        self._update_mix_sum()

    def _del_mix(self):
        sel = self.mix_tree.selection()
        for i in sel:
            self.mix_tree.delete(i)
        self._update_mix_sum()

    def _on_mouse_hover(self, event):
        """鼠标悬停在谱图上时，在状态栏显示精确波数和吸收系数/透过率。"""
        if event.inaxes != self.ax or not self._overlay_data:
            # 鼠标离开 axes 或无数据时，恢复之前的状态栏
            if self._hover_last_status is not None:
                self.status_var.set(self._hover_last_status)
                self._hover_last_status = None
            return
        # 记录当前状态栏（仅记录一次，避免被悬停文本覆盖后无法恢复）
        if self._hover_last_status is None:
            self._hover_last_status = self.status_var.get()
        try:
            x = float(event.xdata)
            # 遍历所有图层，找到最近的数据点
            parts = []
            for ds in self._overlay_data:
                tag = ds["tag"]
                res = ds["data"]["res"]
                nu = res["nu"]
                # 确定 y 数据：透过率模式用 trans，否则用 total 或单组分
                if res.get("trans") is not None:
                    ydata = res["trans"]
                    unit = "T"
                elif len(res["per"]) > 1 and res.get("total") is not None:
                    ydata = res["total"]
                    unit = "α"
                else:
                    ydata = list(res["per"].values())[0]
                    unit = "α"
                # 找到最近的索引
                idx = int(np.argmin(np.abs(nu - x)))
                if 0 <= idx < len(ydata):
                    y_val = float(ydata[idx])
                    if unit == "T":
                        parts.append(f"{tag}: ν={nu[idx]:.4f} cm⁻¹, T={y_val:.6f}")
                    else:
                        # 吸收系数用科学计数法
                        parts.append(f"{tag}: ν={nu[idx]:.4f} cm⁻¹, α={y_val:.4e} cm⁻¹")
            if parts:
                self.status_var.set(" | ".join(parts))
        except Exception:
            pass  # 悬停探查失败不影响其他功能

    def _clear_plot(self):
        """只清空画布，不改变参数。重置叠加计数器和数据。"""
        self._overlay_count = 0
        self._overlay_data = []
        self._view_mode = "spectrum"  # 当前视图模式: spectrum / qcurve / xsc
        self._last_fig_data = None
        self._last_lines_data = None      # 与已清空的强线列表保持一致，避免"清空后仍能导出上一轮线表"
        self.ax.clear()
        self.ax.set_xlabel("Wavenumber (cm$^{-1}$)")
        self.ax.set_ylabel("Absorption coefficient α (cm$^{-1}$)")
        self.ax.grid(alpha=0.4, lw=0.6)
        self.ax.text(0.5, 0.5, "设置参数后点击「计算并绘图」", ha="center", va="center",
                     transform=self.ax.transAxes, color="#8A8A92", fontsize=13)
        self.fig.tight_layout()
        self.canvas.draw()
        # 清空峰统计和强线列表
        if hasattr(self, "peak_text"):
            self.peak_text.delete("1.0", tk.END)
            self.peak_text.insert("1.0", "（清空画布后无数据）")
        if hasattr(self, "line_tree"):
            self.line_tree.delete(*self.line_tree.get_children())
        self._refresh_layers()
        self.status_var.set("画布已清空")

    def _refresh_layers(self):
        """刷新图层管理列表。"""
        if not hasattr(self, "layer_list"):
            return
        self.layer_list.delete(0, tk.END)
        for i, ds in enumerate(self._overlay_data):
            self.layer_list.insert(tk.END, f"[{i+1}] {ds['tag']}")

    def _remove_layer(self):
        """删除选中的图层，重新绘制剩余曲线。"""
        if not hasattr(self, "layer_list"):
            return
        if self._view_mode != "spectrum":
            messagebox.showinfo("HitranLab", "当前为 Q(T) / 截面视图，请先「计算并绘图」或「清空图」返回谱线视图")
            return
        sel = self.layer_list.curselection()
        if not sel:
            messagebox.showinfo("HitranLab", "请先在图层列表中选择一条曲线")
            return
        idx = sel[0]
        if idx >= len(self._overlay_data):
            return
        del self._overlay_data[idx]
        # 重新绘制所有剩余图层
        self.ax.clear()
        self._overlay_count = 0
        if not self._overlay_data:
            # 没有剩余图层，显示提示文字
            self.ax.set_xlabel("Wavenumber (cm$^{-1}$)")
            self.ax.set_ylabel("Absorption coefficient α (cm$^{-1}$)")
            self.ax.grid(alpha=0.4, lw=0.6)
            self.ax.text(0.5, 0.5, "设置参数后点击「计算并绘图」", ha="center", va="center",
                         transform=self.ax.transAxes, color="#8A8A92", fontsize=13)
            self.fig.tight_layout()
            self.canvas.draw()
            self._refresh_layers()
            self.status_var.set("已删除选中图层")
            return
        # 逐个重绘剩余图层
        saved_data = list(self._overlay_data)
        self._overlay_data = []
        for ds in saved_data:
            if ds["data"].get("kind") == "linestrength":
                self._render_linestrength(ds["data"])
            else:
                self._render_spectrum(ds["data"])
        self.status_var.set(f"已删除选中图层，剩余 {len(self._overlay_data)} 条")

    def _reset_params(self):
        self.mol_var.set("CH4")
        self._load_isotopologues()
        self.numin_var.set("2962.0")
        self.numax_var.set("2969.0")
        self.step_var.set("0.01")
        self.T_var.set("296.0")
        self.P_var.set("1.0")
        self.L_var.set("100.0")
        self.mode_var.set("吸收系数 α (cm⁻¹)")
        self.profile_var.set("voigt")
        self.ylog_var.set(False)
        self.winghw_var.set("50.0")
        self.cutoff_var.set("")
        self.topn_var.set("15")
        self.qtmin_var.set("200")
        self.qtmax_var.set("400")
        self.qtstep_var.set("20")
        self.frac_var.set("")
        for it in self.mix_tree.get_children():
            self.mix_tree.delete(it)
        self.mix_unit_var.set("摩尔分数")  # 重置单位为默认
        self._update_mix_sum()              # 更新总和显示为 0
        self._overlay_count = 0
        self._overlay_data = []
        self._view_mode = "spectrum"  # 当前视图模式: spectrum / qcurve / xsc
        self._last_fig_data = None
        self.ax.clear()
        self.ax.set_xlabel("Wavenumber (cm$^{-1}$)")
        self.ax.set_ylabel("Absorption coefficient α (cm$^{-1}$)")
        self.ax.grid(alpha=0.4, lw=0.6)
        self.ax.text(0.5, 0.5, "设置参数后点击「计算并绘图」", ha="center", va="center",
                     transform=self.ax.transAxes, color="#8A8A92", fontsize=13)
        self.canvas.draw()
        self._last_fig_data = None
        self._last_lines_data = None
        self._on_mode_change()  # 更新光程/摩尔分数启用状态
        self.status_var.set("参数已重置")

    def _pick_xsc(self):
        p = filedialog.askopenfilename(
            title="选择 HITRAN 截面文件", filetypes=[("HOTW 文本", "*.txt"), ("所有文件", "*.*")])
        if p:
            self.xsc_var.set(p)

    def _get_mix(self):
        rows = []
        for it in self.mix_tree.get_children():
            v = self.mix_tree.item(it, "values")
            display_str = str(v[1]) if v[1] else ""
            if display_str and "纯" not in display_str:
                xf = self._parse_any_frac(display_str)
                if xf <= 0 or xf > 1:
                    raise ValueError(f"混合气浓度非法: {display_str!r}（转换后摩尔分数 {xf} 不在 (0,1]）")
            else:
                xf = None
            rows.append({"name": str(v[0]).strip().upper(), "mole_frac": xf})
        return rows

    def _selected_iso(self):
        """返回当前选中的同位素：'all'=所有同位素(自然丰度)，int=指定同位素，None=主同位素。"""
        label = self.iso_var.get().strip()
        if not label:
            return None
        if hasattr(self, "_iso_map") and label in self._iso_map:
            val = self._iso_map[label]
            return val if val == "all" else int(val)
        return None

    def _params(self):
        """读取参数面板 -> (specs, numin, numax, T, P, step, mode, profile, L, ylog, hitran_units)。"""
        def f(v, label):
            try:
                return float(v)
            except ValueError:
                raise ValueError(f"{label} 非法: {v!r}")
        name = self.mol_var.get().strip().upper()
        if not name:
            raise ValueError("请选择分子")
        numin, numax, step = f(self.numin_var.get(), "numin"), f(self.numax_var.get(), "numax"), f(self.step_var.get(), "step")
        if numin >= numax:
            raise ValueError("窗口非法: numin ≥ numax")
        if step <= 0:
            raise ValueError("步长必须 > 0")
        T, P = f(self.T_var.get(), "T"), f(self.P_var.get(), "P")
        if T <= 0:
            raise ValueError("温度 T 必须 > 0 K")
        if P <= 0:
            raise ValueError("压力 P 必须 > 0 atm")
        L = f(self.L_var.get(), "光程")
        mode = MODES.get(self.mode_var.get(), "alpha")
        if mode == "transmittance" and L <= 0:
            raise ValueError("光程 L 必须 > 0 cm")
        profile = self.profile_var.get()
        ylog = self.ylog_var.get()
        hitran_units = mode == "sigma"
        wingHW = f(self.winghw_var.get(), "wingHW")
        if wingHW <= 0:
            raise ValueError("翼宽必须 > 0 cm⁻¹")
        cutoff_str = self.cutoff_var.get().strip()
        intensity_cutoff = float(cutoff_str) if cutoff_str else None
        if intensity_cutoff is not None and intensity_cutoff < 0:
            raise ValueError("强度截断必须 >= 0")
        rows = self._get_mix()
        if rows:
            specs = rows
        else:
            specs = [{"name": name, "mole_frac": None, "iso": self._selected_iso()}]
        return specs, numin, numax, T, P, step, mode, profile, L, ylog, hitran_units, wingHW, intensity_cutoff

    # ───────────────────────── 计算（后台线程） ─────────────────────────
    def _on_mode_change(self):
        """输出模式改变时，启用/禁用光程和摩尔分数输入。"""
        mode = MODES.get(self.mode_var.get(), "alpha")
        # 光程：只有透过率需要
        if hasattr(self, "L_entry"):
            self.L_entry.configure(state="normal" if mode == "transmittance" else "disabled")
        # 摩尔分数：吸收系数和透过率需要，截面和线强不需要
        if hasattr(self, "frac_var_entry"):
            need_frac = mode in ("alpha", "transmittance")
            self.frac_var_entry.configure(state="normal" if need_frac else "disabled")

    def _compute_and_plot(self):
        if self.worker.busy:
            messagebox.showinfo("HitranLab", "计算进行中，请稍候或点击「停止计算」")
            return
        # 停止计算后 cancel_event 可能仍为 set 状态，run() 会自动 clear，这里无需拦截
        try:
            specs, numin, numax, T, P, step, mode, profile, L, ylog, hunits, wingHW, cutoff = self._params()
        except ValueError as e:
            self._show_error(str(e))
            return
        if mode == "linestrength":
            # 线强模式：获取线表数据，绘制竖线图
            self._set_busy(True, "查询线表…")
            name = specs[0]["name"] if specs else self.mol_var.get()
            self.worker.run(self._job_linestrength, name, numin, numax, T, profile)
            return
        if mode == "alpha":
            cmode = "alpha"
        elif mode == "sigma":
            cmode = "alpha"
        elif mode == "transmittance":
            cmode = "transmittance"
        else:
            cmode = "alpha"
        path_cm = L if cmode == "transmittance" else None
        self._set_busy(True, "准备中（首次需联网抓取线表，之后走本地缓存）…")
        self.worker.run(self._job_spectrum, specs, numin, numax, T, P, step,
                        cmode, profile, path_cm, hunits, ylog, wingHW, cutoff)

    def _prog_cb(self):
        """给后台线程用的进度回调：只往队列投消息，绝不直接碰 Tk（跨线程安全）。"""
        def cb(done, total, label):
            try:
                self.worker.q.put(("progress", {"done": int(done), "total": int(total),
                                                "label": str(label)}))
            except Exception:
                pass
        return cb

    def _on_progress(self, d):
        """主线程更新进度条 + 倒计时（剩余时间按已用时间线性外推）。"""
        done = int(d.get("done", 0))
        total = max(1, int(d.get("total", 1)))
        pct = min(100, int(done * 100 / total))
        self.progress.configure(value=pct)
        if not self._prog.get("t0"):
            self._prog["t0"] = time.time()
        self._prog["done"], self._prog["total"] = done, total
        el = time.time() - self._prog["t0"]
        eta = (el / done * (total - done)) if done else 0.0
        self.eta_var.set(f"{pct}%  ·  已用 {el:.0f}s  ·  预计剩余 ~{eta:.0f}s")
        self.status_var.set(f"{d.get('label', '计算中')}（{done}/{total}）")

    def _job_spectrum(self, specs, numin, numax, T, P, step, cmode, profile, path_cm, hunits, ylog, wingHW, cutoff):
        res = hm._compute(specs, numin, numax, T=T, P=P, step=step, wingHW=wingHW,
                          mode=cmode, path_length_cm=path_cm, hitran_units=hunits,
                          profile=profile, intensity_cutoff=cutoff,
                          progress=self._prog_cb())
        label = "+".join(res["per"].keys())
        return {"kind": "spectrum", "res": res, "label": label,
                "mode": cmode, "hitran_units": hunits, "ylog": ylog,
                "specs": specs, "profile": profile}

    def _job_linestrength(self, name, numin, numax, T, profile):
        """获取线表数据，用于线强模式。
        注意：HITRAN 线表的 S 列是参考温度 296K 下的线强，
        非用户设定温度。标签如实标注 S(296K)，不谎报。"""
        data = hm.t_lines(name, numin, numax, top_n=10000, min_intensity=0)
        lines = data.get("lines", [])
        import numpy as np
        nu = np.array([l["nu_cm-1"] for l in lines])
        S = np.array([l["S_cm_per_molecule"] for l in lines])
        res = {"nu": nu, "per": {name: S}, "total": None, "trans": None,
               "numin": numin, "numax": numax, "T": 296.0, "P": 1.0,
               "peaks": {}, "warnings": ["线强为 HITRAN 参考温度 296K 下的值，非用户设定温度"]}
        return {"kind": "linestrength", "res": res, "label": name,
                "mode": "linestrength", "hitran_units": False, "ylog": False,
                "specs": [{"name": name}], "profile": profile}

    def _lines(self):
        if self.worker.busy:
            messagebox.showinfo("HitranLab", "计算进行中，请稍候")
            return
        try:
            specs, numin, numax, T, P, step, mode, profile, L, ylog, hunits, _w, _c = self._params()
            names = [s["name"] for s in specs]
        except ValueError as e:
            self._show_error(str(e))
            return
        self._set_busy(True, "取强线…")
        try:
            top_n = int(self.topn_var.get())
            if top_n <= 0:
                top_n = 15
        except ValueError:
            top_n = 15
        self.worker.run(self._job_lines, names, numin, numax, top_n)

    def _job_lines(self, names, numin, numax, top_n=15):
        """取一个或多个分子的窗口内全部线，合并后按线强降序排序。
        每条线附加 molecule 字段标注来源分子。"""
        if isinstance(names, str):
            names = [names]
        all_lines = []
        n_in_window_total = 0
        warnings = []
        mol_infos = []                       # 每分子溯源信息（导出线表时写头）
        for name in names:
            data = hm.t_lines(name, numin, numax, top_n=100000)
            lines = data.get("lines", [])
            for ln in lines:
                ln["molecule"] = name
            all_lines.extend(lines)
            n_in_window_total += data.get("n_in_window", 0)
            mol_infos.append({"name": name, "M": data.get("M"), "iso": data.get("iso"),
                              "coverage_cm-1": data.get("coverage_cm-1")})
            if data.get("warning"):
                warnings.append(f"[{name}] {data['warning']}")
        # 按线强降序排序
        all_lines.sort(key=lambda x: x.get("S_cm_per_molecule", 0), reverse=True)
        return {"kind": "lines", "data": {
            "lines": all_lines,
            "n_in_window": n_in_window_total,
            "display_top_n": top_n,
            "molecules": names,
            "molecules_info": mol_infos,
            "window_cm-1": [float(numin), float(numax)],
            "warning": "；".join(warnings) if warnings else None,
        }}

    def _partition(self):
        if self.worker.busy:
            messagebox.showinfo("HitranLab", "计算进行中，请稍候")
            return
        try:
            specs, numin, numax, T, P, step, mode, profile, L, ylog, hunits, _w, _c = self._params()
            name = specs[0]["name"]
        except ValueError as e:
            self._show_error(str(e))
            return
        self._set_busy(True, "计算配分函数…")
        self.worker.run(self._job_partition, name, T)

    def _job_partition(self, name, T):
        return {"kind": "partition", "data": hm.t_partition_sum(name, T=T)}

    def _qcurve(self):
        if self.worker.busy:
            messagebox.showinfo("HitranLab", "计算进行中，请稍候")
            return
        try:
            specs, numin, numax, T, P, step, mode, profile, L, ylog, hunits, _w, _c = self._params()
            name = specs[0]["name"]
        except ValueError as e:
            self._show_error(str(e))
            return
        self._set_busy(True, "Q(T) 扫描…")
        try:
            tmin = int(float(self.qtmin_var.get()))
            tmax = int(float(self.qtmax_var.get()))
            tstep = int(float(self.qtstep_var.get()))
            if tmin >= tmax or tstep <= 0:
                tmin, tmax, tstep = 200, 400, 20
        except ValueError:
            tmin, tmax, tstep = 200, 400, 20
        self.worker.run(self._job_qcurve, name, tmin, tmax, tstep)

    def _job_qcurve(self, name, tmin=200, tmax=400, tstep=20):
        Ts = list(range(tmin, tmax + 1, tstep))
        qs = []
        for t in Ts:
            if self.worker.cancel_event.is_set():
                return {"kind": "cancelled"}
            qs.append(hm.t_partition_sum(name, T=float(t))["Q"])
        return {"kind": "qcurve", "name": name, "Ts": Ts, "Qs": qs}

    def _import_xsc(self):
        if self.worker.busy:
            messagebox.showinfo("HitranLab", "计算进行中，请稍候")
            return
        p = self.xsc_var.get().strip()
        if not p or not Path(p).exists():
            messagebox.showwarning("HitranLab", "请先选择截面文件")
            return
        self._set_busy(True, "读入截面文件…")
        self.worker.run(self._job_xsc, p)

    def _job_xsc(self, path):
        out = hm.t_cross_section(file_path=path)
        nu, coef, header, skipped = _read_hotw(path)
        return {"kind": "xsc", "path": path, "out": out, "nu": nu, "coef": coef}

    # ───────────────────────── 结果回填（主线程） ─────────────────────────
    def _drain_queue(self):
        try:
            while True:
                tag, payload = self.worker.q.get_nowait()
                if tag == "err":
                    self._set_busy(False, "出错")
                    self._show_error(payload)
                elif tag == "progress":        # 后台线程上报的进度（不结束忙碌态）
                    self._on_progress(payload)
                else:
                    try:
                        self._render(payload)
                    except Exception as e:
                        import traceback
                        self._set_busy(False, "渲染出错")
                        self._show_error(f"渲染失败: {type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}")
        except queue.Empty:
            pass
        self.after(100, self._drain_queue)

    def _render(self, d):
        kind = d.get("kind")
        if kind == "cancelled":
            self._set_busy(False, "已停止")
            return
        self._set_busy(False, "完成")
        if kind == "species":
            self._species = d["data"]
            self._all_species = sorted(d["data"].keys())
            self.mol_cb["values"] = self._all_species
            # 恢复上次选择的分子（如果在列表中）
            if hasattr(self, "_pending_mol") and self._pending_mol and self._pending_mol in self._all_species:
                self.mol_var.set(self._pending_mol)
            elif "CH4" in d["data"]:
                self.mol_var.set("CH4")
            self.status_var.set(f"已加载官方分子表（{len(d['data'])} 种）")
            self._load_isotopologues()
            # 恢复上次选择的同位素（在同位素列表加载后）
            if hasattr(self, "_pending_iso") and self._pending_iso:
                try:
                    if self._pending_iso in self.iso_cb["values"]:
                        self.iso_var.set(self._pending_iso)
                except Exception:
                    pass
            return
        if kind == "check_update":
            self._render_check_update(d)
            return
        if kind == "update_ready":
            self._render_update_ready(d)
            return
        if kind == "update_prepared":
            self._render_update_prepared(d)
            return
        if kind == "spectrum":
            self._render_spectrum(d)
        elif kind == "linestrength":
            self._render_linestrength(d)
        elif kind == "lines":
            self._render_lines(d["data"])
        elif kind == "partition":
            self._render_partition(d["data"])
        elif kind == "qcurve":
            self._render_qcurve(d)
        elif kind == "xsc":
            self._render_xsc(d)
        if kind in ("spectrum", "linestrength", "lines", "xsc"):
            self._refresh_status()      # 线表/产物数量会变：动态刷新「运行状态」页，避免永远停在开机快照

    def _render_spectrum(self, d):
        res = d["res"]
        nu, per, total = res["nu"], res["per"], res["total"]
        self._last_fig_data = d
        ax = self.ax
        # 如果当前是 Q(T) 或截面视图，切换回谱线视图（清空旧图层数据）
        if self._view_mode != "spectrum":
            self._view_mode = "spectrum"
            self._overlay_count = 0
            self._overlay_data = []
            self.ax.clear()
        first_draw = (self._overlay_count == 0)

        # 统一标签格式：分子 波段 T P（导入数据可能缺字段，安全获取）
        label = d.get("label", "imported")
        numin = res.get("numin", "")
        numax = res.get("numax", "")
        T = res.get("T", "")
        P = res.get("P", "")
        # 将 label 中的分子式替换为显示名（如 CH4 -> CH4 (Methane)）
        disp_label = "+".join(molecule_display_name(part) for part in label.split("+"))
        if numin and numax and T and P:
            tag = f"{disp_label} {float(numin):g}-{float(numax):g} T={float(T):g}K P={float(P):g}atm"
        else:
            tag = disp_label
        self._overlay_data.append({"tag": tag, "data": d})

        if first_draw:
            ax.clear()  # 首次绘制清空提示文字

        unit_lab = ("Cross section σ (cm$^2$/molecule)" if d["hitran_units"]
                    else "Absorption coefficient α (cm$^{-1}$)")
        show_t = res.get("trans") is not None
        # 统一 ylog 口径：以实时复选框为准（无复选框时回退到计算时快照）
        _ylog = self.ylog_var.get() if hasattr(self, "ylog_var") else bool(d.get("ylog"))

        if first_draw:
            # 首次绘制：画各组分 + TOTAL，图例含参数标签
            if show_t:
                ax.plot(nu, res["trans"], color="#6B8FD4", lw=1.4, label=f"{tag} transmittance")
                ylab = "Transmittance"
            else:
                if len(per) > 1:
                    # 多组分：各组分用颜色循环，TOTAL 用白色
                    for i, (lab, c) in enumerate(per.items()):
                        ax.plot(nu, c, color=OVERLAY_COLORS[i % len(OVERLAY_COLORS)],
                                lw=0.9, alpha=0.85, label=lab)
                    ax.plot(nu, total, color="#D8D8DE", lw=1.5, label=f"{tag} TOTAL")
                else:
                    # 单组分：用颜色循环（与叠加一致）
                    lab = list(per.keys())[0]
                    color = OVERLAY_COLORS[self._overlay_count % len(OVERLAY_COLORS)]
                    ax.plot(nu, per[lab], color=color, lw=1.5, label=tag)
                ylab = unit_lab
            ax.set_xlabel("Wavenumber (cm$^{-1}$)")
            ax.set_ylabel(ylab)
            ax.set_title(tag, fontsize=10, pad=10)
            if self._show_grid:
                ax.grid(alpha=0.4, lw=0.6)
            else:
                ax.grid(False)
            if self._show_legend:
                ax.legend(fontsize=7, framealpha=0.9)
            elif ax.get_legend():
                ax.get_legend().remove()
            if not _ylog and not show_t:
                ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
        else:
            # 叠加绘制：只画 total（或单组分），用循环颜色
            color = OVERLAY_COLORS[self._overlay_count % len(OVERLAY_COLORS)]
            if show_t:
                ydata = res["trans"]
                ylab = "Transmittance"
            else:
                ydata = total if len(per) > 1 else list(per.values())[0]
                ylab = unit_lab
            ax.plot(nu, ydata, color=color, lw=1.4, label=tag)
            ax.set_ylabel(ylab)
            if self._show_legend:
                ax.legend(fontsize=7, framealpha=0.9)
            elif ax.get_legend():
                ax.get_legend().remove()
            ax.set_title(f"叠加对比（{self._overlay_count + 1} 条曲线）", fontsize=11, pad=10)

        # 每次绘制都应用一次（叠加层也生效），避免"切换复选框后再叠加不生效"
        ax.set_yscale("log" if _ylog else "linear")
        self._overlay_count += 1
        self.fig.tight_layout()
        self.canvas.draw()
        self._refresh_layers()

        # 峰统计
        txt = []
        for lab, pk in res.get("peaks", {}).items():
            txt.append(f"[{lab}] 峰值 {pk['peak_value']:.4g} @ {pk['peak_nu']:.3f} cm$^{-1}$  "
                       f"(窗口内积分 {pk['integral']:.4g})")
        if len(per) > 1 and total is not None and len(total) > 0:
            # _compute() 不返回 total_peak，自己计算 TOTAL 峰值和积分
            import numpy as np
            idx = int(np.argmax(total))
            peak_val = float(total[idx])
            peak_nu = float(nu[idx])
            integral = float(np.trapz(total, nu)) if len(nu) > 1 else 0.0
            txt.append(f"[TOTAL] 峰值 {peak_val:.4g} @ {peak_nu:.3f} cm$^{-1}$  "
                       f"(积分 {integral:.4g})")
        for w in res.get("warnings", []):
            txt.append(f"! {w}")
        if res.get("trans") is not None:
            tm = res["trans"]
            i = int(tm.argmin())
            txt.append(f"[透过率] 谷值 {float(tm[i]):.4g} @ {float(nu[i]):.3f} cm$^{-1}$ "
                       f"(L={res.get('path_length_cm') or 1.0:g} cm)")
        self.peak_text.delete("1.0", tk.END)
        self.peak_text.insert("1.0", "\n".join(txt) if txt else "（无峰/无警告）")

    def _render_linestrength(self, d):
        """线强 S(296K) 模式：竖线图显示各谱线强度（HITRAN 参考温度 296K）。"""
        res = d["res"]
        nu = res["nu"]
        S = list(res["per"].values())[0]
        name = d["label"]
        numin = res.get("numin", "")
        numax = res.get("numax", "")
        if numin and numax:
            disp = molecule_display_name(name)
            tag = f"{disp} {float(numin):g}-{float(numax):g} S(296K)"
        else:
            tag = f"{name} S(296K)"
        # 如果当前是 Q(T) 或截面视图，切换回谱线视图（清空旧图层数据）
        if self._view_mode != "spectrum":
            self._view_mode = "spectrum"
            self._overlay_count = 0
            self._overlay_data = []
            self.ax.clear()
        self._overlay_data.append({"tag": tag, "data": d})
        first_draw = (self._overlay_count == 0)
        if first_draw:
            self.ax.clear()
        color = OVERLAY_COLORS[self._overlay_count % len(OVERLAY_COLORS)]
        # 对数轴无法表示 0，底端用 S.min()/1000 代替
        ymin = float(S.min()) / 1000.0 if len(S) > 0 and S.min() > 0 else 1e-30
        self.ax.vlines(nu, ymin, S, color=color, lw=0.8, alpha=0.8, label=tag)
        # 为前 5 条最强线添加波数标注
        if len(nu) > 0 and len(S) > 0:
            import numpy as np
            S_arr = np.array(S)
            top_idx = np.argsort(S_arr)[-5:][::-1]  # 前 5 强线
            for idx in top_idx:
                self.ax.annotate(f"{nu[idx]:.2f}", xy=(nu[idx], float(S[idx])),
                                  xytext=(0, 5), textcoords="offset points",
                                  fontsize=7, color=color, alpha=0.9,
                                  ha="center", va="bottom")
        self.ax.set_xlabel("Wavenumber (cm$^{-1}$)")
        self.ax.set_ylabel("Line strength S(296K) (cm/molecule)")
        # 与吸收谱统一口径：尊重「对数坐标」复选框（默认线性，勾选才对数）
        use_log = getattr(self, "ylog_var", None)
        if use_log is not None and not use_log.get():
            self.ax.set_yscale("linear")
        else:
            self.ax.set_yscale("log")
        self.ax.grid(alpha=0.4, lw=0.6)
        self.ax.legend(fontsize=7, framealpha=0.9)
        self.ax.set_title("Line Strength S(296K)" if first_draw else f"叠加对比（{self._overlay_count + 1} 条）", fontsize=11, pad=10)
        self._overlay_count += 1
        self.fig.tight_layout()
        self.canvas.draw()
        self._refresh_layers()
        # 显示警告（线强为 HITRAN 参考温度 296K，非用户设定温度）
        warnings = res.get("warnings", [])
        self.peak_text.delete("1.0", tk.END)
        if warnings:
            warn_text = "⚠ " + "\n⚠ ".join(str(w) for w in warnings[:3]) + "\n\n"
            self.peak_text.insert("1.0", warn_text)
        if len(nu) > 0:
            self.peak_text.insert("1.0", f"[{name}] 窗口内 {len(nu)} 条谱线\n"
                                         f"最强线: {float(S.max()):.4g} @ {float(nu[S.argmax()]):.3f} cm$^{-1}$\n"
                                         f"最弱线: {float(S.min()):.4g} @ {float(nu[S.argmin()]):.3f} cm$^{-1}$")
        else:
            self.peak_text.insert("1.0", f"[{name}] 窗口内无谱线（请扩大波段范围）")

    def _render_lines(self, data):
        self._last_lines_data = data
        self.line_tree.delete(*self.line_tree.get_children())
        all_lines = data.get("lines", [])
        display_n = data.get("display_top_n", 15)
        display = all_lines[:display_n]
        molecules = data.get("molecules", [])
        for ln in display:
            self.line_tree.insert("", "end", values=(
                ln.get("molecule", "?"),
                f"{ln['nu_cm-1']:.4f}", f"{ln['S_cm_per_molecule']:.3e}",
                f"{ln['gamma_air']:.4f}", f"{ln['E_lower_cm-1']:.2f}"))
        w = data.get("warning")
        if w:
            self.status_var.set("强线完成：窗口内 0 条？见提示")
            messagebox.showinfo("HitranLab", w)
        else:
            mol_str = "+".join(molecules) if molecules else "未知"
            self.status_var.set(f"强线完成：{len(molecules)} 个分子（{mol_str}），窗口内共 {data.get('n_in_window', 0)} 条，显示最强 {len(display)} 条（完整数据可导出）")
        self.nb.select(self.line_tab)

    def _render_partition(self, data):
        self.peak_text.delete("1.0", tk.END)
        self.peak_text.insert("1.0",
            f"配分函数 Q({data['T']:g} K) = {data['Q']:.6g}\n"
            f"分子 {data['molecule']} (M={data['M']}, I={data['I']}) · TIPS-{data['tips_version']}\n")
        self.nb.select(self.peak_tab)
        self.status_var.set(f"Q({data['T']:g} K) = {data['Q']:.6g}")

    def _render_qcurve(self, d):
        # 切换视图：同时清空谱线图层数据，避免「图层管理」残留幽灵条目/误删打回谱线图
        self._view_mode = "qcurve"
        self._overlay_count = 0
        self._overlay_data = []
        ax = self.ax
        ax.clear()
        ax.plot(d["Ts"], d["Qs"], "o-", color="#7BC47F", lw=1.5, markersize=5)
        ax.set_xlabel("Temperature T (K)")
        ax.set_ylabel("Partition function Q(T)")
        ax.set_title(f"{d['name']}  Q(T)  TIPS-2025 （点击「计算并绘图」返回谱线视图）", fontsize=10, pad=10)
        ax.grid(alpha=0.4, lw=0.6)
        self.fig.tight_layout()
        self.canvas.draw()
        self._last_fig_data = {"kind": "qcurve", "name": d["name"]}
        self._refresh_layers()
        self.status_var.set(f"Q(T) 曲线：{d['Ts'][0]}–{d['Ts'][-1]} K（点击「计算并绘图」返回谱线视图）")

    def _render_xsc(self, d):
        # 切换视图：清空谱线图层数据（同 _render_qcurve）
        self._view_mode = "xsc"
        self._overlay_count = 0
        self._overlay_data = []
        nu, coef = d["nu"], d["coef"]
        ax = self.ax
        ax.clear()
        if nu is not None and len(nu):
            ax.plot(nu, coef, lw=1.0, color="#BB9AF7")
            ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
        ax.set_xlabel("Wavenumber (cm$^{-1}$)")
        ax.set_ylabel("Cross section σ (cm$^2$/molecule)")
        ax.set_title(Path(d["path"]).name, fontsize=11, pad=10)
        ax.grid(alpha=0.4, lw=0.6)
        self.fig.tight_layout()
        self.canvas.draw()
        self._last_fig_data = d
        out = d["out"]
        pk = out.get("peak") or {}
        pk_str = (f"{pk.get('sigma_cm2_per_molecule'):.4g} @ {pk.get('at_nu_cm-1'):.3f} cm-1"
                  if pk else "—")
        self.xsc_text.delete("1.0", tk.END)
        self.xsc_text.insert("1.0",
            f"文件: {d['path']}\n"
            f"数据点: {out.get('n_points_file')}（窗口内 {out.get('n_points_in_window')}）\n"
            f"峰值 σ: {pk_str}\n"
            f"产物: {out.get('png')}\n      {out.get('csv')}\n"
            + ("".join(f"! {w}\n" for w in out.get("warnings", []))))
        self.nb.select(self.xsc_tab)
        self._refresh_layers()
        self.status_var.set("截面导入完成")

    def _refresh_status(self):
        try:
            st = hm.t_apikey_status()
            self.stat_text.delete("1.0", tk.END)
            self.stat_text.insert("1.0",
                f"API key: {'已配置' if st.get('api_key_configured') else '未配置'}（{st.get('api_key_source')}）\n"
                f"线表缓存: {st.get('line_cache_files')} 个 / {st.get('line_cache_MB')} MB\n"
                f"截面文件: {st.get('xsc_data_files')} 个\n"
                f"产物: {st.get('output_files')} 个\n"
                f"目录: {hm.OUT_DIR}")
        except Exception as e:
            self.stat_text.delete("1.0", tk.END)
            self.stat_text.insert("1.0", f"状态读取失败: {e}")

    # ───────────────────────── 导出 ─────────────────────────
    def _export_lines(self):
        if not getattr(self, "_last_lines_data", None):
            messagebox.showinfo("HitranLab", "请先点击「强线列表」获取线表")
            return
        data = self._last_lines_data
        lines = data.get("lines", [])
        if not lines:
            messagebox.showinfo("HitranLab", "窗口内无谱线")
            return
        molecules = data.get("molecules", [])
        mol_str = "+".join(molecules) if molecules else "lines"
        p = filedialog.asksaveasfilename(defaultextension=".csv",
                                         filetypes=[("CSV", "*.csv")],
                                         initialfile=f"{mol_str}_linelist.csv")
        if not p:
            return
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(f"# HitranLab line list · molecules: {mol_str}\n")
            win = data.get("window_cm-1")
            if win:
                f.write(f"# requested window: {win[0]:g}-{win[1]:g} cm-1\n")
            for mi in data.get("molecules_info", []):
                f.write(f"#   [{mi.get('name')}] M={mi.get('M')}, iso={mi.get('iso')}, "
                        f"coverage={mi.get('coverage_cm-1')} cm-1\n")
            f.write(f"# n_in_window: {data.get('n_in_window',0)}\n")
            f.write("molecule,nu_cm-1,S_cm_per_molecule,gamma_air,E_lower_cm-1\n")
            for ln in lines:
                f.write(f"{ln.get('molecule','?')},{ln['nu_cm-1']:.6f},{ln['S_cm_per_molecule']:.6e},"
                        f"{ln['gamma_air']:.6f},{ln['E_lower_cm-1']:.4f}\n")
        self.status_var.set(f"线表已导出 ({len(lines)} 条, {len(molecules)} 个分子): {p}")
        messagebox.showinfo("HitranLab", f"完整线表已导出 ({len(lines)} 条, {len(molecules)} 个分子):\n{p}")

    def _export_csv(self):
        if not self._overlay_data:
            messagebox.showinfo("HitranLab", "请先「计算并绘图」")
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv",
                                         filetypes=[("CSV", "*.csv")],
                                         initialfile="spectrum.csv")
        if not p:
            return

        datasets = self._overlay_data
        # 用第一个数据集的波数轴作为基准
        first_res = datasets[0]["data"]["res"]
        nu = first_res["nu"]
        first_mode = datasets[0]["data"].get("mode", "alpha")

        header = "# HitranLab export · HITRAN2024 via HAPI 1.3.0.0 · TIPS-2025\n"
        header += f"# {len(datasets)} dataset(s) overlaid\n"
        if first_res.get("trans") is not None:
            header += (f"# units: transmittance (dimensionless), "
                       f"L={first_res.get('path_length_cm') or 1.0:g} cm\n")
        elif datasets[0]["data"].get("hitran_units"):
            header += "# units: sigma cm2/molecule\n"        # 截面 σ 模式（GUI 里 mode 会被折成 alpha，故按 hitran_units 判定）
        elif first_mode == "linestrength":
            header += "# units: S(296K) cm/molecule\n"       # HITRAN 线强参考温度 296K
        else:
            header += "# units: alpha cm-1\n"

        # 列：波数 + 每个数据集的 T（透过率）或 total（多组分）或单组分
        cols = ["nu_cm-1"]
        data_cols = []
        for ds in datasets:
            tag = ds["tag"]
            res = ds["data"]["res"]
            per = res["per"]
            if res.get("trans") is not None:
                # 透过率模式：导出画布上真正画出来的那条 T（而非 α），否则 CSV 与 PNG 内容不一致
                cols.append(f"{tag}_transmittance")
                data_cols.append(res["trans"])
            elif len(per) > 1 and res.get("total") is not None:
                cols.append(f"{tag}_total")
                data_cols.append(res["total"])
            else:
                first_key = list(per.keys())[0]
                cols.append(f"{tag}_{first_key}")
                data_cols.append(per[first_key])

        import numpy as np
        # 校验所有数据集波数轴长度一致（不同窗口/步长/模式无法合并导出）
        ref_len = len(nu)
        for i, ds in enumerate(datasets[1:], 1):
            res_i = ds["data"]["res"]
            if "nu" in res_i and len(res_i["nu"]) != ref_len:
                messagebox.showerror("HitranLab",
                    f"无法合并导出：第 {i+1} 组数据（{ds['tag']}）波数点数 {len(res_i['nu'])} "
                    f"与第一组 {ref_len} 不一致。\n\n"
                    f"可能原因：不同波数窗口 / 不同步长 step / 线强模式与吸收谱模式混用。\n"
                    f"请分别导出，或使用相同窗口和步长重新计算。")
                return
        # 用 numpy 组装矩阵并一次性写入，避免逐行 Python 循环卡死 UI
        try:
            out = np.column_stack([nu] + data_cols)
        except ValueError as e:
            messagebox.showerror("HitranLab", f"CSV 导出失败（数组维度不一致）：{e}")
            return
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(header)
            f.write(",".join(cols) + "\n")
            np.savetxt(f, out, delimiter=",", fmt=["%.6f"] + ["%.6e"] * len(data_cols))

        self.status_var.set(f"CSV 已导出 ({len(datasets)} 组数据): {p}")
    def _export_png(self):
        p = filedialog.asksaveasfilename(defaultextension=".png",
                                         filetypes=[("PNG", "*.png")],
                                         initialfile="spectrum.png")
        if not p:
            return
        self.fig.savefig(p, dpi=200)
        self.status_var.set(f"PNG 已导出: {p}")
        messagebox.showinfo("HitranLab", f"PNG 已导出:\n{p}")

    def _stop_compute(self):
        """请求停止当前计算。HAPI 单次调用无法中断，但立即恢复 UI，后台结果自动丢弃。"""
        if self.worker.busy:
            self.worker.force_reset()
            self._set_busy(False, "已停止（后台计算结果将被丢弃）")

    def _show_error(self, msg):
        """状态栏红字提示错误，不弹窗打断。"""
        self.status_label.configure(foreground="#E07A7A")
        self.status_var.set(f"✗ {msg}")
        self.after(5000, self._restore_status)

    def _restore_status(self):
        self.status_label.configure(foreground="")
        if not self.worker.busy:
            self.status_var.set("就绪")

    # ───────────────────────── 菜单栏功能 ─────────────────────────
    def _save_project(self):
        """保存当前参数和叠加数据为 JSON 项目文件。"""
        p = filedialog.asksaveasfilename(defaultextension=".json",
                                          filetypes=[("项目文件", "*.json")],
                                          initialfile="hitran_project.json")
        if not p:
            return
        import json
        project = {
            "version": APP_VERSION,
            "params": {
                "molecule": self.mol_var.get(),
                "iso": self.iso_var.get(),
                "numin": self.numin_var.get(), "numax": self.numax_var.get(),
                "step": self.step_var.get(),
                "T": self.T_var.get(), "P": self.P_var.get(), "L": self.L_var.get(),
                "mode": self.mode_var.get(), "profile": self.profile_var.get(),
                "ylog": self.ylog_var.get(),
                "wingHW": self.winghw_var.get(), "cutoff": self.cutoff_var.get(),
                "topn": self.topn_var.get(),
                "qtmin": self.qtmin_var.get(), "qtmax": self.qtmax_var.get(), "qtstep": self.qtstep_var.get(),
            },
            "mixture": [(self.mix_tree.item(it)["values"][0], self.mix_tree.item(it)["values"][1])
                        for it in self.mix_tree.get_children()],
            "mix_unit": self.mix_unit_var.get(),
            "n_layers": len(self._overlay_data),
        }
        try:
            Path(p).write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status_var.set(f"项目已保存: {p}")
            messagebox.showinfo("HitranLab", f"项目已保存:\n{p}")
        except Exception as e:
            self._show_error(f"保存失败: {e}")

    def _open_project(self):
        """打开之前保存的项目 JSON，恢复参数与混合气表格（谱线需重新计算）。"""
        p = filedialog.askopenfilename(filetypes=[("项目文件", "*.json"), ("所有文件", "*.*")])
        if not p:
            return
        try:
            import json
            d = json.loads(Path(p).read_text(encoding="utf-8"))
            pr = d.get("params", {}) or {}
            if pr.get("molecule"):
                self.mol_var.set(str(pr["molecule"]))
            self._load_isotopologues()          # 先重建同位素候选，再恢复选择
            for key, var in (("iso", self.iso_var),
                             ("numin", self.numin_var), ("numax", self.numax_var),
                             ("step", self.step_var), ("T", self.T_var), ("P", self.P_var),
                             ("L", self.L_var), ("mode", self.mode_var),
                             ("profile", self.profile_var), ("wingHW", self.winghw_var),
                             ("cutoff", self.cutoff_var), ("topn", self.topn_var),
                             ("qtmin", self.qtmin_var), ("qtmax", self.qtmax_var),
                             ("qtstep", self.qtstep_var)):
                v = pr.get(key)
                if v in (None, ""):
                    continue
                try:
                    var.set(str(v))
                except Exception:
                    pass
            if "ylog" in pr:
                self.ylog_var.set(bool(pr["ylog"]))
            for it in self.mix_tree.get_children():
                self.mix_tree.delete(it)
            for row in (d.get("mixture") or []):
                try:
                    self.mix_tree.insert("", "end", values=(row[0], row[1]))
                except Exception:
                    continue
            # 恢复单位选择（兼容旧项目：无单位字段时默认摩尔分数）
            saved_unit = d.get("mix_unit", "摩尔分数")
            if saved_unit in ("摩尔分数", "ppm", "ppb"):
                self.mix_unit_var.set(saved_unit)
            self._update_mix_sum()
            self._on_mode_change()
            self.status_var.set(f"项目已打开: {Path(p).name}（谱线请重新计算）")
        except Exception as e:
            self._show_error(f"打开项目失败: {e}")

    def _import_spectrum(self):
        """从外部 CSV/TXT 导入光谱数据，叠加到当前图。"""
        p = filedialog.askopenfilename(filetypes=[("数据文件", "*.csv *.txt *.dat"), ("所有文件", "*.*")])
        if not p:
            return
        try:
            import numpy as np
            nu, coef = [], []
            with open(p, encoding="utf-8", errors="replace") as f:
                for ln in f:
                    s = ln.strip()
                    if not s or s.startswith("#"):
                        continue
                    parts = s.replace(",", " ").split()
                    if len(parts) >= 2:
                        try:
                            nu.append(float(parts[0]))
                            coef.append(float(parts[1]))
                        except ValueError:
                            continue
            if not nu:
                self._show_error("文件中无有效数据（需要两列：波数, 值）")
                return
            tag = f"{Path(p).stem} (imported)"
            # 若当前处于 Q(T)/截面视图，先切回谱线视图（清空旧图层）
            if self._view_mode != "spectrum":
                self._view_mode = "spectrum"
                self._overlay_count = 0
                self._overlay_data = []
                self.ax.clear()
            color = OVERLAY_COLORS[self._overlay_count % len(OVERLAY_COLORS)]
            if self._overlay_count == 0:
                self.ax.clear()
            self.ax.plot(nu, coef, color=color, lw=1.4, label=tag)
            self.ax.set_xlabel("Wavenumber (cm$^{-1}$)")
            self.ax.legend(fontsize=7, framealpha=0.9)
            self.ax.grid(alpha=0.4, lw=0.6)
            self.fig.tight_layout()
            self.canvas.draw()
            self._overlay_count += 1
            self._overlay_data.append({"tag": tag, "data": {
                "kind": "imported", "label": tag,
                "res": {"nu": np.array(nu), "per": {tag: np.array(coef)}, "total": None},
                "hitran_units": False, "ylog": False}})
            self._refresh_layers()
            self.status_var.set(f"已导入 {len(nu)} 个数据点: {Path(p).name}")
        except Exception as e:
            self._show_error(f"导入失败: {e}")

    def _copy_image(self):
        """复制当前图像到剪贴板。"""
        try:
            from PIL import Image
            import io
            buf = io.BytesIO()
            self.fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            img = Image.open(buf)
            img.copy_to_clipboard()
            self.status_var.set("图像已复制到剪贴板")
        except Exception as e:
            self._show_error(f"复制图像失败: {e}")

    def _copy_data(self):
        """复制当前叠加数据到剪贴板（CSV 格式）。"""
        if not self._overlay_data:
            self._show_error("无数据可复制")
            return
        try:
            lines = []
            for ds in self._overlay_data:
                res = ds["data"]["res"]
                nu = res["nu"]
                per = res["per"]
                if res.get("trans") is not None:
                    y = res["trans"]                 # 与画布一致：透过率给 T，不给 α
                elif len(per) > 1 and res.get("total") is not None:
                    y = res["total"]
                else:
                    y = list(per.values())[0]
                lines.append(f"# {ds['tag']}")
                for i in range(len(nu)):
                    lines.append(f"{nu[i]:.6f},{y[i]:.6e}")
                lines.append("")
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))
            self.status_var.set(f"数据已复制到剪贴板（{len(self._overlay_data)} 组）")
        except Exception as e:
            self._show_error(f"复制数据失败: {e}")

    def _load_prefs(self):
        """启动时载入上次「首选项」；文件缺失/损坏时静默跳过。"""
        try:
            import json
            if not PREFS_PATH.exists():
                return
            d = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        # 保存分子/同位素选择，等 _load_species 完成后再恢复
        self._pending_mol = d.get("molecule", "")
        self._pending_iso = d.get("iso", "")
        for key, attr in (("numin", "numin_var"), ("numax", "numax_var"), ("step", "step_var"),
                          ("T", "T_var"), ("P", "P_var"), ("L", "L_var"),
                          ("wingHW", "winghw_var"), ("profile", "profile_var"), ("mode", "mode_var"),
                          ("cutoff", "cutoff_var"), ("topn", "topn_var"),
                          ("qtmin", "qtmin_var"), ("qtmax", "qtmax_var"), ("qtstep", "qtstep_var")):
            v = d.get(key)
            if v in (None, ""):
                continue
            try:
                getattr(self, attr).set(str(v))
            except Exception:
                pass
        # ylog 复选框
        if "ylog" in d and hasattr(self, "ylog_var"):
            try:
                self.ylog_var.set(bool(d["ylog"]))
            except Exception:
                pass
        # 恢复混合气单位（mix_unit_var 在 _build_ui 中已初始化）
        _mu = d.get("mix_unit")
        if _mu in ("摩尔分数", "ppm", "ppb") and hasattr(self, "mix_unit_var"):
            try:
                self.mix_unit_var.set(_mu)
                self._mix_unit = _mu
            except Exception:
                pass

    def _save_prefs(self, d):
        """把首选项写入 hitran_prefs.json（读-改-写，保留 theme 等其他键）。"""
        try:
            import json
            # 读-改-写：合并现有配置，避免保存首选项时把 theme 等键洗掉
            merged = {}
            if PREFS_PATH.exists():
                try:
                    merged = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
                except Exception:
                    pass
            merged.update(d)
            PREFS_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            self._show_error(f"首选项保存失败: {e}")

    def _save_all_prefs(self):
        """保存所有当前设置到首选项文件（退出时自动调用）。"""
        try:
            import json
            d = {}
            # 基本参数
            for key, attr in (("molecule", "mol_var"), ("iso", "iso_var"),
                              ("numin", "numin_var"), ("numax", "numax_var"), ("step", "step_var"),
                              ("T", "T_var"), ("P", "P_var"), ("L", "L_var"),
                              ("wingHW", "winghw_var"), ("profile", "profile_var"), ("mode", "mode_var"),
                              ("cutoff", "cutoff_var"), ("topn", "topn_var"),
                              ("qtmin", "qtmin_var"), ("qtmax", "qtmax_var"), ("qtstep", "qtstep_var")):
                try:
                    d[key] = getattr(self, attr).get()
                except Exception:
                    pass
            # ylog
            if hasattr(self, "ylog_var"):
                d["ylog"] = bool(self.ylog_var.get())
            # mix_unit
            if hasattr(self, "mix_unit_var"):
                d["mix_unit"] = self.mix_unit_var.get()
            # theme
            d["theme"] = self._theme
            self._save_prefs(d)
        except Exception:
            pass  # 保存失败不影响退出

    def _on_exit(self):
        """退出程序：保存所有设置后销毁窗口。"""
        try:
            self._save_all_prefs()
        except Exception:
            pass
        try:
            self.worker.stop()
        except Exception:
            pass
        self.destroy()

    def _show_preferences(self):
        """首选项对话框（默认参数，落盘 hitran_prefs.json）。"""
        win = tk.Toplevel(self)
        win.title("首选项")
        win.geometry("380x450")
        win.configure(bg=self._bg)
        win.transient(self)
        win.grab_set()

        def row(label, var):
            ttk.Label(win, text=label, background=self._bg).pack(anchor="w", padx=16, pady=(10, 2))
            ttk.Entry(win, textvariable=var, width=12).pack(anchor="w", padx=16)

        pv1 = tk.StringVar(value=self.numin_var.get())
        pv2 = tk.StringVar(value=self.numax_var.get())
        ttk.Label(win, text="默认波数范围 (cm⁻¹):", background=self._bg).pack(anchor="w", padx=16, pady=(16, 2))
        pf = ttk.Frame(win); pf.pack(fill="x", padx=16)
        ttk.Entry(pf, textvariable=pv1, width=10).pack(side="left")
        ttk.Label(pf, text="—", background=self._bg).pack(side="left", padx=6)
        ttk.Entry(pf, textvariable=pv2, width=10).pack(side="left")
        sv = tk.StringVar(value=self.step_var.get())
        row("默认步长 (cm⁻¹):", sv)
        tv = tk.StringVar(value=self.T_var.get())
        row("默认温度 (K):", tv)
        prv = tk.StringVar(value=self.P_var.get())
        row("默认压力 (atm):", prv)
        wv = tk.StringVar(value=self.winghw_var.get())
        row("默认翼宽 (cm⁻¹):", wv)
        pvv = tk.StringVar(value=self.profile_var.get())
        ttk.Label(win, text="默认线型:", background=self._bg).pack(anchor="w", padx=16, pady=(10, 2))
        ttk.Combobox(win, textvariable=pvv, values=PROFILES, width=18, state="readonly").pack(anchor="w", padx=16)

        def apply():
            self.numin_var.set(pv1.get()); self.numax_var.set(pv2.get())
            self.step_var.set(sv.get()); self.T_var.set(tv.get()); self.P_var.set(prv.get())
            self.winghw_var.set(wv.get()); self.profile_var.set(pvv.get())
            self._save_prefs({"numin": pv1.get(), "numax": pv2.get(), "step": sv.get(),
                              "T": tv.get(), "P": prv.get(), "wingHW": wv.get(),
                              "profile": pvv.get(), "mode": self.mode_var.get()})
            self.status_var.set("首选项已保存（下次启动自动载入）")
            win.destroy()

        ttk.Button(win, text="保存并应用", command=apply).pack(pady=16)

    def _toggle_grid(self):
        self._show_grid = self._var_grid.get()
        if self._show_grid:
            self.ax.grid(alpha=0.4, lw=0.6)
        else:
            self.ax.grid(False)
        self.canvas.draw()

    def _toggle_legend(self):
        self._show_legend = self._var_legend.get()
        leg = self.ax.get_legend()
        if self._show_legend:
            if leg is None:
                self.ax.legend(fontsize=7, framealpha=0.9)
        else:
            if leg is not None:
                leg.remove()
        self.canvas.draw()

    def _show_converter(self):
        """波长 ↔ 波数换算器。"""
        win = tk.Toplevel(self)
        win.title("波长 ↔ 波数换算器")
        win.geometry("340x200")
        win.configure(bg=self._bg)
        win.transient(self)
        ttk.Label(win, text="波长 λ (nm):", background=self._bg).pack(anchor="w", padx=16, pady=(16, 2))
        wv = tk.StringVar(value="1650")
        we = ttk.Entry(win, textvariable=wv, width=14); we.pack(anchor="w", padx=16)
        ttk.Label(win, text="波数 ν (cm⁻¹):", background=self._bg).pack(anchor="w", padx=16, pady=(12, 2))
        nv = tk.StringVar(value="6060.6")
        ne = ttk.Entry(win, textvariable=nv, width=14); ne.pack(anchor="w", padx=16)
        _guard = {"on": False}
        def wv_to_nv(*a):
            if _guard["on"]: return
            try:
                w = float(wv.get())
                if w > 0:
                    _guard["on"] = True
                    nv.set(f"{1e7/w:.6g}")
                    _guard["on"] = False
            except ValueError:
                pass
        def nv_to_wv(*a):
            if _guard["on"]: return
            try:
                n = float(nv.get())
                if n > 0:
                    _guard["on"] = True
                    wv.set(f"{1e7/n:.6g}")
                    _guard["on"] = False
            except ValueError:
                pass
        wv.trace_add("write", wv_to_nv)
        nv.trace_add("write", nv_to_wv)
        ttk.Label(win, text="公式: ν(cm⁻¹) = 10⁷ / λ(nm)", background=self._bg,
                  foreground="#8A8A92").pack(pady=12)

    def _show_molecule_table(self):
        """HITRAN 分子表查询对话框。"""
        win = tk.Toplevel(self)
        win.title("HITRAN 分子表查询")
        win.geometry("520x480")
        win.configure(bg=self._bg)
        win.transient(self)
        ttk.Label(win, text="搜索（分子式）:", background=self._bg).pack(anchor="w", padx=12, pady=(10, 2))
        sv = tk.StringVar()
        se = ttk.Entry(win, textvariable=sv); se.pack(fill="x", padx=12)
        cols = ("id", "name", "main_iso")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=16)
        for c, t, w in (("id", "M", 50), ("name", "分子式", 180), ("main_iso", "主同位素", 80)):
            tree.heading(c, text=t); tree.column(c, width=w)
        tree.pack(fill="both", expand=True, padx=12, pady=8)
        def refresh(*a):
            tree.delete(*tree.get_children())
            q = sv.get().strip().lower()
            for name, info in self._species.items():
                if q and q not in name.lower():
                    continue
                M = info.get("M", "") if isinstance(info, dict) else info
                mi = info.get("main_iso", "") if isinstance(info, dict) else ""
                tree.insert("", "end", values=(M, name, mi))
        sv.trace_add("write", refresh)
        refresh()

    def _show_shortcuts(self):
        """快捷键列表。"""
        shortcuts = [
            ("Ctrl+O", "打开项目"),
            ("Ctrl+S", "保存项目"),
            ("Alt+F4", "退出"),
            ("鼠标滚轮", "缩放/平移（matplotlib 工具栏）"),
            ("左键拖拽", "平移视图"),
            ("右键拖拽", "缩放视图"),
        ]
        win = tk.Toplevel(self)
        win.title("快捷键列表")
        win.geometry("320x220")
        win.configure(bg=self._bg)
        win.transient(self)
        for key, desc in shortcuts:
            row = ttk.Frame(win); row.pack(fill="x", padx=16, pady=4)
            ttk.Label(row, text=key, width=14, foreground="#6B8FD4", background=self._bg).pack(side="left")
            ttk.Label(row, text=desc, background=self._bg).pack(side="left")

    def _show_help(self):
        """使用说明。"""
        help_text = """HitranLab 使用说明

【基本流程】
1. 选择分子和波段（波数范围）
2. 设置温度、压力、步长
3. 选择输出类型（吸收系数/透过率/截面）
4. 点击「计算并绘图」

【叠加绘图】
- 多次点击「计算并绘图」会自动叠加曲线
- 在「图层管理」tab 可删除单条曲线
- 「清空图」重置画布

【混合气】
- 在「混合气」区添加多组分
- 浓度留空表示纯气体

【截面文件】
- 支持 HOTW 格式（两列：波数, 截面）
- 用于 HITRAN 未收录的分子

【导出】
- CSV：导出所有叠加曲线数据
- PNG：导出当前图像

【快捷键】
- Ctrl+S：保存项目
- Alt+F4：退出
"""
        win = tk.Toplevel(self)
        win.title("使用说明")
        win.geometry("480x520")
        win.configure(bg=self._bg)
        win.transient(self)
        txt = tk.Text(win, font=("Microsoft YaHei", 9), bg="#1A1A1F", fg="#D8D8DE",
                      wrap="word", padx=12, pady=10, relief="flat")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("1.0", help_text)
        txt.configure(state="disabled")

    def _render_check_update(self, d):
        """处理检查更新结果：有新版本则询问是否下载并自动升级。"""
        if "error" in d:
            self._show_error(f"检查更新失败: {d['error']}")
            return
        if not d.get("has_update"):
            messagebox.showinfo("检查更新", f"当前已是最新版本 v{d['current']}")
            self.status_var.set("检查更新完成")
            return
        if not getattr(sys, "frozen", False):
            messagebox.showinfo("检查更新",
                f"发现新版本 v{d['latest']}（当前 v{d['current']}）\n\n"
                f"源码模式下不做自动替换，请到发布页取新版：\n{d['url']}")
            self.status_var.set("检查更新完成")
            return
        if not d.get("asset_url"):
            messagebox.showwarning("检查更新",
                f"发现新版本 v{d['latest']}，但该发布未附带 {UPDATE_ASSET}。\n\n"
                f"请到发布页手动下载：\n{d['url']}")
            self.status_var.set("检查更新完成")
            return
        if not messagebox.askyesno("检查更新",
                f"发现新版本！\n\n当前版本: v{d['current']}\n最新版本: v{d['latest']}\n\n"
                f"发布说明: {d['body']}\n\n现在下载并自动升级吗？\n"
                f"（下载完成后需重启程序，替换时保留 Hitran_Data 线表缓存）"):
            self.status_var.set(f"已有新版本 v{d['latest']}，可到 {d['url']} 下载")
            return
        self._set_busy(True, "下载更新包…")
        self.worker.run(self._job_download_update, d["asset_url"], UPDATE_ASSET)

    def _job_download_update(self, url, name):
        """后台下载新版免安装包到 _update/（复用进度通道，按字节上报）。"""
        import urllib.request
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        dst = UPDATE_DIR / (name or UPDATE_ASSET)
        cb = self._prog_cb()
        req = urllib.request.Request(url, headers={"User-Agent": "HitranLab"})
        with urllib.request.urlopen(req, timeout=60) as r:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            with open(dst, "wb") as f:
                while True:
                    chunk = r.read(262144)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    if total:
                        cb(got, total, "下载更新包")
        if dst.stat().st_size < 1_000_000:
            raise RuntimeError(f"下载的更新包异常（仅 {dst.stat().st_size} 字节），已放弃")
        return {"kind": "update_ready", "zip": str(dst), "dir": str(UPDATE_DIR)}

    def _render_update_ready(self, d):
        """更新包下载完成 → 询问是否立即更新 → 后台解压 → 替换重启。"""
        zip_path = Path(d["zip"])
        if not messagebox.askyesno("自动升级",
                f"新版已下载：\n{zip_path}\n\n"
                f"是否立即解压、替换文件并自动重启？\n"
                f"（替换用 robocopy 覆盖，不会删除你的 Hitran_Data 线表缓存）"):
            self.status_var.set("更新包已下载，可手动解压 _update 目录替换")
            return
        # 解压挪到 worker，避免大文件解压阻塞主线程
        self._set_busy(True, "正在解压更新包…")
        if not self.worker.run(self._job_prepare_update, d["zip"], d["dir"]):
            self._set_busy(False, "启动解压失败")

    def _job_prepare_update(self, zip_path, update_dir):
        """后台解压更新包，返回解压后的源目录路径。"""
        import zipfile
        import shutil
        zip_path = Path(zip_path)
        newdir = Path(update_dir) / "new"
        if newdir.exists():
            shutil.rmtree(newdir)
        newdir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(newdir)
        # 定位策略：先判解压根是否有 HitranLab.exe（扁平 zip），
        # 再退回唯一子目录（带一层目录的 zip），避免扁平 zip 被误判为 _internal
        if (newdir / "HitranLab.exe").exists():
            src = newdir
        else:
            subs = [p for p in newdir.iterdir() if p.is_dir()]
            src = subs[0] if len(subs) == 1 else newdir
        if not (src / "HitranLab.exe").exists():
            raise RuntimeError(f"更新包结构不符合预期（未找到 HitranLab.exe）：{src}")
        return {"kind": "update_prepared", "src": str(src), "zip": str(zip_path)}

    def _render_update_prepared(self, d):
        """解压完成 → 生成升级脚本 → 启动 → 退出本程序。"""
        src = Path(d["src"])
        zip_path = Path(d["zip"])
        bat = self._write_update_bat(src, zip_path)
        if not bat:
            return
        try:
            os.startfile(str(bat))            # 独立进程执行，不阻塞本程序退出
        except Exception as e:
            self._show_error(f"无法启动升级脚本: {e}")
            return
        self.status_var.set("升级脚本已启动，程序即将退出…")
        self.after(600, self.destroy)

    def _write_update_bat(self, src, zip_path):
        """生成"等本程序退出 → robocopy 覆盖 → 重启 → 清理"的批处理。"""
        try:
            appdir = Path(sys.executable).resolve().parent
            exe_name = Path(sys.executable).name
            exe_full = appdir / exe_name
            root = str(ROOT)
            lines = [
                "@echo off",
                "rem 使用系统默认编码（mbcs/GBK），避免中文路径在 chcp 65001 下解析异常",
                ":wait",
                f'tasklist /FI "IMAGENAME eq {exe_name}" | find /I "{exe_name}" >nul && (timeout /t 1 /nobreak >nul & goto wait)',
                f'robocopy "{src}" "{appdir}" /E /NFL /NDL /NJH /NJS /R:2 /W:1',
                "if errorlevel 8 (",
                "    echo 更新失败：robocopy 返回错误码 %errorlevel%",
                "    echo 请手动解压更新包替换文件",
                "    pause",
                "    exit /b 1",
                ")",
                f'start "" "{exe_full}"',
                f'rmdir /S /Q "{root}\\_update\\new"',
                f'del /Q "{zip_path}"',
                'del /Q "%~f0"',
            ]
            bat = UPDATE_DIR / "apply_update.bat"
            bat.write_text("\r\n".join(lines) + "\r\n", encoding="mbcs")
            return bat
        except Exception as e:
            self._show_error(f"生成升级脚本失败: {e}")
            return None

    @staticmethod
    def _vkey(s):
        """版本号字符串 → 可比较元组（1.10.0 > 1.9.0）。"""
        import re
        return tuple(int(x) if x.isdigit() else 0 for x in re.findall(r"\d+|[a-z]+", s.lower()))

    def _check_update(self):
        """通过 GitHub API 检查最新版本（后台线程，不阻塞 UI）。"""
        if self.worker.busy:
            messagebox.showinfo("HitranLab", "计算进行中，请稍候再检查更新")
            return
        self.status_var.set("正在检查更新…")
        if not self.worker.run(self._job_check_update):
            self.status_var.set("就绪")

    def _job_check_update(self):
        """后台检查更新，结果通过队列回传。"""
        import urllib.request
        import json
        try:
            url = "https://api.github.com/repos/LKF0402/hitran-mcp/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "HitranLab"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            latest = data.get("tag_name", "").lstrip("v")
            current = APP_VERSION.lstrip("v")
            has_update = bool(latest) and self._vkey(latest) > self._vkey(current)
            assets = {a.get("name"): a.get("browser_download_url")
                      for a in (data.get("assets") or [])}
            return {"kind": "check_update", "has_update": has_update,
                    "latest": latest, "current": current,
                    "body": data.get("body", "无")[:200],
                    "url": data.get("html_url", APP_REPO),
                    "asset_url": assets.get(UPDATE_ASSET)}
        except Exception as e:
            return {"kind": "check_update", "error": str(e)}


    def _show_api_key_config(self):
        """配置 HITRAN API key（保存到 Hitran_Data/hitran_api_key.txt，已 gitignore）。"""
        import os
        win = tk.Toplevel(self)
        win.title("配置 API key")
        win.geometry("480x260")
        win.configure(bg=self._bg)
        win.transient(self)
        win.grab_set()

        # 当前状态
        current_key = os.environ.get("HITRAN_API_KEY", "").strip()
        key_file = ROOT / "Hitran_Data" / "hitran_api_key.txt"
        if not current_key and key_file.exists():
            try:
                current_key = key_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass

        status_text = "已配置（环境变量）" if os.environ.get("HITRAN_API_KEY", "").strip() else \
                      ("已配置（文件）" if current_key else "未配置")
        status_color = "#34C759" if current_key else "#FF9500"
        ttk.Label(win, text=f"当前状态：{status_text}", background=self._bg,
                  foreground=status_color, font=("", 10, "bold")).pack(anchor="w", padx=16, pady=(16, 4))

        ttk.Label(win, text="HITRAN API key：", background=self._bg).pack(anchor="w", padx=16, pady=(8, 2))
        key_var = tk.StringVar(value=current_key)
        entry = ttk.Entry(win, textvariable=key_var, width=50, show="*")
        entry.pack(anchor="w", padx=16, fill="x")

        # 显示/隐藏切换
        show_var = tk.BooleanVar(value=False)
        def toggle_show():
            entry.config(show="" if show_var.get() else "*")
        ttk.Checkbutton(win, text="显示 key", variable=show_var, command=toggle_show).pack(anchor="w", padx=16, pady=(4, 0))

        ttk.Label(win, text="获取 key：注册 https://hitran.org 账号 → 用户个人资料页",
                  background=self._bg, foreground="#8A8A92", font=("", 9)).pack(anchor="w", padx=16, pady=(8, 0))

        def save():
            key = key_var.get().strip()
            try:
                (ROOT / "Hitran_Data").mkdir(parents=True, exist_ok=True)
                if key:
                    key_file.write_text(key, encoding="utf-8")
                    self.status_var.set("API key 已保存，立即生效")
                else:
                    if key_file.exists():
                        key_file.unlink()
                    self.status_var.set("API key 已清除")
            except Exception as e:
                self._show_error(f"保存失败: {e}")
            win.destroy()

        def clear():
            key_var.set("")

        btn_frame = ttk.Frame(win); btn_frame.pack(fill="x", padx=16, pady=16)
        ttk.Button(btn_frame, text="清除", command=clear).pack(side="left")
        ttk.Button(btn_frame, text="保存", command=save).pack(side="right")

    def _clear_line_cache(self):
        """清理线表缓存：删除 Hitran_Data/ 下的 .data/.header 文件，清空内存计算缓存。"""
        import shutil
        cache_dir = ROOT / "Hitran_Data"
        if not cache_dir.exists():
            messagebox.showinfo("清理缓存", "线表缓存目录不存在，无需清理。")
            return
        files = list(cache_dir.glob("*.data")) + list(cache_dir.glob("*.header"))
        total_size = sum(f.stat().st_size for f in files)
        if not files:
            messagebox.showinfo("清理缓存", "缓存目录为空，无需清理。")
            return
        if not messagebox.askyesno("清理线表缓存",
            f"将删除 {len(files)} 个缓存文件（{total_size/1024/1024:.1f} MB）。\n\n"
            f"清理后下次计算相同分子/窗口需要重新联网抓取线表。\n\n"
            f"确定清理吗？"):
            return
        try:
            deleted = 0
            for f in files:
                f.unlink()
                deleted += 1
            # 清空内存中的计算缓存
            _cache_warn = []
            try:
                from tools import hitran_mcp as hm
                hm.abs_cache_clear()
            except Exception as _e:
                _cache_warn.append(f"内存计算缓存清理失败: {_e}")
            try:
                from tools import hitran as ht
                ht.cache_clear()
            except Exception as _e:
                _cache_warn.append(f"线表缓存清理失败: {_e}")
            _warn_msg = ""
            if _cache_warn:
                _warn_msg = "\n\n注意（内存缓存）：\n" + "\n".join(f"• {w}" for w in _cache_warn)
            messagebox.showinfo("清理完成",
                f"已删除 {deleted} 个缓存文件。\n下次计算将重新联网抓取线表。{_warn_msg}")
            _status = f"已清理 {deleted} 个线表缓存文件"
            if _cache_warn:
                _status += f"（{len(_cache_warn)} 项内存缓存清理失败，见弹窗）"
            self.status_var.set(_status)
        except Exception as e:
            messagebox.showerror("清理失败", f"清理缓存时出错：{e}")


    def _switch_theme(self, theme=None):
        """切换浅色/深色主题，实时更新 UI。"""
        if theme is None:
            theme = "light" if self._theme == "dark" else "dark"
        if theme not in ("dark", "light"):
            return
        self._theme = theme
        c = self._get_colors(self._theme)     # 必须在 try 块之前定义，否则重着色全部 NameError 被吞
        # 重新应用样式
        self._build_style()
        # 更新窗口背景
        self.configure(bg=self._bg)
        # 更新左侧滚动画布背景
        if hasattr(self, 'left_cv'):
            self.left_cv.configure(bg=self._bg)
        # 更新 matplotlib 画布背景
        if hasattr(self, 'canvas'):
            self.canvas.get_tk_widget().configure(bg=self._bg)
            # 重绘当前图形（如果有）
            try:
                self.fig.patch.set_facecolor(self._bg)
                self.ax.set_facecolor(self._bg)
                # 重设坐标轴文字/tick/spines/图例颜色（rcParams 不回溯已有 artist）
                _tc = c["TEXT"]
                _bc = c["BORDER"]
                for _ax in self.fig.axes:
                    _ax.tick_params(colors=_tc, which="both")
                    _ax.xaxis.label.set_color(_tc)
                    _ax.yaxis.label.set_color(_tc)
                    if _ax.title:
                        _ax.title.set_color(_tc)
                    for _sp in _ax.spines.values():
                        _sp.set_color(_bc)
                    if _ax.get_legend():
                        _leg = _ax.get_legend()
                        _leg.get_frame().set_facecolor(c["SURFACE"])
                        _leg.get_frame().set_edgecolor(_bc)
                        for _t in _leg.get_texts():
                            _t.set_color(_tc)
                    # 重设网格线颜色（rcParams 不回溯已有 gridline）
                    for _gl in _ax.get_xgridlines() + _ax.get_ygridlines():
                        _gl.set_color(_bc)
                self._style_toolbar()
                self.canvas.draw()
            except Exception:
                pass
        # 更新菜单栏单选按钮状态
        if hasattr(self, '_var_theme'):
            self._var_theme.set(self._theme)
        # 保存到首选项（复用 _save_prefs，合并现有配置）
        try:
            import json as _json
            _p = {}
            if PREFS_PATH.exists():
                try:
                    _p = _json.loads(PREFS_PATH.read_text(encoding="utf-8"))
                except Exception:
                    pass
            _p["theme"] = self._theme
            self._save_prefs(_p)
        except Exception:
            pass
        # 更新 RoundedButton 颜色（计算按钮/停止按钮）
        if hasattr(self, 'btn_compute'):
            self.btn_compute.configure(bg=c["ACCENT"], hover_bg=c["ACCENT_H"])
        if hasattr(self, 'btn_stop'):
            stop_bg = c["SURFACE"] if self._theme == "dark" else c["SURFACE2"]
            stop_hover = c["SURFACE2"] if self._theme == "dark" else c["SURFACE3"]
            self.btn_stop.configure(bg=stop_bg, hover_bg=stop_hover,
                                     disabled_bg=stop_bg)
        # 更新 Listbox/Text 等直接设置颜色的控件
        for attr in ['layer_list', 'peak_text', 'xsc_text', 'stat_text']:
            widget = getattr(self, attr, None)
            if widget is not None:
                try:
                    widget.configure(bg=c["SURFACE"], fg=c["TEXT"])
                    if hasattr(widget, 'configure') and 'selectbackground' in widget.keys():
                        widget.configure(selectbackground=c["ACCENT"], selectforeground=c["TEXT"])
                except Exception:
                    pass
        self.status_var.set(f"已切换到{'浅色' if self._theme == 'light' else '深色'}模式")

    def _show_about(self):
        """关于对话框。"""
        win = tk.Toplevel(self)
        win.title("关于 HitranLab")
        win.geometry("380x280")
        win.configure(bg=self._bg)
        win.transient(self)
        win.grab_set()
        ttk.Label(win, text="HitranLab", font=("Microsoft YaHei", 18, "bold"),
                  foreground="#6B8FD4", background=self._bg).pack(pady=(24, 4))
        ttk.Label(win, text=f"版本 v{APP_VERSION}", background=self._bg, foreground="#8A8A92").pack()
        ttk.Label(win, text="HITRAN 光谱分析桌面工作站", background=self._bg).pack(pady=(8, 0))
        ttk.Label(win, text="基于 HITRAN2024 + HAPI 1.3.0.0 + TIPS-2025", background=self._bg,
                  foreground="#8A8A92", font=("Microsoft YaHei", 8)).pack(pady=(4, 0))
        ttk.Label(win, text="", background=self._bg).pack()
        ttk.Label(win, text=f"仓库: {APP_REPO}", background=self._bg, foreground="#6B8FD4",
                  font=("Microsoft YaHei", 8)).pack()
        ttk.Label(win, text="License: MIT", background=self._bg, foreground="#8A8A92",
                  font=("Microsoft YaHei", 8)).pack(pady=(2, 0))
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=16)

    # ───────────────────────── 工具 ─────────────────────────
    def _set_busy(self, busy, msg):
        self.status_label.configure(foreground="")
        self.status_var.set(msg or "就绪")
        if busy:
            self._prog = {"t0": time.time(), "done": 0, "total": 0}
        if hasattr(self, "progress"):
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=100,
                                    value=0)
        if hasattr(self, "eta_var"):
            self.eta_var.set("")
        if hasattr(self, "btn_compute"):
            self.btn_compute.configure(state="disabled" if busy else "normal")
        if hasattr(self, "btn_stop"):
            self.btn_stop.configure(state="normal" if busy else "disabled")
        self.update_idletasks()


def _read_hotw(path):
    """读两列 ν–σ 截面文件（跳过 #/空行/非数值行），返回 (nu, coef, header, skipped)。"""
    import numpy as np
    nu_l, coef_l, header, skipped = [], [], [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for ln in f:
            s = ln.strip()
            if not s:
                continue
            if s.startswith("#"):
                header.append(s)
                continue
            parts = s.replace(",", " ").split()
            if len(parts) < 2:
                skipped += 1
                continue
            try:
                nu_l.append(float(parts[0])); coef_l.append(float(parts[1]))
            except ValueError:
                skipped += 1
    return (np.asarray(nu_l), np.asarray(coef_l), header, skipped)


def _selftest(out_json):
    """无界面自检：验证引擎 + 数据 + 网络在打包环境内完整可用。"""
    import json, traceback
    try:
        import tools.hitran_mcp as hm
        sp = hm.t_species()
        st = hm.t_apikey_status()
        res = hm._compute([{"name": "CH4", "mole_frac": 1.0}],
                          numin=3025.0, numax=3040.0, T=296.0, P=1.0,
                          step=0.01, wingHW=50.0, mode="alpha",
                          path_length_cm=None, hitran_units=False, profile="voigt")
        peaks = res.get("peaks", {})
        top = sorted(peaks.items(), key=lambda kv: -kv[1]["peak_value"])[:3]
        def _l(v):
            return 0 if v is None else int(len(v))
        out = {
            "species_count": len(sp.get("species", {})),
            "apikey_status": st,
            "nu_points": _l(res.get("nu")),
            "total_len": _l(res.get("total")),
            "trans_len": _l(res.get("trans")),
            "top_peaks": [{"line": k, **v} for k, v in top],
            "warnings": [str(w) for w in (res.get("warnings") or [])][:5],
        }
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump({"error": traceback.format_exc()}, f, ensure_ascii=False, indent=2)
        raise SystemExit(2)


def main():
    import sys
    if "--selftest" in sys.argv:
        idx = sys.argv.index("--selftest")
        out_json = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "selftest.json"
        _selftest(out_json)
        return
    try:
        app = HitranLab()
        app.protocol("WM_DELETE_WINDOW", app._on_exit)
        app.mainloop()
    except Exception:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("HitranLab 启动失败", traceback.format_exc())


if __name__ == "__main__":
    main()
