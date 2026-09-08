# hitran-mcp

> 让 AI 直接调用 [HITRAN](https://hitran.org) 数据库：查谱线、算截面、画谱图。
> 一个纯标准库实现的 **MCP 服务器**（stdio），数据实时取自 HITRANonline（经官方 HAPI），本地不预置任何谱数据。

[English](#english) | 中文

**7 个工具覆盖全链路**：物种查询（官方 ISO 表，含同位素丰度）→ 线表抓取 → 强线列表（选线/干扰分析）→ 单/混合气吸收·透过率谱 → 谱图绘制 → 配分函数 → 截面文件（HOTW）读入分析。

把 HITRAN 数据库的**取数、谱计算、绘图**封装成 AI 可直接调用的 MCP 服务器。
数据全部**实时取自 HITRANonline（经官方 HAPI 1.3.0.0）**，本地不预置任何谱数据；
物种表、同位素丰度也直接读 HAPI 官方 ISO 表，无硬编码白名单。

## 一、包含文件

```
hitran-mcp-kit/
├─ README.md                    # 本文件
├─ mcp.config.example.json      # MCP 客户端注册片段（改路径后合入你的配置）
└─ tools/
   ├─ hitran_mcp.py             # ★ MCP 服务器本体（stdio JSON-RPC，纯标准库）
   ├─ hitran.py                 # 官方 HAPI 的统一薄封装（防呆护栏 + 溯源水印）
   └─ __init__.py
```

运行期自动生成（不用打包、可随时删）：
- `Hitran_Data/` — 线表缓存（体大，可由 fetch 重生）
- `tmp/mcp_out/` — 工具产物（CSV/PNG，自带 HITRAN 溯源水印）

## 二、安装

1. Python 3.9+，装依赖（官方 HAPI 直接 pip 装）：
   ```
   git clone https://github.com/LKF0402/hitran-mcp.git
   pip install -r hitran-mcp/requirements.txt
   ```
   或不用 git，直接下载仓库 zip 后 `pip install hitran-api numpy matplotlib`。
2. 把仓库放到任意固定路径，例如 `D:\hitran-mcp\`（下文以此为例）。
3. **API key（可选但建议）**：到 hitran.org 注册账号获取 API key，
   新建 `tools\hitran_api_key.txt`（与 hitran_mcp.py 同目录）写入 key 即可；
   也可设环境变量 `HITRAN_API_KEY`。
   > 说明：HAPI 1.3.0.0 的下载接口暂不校验 key，此文件属预置；官方对 fetch 有每日配额，
   > 超限会返回 403，届时等次日或减少抓取（本工具会自动复用缓存，不重复下载）。

## 三、注册到 AI 客户端（任意支持 MCP 协议的客户端均可）

在客户端的 MCP 服务器配置里（各产品入口不同，通常是设置中的 MCP/工具管理，
或直接编辑其 JSON 配置文件），合入 `mcp.config.example.json` 的内容，
**把 python 与脚本路径改成你的实际路径**：

```json
"hitran": {
  "command": "python",
  "args": ["D:/hitran-mcp-kit/tools/hitran_mcp.py"],
  "type": "stdio",
  "timeout": 600000,
  "disabled": false
}
```

> Windows 下若 python 不在 PATH，`command` 用解释器的完整路径（正斜杠或双反斜杠均可）。

保存后重启客户端，看到 `hitran` 服务器与 7 个工具即成功。

## 四、7 个工具速览

| 工具 | 作用 |
|---|---|
| `hitran_species` | 官方分子表：分子号 M、主同位素、各同位素自然丰度（支持分子式或分子号） |
| `hitran_fetch` | 抓取波数窗口线表；未覆盖窗口自动重抓；0 线/失败会报错，不静默出空谱 |
| `hitran_lines` | 窗口内最强 N 条线（ν、S、γ_air、E″）——选线/干扰分析 |
| `hitran_spectrum` | 吸收系数 α / 透过率谱（单/混合气、全同位素），CSV 带溯源水印 |
| `hitran_plot` | 谱图 PNG（多物种叠加 + 总谱，ylog 可选） |
| `hitran_partition_sum` | 配分函数 Q(T)（TIPS 2025/2021/2017/2011） |
| `hitran_cross_section` | 读入本地 HOTW 截面文件（hitran.org/xsc 下载，ν–σ 两列）→ 截窗/绘图/溯源 CSV；桥接截面子库 |

## 五、自测

```
python tools\hitran_mcp.py --selftest     # 走真实网络，抓 CO 小窗口 + 出图 + 截面链路（合成文件）
```

## 六、使用纪律（重要，写进了工具的返回值）

1. **单位**：默认返回吸收系数 α（cm⁻¹）；`hitran_units=true` 返回截面 σ（cm²/molecule，不按摩尔分数缩放）。
2. **混合气**：按 α_i = x_i · α_pure_i(T, P, 浴气) 计算，绝不用 x·P 当分压；不给浓度会强提示并按纯气体算。
3. **参数澄清**：没给的参数用默认值，但如实列在返回的 `assumed_defaults`（`needs_confirm=true` 时 AI 应向你确认 T/P/窗口/浓度）；`strict=true` 时 T/P 缺失直接报错。
4. **线型**：`profile` 可选 voigt(默认)/lorentz/gauss/doppler/ht/sdvoigt（全部直调官方 HAPI 函数）。
5. **溯源**：任何 CSV/图都能追到 HITRAN2024（Gordon et al., JQSRT 2026, doi:10.1016/j.jqsrt.2026.109807）+ HAPI（Kochanov et al., JQSRT 2016）+ TIPS 版本；论文引用以返回中的 citation 字段为准。
6. **同位素口径**：默认主同位素（纯气体权重 1.0）；`iso="all"` 按官方自然丰度加权（更接近真实大气）。

## 七、常见问题

- **抓取失败 "daily limit"**：官方每日配额超限，次日再试；缓存未删的前提下大部分窗口无需重新抓。
- **改了代码不生效**：重启 AI 客户端（MCP 进程随客户端启动）。
- **想清缓存**：删 `Hitran_Data/*.data|*.header` 即可，需要时自动重抓。

## 八、数据架构与分子覆盖（为什么有的分子"查不到"）

HITRAN2024 采用**双库分发架构**，两条数据通道的访问机制截然不同，这也是"某物种在逐线工具里查不到"的根因：

### 1. 逐线光谱数据库（Line-By-Line, LBL）

- 覆盖 **61 种分子**（H₂O / CO₂ / CH₄ / C₂H₆ / N₂O…）及 130+ 同位素体，数据为**逐跃迁线参数**（ν, S, γ_air, E″…）。
- 存储于 HITRANonline 关系型数据库，经官方 **HAPI**（HITRAN Application Programming Interface, Kochanov et al., JQSRT 177, 15–30, 2016）**在线 API** 提供——即本 MCP 的 `hitran_fetch / lines / spectrum / plot` 通道：实时取数、本地缓存、可复现。

### 2. 截面数据库（Cross-Section, XSC）

- 覆盖 **600+ 重分子**（丙烷、丁烷、VOC、制冷剂、含卤化物…）：多为稠密振动带结构、缺乏逐线验证参数，以**测量光谱文件**（两列 ν–σ，单位 cm⁻¹ / cm²·molecule⁻¹）形式收录。
- 访问机制：**仅经 HITRANonline Web Portal**（hitran.org/xsc）分发——需注册账号登录后按分子–温度–压力勾选下载；**无在线 API**。HAPI 侧只提供 `read_hotw()` 本地读文件接口，无网络取数接口。

### 3. 典型案例：丙烷（C₃H₈, molecule_id=137）

IR 截面共 136 个文件（实测元数据，2026-09 在线核对），3.3 μm 相关数据组：

| 数据组 | 波数范围 | 温度 / 压力 | 分辨率 | 说明 |
|---|---|---|---|---|
| PNNL NWIR（Sharpe et al. 2004） | 600–6500 cm⁻¹ | 278.15 / 298.15 / 323.15 K @ 760 Torr | 0.112 cm⁻¹ | 工业气体传感事实标准；ACP 2021（doi:10.5194/acp-21-10727-2021）Fig.1 即引用此数据 |
| Harrison & Bernath 2010 | 2540–3300 cm⁻¹ | 195–296 K | 0.015 cm⁻¹ | 完整覆盖 3.3 μm C–H 伸缩带 |
| 高分辨实验室系列 | 2700–3200 / 2700–3180 cm⁻¹ | 200–300 K | 0.005–0.01 cm⁻¹ | 多实验室（Wong 2018 / Bernath MoLLIST 等） |

> 物理要点：丙烷最强带位于 **2967 cm⁻¹**，3.3 μm 区截面峰值与 C₂H₆ 同量级（~10⁻¹⁸ cm²/mol），做 CH₄ 传感干扰分析时**不可按弱干扰忽略**。

### 4. 边界与桥接

- 逐线通道（API）**无法**访问截面通道（登录 Portal）——两者网络面不同，这是 HITRAN 官方数据分发设计，非本工具缺陷。
- 第 7 个工具 `hitran_cross_section` **桥接此缺口**：把 Portal 下载的 HOTW 截面文件（本地路径）读入，完成截窗、绘图、溯源 CSV 导出，与逐线谱共用同一产物链路（`tmp/mcp_out/`），实现截面分子"**下载一次、缓存复用、随时叠加分析**"。
- 流程：hitran.org/xsc → 搜索分子 → 勾选目标 T/P 文件 → 下载 .txt → `hitran_cross_section(file_path=...)`。
- 逐线工具遇到截面分子（如丙烷）时，报错信息会显式提示这一架构差异与正确路径。
