# -*- coding: utf-8 -*-
"""CI 编排护栏自测（M-02/M-24）：先证红，再证绿。

断言面：
  1. job 未挂 needs → 红（本护栏存在的理由）
  2. 内联 needs 全覆盖 → 绿
  3. 块状 needs 全覆盖 → 绿
  4. 汇总 job 缺失 → 红（防止汇总节点被误删后护栏静默放行）
  5. CD 监听名不一致 → 红（防 CI 改名后 CD 静默停摆）
  6. CD 监听名一致 → 绿
  7. 真实仓库两个 workflow + 监听链 → 绿
"""

from pathlib import Path

import check_ci_orchestration as guard
from helpers import write

BLOCK_FORM = """name: T

on:
  push:
    branches: [master]

jobs:
  alpha:
    runs-on: ubuntu-latest

  beta:
    runs-on: ubuntu-latest

  summary:
    runs-on: ubuntu-latest
    needs:
      - alpha
      - beta
"""

INLINE_FORM = """name: T

on:
  push:

jobs:
  alpha:
    runs-on: ubuntu-latest

  summary:
    needs: [alpha]
"""

MISSING_FORM = """name: T

on:
  push:

jobs:
  alpha:
    runs-on: ubuntu-latest

  beta:
    runs-on: ubuntu-latest

  summary:
    needs:
      - alpha
"""

CI_NAME = """name: CI Pipeline

on:
  push:

jobs:
  alpha:
    runs-on: ubuntu-latest
"""

CD_MATCH = """name: CD Pipeline

on:
  workflow_run:
    workflows: ["CI Pipeline"]
    types: [completed]

jobs:
  gate:
    runs-on: ubuntu-latest
"""

CD_MISMATCH = CD_MATCH.replace('"CI Pipeline"', '"Renamed Pipeline"')


def _workflow(tmp_path, text):
    return write(tmp_path / ".github" / "workflows" / "ci.yml", text)


def test_unlisted_job_is_red(tmp_path):
    problems = guard.audit(_workflow(tmp_path, MISSING_FORM), "summary")
    assert len(problems) == 1
    assert "beta" in problems[0]


def test_inline_needs_green(tmp_path):
    assert guard.audit(_workflow(tmp_path, INLINE_FORM), "summary") == []


def test_block_needs_green(tmp_path):
    assert guard.audit(_workflow(tmp_path, BLOCK_FORM), "summary") == []


def test_missing_summary_job_is_red(tmp_path):
    problems = guard.audit(_workflow(tmp_path, INLINE_FORM), "absent-summary")
    assert len(problems) == 1
    assert "未找到汇总 job" in problems[0]


def test_listener_mismatch_is_red(tmp_path):
    ci = write(tmp_path / "ci.yml", CI_NAME)
    cd = write(tmp_path / "ci-cd.yml", CD_MISMATCH)
    problems = guard.audit_listener(ci, cd)
    assert len(problems) == 1
    assert "Renamed Pipeline" in problems[0] and "CI Pipeline" in problems[0]


def test_listener_match_green(tmp_path):
    ci = write(tmp_path / "ci.yml", CI_NAME)
    cd = write(tmp_path / "ci-cd.yml", CD_MATCH)
    assert guard.audit_listener(ci, cd) == []


SECURITY_SCAN_FORM = """name: Dependency Security Scan

on:
  push:

jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      deps-changed: "true"
  python-audit:
    runs-on: ubuntu-latest
  node-audit:
    runs-on: ubuntu-latest
  secret-scan:
    runs-on: ubuntu-latest
  weekly-report:
    runs-on: ubuntu-latest
    needs: [python-audit, node-audit]
    if: always() && github.event_name == 'schedule'
  security-summary:
    runs-on: ubuntu-latest
    needs: [changes, python-audit, node-audit, secret-scan]
    if: always()
    steps:
      - name: 汇总
        run: echo inline-shell
"""


