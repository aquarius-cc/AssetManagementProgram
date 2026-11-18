# -*- coding: utf-8 -*-
"""BR-4 函数长度护栏自测：逐条断言先证红，再证绿。

护栏：scripts/check_function_length_guard.py（进程内调用 main()，--root/--ledger 注入夹具）。
断言面：
  1. 未登记超长函数 → 红（防新增回潮）
  2. 台账条目已达标未移除 → 红（防台账腐烂）
  3. 台账登记行数 <=50 非法 → 红
  4. 台账与扫描一致 → 绿
  5. 函数 docstring 不计数（口径）→ 绿
  6. 真实仓库默认路径 → 绿（护栏默认行为不受 --root 改造影响）
"""

import check_function_length_guard as br4
from helpers import BR4_LEDGER_HEADER, assign_lines, br4_row, write

# BR-4 以 apps/ 为扫描根：文件放 asset_management_backend/apps/<MOD>，台账行用相对 apps/ 的路径
MOD = "mod.py"
BIGFUNC = "big"


def _run(tmp_path, ledger_text, source, func_name=BIGFUNC, lineno=1):
    write(tmp_path / "asset_management_backend" / "apps" / MOD, source)
    ledger = write(tmp_path / "Rules_Fiels" / "BR4_function_length_ledger.md", ledger_text)
    return br4.main(["--root", str(tmp_path), "--ledger", str(ledger)])


def _big_func(n):
    return f"def {BIGFUNC}():\n" + assign_lines(n)


def test_unregistered_over_limit_is_red(tmp_path, capsys):
    source = _big_func(57)  # def 行 1 + 56 赋值行
    rc = _run(tmp_path, BR4_LEDGER_HEADER, source)
    out = capsys.readouterr().out
    assert rc == 1
    assert "未登记超长函数" in out and MOD in out


# 【MA-26】G-0 fail-closed: 解码失败/语法错误不再静默跳过（B-31 缺陷族收编）
def test_nonempty_undecodable_file_is_red(tmp_path, capsys):
    """非空但三种编码均不可解码 → BLOCKING（fail-closed），不得静默跳过"""
    target = tmp_path / "asset_management_backend" / "apps" / MOD
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"\xff\xff\xff")  # utf-8-sig/utf-8/gbk 全部解码失败
    ledger = write(tmp_path / "Rules_Fiels" / "BR4_function_length_ledger.md", BR4_LEDGER_HEADER)
    rc = br4.main(["--root", str(tmp_path), "--ledger", str(ledger)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "非空文件不可解码" in out and MOD in out


def test_zero_byte_file_is_exempt(tmp_path, capsys):
    """零字节文件（合法空文件）豁免跳过，不触发 BLOCKING"""
    target = tmp_path / "asset_management_backend" / "apps" / MOD
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"")
    ledger = write(tmp_path / "Rules_Fiels" / "BR4_function_length_ledger.md", BR4_LEDGER_HEADER)
    rc = br4.main(["--root", str(tmp_path), "--ledger", str(ledger)])
    assert rc == 0


def test_syntaxerror_file_is_red(tmp_path, capsys):
    """语法错误文件 → BLOCKING（fail-closed），不再 WARN 跳过"""
    target = tmp_path / "asset_management_backend" / "apps" / MOD
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("def f(:\n", encoding="utf-8")
    ledger = write(tmp_path / "Rules_Fiels" / "BR4_function_length_ledger.md", BR4_LEDGER_HEADER)
    rc = br4.main(["--root", str(tmp_path), "--ledger", str(ledger)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "SyntaxError" in out and MOD in out


def test_stale_ledger_entry_is_red(tmp_path, capsys):
    source = "def tiny():\n    return 1\n"  # 1 逻辑行，已达标
    ledger = BR4_LEDGER_HEADER + br4_row(MOD, 1, "big", 57)
    rc = _run(tmp_path, ledger, source)
    out = capsys.readouterr().out
    assert rc == 1
    assert "台账含已达标条目" in out and MOD in out


def test_invalid_registered_count_is_red(tmp_path, capsys):
    source = _big_func(57)
    ledger = BR4_LEDGER_HEADER + br4_row(MOD, 1, "big", 50)  # 50 <= 50 非法
    rc = _run(tmp_path, ledger, source)
    out = capsys.readouterr().out
    assert rc == 1
    assert "登记行数 50 <= 50" in out


def test_green_when_ledger_matches(tmp_path, capsys):
    source = _big_func(57)
    ledger = BR4_LEDGER_HEADER + br4_row(MOD, 1, "big", 57)
    rc = _run(tmp_path, ledger, source)
    assert rc == 0
    assert "[PASS]" in capsys.readouterr().out


def test_func_docstring_not_counted_green(tmp_path, capsys):
    # 【MA-26】夹具: 4 空格函数体直接构造(合法 Python),验证 docstring 行不计入逻辑行
    # (31 逻辑行 < 50;旧版护栏对语法非法文件静默跳过曾使其「假绿」,G-0 fail-closed 后必现)
    body = "\n".join(f"    v{i} = {i}" for i in range(30))
    source = f'def documented():\n    """doc"""\n{body}\n'
    rc = _run(tmp_path, BR4_LEDGER_HEADER, source)
    assert rc == 0
    assert "[PASS]" in capsys.readouterr().out


def test_real_repo_default_root_green(capsys):
    rc = br4.main([])
    assert rc == 0
    assert "[PASS]" in capsys.readouterr().out