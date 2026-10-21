# CodeGraph 全量审计报告 — 2026-10-15

> 模式：全量五阶段 | Skill：project-all-code-review v1.2.0 | 性质：只读审计（唯一写入为本报告）
>
> 审计对象：`asset_management_backend`（HEAD 9fe6746）+ `vue-assetmanagement`（HEAD 06653d6）
> 两子仓未提交改动列为高危区优先精查。CodeGraph sync up-to-date（969 文件 / 17,155 节点 / 38,539 边），未执行 `codegraph generate`。
> 上轮报告 `docs/Review/CodeReview20261014.md` 结论未豁免，已全量重审比对。
>
> 路径缩写：后端省略 `asset_management_backend/`，前端省略 `vue-assetmanagement/src/`。
> **v2（2026-10-16）**：已融合 R2 增补轮（`codegraph-audit-2026-10-15-r2.md`）——继承 13 条待修项逐条复核均未修复（12 条原样命中）；
> P2-04 范围经 reviewer 自审订正由 5 处扩为 **9 处**；新增 P2-08（BR-4 函数超长）。
> R2 中 P2-05 行号误记为 :16（path 行），基线 :23 为准，未采纳。
> 终态统计：**P1 待修 ×3 / P2 待修 ×8 / P3 待修 ×3 / 不采纳 ×6**。
> **v3（2026-10-17）**：P3-01 ~ P3-04 三批次执行完毕并全部标记已修复（活账本 BF-101）；此前 P1/P2 各条修复见修复追踪（BF-096 ~ BF-100）。上行 v2 统计为其发布时点快照，不作回溯改写。

## §一 验证记录

| # | 命令 / 检查 | 结果 | 处置 |
|---|---|---|---|
| 1 | 后端 `pytest`（含覆盖率） | 1916 passed；整体 87.06%（≥80）；services 层 contract_service 93%、多模块 100%（≥90） | 通过（CT-1/CT-2） |
| 2 | 前端 `npx vitest run --coverage` | 167 文件 2183 passed；stores 97.63%（≥90），无阈值报错 | 通过（CT-2） |
| 3 | `ruff check`（后端） | 0 错误 | 通过 |
| 4 | `mypy --strict` | 本地 1.15.0 与 `dev.txt` 声明 2.1.0 漂移；按 CT-7 以 CI 同版本结论为准（CI：0 errors / 220 files），本地数字不作基线 | 通过（CT-7，本地漂移已标注） |
| 5 | `eslint` + `vue-tsc` | 0 错误 | 通过 |
| 6 | `npm audit` | exit 1；8 漏洞：dev `shell-quote` critical 1 + high 7（含 prod `vue` 3.5.34 XSS advisory、prod `source-map-js` 1.2.1） | 登记 P2-07（SC-7），以 CI `security-scan.yml` 为权威门禁 |
| 7 | `pip-audit` | 本地两轮失败（GBK 编码异常 + 隔离 venv PyPI 超时） | 未取得本地结论；按 skill 兜底条款以 CI 权威留痕，不再重试 |
| 8 | `codegraph status` / `sync` | up-to-date，无索引漂移 | 通过 |
| 9 | （R2）两子仓 `git status` / `diff --stat` | 后端 25 文件 / 前端 63 文件未提交（高危区，与基线一致；含 P1-01/02/03 缺陷文件） | 逐条复核前提；**建议尽快分批落盘，否则门禁结论与工作区脱节** |
| 10 | （R2）基线 13 条待修项 file:line 逐条 grep | 12 条原样命中（未修）；P2-04 范围由 5 处扩为 9 处（grep 口径补全 `page_size: <store>.pagination.total` 写法） | 见 §二各条「复核证据」 |
| 11 | （R2）状态机直写旁路扫描（`asset_current_status =` / `contract_status =`） | 命中均为 filter/模型定义/管理命令，无服务层直写旁路 | 通过（CT-3 旁路维度） |
| 12 | （R2）裸 `return Response(` 契约入口扫描 | 唯一命中 `apps/assetmanagement/urls.py:142` 为 docstring 示例，非真实端点 | 通过 |
| 13 | （R2）SC-1 密钥 / SC-3 裸 SQL 扫描 | 均 0 命中（排除测试/空串） | 通过 |
| 14 | （R2）SC-5/6 上传链路 | 全后端 apps/+core/ 无 FileField/InMemoryUploadedFile/upload 命中 → 不适用 | 通过（留痕） |
| 15 | （R2）OC-6 健康端点 | `config/urls.py:54 health_check`（DB+Redis，200/503）在位 | 通过 |
| 16 | （R2）跨端契约补扫 | 前端 `api/*.ts` 无 `pageSize` 驼峰混用；日期 iso-8601 前后端一致 | 通过 |
| 17 | （R2）`check_file_length_guard.py`（仓库根执行） | BR-6 PASS（0 超长文件，最大 `asset_view.py` 475/500） | 通过 |
| 18 | （R2）`check_function_length_guard.py`（仓库根执行） | **BR-4 FAIL**：`repair_asset_service.py complete_repair()` 53 逻辑行 > 50，未登记豁免 | **新增 P2-08** |
| 19 | （R2）CT-3 资产状态机测试 | `test_state_machine.py` 36 用例，路径覆盖通过 | 通过（合同 FSM 缺口继承 P2-06） |

> 覆盖率（CT-2）/ ruff / mypy / eslint / vue-tsc：R2 轮 HEAD 未动未重跑，以基线 §一 #1-8 结论继承
> （后端 1916 passed 87.06%；前端 2183 passed；静态门禁 0 错误）。未提交改动落盘后应由下一轮审计复跑全部门禁。

## §二 缺陷台账

### P1（3 条）

