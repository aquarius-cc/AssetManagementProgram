# -*- coding: utf-8 -*-
"""文档结构解析与区域定位 (doc region parser)

设计要点：**外科式替换**。解析器只定位"由代码生成"的表格所占的连续行
区间，生成器只重写这些区间，其余行按原样拼回。

为什么不用"整篇重新渲染"：那样无法把差异归因。若整篇重渲染后与原文
比对，任何一处渲染器风格差异都会与真实缺陷混在一起，验证就失去意义。
外科式替换使"生成结果 vs 原文"的每一处差异都必然对应一个真实的数据差异。

识别的两类区域：

* 枚举表  —— 形如 ``#### 资产状态 (asset_current_status)`` 之下、
  首列表头为 ``值`` 的表格。
* 参数表  —— 端点小节内、首列表头为 ``参数`` 或 ``字段`` 的表格，
  归属其最近的 ``**查询参数**`` / ``**请求体**`` / ``**路径参数**`` 标记。
"""

import re

HEADING_ENDPOINT = re.compile(r"^#{3,4}\s+(GET|POST|PUT|PATCH|DELETE)\s+(\S+)")
HEADING_ENUM = re.compile(r"^#{3,4}\s+(.*?)\s*\(([A-Za-z_][A-Za-z0-9_]*)\)\s*$")
SEP = re.compile(r"^\|[\s:|-]+\|$")

# 任何"整行只有一个粗体标签"都是表角色标记。**不能只认四类**：同一端点
# 常有多张表（如 `**请求体**` 列 items、`**items 子项**` 列元素字段），
# 若把不认识的后者当作前者的延续，两张表会被合并成一份并互相渲染出
# 重复行——实测 `PUT /users/departments/sort` 因此产出 4 行 `| field | note |`。
# 末尾允许冒号；带正文（如 `**权限**: IsAdminUser`）的不算角色标记。
LABEL = re.compile(r"^\*\*(.+?)\*\*:?\s*$")

KNOWN_ROLES = {
    "查询参数": "query",
    "请求体": "body",
    "路径参数": "path",
    "返回字段": "response",
}


def _cells(line):
    """拆分 Markdown 表格行，返回去空白/去反引号的单元格。"""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    return [c.strip().strip("`") for c in stripped.strip("|").split("|")]


def _table_end(lines, start):
    """返回表格结束行号（含），即首个非表格行或文件尾。"""
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        index += 1
    return index - 1


class Region:
    """一段可重写的表格区域。

    ``style`` 记录原表的书写约定，渲染时必须沿用。否则生成器会剥掉反引号、
    重算分隔线宽度，把一次 20 行的语义修正变成 400 行的排版噪音——评审
    无法进行，"外科式替换"也就名存实亡。本文档反引号/留白/分隔线三种风格
    混用（如枚举表为 ``|----|------|``，参数表为 ``| --- | --- |``），
    故样式必须**逐区域**探测，不能全局统一。
    """

    def __init__(self, kind, start, end, meta, rows, style=None):
        self.kind = kind
        self.start = start
        self.end = end
        self.meta = meta
        self.rows = rows
        self.style = style or {}
        self.replacement = None

    def __repr__(self):
        return "Region(%s, L%d-%d, %s)" % (self.kind, self.start + 1, self.end + 1, self.meta)


def _detect_style(lines, start, end):
    """探测原表样式：``{pad, backtick, sep}``。

    ``pad`` 取自**表头/数据行**而非分隔线：本文档的留白约定与分隔线写法
    并不一致（数据行 ``| x | y |`` 配分隔线 ``|----|----|``），
    只看分隔线会把所有留白表误判为紧凑表。
    """
    sep = None
    pad = None
    backtick = False
    for index in range(start, min(end + 1, start + 4)):
        line = lines[index]
        if SEP.match(line.strip()):
            sep = line.strip()
            continue
        raw = line.strip()
        if not raw.startswith("|"):
            continue
        first = raw.strip("|").split("|")[0] if "|" in raw else ""
        if pad is None and first:
            pad = first != first.strip()
        if "`" in line:
            backtick = True
    return {"pad": bool(pad), "backtick": backtick, "sep": sep}


