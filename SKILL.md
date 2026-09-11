---
name: hitran-mcp
description: HITRAN spectroscopic database MCP server. Triggers on HITRAN, absorption spectrum, line strength, absorption cross section, gas sensing spectroscopy, TDLAS, WMS, molecular absorption calculation, spectral simulation, or atmospheric transmission queries.
---

# hitran-mcp：HITRAN 光谱数据库 MCP 服务器

基于 HITRAN2024 数据库的光谱计算 MCP 服务器，提供直接吸收光谱（DAS）、线表查询、截面分析与配分函数计算。

## 触发域

当用户请求涉及以下任一领域时触发：

| 领域 | 关键词示例 |
|------|-----------|
| 分子光谱计算 | absorption spectrum, transmittance, absorption coefficient α |
| 线参数分析 | line strength S(T), line list, spectral lines |
| 截面数据 | absorption cross section σ, HITRAN cross-sections |
| 气体传感 | gas sensing, TDLAS, WMS, concentration retrieval |
| 热力学参数 | partition function Q(T), TIPS |

## 工具接口

### 光谱计算类

| 工具 | 功能 | 输入参数 | 输出 |
|------|------|---------|------|
| `hitran_spectrum` | 吸收系数 / 透过率谱计算 | `name`, `numin`, `numax`, `T`, `P`, `mole_frac`, `step`, `profile` | CSV 数据 + 溯源元数据 |
| `hitran_lines` | 窗口内强线列表 | `name`, `numin`, `numax`, `top_n` | 线参数表（ν, S, γ, E″） |
| `hitran_fetch` | 线表下载与缓存 | `name`, `numin`, `numax`, `iso` | 缓存状态 |
| `hitran_plot` | 谱图绘制 | 同 `hitran_spectrum` + `ylog`, `dpi` | PNG 图像 |

### 分子与数据类

| 工具 | 功能 |
|------|------|
| `hitran_species` | 官方分子表查询（M 编号、同位素、丰度） |
| `hitran_partition_sum` | 配分函数 Q(T) 计算（TIPS 2025） |
| `hitran_apikey_status` | API key / 缓存 / 产物状态 |

### 截面库（XSC）类

| 工具 | 功能 |
|------|------|
| `hitran_xsc_search` | 截面分子在线检索（中文名模糊匹配） |
| `hitran_xsc_download` | 截面文件批量下载 |
| `hitran_cross_section` | 截面文件读取与分析 |

## 参数规范

### 物理单位

| 参数 | 单位 | 类型 | 默认值 |
|------|------|------|--------|
| `numin`, `numax` | cm⁻¹ | 浮点数 | **无默认，必填** |
| `T`（温度） | K | 浮点数 | 296.0 |
| `P`（压力） | atm | 浮点数 | 1.0 |
| `mole_frac`（摩尔分数） | 无量纲 [0, 1] | 浮点数 | 1.0 |
| `step`（步长） | cm⁻¹ | 浮点数 | 0.01 |
| `L`（光程） | cm | 浮点数 | 1.0 |

### 物种标识

- `name`：分子式（大小写不敏感）或 HITRAN M 编号（1~61）
- `iso`：同位素编号，`"all"` 表示按自然丰度加权，默认主同位素

## 参数完整性校验流程

### 必须显式确认的参数

以下参数缺失时，**必须向用户确认，不得使用默认值自动计算**：

1. **波数范围（`numin`, `numax`）**——物理窗口必须由用户指定
2. **物种名称（`name`）**——计算目标必须明确

### 可使用默认值的参数

以下参数可使用默认值，但**必须在结果中显式标注**：

- 温度 T：默认 296 K
- 压力 P：默认 1 atm
- 摩尔分数：默认 1.0（纯气体）
- 步长：默认 0.01 cm⁻¹

### 默认值标注规则

当使用了默认参数时，工具返回 `assumed_defaults` 字段。Agent 收到此字段后：

1. 必须向用户展示本次使用的默认参数列表
2. 询问用户是否需要调整
3. 用户确认后再进行后续计算

### 禁止行为

- ❌ 不得在用户未明确请求时，自行选择分子或波数范围
- ❌ 不得将假设的参数值直接用于计算而不告知用户
- ❌ 不得在物种未识别时，猜测分子进行计算

## 输出模式

| 模式 | 输出物理量 | 单位 |
|------|-----------|------|
| `alpha`（默认） | 吸收系数 α | cm⁻¹ |
| `transmittance` | 透过率 T | 无量纲 |
| `both` | 同时输出 α 和 T | — |

## 物理口径

- **混合气叠加**：α_total = Σ xᵢ · α_pure,i(T, P, 浴气)
- **透过率**：T(ν) = exp(-α(ν) · L)
- **截面换算**：σ = α / N（N = 数密度，molecules/cm³）
- **线强**：S(T) = S(T_ref) · Q(T_ref)/Q(T) · Boltzmann 修正

## 数据溯源

所有 CSV / PNG 输出均包含：
- HITRAN 版本（2024）
- HAPI 版本
- TIPS 版本
- 计算参数（T, P, step, profile）
- 生成时间

## 错误处理

| 错误类型 | 处理方式 |
|---------|---------|
| 物种未识别 | 返回可用分子列表，请用户确认 |
| 波数窗口未覆盖 | 自动扩展窗口重抓线表 |
| 0 条谱线 | 显式报错，禁止返回空平谱 |
| 参数单位错误 | 明确指出单位错误，请用户修正 |

## 项目地址

https://github.com/LKF0402/hitran-mcp
