"""重复代码回归护栏 (Duplicate Code Regression Guard)

守护可验证不变量，防止已在活账本中关闭的重复实现复现。
账本：Rules_Fiels/Duplicate_Codes/complete-patterns.md

退出码：
  0 = 全部通过
  1 = 阻断项失败（G-1~G-3、G-5~G-7 任一命中）

用法：python scripts/check_duplicate_invariants.py
"""

import argparse
import ast
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
ROOT = DEFAULT_ROOT
BACKEND = ROOT / "asset_management_backend"
FRONTEND = ROOT / "vue-assetmanagement"

BLOCKING = []
WARNINGS = []

# G-6/G-7 共享豁免名单（BF-170）：system_admin-only 域的批量删除——
# 权限类（IsSystemAdmin）已在视图层兜底，无部门范围语义可校验。
G6_G7_EXEMPT = frozenset(
    {
        "batch_delete_asset_type",
        "batch_delete_contract",
        "batch_delete_storage",
        "batch_delete_department",
        "batch_delete_employee",
    }
)


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
    yield from scope_dir.rglob("*.py")


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
        r"def get_asset_recordcode_by_asset_code",
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


def check_g5_no_shadow_modules():
    """G-5: 影子死文件不得复现——同名 .py 不得与包（含 __init__.py）并存（包优先解析使 .py 成死代码）"""
    apps_dir = BACKEND / "apps"
    if not apps_dir.exists():
        return
    for init in apps_dir.rglob("__init__.py"):
        pkg_dir = init.parent
        shadow = pkg_dir.parent / (pkg_dir.name + ".py")
        if shadow.exists():
            BLOCKING.append(
                f"G-5 影子死文件 {shadow.relative_to(ROOT)} 与包 {pkg_dir.relative_to(ROOT)}/ 并存，禁止新增，需删除同名 .py"
            )


def _iter_ast_trees(apps_dir: Path):
    """apps/ 下全部 .py 的 (path, ast_tree)（语法错误跳过，由 ruff/mypy 兜底）。"""
    for path in apps_dir.rglob("*.py"):
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError:
            continue
        yield path, tree


def check_g6_batch_delete_services_carry_user():
    """G-6: service 层批量删除必须携带 user 参数（BF-170，B14 逐条校验自动化断言）

    范围谓词：父目录名 == services 或 文件名 == services.py（覆盖包式与单文件两种布局）。
    仅断言 user 参数存在（AST arg 检测），不断言默认值/跳过分支——
    「必填无跳过」由签名纪律与 CT-1 用例在运行时约束。
    """
    apps_dir = BACKEND / "apps"
    if not apps_dir.exists():
        return
    for path, tree in _iter_ast_trees(apps_dir):
        is_service_file = path.parent.name == "services" or path.name == "services.py"
        if not is_service_file:
            continue
        rel = path.relative_to(ROOT)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("batch_delete_"):
                args = {a.arg for a in node.args.args + node.args.kwonlyargs}
                if "user" not in args and node.name not in G6_G7_EXEMPT:
                    BLOCKING.append(
                        f"G-6 批量删除服务缺少 user 参数 {rel}:{node.lineno} {node.name}（B14 逐条校验）"
                    )


def check_g7_view_batch_delete_wired():
    """G-7: view 层批量删除必须接线 batch_delete_passes_user = True（BF-170，B12 自动化断言）

    检测含 `batch_delete_service = <X>.<name>` 赋值的类；取赋值尾段标识符（服务函数名）
    查共享豁免名单，未豁免而未接线（或接线非 True）→ BLOCKING。
    """
    apps_dir = BACKEND / "apps"
    if not apps_dir.exists():
        return
    for path, tree in _iter_ast_trees(apps_dir):
        rel = path.relative_to(ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            service_name: str | None = None
            passes_user = None
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                    target = stmt.targets[0]
                    # 类体赋值目标为 ast.Name；属性赋值（self.x = ...）为 ast.Attribute——两者皆收
                    attr = target.attr if isinstance(target, ast.Attribute) else (
                        target.id if isinstance(target, ast.Name) else None
                    )
                    if attr not in ("batch_delete_service", "batch_delete_passes_user"):
                        continue
                    if attr == "batch_delete_service":
                        # 取赋值尾段标识符：OutAssetService.batch_delete_outasset → batch_delete_outasset
                        if isinstance(stmt.value, ast.Attribute) and isinstance(stmt.value.attr, str):
                            service_name = stmt.value.attr
                    else:
                        passes_user = stmt.value
            if service_name is None or service_name in G6_G7_EXEMPT:
                continue
            if not (isinstance(passes_user, ast.Constant) and passes_user.value is True):
                BLOCKING.append(
                    f"G-7 批量删除视图未接线 passes_user {rel}:{node.lineno} {node.name} "
                    f"（service={service_name}，需 batch_delete_passes_user = True）"
                )


def main(argv=None) -> int:
    global ROOT, BACKEND, FRONTEND
    parser = argparse.ArgumentParser(description="重复代码回归护栏 (G-1~G-3、G-5~G-7)")
    parser.add_argument("--root", type=Path, default=None, help="扫描根目录(默认仓库根)")
    args = parser.parse_args(argv)

    BLOCKING.clear()
    WARNINGS.clear()
    ROOT = args.root if args.root is not None else DEFAULT_ROOT
    BACKEND = ROOT / "asset_management_backend"
    FRONTEND = ROOT / "vue-assetmanagement"

    check_g1_closed_patterns_absent()
    check_g2_operation_log_single_impl()
    check_g3_frontend_single_source()
    check_g5_no_shadow_modules()
    check_g6_batch_delete_services_carry_user()
    check_g7_view_batch_delete_wired()

    for item in BLOCKING:
        print(f"[BLOCK] {item}")
    for item in WARNINGS:
        print(f"[WARN] {item}")

    if BLOCKING:
        print(f"[RESULT] FAIL: {len(BLOCKING)} 个阻断项")
        return 1
    print("[RESULT] PASS: 重复代码回归护栏全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
