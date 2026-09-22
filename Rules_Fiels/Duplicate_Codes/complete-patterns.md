# 重复代码模式活账本（Living Ledger）
> **版本**：v2.9.36 | **最后更新**：2026-09-22 | **性质**：动态账本，取代 v1.0 静态清单
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

### A-10. Selector 死方法簇×7 + 专属测试（F-6）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-24 | commit b5091d5
- **修复内容**：删除 `out_asset_selector.py` 5 个死方法 + `recycle_asset_selector.py` 2 个死方法 + 对应 5 个专属测试方法。净减 102 行。
- **验证命令**：`ruff check apps/assetmanagement/selectors/` + `pytest apps/assetmanagement/tests/ -q`

### A-11. dashboard STATUS_LABELS 硬编码字典（F-3）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-24 | commit 9b15833
- **修复内容**：`dashboard_selector.py` 中 `STATUS_LABELS` 硬编码 dict 替换为 `Asset.ASSET_STATUS_CHOICES`（验证 14 项完全匹配，零填充语义保持）。净减 10 行。
- **验证命令**：`ruff check apps/assetmanagement/selectors/dashboard_selector.py`

### A-12. 审计适配器 exc_info 漂移（F-2 附带）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-24 | commit a7fb4ca
- **修复内容**：department adapter 3 处 + role adapter 3 处 `exc_info=True` 漂移修复（原 exc_info 条件分支在 `except Exception` 之后，永远不会执行）。合并入 F-2 safe_audit_log 提交。
- **验证命令**：`ruff check apps/usermanagement/audit_adapter.py apps/usermanagement/role_audit_adapter.py`

### A-13. 手写批量创建循环×3 → batch_execute（F-1）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-24 | commit 7439ed7
- **修复内容**：`storage_service.batch_create_storage`、`contract_service.batch_create_contract`、`asset_type_service.batch_create_asset_type` 三处手写循环收敛至 `BatchOperationMixin.batch_execute`。净减 81 行。
- **行为等价**：deepcopy 保留在闭包内，error_code BATCH_SIZE_EXCEEDED 不变，新增 `_normalize_input_data` 防御（B-8）。
- **例外**：F-5（unregisteredasset batch_create）因 7 处行为差异暂不收敛，已登记 D-1。
- **验证命令**：`pytest apps/assetmanagement/tests/ -q`

### A-14. exception_handler IntegrityError + View try/except 清理（F-7）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-24 | commit 0aa99f9
- **修复内容**：
  - `core/exception_handler.py` 新增 `IntegrityError → 400` 映射（unique/foreign_key/not_null/check），消除 IntegrityError 暴露为 500。
  - `views.py` 删除 3 处冗余 `try/except AppValidationError`（DRF handler 已转为 400）+ 1 处残留 debug `print`。
  - 保留 13 处有 `except Exception` fallback 的块（删除会变 500）+ 19 处 DoesNotExist/ValueError 块。
- **净变化**：+13 行（exception_handler）-17 行（views.py）
- **验证命令**：`mypy . --config-file pyproject.toml` + `ruff check core/exception_handler.py apps/assetmanagement/views.py`

