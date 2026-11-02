# 资产管理项目全项目审计报告（CodeGraph 增强版）

> 执行者：opencode（`project-all-code-review` skill v1.2.0，纯审计不修复）
> 日期：2026-11-01 ｜ 版本基线：父仓 HEAD `d7e2fa9` / 后端子模块 `5a27ca5` / 前端子模块 `9ba1fb1`
> 只读纪律：**本次会话未改动任何业务代码**（唯一新增文件为本报告；pytest/vitest 仅产生被 .gitignore 覆盖的缓存与覆盖率数据）
> **工作区披露（Fact-1）**：审计开始时工作区已存在**他人未提交改动**——后端子模块 6 个文件（`contract_view.py`、`damaged_asset_view.py`、`dashboard_selector.py`、`conftest.py`、`test_base_selector.py`、`test_p2_04_export_endpoints.py`）+ 2 个未跟踪测试，前端子模块 1 个文档，父仓 `merge-audit-20261031.md` 等。本报告全部结论基于**该工作区状态**（codegraph 索引 `✓ up to date`），非纯 HEAD 状态。
> 索引状态：`codegraph status` → Files 1,023 / Nodes 18,224 / Edges 41,491，`✓ Index is up to date`

---

## §一 项目上下文

### 1.1 技术栈与模块边界

| 端 | 技术栈 | 规模（图谱实测） |
|:---|:---|:---|
| 后端 `asset_management_backend` | Django 6.0.8 + DRF 3.18.3（声明）+ PostgreSQL 16 + channels/daphne + drf-spectacular 0.29.0 | 472 索引文件 / 483 .py |
| 前端 `vue-assetmanagement` | Vue 3 + TS + Pinia + Element Plus + Vite + Vitest 4.1.11 | 510 索引文件（396 ts + 121 vue） |
| 分层约定 | 后端 View → Service → Selector 三层（BR-7 ≤3 层）；前端 api / stores / composables / components / types / utils | 后端 12 Service + 17 Selector + 15 Serializer |

### 1.2 分域清单与探索入口（阶段 1 已逐域执行）

| 分域 | 锚点 | 探索方式 |
|:---|:---|:---|
| 资产状态机 | `apps/assetmanagement/state_machine/`（constants.py `AssetState` / transitions.py `VALID_TRANSITIONS` / core.py `AssetFSM` + 4 个 mixin） | 全域 explore + 旁路 rg 扫描 |
| 合同状态机 | `state_machine/contract_fsm.py`（`ContractState` / `ContractFSM`） | explore + 直写扫描 |
| API 响应契约 | `utils/response_utils.py`（`success_response`:23 / `error_response`:37） | node + `return Response(` 全量统计 |
| 跨端契约 4 项 | `types/asset.ts` / `types/outasset.ts` / `core/pagination.py` / `config/settings/base.py` | 逐项源码核对 + 序列化运行时实测 |
| 安全 / RBAC | `core/permissions.py:207 resolve_viewset_permissions` + 各 ViewSet | ViewSet 全枚举 + rg 扫描 |
| 前端架构 | `stores/createEntityStore.ts:61`、`api/request.ts`、`utils/statusMapping.ts` | explore + 旁路 rg + 护栏实跑 |
| 测试与规模 | `scripts/`（line_metrics / file_length / function_length / frontend_invariants / duplicate_invariants） | 全部实跑 |
| CI 门禁 | `.github/workflows/security-scan.yml`、`ci.yml` | 只读核查 |

### 1.3 本次实跑的量化结论（CT-2 / CT-7 声明）

