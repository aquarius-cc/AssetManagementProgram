# 批次 8 任务清单（OP-09 方案 A：信封建模 + 幽灵路由清理）

> 前置：用户确认 spec.md（方案 A 定稿，含 G-1/G-2 补入项）后执行。
> 执行纪律：原子提交（路由清理 / 信封后处理器 / 基线重导分开），每项先红后绿，完成后汇报再进下一项。

## 阶段 0：Stage 0 名单报告（阻塞，名单不许手打）
- [ ] T0.1 写临时脚本 `scripts/_op09_report.py`（不提交），对现基线跑 NO_BODY/NON_JSON 分类
- [ ] T0.2 将输出原样粘贴为 `ENVELOPE_NO_BODY_OPERATIONS` / `NON_ENVELOPE_OPERATIONS` 常量草稿；方案 A 下从 delete 名单剔除 dashboard/permissions 两条幽灵 destroy

## 阶段 1：方案 A 幽灵路由清理（原子提交 1）
- [ ] T1.1 `apps/assetmanagement/views/dashboard_view.py:50`：去掉 `ResponseWrapperMixin`，追加 `http_method_names = ["get","head","options"]`
- [ ] T1.2 `apps/usermanagement/views/permission_view.py:34`：追加 `http_method_names = ["get","head","options"]`（保留 mixin 供 list/retrieve）
- [ ] T1.3 新建 `core/tests/test_openapi_envelope_contract.py` 骨架，先写 `test_phantom_crud_routes_removed`（8 个 operationId），未改代码前证红
- [ ] T1.4 重导临时 schema 验证 8 个 operation 消失，证绿；grep 确认前端/测试仍零引用（回归）

## 阶段 2：信封后处理器（原子提交 2）
- [ ] T2.1 新建 `core/envelope_schema.py`：**G-2 复用 `core.schema.ENVELOPE_EXT_NAME`**；`build_envelope_schema` / `build_paginated_data_schema` / `is_enveloped` / `envelope_postprocessing_hook` + T0 名单
- [ ] T2.2 `core/pagination.py:94-118`：`get_paginated_response_schema` 改调 builder（7 分页字段原样 + x-envelope + required）
- [ ] T2.3 `config/settings/base.py` `SPECTACULAR_SETTINGS`（:357 起）追加 `POSTPROCESSING_HOOKS`
- [ ] T2.4 `apps/assetmanagement/views/asset_view.py:543` `qr_code_image` 补 `@extend_schema` image/png 占位
- [ ] T2.5 `permission_view.py` list 显式 `data={count, results:[Permission]}`；`role_view.py:209` UserRoleViewSet list 显式同构
- [ ] T2.6 补齐 9 条护栏用例；先红后绿各一次（临时关 hook 取红 / 回归 QR 取红 / 移出名单取红）
- [ ] T2.7 改 `test_employee_openapi_contract.py:67-79`（statistics 改读 `.data`）、`:136-151`（sort 断言改读 data 内层 array）
- [ ] T2.8 **G-1**：同步 `test_openapi_security_schema.py:9,18` 注释 267→259（确认断言动态遍历无破坏）

## 阶段 3：基线重导 + 规范（原子提交 3）
- [ ] T3.1 根 `conftest.py` 上提 `api_schema` fixture（从 `apps/usermanagement/tests/conftest.py:13`，session 级仍只生成一次）
- [ ] T3.2 重导 `api-schema-baseline.json` + 双跑 diff 无输出
- [ ] T3.3 `Rules_Fiels/backend-business-rules.md:282`（OS-7）改「code/message 不入 schema」条文，补信封护栏要求
- [ ] T3.4 核对基线 diff 落点 = 8 个幽灵 operation 删除 + 信封包裹 + D1 204→200，仅此三类（OS-6）

## 阶段 4：全量门禁
- [ ] T4.1 CT-7 版本对齐（pip list vs `requirements/dev.txt`）
- [ ] T4.2 `pytest core/tests/test_openapi_envelope_contract.py apps/usermanagement/tests/test_employee_openapi_contract.py -v` 全绿
- [ ] T4.3 `pytest --cov=. --cov-fail-under=80`；services ≥90%
- [ ] T4.4 `ruff check . && ruff format --check . && mypy . --strict`
- [ ] T4.5 护栏：`check_file_length_guard.py --print` / `check_duplicate_invariants.py` / `line_metrics.py`（新文件 ≤500 行）
- [ ] T4.6 `spectacular --validate` 双跑一致；量化预期：裸 JSON=0 / 二次信封=0 / 非 JSON 被包=0 / 未分类 2xx 无 body=0
- [ ] T4.7 留痕登记：P1 22 operation 清单、P2 四类 BF（batch-*/token-verify/人类文档/重复 _2 后缀）
- [ ] T4.8 输出根级 AGENTS §4 审计票

## 提交
- [ ] 原子提交 ×3（① 幽灵路由清理+反向护栏 ② 信封后处理器+护栏 ③ 基线重导+规范条文），提交信息注明「OP-09 方案A / OP-09 信封 / OP-09 基线」
