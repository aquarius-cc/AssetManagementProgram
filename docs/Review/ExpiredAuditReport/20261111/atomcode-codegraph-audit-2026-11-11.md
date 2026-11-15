# AtomCode CodeGraph 审计报告（2026-11-11）

> 审计模式：project-all-code-review v1.2.0（纯审计不修复，全程只读）
> 规范基准：根 AGENTS.md v3.7.7 + Rules_Fiels 四份规则（backend v1.26/v1.9、frontend v1.7/v1.9）
> 索引：CodeGraph up to date（1,142 文件 / 19,645 节点 / 45,746 边；py 518 / ts 480 / vue 121）

## §一 项目上下文

| 项 | 内容 |
|---|---|
| 后端 | Django 6.0 + DRF 3.16 + PostgreSQL 16，`asset_management_backend/`，5 个 app（assetmanagement / authusermanagement / usermanagement / unregisteredasset / notification）+ core/ 框架层 |
| 前端 | Vue 3.5 + TS + Element Plus + Vite，`vue-assetmanagement/`（子模块 gitlink），`<script setup>` + Pinia Setup Store |
| 架构分层 | View → Service → Selector（BR-7 ≤3 层），状态机独立层 `state_machine/`，响应唯一入口 `utils/response_utils.py::success_response`（176 callers，全 View 收敛） |
| 分域清单 | 资产状态机（constants/transitions/core/4 mixin）、合同状态机（contract_fsm.py 8 态单向链）、API 响应契约、前端状态枚举（types/asset.ts）、鉴权/操作日志/批量导入、测试锚（test_state_machine.py 等） |

## §二 问题台账

