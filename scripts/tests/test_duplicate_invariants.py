# -*- coding: utf-8 -*-
"""重复代码回归护栏（G-1~G-3、G-5~G-7）自测：每条不变量造一个复发夹具证红，干净镜像证绿。

护栏：scripts/check_duplicate_invariants.py（进程内调用 main()，--root 注入夹具根）。
"""
from helpers import write

import check_duplicate_invariants as g

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


def test_real_repo_default_root_green(capsys):
    assert g.main([]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out