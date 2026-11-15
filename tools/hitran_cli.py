# -*- coding: utf-8 -*-
"""hitran_cli：不接 MCP 客户端也能直接调用 HITRAN 工具函数。

用途：任何能在本机执行命令的 AI 助手（或用户本人）无需配置 MCP，即可直接取数、算谱、绘图。

用法：
  python tools/hitran_cli.py --list
  python tools/hitran_cli.py t_species --name CH4
  python tools/hitran_cli.py t_lines --name CH4 --numin 2960 --numax 2975 --top_n 5
  python tools/hitran_cli.py t_spectrum --name CH4 --mole_frac 0.002 \
      --numin 2950 --numax 3100 --T 296 --P 1.01325
  python tools/hitran_cli.py hitran_partition_sum --name CH4 --T 300

参数写法：`--键 值`，键名与工具函数参数名一致；值自动识别为数字/布尔/JSON 数组。
输出：JSON（UTF-8），可用 --out 落盘。
"""
import argparse
import contextlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# 库侧（HAPI/hapi2）会往 stdout 打初始化日志；导入即重定向到 stderr，保证 stdout 只有 JSON。
with contextlib.redirect_stdout(sys.stderr):
    import hitran_mcp as hm  # noqa: E402
    with contextlib.suppress(Exception):
        hm._quiet()

_NAME_MAP = {}
for _item in hm.TOOLS:
    _fn = "t_" + _item["name"].replace("hitran_", "", 1)
    if hasattr(hm, _fn):
        _NAME_MAP[_item["name"]] = _fn
        _NAME_MAP.setdefault(_fn, _fn)


def _coerce(text):
    """把命令行字符串还原成 Python 值：数字、布尔、null、JSON 数组/对象，其余保持字符串。"""
    low = text.strip().lower()
    if low in {"true", "yes", "on"}:
        return True
    if low in {"false", "no", "off"}:
        return False
    if low in {"none", "null"}:
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    if text[:1] in "[{":
        try:
            return json.loads(text)
        except ValueError:
            pass
    return text


def _parse_kwargs(rest):
    """解析 `--键 值` 序列；不带值的开关视为 True。"""
    kw = {}
    i = 0
    while i < len(rest):
        tok = rest[i]
        if not tok.startswith("--"):
            raise SystemExit("参数必须以 --键 值 的形式给出，错误片段：%r" % tok)
        key = tok[2:].replace("-", "_")
        if i + 1 < len(rest) and not rest[i + 1].startswith("--"):
            kw[key] = _coerce(rest[i + 1])
            i += 2
        else:
            kw[key] = True
            i += 1
    return kw


def _print_tools():
    for item in hm.TOOLS:
        first = (item["description"] or "").split("；")[0].split("。")[0]
        print("%-26s %s" % (item["name"], first))
    print("\n直接调用示例：python tools/hitran_cli.py hitran_species --name CH4")


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=True, description="HITRAN 命令行入口（无需 MCP 客户端）")
    parser.add_argument("--list", action="store_true", help="列出全部工具")
    parser.add_argument("--out", default=None, help="把 JSON 结果写入文件")
    parser.add_argument("tool", nargs="?", help="工具名，如 hitran_spectrum 或 t_spectrum")
    args, rest = parser.parse_known_args(argv)

    if args.list or not args.tool:
        _print_tools()
        return 0

    fn_name = _NAME_MAP.get(args.tool)
    if not fn_name:
        print("未知工具：%s（用 --list 查看可用工具）" % args.tool, file=sys.stderr)
        return 2

    try:
        with contextlib.redirect_stdout(sys.stderr):  # 工具内部可能的库打印一律不进 stdout
            result = getattr(hm, fn_name)(**_parse_kwargs(rest))
    except SystemExit:
        raise
    except Exception as exc:  # 工具函数自身报错时，保留原始信息便于 AI 判断
        print("调用失败：%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1

    text = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("已写入 %s" % args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
