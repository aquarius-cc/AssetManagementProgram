# -*- coding: utf-8 -*-
"""CI 编排护栏（M-02 / M-24 / M-01 / M-18 / S-1）：断言集防 CI 门禁稀释与静默停摆。

断言一（needs 覆盖率）：workflow 汇总节点的 needs 必须覆盖同 workflow 内全部 job。
  动机：2026-10-31 审计 M-02 实测发现 ci.yml 的 ci-summary 只收 4/15 个 job，
  其中 backend-permission-check / api-doc-guard / api-doc-generate 无下游，
  失败不进汇总 → 出现「有 job 红、汇总绿」的假绿。本护栏把该缺口变成可回归
  断言：新增 job 忘记挂 needs 立即红。
  不套用 needs 全覆盖口径于 security-scan.yml：其「Security 汇总」按 deps-changed
  分流，audit 被有意跳过时 result=skipped 属正常（无条件覆盖会误红）。改为窄断言
  （audit_security_summary，M-18）：needs 必须含 weekly-report + 汇总 step 必须走
  scripts/security_summary.py（外部化纯函数，六态单测面，防内联回潮 S-3）。

断言二（监听名一致性）：ci-cd.yml 的 workflow_run.workflows 列表必须包含
  ci.yml 的 name 值。workflow_run 按 workflow 名匹配，CI 改名后 CD 永不触发
  且无任何报错（静默停摆），fail-closed 方向虽安全但部署会无声中断。

断言三（迁移触发形态，M-01）：migration-check 必须有 push 触发——本仓历史
0 PR、直推 master（required checks 空转），on: pull_request only 永久休眠，
CT-6 迁移红线从未进部署链回查面（M-01 根因）。
断言四（双名单生效性，M-01）：ci-cd 门禁回查 step 必须走 scripts/gate_recheck.py
（双名单唯一真源 RECHECK_NAMES），防内联单名单回查回潮把迁移红线静默移出回查面。
断言五（push 面三点断言，S-1/P-3）：duplicate-guard.yml 删除后护栏自测的
push 面唯一依赖 ci.yml:backend-lint——自测 step 文本、5 个护栏自测文件的
真仓绿锚、BR-4/BR-6 直跑 step 文本三者必须全在场。

解析口径（刻意零第三方依赖）：GitHub Actions 的 job 键固定为 jobs: 段内 2 空格缩进，
故用行缩进定位，不引入 PyYAML（requirements 未声明，可用性不确定）。
needs 的内联（`needs: [a, b]`）与块状（`- a` 列表）两种写法都支持。
on 段的事件键同为 2 空格缩进（_on_events 复用 JOB_KEY）。
"""

import argparse
import re
import sys
from pathlib import Path

