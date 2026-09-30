# -*- coding: utf-8 -*-
"""scripts/tests 夹具助手 —— 护栏负向/正向测试的公共构造。

所有夹具均在 pytest tmp_path 下按需生成，**绝不触碰真实仓库**。
真实仓库回归用例（无 --root 默认路径）单独在各自 test 文件中给出。
"""

from pathlib import Path


def write(path: Path, text: str) -> Path:
    """以 UTF-8（无 BOM，避免触发护栏 read_text 的 utf-8-sig 分支）写入文件并创建父目录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def assign_lines(n: int) -> str:
    """生成 n 行缩进赋值语句（每行计 1 逻辑行；用于函数体内）。"""
    return "".join(f"        v{i} = {i}\n" for i in range(n))


def assign_module_lines(n: int) -> str:
    """生成 n 行模块级赋值语句（合法 Python，每行计 1 逻辑行；用于文件级夹具）。"""
    return "".join(f"v{i} = {i}\n" for i in range(n))


# ---- BR-4 台账模板（活跃分区 + 9 列行）----
BR4_LEDGER_HEADER = """# BR-4 函数长度台账（测试夹具）

## 活跃台账（Active）

| 批次 | 文件 | 行号 | 函数 | 逻辑行数 | 拆分目标 | 回归锚 | 风险 | 状态 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
"""


def br4_row(relpath: str, lineno: int, func: str, count: int) -> str:
    return f"| A | {relpath} | {lineno} | {func} | {count} | - | - | - | 活跃 |"


# ---- BR-6 台账模板（活跃分区 + 2 列行）----
BR6_LEDGER_HEADER = """# BR-6 文件长度台账（测试夹具）

## 活跃台账（Active）

| 文件 | 逻辑行数 | 状态 |
|:---|:---|:---|
"""


def br6_row(relpath: str, count: int) -> str:
    return f"| {relpath} | {count} | 活跃 |"


# ---- FR-6 台账模板（前端护栏当前整文件解析，无分区）----
FR6_LEDGER_HEADER = """# FR-6 composable 台账（测试夹具）

| 批次 | 文件 | 逻辑行数 | 状态 |
|:---|:---|:---|:---|
"""


def fr6_row(relpath: str, count: int) -> str:
    return f"| FR6 | {relpath} | {count} | 活跃 |"