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


def test_real_repo_workflows_green(capsys):
    assert guard.main([]) == 0
    assert "[PASS]" in capsys.readouterr().out
