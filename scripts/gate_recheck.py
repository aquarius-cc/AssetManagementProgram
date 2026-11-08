"""gate_recheck：部署门禁双名单回查（M-01 / BF-183 批次 1，3a+3c）。

CD 门禁（ci-cd.yml security-gate）原为单名单：只回查 "Dependency Security Scan"，
"Migration Safety Check" 在直推模式下休眠（on: pull_request only，本仓 0 PR 历史）→
CT-6 迁移红线从未进部署链回查面（M-01 根因）。v3.1：双名单回查，缺失/终态红/
超时未完成 → fail-closed 拒部署。

evaluate(runs) 为纯函数（单测面 test_gate_recheck.py）；main() 走 gh api
（head_sha + event=push）按名单取最新 run，gh 失败/超时/未完成超时 → exit 1。
env 口径与原内联 shell 一致（REPO/SHA/WAIT_SECONDS/POLL_SECONDS；AR-4：等待
上限与轮询间隔由 repo variables 配置管理，不硬编码在逻辑里）。
"""

import json
import os
import subprocess
import sys
import time

# 双名单唯一真源：门禁按这两个 workflow 名回查同 SHA 最新 run 结论。
# 新增回查对象必须登记于此（生效性断言见 check_ci_orchestration.audit_gate_recheck）。
RECHECK_NAMES = ("Dependency Security Scan", "Migration Safety Check")
# CI Pipeline 的结论由 workflow_run 事件直接给出（门禁第 ① 步已校验），此处不回查。
EXCLUDED = ("CI Pipeline",)


def evaluate(runs):
    """返回 (state, details)：state ∈ {"pass", "wait", "fail"}（三态而非布尔）。

    runs: {name: {"status", "conclusion", "html_url"} | None}——None = 该名单无 run。
    - "fail"：任一名单 conclusion 终态非 success → 立即拒部署（不再轮询）；
    - "wait"：任一名单无 run 或仍 in progress → 由调用方轮询至 deadline；
    - "pass"：全部名单 conclusion=success。
    缺失 = wait（同 push 的 migration-check run 可能晚于 CI 入队/运行中）；
    deadline 到期仍缺失 → main() 按 fail-closed 拒绝——「缺失」永不得解释为
    「不需要」（静默休眠正是 M-01 的洞）。EXCLUDED 名单不参与判定。
    """
    reasons = []
    waiters = []
    for name in RECHECK_NAMES:
        run = runs.get(name)
        if run is None:
            waiters.append(f"{name}: 无 run（等待中）")
            continue
        conclusion = str(run.get("conclusion") or "")
        status = str(run.get("status") or "")
        if conclusion == "success":
            continue
        if conclusion:
            reasons.append(f"{name}: conclusion={conclusion}（{run.get('html_url') or ''}）")
        else:
            waiters.append(f"{name}: 未完成（status={status}）（{run.get('html_url') or ''}）")
    if reasons:
        return "fail", reasons
    if waiters:
        return "wait", waiters
    return "pass", []


def _query_latest_runs(repo, sha):
    """gh api：同 SHA 的 push runs 按名单取最新 → {name: run}。

    gh 失败/超时/解析失败 → RuntimeError（调用方 fail-closed）。
    """
    raw = subprocess.run(
        ["gh", "api", f"repos/{repo}/actions/runs?head_sha={sha}&event=push&per_page=100"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,  # 返回码由下方显式判定（fail-closed 走 RuntimeError），非默认 raise
    )
    if raw.returncode != 0:
        raise RuntimeError(f"gh api exit {raw.returncode}: {(raw.stderr or raw.stdout).strip()[:200]}")
    payload = json.loads(raw.stdout)
    latest = {}
    for run in payload.get("workflow_runs", []):
        name = run.get("name")
        if name in EXCLUDED or name not in RECHECK_NAMES:
            continue
        current = latest.get(name)
        if current is None or (run.get("created_at") or "") >= (current.get("created_at") or ""):
            latest[name] = {
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "html_url": run.get("html_url"),
                "created_at": run.get("created_at"),
            }
    return latest


def main() -> int:
    repo = os.environ.get("REPO", "")
    sha = os.environ.get("SHA", "")
    if not repo or not sha:
        print("❌ REPO/SHA 未设置（fail-closed）")
        return 1
    try:
        wait_seconds = int(os.environ.get("WAIT_SECONDS", "600"))
        poll_seconds = int(os.environ.get("POLL_SECONDS", "20"))
    except ValueError:
        print("❌ WAIT_SECONDS/POLL_SECONDS 非数值（fail-closed）")
        return 1
    deadline = time.time() + wait_seconds
    while True:
        try:
            runs = _query_latest_runs(repo, sha)
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            print(f"❌ 查询回查 run 失败（API 异常：{exc}），按 fail-closed 拒绝部署")
            return 1
        state, details = evaluate(runs)
        for line in details:
            print("回查: " + line)
        if state == "pass":
            print("✅ 回查名单全部通过，允许部署")
            return 0
        if state == "fail":
            print("❌ 回查名单未通过，拒绝部署")
            return 1
        if time.time() >= deadline:
            print(f"❌ 等待 {wait_seconds}s 后回查仍未完成，按 fail-closed 拒绝部署")
            return 1
        time.sleep(poll_seconds)


if __name__ == "__main__":
    sys.exit(main())
