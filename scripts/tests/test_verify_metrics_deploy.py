"""verify_metrics_deploy 测试套（批次 3/M-05，BF-190）。

部署前置自检 --preflight 的纯函数与 CLI 负向用例：
- G2 串联：渲染核对须覆盖 Bearer 链路三要件
- G3 同源：两栈 token 渲染值一致
- G6 精确诊断：validate_token 各失败原因独立可辨
- G7 脱敏：任何输出不得包含 token 原值
- G-0：空输入/坏输入 exit 2（fail-closed）
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verify_metrics_deploy import (
    check_rendered,
    check_same_source,
    main,
    validate_token,
)

TOKEN = "unit-test-token-0123456789abcdef-xyz"  # tests 路径, 占位判定不适用
OTHER = "unit-test-token-ffffffffffffffffff-abc"

CFG_OK = {
    "services": {
        "web": {"environment": {"METRICS_TOKEN": TOKEN}},
        "prometheus": {
            "environment": {"METRICS_TOKEN": TOKEN},
            "command": [
                "--config.file=/etc/prometheus/prometheus.yml",
                "--config.expand-env",
            ],
            "volumes": [
                {
                    "type": "bind",
                    "source": "./config/prometheus.auth.yml",
                    "target": "/etc/prometheus/prometheus.yml",
                }
            ],
        },
    }
}


# ---------- validate_token (G6/G7) ----------

def test_validate_token_ok():
    ok, reason = validate_token(TOKEN)
    assert ok and reason == ""


def test_validate_token_empty_reason():
    ok, reason = validate_token("")
    assert not ok and "空" in reason


def test_validate_token_whitespace_reason():
    ok, reason = validate_token("abc def" + "x" * 14)
    assert not ok and "空白" in reason


def test_validate_token_short_reason():
    ok, reason = validate_token("short-token-12")
    assert not ok and "长度" in reason and "20" in reason


def test_validate_token_placeholder_reason():
    ok, reason = validate_token("your-token-here-please-replace-12345")
    assert not ok and "占位" in reason


def test_validate_token_never_leaks_value():
    for bad in ["", "short", "your-token-here-please-replace-12345", "a b" + "c" * 20]:
        _, reason = validate_token(bad)
        assert bad == "" or reason == "" or bad not in reason


# ---------- check_same_source (G3) ----------

def test_same_source_ok():
    ok, reason = check_same_source(TOKEN, TOKEN)
    assert ok and reason == ""


def test_same_source_mismatch_reason():
    ok, reason = check_same_source(TOKEN, OTHER)
    assert not ok and "同源" in reason and TOKEN not in reason and OTHER not in reason


# ---------- check_rendered (G2) ----------

def test_rendered_ok():
    ok, reasons = check_rendered(CFG_OK)
    assert ok and reasons == []


def test_rendered_missing_expand_env():
    cfg = json.loads(json.dumps(CFG_OK))
    cfg["services"]["prometheus"]["command"] = ["--config.file=/etc/prometheus/prometheus.yml"]
    ok, reasons = check_rendered(cfg)
    assert not ok and any("expand-env" in r for r in reasons)


def test_rendered_default_config_volume():
    cfg = json.loads(json.dumps(CFG_OK))
    cfg["services"]["prometheus"]["volumes"][0]["source"] = "./config/prometheus.yml"
    ok, reasons = check_rendered(cfg)
    assert not ok and any("prometheus.auth.yml" in r for r in reasons)


def test_rendered_prometheus_token_empty():
    cfg = json.loads(json.dumps(CFG_OK))
    cfg["services"]["prometheus"]["environment"]["METRICS_TOKEN"] = ""
    ok, reasons = check_rendered(cfg)
    assert not ok and any("同源" in r or "空" in r for r in reasons)


# ---------- CLI (G-0 / G6) ----------

def test_cli_empty_stdin_exit_2(capsys):
    assert main(["--preflight"], stdin="") == 2
    assert "护栏输入" in capsys.readouterr().out


def test_cli_bad_json_exit_2(capsys):
    assert main(["--preflight"], stdin="{not-json") == 2
    assert "护栏输入" in capsys.readouterr().out


def test_cli_placeholder_token_exit_1(capsys):
    cfg = json.loads(json.dumps(CFG_OK))
    cfg["services"]["web"]["environment"]["METRICS_TOKEN"] = "your-token-here-please-replace-12345"
    assert main(["--preflight"], stdin=json.dumps(cfg)) == 1
    out = capsys.readouterr().out
    assert "占位" in out


def test_cli_ok_exit_0(capsys):
    assert main(["--preflight"], stdin=json.dumps(CFG_OK)) == 0
    out = capsys.readouterr().out
    assert "PASS" in out
    assert TOKEN not in out
