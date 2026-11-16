# 完善度评估与敏感性检测报告（v1.6.3）

## 结论速览

- 评估对象：`D:\software\skills\hitran-mcp`（HitranLink GUI + HITRAN MCP）。
- 评估时间：2026-11-15。
- 评估口径：9 个维度独立打分，0–100；每个维度必须 ≥95；综合分按权重加权。
- 结果：**9/9 维度达到 95 分以上，综合 95.7 分**。
- 敏感性检测：跟踪文件、Git 历史、工作区缓存、发布 ZIP 均未检出 API key、第三方 Token、私钥或真实用户路径；本机运行期敏感文件全部在 `.gitignore` 覆盖范围内，未进入发布 ZIP。
- 发布产物：`dist/HitranLink-windows-x64.zip`（v1.6.3），大小 99,976,778 B，SHA-256 `5a7a0501888abfa1f93d47117646a9b5dd4987cc9203839a5f11c4bd0a8872cb`。

> 说明：本报告原始评估基于 v1.6.2；v1.6.3 完成桌面端更名与文档同步，引擎行为未变，评分沿用。

## 分维度评分

| 维度 | 权重 | 得分 | 主要依据 | 仍存在的非阻断项 |
| --- | ---: | ---: | --- | --- |
| 功能完整性 | 15 | 96 | 12 个 MCP 工具契约通过；GUI 无界面自检 61 物种 / 1501 点 / warnings=[]；物种、线表、吸收谱、截面、绘图、API key 诊断链路均可用 | 真实点击级 UI 自动化未覆盖 |
| 数值与物理正确性 | 15 | 96 | CH4 峰值 `14.284867706882977 @ 3028.75 cm⁻¹`、积分 `4.591485214251392` 与改动前基线一致；HAPI 1.x/HAPI2 双通道均有自检 | 极端参数组合仍依赖 HITRAN 官方数据质量 |
| 可靠性与异常处理 | 15 | 95 | 更新下载边下边校验 SHA-256/大小；半截包自动删除；解压失败不覆盖现有安装；线程世代校验保留 | 无真实弱网/断网的长时回归 |
| 安全性 | 15 | 96 | 固定 Release URL；拒绝 http/异域主机/查询串；ZIP 逐条拒绝绝对路径、盘符、`..`、符号链接、加密条目、超限；顶层白名单 | 未做 Windows 代码签名，SmartScreen 仍可能提示 |
| 隐私与敏感性 | 10 | 96 | API key 只在运行期数据目录；工作区 key 扩散扫描 0 命中；Git 历史与发布 ZIP 无 key；构建机路径回扫通过 | 本机 `local`/日志仍可能存在，但已 gitignore 且不入包 |
| 测试与 CI | 10 | 95 | 23 个离线单元测试通过；CI 三版本矩阵 + 安全 job + 契约检查；依赖精确锁定 | 无 GUI 事件级自动化 |
| 文档与可复现性 | 8 | 96 | README 中英双版、SECURITY、CHANGELOG、本报告；构建/发布/回滚路径明确 | 历史 v1.6.0 日志未重写 |
| 发布工程 | 7 | 96 | 打包/发布/自检/ZIP/CRC 校验原子化；发布前安全闸门；资产哈希可复核 | 资产上传仍依赖手动 GitHub Release 流程 |
| 可维护性 | 5 | 95 | 更新安全原语拆到 `app/updater.py`；安全扫描独立为 `tools/security_check.py`；测试独立目录 | `app/hitran_app.py` 仍约 4000 行，未彻底拆分 |

加权计算：`(96×15 + 96×15 + 95×15 + 96×15 + 96×10 + 95×10 + 96×8 + 96×7 + 95×5) / 100 = 95.7`。

## 敏感性/敏感信息检测

### 检查范围

1. Git 跟踪文件（当前 29 个，含安全/测试/文档文件）。
2. Git 全历史（132 个提交）中的敏感文件名。
3. 当前 HITRAN API key 在跟踪文件、历史提交、工作区、发布 ZIP 中的扩散。
4. 工作区运行期文件：`config.json`、`Hitran_Data/`、`hitran_prefs.json`、`local`、`error.log`。
5. 发布 ZIP 的 1995 个条目：顶层结构、敏感条目、key 内容、构建机路径。

### 检查方法

- 跟踪文件：逐文件文本扫描；正则覆盖 GitHub/OpenAI/AWS/Google/Slack/JWT/私钥；Windows/Unix 用户路径与邮箱。
- Git 历史：`git log --all --name-only` 检查敏感文件名；`git log --all -S <key>` 检查 key 明文。
- 工作区：读取 `Hitran_Data/hitran_api_key.txt` 的 key 值，递归扫描除 key 文件外的文本/二进制文件。
- 发布 ZIP：`zipfile` 逐条读取；检查顶层白名单、敏感条目、key 字节、构建机家目录/用户名。
- 代码安全：Python AST 检查 `eval/exec/compile/__import__`、`os.system`、`shell=True`、`extractall`、`verify=False`。