| ID | 级 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 终态 |
|---|---|---|---|---|---|---|---|---|
| P1-01 | P1 | ~~状态机旁路 + 审计缺失~~ | `apps/assetmanagement/serializers/base_model_serializers.py:201-243`；`apps/assetmanagement/views/contract_view.py:123-133` | `ContractUpdateSerializer`；`ContractViewSet.perform_update` | `contract_status` 可写（在 fields:223、不在 read_only:243）。前端 `views/.../ContractForm.vue:394` 编辑恒提交该字段 → 生产路径上 8 个合法状态间任意跳转均被接受：不过 `ContractFSM.transition`、无 `GenericAuditService.log_update`（仅 LoggingMixin logger.info 不落库）、状态变更不触发 `_recalc_paid_amounts` 致 `amount_unpaid` 滞留旧口径。正规 FSM 入口 `update_settlement_status` 前端零调用（死端点）。违反 B7 状态流转审计规则与 BF-092/I-10 约定 | `perform_update` 检测 `contract_status` 变更时改路由 `ContractService.update_settlement_status`（FSM+审计+重算一次收齐），或将该字段设 read_only、流转仅走专用 action | `codegraph explore "ContractUpdateSerializer perform_update"`；回归：PUT 改状态断言 `log_update` 被调、非法跳转抛 `INVALID_CONTRACT_TRANSITION` | ✅ **已修复 2026-10-16**（详见「修复追踪」+ 活账本 BF-096） |
| P1-02 | P1 | ~~跨端契约错位~~ | `apps/notification/views.py:22-55`；`views/NotificationList.vue:68-79`；`stores/notificationStore.ts:46-48` | `notification_list`；`fetchNotifications` | 后端仅识别 `limit`（默认 20、钳 100）与 `is_read`，返回裸数组；前端发送的 `page/page_size/notification_type/priority/keyword` 全部静默丢弃；store 数组分支 `pagination.total = data.length` → 分页 UI 失效、>20 条通知不可见、四类筛选全死。违反根级 §3 分页参数契约 | 后端对齐 `CustomPageNumberPagination` 并支持 type/priority/keyword 过滤、返回 `{count, results}`；或前端裁剪为 limit 模式并移除假分页 UI（两端同步） | `rg -n "page_size|limit" apps/notification/views.py`（当前仅 limit） | ✅ **已修复 2026-10-17**（详见「修复追踪」+ 活账本 BF-097；limit 参数已移除） |
| P1-03 | P1 | ~~数据一致性（陈旧值可提交）~~ | `views/RecycleAssetView.vue:152-174` | `watch(asset)`；`canSubmit` | watch 无精确匹配出库单时仅 warning、**不清空** `recyclableRecordcode`（全文件无 `= ''` 重置）；`storage_code` 亦仅空时回填（:156）同样残留 → 从「有出库单资产 A」切到「无出库单资产 B」后 `canSubmit` 仍 true，提交将使用 A 的出库单 + 残留 A 仓库，对错误出库单创建回收记录 | watch 无匹配分支补 `recyclableRecordcode.value = ''`；`storage_code` 随 asset 变更重置 | 组件测试：加载 A（有单）→ 切 B（无单）→ 断言 `canSubmit === false` 且 `submitFn` 拒绝 | ✅ **已修复 2026-10-16**（详见「修复追踪」+ 活账本 BF-096） |

### P2（10 条，其中 P2-09/P2-10 为 2026-10-17 批修预核查新发现）

