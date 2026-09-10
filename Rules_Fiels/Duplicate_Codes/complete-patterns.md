# 重复代码模式活账本（Living Ledger）
> **版本**：v2.9.7 | **最后更新**：2026-09-09 | **性质**：动态账本，取代 v1.0 静态清单
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
- **合法例外（非 bug，勿误改）**：部门 `lookup_field="department_code"`（`apps/usermanagement/views.py:61`）、未登记资产 `lookup_field="unregistered_code"`（`apps/unregisteredasset/views.py:86`）——这两个域的 detail 路由以业务编码为键，与资产/合同的 recordcode 约定不同。
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
- **验证命令**：`rg -n "2b5fd7" vue-assetmanagement/src`；`rg -n '\$primary-color' vue-assetmanagement/src/assets/styles/common-forms.scss`；`rg -nE "#333|#e5e7eb|getComputedStyle" vue-assetmanagement/src/composables/useDashboardCharts.ts`
- **登记日期**：2026-09-09 | 来源：前端设计与质量审计核验

### C-10. 详情页 :deep(.el-table) 覆盖战争（全仓 63 处 !important）
- **判定**：样式交叉覆盖（各详情页用 `!important` 对抗公共组件内部样式；改 `CommonList` 样式会被静默拦截或引发连锁回归）。
- **证据（2026-09-09 复验修正拆分）**：全仓 `!important` 共 **63 处**——6 个详情页样式文件各 8 处（WasteAsset/UnregisteredAsset/OutAsset/OperationLogDetails.scss/HardDiskSN/DamagedAssetDetails.scss，48 处）+ `CommonList.vue` 8 + `common-forms.scss` 6 + `MainView.vue` 1。`:deep(.el-table)` 为 `CommonList.vue` 8 处 + 4 个详情页各 2 处重复（OutAsset/UnregisteredAsset/HardDiskSN/WasteAsset）。
- **修复建议**：提取共享 SCSS mixin 收敛 `:deep` 覆盖；以 CSS 变量/组件 props 传参替代 `!important`；与 Phase 3 DRY 重构合并为"表格样式覆盖"专项。
- **决策（2026-09-09）**：登记不立即重构（涉及 5+ 文件样式回归验证，需独立专项）。
- **验证命令**：`rg -c "!important" vue-assetmanagement/src --glob "*.vue" --glob "*.scss" | awk -F: '{s+=$NF} END {print s}'`（预期 63）；`rg -c ":deep\(\.el-table" vue-assetmanagement/src --glob "*.vue"`（预期 CommonList 8 + 详情页 2×4）
- **登记日期**：2026-09-09 | 来源：前端设计与质量审计核验

### C-11. bottom-buttons sticky 悬浮遮盖列表内容（布局范式问题，非层级问题）
- **判定**：交互遮盖缺陷（`position: sticky + z-index: 50` 使按钮组悬浮盖住从其下方滑过的表格内容；调 z-index/令牌无法解决，已按 App 壳式布局根治）。
- **证据（2026-09-09）**：`bottom-buttons` mixin（common-forms.scss）原为 sticky 悬浮方案；`table-container` 有 `margin-bottom: 100px` sticky 预留 hack；`.common-list` `min-height: calc(100vh - 120px)` 整页滚动范式。
- **修复（已实施）**：改为 App 壳式布局（页面名/筛选不压缩 + 表格区 `flex:1; min-height:0; overflow:auto` 自滚 + 分页/按钮组流内页脚常驻）——共享层 8 处改动（list-container/table-container/bottom-buttons 三 mixin + responsive 两处 bottom 残留 + MainView/CommonList/SmartListContainer/SearchBar flex 链），16 个列表页经共享 mixin 零模板改动自动生效；`--z-sticky-bar` 令牌退役（D-6 阶梯同步更新）。
- **边界（不参与）**：Dashboard/通讯录/通知/独立视图页；子路由详情（child-router-container 200）与全屏遮罩（router-mask 1000）行为不变。
- **对抗审核结论**：UserDetails/DamagedAssetDetails/OperationLogDetails 三页初判"无 list-container 链路"系误报（实经外链 .scss `@include` 走共享 mixin，无断链）；组件内 6 处自写 `.bottom-buttons` 覆盖均无 sticky/z-index 残留；el-table fixed 列（5 文件）位于 overflow:auto 容器内表现正常；sass 编译/lint 通过。
- **优先级**：中（用户可见交互缺陷，已根治）。
- **登记日期**：2026-09-09 | 来源：用户复审方案（第②点遮盖问题）+ 对抗审核

