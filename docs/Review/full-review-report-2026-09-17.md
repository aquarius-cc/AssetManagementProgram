# 全量代码审查报告

> 审查时间：2026-09-17 | 审查方式：7 轮分审（code-quality-check skill）
> 审查范围：全项目（asset_management_backend + vue-assetmanagement）
> 审计员：AI Code Quality Check

---

## P0 — 阻断级（2 件）

| # | 文件:行号 | 问题 | 规则 |
|:--|:----------|:-----|:-----|
| 1 | ~~`serializers/asset_crud_serializers.py`~~ ~~+ `services/asset_service.py`~~ | ~~`AssetCreateSerializer` 将 `asset_current_status` 暴露在写入字段集，客户端可 POST `{"asset_current_status":"scrapped"}` 直接创建终态资产，绕过 FSM 全部校验~~ ✅ **已修复 2026-09-17**（详见「修复追踪」） | ~~B5, B9~~ |
| 2 | `services/out_asset_service.py:66-84,215-245` | cancel_outasset 快照只记录出库单的申请人/保管人，未记录出库前资产原值；取消后资产被错误覆写为出库单上的人员而非原始人员，数据不可逆 | B7, 数据完整性 |

## P1 — 严重级（10 件）

| # | 文件:行号 | 问题 | 规则 |
|:--|:----------|:-----|:-----|
| 3 | `selectors/asset_selector.py:73-229` | `get_available_assets`/`search_assets` 等 5 个查询方法未内置行级隔离，完全依赖 View._scoped() 包裹；任何未来 Service 直接调用即泄露跨部门数据 | B12 |
| 4 | `services/recycle_asset_service.py:100-138` | 回收时 is_broken/is_lost 产生二次 FSM 转换（recycled_pending→broken/lost），第二次转换无 `AuditLogger.log_state_change` 审计 | B7 |
| 5 | `services/asset_service.py:358-390` + `views/asset_view.py:314` | `change_outasset_employee`/`transfer_asset_to_storage` 审计记录 operator_jobcode=None，无法追溯操作人 | B7 |
| 6 | `composables/useOutAssetForm.ts:286-289` + `stores/createEntityStore.ts:340` | 编辑外借资产提交时 key 不匹配（payload 用 `asset_recordcode`，store 期望 `recordcode`），更新必定失败 | CT-4 |
| 7 | `components/componentsdetails/detils/AssetBatchImport.vue:146,269` | 组件内直接 `request.post('/assets/assets/batch-create/')` 重复定义已有 API 端点，绕过 unwrapResponse，违反 FR-3 和 F11 | FR-3, F11, B1 |
| 8 | 缺失 `.github/workflows/security-scan.yml` | SC-7 要求 pip-audit/npm audit 依赖漏洞扫描阻断高危合并，CI 尚未配置 | SC-7 |
| 9 | `services/asset_service.py:199-225 vs 267-303` | `delete_asset` 与 `batch_delete_asset` 重复实现同一套删除校验逻辑，且错误码分叉（`IN_USE` vs `ASSET_IN_USE`） | DR-1 |
| 10 | `services/damaged_asset_service.py:138/213/277` | approve/reject/cancel 三处手写 `DamagedAsset.objects.filter(...)` 绕过已有的 `DamagedAssetSelector.get_asset_recordcode_for_update` | DR-3 |
| 11 | `apps/usermanagement/services.py` + `services/` 包 | `usermanagement/services.py`（277 行）与 `services/` 包各存一套 EmployeeService/DepartmentService，因包优先解析 `.py` 版为影子死代码 | DR-1 |
| 12 | `views/asset_view.py`（502 行） | 超过 DR-5 500 行上限，且无 `# TECHNICAL_DEBT` 标注 | DR-5 |

## P2 — 中等级（18 件）

