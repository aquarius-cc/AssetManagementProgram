# -*- coding: utf-8 -*-
"""字段注释层 (annotations) —— 生成器唯一的人工输入

为什么用 JSON 而不是 YAML：``PyYAML`` 在本机可用但**未在
``requirements/*.txt`` 声明**，CI job 不可依赖；且本文件由
``--bootstrap`` 机器生成，人工只在补说明时编辑，JSON 的可读性损失
可接受。Python dict 保序，故字段顺序由本文件决定。

结构::

    {
      "endpoints": {
        "GET /api/v1/users/departments": {
          "query":  [{"field": "page", "note": "页码"}],
          "body":   [],
          "response": []
        }
      },
      "enum_notes": {
        "asset_current_status": {"in_store": "新增加、已拒绝报废"}
      }
    }

``endpoints`` 的 key 是"方法 + 归一化路径"（尾斜杠已去、``{id}`` 折叠为
``{}``），其下**必须按 role 分层**：同一端点的查询参数表与请求体表是两个
独立区域且字段集不同，若压平成一个列表会互相覆盖——实测
``PUT /api/v1/users/departments/{id}/move`` 即因此丢失一张表。
"""

import json

from . import docparser

SCHEMA_VERSION = 1
ROLES = ("query", "body", "path", "response")

class AnnotationsError(Exception):
    """注释层不可用或与真值不匹配"""


def empty():
    return {"version": SCHEMA_VERSION, "endpoints": {}, "enum_notes": {}}


def load(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return empty()
    except json.JSONDecodeError as exc:
        raise AnnotationsError("注释层 JSON 损坏：%s" % exc) from exc
    for key in ("endpoints", "enum_notes"):
        data.setdefault(key, {})
    return data


def save(path, data):
    data["version"] = SCHEMA_VERSION
    data["endpoints"] = {k: data["endpoints"][k] for k in sorted(data["endpoints"])}
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def notes_for(data, endpoint_key, role):
    """返回 ``[(字段, 说明), ...]``，保持注释层中的顺序。"""
    bucket = (data["endpoints"].get(endpoint_key) or {}).get(role) or []
    return [(item["field"], item.get("note", "")) for item in bucket]


def fields_for(data, endpoint_key, role):
    return [field for field, _ in notes_for(data, endpoint_key, role)]


def has(data, endpoint_key, role):
    return bool((data["endpoints"].get(endpoint_key) or {}).get(role))


def put(data, endpoint_key, role, pairs):
    """写入一个端点某一角色的字段清单（顺序即给定顺序）。"""
    data["endpoints"].setdefault(endpoint_key, {})[role] = [
        {"field": field, "note": note} for field, note in pairs
    ]


def enum_note(data, field_name, value):
    return (data.get("enum_notes") or {}).get(field_name, {}).get(value, "")


def put_enum_note(data, field_name, value, note):
    data.setdefault("enum_notes", {}).setdefault(field_name, {})[value] = note


def bootstrap(regions):
    """从文档现有表格引导注释层，并返回 (data, report)。

    report 记录命中/未命中，用于落台账。**引导结果必须人工过目后**
    才允许锁门禁——否则一次错误的表头解析会静默产出空注释层。
    """
    data = empty()
    report = {
        "endpoints": {"hit": 0, "empty_note": 0},
        "enums": {"hit": 0, "empty_note": 0},
        "skipped": [],
    }
    for region in regions:
        if region.kind == "params":
            key = docparser.endpoint_key(region.meta["endpoint"])
            role = region.meta["role"]
            pairs = []
            for row in region.rows:
                if len(row) < 2 or not row[0]:
                    continue
                note = row[1].strip()
                pairs.append((row[0], note))
                if note:
                    report["endpoints"]["hit"] += 1
                else:
                    report["endpoints"]["empty_note"] += 1
            if pairs:
                put(data, key, role, data["endpoints"].get(key, {}).get(role, []) + pairs)
        elif region.kind == "enum":
            field = region.meta["field"]
            rows_seen = 0
            for row in region.rows:
                if len(row) < 2 or not row[0]:
                    continue
                value = row[0]
                rows_seen += 1
                note = row[2].strip() if len(row) > 2 else ""
                if note:
                    put_enum_note(data, field, value, note)
                    report["enums"]["hit"] += 1
                else:
                    report["enums"]["empty_note"] += 1
            if rows_seen == 0:
                report["skipped"].append("枚举表 %s 未解析出任何数据行" % field)
    return data, report