### A-16. Python 依赖清单双份维护（pyproject.toml vs requirements/base.txt）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-26 | 来源：H-1 上线七维审查整改
- **判定**：同一组运行时依赖在两处声明且版本漂移 6 处（Django 6.0.5 vs 5.2.17-LTS、pillow 11.3.0 vs 12.3.0、requests 2.32.5 vs 2.33.0、PyJWT 2.10.1 vs 2.13.0、drf-spectacular 0.28 vs 0.29、sidecar 2025.1.24 vs 2026.4.14），另缺失 channels/daphne/channels-redis/redis/prometheus-client/sentry-sdk/urllib3/chardet 共 8 包。
- **修复内容**：删除 pyproject.toml `[project] dependencies` 整块（原位注明唯一事实源为 requirements/base.txt）；classifiers 由 `Framework :: Django :: 6.0` 修正为 `:: 5.2`。requirements/base.txt 成为唯一事实源（DR-1）。
- **证据**：Dockerfile 与全部 CI workflow 均从 requirements/*.txt 安装，全仓无 `pip install -e .` 使用方。
- **验证命令**：`python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"`（解析通过）；`pip install -e . --dry-run`（仅安装项目自身元数据）；`python -m ruff check .`（通过）。
- **回滚风险**：若未来恢复 pip install -e . 用法，须先恢复 dependencies 并与 base.txt 逐项核对版本。
- **A-16 变更 (2026-09-13)**：根级决策将 base.txt 的 Django 钉版由 5.2.17-LTS **升至 6.0.5**，对齐方向为"锁文件匹配实际运行环境"而非降级环境。依据：本地 `.venv` 长期运行 Django 6.0.5（assetmanagement 迁移 0021/0022 于 2026-09-12 由其生成）；根 README、CheckReport.md、backend-business-rules 均标注 Django 6.0/6.0.5；dev.txt 钉 django-stubs==6.1.0（Django 6.x 时代 stub），升版后 mypy 门禁与镜像自洽。本变更**推翻**此条目原 5.2.17 判定（原判定语境为 pyproject.toml vs base.txt 的双份清单新旧之争），现明确 base.txt 仍为唯一事实源（DR-1），仅版本值更新。注意：6.0 为功能版本非 LTS，如需 LTS 支持应待 6.2 LTS 发布后另行评估。决策留痕，防止再次回退。

### A-15. BatchDeleteValidationMixin 收敛 validate_ids×11（F-4）
- **状态**：✅ 已关闭 | 关闭日期：2026-08-24 | commit 2022814
- **修复内容**：新增 `core/batch_mixins.py::BatchDeleteValidationMixin`，替换 11 个 BatchDeleteSerializer 中完全相同的 `validate_ids`。净减 47 行。
- **validate_items 不收敛**：每个模块唯一性字段不同（contract_code/storage_code/type_code/asset_code/employee_jobcode/department_code），不适合统一 mixin。
- **验证命令**：`mypy . --config-file pyproject.toml` + `pytest apps/ -q`

### A-17. 前端批量导入模板导出收敛 handleExportTemplate×8 → downloadExcelTemplate（审计第 7 项）
- **状态**：✅ 已关闭 | 关闭日期：2026-09-09 | 本次修复
- **修复内容**：
  - 8 个批导入组件（Asset/AssetType/Contract/OutAsset/Storage/Unregistered/Damaged/Department）的模板导出统一收敛至 `src/utils/batchImport/templateExport.ts::downloadExcelTemplate`，删除各组件的内联 ExcelJS 实现（各 ~30-40 行 → ~10 行数据声明）。
  - 删除重复工具 `src/utils/exportImportTemplate.ts`（与 templateExport.ts 近同构的第二个实现，DR-1 内部双实现违规），Storage 由 exportImportTemplate 迁移至 downloadExcelTemplate。
  - 相关组件清理孤儿 `import ExcelJS from 'exceljs'` 与 `InfoFilled` 未使用引用。
- **证据**：`rg -n "new ExcelJS.Workbook" src/components/componentsdetails/detils --glob "*.vue"`（批导入组件 0 命中；UserBatchImport 除外，见 B-9）。
- **验证命令**：`npm run type-check` + `npm run lint` + `npm run format:check`（通过）；`npx vitest run src/utils/__tests__/batchImportHelpers.spec.ts`（通过）。
- **回滚风险**：若新增批导入组件，模板导出必须复用 `downloadExcelTemplate`。

### A-18. 前端分页 page-sizes 字面量收敛 → PAGE_SIZE_OPTIONS（审计第 9 项）
- **状态**：✅ 已关闭 | 关闭日期：2026-09-09 | 本次修复
- **修复内容**：`[10, 20, 50]` 字面量在 5 个文件（ContactsView/AuthUserManage/RoleManage/NotificationList/DepartmentEmployeeList）重复，新建 `src/utils/pagination.ts::PAGE_SIZE_OPTIONS` 单一来源，全部改引用。
- **范围说明**：CommonList 默认 `[20,50,100,200,500]` 是另一组分档，**不属于**本收敛目标，保持不变。
- **验证命令**：`rg -n "page-sizes" src`（无 `[10, 20, 50]` 字面量）；`npx vitest run src/utils/__tests__/pagination.spec.ts`（3 passed）。

### A-19. 残留裸查询治理（B12 收尾，本次修复）
- **状态**：✅ 已关闭 | 关闭日期：2026-09-18 | 本次修复
- **修复内容**：
  1. **三处删除守卫收敛**：`storage_service.py:96` / `contract_service.py:206-209` / `asset_type_service.py:135` 的 `Asset.objects.filter(..., is_deleted=False).exists()` 裸查询全部收敛至 `AssetSelector.exists_by_storage / exists_by_contract / exists_by_asset_type`（新增 3 个 staticmethod，docstring 豁免清单 #7/8/9，与 `exists_by_code` 同类的全局主数据删除守卫豁免）。同时清理孤儿 import（storage/asset_type 顶层去 `Asset`，contract 删除函数内局部 `import Asset`）。
  2. **死方法删除**：`waste_asset_selector.py` / `damaged_asset_selector.py` 各删 `get_asset_recordcode_by_asset_code`（A-10 同型死方法）+ 对应 4 个测试方法。净删 ~40 行。
- **行为等价**：替换谓词逐字节一致（同一 FK 字段 + is_deleted=False），HAS_RELATED_ASSETS 错误码与文案未变。
- **验证命令**：`rg -n "get_asset_recordcode_by_asset_code" asset_management_backend --glob "*.py"`（预期 0 命中）；`pytest apps/assetmanagement/tests/ -q` 全量 1155 passed；Service 覆盖率 93.06%（≥90）；整体覆盖率 81.61%（≥80）。

### A-20. AC-61 审计断链：回收二次 FSM 转换裸奔（用户审计项"B7"）
- **状态**：✅ 已关闭 | 关闭日期：2026-09-18 | 本次修复
- **编号说明**：用户审计项编号"B7"与既有闸板条目 **B-7（throttles 登录名三重复制）** 重号，为保持活账本 ID 唯一，本项目登记为 A-20，原文案引以「用户审计项 B7」。约：非重复代码复制问题，属 AC-61 全链路审计缺口（可观测性违规）。
- **诊断**：`apps/assetmanagement/services/recycle_asset_service.py` `create_recycle_asset` 的 broken/lost 分支先 `_do_recycle_asset_update`（内含第一次转换 recycle→recycled_pending + `log_asset_recycle` 审计），随后 `AssetFSM.mark_broken/mark_lost`（recycled_pending→broken/lost）与 `asset.save()` 之间**无任何 log_state_change**，仅创建 BrokenAsset/LostAsset 收尾——二次状态跳变（伴随 broken_reason/lost_reason）不可追溯。同域先例：`cancel_recycle`（:296）、repair（:93/:209/:253）、damaged（4 处）、asset_service（:378）、out_asset_service（:294）均每转换一记。
- **修复内容**：broken/lost 分支 `asset.save(update_fields=["asset_current_status"])` 之后、子记录创建之前，各插入 `AuditLogger.log_state_change(asset=asset, from_state=RECYCLED_PENDING, to_state=BROKEN/LOST, trigger="recycle_mark_broken"/"recycle_mark_lost", operator_jobcode=operator_jobcode or fallback_jobcode, operator_name=operator_name or "")`；operator 回退逻辑与 `_do_recycle_asset_update` 完全一致（存量先例复用）；normal 分支不动。零新增 import；枚举成员名与 `mark_broken/mark_lost` 内部写入值一致（AssetState.BROKEN/LOST.value）。
- **CT-1 补全**：该路径此前**零测试覆盖**（全 tests 目录 grep `is_broken|is_lost` = 无命中），本次新增 `test_recycle_asset_service.py::TestRecycleWithBrokenLostMarks` 3 条用例（broken 审计 / lost 审计 / normal 反向回归护栏：断言 normal 路径不得泄漏 broken/lost 触发日志）。
- **验证命令**：`pytest apps/assetmanagement/tests/test_recycle_asset_service.py -q`（19 passed +3）；rec交叉向 32 passed；全量 1165 passed、整体覆盖率 81.73%（≥80）；app 级 mypy strict 26 条存量不变、recycle_asset_service 零新增；ruff 改动 2 文件 0 错误。

### A-21. asset_service 单条/批量删除守卫重复 + 批量删除框架手写（审查报告 #9）
- **状态**：✅ 已关闭 | 关闭日期：2026-09-20 | 本次修复
- **判定**：克隆。`delete_asset` 与 `batch_delete_asset` 逐条重复「状态非在库 / 出库记录 / 待报废记录 / 审计+软删除」4 步；且 `batch_delete_asset` 手写 BATCH_SIZE 前置校验 + 循环 + AppValidationError 收集 + 兜底 INTERNAL_ERROR + 结果 dict 组装，与 `core/batch_mixins.py::batch_delete_execute` 重复——B-5 已收敛其余 6 服务（asset_type/contract/storage/out_asset/recycle），唯独漏了 asset。
- **位置**：`apps/assetmanagement/services/asset_service.py`（修复前 `delete_asset:217-242` / `batch_delete_asset:273-347`；审查报告原述 `IN_USE vs ASSET_IN_USE` 有误，真实分叉为 `ASSET_HAS_OUTASSET` vs `HAS_OUTASSET_RECORDS`）。
- **修复内容**：新增 `_delete_guarded`（守卫 + 审计 + `asset.delete()` 的唯一实现，DR-1）；`delete_asset` 复用之；`batch_delete_asset` 收敛至 `BatchOperationMixin.batch_delete_execute`（闭包 `_delete_one` 保留 B12 NOT_FOUND 映射，守卫调用置于 try 之外防误映射）；错误码分叉 `HAS_OUTASSET_RECORDS` 统一为 `ASSET_HAS_OUTASSET`。净减约 50 行。
- **行为等价**：响应结构（total/success_count/fail_count/success_ids/fail_items）与守卫顺序不变；BATCH_SIZE_EXCEEDED 同码同文案；唯一对外值变化为批量出库 fail_items 的 error_code 与 error_message（前端不消费 error_code，G-4 无需注册）。
- **CT-4 护栏**：新增 3 用例（批量出库失败码统一 / 混合逐条独立 / TOCTOU 锁内不可见归入 NOT_FOUND）。
- **验证命令**：`pytest apps --cov=apps --cov-fail-under=80 -q`（972 passed，整体 84.16%）；`rg -n "HAS_OUTASSET_RECORDS" apps core --glob "*.py"`（预期 0）；`python scripts/check_duplicate_invariants.py`（PASS）；Service 层覆盖率 95.00%。

### A-22. damaged_asset_service 三处手写「过滤+判空+加锁」绕过 Selector（审查报告 #10）
- **状态**：✅ 已关闭 | 关闭日期：2026-09-20 | 本次修复
- **判定**：克隆 + 孤儿抽象。approve/reject/cancel 三处逐字重复「`filter(asset_recordcode__recordcode=…, is_deleted=False).first()` → 判空抛 `DAMAGED_ASSET_NOT_FOUND` → `select_for_update().get(pk=…)` 重取加锁」；仓库已有的 `DamagedAssetSelector.get_asset_recordcode_for_update` 全仓 0 调用方（含测试）。
- **位置**：`apps/assetmanagement/services/damaged_asset_service.py`（修复前 `:138-147 / :213-221 / :277-285`）；被绕过的抽象在 `apps/assetmanagement/selectors/damaged_asset_selector.py`。
- **前置缺陷（本次一并修复）**：该 Selector 自身不可用——`DamagedAsset.objects.with_asset_details().select_for_update()` 中 `with_asset_details()` 对可空 `asset_recordcode`（OneToOneField null=True）与 `approver` 生成 LEFT OUTER JOIN，PostgreSQL 抛 `NotSupportedError: FOR UPDATE ... nullable side of an outer join`。因从未被调用故此前未暴露。
- **修复内容**：Selector 去掉 `with_asset_details()`（单查询仅锁主表），并加注释禁止叠加 `select_related`；三处调用点改为 `try: damaged_asset = DamagedAssetSelector.get_asset_recordcode_for_update(...) except DamagedAsset.DoesNotExist: raise AppValidationError(..., "DAMAGED_ASSET_NOT_FOUND") from None`。
- **行为等价**：错误码/detail/响应结构/方法签名全保留；原「检查→加锁」两步间的 TOCTOU 窗口被消除（更严）。
- **CT-4 护栏**：复用既有 `TestDamagedAssetSelector` 新增 3 用例（命中加锁实例 / 缺失 `DoesNotExist` / 软删等同不存在）。
- **验证命令**：`pytest apps --cov=apps --cov-fail-under=80 -q`（975 passed，整体 84.17%）；`rg -n "asset_recordcode__recordcode=" apps/assetmanagement/services --glob "*.py"`（预期 0）；先红证据：修复前 3 failed（`NotSupportedError`）。

### A-23. usermanagement 同名模块 `services.py` 以包遮蔽成为影子死代码（审查报告 #11）
- **状态**：✅ 已关闭 | 关闭日期：2026-09-20 | 本次修复
- **判定**：死代码 + 克隆（DR-1，B-11 应用级同型）。`apps/usermanagement/services.py`（277 行）与同名 `services/` 包并存，各实现一套 `EmployeeService`/`DepartmentService`；实测 `FileFinder.find_spec('services')` → 包 `__init__.py`、`is_package=True`，包优先解析，`.py` 版永不参与生产导入（`__pycache__/services.cpython-313.pyc` 为历史编译残留）。
- **靶点修正**：影子**可正常导入**——`core/exceptions.py:72` 定义 `BusinessLogicError`，`:119` 定义 `ValidationError = AppValidationError` 别名，故死因纯系包优先解析，而非引用缺失异常类；另 `services.py:527/182/391-418` 等旧行号属更老 527 行版本快照，早已失效。
- **位置**：`apps/usermanagement/services.py` + `__pycache__/services.cpython-313.pyc`（均已删除）；权威实现为 `apps/usermanagement/services/` 包内 4 文件。
- **修复内容**：删除影子 `services.py` 与其编译产物；包内 4 个 service 及既有未提交改动不动。方法清单 diff 留证：影子 EmployeeService={create_employee, change_employee_status}、DepartmentService={create_department, move_department, _update_children_level, _get_max_child_depth, batch_update_sort_order} 均为包版子集，零独有逻辑；`_update_children_level` 包版以 `_update_children_paths_and_levels`（含 path 维护）增强替代。
- **行为等价**：10 个 import 落点（5 生产：employee_view/employee_auth_mixin/department_view/role_view/my_permissions_view + 5 测试）全落包，删前删后导入解析一致（皆为包），删除仅移除不可达代码，契约零变化。
- **验证命令**：`pytest apps/usermanagement -q`（99 passed，基线 99）；`ruff check apps/usermanagement`（0→0 `All checks passed!`）；`mypy apps/usermanagement --strict`（仅存量 `models.py:122`，零新增）；`python manage.py check`（no issues）。

### A-24. 【关闭 2026-09-21】mark_asset_broken / mark_asset_lost 状态流转双胞胎（原 B-23，C10 统一）
- **判定**：克隆（DR-1 风险面）。`asset_lifecycle_mixin.py` 标记损坏与标记遗失两方法逐段同构：`select_for_update` 取资产 + `ensure_asset_visible`（BEQ-02 行级隔离）+ 终态幂等分支（已有记录返回/补建）+ FSM 转换（`InvalidTransitionError`→`INVALID_STATE_TRANSITION`）+ `save(update_fields=...)` + 子记录 create + `refresh_from_db()`（DateField 序列化修正）+ `AssetOperationLog` + 文案/返回值。
- **位置**：`apps/assetmanagement/services/asset_lifecycle_mixin.py:26`（`mark_asset_broken`，60 行）vs `:89`（`mark_asset_lost`，63 行，BR-4 B3 台账第 4 行，52 逻辑行）。
- **六处差异**：① 目标状态枚举 `BROKEN`/`LOST`；② 子记录模型 `BrokenAsset`/`LostAsset`；③ FSM 方法 `AssetFSM.mark_broken`/`mark_lost`；④ `AssetOperationLog.OperationType.BROKEN/LOST`；⑤ 文案前缀「已损坏」/「已遗失」；⑥ lost 独有可选参数 `last_known_location` + `lost_description`（broken 为 `broken_reason` + `broken_description`）。
- **关闭手段（C10，2026-09-21 落地）**：抽模块级 `_run_lifecycle_transition`（:22-77，47 逻辑行）收敛幂等分支/FSM/子记录/审计全流程，`mark_asset_broken`（21 行）与 `mark_asset_lost`（26 行）降为差异化参数薄封装（六处差异经 `target_status`/`fsm_method`/`record_model`/`record_kwargs`/`operation_type`/`audit_description` 注入）；保留 `AssetOperationLog.objects.create` 原调用（不走 AuditLogger，行为不变）；闭包注解 :316/:340 修正 `-> BrokenAsset`/`-> LostAsset`；mypy 26→24 目标达成（新增 no-any-return 经 `cast` 消除）。
- **状态**：✅ 已关闭（2026-09-21，C10）。
- **验证命令**：`pytest apps/assetmanagement/tests/test_asset_lifecycle.py apps/assetmanagement/tests/test_state_machine.py -q`（78 passed，lost 幂等 :99 锚 + FSM :130 锚原样通过）；`python scripts/check_function_length_guard.py`（PASS 0/0，台账 B3 同提交移除）。

### A-25. 【关闭 2026-09-21】unregisteredasset 审计留痕 try/except×4（原 B-22，C10 收尾①收敛）
- **判定**：同构重复（DR-1 风险面）。未登记资产业务四类写操作（create/update/approve/delete）各自包裹逐字同构的「审计留痕块」：延迟导入 `UnregisteredAssetAuditAdapter` + `try/except Exception` + `logger.warning(f"审计日志记录失败(<op>): {e}", exc_info=True)` + `【P2-10 修复】` 注释。
- **位置**：`apps/unregisteredasset/services.py` —— `_log_create_audit`(:88-100)、`_log_update_audit`(:112-132)、`_log_approve_audit`(:184-204)、`delete_unregistered` 内联(:442-451)。
- **收敛进展（2026-09-21，C4）**：create/update/approve 三处已提升为模块级 `_log_*_audit` helper（重复面由"散落业务方法内"缩小为"独立 helper 间"）；`delete_unregistered` 内联块未处理，仍逐字同构。三 helper 主体仍互为镜像（仅 audit 方法名 + 文案前缀不同）。
- **关闭手段（2026-09-21，C10 收尾①）**：新增模块级 `_safe_call_audit(operation, *args, **kwargs)`（:89，唯一 try/except + `getattr(UnregisteredAssetAuditAdapter, f"log_{operation}")` 分派 + 唯一 `审计日志记录失败` 文案）；三既有 helper 改为薄委托，`delete_unregistered` 内联块替换为直接调用 `_safe_call_audit("delete", ...)`。行为等价：延迟导入/异常吞并/文案逐字（operation 前缀相同）。
- **状态**：✅ 已关闭（2026-09-21）。
- **验证命令**（收敛后）：`rg -n "审计日志记录失败" apps/unregisteredasset/services.py`（仅 :96 `_safe_call_audit` 内 1 处）；`pytest apps/unregisteredasset -q --create-db`（86 passed 零回归）；`python scripts/check_function_length_guard.py`（PASS 0/0）；`ruff check` clean；`mypy` 目标文件 0 新增。

### A-26. 前端 10 处 XxxBatchCreateResult 接口骨架复制（审查报告 #24，DR-1/DR-4）
- **状态**：✅ 已关闭 | 关闭日期：2026-09-21 | 本次修复
- **判定**：克隆（DR-1）+ 工具函数散落（DR-4）。10 处 `XxxBatchCreateResult` 接口（api/7 处内联 + types/3 处）逐字重复相同骨架（total/success_count/fail_count/success_items: T[]/fail_items: Array<{index/error_code/error_message/input_data: F/row_number?}>），仅 success_items 元素类型与 input_data 类型不同。
- **位置**：
  - api/asset.ts:44 `AssetBatchCreateResult`（AssetDetail, AssetCreateForm）
  - api/assetType.ts:29 `AssetTypeBatchCreateResult`（AssetType, AssetTypeCreateForm）
  - api/contract.ts:31 `ContractBatchCreateResult`（Contract, ContractCreateForm）
  - api/department.ts:36 `DepartmentBatchCreateResult`（Department, DepartmentCreateForm）
  - api/outAsset.ts:32 `OutAssetBatchCreateResult`（OutAssetDetail, OutAssetCreateForm）
  - api/storage.ts:30 `StorageBatchCreateResult`（Storage, StorageCreateForm）
  - api/user.ts:34 `EmployeeBatchCreateResult`（EmployeeExtended, EmployeeCreateForm）
  - types/brokenasset.ts:76 `BrokenAssetBatchCreateResult`（BrokenAssetExtended, Record<string, unknown>）
  - types/lostasset.ts:167 `LostAssetBatchCreateResult`（LostAssetExtended, LostAssetBatchItem）
  - types/recycleasset.ts:180 `RecycleAssetBatchCreateResult`（RecycleAssetExtended, RecycleAssetBatchItem）
- **收敛先例**：`BatchDeleteResult` 已由各 api 文件统一从 `@/stores/createEntityStore` 引入（单一定义）。
- **修复内容**：`src/types/common.ts` 新增 `BatchCreateFailItem<F = unknown>` + `BatchCreateResult<T, F = unknown>` 泛型基类型；10 处 interface 改为 type 别名（`export type XxxBatchCreateResult = BatchCreateResult<T, F>`）；7 个 api 文件新增 `import type { BatchCreateResult } from '@/types/common'`；3 个 types 文件追加 BatchCreateResult 到已有 common 导入。
- **行为等价**：零运行时变更（纯类型层）；消费方零改动（同名导出）；契约无变化。
- **验证命令**：`npm run type-check`（0 错误）；`npx vitest run src/stores/__tests__ src/api/__tests__`（59 文件 774 测试通过）；`npm run lint`（通过）；`rg -c "export interface.*BatchCreateResult" src/api src/types --glob "*.ts" --glob "!*.d.ts"`（预期仅 common.ts 1 处）。

### A-27. 前端双分页响应类型并存（`ListResponse` vs `PaginatedResponse`，审查报告 #25，DR-1）
- **状态**：✅ 已关闭 | 关闭日期：2026-09-21 | 本次修复
- **判定**：克隆（DR-1）。`stores/entityStoreTypes.ts` 的 `ListResponse<T>`（count/results/total_pages?/page?/page_size?）与 `types/common.ts` 的 `PaginatedResponse<T>`（DRF 契约全字段：count/next/previous/results/total_pages/page/page_size）各自独立定义分页形状，且 18 个 store 在 `getList` 中手工把 `response.next`/`response.previous` 逐字段搬进映射对象，形成第二套「事实上的分页形状」。
- **位置**：
  - `src/stores/entityStoreTypes.ts:63` `ListResponse<T>`（旧为独立 interface，现为派生别名）
  - `src/types/assettype.ts:98` `AssetTypeListResponse`
  - `src/types/contract.ts:217` `ContractListResponse`（另含死类型 `ContractListResponseOld`）
  - `src/types/department.ts:113` `DepartmentListResponse`（另含注释版 `DepartmentListResponseOld`）
  - `src/types/user.ts:155` `EmployeeListResponse`（另含注释版 `EmployeeListResponseOld`）
  - `src/types/storage.ts:136` `StorageResponse`
  - 18 个 `src/stores/*Store.ts` 的 `getList` 映射（authUser/assetType/damagedAsset/brokenAsset/department/contract/harddiskSn/lostAsset/foundAsset/operationLog/outAsset/storage/role/waste/user/recycle/repair/unregistered）
- **修复内容**：① `entityStoreTypes.ts` 的 `ListResponse<T>` 改为 `PaginatedResponse<T>` 派生别名 —— `Pick<PaginatedResponse<T>, 'count' | 'results'> & Partial<Pick<PaginatedResponse<T>, 'next' | 'previous' | 'total_pages' | 'page' | 'page_size'>>`（`count`/`results` 必填，其余可选以兼容旧消费方），新增 `import type { PaginatedResponse } from '@/types/common'`；② 5 处领域手写接口改为 `export type Xxx = PaginatedResponse<T>` 别名（保留原导出名，消费方零改动）；③ 删除 18 个 store 中冗余的 `next: response.next,` / `previous: response.previous,`（各 2 行，共 36 行）；④ 删除旧兼容死类型 `ContractListResponseOld` 与注释版 `EmployeeListResponseOld`/`DepartmentListResponseOld`。
- **行为等价**：零运行时变更（纯类型层 + 删除无读取方的死键）。`createEntityStore` 工厂仅消费 `count`/`results`/`total_pages`/`page`/`page_size`；全仓无任何代码读取该映射对象的 `next`/`previous`（`rg` 仅命中 `Map.keys().next()`，非分页语义）。
- **测试豁免说明**：`vue-assetmanagement/tsconfig.app.json` 的 `exclude` 含 `src/**/__tests__/*`，spec fixture 缺 `total_pages`/`page`/`page_size` 不参与 `type-check`（既有项目设计，vitest 走 esbuild 不做类型检查），故严格化后的领域类型未对测试 mock 产生编译期约束。
- **验证命令**：`npm run type-check`（0 错误）；`npx vitest run src/stores/__tests__`（32 文件 495 测试通过）；全量 `npm test`（135 文件 1912 测试通过）；`npm run lint` / `npm run format:check`（通过）；`rg "next: response\.next|previous: response\.previous" vue-assetmanagement/src/stores`（预期 0 命中）；`rg "ContractListResponseOld|EmployeeListResponseOld|DepartmentListResponseOld" vue-assetmanagement/src --glob "!__tests__"`（预期 0 命中）。
- **回滚风险**：`PaginatedResponse` 若未来放宽 `next`/`previous` 必填性，需同步复核 5 处领域别名与 `ListResponse` 的 `Partial` 集；`count`/`results` 为唯一强契约字段，不得移除。

### A-28. 前端 Excel 导出流程三归一并（`useExcelExport` / `useOperationLogExcelExport` / `useUserExcelExport`，审查报告 #26，DR-1/FR-2）
- **状态**：✅ 已关闭 | 关闭日期：2026-09-21 | 本次修复
- **判定**：克隆（DR-1）+ 未复用既有抽象（FR-2）。三份实现均含「导出范围选择弹窗 > 当前页/全量分支 > >1000 条大数据确认 > fetch 全量 > exportToExcel 收口」完整流程：
  - `composables/useExcelExport.ts`（154 行）：通用版，`ExportOptions<T>` 参数化，8+ 详情页在用；
  - `composables/useOperationLogExcelExport.ts`（112 行）：自建 `ElMessageBox.confirm` 范围弹窗 + 自建分支；
  - `composables/useUserExcelExport.ts`（168 行）：自建 h() 弹窗 + 自建分支 + 自建部门映射。
- **位置**：`vue-assetmanagement/src/composables/useOperationLogExcelExport.ts`、`vue-assetmanagement/src/composables/useUserExcelExport.ts`（收敛前）；收敛后仅剩通用 `useExcelExport.ts` 一处流程实现。
- **事实纠偏（对抗审核）**：方案初稿「User 版实际在用 additionalData」不成立——`ExcelExportConfig.additionalData` 声明于 `excelExporter.ts:39` 但 `exportToExcel` 函数体（:47-129）从不读取；User 版部门映射靠列 formatter **闭包**（`useUserExcelExport.ts:64`）生效，`additionalData: { departmentMapping }` 为死透传。故不新增 additionalData 透传，并移除 User 版传递与 spec 断言。
- **修复内容**：两专用 composable 重写为「列配置 + 参数组装」薄壳（`useOperationLogExcelExport` 46 逻辑行 / `useUserExcelExport` 62 逻辑行，guard `--print` 权威计数），只保留列配置（9 列/8 列含 formatter 闭包）+ 组装 `ExportOptions`（`entityName`/`columns`/`currentData=store.list`/`totalCount=pagination.total`/`fetchAllData=() => store.getList({page:1,page_size:total})`/`sheetName`）+ 委托通用 `exportList`；签名与导出不变，消费方（OperationLogDetails/UserDetails）零改动；删除去往 `ElMessage/ElMessageBox/exportToExcel/h/showErrorMessage` 的 import。
- **行为差异清单（用户 2026-09-21 拍板统一）**：a) User 当前页文件名去 `pagination.page`；b) 全量失败 `showErrorMessage` → 通用版 `console.error + ElMessage.error`；c) 范围弹窗未知异常「吞掉」→ 通用版「重抛向上传播」；d) 文案统一（`正在准备全部XX数据，请稍候...`、大数据确认、范围弹窗 OpLog 简版升级为通用 h() 消息体）。
- **验证命令**：`npx vitest run src/composables/__tests__/useOperationLogExcelExport.spec.ts src/composables/__tests__/useUserExcelExport.spec.ts`（17 passed，先红 11 failed）；`npx vitest run src/composables/__tests__/useExcelExport.spec.ts`（8 passed）；全量 `npm test`（135 文件 1912 passed）；`npm run type-check`/`lint`/`format:check`（0 错/0/全绿）；`python scripts/check_duplicate_invariants.py` PASS；`python scripts/check_frontend_invariants.py` PASS（FR-6 composables 50 文件 / 4 孤儿已登记）；`rg -n "ElMessageBox\.confirm\(" src/composables`（预期仅 `useExcelExport.ts:90` 一处）。
- **回滚风险**：若通用版 `exportList` 某日调整范围弹窗交互，两薄壳同步受益（无实体逻辑）；`showErrorMessage` 语义已离场，需在 utils/errorHandler 登记归档。

### A-29. 【关闭 2026-09-22】Service 层 5 处裸查询下沉 Selector + 批量旧错误码 HTML 同步（DR-1/DR-3，§1.8 新发现义务登记）
- **编号冲突规避**：按 §1.8 新发现义务命名时撞号 A-23（已被 #11 影子 services.py 占用），沿用 v2.9.23 先例顺延命名。
- **状态**：✅ 已关闭 | 关闭日期：2026-09-22 | 本批修复
- **判定**：DR-3 违规（Service 层 5 处裸 `OutAsset/DamagedAsset.objects.filter/exists` 直查，未走 Selector 统一入口）+ §1.8 未登记。
- **靶点修正（归属核对）**：`asset_service.py:215/:219` 实为 A-21 收编时残留的裸守卫，`recycle_asset_service.py:319-321` 无人点名（扫描新发现）；原指该批属「审查报告 #10」系张冠李戴（#10=A-22 damaged approve/reject/cancel，已于 2026-09-20 关闭；其循 A-21 先例检出 3 处 `select_for_update().filter` 手写，与本批不重合）。
- **修复内容（5 处下沉，逐字保留查询形态，零行为变化）**：
  1. `OutAssetSelector.has_active_outasset`（`.filter(asset_recordcode=asset, is_deleted=False).exists()`）← `asset_service.py:215`；
  2. `DamagedAssetSelector.has_active_record`（同型 exists）← `asset_service.py:219`（asset_service 孤儿 import `OutAsset/DamagedAsset` 移除，selectors import 补 `DamagedAssetSelector/OutAssetSelector`）；
  3. `OutAssetSelector.get_active_outasset(recordcode)`（轻量 `.filter(recordcode, is_deleted=False).first()`）← `recycle_asset_service.py:319-321`；
  4. `OutAssetSelector.get_outasset_for_update(recordcode)`（`select_for_update().filter(recordcode, is_deleted=False).first()`）← `out_asset_service.py:276`（`_delete_one` 锁内）；
  5. `DamagedAssetSelector.get_for_update(recordcode)`（`select_for_update().filter(recordcode).first()`）← `damaged_asset_service.py:108`。
  不复用缘由：③ 不复用 `get_outasset_by_record_code`（其 `with_asset_details()` 有 select_related 开销，破坏轻量语义）；④ 不复用 ③（二者同族但 ④ 需锁，若让 ③ 加锁会扩锁=行为变化）。
- **观察项收口（2026-09-22 用户复核，三条已记录取舍）**：
  1. **不含 `is_deleted`**：`get_for_update` 保留既有查询形态（行为等价红线，不得擅自加过滤），与 #4 的 `is_deleted=False` 判定不一致处留待加固独立批次，不属本批射程。
  2. **未预取关联（已记录取舍，复核确认非问题）**：`get_for_update`（damaged_asset_selector.py:61）仅锁主表单行，唯一调用方 `update_damaged_asset`（damaged_asset_service.py:108）只改 3 个白名单自身字段 + :126 审计惰性读 FK 一次，无预取收益；锁场景叠 `with_asset_details()` 会触发 PostgreSQL 对可空 outer join 侧加锁的 NotSupportedError（A-22 :157 已实证）。`select_for_update(of=("self",))` 可绕过该坑并恢复预取——登记为**可选优化增强，未排期**（收益场景=approve/reject 高并发 + 列表热路径，当前未出现）。表述更正：原注引 `:172` Asset 行锁属 approve 家族（走 `get_asset_recordcode_for_update`），非本方法调用方。
  3. **行级隔离（已记录取舍，复核确认方向 + 修正一处越权面）**：`get_for_update`/`has_active_record` 不加 `user` 参数属既有设计（A-22 #10 修复时未涉）；隔离实证为——**View 层** `get_queryset_for_user`（damaged_asset_view.py:94-96）经 `RecordcodeLookupMixin.get_object()`（views/_mixins.py:24-42）对单对象写路径（update/partial_update/destroy/approve/reject）强制部门作用域，跨部门 recordcode 一律 404；by_asset（:190）另有资产预检；create 路径 `ensure_asset_visible`（:46-47）与资产删除路径 `get_asset_by_code(user=user)` 兜底（不成立表述：原注称「Asset 主表 :172 已 ensure_asset_visible」——:172 仅为 Asset 行锁，隔离不在锁上）。**例外（独立加固项，预先存量，非本批射程）**：`batch-delete`（damaged_asset_view.py:211-225）将 ids（资产 recordcode 列表）原样透传 Service → `cancel_asset_recordcode` → `get_asset_recordcode_for_update`，零 user 零作用域（`BatchDeleteValidationMixin.validate_ids` 仅验长度/去重），权限门控为角色级 `IsDeptManagerOrAbove`（非部门范围）→ A 部门 dept_manager 可输入 B 部门资产 recordcode 取消其待报废记录并连带恢复其资产状态（跨部门写）。最小加固形态：ids 先经 `get_queryset_for_user` 预筛，或 Service 方法加 `user=None` 可选参数 + `apply_user_scope` 风格过滤（B12 模式）——改动面 2 方法 + 调用点透传，暂不排期。
- **加固落地（2026-09-22，A-29 例外项闭环）**：`batch-delete`（及同族写路径）经用户拍板执行独立安全修复——Service 写路径 approve/reject/cancel/update + `batch_delete_asset_recordcodes` 全加 `user=None` 透传，Selector `get_asset_recordcode_for_update`/`get_for_update` 加 user 参数并经 `get_asset_linked_queryset_for_user` 过滤（B12 模式：越界≡不存在→`DAMAGED_ASSET_NOT_FOUND` fail_item）；View 六动作（approve/reject/destroy/update/partial_update/batch_delete）传 `user=request.user`。**`of=("self",)` 启用技术修正**：作用域 Q 对可空 `asset_recordcode` 生成 LEFT OUTER JOIN，叠加裸 `select_for_update()` 复现实测的 A-22 NotSupportedError——两锁查询统一 `select_for_update(of=("self",))` 仅锁主表，该写法由 v2.9.35 观察项①的「可选优化增强」升级为**本修复的启用前置（mandatory）**。批量契约守护：走 Service 锁内取消（Option B 定案），不经 ids 预筛（Option A 否决理由：`batch_delete_execute` total=len(ids) 且 success+fail==total，预筛剔除破坏响应语义）。`DamagedAssetBatchDeleteSerializer.ids` help_text 修正为「关联资产 recordcode 列表」（原「待报废记录编码列表」误导；ides 实为 FK 资产 recordcode，spectacular 不输出 ListField child help_text，schema 逐字节无 diff）。新增 `TestWritePathDeptScope` 5 用例（红→绿：跨部门批删拒绝不触碰记录/状态、同部门批删回归、部门经理 approve 作用域 JOIN+锁路径不抛阻塞、跨部门 update 拒绝、同部门 update 通过）。
- **决策反转留痕**：A-21 于 2026-09-20 定案「HTML 历史快照 `batch-create-optimization-plan.html` 未改写」（Bug修复活账本 :948 同述）；经用户 2026-09-22 拍板**反转**——HTML :832（错误码示例表 `<td>`）/ :899（示例 JSON `error_code`）同步为 `ASSET_HAS_OUTASSET`，两处上方各加注记，方案文档随现行契约更新。
- **边界声明（gate 扩围口径）**：下沉后 Service 层残余非 filter ORM 直查 4 处（均非裸过滤查询，import 保留）：`out_asset_service.py:67`（create）/ `:177`（锁内 `get(pk)` 复用引用）、`damaged_asset_service.py:62`（create）、`repair_asset_service.py:260`（create）；gate `rg "OutAsset\.objects\.filter|DamagedAsset\.objects\.filter" apps/assetmanagement/services` = 0 残留。
- **验证命令**：`rg "OutAsset\.objects\.filter|DamagedAsset\.objects\.filter" apps/assetmanagement/services`（0）; `rg "HAS_OUTASSET_RECORDS" apps core --glob "*.py"`（0，全仓仅历史快照/A-21 已关闭记录）; 定向 5 套件（asset/recycle/out/damaged/recycle_damaged_waste_selector）110 passed；全量 `pytest apps -q` 1043 passed（整体 81.11%）；`--cov=apps.assetmanagement.services` 96.44%（单文件最低 recycle 91% ≥90%）；`ruff` scoped 0 错；`mypy` scoped 0 新增（7 存量噪声不变）；`python scripts/check_duplicate_invariants.py` PASS。

---

## B — 待修复（To Fix）

### B-1. 审计适配器克隆（DepartmentAuditAdapter vs EmployeeAuditAdapter）
- **判定**：克隆（结构同构：try/except + GenericAuditService 委托 + record_code/app_label/description 模式），差异仅为模型字段与 app_label；Employee 版多一个 `log_state_change`。
- **位置**：`apps/usermanagement/audit_adapter.py` vs `apps/usermanagement/employee_audit_adapter.py`（log_create/log_update/log_delete 三方法同构）。
- **修复建议**：抽公共基类 `BaseAuditAdapter`（参数化 app_label/实体名/快照字段），约省 150 行。
- **状态**：✅ 已关闭（2026-08-24，commit a7fb4ca）。提取 `safe_audit_log()` 辅助函数，3 个适配器（department/employee/role）全部收敛；修复 exc_info 漂移（6 处）。净减 29 行。
- **验证命令**：`ruff check apps/usermanagement/audit_adapter.py apps/usermanagement/employee_audit_adapter.py apps/usermanagement/role_audit_adapter.py apps/usermanagement/audit_helper.py`

### B-2. types/outasset.ts::outassetStatusMapping 死副本
- **位置**：`src/types/outasset.ts:47`，与 `src/utils/Format.ts::outassetStatusMapping` 内容完全一致。
- **证据**：全仓仅 `types/outasset.ts` 定义导出，无任何消费方 import 它（`@/types/outasset` 的 outassetStatusMapping）。
- **修复建议**：删除该导出（属公共导出面变更，需批准后执行）；保留方为 `Format.ts`（被 useOutAssetDetailCards / OutAssetBasicDetails 消费）。
- **优先级**：低。**状态**：✅ 已修复（2026-09-09 复核核实，前端 commit `bbccfbe` M-7 状态映射去重统一）——`types/outasset.ts` 的死副本导出已删除，保留方为 `Format.ts`；文件头注释仍提及该方法名（无害，指引至 Format.ts）。

### B-3. asset_lifecycle_view.py 三重复制 ViewSet（Broken/Lost/Found）
- **判定**：克隆（batch_delete/batch_create/by_asset/get_queryset/get_serializer_class/get_permissions 90% 同构）。
- **位置**：`apps/assetmanagement/views/asset_lifecycle_view.py`（338 行，三 ViewSet 各 ~105 行）。
- **修复建议**：提取 `AssetLifecycleViewSetBase` 基类，子类声明化（batch_create 按方案 A 留在子类）。
- **状态**：✅ 已关闭（2026-08-24，commit 0259664）。asset_lifecycle_view.py 338→127 行 + 基类 _lifecycle_base.py 145 行；batch_create 按方案 A 留在 Broken/Lost 子类。
- **验证命令**：`python -m pytest apps/assetmanagement/tests/test_lifecycle_view_api.py apps/assetmanagement/tests/test_batch_contract_snapshot.py -q`（48+ 用例锁定契约）

### B-4. MAX_BATCH_SIZE=100 重复定义（31 处/17 文件）
- **判定**：常量重复（另有 core/batch_mixins.py DEFAULT_MAX_BATCH_SIZE=100 存量定义）。
- **位置**：apps/assetmanagement/serializers/*、apps/usermanagement/services/employee_service.py、department_service.py 等。
- **修复建议**：收敛至 core/constants.py::MAX_BATCH_SIZE；序列化器 validate 方法体去重列为后续独立提交。
- **状态**：✅ 已关闭（2026-08-24，commit 550a9af）。常量收敛至 core/constants.py；batch_mixins fallback 改为常量引用；字面量残留 0 处。序列化器 validate 方法体去重列为后续独立提交。
- **验证命令**：`rg -n "MAX_BATCH_SIZE = 100" --glob "*.py" asset_management_backend`（预期无命中）

### B-5. batch-result dict 手写组装（Service 层 10+ / View 层 10+）
- **判定**：克隆（循环 + try/except AppValidationError 取 error_code + 兜底 INTERNAL_ERROR + 结果 dict 组装）。
- **位置**：employee_service.py:289-342 等；View 层 batch_create/batch_delete action 二次搬运。
- **修复建议**：复用既有 core/batch_mixins.py::batch_execute/batch_delete_execute；View 层新增 BatchResponseHelper（message 必须由调用方显式传入，禁止默认兜底文案）。
- **状态**：✅ 已关闭（2026-08-24，commits e85b6cf/90adf24/d7d2351，第二阶段收编剩余 10 处）。
  - damaged/waste：View 手写循环下沉至 Service.batch_delete_*（错误码透传修正漂移，
    前端证据 b5-frontend-error-code-search.md）
  - asset_type/contract/storage/out_asset/recycle batch_delete → delete_response
  - asset_type batch_create 逐条推导式 → create_response（many=True 等价性实证锁定）
  - unregistered：CREATE_FAILED 单码制消灭（三层异常分层）、MAX_BATCH_SIZE 常量化、
    组装迁移 delete_response；**400 超限契约按原样保留**
  - 例外保留：repair_asset 静态 message"批量删除完成"；unregistered 400 超限契约
- **验证命令**：`python -m pytest apps -q`（864 全绿）+ 基线快照 test_b5_baseline_snapshot.py

### B-6. employee_service / department_service 批量方法镜像结构
- **判定**：克隆（batch_create_*/batch_delete_* 循环骨架逐行同构，仅模型与单条方法名不同）。
- **位置**：apps/usermanagement/services/employee_service.py vs department_service.py。
- **修复建议**：随 B-5 迁移至 batch_execute 自动解决，不额外抽泛型实体函数（避免 mypy 类型推断退化）。
- **状态**：✅ 已关闭（随 B-5，commit d0a78dc）。循环框架已收敛至 batch_execute，两 Service 仅剩声明式闭包差异。
- **验证命令**：同 B-5。