| 检查 | 命令 | 结果 |
|:---|:---|:---|
| 后端全量测试 + 覆盖率 | `python -m pytest --cov=. --cov-fail-under=80 -q` | **2269 passed，Total coverage 89.40% ≥80**（11m47s） |
| 后端核心 Service 层 | `coverage report --include="*/services/*"` | **98% ≥90**（2046 stmts / 36 miss） |
| Selector 层 | `coverage report --include="*/selectors/*"` | 96%；`state_machine/` 99% |
| 前端 Store 层 | `npx vitest run --coverage --coverage.include="src/stores/**/*.ts"`（阈值 90 四项） | **Lines 97.21 / Stmts 96.82 / Branches 93.24 / Funcs 91.15，四项全过** |
| 前端全量用例 | `npx vitest run`（前端子代理实跑） | **186 files / 2420 tests 全绿** |
| 规模护栏 | `check_file_length_guard.py --print` | 最大 `views/asset_view.py` 483 逻辑行，**全部 ≤500，PASS** |
| 函数长度护栏 | `check_function_length_guard.py` | `[PASS] 0 个超长函数 / 0 个文件未登记` |
| 前端护栏 | `check_frontend_invariants.py --print` | FR-6 56 个 / FR-8 31 个 / FR-5 121 个 **全 ok**（存在 1 个扫描盲区 → P2-3） |
| 重复代码护栏 | `scripts/check_duplicate_invariants.py` | `[PASS] 不变量检查全部通过` |
| 生产依赖漏洞 | `npm audit --omit=dev` | **7 moderate / 0 high**（exceljs→archiver→glob→minimatch 链），CI 门禁 `--audit-level=high --omit=dev` 通过 |
| 后端依赖漏洞 | 本地 pip-audit 未装 | **未执行**，按 skill §5.3 兜底：以 CI `security-scan.yml`（pip-audit 双 requirements，fail-closed）为权威门禁 |

> **CT-7 环境漂移声明**：本地 venv 实测 **DRF 3.17.2**，而 `requirements/base.txt:26` 声明 **3.18.3**。本地取得的静态门禁数字（含 OpenAPI 基线 diff）**不代表 CI**；本文引用的 pytest/vitest 覆盖率与护栏结论为行为级结论，不受该漂移影响。

---

## §二 问题台账

**分级口径**：P0 阻断/高危 ｜ P1 重要（行级隔离等授权缺口）｜ P2 优化（合规缺陷、护栏/测试盲区）｜ P3 建议（卫生项、文档项）
**回查命令**固定为 `codegraph node <symbol>` / `codegraph callers <symbol>`，已逐条实跑校验非虚构。

### 2.1 P1 级（3 条，均为 B12/B14 行级隔离真实缺口）

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 状态 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| **P1-1** | P1 | B12/§4.7 旁路 | `apps/usermanagement/views/department_view.py:100`；`apps/usermanagement/selectors.py:175-188` | `DepartmentViewSet.employees` / `get_employees_by_department_instance` | `employees` action 落入 `get_permissions` else 分支 → **仅 `IsAuthenticated`**（department_view.py:71），底层为未收窄的 `Employee.objects.filter(employee_department=department)`（selectors.py:188）。任意登录用户遍历部门即可枚举全公司员工档案——正是 §4.7 明令禁止的「只在某个 action 里 filter」旁路 | 改走 `get_employee_scoped_queryset_for_user(user, ...)`，越权部门 404；同步扩展 `test_employee_rbac_scope.py` | `codegraph node DepartmentViewSet.employees` | 待修 |
| **P1-2** | P1 | B14/B12 | `apps/assetmanagement/views/out_asset_view.py:295`；`apps/assetmanagement/services/out_asset_service.py:296,307` | `OutAssetService.batch_delete_outasset` / `_delete_one` | service 签名**不接收 user**，`_delete_one` 经全表 `OutAssetSelector.get_outasset_for_update` 取行，全程无可见性校验。对比同仓 `asset_service.py:303-310`（`ensure_asset_visible`）与 `recycle_asset_service.py:386`（`_ensure_recycle_visible`）——**同型实现已做收口，出库批量是唯一漏网** | `batch_delete_passes_user = True` + `_delete_one` 补 `ensure_asset_visible(outasset.asset_recordcode, user)`（复用既有助手，DR-1） | `codegraph node OutAssetService.batch_delete_outasset` | 待修 |
| **P1-3** | P1 | B14/B12 | `apps/assetmanagement/views/waste_asset_view.py:206`；`apps/assetmanagement/services/waste_asset_service.py:57,25` | `WasteAssetService.batch_delete_waste_assets` / `cancel_waste_asset` | 与 P1-2 同型：`cancel_waste_asset` 按 `asset_recordcode__asset_code` 全表查找且不收 user，批量路径可跨部门软删报废记录 | 同 P1-2：传 user + 逐条 `ensure_asset_visible` | `codegraph node WasteAssetService.cancel_waste_asset` | 待修 |

