#!/usr/bin/env python3
# =============================================================================
# 部署前置自检: METRICS_TOKEN 合规 + 两栈同源 + 渲染核对 (批次 3/M-05, BF-190)
# =============================================================================
# 用法(生产部署清单 §4.3 步骤 3, 三文件合并渲染管线):
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
#     -f docker-compose.monitoring.yml config --format json \
#     | python ../scripts/verify_metrics_deploy.py --preflight
#
# 三道检查(全部通过 exit 0, 任一违规 exit 1, 输入面故障 exit 2):
#   1. validate_token   非空 / 无空白 / 长度 ≥20 / 非占位值(复用
#      check_secret_tracking.is_placeholder 唯一真源, G11); 诊断消息永不回显 token 原值(G7)
#   2. check_same_source 两栈(web / prometheus)渲染 METRICS_TOKEN 逐字一致(G3 同源)
#   3. check_rendered   渲染核对(G2 串联): prometheus command 含 --config.expand-env
#      + 首个 volume 源为 prometheus.auth.yml + 两栈 token 均非空
#
# G-0: stdin 为空 / 非 JSON → exit 2 (fail-closed, B-31 缺陷族——禁止静默跳过)。
# 注意: 管线输出含全量渲染值(含 Secrets), 禁止 tee / 重定向落盘。
# =============================================================================
import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_secret_tracking import is_placeholder

AUTH_SUFFIX = "prometheus.auth.yml"
_EXPAND_ENV = "--config.expand-env"
_PROM_TARGET = "/etc/prometheus/prometheus.yml"
WEB = "web"
PROM = "prometheus"


def _env_value(env, key: str) -> str:
    """compose config --format json 的 environment 兼容 dict / list 两形态。"""
    if isinstance(env, dict):
        return str(env.get(key, "") or "")
    for item in env or []:
        if isinstance(item, str) and item.startswith(key + "="):
            return item.split("=", 1)[1]
    return ""


def validate_token(value: str) -> tuple[bool, str]:
    """G6: 四类失败原因独立可辨; G7: 诊断消息不含 token 原值。"""
    if not value:
        return False, "METRICS_TOKEN 为空(部署期 fail-closed, 请在 .env 生成)"
    if any(ch.isspace() for ch in value):
        return False, "METRICS_TOKEN 含空白字符(取值段被截断, 请重新生成)"
    if len(value) < 20:
        return False, f"METRICS_TOKEN 长度 {len(value)} < 20(请用 token_urlsafe(32) 重新生成)"
    if is_placeholder(value):
        return False, "METRICS_TOKEN 为占位值(禁止 your-token-here/placeholder 等, 请生成正式 token)"
    return True, ""


def check_same_source(web_token: str, prom_token: str) -> tuple[bool, str]:
    """G3: 两栈渲染值逐字一致(同机同 .env 拓扑的运行时证据)。"""
    if web_token != prom_token:
        return False, "两栈 METRICS_TOKEN 渲染值不一致(同源断裂: web 与 prometheus 读到了不同值)"
    if not prom_token:
        return False, "两栈 METRICS_TOKEN 渲染值均为空(同源成立但 token 未配置)"
    return True, ""


def _prom(cfg: dict) -> dict:
    return (cfg.get("services") or {}).get(PROM) or {}


