# -*- coding: utf-8 -*-
"""[M-34] FR-5 .vue 行数护栏自测：逐条断言先证红，再证绿。

护栏：scripts/check_frontend_invariants.py（进程内调用 main()，--root/--ledger 注入夹具）。
断言面：
  1. 未登记超长 .vue（template+script 和 > 500）→ 红（防新增回潮）
  2. 恰好 500 逻辑行 → 绿（边界不误伤）
  3. 非 setup 存量 <script> 超长同样被拦（script 段匹配放宽 '<script' 防逃逸）
"""

import check_frontend_invariants as fr

VUE_RELPATH = "views/Huge.vue"


def _vue_source(script_lines: int, setup: bool = True) -> str:
    tag = "<script setup>" if setup else "<script>"
    body = "\n".join(f"const v{i} = {i}" for i in range(script_lines))
    return f"<template>\n  <div>demo</div>\n</template>\n\n{tag}\n{body}\n</script>\n"


def _run(tmp_path, source, vue_ledger_text):
    (tmp_path / "vue-assetmanagement" / "src" / VUE_RELPATH).parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / "vue-assetmanagement" / "src" / VUE_RELPATH).write_text(
        source, encoding="utf-8"
    )
    # composables/stores 目录留空（FR-6/FR-8 零文件，仅 FR-5 断言面）
    ledger = tmp_path / "Rules_Fiels" / "FR6_composable_ledger.md"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("", encoding="utf-8")
    vue_ledger = tmp_path / "Rules_Fiels" / "FR5_vue_ledger.md"
    vue_ledger.write_text(vue_ledger_text, encoding="utf-8")
    return fr.main(
        [
            "--root",
            str(tmp_path),
            "--ledger",
            str(ledger),
            "--vue-ledger",
            str(vue_ledger),
        ]
    )


def test_unregistered_over_limit_vue_is_red(tmp_path, capsys):
    """501 逻辑行未登记 → 退出码 1 且错误含文件路径"""
    # template 1 有效行 + script 500 = 501 > 500
    rc = _run(tmp_path, _vue_source(500), "")
    out = capsys.readouterr().out
    assert rc == 1
    assert "未登记超限 .vue 文件" in out and VUE_RELPATH in out


def test_exactly_500_lines_passes(tmp_path):
    """恰好 500（边界）→ 通过（退出码 0）"""
    # template 1 有效行 + script 499 = 500，不越线
    rc = _run(tmp_path, _vue_source(499), "")
    assert rc == 0


def test_non_setup_script_over_limit_also_blocked(tmp_path, capsys):
    """存量非 setup <script> 超长同样被拦（防逃逸）"""
    rc = _run(tmp_path, _vue_source(500, setup=False), "")
    out = capsys.readouterr().out
    assert rc == 1
    assert VUE_RELPATH in out