### 2.2 P2 级（6 条）

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 状态 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| **P2-1** | P2 | B11 越权读面 | `core/permissions.py:229-230`；`apps/assetmanagement/views/contract_view.py:80-88` | `resolve_viewset_permissions` / `ContractViewSet.get_permissions` | 权限优先级为 `export_excel → action_overrides → admin_actions`，**export 短路排在最前**。BF-127 已把合同读面收口 `IsSystemAdmin`，但 `ContractViewSet` 挂 `ExportExcelMixin`，dept_manager/asset_admin/auditor 持 `CanExportExcel` 即可导出**全量合同**（金额/起止日期），与权限矩阵「合同仅 system_admin」矛盾 | 首选**局部修**：`ContractViewSet.get_permissions` 对 `export_excel` 显式返回 `[IsSystemAdmin()]`（避免改 resolve 全局优先级——其 impact 达 53 符号） | `codegraph node resolve_viewset_permissions` | 待修 |
| **P2-2** | P2 | OC-3 敏感信息入日志 | `apps/usermanagement/views/employee_view.py:224,229`；`employee_serializers.py:80`；`employee_audit_adapter.py:35` | `EmployeeViewSet.update` / `EmployeeAuditAdapter.log_update` | `before_data/after_data = EmployeeDetailSerializer(...).data`（`fields="__all__"` 含 `employee_phone` **明文**）整份写入 `AuditLog`。OC-3 明令日志禁止记录明文手机号。注：API 响应口径明文系 M-03 业务决策，且审计日志读面（IsAuditorOrAdmin）窄于 API（IsAuthenticated），故**增量暴露有限，属条文级违规** | 入库前对快照剥离/脱敏 `employee_phone`（复用 `utils/string_utils.mask_phone_number`，DR-4）+ 回归用例断言快照无明文手机号 | `codegraph node EmployeeAuditAdapter.log_update` | 待修 |
| **P2-3** | P2 | 护栏盲区（FR-8） | `scripts/check_frontend_invariants.py:74-78` | `is_store_target` | 用 `path.name.startswith("use")` 排除 composable，导致 **`userStore.ts` 被误排除**：护栏报 31 个 store、实际 32 个（该文件当前 162 逻辑行合规，但**不在断言面内**，未来超限将假绿） | 排除条件改显式白名单或按目录全量扫描；补 `scripts/tests/` 护栏自测证红证绿 | `codegraph explore "is_store_target"` | 待修 |
| **P2-4** | P2 | CT-1/CT-4 测试盲区 | `src/composables/useGroupChildrenCache.ts`(126) 等 8 个 | `useGroupChildrenCache` `useAssetExtendedInfoCards` `useGroupedAssetSelection` `useServerExcelExport` `useDashboardUser` `usePreviewPagination` `usePageHeader` `useContainerWidth` | 8 个 composable **零测试引用**（部分仅有他 spec 的 mock 注册），规模榜首区无行为锚，回归屏障缺失 | 按逻辑行降序补 spec（前 4 个优先），微小件并入消费方组件测试 | `codegraph explore "useGroupChildrenCache"` | 待修 |
| **P2-5** | P2 | 测试健壮性（未来假红） | `src/composables/__tests__/batchB.contract.spec.ts:50-97` | `batchB.contract.spec` | vitest 4.1.11 实跑输出 9 条警告：`vi.hoisted`/`vi.mock` 不在模块顶层，官方标注「will become an error in a future version」——升级即阻塞 CT-5 | 全部 `vi.mock`/`vi.hoisted` 提升至文件顶层（参考同目录顶置范式） | `codegraph explore "batchB.contract.spec"` | 待修 |
| **P2-6** | P2 | OpenAPI 文档保真度 | `utils/response_utils.py:23,37`；`core/mixins.py:91-215` | `success_response` / `error_response` | 响应信封由 dict 手工构造，spectacular 无法推断：338 个响应规格中仅 **27 个（8%）**建模 `{code,message,data}`，211 个呈裸对象。运行时契约正确，但生成的客户端/接入方拿到错误契约（§4.8 OS-5 同类失真） | 新增共享 `ENVELOPE_SCHEMA` 后处理器（复用 `core/pagination.py:94-118` 建模方式），不改运行时；重导 `api-schema-baseline.json` | `codegraph node success_response` | 待修 |

