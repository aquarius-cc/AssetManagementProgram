"""P-2 根仓 scripts/ 轻量长度断言（BF-183 批次 1；scripts/ 全量护栏另立 M 项）。

根仓 scripts/ 无 CI 静态护栏覆盖：CI 全部 ruff 步 working-directory 在后端子仓，
BR-4/BR-6 扫描域均在 backend/——gate_recheck.py / security_summary.py 等新脚本
将处于「规模零护栏」。本批以轻量断言兜底：
  1. 顶层 scripts/*.py 逐文件逻辑行 ≤500（计数走 line_metrics 单源，LT-1）；
  2. 解码/解析失败 → 显式红（护栏向失败——不得复制 BR-6 的 WARN+skip 形态
     check_file_length_guard.py:86-88，那正是 B-31 缺陷族本批要关闭的反模式）。
"""

from pathlib import Path

import line_metrics
from helpers import assign_module_lines, write

MAX_LOGICAL_LINES = 500


def _scan(scripts_dir: Path):
    """返回 (violations, errors)：violations=[(文件名, 逻辑行数)]，errors=[(文件名, 原因)]。"""
    violations = []
    errors = []
    for path in sorted(scripts_dir.glob("*.py")):
        if path.stat().st_size == 0:
            continue  # 合法空文件
        source = line_metrics.read_text(path)
        if not source:
            errors.append((path.name, "G-0 解码失败（非空文件不可解码，fail-closed：不跳过）"))
            continue
        try:
            tree = line_metrics.parse_module(source)
        except SyntaxError as exc:
            errors.append((path.name, f"解析失败 SyntaxError:{exc.lineno} {exc.msg}"))
            continue
        count = line_metrics.logical_line_count(source, tree)
        if count > MAX_LOGICAL_LINES:
            violations.append((path.name, count))
    return violations, errors


def test_real_repo_scripts_within_limit():
    """真仓回归：顶层 scripts/*.py 全部 ≤500 逻辑行，解码/解析失败显式红。"""
    scripts_dir = Path(__file__).resolve().parent.parent
    violations, errors = _scan(scripts_dir)
    assert errors == [], f"scripts/ 解码/解析失败（fail-closed）: {errors}"
    assert violations == [], f"scripts/ 超限文件（逻辑行 >{MAX_LOGICAL_LINES}）: {violations}"


def test_over_limit_fixture_is_red(tmp_path):
    """证红：501 逻辑行的顶层脚本必须被标记。"""
    write(tmp_path / "big.py", assign_module_lines(501))
    violations, errors = _scan(tmp_path)
    assert errors == []
    assert ("big.py", 501) in violations


def test_syntax_error_fixture_is_red(tmp_path):
    """证红：解析失败脚本显式红（不得复制 BR-6 的 skip 形态）。"""
    write(tmp_path / "broken.py", "def f(:\n    pass\n")
    violations, errors = _scan(tmp_path)
    assert violations == []
    assert len(errors) == 1 and errors[0][0] == "broken.py"
