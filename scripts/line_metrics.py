# -*- coding: utf-8 -*-
"""逻辑行数口径 (Logical Line Metrics) —— BR-4 / BR-6 护栏的唯一事实来源

本模块是「逻辑行数」计算与 Python 文件遍历的**唯一实现**（DR-1 单一实现）。
`check_function_length_guard.py`（BR-4）与 `check_file_length_guard.py`（BR-6）
均从此处导入，禁止任一护栏再内联第二份实现。

口径定义（BR-4 采纳 BR-6 统一口径，2026-09-29）
------------------------------------------------
逻辑行数 = 物理跨度行数 - 空行 - 纯 '#' 注释行 - 本节点 docstring 覆盖的行

排除项：
  1. 空行（`strip()` 后为空）
  2. 纯注释行（`strip()` 后以 '#' 开头）
  3. 本节点（模块 / 函数）的 docstring——即 `body[0]` 为字符串常量表达式时，
     其 `lineno..end_lineno` 覆盖的全部行。

排除 docstring 的理由：docstring 属说明性文字，不构成逻辑密度；
将其计入会让「文档写得详尽」的模块在规模口径上被不当惩罚。

⚠️ 数行数口径警告
------------------
PowerShell 的 `Measure-Object -Line` **会跳过空行**，同一文件可低估约 12%
（例：`operation_log_service.py` 真实 508 行，`Measure-Object -Line` 报 447）。
本项目历史上已因 `wc -l`（含空行 508）与逻辑口径（444）混用导致两次误判，
一律以本模块结果为准，**不要**用 PowerShell 速查行数。
"""

import ast
from pathlib import Path

__all__ = [
    "read_text",
    "iter_py_files",
    "is_migration",
    "is_test",
    "docstring_line_numbers",
    "logical_line_count",
    "parse_module",
    "active_ledger_lines",
]


def read_text(path: Path) -> str:
    """按 utf-8-sig -> utf-8 -> gbk 顺序解码；全部失败返回空串。

    必须以 `utf-8-sig` 打头：Windows 上 `Set-Content -Encoding UTF8` 等工具会写入
    BOM，若用 `utf-8` 解码，BOM 会变成源码首字符 U+FEFF，导致 `ast.parse` 抛
    SyntaxError，进而使该文件被护栏**静默跳过**——超限文件可因此蒙混过关（假绿）。
    `utf-8-sig` 对有无 BOM 的 UTF-8 均能正确解码。
    """
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return ""


def iter_py_files(scope_dir: Path):
    """递归产出 scope_dir 下所有 .py 文件。"""
    if not scope_dir.exists():
        return
    for path in scope_dir.rglob("*.py"):
        yield path


def is_migration(path: Path) -> bool:
    return any(part == "migrations" for part in path.parts)


def is_test(path: Path) -> bool:
    """测试文件判定：文件名含 test/conftest，或路径含 tests/ test/ 段。"""
    name = path.name
    if "test" in name.lower() or "conftest" in name.lower():
        return True
    return any(part in ("tests", "test") for part in path.parts)


def docstring_line_numbers(node: ast.AST) -> set[int]:
    """返回本节点 docstring 覆盖的行号集合；无 docstring 则空集。"""
    body = getattr(node, "body", None)
    if not body:
        return set()
    first = body[0]
    if not isinstance(first, ast.Expr):
        return set()
    value = first.value
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        return set()
    return set(range(first.lineno, (first.end_lineno or first.lineno) + 1))


def logical_line_count(source: str, node: ast.AST) -> int:
    """按统一口径统计 node 的逻辑行数（空行 / '#' 注释 / 本节点 docstring 均剔除）。

    node 为 ast.Module 时（BR-6 文件级统计）无 lineno，按整份文件跨度处理：
    start 记为 1，end 记为文件总行数。
    """
    lines = source.splitlines()
    start = getattr(node, "lineno", None) or 1
    end = getattr(node, "end_lineno", None) or len(lines)
    skip = docstring_line_numbers(node)
    count = 0
    for lineno in range(start, end + 1):
        if lineno in skip:
            continue
        stripped = lines[lineno - 1].strip()
        if not stripped or stripped.startswith("#"):
            continue
        count += 1
    return count


def parse_module(source: str) -> ast.Module:
    """解析源码为 AST；SyntaxError 由调用方处理。"""
    return ast.parse(source)


ACTIVE_SECTION_TITLE = "## 活跃台账"


def active_ledger_lines(text: str) -> list[str]:
    """切片出台账的「活跃」分区行——'## 活跃台账' 标题起，至下一个 '## ' 标题（含）止。

    三个护栏（BR-4 / BR-6 / FR-6）共用，保证「已关闭存档」行永不被当成活跃断言。
    台账必须显式声明活跃区；若缺失该标题，返回空表（护栏对超限零豁免 = 安全向失败）。
    """
    lines = text.splitlines()
    result = []
    active = False
    for line in lines:
        if line.startswith("## "):
            if active:
                break
            active = ACTIVE_SECTION_TITLE in line
            continue
        if active:
            result.append(line)
    return result