### 2.3 P3 级（18 条，卫生/文档/待确认项）

| ID | 类型 | 位置 | symbol | 描述与修复建议 | 回查命令 | 状态 |
|:---|:---|:---|:---|:---|:---|:---|
| P3-1 | B7 审计粒度 | `apps/unregisteredasset/handlers.py:154-222` | `_handle_s1_create_and_recycle` | S1 场景裸 `Asset.objects.create` + FSM 落态，**无资产级 create/state 审计**（S2/S3 已由 M-16 补 `log_state_change`）。建议对齐 M-16 范式补痕 | `codegraph node _handle_s1_create_and_recycle` | 待修 |
| P3-2 | 文档缺口 | `Rules_Fiels/backend-business-rules.md:100-107` | `unregistered.py` | 规则表「特殊回退操作」未收录 `unregistered_create_and_recycle/_damaged` 两条已声明例外（代码 `transitions.py:9-14` 已留痕）。建议规则表补两行 | `codegraph node VALID_TRANSITIONS` | 待修 |
| P3-3 | 文档缺口 | `backend-business-rules.md`（全文无「合同状态」） | `ContractFSM` | 合同 8 态链**零文档**，与资产状态机（§三完整成文）不对称。建议增设「合同状态机」小节 | `codegraph node ContractFSM` | 待修 |
| P3-4 | 文档粒度 | `backend-business-rules.md:86` | `VALID_TRANSITIONS` | `repairing→damaged` 实为双入口共边（`repair_failed` + `to_damaged`，M-30），规则表未区分边名。建议备注双边 | `codegraph node VALID_TRANSITIONS` | 待修 |
| P3-5 | 防御纵深 | `serializers/asset_crud_serializers.py:91-127` | `AssetDetailSerializer` | 含 `asset_current_status` 但**未声明 `read_only_fields`**（List 版已全只读），且是 `get_serializer_class()` 兜底类。当前无写入用例，属「未上膛的枪」。补 `read_only_fields = fields` 零行为变更 | `codegraph node AssetDetailSerializer` | 待修 |
| P3-6 | B7 字段完整性 | `services/asset_lifecycle_mixin.py:82-90,215-223` | `_run_lifecycle_transition` | mark_broken/lost/found 的 `log_operation` 未传 `before_data/after_data`，before 状态（三源之一）丢失。建议改走 `AuditLogger.log_state_change` | `codegraph node _run_lifecycle_transition` | 待修 |
| P3-7 | 约束 7 字面偏差 | `unregisteredasset/handlers.py:69-84` | `_create_unregistered_asset` | S1 走裸 `create` 而非 `AssetService.create_asset`（效果等价，依赖模型默认 `in_store`）。长期复用 Service，短期在约束 7 备注受控例外 | `codegraph node _create_unregistered_asset` | 待修 |
| P3-8 | §4.7 遗留 | `apps/usermanagement/views/employee_query_actions.py:234` | `get_department_by_jobcode` | 按工号探测员工存在性（仅回部门三字段，无 PII），A-43 已声明未评估。建议改走 `self.get_queryset()` 越权 404 | `codegraph node get_department_by_jobcode` | 待修 |
| P3-9 | 读面宽松 [待确认] | `role_view.py:80`、`permission_view.py:43`、部门树/资产类型/仓库读面 | `RoleViewSet.get_permissions` | 矩阵「系统配置」行非 system_admin 全 ❌，但读面仍对全体登录开放。疑似前端下拉刻意设计，**需业务确认**后显式豁免入册或收口 | `codegraph node RoleViewSet.get_permissions` | [待确认] |
| P3-10 | 端点无鉴权 [待确认] | `config/urls.py:155` | `metrics_view` | `/metrics/` 无认证，任何人可读请求量分布。多数部署靠网络层隔离；QPS<10 阶段可暂缓，建议 IP 白名单 | `codegraph node metrics_view` | [待确认] |
| P3-11 | SC-1 卫生 | `asset_management_backend/.env:9,14` | `.env` | 疑似真实 DB/Redis 密码；已核实 `git ls-files`/`git log --full-history` 均空、`.gitignore:70` 命中 → **从未入库，SC-1 未违例**。建议确认轮换 + pre-commit 强拦截 | `git log --full-history -- asset_management_backend/.env` | 待修 |
| P3-12 | SC-7 范围 | `vue-assetmanagement/package.json` | devDeps | 全量 `npm audit` 37 项（**4 high**：happy-dom / undici / vite(launch-editor) / zod），均为 dev 链；CI 刻意 `--omit=dev`（P2-07 决策注释）。生产链 0 high。建议定期 `npm audit fix` 收敛 dev 高危 | `npm audit --omit=dev` | 待修 |
| P3-13 | DR-4 时区 | `src/composables/useExcelExport.ts:165` | `useExcelExport` | `toISOString()` 生成 UTC 时间戳做导出文件名，本地 16:00 后日期少一天；与 `utils/excelExporter.ts:69` 本地口径不一致。改用 `toLocalDateString`（M-33 单源） | `codegraph node toLocalDateString` | ✅ 已修（2026-11-02 批次 4，工作树，BF-172） |
| P3-14 | 类型弱化 | `src/types/outasset.ts:126` | `OutAssetCurrentStatus` | `outasset_current_status: string \| null` 用裸 string，同文件枚举已定义 8 键。改为 `OutAssetCurrentStatus \| string \| null` | `codegraph node OutAssetCurrentStatus` | ✅ 已修（2026-11-02 批次 4，工作树，BF-172；**采纳别名化拍板** `export { AssetCurrentStatus as OutAssetCurrentStatus }` 与 asset 枚举单一来源收敛，非本行补宽建议） |
| P3-15 | 注释过时 | `src/types/asset.ts:321,364` | `AssetQueryParams` | 注释只列 4 态，实际后端接受 8 态，易误导接入方 | `codegraph node AssetCurrentStatus` | ✅ 已修（2026-11-02 批次 4，工作树，BF-172） |
| P3-16 | FR-4 潜在重复 | `components/.../ContractPaymentRecord.vue:180-191` | `statusMap` | 组件内本地状态/支付方式映射，当前仅 1 处消费（未触 FR-1 ≥2 门槛）。**按 §1.8 新发现义务须先登记入 `Duplicate_Codes/complete-patterns.md` 待核查区**，第二个消费方出现前不强制迁移 | `codegraph explore "ContractPaymentRecord"` | 待修 |
| P3-17 | FR-4 / FR-7 门禁 | `src/views/LogIn.vue:228-232`；`eslint.config.ts:37` | `handleLogin` | ① `savedUsername/rememberMe` 4 处直写视图，建议抽 `utils/rememberMe.ts`；② ESLint **无 `vue/max-depth`**，FR-7（模板嵌套 ≤3 层）无自动门禁。②按 §5.4 走 14 日沙盒期 | `codegraph explore "LogIn"` | 待修 |
| P3-18 | 工件卫生 | `vue-assetmanagement/coverage-summary.json`、`coverage-run.log` | — | 陈旧覆盖率工件仍含 20 个**已删除影子死文件**条目，误读会得出错误覆盖面结论。建议移出仓库根或 `.gitignore`，覆盖率一律以当次运行输出为准 | — | 待修 |

