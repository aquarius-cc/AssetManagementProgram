#!/usr/bin/env python3
# =============================================================================
# 部署护栏: docker-entrypoint.sh 失败快速退出不变量 (M-36)
# =============================================================================
# 锁定两条核心不变量, 防止入口脚本回退为「迁移失败仍启动」:
#   ① 脚本含 set -e 语义 (set -euo pipefail / set -e)
#   ② migrate / collectstatic 关键步显式 || exit 1
#     (双保险: 即使 ① 被后人删除, ② 仍保住关键步, 且可被本护栏文本校验)
#
# 设计约束: 只做规则①②, 不做「顶层命令白名单」通用静态分析——
# 用正则对 shell 做块/续行级解析误报率不可控 (M-36 评审决议)。
# =============================================================================
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "asset_management_backend"
ENTRYPOINT = BACKEND / "docker-entrypoint.sh"

# 规则②的目标命令前缀 (仅 migrate / collectstatic 两类关键步)
CRITICAL_PREFIXES = (
    "python manage.py migrate",
    "python manage.py collectstatic",
)


def check() -> list[str]:
    errors: list[str] = []
    text = ENTRYPOINT.read_text(encoding="utf-8")
    lines = text.splitlines()

    # ① set -e 语义
    if not re.search(r"^set\s+-e", text, re.MULTILINE):
        errors.append(
            f"{ENTRYPOINT.name}: 未找到 set -e 语义 (需 set -euo pipefail 或 set -e)——"
            "迁移/静态收集失败将不再阻断启动 (M-36 回归)"
        )

    # ② 关键步显式 || exit 1
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for prefix in CRITICAL_PREFIXES:
            if stripped.startswith(prefix):
                if "|| exit 1" not in stripped:
                    errors.append(
                        f"{ENTRYPOINT.name}:{raw}: 关键步 '{prefix}...' 缺少 '|| exit 1'——"
                        "失败时容器仍会启动, 以未迁移库对外服务 (M-36 回归)"
                    )

    return errors


def main() -> int:
    errors = check()
    if errors:
        print("[FAIL] BR-D1 部署入口护栏: %d 处违规" % len(errors))
        for e in errors:
            print("  -", e)
        return 1
    print("[PASS] BR-D1 部署入口护栏通过(set -e 语义在位, migrate/collectstatic 关键步显式 || exit 1)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
