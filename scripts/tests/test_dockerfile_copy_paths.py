# -*- coding: utf-8 -*-
"""Dockerfile COPY 路径护栏自测（BF-166，D1）：先证红，再证绿。"""
from pathlib import Path

import check_dockerfile_copy_paths as guard

COMPOSE_GREEN = """services:
  web:
    build: .
  nginx:
    build:
      context: ..
      dockerfile: asset_management_backend/docker/ok/Dockerfile
"""

COMPOSE_GREEN_FILES = {
    "Dockerfile": "FROM python:3.12-slim\n",
    "docker/ok/Dockerfile": "FROM busybox:1.36\nCOPY asset_management_backend/docker/ok/nginx.conf /etc/nginx.conf\n",
    "docker/ok/nginx.conf": "",
}

COMPOSE_RED = """services:
  nginx:
    build:
      context: ..
      dockerfile: asset_management_backend/docker/ok/Dockerfile
"""

COMPOSE_RED_DOCKERFILE = "FROM busybox:1.36\nCOPY docker/ok/missing.conf /etc/nginx.conf\n"


def _materialize(tmp_path: Path, compose_text: str, files: dict[str, str]) -> Path:
    backend = tmp_path / "asset_management_backend"
    backend.mkdir(parents=True)
    for relative, content in files.items():
        p = backend / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    (backend / "docker-compose.yml").write_text(compose_text, encoding="utf-8")
    # 护栏同时审计 monitoring compose；纯蓝本用例给空 services stub
    if not (backend / "docker-compose.monitoring.yml").exists():
        (backend / "docker-compose.monitoring.yml").write_text("services: {}\n", encoding="utf-8")
    return tmp_path


def test_copy_sources_resolved_green(tmp_path):
    root = _materialize(tmp_path, COMPOSE_GREEN, COMPOSE_GREEN_FILES)
    assert guard.audit(root) == []


def test_copy_source_missing_red(tmp_path):
    root = _materialize(tmp_path, COMPOSE_RED, {"docker/ok/Dockerfile": COMPOSE_RED_DOCKERFILE})
    problems = guard.audit(root)
    assert any("missing.conf" in p for p in problems)


def test_dockerfile_absent_red(tmp_path):
    root = _materialize(tmp_path, COMPOSE_RED, {})
    problems = guard.audit(root)
    assert any("Dockerfile 不存在" in p for p in problems)


def test_multistage_from_skipped(tmp_path):
    files = {
        "Dockerfile": "FROM python\n",
        "docker/ok/Dockerfile": (
            "FROM node AS build\nCOPY asset_management_backend/docker/ok/pkg.json /app\n"
            "COPY --from=build /app/dist /dist\n"
        ),
        "docker/ok/pkg.json": "{}",
    }
    root = _materialize(tmp_path, COMPOSE_GREEN, files)
    assert guard.audit(root) == []


def test_real_repo_green():
    root = Path(guard.__file__).resolve().parent.parent
    assert guard.audit(root) == []
