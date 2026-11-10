"""check_secret_fingerprints 护栏自测（批次 5 / M-34 + M-11）

5 态夹具矩阵（方案 §3.4）+ fail-closed 边界 + 真仓绿锚（G9 第 5 项）。
夹具值一律运行时拼接（源码零连续密样，含 AKIA/PEM 结构样例的分段拼接——
本文件位于 tests 路径且被真仓绿锚扫描，字面量必须无法被自身第一道命中）。
"""

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from check_secret_fingerprints import (  # noqa: E402
    FINGERPRINTS_PATH,
    _load_fingerprints,
    _read_or_flag,
    _scan_mode,
    scan_quoted_text,
    scan_revoked_text,
)

_FX_PASS = "Test@" + "12345678!"  # 真仓已登记夹具值（allowlist 覆盖）
_FX_MOCK = "valid" + "-token"  # 真仓前端 spec 高频 mock 值
_REVOKED = "Postgres" + "Terminal@8348"
_AKIA = "AKIA" + "IOSFODNN7" + "EXAMPLE"  # AWS 官方文档示例键，分段防自锚
_PEM = "-----BEGIN" + " " + "PRIVATE" + " KEY-----"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_real_repo_default_root_green():
    """真仓绿锚（G9 第 5 项）：当前仓库两道扫描零命中（53 处夹具全走白名单）。"""
    root = Path(__file__).resolve().parent.parent.parent
    fingerprints = _load_fingerprints(FINGERPRINTS_PATH)
    assert _scan_mode(root, fingerprints, "quoted") == []
    assert _scan_mode(root, fingerprints, "revoked") == []


def test_registered_fixture_in_tests_green():
    """态 1：tests 夹具值已登记指纹 → 放行（M-34 修复主锚）。"""
    text = 'password="' + _FX_PASS + '"\n'
    assert scan_quoted_text("pkg/tests/test_a.py", text, {_sha(_FX_PASS)}) == []


def test_frontend_spec_path_diversion_green():
    """态 1 扩：前端 __tests__/*.spec.ts 同享分流（is_tests_path 扩展段）。"""
    text = "token = '" + _FX_MOCK + "'\n"
    assert scan_quoted_text("src/stores/__tests__/x.spec.ts", text, {_sha(_FX_MOCK)}) == []


def test_unregistered_high_entropy_in_tests_red():
    """态 2：tests 内未登记高熵值 → 红（SC-2 不因白名单稀释）。"""
    text = 'password="Unregistered9!"\n'
    assert len(scan_quoted_text("pkg/tests/test_a.py", text, set())) == 1


def test_registered_value_outside_tests_red():
    """态 3：同一已登记值出现在非 tests 路径 → 恒红（分流仅限 tests）。"""
    text = 'password="' + _FX_PASS + '"\n'
    assert len(scan_quoted_text("apps/service.py", text, {_sha(_FX_PASS)})) == 1


def test_yaml_quoted_secret_red():
    """态 4a：M-11 扩面——.yml 引号形态纳入第一道（原 rg 无 --type yaml）。"""
    text = 'password: "SomePass123"\n'
    assert len(scan_quoted_text(".github/workflows/x.yml", text, set())) == 1


def test_quoted_placeholder_in_tests_green():
    """CI 哑值/占位值经 is_placeholder 单源判定放行（G11 复用）。"""
    text = 'password = "changeme-fixture-123"\n'
    assert scan_quoted_text("scripts/tests/fixtures/x.py", text, set()) == []


def test_structural_patterns_never_diverted():
    """态 4b：AKIA / PEM 结构形态即使位于 tests 路径也永不分流。"""
    assert len(scan_quoted_text("pkg/tests/test_b.py", _AKIA + "\n", set())) == 1
    assert len(scan_quoted_text("pkg/tests/test_b.py", _PEM + "\n", set())) == 1


def test_revoked_reflow_red_anywhere():
    """态 4c：已轮换凭据回流 → 红（第三道，无注释豁免——取代 rg -F 黑名单）。"""
    text = "db_password" + "=" + _REVOKED + "  # 已轮换失效，仅留痕\n"
    assert len(scan_revoked_text("docs/incident.md", text, {_sha(_REVOKED)})) == 1


def test_decode_failure_fail_closed_red(tmp_path):
    """态 5：解码失败（utf-8-sig/utf-8/gbk 全失败）且无 NUL → fail-closed 判红（B-31 同型）。"""
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"\xff\xff\xff\xff\xff")
    text, flagged = _read_or_flag(blob, "blob.bin")
    assert text == ""
    assert len(flagged) == 1 and "解码失败" in flagged[0]


def test_binary_nul_skipped_not_red(tmp_path):
    """二进制文件（前 8KB 含 NUL）跳过留痕，不误伤为解码失败红。"""
    blob = tmp_path / "cache.db"
    blob.write_bytes(b"SQLite format 3\x00" + b"\xff" * 64)
    text, flagged = _read_or_flag(blob, "cache.db")
    assert text == ""
    assert flagged == []


def test_git_failure_fail_closed(tmp_path):
    """git ls-files 失败（非 git 目录）→ RuntimeError → main 转 exit 2（不放行空树）。"""
    with pytest.raises(RuntimeError):
        _scan_mode(tmp_path, {"revoked": [_sha("x")], "allowlist": [_sha("y")]}, "quoted")


def test_fingerprints_config_missing_exit2(tmp_path):
    """配置缺失 → exit 2（fail-closed，不放行为空配置绿）。"""
    import check_secret_fingerprints as guard

    assert guard.main(["--quoted", "--fingerprints", str(tmp_path / "nope.json")]) == 2
