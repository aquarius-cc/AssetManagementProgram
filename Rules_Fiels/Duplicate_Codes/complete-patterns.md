# 重复代码模式活账本（Living Ledger）
> **版本**：v2.0 | **最后更新**：2026-08-13 | **性质**：动态账本，取代 v1.0 静态清单
>
> 本账本为"重复代码/重复实现"问题的唯一事实来源。凡新增/关闭/降级条目，必须在此登记并附证据与验证命令。
>
> 四区导航：[已关闭](#a--已关闭closed) • [待修复](#b--待修复to-fix) • [降级/待决策](#c--降级downgraded待决策) • [待核查](#d--待核查to-verify)

---

## A — 已关闭（Closed）

> 关闭标准：原文涉及的重复实现已不存在，或已收敛为单一实现，并附"证据"与"验证命令"。

### A-1. 原 A-1~A-3（AssetStateValidator / RecyclePathSanitizer / AssetStatusValidator）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-13
- **证据**：原引用文件 `services/asset_management/state.py`、`models.py:validate_recycling_path/validate_status_transition` 均不存在；资产状态流转已收敛为单一实现 `apps/assetmanagement/state_machine/core.py::AssetFSM`。
- **验证命令**：`rg -n "validate_asset_status|validate_recycling_path|check_recycling_chain|validate_status_transition" asset_management_backend --glob "*.py"`（预期无命中）。
- **回滚风险**：若后续新增校验函数，须先索引 `state_machine/core.py`。

### A-2. 原 B-1/B-4（AssetSelector vs AssetQueryManager / filter_assets）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-13
- **证据**：`asset_query_managers.py`、`selectors.py`（聚合文件）已不存在；查询逻辑收敛至 `apps/assetmanagement/selectors/` 包（asset_selector / outasset_selector / operation_log_selector / base_selector）。
- **验证命令**：`rg -n "def filter_assets|class AssetQueryManager" asset_management_backend --glob "*.py"`（预期无命中）。

### A-3. 原 B-2/B-3（asset_get_by_id / user_get_by_id）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-13
- **证据**：`asset_management_service.py`、`user_management_service.py`、`users_selectors.py` 均不存在；改由 `services/` 包 + `selectors/` 包承接。

### A-4. 原 C-1/C-2（View 层重复业务逻辑）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-13
- **证据**：View 层已按五层架构仅做参数解析+调用 Service+返回 Response；领用/创建等业务逻辑仅在 Service 层单一实现。
- **验证命令**：抽查任一 view，业务逻辑均通过 `services.` 或 Selector 委托。

### A-5. 原 D-1（ValidationError 多次手动抛出）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-13
- **证据**：同类错误统一走 `AppValidationError`/`BusinessError` 体系；多个 `raise` 点属正常防御式编程，非重复实现。

### A-6. 原 F-1（asset-table-create-dialog 巨型组件）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-13
- **证据**：`components/AssetTable/CreateDialog.vue` 不存在。
- **后续约束**：DR-5 文件规模红线（≤500 行）对新组件继续生效。

### A-7. 操作日志查询三处实现（本次修复）
- **状态**：✅ 已关闭（本次已修复） | 关闭日期：2026-08-13
- **修复内容**：
  - `services/operation_log_service.py::OperationLogQueryService` 全部 8 个查询方法改为委托 `OperationLogSelector`（唯一实现），View→Service→Selector 三层调用链。
  - `models/operation_log.py` 删除 `AssetOperationLogManager` 4 个无调用方方法及类，`objects` 还原为标准 `models.Manager()`。
- **证据**：`rg -n "AssetOperationLogManager" asset_management_backend --glob "*.py"` 仅剩 `models.py:1414` 注释行。
- **验证命令**：`pytest apps/assetmanagement/tests/test_operation_log_service.py apps/assetmanagement/tests/test_operation_log.py -q`（44 passed）；`ruff check apps/assetmanagement/services/operation_log_service.py apps/assetmanagement/models/operation_log.py`（通过）。

### A-8. 前端资产状态映射字面量重复（本次修复）
- **状态**：✅ 已关闭（本次已修复） | 关闭日期：2026-08-13
- **修复内容**：`src/utils/Format.ts::assetCurrentStatusMapping` 由字面量表改为从 `statusMapping.ts::ASSET_STATUS_MAP` 派生（`Object.fromEntries(Object.entries(ASSET_STATUS_MAP).map(...))`），标签值完全等价，消除 8 个重复字面量。`getAssetStatusText` 保留可空包装（返回 `'未知'`）。
- **已知行为差异**：派生映射继承 `ASSET_STATUS_MAP` 的键序（`在库/在用/已回收待发放/...`），与旧字面量顺序相比 `在用` 与 `已回收待发放` 互换，影响 `useAssetListConfig.ts` 过滤下拉的选项顺序（纯外观，非契约）。
- **验证命令**：`npm run type-check`、`npx vitest run src/utils/__tests__/Format.spec.ts`（75 passed）、`npx eslint src/utils/Format.ts`。

### A-9. 前端资产状态回退行为统一（C-1 决策落地，本次修复）
- **状态**：✅ 已关闭（本次已修复） | 关闭日期：2026-08-13
- **决策（用户批准）**：未知状态回退**原始值**；空值（null/undefined/''）统一回退 `'未知'`。
- **修复内容**：
  - `Format.ts::getAssetStatusText` 回退由 `'未知'` 改为原始值，并委托 `statusMapping.getAssetStatusText`（DR-1 收敛为单一实现，消除函数体重复）。
  - `BasicAssetDetails.vue` 删除本地第三处实现（原回退 `'未知状态'`），改为委托 `Format.getAssetStatusText`；原 null 回退 `'未知状态'` 统一为 `'未知'`。
  - `Format.spec.ts` 同步断言（CT-4）。
- **验证命令**：`npx vitest run src/utils/__tests__/Format.spec.ts`、`npm run type-check`。

---

## B — 待修复（To Fix）

### B-1. 审计适配器克隆（DepartmentAuditAdapter vs EmployeeAuditAdapter）
- **判定**：克隆（结构同构：try/except + GenericAuditService 委托 + record_code/app_label/description 模式），差异仅为模型字段与 app_label；Employee 版多一个 `log_state_change`。
- **位置**：`apps/usermanagement/audit_adapter.py` vs `apps/usermanagement/employee_audit_adapter.py`（log_create/log_update/log_delete 三方法同构）。
- **修复建议**：抽公共基类 `BaseAuditAdapter`（参数化 app_label/实体名/快照字段），约省 150 行。
- **优先级**：低（两适配器均小于 DR-5 上限，无行为差异风险）。**未执行**，留待独立 PR。
- **排期（2026-08-13 用户确认）**：纳入独立 PR 实施。
- **验证命令**：对比两文件方法体（已人工核验，2026-08-13）。

### B-2. types/outasset.ts::outassetStatusMapping 死副本
- **位置**：`src/types/outasset.ts:47`，与 `src/utils/Format.ts::outassetStatusMapping` 内容完全一致。
- **证据**：全仓仅 `types/outasset.ts` 定义导出，无任何消费方 import 它（`@/types/outasset` 的 outassetStatusMapping）。
- **修复建议**：删除该导出（属公共导出面变更，需批准后执行）；保留方为 `Format.ts`（被 useOutAssetDetailCards / OutAssetBasicDetails 消费）。
- **优先级**：低。**未执行**。
- **排期（2026-08-13 用户确认）**：纳入独立 PR 实施。

---

## C — 降级/待决策（Downgraded / Decision Gate）

### C-1. 前端资产状态回退行为三态分歧（已解决）
- **状态**：✅ 已解决（2026-08-13，用户决策：原始值回退），详见 [A-9](#a-9-前端资产状态回退行为统一c-1-决策落地本次修复)。

### C-2. outasset 映射语义碰撞（命名冲突，不可合并）
- **描述**：同名 `outassetStatusMapping` 实为两套不同域：
  - `statusMapping.ts::OUTASSET_STATUS_MAP`（active/returned/overdue = 出库单记录状态）
  - `Format.ts:364` 与 `types/outasset.ts:47`（recycled_pending/in_use/damaged/scrapped = 资产当前状态）
- **判定**：不可合并，仅命名易混淆。建议后续重命名（如 `OUTASSET_RECORD_STATUS_MAP` vs `OUTASSET_ASSET_STATUS_MAP`）。
- **阻塞原因**：重命名触及公共导出面，需批准；且需同步 types/outasset.ts 枚举语义。

### C-3. 错误码重复/未注册（v1.7 BizCode 遗留债）
- **描述**：`INVALID_STATE_TRANSITION` 在 services 中约 10 处 raise，但 `utils/response_utils.py` BizCode 注册表无此键；前端 `entityStoreTypes.ts:82` 消费 `error_code`。
- **判定**：降级处理，不纳入本次修复。属 API 可见变更（错误码契约），须由根级统筹。
- **验证命令**：`rg -n "INVALID_STATE_TRANSITION" asset_management_backend/utils/response_utils.py`（预期无命中，证未注册）。

---

## D — 待核查（To Verify）

- **当前为空**。新发现重复模式请在此登记后再决定流向（关闭/修复/降级）。

---

## 附：回归护栏（可验证不变量）

由 `scripts/check_duplicate_invariants.py` 守护，CI job `duplicate-guard.yml` 触发：

| ID | 不变量 | 守护方式 |
|:--|:--|:--|
| G-1 | 已关闭模式的函数名不得复现 | 关键词黑名单（validate_asset_status、filter_assets、AssetQueryManager 等）全仓 grep |
| G-2 | 操作日志查询唯一实现 | `operation_log_service.py` 必须 import `OperationLogSelector`，且 `AssetOperationLogManager` 不得重新出现 |
| G-3 | 前端资产状态映射单一来源 | `Format.ts` 不得包含资产状态标签字面量表（已改为派生）；`statusMapping.ts` 为唯一字面量来源 |
| G-4 | 新错误码必须注册 | 任何新增 raise 的 error_code 常量须在 `response_utils.py` 中注册（grep 校验） |

> G-4 为"仅守护新代码"提示型检查：扫描最近提交新增的 error_code，与注册表比对，不满足即 fail。

## 变更记录
- **v2.1 (2026-08-13)**：落地 C-1 决策（未知状态回退=原始值），新增 A-9；B-1/B-2 确认排入独立 PR。
- **v2.0 (2026-08-13)**：由静态清单重构为四区活账本。关闭原 A-1~F-1 全部 11 条（含证据）；登记本次 2 项修复（A-7/A-8）、2 项待修复（B-1/B-2）、3 项降级/决策门（C-1/C-2/C-3）；新增回归护栏不变量（G-1~G-4）。