JOB_KEY = re.compile(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$")
TOP_KEY = re.compile(r"^([A-Za-z0-9_-]+):\s*(?:#.*)?$")
INLINE_NEEDS = re.compile(r"^    needs:\s*\[(.*)\]\s*(?:#.*)?$")
BLOCK_NEEDS = re.compile(r"^    needs:\s*(?:#.*)?$")
LIST_ITEM = re.compile(r"^      -\s*([A-Za-z0-9_-]+)\s*(?:#.*)?$")
WORKFLOWS_INLINE = re.compile(r"^\s*workflows:\s*\[(.*)\]\s*(?:#.*)?$")

# 每个 workflow 的「汇总节点」唯一真源，新增汇总节点在此登记
TARGETS = (
    (Path(".github") / "workflows" / "ci.yml", "ci-summary"),
    # 【BF-183 3a，方案 C】duplicate-guard.yml 已删：其三 job（G/FR 护栏直跑 +
    # guard-summary）与 ci.yml:backend-lint 的护栏自测步（pytest ../scripts/tests）
    # 覆盖同一面，双链并存制造「两条链一条覆盖」的假安心。删重复 workflow 后
    # push 面覆盖由断言五（P-3）锁住，防静默消失。
)
CI_PATH = Path(".github") / "workflows" / "ci.yml"
CD_PATH = Path(".github") / "workflows" / "ci-cd.yml"
SECURITY_SCAN_PATH = Path(".github") / "workflows" / "security-scan.yml"
SECURITY_SUMMARY_MARKER = "python scripts/security_summary.py"
MIGRATION_CHECK_PATH = Path(".github") / "workflows" / "migration-check.yml"
GATE_RECHECK_MARKER = "python3 scripts/gate_recheck.py"
# 断言五（P-3/S-1）：护栏自测 push 面三点断言
GUARD_SELFTEST_MARKER = "pytest ../scripts/tests -q"
BR4_RUN_MARKER = "python ../scripts/check_function_length_guard.py"
BR6_RUN_MARKER = "python ../scripts/check_file_length_guard.py"
REAL_REPO_ANCHOR = "def test_real_repo_default_root_green"
# 【M-34/M-11，2026-11-10】新增第 5 项：密钥指纹护栏自测（真仓绿锚覆盖 53 处
# 夹具分流 + 已轮换凭据指纹零回流）
GUARD_REAL_REPO_ANCHORS = (
    "scripts/tests/test_duplicate_invariants.py",
    "scripts/tests/test_frontend_invariants.py",
    "scripts/tests/test_file_length_guard.py",
    "scripts/tests/test_function_length_guard.py",
    "scripts/tests/test_check_secret_fingerprints.py",
)
# 断言六（BF-183 首跑 42432138344 修复）：变更面 GITHUB_ENV 写入必须走 heredoc
# 形式（多行兼容、空值必定义变量），③/④ 读取必须走 set -u 安全形式
MIG_ENV_HEREDOC_MARKER = "MIGRATION_FILES<<MIG_DELIM"
MIG_SETU_SAFE_MARKER = "${MIGRATION_FILES-}"


def _jobs_section(lines):
    """截取 jobs: 段；段内才存在 2 空格缩进的 job 键。"""
    start = None
    for index, line in enumerate(lines):
        match = TOP_KEY.match(line)
        if match and match.group(1) == "jobs":
            start = index + 1
            break
    if start is None:
        return []
    section = []
    for line in lines[start:]:
        match = TOP_KEY.match(line)
        if match and match.group(1) != "jobs":
            break
        section.append(line)
    return section


def _job_blocks(section):
    blocks = {}
    current = None
    for line in section:
        match = JOB_KEY.match(line)
        if match:
            current = match.group(1)
            blocks[current] = []
        elif current:
            blocks[current].append(line)
    return blocks


def _needs_of(block_lines):
    for index, line in enumerate(block_lines):
        inline = INLINE_NEEDS.match(line)
        if inline:
            return [item.strip() for item in inline.group(1).split(",") if item.strip()]
        if BLOCK_NEEDS.match(line):
            needs = []
            for follow in block_lines[index + 1 :]:
                item = LIST_ITEM.match(follow)
                if not item:
                    break
                needs.append(item.group(1))
            return needs
    return []


def audit(workflow_path, summary_job):
    """断言一：返回违规清单（空 list = 通过）。"""
    workflow_path = Path(workflow_path)
    blocks = _job_blocks(_jobs_section(workflow_path.read_text(encoding="utf-8").splitlines()))
    if summary_job not in blocks:
        return ["%s: 未找到汇总 job `%s`" % (workflow_path.name, summary_job)]
    needs = set(_needs_of(blocks[summary_job]))
    missing = sorted(set(blocks) - {summary_job} - needs)
    return [
        "%s: `%s` 的 needs 未覆盖 job `%s`" % (workflow_path.name, summary_job, job)
        for job in missing
    ]


def _workflow_name(ci_path):
    # 行首 name: 即顶层（job 内 name: 有 4 空格缩进，不会误命中）
    for line in Path(ci_path).read_text(encoding="utf-8").splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return None


def _listened_workflows(cd_path):
    for line in Path(cd_path).read_text(encoding="utf-8").splitlines():
        match = WORKFLOWS_INLINE.match(line)
        if match:
            return [
                item.strip().strip("\"'") for item in match.group(1).split(",") if item.strip()
            ]
    return []


def audit_listener(ci_path, cd_path):
    """断言二：CD 监听名必须包含 CI 的 name 值（防改名后 CD 静默停摆）。"""
    ci_name = _workflow_name(ci_path)
    if not ci_name:
        return ["ci.yml: 未找到顶层 name"]
    listened = _listened_workflows(cd_path)
    if not listened:
        return ["ci-cd.yml: 未找到 workflow_run.workflows 列表"]
    if ci_name not in listened:
        return [
            "ci-cd.yml: workflows %s 未包含 ci.yml 的 name `%s`（CD 将永不触发）"
            % (listened, ci_name)
        ]
    return []


def audit_security_summary(workflow_path):
    """窄断言（M-18/S-3）：① security-summary 的 needs 必须含 weekly-report
    （M-18 漏项面：schedule 周周报失败被漏判）② 汇总 step 必须走外部脚本
    （防内联回潮，S-3）。不套 needs 全覆盖口径（weekly-report 按 event 分流，
    skipped 属正常，见模块 docstring）。"""
    problems = []
    text = Path(workflow_path).read_text(encoding="utf-8")
    blocks = _job_blocks(_jobs_section(text.splitlines()))
    if "security-summary" not in blocks:
        return ["security-scan.yml: 未找到 security-summary job"]
    needs = set(_needs_of(blocks["security-summary"]))
    if "weekly-report" not in needs:
        problems.append(
            "security-scan.yml: security-summary 的 needs 未含 weekly-report"
            "（schedule 周兜底失败将被漏判，M-18）"
        )
    if SECURITY_SUMMARY_MARKER not in "\n".join(blocks["security-summary"]):
        problems.append(
            f"security-scan.yml: 汇总 step 未调用 `{SECURITY_SUMMARY_MARKER}`（防内联回潮，S-3）"
        )
    return problems


def _on_events(workflow_path):
    """on 段解析器：返回顶层事件名列表（如 ["push", "workflow_run"]）。

    GitHub Actions 的 on: 是顶层键，其事件键固定 2 空格缩进（与 JOB_KEY 同形，
    复用之）；事件下的 branches/paths/workflows 等子键 4+ 空格缩进，不会误命中。
    """
    events = []
    in_on = False
    for line in Path(workflow_path).read_text(encoding="utf-8").splitlines():
        top = TOP_KEY.match(line)
        if top:
            in_on = top.group(1) == "on"
            continue
        if in_on:
            event = JOB_KEY.match(line)
            if event:
                events.append(event.group(1))
    return events


def audit_migration_trigger(workflow_path):
    """断言三（M-01）：migration-check 必须有 push 触发（直推模式防休眠）。"""
    events = _on_events(workflow_path)
    if "push" not in events:
        return [
            f"migration-check.yml: on 段缺 push 触发（当前 {events}）——直推模式下迁移检查永久休眠，CT-6 红线不进部署链（M-01）"
        ]
    return []


def audit_migration_env_safety(workflow_path):
    """断言六（BF-183 首跑 42432138344）：变更面 GITHUB_ENV 写入与 ③/④ 读取的 fail-safe 形态。

    首跑直证两种失效：空变更面时 `printf '%s' ""` 向 GITHUB_ENV 写零字节、变量未
    定义 → ③ `set -u` unbound 判红；≥2 文件时裸多行写入使 GITHUB_ENV 解析错位、
    文件静默丢失（fail-open）。修复口径：写入走 heredoc 形式，读取走
    `${MIGRATION_FILES-}` 形式。
    """
    text = Path(workflow_path).read_text(encoding="utf-8")
    problems = []
    if MIG_ENV_HEREDOC_MARKER not in text:
        problems.append(
            "migration-check.yml: 变更面 GITHUB_ENV 写入非 heredoc 形式（MIGRATION_FILES<<MIG_DELIM）——空面变量未定义（set -u unbound）、多文件面解析错位静默丢文件（42432138344 首跑红直证）"
        )
    if MIG_SETU_SAFE_MARKER not in text:
        problems.append(
            "migration-check.yml: ③/④ MIGRATION_FILES 读取非 ${MIGRATION_FILES-} set -u 安全形式（unbound 变量风险）"
        )
    return problems


def audit_gate_recheck(cd_path):
    """断言四（M-01）：门禁回查 step 必须走 gate_recheck.py（双名单唯一真源）。"""
    if GATE_RECHECK_MARKER not in Path(cd_path).read_text(encoding="utf-8"):
        return [
            f"ci-cd.yml: 门禁回查 step 未走 `{GATE_RECHECK_MARKER}`（双名单唯一真源失效，迁移红线将被静默移出回查面，M-01）"
        ]
    return []


def audit_guard_push_surface(root):
    """断言五（P-3/S-1）：护栏自测 push 面三点断言（ci.yml 必在场）。

    duplicate-guard.yml 删除后，G/FR/BR-4/BR-6 护栏在 push 面唯一被
    ci.yml:backend-lint 执行。任一点消失 = 对应护栏静默退出 push 面。
    """
    problems = []
    ci_text = (root / CI_PATH).read_text(encoding="utf-8")
    if GUARD_SELFTEST_MARKER not in ci_text:
        problems.append(
            f"ci.yml: 护栏自测 step 缺失（{GUARD_SELFTEST_MARKER}）——G/FR 护栏 push 面消失（S-1）"
        )
    for marker, label in ((BR4_RUN_MARKER, "BR-4"), (BR6_RUN_MARKER, "BR-6")):
        if marker not in ci_text:
            problems.append(f"ci.yml: {label} 直跑 step 缺失（{marker}）——长度护栏 push 面消失（S-1）")
    for relative in GUARD_REAL_REPO_ANCHORS:
        path = root / relative
        if not path.exists():
            problems.append(f"{relative}: 文件缺失——护栏自测真仓绿锚消失（S-1）")
        elif REAL_REPO_ANCHOR not in path.read_text(encoding="utf-8"):
            problems.append(f"{relative}: 缺 {REAL_REPO_ANCHOR}——护栏自测真仓绿锚消失（S-1）")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="CI 编排护栏（needs 覆盖率 + CD 监听名 + security-summary 窄断言 + 迁移触发形态 + 双名单生效性 + push 面三点 + 变更面 env 安全）"
    )
    parser.add_argument("--root", default=None, help="仓库根目录（默认按 __file__ 推导）")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent

    problems = []
    for relative, summary_job in TARGETS:
        path = root / relative
        if not path.exists():
            problems.append("%s: 文件不存在" % relative.as_posix())
            continue
        problems.extend(audit(path, summary_job))
    ci_path, cd_path = root / CI_PATH, root / CD_PATH
    if ci_path.exists() and cd_path.exists():
        problems.extend(audit_listener(ci_path, cd_path))
    else:
        for relative in (CI_PATH, CD_PATH):
            if not (root / relative).exists():
                problems.append("%s: 文件不存在" % relative.as_posix())

    sec_path = root / SECURITY_SCAN_PATH
    if sec_path.exists():
        problems.extend(audit_security_summary(sec_path))
    else:
        problems.append(f"{SECURITY_SCAN_PATH.as_posix()}: 文件不存在")

    mig_path = root / MIGRATION_CHECK_PATH
    if mig_path.exists():
        problems.extend(audit_migration_trigger(mig_path))
        problems.extend(audit_migration_env_safety(mig_path))
    else:
        problems.append(f"{MIGRATION_CHECK_PATH.as_posix()}: 文件不存在")

    if ci_path.exists():
        if cd_path.exists():
            problems.extend(audit_gate_recheck(cd_path))
        problems.extend(audit_guard_push_surface(root))

    if problems:
        print("[FAIL] CI 编排护栏未通过：")
        for item in problems:
            print("   - " + item)
        print("→ needs 缺口：新增 job 必须同步加入汇总节点（M-02/M-24）；")
        print("→ 监听名缺口：ci.yml 改名必须同步 ci-cd.yml 的 workflows 列表。")
        print("→ security-summary 窄断言：needs 须含 weekly-report，汇总 step 须走外部脚本（M-18/S-3）。")
        print("→ 迁移触发形态：migration-check on 段必须含 push（M-01 防休眠）。")
        print("→ 双名单生效性：门禁回查 step 必须走 scripts/gate_recheck.py（M-01）。")
        print("→ push 面三点：ci.yml 自测 step + 5 真仓绿锚 + BR-4/BR-6 直跑文本（S-1/P-3）。")
        print("→ 变更面 env 安全：GITHUB_ENV heredoc 写入 + ③/④ set -u 安全读取（42432138344 首跑红直证）。")
        return 1
    print("[PASS] CI 编排护栏全绿：needs 覆盖 / CD 监听名 / security-summary 窄断言 / 迁移触发形态 / 双名单生效性 / push 面三点 / 变更面 env 安全")
    return 0


if __name__ == "__main__":
    sys.exit(main())
