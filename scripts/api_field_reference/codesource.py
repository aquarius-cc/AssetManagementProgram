# -*- coding: utf-8 -*-
"""字段/枚举真值数据源 (authoritative source)

两路真值，各司其职：

1. 枚举值与中文标签 —— 取自 Django 模型字段的 ``choices``。
   选它而非 schema 的理由：``TextChoices`` 成员自带结构化 label
   （如 ``broken='损坏存放出库'``），而 drf-spectacular 只是把它渲染进
   ``description`` 的 markdown 列表（``* `pending` - 待审批``），
   那是**已渲染的字符串**，解析它属于依赖实现细节的脆弱做法。
   标签的真值只能来自代码。

2. 端点参数（查询/请求体字段名） —— 取自 ``api-schema-baseline.json``。
   选它而非内省 filterset/serializer 的理由：基线是**已发布契约**的
   机器可读快照，且已有 ``api-schema-check`` job 守着它与代码的漂移；
   内省 100+ 个 filterset 与嵌套 serializer 取"第一层 properties"
   反而会与基线产生第二套口径。

本模块**不连接数据库**：模型字段元数据在 import 期即可读出。
（已实测：DB_HOST/DB_PORT/DB_NAME 全部指向不可达地址时内省仍成功）
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "asset_management_backend"
DOC = BACKEND / "docs" / "API详细文档0608.md"
BASELINE = BACKEND / "api-schema-baseline.json"
ANNOTATIONS = BACKEND / "docs" / "api_field_annotations.json"

# ORM 跨表查找式（如 employee_department__department_code__iexact）
# 由 django-filter 从 related-field lookup 自动派生，是实现细节，
# 不属于对外契约，不进文档。
LOOKUP_SEP = "__"


class SourceError(Exception):
    """真值数据不可用（设置缺失 / 基线损坏 / 字段无法解析）"""


def _setup_django():
    """装配 Django 环境以便内省模型字段。无需数据库连接。"""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    # 纯元数据内省不需要真实密钥，但 settings 强制要求非空。
    os.environ.setdefault("SECRET_KEY", "api-doc-generator-metadata-only")
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    if str(BACKEND / "apps") not in sys.path:
        sys.path.insert(0, str(BACKEND / "apps"))
    try:
        import django
    except ImportError as exc:  # pragma: no cover - 环境缺依赖
        raise SourceError(f"无法导入 Django：{exc}") from exc
    try:
        django.setup()
    except Exception as exc:  # pragma: no cover - settings 缺配置
        raise SourceError(f"django.setup() 失败：{exc}") from exc


def load_choices():
    """返回 ``{字段名: [(值, 中文标签), ...]}``，顺序为 TextChoices 声明序。

    同一字段名若在多个模型上定义且取值不一致，说明是 DR-1 隐患，
    此处直接报错而不是任选其一，避免静默取到错误的真值。
    """
    _setup_django()
    from django.apps import apps

    found = {}
    conflicts = {}
    for model in apps.get_models():
        for field in model._meta.get_fields():
            choices = getattr(field, "choices", None)
            if not choices:
                continue
            pairs = [(str(c[0]), str(c[1])) for c in choices]
            name = field.name
            if name in found and found[name] != pairs:
                conflicts.setdefault(name, set()).update(
                    "%s=%s" % (m.__name__, pairs) for m in apps.get_models()
                    if any(f.name == name for f in m._meta.get_fields() if getattr(f, "choices", None))
                )
                continue
            found[name] = pairs
    if conflicts:
        detail = "; ".join("%s: %s" % (k, sorted(v)) for k, v in sorted(conflicts.items()))
        raise SourceError("同名字段取值不一致，枚举真值不唯一 -> %s" % detail)
    return found


def load_baseline():
    """返回已发布 OpenAPI 契约字典。"""
    try:
        with BASELINE.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceError("读取基线失败：%s -> %s" % (BASELINE, exc)) from exc


def overlap_ratio(doc_keys, baseline):
    """文档端点键在基线中的命中占比。

    正常应 ≥ 0.9。骤降到 0 几乎总是**键格式不一致**（前缀、尾斜杠、
    路径参数折叠三处），而非"文档写错了 100 个端点"。此函数把该故障
    从"逐条 189 条提示淹没输出"变成一条明确报错。
    """
    schema_keys = set(_operation_index(baseline))
    if not doc_keys:
        return 1.0
    hit = sum(1 for key in doc_keys if key in schema_keys)
    return hit / float(len(doc_keys))


def _deref(node, schemas, depth=0):
    """解析 ``$ref`` 指针。"""
    seen = set()
    while isinstance(node, dict) and "$ref" in node and depth < 10:
        ref = node["$ref"]
        if ref in seen:
            break
        seen.add(ref)
        node = schemas.get(ref.rsplit("/", 1)[-1], {})
        depth += 1
    return node if isinstance(node, dict) else {}


def _operation_index(baseline):
    """``{"METHOD /归一化路径": operation}``。

    键格式必须与 ``docparser.endpoint_key`` **逐字一致**（"METHOD /path"，
    尾斜杠已去、``{x}`` 折叠为 ``{}``）。两侧曾因格式不一致（tuple vs str）
    导致查表 100% 落空却不报错，故此处用字符串而非 tuple，并在
    ``overlap_ratio`` 中做覆盖率自检。
    """
    index = {}
    for path, operations in (baseline.get("paths") or {}).items():
        for method, operation in (operations or {}).items():
            if not isinstance(operation, dict):
                continue
            index[_key(method, path)] = operation
    return index


def _key(method, path):
    import re

    normalized = re.sub(r"\{[^}]+\}", "{}", path.split("--")[0].strip()).rstrip("/")
    return "%s %s" % (method.upper(), normalized)


def _response_properties(operation, schemas):
    """取 200 响应体的第一层字段名。

    兼容三种外层形态：裸数组（列表接口）、``{"results": [...], "count": n}``
    分页信封、以及普通对象。分页信封取 ``results`` 元素的属性，
    否则会把 ``count``/``next``/``previous`` 当成业务字段。
    """
    responses = operation.get("responses") or {}
    for status in sorted(responses):
        if not str(status).startswith("2"):
            continue
        content = ((responses[status] or {}).get("content") or {})
        schema = _deref((content.get("application/json") or {}).get("schema") or {}, schemas)
        if schema.get("type") == "array":
            schema = _deref(schema.get("items") or {}, schemas)
        elif "results" in (schema.get("properties") or {}):
            schema = _deref(schema["properties"]["results"], schemas)
            if schema.get("type") == "array":
                schema = _deref(schema.get("items") or {}, schemas)
        return [name for name in (schema.get("properties") or {}) if LOOKUP_SEP not in name]
    return []


def load_endpoint_fields():
    """返回 ``{"METHOD /归一化路径": {query, path, body, body_items, response}}``。

    query 取 schema ``parameters[].name`` 中 ``in=query`` 者（排除含 ``__``
    的 ORM 查找式）；path 取 ``in=path``；body 取 ``requestBody`` 第一层
    ``properties``；``body_items`` 另取数组元素的 ``properties``，用于
    文档有意展开 ``{"items": [...]}`` 的端点；response 取 200 响应体
    第一层 ``properties``。所有含 ``__`` 的名称一律剔除。
    """
    baseline = load_baseline()
    schemas = (baseline.get("components") or {}).get("schemas") or {}
    result = {}
    for key, operation in _operation_index(baseline).items():
        path_params = []
        query = []
        for param in operation.get("parameters") or []:
            if not isinstance(param, dict):
                continue
            name = param.get("name")
            if not name:
                continue
            where = param.get("in")
            if where == "path":
                path_params.append(name)
            elif where == "query" and LOOKUP_SEP not in name:
                query.append(name)

        content = ((operation.get("requestBody") or {}).get("content") or {})
        schema = _deref((content.get("application/json") or {}).get("schema") or {}, schemas)
        body, body_items, wrappers = _body_fields(schema, schemas)

        result[key] = {
            "query": query,
            "path": path_params,
            "body": body,
            "body_items": body_items,
            "body_wrappers": wrappers,
            "response": _response_properties(operation, schemas),
        }
    return result


def _body_fields(schema, schemas):
    """返回 ``(顶层字段名, 元素字段名, 已展开的包装层名)``。

    三种数组容器都要处理，否则 ``/sort`` 系列会整片误判：

    1. 顶层即数组 —— ``[{...}]``；
    2. 顶层对象内含数组属性 —— ``{"items": [{...}]}``，这是本项目
       批量排序端点的实际形态，文档**有意展开**为元素字段。

    ``wrappers`` 记录被展开的包装层（如 ``items``）。文档既不列包装层
    也列元素字段是**表述约定**而非缺陷，故包装层不参与"缺失"判定；
    否则每个 ``/sort`` 端点都会凭空多一条假警报。
    """
    items = []
    wrappers = []
    node = schema
    if node.get("type") == "array":
        node = _deref(node.get("items") or {}, schemas)
        items.extend(_prop_names(node, schemas))
    top = _prop_names(node, schemas)
    for name, sub in (node.get("properties") or {}).items():
        sub_node = _deref(sub, schemas)
        if sub_node.get("type") == "array":
            element = _deref(sub_node.get("items") or {}, schemas)
            if element.get("properties"):
                wrappers.append(name)
                items.extend(_prop_names(element, schemas))
    unique = list(dict.fromkeys(items))
    return top, unique, wrappers


def _prop_names(node, schemas):
    if not isinstance(node, dict):
        return []
    node = _deref(node, schemas) if "$ref" in node else node
    return [name for name in (node.get("properties") or {}) if LOOKUP_SEP not in name]


def cross_check_choices(baseline, choices):
    """交叉校验：schema 内嵌的中文标签应与模型 choices 一致。

    schema 侧标签来自 ``description`` 里的 markdown 列表，是**推导值**；
    本函数只用于发现两侧背离，不作为真值来源。返回不一致清单。
    """
    import re

    problems = []
    for name, pairs in sorted(choices.items()):
        pattern = re.compile(
            r"`%s`\s*[-:：]\s*([^\n*]+)" % re.escape(name)
        )
        blob = json.dumps(baseline, ensure_ascii=False)
        for value, label in pairs:
            if pattern.search(blob) is None:
                continue
            if label not in blob:
                problems.append("%s.%s 标签 `%s` 未出现在 schema 中" % (name, value, label))
    return problems
