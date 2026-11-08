"""security-summary 纯函数判定（M-18 / BF-183 批次 1）。

原 security-scan.yml 汇总 step 为内联 shell 判定（deps-changed 分流 + schedule 兜底），
无测试面；外部化为纯函数 evaluate() 后获得六态注入单测面（CT-4，
test_security_summary.py）。刻意偏离 ci.yml ci-summary 的内联 python3 heredoc 口径，
理由 = 可单测性，并已写入 workflow 注释，防日后以「一致性」为由内联回去（S-3）。

判定序（与旧 shell 语义逐条对齐，零行为变更 + M-18 新增判项）：
  1. secret-scan 任何情况下必须 success（新增密钥与依赖变更无关）；
  2. 需审计 = deps_changed == "true" 或 event in ("schedule", "workflow_dispatch")
     → 要求 python-audit / node-audit 均 success；
  3. event == "schedule" → 加判 weekly-report success（M-18：原 needs 缺项
     致其失败被漏判）。
  非 schedule 下 weekly-report 恒 skipped（其 if 锁 schedule），不判——
  禁止简化为无条件判红。
"""

import json
import os
import sys

JOB_IDS = ("changes", "python-audit", "node-audit", "secret-scan", "weekly-report")


def evaluate(needs: dict, event: str, deps_changed: str) -> tuple:
    """返回 (放行?, 理由)。needs = {job_id: {"result": ...}}（GitHub toJSON(needs) 原形）。"""

    def result(job_id: str) -> str:
        entry = needs.get(job_id) or {}
        return str(entry.get("result", "null"))

    if result("secret-scan") != "success":
        return False, f"secret-scan={result('secret-scan')}（任何情况下必查）"
    if deps_changed == "true" or event in ("schedule", "workflow_dispatch"):
        py, node = result("python-audit"), result("node-audit")
        if py != "success" or node != "success":
            return False, f"依赖安全审计未通过 python-audit={py} node-audit={node}"
        if event == "schedule":
            weekly = result("weekly-report")
            if weekly != "success":
                return False, f"weekly-report={weekly}（schedule 周全量兜底）"
    return True, "安全门禁通过"


def main() -> int:
    try:
        needs = json.loads(os.environ.get("NEEDS_JSON", "{}"))
    except json.JSONDecodeError:
        print("❌ NEEDS_JSON 解析失败（fail-closed）")
        return 1
    event = os.environ.get("EVENT_NAME", "")
    deps_changed = os.environ.get("DEPS_CHANGED", "")
    if not event:
        print("❌ EVENT_NAME 未设置（fail-closed）")
        return 1
    print("=== Security Scan Results ===")
    for job_id in JOB_IDS:
        entry = needs.get(job_id) or {}
        print(f"{job_id}: {entry.get('result', 'null')}")
    print(f"event={event} deps-changed={deps_changed}")
    ok, reason = evaluate(needs, event, deps_changed)
    if ok:
        print(f"✅ {reason}")
        return 0
    print(f"❌ {reason}，阻止合并")
    return 1


if __name__ == "__main__":
    sys.exit(main())
