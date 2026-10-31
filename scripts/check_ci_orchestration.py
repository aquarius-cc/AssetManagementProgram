# -*- coding: utf-8 -*-
"""CI 编排护栏（M-02 / M-24）：两条断言防 CI 门禁稀释与静默停摆。

断言一（needs 覆盖率）：workflow 汇总节点的 needs 必须覆盖同 workflow 内全部 job。
  动机：2026-10-31 审计 M-02 实测发现 ci.yml 的 ci-summary 只收 4/15 个 job，
  其中 backend-permission-check / api-doc-guard / api-doc-generate 无下游，
  失败不进汇总 → 出现「有 job 红、汇总绿」的假绿。本护栏把该缺口变成可回归
  断言：新增 job 忘记挂 needs 立即红。
  刻意不覆盖 security-scan.yml：其「Security 汇总」按 deps-changed 分流，
  audit 被有意跳过时 result=skipped 属正常，需条件判断而非「!= success 即失败」，
  与本护栏的无条件覆盖口径不同（该分流逻辑由其 workflow 内联实现，另行审查）。

断言二（监听名一致性）：ci-cd.yml 的 workflow_run.workflows 列表必须包含
  ci.yml 的 name 值。workflow_run 按 workflow 名匹配，CI 改名后 CD 永不触发
  且无任何报错（静默停摆），fail-closed 方向虽安全但部署会无声中断。

解析口径（刻意零第三方依赖）：GitHub Actions 的 job 键固定为 jobs: 段内 2 空格缩进，
故用行缩进定位，不引入 PyYAML（requirements 未声明，可用性不确定）。
needs 的内联（`needs: [a, b]`）与块状（`- a` 列表）两种写法都支持。
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
    (Path(".github") / "workflows" / "duplicate-guard.yml", "guard-summary"),
)
CI_PATH = Path(".github") / "workflows" / "ci.yml"
CD_PATH = Path(".github") / "workflows" / "ci-cd.yml"


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


def main(argv=None):
    parser = argparse.ArgumentParser(description="CI 编排护栏（needs 覆盖率 + CD 监听名）")
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

    if problems:
        print("[FAIL] CI 编排护栏未通过：")
        for item in problems:
            print("   - " + item)
        print("→ needs 缺口：新增 job 必须同步加入汇总节点（M-02/M-24）；")
        print("→ 监听名缺口：ci.yml 改名必须同步 ci-cd.yml 的 workflows 列表。")
        return 1
    print("[PASS] CI 汇总 needs 已覆盖全部 job，CD 监听名一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