**其余无问题域（留痕）**：状态机旁路 **0 处**、契约 4 项 **全通过**、SC-3/SC-4 **合规**、SC-1 **合规**（.env 未入库）、SC-5/SC-6 **N/A**（后端无上传面）、AllowAny 端点 **7 个全部合理**（含限流/白名单/开关证据）、`security-scan.yml` 存在且为权威门禁、四护栏全 PASS、双端测试全绿。

---

## §三 分域结论与修复建议（按优先级排序，含影响面与建议验证方式）

> 排序原则：同域合并 → 级别优先 → 影响面小者先行。**批次 A（P1×3）共用同一助手族，一次清干净（DR-1）。**

### 批次 A — 行级隔离收口（P1-1 ~ P1-3，建议同批）

**影响面（`codegraph impact` 实测）**
- `get_employees_by_department_instance`：**2 个受影响符号**（selector 自身 + `department_view.employees`）——影响面最小，先行。
- `cancel_waste_asset`：**6 个符号**（service 内 `_delete_one`/`batch_delete_waste_assets` + 3 个既有测试）。
- `batch_delete_execute`（若改公共 mixin）：**92 个符号**——**禁止改公共实现**；正确做法是在各 service 的 `_delete_one` 内补 user 校验（`asset_service.py:303-310` 已有可复制范式，且 `test_row_level_isolation_r1.py:194`、`test_batch_delete_cross_dept_blocked` 已为 recycle/lifecycle/damaged 建立同型回归锚）。

