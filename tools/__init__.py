# -*- coding: utf-8 -*-
"""hitran-mcp-kit 的 tools 包。

刻意保持最小化：MCP 服务器只用到 tools.hitran（官方 HAPI 薄封装）。
不在此处预 import 任何子模块，避免连带拉起绘图/机器特定依赖（换机即坏）。
用法：
    from tools import hitran
    from tools import hitran_mcp   # MCP 服务器本体
"""
