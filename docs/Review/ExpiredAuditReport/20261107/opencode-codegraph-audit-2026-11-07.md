# 全项目审计报告（CodeGraph 增强版）

> 审计日期：2026-11-07 | 审计执行：opencode（主代理 + 5 个 explore/general 子代理）
> 模式：**纯审计，不修复**（审计 skill v1.2.0）。全程只读，未改动任何业务代码。
> 索引：`codegraph status` 已就绪（524 文件索引覆盖前后端）。规范基线：根 AGENTS.md v3.7.5（系统提示注入版）、backend-business-rules.md v1.23、backend-testing-rules.md v1.8、frontend-business-rules.md v1.5、frontend-testing-rules.md v1.8、重复代码活账本 complete-patterns.md。
> 触发技能：/code-reviewer /code-quality-check /code-explorer /ponytail /ponytail-audit /ponytail-review

---

## §一 项目上下文与分域结构报告

### 1.1 技术栈与架构

| 端 | 技术 | 分层 |
|---|---|---|
| 后端 | Django 6.0 + DRF 3.16 + PostgreSQL 16 + SimpleJWT + drf-spectacular | Model → Selector → Service → Serializer → View（五层铁律） |
| 前端 | Vue 3.5 + Element Plus 2.10 + Pinia 3 + Vite + Vitest 4 | 组件 → Composables → Store(createEntityStore 工厂) → API 层 → 后端 |
| 治理 | mutmut 83.26% 基线、Stryker vitest-runner、五护栏脚本 + CI 门禁、契约基线 api-schema-baseline.json（OP-09 信封全包） | — |

### 1.2 本次按域逐个探索的分域清单与结论索引