**建议验证方式**
1. P1-1：A 部门 `regular_user` 登录 → 请求 B 部门 `employees` → 现状 200 返回 B 部门全量员工（漏洞成立）；修复后 404/空集。落 `test_employee_rbac_scope.py` 新增用例。
2. P1-2/P1-3：A、B 两部门各建 1 条记录 → A 部门 manager 批量删除携带 B 部门编码 → 现状静默删除成功；修复后该条进 `fail_items`（NOT_FOUND 语义），本部门记录正常删。**同时保留 `select_for_update` 行锁与 TOCTOU 兜底**（`asset_service.py:300-306` 范式）。
3. 回归：`pytest apps/assetmanagement apps/usermanagement -q` + 覆盖率复跑 ≥80。

### 批次 B — 权限与敏感数据（P2-1、P2-2）

**影响面**
- P2-1 若改 `resolve_viewset_permissions`：**53 个符号**（14 个 ViewSet.get_permissions + 大量 RBAC 测试）→ 采用**方案①局部覆写**，影响面收敛到 `ContractViewSet.get_permissions` 1 个符号 + `ExportExcelMixin` 13 个 import 方（不改公共优先级）。若选方案②改全局优先级，必须走根 AGENTS §5.2 审批并全量回归导出矩阵。
- P2-2 `EmployeeAuditAdapter.log_update`：**3 个符号**（adapter + `update`/`partial_update`）——影响面小。

**建议验证方式**
- P2-1：auditor 登录 → `GET .../contracts/export-excel/` → 现状 200 全量合同（漏洞成立），修复后 403；补「auditor 导出合同→403」用例，并回归其余 11 个导出端点仍按矩阵工作。
- P2-2：更新员工手机号 → 直查 `AuditLog` 该行 → 断言 `before_data/after_data` 无明文手机号（脱敏或剔键）；补回归用例防回潮。

### 批次 C — 前端护栏与测试锚（P2-3 ~ P2-5）

- **影响面**：P2-3 仅 `scripts/check_frontend_invariants.py`（+ 护栏自测），零业务改动；P2-4/P2-5 仅新增/调整 spec。
- **建议验证方式**：P2-3 修后跑 `python scripts/check_frontend_invariants.py --print`，并**故意给 `userStore.ts` 造 >500 行变体证红**（护栏自测先证红后证绿，参 `scripts/tests/`）；P2-4 修后 `npx vitest run` 全绿且 8 个 composable 各有独立 spec；P2-5 修后运行无 `vi.mock` 顶层警告。

### 批次 D — OpenAPI 信封建模（P2-6）

- **影响面**：纯文档产物（`api-schema-baseline.json`），**零运行时改动**；改动落在 `core/pagination.py:94-118` 同构的共享 schema 片段。
- **建议验证方式**：`python manage.py spectacular --format openapi-json --file <tmp> --validate` 后与基线 diff，确认新增信封只落在预期端点、无破坏性变更（§4.8 OS-6），CI `api-schema-check` 绿。

### 批次 E — P3 文档/卫生（P3-1 ~ P3-18）

低风险、可批量；其中 **P3-16 按 §1.8 新发现义务须先登记账本**，**P3-17② 新增 lint 规则须走 §5.4 沙盒期**，**P3-9/P3-10 需业务确认后才能定案**（暂不采纳-待确认）。

### 分域结论一览

