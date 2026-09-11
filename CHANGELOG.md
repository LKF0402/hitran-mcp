# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [v1.5.2] - 2026-09-11

### Bug Fixes
- Fixed auto-updater hang on Windows
- Added real-time progress display during updates
- Added automatic retry (up to 3 attempts)
- Fixed Chinese character garbling in UTF-8 terminals

---

## [v1.5.1] - 2026-09-11

### License Change
- Changed license from MIT to GNU GPLv3

### Bug Fixes
- Fixed cross-section download selection not registering
- Fixed bottom control bar being squeezed off-screen on small displays
- Eliminated duplicate cross-section queries
- Centralized checkbox state management

---

## [v1.5.0] - 2026-09-11

### New Features
- Cross-section database online search and one-click download (600+ heavy molecules)
- Chinese/chemical formula molecule search (no need to memorize English names)
- HAPI2 official API integration for line list downloads
- Support for native HITRAN `.xsc` file format

### Improvements
- Reduced startup memory usage (225 MB → 137 MB)
- Added network retry with exponential backoff
- Enhanced error logging and diagnostics

### Bug Fixes
- Fixed silent data corruption during chunked computation
- Fixed line list truncation detection
- Fixed dialog focus issues (API key / preferences / about)
- Fixed molecular search input lag

---

## [v1.4.2] - 2026-09-11

### Critical Fixes
- Fixed engine crash on startup (all computation failed)
- Fixed chunked computation point count inconsistency
- Added truncated line list file detection and auto-re-download

### Improvements
- Error dialog now supports text selection and copy
- All errors automatically logged to `Hitran_Data/error.log`

---

## [v1.4.1] - 2026-09-11

> **Note:** This release had a source code bug and is deprecated. Users are recommended to upgrade to v1.4.2 or later.

### New Features
- API key configuration dialog (Tools → Configure API Key)
- Network connectivity check before computation

### Bug Fixes
- Fixed undefined variable errors (numpy, json)
- Fixed stop button incorrectly interrupting downloads
- Fixed mixture mode dropping isotope selection
- Fixed import spectrum bypassing grid/legend toggles
- Fixed unit switch precision loss
- Fixed CSV export wave number axis validation

### Performance
- Reduced package size from 362 MB to 106 MB (70.7% reduction)

---

## [v1.4.0] - 2026-09-10

### New Features
- Molecular alias search (166 aliases, supports English names, chemical formulas, and M-numbers)
- Enhanced legend with English molecule names (55 species)
- Extended configuration persistence (molecule, isotope, path length, cutoff, etc.)
- HAPI2 compatibility layer framework
- Numba capability detection

---

## [v1.3.0] - 2026-09-10

### New Features
- Light/Dark mode toggle (View → Light Mode / Dark Mode)
- iOS-inspired light color scheme (soft, low-saturation)
- Optional HAPI2 support (auto-detect, auto-fallback to HAPI1)

### Architecture
- Refactored color configuration to dynamic retrieval system
- Extended RoundedButton for runtime color updates

---

## [v1.2.3] - 2026-09-10

### New Features
- Menu: Tools → Clear Line Cache (one-click cache cleanup)

### UI Fixes
- Fixed dark mode button color confusion
- Improved listbox selected text readability

---

## [v1.2.2] - 2026-09-10

### Performance
- Line list local caching (no repeated network downloads)
- Chunked computation with real-time progress reporting

### UI
- Real progress bar with elapsed/remaining time
- Fixed intensity cutoff unit label (cm/molecule)

### Auto-Update
- One-click auto-upgrade (download → extract → replace → restart)
- Preserves line list cache during updates

---

## [v1.2.1] - 2026-09-10

