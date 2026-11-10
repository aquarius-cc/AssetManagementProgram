"""重复代码回归护栏（G-1~G-3、G-5~G-8）自测：每条不变量造一个复发夹具证红，干净镜像证绿。

护栏：scripts/check_duplicate_invariants.py（进程内调用 main()，--root 注入夹具根）。
"""
import check_duplicate_invariants as g
from helpers import write, write_bom

SVCS = "asset_management_backend/apps/assetmanagement/services/operation_log_service.py"
FORMAT = "vue-assetmanagement/src/utils/Format.ts"


def test_g1_closed_pattern_reappears_red(tmp_path, capsys):
    write(tmp_path / "asset_management_backend" / "apps" / "service.py",
          "def validate_asset_status():\n    pass\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-1" in capsys.readouterr().out


def test_g2_service_not_delegating_red(tmp_path, capsys):
    write(tmp_path / SVCS, "def query():\n    pass\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-2" in capsys.readouterr().out


def test_g2_manager_reappears_red(tmp_path, capsys):
    write(tmp_path / "asset_management_backend" / "apps" / "x.py",
          "class AssetOperationLogManager:\n    pass\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-2" in capsys.readouterr().out


def test_g3_inline_mapping_red(tmp_path, capsys):
    text = 'import { ASSET_STATUS_MAP } from "./statusMapping";\n'
    text += "export const M = ASSET_STATUS_MAP;\n"
    text += "const X = { in_store: '在库' };\n"
    write(tmp_path / FORMAT, text)
    assert g.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "G-3" in out and "内联" in out


# ---------------- 批次 4b G-3 扩展自测（账本 C-16：全消费点覆盖 + 跨端 8 键全等） ----------------

ASSET_PY = "asset_management_backend/apps/assetmanagement/models/asset.py"
STATUS_MAP_TS = "vue-assetmanagement/src/utils/statusMapping.ts"
EIGHT_KEYS = [
    "broken",
    "damaged",
    "in_store",
    "in_use",
    "lost",
    "recycled_pending",
    "repairing",
    "scrapped",
]


def _asset_status_py(keys):
    body = "\n".join(f'    {k.upper()} = "{k}", "{k}"' for k in keys)
    return f"from django.db import models\n\nclass AssetStatus(models.TextChoices):\n{body}\n"


def _status_map_ts(keys):
    body = "\n".join(f"  {k}: {{ label: '{k}', type: 'info' }}," for k in keys)
    return (
        "export const ASSET_STATUS_MAP: Record<string, { label: string; type: string }> = {\n"
        f"{body}\n}}\n"
    )


def _write_cross_end(tmp_path, backend_keys, frontend_keys):
    write(tmp_path / ASSET_PY, _asset_status_py(backend_keys))
    write(tmp_path / STATUS_MAP_TS, _status_map_ts(frontend_keys))


def test_g3_component_inline_semantic_map_red(tmp_path, capsys):
    """组件 .vue 内联语义映射（C-16 形态清单）回潮即红。"""
    write(
        tmp_path / "vue-assetmanagement/src/components/X.vue",
        "<template><div/></template>\n"
        "<script setup>\n"
        "const typeColorMap: Record<string, string> = { approval: 'primary' }\n"
        "</script>\n",
    )
    _write_cross_end(tmp_path, EIGHT_KEYS, EIGHT_KEYS)
    assert g.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "G-3" in out and "内联状态语义映射回潮" in out


def test_g3_function_internal_map_red(tmp_path, capsys):
    """函数内 `const map: Record<string,string>` 形态（C-16 命令 A 命中形态）回潮即红。"""
    write(
        tmp_path / "vue-assetmanagement/src/views/Y.vue",
        "<template><div/></template>\n"
        "<script setup>\n"
        "function f() {\n"
        "  const map: Record<string, string> = { a: 'b' }\n"
        "  return map\n"
        "}\n"
        "</script>\n",
    )
    _write_cross_end(tmp_path, EIGHT_KEYS, EIGHT_KEYS)
    assert g.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "G-3" in out and "函数内联语义 map 回潮" in out


def test_g3_cross_end_key_divergence_red(tmp_path, capsys):
    """跨端键集分叉（双侧各 8 键但键名不一致）即红。"""
    frontend_keys = [k if k != "scrapped" else "scrapped_typo" for k in EIGHT_KEYS]
    _write_cross_end(tmp_path, EIGHT_KEYS, frontend_keys)
    assert g.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "G-3" in out and "键集分叉" in out


def test_g3_cross_end_unparseable_fail_closed(tmp_path, capsys):
    """后端 AssetStatus 块缺失/不可定位 → fail-closed 判红，不得静默跳过（G-0/B-31 族）。"""
    write(tmp_path / ASSET_PY, "from django.db import models\n\nclass Other(models.TextChoices):\n    A = 'a', 'a'\n")
    write(tmp_path / STATUS_MAP_TS, _status_map_ts(EIGHT_KEYS))
    assert g.main(["--root", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "G-3" in out and "未定位到 class AssetStatus" in out


def test_g3_cross_end_eight_keys_green(tmp_path, capsys):
    """干净镜像：双侧 8 键全等 + 组件零内联 → 绿。"""
    _write_cross_end(tmp_path, EIGHT_KEYS, EIGHT_KEYS)
    write(
        tmp_path / FORMAT,
        'import { ASSET_STATUS_MAP } from "./statusMapping";\n'
        "export const fmt = (s: string) => ASSET_STATUS_MAP[s];\n",
    )
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


def test_g5_shadow_file_red(tmp_path, capsys):
    write(tmp_path / "asset_management_backend" / "apps" / "assetmanagement" / "__init__.py", "")
    write(tmp_path / "asset_management_backend" / "apps" / "assetmanagement.py",
          "class App:\n    pass\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-5" in capsys.readouterr().out


def test_green_compliant_fixture(tmp_path, capsys):
    write(tmp_path / SVCS, "class OperationLogSelector:\n    pass\n")
    write(tmp_path / "asset_management_backend" / "apps" / "assetmanagement" / "__init__.py", "")
    write(tmp_path / FORMAT,
          'import { ASSET_STATUS_MAP } from "./statusMapping";\n'
          "export const fmt = (s: string) => ASSET_STATUS_MAP[s];\n")
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


# --------------------------------------------------------------------------
# G-6：service 层批量删除必须携带 user 参数（BF-170）
# --------------------------------------------------------------------------


def test_g6_service_batch_delete_without_user_red(tmp_path, capsys):
    write(tmp_path / "asset_management_backend" / "apps" / "x" / "services" / "a.py",
          "class S:\n    def batch_delete_thing(self, ids):\n        pass\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-6" in capsys.readouterr().out


def test_g6_service_batch_delete_with_user_green(tmp_path, capsys):
    write(tmp_path / "asset_management_backend" / "apps" / "x" / "services" / "a.py",
          "class S:\n    def batch_delete_thing(self, ids, *, user):\n        pass\n")
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


def test_g6_exempt_service_green(tmp_path, capsys):
    """豁免名单（system_admin-only 域）不带 user 亦绿。"""
    write(tmp_path / "asset_management_backend" / "apps" / "x" / "services" / "a.py",
          "class S:\n    def batch_delete_employee(self, jobcodes):\n        pass\n")
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


def test_g6_single_file_services_layout_red(tmp_path, capsys):
    """范围谓词：文件名 == services.py 的单文件布局同样受检。"""
    write(tmp_path / "asset_management_backend" / "apps" / "y" / "services.py",
          "class S:\n    def batch_delete_widget(self, ids):\n        pass\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-6" in capsys.readouterr().out


def test_g6_views_dir_not_scanned(tmp_path, capsys):
    """views/ 下的 action 方法不受 G-6 约束（范围谓词仅 services）。"""
    write(tmp_path / "asset_management_backend" / "apps" / "x" / "views" / "a.py",
          "class V:\n    def batch_delete(self, request):\n        pass\n")
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


# --------------------------------------------------------------------------
# G-7：view 层批量删除必须接线 batch_delete_passes_user = True（BF-170）
# --------------------------------------------------------------------------


def test_g7_view_batch_delete_unwired_red(tmp_path, capsys):
    write(tmp_path / "asset_management_backend" / "apps" / "x" / "views" / "a.py",
          "class V:\n"
          "    batch_delete_service = S.batch_delete_thing\n"
          )
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-7" in capsys.readouterr().out


def test_g7_view_batch_delete_wired_green(tmp_path, capsys):
    write(tmp_path / "asset_management_backend" / "apps" / "x" / "views" / "a.py",
          "class V:\n"
          "    batch_delete_service = S.batch_delete_thing\n"
          "    batch_delete_passes_user = True\n"
          )
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


def test_g7_wired_false_red(tmp_path, capsys):
    """接线为 False 同样红（形接线实未通）。"""
    write(tmp_path / "asset_management_backend" / "apps" / "x" / "views" / "a.py",
          "class V:\n"
          "    batch_delete_service = S.batch_delete_thing\n"
          "    batch_delete_passes_user = False\n"
          )
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-7" in capsys.readouterr().out


def test_g7_exempt_service_green(tmp_path, capsys):
    """豁免服务不接线亦绿（system_admin-only 域）。"""
    write(tmp_path / "asset_management_backend" / "apps" / "x" / "views" / "a.py",
          "class V:\n"
          "    batch_delete_service = S.batch_delete_department\n"
          )
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


# --------------------------------------------------------------------------
# G-8：role/employee_status 历史字面量回归拦截（M-08）
# --------------------------------------------------------------------------


def test_g8_role_kwarg_literal_red(tmp_path, capsys):
    write(tmp_path / "asset_management_backend" / "apps" / "em" / "views" / "a.py",
          'def f():\n    filter(role="dept_manager")\n')
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-8" in capsys.readouterr().out


def test_g8_status_assign_literal_red(tmp_path, capsys):
    write(tmp_path / "asset_management_backend" / "apps" / "em" / "services" / "a.py",
          "def f():\n    employee_status = 'left'\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-8" in capsys.readouterr().out


def test_g8_enum_call_form_green(tmp_path, capsys):
    write(tmp_path / "asset_management_backend" / "apps" / "em" / "services" / "a.py",
          "from apps.usermanagement.models import EmployeeRole\n"
          "def f():\n"
          "    filter(role=EmployeeRole.DEPT_MANAGER, employee_status=EmployeeStatus.ACTIVE)\n")
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


def test_g8_non_whitelist_literal_green(tmp_path, capsys):
    """值域白名单外的字面量（如 asset_admin）不受 G-8 约束。"""
    write(tmp_path / "asset_management_backend" / "apps" / "em" / "views" / "a.py",
          "def f():\n    filter(role='asset_admin')\n")
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


def test_g8_migrations_and_tests_not_scanned(tmp_path, capsys):
    """migrations/（CT-6 禁改）与 tests/（夹具）在范围外。"""
    write(tmp_path / "asset_management_backend" / "apps" / "em" / "migrations" / "0001.py",
          "def seed():\n    Employee.objects.create(role='dept_manager')\n")
    write(tmp_path / "asset_management_backend" / "apps" / "em" / "tests" / "test_x.py",
          "def t():\n    Employee(employee_status='active')\n")
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


def test_g8_docstring_noise_green(tmp_path, capsys):
    """docstring/help_text/错误文案中的字面量是 AST 字符串表达式，不构成 kwargs/赋值，不误红。"""
    write(tmp_path / "asset_management_backend" / "apps" / "em" / "views" / "a.py",
          "def f():\n"
          '    """示例: role=\'dept_manager\', employee_status=\'active\'"""\n'
          "    return '有效值为: active, left, retirement'\n")
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


def test_real_repo_default_root_green(capsys):
    assert g.main([]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# B-31 缺陷族「解码序/静默跳过」证红用例（M-02，G-0 fail-closed）
# ---------------------------------------------------------------------------

def test_bom_batch_delete_service_missing_user_red(tmp_path, capsys):
    """证红：BOM .py 不得绕过 G-6（修复前 ast.parse 抛 SyntaxError → 静默跳过 → 假绿）。"""
    write_bom(tmp_path / SVCS,
              "from .selectors import OperationLogSelector\n"
              "def batch_delete_assets(items):\n    pass\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-6" in capsys.readouterr().out


def test_bom_enum_literal_red(tmp_path, capsys):
    """证红：BOM .py 不得绕过 G-8（合规 SVCS 随行写入，隔离 G-2 面）。"""
    write(tmp_path / SVCS, "from .selectors import OperationLogSelector\n")
    write_bom(tmp_path / "asset_management_backend" / "apps" / "assetmanagement" / "foo.py",
              "role = 'dept_manager'\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-8" in capsys.readouterr().out


def test_no_bom_batch_delete_control_red(tmp_path, capsys):
    """对照组：无 BOM 同型 G-6 夹具亦红（修的是堵绕过，不是变全红）。"""
    write(tmp_path / SVCS,
          "from .selectors import OperationLogSelector\n"
          "def batch_delete_warehouses(items):\n    pass\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-6" in capsys.readouterr().out


def test_syntax_error_is_red(tmp_path, capsys):
    """证红：语法破损非空 .py → G-0 阻断项（修复前静默跳过 → 假绿）。"""
    write(tmp_path / SVCS, "from .selectors import OperationLogSelector\n")
    write(tmp_path / "asset_management_backend" / "apps" / "broken.py",
          "def f(:\n    pass\n")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-0" in capsys.readouterr().out


def test_zero_byte_py_stays_green(tmp_path, capsys):
    """回归锚：零字节文件（现实仓 11 个 __init__.py 实例）合法跳过，不得 G-0 误红。"""
    write(tmp_path / SVCS, "from .selectors import OperationLogSelector\n")
    write(tmp_path / "asset_management_backend" / "apps" / "assetmanagement" / "__init__.py", "")
    write(tmp_path / "asset_management_backend" / "apps" / "assetmanagement" / "services" / "__init__.py", "")
    assert g.main(["--root", str(tmp_path)]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out


def test_undecodable_nonempty_is_red(tmp_path, capsys, monkeypatch):
    """证红（AR-1：不赌 gbk 字节行为，直接注入解码失败）：非空文件不可解码 → G-0。"""
    write(tmp_path / SVCS, "from .selectors import OperationLogSelector\n")
    write(tmp_path / "asset_management_backend" / "apps" / "weird.py", "x = 1\n")
    monkeypatch.setattr(g, "read_text", lambda path: "")
    assert g.main(["--root", str(tmp_path)]) == 1
    assert "G-0" in capsys.readouterr().out