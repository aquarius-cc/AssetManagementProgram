# -*- coding: utf-8 -*-
"""文件长度回归护栏 (BR-6 File Length Regression Guard)

扫描后端全部业务 .py 文件，按逻辑行口径检查是否超过 500 行。

口径定义与实现见 scripts/line_metrics.py（本护栏不内联第二份实现，DR-1）：
物理跨度行数 - 空行 - '#' 注释行 - 本文件模块 docstring。
测试文件与 migrations 不纳入（用户 2026-09-29 拍板）。

台账（豁免登记表）为唯一事实来源：Rules_Fiels/BR6_file_length_ledger.md

断言规则（与 BR-4 护栏一致，防「只会 PASS」的假绿护栏）：
  1. 扫描出的每个 >500 行文件，必须已登记台账（未登记即红，防新增回潮）。
  2. 台账中的每个条目，当前逻辑行数必须仍 >500（已拆分未移除即红，防台账腐烂）。

退出码：
  0 = 全部通过
  1 = 护栏失败（任一断言命中）

用法：
  python scripts/check_file_length_guard.py            # 正常检查
  python scripts/check_file_length_guard.py --print    # 打印全量文件计数值

⚠️ 数行数口径警告
------------------
PowerShell 的 `Measure-Object -Line` 会跳过空行，同一文件可低估约 12%
（例：operation_log_service.py 真实 508 行，它会报 447）。
本项目历史上已因 `wc -l`（含空行）与逻辑口径混用导致两次误判，
一律以本护栏结果为准，不要用 PowerShell 速查行数。
"""

import argparse
import re
import sys
from pathlib import Path

from line_metrics import (
    is_migration,
    is_test,
    iter_py_files,
    logical_line_count,
    parse_module,
    read_text,
)

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "asset_management_backend"
LEDGER = ROOT / "Rules_Fiels" / "BR6_file_length_ledger.md"

MAX_LINES = 500

# 扫描范围：apps/ 为业务主体，其余为 apps/ 外的业务目录（core/config/utils）与后端根级脚本。
SCAN_DIRS = ("apps", "core", "config", "utils")
SCAN_ROOT_FILES = True

BLOCKING = []
WARNINGS = []


def iter_scope_files():
    """产出扫描范围内的 .py 文件（已排除测试与 migrations）。"""
    for name in SCAN_DIRS:
        for path in iter_py_files(BACKEND / name):
            if is_migration(path) or is_test(path):
                continue
            yield path
    if SCAN_ROOT_FILES:
        for path in sorted(BACKEND.glob("*.py")):
            if is_migration(path) or is_test(path):
                continue
            yield path


def scan() -> dict:
    """返回 {后端相对 posix 路径: 逻辑行数}。"""
    result = {}
    for path in iter_scope_files():
        relative = path.relative_to(BACKEND).as_posix()
        source = read_text(path)
        if not source:
            continue
        try:
            tree = parse_module(source)
        except SyntaxError:
            WARNINGS.append(f"{relative}: SyntaxError, skipped")
            continue
        result[relative] = logical_line_count(source, tree)
    return result


LEDGER_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|")


def read_ledger(path: Path) -> dict:
    """解析台账，返回 {后端相对 posix 路径: 登记行数}。"""
    entries = {}
    if not path.exists():
        WARNINGS.append(f"{path.as_posix()}: 台账文件不存在")
        return entries
    for line in read_text(path).splitlines():
        match = LEDGER_ROW_RE.match(line)
        if not match:
            continue
        relpath, count = match.groups()
        registered = int(count)
        if registered <= MAX_LINES:
            BLOCKING.append(
                f"台账条目非法: {relpath} 登记行数 {registered} <= {MAX_LINES}"
            )
            continue
        entries[relpath.strip().replace("\\", "/")] = registered
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description="BR-6 文件长度回归护栏")
    parser.add_argument("--print", action="store_true", help="打印全量文件计数值(生成台账用)")
    args = parser.parse_args()

    scanned = scan()

    if args.print:
        for relpath, count in sorted(scanned.items(), key=lambda x: (-x[1], x[0])):
            print(f"{count:4d}  {relpath}")
        return 0

    ledger = read_ledger(LEDGER)
    over_limit = {p: c for p, c in scanned.items() if c > MAX_LINES}

    for relpath in sorted(over_limit):
        if relpath not in ledger:
            BLOCKING.append(
                f"未登记超长文件: {relpath} 逻辑行数 {over_limit[relpath]} > {MAX_LINES}"
            )

    for relpath in sorted(ledger):
        if relpath not in over_limit:
            BLOCKING.append(f"台账含已达标条目(须移除/更新): {relpath}")

    if BLOCKING:
        print("[FAIL] BR-6 文件长度护栏失败:")
        for item in BLOCKING:
            print(f"  - {item}")
        if WARNINGS:
            print("[WARN]")
            for item in WARNINGS:
                print(f"  - {item}")
        return 1

    if WARNINGS:
        print("[WARN]")
        for item in WARNINGS:
            print(f"  - {item}")
    top = max(scanned.items(), key=lambda x: x[1]) if scanned else ("-", 0)
    print(
        f"[PASS] BR-6 文件长度护栏通过({len(over_limit)} 处超长文件/ "
        f"共扫描 {len(scanned)} 个业务 .py，最大 {top[0]} {top[1]} 行 / 上限 {MAX_LINES})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