### B-7. throttles.py 登录用户名提取逻辑三重复制
- **判定**：克隆（LoginRateThrottle.get_cache_key 与 LoginLockoutThrottle._get_username/get_cache_key 完全相同，含相同 silent except）。
- **位置**：core/throttles.py。
- **修复建议**：提取模块级 `_extract_login_username(request, owner)`；**日志前缀按类名保留原文**（LoginRateThrottle/LoginLockoutThrottle 各自文案不变）。
- **状态**：✅ 已关闭（2026-08-24，commit 76b0180）。提取模块级 _extract_login_username(request, owner)，日志前缀按类名保留原文。
- **验证命令**：`rg -n "无法读取请求数据" core/throttles.py`

### B-8. 【新发现】员工批量创建失败条目携带部门时响应 500
- **判定**：存量缺陷（非重复代码，但由 B-5 快照测试暴露）。
- **证据**：`EmployeeService.batch_create_employee` 将 validated_data 原样放入 fail_items[].input_data；当条目含 employee_department_code 时 validated_data 中 employee_department 为 Department 模型对象，DRF JSON 渲染抛 `TypeError: Object of type Department is not JSON serializable` → 500。
- **位置**：apps/usermanagement/services/employee_service.py:289-342（input_data 组装处）。
- **修复建议**：input_data 改存原始请求 dict（serializer.initial_data）或对模型对象做序列化降级；需人工确认后单独 PR。
- **优先级**：高（用户可触发的 500）。**状态**：✅ 已关闭（2026-08-24，commits 8403b10/bb5c785）。
  采用 BatchResponseHelper.create_response 新增 request_items 参数方案：失败条目 input_data 以
  serializer.initial_data 按 index 回写（键名/值与用户提交逐字一致，天然可序列化）。
  受影响 4 端点（employees/assets/out-assets/recycle-assets batch-create）全部接入；
  排查确认 departments/lifecycle/contract/asset_type/storage 无 SlugRelatedField 不受影响。
  遗留：unregisteredasset 的 CREATE_FAILED 变体另行登记治理。