def _collect_rows(lines, start, end):
    """表格数据行（跳过表头与分隔线）。"""
    rows = []
    for index in range(start + 1, end + 1):
        if SEP.match(lines[index].strip()):
            continue
        row = _cells(lines[index])
        if row:
            rows.append(row)
    return rows


def parse(lines):
    """返回 ``(regions, context)``。

    regions 顺序即文档顺序；context 记录标题层级与端点小节，供报错定位。
    """
    regions = []
    current_endpoint = None
    current_role = None
    in_enum_heading = False
    enum_title = None
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        endpoint = HEADING_ENDPOINT.match(stripped)
        if endpoint:
            current_endpoint = (endpoint.group(1), endpoint.group(2).split("--")[0].strip())
            current_role = None
            in_enum_heading = False
            index += 1
            continue

        enum_heading = HEADING_ENUM.match(stripped)
        if enum_heading and not HEADING_ENDPOINT.match(stripped):
            in_enum_heading = True
            enum_title = (enum_heading.group(1), enum_heading.group(2))
            current_role = None
            index += 1
            continue

        label = LABEL.match(stripped)
        if label:
            text = label.group(1).strip()
            current_role = KNOWN_ROLES.get(text, "sub:" + text)
            in_enum_heading = False
            index += 1
            continue

        if not stripped.startswith("|"):
            # 仅新标题才清空角色。空行、**权限**: 等非表格内容必须保留
            # current_role —— 否则 "**查询参数**:" 与表格之间的空行会
            # 把角色清掉，导致该表格永远匹配不上（引导命中 0 的成因）。
            if stripped.startswith("#"):
                in_enum_heading = False
                current_role = None
            index += 1
            continue

        cells = _cells(line)
        if not cells or not cells[0]:
            index += 1
            continue

        if cells[0] == "值" and in_enum_heading:
            end = _table_end(lines, index)
            regions.append(Region(
                "enum",
                index,
                end,
                {"field": enum_title[1], "title": enum_title[0]},
                _collect_rows(lines, index, end),
                _detect_style(lines, index, end),
            ))
            index = end + 1
            continue

        if cells[0] in ("参数", "字段") and current_endpoint and current_role:
            end = _table_end(lines, index)
            regions.append(Region(
                "params",
                index,
                end,
                {"endpoint": current_endpoint, "role": current_role},
                _collect_rows(lines, index, end),
                _detect_style(lines, index, end),
            ))
            index = end + 1
            continue

        index += 1

    context = {
        "enum_count": sum(1 for r in regions if r.kind == "enum"),
        "param_count": sum(1 for r in regions if r.kind == "params"),
    }
    return regions, context


def endpoint_key(endpoint):
    """端点 -> 注释层与 schema 共用的唯一键。

    归一化两处差异，否则查表必然落空：

    * 尾斜杠 —— 文档写 ``/api/v1/users/departments/``，schema 也是带斜杠，
      但按路径查模型字段时需要去斜杠，故统一 ``rstrip("/")``。
    * 路径参数名 —— 文档写 ``{id}``，跨端点无意义，统一折叠为 ``{}``。

    注意键**不含 role**：同一端点的查询参数表与请求体表是两个独立区域、
    字段集不同，故 role 由调用方作为第二层传入注释层，不并入此键。
    """
    method, path = endpoint
    head = path.split("--")[0].strip()
    normalized = re.sub(r"\{[^}]+\}", "{}", head).rstrip("/")
    return "%s %s" % (method.upper(), normalized)


def assemble(lines, regions):
    """按 regions 的 replacement 外科式拼回整篇文档。

    未被覆盖的行原样保留，因此替换后的文档与原文的差异集合
    恰好等于"被重写区域的内容差异"。
    """
    out = []
    cursor = 0
    for region in sorted(regions, key=lambda r: r.start):
        out.extend(lines[cursor : region.start])
        if region.replacement is None:
            out.extend(lines[region.start : region.end + 1])
        else:
            out.extend(region.replacement)
        cursor = region.end + 1
    out.extend(lines[cursor:])
    return out
