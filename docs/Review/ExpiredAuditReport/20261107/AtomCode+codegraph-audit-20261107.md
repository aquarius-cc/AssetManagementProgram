# 全项目 CodeGraph 增强版审计报告（2026-11-07）

> **审计模式**：纯只读，未改动任何业务代码。本报告仅交付问题台账与修复建议；
> 修复执行归 bug-surgical-fix / rigorous-dev 承接。
> **审计依据**：根 `AGENTS.md` v3.7.5 + `Rules_Fiels/` 四规则文件（backend-business v1.23 /
> backend-testing v1.6 / frontend-business v1.5 / frontend-testing v1.8）+ 子仓 AGENTS（BE v9.3.3 / FE v9.9.1）。
> **工作流**：`project-all-code-review` 项目落地版 v1.2.0（五阶段：探索→台账→影响面→报告→自审）。

## 0. 前置检查与基线

| 检查项 | 结果 | 证据 |
|---|---|---|
| codegraph 索引 | `[OK] Index is up to date`：1,063 文件 / 18,902 节点 / 43,231 边 / 71.06 MB | `codegraph status` |
| 索引覆盖（后端） | python 508 文件在索引内 | `codegraph files --filter asset_management_backend` |
| 索引覆盖（前端） | typescript 410 + vue 121 文件在索引内 | `codegraph files --filter vue-assetmanagement/src` |
| 规范读取 | 根 AGENTS v3.7.5 + 四规则文件 + 双子仓 AGENTS + README 已读 | §1.1 读取优先 |
| 基线 HEAD | 后端 `051d714` / 前端 `acffadb` / 根仓 `2145fbe`（均 2026-11-06） | `git log -1` |
| 本地工具链（CT-7） | mypy 2.1.0 / django-stubs 6.1.0 / djangorestframework-stubs 3.18.0 / types-channels 4.3.0.20260518 / pytest 9.1.1 / ruff 0.17.1 — 与 `requirements/dev.txt` 声明一致，本地数字可作结论 | `pip list` |

## 一、项目上下文

### 1.1 技术栈

| 层 | 选型 |
|---|---|
| 前端 | Vue 3.5 + TypeScript + Element Plus 2.10 + Pinia（Setup Store）+ Vite + Vitest + Stryker(vitest-runner) |
| 后端 | Django 6.0 + DRF 3.16 + PostgreSQL 16 + SimpleJWT + drf-spectacular + pytest + mutmut |
| 部署门禁 | GitHub Actions：ci.yml（16 job）+ duplicate-guard.yml + security-scan.yml + ci-cd.yml（部署前置门禁） |

### 1.2 模块边界

**后端**（`asset_management_backend/`）：
- `apps/assetmanagement/` — 资产核心：13 models / 16 selectors / 12 services / 13 serializers / state_machine 包（constants + transitions + core + 4 mixins + contract_fsm）
- `apps/authusermanagement/` — 认证（JWT）；`apps/usermanagement/` — 员工/部门/角色/权限；`apps/unregisteredasset/` — 未登记资产；`apps/notification/` — 通知（HTTP + WebSocket）
- `core/` — 权限（11 类/函数）、部门范围、审计（GenericAuditService）、限流（3 scope + 登录锁定）、信封 schema 后处理器、Excel 导出内核
- `utils/` — `response_utils.success_response`（API 响应唯一入口）、日期/字符串工具

**前端**（`vue-assetmanagement/src/`）：
- `stores/`（32 文件，全 Setup 语法）/ `composables/`（55 文件）/ `views/`（28 文件）/ `components/`（166 .vue）/ `api/`（61 文件，端点唯一定义层）/ `types/`（含 `asset.ts` 8 态枚举单源）/ `utils/`（`Format.ts` 日期、`statusMapping.ts` 状态映射单源）

### 1.3 分域清单（本次审计 6 域）

