#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""密钥指纹护栏（批次 5 / M-34 + M-11，SC-2 落地强化）

分工（DR-1 单源，两脚本不互相替代、不各写一套占位判定）:
  check_secret_tracking.py      → 跟踪面: git ls-files 的 .env 断言 + staged 新增行键模式;
                                  is_placeholder() 为占位判定唯一真源（G11）。
  check_secret_fingerprints.py  → 指纹面（本文件）:
                                  ① 引号形态疑似密钥——原 security-scan.yml PATTERNS 逐字
                                    移植（保持大小写敏感与无词边界语义），扫描类型集 = 原
                                    --type py/js/ts/json + M-11 扩 --type yaml；tests 夹具
                                    值按 SHA-256 白名单分流（方案 A：误报转可审计豁免，
                                    SC-2 不削弱——tests 内未登记高熵值仍判红）。
                                  ③ 已轮换凭据回流——全树 token SHA-256 指纹，取代原
                                    rg -F 明文黑名单：明文黑名单既违反 SC-1（workflow 自身
                                    携带凭据）又需要 -g '!.github/**' 自我豁免（排除面自残），
                                    指纹化后两者一并收口（B3 路线 (b) 拍板）。

指纹口径: sha256(value.encode("utf-8")) 十六进制，配置于 scripts/secret_fingerprints.json，
只存哈希不存明文（哈希不可逆，不构成 SC-1 违规）。
检测力边界: 哈希检测依赖分词正则命中完整凭据 token——凭据被拆行、插入标点或改大小写
会漏检，故第三道只取代原黑名单，不替代第一/二道正则（纵深防御，三道职责不混）。

