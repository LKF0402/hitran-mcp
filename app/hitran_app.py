#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HitranLab —— HITRAN 光谱分析桌面工作站（Windows）。

复用 tools/hitran_mcp.py 的取数/计算引擎（同一套物理纪律与防呆），
提供本地 GUI：多组分吸收谱 / 透过率 / 截面谱计算与绘图、强线列表、
配分函数、截面文件（HOTW）导入、CSV/PNG 导出。

运行:  python app/hitran_app.py
打包:  PyInstaller（见 README 或本文件底部注释）
"""
import os
import queue
import sys
import threading
import traceback
import ctypes
from pathlib import Path

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
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

# 叠加模式的颜色循环（每次叠加取下一个颜色）
OVERLAY_COLORS = ["#F7768E", "#7AA2F7", "#9ECE6A", "#E0AF68", "#BB9AF7", "#7DCFFF", "#FF9E64", "#4ABCF9"]

MODES = {"吸收系数 α (cm⁻¹)": "alpha",
         "透过率 T": "transmittance",
         "两者 both": "both",
         "截面 σ (cm²/molecule)": "sigma"}
DEFAULT_W = 1280
DEFAULT_H = 880


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


class Worker:
    """后台线程：不阻塞 GUI。result_queue 收到 (tag, payload)。
    支持 busy 互斥（防止重复提交）与 cancel（长循环可中途退出）。"""

    def __init__(self):
        self.q = queue.Queue()
        self.cancel_event = threading.Event()
        self._busy = False
        self._lock = threading.Lock()

    @property
    def busy(self):
        return self._busy

    def run(self, fn, *args, **kw):
        """提交任务。已有任务在跑时返回 False（不提交）。"""
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            self.cancel_event.clear()

        def target():
            try:
                result = fn(*args, **kw)
                if not self.cancel_event.is_set():
                    self.q.put(("ok", result))
            except Exception as e:
                if not self.cancel_event.is_set():
                    self.q.put(("err", f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=4)}"))
            finally:
                with self._lock:
                    self._busy = False

        threading.Thread(target=target, daemon=True).start()
        return True

    def cancel(self):
        """请求取消当前任务。HAPI 单次阻塞调用无法中断，
        但多步循环（Q(T) 扫描）会在每步检查 cancel_event。"""
        self.cancel_event.set()


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
        self._mix_rows = []             # [{"name","mole_frac"}]

        self._build_style()
        self._build_ui()
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
    def _build_style(self):
        """现代深色主题（Tokyo Night 风格）。"""
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        BG       = "#1A1B26"   # 主背景
        SURFACE  = "#24283B"   # 面板
        SURFACE2 = "#2E3347"   # 输入框/悬停
        ACCENT   = "#7AA2F7"   # 强调蓝
        ACCENT_H = "#9DBBFF"   # 强调蓝悬停
        GREEN    = "#9ECE6A"   # 成功绿
        TEXT     = "#C0CAF5"   # 主文字
        TEXT_DIM = "#7A82A0"   # 次要文字
        BORDER   = "#3B4261"   # 边框

        self._bg, self._surface, self._accent = BG, SURFACE, ACCENT
        self.configure(bg=BG)

        # 全局
        style.configure(".", background=BG, foreground=TEXT,
                        fieldbackground=SURFACE2, bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER,
                        font=("Microsoft YaHei UI", 10))

        # Frame / PanedWindow
        style.configure("TFrame", background=BG)
        style.configure("TPanedwindow", background=BG)

        # LabelFrame（卡片）
        style.configure("TLabelframe", background=BG, bordercolor=BORDER,
                        relief="solid", borderwidth=1)
        style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                        font=("Microsoft YaHei UI", 10, "bold"))

        # Label
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Dim.TLabel", background=BG, foreground=TEXT_DIM,
                        font=("Microsoft YaHei UI", 9))

        # 普通按钮
        style.configure("TButton", background=SURFACE, foreground=TEXT,
                        bordercolor=BORDER, focusthickness=0, padding=(10, 5),
                        font=("Microsoft YaHei UI", 9))
        style.map("TButton",
                  background=[("active", SURFACE2), ("pressed", ACCENT)],
                  foreground=[("active", TEXT), ("pressed", BG)])

        # 主按钮（强调色）
        style.configure("Accent.TButton", background=ACCENT, foreground=BG,
                        bordercolor=ACCENT, padding=(12, 8),
                        font=("Microsoft YaHei UI", 10, "bold"))
        style.map("Accent.TButton",
                  background=[("active", ACCENT_H), ("pressed", "#5B85D6")],
                  foreground=[("active", BG)])

        # Entry
        style.configure("TEntry", fieldbackground=SURFACE2, foreground=TEXT,
                        insertcolor=TEXT, bordercolor=BORDER, padding=5)

        # Combobox
        style.configure("TCombobox", fieldbackground=SURFACE2, foreground=TEXT,
                        background=SURFACE, arrowcolor=ACCENT, bordercolor=BORDER,
                        padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", SURFACE2),
                                                  ("active", SURFACE2)])

        # Notebook
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=SURFACE, foreground=TEXT_DIM,
                        padding=(18, 7), font=("Microsoft YaHei UI", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", SURFACE2)],
                  foreground=[("selected", ACCENT)])

        # Treeview
        style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE,
                        foreground=TEXT, bordercolor=BORDER, rowheight=26)
        style.configure("Treeview.Heading", background=SURFACE2, foreground=ACCENT,
                        font=("Microsoft YaHei UI", 9, "bold"), relief="flat")
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", BG)])

        # Scrollbar
        style.configure("Vertical.TScrollbar", background=SURFACE, troughcolor=BG,
                        bordercolor=BORDER, arrowcolor=TEXT_DIM)
        style.configure("Horizontal.TScrollbar", background=SURFACE, troughcolor=BG,
                        bordercolor=BORDER, arrowcolor=TEXT_DIM)

        # Checkbutton
        style.configure("TCheckbutton", background=BG, foreground=TEXT)
        style.map("TCheckbutton", background=[("active", BG)])

        # matplotlib 深色配色
        mpl.rcParams.update({
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "axes.edgecolor": BORDER,
            "axes.labelcolor": TEXT,
            "xtick.color": TEXT_DIM,
            "ytick.color": TEXT_DIM,
            "grid.color": "#252840",
            "grid.linestyle": "--",
            "grid.alpha": 0.6,
            "text.color": TEXT,
            "axes.titlecolor": TEXT,
            "legend.facecolor": SURFACE,
            "legend.edgecolor": BORDER,
            "legend.labelcolor": TEXT,
        })

    def _style_toolbar(self):
        """matplotlib 工具栏（tk.Button）深色主题适配。"""
        self.toolbar_frame.configure(style="TFrame")
        for child in self.toolbar.winfo_children():
            if isinstance(child, tk.Button):
                child.configure(bg=self._surface, fg=self._accent,
                                activebackground="#2E3347", activeforeground="#9DBBFF",
                                relief="flat", bd=0, padx=4, pady=2, highlightthickness=0,
                                cursor="hand2")
            elif isinstance(child, tk.Label):
                child.configure(bg=self._surface, fg=self._text_dim if hasattr(self, "_text_dim") else "#7A82A0")
        self.toolbar.configure(bg=self._surface)

    def _build_ui(self):
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
        self.mol_cb = ttk.Combobox(f0, textvariable=self.mol_var, width=20, state="readonly")
        self.mol_cb.grid(row=0, column=1, sticky="we", padx=(4, 0))
        ttk.Label(f0, text="窗口 ν (cm⁻¹):").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.numin_var, self.numax_var = tk.StringVar(value="2950.0"), tk.StringVar(value="3120.0")
        self.step_var = tk.StringVar(value="0.01")
        e = ttk.Entry(f0, textvariable=self.numin_var, width=8); e.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        ttk.Label(f0, text="—").grid(row=1, column=2)
        ttk.Entry(f0, textvariable=self.numax_var, width=8).grid(row=1, column=3, sticky="w")
        ttk.Label(f0, text="步长:").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(f0, textvariable=self.step_var, width=8).grid(row=2, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        ttk.Label(f0, text="同位素:").grid(row=3, column=0, sticky="w", pady=(4, 0))
        self.iso_var = tk.StringVar(value="主同位素")
        self.iso_cb = ttk.Combobox(f0, textvariable=self.iso_var, width=20, state="readonly")
        self.iso_cb.grid(row=3, column=1, columnspan=3, sticky="we", padx=(4, 0), pady=(4, 0))
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
        ttk.Entry(f1, textvariable=self.L_var, width=10).grid(row=2, column=1, sticky="w", padx=(4, 0), pady=(4, 0))

        # 计算选项
        f2 = ttk.LabelFrame(inner, text="计算选项", padding=8)
        f2.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f2, text="输出:").grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value="吸收系数 α (cm⁻¹)")
        ttk.Combobox(f2, textvariable=self.mode_var, values=list(MODES), width=20, state="readonly").grid(row=0, column=1, padx=(4, 0))
        ttk.Label(f2, text="线型:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.profile_var = tk.StringVar(value="voigt")
        ttk.Combobox(f2, textvariable=self.profile_var, values=PROFILES, width=20, state="readonly").grid(row=1, column=1, padx=(4, 0), pady=(4, 0))
        self.ylog_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(f2, text="对数轴 (ylog)", variable=self.ylog_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(f2, text="翼宽 wingHW:").grid(row=3, column=0, sticky="w", pady=(4, 0))
        self.winghw_var = tk.StringVar(value="50.0")
        ttk.Entry(f2, textvariable=self.winghw_var, width=10).grid(row=3, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        ttk.Label(f2, text="强度截断:").grid(row=4, column=0, sticky="w", pady=(4, 0))
        self.cutoff_var = tk.StringVar(value="")
        ttk.Entry(f2, textvariable=self.cutoff_var, width=10).grid(row=4, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        ttk.Label(f2, text="(cm⁻¹/(mol·cm⁻²), 空=不截断)", foreground="#7A82A0").grid(row=5, column=0, columnspan=2, sticky="w")

        # 高级选项
        f2b = ttk.LabelFrame(inner, text="高级选项", padding=8)
        f2b.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f2b, text="强线 TOP N:").grid(row=0, column=0, sticky="w")
        self.topn_var = tk.StringVar(value="15")
        ttk.Entry(f2b, textvariable=self.topn_var, width=8).grid(row=0, column=1, sticky="w", padx=(4, 0))
        ttk.Label(f2b, text="Q(T) 范围:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        qframe = ttk.Frame(f2b)
        qframe.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(4, 0))
        self.qtmin_var = tk.StringVar(value="200")
        self.qtmax_var = tk.StringVar(value="400")
        self.qtstep_var = tk.StringVar(value="20")
        ttk.Entry(qframe, textvariable=self.qtmin_var, width=6).pack(side="left")
        ttk.Label(qframe, text="–", foreground="#7A82A0").pack(side="left", padx=2)
        ttk.Entry(qframe, textvariable=self.qtmax_var, width=6).pack(side="left")
        ttk.Label(qframe, text="K  步长", foreground="#7A82A0").pack(side="left", padx=(4, 2))
        ttk.Entry(qframe, textvariable=self.qtstep_var, width=5).pack(side="left")

        # 混合气
        f3 = ttk.LabelFrame(inner, text="混合气组分（浓度留空 = 纯气体）", padding=8)
        f3.pack(fill=tk.X, pady=(0, 6))
        mix_frame = ttk.Frame(f3)
        mix_frame.grid(row=0, column=0, columnspan=3, sticky="we")
        self.mix_tree = ttk.Treeview(mix_frame, columns=("name", "x"), show="headings", height=5)
        self.mix_tree.heading("name", text="分子"); self.mix_tree.column("name", width=120)
        self.mix_tree.heading("x", text="摩尔分数"); self.mix_tree.column("x", width=90)
        self.mix_tree.pack(side="left", fill="both", expand=True)
        mix_vsb = ttk.Scrollbar(mix_frame, orient="vertical", command=self.mix_tree.yview)
        mix_vsb.pack(side="right", fill="y")
        self.mix_tree.configure(yscrollcommand=mix_vsb.set)
        self.frac_var = tk.StringVar(value="")
        ttk.Entry(f3, textvariable=self.frac_var, width=10).grid(row=1, column=0, sticky="w", pady=(4, 0))
        ttk.Button(f3, text="添加组分", command=self._add_mix).grid(row=1, column=1, padx=(4, 0), pady=(4, 0))
        ttk.Button(f3, text="删除选中", command=self._del_mix).grid(row=1, column=2, padx=(4, 0), pady=(4, 0))
        f3.columnconfigure(0, weight=1)

        # 动作按钮
        fb = ttk.Frame(inner)
        fb.pack(fill=tk.X, pady=(0, 6))
        self.btn_compute = ttk.Button(fb, text="▶  计算并绘图", style="Accent.TButton",
                                       command=self._compute_and_plot)
        self.btn_compute.pack(fill=tk.X, pady=(0, 4))
        self.btn_stop = ttk.Button(fb, text="■  停止计算", command=self._stop_compute,
                                    state="disabled")
        self.btn_stop.pack(fill=tk.X, pady=(0, 6))
        fbg = ttk.Frame(fb)
        fbg.pack(fill=tk.X)
        acts = [("强线 TOP N", self._lines), ("配分函数", self._partition),
                ("Q(T) 曲线", self._qcurve), ("导出 CSV", self._export_csv),
                ("导出 PNG", self._export_png), ("截面文件", self._pick_xsc),
                ("清空图", self._clear_plot), ("重置参数", self._reset_params)]
        for i, (txt, cmd) in enumerate(acts):
            ttk.Button(fbg, text=txt, command=cmd).grid(row=i // 2, column=i % 2,
                                                        sticky="we", padx=2, pady=2)
        fbg.columnconfigure(0, weight=1); fbg.columnconfigure(1, weight=1)

        # 截面导入
        f4 = ttk.LabelFrame(inner, text="截面文件（HOTW，xsc 下载）", padding=8)
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
        self.ax.set_xlabel("Wavenumber (cm⁻¹)")
        self.ax.set_ylabel("Absorption coefficient α (cm⁻¹)")
        self.ax.grid(alpha=0.4, lw=0.6)
        self.ax.text(0.5, 0.5, "设置参数后点击「计算并绘图」", ha="center", va="center",
                     transform=self.ax.transAxes, color="#7A82A0", fontsize=13)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().configure(bg=self._bg)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=(0, 0), pady=(0, 2))

        # matplotlib 导航工具栏（缩放/平移/取点/保存）
        self.toolbar_frame = ttk.Frame(right)
        self.toolbar_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 4))
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame)
        self.toolbar.update()
        self._style_toolbar()

        self.nb = ttk.Notebook(right)
        self.nb.pack(fill=tk.BOTH, expand=True)
        # 峰统计
        self.peak_tab = ttk.Frame(self.nb)
        self.nb.add(self.peak_tab, text="峰 / 统计")
        peak_frame = ttk.Frame(self.peak_tab)
        peak_frame.pack(fill=tk.BOTH, expand=True)
        self.peak_text = tk.Text(peak_frame, height=7, font=("Consolas", 10),
                                  bg="#24283B", fg="#C0CAF5", insertbackground="#C0CAF5",
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
        self.line_tree = ttk.Treeview(line_frame, columns=("nu", "S", "gair", "E"), show="headings", height=7)
        for c, t, w in (("nu", "ν (cm⁻¹)", 110), ("S", "S (cm/molecule)", 130),
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
                                 bg="#24283B", fg="#C0CAF5", insertbackground="#C0CAF5",
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
                                  bg="#24283B", fg="#C0CAF5", insertbackground="#C0CAF5",
                                  relief="flat", borderwidth=0, padx=8, pady=6)
        self.stat_text.pack(side="left", fill=tk.BOTH, expand=True)
        stat_vsb = ttk.Scrollbar(stat_frame, orient="vertical", command=self.stat_text.yview)
        stat_vsb.pack(side="right", fill="y")
        self.stat_text.configure(yscrollcommand=stat_vsb.set)
        self.stat_text.insert("1.0", "显示计算日志、线表下载状态和引擎警告。\n\n"
                                     "四个标签页用途：\n"
                                     "  峰/统计 — 计算后自动显示峰值、积分、警告\n"
                                     "  强线列表 — 点左侧「强线 TOP N」后显示最强谱线\n"
                                     "  截面文件信息 — 导入 HOTW 截面文件后显示元数据\n"
                                     "  运行状态 — 计算日志和引擎状态")

        # 底部状态栏（文字 + 进度条）
        sb = ttk.Frame(self)
        sb.pack(fill=tk.X, padx=10, pady=(0, 6))
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = ttk.Label(sb, textvariable=self.status_var, anchor="w",
                                       style="Dim.TLabel")
        self.status_label.pack(side="left", fill=tk.X, expand=True)
        self.progress = ttk.Progressbar(sb, mode="indeterminate", length=120)
        self.progress.pack(side="right", padx=(8, 0))

    # ───────────────────────── 数据加载 ─────────────────────────
    def _load_species(self):
        def job():
            s = hm.t_species()["species"]
            return {"kind": "species", "data": {f: e["M"] for f, e in s.items()}}
        self.status_var.set("加载官方分子表…")
        self.worker.run(job)

    def _load_isotopologues(self):
        """分子改变时加载该分子的同位素列表。"""
        name = self.mol_var.get().strip()
        if not name:
            self.iso_cb["values"] = []
            self.iso_var.set("")
            return
        try:
            info = hm.t_species(name, with_isotopologues=True)
            isos = info.get("isotopologues", [])
            labels = []
            self._iso_map = {}
            for iso in isos:
                label = f"{iso['name']} ({iso['abundance']*100:.2f}%)"
                labels.append(label)
                self._iso_map[label] = iso["I"]
            self.iso_cb["values"] = labels
            if labels:
                self.iso_var.set(labels[0])  # 默认主同位素（丰度最高，已排序）
            else:
                self.iso_var.set("")
        except Exception as e:
            self.iso_cb["values"] = []
            self.iso_var.set("主同位素")

    # ───────────────────────── 交互 ─────────────────────────
    def _add_mix(self):
        name = self.mol_var.get().strip().upper()
        if not name:
            messagebox.showwarning("HitranLab", "请先选择分子")
            return
        x = self.frac_var.get().strip()
        try:
            xf = float(x) if x else None
            if xf is not None and not (0 < xf <= 1):
                raise ValueError
        except ValueError:
            messagebox.showwarning("HitranLab", "摩尔分数需在 (0,1] 区间或留空（纯气体）")
            return
        self.mix_tree.insert("", "end", values=(name, xf if xf is not None else "1 (纯)"))
        self.frac_var.set("")

    def _del_mix(self):
        sel = self.mix_tree.selection()
        for i in sel:
            self.mix_tree.delete(i)

    def _clear_plot(self):
        """只清空画布，不改变参数。重置叠加计数器和数据。"""
        self._overlay_count = 0
        self._overlay_data = []
        self._last_fig_data = None
        self.ax.clear()
        self.ax.set_xlabel("Wavenumber (cm⁻¹)")
        self.ax.set_ylabel("Absorption coefficient α (cm⁻¹)")
        self.ax.grid(alpha=0.4, lw=0.6)
        self.ax.text(0.5, 0.5, "设置参数后点击「计算并绘图」", ha="center", va="center",
                     transform=self.ax.transAxes, color="#7A82A0", fontsize=13)
        self.fig.tight_layout()
        self.canvas.draw()
        # 清空峰统计和强线列表
        if hasattr(self, "peak_text"):
            self.peak_text.delete("1.0", tk.END)
            self.peak_text.insert("1.0", "（清空画布后无数据）")
        if hasattr(self, "line_tree"):
            self.line_tree.delete(*self.line_tree.get_children())
        self.status_var.set("画布已清空")

    def _reset_params(self):
        self.mol_var.set("CH4")
        self._load_isotopologues()
        self.numin_var.set("2950.0")
        self.numax_var.set("3120.0")
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
        self._overlay_count = 0
        self._overlay_data = []
        self._last_fig_data = None
        self.ax.clear()
        self.ax.set_xlabel("Wavenumber (cm⁻¹)")
        self.ax.set_ylabel("Absorption coefficient α (cm⁻¹)")
        self.ax.grid(alpha=0.4, lw=0.6)
        self.ax.text(0.5, 0.5, "设置参数后点击「计算并绘图」", ha="center", va="center",
                     transform=self.ax.transAxes, color="#7A82A0", fontsize=13)
        self.canvas.draw()
        self._last_fig_data = None
        self._last_lines_data = None
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
            x = v[1]
            xf = float(x) if x and x != "1 (纯)" else None
            rows.append({"name": str(v[0]).strip().upper(), "mole_frac": xf})
        return rows

    def _selected_iso(self):
        """返回当前选中的同位素 I 值；主同位素或未选返回 None。"""
        label = self.iso_var.get().strip()
        if not label or label == "主同位素":
            return None
        if hasattr(self, "_iso_map") and label in self._iso_map:
            return self._iso_map[label]
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
        if L <= 0:
            raise ValueError("光程 L 必须 > 0 cm")
        mode = MODES[self.mode_var.get()]
        profile = self.profile_var.get()
        ylog = self.ylog_var.get()
        hitran_units = mode == "sigma"
        wingHW = f(self.winghw_var.get(), "wingHW")
        if wingHW <= 0:
            raise ValueError("翼宽 wingHW 必须 > 0")
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
    def _compute_and_plot(self):
        if self.worker.busy:
            messagebox.showinfo("HitranLab", "计算进行中，请稍候或点击「停止计算」")
            return
        try:
            specs, numin, numax, T, P, step, mode, profile, L, ylog, hunits, wingHW, cutoff = self._params()
        except ValueError as e:
            self._show_error(str(e))
            return
        if mode == "alpha":
            cmode = "alpha"
        elif mode == "sigma":
            cmode = "alpha"
        elif mode == "transmittance":
            cmode = "transmittance"
        else:
            cmode = "both"
        path_cm = L if cmode in ("transmittance", "both") else None
        self._set_busy(True, "计算谱线…")
        self.worker.run(self._job_spectrum, specs, numin, numax, T, P, step,
                        cmode, profile, path_cm, hunits, ylog, wingHW, cutoff)

    def _job_spectrum(self, specs, numin, numax, T, P, step, cmode, profile, path_cm, hunits, ylog, wingHW, cutoff):
        res = hm._compute(specs, numin, numax, T=T, P=P, step=step, wingHW=wingHW,
                          mode=cmode, path_length_cm=path_cm, hitran_units=hunits,
                          profile=profile, intensity_cutoff=cutoff)
        label = "+".join(res["per"].keys())
        return {"kind": "spectrum", "res": res, "label": label,
                "mode": cmode, "hitran_units": hunits, "ylog": ylog,
                "specs": specs, "profile": profile}

    def _lines(self):
        if self.worker.busy:
            messagebox.showinfo("HitranLab", "计算进行中，请稍候")
            return
        try:
            specs, numin, numax, T, P, step, mode, profile, L, ylog, hunits, _w, _c = self._params()
            name = specs[0]["name"]
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
        self.worker.run(self._job_lines, name, numin, numax, top_n)

    def _job_lines(self, name, numin, numax, top_n=15):
        # 取窗口内全部线（top_n 设大），GUI 只显示 top_n，完整数据供导出
        data = hm.t_lines(name, numin, numax, top_n=100000)
        data["display_top_n"] = top_n
        return {"kind": "lines", "data": data}

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
                    messagebox.showerror("HitranLab", payload)
                else:
                    self._render(payload)
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
            self.mol_cb["values"] = sorted(d["data"].keys())
            if "CH4" in d["data"]:
                self.mol_var.set("CH4")
            self.status_var.set(f"已加载官方分子表（{len(d['data'])} 种）")
            self._load_isotopologues()
            return
        if kind == "spectrum":
            self._render_spectrum(d)
        elif kind == "lines":
            self._render_lines(d["data"])
        elif kind == "partition":
            self._render_partition(d["data"])
        elif kind == "qcurve":
            self._render_qcurve(d)
        elif kind == "xsc":
            self._render_xsc(d)

    def _render_spectrum(self, d):
        res = d["res"]
        nu, per, total = res["nu"], res["per"], res["total"]
        self._last_fig_data = d
        ax = self.ax
        first_draw = (self._overlay_count == 0)

        # 统一标签格式：分子 波段 T P
        tag = f"{d['label']} {float(res['numin']):g}-{float(res['numax']):g} T={res['T']:g}K P={res['P']:g}atm"
        self._overlay_data.append({"tag": tag, "data": d})

        if first_draw:
            ax.clear()  # 首次绘制清空提示文字

        unit_lab = ("Cross section σ (cm²/molecule)" if d["hitran_units"]
                    else "Absorption coefficient α (cm⁻¹)")
        show_t = res.get("trans") is not None

        if first_draw:
            # 首次绘制：画各组分 + TOTAL，图例含参数标签
            if show_t:
                ax.plot(nu, res["trans"], color="#7AA2F7", lw=1.4, label=f"{tag} transmittance")
                ylab = "Transmittance"
            else:
                for lab, c in per.items():
                    ax.plot(nu, c, lw=0.9, alpha=0.85, label=f"{tag} {lab}")
                if len(per) > 1:
                    ax.plot(nu, total, color="#F7768E", lw=1.5, label=f"{tag} TOTAL")
                ylab = unit_lab
            if d["ylog"]:
                ax.set_yscale("log")
            ax.set_xlabel("Wavenumber (cm⁻¹)")
            ax.set_ylabel(ylab)
            ax.set_title(tag, fontsize=10, pad=10)
            ax.grid(alpha=0.4, lw=0.6)
            ax.legend(fontsize=7, framealpha=0.9)
            if not d["ylog"] and not show_t:
                ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
        else:
            # 叠加绘制：只画 total（或单组分），用循环颜色
            color = OVERLAY_COLORS[(self._overlay_count - 1) % len(OVERLAY_COLORS)]
            if show_t:
                ydata = res["trans"]
                ylab = "Transmittance"
            else:
                ydata = total if len(per) > 1 else list(per.values())[0]
                ylab = unit_lab
            ax.plot(nu, ydata, color=color, lw=1.4, label=tag)
            ax.set_ylabel(ylab)
            ax.legend(fontsize=7, framealpha=0.9)
            ax.set_title("叠加对比", fontsize=11, pad=10)

        self._overlay_count += 1
        self.fig.tight_layout()
        self.canvas.draw()

        # 峰统计
        txt = []
        for lab, pk in res["peaks"].items():
            txt.append(f"[{lab}] 峰值 {pk['peak_value']:.4g} @ {pk['peak_nu']:.3f} cm⁻¹  "
                       f"(窗口内积分 {pk['integral']:.4g})")
        if len(per) > 1 and "total_peak" in res:
            tp = res["total_peak"]
            txt.append(f"[TOTAL] 峰值 {tp['peak_value']:.4g} @ {tp['peak_nu']:.3f} cm⁻¹  "
                       f"(积分 {tp['integral']:.4g})")
        for w in res.get("warnings", []):
            txt.append(f"! {w}")
        if res.get("trans") is not None:
            tm = res["trans"]
            i = int(tm.argmin())
            txt.append(f"[透过率] 谷值 {float(tm[i]):.4g} @ {float(nu[i]):.3f} cm⁻¹ "
                       f"(L={res.get('path_length_cm', 1.0):g} cm)")
        self.peak_text.delete("1.0", tk.END)
        self.peak_text.insert("1.0", "\n".join(txt) if txt else "（无峰/无警告）")

    def _render_lines(self, data):
        self._last_lines_data = data
        self.line_tree.delete(*self.line_tree.get_children())
        all_lines = data.get("lines", [])
        display_n = data.get("display_top_n", 15)
        display = all_lines[:display_n]
        for ln in display:
            self.line_tree.insert("", "end", values=(
                f"{ln['nu_cm-1']:.4f}", f"{ln['S_cm_per_molecule']:.3e}",
                f"{ln['gamma_air']:.4f}", f"{ln['E_lower_cm-1']:.2f}"))
        w = data.get("warning")
        if w:
            self.status_var.set("强线完成：窗口内 0 条？见提示")
            messagebox.showinfo("HitranLab", w)
        else:
            self.status_var.set(f"强线完成：窗口内 {data.get('n_in_window', 0)} 条，显示最强 {len(display)} 条（完整数据可导出）")
        self.nb.select(self.line_tab)

    def _render_partition(self, data):
        self.peak_text.delete("1.0", tk.END)
        self.peak_text.insert("1.0",
            f"配分函数 Q({data['T']:g} K) = {data['Q']:.6g}\n"
            f"分子 {data['molecule']} (M={data['M']}, I={data['I']}) · TIPS-{data['tips_version']}\n")
        self.nb.select(self.peak_tab)
        self.status_var.set(f"Q({data['T']:g} K) = {data['Q']:.6g}")

    def _render_qcurve(self, d):
        ax = self.ax
        ax.clear()
        ax.plot(d["Ts"], d["Qs"], "o-", color="#9ECE6A", lw=1.5, markersize=5)
        ax.set_xlabel("Temperature T (K)")
        ax.set_ylabel("Partition function Q(T)")
        ax.set_title(f"{d['name']}  Q(T)  TIPS-2025", fontsize=11, pad=10)
        ax.grid(alpha=0.4, lw=0.6)
        self.fig.tight_layout()
        self.canvas.draw()
        self._last_fig_data = {"kind": "qcurve", "name": d["name"]}
        self.status_var.set(f"Q(T) 曲线：{d['Ts'][0]}–{d['Ts'][-1]} K")

    def _render_xsc(self, d):
        nu, coef = d["nu"], d["coef"]
        ax = self.ax
        ax.clear()
        if nu is not None and len(nu):
            ax.plot(nu, coef, lw=1.0, color="#BB9AF7")
            ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
        ax.set_xlabel("Wavenumber (cm⁻¹)")
        ax.set_ylabel("Cross section σ (cm²/molecule)")
        ax.set_title(Path(d["path"]).name, fontsize=11, pad=10)
        ax.grid(alpha=0.4, lw=0.6)
        self.fig.tight_layout()
        self.canvas.draw()
        self._last_fig_data = d
        out = d["out"]
        self.xsc_text.delete("1.0", tk.END)
        self.xsc_text.insert("1.0",
            f"文件: {d['path']}\n"
            f"数据点: {out.get('n_points_file')}（窗口内 {out.get('n_points_in_window')}）\n"
            f"峰值 σ: {out.get('peak')}\n"
            f"产物: {out.get('png')}\n      {out.get('csv')}\n"
            + ("".join(f"! {w}\n" for w in out.get("warnings", []))))
        self.nb.select(self.xsc_tab)
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
            messagebox.showinfo("HitranLab", "请先点击「强线 TOP N」获取线表")
            return
        data = self._last_lines_data
        lines = data.get("lines", [])
        if not lines:
            messagebox.showinfo("HitranLab", "窗口内无谱线")
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv",
                                         filetypes=[("CSV", "*.csv")],
                                         initialfile=f"{data.get('molecule','lines')}_linelist.csv")
        if not p:
            return
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(f"# HitranLab line list · {data.get('molecule','')} (M={data.get('M','')}, iso={data.get('iso','')})\n")
            f.write(f"# window: {data.get('coverage_cm-1',['?','?'])[0]}-{data.get('coverage_cm-1',['?','?'])[1]} cm-1\n")
            f.write(f"# n_in_window: {data.get('n_in_window',0)}\n")
            f.write("nu_cm-1,S_cm_per_molecule,gamma_air,E_lower_cm-1\n")
            for ln in lines:
                f.write(f"{ln['nu_cm-1']:.6f},{ln['S_cm_per_molecule']:.6e},"
                        f"{ln['gamma_air']:.6f},{ln['E_lower_cm-1']:.4f}\n")
        self.status_var.set(f"线表已导出 ({len(lines)} 条): {p}")
        messagebox.showinfo("HitranLab", f"完整线表已导出 ({len(lines)} 条):\n{p}")

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
        hitran_units = datasets[0]["data"]["hitran_units"]

        header = "# HitranLab export · HITRAN2024 via HAPI 1.3.0.0 · TIPS-2025\n"
        header += f"# {len(datasets)} dataset(s) overlaid\n"
        header += ("# units: sigma cm2/molecule\n" if hitran_units else "# units: alpha cm-1\n")

        # 列：波数 + 每个数据集的 total（或单组分）
        cols = ["nu_cm-1"]
        data_cols = []
        for ds in datasets:
            tag = ds["tag"]
            res = ds["data"]["res"]
            per = res["per"]
            if len(per) > 1 and res.get("total") is not None:
                cols.append(f"{tag}_total")
                data_cols.append(res["total"])
            else:
                first_key = list(per.keys())[0]
                cols.append(f"{tag}_{first_key}")
                data_cols.append(per[first_key])

        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(header)
            f.write(",".join(cols) + "\n")
            for i in range(len(nu)):
                row = [f"{nu[i]:.6f}"] + [f"{c[i]:.6e}" for c in data_cols]
                f.write(",".join(row) + "\n")

        self.status_var.set(f"CSV 已导出 ({len(datasets)} 组数据): {p}")
        messagebox.showinfo("HitranLab", f"CSV 已导出 ({len(datasets)} 组数据):\n{p}")

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
        """请求停止当前计算。HAPI 单次调用无法中断，Q(T) 扫描等多步循环可中途退出。"""
        if self.worker.busy:
            self.worker.cancel()
            self.status_var.set("已请求停止…")

    def _show_error(self, msg):
        """状态栏红字提示错误，不弹窗打断。"""
        self.status_label.configure(foreground="#F7768E")
        self.status_var.set(f"✗ {msg}")
        self.after(5000, self._restore_status)

    def _restore_status(self):
        self.status_label.configure(foreground="")
        if not self.worker.busy:
            self.status_var.set("就绪")

    # ───────────────────────── 工具 ─────────────────────────
    def _set_busy(self, busy, msg):
        self.status_label.configure(foreground="")
        self.status_var.set(msg if busy else "就绪")
        if hasattr(self, "progress"):
            if busy:
                self.progress.start(10)
            else:
                self.progress.stop()
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
        res = hm._compute([{"name": "CH4", "mole_frac": 1.0}], 3025.0, 3040.0, 296.0, 1.0, 0.01, 0.1, "alpha", 100.0, True, "voigt")
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
        app.mainloop()
    except Exception:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("HitranLab 启动失败", traceback.format_exc())


if __name__ == "__main__":
    main()