资产状态机 / 合同状态机 / API 响应契约 / 前端状态枚举 / 测试锚 / 鉴权·操作日志·批量导入（上传）。
图谱外事实（配置、路由、CI 门禁、限流、健康端点）已用 rg/read 补齐，见 §三。

### 1.4 CI 门禁清单（`.github/workflows/ci.yml`）

backend-lint / backend-type-check / backend-complexity / backend-permission-check /
api-schema-check / api-doc-guard / api-doc-generate / backend-test / backend-mutation /
frontend-lint / frontend-type-check / frontend-complexity / frontend-format / frontend-test /
frontend-mutation / ci-summary；另有独立 workflow：duplicate-guard.yml（G-1~G-8 回归护栏）、
security-scan.yml（SC-7/SC-8 依赖审计，权威门禁）、ci-cd.yml（部署前置门禁）。

## 二、问题台账

> 每条固定字段：ID / 级别 / 类型 / file:line / symbol / 描述 / 修复建议 / 回查命令；
> 增补「影响面 / 优先级 / 建议验证方式」三列（阶段 3）。状态：已确认 / 待修 / 不采纳。
> 本报告为纯审计，不产生「已修复」状态。

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 影响面 | 优先级 | 建议验证方式 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AUDIT-001 | P1 | 审计缺失（B7） | `apps/assetmanagement/services/contract_service.py:214,265,474,509` | `add_payment_record` / `add_payment_record_batch` / `delete_payment_record` / `approve_payment_record` | 合同支付记录 4 个写操作（单条添加 / 批量回填 / 软删 / 审批通过）均无审计留痕。方法体逐一核读确认无 `GenericAuditService` 调用（同域 `create_contract:195` / `update_settlement_status:350` / `delete_contract:407` 均有）。批量回填的 add→approve 双写尤其关键：`add_payment_record_batch:270-271` 设计注释自述 approve 应承载「谁批准了这笔付款」的业务控制，但 `paid_record` 结构无 approver 字段且无审计，审批痕迹不可追溯，与注释声明的意图直接矛盾。B7「所有状态变更必须记录操作人、时间、变更前后状态」违规。 | 在 4 个方法的成功写库后补 `GenericAuditService.log_update`（或新增 `log_payment_operation`）：记录操作人、动作（add/approve/delete）、payment_id、金额、状态前后值。方法签名需补 `operator_jobcode` 参数（当前签名无操作人，View 层 `contract_view.py:338,388,396` 从 `request.user` 取 jobcode 下传）；批量路径逐条记或聚合记。 | `codegraph node approve_payment_record` | `codegraph impact approve_payment_record`：8 符号（view `approve_payment:396`、`_add_item:285`、`add_payment_record_batch:265`、tests 4 处）；`delete_payment_record` 8 callers（view `delete_payment:388` + tests） | 高（财务审批审计合规） | 补测试：断言 `approve_payment_record` / `delete_payment_record` 成功后生成 AuditLog 记录（参照 `test_contract_service.py` 既有断言模式）；全量 `pytest --cov-fail-under=80` 绿 | 已确认 / 待修 |
| AUDIT-002 | P3 | 可观测性一致性 | `apps/unregisteredasset/services.py:89-106` | `_safe_call_audit` | 未登记资产域审计写失败容错仅 `logger.warning`（:104），无 `AUDIT_WRITE_FAILED` 指标。core 域同型容错已接线指标告警（`core/audit_service.py:67-70`，M-19），两域口径不一致——本域审计静默失败时无法被监控发现。 | `_run_audit` 的 except 分支补与 core 同型指标递增（AUDIT_WRITE_FAILED，label 带 operation）。 | `codegraph node _safe_call_audit` | `codegraph impact _safe_call_audit`：21 符号（unregisteredasset 域 create/update/approve_and_handle/delete 四动作全路径） | 低 | 单测：模拟审计异常后断言指标递增（参照 core M-19 测试） | 已确认 / 待修 |
| AUDIT-003 | P3 | 流程健壮性 | `apps/notification/services/notification_service.py:99-139` | `_persist_individually` | 通知持久化 bulk 失败降级逐条、2 次重试后死信，仅 error 级完整字段日志 + 「请人工补偿」注释，无死信持久化 / 自动重试 / 告警接线。属显式设计契约（非缺陷），但人工补偿无 SLA 保障。 | 建议（非强制）：死信落表或队列 + 定时重试管理命令；最低要求将「通知持久化失败(死信」关键字接入告警渠道。 | `codegraph node _persist_individually` | `persist_notifications` 的降级路径调用方（bulk 失败场景） | 低 | 测试死信分支告警/落库断言；人工核对死信日志字段完整性（recipient/type/title/message/priority/related 全字段已具备） | 已确认 / 待修 |
| AUDIT-004 | P3 | 文档漂移 | `vue-assetmanagement/src/utils/Format.ts:19` | （模块注释） | 文档行引用旧名 `outassetStatusMapping`（已更名 `ASSET_STATUS_MAP`，全仓该旧名零定义），新维护者会被误导去查不存在的符号。 | 删除旧名引用或更新为 `ASSET_STATUS_MAP`。 | `rg -n "outassetStatusMapping" vue-assetmanagement/src` | 零运行时影响（纯注释） | 低 | 修复后 rg 旧名零命中 | 已确认 / 待修 |
| AUDIT-005 | P3 | 规模预警 | `vue-assetmanagement/src/composables/usePaginationSearch.ts` | `usePaginationSearch` | 199 逻辑行，距 FR-6 红线 200 仅 1 行（FR-6 护栏 `--print` 实测），任何逻辑追加即触发 `[HALT]`。 | 建议预防性拆分：分页状态初始化等非核心部分并入既有 `usePaginationSearchState.ts`（156 行，同域独立文件，语义可承接）。 | `codegraph node usePaginationSearch` | 1 符号（FR-6 护栏清单在列，超限即 CI 红） | 低 | `python scripts/check_frontend_invariants.py --print` composables 段 < 200 | 已确认 / 待修 |

**台账规模**：P0 ×0，P1 ×1，P2 ×0，P3 ×4。全库无阻断级问题。

## 三、分域结论与修复建议

> 排序：级别优先 → 影响面小者先行；同域合并。每条均含 file:line/symbol 去处 + 验证方式。

### 3.1 资产状态机（CT-3 全路径）— 结论：合规，0 未声明旁路

| 检查点 | 结果 | 证据 |
|---|---|---|
| 转换规则表比对 | `VALID_TRANSITIONS`（`transitions.py:32-85`）22 个转换 cell（3+3+4+2+2+2+6）+ 1 终态，与规则文档 §三规则表逐条一致（主代理按规则文档 §三原文逐条比对；reviewer 已核代码侧）：in_store 三分支 / in_use 三出边（`in_use→damaged` 已按 V2.8 决策移除）/ recycled_pending 四出边 / broken 两出边 / repairing 双入口共边 `("repair_failed","to_damaged")`（M-30）/ lost 两出边 / damaged 六出边（approve + 5 条 reject_to_original：broken/lost/in_use/recycled_pending/repairing）/ scrapped `{}` 终态 | `codegraph node VALID_TRANSITIONS` + 源码核读 |
| 声明例外核查 | 3 处直写 `asset_current_status` 全部具前置状态守卫：`unregistered_create_and_recycle:53` 与 `unregistered_create_and_damaged:87`（仅 in_store/空白放行，否则抛 `InvalidTransitionError`）、`force_recycle_from_any:125`（scrapped 终态拒绝） | `state_machine/unregistered.py:25-129` 核读；`transitions.py:9-14` 模块文档声明锚点（M-60） |
| P0-1 回归（FSM 旁路防上膛） | 创建 Serializer 无 `asset_current_status` 写字段（`asset_crud_serializers.py:232`）；List/Detail 全字段 `read_only_fields = fields`（`:85,:133`，[OP-11] 兜底）；Update 显式排除（`:140`）；CombineSearch 仅筛选入参（`:426`） | 源码核读 4 处 |
| 手动改状态路径 | `_run_manual_transition → _transition`（仍经规则表校验），无表外路径 | `codegraph explore` calls 边 |
| 测试锚（CT-3） | `test_state_machine.py` 48 个测试函数 + parametrize 全表遍历：reject 5 原状态逐一回退（`:27-41`）+ 4 非法值兜底 recycled_pending（`:43-48`）+ in_store→broken/lost 显式路径（`:296,:306`）；每条规则表路径至少 1 用例 | 源码核读 |

**结论**：状态机实现、声明例外、Serializer 防旁路、测试覆盖四线全绿，无需修复。

### 3.2 合同状态机 — 结论：合规；合同支付域有 P1（AUDIT-001）

- 8 态单向链与规则文档 §3.1 逐边一致（`contract_fsm.py:31-54`）：每态单出边、`project_finished` 终态空集。
- AUD-15 非法态收敛：`_validate_transition:69-72` 非法 current/target 收敛为 `ContractInvalidTransitionError`（不裸抛 500）；读路径 `allowed_next_states:90-91` 脏数据防御性返回 `[]`（前端据此禁用下拉）。
- 同步约束三处齐全：`_CONTRACT_TRANSITIONS`（事实源）+ `test_contract_fsm.py`（回归锚，`codegraph explore` 确认 10+ 用例含边集比对）+ 规则文档小节。
- **修复（AUDIT-001，P1，唯一 P 级阻断项）**：见 §二台账。去处 `contract_service.py:214,265,474,509` + View 下传操作人 `contract_view.py:338,388,396`；验证方式：补审计断言测试 + 全量 pytest 绿。

### 3.3 API 响应契约（跨端 4 项）— 结论：4/4 合规

| 契约项 | 结果 | 证据 |
|---|---|---|
| 响应根结构 | `success_response`（`utils/response_utils.py:23`）唯一入口，167+ 调用方；全库 `return Response({...})` 唯一命中在 `urls.py:142` 的 **docstring 示例**内（非代码）→ 手写 dict 旁路 0 | `codegraph node success_response`（Trail 163+）+ `grep "return Response\(\{"` |
| 状态枚举键名 | 后端 `AssetState` 8 键（`constants.py:44-51`）与前端 `AssetCurrentStatus` 8 键（`types/asset.ts:47-56`）8/8 一致；`types/outasset.ts:55` 别名 re-export（OP-14 单源收敛） | 双侧源码核读 |
| 分页参数名 | 前端 61 个 api 文件全发 `page`/`page_size`，`pageSize` 零命中；后端接收同名（`contract_view.py:369-370` 等） | 子代理全量 grep |
| 日期格式 | `formatDateTimeFull`（`Format.ts:96-101`）= `new Date(ISO 8601)` 引擎解析（含时区偏移按 ES 规范转本地），无效值返回 `''`；组件内 `new Date(` 旁路扫描仅命中本地月份选择器/问候语构造（非 API 时间）→ 0 旁路 | 源码核读 + 子代理 grep |

### 3.4 安全红线（SC 分流）— 结论：业务代码 0 违规；SC-5/6 N/A

| 规范 | 结果 | 证据 |
|---|---|---|
| SC-1 密钥硬编码 | 业务代码（apps/core/config/utils + 前端 src）0 真实密钥；唯一命中 `schema.py:68 token_prefix="Bearer"` 为 OpenAPI 文档参数非密钥 | `rg` 业务目录限定扫描 |
| SC-3 参数化查询 | 3 处 `cursor.execute` 全部为静态 `SELECT 1` 健康探测（`config/urls.py:70,117` + 测试），无用户输入，无注入面 | `rg` 业务目录限定扫描 |
| SC-5/SC-6 上传安全 | **N/A**：全仓 0 文件上传端点（`request.FILES/FileField/ImageField` 零命中）、0 导入实现（`openpyxl` 仅导出内核 `core/excel_export/` 与测试回读）；QR 码 PNG 为服务端生成下载，非上传 | 子代理全仓 grep |
| SC-7/SC-8 依赖漏洞 | 前端 `npm audit --omit=dev`：**0 vulnerabilities**；后端 pip-audit 本机未装，留痕——以 CI `security-scan.yml` 为权威门禁（近期 CI 42237271531 全绿，含安全扫描分流） | 本次实测 + CI 结论 |
| 限流 | `DEFAULT_THROTTLE_RATES`（`config/settings/base.py:205-211`）：anon 20/min、user 100/min、register 5/min；`LoginLockoutThrottle` 连续失败 5 次锁 15 分钟（`core/throttles.py:100-101`）；`public_scan_view:20` 显式双类声明 | 源码核读 |

### 3.5 可观测性（OC 抽查）— 结论：合规

- **OC-1 trace_id**：`core/request_context.py` / `logging_filters.py` / `json_formatter.py` 全链透传，settings 已接线。
- **OC-3 敏感日志**：业务代码日志调用中 phone/id_card/身份证/手机 0 命中（公开扫码仅记客户端 IP，符合 §4.6）。
- **OC-6 健康端点**：`/health`（DB `SELECT 1` + Redis ping，不健康 503）与 `/ready` 注册于根 urls（`config/urls.py:152-153`）。
- **OC-2 结构化日志**：JSON formatter 在位（`core/json_formatter.py`）。

### 3.6 鉴权与行级隔离（RBAC）— 结论：合规

- 权限类齐备（`core/permissions.py`）：`IsSystemAdmin:98` / `IsDeptManagerOrAbove:111` / `IsAssetAdminOrAbove:125` / `IsSystemAdminOrAssetAdmin:139` / `IsAuditorOrAdmin:154` / `CanExportExcel:177` / `resolve_viewset_permissions:207`（M-09 fail-closed，未登记写 action 收敛 admin 权限）。
- 行级隔离：13 个 ViewSet 覆写 `get_queryset()`（asset/contract/damaged/hard_disk_sn/out/recycle/repair/storage/waste/_lifecycle_base/unregistered/employee/role）；`get_department_codes_for_user`（`core/department_scope.py:47-88`）三态语义正确——superuser→None、**无 Employee→[]（AUD-21 反转已落地 :56-57）**、全局角色→None、dept_manager→本部门+子孙、其余→本部门。
- 读面豁免登记 §4.2.1 三行（departments tree / asset-types / storages）与实现一致。

### 3.7 操作日志与批量导入 — 结论：资产/用户域合规；合同支付域缺审计（AUDIT-001）

- **资产操作日志**：`OperationLogService._insert_operation_log`（`operation_log_service.py:61-97`）失败 **re-raise**（:97）不吞；出库/回收/报废审批抽查 3 路径均带 `AuditLogger.log_*`（out_asset_service.py:86 / recycle_asset_service.py:306 / damaged_asset_service.py:187，strict 模式随事务回滚）。
- **通用审计**：`GenericAuditService` on_commit(robust=True) 延迟写 + 失败指标 AUDIT_WRITE_FAILED（M-19 设计容错）。未登记资产域同型容错缺指标 → AUDIT-002（P3）。
- **批量导入**：不存在（零命中），无逐行校验缺口可查；Excel 导出经 `core/excel_export/` 流式内核。
- **异常吞没抽样**：service 层 5 处 `except Exception` 逐条判读——0 处关键业务路径吞没（1 处 re-raise、2 处降级有兜底、2 处显式死信契约见 AUDIT-003）；吞点全部集中在审计写侧（设计性 + 指标告警）。
- **竞态抽样**：合同支付读-改-写均持行锁（BF-092 `get_contract_for_update`，`contract_service.py:222,238,522`），定向 `update_fields` 保存。

### 3.8 前端质量 — 结论：合规（2 条 P3 预警，见台账）

- **F6/F10/F11**：550 文件 `export default {` 零命中（无 Options API）；32 stores 全 Setup 语法（抽查 + 工厂 `createEntityStore.ts:72` 内部即 Setup）；组件内直接 axios 请求 0（仅 `isAxiosError` 错误分类导入）。
- **F1-F5 设计令牌**：`.vue` 内 `#fff`/`#000` 零命中；唯一硬编码 hex 为 `AssetTypeChildList.vue:33` 的 `var(--table-header-bg, #f5f7fa)` 回退值（合规形态）。
- **覆盖率（CT-2，阈值由 vitest.config 强制，本次 run exit 0）**：TS 层 93.73%（≥80）/ **Store 层 96.83%（≥90）**/ .vue 层 21.19% 语句（≥棘轮基线 12.9，只升不降）；ts+vue 并集 48.96%（信息量，无全局块）。
- **规模（DR-5/FR-5/6/8，护栏 `--print` 权威口径）**：FR-6 composables 55 文件 0 超限（max 199，AUDIT-005 预警）；FR-8 stores 32 文件 0 超限；FR-5 .vue 121 文件 0 超限（template+script 逻辑行 max 318，AssetTypeDetails.vue）。

### 3.9 后端规模与复用（DR/BR）— 结论：合规

- **DR-5/BR-6**：后端 max 484 逻辑行（`asset_view.py`），全库 ≤500，护栏 PASS（`check_file_length_guard.py --print`）。
- **BR-4**：`check_function_length_guard.py` → `[PASS] 0 处超长函数`。
- **DR-6/BR-7 调用链**：抽样 `create_outasset` 调用面 = View→Service→Selector 标准三层（`ensure_employees_in_scope` / `ensure_asset_visible`(selector) / 私有 helper），未见 4 层+ 链；五层架构分层在 codegraph extends/calls 边上全局成立。
- **§1.8 重复代码护栏**：`check_duplicate_invariants.py` → `[RESULT] PASS`（G-1~G-3、G-5~G-8 全绿）。
- **覆盖率（CT-2）**：全量 **2398 passed，整体 89.55%（≥80）**；Service 层专项 **98%（≥90）**（复用本次 run 存盘数据 report，未重跑）。
- **变异测试（T7）**：mutmut 3.x 拒绝 Windows 原生运行（规则明示），本地不执行；权威口径为 CI `backend-mutation` job（CI 42237271531 全绿，双重门禁 ≥80 绝对红线且 ≥ 基线 83.25676365492598）。前端 Stryker 同理走 CI `frontend-mutation`（同批全绿）。

### 3.10 修复批次建议（按「同域合并 → 级别优先 → 影响面小先行」）

| 批次 | 内容 | 依据 |
|---|---|---|
| 批次 A（先） | AUDIT-004（注释 1 行）+ AUDIT-002（1 处指标）+ AUDIT-005（预防拆分）+ AUDIT-003（告警接线） | 4 个 P3，影响面均 ≤21 符号，可一次清干净（DR-1/DR-2 同型归并） |
| 批次 B（后） | AUDIT-001（合同支付审计 4 方法 + View 下传操作人 + 回归测试） | 唯一 P1；跨 Service/View/测试三层，需单独走 bug-surgical-fix 并补审计断言测试（CT-4 回归屏障） |

> 两批次均不涉及跨端契约、状态机主路径、数据库结构——**不触发根 AGENTS.md §1.3 [HALT] 红线**。

## 四、评审结论与台账终态（阶段 5）

**自审执行**：reviewer 角色以独立 subagent 复核本报告（只读、不涉业务代码改动），
置信度阈值 ≥80 才报告。**结果：通过，总体置信度 90/100**。

| 自审项 | 结果 |
|---|---|
| 逐引用回查（台账 5 条 + §三抽查，20 组 file:line/symbol） | 全部一致 |
| AUDIT-001（唯一 P1）四要素 | 证据 / 影响面 / 修复建议 / 验证方式齐全 |
| 结构完整性（§一/§二/§三 + 台账字段） | 齐全 |
| 数字差异 | 1 处（「21 cell」实为 22，damaged 出边表述）——**已修正**（§3.1） |

**无法独立重验清单**（留痕，不计失败）：FR-6 逻辑行 199 以护栏 `--print` 输出为准；
codegraph 命令输出与 CI 结论（run 42237271531、mutation 基线、security-scan）；覆盖率与
2398 passed 为本次本地实测（工具链已对齐 dev.txt，CT-7）。规则文档比对由主代理按 §三/§3.1
原文逐条完成，reviewer 复核代码侧。

**台账终态**：AUDIT-001~005 全部【已确认 / 待修】；无「不采纳」项；
SC-5/SC-6 标【N/A + 理由】（全仓无上传端点、无导入实现）。本审计不产生「已修复」状态，
修复批次 A/B 建议见 §3.10，交接 bug-surgical-fix / rigorous-dev。

## 五、审计票（根 AGENTS.md §4 格式）

[审计票 - 必填项]
- 读取规范：已读 后端/前端 AGENTS & Rules（根 v3.7.5、BE v9.3.3、FE v9.9.1、四规则文件、README）
- CT-1[√] CT-3[√] CT-5[√] CT-7[√] — 核心测试覆盖（Service 98%）/ 状态机全路径（22 cell + 48 测试函数）/ 测试失败阻塞（2398 passed 0 failed）/ 门禁结论已按 dev.txt 工具链复核（pip list 比对一致）
- DR-1[√] DR-5[√] — 业务逻辑唯一实现（重复护栏 G-1~G-8 PASS）/ 文件规模（BE max 484、FE FR-5 max 318，均 ≤500）
- SC-1[√] SC-3[√] — 密钥硬编码业务代码 0 命中 / SQL 注入 0 拼接（3 处静态 SELECT 1）
- 跨端契约：未破坏（4/4：根结构旁路 0 / 枚举 8/8 / 分页 0 混用 / 日期 0 旁路）
- 红线触发：无
- 建议提交：是（仅报告文件 `docs/Review/AtomCode+codegraph-audit-20261107.md`，零业务代码改动）

[审计票 - 自检项]
- 测试：CT-2[√]（整体 89.55% ≥80 / Service 98% ≥90；前端 TS 93.73% ≥80、Store 96.83% ≥90、.vue 21.19% ≥棘轮 12.9，vitest 阈值强制 exit 0）CT-4[√] CT-6[N/A]（纯审计无迁移变更）
- DRY：DR-2[√] DR-3[√] DR-4[√] DR-6[√]（BR-4 0 超长函数；BR-7 抽样三层）
- 安全：SC-2[√]（CI 门禁在位）SC-4[√]（0 动态表/列名）SC-5[~N/A] SC-6[~N/A]（无上传端点/无导入）SC-7[√]（npm audit 0；pip-audit [x] 未执行+原因：本机未装，以 CI security-scan.yml 为权威门禁）SC-8[√]（同 SC-7 分流）
- 可观测性：OC-1~OC-3[√]（trace_id 全链 / JSON 结构化 / 0 敏感日志）OC-4[~] OC-5[~] OC-6[√]（/health + /ready 已注册）OC-7[~]
- AI鲁棒性：AR-1~AR-5[√]（本会话零新增业务代码，无生成物需标注）
- AI行为：Fact-1[√]（reviewer 发现 1 处数字差异，已修正后复核通过）
- 写作风格：Style-1~Style-3[√]
- 覆盖率：整体 89.55%（≥80%）/ 核心 98%（≥90%）；前端 TS 93.73% / Store 96.83%
- **专项补检（本 skill §5）**：状态机旁路 **0** 未声明（3 声明例外均带前置守卫，`unregistered.py:53/87/125`）；契约 4 项 **4/4 通过**；SC 分流：SC-1 零命中 / SC-3 静态 3 处无注入面 / SC-5/6 N/A（无上传无导入）/ SC-8 npm 0 + pip-audit 留痕未执行