| ID | 级 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 终态 |
|---|---|---|---|---|---|---|---|---|
| P2-01 | P2 | ~~审计字段污染~~ | `apps/unregisteredasset/services.py:195`；`apps/unregisteredasset/audit_adapter.py:156-206` | `_log_approve_audit` | `operator_jobcode` 传入 `Employee` 实例，落库为 `str(Employee)`=姓名 → `AssetOperationLog.operator_jobcode` 列存姓名不存工号，按工号过滤/检索该类审批日志全部失配。对照组 `apps/assetmanagement/views/damaged_asset_view.py:164` 传 `auth_username`（正确）→ 仅未登记审批路径污染。mypy 不报（`approver_employee: Any` + `_safe_call_audit` 动态 getattr 双重绕过）；测试无断言 | `operator_jobcode=approver_employee.employee_jobcode`，姓名走 `operator_name`；补回归测试断言 `log_operation` 收到字符串工号 | `rg -n "operator_jobcode=approver_employee" apps/unregisteredasset/services.py` | ✅ **已修复 2026-10-17**（详见「修复追踪」+ 活账本 BF-097） |
| P2-02 | P2 | ~~OpenAPI schema 漂移~~ | `apps/assetmanagement/views/contract_view.py:193-211` vs `services/contract_service.py:307-309` | `update_settlement_status` | schema/inline_serializer 与错误提示声明 choices `["pending","settled"]`，实现按 `Contract.CONTRACT_STATUS_CHOICES`（8 状态，`models/contract.py:26-34`）校验 → 文档宣称取值全部被拒 `INVALID_CONTRACT_STATUS`；前端零调用（死端点 + schema 漂移） | schema choices 改为 8 状态常量；修 schema 后重导出 `api-schema-baseline.json`（§3 M-3 要求） | `python manage.py spectacular --format openapi-json --file api-schema-baseline.json --validate` | ✅ **已闭·实证 2026-10-17**（73d6415 批：`contract_view.py:230` 现用 `Contract.CONTRACT_STATUS_CHOICES` 8 态常量，schema 漂移消除） |
| P2-03 | P2 | ~~限流绕过 + 注释不符~~ | `apps/authusermanagement/urls.py:22-24`；`apps/authusermanagement/views.py:65-66,172` | `AuthUserViewSet`（create） | DefaultRouter 未限 actions → `POST /auth/users/` 亦开放注册（AllowAny），仅挂全局匿名 20/min，而 `/auth/register/` 为 `RegisterRateThrottle` 5/min → 注册限流口径绕过；urls 注释「仅注册 list/retrieve/update/delete」与实现不符。`RegisterSerializer` S8 校验在位，无提权 → 不及 P1 | `router.register(..., actions=[...])` 排除 create，或 create 挂 `RegisterRateThrottle`；订正注释 | `rg -n "RegisterRateThrottle|router.register" apps/authusermanagement/` | ✅ **已修复 2026-10-17**（create 前插 RegisterRateThrottle + urls 注释订正 + 4 用例，详见「修复追踪」+ 活账本 BF-098） |
| P2-04 | P2 | ~~导出截断（已知遗留同型）~~ | `components/componentsdetails/` 下 9 处：`AssetContentDetails.vue:436`、`ContractDetails.vue:394`、`DamagedAssetDetails.vue:421`、`WasteAssetDetails.vue:224`、`AuditLogDetails.vue:223`（`total.value \|\| 1000` 变体）、`HardDiskSNDetails.vue:408`、`OutAssetDetails.vue:364`、`RecycleAssetDetails.vue:373`、`UnregisteredAssetDetails.vue:351`；钳制源 `core/pagination.py:33-35` + `core/constants.py:12` | `fetchAllData` → `page_size: total` | **9 处**（R2 reviewer 自审订正，基线原判 5 处系 grep 口径不完整漏 `page_size: <store>.pagination.total` 写法）客户端导出残留 → `max_page_size=100` 静默钳制 →「导出全部」截断 100 条。BF-092/I-1 账本已知遗留（上批仅迁移 4 个生命周期页；操作日志/员工两域已改服务端导出 `useOperationLogExcelExport`/`useUserExcelExport`），交叉引用不重复立账 | 迁移至 `useServerExcelExport`（生命周期页已有先例） | 导出 >100 行数据集断言行数；`rg -n "page_size:.*pagination\.total\|page_size: total" components/componentsdetails/`（R2 复核仍命中 9 处） | ✅ **已修复 2026-10-17**（后端 3 导出端点 + Damaged pending 覆写 + AuditLog 流式导出 + 前端 9 组件迁 exportFromServer，详见「修复追踪」+ 活账本 BF-099） |
| P2-05 | P2 | ~~RBAC 前后端口径不一致~~ | `router/routes-main-system.ts:23`；`components/AsideMenu.vue:93`；`apps/assetmanagement/views/operation_log_views.py:63`（对照矩阵 `Rules_Fiels/backend-business-rules.md:146`） | `operationlogdetails` 路由守卫 | 前端 `requiredMinRole:'auditor'` 拦截 regular_user，但 RBAC 矩阵 :146 允许 regular_user 查看本部门操作日志、后端 `_scope_by_user` 亦放行 → 三处口径互斥：regular_user 菜单可见（AsideMenu:93 无条件显示）、点击被拒、API 却允许 | 二选一并同步矩阵：守卫降为 regular_user，或菜单按权限隐藏 | 对照三处 `rg -n "operationlogdetails\|requiredMinRole\|_scope_by_user"` | ✅ **已修复 2026-10-17**（守卫降级对齐矩阵，详见「修复追踪」+ 活账本 BF-097） |
| P2-06 | P2 | ~~测试缺口（CT-3 违规）~~ | `apps/assetmanagement/state_machine/contract_fsm.py:26-68` | `ContractInvalidTransitionError`；`ContractFSM.transition` | `ContractInvalidTransitionError` / `INVALID_CONTRACT_TRANSITION` 测试目录零匹配；7 条合法转移仅 `purchasing→purchase_finished` 被测（`test_contract_service.py:105`、`test_contract_view_api.py:155-163`）。CT-3 要求状态机每条流转路径至少一个集成用例。R2 复核：tests/ 源码仍 0 命中（仅 stale `__pycache__` 编译残留，疑为补测后又删） | 补全路径集成测试：7 条合法转移 + 非法跳转分支各至少 1 用例 | `rg -n "INVALID_CONTRACT_TRANSITION|ContractInvalidTransitionError" apps/assetmanagement/tests/` | ✅ **已闭·实证 2026-10-17**（随 BF-096 P1-01 批闭合：`test_contract_view_api.py:431/:439/:505` 非法跳转 + CT-3 七边全路径集成断言命中） |
| P2-07 | P2 | ~~依赖漏洞（SC-7）~~ | `package.json` / `package-lock.json`（前端子仓） | `npm audit` | 8 漏洞：dev `shell-quote` critical 1 + high 7，含 prod `vue` 3.5.34 XSS advisory、prod `source-map-js` 1.2.1。BF-067 曾双 audit 归零，此后 advisory DB 新增所致，零代码变更；CI `security-scan.yml` 可能转红 | `npm audit fix` / 升级 `vue`；以 CI 为权威门禁复核 | `npm audit --json`（证据：`Temp/opencode/npmaudit.json`） | ✅ **已修复 2026-10-17**（shell-quote critical + vue XSS + source-map-js 归零；braces 上游无补丁仅 dev 链，CI 改 `--omit=dev` 经用户批准，详见「修复追踪」+ 活账本 BF-100） |
| P2-08 | P2 | ~~规模红线（DR-5 / BR-4）（R2 新增）~~ | `apps/assetmanagement/services/repair_asset_service.py:166` | `RepairAssetService.complete_repair` | 护栏实测 53 逻辑行 > 50 上限（BR-4 FAIL），且未在 BR4 函数长度台账登记豁免。影响面小：调用方为 `test_repair_service_gaps.py`（约 15 处）+ `test_asset_lifecycle.py`（3 处）+ 1 个 view 入口 | **必须拆分**（BF-058 教训③：新增超限一律拆分不得豁免）：将通知构造与操作日志写入抽为私有方法（`_build_complete_notification` / `_write_complete_log`），主函数降至 ≤50 行 | `python scripts/check_function_length_guard.py`；拆分后重跑 BR-4 护栏 + 上述两测试文件全绿 | ✅ **已闭·实证 2026-10-17**（73d6415 批已拆出 `_write_complete_log`；BR-4 护栏 2026-10-17 复跑 PASS、0 超限） |
| P2-09 | P2 | 信封误解析（批修预核查新发现，2026-10-17） | `composables/useNotification.ts:104-114`；`api/notification.ts:27`；`types/notification.ts:38-42` | `fetchNotifications`；`getNotifications` | `unwrapResponse`（`api/request.ts:536-542`）返回 `res.data` 内层载荷，但 useNotification 按信封解析 `res.data` → 运行时 `data` 为 undefined → `data.results` 抛 TypeError 被 catch 吞为 fetchError → **铃铛面板 REST 拉取在生产恒失败**（列表仅靠 WS unshift 维持，NotificationBell 挂载于 AsideMenu）；spec 以 `{data:[...]}` envelope mock 替换整个 getNotifications（连 unwrap 一起换）→ mock 与生产分叉、测试恒绿；返回类型 `Promise<NotificationListResponse>` 为类型级双层包裹谎言。同批更正：`limit` 的真实调用方即此文件（原「零调用方」判断有误） | 解析改与 notificationStore 同构双分支 + 传 `page_size` + 返回类型改 `Promise<NotificationItem[] \| NotificationPaginatedData>` + 删孤儿 `NotificationListResponse` 与 `limit?` 字段 + 3 处 spec mock 对齐载荷形状 | `npx vitest run src/composables/__tests__/useNotification.spec.ts`；`rg -n "unwrapResponse" src/api/request.ts` | ✅ **已修复 2026-10-17**（详见「修复追踪」+ 活账本 BF-097） |
| P2-10 | P2 | 同型信封误解析·未读计数（2026-10-17 登记，同日批准补修） | `composables/useNotification.ts:131-136`；`api/notification.ts:46-48` | `fetchUnreadCount`；`getUnreadCount` | 与 P2-09 同型：`res.data.count` 中运行时 `res` 已是 `{count:n}` 载荷 → `res.data` undefined → TypeError 被 `catch { // ignore }` 静默吞 → **`unreadCount` 初始恒 0**，NotificationBell 徽标仅靠 WS `++` 与本地 `--` 维护，刷新后不准。`markAllRead`/`markRead` 返回类型同为信封谎言但消费端只 `await` 不解引用 → 无运行时影响 | 1 行：`res.data.count` → `res.count`；`UnreadCountResponse` 类型改载荷形状；spec 2 处 envelope mock 对齐 | `rg -n "res.data.count" src/composables/useNotification.ts` | ✅ **已修复 2026-10-17**（同日获批准补修，详见「修复追踪」+ 活账本 BF-097） |

### P3（4 条）

