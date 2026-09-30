# -*- coding: utf-8 -*-
"""前端规模护栏（FR-6 composables / FR-8 stores）自测。

护栏：scripts/check_frontend_invariants.py（进程内调用 main()，--root/--ledger 注入夹具）。
FR-6 相对扫描根=composables/，台账行用「use_*.ts」带目录相对名；FR-8 相对扫描根=stores/。
断言面：
  1. 未登记超限 composable → 红
  2. 台账条目已达标未移除 → 红
  3. 台账登记行数 <=200 非法 → 红
  4. 台账与扫描一致 → 绿
  5. store 超 500 严格模式 → 红（无台账豁免）
  6. 真实仓库默认路径 → 绿
"""

import check_frontend_invariants as fr
from helpers import FR6_LEDGER_HEADER, assign_lines, fr6_row, write

USE_FILE = "composables/use_big.ts"
STORE_FILE = "stores/big_store.ts"
# FR-6 台账行路径相对 composables/ 扫描根
USE_LEDGER_REL = "use_big.ts"


def _run(tmp_path, ledger_text, files=None):
    files = files or {USE_FILE: assign_lines(205)}
    (tmp_path / "vue-assetmanagement" / "src" / "stores").mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        write(tmp_path / "vue-assetmanagement" / "src" / rel, text)
    ledger = write(tmp_path / "Rules_Fiels" / "FR6_composable_ledger.md", ledger_text)
    return fr.main(["--root", str(tmp_path), "--ledger", str(ledger)])


def test_unregistered_over_limit_composable_red(tmp_path, capsys):
    rc = _run(tmp_path, FR6_LEDGER_HEADER)
    out = capsys.readouterr().out
    assert rc == 1
    assert "未登记超限 Composable" in out and USE_LEDGER_REL in out


def test_stale_ledger_entry_is_red(tmp_path, capsys):
    ledger = FR6_LEDGER_HEADER + fr6_row(USE_LEDGER_REL, 205)
    rc = _run(tmp_path, ledger, files={USE_FILE: "export const a = 1;\n"})  # 已达标
    out = capsys.readouterr().out
    assert rc == 1
    assert "台账含已达标条目" in out


def test_invalid_registered_count_is_red(tmp_path, capsys):
    ledger = FR6_LEDGER_HEADER + fr6_row(USE_LEDGER_REL, 200)  # 200 <= 200 非法
    rc = _run(tmp_path, ledger)
    out = capsys.readouterr().out
    assert rc == 1
    assert "登记行数 200 <= 200" in out


def test_green_when_ledger_matches(tmp_path, capsys):
    ledger = FR6_LEDGER_HEADER + fr6_row(USE_LEDGER_REL, 205)
    rc = _run(tmp_path, ledger, files={USE_FILE: assign_lines(205), STORE_FILE: "export const s = 1;\n"})
    assert rc == 0
    assert "[PASS]" in capsys.readouterr().out


def test_store_over_500_strict_red(tmp_path, capsys):
    rc = _run(tmp_path, FR6_LEDGER_HEADER, files={STORE_FILE: assign_lines(505)})
    out = capsys.readouterr().out
    assert rc == 1
    assert "超限 Store 文件" in out and "big_store.ts" in out


def test_real_repo_default_root_green(capsys):
    assert fr.main([]) == 0
    assert "[PASS]" in capsys.readouterr().out