文件源: git ls-files（根仓 + 两子仓，与 check_secret_tracking 同口径）。与原 rg 工作树
扫描的差异: ls-files 含 .github/** 等隐藏目录（rg 默认跳过隐藏目录），覆盖面只增不减;
不含未跟踪文件（CI 全新 checkout 下两者等价；本地未跟踪 .env 由跟踪面护栏负责）。

解码纪律（G-0 同型，B-31）: 文本读取复用 line_metrics.read_text（utf-8-sig 打头）;
读出空串且文件非空 → 解码失败 → 判红，禁止静默跳过。

退出码: 0 = 无命中; 1 = 有命中; 2 = 运行异常（git 失败/配置缺失或非法，fail-closed）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from check_secret_tracking import is_placeholder
from line_metrics import is_test, read_text

ROOT = Path(__file__).resolve().parent.parent
SUBMODULES = ("asset_management_backend", "vue-assetmanagement")
FINGERPRINTS_PATH = Path(__file__).resolve().parent / "secret_fingerprints.json"

# 第一道·kv 形态（自 security-scan.yml PATTERNS 逐字移植，大小写敏感、无词边界）:
# 命中值可按指纹白名单/占位判定分流（仅限 tests 路径）。
# AI_REVIEW_NEEDED: regex validation required
QUOTED_KV_PATTERNS = (
    ("password", r"password\s*[:=]\s*[\"'][^\"']{8,}"),
    ("secret", r"secret\s*[:=]\s*[\"'][^\"']{8,}"),
    ("token", r"token\s*[:=]\s*[\"'][^\"']{8,}"),
    ("api_key", r"api_key\s*[:=]\s*[\"'][^\"']{8,}"),
)
# 结构形态（AWS AKID / PEM 私钥头）：永不分流，命中即红。
QUOTED_STRUCTURAL_PATTERNS = (
    ("AKIA", r"AKIA[0-9A-Z]{16}"),
    ("PRIVATE_KEY", r"-----BEGIN.*PRIVATE KEY-----"),
)
# 原 rg 口径: --type py/js/ts/json + --type yaml（M-11 扩面）。rg 的 js/ts 含 jsx/tsx。
QUOTED_EXTENSIONS = frozenset(
    {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yaml", ".yml"}
)
# 第一道恢复旧 rg 的隐藏目录口径：.opencode/**（AI 工具链目录，含 vendored skill 脚本，
# 旧 rg 从未扫描）不进引号形态扫描；第三道指纹模式为精确哈希、无假阳，仍全树覆盖。
# 排除非静默：跳过数量在扫描结束时汇总打印（可审计）。
QUOTED_EXCLUDED_PREFIXES = (".opencode/",)

# 第三道·token 分词（指纹化检测力的载体，边界见模块 docstring）。
# AI_REVIEW_NEEDED: regex validation required
TOKEN_RE = re.compile(r"[A-Za-z0-9@#*_\-+/]{8,}")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _kv_value(match_text: str) -> str:
    """取 kv 命中串中最后一个引号之后的值段（PATTERNS 的值游程止于闭合引号/行尾）。"""
    idx = max(match_text.rfind('"'), match_text.rfind("'"))
    return match_text[idx + 1 :] if idx >= 0 else ""


def is_tests_path(path: Path) -> bool:
    """tests 路径判定：复用 line_metrics.is_test（后端 tests/、test_*.py、conftest），
    并扩展前端形态（__tests__/ 目录段、*.spec.ts 文件名）。"""
    if is_test(path):
        return True
    return any(part == "__tests__" for part in path.parts) or ".spec." in path.name.lower()


def tracked_files(repo: Path) -> list[Path]:
    """git ls-files（失败抛 RuntimeError → main 转 exit 2 fail-closed，
    不复用 check_secret_tracking._ls_files 的静默空串语义——指纹护栏不允许把
    git 故障当成空树放行）。

    -c core.quotePath=false: 非 ASCII 路径输出原始字符而非八进制转义（否则中文
    路径被误判为工作树缺失，对文档类文件形成 fail-open 盲区）。
    gitlink 条目（子模块指针，mode 160000，路径即子仓目录本身）不是文件，剔除。
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotePath=false", "ls-files"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files 失败（{repo}）: {result.stderr.strip()}")
    files = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        path = repo / line
        if path.is_dir():
            continue  # gitlink（子模块指针条目），子仓文件由 SUBMODULES 循环单独枚举
        files.append(path)
    return files


def _iter_repo_files(root: Path):
    for repo in (root, *(root / sub for sub in SUBMODULES)):
        if not repo.exists():
            continue  # 测试注入 tmp root 时子仓不存在；CI 三仓恒在场
        for path in tracked_files(repo):
            yield path


def _read_or_flag(path: Path, display: str) -> tuple[str, list[str]]:
    """读文件；解码失败按 G-0 同型判红（空串且非空文件），不静默跳过。

    例外（git 同款二进制启发式）：前 8KB 含 NUL 字节 → 二进制文件（图片/缓存 db 等，
    token 分词对二进制无检测力且必假阳），跳过并留痕；无 NUL 但解码失败 → 真·文本
    异常，维持 fail-closed 判红（B-31 同型）。
    """
    if not path.exists():
        print(f"[SKIP-missing] {display}: 已跟踪文件在工作树缺失（未提交的删除?）")
        return "", []
    text = read_text(path)
    if text == "" and path.stat().st_size > 0:
        head = path.open("rb").read(8192)
        if b"\x00" in head:
            print(f"[SKIP-binary] {display}: 二进制文件（NUL 探测），token 扫描跳过")
            return "", []
        return "", [f"{display}: 解码失败（utf-8-sig/utf-8/gbk 全失败）——fail-closed 判红（B-31 同型）"]
    return text, []


def scan_quoted_text(display: str, text: str, allow: set[str]) -> list[str]:
    """第一道核心（纯函数，供自测注入）：对单文件文本执行引号形态扫描。

    分流规则：tests 路径 + 值已登记（指纹在 allowlist）或值属占位（is_placeholder）
    → 放行并留痕；tests 路径 + 未登记高熵值 → 红；非 tests 路径 → 恒红（SC-2 不削弱）。
    """
    path = Path(display)
    tests_path = is_tests_path(path)
    violations: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name, pattern in QUOTED_KV_PATTERNS:
            for match in re.finditer(pattern, line):
                value = _kv_value(match.group(0))
                digest = _sha256(value)
                if tests_path and (digest in allow or is_placeholder(value)):
                    print(f"[ALLOWED] {display}:{lineno} 指纹={digest[:12]}（tests 夹具白名单/占位）")
                    continue
                violations.append(
                    f"{display}:{lineno}: 引号形态疑似密钥（{name}）指纹={digest[:12]}"
                )
        for name, pattern in QUOTED_STRUCTURAL_PATTERNS:
            if re.search(pattern, line):
                violations.append(f"{display}:{lineno}: 结构形态密钥（{name}）——永不分流")
    return violations


def scan_revoked_text(display: str, text: str, revoked: set[str]) -> list[str]:
    """第三道核心（纯函数）：token 指纹扫描，无注释豁免（已轮换凭据回流零容忍）。"""
    violations: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for token in TOKEN_RE.findall(line):
            digest = _sha256(token)
            if digest in revoked:
                violations.append(f"{display}:{lineno}: 已轮换凭据回流 指纹={digest[:12]}")
    return violations


def _scan_mode(root: Path, fingerprints: dict, mode: str) -> list[str]:
    allow = set(fingerprints.get("allowlist", []))
    revoked = set(fingerprints.get("revoked", []))
    if mode == "quoted" and not allow:
        raise RuntimeError("allowlist 为空——疑似配置缺失（fail-closed）")
    if mode == "revoked" and not revoked:
        raise RuntimeError("revoked 为空——疑似配置缺失（fail-closed）")
    violations: list[str] = []
    excluded = 0
    for path in _iter_repo_files(root):
        display = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()
        if mode == "quoted":
            if display.startswith(QUOTED_EXCLUDED_PREFIXES):
                excluded += 1
                continue
            if path.suffix.lower() not in QUOTED_EXTENSIONS:
                continue
            text, flagged = _read_or_flag(path, display)
            violations.extend(flagged)
            violations.extend(scan_quoted_text(display, text, allow))
        else:
            text, flagged = _read_or_flag(path, display)
            violations.extend(flagged)
            violations.extend(scan_revoked_text(display, text, revoked))
    if excluded:
        print(
            f"[SKIP-opencode] {excluded} 个 .opencode/** 文件按旧 rg 隐藏目录口径"
            "排除（仅第一道；第三道指纹模式仍覆盖）"
        )
    return violations


def _load_fingerprints(path: Path) -> dict:
    """配置加载（缺失/非法 → RuntimeError → exit 2 fail-closed）。"""
    if not path.exists():
        raise RuntimeError(f"指纹配置缺失: {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not all(
        isinstance(data.get(key), list) for key in ("revoked", "allowlist")
    ):
        raise RuntimeError(f"指纹配置结构非法（需含 revoked/allowlist 数组）: {path}")
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="密钥指纹护栏（引号形态 + 已轮换回流）")
    parser.add_argument("--quoted", action="store_true", help="仅跑第一道（引号形态 + 白名单分流）")
    parser.add_argument("--revoked", action="store_true", help="仅跑第三道（已轮换凭据指纹）")
    parser.add_argument("--fingerprints", type=Path, default=FINGERPRINTS_PATH)
    args = parser.parse_args(argv)
    modes = []
    if args.quoted:
        modes.append("quoted")
    if args.revoked:
        modes.append("revoked")
    if not modes:
        modes = ["quoted", "revoked"]

    try:
        fingerprints = _load_fingerprints(args.fingerprints)
        violations: list[str] = []
        for mode in modes:
            violations.extend(_scan_mode(ROOT, fingerprints, mode))
    except (RuntimeError, json.JSONDecodeError, OSError) as exc:
        print(f"[FAIL] 指纹护栏运行异常（fail-closed）: {exc}")
        return 2

    if violations:
        print("[FAIL] 密钥指纹护栏失败:")
        for item in violations:
            print(f"  - {item}")
        print("  修复: 测试夹具值请按 CONTRIBUTING 登记指纹白名单; 真凭据立即删除并轮换")
        return 1
    print(f"[PASS] 密钥指纹护栏通过（{', '.join(modes)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