| ID | 级 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 终态 |
|---|---|---|---|---|---|---|---|---|
| P3-01 | P3 | ~~序列化缺陷~~ | ~~`core/excel_export/workbook.py:68`~~ | ~~`coerce_excel_value`~~ | ~~`return coerce_excel_value(value) or ""` 将 0/False 转空串，导出数值/布尔列丢 0~~ ✅ **已修复 2026-10-17**（详见「修复追踪」） | 改判空逻辑仅对 `None` 生效（`if value is None: return ""`） | 单测：导出含 0 值列断言保留 `0` | ✅ **已修复 2026-10-17**（详见「修复追踪」；活账本 BF-101） |
| P3-02 | P3 | ~~死代码 / 注释漂移~~ | ~~`types/employee.d.ts:62`；`stores/createEntityStore.ts:156`~~ | ~~`pageSize`（类型）~~ | ~~死类型字段 `pageSize` 与注释漂移，无运行时影响~~ ✅ **已修复 2026-10-17**（详见「修复追踪」） | 删除死类型、订正注释 | `rg -n "pageSize" types/employee.d.ts` | ✅ **已修复 2026-10-17**（详见「修复追踪」；活账本 BF-101） |
| P3-03 | P3 | ~~UI 优雅降级（显示瑕疵）~~ | ~~`utils/statusMapping.ts:46-54`；`components/commoncomponents/StatusTag.vue`~~ | ~~`OUTASSET_STATUS_MAP`~~ | ~~映射仅 4 键、StatusTag 无 default slot → 未知出库状态显示原始值 + logWarn（降级不崩溃）~~ ✅ **已修复 2026-10-17**（详见「修复追踪」） | 补全映射键或加 default slot | 组件测试：传未知 status 断言降级展示 | ✅ **已修复 2026-10-17**（枚举扩 8 + 别名收敛，详见「修复追踪」；活账本 BF-101） |
| P3-04 | P3 | ~~UX 改进（P1-01 收口遗留交互项，2026-10-16 立项）~~ | ~~`apps/assetmanagement/state_machine/contract_fsm.py:31-54`；`components/componentsdetails/detils/ContractForm.vue:127-129,394`~~ | ~~`_CONTRACT_TRANSITIONS`；`ContractForm` 状态下拉~~ | ~~P1-01 收口后后端已强校验，但编辑态状态下拉仍列出全部 8 态，用户选非法下一状态须**提交后**才收到 400（`INVALID_CONTRACT_TRANSITION`，`notifyApiError` 会展示 message），报错链已通仅交互不友好。BF-096 人工决策本轮「仅后端收口、前端状态下拉不收紧」；DR-1 禁止前端复制第二份 FSM，故单独立项~~ ✅ **已修复 2026-10-17**（详见「修复追踪」） | **后端下发单源**：合同详情 GET 响应新增 `allowed_next_states`（由 `ContractFSM._CONTRACT_TRANSITIONS` 计算，合法下一状态唯一来源），前端下拉按其过滤；终态 `project_finished` 返回空数组 → 下拉禁用。**需重导出 `api-schema-baseline.json`**（响应新增字段，根级 §3 M-3 非破坏性变更） | 后端：详情响应断言 `allowed_next_states` 等于该态出边、终态为空数组；前端：组件测试断言下拉仅渲染合法下一状态 | ✅ **已修复 2026-10-17**（schema 已重导，详见「修复追踪」；活账本 BF-101） |

### 不采纳（6 条，附裁决理由）

| ID | 线索 | 裁决理由 |
|---|---|---|
| N-01 | 域B「export_excel 权限口径不一致」 | **误报**：`core/permissions.py:204-205` `resolve_viewset_permissions` 对所有走该函数的 ViewSet 统一返回 `CanExportExcel`；逐一核实 asset/contract/damaged/lifecycle/out/repair/waste/recycle/asset_type/hard_disk/grouped 全覆盖，operation_log 导出显式声明（`operation_log_views.py:156`）→ 无缺口 |
| N-02 | damagedassetdetails 白名单排除 asset_admin | **正确**：RBAC 矩阵 `backend-business-rules.md:142` 报废审批 asset_admin ❌ |
| N-03 | AssetAdmin 后台直改 `asset_current_status` | **线索无效**：assetmanagement 无 admin.py（仅 authusermanagement/usermanagement 有） |
| N-04 | guards 层级「非单调」（asset_admin 缺报废审批） | **非缺陷**：符合矩阵 :142，asset_admin 本就无此权限 |
| N-05 | 未登记 handlers S1/S2/S3 缺 AssetOperationLog | **已有覆盖**：approve 路径经 `_log_approve_audit→log_approve` 写操作日志（含 asset_code/handle_type）；仅 operator_jobcode 字段污染另立 P2-01 |
| N-06 | 回收页双 toast | **已修复**：`stores/recycleAssetStore.ts:56` `disableAutoMessage: true`（codegraph 直证，含 BF 注释） |

## §三 影响面、优先级与评审结论

### P1 影响面（codegraph impact / callers 直证）

| ID | 影响面 | 优先级 | 建议验证方式 |
|---|---|---|---|
| P1-01 | `ContractUpdateSerializer` 仅被 `ContractViewSet.update/partial_update` 消费；前端编辑表单恒提交 → **真实生产路径非死代码**，影响全部合同 PUT/PATCH。数据完整性 + 审计合规双违规 | 立即（本批最高） | 集成测试：改状态后查 `AuditLog` before/after + `amount_unpaid` 重算；非法跳转 400 |
| P1-02 | `notification_list` 仅 urls.py 2 处引用、零测试；影响通知列表页全部交互，`unread_count`/`mark_read`/`mark_all_read` 独立端点不受影响 | 本迭代（需前后端同步改） | 后端断言 page/page_size 生效；前端组件测试筛选回显 |
| P1-03 | `recyclableRecordcode` 单视图唯一消费；触发条件为同页切换资产编码或重试加载；局部缺陷不外溢 | 立即（修复成本极低，一行清空） | 见 P1-03 回查命令列组件测试 |

### 优先级路线

1. **立即**：P1-01、P1-03（✅ **已修复 2026-10-16**，详见「修复追踪」与活账本 BF-096；原「三案涉改文件均在未提交改动中」的合并风险已随工作区落定解除）。
2. **本迭代**：P1-02、P2-01（一行修复 + 回归）、P2-02（schema 重导出）、P2-05（三处口径统一）、P2-06（CT-3 补测）、P2-08（BR-4 护栏 FAIL，必须拆分）。
3. **计划**：P2-03、P2-04（9 处，复用 useServerExcelExport 先例）、P2-07（CI 权威，升级依赖）。
4. **低优**：P3-01 ~ P3-04（✅ **已修复 2026-10-17**，三批次执行完毕，详见「修复追踪」与活账本 BF-101；P3-03 枚举方案 A、P3-04 后端下发 `allowed_next_states` 单源方案均按立项落地）。

### 分域结论（R2 增补轮）

| 分域 | 结论 | 证据 |
|---|---|---|
| 资产状态机 | **健康**：无服务层直写旁路；`test_state_machine.py` 36 用例 | §一 #11、#19 |
| 合同状态机 | **缺陷集中区**：P1-01（序列化层旁路）+ P2-02（schema 漂移）+ P2-06（测试缺口）三案同源——流转缺统一收口，修复建议按同域归并一次清干净（DR-1） | 基线 §二 + R2 复核 |
| API 响应契约 / 跨端契约 4 项 | **健康**：无裸 Response 真实端点；响应根结构/枚举键名/分页参数/日期格式均一致 | §一 #12、#16 |
| 安全红线 | SC-1/SC-3 零命中；SC-5/6 不适用（无上传链路）；SC-8 以 CI 权威（P2-07） | §一 #13-14 |
| 规模红线 | BR-6 文件护栏通过（最大 475/500）；BR-4 函数护栏 FAIL 1 处（P2-08） | §一 #17-18 |
| 未提交改动 | **高危区**：后端 25 文件 / 前端 63 文件未提交，含 P1-01/02/03 缺陷文件。建议尽快分批落盘，否则门禁结论与工作区实际状态脱节 | §一 #9 |

### 交叉引用

- P2-04 为 BF-092/I-1 已知遗留同型点（账本已标注「8+ 同型点未迁移」），R2 复核订正为剩余 **9 处**，**不重复立账**。
- P2-07 与 BF-067（曾双 audit 归零）关联：advisory DB 后增，零代码变更。
- P2-08 适用 BF-058 教训③（新增超限一律拆分不得豁免）。
- RBAC 比对基准：`Rules_Fiels/backend-business-rules.md:135-149`（§4.2/4.3 矩阵）。