> 级别：P0 阻断/高危、P1 重要、P2 优化、P3 建议。回查命令均可直接执行。

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 影响面 | 建议验证方式 |
|---|---|---|---|---|---|---|---|---|---|
| A-01 | — | 状态机空值兜底 | asset_management_backend/apps/assetmanagement/services/damaged_asset_service.py:219 | `DamagedAssetService._resolve_revert_target` | 【阶段5自审核销，不采纳】诊断初报称空串/None 会 500；复核 FSM 两侧均有兜底：`cancel_damaged`（scrapping.py:71-78 空值→recycled_pending）与 `reject_to_original`（:107 docstring 明示缺失/非法兜底）。无缺陷。 | 无需修复 | `codegraph node cancel_damaged` | — | — |
| A-02 | P2 | 可观测性缺口 | asset_management_backend/apps/assetmanagement/audit.py:350 | audit 装饰器 | `except Exception` 仅 logger.error 后吞掉，审计丢失不阻断主流程；对比 :103 strict 分支有 metric，此处缺 `AUDIT_WRITE_FAILED` 计数（与业务约束 8 的分渠道计数口径不齐） | 补 `AUDIT_WRITE_FAILED` 分渠道计数，与 unregistered_adapter/unregistered_safe_call 同口径 | `codegraph callers audit`（注意同名脚本符号，指定文件路径） | audit 装饰器覆盖的全部 service 方法 | 单测：mock 写日志抛异常，断言计数递增且主流程不抛 |
| A-03 | P3 | 可观测性 | asset_management_backend/apps/authusermanagement/audit_adapter.py:33,49,65；apps/usermanagement/audit_helper.py:27 | 审计适配器 | 注册/登录/登出宽吞仅日志、无指标；低危（与 A-02 同型，归并同批） | 同 A-02 口径 | `codegraph node audit_adapter` | 4 处包装点 | 同 A-02 |
| A-04 | P2 | 前端类型位置（F15） | vue-assetmanagement/src/components/commoncomponents/DashboardStatCard.vue:44；src/components/componentsdetails/detils/detilschildcomponents/SelectedRecordsTable.vue:28 | `StatItem` / `SelectedRecord` | 跨组件导出的 interface 定义在组件内，违反 F15（应放 /src/types） | 迁移至 src/types/*.ts，组件改 import | grep "export interface" src/components | 2 文件 + 各自消费方 | vue-tsc + vitest 通过 |
| A-05 | P2 | DRY 重复类型（FR-2/DR-2） | RecyclableOutAssetsSearch.vue:176 / ScrapableAssetsSearch.vue:164 / WastedAssetsSearch.vue:158 | `SearchForm` | 同一搜索表单接口第 3 份拷贝 | 收敛到 src/types 或共享 composable | grep "interface SearchForm" | 3 组件 | vue-tsc |
| A-06 | P2 | 重复 UI 面（FR-1/DR-2） | src/views/ContactsView.vue:79,88；src/views/NotificationList.vue:204,259；src/views/system/AuthUserManage.vue:42,97；src/views/system/RoleManage.vue:~307 | 页面级 | 4 个页面手写 el-table + el-pagination，绕过 CommonList/SmartListContainer 公共表格面，分页样式逻辑重复 | 按页面差异评估接入 CommonList 的成本，能接则接；不能接的至少收敛分页块 | grep "el-pagination" src/views | 4 页面 | vitest 快照 + 人工 UI 走查 |
| A-07 | P2 | 样式覆盖重复（F12） | AssetTypeForm.vue:252,262 / DepartmentForm.vue:291,303 / StorageForm.vue:279,291 / LogIn.vue:401-410 / CommonList.vue:416-451 | `:deep(.el-input__wrapper…)` | EP 输入框 :deep 覆盖在 3 个表单组件逐字重复（+LogIn、CommonList 分页块），应收敛全局样式文件 | 抽取全局 `.form-input` 覆盖类至 styles/，组件内删除拷贝 | grep ":deep(.el-input__wrapper" | 5 文件 | 视觉走查 + scrollbarTokens 类等值断言模式 |
| A-08 | P3 | 前端类型位置（F15） | ContractForm.vue:246 / DamagedAssetForm.vue:228 / AssetTypeTree.vue:55 / RecyclableOutAssetsSearch.vue 内多处 | 组件内表单契约类型 | 仅组件内消费的表单类型，迁 /src/types 收益一般 | 低优先：随 A-04 同批迁移或保留（组件私有类型不强制） | — | 局部 | vue-tsc |

## §三 分域结论与专项检查证据

### 3.1 状态机（CT-3）— ✅ 无未登记旁路
- `codegraph node VALID_TRANSITIONS`：8 态全表与 `backend-business-rules.md` §三规则表**逐条一致**（in_use 不可直接报废 V2.8、repairing→damaged 双入口共边 M-30、damaged 5 向回退、scrapped 终态空集）。
- 旁路扫描：排除 state_machine/tests/migrations 后，直接写 `asset_current_status` 命中 0 处未登记点。3 处登记豁免均核实：`unregistered.py:56,89,128`（S1 + force_recycle，有前置守卫）、`seed_grouped_assets.py:218`（demo 注入）。
- 路径测试：test_state_machine.py 覆盖 `_validate_transition` 各边（含双入口共边正反用例）；全量 2442 passed。

### 3.2 跨端契约 4 项 — ✅ 全部一致
| 契约项 | 结论 | 证据 |
|---|---|---|
| 响应根结构 | ✅ | `success_response` 176 callers，View 层无手写 dict 旁路（codegraph explore） |
| 状态枚举键名 | ✅ | 后端 AssetState 8 键 = 前端 types/asset.ts AssetCurrentStatus（含注释逐边对齐 V2.8/多态回退） |
| 分页参数名 | ✅ | 后端 `core/pagination.py:34` `page_size_query_param="page_size"`；前端 stores 层发 `page_size`（auditLogStore.ts:47 等；`pageSize` 命中均为 Vue/el-pagination 组件 prop，非 API 参数） |
| 日期格式 | ✅ | `USE_TZ=True` + `TIME_ZONE=Asia/Shanghai`（ISO 8601 +08:00）；前端 M-15 双入口 `Format.ts` 东八区渲染 |

### 3.3 安全红线（SC-1~SC-8）
| 项 | 结论 | 证据 |
|---|---|---|
| SC-1 密钥 | ✅ 未命中 | rg 扫描（排除 md/log/test）0 命中 |
| SC-3 参数化 | ✅ | 仅命中 `config/urls.py:70,117` `cursor.execute("SELECT 1")`（常量无用户输入）；apps 内 .raw(/extra( 0 命中 |
| SC-4 | ✅ | 同上无动态表名/列名拼接 |
| SC-5/SC-6 上传 | N/A | 后端无 FileField/ImageField/multipart 上传端点（grep 全 apps 无命中），上传面不存在 |
| SC-7/SC-8 | 留痕 | 本机 pip-audit 未安装 → 以 CI `security-scan.yml` 为权威门禁（两条豁免登记见根 AGENTS.md §6④）；前端 `npm audit --audit-level=high` **exit 0**（18 个 moderate，均低于 high 门槛） |
| OC-6 | ✅ | `/health` `/ready` 均在 config/urls.py:54,98（含 DB/Redis 探活，503 降级） |

### 3.4 测试与规模（CT-2 / DR-5 / DR-6）
- CT-2 整体覆盖率：**90.28% ≥ 80**（`pytest --cov=. --cov-fail-under=80`，2442 passed，32m50s；本机实测）。CT-7 注：结论基于本机环境，若与 requirements/dev.txt 声明版本漂移则以 CI 为准；mutmut 为 Windows 拒跑项，以 CI backend-mutation 为准。**【2026-11-15 标注：本机实测、非 CI 基线（仲裁 C-2 已关闭）；权威覆盖率以 CI run 的 `$GITHUB_STEP_SUMMARY` 为准——M-21 已固化，绿态 run https://github.com/aquarius-cc/AssetManagementProgram/actions/runs/43623471892 】**
- DR-5/DR-6：`scripts/line_metrics.py` 与 `check_file_length_guard.py --print` 于仓库根执行，无超限条目（BR-6/BR-4 护栏输出尾段全 ok）。
- 前端 FR-6/FR-8：`check_frontend_invariants.py --print` 全 ok（无超限 composable/store）。

### 3.5 语义诊断汇总（后端）
- 事务与通知：✅ `notify_dept_managers` 唯一调用点经 `send_notification_on_commit`（helpers.py:97 有 in_atomic_block 硬守卫）；状态变更 service 均有 `@transaction.atomic` + 关键路径 `select_for_update`。
- 异常吞没：仅 A-02/A-03 两类登记点，无高危吞错。
- 空值风险：A-01 为唯一中置信项；out_asset_service/dashboard_selector 抽查点均有 None 兜底。

## §评审结论（阶段 5 自审）

- 证据可回查：台账每条均含 file:line + 回查命令；专项检查均有命令输出支撑（§3.1~§3.4）。
- P0/P1：**0 条**。P2 共 4 条（A-02/04/05/06/07，A-01 已自审核销），P3 共 2 条，均给出修复建议与验证方式。
- 台账终态：A-02/04/05/06/07 已确认待修；A-08 建议随批处理不强制；A-01 不采纳（自审复核 FSM 兜底完整）。
- 未执行项留痕：mutmut（Windows 平台拒绝，以 CI 为准）；pip-audit（未安装，以 CI security-scan.yml 为权威）；Service 层 90% 专项未逐 app 单跑（整体 90.28% 已含 Service 层实测值高于阈值的间接证据，精确分项以 CI 为准）。
- 只读纪律：本次审计未改动任何业务代码；唯一落盘物为本报告。
