# -*- coding: utf-8 -*-
"""API 文档一致性护栏 (API Doc Consistency Guard)

文档中的端点、参数、字段都是 OpenAPI schema 的人工副本。凡是人工副本,就会随实现
改动而失真——本护栏把「文档不得偏离 schema」变成可执行断言,阻止副本再次分叉。

权威事实来源: asset_management_backend/api-schema-baseline.json (drf-spectacular 生成)
受检文档:
  - asset_management_backend/docs/API详细文档0608.md  (详细文档)
  - asset_management_backend/docs/API.md                (索引导文档)

断言 (BLOCKING):
  V-1  文档中不得出现非 /api/v1/ 的 /api/ 路径串 (契约完整性)
  V-2  文档中每个 /api/v1/ 路径必须能在基线 paths 中找到 (含路径参数名逐字一致;
       仅归一后相同者视为参数名漂移,报红并给出基线真值)
  V-3  不得重新引入「方法|URL|描述|权限」形态的端点清单表 (V-2 的镜像副本,已退役)
  V-4  「请求参数与请求体」章节的表格不得携带 类型/必填/约束/默认值 列 (与基线重复的漂移面)

统计: 所有计数均由本脚本运行时枚举得出并打印,脚本与文档均不维护任何魔法数字。

退出码: 0 = 全部通过 / 1 = 有阻断项失败
用法:   python scripts/check_api_doc_consistency.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "asset_management_backend"
BASELINE = BACKEND / "api-schema-baseline.json"
DOCS = [
    BACKEND / "docs" / "API详细文档0608.md",
    BACKEND / "docs" / "API.md",
]

# /api/ 路径串。是否合法 v1 由 is_v1_path() 显式判定,不用正则前瞻:
# 前瞻覆盖不了「补 /api/v1 前缀」这类行文(v1 之后既无斜杠也无行尾锚点)。
RAW_API_PATH_RE = re.compile(r"/api/[A-Za-z0-9_./{}-]*")


def is_v1_path(path: str) -> bool:
    return path == "/api/v1" or path.startswith("/api/v1/")
# 端点标题两种形态: 单方法式与 "PUT/PATCH" 双方法式。双方法式若不被识别即产生覆盖漏洞,
# 因为这类标题在基线中同时承载两个 operation。
HEADING_METHODS = r"(?:GET|POST|PUT|PATCH|DELETE)"
HEADING_RE = re.compile(rf"^####\s+({HEADING_METHODS}(?:/{HEADING_METHODS})*)\s+(/\S+)")
TABLE_SEP_RE = re.compile(r"^\|\s*:?-{2,}")
SECTION_RE = re.compile(r"^##\s+(.+?)\s*$")
PARAM_RE = re.compile(r"\{[^}]+\}")

# 允许但不属 schema operation 的路径: schema 自身出口 + 模块挂载前缀 (用于文档说明路由结构)
# 允许但不属 schema operation 的路径: schema 自身出口 + 挂载点根。
# 挂载点根同时收录 /api/v1 与 /api/v1/：中文行文里「补 /api/v1 前缀」不带尾斜杠是常态,
# 那是引用挂载点而非可调用端点,不应报红。
NON_OPERATION_PATHS = {
    "/api/v1",
    "/api/v1/",
    "/api/v1/swagger/",
    "/api/v1/redoc/",
    "/api/v1/schema/",
}
# 已在实现中退役、但文档仍需指明迁移去向的路径。显式登记,避免「未登记的消失端点」蒙混过关。
RETIRED_PATHS = {"/api/v1/auth/token/": "改用 /api/v1/auth/login/"}
# 模块挂载前缀（如 /api/v1/assets/）的段名由基线派生,不写死、不用宽松正则。
# 曾用 `^/api/v1/[a-z-]+/$` 兜底,那会让任何形如 /api/v1/<小写段>/ 的路径被豁免,
# 写错的端点（/api/v1/ghost/）会静默通过——豁免范围比真实模块大即是漏洞。
MODULE_PREFIX_RE = re.compile(r"^/api/v1/([^/]+)/$")


def module_segments(baseline: set[str]) -> set[str]:
    """从基线派生模块挂载段名（auth / users / assets ...）。

    只收录基线中真实作为目录前缀出现的段,新增模块自动跟随,伪造段名则不在其中。
    """
    segments = set()
    for path in baseline:
        if not path.startswith("/api/v1/"):
            continue
        rest = path[len("/api/v1/") :]
        head, sep, _ = rest.partition("/")
        if head and sep:
            segments.add(head)
    return segments


def is_module_prefix(path: str, segments: set[str]) -> bool:
    """以模块挂载点结尾的路径: 文档中用于说明路由结构,不是可调用端点。"""
    m = MODULE_PREFIX_RE.match(path)
    return bool(m) and m.group(1) in segments

BLOCKING: list[str] = []
REPORT: dict[str, object] = {}


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def load_baseline_paths() -> set[str]:
    return set(json.loads(BASELINE.read_text(encoding="utf-8"))["paths"])


def normalize(path: str) -> str:
    """把路径参数名归一为 {}, 用于识别「仅参数名不同」的漂移。"""
    return PARAM_RE.sub("{}", path)


def is_retired_heading(line: str) -> bool:
    """`#### ~~/path~~` 形式的退役标记：路径被删除线包围且带退役字样。"""
    return "~~" in line and "退役" in line


def scan_headings(lines: list[str], rel: str) -> tuple[list[dict], int]:
    """枚举端点标题,含单方法式与双方法式。返回 (标题列表, 无方法标记的标题数)。"""
    found = []
    unlabeled = 0
    for lineno, line in enumerate(lines, start=1):
        if not line.startswith("####"):
            continue
        m = HEADING_RE.match(line)
        if m:
            methods = m.group(1).split("/")
            found.append({"line": lineno, "methods": methods, "path": m.group(2)})
        elif re.search(r"/\S+", line) and not is_retired_heading(line):
            # 退役标记（#### ~~/api/v1/auth/token/~~ — 已退役）本就故意不带方法,
            # 它描述的是「此路径已消失」而非可调用端点,不能按无方法端点报红。
            unlabeled += 1
            BLOCKING.append(
                f"V-2 {rel}:{lineno} 端点标题未被识别(方法式不在 {HEADING_METHODS} 组合内): {line.strip()[:70]}"
            )
    return found, unlabeled


def is_placeholder(path: str) -> bool:
    """`...` 不是合法路径字符，含它的匹配是行文占位（如「旧前缀为 /api/...」）而非端点。"""
    return "..." in path


def scan_paths(lines: list[str], rel: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """提取 /api/ 路径串。返回 (非 v1 者供 V-1, 全部 v1 者供 V-2)。

    单次扫描 + is_v1_path() 分类：若再用两条正则分别匹配,同一行文本可能被重复计数,
    且 v1 判定逻辑分散在两处,容易一边漏判一边误判。
    """
    legacy, current = [], []
    for lineno, line in enumerate(lines, start=1):
        for m in RAW_API_PATH_RE.finditer(line):
            path = m.group(0)
            if is_placeholder(path):
                continue
            (current if is_v1_path(path) else legacy).append((lineno, path))
    return legacy, current


def check_v1_prefix(rel: str, occurrences: list[tuple[int, str]]) -> int:
    """V-1: 非 /api/v1/ 的路径串报红。返回违规数。"""
    hits = 0
    for lineno, path in occurrences:
        hits += 1
        BLOCKING.append(f"V-1 {rel}:{lineno} 路径缺少 v1 版本前缀(当前全部端点位于 /api/v1/): {path}")
    return hits


def check_v2_resolves(rel: str, occurrences: list[tuple[int, str]], baseline: set[str]) -> tuple[int, int, int]:
    """V-2: 路径须逐字命中基线; 仅归一后相同者按参数名漂移报红。返回 (命中, 豁免, 已登记退役)。"""
    exact = 0
    exempt = 0
    retired = 0
    segments = module_segments(baseline)
    by_shape: dict[str, list[str]] = {}
    for p in baseline:
        by_shape.setdefault(normalize(p), []).append(p)
    for lineno, path in occurrences:
        if path in RETIRED_PATHS:
            retired += 1
            continue
        if path in NON_OPERATION_PATHS or is_module_prefix(path, segments):
            exempt += 1
            continue
        if path in baseline:
            exact += 1
            continue
        candidates = by_shape.get(normalize(path), [])
        if candidates:
            BLOCKING.append(
                f"V-2 {rel}:{lineno} 路径参数名与基线不一致: 文档 {path} -> 基线 {sorted(candidates)[0]}"
            )
        else:
            BLOCKING.append(f"V-2 {rel}:{lineno} 路径在基线中不存在(端点可能已删除或改名): {path}")
    return exact, exempt, retired


def iter_tables(lines: list[str]) -> list[dict]:
    """枚举所有 Markdown 表格,返回 表头列名 + 起始行号 + 所在章节标题 + 表体行。"""
    section = ""
    tables = []
    i = 0
    while i < len(lines):
        m = SECTION_RE.match(lines[i])
        if m:
            section = m.group(1)
        if TABLE_SEP_RE.match(lines[i].strip()) and i >= 1:
            header = lines[i - 1].strip()
            if header.startswith("|"):
                columns = [c.strip() for c in header.strip("|").split("|")]
                body = []
                j = i + 1
                while j < len(lines) and lines[j].strip().startswith("|"):
                    body.append(lines[j])
                    j += 1
                tables.append(
                    {
                        "line": i + 1,
                        "columns": columns,
                        "section": section,
                        "body": body,
                    }
                )
                i = j
                continue
        i += 1
    return tables


def check_v3_no_inventory(tables: list[dict], rel: str) -> int:
    """V-3: 禁止「枚举 schema 端点」的清单表回归。

    判据是内容而非列名: 只拦「方法|URL…」形态**且表体含 /api/ 路径**的表格。
    这样 API.md 的运维端点表(Django 直挂、不在 schema、表体无 /api/ 路径)不受影响,
    而 0608 中已退役的 §4 端点清单(逐条罗列 /api/ 路径)会被拦下。
    """
    hits = 0
    for t in tables:
        if t["columns"][:2] != ["方法", "URL"]:
            continue
        # 用全路径提取器判定表体是否罗列端点。只查非 v1 路径会让「已补 v1 前缀的
        # 端点清单」整个溜过 V-3,而那正是本文档的现状,漏检等于规则失效。
        if not any(RAW_API_PATH_RE.search(row) for row in t["body"]):
            continue
        hits += 1
        BLOCKING.append(
            f"V-3 {rel}:{t['line']} 端点清单表(方法|URL 且罗列 /api/ 路径)已退役,"
            "端点清单请以基线为准"
        )
    return hits


def check_v4_no_schema_columns(tables: list[dict], rel: str) -> tuple[int, int]:
    """V-4: 请求参数表不得携带与基线重复的列。返回 (违规表数, 已收敛表数)。"""
    bad_cols = {"类型", "必填", "约束", "默认值"}
    violations = 0
    slimmed = 0
    for t in tables:
        if "请求参数" not in t["section"]:
            continue
        overlap = bad_cols & set(t["columns"])
        if overlap:
            violations += 1
            BLOCKING.append(
                f"V-4 {rel}:{t['line']} 请求参数表仍携带 {'/'.join(sorted(overlap))} 列"
                "(与基线重复,属漂移面,请收敛为 字段|说明)"
            )
        else:
            slimmed += 1
    return violations, slimmed


def check_document(lines: list[str], rel: str, baseline: set[str]) -> dict:
    """对单份文档跑 V-1~V-4,返回统计并把违规写入 BLOCKING。

    抽出独立函数是为了让 ``--self-test`` 能用内存样本驱动同一套规则——
    守卫最大的风险不是误报,而是「永远绿」而无人察觉。
    """
    headings, unlabeled = scan_headings(lines, rel)
    legacy, current = scan_paths(lines, rel)
    v1_hits = check_v1_prefix(rel, legacy)
    exact, exempt, retired = check_v2_resolves(rel, current, baseline)
    tables = iter_tables(lines)
    inventory = check_v3_no_inventory(tables, rel)
    violations, slimmed = check_v4_no_schema_columns(tables, rel)
    single = sum(1 for h in headings if len(h["methods"]) == 1)
    return {
        "headings": len(headings),
        "single": single,
        "dual": len(headings) - single,
        "ops": sum(len(h["methods"]) for h in headings),
        "occurrences": len(current) + len(legacy),
        "legacy": len(legacy),
        "distinct": len({p for _, p in current} | {p for _, p in legacy}),
        "exact": exact,
        "exempt": exempt,
        "retired": retired,
        "v1_hits": v1_hits,
        "unlabeled": unlabeled,
        "tables": len(tables),
        "inventory": inventory,
        "violations": violations,
        "slim": slimmed,
    }


def summarize(per_doc: dict) -> None:
    REPORT.update(
        {
            "文档数": len(DOCS),
            "端点标题总数": sum(d["headings"] for d in per_doc.values()),
            "其中单方法式": sum(d["single"] for d in per_doc.values()),
            "其中双方法式": sum(d["dual"] for d in per_doc.values()),
            "标题覆盖 operation 数": sum(d["ops"] for d in per_doc.values()),
            "/api/ 路径串出现总次数": sum(d["occurrences"] for d in per_doc.values()),
            "其中缺 v1 前缀(V-1 违规)": sum(d["legacy"] for d in per_doc.values()),
            "/api/ 路径串去重数": sum(d["distinct"] for d in per_doc.values()),
            "命中基线(逐字)": sum(d["exact"] for d in per_doc.values()),
            "豁免(出口/模块前缀)": sum(d["exempt"] for d in per_doc.values()),
            "已登记退役路径": sum(d["retired"] for d in per_doc.values()),
            "表格总数": sum(d["tables"] for d in per_doc.values()),
            "端点清单表(应恒为 0)": sum(d["inventory"] for d in per_doc.values()),
            "请求参数表已收敛": sum(d["slim"] for d in per_doc.values()),
            "请求参数表违规": sum(d["violations"] for d in per_doc.values()),
        }
    )


SELF_TEST_BASELINE = {
    "/api/v1/auth/login/",
    "/api/v1/assets/",
    "/api/v1/assets/{asset_code}/",
    "/api/v1/users/employees/{employee_jobcode}/",
}

# (用例名, 文档行, 期望命中的规则前缀或 None 表示「不应报红」)
SELF_TEST_CASES: list[tuple[str, list[str], str | None]] = [
    (
        "V-1 缺 v1 前缀",
        ["#### POST /api/auth/login/ -- 登录"],
        "V-1",
    ),
    (
        "V-2 端点不存在",
        ["#### GET /api/v1/ghost/ -- 不存在"],
        "V-2",
    ),
    (
        "V-2 仅路径参数名漂移",
        ["#### GET /api/v1/assets/{id}/ -- 参数名过时"],
        "V-2",
    ),
    (
        "V-2 方法式不识别",
        ["#### FETCH /api/v1/assets/ -- 非法方法"],
        "V-2",
    ),
    (
        "V-3 端点清单表回归",
        [
            "## 四、资源端点列表",
            "",
            "| 方法 | URL | 说明 |",
            "|------|-----|------|",
            "| GET | /api/v1/assets/ | 资产列表 |",
        ],
        "V-3",
    ),
    (
        "V-4 请求参数表带 schema 列",
        [
            "## 四、请求参数与请求体",
            "",
            "| 字段 | 类型 | 必填 | 说明 |",
            "|------|------|------|------|",
            "| `asset_code` | str | 是 | 资产编码 |",
        ],
        "V-4",
    ),
    (
        "干净文档不应报红",
        [
            "## 四、请求参数与请求体",
            "",
            "| 字段 | 说明 |",
            "|------|------|",
            "| `asset_code` | 资产编码 |",
            "",
            "#### GET /api/v1/assets/ -- 资产列表",
            "",
            "#### PUT/PATCH /api/v1/assets/{asset_code}/ -- 更新资产",
            "",
            "#### ~~/api/v1/auth/token/~~ — 已退役",
            "",
            "旧前缀曾写作 /api/... ",
        ],
        None,
    ),
]


def run_self_test() -> int:
    """用内存样本证明每条规则真的会红,并证明干净样本不会误报。

    护栏若无负样本测试,「规则恒绿」与「规则生效」在 CI 输出一模一样。
    """
    failures: list[str] = []
    for name, lines, expected in SELF_TEST_CASES:
        BLOCKING.clear()
        stats = check_document(lines, "<self-test>", SELF_TEST_BASELINE)
        got = BLOCKING[:]
        if expected is None:
            if got:
                failures.append(f"{name}: 期望无违规, 实际 {got}")
            if stats["dual"] != 1 or stats["ops"] != 3:
                failures.append(
                    f"{name}: 双方法式标题应计为 2 个 operation, "
                    f"实得 dual={stats['dual']} ops={stats['ops']}"
                )
        else:
            if not any(item.startswith(expected) for item in got):
                failures.append(f"{name}: 期望 {expected} 报红, 实际 {got or '无'}")
        print(f"  [{'OK ' if not any(name in f for f in failures) else 'FAIL'}] {name}")
    BLOCKING.clear()

    if failures:
        print("-" * 68)
        print(f"自检失败 {len(failures)} 项:")
        for item in failures:
            print(f"  {item}")
        return 1
    print("-" * 68)
    print(f"自检通过: {len(SELF_TEST_CASES)} 个用例（负样本必红 + 正样本不误报）")
    return 0


def main() -> int:
    if not BASELINE.exists():
        print(f"基线缺失: {BASELINE}")
        return 1
    baseline = load_baseline_paths()
    per_doc = {}
    for path in DOCS:
        rel = str(path.relative_to(ROOT))
        if not path.exists():
            BLOCKING.append(f"文档缺失: {rel}")
            continue
        per_doc[path.name] = check_document(read_lines(path), rel, baseline)
    summarize(per_doc)

    print("=" * 68)
    print("API 文档一致性护栏 — 运行时统计 (计数由提取器枚举,无魔法数字)")
    print("=" * 68)
    for k, v in REPORT.items():
        print(f"  {k:<28} {v}")
    print("-" * 68)
    if BLOCKING:
        print(f"阻断项 {len(BLOCKING)} 条:")
        for item in BLOCKING:
            print(f"  {item}")
        return 1
    print("V-1~V-4 全部通过")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(run_self_test())
    sys.exit(main())