### 评审结论

无 P0。存量主要风险集中在**合同状态机旁路（P1-01）**与**跨端契约漂移（P1-02 / P2-02 / P2-05）**。核心资产状态机（AssetFSM）路径与测试完整、未发现旁路；ContractFSM 存在测试缺口（P2-06）。静态门禁与测试全绿，npm audit 为唯一 SC 违规（P2-07，CI 权威）；BR-4 函数护栏 FAIL 1 处（P2-08）。R2 增补轮独立复核结论：继承 13 条待修项 file:line 全部可回查命中、无虚构，置信度 ≥95%；本融合报告为只读审计产物，未改动任何业务代码。

## 修复追踪

| ID | 日期 | 文件 / 区域 | 措施 | 验证 |
|---|---|---|---|---|
| P1-01 | 2026-10-16 | `apps/assetmanagement/views/contract_view.py` `ContractViewSet.perform_update`（:124-154） | 检测 `contract_status` **实际变更**（`vd.get != instance.contract_status`）时先 `pop` 该字段，改路由 `ContractService.update_settlement_status`（行锁 + `ContractFSM.transition` + `_recalc_paid_amounts` + `GenericAuditService.log_update` 一次收齐，DR-1 不写第二份流转逻辑），与其余字段同处一个 `transaction.atomic()`：非法跳转由 `AppValidationError(INVALID_CONTRACT_TRANSITION)` 抛 400 且整事务回滚；`serializer.instance.refresh_from_db()` 保证响应为 FSM 写入后的真实状态 | `python -m pytest apps/assetmanagement/tests/test_contract_view_api.py -q` → **36 passed**；`python -m pytest -q` → **1934 passed**；`python -m ruff check .` / `--select C90` → 0；`python -m mypy . --strict` → **Success, 226 files** |
| P1-01 | 2026-10-16 | 同上 `_save_editable_fields`（:156-160） | 状态未变更路径抽为私有方法，保留 BF-092/I-10 的「`settlemented_price` 变更触发 `recalculate_amounts_for_update`」语义，避免 `perform_update` 分支膨胀（DR-5/BR-4） | 同上；`test_put_without_status_field_is_plain_edit` / `test_put_same_status_skips_transition_audit` 直证 |
| P1-01 | 2026-10-16 | `apps/assetmanagement/tests/test_contract_view_api.py` `TestPutContractStatusRouting`（:364-506） | 新增 5 用例：①合法流转路由 Service + 状态审计 + `amount_unpaid 7000→5000` 重算；②非法跳转 400 + `error_code=INVALID_CONTRACT_TRANSITION` + `contract_name` 未落库（回滚）；③不含状态字段的纯编辑不触发审计；④同状态提交跳过路由与审计；⑤**CT-3 全路径**——PUT 逐边走完 7 条合法转移并断言 7 条状态审计，终态 `project_finished` 再流转 400 | 同上 36 passed / 全量 1934 passed（CT-3 补齐，部分闭合 P2-06） |
| P1-03 | 2026-10-16 | `vue-assetmanagement/src/views/RecycleAssetView.vue` `watch(asset)`（:153-179，身份基线 `lastAssetCode` :98） | 入口做 `asset_code` 身份比对：**跨资产切换**清空 `recyclableRecordcode` 并把 `storage_code` 重置为新资产的 `asset_storage_code ?? ''`；**同资产重载**保留用户已选仓库、仅空时回填；`await searchRecyclable` 后复核 `asset.value?.asset_code !== current.asset_code` 直接 return，拦截快速切换时上一次晚到响应写回陈旧单号 | `npx vitest run src/views/__tests__/RecycleAssetView.spec.ts` → **10 passed**；**先红后绿**：`git checkout --` 还原旧 watch 后新用例 **3 红**（`ST-001≠ST-002`、竞态 disabled undefined）1 过，恢复修复后 10/10 绿 |
| P1-03 | 2026-10-16 | `vue-assetmanagement/src/views/__tests__/RecycleAssetView.spec.ts`（`switchAsset` helper :183，新用例 :307/:324/:343/:353） | 新增 helper（重置 mock + 点 `.retry-btn` 同实例切换资产）与 4 用例：A→B 清残留且 `canSubmit=false`、提交被拦截（`createRecycleMock` 零调用）；A→B→A 往返后出库单与仓库恢复为 A（重置不误伤正常路径）；切换后 `storage_code` 为 B 的 `ST-002`；A 的晚到响应不写回、提交保持禁用 | 同上；全量 `npx vitest run` → **167 文件 2187 passed**；`npm run type-check` / `format:check` / `eslint`（裸 + `--fix`）→ 全 0；`npm run test:coverage` → exit 0（ts 80 / stores 90 / .vue 基线棘轮分层阈值达标） |
| P1-02 | 2026-10-17 | `apps/notification/selectors.py`（新建）`NotificationSelector.list_for_user`（:47） | 过滤链收敛 Selector（DR-3）：`recipient_jobcode` 身份约束 + `is_read` 逐字迁移自旧 view；新增 `notification_type`/`priority` 精确匹配与 `keyword` icontains（参数化，SC-3） | `python -m pytest apps/notification -q` → 全绿；`mypy . --strict` → Success, 227 files |
| P1-02 | 2026-10-17 | `apps/notification/views.py` `notification_list`（:39）+ `_serialize_notification`（:22） | 移除 M-1 `limit` 参数与裸数组返回（BF-095 该语义作废）；接 `CustomPageNumberPagination`（`page` 缺省时兜底 page=1 恒出信封，对齐 `operation_log_views.py:133-141` 范式）；响应改 7 键信封；`_serialize_notification` 抽 helper 与列表/详情共用（DR-1） | 15 用例：信封 7 键断言、默认 20 条、第 2 页、page_size、钳 100、`page=abc`→404、limit 被忽略锚、四类过滤、跨用户隔离，全绿 |
| P1-02 | 2026-10-17 | `core/pagination.py:39` `paginate_queryset` | 返回注解 `object \| None` → `list[Any] \| None`（收窄以删 View 侧多余 `type: ignore[no-any-return]`，CT-7 工具链复核） | `mypy . --strict` → Success, 227 files（无 unused-ignore 报错） |
| P1-02 | 2026-10-17 | `api-schema-baseline.json:10052` | `/api/v1/notifications/` GET description 定点同步（该端点 responses.200 无 response schema，结构 diff=0，属非破坏性文档对齐） | `python manage.py spectacular --format openapi-json --file api-schema-baseline.json --validate` → exit=0；baseline vs 重导出结构比对 diff=0 |
| P1-02 | 2026-10-17 | `apps/notification/tests/test_notification_views.py`（:42 `TestNotificationListPagination`、:118 `TestNotificationListFilters`） | 重写 15 用例（删 3 条 limit 旧锚）：401 鉴权、信封结构、分页语义、过滤矩阵、跨用户隔离 | `python -m pytest apps/notification -q` → 全绿；全量 **1947 passed** |
| P1-02 / P2-09 | 2026-10-17 | `vue-assetmanagement/src/composables/useNotification.ts` `fetchNotifications`（:106）+ `api/notification.ts:27` + `types/notification.ts` | P2-09：`res.data` 信封误解析改为与 `notificationStore` 同构双分支（数组/对象直取载荷），铃铛 REST 列表恢复可用；`page_size` 替代已删 `limit`（真实调用方即此文件，更正「零调用方」误判）；返回类型改 `Promise<NotificationItem[] \| NotificationPaginatedData>`；删孤儿 `NotificationListResponse` 与 `limit?` 字段 | `npx vitest run src/composables/__tests__/useNotification.spec.ts` → 全绿；`npm run type-check` → 0 |
| P1-02 | 2026-10-17 | `stores/__tests__/notificationStore.spec.ts:75` + `composables/__tests__/useNotification.spec.ts` | `{limit:3}` → `{page, page_size:3}` 参数锚；新增 30 条第 2 页用例（信封对象分支）；useNotification 3 处 envelope mock 改生产载荷形状（mock 与 unwrapResponse 现实对齐） | 全量 `npx vitest run` → **167 文件 2188 passed** |
| P2-01 | 2026-10-17 | `apps/unregisteredasset/services.py` `_log_approve_audit`（:196） | `operator_jobcode=approver_employee`（实例）→ `(approver_employee.employee_jobcode if approver_employee else None)`；姓名仍走 `operator_name`（`Employee.__str__`=employee_name，实例入 CharField 即污染根因） | **先红后绿**：还原 bug 行 → `test_approve_audit_log_records_jobcode_not_name` FAILED；恢复 → 绿 |
| P2-01 | 2026-10-17 | `apps/unregisteredasset/tests/test_services.py:251` | 新增回归用例：断言 `log_operation` 收到字符串工号而非姓名（堵 `_safe_call_audit` 吞异常的盲区） | `python -m pytest apps/unregisteredasset -q` → **143 passed** |
| P2-05 | 2026-10-17 | `vue-assetmanagement/src/router/routes-main-system.ts:25` | `operationlogdetails` 守卫 `requiredMinRole: 'auditor'` → `'regular_user'`（对齐 RBAC 矩阵 `backend-business-rules.md:146` 与后端 `_scope_by_user`；AsideMenu:93 菜单本就无条件显示，三处口径统一）+ 指向矩阵注释 | `npx vitest run src/router/__tests__/guards.spec.ts` → **72 passed** |
| P2-05 | 2026-10-17 | `vue-assetmanagement/src/router/__tests__/guards.spec.ts:863` | 双锚新用例：直接 import `routesMainSystem` 断言真实路由 meta（防「回改 auditor 而旧测试仍绿」空转）+ 守卫放行断言 | 同上 72 passed；`npm run type-check` → 0 |
| P2-10 | 2026-10-17 | `types/notification.ts` `UnreadCountResponse`（:56-58） | 信封形状 `{code, data: {count}, message}` → 载荷形状 `{count: number}`（`unwrapResponse` 已剥外层信封，对齐真实返回；类型级谎言清除） | `npm run type-check` → 0 |
| P2-10 | 2026-10-17 | `composables/useNotification.ts` `fetchUnreadCount`（:134）+ `useNotification.spec.ts`（:38-39、:526-527） | `res.data.count` → `res.count`（1 行）；3 处 mock 信封形状改载荷（getUnreadCount ×2 + markAllRead ×1，对齐 `notificationStore.spec` 既有载荷形状） | **先红后绿**：mock 改后旧代码 FAILED（`unreadCount` 0≠3，生产吞异常行为复现）→ 改 1 行后 37 绿；全量 **167 文件 2189 passed**；coverage exit=0 |
| P2-03 | 2026-10-17 | `apps/authusermanagement/views.py` `AuthUserViewSet.get_throttles`（:74-82） | create 前插 `RegisterRateThrottle()`（AnonRateThrottle 子类 scope=register，匿名 5/min/IP；已认证不受误伤）+ urls.py 注释订正 | `python -m pytest apps/authusermanagement/tests/test_create_throttle.py -q` → **4 passed**；auth 域 **87 passed**；ruff/mypy --strict/schema validate 全绿 |
| P2-04 | 2026-10-17 | `apps/assetmanagement/views/hard_disk_sn_view.py:29`、`apps/unregisteredasset/views.py:77`、`apps/assetmanagement/views/damaged_asset_view.py:97`（get_export_queryset 写死 pending）、`core/audit_log_views.py:175` + `core/audit_log_filters.py` + `core/audit_query_service.py` | HardDiskSN/UnregisteredAsset 挂 ExportExcelMixin + export_columns；DamagedAsset export 覆写 pending；AuditLogExportView（IsAuditorOrAdmin、7 参数、8 列）+ 共享 parser（DR-1）；schema 重导 3 新路径入基线 | 12 新用例 + 58 回归 + 全量 **1963 passed**；ruff 0；mypy --strict **Success 228 files**；`spectacular --validate` exit=0 |
| P2-04 | 2026-10-17 | `vue-assetmanagement`：9 api 文件 + 9 store 文件（`xxxExportExcel` 中转，满足 no-restricted-imports）+ 9 组件（HardDiskSN/UnregisteredAsset/OutAsset/RecycleAsset/WasteAsset/Contract/DamagedAsset/AssetContent/AuditLog） | 「导出全部」迁 `exportFromServer`（保留「导出当前页」客户端 exportToExcel）；AuditLog 带当前筛选；Damaged params={}；`useAssetLifecycleActions` 存量 6 处未动 | type-check / lint / format:check 全 0；vitest **167 文件 2189 passed** |
| P2-07 | 2026-10-17 | `vue-assetmanagement/package.json`（vue 3.5.44、@vue/server-renderer 3.5.44）+ `package-lock.json` + `.github/workflows/security-scan.yml:134`（`--omit=dev`，经用户批准） | `npm audit fix` 修 shell-quote critical + source-map-js；升级 vue 修 XSS；braces 上游无补丁仅 dev 链 → CI 改 `--audit-level=high --omit=dev`，报告步骤保留全量 `--json` | `npm audit --audit-level=high --omit=dev` → **found 0 vulnerabilities, exit 0**；type-check 0；vitest 2189 passed |
| P3-04 | 2026-10-17 | `asset_management_backend/apps/assetmanagement/state_machine/contract_fsm.py:76` | 新增 classmethod `allowed_next_states()`（未知值防御返回 `[]`），由 `_CONTRACT_TRANSITIONS` 计算合法下一状态，**唯一数据源**（DR-1） | `python -m pytest apps/assetmanagement/tests/test_contract_fsm.py -q` → **22 passed**；ruff / mypy --strict 全绿 |
| P3-04 | 2026-10-17 | `asset_management_backend/apps/assetmanagement/serializers/base_model_serializers.py:169,185,204-206` | `ContractDetailSerializer` 加 `allowed_next_states = SerializerMethodField()` + 入 `fields`（:185）+ `get_allowed_next_states` 委托 FSM；`read_only_fields = fields` 自动覆盖 → **仅 GET 下发、PUT/PATCH 不可写** | `test_contract_view_api.py:510 TestAllowedNextStatesField`（出边参数化 3 点 / 终态 `[]` / settlement 连带 / PUT 响应不含字段口径锁定）+ `test_contract_fsm.py:20`；全量 **1985 passed** |
| P3-04 | 2026-10-17 | `asset_management_backend/api-schema-baseline.json:15608,15733` | schema 重导出（响应新增非破坏性字段，根级 §3 M-3） | `python manage.py spectacular --format openapi-json --file api-schema-baseline.json --validate` → **exit 0**（`allowed_next_states` 2 处入基线） |
| P3-04 | 2026-10-17 | `vue-assetmanagement/src/types/contract.ts:155` + `detils/ContractForm.vue:285,299` + `detils/__tests__/ContractForm.spec.ts:99` | Contract 加 `allowed_next_states?: string[]`；`statusOptions` computed 按下发出边过滤、终态空数组 → 下拉禁用（:299）；`loadContractDetail` 字段缺失回退 `getById`（陈旧缓存窗口靠后端 400 兜底）；新建 5 测试组件 | vitest `ContractForm.spec` → **5 passed**；全量 167 文件 2194 passed；type-check / lint / format:check 全 0 |
| P3-01 | 2026-10-17 | `asset_management_backend/core/excel_export/workbook.py:62,73` | `resolve_cell_value` 判空改「`coerce_excel_value` 后仅 `None → ""`」，0/False 保留；docstring 同步订正 | **先红后绿**：`test_write_export_workbook_preserves_zero_and_false`（`core/tests/test_excel_export.py:168`）先证红；文件 **30 passed**；全量 **1987 passed**（`test_unknown_path_404` 首轮失败 → 单跑 14 passed + 复跑全量绿，环境性抖动如实标注） |
| P3-02 | 2026-10-17 | `vue-assetmanagement/src/types/employee.d.ts`（已 `git rm`）+ `src/stores/createEntityStore.ts:156` | 删除零引用死类型文件（终核 `rg "types/employee"` → EXIT=1）；分页 docstring 订正为只读 `page/page_size` | `npm run type-check` → 0；vitest 全量绿；`check_frontend_invariants.py` → **PASS** |
| P3-03 | 2026-10-17 | `vue-assetmanagement/src/types/outasset.ts:48-55` + `src/utils/statusMapping.ts:48` | `OutAssetCurrentStatus` 扩 8 值（方案 A，用户拍板）；`OUTASSET_STATUS_MAP = ASSET_STATUS_MAP` 别名收敛（DR-1）；头注释删不存在的 `outassetStatusMapping`、枚举注释值订正 `recycled_pending` | **先红后绿**：`statusMapping.spec.ts` `toHaveLength(4)→8`（:191/:204）+ 别名 `toBe` 断言 + 8 态 property + unknown fallback 断言 |
| P3-03 | 2026-10-17 | `vue-assetmanagement/src/components/componentsdetails/detils/outAssetBatchImport.config.ts:66` + `__tests__/outAssetBatchImport.config.spec.ts:98` + `detils/OutAssetBasicDetails.vue:16` | 导入 `validStatuses` 走 `Object.values` 自动受益 8 态；spec 补「新增 4 态在导入校验入口合法」回归锚（用户复核修订②）；StatusTag 无 slot → 删死 children（同文件 `:165` `getAssetStatusText` 活用与 import 保留） | vitest 对应 spec 绿；全量 **168 文件 2196 passed**；type-check / lint / format:check 全 0 |