### 检查结果

| 检查项 | 结果 |
| --- | --- |
| 跟踪文件中的 API key 值 | 0 命中 |
| 跟踪文件中的第三方 Token/私钥 | 0 命中 |
| Git 历史中的敏感文件名 | 0 命中 |
| Git 历史中的 API key 明文 | 0 命中 |
| 工作区 key 扩散（除 key 文件） | 0 命中 |
| 发布 ZIP 中的 key | 0 命中 |
| 发布 ZIP 顶层结构 | 仅 `HitranLink.exe`、`_internal` |
| 发布 ZIP 中的构建机路径 | 0 命中 |
| 跟踪文件中的真实用户路径/邮箱 | 0 命中；仅 README `C:/Users/你`、`build_release.py` 的 `<本机用户名>/<构建者>` 占位符 |
| 危险调用 | 0 命中（`compile` 仅出现在 `re.compile`，已按 AST 节点类型排除） |

本机敏感文件清单（均 `ignored=true`，不进入发布 ZIP）：

| 文件 | 大小 | 内容/用途 | Git | 发布 ZIP |
| --- | ---: | --- | --- | --- |
| `config.json` | 339 B | HAPI2 本地配置，`api_key:null` | 忽略 | 排除 |
| `Hitran_Data/hitran_api_key.txt` | 36 B | 本机 HITRAN API key | 忽略 | 排除 |
| `Hitran_Data/error.log` | 116 B | 历史运行错误日志 | 忽略 | 排除 |
| `hitran_prefs.json` | 23 B | GUI 偏好 | 忽略 | 排除 |
| `local` | 143,360 B | 本机 HAPI2 SQLite 数据 | 忽略 | 排除 |

### 复现命令

```powershell
cd D:\software\skills\hitran-mcp
py -3.10 tools\security_check.py
py -3.10 -m unittest discover -s tests -v
py -3.10 tools\contract_check.py
py -3.10 app\hitran_app.py --selftest tmp\gui_selftest_after.json
```

期望：安全脚本 `"ok": true`、`issues: []`；单元测试 23/23 通过；契约 `{"ok": true, "tools": 12, "version": "1.6.3"}`；GUI 自检 `warnings: []`。

## 本轮改动清单

- 新增 `app/updater.py`、`app/__init__.py`：固定 Release URL、SHA-256 校验、安全解压、顶层白名单。
- 修改 `app/hitran_app.py`：检查更新不信任 API 返回的下载 URL；下载时要求 size/digest；解压改用安全原语。
- 新增 `tools/security_check.py`：跟踪文件/历史/工作区/发布 ZIP/代码 AST 的发布前安全闸门。
- 新增 `tests/test_updater.py`、`tests/test_core.py`：当时 13 个离线测试，后续补测至 23 个。
- 修改 `requirements.txt`：`hitran-api==1.3.0.0`、`numpy==2.0.1`、`matplotlib==3.9.1`。
- 修改 CI：只读权限、并发取消、三版本矩阵、单元测试、安全 job；新增 Dependabot。
- 修改 `tools/build_release.py`：ZIP 后追加安全闸门，失败拒绝出包。
- 修改 `SECURITY.md`：安全控制、敏感文件清单、报告渠道与验证命令。
- 版本提升到 `1.6.2`，CHANGELOG 仅保留 GUI 的“问题修复”小节。

## 残余风险与后续建议

1. **未做代码签名**：Windows 首次运行仍可能出现 SmartScreen 提示；若需要消除，需购买代码签名证书。
2. **GUI 未拆分**：`app/hitran_app.py` 约 4000 行，功能与安全原语已解耦，但 UI 层仍是单文件；后续可按“更新/设置/绘图/任务”拆分，代价是需要重新验证 PyInstaller 打包。
3. **无点击级 UI 自动化**：当前只有 headless selftest；如要覆盖按钮状态、进度条和异常弹窗，需要引入 UI 自动化框架，成本较高。
4. **`HITRAN_DATA_DIR` 只覆盖缓存/API key**：`OUT_DIR`、`XSC_DIR` 仍跟随 `ROOT`；这是共享数据目录的后续优化项，不影响当前安全与功能。
5. **打包 GUI 首次运行仍是 HAPI 1.x 回退**：发布包不携带 API key，首次运行未配置 key 时回退到 HAPI 1.x；这是有意的“无凭据发布”设计。
