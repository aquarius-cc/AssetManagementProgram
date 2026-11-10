"""check_secret_tracking 护栏自测 (OP-20, G-8 自测口径先例)

夹具值一律运行时拼接(源码零连续密样): 护栏扫描 staged 行, 自测若含连续
"键=真值" 字面量会被自身拦截(dogfooding 闭环); 拼接后断言效力不变。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from check_secret_tracking import is_placeholder, scan_staged  # noqa: E402

_REAL_DB = "Super" + "Secret123"
_REAL_REDIS = "Rd3al" + "Secret99"

DIFF_REAL_DB = "+DB_PASSWORD=" + _REAL_DB + "\n"
DIFF_REAL_REDIS = '+REDIS_PASSWORD="' + _REAL_REDIS + '"\n'
DIFF_CONTEXT = " DB_PASSWORD=" + _REAL_DB + "\n+++ b/.env.example\n-DB_PASSWORD=" + _REAL_DB + "\n"


def test_staged_real_db_password_red():
    assert len(scan_staged(DIFF_REAL_DB)) == 1


def test_staged_real_redis_password_quoted_red():
    assert len(scan_staged(DIFF_REAL_REDIS)) == 1


def test_staged_placeholders_pass():
    diff = (
        "+DB_PASSWORD=\n"
        "+DB_PASSWORD=${DB_PASSWORD}\n"
        "+METRICS_TOKEN=${METRICS_TOKEN:-}\n"
        "+SECRET_KEY=change-this-to-a-real-secret-key\n"
        "+METRICS_TOKEN=your-token-here-please-replace\n"
    )
    assert scan_staged(diff) == []


def test_staged_context_and_header_lines_ignored():
    """上下文行(空格前缀)/文件头(+ + +)/删除行(-)不扫描"""
    assert scan_staged(DIFF_CONTEXT) == []


def test_staged_short_value_not_matched():
    """值 <8 字符不构成凭据强度, 不误报"""
    assert scan_staged("+DB_PASSWORD=123\n") == []


def test_staged_compose_env_passthrough_passes():
    """compose 透传行（${VAR:-} 插值）放行"""
    assert scan_staged("      - METRICS_TOKEN=${METRICS_TOKEN:-}\n") == []


def test_is_placeholder_public_entry():
    """G11：占位判定公共入口——指纹护栏（check_secret_fingerprints）按此单源复用"""
    assert is_placeholder("your-secret-key-here")
    assert is_placeholder("changeme-after-first-login")
    assert is_placeholder("${DB_PASSWORD}")
    assert not is_placeholder("Str0ng" + "Pass!123")
    assert not is_placeholder("ci-test-generic-key-not-for-any-environment-123")
