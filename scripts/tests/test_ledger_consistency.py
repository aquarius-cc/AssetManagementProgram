# -*- coding: utf-8 -*-
"""账本一致性护栏自测（BF-172/173 标题错位实证型，D1）：先证红，再证绿。"""
from pathlib import Path

import check_ledger_consistency as guard

HEADER = "docs/BugFixed/Bug修复活账本.md"

LEDGER_GREEN = """# Bug 修复活账本

> **规范状态词表（2026-11-19 校准批）**：`已关闭` / `部分关闭` / `待修复` / `待验证` / `待决策` / `评估中` / `收口中` / `进行中`。

## BF-001【已关闭】示例条目

- 状态：【已关闭】（2026-01-01）
"""

LEDGER_MISMATCH = """# Bug 修复活账本

> **规范状态词表（2026-11-19 校准批）**：`已关闭` / `部分关闭` / `待修复` / `待验证` / `待决策` / `评估中` / `收口中` / `进行中`。

## BF-172【已修复·待提交】批次 4 前端 UX 五件

- 状态：【已关闭】（2026-11-04）
"""

LEDGER_MIXED_LEVEL = """# Bug 修复活账本

> **规范状态词表（2026-11-19 校准批）**：`已关闭` / `待修复`。

## BF-001【已关闭】示例条目

### BF-002【已关闭】混排条目
"""

LEDGER_NONCANONICAL = """# Bug 修复活账本

> **规范状态词表（2026-11-19 校准批）**：`已关闭` / `待修复`。

## BF-165【WAI 关闭】留痕条目
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "Bug修复活账本.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_aligned_green(tmp_path):
    assert guard.audit(_write(tmp_path, LEDGER_GREEN)) == []


def test_title_body_mismatch_red(tmp_path):
    problems = guard.audit(_write(tmp_path, LEDGER_MISMATCH))
    assert any("BF-172" in p and "错位" in p for p in problems)


def test_mixed_heading_level_red(tmp_path):
    problems = guard.audit(_write(tmp_path, LEDGER_MIXED_LEVEL))
    assert any("### 层级" in p for p in problems)


def test_noncanonical_status_red(tmp_path):
    problems = guard.audit(_write(tmp_path, LEDGER_NONCANONICAL))
    assert any("不在规范词表" in p for p in problems)


def test_duplicate_code_red(tmp_path):
    text = LEDGER_GREEN + "\n## BF-001【已关闭】重复登记\n\n- 状态：【已关闭】\n"
    problems = guard.audit(_write(tmp_path, text))
    assert any("撞号" in p for p in problems)


def test_real_repo_green():
    root = Path(guard.__file__).resolve().parent.parent
    assert guard.audit(root / HEADER) == []


def test_canonical_suffixes_accepted():
    assert guard._canonical("已关闭")
    assert guard._canonical("已关闭·WAI")
    assert guard._canonical("已关闭·已闭环")
    assert not guard._canonical("已修复·待提交")
    assert not guard._canonical("WAI 关闭")
