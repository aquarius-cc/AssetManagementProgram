#!/usr/bin/env python3
"""
密钥跟踪护栏 (OP-20, 批次 11)

.env 凭据文件跟踪双轨拦截(本地钩子 + CI security-scan 断言步同口径):
1. 已跟踪 .env 检测: 根仓与两子仓(asset_management_backend / vue-assetmanagement)
   的 `git ls-files` 中, 文件名恰为 `.env` 的文件必须零命中(.env.example 等
   模板不受此限)。
2. staged 内容扫描: 根仓 `git diff --cached` 新增行扫描
   DB_PASSWORD / REDIS_PASSWORD / SECRET_KEY / METRICS_TOKEN 键模式;
   占位值放行(空值 / ${...} 插值 / change* / your* / example / xxx / <...>)。

口径说明: 子仓无独立钩子(钩子链仅根仓 .githooks/pre-commit), 子仓提交的
本地拦截由 CI 断言步兜底(git ls-files 跨仓取证, .gitignore 不构成不跟踪证据)。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUBMODULES = ("asset_management_backend", "vue-assetmanagement")

# 键模式(大小写不敏感): 键名 + 赋值 + 值 ≥8 字符(短值不构成凭据强度, 不误报)
_SECRET_KEY_RE = re.compile(
    r"(?i)\b(DB_PASSWORD|REDIS_PASSWORD|SECRET_KEY|METRICS_TOKEN)\s*[=:]\s*['\"]?([^\s'\"]{8,})"
)

# 占位值放行: 典型占位词 / 环境变量插值 / 掩码 / 尖括号占位(前缀匹配, 长占位值亦放行)
_PLACEHOLDER_RE = re.compile(
    r"(?i)^(changeme.*|change[-_]?me.*|change[-_]?this.*|your[-_].*|example.*|placeholder.*|"
    r"please[-_ ]?replace.*|xxx.*|\*{3,}.*|<.*>|\$\{.*|none.*|null.*|todo.*)$"
)


def _ls_files(repo: Path) -> str:
    """git ls-files 输出(失败返回空, 由调用方按空处理)"""
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def find_tracked_env() -> list[str]:
    """检测 1: 各仓已跟踪的 .env 文件(零容忍)"""
    violations: list[str] = []
    repos = [ROOT, *(ROOT / sub for sub in SUBMODULES)]
    for repo in repos:
        for line in _ls_files(repo).splitlines():
            if line.rsplit("/", 1)[-1] == ".env":
                violations.append(f"{repo.name}: {line}")
    return violations


def scan_staged(diff_text: str) -> list[str]:
    """检测 2: staged 新增行键模式扫描(占位值放行)"""
    violations: list[str] = []
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for match in _SECRET_KEY_RE.finditer(line):
            value = match.group(2).strip("\"'")
            if _PLACEHOLDER_RE.match(value):
                continue
            violations.append(line.strip())
    return violations


def main() -> int:
    violations = find_tracked_env()

    staged = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    ).stdout
    violations.extend(f"[staged] {v}" for v in scan_staged(staged))

    if violations:
        print("[FAIL] 密钥跟踪护栏失败:")
        for item in violations:
            print(f"  - {item}")
        print("  修复: 对 .env 文件执行 git rm --cached; 真实值改占位符或 ${ENV} 插值")
        return 1
    print("[PASS] 密钥跟踪护栏通过(0 已跟踪 .env / 0 staged 真实值)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
