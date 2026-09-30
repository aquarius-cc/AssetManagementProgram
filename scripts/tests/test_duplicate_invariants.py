# -*- coding: utf-8 -*-
"""重复代码回归护栏（G-1~G-5）自测：每条不变量造一个复发夹具证红，干净镜像证绿。

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


def test_real_repo_default_root_green(capsys):
    assert g.main([]) == 0
    assert "[RESULT] PASS" in capsys.readouterr().out