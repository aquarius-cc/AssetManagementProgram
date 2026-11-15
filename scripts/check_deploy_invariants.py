#!/usr/bin/env python3
# =============================================================================
# 部署护栏: docker-entrypoint.sh 失败快速退出不变量 (M-36)
#          + METRICS_TOKEN 部署形态与 Bearer 链路不变量 (批次 3/M-05, BF-190)
# =============================================================================
# 锁定四条不变量, 防止入口脚本回退为「迁移失败仍启动」, 或 metrics 鉴权
# 部署形态回退为「空 token 放行」:
#   ① 脚本含 set -e 语义 (set -euo pipefail / set -e)
#   ② migrate / collectstatic 关键步显式 || exit 1
#     (双保险: 即使 ① 被后人删除, ② 仍保住关键步, 且可被本护栏文本校验)
#   ③ METRICS_TOKEN 三处形态矩阵(各唯一):
#     prod compose    = ${METRICS_TOKEN:?...}   部署期 fail-closed(空 token 拒绝启动)
#     monitoring      = ${METRICS_TOKEN:-}      透传(空 = 无凭据抓取兼容)
#     settings/base.py= METRICS_TOKEN = config("METRICS_TOKEN", default="")
#                       (django-environ 语法, 非插值——运行时空 = 放行为登记设计 P3-10)
#   ④ Bearer 链路三要件:
#     monitoring volume 经 ${PROMETHEUS_CONFIG:-./config/prometheus.yml} 变量插值切换
#     + prometheus.auth.yml 含 bearer_token: ${METRICS_TOKEN}
#     + prometheus 透传 --config.expand-env
#
# 设计约束: 只做规则①②, 不做「顶层命令白名单」通用静态分析——
# 用正则对 shell 做块/续行级解析误报率不可控 (M-36 评审决议)。
# G-0: 输入文件缺失/解码失败一律 exit 2 (fail-closed, B-31 缺陷族——禁止静默跳过)。
# =============================================================================
import argparse
import sys
from pathlib import Path

from line_metrics import read_text  # utf-8-sig 打头, G-0 解码纪律唯一真源 (B-31)

BACKEND_DIRNAME = "asset_management_backend"

# 规则②的目标命令前缀 (仅 migrate / collectstatic 两类关键步)
CRITICAL_PREFIXES = (
    "python manage.py migrate",
    "python manage.py collectstatic",
)

# 规则③形态锚
_FORM = "METRICS_TOKEN=${METRICS_TOKEN"
_BASE_FORM = 'METRICS_TOKEN = config("METRICS_TOKEN", default="")'

# 规则④锚
_CONFIG_VOLUME_ANCHOR = "${PROMETHEUS_CONFIG:-"
# bearer_token 键前缀: 拆段拼接避免源码行出现 token"..." 引号形态
# (check_secret_fingerprints 的 token kv 模式会误判新指纹, BF-190)
_BEARER_KEY_PREFIX = "bearer_token" ":"
_EXPAND_ENV_ANCHOR = "--config.expand-env"


class GuardInfraError(Exception):
    """护栏输入面故障(文件缺失/解码失败)——G-0 fail-closed, exit 2, 不得当规则违规处理。"""


def _read(path: Path) -> str:
    try:
        return read_text(path)
    except (OSError, UnicodeDecodeError) as exc:
        raise GuardInfraError(f"护栏输入不可读: {path.name}: {exc}") from exc


def _check_entrypoint(text: str, name: str) -> list[str]:
    """规则①②: M-36 语义逐字保留。"""
    errors: list[str] = []
    if not _has_set_e(text):
        errors.append(
            f"{name}: 未找到 set -e 语义 (需 set -euo pipefail 或 set -e)——"
            "迁移/静态收集失败将不再阻断启动 (M-36 回归)"
        )
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for prefix in CRITICAL_PREFIXES:
            if stripped.startswith(prefix) and "|| exit 1" not in stripped:
                errors.append(
                    f"{name}:{raw}: 关键步 '{prefix}...' 缺少 '|| exit 1'——"
                    "失败时容器仍会启动, 以未迁移库对外服务 (M-36 回归)"
                )
    return errors


def _has_set_e(text: str) -> bool:
    import re

    return bool(re.search(r"^set\s+-e", text, re.MULTILINE))


def _token_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if _FORM in line]