def check_rendered(cfg: dict) -> tuple[bool, list[str]]:
    """G2: 渲染核对(Bearer 链路三要件 + 两栈非空)。"""
    reasons: list[str] = []
    web_token = _env_value((cfg.get("services") or {}).get(WEB, {}).get("environment"), "METRICS_TOKEN")
    prom = _prom(cfg)
    prom_token = _env_value(prom.get("environment"), "METRICS_TOKEN")
    ok_same, reason = check_same_source(web_token, prom_token)
    if not ok_same:
        reasons.append(reason)
    if _EXPAND_ENV not in (prom.get("command") or []):
        reasons.append("prometheus command 缺少 --config.expand-env(bearer_token 的 ${} 不会展开, 链路断裂)")
    volumes = prom.get("volumes") or []
    first = volumes[0] if volumes else {}
    source = str(first.get("source", "") or "")
    if not source.endswith(AUTH_SUFFIX) or str(first.get("target", "")) != _PROM_TARGET:
        reasons.append(
            f"prometheus 首个 volume 未指向 {AUTH_SUFFIX}"
            "(.env 的 PROMETHEUS_CONFIG 未生效或未设, Bearer 抓取配置未启用)"
        )
    return (not reasons), reasons


def _preflight(text: str) -> tuple[int, str]:
    """返回 (exit_code, 输出文本); 全输出不含 token 原值(G7)。"""
    if not text.strip():
        return 2, "[FAIL] 护栏输入为空(compose config --format json 管线未送入渲染结果, G-0 fail-closed)\n"
    try:
        cfg = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return 2, f"[FAIL] 护栏输入非合法 JSON: {exc} (G-0 fail-closed)\n"
    if not isinstance(cfg, dict) or not isinstance(cfg.get("services"), dict):
        return 2, "[FAIL] 护栏输入缺少 services 结构(非 compose config 输出, G-0 fail-closed)\n"
    web_token = _env_value((cfg["services"].get(WEB) or {}).get("environment"), "METRICS_TOKEN")
    lines: list[str] = []
    ok_token, token_reason = validate_token(web_token)
    lines.append(f"  token 合规: {'PASS' if ok_token else 'FAIL' + ' — ' + token_reason}")
    ok_chain, chain_reasons = check_rendered(cfg)
    for r in chain_reasons:
        lines.append(f"  渲染核对: FAIL — {r}")
    if ok_chain:
        lines.append("  渲染核对: PASS (expand-env / auth volume / 两栈同源)")
    bad = [ln for ln in lines if "FAIL" in ln]
    header = (
        f"[FAIL] 部署前置自检 {len(bad)} 项违规(禁止启动生产栈):\n"
        if bad
        else "[PASS] 部署前置自检通过(token 合规 + 两栈同源 + Bearer 渲染链路完整)\n"
    )
    return (1 if bad else 0), header + "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, stdin: str | None = None) -> int:
    parser = argparse.ArgumentParser(description="M-05 部署前置自检(--preflight)")
    parser.add_argument("--preflight", action="store_true", help="从 stdin 读 compose 渲染 JSON")
    args = parser.parse_args(argv)
    if not args.preflight:
        print("用法: <compose config --format json> | verify_metrics_deploy.py --preflight")
        return 2
    code, out = _preflight(stdin if stdin is not None else sys.stdin.read())
    print(out, end="")
    return code


def _self_smoke(host: str, port: int, token: str, timeout: float) -> tuple[bool, str]:
    """容器内网 401/200 双态冒烟(§4.3 步骤 5 内嵌脚本的宿主侧同源实现, 仅供本地演练)。"""
    import http.client

    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", "/metrics/", headers={"Authorization": f"Bearer {token}"})
        resp = conn.getresponse()
        resp.read()
        return resp.status in (200, 401), f"status={resp.status}"
    finally:
        conn.close()


def render_configs(backend_dir: Path) -> str:
    """三文件合并渲染(宿主侧演练入口; 生产清单 §4.3 步骤 3 用 bash 管线, 本函数不用于生产)。"""
    files = [
        "docker-compose.yml",
        "docker-compose.prod.yml",
        "docker-compose.monitoring.yml",
    ]
    cmd = ["docker", "compose"]
    for f in files:
        cmd += ["-f", str(backend_dir / f)]
    cmd += ["config", "--format", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"compose config 失败(exit {result.returncode}): {result.stderr.strip()}")
    return result.stdout


if __name__ == "__main__":
    sys.exit(main())
