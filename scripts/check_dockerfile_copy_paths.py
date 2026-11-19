# -*- coding: utf-8 -*-
"""Dockerfile COPY 路径护栏（BF-166，D1）：compose context × Dockerfile 静态解析。

背景：nginx/certbot/blackbox 三个 Dockerfile 的 COPY 源相对 compose build
context（仓根）解析——CI 只构建 Django 主镜像，该失配从未被门禁抓获
（静态解析 8/9 MISSING）。本护栏把逐条解析固化，防回潮。

断言面（违反任一即红）：
  1. docker-compose*.yml 可被 YAML 解析且含 services
  2. build.context + build.dockerfile 指向的文件存在
  3. Dockerfile 内 COPY/ADD 源相对 context 解析后存在（跳过 --from= 多阶段
     引用与 http(s):// 远端源；通配符按 glob 判定）

用法：
    python scripts/check_dockerfile_copy_paths.py [--root <repo>]
"""
from __future__ import annotations

import argparse
import glob as globmod
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - 后端 venv 必有 PyYAML
    print("[FAIL] 需要 PyYAML（pip install pyyaml）")
    sys.exit(1)

COPY_RE = re.compile(r"^\s*(?:COPY|ADD)\s+(.+)$")
BACKEND_COMPOSE = Path("asset_management_backend") / "docker-compose.yml"
MONITORING_COMPOSE = Path("asset_management_backend") / "docker-compose.monitoring.yml"


def _copy_sources(dockerfile: Path) -> list[tuple[int, str]]:
    sources = []
    for index, line in enumerate(dockerfile.read_text(encoding="utf-8").splitlines(), 1):
        match = COPY_RE.match(line)
        if not match or "--from=" in match.group(1):
            continue
        src = match.group(1).split()[0].strip('"')
        if src.startswith(("http://", "https://")):
            continue
        sources.append((index, src))
    return sources


def audit(root: Path) -> list[str]:
    problems: list[str] = []
    for compose_relative in (BACKEND_COMPOSE, MONITORING_COMPOSE):
        compose_path = root / compose_relative
        if not compose_path.exists():
            problems.append(f"{compose_relative.as_posix()}: 文件不存在")
            continue
        doc = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        services = doc.get("services", {}) if isinstance(doc, dict) else {}
        for name, service in services.items():
            build = (service or {}).get("build")
            if not build:
                continue
            if isinstance(build, str):
                context, dockerfile = build, "Dockerfile"
            else:
                context = build.get("context", ".")
                dockerfile = build.get("dockerfile", "Dockerfile")
            resolved_ctx = (compose_path.parent / context) if not os.path.isabs(context) else Path(context)
            df_path = resolved_ctx / dockerfile
            if not df_path.exists():
                problems.append(
                    f"{compose_relative.as_posix()}[{name}]: Dockerfile 不存在 {df_path.as_posix()}"
                )
                continue
            for index, src in _copy_sources(df_path):
                # 通配符按 glob 判定；其余按 context 相对路径判定
                pattern = str(resolved_ctx / src) if "*" in src else str(resolved_ctx / src)
                ok = bool(globmod.glob(pattern)) if "*" in src else os.path.exists(pattern)
                if not ok:
                    problems.append(
                        f"{compose_relative.as_posix()}[{name}] {df_path.name}:{index}: "
                        f"COPY 源 `{src}` 相对 context `{context}` 不存在（BF-166 同型失配）"
                    )
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Dockerfile COPY 路径护栏：compose context × Dockerfile 逐条静态解析（BF-166）"
    )
    parser.add_argument("--root", default=None, help="仓库根目录（默认按 __file__ 推导）")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent

    problems = audit(root)
    if problems:
        print("[FAIL] Dockerfile COPY 路径护栏未通过：")
        for item in problems:
            print("   - " + item)
        return 1
    print("[PASS] Dockerfile COPY 路径护栏全绿：compose build.context × COPY/ADD 源逐条解析通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
