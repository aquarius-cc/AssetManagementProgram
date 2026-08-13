# -*- coding: utf-8 -*-
"""重复代码回归护栏 (Duplicate Code Regression Guard)

守护可验证不变量，防止已在活账本中关闭的重复实现复现。
账本：Rules_Fiels/Duplicate_Codes/complete-patterns.md

退出码：
  0 = 全部通过
  1 = 阻断项失败（G-1~G-3 任一命中）
  2 = 仅报告项命中（G-4 为 v1.7 遗留债提示，不阻断）

用法：python scripts/check_duplicate_invariants.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "asset_management_backend"
FRONTEND = ROOT / "vue-assetmanagement"

BLOCKING = []
WARNINGS = []


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return ""


def iter_py_files(scope_dir: Path):
    if not scope_dir.exists():
        return
    for path in scope_dir.rglob("*.py"):
        yield path


def check_g1_closed_patterns_absent():
    """G-1: 已关闭模式名称不得复现"""
    blacklist = [
        r"def validate_asset_status",
        r"def validate_recycling_path",
        r"def check_recycling_chain",
        r"def validate_status_transition",
        r"def filter_assets",
        r"class AssetQueryManager",
        r"class AssetStateValidator",
        r"class AssetSelectionStrategy",
        r"def asset_view_checkout",
        r"def asset_view_create",
        r"def get_by_asset_id",
        r"def user_profile_by_user_id",
    ]
    for path in iter_py_files(BACKEND / "apps"):
        for lineno, line in enumerate(read_text(path).splitlines(), start=1):
            for pattern in blacklist:
                if re.search(pattern, line):
                    BLOCKING.append(f"G-1 已关闭模式复发 {path.relative_to(ROOT)}:{lineno} 匹配 {pattern!r}")


def check_g2_operation_log_single_impl():
    """G-2: 操作日志查询唯一实现（Service 委托 Selector，Manager 不得复现）"""
    svc = BACKEND / "apps" / "assetmanagement" / "services" / "operation_log_service.py"
    if svc.exists() and "OperationLogSelector" not in read_text(svc):
        BLOCKING.append("G-2 operation_log_service.py 未 import/委托 OperationLogSelector")
    for path in iter_py_files(BACKEND / "apps"):
        for lineno, line in enumerate(read_text(path).splitlines(), start=1):
            if re.search(r"^\s*class AssetOperationLogManager", line):
                BLOCKING.append(f"G-2 AssetOperationLogManager 重新出现 {path.relative_to(ROOT)}:{lineno}")


def check_g3_frontend_single_source():
    """G-3: 前端资产状态映射单一来源（Format.ts 派生自 statusMapping，不得内联字面量）"""
    fmt = FRONTEND / "src" / "utils" / "Format.ts"
    if not fmt.exists():
        return
    text = read_text(fmt)
    if "ASSET_STATUS_MAP" not in text or "./statusMapping" not in text:
        BLOCKING.append("G-3 Format.ts 未从 ./statusMapping 的 ASSET_STATUS_MAP 派生资产状态映射")
    if re.search(r"in_store:\s*'在库'", text):
        BLOCKING.append("G-3 Format.ts 内联了资产状态字面量映射(应改为派生)")


def check_g4_error_codes_registered():
    """G-4(报告型): 服务层 raise 使用的 error_code 字面量应注册于 BusinessCode

    当前大量字符串码未注册属 v1.7 BizCode 遗留债(C-3)，仅报告不阻断。
    新增 error_code 时若未注册将在此提示，需根级统筹后注册。
    """
    reg = BACKEND / "utils" / "response_utils.py"
    if not reg.exists():
        return
    registered = set(re.findall(r"^\s+([A-Z][A-Z0-9_]+)\s*=\s*\d+", read_text(reg), re.M))
    used: dict[str, list[str]] = {}
    for path in iter_py_files(BACKEND / "apps"):
        for code in re.findall(r'error_code="([A-Z][A-Z0-9_]+)"', read_text(path)):
            used.setdefault(code, []).append(str(path.relative_to(BACKEND)))
    unregistered = {code for code in used if code not in registered}
    if unregistered:
        detail = ", ".join(f"{c}({len(used[c])}处)" for c in sorted(unregistered))
        WARNINGS.append(f"G-4 未注册 error_code 字面量(v1.7 BizCode 遗留债): {detail}")


def main() -> int:
    check_g1_closed_patterns_absent()
    check_g2_operation_log_single_impl()
    check_g3_frontend_single_source()
    check_g4_error_codes_registered()

    for item in BLOCKING:
        print(f"[BLOCK] {item}")
    for item in WARNINGS:
        print(f"[WARN] {item}")

    if BLOCKING:
        print(f"[RESULT] FAIL: {len(BLOCKING)} 个阻断项")
        return 1
    if WARNINGS:
        print(f"[RESULT] PASS(带提示): {len(WARNINGS)} 个报告项(不阻断)")
        return 0
    print("[RESULT] PASS: 重复代码回归护栏全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
