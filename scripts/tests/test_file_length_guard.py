# -*- coding: utf-8 -*-
"""BR-6 文件长度护栏自测：逐条断言先证红，再证绿。

护栏：scripts/check_file_length_guard.py（进程内调用 main()，--root/--ledger 注入夹具）。
断言面：
  1. 未登记超长文件 → 红（防新增回潮）
  2. 台账条目已达标未移除 → 红（防台账腐烂）
  3. 台账登记行数 <=500 非法 → 红
  4. 台账与扫描一致 → 绿
  5. 模块 docstring 不计数（口径，超大 span 由文档撑起）→ 绿
  6. 真实仓库默认路径 → 绿
"""

import check_file_length_guard as br6
from helpers import BR6_LEDGER_HEADER, assign_module_lines, br6_row, write

# BR-6 以后端根为基准：文件放 asset_management_backend/apps/<RELPATH>，台账行用相对后端根的路径
RELPATH = "apps/mod.py"


def _run(tmp_path, ledger_text, source):
    write(tmp_path / "asset_management_backend" / RELPATH, source)
    ledger = write(tmp_path / "Rules_Fiels" / "BR6_file_length_ledger.md", ledger_text)
    return br6.main(["--root", str(tmp_path), "--ledger", str(ledger)])


def test_unregistered_over_limit_file_is_red(tmp_path, capsys):
    source = assign_module_lines(520)
    rc = _run(tmp_path, BR6_LEDGER_HEADER, source)
    out = capsys.readouterr().out
    assert rc == 1
    assert "未登记超长文件" in out and RELPATH in out


def test_stale_ledger_entry_is_red(tmp_path, capsys):
    source = assign_module_lines(5)  # 已达标
    ledger = BR6_LEDGER_HEADER + br6_row(RELPATH, 520)
    rc = _run(tmp_path, ledger, source)
    out = capsys.readouterr().out
    assert rc == 1
    assert "台账含已达标条目" in out and RELPATH in out


def test_invalid_registered_count_is_red(tmp_path, capsys):
    source = assign_module_lines(520)
    ledger = BR6_LEDGER_HEADER + br6_row(RELPATH, 500)  # 500 <= 500 非法
    rc = _run(tmp_path, ledger, source)
    out = capsys.readouterr().out
    assert rc == 1
    assert "登记行数 500 <= 500" in out


def test_green_when_ledger_matches(tmp_path, capsys):
    source = assign_module_lines(520)
    ledger = BR6_LEDGER_HEADER + br6_row(RELPATH, 520)
    rc = _run(tmp_path, ledger, source)
    assert rc == 0
    assert "[PASS]" in capsys.readouterr().out


def test_module_docstring_not_counted_green(tmp_path, capsys):
    doc = '"""' + "\n".join(["doc"] * 30) + '"""\n'
    source = doc + assign_module_lines(480)  # 物理 511 行，逻辑 480 行 < 500
    rc = _run(tmp_path, BR6_LEDGER_HEADER, source)
    assert rc == 0
    assert "[PASS]" in capsys.readouterr().out


def test_real_repo_default_root_green(capsys):
    rc = br6.main([])
    assert rc == 0
    assert "[PASS]" in capsys.readouterr().out
