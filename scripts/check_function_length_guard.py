# -*- coding: utf-8 -*-
"""函数长度回归护栏 (BR-4 Function Length Regression Guard)

基于 AST 语义节点扫描后端 apps 目录下所有函数/方法，按 BR-4 逻辑行口径
（物理跨度行数 - 空行 - '#' 注释行，docstring 计入代码行）检查是否超过 50 行。

台账（豁免登记表）为唯一事实来源：Rules_Fiels/BR4_function_length_ledger.md

断言规则：
  1. 扫描出的每个 >50 行函数，必须已登记台账（未登记即红，防新增回潮）。
  2. 台账中的每个条目，当前逻辑行数必须仍 >50（已拆分未移除即红，防台账腐烂）。

退出码：
  0 = 全部通过
  1 = 护栏失败（任一断言命中）

用法：
  python scripts/check_function_length_guard.py            # 正常检查
  python scripts/check_function_length_guard.py --print    # 打印全量函数计数(生成台账用)
"""

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "asset_management_backend"
LEDGER = ROOT / "Rules_Fiels" / "BR4_function_length_ledger.md"

MAX_LINES = 50

BLOCKING = []
WARNINGS = []


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return ""


def iter_py_files(scope_dir: Path):
    if not scope_dir.exists():
        return
    for path in scope_dir.rglob("*.py"):
        yield path


def is_migration(path: Path) -> bool:
    parts = path.parts
    return any(part == "migrations" for part in parts)


def is_test(path: Path) -> bool:
    name = path.name
    if "test" in name.lower() or "conftest" in name.lower():
        return True
    parts = path.parts
    return any(part in ("tests", "test") for part in parts)


def logical_line_count(source: str, node: ast.AST) -> int:
    """BR-4 逻辑行口径：物理跨度行数 - 空行 - '#' 注释行。docstring 计入代码行。"""
    lines = source.splitlines()
    count = 0
    for lineno in range(node.lineno, node.end_lineno + 1):
        text = lines[lineno - 1]
        stripped = text.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        count += 1
    return count


def scan(scope_dir: Path):
    """扫描 app 内所有函数，返回 {posix_relpath: [(func_name, def_line, logical_count), ...]}"""
    result = {}
    for path in iter_py_files(scope_dir):
        if is_migration(path) or is_test(path):
            continue
        relative = path.relative_to(scope_dir).as_posix()
        source = read_text(path)
        if not source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            WARNINGS.append(f"{relative}: SyntaxError, skipped")
            continue
        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                count = logical_line_count(source, node)
                funcs.append((node.name, node.lineno, count))
        result[relative] = sorted(funcs, key=lambda x: x[1])
    return result


LEDGER_ROW_RE = re.compile(r"^\|\s*[^|]+\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*[^|]+\|")


def read_ledger(path: Path):
    """解析台账，返回 {posix_relpath: set(func_name)} 与原始行数。"""
    entries = {}
    if not path.exists():
        WARNINGS.append(f"{path.as_posix()}: 台账文件不存在")
        return entries
    for line in read_text(path).splitlines():
        match = LEDGER_ROW_RE.match(line)
        if not match:
            continue
        relpath, lineno, func, count = match.groups()
        assert_count = int(count)
        if assert_count <= MAX_LINES:
            BLOCKING.append(f"台账条目非法: {relpath}:{lineno} {func} 登记行数 {assert_count} <= {MAX_LINES}")
            continue
        entries.setdefault(relpath.strip().replace("\\", "/"), set()).add(func.strip())
    return entries


def main():
    parser = argparse.ArgumentParser(description="BR-4 函数长度回归护栏")
    parser.add_argument("--print", action="store_true", help="打印 app 全量函数计数值(不含迁移/测试)")
    args = parser.parse_args()

    scanned = scan(BACKEND / "apps")

    if args.print:
        rows = []
        for relpath in sorted(scanned):
            for name, lineno, count in scanned[relpath]:
                rows.append((count, relpath, name, lineno))
        for count, relpath, name, lineno in sorted(rows, reverse=True):
            print(f"{count:4d}  {relpath}:{lineno}  {name}")
        return 0

    ledger = read_ledger(LEDGER)

    over_limit = {}
    for relpath, funcs in scanned.items():
        for name, lineno, count in funcs:
            if count > MAX_LINES:
                over_limit.setdefault(relpath, {})[name] = count

    for relpath in sorted(over_limit):
        for name, count in sorted(over_limit[relpath].items()):
            if relpath not in ledger or name not in ledger[relpath]:
                BLOCKING.append(
                    f"未登记超长函数: {relpath} {name}() 逻辑行数 {count} > {MAX_LINES}"
                )

    for relpath in sorted(ledger):
        for name in sorted(ledger[relpath]):
            if relpath not in over_limit or name not in over_limit[relpath]:
                BLOCKING.append(
                    f"台账含已达标条目(须移除/更新): {relpath} {name}()"
                )

    if BLOCKING:
        print("[FAIL] BR-4 函数长度护栏失败:")
        for item in BLOCKING:
            print(f"  - {item}")
        if WARNINGS:
            print("[WARN]")
            for item in WARNINGS:
                print(f"  - {item}")
        return 1

    over_funcs = sum(len(items) for items in over_limit.values())
    print(f"[PASS] BR-4 函数长度护栏通过({over_funcs} 处超长函数/ {len(over_limit)} 个文件，已全部登记台账)")
    if WARNINGS:
        print("[WARN]")
        for item in WARNINGS:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())