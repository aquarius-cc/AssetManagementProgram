# -*- coding: utf-8 -*-
"""账本一致性护栏（BF-172/173/183 标题↔正文错位 + 编号空缺/乱序治理，D1）。

断言面（违反任一即红）：
  1. BF 编号唯一（同号重复登记 = 撞号）
  2. H2/H3 标题状态 ∈ 规范词表（已关闭 允许 ·WAI/·已闭档/·已闭环/·已修复/·已核实 后缀）
  3. 标题状态 == 正文末条 `状态：【…】`（正文存在该标记时才比对其间错位，
     如 BF-172/173 正文已【已关闭】而标题停在【已修复·待提交】的失真形态）
  4. 禁止 `### BF-` 混排（BF 条目一律 H2；### 仅用于条目内小节）

用法：
    python scripts/check_ledger_consistency.py                # 默认按 __file__ 推导
    python scripts/check_ledger_consistency.py --root <repo> --ledger <path>
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LEDGER_RELATIVE = Path("docs") / "BugFixed" / "Bug修复活账本.md"

#: 规范状态词表（8 个；已关闭允许白名单后缀）
CANONICAL_BASE = {
    "已关闭",
    "部分关闭",
    "待修复",
    "待验证",
    "待决策",
    "评估中",
    "收口中",
    "进行中",
}
CLOSED_SUFFIXES = {"", "·WAI", "·已闭档", "·已闭环", "·已修复", "·已核实"}

HEADER_RE = re.compile(r"^(#{2,3}) (BF-\d+)【([^】]*)】")
BODY_STATUS_RE = re.compile(r"状态：【([^】]*)】")
CANONICAL_NOTE = "规范状态词表（2026-11-19 校准批）"


def _canonical(status: str) -> bool:
    base = status.split("·", 1)[0]
    if base != "已关闭":
        return status in CANONICAL_BASE
    return status in {f"已关闭{suffix}" for suffix in CLOSED_SUFFIXES}


def audit(ledger_path: Path) -> list[str]:
    problems: list[str] = []
    lines = ledger_path.read_text(encoding="utf-8").splitlines()

    seen: dict[str, int] = {}
    current: dict[str, object] | None = None
    entries: list[dict[str, object]] = []
    for index, line in enumerate(lines, 1):
        match = HEADER_RE.match(line)
        if match:
            if current:
                entries.append(current)
            current = {
                "level": len(match.group(1)),
                "code": match.group(2),
                "status": match.group(3),
                "line": index,
                "body": [],
            }
            continue
        if current:
            current["body"].append(line)  # type: ignore[union-attr]
    if current:
        entries.append(current)

    for entry in entries:
        code = str(entry["code"])
        status = str(entry["status"])
        line_no = int(entry["line"])

        if not _canonical(status):
            problems.append(f"{ledger_path.name}:{line_no} {code}：标题状态【{status}】不在规范词表")

        body_status = [
            m.group(1) for m in (BODY_STATUS_RE.search(line) for line in entry["body"]) if m
        ]
        if body_status:
            last = body_status[-1]
            last_base = last.split("（", 1)[0]
            title_base = status.split("·", 1)[0]
            if "关闭" in last_base and title_base == "已关闭":
                pass  # 标题已关闭 + 正文已关闭（可带日期括注）= 一致
            elif last_base != title_base and not (
                title_base == "待验证" and last_base in {"已修复·待提交", "已提交"}
            ):
                problems.append(
                    f"{ledger_path.name}:{line_no} {code}：标题【{status}】与正文末状态【{last}】错位"
                )

    # 编号唯一
    codes = [str(e["code"]) for e in entries]
    for code in sorted({c for c in codes if codes.count(c) > 1}):
        problems.append(f"{ledger_path.name}: 编号 {code} 重复登记（撞号）")

    # ### BF- 混排
    for index, line in enumerate(lines, 1):
        if line.startswith("### BF-"):
            problems.append(f"{ledger_path.name}:{index}：BF 条目混用 ### 层级（一律 H2）")

    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="账本一致性护栏：编号唯一 / 标题状态规范 / 标题与正文末状态对齐 / 无 ### 混排"
    )
    parser.add_argument("--root", default=None, help="仓库根目录（默认按 __file__ 推导）")
    parser.add_argument("--ledger", default=None, help="账本路径（默认 docs/BugFixed/Bug修复活账本.md）")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    ledger = Path(args.ledger).resolve() if args.ledger else root / LEDGER_RELATIVE

    if not ledger.exists():
        print(f"[FAIL] 账本不存在：{ledger}")
        return 1
    text = ledger.read_text(encoding="utf-8")
    if CANONICAL_NOTE not in text:
        print(f"[FAIL] {ledger.name}: 头部缺规范状态词表（{CANONICAL_NOTE}）")
        return 1
    problems = audit(ledger)
    if problems:
        print("[FAIL] 账本一致性护栏未通过：")
        for item in problems:
            print("   - " + item)
        return 1
    print("[PASS] 账本一致性护栏全绿：编号唯一 / 标题状态规范 / 标题与正文末状态对齐 / 无 ### 混排")
    return 0


if __name__ == "__main__":
    sys.exit(main())
