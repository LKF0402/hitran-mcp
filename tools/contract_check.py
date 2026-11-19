#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线契约检查：不联网、不读写数据缓存，验证 MCP 工具表与协议入口的一致性。

用法：
    python tools/contract_check.py
退出码 0 = 全部通过；1 = 有断言失败。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.hitran_mcp as m


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def check_tools():
    names = [t.get("name") for t in m.TOOLS]
    _assert(len(names) == 14, f"工具数应为 14，实际 {len(names)}")
    _assert(len(set(names)) == len(names), "工具名重复")
    _assert(set(names) == set(m.DISPATCH), "TOOLS 与 DISPATCH 不一致")
    for tool in m.TOOLS:
        _assert(tool.get("description"), f"{tool.get('name')} 缺少 description")
        schema = tool.get("inputSchema")
        _assert(isinstance(schema, dict) and schema.get("type") == "object",
                f"{tool.get('name')} inputSchema 必须是 object")
        props = schema.get("properties", {})
        _assert(isinstance(props, dict), f"{tool.get('name')} properties 必须是对象")
        required = schema.get("required", [])
        _assert(isinstance(required, list), f"{tool.get('name')} required 必须是数组")
        for key in required:
            _assert(key in props, f"{tool.get('name')} required 含未声明字段: {key}")


def check_protocol():
    rid, result, error = m.handle({
        "jsonrpc": "2.0", "id": "init", "method": "initialize",
        "params": {"protocolVersion": m.PROTOCOL_VERSION,
                   "capabilities": {}, "clientInfo": {"name": "contract-check"}},
    })
    _assert(error is None and result, "initialize 应返回 result")
    _assert(result["protocolVersion"] == m.PROTOCOL_VERSION, "协议版本不一致")
    _assert(result["serverInfo"]["version"] == m.VERSION, "serverInfo 版本不一致")
    _assert(result["capabilities"]["tools"]["listChanged"] is False,
            "tools/listChanged 应为 False")

    _, listed, error = m.handle({"jsonrpc": "2.0", "id": "list", "method": "tools/list"})
    _assert(error is None and listed, "tools/list 应返回 result")
    _assert(len(listed["tools"]) == 14, "tools/list 工具数不是 14")

    _, pong, error = m.handle({"jsonrpc": "2.0", "id": "ping", "method": "ping"})
    _assert(error is None and pong == {}, "ping 应返回空对象")

    _, unknown, error = m.handle({
        "jsonrpc": "2.0", "id": "bad", "method": "tools/call",
        "params": {"name": "__missing__", "arguments": {}},
    })
    _assert(error is None and unknown["isError"] is True, "未知工具应返回 isError")


def check_no_bom():
    for rel in ("tools/hitran_mcp.py", "app/hitran_app.py"):
        head = (ROOT / rel).read_bytes()[:3]
        _assert(head != b"\xef\xbb\xbf", f"{rel} 仍带 UTF-8 BOM")


def main():
    check_tools()
    check_protocol()
    check_no_bom()
    print(json.dumps({"ok": True, "tools": len(m.TOOLS), "version": m.VERSION},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as e:
        print(f"contract check failed: {e}", file=sys.stderr)
        raise SystemExit(1)