### Engine
- Cross-section file separator compatibility (space / tab / comma)
- Line list window safety check (auto re-download if cached table doesn't cover requested window)

### Desktop UI
- Transmittance mode CSV export now outputs actual displayed transmittance
- Clear plot button also clears strong line data
- Added project open/save (Ctrl+O / Ctrl+S)
- Preferences persistence (step size, wing half-width, line profile)
- Fixed rounded button background color degradation

### Build
- HitranLab.spec included in version control for reproducible builds

---

# 更新日志

本文件记录了项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/)，本项目遵循 [语义化版本](https://semver.org/)。

---

## [v1.5.2] - 2026-09-11

### 问题修复
- 修复自动更新器卡死问题
- 更新过程显示实时进度
- 自动重试机制（最多 3 次）
- 修复 UTF-8 终端下中文乱码

---

## [v1.5.1] - 2026-09-11

### 许可证变更
- 许可证由 MIT 改为 GNU GPLv3

### 问题修复
- 修复截面下载勾选失效问题
- 修复小屏幕下底栏按钮被挤出可视区
- 消除重复截面查询
- 统一勾选状态管理

---

## [v1.5.0] - 2026-09-11

### 新功能
- 截面数据库在线检索与一键下载（600+ 重分子）
- 中文/化学式分子搜索（无需记忆英文名）
- HAPI2 官方 API 线表下载接入
- 支持 HITRAN 原生 `.xsc` 文件格式

### 优化改进
- 降低启动内存占用（225 MB → 137 MB）
- 网络请求指数退避重试
- 增强错误日志与诊断能力

### 问题修复
- 修复分块计算时静默数据篡改
- 增强线表截断检测
- 修复弹窗焦点问题（API key / 首选项 / 关于）
- 修复分子搜索框输入卡顿

---

## [v1.4.2] - 2026-09-11

### 关键修复
- 修复启动时引擎崩溃（所有计算功能失效）
- 修复分块计算点数不一致
- 新增线表截断检测与自动重下

### 优化改进
- 错误对话框支持文本选中与复制
- 所有错误自动记录到 `Hitran_Data/error.log`

---

## [v1.4.1] - 2026-09-11

> **注意：** 本版本存在源码 bug，已废弃。建议升级到 v1.4.2 或更高版本。

### 新功能
- API key 配置对话框（工具 → 配置 API key）
- 计算前联网状态检测

### 问题修复
- 修复未定义变量错误（numpy, json）
- 修复停止按钮误中断下载
- 修复混合气模式丢失同位素选择
- 修复导入谱线绕过网格/图例开关
- 修复单位切换精度损失
- 修复 CSV 导出波数轴校验

### 性能优化
- 打包体积从 362 MB 降至 106 MB（减少 70.7%）

---

## [v1.4.0] - 2026-09-10

### 新功能
- 分子别名搜索（166 条别名，支持英文名/化学式/M 编号）
- 图例增强（55 种分子英文名显示）
- 配置持久化扩展（分子/同位素/光程/截断等）
- HAPI2 兼容层框架
- Numba 能力检测

---

## [v1.3.0] - 2026-09-10

### 新功能
- 浅色/深色模式切换（视图 → 浅色模式 / 深色模式）
- iOS 风格浅色配色（柔和低饱和）
- HAPI2 可选支持（自动检测，自动回退 HAPI1）

### 架构改进
- 重构颜色配置为动态检索系统
- 扩展圆角按钮支持运行时颜色更新

---

## [v1.2.3] - 2026-09-10

### 新功能
- 工具菜单新增：清理线表缓存（一键删除）

### UI 修复
- 修复深色模式按钮颜色混淆
- 提升列表选中文字可读性

---

## [v1.2.2] - 2026-09-10

### 性能优化
- 线表本地缓存复用（不再重复联网下载）
- 分块计算与实时进度上报

### 界面改进
- 真实进度条与预计剩余时间
- 修正强度截断单位标注

### 自动更新
- 一键自动升级（下载 → 解压 → 替换 → 重启）
- 更新时保留线表缓存

---

## [v1.2.1] - 2026-09-10

### 引擎
- 截面文件分隔符兼容（空格 / 制表符 / 逗号）
- 线表窗口安全检查（缓存表不覆盖请求窗口时自动重抓）

### 桌面界面
- 透过率模式导出 CSV 输出实际显示的透过率值
- 清空图按钮同步清空强线数据
- 新增项目打开/保存（Ctrl+O / Ctrl+S）
- 首选项持久化（步长/翼宽/线型）
- 修复圆角按钮背景色退化

### 工程
- 打包配置纳入版本控制，可复现构建