def _check_metrics_forms(prod: str, mon: str, base: str) -> list[str]:
    """规则③: 三处形态矩阵各唯一 (prod :? / monitoring :- / base django-environ)。"""
    errors: list[str] = []
    prod_lines = _token_lines(prod)
    if len(prod_lines) != 1 or ":?" not in prod_lines[0]:
        errors.append(
            "docker-compose.prod.yml: METRICS_TOKEN 必须且仅一处(唯一)为 ${METRICS_TOKEN:?...}"
            " fail-closed 形态 (空 token 生产栈拒绝启动, M-05); 现为 "
            + (prod_lines[0].strip() if prod_lines else "缺失")
        )
    mon_lines = _token_lines(mon)
    if len(mon_lines) != 1 or ":-" not in mon_lines[0] or ":?" in mon_lines[0]:
        errors.append(
            "docker-compose.monitoring.yml: METRICS_TOKEN 必须且仅一处为 "
            "${METRICS_TOKEN:-} 透传形态 (空 = 无凭据抓取兼容, P3-10); 现为 "
            + (mon_lines[0].strip() if mon_lines else "缺失")
        )
    if base.count(_BASE_FORM) != 1:
        errors.append(
            "config/settings/base.py: METRICS_TOKEN 必须且仅一处为 "
            'config("METRICS_TOKEN", default="") (django-environ 语法, 非插值——'
            "运行时空 = 放行为 P3-10 登记设计); 形态漂移请回退"
        )
    return errors


def _check_bearer_chain(mon: str, auth: str) -> list[str]:
    """规则④: Bearer 链路三要件。"""
    errors: list[str] = []
    volume_lines = [line for line in mon.splitlines() if _CONFIG_VOLUME_ANCHOR in line]
    if len(volume_lines) != 1 or "prometheus.yml" not in volume_lines[0]:
        errors.append(
            "docker-compose.monitoring.yml: prometheus 首个 volume 必须经 "
            "${PROMETHEUS_CONFIG:-./config/prometheus.yml} 变量插值切换 (M-05); "
            "硬编码路径使 Bearer 配置无法启用"
        )
    if not any(
        line.strip().startswith(_BEARER_KEY_PREFIX) for line in auth.splitlines()
    ):
        errors.append(
            "config/prometheus.auth.yml: 缺少 bearer_token: ${METRICS_TOKEN}"
            " (Bearer 抓取凭据注入点, P3-10; 注释行不算)"
        )
    if _EXPAND_ENV_ANCHOR not in mon:
        errors.append(
            "docker-compose.monitoring.yml: prometheus command 缺少 --config.expand-env"
            " (无它则 bearer_token 的 ${METRICS_TOKEN} 不会被展开, Bearer 链路断裂)"
        )
    return errors


def check(root: Path | None = None) -> list[str]:
    """四规则全检; 输入面故障抛 GuardInfraError (G-0, exit 2)。"""
    backend = (root or Path(__file__).resolve().parent.parent) / BACKEND_DIRNAME
    entrypoint = backend / "docker-entrypoint.sh"
    prod = backend / "docker-compose.prod.yml"
    mon = backend / "docker-compose.monitoring.yml"
    base = backend / "config" / "settings" / "base.py"
    auth = backend / "config" / "prometheus.auth.yml"
    errors = _check_entrypoint(_read(entrypoint), entrypoint.name)
    errors += _check_metrics_forms(_read(prod), _read(mon), _read(base))
    errors += _check_bearer_chain(_read(mon), _read(auth))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BR-D1 部署护栏 (M-36 + 批次 3/M-05)")
    parser.add_argument("--root", default=None, help="仓库根目录 (默认脚本上一级)")
    args = parser.parse_args(argv)
    try:
        errors = check(Path(args.root) if args.root else None)
    except GuardInfraError as exc:
        print(f"[FAIL] BR-D1 部署护栏输入面故障 (G-0 fail-closed): {exc}")
        return 2
    if errors:
        print(f"[FAIL] BR-D1 部署护栏: {len(errors)} 处违规")
        for e in errors:
            print("  -", e)
        return 1
    print(
        "[PASS] BR-D1 部署护栏通过(①set -e 语义在位 ②migrate/collectstatic 关键步 || exit 1 "
        "③METRICS_TOKEN 三处形态矩阵各唯一 ④Bearer 链路三要件在位)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