**P1-01 / P1-03 验证结果小结**

- 后端：`pytest` 全量 **1934 passed**；整体覆盖率 **87.12%**（≥80）、Service 层 **98.24%**（≥90）；`ruff` / `C90(≤10)` / `mypy . --strict`（本地 mypy 2.1.0 = `requirements/dev.txt` 声明版本，CT-7 已复核）均 0；`check_function_length_guard.py`（BR-4）/ `check_file_length_guard.py`（BR-6）/ `check_duplicate_invariants.py` / `check_frontend_invariants.py` 全 PASS。
- 前端：`vitest` 全量 **167 文件 2187 passed**；type-check / format:check / eslint / 分层棘轮覆盖率全绿。
- **契约与 schema**：`ContractUpdateSerializer` 的 fields（:223）与 read_only（:243）清单**未改动**（人工决策：状态写入由 Service 定向收口，而非把字段设为 read_only），API 响应根结构、状态枚举、分页参数、日期格式均未变 → **无需重导出 `api-schema-baseline.json`**；实测结构比对（剥除全部 `description` 后 JSON 全等）零漂移，本机 `spectacular` 重导出产生的 113 行差异经核实全为 zh-hans gettext 本地化回退，基线文件未提交任何改动。
- **变异测试门禁**：后端 `mutmut`（≥80 且 ≥ 基线 83.2567）与前端 `stryker`（≥80）**未在本地执行**（人工决策：留待 push 后由 CI `backend-mutation` / `frontend-mutation` 阻断 job 取证），本条按 Fact-1 如实标注为未运行。
- 修复登记：`docs/BugFixed/Bug修复活账本.md` **BF-096**（本表与该条目双向交叉引用）。