| # | 文件:行号 | 问题 | 规则 |
|:--|:----------|:-----|:-----|
| 13 | `tests/test_state_machine.py` | 5+ 条合法 FSM 路径（outasset、cancel_outasset、cancel_recycle、in_store→broken、in_store→lost）无测试用例 | CT-3 |
| 14 | `tests/` 缺 `test_out_asset_service.py` | 核心 Service 层 out_asset_service 无独立单测文件，仅通过快照/API 测试间接覆盖 | CT-1 |
| 15 | `services/damaged_asset_service.py:51,54` | `DamagedAsset.objects.create` 在 `select_for_update` 之前执行，存在 TOCTOU 并发竞态 | B5 |
| 16 | `views/damaged_asset_view.py:130-150` + `out_asset_view.py:197-203` | update/partial_update 直接传 `request.data` 给 Service，Serializer 仅用于响应而非输入校验 | B8 |
| 17 | `views/_lifecycle_base.py:100-134` | batch_delete 在 View 层含业务循环+错误分类，应在 Service 层实现 | §1.2 |
| 18 | `views/asset_view.py:179,187` | `getassetbyname`/`getassetbyrecordcode` URL 使用 camelCase 而非 plural_snake_case | B2 |
| 19 | `services/damaged_asset_service.py:68` + `serializers/asset_crud_serializers.py:302` | 状态值使用字符串字面量 `"damaged"`/`"in_store"` 而非枚举引用 `Asset.AssetStatus.*` | B9 |
| 20 | `config/settings/base.py:25,196` | `SECRET_KEY` 默认空字符串，误用 base.py 的部署环境 JWT 签名可被伪造 | SC-1 |
| 21 | 13 处后端方法 >50 行 | `batch_delete_asset`(66)、`create_recycle_asset`(85)、`create_outasset`(68)、`approve_asset_recordcode`(58) 等 | BR-4 |
| 22 | 9 处前端 Composable >200 行 | `useOutAssetForm`(358)、`useNotification`(312)、`useDashboardPage`(275) 等 | FR-6 |
| 23 | `stores/createEntityStore.ts`（501 行） | 超 DR-5 上限且无 `TECHNICAL_DEBT` 标注 | DR-5 |
| 24 | 10 处重复 `XxxBatchCreateResult` 接口 | `api/asset.ts`、`outAsset.ts`、`department.ts` 等 10 个文件定义相同形状 | DR-1/DR-4 |
| 25 | `stores/entityStoreTypes.ts:60` vs `types/common.ts:26` | 两套分页响应类型 `ListResponse`/`PaginatedResponse` 并存，Store 映射不一致 | DR-1 |
| 26 | `composables/useExcelExport` / `useOperationLogExcelExport` / `useUserExcelExport` | 三处 Excel 导出流程重复实现，仅列配置不同 | DR-1/FR-2 |
| 27 | 前端 ~80+ 处 `console.error` 无结构化 | catch 块均使用 `console.error('...:', error)`，无 trace_id、无 JSON 格式 | OC-2 |
| 28 | `core/permissions.py:63-80` | 无部门的 dept_manager/asset_admin 角色返回 None → 完全锁定（无任何权限），无测试覆盖此边界 | RBAC |
| 29 | `LoginDialog.vue:16-17` | 用户名/密码 reactive 绑定到 input 但从未提交，死代码或安全隐患 | SC-1 |
| 30 | `views/out_asset_view.py:170-172` | recyclable 未分页时返回裸列表 `data=[...]`，与其他 list 端点 `data={count,results}` 不一致 | §3 |

## P3 — 低级/优化建议（16 件）

| # | 问题摘要 | 规则 |
|:--|:---------|:-----|
| 31 | `broken_lost_repair.py:27` docstring 漏写 `in_use` 源状态 | — |
| 32 | `scrapping.py:131-186` 5 个 `reject_to_*` 方法为死代码 | — |
| 33 | `clear_database.py:130,205` f-string SQL（有白名单缓解） | SC-3 |
| 34 | `development.py:24-27` 弱 dev key 未加入 `_INSECURE_KEYS` | SC-1 |
| 35 | `request_context.py:79-81` 信任 X-Forwarded-For 首值无配置守卫 | SC |
| 36 | `core/constants.py:15-24` 状态枚举与 Model 重复定义 | DR-1 |
| 37 | `asset_service.py:133` 循环内 `import json` | DR-4 |
| 38 | `asset_service.py:337` 访问 FSM 私有方法 `_transition` | AR-1 |
| 39 | `out_asset_view.py:172` recyclable 分页形状不一致 | §3 |
| 40 | `_export_mixin.py:51,69` 无界 queryset 导出有 OOM 风险 | OC-7 |
| 41 | `exception_handler.py:53-78` error_code 未进入单条错误响应 | B1 |
| 42 | `repair_asset_service.py:177,238` 查询未加 `is_deleted=False` | — |
| 43 | `recycle_asset_service.py:348` 调用链 View→Service→Service→FSM=5 层 | BR-7 |
| 44 | `common-forms.scss:11-30` SCSS 重复定义 CSS 变量 | DR-1/F1 |
| 45 | `variables.css` 暗色模式未覆盖 `--gradient-card-*` | F13 |
| 46 | 7 个 composable 无测试（useChartTheme 等） | CT-1 |

---

## 规则符合性矩阵

