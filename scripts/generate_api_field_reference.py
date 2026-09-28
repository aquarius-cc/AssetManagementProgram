# -*- coding: utf-8 -*-
"""API 字段/枚举层生成器 (field & enum layer generator)

把 ``API详细文档0608.md`` 中的**枚举表与参数表**改为由代码生成，
手写部分（业务规则、状态流转、调用示例）保持不动。

真值分工（详见 ``api_field_reference/codesource.py`` 顶部说明）：

* 枚举值 + 中文标签  <- Django 模型字段 ``choices``（标签只可能来自代码）
* 端点参数字段名      <- ``api-schema-baseline.json``（已发布契约）
* 字段中文说明        <- ``docs/api_field_annotations.json``（唯一人工输入）

退出码：
  0 = 文档与真值一致（或 --write 已同步）
  1 = 存在漂移/虚构/未解析字段，门禁失败
  2 = 真值不可用（设置缺失、基线损坏、注释层 JSON 损坏）

用法：
  python scripts/generate_api_field_reference.py --bootstrap
  python scripts/generate_api_field_reference.py --check
  python scripts/generate_api_field_reference.py --write
"""

import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api_field_reference import annotations as ann  # noqa: E402
from api_field_reference import codesource, docparser, render  # noqa: E402


def bootstrap(args, lines, regions):
    """从文档现有表格引导注释层，并打印命中/未命中。"""
    data, report = ann.bootstrap(regions)
    ann.save(args.annotations, data)
    print("=" * 68)
    print("注释层引导完成 -> %s" % args.annotations)
    print("=" * 68)
    print("  端点字段说明  命中 %-4d 空说明 %-4d" % (
        report["endpoints"]["hit"], report["endpoints"]["empty_note"]))
    print("  枚举值说明    命中 %-4d 空说明 %-4d" % (
        report["enums"]["hit"], report["enums"]["empty_note"]))
    print("  端点条目数    %d" % len(data["endpoints"]))
    print("  枚举字段数    %d" % len(data["enum_notes"]))
    if report["skipped"]:
        print("  未采集:")
        for item in report["skipped"]:
            print("    - %s" % item)
    print()
    print("  引导结果须人工过目后再锁门禁：空说明 %d 项为“该字段无补充说明”，"
          % (report["endpoints"]["empty_note"] + report["enums"]["empty_note"]))
    print("  若上表命中数与预期不符，说明表头解析有误，勿锁门禁。")
    return 0


def generate(args, lines, regions, data):
    """为每个区域生成 replacement，并收集阻断项。"""
    choices = codesource.load_choices()
    fields = codesource.load_endpoint_fields()

    # 键格式自检：命中率过低几乎必然是两侧归一化规则不一致，而非文档错百处。
    doc_keys = {docparser.endpoint_key(r.meta["endpoint"]) for r in regions if r.kind == "params"}
    ratio = codesource.overlap_ratio(doc_keys, codesource.load_baseline())
    if ratio < 0.5:
        raise codesource.SourceError(
            "文档端点键与 schema 基线仅 %.0f%% 命中（%d/%d），判定为键格式不一致。"
            "请核对 _key() 与 docparser.endpoint_key() 的归一化规则"
            "（尾斜杠 / {x} 折叠 / 前缀）。" % (ratio * 100, int(ratio * len(doc_keys)), len(doc_keys))
        )

    blocking = []
    code_side = []
    warnings = []

    for region in regions:
        if region.kind == "enum":
            name = region.meta["field"]
            if name not in choices:
                blocking.append(
                    "枚举表 `#### %s (%s)` 的字段名在代码中无 choices 定义（行 L%d）"
                    % (region.meta["title"], name, region.start + 1)
                )
                continue
            pairs = choices[name]
            notes = (data.get("enum_notes") or {}).get(name, {})
            documented = {row[0] for row in region.rows if row and row[0]}
            actual = {v for v, _ in pairs}
            for gone in sorted(documented - actual):
                warnings.append("枚举 %s：文档中的 `%s` 在代码中已不存在" % (name, gone))
            for added in sorted(actual - documented):
                warnings.append("枚举 %s：代码新增 `%s`，文档需补说明" % (name, added))
            region.replacement = render.render_enum_table(region, pairs, notes)

        elif region.kind == "params":
            key = docparser.endpoint_key(region.meta["endpoint"])
            role = region.meta["role"]
            where = "%s [%s]  (行 L%d)" % (key, role, region.start + 1)
            if not ann.has(data, key, role):
                blocking.append(
                    "端点 `%s [%s]` 无注释层条目（行 L%d），需 --bootstrap 或人工补录"
                    % (key, role, region.start + 1)
                )
                continue
            truth = fields.get(key)
            if truth is None:
                warnings.append("端点 `%s` 不在 schema 基线中，跳过校验" % key)
                truth = {"query": [], "body": [], "path": [], "response": []}
            if role.startswith("sub:"):
                # 子结构表（如 `**items 子项**`）：不是对外请求体本身，
                # 无法用 schema 第一层字段直接对账，故不强制校验字段集，
                # 只按注释层渲染。仅当其字段与父级 body_items 明显冲突时提示。
                pairs = ann.notes_for(data, key, role)
                region.replacement = render.render_param_table(
                    region, pairs, "字段"
                )
                continue
            truth_fields = truth.get(role, [])
            annotated = ann.fields_for(data, key, role)
            missing, mismatches = render.reconcile_params(
                truth_fields,
                annotated,
                where,
                alt_fields=truth.get("body_items"),
                wrappers=truth.get("body_wrappers"),
                role=role,
            )
            blocking.extend(str(m) for m in mismatches)
            code_side.extend(m for m in mismatches if m.side == "code")
            pairs = ann.notes_for(data, key, role)
            for field in missing:
                warnings.append("%s 参数 `%s` 待补注释层说明" % (key, field))
            header = render.PARAM_HEADER.get(role, "参数")
            region.replacement = render.render_param_table(region, pairs, header)

    return blocking, warnings, code_side