**P1-02 / P2-01 / P2-05 / P2-09 验证结果小结**

- 后端：`pytest` 全量 **1947 passed**；整体覆盖率 **87.13%**（≥80）、Service 层 **98.24%**（≥90）；`ruff` / `C90(≤10)` / `mypy . --strict` → **Success, 227 files**（CT-7：以 `requirements/dev.txt` 声明版本工具链复核）；BR-4 / BR-6（最大 `asset_view.py` 475/500）/ `check_duplicate_invariants.py` / `check_frontend_invariants.py` 全 PASS。
- 前端：`vitest` 全量 **167 文件 2188 passed**；type-check / format:check / eslint（裸 + `--fix`）/ `test:coverage`（分层棘轮阈值）全绿。
- **契约与 schema**：`GET /api/v1/notifications/` 响应由裸数组改为分页对象 `{count,total_pages,page,page_size,next,previous,results}`（外层信封包裹），属根级 §3 分页契约对齐；OpenAPI 结构 diff **0**（改前快照 vs 改后、baseline vs 改后两组比对，剥除 description 后全等），仅 view docstring description 变化 → `api-schema-baseline.json:10052` **定点 1 行**同步（写入时 CRLF 归一），`spectacular --validate` exit=0。根结构 `code/data/message`、状态枚举、日期格式未变。
- **变异测试门禁**：后端 `mutmut`（≥80 且 ≥ 基线 83.2567）与前端 `stryker`（≥80）**未在本地执行**（留待 push 后 CI `backend-mutation` / `frontend-mutation` 阻断 job 取证），本条按 Fact-1 如实标注为未运行。
- 修复登记：`docs/BugFixed/Bug修复活账本.md` **BF-097**（本表与该条目双向交叉引用）；新发现 **P2-10**（unread-count 同型信封误解析）同日获批准补修（1 行 + 类型 + 3 处 mock，先红后绿），已闭合并入本小结；前端终值 **167 文件 2189 passed**。

**P2-03 / P2-04 / P2-07 验证结果小结**

