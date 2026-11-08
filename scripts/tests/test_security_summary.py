"""security_summary 六态注入（M-18 / BF-183 批次 1，CT-4）。

六态 = 需审计两分支（schedule / workflow_dispatch）× weekly-report 豁免逻辑
+ 不需审计分支（push 无依赖变更）+ secret-scan 无条件判项。
分支语义依据：security-scan.yml weekly-report 的 if 锁 schedule
（非 schedule 恒 skipped，豁免分支不得判红）。
"""

import security_summary as ss


def _needs(results: dict) -> dict:
    return {job: {"result": r} for job, r in results.items()}


def test_schedule_all_success_passes():
    """态 1：schedule 全量 + 周报 success → 放行。"""
    needs = _needs({"changes": "success", "python-audit": "success", "node-audit": "success",
                    "secret-scan": "success", "weekly-report": "success"})
    ok, _ = ss.evaluate(needs, "schedule", "")
    assert ok


def test_schedule_weekly_report_failure_rejects():
    """态 2：schedule + 周报 failure → 拒绝（M-18：原 needs 缺项正是漏判此态）。"""
    needs = _needs({"changes": "success", "python-audit": "success", "node-audit": "success",
                    "secret-scan": "success", "weekly-report": "failure"})
    ok, reason = ss.evaluate(needs, "schedule", "")
    assert not ok and "weekly-report" in reason


def test_schedule_python_audit_failure_rejects():
    """态 3：schedule + python-audit failure → 拒绝。"""
    needs = _needs({"changes": "success", "python-audit": "failure", "node-audit": "success",
                    "secret-scan": "success", "weekly-report": "success"})
    ok, reason = ss.evaluate(needs, "schedule", "")
    assert not ok and "python-audit" in reason


def test_workflow_dispatch_weekly_skipped_passes():
    """态 4（豁免分支）：dispatch 需审计但周报恒 skipped（if 锁 schedule）→ 不得判红。"""
    needs = _needs({"changes": "success", "python-audit": "success", "node-audit": "success",
                    "secret-scan": "success", "weekly-report": "skipped"})
    ok, _ = ss.evaluate(needs, "workflow_dispatch", "")
    assert ok


def test_push_no_dep_change_skipped_audit_passes():
    """态 5（不需审计分支）：push 无依赖变更，audit 有意 skipped 属正常。"""
    needs = _needs({"changes": "success", "python-audit": "skipped", "node-audit": "skipped",
                    "secret-scan": "success", "weekly-report": "skipped"})
    ok, _ = ss.evaluate(needs, "push", "")
    assert ok


def test_push_secret_scan_failure_rejects():
    """态 6：secret-scan 必查项，任何场景红。"""
    needs = _needs({"changes": "success", "python-audit": "skipped", "node-audit": "skipped",
                    "secret-scan": "failure", "weekly-report": "skipped"})
    ok, reason = ss.evaluate(needs, "push", "")
    assert not ok and "secret-scan" in reason