def test_security_summary_missing_weekly_needs_red(tmp_path):
    """证红（M-18）：needs 缺 weekly-report → 窄断言红。"""
    p = write(tmp_path / ".github" / "workflows" / "security-scan.yml", SECURITY_SCAN_FORM)
    problems = guard.audit_security_summary(p)
    assert any("weekly-report" in item for item in problems)


def test_security_summary_inline_step_red(tmp_path):
    """证红（S-3）：汇总 step 内联（未走外部脚本）→ 窄断言红。"""
    text = SECURITY_SCAN_FORM.replace(
        "needs: [changes, python-audit, node-audit, secret-scan]",
        "needs: [changes, python-audit, node-audit, secret-scan, weekly-report]",
    )
    p = write(tmp_path / ".github" / "workflows" / "security-scan.yml", text)
    problems = guard.audit_security_summary(p)
    assert any("security_summary.py" in item for item in problems)


def test_real_repo_security_summary_green():
    """真仓正样本：现行 security-scan.yml 通过窄断言。"""
    root = Path(guard.__file__).resolve().parent.parent
    assert guard.audit_security_summary(root / ".github" / "workflows" / "security-scan.yml") == []


MIG_YAML_NO_PUSH = """name: Migration Safety Check

on:
  pull_request:
    branches: [master]
    paths:
      - "**/migrations/**"

jobs:
  migration-safety:
    runs-on: ubuntu-latest
"""

MIG_YAML_WITH_PUSH = MIG_YAML_NO_PUSH.replace(
    "on:\n  pull_request:", "on:\n  push:\n    branches: [master]\n  pull_request:"
)


def test_on_parser_extracts_events(tmp_path):
    """on 段解析器：只认 2 空格缩进的事件键，branches/paths 子键不误命中。"""
    p = write(tmp_path / ".github" / "workflows" / "migration-check.yml", MIG_YAML_NO_PUSH)
    assert guard._on_events(p) == ["pull_request"]


def test_migration_trigger_missing_push_red(tmp_path):
    """证红（M-01）：on 段缺 push（本仓直推模式下的休眠形态）→ 断言三红。"""
    p = write(tmp_path / ".github" / "workflows" / "migration-check.yml", MIG_YAML_NO_PUSH)
    assert any("push" in item for item in guard.audit_migration_trigger(p))


def test_migration_trigger_push_green(tmp_path):
    p = write(tmp_path / ".github" / "workflows" / "migration-check.yml", MIG_YAML_WITH_PUSH)
    assert guard.audit_migration_trigger(p) == []


def test_gate_recheck_inline_fallback_red(tmp_path):
    """证红（M-01）：门禁回查 step 未走 gate_recheck.py（内联单名单回潮）→ 断言四红。"""
    p = write(tmp_path / ".github" / "workflows" / "ci-cd.yml",
              "name: CD Pipeline\non:\n  workflow_run:\n    workflows: [\"CI Pipeline\"]\n"
              "jobs:\n  security-gate:\n    steps:\n      - run: echo inline-single-name\n")
    assert any("gate_recheck" in item for item in guard.audit_gate_recheck(p))


def test_guard_push_surface_real_repo_green():
    """真仓正样本：ci.yml 自测 step + 4 真仓绿锚 + BR-4/BR-6 直跑文本全在场。"""
    root = Path(guard.__file__).resolve().parent.parent
    assert guard.audit_guard_push_surface(root) == []


def test_guard_push_surface_missing_selftest_red(tmp_path):
    """证红（S-1）：ci.yml 缺护栏自测 step → G/FR push 面消失红。"""
    write(tmp_path / ".github" / "workflows" / "ci.yml",
          "name: CI Pipeline\njobs:\n  backend-lint:\n    steps:\n"
          "      - run: python ../scripts/check_function_length_guard.py\n"
          "      - run: python ../scripts/check_file_length_guard.py\n")
    problems = guard.audit_guard_push_surface(tmp_path)
    assert any("pytest ../scripts/tests -q" in item for item in problems)


def test_real_repo_workflows_green(capsys):
    assert guard.main([]) == 0
    assert "[PASS]" in capsys.readouterr().out
