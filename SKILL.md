---
name: hitran-mcp
description: HITRAN spectroscopic database MCP server. Use when the user mentions HITRAN, absorption spectrum, line strength, cross section, gas sensing spectroscopy, TDLAS, WMS, or asks to calculate molecular absorption, line parameters, spectral simulation, or atmospheric transmission.
---

# hitran-mcp：HITRAN 光谱数据库 MCP 服务器

通过 MCP 协议接入 AI 助手，用自然语言完成 HITRAN 光谱计算，包括吸收系数、透过率、线强、截面、配分函数等。

## 触发条件

当用户提到以下关键词时触发：

- HITRAN / 吸收谱 / 透过率 / 吸收系数
- 线强 / 谱线参数 / line strength
- 吸收截面 / cross section
- 气体传感 / 光谱仿真
- TDLAS / WMS（需要光谱数据时）
- 分子吸收 / 红外光谱
- 配分函数 / partition sum

## 前提条件

- Python ≥ 3.10
- 依赖：hitran-api（HAPI）、numpy、matplotlib
- 首次使用会自动下载线表数据到本地缓存

## 工具列表

### 🔬 光谱计算

| 工具 | 说明 | 关键输入 |
|------|------|---------|
| `hitran_spectrum` | 吸收系数 α / 透过率谱计算 | `name`, `numin`, `numax`, `T`, `P`, `mole_frac` |
| `hitran_lines` | 窗口内最强 N 条谱线列表 | `name`, `numin`, `numax`, `top_n` |
| `hitran_fetch` | 抓取线表到本地缓存 | `name`, `numin`, `numax`, `iso` |
| `hitran_plot` | 谱图 PNG 绘制 | 同 spectrum，加 `ylog`, `title`, `dpi` |

### 📊 分子与数据

| 工具 | 说明 |
|------|------|
| `hitran_species` | 查询分子表（M 号、同位素、丰度） |
| `hitran_partition_sum` | 配分函数 Q(T) 查询（TIPS 2025） |
| `hitran_apikey_status` | API key / 缓存 / 产物状态 |

### 🧪 截面库（XSC）

| 工具 | 说明 |
|------|------|
| `hitran_xsc_search` | 在线搜索截面分子（中文名模糊匹配） |
| `hitran_xsc_download` | 一键下载截面文件 |
| `hitran_cross_section` | 读入截面文件并绘图/导出 |

## 使用规范

### 📏 单位标准

| 参数 | 单位 | 默认值 |
|------|------|--------|
| 波数范围 | cm⁻¹ | 必填，无默认 |
| 温度 T | K | 296 K（室温） |
| 压力 P | atm | 1.0 atm |
| 摩尔分数 | 无量纲（0~1） | 1.0（纯气体） |
| 光程 L | cm | 1.0 cm（透过率模式用） |
| 步长 step | cm⁻¹ | 0.01 |

### ⚠️ 主动澄清规则（重要）

**当用户说的参数不全时，必须主动问，不要瞎猜：**

#### 必须问用户的情况：
1. **没说波数范围** → 问："要算哪个波数范围？"
2. **没说温度** → 可以用 296 K 默认值，但要告诉用户："用了默认温度 296 K，需要改吗？"
3. **没说压力** → 可以用 1 atm 默认值，但要告诉用户
4. **没说浓度** → 默认纯气体，但要告诉用户

#### 绝对不能瞎猜的情况：
- ❌ 不知道要算什么分子 → 必须问
- ❌ 波数范围完全不知道 → 必须问
- ❌ 用户说的分子不在 HITRAN 表里 → 告诉用户，不要瞎算

### 📋 典型工作流

```
① 用户说："帮我算 CH4 的吸收谱"
② AI 应该：
   → 先问："波数范围？（比如 2950-3100 cm⁻¹）"
   → 用户回答后，再确认："温度 296 K，压力 1 atm，可以吗？"
   → 确认后调用 hitran_spectrum
③ 工具返回 needs_confirm=true 时：
   → 把 assumed_defaults 列给用户看
   → 问："这些默认值可以吗？需要改吗？"
```

### 🔢 输出模式

| 模式 | 说明 |
|------|------|
| `alpha` | 吸收系数 α（cm⁻¹）—— 默认 |
| `transmittance` | 透过率 T（无量纲） |
| `both` | 同时输出 α 和 T |

## 注意事项

- **数据实时取自 HITRANonline**，缓存后离线可用
- **混合气按 α_i = x_i · α_pure_i 计算**，不是简单叠加
- **结果带溯源水印**：任何 CSV/PNG 都标注 HITRAN2024 + HAPI + TIPS 版本
- **首次使用较慢**：需要下载线表数据，后续自动复用缓存

## 项目地址

- GitHub: https://github.com/LKF0402/hitran-mcp