| 规则 | 状态 | 说明 |
|:-----|:-----|:-----|
| CT-1 | [~] | 核心模块大部分有测试，out_asset_service 缺专用测试 |
| CT-2 | [~] | 整体估计 ≥80%，Store 层 ≥90%，未经 CI 实测 |
| CT-3 | [x] | 5+ 条 FSM 路径无测试（见 #13） |
| CT-4 | [√] | 回归屏障存在（快照测试），但 out-asset edit key 契约未覆盖 |
| CT-5 | [√] | 测试失败阻塞机制存在 |
| CT-6 | [N/A] | 本次审查无迁移文件变更 |
| DR-1 | [x] | 多处重复：删除校验、Selector 绕过、枚举重复、接口重复（#9,#10,#11,#24,#25,#36） |
| DR-2 | [√] | 组件原子化基本合规 |
| DR-3 | [x] | damaged_asset_service 绕过 Selector（#10） |
| DR-4 | [x] | 批量结果接口 10 份重复、Excel 导出 3 份重复（#24,#26） |
| DR-5 | [x] | asset_view.py 502 行、createEntityStore 501 行（#12,#23） |
| DR-6 | [√] | 嵌套层级基本合规 |
| SC-1 | [~] | dev key 弱但有缓解，base.py 默认空串需关注（#20） |
| SC-3 | [√] | 核心查询均参数化，clear_database 有白名单缓解 |
| SC-7 | [x] | CI 未配置依赖扫描（#8） |
| OC-1 | [√] | trace_id 全链路透传 |
| OC-2 | [x] | 前端 ~80+ 处 console.error 无结构化（#27） |
| OC-3 | [√] | 后端日志脱敏，前端有泄露风险（#43） |
| OC-6 | [√] | /health /ready 端点已实现 |
| AR-1~AR-5 | [√] | AI 鲁棒性整体合规 |

---

## 统计

| 严重级别 | 数量 |
|:---------|:-----|
| P0 | 2 |
| P1 | 10 |
| P2 | 18 |
| P3 | 16 |
| **合计** | **46** |

## 建议修复优先级

1. **立即修复**（P0）：FSM 绕过（#1）、cancel 数据完整性（#2）
2. **本迭代修复**（P1）：行级隔离加固（#3）、审计补全（#4,#5）、前端 edit key 修复（#6）、重复代码收敛（#9,#10,#11）
3. **下迭代规划**（P2）：DR-5 拆分（#12,#23）、BR-4 函数拆分（#21）、FR-6 composable 拆分（#22）、CI 依赖扫描（#8）
4. **持续改进**（P3）：前端结构化日志（#27）、死代码清理（#31,#32）、暗色模式补全（#45）

---

## 修复追踪

| # | 修复日期 | 改动文件 | 措施 | 验证 |
|:--|:---------|:---------|:-----|:-----|
| 1 | 2026-09-17 | `serializers/asset_crud_serializers.py` `AssetCreateSerializer` | ① 从 `Meta.fields` 移除 `asset_current_status`；② 移除 `extra_kwargs` 中的字符串默认值 `"in_store"`；③ 类 docstring 标注状态归 Service 注入（防回归） | — |
| 1 | 2026-09-17 | `services/asset_service.py` `create_asset` | 防污染拷贝 `dict(asset_data)` 之后、批量循环之前，注入 `asset_data["asset_current_status"] = Asset.AssetStatus.IN_STORE`（枚举引用，满足 B9） | — |
| 1 | 2026-09-17 | `tests/test_services.py` | ① `test_create_asset` 增加 DB 断言；② 新增 `test_create_asset_forces_initial_status`（传 `"scrapped"` → 落库 `in_store`，含调用方 dict 防污染断言）；③ 批量用例断言全部 `in_store` | `pytest test_services.py` 8 passed |
| 1 | 2026-09-17 | `tests/test_asset_view_api.py` | ① `test_create_asset` 移除状态字段并增加 DB 断言；② 新增 `test_create_asset_ignores_status_field`（POST `scrapped` → 201 + DB `in_store`） | `pytest test_asset_view_api.py` 32 passed |

**修复设计决策**：CreateSerializer 未加 `StrictUnknownFieldMixin`，未知字段采用「静默忽略 + Service 强制兜底」（与 Update 侧显式 400 区分）。依据：前端 create/import 链路均未实际提交该字段（已静默丢弃），保守策略最安全。

**验证结果**：全量 655 passed；Service 层覆盖率 94.23%（≥90%）；`ruff check` 通过；`api-schema-baseline.json` 已重导出（create 端点写字段移除）。