- **验证命令**：`python -m pytest apps/assetmanagement/tests/test_batch_contract_snapshot.py -q`
  （含 B-8 回归屏障用例：移除 request_items 传参即精确复现修复前 500）

---

### B-10. 【新发现】unregistered batch-create 早退分支误用 error_response 参数致 500
- **判定**：存量缺陷（2026-08-24 B-5 基线快照测试暴露）。
- **证据**：`error_response()` 签名为 (message, errors, status_code)，无 data 参数；
  空 items 与超限两分支调用 `error_response(data={"message": ...})` 抛 TypeError，
  被全局异常兜底转为 500（代码意图为 400）。
- **位置**：apps/unregisteredasset/views.py L243、L245-247。
- **修复**：commit d784848 改为正确 message= 传参，恢复 400 契约；基线快照锁定。
- **状态**：✅ 已关闭。

---

### B-11. 【新发现 2026-09-01】后端同名模块死文件簇（模块被同名包遮蔽）
- **判定**：死代码 + 维护误导（非双活实现，实际运行走包目录）。
- **证据**：`apps/assetmanagement/` 下 5 个被 git 跟踪的根级 .py 与同名包共存，Python 导入系统
  中包优先于同名模块（实测 `django.setup()` 后 `serializers.__file__` 等全部解析到包 `__init__.py`），
  根级文件永不可达：`serializers.py`（1846 行）、`views.py`（1507 行）、`operation_log_service.py`
  （612 行，全仓零引用）、`services.py`、`selectors.py`。且死文件仍在被持续维护
  （serializers.py 最后修改 2026-08-23 `32a6eb9`，views.py / operation_log_service.py 2026-08-24），
  存在"改了不生效"的误导风险；均超 500 行且无 TECHNICAL_DEBT 标记（DR-5 风险面）。
- **验证命令**：`DJANGO_SETTINGS_MODULE=config.settings.test python -c "import django; django.setup(); import apps.assetmanagement.serializers as s; print(s.__file__)"`
- **修复建议**：确认无 importlib 按路径加载后，直接删除 5 个死文件（零行为变更，1063 测试回归验证）。
- **优先级**：高（维护成本与误导风险）。**状态**：✅ 已修复（2026-09-09 核实，后端 commit `c64675c` "删除5个被包遮蔽的死文件（~4800行不可达代码）"）——5 个根级死 .py（serializers/views/operation_log_service/services/selectors）已全部删除，根级仅剩正常模块（admin/apps/audit/urls 等）。

---

### B-12. 【新发现 2026-09-01】前端员工状态映射双源（键集与文案不一致）
- **判定**：重复定义（DR-1 风险面，改标签易漏改一处）。
- **证据**：`src/utils/statusMapping.ts` `EMPLOYEE_STATUS_MAP`（active/left/retirement → 在职/离职/退休）
  与 `src/utils/Format.ts:247-252` `userStatusMapping`（active/left/retirement/dismissed → 在职员工/
  离职员工/退休员工/辞退员工）键集与文案均不一致，两份独立维护。
- **修复建议**：Format 侧改为从 `EMPLOYEE_STATUS_MAP` 派生并补 dismissed 键，收敛单一来源。
- **优先级**：低。**状态**：✅ 已修复（2026-09-09 核实，前端 commit `2ced9dd`）——Format.ts `userStatusMapping` 已改为从本地 `USER_STATUS_DISPLAY_MAPPING` 派生（Object.fromEntries + '员工' 后缀，L272-274，注释明示单一事实源），双源文案维护问题消除。实现与原建议有两点偏差，均合理：① dismissed 键未补——`EmployeeStatus` 枚举本身仅 active/left/retirement 三态，原报告所称 dismissed 分支已不存在于类型层；② 派生源为 Format.ts 本地表而非 statusMapping.ts 的 `EMPLOYEE_STATUS_MAP`——后者是带 tag type 的 UI 标签映射，与纯文案表用途不同，语义上不构成双源。

---

### B-13. 【已修复 2026-09-09】UserBatchImport 模板导出第 9 处的残留内联实现
- **判定**：克隆（`src/components/componentsdetails/detils/UserBatchImport.vue::downloadTemplate` 与 A-17 收敛的同构现有第 9 处，依旧内联 `new ExcelJS.Workbook()`，未走 `downloadExcelTemplate`）。
- **证据（修复前）**：`UserBatchImport.vue:295-325` 手写创建工作簿/表头/示例行/下载；导出的 `userTemplateData` 单元格含**非字符串值**（`排序: 100` 数字），强行走 `downloadExcelTemplate`（签名 `Record<string, string>[]`）会产生类型不匹配，需先规范数据映射。
- **修复方式（2026-09-09 实施）**：`downloadTemplate` 迁移至 `downloadExcelTemplate`（改名 `handleExportTemplate`，与其余 8 组件一致），删除内联实现与 `import ExcelJS`；`templateExport.ts` 参数类型从 `Record<string, string>[]` 拓宽为 `Record<string, TemplateCellValue>[]`（`TemplateCellValue = string | number`），非字符串单元格（`排序: 100`）原样直通，缺失/空值统一补空字符串。配套新增 `src/utils/batchImport/__tests__/templateExport.spec.ts` 4 条用例（CT-4 回归护栏：数值保留 / 空值补空 / 触发下载+成功提示 / 写入失败提示）。
- **优先级**：低（与 A-17 同构但无功能缺陷）。**状态**：✅ 已关闭（2026-09-09，任务清单 ① 合并 PR）。
- **验证命令**：`rg -n "new ExcelJS.Workbook" src/components/componentsdetails/detils/UserBatchImport.vue`（预期 0 命中，实测 0）；`rg -n "import ExcelJS" src/components/componentsdetails/detils`（预期 0，实测 0）；`npx vitest run src/utils/batchImport/__tests__/templateExport.spec.ts`（4 passed）。

---

### B-14. 【新发现 2026-09-10】usermanagement 域同名模块被同名包遮蔽（R6-03 同型死文件，已闭环）
- **判定**：死代码 + 维护误导（B-11 同型，应用级而非根级）。
- **证据**：`apps/usermanagement/views.py`（894 行）与同名包 `views/` 共存，Python 导入系统包优先于同名模块；`urls.py:13` `from apps.usermanagement.views import (...)` 与 `views/employee_view.py:27` 均解析到包（`views/__init__.py:1-13` re-export 5 个 ViewSet）。全仓代码引用仅此两处，其余 `rg "usermanagement\.views"` 命中全为历史文档/注释，无 importlib/字符串路径加载。文件含过期契约残留（`'code': 200` 旧响应格式），持续"改不生效"误导。
- **修复（2026-09-10）**：确认无路径级引用后整文件删除（对齐 B-11 资产域 `c64675c` 处理）；删除后 `python manage.py check` no issues、全量 pytest 1074 passed 回归。
- **验证命令**：`rg -n "apps\.usermanagement\.views" asset_management_backend --glob "*.py"`（预期仅 `urls.py:13` 与 `views/` 包内引用，views.py 模块零命中）；`python manage.py check`（no issues）。
- **优先级**：高（维护误导）。

---

### B-15. 【已关闭 2026-09-22】审计值 JSON 安全归一化双实现（asset_service._normalize vs operation_log_service._to_json_safe）
- **判定**：重复实现（DR-1 风险面）。同一语义「审计快照值归一位 JSON 安全类型」两处各自内联：`asset_service._normalize` 为方法内嵌局部函数（不可跨模块 import，处理 FK→recordcode + Decimal/date/datetime/time/UUID→str），本次修复在日志唯一写入点新增 `operation_log_service._to_json_safe`（模块级，另支持 dict/list 递归）。两实现幂等且结果一致，存在漂移风险（一方改语义另一方不同步）。
- **来源**：BE-05（审计留痕）修复过程中为打通 date 序列化雷（修复前 before/after 含 date 时 JSONField 序列化失败被 `_safe_log` 静默吞掉）在写入收口点新增归一化，未在 out/damaged service 复制第三处；此收敛候选需人工排期。
- **位置**：原 `apps/assetmanagement/services/asset_service.py:192`（`update_asset` 内嵌局部函数）vs `apps/assetmanagement/services/operation_log_service.py:31`。旧条目位置记 `:173（update_asset_info 内嵌）`为早期方法布局，已随本次修正。
- **修复（2026-09-22 实施，用户批准）**：删除 `asset_service.py` 内嵌 `_normalize` 局部函数完整体（原 :192-200 含 `return value`）；before_data 改 `{key: getattr(asset, key) for key in update_data}`、after_data 直传 `update_data` 原值；归一化由 `log_operation` :134-135 已落库的 `_to_json_safe` 幂等收口（行为零变化）。同步删除三个孤儿 import（`from datetime import date, datetime, time` / `from decimal import Decimal` / `from uuid import UUID`，均为 `_normalize` 唯一消费方），保留模块级 `import uuid`（:74 消费）。docstring 归一化表述改指写入收口。未采纳替代案：提升至 `utils/` 公共工具（需动三端且与"写入收口"收敛方针相悖）；跨模块 import 私有 `_to_json_safe`（违反模块封装）。
- **测试（CT-4 新增锚点）**：`test_update_asset_fk_instance` 扩展——update_data 含 FK 模型实例 + `Decimal("2000.00")`，新增快照断言：`before_data` FK 键 == `str(旧类型.recordcode)`、金额 == `"1000.00"`；`after_data` FK 键 == `str(new_type.recordcode)`、金额 == `"2000.00"`。该方法 docstring 本已声明「审计快照归一化」而断言缺失，本次补锚即兑现既有声明。
- **优先级**：低（幂等等效、非缺陷，收敛候选）。**状态**：✅ 已关闭（2026-09-22）。
- **验证命令**：`pytest apps/assetmanagement/tests/test_asset_service.py apps/assetmanagement/tests/test_operation_log_service.py apps/assetmanagement/tests/test_asset_view_api.py -q`（97 passed）；`rg -n "def _normalize|_normalize\(" apps/assetmanagement/services/asset_service.py`（实测无命中）；ruff 两改动文件 0；mypy `asset_service.py` 零新增（其余报错为 dateutil stubs/var-annotated 存量，测试目录经 `.*test.*` exclude 不纳入 gate）。

### B-20. 【已修复 2026-09-18】employee 批量删除守卫直查 Asset（A-19 未收敛的第 4 处裸查询）
- **判定**：DR-3 风险面（资产查询绕过 Selector 层）——`apps/usermanagement/services/employee_service.py`（修复前 L342-357）在批量删除员工守卫中直接 `Asset.objects.filter(asset_applicant_recordcode__in=..., is_deleted=False).values_list(...)`（申请人/保管人两个 recordcode 集合），与 A-19 收敛的三处删除守卫同属「删除前引用存在性检查」家族。
- **与 A-19 差异**：跨 App 引用（usermanagement 查询 assetmanagement 的 Asset）、返回值是 recordcode 集合而非 bool exists。
- **修复（2026-09-18 实施，用户批准）**：新增 `AssetSelector.referenced_employee_recordcodes(employee_recordcodes: Iterable[str]) -> set[str]` 单一实现（豁免清单 #10，保持现状全局语义=无部门范围，仅登记豁免不 scoped）。FK `to_field="recordcode"` 语义下沉至 Selector 并注释留痕；django-stubs 将 FK `values_list(flat=True)` 推算为 pk 类型 int，运行时为 recordcode 字符串，统一 `str()` 归一。employee_service 预检查块改为委托（局部 import AssetSelector，保留 recordcode 提取行，`# type: ignore[var-annotated]` 随类型明确删除）；**闭包注入机制与 _delete_one 不变**，仅预检查生产来源由内联 ORM 收敛为 Selector 委托（先期条目"改动闭包注入逻辑"措辞精化为此）。
- **测试（CT-1/CT-4）**：`test_asset_selector.py` 新增 `TestReferencedEmployeeRecordcodes` 6 条单测（空集/申请人命中/保管人命中/双角色去重/软删资产排除/未引用排除）；`test_service_coverage.py` 新增保管人端到端 `HAS_RELATED_ASSETS` 用例（申请人路径既有用例自动经新方法回归）。
- **优先级**：低（无缺陷、无泄漏，仅入口未统一）。**状态**：✅ 已关闭（修复完成）。
- **验证命令**：`pytest apps/assetmanagement/tests/test_asset_selector.py apps/usermanagement/tests/test_service_coverage.py -q`（66 passed）；全量 1162 passed、整体覆盖率 81.62%；usermanagement Service 层 91.60%；mypy 双 app scoped-strict 改动文件零新增。

### B-21. 【新发现 2026-09-20】写路径 IntegrityError→业务码兜底双实现（hard_disk_sn_service vs damaged_asset_service）
- **判定**：重复模式（DR-1 风险面）。同一语义「DB 唯一约束冲突 = 并发窗口穿透预检 → 映射为业务错误码而非通用 400」两处独立内联：`apps/assetmanagement/services/hard_disk_sn_service.py:46-55`（`create`，`except IntegrityError` + 列 token 匹配 + `AppValidationError(DUPLICATE_SN_CODE) from exc`）与 `apps/assetmanagement/services/damaged_asset_service.py`（`create_damaged_asset` PR-1 修复时按该先例新增同构块，列 token=`asset_recordcode`、错误码 `DUPLICATE_DAMAGED_RECORD`）。
- **来源**：审查报告 #15（B5 TOCTOU）修复过程中发现；pre-existing 仅 hard_disk_sn 一处，本次修复使其成为全仓第二实例（§1.8 新发现义务，登记留痕）。
- **差异**：目标列 token、错误码、detail 文案各异；外层结构（内层 `with transaction.atomic()` + 外层 `except IntegrityError` 判定 + `raise` 兜底）逐字同构。
- **修复建议**：提取公共兜底 helper（如 `core/exceptions.py` 或 `utils/` 的 `re_raise_or_map_integrity_error(exc, column_token, error_code, detail) -> None`），两处统一委托；或复用 DR-4 的异常归一化/映射收口。
- **优先级**：低（两处逻辑幂等、无缺陷，收敛候选）。**状态**：待修复。
- **验证命令**（收敛后）：`pytest apps/assetmanagement/tests/test_damaged_asset_service.py apps/assetmanagement/tests/test_hard_disk_sn_service_integrity.py apps/assetmanagement/tests/test_hard_disk_sn_service.py -q`；`rg -n "except IntegrityError" apps/assetmanagement/services`（预期仅工具函数内 1 处）。

---

## C — 降级/待决策（Downgraded / Decision Gate）