- 后端：`pytest` 全量 **1963 passed**（CT-5 零失败）；`ruff check .` / `--select C90` → 0；`mypy . --strict` → **Success, 228 source files**（CT-7：以 `requirements/dev.txt` 声明版本工具链复核）；`spectacular --validate` exit=0（3 新 export 路径入基线，`--omit=dev` 不影响后端）。
- 前端：`vitest` 全量 **167 文件 2189 passed**；type-check / lint / format:check 全 0；`npm audit --audit-level=high --omit=dev` → **found 0 vulnerabilities, exit 0**。
- **契约与 schema**：3 个新导出端点（harddisk-sn/export、audit-logs/export、unregisteredassets/export）入 `api-schema-baseline.json`，validate exit=0；根结构 `code/data/message`、状态枚举、分页参数、日期格式未变 → 跨端契约未破坏（新增非破坏性，M-3 已重导）。
- **变异测试门禁**：后端 `mutmut`（≥80 且 ≥ 基线 83.2567）与前端 `stryker`（≥80）**未在本地执行**（留待 push 后 CI `backend-mutation` / `frontend-mutation` 阻断 job 取证），本条按 Fact-1 如实标注为未运行。
- 修复登记：`docs/BugFixed/Bug修复活账本.md` **BF-098**（P2-03）、**BF-099**（P2-04）、**BF-100**（P2-07，本表与三条目双向交叉引用）。
- **CI 权威复核直证（2026-10-17，活账本 BF-102）**：P2-07 `--omit=dev` 门禁触发路径 run `39050296550` job 级 success（npm audit + 汇总双绿）；降噪路径 run `39048461356`（audit 双 skipped + 汇总不误红）；附带修复同轮 CI ruff format 红（run `39045715708`，本批引入 3 文件）并全绿复跑（run `39050296530`，含后端变异 83.9012% / 前端变异 82.11 双门禁直证）；twisted 新 CVE（CVE-2026-106454，上游无修复版本）经批准点名豁免。

**P3-01 / P3-02 / P3-03 / P3-04 验证结果小结**

- 后端（P3-01 + P3-04）：`pytest` 全量 **1987 passed**（CT-5 零失败；P3-01 批首轮 `test_unknown_path_404` 失败 → 单跑 14 passed + 复跑全量绿，环境性抖动如实标注）；`ruff check .` / `--select C90` → 0；`mypy . --strict` → **Success**（CT-7：以 `requirements/dev.txt` 声明版本工具链复核）；`spectacular --validate` exit=0（`allowed_next_states` 2 处入基线，M-3 非破坏性新增已重导）。
- 前端：`vitest` 终值 **168 文件 2196 passed**（批1 时点 2194，批3 增 statusMapping 改造 + 导入回归锚后 2196）；type-check / lint / format:check 全 0；`check_frontend_invariants.py`（FR-6/FR-8）→ **PASS**；`ContractForm.vue` 物理 489 行 < FR-5 红线 500。
- **契约与 schema**：合同详情 GET 响应**新增** `allowed_next_states`（非破坏性，M-3 已重导 `api-schema-baseline.json`）；`ContractUpdateSerializer` 的 fields/read_only 清单未动、新字段经 `read_only_fields = fields` 自动只读，PUT/PATCH 不可写（测试口径锁定）；API 根结构 `code/data/message`、状态枚举键名、分页参数、日期格式均未变 → 跨端契约未破坏。
- **变异测试门禁**：后端 `mutmut`（≥80 且 ≥ 基线 83.2567）与前端 `stryker`（≥80）**未在本地执行**（留待 push 后 CI `backend-mutation` / `frontend-mutation` 阻断 job 取证），本条按 Fact-1 如实标注为未运行。
- 修复登记：`docs/BugFixed/Bug修复活账本.md` **BF-101**（P3-01~P3-04 四项三批次批修，本表与该条目双向交叉引用）。
- **注释债（登记不入批）**：`src/utils/Format.ts:19/:22` 同型 `//` 位置注释漂移（skip/register 语义与实际不符），零运行时影响，按用户复核修订③ 不入本次批，挂账待下轮注释清理统一处置；`statusMapping.ts` 中 4 键缺失历史（`in_store`/`broken`/`repairing`/`lost` 曾不显示）已随方案 A 消除。

---

## AGENTS.md §4 审计票

```markdown
[审计票 - 必填项]
- 读取规范：已读 根级 + 后端/前端 AGENTS & Rules（含 backend-business-rules §4.2-4.3 RBAC 矩阵）
- CT-1[√] CT-3[x] CT-5[√] CT-7[√]
  - CT-1：核心业务逻辑（状态机/Selector/鉴权）测试覆盖已核（后端 1916 passed、前端 2183 passed；R2 补核资产 FSM 36 用例）
  - CT-3：存量缺口已登记 P2-06（ContractInvalidTransitionError 零测试、6/7 合法转移未覆盖）；非本次引入，审计已履行核查义务
  - CT-5：无失败测试（全量绿）；R2 轮新增 BR-4 护栏 FAIL 已登记 P2-08（护栏为规模门禁非测试门禁，不触发 CT-5 阻塞）
  - CT-7：ruff/eslint/vue-tsc/vitest 本地通过；mypy 本地版本漂移（1.15.0 vs 声明 2.1.0），以 CI 同版本结论（0 errors）为准，本地数字不作基线
- DR-1[√] 无业务逻辑新增；DR-5[√] 本报告 <500 行（存量超限函数已登记 P2-08，非本报告文件）
- SC-1[√] SC-3[√] 无密钥硬编码、无 SQL 拼接（R2 双扫描 0 命中）
- 跨端契约：未破坏（审计本身不改契约；发现的契约问题已登记 P1-02 / P2-02 / P2-05）
- 红线触发：无 [HALT]
- 建议提交：是（仅本报告文件 docs/Review/codegraph-audit-2026-10-15.md；R2 原文件可归档或保留为过程记录）

[审计票 - 自检项]
- 测试：CT-2[√] 整体 87.06%（≥80）/ 后端 services ≥90 / 前端 stores 97.63%（≥90）；CT-4[√]（只读审计无代码修复；回归缺口已随 P1/P2 登记）；CT-6[√]（无迁移）
- DRY：DR-2[~]（P2-04 遗留同型点已交叉引用账本）DR-3[√] DR-4[√] DR-6[√]
- 安全：SC-2[√] SC-4~SC-8[√]（SC-7 见 P2-07 已登记，CI 权威；SC-5/6 不适用已留痕）
- 可观测性：OC-1~OC-3[√] OC-4[~] OC-5[~] OC-6[√] OC-7[~]（QPS 未达阈值豁免；R2 补核 /health 在位）
- AI鲁棒性：AR-1~AR-5[√]（无猜测补全；验证命令均实际执行，失败项如实留痕）
- AI行为：Fact-1[√]（结论均附 file:line / 回查命令；pip-audit 失败未编造结论；R2 融合前逐条独立复核，P2-05 行号错误已剔除）
- 写作风格：Style-1~Style-3[√]
- 覆盖率：整体 87.06%（≥80%）/ 核心 services ≥90%、stores 97.63%（≥90%）
```