def report_diff(original, updated, limit=60):
    diff = list(
        difflib.unified_diff(
            original,
            updated,
            fromfile="committed",
            tofile="regenerated",
            lineterm="",
            n=1,
        )
    )
    if not diff:
        return 0
    print("-" * 68)
    print("生成结果与已提交文档存在差异（门禁失败）：")
    print("-" * 68)
    for line in diff[:limit]:
        print(line)
    if len(diff) > limit:
        print("... 另有 %d 行差异" % (len(diff) - limit))
    print()
    print("处置：若差异是代码真值变更 → 运行 --write 同步并复核；")
    print("      若差异非预期 → 先修注释层或生成器，不要直接 --write。")
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="API 字段/枚举层生成器")
    parser.add_argument("--doc", type=Path, default=codesource.DOC)
    parser.add_argument("--annotations", type=Path, default=codesource.ANNOTATIONS)
    parser.add_argument("--bootstrap", action="store_true", help="从现有文档引导注释层")
    parser.add_argument("--check", action="store_true", help="只校验，差异即 exit 1（CI 用）")
    parser.add_argument("--write", action="store_true", help="就地同步文档")
    args = parser.parse_args(argv)

    try:
        lines = args.doc.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        print("读取文档失败：%s" % exc, file=sys.stderr)
        return 2

    regions, context = docparser.parse(lines)
    print("端点小节 %d  枚举表 %d  参数表 %d" % (
        len({r.meta["endpoint"] for r in regions if r.kind == "params"}),
        context["enum_count"],
        context["param_count"],
    ))

    if args.bootstrap:
        return bootstrap(args, lines, regions)

    try:
        data = ann.load(args.annotations)
    except ann.AnnotationsError as exc:
        print("%s" % exc, file=sys.stderr)
        return 2

    try:
        blocking, warnings, code_side = generate(args, lines, regions, data)
    except codesource.SourceError as exc:
        print("%s" % exc, file=sys.stderr)
        return 2

    for item in warnings:
        print("  [提示] %s" % item)
    if warnings:
        print()

    updated = docparser.assemble(lines, regions)

    original_text = "\n".join(lines)
    updated_text = "\n".join(updated)

    if args.write:
        # 写作工具语义：**写入可解析部分**，不因未定性项而拒绝落盘。
        # fail-closed 只属于 --check（CI 门禁）。若在此处也拒绝，则
        # 任何"已验证的子集"都无法单独落地——枚举层会被 100+ 条
        # 尚未定性的参数差异无限期挡住，这是错误的耦合。
        if updated_text != original_text:
            args.doc.write_text(updated_text + "\n", encoding="utf-8")
        written = sum(1 for r in regions if r.replacement is not None)
        print("已同步 %d/%d 个生成区域 -> %s" % (written, len(regions), args.doc))
        if blocking:
            print("仍有 %d 条未定性差异（%d 条须改后端代码），未处理项保持原文："
                  % (len(blocking), len(code_side)))
            for item in (code_side or blocking)[:10]:
                print("  - %s" % item)
            if len(blocking) > 10:
                print("  ... 另有 %d 条" % (len(blocking) - 10))
        return 0

    if blocking:
        print("=" * 68)
        print("阻断项 %d 条（门禁失败）：" % len(blocking))
        print("=" * 68)
        if code_side:
            print()
            print("  ⚠ 以下 %d 条须改【后端代码】，不是改文档：" % len(code_side))
            print("    把它们当文档错来改，等于把 schema 的缺陷固化成契约。")
            print()
            for item in code_side:
                print("  - %s" % item)
            print()
        doc_items = [m for m in blocking if str(m) not in {str(c) for c in code_side}]
        if doc_items:
            print("  以下 %d 条改【文档】即可：" % len(doc_items))
            for item in doc_items:
                print("  - %s" % item)
        return 1

    if updated_text == original_text:
        print("文档与真值一致，无需同步。")
        return 0

    return report_diff(original_text.splitlines(), updated_text.splitlines())


if __name__ == "__main__":
    sys.exit(main())