### C-1. 前端资产状态回退行为三态分歧（已解决）
- **状态**：✅ 已解决（2026-08-13，用户决策：原始值回退），详见 [A-9](#a-9-前端资产状态回退行为统一c-1-决策落地本次修复)。

### C-2. outasset 映射语义碰撞（命名冲突，不可合并）
- **描述**：同名 `outassetStatusMapping` 实为两套不同域：
  - `statusMapping.ts::OUTASSET_STATUS_MAP`（active/returned/overdue = 出库单记录状态）
  - `Format.ts`（recycled_pending/in_use/damaged/scrapped = 资产当前状态；原 `types/outasset.ts:47` 死副本已随 B-2 删除）
- **判定**：不可合并，仅命名易混淆。建议后续重命名（如 `OUTASSET_RECORD_STATUS_MAP` vs `OUTASSET_ASSET_STATUS_MAP`）。
- **阻塞原因**：重命名触及公共导出面，需批准；且需同步 types/outasset.ts 枚举语义。

### C-3. 错误码字符串与 BusinessCode 命名不一致（v1.7 修正）
- **描述**：服务层 `error_code` 字符串（如 `INVALID_STATE_TRANSITION`/`ASSET_NOT_FOUND`）与 `BusinessCode` 常量（如 `INVALID_TRANSITION`/`ASSET_NOT_FOUND=1003`）命名不同但语义重叠。两套体系独立运作：`BusinessCode` 用于响应体 `code` 字段（现仅保留 `SUCCESS=0`），`error_code` 字符串仅用于批量操作 `fail_items` 日志（前端不消费）。
- **判定**：降级处理，不纳入本次修复。`error_code` 字符串无注册表需求，仅作日志标识。
- **验证命令**：`rg -n "business_code" asset_management_backend/utils/response_utils.py`（预期无命中，已删除该参数）。

### C-4. 前端批量导入页「上传提示 + 导入指南」区块重复（P3 登记，部分收敛）
- **判定**：克隆（`.upload-tip` 提示块 + `.import-guide-card` 区块在 8 个批量导入页逐字同构，含相同 CSS 与结构）。
- **位置**：`AssetBatchImport.scss` / `StorageBatchImport.vue` / `ContractBatchImport.scss` / `OutAssetBatchImport.scss` / `UnregisteredAssetBatchImport.vue` / `DamagedAssetBatchImport.vue` / `DepartmentBatchImport.vue` / `AssetTypeBatchImport.vue`。
- **证据**：8 处 `.upload-tip { margin-top: 8px; color: var(--text-secondary); ... }` 结构一致；`BatchImportGuideCard.vue` 已封装的指南卡片小于实际复用范围。
- **用户决策（2026-09-08）**：`.upload-tip` 提示块整体**不重构**（8 处保留），未来若采用 `ListPageShell` 类底座随 P3 统一处理。
- **局部收敛（2026-09-09，本次修复）**：2 处残留手写 `.import-guide-card`（`DamagedAssetBatchImport.vue` / `DepartmentBatchImport.vue`）改为复用已封装的 `BatchImportGuideCard` 组件（DR-2），净删 ~90 行重复模板；`.upload-tip` 提示块按 09-08 决策保留不动。
- **验证命令**：`rg -n "import-guide-card" src/components/componentsdetails/detils --glob "*.vue"`（不再命中 Damaged/Department）；`rg -c "upload-tip" vue-assetmanagement/src --glob "*.vue" --glob "*.scss"`（预期 ≥8，保持）。

### C-5. 前端详情页「页标题 + child-page-header」双结构（P3 登记，不重构）
- **判定**：近重复（主容器 `@mixin child-router-container` 提供的 `child-page-header h2` 与详情组件自身的 `.page-title` 均为页标题；P0/P1 已将两者统一为 20px，结构未合并）。
- **位置**：`assets/styles/common-forms.scss`（`child-page-header`、`detail-container .page-title`）与 `BasicAssetDetails.scss` 等详情组件。
- **用户决策（2026-09-08）**：仅登记，**不重构**（结构合并涉及详情页模板重构，风险大于收益）。
- **验证命令**：`rg -n "child-page-header|page-title" vue-assetmanagement/src/components --glob "*.vue" --glob "*.scss"`

### C-6. 前端列表页骨架逐页组装（P3 登记，不重构）
- **判定**：结构重复（各列表页自行组装：搜索栏 + 表格容器 + 分页 + 页面头声明；P0 已将页头收敛至 MainView 统一渲染，剩余骨架未见公共底座）。
- **位置**：`views/` 与 `components/componentsdetails/` 下各列表页。
- **用户决策（2026-09-08）**：仅登记，**不重构**。未来 `ListPageShell` 底座可作为独立架构项推进。
- **验证命令**：`rg -l "SmartListContainer|CommonList" vue-assetmanagement/src/components/componentsdetails vue-assetmanagement/src/views`（预期多文件命中，印证无公共底座）。

### C-7. 前端底部悬浮操作栏 form-actions 模式重复（P3 登记，不重构）
- **判定**：样式克隆（`@mixin table-container form-actions` 底部浮层样式在表单/详情编辑场景重复出现）。
- **位置**：`assets/styles/common-forms.scss`（form-actions 内联块）及各表单页组件。
- **用户决策（2026-09-08）**：仅登记，**不重构**。
- **验证命令**：`rg -ln "form-actions" vue-assetmanagement/src --glob "*.vue" --glob "*.scss"`

### C-8. 资产/合同域「detail 路由 = recordcode，batch-delete = asset_code」双约定契约特性（ID-2 资产域实证，不可统一）
- **判定**：跨端契约特性（非重复代码，登记以防后续"统一取键"引入回归）。后端对同一资源的两类端点使用**不同的定位键**，前端两套键不可互换。
- **资产域实证（2026-09-09）**：
  1. detail 路由（GET/PUT/DELETE `/assets/assets/{id}/`）：`AssetViewSet` `lookup_field="recordcode"`（`apps/assetmanagement/views/asset_view.py:57`）+ `RecordcodeLookupMixin.get_object`（`mixins/_mixins.py:24-42`，数字 pk → recordcode → 404）。前端传 `asset_code`（业务编码 "AST-A001"）必然 404——即 ID-2 根因（资产列表页编辑/单删曾传 asset_code）。
  2. batch-delete 端点（`POST /assets/assets/batch-delete/`）：显式按业务编码处理——`filter(asset_code__in=ids)` 并按 asset_code 做 RBAC 范围校验（`asset_view.py:357-367`）。前端批删**必须**传 asset_code，若"统一"改 recordcode 会改坏。
- **合同域同构**：detail 路由 = recordcode（ContractViewSet 同 lookup 机制）；`contract_code` 为纯展示字段，不参与定位（A-5 已落地 4 处修正：`ContractDetails.vue` L216/237/261/279）。
- **合法例外（非 bug，勿误改）**：部门 `lookup_field="department_code"`（`apps/usermanagement/views/department_view.py:64`）、未登记资产 `lookup_field="unregistered_code"`（`apps/unregisteredasset/views.py:85`）——这两个域的 detail 路由以业务编码为键，与资产/合同的 recordcode 约定不同。
- **前端防线（已落地）**：`api/asset.ts`（updateAsset/deleteAsset/getAssetByCode 入参语义 = recordcode，batchDeleteAssets 入参语义 = asset_code，均带契约注释）、`stores/assetStore.ts`（api 绑定行内注释）、`AssetContentDetails.vue`（编辑/单删取 row.recordcode，批删取 row.asset_code 并注释双约定）、`types/asset.ts::AssetUpdateForm`（recordcode 必填）。防回归断言：`assetStore.spec.ts`（批删原样透传 asset_code）、`asset.spec.ts`（recordcode URL 拼装 4 断言）。
- **验证命令**：`rg -n "row\.asset_code" vue-assetmanagement/src/components/componentsdetails/AssetContentDetails.vue`（预期仅剩批删 1 处）；`rg -n "recordcode" vue-assetmanagement/src/api/asset.ts`（updateAsset URL/校验均用 recordcode）。
- **登记日期**：2026-09-09 | 来源：前端展示 Bug 审核 · ID-2 独立核验（后端双约定实证）

### C-9. 前端主色令牌三源不同步（亮色 CSS 变量 / 编译期 SCSS 变量 / 暗色 EP 变量）
- **判定**：令牌契约特性（非可直接删除的重复，登记以防"统一取值"误改；同时是暗色模式修复的前置阻塞项）。
- **证据（2026-09-09 核验）**：同一"主色"概念三处独立声明——
  1. 亮色运行时：`src/styles/variables.css:4` `--color-primary: #2b5fd7`（CSS 变量，`html.dark` 中重定义 79 个变量）；
  2. 编译期固化：`src/assets/styles/common-forms.scss:11` `$primary-color: #2b5fd7`（SCSS 变量编译为字面量，暗色不切换）；`AsideMenu.vue:171-215` 等 8+ 处直接引用 `$border-color/$text-primary/$primary-color`；
  3. 暗色 EP 侧：`src/styles/dark.css:10` `--el-color-primary: #4a90e2`（Element Plus 变量，与亮色 #2b5fd7 色相不同）。
- **影响**：暗色模式下 EP 组件主色（#4a90e2）与自定义组件固化亮色（#2b5fd7）并排呈现两种蓝；三源同值但独立维护，任一改色即漂移。ECharts（useDashboardCharts.ts/useDashboardPage.ts）硬编码 #333/#e5e7eb/#fff，不读任何令牌，暗色完全失效。
- **决策**：暗色修复**须先收敛三源**（SCSS 变量改引用 CSS 变量；dark.css 主色与亮色对齐或声明暗色专用色阶——后者需产品决策）；组件级替换（AsideMenu/LogIn/Dashboard）在三源收敛后进行，否则白做。
- **优先级**：中（暗色模式前置阻塞项）。**状态**：✅ 已修复（2026-09-09，Phase 1 实施）——组件裸引用清零（AsideMenu/LoginDialog/DashboardPage/AssetDetails/ContractOfDetails/UserBatchImport.scss 全部换 var()，4 处 rgba 预派生 --color-primary-8/-12）；ECharts 经 useChartTheme.ts 主题化（theme computed 内消费 isDark.value，4 个 option computed 全部接入），硬编码色值清零；SCSS 变量定义保留（52 处 var(--x,$var) fallback 依赖）。遗留决策项：暗色主色色相统一（#4a90e2 vs #2b5fd7）待产品拍板。
- **验证命令**：`rg -n "2b5fd7" vue-assetmanagement/src`；`rg -n '\$primary-color' vue-assetmanagement/src/assets/styles/common-forms.scss`；`rg -nE "#333|#e5e7eb|getComputedStyle" vue-assetmanagement/src/composables/useDashboardCharts.ts`
- **登记日期**：2026-09-09 | 来源：前端设计与质量审计核验

### C-10. 详情页 :deep(.el-table) 覆盖战争（全仓 63 处 !important）
- **判定**：样式交叉覆盖（各详情页用 `!important` 对抗公共组件内部样式；改 `CommonList` 样式会被静默拦截或引发连锁回归）。
- **证据（2026-09-09 复验修正拆分）**：全仓 `!important` 共 **63 处**——6 个详情页样式文件各 8 处（WasteAsset/UnregisteredAsset/OutAsset/OperationLogDetails.scss/HardDiskSN/DamagedAssetDetails.scss，48 处）+ `CommonList.vue` 8 + `common-forms.scss` 6 + `MainView.vue` 1。`:deep(.el-table)` 为 `CommonList.vue` 8 处 + 4 个详情页各 2 处重复（OutAsset/UnregisteredAsset/HardDiskSN/WasteAsset）。
- **修复建议**：提取共享 SCSS mixin 收敛 `:deep` 覆盖；以 CSS 变量/组件 props 传参替代 `!important`；与 Phase 3 DRY 重构合并为"表格样式覆盖"专项。
- **决策（2026-09-09）**：登记不立即重构（涉及 5+ 文件样式回归验证，需独立专项）。
- **状态**：✅ 已修复（2026-09-10，第一阶段 + 收尾两批，commits `eb73f17`/`03f5630`）——`--table-*` 令牌体系（9 变量，后退役 min-width 项余 8）收敛三层覆盖：mixin 6 处 + CommonList 8 处 + 6 详情页 48 处 `:deep !important` 全部清除，改外层变量覆盖（M2 继承机制）；随后修复收尾引入的表头截断（根 min-width 撑开 EP clientWidth 布局基准）。**残余 1 处**：MainView.vue:205（`padding: var(--el-main-padding) !important`，移动端 el-main 内边距覆盖，与表格战争无关，另立专项待办）。详见变更记录 v2.9.11/v2.9.12/v2.9.13。
- **验证命令**：`rg -n "!important" vue-assetmanagement/src --glob "*.vue" --glob "*.scss"`（预期仅 MainView.vue:205 1 处活规则；6 详情页命中为注释文字）；`rg -c ":deep\(\.el-table__" vue-assetmanagement/src/components/componentsdetails/`（预期 0）
- **登记日期**：2026-09-09 | 来源：前端设计与质量审计核验

### C-11. bottom-buttons sticky 悬浮遮盖列表内容（布局范式问题，非层级问题）
- **判定**：交互遮盖缺陷（`position: sticky + z-index: 50` 使按钮组悬浮盖住从其下方滑过的表格内容；调 z-index/令牌无法解决，已按 App 壳式布局根治）。
- **证据（2026-09-09）**：`bottom-buttons` mixin（common-forms.scss）原为 sticky 悬浮方案；`table-container` 有 `margin-bottom: 100px` sticky 预留 hack；`.common-list` `min-height: calc(100vh - 120px)` 整页滚动范式。
- **修复（已实施）**：改为 App 壳式布局（页面名/筛选不压缩 + 表格区 `flex:1; min-height:0; overflow:auto` 自滚 + 分页/按钮组流内页脚常驻）——共享层 8 处改动（list-container/table-container/bottom-buttons 三 mixin + responsive 两处 bottom 残留 + MainView/CommonList/SmartListContainer/SearchBar flex 链），16 个列表页经共享 mixin 零模板改动自动生效；`--z-sticky-bar` 令牌退役（D-6 阶梯同步更新）。
- **边界（不参与）**：Dashboard/通讯录/通知/独立视图页；子路由详情（child-router-container 200）与全屏遮罩（router-mask 1000）行为不变。
- **对抗审核结论**：UserDetails/DamagedAssetDetails/OperationLogDetails 三页初判"无 list-container 链路"系误报（实经外链 .scss `@include` 走共享 mixin，无断链）；组件内 6 处自写 `.bottom-buttons` 覆盖均无 sticky/z-index 残留；el-table fixed 列（5 文件）位于 overflow:auto 容器内表现正常；sass 编译/lint 通过。
- **优先级**：中（用户可见交互缺陷，已根治）。**状态**：✅ 已修复（2026-09-09，前端 commit `cb7b48f` + `4cddc43` + `bb71ff4` + `09d5bc5`）——App 壳式布局落地（8 处共享层改动，16 列表页零模板改动生效），AssetDetails 包装容器入链、DepartmentDetails 80px sticky 残留清除，两处后续断点经用户报告修复。
- **登记日期**：2026-09-09 | 来源：用户复审方案（第②点遮盖问题）+ 对抗审核

---

## D — 待核查（To Verify）

### D-1. ✅ 已关闭 2026-09-10 —— unregisteredasset batch_create 手写循环收敛至 batch_execute
- **判定**：与 `batch_execute` 不同构（7 项行为差异）。2026-09-09/09-10 逐条 diff 复核确认：
  1. 空列表 → 400（batch_execute 空列表为零计数；View 预检保留，文案不变）
  2. 超限 → 400 响应（batch_execute 抛 AppValidationError；View 预检保留原「单次批量创建」文案，防「创建/操作」漂移，test_b5 L38 锁定）
  3. DRF `ValidationError` → `VALIDATION_ERROR`（batch_execute 原无此层级，落入 `except Exception` 被吞为 INTERNAL_ERROR；已补 `except serializers.ValidationError` 分支——复用 L30 已导入的 serializers 零新依赖，完整复刻 AppValidationError 分支的 row_number/input_data 组装；core 变更，跨全部消费方）
  4. `row_number` 键——新 Service 方法内对每个 fail_item `pop("row_number", None)` 剔除，fail_items 契约与手写版逐字节一致（test_b5 逐键锁定断言零改动）；剔除仅在新方法内生效，其他 10 个 batch_execute 消费方零影响
  5. 无 logger.error——batch_execute Exception 分支自带日志异常排查，差异保留（更优）
  6. View 层调用——已下沉 `UnregisteredAssetService.batch_create_unregistered`（services.py）；View 收缩为 空/超限 400 + `resolve_operator` 循环外一次 + 委托 Service + `BatchResponseHelper.create_response(request_items=items)`；删除原三层 try 与 `drf_exceptions` import
  7. deepcopy / `_normalize_input_data`——batch_execute 提供 `_normalize_input_data` 防御层（B-8），`create_response(request_items)` 以原始提交回写 input_data，替代手写版无归一化直传
- **位置**：`apps/unregisteredasset/views.py` L246-269 | `apps/unregisteredasset/services.py` `batch_create_unregistered` | `core/batch_mixins.py` DRF ValidationError 分支
- **状态**：✅ 已关闭 | 关闭日期：2026-09-10
- **验证命令**：`pytest apps/unregisteredasset/tests/ -q`（76 passed，test_b5 断言零改动）+ `pytest apps/assetmanagement/tests/ apps/usermanagement/tests/ -q`（694 passed）+ `python scripts/check_duplicate_invariants.py`（PASS）+ `ruff`（0 error）+ `mypy`（改动文件干净）+ Service 覆盖率 90.48%（≥90）

### D-3. ✅ 已修复 2026-09-09 —— vite.config.ts 注释态插件配置副本
- **判定**：死代码/配置残留（visualizer 与 compression 插件各存在一份被整块注释的历史配置，与生产启用的配置同构，约 30 行）。
- **位置**：`vue-assetmanagement/vite.config.ts`（visualizer/compression 相关注释块）。
- **修复方式（2026-09-09 实施）**：删除整块注释态副本（含被注释的 visualizer/compression 调用）。**注意**：`vite.config.ts` 另有**在用**的 production 块（`...(mode === 'production' ? [ ANALYZE 触发的 visualizer + 两处 compression ] : [])`，约 L62-89）持续引用 `rollup-plugin-visualizer` / `vite-plugin-compression` 导入——**导入必须保留**，实施前勿按"死导入"误删（本次曾误删后立即恢复，已复核）。
- **优先级**：低。**状态**：✅ 已关闭（2026-09-09，任务清单 ① 合并 PR）。
- **登记日期**：2026-08-26 | 来源：H-1~H-3 整改期间审查发现
- **验证命令**：`rg -n "visualizer|compression" vite.config.ts`（预期仅导入 2 行 + 在用 production 块 3 处引用，无注释残留，实测相符）。

### D-4. API 详细文档双份维护（前端/后端子仓各一份）
- **判定**：文档克隆（`API详细文档0608.md` 同时存在于 `vue-assetmanagement/docs/` 与 `asset_management_backend/docs/`，内容高度一致，存在漂移风险）。
- **修复建议**：保留单份权威来源（建议随 OpenAPI 契约快照走后端侧），另一份删除或改为链接引用；触及跨端文档归属，需人工决策。
- **优先级**：低。
- **登记日期**：2026-08-26 | 来源：H-1~H-3 整改期间审查发现

### D-2. init_production_data 管理命令 3 个字段名 bug（CT-4 测试发现）
- **判定**：存量缺陷（非重复代码，但由新增测试暴露）。
- **证据**：
  1. `create_superuser(username=...)` → 应为 `auth_username=...`（自定义管理器参数名不匹配）
  2. `Employee.objects.get_or_create(department="系统管理")` → `department` 字段不存在（应删除或改为其他逻辑）
  3. `UserRole.objects.get_or_create(user=employee)` → `auth_user` FK 需要 `AuthUser` 实例，不能传 `Employee` 字符串
- **位置**：`apps/usermanagement/management/commands/init_production_data.py`
- **修复**：commit 2b36f8e，3 个 bug 全部修复。
- **状态**：✅ 已关闭 | 关闭日期：2026-08-24
- **验证命令**：`pytest apps/usermanagement/tests/test_init_production_data.py -v`（8 passed）

### D-5. 后端 getassetbyrecordcode 路径参数失效（路径与 query 双入口，纯路径调用必 400）
- **判定**：后端存量缺陷（用户决策 Q4=a：只登记、不动后端，等后端排期）。
- **证据**：`apps/assetmanagement/views/asset_view.py:182-187`——路由签名 `def getassetbyrecordcode(self, request, recordcode)` 接收了路径参数，但函数体只读 `request.query_params.get("recordcode")` 并校验 `if not recordcode`（此处是局部 query 变量遮蔽/重赋值逻辑）；当客户端以**纯路径**方式 `GET /assets/assets/getassetbyrecordcode/{recordcode}/` 调用时 query 为空 → 400「缺少记录编码」，路径参数被忽略。
- **影响面**：前端 `vue-assetmanagement/src` 全仓无 `getassetbyrecordcode` 调用方（2026-09-09 全仓 grep 0 命中），**无前端影响**；仅第三方/集成调用纯路径形态会踩坑。
- **修复建议**（供后端排期）：函数体改为优先取路径参数、query 参数兜底（或移除 query 兜底统一路径）；补一个纯路径调用的集成测试。
- **优先级**：中（无前端影响，但属 OpenAPI 契约与实现不符）。
- **状态**：✅ 已修复（2026-09-10，Q4=a 冻结经用户解除）——`asset_view.py:185` 改 `recordcode or request.query_params.get("recordcode")`（路径优先、query 兜底，query-only 调用行为不变、双传时路径优先）；新增纯路径集成测试 `test_get_asset_by_recordcode_path_only`。对抗审核实证：400"缺少 recordcode 参数"分支现为防御性代码——url_path 捕获组 `[^/.]+` 要求路径段非空，路由层无法产生空 recordcode 请求（曾尝试的空串 reverse 用例被 Django 拒绝，已改注释说明不设用例）；全仓无第二处 query-only 读取。回归：test_asset_view_api + test_asset_view_rbac 共 42 passed。
- **验证命令**：`pytest apps/assetmanagement/tests/test_asset_view_api.py::TestAssetViewSet::test_get_asset_by_recordcode_path_only -q`（应 passed）；`curl .../api/assets/assets/get_asset_by_recordcode/Asset-20260101-XXXXXXXX/`（修复后 200）
- **URL 改名联动（2026-09-20，B2 整改）**：端点 `getassetbyrecordcode` 随 B2 URL 命名一致性整改更名为 `get_asset_by_recordcode`（`asset_view.py:190` url_path 变更，路径参数与 query 兜底语义、纯路径可调用性均不变）；证据文本中的旧路径 `getassetbyrecordcode`/旧行号 `:182-187` 对应更新。验证命令同步更新为 `test_get_asset_by_recordcode_path_only`（用例名不变）。方法名 `get_asset_by_recordcode` 未动。

### D-6. 自定义浮层 z-index 无层级令牌（并列 1000 ×2 + 高层 2000，遮盖靠 DOM 顺序）
- **判定**：隐形错位风险（当前无实际遮盖缺陷，但层级值无令牌约束；EP 弹窗默认 ~2000+ 起始）。**证据经 2026-09-09 二次核验修正**（初版"仅 3 文件/各页手写无共享 mixin"两处不实，已更正）。
- **证据（2026-09-09 复验）**：全仓 z-index 共 **4 个文件 8 处**——
  1. `common-forms.scss`：bottom-buttons sticky=50（L439）、router-mask-container=**1000**（L496）、mask=100（L506）、child-router-container=200（L511）——后三者经 `@include` 被 **13 个详情页**复用（AssetContentDetails/ContractDetails/OutAssetDetails 等），非各页手写；
  2. `NotificationBell.vue:175` = **1000**（与 router-mask-container 并列，真隐患）；
  3. `MainView.vue:165` = **2000**（与 EP 弹窗起始值同量级，同样需纳入阶梯）；
  4. `AuditLogDetails.vue:328/342` 手写 100/1（唯一游离于 mixin 体系外的值）。
- **非 z-index 问题（勿误治）**：`.common-list`（CommonList.vue:307）无 position/z-index → 非 stacking context，永远被 sticky bottom-buttons(z=50) 悬浮压住——这是设计意图，令牌化不改变也不应改变；若按钮栏被遮挡，根因在祖先 stacking context（transform/filter）或 el-table fixed 列，令牌化无效。
- **触发条件**：并列 1000 两浮层（详情遮罩 vs 消息铃铛）同屏时遮盖靠 DOM 顺序；新增浮层可能意外互遮。
- **修复建议**：建立层级令牌阶梯（`--z-sticky-bar:50 / --z-mask:100 / --z-child-container:200 / --z-router-mask / --z-bell / --z-view-overlay`），收敛 4 文件 8 处 + AuditLogDetails 游离值；令牌取值按实际绘制顺序约定，避免并列。
- **状态**：✅ 已修复（2026-09-09）——variables.css 新增 `--z-*` 阶梯（content:1 / mask:100 / child-container:200 / notification:900 / router-mask:1000 / view-overlay:2000，主题无关仅 :root 定义），4 文件 8 处手写 z-index 全部收敛为 var() 引用（common-forms.scss 4 处 mixin、MainView 2000、NotificationBell 1000→**900 有意变更**：消除并列，详情遮罩明确盖过侧边栏铃铛、AuditLogDetails 游离值 100/1 归入 mask/content）。验证：sass 编译通过、裸 z-index 残留 0、var() 引用恰 8 处、对抗审核（暗色块零冲突/无重复定义/scoped 上下文完整/测试零依赖/铃铛挂载于 AsideMenu 不在遮罩内，900<1000 语义成立）全部通过。**后续演进（同日）**：bottom-buttons 随 App 壳式布局改造改为普通流内页脚（见 C-11），`--z-sticky-bar:50` 令牌退役删除——"令牌化不是遮盖问题的解药，改布局才是"的判定落地验证。
- **优先级**：低（暂无用户可见缺陷，收敛属预防性治理）。
- **登记日期**：2026-09-09 | 二次核验修正：2026-09-09 | 来源：前端设计与质量审计核验
- **验证命令**：`rg -n "z-index" vue-assetmanagement/src --glob "*.vue" --glob "*.scss"`（预期 4 文件 8 处）

---

## B-19. 【执行顺序清单】Bug 修复优先级排序（按复杂度分级）

> **登记日期**：2026-09-09 | **来源**：用户提供的 Bug 修复顺序清单（按复杂度分级）
> **判定**：执行路线图，非独立 Bug 条目。各条目已在 A/B/C/D 区登记，此处仅标注执行顺序与前置条件。

### 优先级一：低复杂度（单人单文件，≤30 分钟，无契约风险）— 建议合并为一个小 PR

- **D-3**：`vite.config.ts` L93-115 visualizer/compression 注释态配置块（死配置，误导维护者）
  - 修复建议：直接删除 3 个注释块（git 历史可追溯），删后跑一次 `vite build`
  - 前置条件：无
  - 风险：无（零行为变更）
- **B-13**：`UserBatchImport.vue:300` 第 9 处内联 ExcelJS 模板导出
  - 修复建议：前置将 `userBatchImport.config.ts:260` 的 `排序: 100` 数值改字符串；然后换 `downloadExcelTemplate`、删 `import ExcelJS`
  - 前置条件：数据规范化（排序字段 String()）
  - 风险：低（与 A-17 同构，无功能缺陷）
  - **两者都碰批导入域，互不冲突，合并为一个小 PR 一次清掉**

### 优先级二：中复杂度（跨文件/需设计，需排期）

- **面包屑 UI**：✅ 已完成（2026-09-09，commits `466d683` UI + `43fb2d8` 字典漂移根治 + `40816d1` 菜单文案对齐）——`AppBreadcrumb.vue` 已建（消费 appStore.breadcrumbs + usePageHeader 共享 computed），generateBreadcrumbs 改从 route.matched meta 派生（routeMap 字典删除，新增路由自动生效），菜单/页头/面包屑三处文案已统一
  - ~~修复建议：新建全局 `AppBreadcrumb.vue` 消费 `appStore.breadcrumbs`，挂 `MainView` 页头下方~~ 已实施并验证（4 用例 spec + 全量 1456 通过）
- **C-10 专项（第一阶段）**：63 处 `!important` 覆盖战争
  - 分布：6 个详情页样式文件各 8 处（48）+ `CommonList.vue` 8 + `common-forms.scss` 6 + `MainView.vue` 1
  - 修复建议：先消解 `common-forms.scss` 6 处与 `CommonList` `:deep` 的冗余（确定单一事实层），再从 6 个详情页中选 2 个试点换共享 mixin；每批需样式回归（明/暗双主题）
  - 风险：中（涉及样式回归验证，需明/暗双主题确认）

### 优先级三：高复杂度 / 需单独评估确认（动契约或架构，未获批不动）

- **D-1 ✅ 已关闭（2026-09-10）**：`unregisteredasset` 手写 `batch_create` 已收敛至 `batch_execute`
  - 结果：core `batch_mixins.py` 补齐 DRF `ValidationError` 分支；新增 Service 方法；View 收缩；Service 内 pop `row_number` 保契约逐字节一致（test_b5 断言零改动）
  - 回归：unregisteredasset 76 passed + 全部消费方 694 passed + 护栏 PASS + Service 覆盖率 90.48%
  - 明细见 D 区条目
- **D-4**：API 详细文档双份维护（后端 docs 25 文件 vs 前端 docs 32 文件并存）
  - 修复建议：跨端文档归属是组织决策——删哪份、谁做唯一事实源，需你拍板；建议后端侧为权威（随 OpenAPI 契约快照），前端改链接引用；或直接引入文档托管统一出口
  - 风险：中（涉及跨端文档归属决策）
  - **前置条件：用户决策唯一事实源**
- **D-5**：后端 `getassetbyrecordcode` 纯路径调用必 400（路径参数被 L184 query 读取遮蔽）
  - 证据：你已决策 Q4=a：只登记不动后端，等后端排期；且前端 0 调用方、无实际影响面
  - 修复建议（供后端排期）：后端改为优先路径参数、query 兜底；补纯路径集成测试
  - 风险：低（无前端影响面）
  - **状态：⏳ 已登记待后端处理**
- **路由直连 API**：39 个 `.vue` 直接 `import @/api/*` 绕过 Pinia Store（实测：45 行 import / 39 唯一文件 = 24 components + 15 views；其中 3 文件属 infra 导入：BasicAssetDetails→`@/api/config`、ScanAssetView→`@/api/request`、AssetBatchImport→`@/api/index`）— AssetBatchImport→`@/api/index` 已消除（2026-09-22，BF-014 复核）
  - 修复建议：架构分层问题，涉及 39 文件的行为面重构；分域迁移（asset/contract/user…），每域先补 store 层缺方法，再改组件消费 store；vitest 回归
  - 风险：高（此前已明确“不搭 DRY 顺车，单独评估”）
  - **增量护栏已落地（2026-09-10，v2.9.18）**：eslint.config.ts 新增 `app/store-layer-no-direct-api`（no-restricted-imports 正则 `@/api/<业务模块>` 拦截，infra 三入口放行）+ `app/legacy-direct-api-files`（存量 36 文件豁免清单）——规则只约束新代码，存量迁移一个、从豁免清单移除一个，清单清空即关闭本条目。验证：`npx eslint .` 0 error（门禁全绿）。
  - **前置条件：专项评估批准，制定分域迁移计划**（现仍待批准，ESLint 增量护栏不阻断、不替代）

### 冻结项（用户已决策不重构，列出仅为完整性）

- **C-5**（双标题结构）、**C-6**（列表页骨架无底座）、**C-7**（form-actions 浮层模式）、**C-4** 的 `.upload-tip` 8 处——均为 09-08 决策“仅登记不重构”，除非未来 `ListPageShell` 底座立项。

### 建议执行顺序

> 1. **两个小活合并一个 PR**（D-3 + B-13，随时可做）
> 2. **面包屑 UI**（独立小特性，纯新增组件）
> 3. **C-10 试点**（需专项排期，明/暗双主题回归）
> 4. **四项待逐一拍板**（D-1 最急，因其证据链最弱，先 diff 再决策）

---

## 附：回归护栏（可验证不变量）

由 `scripts/check_duplicate_invariants.py` 守护，CI job `duplicate-guard.yml` 触发：

| ID | 不变量 | 守护方式 |
|:--|:--|:--|
| G-1 | 已关闭模式的函数名不得复现 | 关键词黑名单（validate_asset_status、filter_assets、AssetQueryManager 等）全仓 grep |
| G-2 | 操作日志查询唯一实现 | `operation_log_service.py` 必须 import `OperationLogSelector`，且 `AssetOperationLogManager` 不得重新出现 |
| G-3 | 前端资产状态映射单一来源 | `Format.ts` 不得包含资产状态标签字面量表（已改为派生）；`statusMapping.ts` 为唯一字面量来源 |
| G-4 | 新错误码无需注册 | 服务层 `error_code` 字符串独立于 `BusinessCode`，仅用于批量操作 `fail_items` 日志，不进入响应体 `code` 字段，无需注册 |

> G-4 为提示型检查：`error_code` 字符串仅用于 `fail_items` 日志，前端不消费，无需与 `BusinessCode` 对齐。

## 变更记录
- **v2.9.36 (2026-09-22)**：A-29 例外项加固落地（跨部门越权安全修复）——Service 写路径 approve/reject/update/cancel/batch 全加 `user=None` 透传 + Selector `get_asset_recordcode_for_update`/`get_for_update` 部门作用域收口（B12 模式，越界≡不存在）；View 六动作传 `user=request.user`；两锁查询改 `select_for_update(of=("self",))` 规避可空外连接 NotSupportedError（`of=("self",)` 由可选增强升级为启用技术）；跨部门批量取消返回 `DAMAGED_ASSET_NOT_FOUND` fail_item，success+fail==total 契约保持（不经 ids 预筛）；`TestWritePathDeptScope` 5 用例先红后绿；BatchDeleteSerializer.ids help_text 修正（schema 逐字节无 diff）。验证：定向 54 passed、全量 1048 passed（+5）、整体 81.12%、Service 96.44%、ruff 0、mypy 4 生产文件 0 错、护栏 PASS。Bug 活账本 BF-034 登记。
- **v2.9.35 (2026-09-22)**：A-29 观察项收口（用户复核，doc-only）——① 未预取关联定性为性能取舍非问题，`select_for_update(of=("self",))` 登记可选增强未排期；② 行级隔离实证修正：背底为 View 层 `get_queryset_for_user` + `RecordcodeLookupMixin.get_object()` 404 兜底 + create 路径 ensure_asset_visible(:46-47)，非「Asset 主表兜底」（:172 仅行锁且属 approve 家族）；③ **新登记例外面**：`batch-delete`（damaged_asset_view.py:211-225）直传 ids 零部门作用域，跨部门可取消他人部门待报废记录并连带恢复资产状态（角色门控 IsDeptManagerOrAbove，预先存量于批量删除框架时代）——独立加固项暂不排期，最小形态=ids 预筛或 Service 加 user 参数（B12 模式）。
- **v2.9.34 (2026-09-22)**：关闭 A-29（DR-3 全清，§1.8 新发现义务）——Service 层 5 处裸 `OutAsset/DamagedAsset.objects` 查询下沉 Selector 共 5 新方法（`has_active_outasset`/`get_active_outasset`/`get_outasset_for_update`/`has_active_record`/`get_for_update`，逐字保留查询形态，零行为变化）；归属修正（`:215/:219` 系 A-21 收编残留、`recycle:319` 系扫描新发现，原「审查 #10」指控张冠李戴）；决策反转（A-21「HTML 快照未改写」定案按用户拍板反转，`batch-create-optimization-plan.html` :832/:899 旧码同步 `ASSET_HAS_OUTASSET` 并加注记）；编号冲突规避（A-23 已被 #11 影子死文件占用，顺延登记 A-29）。验证：定向 110 passed、全量 1043 passed、整体 81.11%、Service 96.44%、ruff 0、mypy 0 新增、护栏 PASS、双 grep 0 残留。
- **v2.9.33 (2026-09-22)**：关闭 B-15（审计归一化双实现收敛，DR-1）——删除 `asset_service.update_asset` 内嵌 `_normalize` 局部函数（原 :192-200），before_data/after_data 改传原值，归一化由 `log_operation` :134-135 已落库的 `_to_json_safe` 幂等收口（唯一实现）；删除 `_normalize` 唯一消费的三个孤儿 import（datetime/Decimal/UUID），保留模块级 `import uuid`；docstring 改指写入收口。测试：`test_update_asset_fk_instance` 扩展 FK 实例 + Decimal 快照断言（CT-4 新增锚点），三套件 97 passed、rg 残留零命中、ruff 0、mypy `asset_service.py` 零新增（其余为 dateutil stubs/var-annotated 存量）。否决替代案：utils/ 公共函数（与写入收口方针相悖）、跨模块 import 私有 `_to_json_safe`（破坏封装）。零行为变化、无契约/迁移。<br>
- **v2.9.32 (2026-09-21)**：关闭 A-28（审查报告 #26，DR-1/FR-2）——Excel 导出流程三归一并：两专用 composable（`useOperationLogExcelExport` 112 物理→46 逻辑 / `useUserExcelExport` 168 物理→62 逻辑）重写为「列配置 + 组装」薄壳，流程收敛至通用 `useExcelExport.exportList`（唯一实现），通用版零改动。事实纠偏：方案初稿「User 版在用 additionalData」不成立（`excelExporter.ts:39` 声明但 `exportToExcel` 函数体从不读取，部门映射靠 formatter 闭包），故不新增透传并移除 User 死透传与 spec 断言。行为差异四类按用户拍板统一并留痕（文件名去 page / 错误处理统一 / 弹窗未知异常吞→重抛 / 文案统一）。验证：双 spec 先红 11 failed → 17 passed，`useExcelExport.spec.ts` 8 passed，全量 `npm test` 1912 passed，type-check/lint/format 全绿，`check_duplicate_invariants.py` + `check_frontend_invariants.py` PASS。契约零变化，`api-schema-baseline.json` 无需重导出。另立任务：`ExcelExportConfig.additionalData` 死字段清理。
- **v2.9.31 (2026-09-21)**：关闭 A-27（审查报告 #25，DR-1）——前端双分页响应类型并存收敛：`stores/entityStoreTypes.ts` 的 `ListResponse<T>` 由独立 interface 改为 `types/common.ts` 的 `PaginatedResponse<T>` 派生别名（`Pick` count/results 必填 + `Partial` next/previous/total_pages/page/page_size），5 处领域手写接口（assettype/contract/department/user/storage）同步别名化，删除 18 个 store 的 `next`/`previous` 冗余映射（36 行）与 3 处旧兼容死类型（`ContractListResponseOld` + 注释版 `EmployeeListResponseOld`/`DepartmentListResponseOld`）。纯类型层，零运行时变更（被删键全仓无读取方）；`tsconfig.app.json` 测试目录豁免使 spec fixture 不参与类型检查（既有设计）。验证：`npm run type-check` 0、`npm run lint` 0、`npm run format:check` 全绿、`npx vitest run src/stores/__tests__` 495 passed、全量 `npm test` 1912 passed、`check_duplicate_invariants.py` PASS、`check_frontend_invariants.py` PASS（FR-8 stores 30 文件 / 0 超限）。附带 `prettier --write` 修正 #24 遗留的 brokenasset/recycleasset 格式漂移。契约零变化，`api-schema-baseline.json` 无需重导出。
- **v2.9.30 (2026-09-21)**：B-22（unregisteredasset 审计留痕 try/except×4）经 C10 收尾①收敛为 `_safe_call_audit`（唯一 try/except + getattr 分派），转「已关闭」归档为 A-25，B-21 遗留孤立验证行清理；B 区清空。
- **v2.9.29 (2026-09-21)**：B-23（broken/lost 双胞胎）随 BR-4 B3 完结（guard 0/0）转「已关闭」归档为 A-24，C10 落地证据与验证命令留档；B 区只余 B-22 待修复。
- **v2.9.28 (2026-09-21)**：BR-4 B2 批次登记（审查报告 #21 联动）——新增 B-22（unregisteredasset 审计留痕 try/except×4，C4 已部分收敛为 `_log_create/_update/_approve_audit` 三 helper，delete 内联待收，状态待修复）与 B-23（`mark_asset_broken`/`mark_asset_lost` 状态流转双胞胎，C10 同步统一排程中，六处差异留档）；两者均系 §1.8 新发现义务登记（B2 拆分过程中暴露/沉淀），非新增重复实现，不触发 G-1~G-4 不变量。同批审查报告 #21 追加 B2 拆分修复追踪行与 B2 验证结果。台账由 B2 移除后 4 行（B3 全为 mark_asset_lost 等）→ 保持不变；C10 统一后本条目转亮闭合并移除台账行。
- **v2.9.27 (2026-09-20)**：SC-1 空密钥签名修复（审查报告 #20，安全红线）+ base 抽象基类守卫——① `config/settings/base.py:212` 删除 `SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY` 物化键：base 加载时快照 `config("SECRET_KEY", default="")` 为空串，simplejwt `api_settings` 命中用户键后永不回落，导致 development/正常部署 JWT 均用空密钥 HMAC 签名（实证空密钥可 decode 任意 token）；删除后 simplejwt `__getattr__` 回落 `DEFAULTS["SIGNING_KEY"] = settings.SECRET_KEY`（运行时、各环境已覆写真实密钥），三环境实证回落正确。② `base.py:34-41` 新增守卫：`DJANGO_SETTINGS_MODULE == config.settings.base` 时 raise ImproperlyConfigured（base 为抽象基类禁止直接部署，模块加载 fail-fast）。③ 修正 :24 不实注释（原称直接部署会抛异常，实为空密钥静默可用）。新增 `config/tests/test_base_settings_guard.py` 4 条（守卫 2 + 回落 2），先红 4 FAILED → 后绿 4 PASSED。非重复代码治理项（SC-1 安全修复），不触发 G 不变量。验证：config/tests 19 + auth 80 + assetmanagement 724 + 其他 211 = 1034 passed；`manage.py check` no issues；ruff 0；mypy `git stash` 前后 23 errors in 10 files 完全一致（零新增，base.py 零 error）。契约零变化，`api-schema-baseline.json` 无需重导出。
- **v2.9.26 (2026-09-20)**：B9 枚举约束收敛（审查报告 #19，BR-3 落地）+ 双枚举豁免留档——生产态字面量归零：`damaged_asset_service.py:80` `to_state="damaged"`→`Asset.AssetStatus.DAMAGED`、`out_asset_serializers.py:208` queryset `"in_store"`→`IN_STORE`、`asset_selector.py:116` 可用资产 Q 两处→`IN_STORE`/`RECYCLED_PENDING`、`dashboard_selector.py:346` `"in_use"`→`IN_USE`；测试侧仅 `test_damaged_asset_service.py` 16 处收敛（构造 7 + 断言 9，用户裁断最小收敛，其余 29 测试文件维持字面量）。靶点修正：报告 `asset_crud_serializers.py:302` 指控不成立（:302 = asset_purchase_number default，该文件零状态字面量）；报告 `:68` 过时实为 `:80`。**豁免留档（新发现义务 §1.8）**：`state_machine/constants.py::AssetState` 为与 `Asset.AssetStatus` 值完全平行的第二套枚举（从字符面环绕 `AssetState.from_string(asset.asset_current_status)` 反解），属 DR-1 更大矛盾面——非字符串字面量，超出 B9 规则射程，建议另立架构任务（state_machine 改消费 `Asset.AssetStatus`，`from_string` 值等价可互换），本次不动；`batch_serializers.py:100` 仓库类型 choices、`operation_log_service.py:306` 记录类型字段、`operation_log_views.py:65` API enum 参数均非资产状态语义。验证：定向 6 套件 145 passed、assetmanagement 全模块 724 passed、ruff 0 错、mypy 4 源文件零新增（20 errors 全为 dateutil stubs/var-annotated 存量，pre-fix 比对确认）；`to_state="<状态>"` 与 `asset_current_status="<状态>"` 生产字面量全仓归零。契约零变化（TextChoices 成员值等价），无迁移，无 G 不变量触发（B9 系 BR-3 规范收敛，非重复模式新增/关闭）。
- **v2.9.25 (2026-09-20)**：D-5 条目联动更新（B2 URL 命名一致性整改，审查报告 #18，跨端契约）——`getassetbyrecordcode` 端点随整体 URL 整改更名为 `get_asset_by_recordcode`（`asset_view.py:190` url_path 变更），证据文本旧路径/旧行号（`:182-187`）同步更新；同批整改关联资产/合同两端点（`getassetbyname`→`get_asset_by_name`、`getcontractByname`→`get_contract_by_name`），方法名与 reverse 名不变，D-5 语义（路径参数优先、query 兜底）不受影响。验证命令保持 `test_get_asset_by_recordcode_path_only`（用例名未变）。非重复代码治理项，账本侧仅做 D-5 路径与行号归档修正；本项非新增/关闭条目，不触发 G 不变量。验证：后端三测试文件 69 passed、assetmanagement 全模块 724 passed；前端 api 2 spec 28 passed、相关套件 104 passed、type-check/lint 干净。

- **v2.9.24 (2026-09-20)**：关闭 A-23（审查报告 #11，DR-1）——`apps/usermanagement/services.py`（277 行）与同名 `services/` 包并存，包优先解析使 `.py` 版为影子死代码（B-11 应用级同型），删除 `services.py` + `__pycache__/services.cpython-313.pyc`，包内 4 文件与既有未提交改动不动。靶点修正：影子可正常导入（`BusinessLogicError`@core/exceptions.py:72、`ValidationError` 为其别名 :119），死因纯系包优先；旧审查文档 `services.py:527/182` 行号属更老 527 行版本快照。验证：`pytest apps/usermanagement -q` 99 passed（基线 99，净变化 0）；`ruff` 0→0；`mypy` 仅存量 `models.py:122` 零新增；`manage.py check` no issues；符号冒烟 `usermanagement.services.__file__` = `services\__init__.py`。附带登记建议项（未实施）：护栏脚本 `scripts/check_duplicate_invariants.py` 补 `if (BACKEND/"apps"/"usermanagement"/"services.py").exists(): BLOCK`（仿 G-2，约 5 行）防同名死文件复现。

- **v2.9.23 (2026-09-18)**：AC-61 审计断链修复（用户审计项 B7，独立小批次）——关闭 A-20：`recycle_asset_service.py::create_recycle_asset` broken/lost 分支补齐第二次 FSM 转换审计（`log_state_change`，from RECYCLED_PENDING，to BROKEN/LOST，trigger `recycle_mark_broken`/`recycle_mark_lost`，operator 回退与 `_do_recycle_asset_update` 一致）；该路径此前零测试覆盖，新增 `TestRecycleWithBrokenLostMarks` 3 条（broken/lost 审计断言 + normal 反向回归护栏防过度审计泄漏）。编号冲突规避：既有 B-7（throttles）占用，登记为 A-20。验证：定向 19 passed、回收向 32 passed、全量 1165 passed、整体覆盖率 81.73%、app 级 mypy 26 存量不变零新增、ruff 0 错误。

- **v2.9.22 (2026-09-18)**：B-20 关闭（第 4 处裸查询收敛，独立小批次）——新增 `AssetSelector.referenced_employee_recordcodes`（豁免 #10，docstring 7 项拆分规范化使 inline #7/8/9 与条目一一对应 + 新增 10）；employee_service 预检查块委托收敛、保留闭包注入机制；新增 6 条 selector 单测 + 1 条保管人端到端（申请人路径既有用例自动回归）。全量 1162 passed、整体 81.62%、usermanagement Service 91.60%、mypy 双 app 零新增、护栏 PASS。
- **v2.9.21 (2026-09-18)**：B12 收尾（残留裸查询治理）——关闭 A-19（三处删除守卫收敛至 `AssetSelector.exists_by_*` 新增豁免 #7/8/9 + 删除 waste/damaged selector 各 1 个死方法及 4 个测试；三守卫零孤儿 import；行为逐字节等价，HAS_RELATED_ASSETS 不变）；登记 B-20（第 4 处裸查询 `employee_service.py:348-357` 员工删除守卫直查 Asset，跨 App、返回值 recordcode 集合，收敛需用户批准，待决策）；G-1 黑名单追加 `def get_asset_recordcode_by_asset_code`（A-10 同型死方法防复现）。全量回归：pytest 1155 passed + Service 覆盖率 93.06% + 整体 81.61% + ruff 存量 7 基线不变 + mypy 改动文件零新增。
- **v2.9.19 (2026-09-10)**：登记 B-14 并关闭（R6-03，usermanagement 同型死文件）——`apps/usermanagement/views.py`（894 行）为包遮蔽死文件（B-11 应用级同型：包优先解析），全仓零模块级引用（唯一入向 `urls.py:13` 与包内 `views/employee_view.py:27` 均解析到 `views/` 包，其余命中为历史文档；无 importlib 路径加载），整文件删除。同时修正 C-8 条目过时路径 `usermanagement/views.py:61` → `views/department_view.py:64`（与活实现一致，原路径实为死文件）。验证：`python manage.py check` no issues + 全量 pytest 1074 passed。
- **v2.9.18 (2026-09-10)**：路由直连 API 条目治理落地（自选主判断通过后用户批准实施方案）——eslint.config.ts 新增两个 flat-config 块：① `app/store-layer-no-direct-api` 对 `src/components/**`、`src/views/**` 启用 `no-restricted-imports`（**ESLint v10 实证：`patterns[].group` 仅支持 glob，斜杠正则已废弃，须走独立 `regex` 字段**——初版 group 不触发，print-config + 读 node_modules 规则源码定位后改 `regex`）；正则 `@\/api\/(?!config$|request$|index$)[a-zA-Z0-9_-]+$` 拦业务模块、放行 infra 三入口（config/request/index）；② `app/legacy-direct-api-files` 登记存量 36 文件豁免（24 components 去 2 infra + 15 views 去 1 infra），迁移一个移除一个。验证五步：正向临时文件 `@/api/department` 必报错、infra 三导入不报错（负向）、`npx eslint .` 0 error、type-check 0 错、format:check 通过——五项全绿；临时文件已删。不新增 G 不变量（ESLint 规则即护栏，grep 式不变量会重标 36 存量，与增量语义冲突）。
- **v2.9.17 (2026-09-10)**：D-5 修复完成（Q4=a 冻结经用户解除）——`asset_view.py:185` 路径参数优先、query 兜底（纯路径调用不再必 400，query-only 行为不变，双传路径优先）；补纯路径集成测试 `test_get_asset_by_recordcode_path_only`。对抗审核：400 分支经证为防御性代码（url_path 捕获组 `[^/.]+` 非空约束，路由层无法产生空参数请求——曾试的空串 reverse 用例被 Django 拒绝，改注释说明不设用例）；全仓无第二处 query-only 读取；错误文案未动。回归：test_asset_view_api + rbac 共 42 passed。后端仓随本批提交。
- **v2.9.16 (2026-09-10)**：D-4 修复完成（方案 B 落地，用户拍板）——实测推翻"双份副本"口径：`API详细文档0608.md` 两份逐字节相同（纯 CRLF 镜像）→ 前端版删除；`API.md`/`SECURITY.md`/`TESTING.md`/`WORKFLOW.md` 四份经内容定性为**同名不同物**（后端 27 章端点契约 vs 前端 16 章 api/*.ts 消费文档；服务端安全 vs casl UI 管控；pytest vs Vitest；后端流程 vs GitHub Flow）→ 前端四份加 `FRONTEND_` 前缀去歧义（git mv，内容零改动）；前端内部错拼双份 `ARCHITECUTRE.md` 经定性为独立文档（系统架构设计/依赖红线）→ 改名 `ARCHITECTURE_OVERVIEW.md` 保留；`docs/README.md` 新增"文档索引"段（API 契约权威指向后端 + 六文档对照表）；全仓引用清查零断链。决策 2（文档托管出口 GitBook/Docusaurus）登记为待办，待 D-4 收敛后出方案。D-1 状态见其条目与 v2.9.15 记录（并行会话已完成关闭，本条目早稿中"待实施"表述作废）。
- **v2.9.15 (2026-09-10)**：D-1 关闭——`unregisteredasset` 手写 `batch_create` 收敛至 `BatchOperationMixin.batch_execute`。core `batch_mixins.py` 补齐 `except serializers.ValidationError` 分支（原 DRF `ValidationError` 落 `except Exception` 被吞为 INTERNAL_ERROR，现路由 VALIDATION_ERROR；复用 L30 已导入的 serializers 零新依赖；完整复刻 row_number/input_data 组装；core 变更跨 10 消费方，已声明）；新增 `UnregisteredAssetService.batch_create_unregistered`（services.py，闭包内 serializer 校验 + create）；View 收缩（空/超限 400 原样保留、`resolve_operator` 循环外一次、委托 Service、`BatchResponseHelper.create_response(request_items)` 回写原始 input_data）；Service 内 `pop("row_number", None)` 保证 fail_items 契约与手写版逐字节一致（test_b5 逐键锁定断言零改动，剔除仅本方法生效）。回归：unregisteredasset 76 passed + 消费方 694 passed + 护栏 PASS + ruff/mypy 干净 + Service 覆盖率 90.48%。前序登记见 D 区条目。
- **v2.9.14 (2026-09-10)**：C-10 账本条目状态同步——条目补 ✅ 已修复状态行（63→1 实测收口，附 `eb73f17`/`03f5630` commit 链与残余 1 处 MainView.vue:205 另立专项说明），验证命令更新为新预期值；修复主体见 v2.9.11/v2.9.12 记录。至此 B-13/D-3 待办外，C 区仅余 C-10 残余 1 处（独立专项）与冻结项。
- **v2.9.13 (2026-09-10)**：首页 Row 4 不显示 + 无滚动条修复——根因：App 壳重构（cb7b48f）后 `.common-main` 为 height:100%+flex column+overflow:hidden 裁剪壳，16+ 列表/详情页均经 list-container mixin 入列壳契约，唯 DashboardPage 根容器仍为旧范式 `height:100%`——内容超高被裁剪且无处滚动（与 AssetDetails 断链 bb71ff4 同型，壳契约第三例）。修复：`.dashboard-page-content` 改壳契约三件套 `flex:1 + min-height:0 + overflow-y:auto`（单文件 3 行）。对抗审核：复核者原方案单一 `flex:1` 不充分（flex 子项 min-height:auto 默认为内容高，无 overflow 仍被撑爆裁剪）——三件套缺一不可；卡片内滚 `el-card__body overflow-y:auto`（L253）经查父链无确定高度基准、处于休眠态，与新页面级滚动无冲突，保留；旧范式残留登记：AssetForm.vue / RecycleAssetDetails.vue（表单页嫌疑，待报告另立专项）、AsideMenu.vue（非路由页不适用）。壳契约模式沉淀：新增路由页根容器必须三件套入列。验证：vue-tsc 0 错、lint 干净、全量 vitest 106 文件、vite build 13.97s。
- **v2.9.12 (2026-09-10)**：C-10 收尾修复——表头截断 Bug（thead th 显示不全、有横滚条也无法完整展示）根因实证：C-10 重构把 mixin 的 `min-width: 1200px` 净新增到 CommonList 根规则，EP（2.13.7，table-layout.mjs:90）以 `.el-table` 根 `clientWidth` 计算全部列宽，根被 min-width 撑开后 EP 布局与可视宽度脱节，表头 wrapper（EP 自带 overflow:hidden、不可滚）与主体滚动位移失步 → th 截断。修复：删除 mixin 与 CommonList 两处 `.el-table` 根的 min-width 与 overflow:hidden（后者系 EP 自带同值重复，删除属清理非修复）；`--table-min-width` 令牌退役（消费点清零，宽度下限需求改走 EP 列定义 min-width prop）。对抗审核：`--table-min-width` 残留仅剩退役注释；其余 8 令牌消费点与定义点一一对应；两处根块终态一致。事实更正：EP 实装版本 2.13.7（此前记 2.10.5 系 package.json ^ 范围误读）；`table-layout` 声明在根 div 上为 no-op（仅对 table 元素生效），本次保留属最小 diff。验证：vue-tsc 0 错、全量 vitest 106 文件、lint 干净、vite build 14.33s。详情页视觉有意变化：删 1200px 下限后窄容器下先收缩列宽再出滚动条（历史行为归一）。
- **v2.9.11 (2026-09-10)**：C-10 第一阶段整改完成——`--table-*` 令牌体系（9 变量，variables.css :root）收敛三层表格覆盖战争：common-forms.scss mixin 内层 6 处 `!important` 与死规则 text-align/white-space 清除，CommonList.vue 8 处 `!important` 变量化（删 2 处冗余 text-align——内联 `:cell-style`/`:header-cell-style` 已居中；删 1 处无效力 nowrap），6 详情页 48 处 `:deep !important` 副本收敛为外层 `.table-container` 变量覆盖（统一值：th 16px 12px / td 12px 8px / word-break break-word，CSS 变量跨 scoped 边界继承至内层 th/td）。对抗审核实证：mixin 全部 19 个消费方 style 块均 scoped（含 4 个外链 scss 引入方）→ th/td 规则全为死代码、容器级规则经 scope-id 继承生效，table-layout fixed→auto 翻转安全；EP `.cell` 自有 `white-space:normal` + `overflow-wrap:break-word` 声明 → th/td 层 white-space 无效力（不设令牌），word-break EP 零声明可继承（设令牌）。全仓 `!important` 63→1（仅 MainView.vue:205 移动端菜单，另立专项）。验证：vue-tsc 0 错、全量 vitest 106 文件通过、lint 0 error、vite build 11.47s 成功。视觉回归需用户明/暗双主题人工比对（长数字列换行为敏感点）。
- **v2.9.10 (2026-09-09)**：账本状态标记规范化（用户要求：已完成的修复在账本中标记，免后续不清）——C-9 补 ✅ 已修复状态行（裸引用清零/ECharts 主题化实证，遗留暗色色相决策项注明）；C-11 补 ✅ 已修复状态行（附 cb7b48f/4cddc43/bb71ff4/09d5bc5 四 commit 链）；B-19 执行清单"面包屑 UI"回填 ✅ 已完成（附 466d683/43fb2d8/40816d1 三 commit）。经全账本扫描，其余条目状态标记已齐备（A 区历史关闭项、B-2/B-10/B-11/B-12 已带 commit、D-5 有 ⏳ 标记、C-2~C-8 冻结项维持原判）。
- **v2.9.9 (2026-09-09)**：菜单/meta 双源文案漂移修复 + 菜单结构调整——userdetails 与 departmentmanagement 的左侧菜单文案（AsideMenu 硬编码）与页头/面包屑文案（路由 meta.title）不一致（员工管理 vs 用户管理、通讯录管理 vs 部门-人员管理），以菜单名为准统一：两路由 meta.title 改为 '员工管理'/'通讯录管理'，guards.spec 断言同步（4 处）；通讯录管理菜单项从"员工信息"子菜单（v2.9.8 修复时仍在子菜单内）提升为顶级项——位置在仓库管理之后、员工信息之前，自带 v-if="canManageSystem"（原继承子菜单门控）+ Postcard 图标。明确不改：RolePermDialog '用户管理' 权限标签（绑定后端权限语义）、8 处文件头注释、/org/contacts 独立通讯录页（命名相近易混淆，留档提示）。验证：vue-tsc 0 错、guards 58/58、全量 vitest 1456/1456、lint 干净。
- **v2.9.8 (2026-09-09)**：面包屑 routeMap 字典双写漂移根治——`generateBreadcrumbs` 改为遍历 `route.matched` 派生 `meta.title`（单一事实源，DR-1），彻底删除 31 键局部字典（不留档，git 可溯）；新增路由（roledetails/authusermanage 等）此后自动生效，无需同步字典。实施事实：vue-router 5 在 addRoute 时将相对子路径归一化为绝对路径（dist addRoute L1167-1172），`record.path` 可直接作 crumb 链接——"matched.path 是相对路径"的判断不成立；跳过 `/main` 与含 `:` 参数级，title 缺失跳级；`matched ?? []` 防御裸路由对象。对抗审核（全表 72 路由比对）：3 处文案以 meta.title 为准发生变化（assettypedetails→资产分类类型管理、repairassetdetails→维修记录、auditlogdetails→其它操作日志），属修正字典时代陈旧文案。验证：vue-tsc 0 错、guards 58/58（11 面包屑用例含 6 场景回归防线）、全量 vitest 1456/1456、lint 干净。
- **v2.9.7 (2026-09-09)**：面包屑 UI 专项完成——新建 `AppBreadcrumb.vue`（消费 appStore.breadcrumbs，el-breadcrumb 首次引入）+ `composables/usePageHeader.ts`（MainView L99-108 页头逻辑抽取为唯一实现，DR-1）+ 同目录 `__tests__/AppBreadcrumb.spec.ts` 4 用例（双条件显隐/末项纯文本/非末项链接/空数组不渲染空壳）；MainView 挂载于 .page-header 与 router-view 之间（keep-alive/transition 不受影响）。实施要点：末项按索引判定纯文本（guards 每项均带 path，"有 path 即可点"会让末项可点）；显示条件三重（showPageHeader && settings.showBreadcrumbs && breadcrumbs.length）；组件自带 flex-shrink:0 适配 C-11 flex 链。对抗审核：EP 经 unplugin-vue-components/ElementPlusResolver 按需注册（components.d.ts 佐证），测试需显式注册组件（生产无需）；EP :to 项渲染 .is-link span 而非 <a>（断言按此修正）。验证：vue-tsc 0 错、定向 4/4、全量 vitest 1450/1450、lint 干净。
- **v2.9.6 (2026-09-09)**：任务清单 ①（两个小活合并单 PR）落地——关闭 B-13（UserBatchImport 第 9 处内联导出迁移至 `downloadExcelTemplate`，工具类型拓宽 `TemplateCellValue = string | number`，新增 4 条单元测试）；关闭 D-3（删除 vite.config.ts 注释态 visualizer/compression 副本，**记录"在用 production 块持续引用，导入必须保留"**，防止后续误删）。前端三项检查 + 全量 vitest（105 files / 1446 tests）通过。
- **v2.9.5 (2026-09-09)**：新增 B-19 执行顺序清单（按复杂度分级：低/中/高/冻结四项，含执行顺序建议与前置条件标记），登记用户提供的 Bug 修复顺序清单作为活账本条目。
- **v2.9.4 (2026-09-09)**：全账本状态复核——B-2 确认已修复（`bbccfbe` M-7 删除死副本，原"未执行"标记过时）；C-2 证据同步（types/outasset.ts 副本已删，仅剩 Format.ts）；B-13 复核确认仍待修复（`new ExcelJS.Workbook` 1 命中）；D-3 复核确认仍待修复（vite.config.ts L94-110 注释块仍在）；D-4 复核确认仍待决策（两份 API 文档并存）；C-9/C-10/D-6/C-11 及 Phase 1/2 执行结果复核全部与代码一致（裸引用 0、!important 63 未变属预期、ECharts 硬编码 0、useChartTheme 含 isDark 依赖）。另同步核验文档：修正 Phase 1.3"重建实例"过时表述（与 §2.4 修正一致）、更新后续专项表（层级令牌/表单按钮/分页配置已完成，61 文件归属已决断）。
- **v2.9.3 (2026-09-09)**：登记 C-11（bottom-buttons sticky 悬浮遮盖内容 → App 壳式布局根治，已修复）——共享层 8 处改动（list-container/table-container/bottom-buttons 三 mixin + responsive 两处残留 + MainView/CommonList/SmartListContainer/SearchBar flex 链），16 个列表页零模板改动自动生效；--z-sticky-bar 令牌退役；对抗审核确认例外页（UserDetails/DamagedAssetDetails/OperationLogDetails）经外链 .scss 同样走共享 mixin、无断链；Dashboard/子路由详情/全屏遮罩边界不受影响。同日 D-6 条目追加 sticky-bar 退役说明。
- **v2.9.2 (2026-09-09)**：B 状态同步核实——B-11 确认已修复（后端 `c64675c` 删除 5 个被包遮蔽的死文件）；B-12 确认已修复（前端 `2ced9dd` userStatusMapping 派生化，dismissed 未补系枚举仅三态、派生源为本地图而非 statusMapping 表，两点偏差均记录为合理）；B-13 保持待修复不动。
- **v2.9.1 (2026-09-09)**：D-6 二次核验修正——z-index 实为 4 文件 8 处（初版漏 MainView:165=2000）；"子路由遮罩各页手写无共享 mixin"不实（实为 common-forms.scss 三个 mixin 经 @include 被 13 个详情页复用，仅 AuditLogDetails 游离）；补充"common-list/bottom-buttons 非层叠问题勿误治"边界说明。
- **v2.9 (2026-09-09)**：前端设计审计修复落地——关闭 A-17（handleExportTemplate×8 → downloadExcelTemplate，含删除重复工具 exportImportTemplate.ts）、A-18（page-sizes 字面量×5 → PAGE_SIZE_OPTIONS）；C-4 局部收敛（Damaged/Department 手写 import-guide-card → BatchImportGuideCard，upload-tip 按 09-08 决策保留）；登记 B-13（UserBatchImport 第 9 处内联模板导出残留，待数据规范化后迁移）。
- **v2.8.1 (2026-09-09)**：C-9 精化——dark.css 与 variables.css 的暗色主色（#4a90e2）实为同步（同值），"三源不同步"修正为"SCSS 编译期固化亮色值不随暗色切换"（真正的缺陷是裸引用，非三源值漂移）；修正 v2.8 记录中"LoginDialog.vue 不存在"的误判（该文件存在于 src/components/LoginDialog.vue:75，初核查错路径）。
- **v2.8 (2026-09-09)**：前端设计审计核验——登记 C-9（主色令牌三源不同步：CSS 变量/SCSS 编译期/dark.css EP 变量，暗色修复前置阻塞）、C-10（63 处 !important 覆盖战争 + :deep(.el-table) 重复，登记不立即重构）、D-6（z-index 并列 1000 无层级令牌）。同时核验外部审计报告：大方向属实但多项数字不实（字体违规 25→15、rgba 8→24、400-485 行文件 20→26、LoginDialog.vue 不存在）。
- **v2.6 (2026-09-09)**：ID-2 资产域双约定实证——新增 C-8（detail 路由=recordcode / batch-delete=asset_code 双约定契约特性，含前端防线与防回归断言）；登记 D-5（后端 getassetbyrecordcode 路径参数失效，只登记不动后端）。
- **v2.5 (2026-09-08)**：前端展示页专项登记 C-4~C-7（批量导入上传提示/导入指南区块、详情页双标题结构、列表页骨架组装、底部操作栏浮层），用户决策仅登记不重构（P3 排期外）。
- **v2.4 (2026-08-26)**：H-1 整改落地——新增 A-16（Python 依赖清单双份维护，已收敛单一事实源）；登记 D-3（vite.config.ts 注释态配置副本）、D-4（API 文档双份维护）。
- **v2.3 (2026-08-24)**：登记 D-2（init_production_data 管理命令 3 个字段名 bug，测试发现并修复）。
- **v2.2 (2026-08-24)**：关闭 F-1~F-4/F-6/F-7 共 6 项（A-10~A-15）；B-1 标记已关闭；登记 D-1（F-5 暂不收敛）。
- **v2.1 (2026-08-13)**：落地 C-1 决策（未知状态回退=原始值），新增 A-9；B-1/B-2 确认排入独立 PR。
- **v2.0 (2026-08-13)**：由静态清单重构为四区活账本。关闭原 A-1~F-1 全部 11 条（含证据）；登记本次 2 项修复（A-7/A-8）、2 项待修复（B-1/B-2）、3 项降级/决策门（C-1/C-2/C-3）；新增回归护栏不变量（G-1~G-4）。
