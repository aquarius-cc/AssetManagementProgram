# -*- coding: utf-8 -*-
"""[M-34] FR-5 .vue 行数护栏自测：逐条断言先证红，再证绿。

护栏：scripts/check_frontend_invariants.py（进程内调用 main()，--root/--ledger 注入夹具）。
断言面：
  1. 未登记超长 .vue（template+script 和 > 500）→ 红（防新增回潮）
  2. 恰好 500 逻辑行 → 绿（边界不误伤）
  3. 非 setup 存量 <script> 超长同样被拦（script 段匹配放宽 '<script' 防逃逸）
  4. FR-8 stores：is_store_target 目录全量边界（OP-06）——userStore.ts 不得因
     "use" 前缀被误排除（先证红后证绿，红态 3 failed 为预期基线）
"""

from pathlib import Path

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


# --------------------------------------------------------------------------
# FR-8 stores：is_store_target 目录全量边界（OP-06，先证红后证绿）
# --------------------------------------------------------------------------


def _write_store(tmp_path, name: str, logic_lines: int) -> None:
    store_dir = tmp_path / "vue-assetmanagement" / "src" / "stores"
    store_dir.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"const v{i} = {i}" for i in range(logic_lines))
    (store_dir / name).write_text(body + "\n", encoding="utf-8")


def _store_run(tmp_path):
    """store 夹具 + 空 FR-6/FR-5 台账（store 超限严格无台账豁免）"""
    ledger = tmp_path / "Rules_Fiels" / "FR6_composable_ledger.md"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("", encoding="utf-8")
    vue_ledger = tmp_path / "Rules_Fiels" / "FR5_vue_ledger.md"
    vue_ledger.write_text("", encoding="utf-8")
    return fr.main(["--root", str(tmp_path), "--ledger", str(ledger), "--vue-ledger", str(vue_ledger)])


def test_store_named_userstore_over_limit_is_red(tmp_path, capsys):
    """stores/userStore.ts 501 逻辑行 → rc=1（红态基线：现状前缀排除使其假绿 rc=0 → fail）"""
    _write_store(tmp_path, "userStore.ts", 501)
    rc = _store_run(tmp_path)
    out = capsys.readouterr().out
    assert rc == 1
    assert "userStore.ts" in out


def test_store_exactly_500_lines_passes(tmp_path):
    """stores 恰好 500 逻辑行 → 边界不误伤 rc=0"""
    _write_store(tmp_path, "userStore.ts", 500)
    rc = _store_run(tmp_path)
    assert rc == 0


def test_store_target_ignores_use_prefix():
    """is_store_target 不再按 use 前缀排除（红态基线：现实现返回 False → fail）"""
    p = Path("vue-assetmanagement/src/stores/userStore.ts")
    assert fr.is_store_target(p) is True


def test_real_repo_userstore_is_scanned():
    """真实仓库 iter_stores 集合含 userStore.ts（红态基线：缺席 → fail）"""
    scanned = os_set = {p.name for p in fr.iter_stores(fr.STORE_SCOPE_DIR)}
    assert "userStore.ts" in scanned


def test_real_repo_default_root_green(capsys):
    """默认根真仓全量 → rc=0（防旧实现回潮误伤）"""
    assert fr.main([]) == 0
    assert "[PASS]" in capsys.readouterr().out
