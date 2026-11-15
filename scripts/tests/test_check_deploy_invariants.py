"""check_deploy_invariants 测试套（批次 3/M-05，BF-190）。

规则①② 为 M-36 既有语义（逐字保留断言），规则③④ 为 M-05 新增：
- ③ METRICS_TOKEN 三处形态矩阵（prod :? / monitoring :- / base django-environ）各唯一
- ④ Bearer 链路三要件（PROMETHEUS_CONFIG 变量插值 volume + bearer_token + expand-env）
G-0：护栏输入文件缺失/解码失败必须 exit 2（fail-closed，B-31 缺陷族）。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from check_deploy_invariants import GuardInfraError, check, main

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = REPO_ROOT / "asset_management_backend"

ENTRYPOINT_OK = """#!/bin/sh
set -euo pipefail
python manage.py migrate --noinput || exit 1
python manage.py collectstatic --noinput || exit 1
exec "$@"
"""

PROD_OK = (
    "  web:\n"
    "    environment:\n"
    "      - SECRET_KEY=${SECRET_KEY}\n"
    "      - METRICS_TOKEN=${METRICS_TOKEN:?请在 .env 中设置 METRICS_TOKEN}\n"
)
PROD_REVERTED = PROD_OK.replace("METRICS_TOKEN:?", "METRICS_TOKEN:-")
PROD_MISSING = PROD_OK.replace("      - METRICS_TOKEN=${METRICS_TOKEN:?请在 .env 中设置 METRICS_TOKEN}\n", "")
PROD_DUP = PROD_OK + "      - METRICS_TOKEN=${METRICS_TOKEN:?dup}\n"

MON_OK = (
    "  prometheus:\n"
    "    volumes:\n"
    "      - ${PROMETHEUS_CONFIG:-./config/prometheus.yml}:/etc/prometheus/prometheus.yml\n"
    "    environment:\n"
    "      - METRICS_TOKEN=${METRICS_TOKEN:-}\n"
    '    command:\n'
    '      - "--config.file=/etc/prometheus/prometheus.yml"\n'
    '      - "--config.expand-env"\n'
)
MON_WRONG = MON_OK.replace("METRICS_TOKEN:-}", "METRICS_TOKEN:?wrong}")
MON_VOLUME_HARD = MON_OK.replace(
    "${PROMETHEUS_CONFIG:-./config/prometheus.yml}", "./config/prometheus.yml"
)
MON_NO_EXPAND = MON_OK.replace('      - "--config.expand-env"\n', "")

BASE_OK = 'METRICS_TOKEN = config("METRICS_TOKEN", default="")\n'
BASE_DRIFT = 'METRICS_TOKEN = config("METRICS_TOKEN", default="preset-token")\n'

AUTH_OK = '    bearer_token: ${METRICS_TOKEN}\n'
AUTH_NO_BEARER = "# bearer_token: ${METRICS_TOKEN}\n"


def build_repo(tmp_path: Path, *, entrypoint: str = ENTRYPOINT_OK, prod: str = PROD_OK,
               mon: str = MON_OK, base: str = BASE_OK, auth: str = AUTH_OK,
               include: tuple = ("entrypoint", "prod", "mon", "base", "auth")) -> Path:
    root = tmp_path / "repo"
    backend = root / "asset_management_backend"
    cfg = backend / "config"
    (cfg / "settings").mkdir(parents=True)
    paths = {
        "entrypoint": backend / "docker-entrypoint.sh",
        "prod": backend / "docker-compose.prod.yml",
        "mon": backend / "docker-compose.monitoring.yml",
        "base": cfg / "settings" / "base.py",
        "auth": cfg / "prometheus.auth.yml",
    }
    content = {"entrypoint": entrypoint, "prod": prod, "mon": mon, "base": base, "auth": auth}
    for key in include:
        paths[key].write_text(content[key], encoding="utf-8")
    return root


# ---------- 规则①②（M-36 语义逐字保留） ----------

def test_rule1_set_e_removed_is_reported(tmp_path):
    text = ENTRYPOINT_OK.replace("set -euo pipefail", "# set -e removed")
    errors = check(build_repo(tmp_path, entrypoint=text))
    assert any("set -e" in e for e in errors)


def test_rule2_migrate_without_exit1_is_reported(tmp_path):
    text = ENTRYPOINT_OK.replace(
        "python manage.py migrate --noinput || exit 1", "python manage.py migrate --noinput"
    )
    errors = check(build_repo(tmp_path, entrypoint=text))
    assert any("migrate" in e and "|| exit 1" in e for e in errors)


# ---------- 规则③（形态矩阵） ----------

def test_rule3_prod_reverted_to_default_form_is_reported(tmp_path):
    errors = check(build_repo(tmp_path, prod=PROD_REVERTED))
    assert any("prod" in e and ":?" in e for e in errors)


def test_rule3_prod_token_line_missing_is_reported(tmp_path):
    errors = check(build_repo(tmp_path, prod=PROD_MISSING))
    assert any("prod" in e for e in errors)


def test_rule3_prod_duplicated_form_is_reported(tmp_path):
    errors = check(build_repo(tmp_path, prod=PROD_DUP))
    assert any("唯一" in e for e in errors)


def test_rule3_monitoring_required_form_is_reported(tmp_path):
    errors = check(build_repo(tmp_path, mon=MON_WRONG))
    assert any("monitoring" in e and ":-" in e for e in errors)


def test_rule3_base_drift_from_environ_form_is_reported(tmp_path):
    errors = check(build_repo(tmp_path, base=BASE_DRIFT))
    assert any('config("METRICS_TOKEN", default="")' in e for e in errors)


# ---------- 规则④（Bearer 链路三要件） ----------

def test_rule4_volume_interpolation_removed_is_reported(tmp_path):
    errors = check(build_repo(tmp_path, mon=MON_VOLUME_HARD))
    assert any("PROMETHEUS_CONFIG" in e for e in errors)


def test_rule4_bearer_token_removed_is_reported(tmp_path):
    errors = check(build_repo(tmp_path, auth=AUTH_NO_BEARER))
    assert any("bearer_token" in e for e in errors)


def test_rule4_expand_env_removed_is_reported(tmp_path):
    errors = check(build_repo(tmp_path, mon=MON_NO_EXPAND))
    assert any("expand-env" in e for e in errors)


# ---------- G-0（fail-closed） ----------

def test_g0_missing_file_raises_infra(tmp_path):
    with pytest.raises(GuardInfraError):
        check(build_repo(tmp_path, include=("entrypoint", "mon", "base", "auth")))


def test_g0_decode_failure_raises_infra(tmp_path):
    root = build_repo(tmp_path, include=("mon", "base", "auth"))
    (root / "asset_management_backend" / "docker-compose.prod.yml").write_bytes(
        b"\xd6\xd0\xce\xc4"  # GBK 字节, utf-8 解码必失败
    )
    with pytest.raises(GuardInfraError):
        check(root)


def test_g0_main_exit_code_2(tmp_path, capsys):
    assert main(["--root", str(build_repo(tmp_path, include=("mon", "base", "auth")))]) == 2
    assert "护栏输入" in capsys.readouterr().out


# ---------- 真仓绿锚 + PASS 文案锚 ----------

def test_real_repo_green():
    assert check(REPO_ROOT) == []


def test_real_repo_pass_message_anchors(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "BR-D1" in out
    assert "形态矩阵" in out
    assert "Bearer 链路" in out