| 分域 | 图谱锚点 | 结论 |
|---|---|---|
| 资产状态机 | `state_machine/transitions.py`、`constants.py`、`core.py`、4 mixins | ✅ 22 条边与规则文档零漂移；旁路 8 处（已登记 7 / 未登记 1）|
| 合同状态机 | `state_machine/contract_fsm.py` | ✅ 8 态单向链一致、异常收敛、脏数据返 [] |
| 跨端契约 4 项 | `utils/response_utils.py`、`Asset.AssetStatus`、`core/pagination.py` | ✅ 4 项全部一致（§三 C 段） |
| 前端状态枚举 | `types/asset.ts`、`types/outasset.ts`、`utils/statusMapping.ts` | ✅ 8 键一致；支付记录状态映射游离（AUD-F-01） |
| 鉴权/操作日志/批量删除 | `core/permissions.py`、batch_mixins、G-6/G-7 护栏 | ✅ 护栏 PASS；读面无未登记端点 |
| 安全红线 | SC-1~SC-8 分流 | ✅ 12 项通过；SC-2 CI 扫描模式 1 疑点 |
| 规模/测试门禁 | scripts/* 护栏 + pytest/vitest | ✅ 全 PASS（数字见 §三 E） |
| 过工程度 | ponytail-audit 全库 | ⚠️ 6 处死代码 + 7 个可疑依赖（§三 F） |

---

## §二 问题台账

> 行为固定字段：ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 影响面 | 优先级 | 建议验证方式 | 回查命令。锚定行号均为 2026-11-07 实读。
> 「回查命令」固定为 `codegraph node/callers <symbol>` 或 rg 命令（标题行注明）。

### 2.1 后端

| ID | 级别 | 类型 | file:line | symbol | 描述 | 建议验证方式 | 影响面 / 优先级 | 回查命令（rg / codegraph） |
|---|---|---|---|---|---|---|---|---|
| AUD-B-01 | P2 | 状态机旁路(未登记) | apps/assetmanagement/management/commands/seed_grouped_assets.py:218 | `Asset.objects.create(asset_current_status="in_store")` | 创建未走 `create_asset`（业务约束 7 唯一入口），且用字符串字面量而非 `Asset.AssetStatus.IN_STORE` 枚举（B9/DR-3 违反字面义），无创建审计 | 影响面：仅 demo seed 命令自身（codegraph impact = 本文件 + 1 测试）。优先级 P2。验证：改为 `create_asset` 或登记 demo 豁免行 + 换枚举后 `pytest tests/test_seed_grouped_assets.py` | `rg -n "asset_current_status" .../seed_grouped_assets.py` |
| AUD-B-02 | P2 | 分层违规(View 内联业务守卫) | apps/usermanagement/views/role_view.py:87-101 | `RoleViewSet.destroy` | 删除守卫（is_system 不可删、已分配用户不可删）内联在 View 层 + 直接 ORM 查询，绕过 RoleService；与同文件 perform_create/perform_destroy 的 Service 路由口径不一致 | 影响面：仅 role 删除路径（callers 唯一遍）。优先级 P2。验证：下沉 `RoleService.delete_role()` 后 `pytest apps/usermanagement/tests/test_role_service.py test_batch_delete_view_api.py` | `codegraph node RoleViewSet.destroy` → 同 view ID 命中 |
| AUD-B-03 | P2 | DR-1 双实现 + 分层违规 | apps/usermanagement/department_serializers.py:151-235 ↔ department_service.py:230-258 | `validate` + `_validate_move_hierarchy` | 部门移动校验（循环引用 + 层级上限）在 Serializer 与 Service 双实现；Serializer 版在锁外读 DB 且 error_code 分叉（Serializer 抛纯文案 dict，Service 抛 CIRCULAR_REFERENCE/DEPARTMENT_LEVEL_EXCEEDED） | 影响面：17 符号（service 移动主链 + 11 测试锚）。优先级 P2。验证：收敛后 `pytest apps/usermanagement/tests/test_department_service.py`（12 用例锚点已列 impact 输出） | `codegraph impact _validate_move_hierarchy` |
| AUD-B-04 | P2 | 回归稳定性(CT-4 临界) | docker/feishu-webhook/test_app.py | `test_unknown_path_404` | 覆盖率专项跑 ×4 中 1 次失败(404 波动)，复跑通过；判定波动用例，非环境问题，疑似端口/时序耦合 | 影响面：单用例。优先级 P2（未阻断门禁，但 CT-4 要求回归屏障）。验证：连跑 5 次定位失败模式后补确定性夹具 | `rg -n "test_unknown_path_404" docker/feishu-webhook/test_app.py` |
| AUD-B-05 | P3 | DRY(跨文件同构块·记录性) | core/audit_log_filters.py:66-102 ↔ apps/assetmanagement/operation_log_filters.py:59-102 | `_parse_date`/`_validate_operation_type` | 两个过滤层 37 行逐字同构（唯一消费面差异可收敛至 core 侧共用 helper）；记录性条目，不强制本批修复 | 影响面：双文件同构块，纯结构收敛、零行为变更。优先级 P3。验证：抽共用 helper 后 diff 输出等价 + 双域过滤测试 | `rg -n "_parse_date" asset_management_backend --glob "*.py"` |
| AUD-B-06 | P3 | 文档漂移(README 图缺边) | README.md:218-241 | 状态机图 | 缺 broken/lost/recycled_pending→damaged 三入口、damaged→in_use/recycled_pending/repairing 三 reject 目标、cancel 边、双入口共边标注；README 图与 transitions.py 陈旧脱节 | 优先级 P3。验证：补边或加「完整规则见 backend-business-rules.md §三」免责声明 | `rg -n "to_damaged\|cancel" README.md` |
| AUD-B-07 | P3 | 文档缺测提示(合同 FSM) | state_machine/contract_fsm.py + tests/test_contract_fsm.py:76-78 | `_validate_transition` | 合法边 7 条中仅 1 条有 FSM 级直测；CT-3 由集成链 test_contract_view_api.py:569-603 满足，非缺测，建议参数化 7 边提升表漂移灵敏度 | 优先级 P3。验证：参数化测试 | `codegraph node _CONTRACT_TRANSITIONS` |
| AUD-B-08 | P3 | 业务口径[待确认] | apps/assetmanagement/services/repair_asset_service.py:253-255 | `repair_done` | 约束 4「维修完成必须更新 physical_grade」实现为可选（不传即不更新，None 落库留痕）；[推测] 宽容历史数据的刻意设计，需产品拍板「必传 or 缺值可略」并落文档 | 优先级 P3。验证：拍板后改文档或校验逻辑 | `codegraph node repair_done` |
| AUD-B-09 | P3 | 分层/Selector 缺位 | usermanagement/views/role_view.py:209-217；authusermanagement employee_auth_mixin.py:61-74；contract_view.py:114-116、storage_view.py:86-96（带注释豁免） | UserRoleViewSet.get_queryset 等 | View 层直查 ORM 未走 Selector（契约/仓库为全局资源已注释豁免，低风险挂账）；usermanagement 无 RoleSelector | 优先级 P3。验证：若补 Selector 跑相关 view 测试 | `rg -n "objects\.filter" apps/usermanagement/views -g "*.py"` |

### 2.2 前端

| ID | 级别 | 类型 | file:line | symbol | 描述 | 建议验证方式 | 影响面 / 优先级 | 回查命令 |
|---|---|---|---|---|---|---|---|---|
| AUD-F-01 | P2 | 状态映射游离(G-3 精神) | src/components/componentsdetails/detils/ContractPaymentRecord.vue:72,180-184 | 内联支付状态映射 + 模板字面量比较 | 组件内联状态映射（待审核/已审核/已删除）且与 statusMapping.APPROVAL_STATUS_MAP 标签用语不一致，未入类型化枚举（真值源 contract.ts:76 字面量联合）；G-3 护栏不覆盖支付状态 | 影响面：单组件（独立组件，无 caller 链）。优先级 P2。验证：收编进 statusMapping.ts 加 `PAYMENT_STATUS_MAP` 后跑 `npx vitest run src/components/componentsdetails/__tests__/` | `codegraph node ContractPaymentRecord` |
| AUD-F-02 | P2 | 竞态保护缺失 + FR-2 双实现 | src/stores/notificationStore.ts:40-56 ↔ src/composables/useNotification.ts:141 | `fetchNotifications` 双实现 | 两套取数（store / composable）并行走两端；store 版无 seq 守卫、无并发去重——过期响应覆盖风险（19 个实体 store 均走 createEntityStore，本 store 是主动独立实现，无等价保护，不同于 auditLogStore/dashboard 的自建守卫） | 影响面：8 符号（bell 链 + 列表页链，impact 输出海）+ 8 测试符号。优先级 P2。验证：合并候选后 `npm run test:coverage -- src/stores/notificationStore.spec.ts`、`useNotification*.spec.ts` | `codegraph impact fetchNotifications` |
| AUD-F-03 | P3 | 回退字面量 | src/components/componentsdetails/components/AssetTypeChildList.vue:33 | header-cell-style 回退 `#f5f7fa` | CSS 变量缺失时的硬编码回退值（非主用值） | 优先级 P3。验证：确认变量在 variables.css 后移除回退字面量 | `rg -n "f5f7fa" vue-assetmanagement/src` |
| AUD-F-04 | P3 | 图表 palette 逸出 F1/F2 | src/composables/useChartTheme.ts:37-47,81-83；src/utils/statusMapping.ts:232-236 | PIE_EXTRA/dividerColor | 8 个派生色（#8B5CF6 等 4 色 + 暗模式派生 + 3 个图表散点色）不在 F1-F2 四色令牌集内，"图表 palette 派生色"无书面豁免口径 | 优先级 P3。[推测] 需产品/设计确认是否豁免；若收编进 tokens 文件即闭环 | `rg -n "#8B5CF6\|#13C2C2\|#F759AB\|#FA8C16\|#6B7280" vue-assetmanagement/src` |
| AUD-F-05 | P3 | 前瞻加固[推测] | src/router/guards.ts:84-87 | roleWhitelist startsWith | 路由白名单前缀匹配无 path-boundary 保护（当前路由集零影响） | 优先级 P3。验证：白名单负向断言侧 spec 展开 | `codegraph node guards` |

### 2.3 安全 / CI

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 影响面 / 优先级 | 回查命令 |
|---|---|---|---|---|---|---|---|---|
| AUD-C-01 | P2 | CI 扫描假阳性[推测](CI 现网未直证) | .github/workflows/security-scan.yml:236-262 | secret-scan PATTERNS | 扫描模式未排除 `*tests*`，按已钉 SHA 051d7141 内容复现 rg：5 处测试夹具密码**确定性命中** → 按脚本逻辑必 `exit 1` 致 secret-scan 步骤必红；CI 现 RUN 结论无法在本环境连 GitHub 直证，故标注 [推测]（机理取自本地 pinned SHA 精确复现） | 影响面：仅该 job；不阻断 final gate if 为非必需门槛（需查 branch protection 真态）。优先级 P2。验证：`gh run list --workflow security-scan.yml` 直证 secret-scan 最近 conclusion；修复 = 模式加 `-g '!*tests*'` 或 tests 命中降级 warn | `rg --pcre2 -i -n '(secret\|password\|api_key\|apikey\|token)\s*[:=]\s*["''][^"'']+' asset_management_backend -g '!*.md'`（按 CI 原命令） |
| AUD-C-02 | P3 | 死代码文件 | asset_management_backend/core/validators.py:17-100 | 4 个校验函数 | 生产代码零调用（rg 全仓剔除自身后仅命中自测与 docstring），整文件死代码（死代码清单已复核） | 优先级 P3。验证：删除后 pytest 全量 + ruff/mypy | `rg -n "validate_asset_code" asset_management_backend -g "*.py"`（零外部命中） |
| AUD-C-03 | P3 | 依赖冗余 | vue-assetmanagement `package.json` | `less`/`less-loader`/`jsdom`/`lodash-es` | less 链零 .less 文件；jsdom 在 happy-dom 工程零使用；lodash-es 仅 useDebouncedSearch 一个 debounce 用途 | 优先级 P3。验证：npm remove 后 `npm run type-check && npm run test:coverage && npm run build` | `rg -n "lodash-es\|less\|jsdom" vue-assetmanagement/src --glob "!*config*"` |

### 2.4 台账状态标记（阶段 4 要求）

| ID | 终态 |
|---|---|
| AUD-B-01 | 待修（[待确认] 主体：是否将 demo seed 的直注登记为 S1/E-1 同型豁免行） |
| AUD-B-02 | 待修 |
| AUD-B-03 | 待修 |
| AUD-B-04 | 待修（附 CT-4 回归屏障补测义务） |
| AUD-B-05 | 不采纳（仅做记录性登记，改不改由后续批次定夺） |
| AUD-B-06 | 待修（文档） |
| AUD-B-07/AUD-B-08/AUD-B-09 | 不采纳（建议级，记录在案） |
| AUD-F-01/AUD-F-02 | 待修 |
| AUD-F-03~F-05 | 不采纳（前瞻/低风险挂账） |
| AUD-C-01 | 待修（修法二选一，须先直证） |
| AUD-C-02/AUD-C-03 | 待修（含删除验证门槛：pytest/前门禁全量） |

---

## §三 分域结论与修复建议（按优先级排序）

### A. CT-3 状态机全路径（结论 + 证据）

1. **资产 FSM 22 条边与 backend-business-rules.md §三 零漂移**——逐边比对（补充：README.md:218-241 仅为导航简化图，完整事实源以 transitions.py + 规则文档为准）。
   - `in_store→in_use/broken/lost`、`in_use→recycled_pending/broken/lost`、`recycled_pending→in_use/broken/lost/damaged`、`broken→repairing/damaged`、`repairing→recycled_pending/damaged(双入口)`、`lost→damaged/recycled_pending`、`damaged→scrapped+5 reject 目标+5 cancel 目标`、`scrapped 终态空出边`——全部一致。
   - 证据：`transition.py:32-84` 与规则表 v1.23 L73-96 逐行行走核对、`_REJECT_TARGETS` 白名单（scrapping.py:25-31）、`test_state_machine.py` 39 处 `InvalidTransitionError` 负向锚。
2. **旁路 8 处，已登记 7 / 未登记 1**：
   - 已登记：cancel_outasset、cancel_recycle、cancel_damaged、reject_to_original、force_recycle_from_any、S1 两条 unregistered.py 直写（:56/:89）——各有前置守卫 + 测试锚（test_state_machine.py:259-291、229-241）。
   - **未登记 1 处：seed_grouped_assets.py:218 未走 create_asset + 字符串字面量（P2，台账 AUD-B-01）**。
3. **业务约束 1-7 全部落实**——damaged 变更必建审批单、进 repairing 必建维修记录（含防重 DB 约束）、reject/cancel 按 original_status 回退 + 兜底、创建注入 IN_STORE 枚举等均有正向与负向测试锚。
4. **合同 FSM**：`_CONTRACT_TRANSITIONS` 8 态链一致、异常收敛 ContractInvalidTransitionError、allowed_next_states 脏数据返 []、trustworthy 写路径收口 contract_view.py:127-174；admin readonly 化防直改 bathroom ladders（admin/asset_admin.py:77）。

**建议**（按优先级）：① 修 AUD-B-01（改枚举注入 + 走 `create_asset`，或该 demo 命令登记为 S1/E-1 同型豁免行）；② 补 README 状态图（AUD-B-06）或加「完整规则见 backend-business-rules.md §三」免责声明；③ 拍板 AUD-B-08（repair_done 是否必填升级）；④ test_contract_fsm 参数化 7 边（AUD-B-07）。

### B. 分层架构 + DRY

- 五层铁律抽样结论：**assetmanagement 质量最好**（12 selector + 17 service 全 atomic、View 全薄）；**unregisteredasset 干净**；**usermanagement 有 3 处分层违例**（AUD-B-02/AUD-B-03/AUD-B-09），是唯一非完全合规的模块。
- DRY：重复实现仅发现 2 处（audit/operation_log_filters 的 _parse_date 同构块、reactiveAccess 双函数，见 §三 F shrink 条）；**BR-3 硬编码资产状态字符串生产代码 0 命中**（assign/kwargs 形态全枚举化）。
- 事务：抽样 17 份 service + core/batch_mixins 全 atomic，批量逐条包裹与 fail_items 语义自洽。

### C. 跨端契约 4 项

1. **响应信封**：`{"code":0,"data":{},"message":...}` 运行时 + schema 双证（success_response 唯一入口、OP-09 envelope_postprocessor、api-schema-baseline.json 201 处 x-envelope）；手写 Response 活代码 0 处。
2. **枚举 8 键**：前后端逐字一致；OUTASSET_STATUS_MAP 收敛为别名（DR-1 合规）。
3. **分页 page/page_size**：前端 0 处 pageSize 混用（外发查询参数）；B4 dashboard limit/days 属设计内豁免（M-28，`dashboard_view.py` 的 `_parse_int_param` 统一解析，勿误报）。
4. **日期 +08:00**：USE_TZ=True、无 DATETIME_FORMAT 硬覆盖、前端 Format.ts 专门防护 `toISOString` 的 UTC 偏移坑。**4 项全过，未破坏。**

### D. 安全红线 SC + RBAC

- **通过 12 项**：SC-1（硬编码零命中，settings/compose fail-closed）、SC-3（无 .raw/.extra，3 处 cursor.execute 皆零注入面）、SC-4（唯一动态 order_by 白名单）、SC-5/SC-6（无上传接收面，N/A 留证）、SC-7/SC-8（workflows 落地 + weekly + 豁免登记闭合）、B11/B12/B14（护栏 PASS、8 组批删接线、5 组豁免名单同构、审计日志 auditor-only）、公开扫码白名单、读面无未登记端点、OC-6 health+ready。
- **1 疑点 AUD-C-01（P2 [推测]）**：security-scan secret-scan 步 PATTERNS 无 tests 排除，5 处夹具密码在钉 SHA 内容上确定性命中 → 若该 job 真按此跑，secret-scan 必红——须 GitHub 直证后修口径。
- OC-1~OC-3：trace_id 全链（request_context/logging_filters/json_formatter 有）、StructuredJSONFormatter 挂 base.py:331、mask_phone_number 进 sanitizer。

### E. 测试与规模门禁（机械复测数字，2026-11-07 实测）

| 门禁 | 结果 | 数字 |
|---|---|---|
| BR-6 文件 ≤500 行 | PASS | max 484（asset_view.py） |
| BR-4 函数 ≤50 行 | PASS | max 50（asset_lifecycle_mixin.py:59） |
| 重复护栏 G-1~G-3,G-5~G-8 | PASS | `[RESULT] PASS` |
| FR-6/FR-8/FR-5 | PASS | max 199/407/411 |
| mypy --strict / ruff / ruff format / C90 | 全 PASS | 0 errors / 446 files formatted；**CT-7 版本对齐（pip 与 dev.txt 一致，结论有效）** |
| 后端 pytest 全量 + cov | PASS | **2398 passed**，整体 cov **89.55% ≥ 80**，782s |
| Service 层 cov 专项 ≥90 | PASS（复跑） | **98.36%**（首跑 feishu 404 波动已记 AUD-B-04） |
| 前端 type-check / lint:ci / format:check | 全 PASS | — |
| 前端 vitest 2542 用例 | PASS | stores cov **96.83% ≥ 90** |
| mutmut 基线 | 未本地跑（Windows 拒绝） | baseline.json = 83.25676365492598（与规范一致） |

> 本轮数字在声明的 dev.txt 版本（CT-7 复核通过）下取得，无本地漂移。

### F. Ponytail 全仓过工程度审计（ponytail-audit + ponytail-review 联合口径）

每条已本地复核（Ponytail 死代码清单一并复核过，零外部调用属实）：

```
delete: core/validators.py 整文件——4 个校验函数生产零引用（已本地 rg 复核：剔除自身后仅命中文档与 definition）. 替代：无. [core/validators.py]
delete: utils/date_utils.py 整文件——5 个日期工具生产零调用（唯一活的是 __init__ re-export）. [utils/date_utils.py]
delete: utils/string_utils.py 5/6 函数死代码（generate_*/mask_id_card 生产零调用，唯一活的 mask_phone_number）. [utils/string_utils.py]
delete: vue Image.ts 5/7 死导出（preloadImage/compressImage 等，唯一活的 lazyLoadDirective）. [vue-assetmanagement/src/utils/Image.ts]
delete: usermanagement/providers.py Mock 三件套（docstring 声称测试用，实际全仓零引用）. [apps/usermanagement/providers.py:44-108]
delete: BaseModel.restore()/hard_delete()+all_objects 软删三件套（restore/hard_delete 生产零调用）. [core/models.py:107,135-155]
stdlib: lodash-es 全量依赖只为 useDebouncedSearch 一个 debounce. [composables/useDebouncedSearch.ts:16]
native: less+less-loader 零 .less 文件 / jsdom 零使用（vitest environment=happy-dom）. [package.json]
yagni: EmployeeProvider 注册中心唯一产品 + Mock 已死；get_employee_queryset 快捷函数已覆盖调用面. [apps/assetmanagement/interfaces.py:63-117]
shrink: audit_log_filters ↔ operation_log_filters _parse_date/_validate_operation_type 37 行跨文件同型复制. [core/audit_log_filters.py:66-102 ↔ apps/assetmanagement/operation_log_filters.py:59-102]
shrink: reactiveAccess 的 readReactive/readStoreValue 三元访问语义双实现. [src/utils/reactiveAccess.ts:18-42]
net: ~-570 行, -7 依赖 可能（requests/urllib3/chardet+less+less-loader+jsdom+lodash-es；零 import 已全仓 rg 验证）。[推测] urllib3 或为传递依赖 pin 守卫，削减前需人工过目 pip-audit 口径。
```

修复优先级：依赖清理（P3 低风险）→ 死文件批量（P3，均需 pytest/vitest 全量兜底）→ shrink 合并（随 AUD-B-05 批次）。

---

## §评审结论（阶段 5 reviewer 自审）

- **证据可回查**：全部 15 条台账条目均附 file:line 与 codegraph/rg 回查命令；effect 输出原始摘录（`_validate_move_hierarchy` impact 17 符号、`fetchNotifications` 双定义各 8 符号、`seed_grouped_assets` impact 2 符号）。
- **置信度门槛**：reviewer 复核后置信 <80 或无法本环节直证的条目已显式标注 [推测]（仅 AUD-C-01 一条 CI 现网结论；AUD-B-08 拍板项；AUD-F-04 palette 口径）。
- **闭环检查**：P0/P1 均无；P2×7（B×4 + F×2 + C×1）每条有 证据 + 影响面 + 修复建议 + 建议验证方式；台账终态除 6 条「不采纳+理由」外全部可交接。
- **抽查回归点**：本次只读纪律维持（git 工作区未动过任何业务代码；本报告只有 docs/Review/docs/ 新文件落盘）。
- **质量管控检查点（§8）**：索引无 missing/陈旧[√]、台账五要素完整[√]、§5 每维度有命令/数字证据[√]、报告闭环[√]、建议可接手[√]、只读[√]。

**综合评级：项目整体健康度良好。** 全量门禁（后端 2398 用例 / cov 89.55%，前端 2542 用例 / stores 96.83%，规模护栏×5、静态门禁×4）全绿，无 P0/P1；遗留集中在 ① seed 命令 1 处未登记旁路、② usermanagement 3 处分层违例、③ 通知域双实现+竞态缺失、④ 7 个死代码/死依赖、⑤ CI 扫描 1 处待直证疑点。无需 [HALT]。
