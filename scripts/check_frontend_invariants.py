# -*- coding: utf-8 -*-
"""前端规模回归护栏 (Frontend Size Regression Guard)

三条子规则，计数统一走 logical_line_count（与后端 BR-4 guard 的
logical_line_count 对齐：BR-4 为物理跨度行数 - 空行 - '#' 注释行；TS
对应去除块注释/行注释，因 TS 无 docstring）：

  FR-5 (.vue)：检查 src/**/*.vue 的 template+script 两段逻辑行之和是否超过 500。
       script 段匹配放宽为 '<script'（覆盖 <script setup> 与存量非 setup，防逃逸）；
       template 段计「非空且非纯 <!-- --> 行」。台账：
       Rules_Fiels/FR5_vue_ledger.md（断言规则与 FR-6 同型，超限未登记即红、
       台账条目已达标未移除即红）。

  FR-6 (composables)：检查 composables 目录下所有 use*.ts 文件逻辑行是否超过 200。
       台账（豁免登记表）为唯一事实来源：Rules_Fiels/FR6_composable_ledger.md
       断言规则：
         1. 扫描出的每个逻辑行 > 200 的 composable，必须已登记台账（未登记即红，防新增回潮）。
         2. 台账中的每个条目，当前逻辑行数必须仍 > 200（已拆分/删除未移除即红，防台账腐烂）。
         3. 台账条目登记的断言行数必须 > 200（数值手写非法即红）。

  FR-8 (stores)：检查 stores 目录下所有 *.ts（非 use*.ts）文件逻辑行是否超过 500。
       严格模式：超限即红，无台账豁免（当前全仓 stores 均 ≤500，无存量登记必需）。

逻辑行口径（FR-6 条文，FR-8/FR-5 script 段沿用）：逻辑行 = 物理行 - 空行 - 整行注释；
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

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
ROOT = DEFAULT_ROOT
SCOPE_DIR = ROOT / "vue-assetmanagement" / "src" / "composables"
STORE_SCOPE_DIR = ROOT / "vue-assetmanagement" / "src" / "stores"
VUE_SCOPE_DIR = ROOT / "vue-assetmanagement" / "src"
LEDGER = ROOT / "Rules_Fiels" / "FR6_composable_ledger.md"
VUE_LEDGER = ROOT / "Rules_Fiels" / "FR5_vue_ledger.md"

MAX_LINES = 200
STORE_MAX_LINES = 500
VUE_MAX_LINES = 500

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


def is_vue_target(path: Path) -> bool:
    """[M-34] FR-5 目标：src/**/*.vue（排除 __tests__）"""
    if path.suffix != ".vue":
        return False
    parts = path.parts
    return not any(part == "__tests__" for part in parts)


def iter_vue_files(scope_dir: Path):
    if not scope_dir.exists():
        WARNINGS.append(f"{scope_dir.as_posix()}: 扫描目录不存在")
        return
    for path in sorted(scope_dir.rglob("*.vue")):
        if is_vue_target(path):
            yield path


def extract_vue_sections(source: str):
    """[M-34] 提取顶层 <template>…</template> 与 <script…>…</script> 行段。

    template 支持嵌套（slot 具名模板），按标签深度取第一个顶层块；
    script 匹配放宽为 '<script'（同时覆盖 <script setup> 与存量非 setup，防逃逸）。
    返回 (template_lines, script_lines)。
    """
    template_lines: list[str] = []
    script_lines: list[str] = []
    section = None
    depth = 0
    for line in source.splitlines():
        stripped = line.strip()
        if section is None:
            if re.match(r"^<template(\s|>)", stripped):
                section, depth = "template", 1
                continue
            if re.match(r"^<script(\s|>|/)", stripped):
                section, depth = "script", 1
                continue
            continue
        if section == "template":
            opens = len(re.findall(r"<template(\s|>)", stripped))
            closes = len(re.findall(r"</template>", stripped))
            depth += opens - closes
            if depth <= 0:
                section = None
                continue
            template_lines.append(line)
        else:
            if "</script" in stripped:
                section = None
                continue
            script_lines.append(line)
    return template_lines, script_lines


def template_effective_lines(lines: list[str]) -> int:
    """[M-34] template 段口径：非空且非纯 <!-- --> 注释行（跨行注释块按行首判定）。"""
    count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            continue
        count += 1
    return count


def vue_logic_line_count(source: str) -> int:
    """[M-34] FR-5 口径：template 有效行 + script 逻辑行（logical_line_count）。"""
    template_lines, script_lines = extract_vue_sections(source)
    return template_effective_lines(template_lines) + logical_line_count("\n".join(script_lines))


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


def scan(scope_dir: Path, target_iter, counter=None):
    """扫描目录，返回 {posix_relpath: logical_count}（counter 缺省 TS 口径）"""
    if counter is None:
        counter = logical_line_count
    result = {}
    for path in target_iter(scope_dir):
        relative = path.relative_to(scope_dir).as_posix()
        source = read_text(path)
        if not source:
            WARNINGS.append(f"{relative}: 读取失败，已跳过")
            continue
        result[relative] = counter(source)
    return result


LEDGER_ROW_RE = re.compile(r"^\|\s*[^|]+\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*[^|]+\|")


def read_ledger(path: Path, min_count: int = MAX_LINES):
    """解析台账，返回 {posix_relpath: int(断言行数)}（min_count 为登记合法性下限）"""
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
        if assert_count <= min_count:
            BLOCKING.append(
                f"台账条目非法: {relpath.strip()} 登记行数 {assert_count} <= {min_count}"
            )
            continue
        entries[relpath.strip().replace("\\", "/")] = assert_count
    return entries


def main(argv=None):
    global ROOT, SCOPE_DIR, STORE_SCOPE_DIR, VUE_SCOPE_DIR, LEDGER, VUE_LEDGER
    parser = argparse.ArgumentParser(description="前端规模回归护栏 (FR-5 .vue / FR-6 composables / FR-8 stores)")
    parser.add_argument("--print", action="store_true", help="打印全量逻辑行数(生成台账用)")
    parser.add_argument("--root", type=Path, default=None, help="扫描根目录(默认仓库根)")
    parser.add_argument("--ledger", type=Path, default=None, help="台账路径(默认 Rules_Fiels/FR6_composable_ledger.md)")
    parser.add_argument("--vue-ledger", type=Path, default=None, help="FR-5 台账路径(默认 Rules_Fiels/FR5_vue_ledger.md)")
    args = parser.parse_args(argv)

    BLOCKING.clear()
    WARNINGS.clear()
    ROOT = args.root if args.root is not None else DEFAULT_ROOT
    SCOPE_DIR = ROOT / "vue-assetmanagement" / "src" / "composables"
    STORE_SCOPE_DIR = ROOT / "vue-assetmanagement" / "src" / "stores"
    VUE_SCOPE_DIR = ROOT / "vue-assetmanagement" / "src"
    LEDGER = args.ledger if args.ledger is not None else ROOT / "Rules_Fiels" / "FR6_composable_ledger.md"
    VUE_LEDGER = args.vue_ledger if args.vue_ledger is not None else ROOT / "Rules_Fiels" / "FR5_vue_ledger.md"

    scanned = scan(SCOPE_DIR, iter_composables)
    scanned_stores = scan(STORE_SCOPE_DIR, iter_stores)
    # [M-34] FR-5 必须用 .vue 口径（template 有效行 + script 逻辑行），
    # 复用 scan 的 TS 口径会把 <template>/<script> 标签行一并计入（504−2=502 假超限）
    scanned_vue = scan(VUE_SCOPE_DIR, iter_vue_files, counter=vue_logic_line_count)

    if args.print:
        print("[composables] (FR-6, 红线 200)")
        for relpath, count in sorted(scanned.items(), key=lambda kv: (-kv[1], kv[0])):
            mark = "OVER" if count > MAX_LINES else "ok  "
            print(f"{mark}  {count:4d}  {relpath}")
        print("[stores] (FR-8, 红线 500)")
        for relpath, count in sorted(scanned_stores.items(), key=lambda kv: (-kv[1], kv[0])):
            mark = "OVER" if count > STORE_MAX_LINES else "ok  "
            print(f"{mark}  {count:4d}  {relpath}")
        print("[.vue] (FR-5, 红线 500)")
        for relpath, count in sorted(scanned_vue.items(), key=lambda kv: (-kv[1], kv[0])):
            mark = "OVER" if count > VUE_MAX_LINES else "ok  "
            print(f"{mark}  {count:4d}  {relpath}")
        return 0

    ledger = read_ledger(LEDGER)
    vue_ledger = read_ledger(VUE_LEDGER, min_count=VUE_MAX_LINES)

    over_limit = {r: c for r, c in scanned.items() if c > MAX_LINES}
    over_limit_stores = {r: c for r, c in scanned_stores.items() if c > STORE_MAX_LINES}
    over_limit_vue = {r: c for r, c in scanned_vue.items() if c > VUE_MAX_LINES}

    for relpath in sorted(over_limit):
        if relpath not in ledger:
            BLOCKING.append(f"未登记超限 Composable: {relpath} 逻辑行数 {over_limit[relpath]} > {MAX_LINES}")

    for relpath in sorted(ledger):
        if relpath not in over_limit:
            BLOCKING.append(f"台账含已达标条目(须移除/更新): {relpath}")

    for relpath in sorted(over_limit_stores):
        BLOCKING.append(f"超限 Store 文件(严格, 无台账豁免): {relpath} 逻辑行数 {over_limit_stores[relpath]} > {STORE_MAX_LINES}")

    # [M-34] FR-5：.vue 超限须登记 FR5_vue_ledger.md（未登记即红；已达标未移除即红）
    for relpath in sorted(over_limit_vue):
        if relpath not in vue_ledger:
            BLOCKING.append(f"未登记超限 .vue 文件: {relpath} 逻辑行数 {over_limit_vue[relpath]} > {VUE_MAX_LINES}")

    for relpath in sorted(vue_ledger):
        if relpath not in over_limit_vue:
            BLOCKING.append(f"FR-5 台账含已达标条目(须移除/更新): {relpath}")

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
        f"FR-8 stores {len(scanned_stores)} 文件 / {len(over_limit_stores)} 超限; "
        f"FR-5 .vue {len(scanned_vue)} 文件 / {len(over_limit_vue)} 超限已登记)"
    )
    if WARNINGS:
        print("[WARN]")
        for item in WARNINGS:
            print(f"  - {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())