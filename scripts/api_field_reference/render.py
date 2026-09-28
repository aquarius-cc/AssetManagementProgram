# -*- coding: utf-8 -*-
"""表格渲染 (render)

渲染原则：**值与中文标签只来自代码，说明只来自注释层**。

生成器不"修补"任何一侧。若注释层与真值不一致，报错退出（门禁失败），
而不是选一边覆盖另一边——那会把契约变更伪装成文档更新，正是本项目
要消除的双源漂移。
"""

# django-filter 派生的 ORM 跨表查找式，属实现细节，不进文档
LOOKUP_SEP = "__"

PARAM_HEADER = {"query": "参数", "body": "字段", "path": "参数", "response": "字段"}


class Mismatch:
    """注释层与真值的差异。

    ``kind`` 区分**处置方不同**的故障，混为一谈会导致改错文件：

    * ``文档缺字段`` / ``文档多字段`` —— 文档侧问题，改文档。
    * ``schema缺请求体``        —— spectacular 未能内省出 requestBody，
      是**后端代码缺陷**，改文档等于把 schema 的缺陷固化成"契约"。
    * ``结构不一致``            —— 两侧字段集**零交集**，不是改名而是
      schema 把响应体描述成了另一套结构（如 statistics 端点被回退成
      实体列表），须在 View 补 ``@extend_schema``。
    """

    DOC_MISS = "文档缺字段"
    DOC_EXTRA = "文档多字段"
    SCHEMA_NO_BODY = "schema缺请求体"
    STRUCTURE = "结构不一致"

    def __init__(self, kind, where, detail, side="doc"):
        self.kind = kind
        self.where = where
        self.detail = detail
        self.side = side

    def __str__(self):
        return "[%s] %s -> %s" % (self.kind, self.where, self.detail)


def render_enum_table(region, pairs, notes):
    """渲染枚举表：列 ``值 | 中文 [| 说明]``。

    值与中文标签来自 ``pairs``（TextChoices 声明序）；``说明`` 列是否
    存在，取决于注释层是否为该字段录入了至少一条说明。

    书写风格沿用原表（``region.style``）：反引号、留白、分隔线逐区域保持，
    使 diff 只包含真实的值/标签变化。
    """
    style = region.style or {}
    has_notes = any(notes.get(value) for value, _ in pairs)
    header = ["值", "中文"]
    body = []
    for value, label in pairs:
        cells = [value, label]
        if has_notes:
            cells.append(notes.get(value, ""))
        body.append(cells)
    if has_notes:
        header.append("说明")
    return _table(header, body, style)


def render_param_table(region, pairs, header_word):
    """渲染参数表：``| 参数 | 说明 |``，字段顺序取自注释层。"""
    body = [[field, note] for field, note in pairs]
    return _table([header_word, "说明"], body, region.style or {})


def _table(header, body, style):
    """按原表风格拼装 Markdown 表格。

    ``sep`` 直接复用原分隔线（原文混用 ``|----|------|`` 与
    ``| --- | --- |``，重算宽度会让整表变成噪音 diff）；原表列数与新列数
    不一致时（如新增说明列）才回退到按列数生成。
    """
    pad = style.get("pad", True)
    sep = style.get("sep")
    bt = style.get("backtick", True)
    quote = (lambda text: "`%s`" % text) if bt else (lambda text: text)

    def line(cells):
        if pad:
            return "| " + " | ".join(cells) + " |"
        return "|" + "|".join(cells) + "|"

    # 表头词（值/参数/字段/中文/说明）**不加反引号**——本文档的约定是
    # 只对数据单元格（字段名、枚举值）加。加了会在 94 张表里制造 94 处
    # 无意义 diff，评审时真正的语义变化会被淹没。
    lines = [line(header)]
    expected = len(header)
    if sep and sep.count("|") - 1 == expected:
        lines.append(sep)
    else:
        cells = ["---"] * expected
        lines.append("| " + " | ".join(cells) + " |" if pad else "|" + "|".join(cells) + "|")
    for cells in body:
        rendered = [quote(cells[0])] + list(cells[1:])
        lines.append(line(rendered))
    return lines


def reconcile_params(truth_fields, annotation_fields, where, alt_fields=None,
                     wrappers=None, role="query", lookup_sep=LOOKUP_SEP):
    """注释层字段集 vs 真值字段集。

    ``alt_fields`` 是可接受的**第二口径**（数组请求体：文档展开
    ``{"items": [{field, sort_order}]}`` 为元素字段）。``wrappers`` 是
    已展开的包装层名，不参与"缺失"判定。

    返回 ``(missing, mismatches)``。关键：``side`` 标出该由哪一侧修——
    当 schema 对某角色**根本没有信息**（body 恒空）时，责任在代码而非
    文档，必须报 ``schema缺请求体`` 而不是让维护者去删文档字段。

    ``lookup_sep``（``__``）过滤**只适用于 query/body/response**：它剔除的是
    文档漏出的 ORM 查找式（如 ``employee_department__department_code``）。
    **path 不可套用**——DRF 的 ``lookup_field = "asset_recordcode__asset_code"``
    会直接把 ``__`` 派生成 URL 命名组
    （``waste-assets/{asset_recordcode__asset_code}/``），那是路由的字面真值
    而非泄漏；无差别过滤会把它误判成"文档多字段"，进而诱导维护者删掉正确参数。
    """
    strip_lookup = role != "path"
    truth = [f for f in truth_fields if not (strip_lookup and lookup_sep in f)]
    alt = [f for f in (alt_fields or []) if not (strip_lookup and lookup_sep in f)]
    wrapper_set = set(wrappers or [])
    note_set = set(annotation_fields)
    mismatches = []

    if role == "body" and not truth and not alt and annotation_fields:
        return [], [Mismatch(
            Mismatch.SCHEMA_NO_BODY, where,
            "schema 未记录 requestBody（drf-spectacular 未内省出），文档字段 %s 应保留并在 View 补 @extend_schema"
            % ", ".join(annotation_fields),
            side="code",
        )]

    if role == "response" and truth and annotation_fields and not (set(truth) & note_set):
        return [], [Mismatch(
            Mismatch.STRUCTURE, where,
            "schema 响应字段与文档零交集（schema: %s；文档: %s），"
            "疑为 spectacular 回退成实体列表，须在 View 补 @extend_schema"
            % (", ".join(truth[:4]), ", ".join(annotation_fields[:4])),
            side="code",
        )]

    accepted = set(truth) | set(alt)
    missing = [f for f in truth if f not in note_set and f not in alt and f not in wrapper_set]
    extra = [f for f in annotation_fields if f not in accepted]
    if missing:
        mismatches.append(Mismatch(Mismatch.DOC_MISS, where, "schema 有而文档无: %s" % ", ".join(missing)))
    if extra:
        mismatches.append(Mismatch(Mismatch.DOC_EXTRA, where, "文档有而 schema 无: %s" % ", ".join(extra)))
    return missing, mismatches
