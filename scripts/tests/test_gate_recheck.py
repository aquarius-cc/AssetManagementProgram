"""gate_recheck.evaluate 双名单三态注入（M-01 / BF-183 批次 1，3a，CT-4）。

三态 = pass / wait（无 run 或运行中）/ fail（终态非 success）。
分支语义依据：缺失 = wait（deadline 到期由 main() fail-closed 拒绝，
「缺失」永不得解释为「不需要」——静默休眠正是 M-01 的洞）。
"""

import gate_recheck as gr


def _run(conclusion, status=None, url=""):
    return {"conclusion": conclusion, "status": status or "completed", "html_url": url}


def test_all_success_passes():
    runs = {"Dependency Security Scan": _run("success"), "Migration Safety Check": _run("success")}
    state, details = gr.evaluate(runs)
    assert state == "pass" and details == []


def test_missing_migration_run_waits():
    """M-01 洞面：migration-check 无 run = wait（deadline 后判红，永不解释为「不需要」）。"""
    runs = {"Dependency Security Scan": _run("success")}
    state, details = gr.evaluate(runs)
    assert state == "wait" and any("Migration Safety Check" in d for d in details)


def test_scan_failure_fails():
    runs = {"Dependency Security Scan": _run("failure"), "Migration Safety Check": _run("success")}
    state, details = gr.evaluate(runs)
    assert state == "fail" and any("Dependency Security Scan" in d for d in details)


def test_migration_cancelled_fails():
    runs = {"Dependency Security Scan": _run("success"), "Migration Safety Check": _run("cancelled")}
    state, details = gr.evaluate(runs)
    assert state == "fail" and any("Migration Safety Check" in d for d in details)


def test_in_progress_waits():
    runs = {"Dependency Security Scan": _run(None, status="in_progress"), "Migration Safety Check": _run("success")}
    state, details = gr.evaluate(runs)
    assert state == "wait" and any("Dependency Security Scan" in d for d in details)


def test_terminal_red_wins_over_wait():
    """终态红优先：一 failure + 一 in progress → fail（不等运行中者）。"""
    runs = {"Dependency Security Scan": _run("failure"), "Migration Safety Check": _run(None, status="in_progress")}
    state, _ = gr.evaluate(runs)
    assert state == "fail"


def test_excluded_ci_pipeline_ignored():
    """EXCLUDED（CI Pipeline）不参与判定：runs 里在场且红也被忽略（门禁第 ① 步已校验）。"""
    runs = {
        "Dependency Security Scan": _run("success"),
        "Migration Safety Check": _run("success"),
        "CI Pipeline": _run("failure"),
    }
    state, _ = gr.evaluate(runs)
    assert state == "pass"