---

## D — 待核查（To Verify）

### D-1. unregisteredasset batch_create 手写循环（F-5 暂不收敛）
- **判定**：与 `batch_execute` 不同构，存在多处行为差异（下述 7 项为 2026-08-24 分析结论，**差异明细未经逐条 diff 复核**——2026-09-09 复审仅实证"手写循环存在"（views.py L247/L262/L349），收敛前须先逐项人工 diff 确认）：
  1. 空列表 → 400（batch_execute 处理空列表为零计数结果）
  2. 超限 → 400 响应（非异常，batch_execute 抛 AppValidationError）
  3. DRF `ValidationError` → `VALIDATION_ERROR`（第三异常层级）
  4. 无 `row_number` 键（batch_execute 添加）
  5. 无 logger.error 日志
  6. View 层调用（非 Service 层）
  7. 无 deepcopy / `_normalize_input_data`
- **位置**：`apps/unregisteredasset/views.py` L246-299
- **决策**：强行收敛会改变 400/500 行为边界，引入回归风险。暂不收敛，后续独立 PR 按方案 A（移到 Service 层 + 逐项对齐差异）处理。

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
- **状态**：⏳ 已登记待后端处理 | 登记日期：2026-09-09
- **验证命令**：`curl .../api/assets/assets/getassetbyrecordcode/Asset-20260101-XXXXXXXX/`（现状 400；修复后应 200）

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

- **面包屑 UI**：数据层完备（`guards.ts` `generateBreadcrumbs` + `stores/app.ts` `setBreadcrumbs`），`.vue` 消费方 0 命中
  - 修复建议：新建全局 `AppBreadcrumb.vue` 消费 `appStore.breadcrumbs`，挂 `MainView` 页头下方；纯新增组件，零存量改动；注意与 `showPageHeader` meta 的显隐联动
  - 风险：低（新增组件，不改存量）
- **C-10 专项（第一阶段）**：63 处 `!important` 覆盖战争
  - 分布：6 个详情页样式文件各 8 处（48）+ `CommonList.vue` 8 + `common-forms.scss` 6 + `MainView.vue` 1
  - 修复建议：先消解 `common-forms.scss` 6 处与 `CommonList` `:deep` 的冗余（确定单一事实层），再从 6 个详情页中选 2 个试点换共享 mixin；每批需样式回归（明/暗双主题）
  - 风险：中（涉及样式回归验证，需明/暗双主题确认）

### 优先级三：高复杂度 / 需单独评估确认（动契约或架构，未获批不动）

- **D-1 !**：`unregisteredasset` 手写 `batch_create`（`views.py` L247/L262/L349），不走 `batch_execute`
  - 证据：2026-08-24 分析结论（7 处行为差异），**差异明细未经逐条 diff 复核**（已在账本标注）
  - 修复建议：先人工 diff 逐项确认差异 > 按方案 A 移 Service 层 > 差异项逐一对齐或显式保留；全程基线快照测试锁定
  - 风险：高（强行收敛可能改坏 400/500 契约边界，如空列表 400、超限 400）
  - **前置条件：逐条 diff 复核完成，用户批准后执行**
- **D-4**：API 详细文档双份维护（后端 docs 25 文件 vs 前端 docs 32 文件并存）
  - 修复建议：跨端文档归属是组织决策——删哪份、谁做唯一事实源，需你拍板；建议后端侧为权威（随 OpenAPI 契约快照），前端改链接引用；或直接引入文档托管统一出口
  - 风险：中（涉及跨端文档归属决策）
  - **前置条件：用户决策唯一事实源**
- **D-5**：后端 `getassetbyrecordcode` 纯路径调用必 400（路径参数被 L184 query 读取遮蔽）
  - 证据：你已决策 Q4=a：只登记不动后端，等后端排期；且前端 0 调用方、无实际影响面
  - 修复建议（供后端排期）：后端改为优先路径参数、query 兜底；补纯路径集成测试
  - 风险：低（无前端影响面）
  - **状态：⏳ 已登记待后端处理**
- **路由直连 API**：39 个 `.vue` 直接 `import @/api/*` 绕过 Pinia Store
  - 修复建议：架构分层问题，涉及 39 文件的行为面重构；分域迁移（asset/contract/user…），每域先补 store 层缺方法，再改组件消费 store；vitest 回归
  - 风险：高（此前已明确“不搭 DRY 顺车，单独评估”）
  - **前置条件：专项评估批准，制定分域迁移计划**

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
