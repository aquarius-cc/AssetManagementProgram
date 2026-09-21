# -*- coding: utf-8 -*-
"""前端规模回归护栏 (Frontend Size Regression Guard)

两条子规则，计数统一走 logical_line_count（与后端 BR-4 guard 的
logical_line_count 对齐：BR-4 为物理跨度行数 - 空行 - '#' 注释行；TS
对应去除块注释/行注释，因 TS 无 docstring）：

  FR-6 (composables)：检查 composables 目录下所有 use*.ts 文件逻辑行是否超过 200。
       台账（豁免登记表）为唯一事实来源：Rules_Fiels/FR6_composable_ledger.md
       断言规则：
         1. 扫描出的每个逻辑行 > 200 的 composable，必须已登记台账（未登记即红，防新增回潮）。
         2. 台账中的每个条目，当前逻辑行数必须仍 > 200（已拆分/删除未移除即红，防台账腐烂）。
         3. 台账条目登记的断言行数必须 > 200（数值手写非法即红）。

  FR-8 (stores)：检查 stores 目录下所有 *.ts（非 use*.ts）文件逻辑行是否超过 500。
       严格模式：超限即红，无台账豁免（当前全仓 stores 均 ≤500，无存量登记必需）。

逻辑行口径（FR-6 条文，FR-8 沿用）：逻辑行 = 物理行 - 空行 - 整行注释；
行注释 '//' 与块注释 '/* */' 起止行剔除；行内/行尾注释计入代码行；
字符串/模板串内的 '//' 与 '/*' 不视为注释。

退出码：
  0 = 全部通过
  1 = 护栏失败（任一断言命中）

用法：
  python scripts/check_frontend_invariants.py            # 正常检查
  python scripts/check_frontend_invariants.py --print    # 打印全量计数(生成台账用)
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCOPE_DIR = ROOT / "vue-assetmanagement" / "src" / "composables"
STORE_SCOPE_DIR = ROOT / "vue-assetmanagement" / "src" / "stores"
LEDGER = ROOT / "Rules_Fiels" / "FR6_composable_ledger.md"

MAX_LINES = 200
STORE_MAX_LINES = 500

BLOCKING = []
WARNINGS = []


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return ""


def is_target(path: Path) -> bool:
    if path.suffix != ".ts" or not path.name.startswith("use"):
        return False
    parts = path.parts
    return not any(part == "__tests__" for part in parts)


def is_store_target(path: Path) -> bool:
    if path.suffix != ".ts" or path.name.startswith("use"):
        return False
    parts = path.parts
    return not any(part == "__tests__" for part in parts)


def iter_composables(scope_dir: Path):
    if not scope_dir.exists():
        WARNINGS.append(f"{scope_dir.as_posix()}: 扫描目录不存在")
        return
    for path in sorted(scope_dir.rglob("use*.ts")):
        if is_target(path):
            yield path


def iter_stores(scope_dir: Path):
    if not scope_dir.exists():
        WARNINGS.append(f"{scope_dir.as_posix()}: 扫描目录不存在")
        return
    for path in sorted(scope_dir.rglob("*.ts")):
        if is_store_target(path):
            yield path


def logical_line_count(source: str) -> int:
    """FR-6 逻辑行口径：物理行 - 空行 - 整行注释。行内/行尾注释计入代码行。"""
    count = 0
    in_block = False
    in_str = None
    for line in source.splitlines():
        has_code = False
        i = 0
        while i < len(line):
            c = line[i]
            if in_str is not None:
                if c == "\\":
                    i += 2
                    continue
                if c == in_str:
                    in_str = None
                i += 1
                continue
            if in_block:
                if c == "*" and i + 1 < len(line) and line[i + 1] == "/":
                    in_block = False
                    i += 2
                    continue
                i += 1
                continue
            if c in ('"', "'", "`"):
                in_str = c
                i += 1
                continue
            if c == "/" and i + 1 < len(line) and line[i + 1] == "/":
                i = len(line)
                continue
            if c == "/" and i + 1 < len(line) and line[i + 1] == "*":
                in_block = True
                i += 2
                continue
            if not c.isspace():
                has_code = True
            i += 1
        if has_code:
            count += 1
    return count


def scan(scope_dir: Path, target_iter):
    """扫描目录，返回 {posix_relpath: logical_count}"""
    result = {}
    for path in target_iter(scope_dir):
        relative = path.relative_to(scope_dir).as_posix()
        source = read_text(path)
        if not source:
            WARNINGS.append(f"{relative}: 读取失败，已跳过")
            continue
        result[relative] = logical_line_count(source)
    return result


LEDGER_ROW_RE = re.compile(r"^\|\s*[^|]+\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*[^|]+\|")


def read_ledger(path: Path):
    """解析台账，返回 {posix_relpath: int(断言行数)}"""
    entries = {}
    if not path.exists():
        WARNINGS.append(f"{path.as_posix()}: 台账文件不存在")
        return entries
    for line in read_text(path).splitlines():
        match = LEDGER_ROW_RE.match(line)
        if not match:
            continue
        relpath, count = match.groups()
        assert_count = int(count)
        if assert_count <= MAX_LINES:
            BLOCKING.append(
                f"台账条目非法: {relpath.strip()} 登记行数 {assert_count} <= {MAX_LINES}"
            )
            continue
        entries[relpath.strip().replace("\\", "/")] = assert_count
    return entries


def main():
    parser = argparse.ArgumentParser(description="前端规模回归护栏 (FR-6 composables / FR-8 stores)")
    parser.add_argument("--print", action="store_true", help="打印全量逻辑行数(生成台账用)")
    args = parser.parse_args()

    scanned = scan(SCOPE_DIR, iter_composables)
    scanned_stores = scan(STORE_SCOPE_DIR, iter_stores)

    if args.print:
        print("[composables] (FR-6, 红线 200)")
        for relpath, count in sorted(scanned.items(), key=lambda kv: (-kv[1], kv[0])):
            mark = "OVER" if count > MAX_LINES else "ok  "
            print(f"{mark}  {count:4d}  {relpath}")
        print("[stores] (FR-8, 红线 500)")
        for relpath, count in sorted(scanned_stores.items(), key=lambda kv: (-kv[1], kv[0])):
            mark = "OVER" if count > STORE_MAX_LINES else "ok  "
            print(f"{mark}  {count:4d}  {relpath}")
        return 0

    ledger = read_ledger(LEDGER)

    over_limit = {r: c for r, c in scanned.items() if c > MAX_LINES}
    over_limit_stores = {r: c for r, c in scanned_stores.items() if c > STORE_MAX_LINES}

    for relpath in sorted(over_limit):
        if relpath not in ledger:
            BLOCKING.append(f"未登记超限 Composable: {relpath} 逻辑行数 {over_limit[relpath]} > {MAX_LINES}")

    for relpath in sorted(ledger):
        if relpath not in over_limit:
            BLOCKING.append(f"台账含已达标条目(须移除/更新): {relpath}")

    for relpath in sorted(over_limit_stores):
        BLOCKING.append(f"超限 Store 文件(严格, 无台账豁免): {relpath} 逻辑行数 {over_limit_stores[relpath]} > {STORE_MAX_LINES}")

    if BLOCKING:
        print("[FAIL] 前端规模护栏失败:")
        for item in BLOCKING:
            print(f"  - {item}")
        if WARNINGS:
            print("[WARN]")
            for item in WARNINGS:
                print(f"  - {item}")
        return 1

    print(
        f"[PASS] 前端规模护栏通过(FR-6 composables {len(scanned)} 文件 / {len(over_limit)} 超限已登记; "
        f"FR-8 stores {len(scanned_stores)} 文件 / {len(over_limit_stores)} 超限)"
    )
    if WARNINGS:
        print("[WARN]")
        for item in WARNINGS:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())