| 分域 | 结论 | 问题数 |
|:---|:---|:---|
| 资产/合同状态机 | **健康**：规则表↔实现逐条一致、旁路 0 处、Serializer 无写暴露、规则表每路径 ≥1 用例、B6/B7 主链路齐备 | 7（全 P3，多为文档粒度） |
| 跨端契约 | **健康**：响应/枚举/分页/日期 4 项全过，错误处理双端一致不吞错 | 1 P2（OpenAPI 信封）+ 4 P3 |
| 安全与 RBAC | **有缺口**：3 处行级隔离旁路 + 1 处越权导出 + 1 处日志明文手机号 | 3 P1 + 1 P2 + 6 P3 |
| 前端架构 | **健康**：分层无旁路、映射单源、超时重试配置化、三护栏全 PASS、2420 用例全绿 | 3 P2 + 6 P3 |
| 测试与规模 | **达标**：后端 89.40% / Service 98% / 前端 Stores 97.21%，四护栏 + 重复护栏全 PASS | 1 P2（composable 测试盲区） |

---

## §四 台账终态

| 终态 | 条目 |
|:---|:---|
| **待修**（已确认，含证据+影响面+建议+验证方式） | P1-1 ~ P1-3、P2-1 ~ P2-6、P3-1 ~ P3-8、P3-11 ~ P3-18 |
| **不采纳** | 无 |
| **[待确认]**（需业务拍板后转待修或不采纳） | P3-9（系统配置读面是否刻意开放）、P3-10（/metrics 是否由网络层隔离） |

> 本 skill 不产生「已修复」状态；修复执行由 `bug-surgical-fix` / `rigorous-dev` 承接，本报告 §三 三批（A/B/C/D）即为其输入。

---

## §五 评审结论（阶段 5 报告质量自审）

| 检查项 | 结论 |
|:---|:---|
| 证据引用可回查 | **通过**：全部 file:line 均来自 `codegraph node` 直出源码或 rg 实测；P1×3、P2-1、P2-2 已由主代理二次 `codegraph node` 独立复核 |
| 置信度 ≥80 才报告 | **通过**：3 条 P1、6 条 P2 置信度均 ≥90（源码直证）；两条 [待确认] 已显式降级不计入确定结论 |
| 每条 P0/P1/P2 四要素 | **通过**：证据 + 影响面（impact 实测符号数）+ 修复建议 + 建议验证方式齐备 |
| §5 各维度有命令输出支撑 | **通过**：CT-2 覆盖率、护栏 ×5、SC-1/SC-3/OC-6 rg 输出、npm audit、状态机旁路 rg 清单均已留痕 |
| 反虚构纪律 | **通过**：未使用 `codegraph generate`、`/` 前缀、占位符 impact；`codegraph impact` 仅作用于真实符号（`get_employees_by_department_instance`/`cancel_waste_asset`/`resolve_viewset_permissions`/`EmployeeAuditAdapter.log_update`/`batch_delete_execute`） |
| 只读纪律 | **通过**：未改动业务代码；唯一写入物为本报告 |

**主动洞察（ID-2）**
1. **同型权限收口的「漏网两条」模式值得固化**：`asset/recycle/damaged/lifecycle` 四条批量删除链已各自做了 user 收口，**只有 out_asset/waste_asset 漏网**——说明收口是逐条人工推进的，建议后续为「所有 `batch_delete_*` 必须接收 user」加一条护栏断言（可入 `check_duplicate_invariants.py` 同构脚本），否则新增实体会继续复现同类缺口。
2. **规则文档对双状态机不对称**（P3-3）：资产状态机有完整 §三规则表，合同状态机零文档——AI 与新开发者只能读代码对齐，正是当年用规则表防住的漂移风险。
3. **`resolve_viewset_permissions` 的 export 短路是全局权限单点**（P2-1）：任何挂 `ExportExcelMixin` 的 ViewSet 都可能被这一行短路绕过 `action_overrides`，修 P2-1 时应评估是否需要一条「导出端点权限矩阵」的表驱动测试兜住全部 12 个导出面。

**SKILL 建议（§1.7）**：`[SKILL 建议] 建议封装：行级隔离批量收口核查` — 触发场景：每次新增 `batch_delete_*` / `*_export` 端点后；包含步骤：① service 签名是否含 user ② `_delete_one` 是否调 `ensure_asset_visible` ③ 权限矩阵行是否一致 ④ 补跨部门回归用例；预期收益：消除 P1-1~P1-3 这类逐条漏网（本次即 3 条）。
