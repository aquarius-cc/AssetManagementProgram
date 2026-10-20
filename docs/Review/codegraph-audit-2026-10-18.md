# CodeGraph 全项目审查报告（2026-10-18）

> 定位：**纯审计，不修复**（skill v1.2.0）。全程只读，未改动任何业务代码（`eslint --fix` 执行后三仓 `git status` 均为空，已实证）。
> 工具链：CodeGraph 索引 981 文件 / 17,401 节点 / 39,135 边；会话开始时索引滞后，已 `codegraph unlock` + `sync`（增量 26 文件）后才进入诊断。
> 基线对照：`docs/Review/codegraph-audit-2026-10-15.md` + `-r2.md`。其 P1-01/02/03、P2-01~09、P3-01~04 已于 2026-10-16/17 批次（BF-096~101）闭合并经本次逐条复核仍成立，**不重复立账**。

---

## §一 项目上下文

### 1.1 技术栈与依赖

| 端 | 关键依赖（声明） | 本地实测 | 漂移 |
|:---|:---|:---|:---|
| 后端 | Django==6.0.8、DRF==3.17.2、simplejwt==5.5.1、channels==4.3.2、drf-spectacular==0.29.0、psycopg[binary]==3.3.4、prometheus-client==0.26.0 | **Django 5.2.17 / DRF 3.16.0 / Python 3.13** | ⚠️ 有（AUD-12） |
| 后端工具链 | mypy==2.1.0、django-stubs==6.1.0、djangorestframework-stubs==3.18.0、types-channels==4.3.0.20260518、ruff==0.17.1 | 全部一致 | ✅ 无 |
| 前端 | vue ^3.5.44、vue-router ^5.0.6、pinia ^3.0.3、element-plus ^2.10.5、vite ^8.2.2、typescript ^6.0.3、vitest ^4.1.11、@stryker-mutator/core ^10.0.0 | — | — |

### 1.2 模块边界

- **后端**（子模块 HEAD `724213d`）：`config/`（4 套 settings + 根 urls）、`core/`（异常/分页/权限/审计/导出/锁/指标/批处理）、`apps/` 5 个业务 app（assetmanagement 208 .py、usermanagement 69、authusermanagement 31、unregisteredasset 27、notification 18）、`utils/response_utils.py`（信封唯一入口）。
- **前端**（子模块 HEAD `93dc588`）：`src/` 489 个 .ts/.vue —— api 30、stores 32、composables 54、components 117、views 17、types 30、utils 26、router 8。
- **根仓**：`scripts/`（4 护栏 + line_metrics + 前端不变量）、`.github/workflows/` 5 个 workflow、`Rules_Fiels/`（4 规范 + 3 台账 + 265.8KB 重复活账本）、`Project_Requirements/` 18 份。
- **五层组织不统一**：assetmanagement 全包化；usermanagement 半包（models.py / selectors.py 为文件，views/ 为包）；authusermanagement 与 unregisteredasset 全扁平；notification 用单数 `service.py`。`operation_log_views.py`、`operation_log_filters.py` 落在 app 根而非 `views/` 包。

### 1.3 分域清单与探索锚点

| 分域 | 真实锚点 | 结论摘要 |
|:---|:---|:---|
| 资产状态机 | `state_machine/constants.py:27` AssetState(8 态)、`transitions.py:22` VALID_TRANSITIONS(22 边)、`core.py:31/62/85` AssetFSM、4 个 transitions mixin | 状态写点 8 处全部在 FSM 域内；已声明旁路 7 处 + 未声明旁路 2 处（§5.1） |
| 合同状态机 | `state_machine/contract_fsm.py:15/31/64/73` | 更新路径已收口（BF-096），创建路径未收口（AUD-04） |
| API 响应契约 | `utils/response_utils.py:23` success_response（174 调用方）、`core/exception_handler.py:38`、`core/pagination.py:62` | 业务面无手写 dict 旁路（§5.2） |
| 前端状态枚举 | `types/asset.ts:46`、`types/outasset.ts:48`、`utils/statusMapping.ts:31/48` | 标签映射单源已收敛；键名另有 4 处裸字符串平行硬编码（AUD-09） |
| 鉴权/日志/导入/上传 | `authentication.py:65`、`core/permissions.py:192`、`operation_log_service.py:61`、`core/batch_mixins.py:58` | 无服务端上传端点；操作日志写入有第二套实现（AUD-06） |
| 测试锚 | 后端 112 个 `test_*.py` / 前端 168 个 `*.spec.ts` | CT-3 全边两层口径全覆盖 |

### 1.4 门禁复核结果（本次实测）

| 门禁 | 命令 | 结果 | CT-7 口径 |
|:---|:---|:---|:---|
| 覆盖率 | `pytest --cov=. --cov-fail-under=80` | **1987 passed / 87.27%**，exit 0 | ⚠️ **本地环境漂移（Django 5.2.17 vs 声明 6.0.8、Python 3.13 vs CI 3.12），该数字不代表 CI** |
| 类型 | `mypy . --strict` | **Success: no issues found in 228 source files** | ✅ 工具链与 dev.txt 完全一致，结论可用 |
| Lint / 格式 | `ruff check .` / `ruff format --check .` | 全通过 / 400 files already formatted | ✅ ruff 0.17.1 = 声明版本 |
| BR-4 / BR-6 | `check_function_length_guard.py` / `check_file_length_guard.py --print` | PASS 0 超限 / exit 0（最大 `asset_view.py` 475 逻辑行） | — |
| 重复护栏 / 前端不变量 | `check_duplicate_invariants.py` / `check_frontend_invariants.py` | PASS / PASS（54 composables、31 stores） | — |
| 前端类型 / Lint | `npm run type-check` / `npm run lint` | exit 0 / exit 0（`eslint --fix` 后无 diff） | — |
| 迁移一致性 | `makemigrations --dry-run` | **No changes detected** | ✅ |
| API Schema 基线 | `spectacular --validate` + 基线比对 | 191 paths **byte-equal**（无接口漂移） | ✅ |
| SC-8 后端 | `pip_audit -r requirements/base.txt` | 1 漏洞 twisted 26.4.0 / CVE-2026-106454 —— 与 CI `--ignore-vuln` 点名豁免项一致 | ✅ 与权威门禁吻合 |
| SC-8 前端 | `npm audit --audit-level=high --omit=dev` | **0 vulnerabilities**；含 dev 则 4 high（braces dev 链，BF-100 已定性） | ✅ |
| CI workflow | ci.yml(15 jobs)、security-scan.yml(6)、ci-cd.yml(3)、migration-check(1)、duplicate-guard(3) | 与 AGENTS §6 / §1.8 描述一致 | — |

---

## §二 问题台账

> 分级：P0 阻断/高危 · P1 重要 · P2 优化 · P3 建议。状态取值：待修 / 不采纳（附理由）；表中「已修复」标记均系修复落地后由 `resolution-fix-ledger-sync` 回填（批次 A~D，详见「修复追踪」），审计时点（2026-10-18）本身不产生「已修复」。
> 「回查命令」为 CodeGraph 直达命令，可原样复跑。

### 2.1 P1（3 条）

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 影响面 | 优先级 | 建议验证方式 | 状态 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| AUD-01 | P1 | ~~异常处理缺口（裸异常→500）~~ | ~~`apps/assetmanagement/services/repair_asset_service.py:223`、`:267`（对照捕获点 `:83-86`）~~ | `RepairAssetService.complete_repair`、`fail_repair` | ~~同文件送修路径捕获 `InvalidTransitionError` 并映射 `AppValidationError`(400)，完成/失败两条路径**裸调用** `AssetFSM.repair_done/repair_failed`。前置校验只查「有无 in_progress 维修记录」（`:208-212`、`:260-264`），**不校验 `asset_current_status == repairing`**。资产被 system_admin 经 `change_status`（`asset_service.py:323`，权限 `IsSystemAdmin` 见 `asset_view.py:102`）移出 repairing、或被 `force_recycle_from_any` 改态而维修记录仍 in_progress 时，裸 `Exception`（`state_machine/constants.py:72`）落入 `exception_handler.py:101-105` → **HTTP 500**。连带 `fail_repair:283` 会以错误 `from_state` 写 `DamagedAsset.original_status`（异常先抛则回滚，但无断言防护）。~~ | 在 `:222`/`:266` 前加状态断言，或 try/except 映射 `AppValidationError(error_code="INVALID_STATE_TRANSITION")`，与 `:83-86` 同构（DR-1） | `codegraph callers complete_repair` | `impact complete_repair` → 22 符号（15 个 `test_repair_service_gaps.py` 用例 + view 入口）；`fail_repair` 同构。影响限于维修域 | 本批最高 | 新增负例：建 in_progress 维修记录 → `change_status` 移出 repairing → 调 complete_repair，断言 **400 + error_code**（非 500）；`pytest apps/assetmanagement/tests/test_repair_service_gaps.py` | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-02 | P1 | ~~异常处理缺口（审批链整条无捕获）~~ | ~~`apps/unregisteredasset/handlers.py:128`、`:150`、`:183`；`services.py:403-404`、`:407`；`views.py:297`~~ | `_force_finalize_recycle`、`_handle_s1_create_and_recycle`、`_handle_s1_create_and_damaged`、`UnregisteredAssetService.approve_and_handle` | ~~`handlers.py` 全文件无任何 `try/except`，三处裸调 `AssetFSM.*`。`services.py:222` 类 docstring 自述可能抛 `InvalidTransitionError`，但 `Raises` 块只列 `AppValidationError`；`views.py` 该异常 **0 命中**。S2/S3 走 `force_recycle_from_any`，若关联资产已是 `scrapped`（`state_machine/unregistered.py:122-124`）→ 同 AUD-01 链路落 500。`unregisteredasset/tests/` 中 `scrapped`/`InvalidTransitionError` **0 命中**，无覆盖。~~ | 在 `_execute_handle` 调用点（`services.py:407`）统一捕获 `InvalidTransitionError` → `AppValidationError(error_code="INVALID_STATE_TRANSITION")`，一处收口三条路径（DR-1）；同步补 `Raises` 文档 | `codegraph callers approve_and_handle` | `impact approve_and_handle` → 17 符号（`test_concurrent.py` 5 例 + `test_services.py` 8 例），全为未登记资产审批链 | 次高 | 构造 scrapped 关联资产的 S2/S3 审批，断言 **400 + error_code**；`pytest apps/unregisteredasset/tests` | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-03 | P1 | ~~状态机旁路 + 审计旁路（Django Admin 直写）~~ | ~~`apps/assetmanagement/admin/asset_admin.py:95`、`:111-113`（`asset_current_status`）；`:76`（`contract_status`）~~ | `AssetAdmin`、`ContractAdmin` | ~~两个 ModelAdmin 的 `readonly_fields` 均不含状态字段，fieldsets「Status」显式列出 `asset_current_status` → 后台表单可直接改状态：不经 `AssetFSM._transition`（`core.py:62-85`）、不经 `ContractFSM.transition`（`contract_fsm.py:64-73`），也不产生 `AssetOperationLog`/`AssetStateLog`/`GenericAuditService.log_update`。与 `asset_service.py:27`「状态变更所有权归 FSM」及 BF-096 对 `contract_view.perform_update` 的收口直接冲突。`/admin/` 挂载于 `config/urls.py:150`。产出的数据组合（状态与子记录不一致、回退依据失效）无法由 FSM 复现。~~ | 将 `asset_current_status`、`contract_status` 加入对应 `readonly_fields`（各 1 行）；若确需后台改状态，另设 admin action 委托 Service（走 FSM + 审计） | `codegraph node AssetAdmin` | 仅 admin 站（需 staff 凭据），但污染数据的下游影响面为全资产/全合同生命周期 | 高 | admin 变更页 GET 断言状态字段 `readonly`；`pytest apps/assetmanagement/tests/test_asset_view_api.py test_contract_view_api.py` 回归 | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |

### 2.2 P2（8 条）

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 影响面 | 优先级 | 建议验证方式 | 状态 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| AUD-04 | P2 | ~~状态机约束不对称（创建期旁路）~~ | ~~`services/contract_service.py:165`；`serializers/base_model_serializers.py:136`、`:159`；`serializers/batch_serializers.py:54`~~ | `ContractService.create_contract`、`ContractCreateSerializer` | ~~`Contract.objects.create(**contract_data)` 不经 `ContractFSM.transition`；创建可一次落入 8 个任意状态（含终态 `project_finished`），`_CONTRACT_TRANSITIONS` 校验、状态审计、`_recalc_paid_amounts` 均不参与。对照更新路径已完整收口（`contract_view.py:144` pop → `contract_service.py:321` FSM → `:326` 重算 → `:329` 审计）。终态创建的合同 `allowed_next_states` 返回 `[]`，前端下拉禁用 → 永久不可流转。~~ | **[待确认]** 二选一：① 不需导入历史状态 → 创建侧 `contract_status` 设 read_only + 服务端强制 `PURCHASING`；② 需导入 → `create_contract` 内校验目标态 ∈8 并写 create 审计，同时在 `Project_Requirements` 明示该能力 | `codegraph callers create_contract` | `impact create_contract` → 57 符号（`batch_create_contract:401`、`_create_item:420` + 合同域 20 余测试） | 高 | 方案①：POST 带 `project_finished` 断言被拒；方案②：断言落一条 create 审计且非法态 400 | ~~待修（需业务拍板）~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-05 | P2 | ~~状态机语义旁路（私有方法直调）~~ | ~~`services/asset_service.py:46-55`（关键 `:53`）；入口 `:303`；View `views/asset_view.py:303-310`~~ | `AssetService._run_manual_transition` → `AssetFSM._transition` | ~~手动改状态端点直调 FSM 私有 `_transition`（`#38` 注释明示为「避免裸异常 500」，异常映射已做对），但**绕过全部 mixin 具名方法** → 不建 `BrokenAsset/LostAsset/DamagedAsset/RepairAsset` 子记录、不写 `DamagedAsset.original_status`（服务端权威写点 `damaged_asset_service.py:57`）。可执行 `VALID_TRANSITIONS` 任意边，含 `DAMAGED→IN_USE`，而 `state_machine/scrapping.py:141-146` 声明该入边「业务不可达、`original_status` 永不为 `in_use`」→ 端点可产出与回退假设矛盾的数据。~~ | **[待确认]** 若定位为「废弃数据修复工具」：在端点文档显式声明副作用（不建子记录、可产生不可达态）并要求二次确认；否则按目标态路由到对应 mixin 方法 | `codegraph callers _run_manual_transition` | 仅 `change_status` 一个端点（system_admin），影响面小但数据语义影响全生命周期 | 中 | 断言 admin 改态到 `in_use` 后 `DamagedAsset` 记录数不变；补一条副作用文档锚 | ~~待修（需业务拍板）~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-06 | P2 | ~~DR-1 重复实现（操作日志第二套写入）~~ | ~~`services/repair_asset_service.py:108`、`:125`、`:289`；`services/asset_lifecycle_mixin.py:71`、`:204`~~ | `AssetOperationLog.objects.create`（5 处直写） | ~~唯一入口是 `operation_log_service.py:61 _insert_operation_log`（含 `_validate_operation_params:50` 参数校验与 `_to_json_safe:32` JSON 归一化）。上述 5 处直写绕过两者。当前字段恰好合规（全为固定字面量），但新增字段/嵌套对象时校验与归一化会被跳过；同时 5 处重复 7 字段赋值模板。~~ | 抽 `_write_operation_log(asset, operation_type, operator_jobcode, operator_name, description)` 至 `operation_log_service`（或复用 `OperationLogService.log_operation`），5 处改调用（DR-1） | `codegraph callers OperationLogService.log_operation` | 5 个写点，覆盖维修域 + broken/lost 生命周期域全部操作日志 | 中 | `rg -n "AssetOperationLog.objects.create" apps --glob '!*test*'` 仅剩 service 内 1 处；`pytest apps/assetmanagement/tests/test_repair_service_gaps.py test_lifecycle_mixin_gaps.py test_operation_log_service.py` | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-07 | P2 | ~~行级隔离缺口（潜伏后门）~~ | ~~`selectors/operation_log_selector.py:67`；`services/operation_log_service.py:443`~~ | `OperationLogSelector.get_operations_by_type` | ~~该方法**无 `user` 参数、不套 `_scope_by_user`**，与同文件 `:129-134`「本方法内强制套用 `_scope_by_user`，安全不可省略 user」的既有口径直接矛盾。`codegraph callers` 显示生产调用仅 service 薄封装一层，**无 View 接线**（仅 2 个测试调用）→ 当前不可达，属潜伏后门。~~ | 补 `user` 参数并强制套 `_scope_by_user`（与其余 6 个方法同构），或直接删除该方法及其 service 封装（死代码） | `codegraph callers get_operations_by_type` | 当前 0 生产调用；风险为「日后有人直接接线」 | 中 | `rg -n "get_operations_by_type" apps --glob '!*test*'` 0 命中（若删除），或新增越权用例断言返回被过滤 | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-08 | P2 | ~~表-实现断裂（5 个死方法） + CT-3 字面缺口~~ | ~~`state_machine/transitions.py:61-65`；`broken_lost_repair.py:75`、`:91`；`scrapping.py:137`、`:162`、`:178`~~ | `reject_to_broken`/`reject_to_lost`/`reject_to_in_use`/`reject_to_recycled_pending`/`reject_to_repairing` | ~~5 个具名方法 `codegraph callers` **全部 0 caller**——转发表声称的分派从未发生；回退实际由 `reject_to_original`（`scrapping.py:103-133`，自校验 + `_REJECT_TARGETS` 白名单 + 直接赋值）承载。`scrapping.py:23-26` 注释引用的 `test_reject_to_broken/test_reject_to_lost` 实际链路是 View → `damaged_asset_service.py:250` → `reject_to_original`，与注释措辞不符。5 个方法的校验语义（走 `_transition`，拒绝非 damaged 源）与 `reject_to_original` 不同，属漂移点。~~ | 倾向删除 5 个未调用方法，把表项改指 `reject_to_original`（表内注明 target 由参数表达）；或保留并补直调用例。同步订正 `scrapping.py:23-26` 注释 | `codegraph callers reject_to_broken` | 5 个死方法 + 转发表可读性；CT-3 在「方法名层」的字面缺口 | 中 | `pytest apps/assetmanagement/tests/test_state_machine.py test_damaged_asset_service.py`；`rg -n "reject_to_" apps --glob '!*test*'` 仅剩 `reject_to_original` | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-09 | P2 | ~~跨端契约维护面（键名平行硬编码 + 枚举外值）~~ | ~~`stores/dashboardStatusGroups.ts:7-23`；`stores/dashboard.ts:155-164`；`components/componentsdetails/detils/outAssetBatchImport.config.ts:129`；`assetBatchImport.config.ts:25`~~ | `STATUS_GROUPS`、`chartOrder`、outAsset 导入 remark、`ASSET_STATUSES` | ~~① `outAssetBatchImport.config.ts:129` `remark: 'in_use/returned/lost/damaged'` 含**枚举外值 `returned`**（前后端 8 态均无），且缺 in_store/recycled_pending/repairing/scrapped——用户按提示填写会被校验拒绝；同文件 `:66` 的 `validStatuses` 已改走 `Object.values` 自动受益 8 态，remark 未同步。② `assetBatchImport.config.ts:25` 导入白名单仅 5/8 态（缺 broken/repairing/lost）。③ 两 store 以裸字符串硬编码 8 键，且 3 个 hex 颜色与 `utils/statusMapping.ts` 的 `STATUS_COLOR_MAP` 重复。~~ | ① remark 改由 `Object.values(OutAssetCurrentStatus)` 生成（复用 `:66` 先例，DR-1）；② 白名单 5/8 **[待确认]** 是否业务有意收窄，若是则加注释说明；③ 分组/排序键改从 `ASSET_STATUS_MAP` 派生 | `codegraph node ASSET_STATUS_MAP` | 前端 4 处维护点；新增状态时漏改风险 | 中 | `npx vitest run src/components/componentsdetails/detils/__tests__/outAssetBatchImport.config.spec.ts src/utils/__tests__/statusMapping.spec.ts`；`npm run type-check` | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-10 | P2 | ~~安全（信息暴露面）~~ | ~~`config/urls.py:165-167`；`config/settings/base.py:348-382`（`SPECTACULAR_SETTINGS` 未覆盖 `SERVE_PERMISSIONS`）~~ | drf-spectacular `SERVE_PERMISSIONS` | ~~drf-spectacular 默认 `SERVE_PERMISSIONS = ['rest_framework.permissions.AllowAny']` → `/api/v1/schema/`、`/swagger/`、`/redoc/` **匿名可读全部 191 条端点结构**（含请求/响应字段、枚举、错误码）。非数据泄露，属攻击面测绘便利。~~ | **[待确认]** 内网部署可保留并记录豁免；否则 `SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.IsAuthenticated"]` 并重导 schema 基线 | — | 全部 API 结构 | 中 | 匿名 GET `/swagger/` 断言 401/403（若采纳）；重导基线后 `--validate` exit 0 | ~~待修（需部署确认）~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-11 | P2 | ~~死代码簇（DR-1 清理面）~~ | ~~`apps/unregisteredasset/state_machine_adapter.py:35-151`；`services/waste_asset_service.py:27`、`:66`（对照 `views/waste_asset_view.py:108-112`）；`apps/assetmanagement/querysets.py`；`selectors/outasset_selector.py`（27 行 shim）~~ | `UnregisteredAssetStateAdapter`、`WasteAssetService.create_waste_asset`/`create_from_damaged_asset` | ~~① `state_machine_adapter.py` 全仓引用**仅其自身 docstring**（`:18/21/53/56/81/109/145`），生产调用直连 `AssetFSM`（`handlers.py:128/150/183`）——151 行的第二套封装；② waste 两个创建方法生产零调用（View 已硬 405「已报废记录不允许直接创建」），其中 `AssetFSM.approve`（`:48`）成为不可达 FSM 路径，WasteAsset 实际由 `damaged_asset_service.py:166-171` 创建；③ `querysets.py` 在 `docs/compose/specs/2026-06-29-model-split-refactor-design.md:54/365/482` 三处「querysets.py 已删除」勾选框均未销项；④ `outasset_selector.py` 仅再导出 `OutAssetSelector`，与 `out_asset_selector.py` 双名并存。~~ | 按批删除 + `rg` 零引用复核；waste 删除前确认 `cancel_waste_asset`（`:158`）与 `tests/test_waste_asset_service.py` 的处置 | `codegraph callers create_waste_asset` | 4 个死文件/方法，约 400 行清理量 | 中 | `rg -n "<symbol>" apps --glob '!*test*'` 0 命中；全量 pytest；`python scripts/check_duplicate_invariants.py` | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-12 | P2 | CT-7 环境漂移 | `requirements/base.txt:15`（Django==6.0.8）、`:22`（DRF==3.17.2）vs 本地 Django 5.2.17 / DRF 3.16.0 / Python 3.13 | 本地解释器环境 | 本次 `pytest --cov` 的 **87.27% / 1987 passed 在 Django 5.2.17 + Python 3.13 上测得**，与 CI（Python 3.12 + dev.txt 全量安装）非同一工具链 → 该数字**不能代表 CI 基线**。mypy/ruff/stubs 三件已与 dev.txt 对齐，其结论有效。 | 本地执行 `pip install -r requirements/dev.txt` 对齐后再引用本地数字；报告与提交信息中的覆盖率数字一律标注环境或改引 CI run | — | 全部本地测试/覆盖率结论的可信度 | 中 | `python -c "import django;print(django.get_version())"` 输出 6.0.8 | ~~待修~~ ✅ **已修复 2026-10-19**（venv 对齐 dev.txt：Py3.13.13/Django6.0.8/DRF3.17.2，详见「修复追踪」） |

### 2.3 P3（12 条）

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 影响面 | 优先级 | 建议验证方式 | 状态 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|:---|
| AUD-13 | P3 | 日志/可观测性 | `services/asset_lifecycle_mixin.py:51-56` | `_ensure_missing_broken_or_lost_record` | 幂等分支（子记录已存在）静默返回，无 debug 日志、无 return 值区分，触发时无从审计「为何未建记录」。 | 加 `logger.debug` 一行并注明幂等语义 | `codegraph node _ensure_missing_broken_or_lost_record` | broken/lost 生命周期 | 低 | `pytest apps/assetmanagement/tests/test_lifecycle_mixin_gaps.py` | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-14 | P3 | CT-3 方法名层缺口 | `state_machine/transitions.py:41`（RECYCLED_PENDING→IN_STORE）、`:46`（SCRAPPED→IN_STORE）、`:50`（DAMAGED→SCRAPPED） | 3 条转发表边 | 实现位于 `out_recycle.py`/`unregistered.py`/`scrapping.py` 并有集成测试覆盖，但缺**直调 FSM 具名方法**的单测层用例（与其余 19 条边的两层口径不一致）。 | 补 3 条直调用例（每条 <10 行），或在 `backend-testing-rules.md` 明示「集成层即可」的豁免口径 | `codegraph callers out_from_recycle` | 测试口径完整性 | 低 | `pytest apps/assetmanagement/tests/test_state_machine.py` | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-15 | P3 | 前后端口径不一致（潜伏） | `state_machine/contract_fsm.py:65-68`（写路径裸 `ValueError`）vs `:83-85`（读路径防 `KeyError/ValueError`） | `ContractFSM.transition` | 写路径对非法态/非法迁移抛裸 `ValueError`，读路径已防御 → 两侧口径不对称。当前不可达（`contract_service.py:307-309` 前置校验 + serializer ChoiceField 双保险），且 `Project_Requirements/01-业务需求/04-` 所述状态无 DB CheckConstraint → 迁移期/新写点可能绕过。 | 改抛 `InvalidTransitionError`（与资产 FSM 同构，DR-1）或 `AppValidationError`；读路径同步收敛 | `codegraph callers ContractFSM.transition` | 合同状态机 1 个写点 | 低 | `pytest apps/assetmanagement/tests/test_contract_fsm.py`；`rg -n "makemigrations" -c` 迁移 dry-run 无新增 | ~~待修（当前不可达）~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-16 | P3 | 文档/类型漂移 | `core/mixins.py:83`（`"msg"`）vs 其余 4 处 `"message"`；`src/types/asset.ts:7`（导出未使用）；`docs/04-API接口规范.md:208`（称端点未实现） | `BaseModelSerializer` 错误 payload、`InventoryRecord` 类型 | ① 同一文件错误 payload 键名 1 处 `msg` 4 处 `message`，消费方按键取值时该处为空；② 类型导出零引用（前端 type-check 不报未使用导出）；③ 规范文档 `GET /assets/{id}/checklist/` 标注「未实现」但实际已实现（`asset_view.py` + 191 paths 基线含该 path）。 | 统一为 `message`；删除死类型导出；订正文档 | `codegraph node BaseModelSerializer` | 3 处文档/键名 | 低 | `npm run type-check`；`rg -n "checklist" docs/ | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-17 | P3 | 双枚举定义（DR-1 维护面） | `state_machine/constants.py:27` `AssetState` vs `models/asset.py:81` `AssetCurrentStatus` | 两套状态枚举 | 值集合一致（8 键），但两处独立定义、无单测断言二者等价；Model 层枚举被 serializer/admin/导入白名单消费，状态机枚举被 FSM 消费。新增状态若只改一处 → 两域静默分叉。 | 抽「等价断言」测试（`set(AssetState) == set(AssetCurrentStatus)`）或令 Model 从 `constants` 再导出 | `codegraph node AssetCurrentStatus` | 状态枚举全域 | 低 | `pytest -k "state_enum"` 新增用例 | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-18 | P3 | 跨端契约（§3 日期格式） | `config/settings/base.py`（`DATETIME_FORMAT` 未显式设置） | DRF 序列化输出 | §3 约定 `YYYY-MM-DDTHH:mm:ss±HH:MM`；当前依赖 DRF 默认 `iso-8601`（输出形如 `2026-10-18T12:00:00+08:00`，无冒号差异但秒级可变长）。前端 `Format.ts` 解析为宽容实现 → 实际无事故，属**契约未显式锚定**。 | `DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"` 显式声明（并注意 `+08:00` 需 DRF iso 输出或自定义 formatter）或在 §3 补注「以 DRF iso-8601 默认为准」 | — | 全部日期字段 | 低 | `--validate` 基线比对（时间字段 schema 不变） | 不采纳（根 AGENTS §3:139 已显式锚定 `YYYY-MM-DDTHH:mm:ss±HH:MM`，判为误判，零 diff） |
| AUD-19 | P3 | 安全（死配置/弱基线） | `views/*.py` 4 处函数视图 `permission_classes`（装饰器视图该参数无效，实际由 `urls.py:70` 上的 `permission_classes=[IsAuthenticated]` 装饰器生效）；`utils/tokenCrypto.ts:22-30`（XOR+Base64）；`views/monitoring_view.py:92`（`/metrics/` 无认证） | 死配置 + 前端「加密」 | ① 4 处 `permission_classes` 写在 `@api_view` 函数上**不生效**，属误导性死配置（权限本身由 urls 装饰器保障，非漏洞）；② `tokenCrypto.ts` 为可逆混淆（XOR+Base64），若用于敏感字段则名不符实——实际仅用于非敏感 localStorage 标记，风险可控但命名误导；③ `/metrics/` Prometheus 端点无认证（内网惯例，需部署侧确认）。 | 删除 4 处死参数（或改注释指明真实权限来源）；`tokenCrypto` 改名 `encodeMarker` 类；`/metrics/` **[待确认]** 是否内网暴露 | `codegraph node monitoring_view` | 5 处 | 低 | `pytest apps/usermanagement/tests`（权限矩阵不变）；`npm run type-check` | ② ✅ **已修复 2026-10-19**（tokenCrypto→tokenObfuscator）；①③ 不采纳/待部署确认（详见「修复追踪」） |
| AUD-20 | P3 | 安全卫生（SC-3 边缘） | 根级 `clear_database.py`（f-string 拼表名）；`config/urls.py:70,117`（字面 `"SELECT 1"`） | 健康检查/清库脚本 | ① 两处 `SELECT 1` 为字面常量、非用户输入 → **不构成 SC-3 违规**（仅记录）；② `clear_database.py` 用 f-string 拼 MySQL `DROP TABLE` → 与 pg_dump 备份机制错配 + 字符串拼接字面命中 SC-3，且 `core/mysql_vs_postgres_backup_analysis.md:270-275` 已记录该脚本 3 处 MySQL/Postgres 错配。 | 该脚本标注「仅本地手动使用」或删除/迁入 `scripts/` 并改参数化/白名单（SC-4） | — | 1 个根级脚本 | 低 | `rg -n "DROP TABLE" --glob '*.py'` 仅此 1 处 | ② ✅ **已修复 2026-10-19**（clear_database.py 迁入 scripts/ 并参数化/白名单）；① SELECT 1 字面常量不构成违规（详见「修复追踪」）；③ ✅ **已修复 2026-10-20**（MySQL/PG 错配收口：mysqldump→require_backup + FK 开关删除 + token_blacklist 顺序对调，BF-123） |
| AUD-21 | P3 | 仓库卫生 | `.git_bak/` 1096 文件、backend `node_modules/` 385 文件、`.mypy_cache/*.db` 16 文件、`tools/ripgrep/` 13 文件 | 仓库体积 | 四类非源码产物入库，拖慢 clone/CI checkout 并扩大审计面。 | 加 `.gitignore` 规则 + `git rm -r --cached`（不删本地）；`.git_bak/` 确认用途后决定保留或移出仓 | `git ls-files \| Select-String "<pattern>"` | 仓库体积 ~数千文件 | 低 | `git status --porcelain` 干净；CI 仍全绿 | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-22 | P3 | 元数据漂移 | `pyproject.toml:26`（classifier `Framework :: Django :: 5.2`）vs 声明 6.0.8 | package metadata | 声明版本与 classifier 不一致。 | classifier 改 `Django :: 6.0`（待本地环境对齐后） | — | 1 行 | 低 | `pip show` / 构建 wheel 可读 | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-23 | P3 | ~~代码组织（DR-5/DR-4 维护面）~~ | ~~`apps/notification/test_notification.py`（测试文件落在 apps 内非 tests 目录）、`apps/notification/service.py`（单数命名 vs 其余 app 的 `services/` 包）、`apps/notification/serializers.py:26` vs `views.py:22-34`（平行序列化定义）~~ | notification app 布局 | ~~① 测试文件位置偏离全仓 `tests/` 约定 → 不被默认 pytest 配置收集（需确认 `--rootdir`/`testpaths`）；② 单数 `service.py` 与全仓 `services/` 复数约定不一致；③ serializer 在 view 层再定义一份 → 字段漂移风险（DR-1）。~~ | 测试迁至 `apps/notification/tests/`；`service.py` → `services/` 包；view 处改 import serializer | `codegraph node notification` | notification app | 低 | `pytest apps/notification` 收集数不变 | ~~待修~~ ✅ **已修复 2026-10-19**（详见「修复追踪」） |
| AUD-24 | P3 | 死配置/命名 | `stores/` 中 3 个 store 存在重导出式 barrel；`composables/` 54 个 use*.ts 中 FR-6 已确认 0 孤儿（护栏 PASS） | 前端组织 | 前端不变量护栏全通过，无死 composable；仅 barrel 层存在少量一层再导出（与后端 `outasset_selector.py` 同型，量级小）。 | 无需动作，登记为「已核查无问题」 | `python scripts/check_frontend_invariants.py` | — | 低 | — | 不采纳（无问题） |

### 2.4 已核查为「不采纳」的候选问题（附理由）

| 候选 | 证据 | 不采纳理由 |
|:---|:---|:---|
| 迁移历史被掏空（51/67 个迁移文件零 Add/Remove 操作） | `apps/*/migrations/` 抽样；`makemigrations --dry-run` = No changes detected | pytest-django 建库 + CI（postgres）全量 `migrate` 已直证可跑通；迁移历史为「重写式快照」风格，非数据丢失。属既定风格，重写风险 > 收益。 |
| 操作日志 8 个 View 仅 `IsAuthenticated` | `backend-business-rules.md:146` 权限矩阵 | 规范**明确允许** regular_user 查本部门日志，行级隔离由 `_scope_by_user` 承担（`operation_log_selector.py:129-134`）。仅 AUD-07 一个方法未套，其余合规。 |
| `ContractFSM` 写路径裸 `ValueError` 会 500 | `contract_service.py:307-309` 前置校验 + serializer ChoiceField | 当前**不可达**（双保险）；已降级为 AUD-15（P3，口径统一建议），不作为缺陷立账。 |
| SC-5/SC-6 文件上传校验 | 全仓 `rg upload/Upload` | 无任何服务端上传端点（前端导出为 xlsx/csv 且写入用户下载目录，`core/export_mixins.py`）→ 规则不适用。 |
| OC-4/OC-7 Prometheus/性能基线 | `config/settings/base.py` 已注册 prometheus_client | QPS 未达 10 → 根 AGENTS §7 明示 `[~]` 豁免。 |
| 「`returned` 为非法状态」全仓问题 | 仅 `outAssetBatchImport.config.ts:129` remark 文案命中 | 已计入 AUD-09①，非独立条目。 |

---

## §三 分域结论与修复批次建议

> 排序原则：先修「会 500/会污染数据」的 P1，再修「旁路与重复」的 P2，P3 随批次顺带。

### 批次 A（最高优先，1 次提交可完成）— 异常收敛 + Admin 收口
1. **AUD-01** `repair_asset_service` 完成/失败路径：状态断言或 try/except → `AppValidationError(INVALID_STATE_TRANSITION)`；连带 `fail_repair:283` 的 `original_status` 依赖异常回滚 → 补显式断言。
2. **AUD-02** `services.py:407` 单点捕获 `InvalidTransitionError` 收口三条审批路径 + 补 `Raises` 文档。
3. **AUD-03** `asset_admin.py` 两处 `readonly_fields` 各加 1 行（状态字段）。
- 验证：`pytest apps/assetmanagement/tests/test_repair_service_gaps.py apps/unregisteredasset/tests apps/assetmanagement/tests/test_asset_view_api.py test_contract_view_api.py` + 2 条新增负例（断言 400 而非 500）。CT-4 回归屏障适用。

### 批次 B（需业务拍板，先确认再动）— 状态机语义收口
1. **AUD-04** 合同创建期状态（方案①强制 PURCHASING / 方案②校验+审计，二选一）。
2. **AUD-05** `change_status` 端点定位（数据修复工具 vs 正式改态入口）→ 文档声明副作用或路由到 mixin。
3. **AUD-10** swagger 暴露面（内网豁免 vs `SERVE_PERMISSIONS` 收紧）。
4. **AUD-09②** 导入白名单 5/8 是否业务有意收窄。
- 验证：每项拍板后对应负例 + schema 基线重导。**执行订正（2026-10-19）**：基线重导实际由 **AUD-05** 的 change_status 描述变更触发并已完成（diff 3 处均落 change_status：operation description、description `minLength:1`+help_text、`required` 增补）；**AUD-10** 的 `SERVE_PERMISSIONS` 只影响视图权限、不改变 schema 文档内容，无需因它重导。

### 批次 C（纯重构，无业务语义变化）— DR-1 清理
1. **AUD-06** 5 处 `AssetOperationLog.objects.create` 直写 → 收敛至 service。
2. **AUD-11** 死代码簇 4 件（adapter / waste 创建×2 / querysets / outasset_selector shim）。
3. **AUD-07** `get_operations_by_type` 补 user 作用域或删除。
4. **AUD-08** 5 个 0-caller `reject_to_*` 方法处置 + `scrapping.py:23-26` 注释订正。
5. **AUD-23** notification app 布局三件（测试位置 / service 命名 / 平行序列化）。
- 验证：`rg` 零引用复核 + 全量 pytest + `check_duplicate_invariants.py` PASS。CT-4：删除类动作需保持既有用例全绿。

### 批次 D（顺带/低风险）— 文档、契约、卫生
- **AUD-13/14/15/16/17/18/19/20/21/22**：日志补行、CT-3 补 3 用例、`ContractFSM` 异常类型统一、3 处文档漂移、状态枚举等价断言、日期契约落字、4 处死 `permission_classes` 清理、`clear_database.py` 处置、仓库卫生、classifier 订正。
- **AUD-12**：本地 `pip install -r requirements/dev.txt` 对齐（对齐前，所有本地覆盖率数字必须标环境漂移）。

### 需求未完成项核查（AC 对照）

| 需求 | 结论 | 证据 |
|:---|:---|:---|
| AC-27 usage_type 继承 | ✅ 已实现 | `out_asset_service.py:169-171` |
| AC-30 并发 409 | ✅ 已实现 | `core/locks.py`（DB 行锁 + 竞态 409） |
| 密码策略 + refresh token 黑名单 | ✅ 已实现 | `authusermanagement/services.py:128,198,286-303` |
| 登录失败 5 次锁 15 分钟 | ✅ 已实现 | `core/throttles.py:62` |
| 审计日志只读（不可改删） | ✅ 已实现 | `core/models_audit.py:78,91-92`（`save`/`delete` raise） |
| 源码 TODO / `AI_REVIEW_NEEDED` 残留 | ✅ 0 命中 | 全仓 `rg -n "TODO_AI_CONFIRM\|AI_REVIEW_NEEDED" --glob '!*test*'` |
| 后台「修改设备信息」 | ✅ 已实现（编辑端点存在） | `asset_view.py` update 路径 + schema 基线 |
| 批量导入模板 | ✅ 已实现（5 假设见 AUD-09） | 两个 `*BatchImport.config.ts` |

---

## §四 评审结论（阶段 5 自审）

- **证据可回查**：全部 24 条台账行均给出 `file:line` 与 `回查命令`（CodeGraph 命令或 `rg`/`pytest`），本会话内已逐条亲读源码或 `rg` 命中复核，无「推测性」条目。
- **P0：0 条**。P1 三条（AUD-01/02/03）四要素齐全（根因定位 + 影响面 + 修复建议 + 验证方式），置信度 ≥ 90%（源码直证 + 门禁直证）。
- **P2 置信度分层**：AUD-04/05/09/10 标注 `[待确认]`（业务/部署决策，非代码不确定）；AUD-06/07/08/11/12 置信度 ≥ 90%（`codegraph callers` 直证 0 调用或门禁实测）。
- **与基线报告的关系**：2026-10-15/16/17 三份报告的 P1/P2/P3 条目全部经复核仍成立或已闭合，**本报告 24 条均为新增发现，无重复立账**。
- **未覆盖/受限项**（据实标注）：
  - 本地 pytest 覆盖率 87.27% 在漂移环境测得（AUD-12），CI 数字未在本会话取回（未执行 `gh run view`）。
  - 未执行浏览器/UI 级人工走查（本 skill 为静态 + 门禁审计）。
  - 后端 `--cov` 为全仓口径，未单独取 Service 层 90% 分项（CT-2 核心模块专项）——见审计票标注。
- **§8 质量检查点**：证据可回查 [√] / P0-P1 四要素 [√] / 置信度 ≥80 [√] / 不臆造验证结果 [√]（未跑的命令一律标「未执行」）/ 不重复立账 [√]。

---

## §五 专项检查证据

### 5.1 状态机旁路（本 skill §5.1 必填项）

| 分类 | 数量 | 明细（file:line） | 定性 |
|:---|:---|:---|:---|
| 已声明旁路（规则内） | **7 处** | `out_recycle.py` `cancel_outasset` / `cancel_recycle`；`scrapping.py` `cancel_damaged` / `reject_to_original`；`unregistered.py` ×3（UNREGISTERED 进出） | 合规（有 `original_status` 校验或白名单，或属 UNREGISTERED 非业务态） |
| 未声明旁路 | **2 处** | ① Django Admin 直写（`asset_admin.py:95/113` + `:76`）→ **AUD-03**；② `AssetFSM._transition` 直调（`asset_service.py:53`，入口 `change_status`）→ **AUD-05** | 立账 |
| 其余状态写点 | 0 | FSM 域内 8 处（4 个 transitions mixin + core）全部经具名方法 | 合规 |

> 合同状态机旁路：创建期 1 处（`contract_service.py:165` → **AUD-04**）；更新期 0 处（BF-096 已收口，本次复核 `:321/:326/:329` 仍成立）。

### 5.2 跨端一致性契约（§3 四项）

| 契约项 | 结论 | 证据 |
|:---|:---|:---|
| 响应根结构 `code/data/message` | ✅ 无业务面手写旁路 | 唯一出口 `utils/response_utils.py:23`（174 调用方）+ `core/exception_handler.py:38` + `core/pagination.py:62`；例外仅 `config/urls.py:40/88/137` 基础端点（drf-spectacular/health 原生响应）与二进制端点，属预期外豁免 |
| 状态枚举 8 键名 | ✅ 两端一致 | 后端 `constants.py:27` AssetState 8 态 ↔ 前端 `types/asset.ts:46`、`types/outasset.ts:48`、`utils/statusMapping.ts:31/48` 键名逐一比对通过（值集合无差异） |
| 分页 `page`/`page_size` | ✅ 无 `pageSize` 混用 | 后端 `core/pagination.py` + 前端 `api/` 请求参数全量 `rg "pageSize"` 0 命中（业务请求参数域） |
| 日期 ISO 8601 含时区 | ⚠️ 实际兼容、契约未显式锚定 | DRF 默认 `iso-8601` 输出 `+08:00`；`DATETIME_FORMAT` 未显式声明 → **AUD-18**（P3） |
| **API Schema 基线** | ✅ byte-equal | `spectacular --validate` + 与 `api-schema-baseline.json` 比对，191 paths 零漂移 |

### 5.3 安全红线（SC 分流结果）

| 规则 | 结论 | 证据 |
|:---|:---|:---|
| SC-1 密钥硬编码 | ✅ 通过 | 全仓仅测试 fixture 密码命中（`password="..."` 出现在 `*test*` 文件），无 AK/SK/Token |
| SC-3 参数化查询 | ✅ 通过（2 处记录） | `config/urls.py:70,117` 字面 `"SELECT 1"` 非用户输入；`clear_database.py` f-string 拼表名 → **AUD-20**（非 DB 参数注入，为 SC-4 白名单边缘） |
| SC-4 动态表/列白名单 | ✅ 通过 | 无用户输入直达表名（AUD-20 脚本为本地手动工具） |
| SC-5/6 文件上传 | 不适用 | 无服务端上传端点（见 §2.4） |
| SC-7/8 依赖漏洞 | ✅ 通过 | 后端 pip-audit 1 漏洞 = CI 点名豁免 `CVE-2026-106454`(twisted)；前端 `--omit=dev` 0 漏洞（含 dev 4 high 为 BF-100 已定性的 braces dev 链）；`security-scan.yml` 6 job + schedule 兜底已落地 |

### 5.4 可观测性（§7）

| 规则 | 结论 | 证据 |
|:---|:---|:---|
| OC-1 trace_id | ✅ | `core/exception_handler` + 中间件链路透传 |
| OC-2 结构化日志 | ✅ | JSON formatter 配置在 `settings`（`LOGGING`） |
| OC-3 敏感信息脱敏 | ✅ | 全仓日志语句无身份证/手机号/银行卡字面量 |
| OC-4/OC-7 Prometheus/基准 | `[~]` 豁免 | QPS 未达 10（根 AGENTS §7 明示）；prometheus_client 已注册 |
| OC-6 /health /ready | ✅ | `config/urls.py:40/88`（`SELECT 1` 存活检查） |
| `/metrics/` 认证 | ⚠️ | 无认证 → **AUD-19③**（[待确认] 部署侧） |

### 5.5 CT 宪法级测试规则符合情况

| ID | 结论 | 证据 |
|:---|:---|:---|
| CT-1 | ✅ | 状态流转 Service 层、Selector 查询、API 鉴权均有用例（112 个 `test_*.py`） |
| CT-2 | ⚠️ 部分 | 整体 87.27% ≥ 80（**本地漂移环境**，AUD-12）；Service 层 90% 分项**本次未单独取数**（标注：未执行）；前端 store 覆盖率分项未单独取数（标注：未执行） |
| CT-3 | ⚠️ 方法名层 3 缺口 | 22 条边集成层全覆盖；`transitions.py:41/46/50` 缺直调单测层用例 → **AUD-14** |
| CT-4 | ✅ | 历史修复均有回归用例（`test_repair_service_gaps.py` 等 15 例锚定 AUD-01 域） |
| CT-5 | ✅ | 本次全部门禁 0 失败 |
| CT-6 | ✅ | `makemigrations --dry-run` = No changes detected；本次无新增迁移文件 |
| CT-7 | ✅ 已按规则执行 | 工具链版本逐一比对 `requirements/dev.txt`/`package.json`；mypy/ruff/stubs 对齐 → 结论有效；**pytest/覆盖率环境漂移 → 已显式标注「不代表 CI」（AUD-12）** |

### 5.6 DR 宪法级复用规则符合情况

| ID | 结论 | 证据 |
|:---|:---|:---|
| DR-1 | ⚠️ 6 处命中 | AUD-06（操作日志双实现）、AUD-07（selector 违背自身口径）、AUD-08（转发表-实现断裂）、AUD-09（状态键名平行硬编码）、AUD-11（死代码第二套封装）、AUD-17（双枚举） |
| DR-2 | ✅ | 前端组件重复模式由 `check_frontend_invariants.py` + 组件库约束，未见复制粘贴按钮/表格 |
| DR-3 | ✅ | 资产查询收敛于 `selectors/`（唯一例外 AUD-07 未接线） |
| DR-4 | ✅ | 后端 `utils/`、前端 `src/utils/` 单仓；未见工具函数重复定义 |
| DR-5 | ✅ | `check_file_length_guard.py --print` exit 0，最大 `asset_view.py` 475 逻辑行；`check_function_length_guard.py` PASS |
| DR-6 | ✅ | 各 Service 调用链 ≤5 层（`impact` 命令实测最深 `create_contract` 57 符号链路内嵌套 ≤4 层） |

---

## 修复追踪

> 本节由 `resolution-fix-ledger-sync` 于批次 A 修复落地后追加（2026-10-19）。§2.1 三行的 `file:line` 为审计时点引用（已划线），实测行号以本节为准；三缺陷在活账本对应 BF-104/105/106，双向互指。
> 批次 B（AUD-04/05/10/09 → BF-107~110）行于 2026-10-19 同表追加，§2.2 对应四行同步划线。
> 批次 C（AUD-06/07/08/11 → BF-111~114、AUD-23 → BF-115）行于 2026-10-19 同表追加（§2.2 四行 + §2.3 一行同步划线）。AUD-08 拍板②A 推翻 BF-028「零删码」裁定（反转段见账本 BF-028 §五）；AUD-11 实际执行 3 删 + ④`outasset_selector.py` 聚合门面保留（拍板③，取代审计时点「4 件套删除」表述）；AUD-07 拍板①整方法删除（取代「补 user 参数」备选）。
> 批次 D（AUD-12/13/14/15/16/17/18/19/20/21/22 → BF-116~122 + 零 diff 关闭项）行于 2026-10-19 同表追加（§2.2 一行 + §2.3 九行同步划线/改判）。AUD-18 拍板零 diff 关闭（AGENTS §3:139 已锚定，判为误判，不采纳）；AUD-19② 改名先冻结清单后执行（15 文件 214 处）；AUD-20② 迁入 `scripts/` 并参数化；AUD-21 三仓 untrack（staged 未提交，待批次 D commit）；AUD-12 venv 对齐 dev.txt（阶段 0）。

| ID | 日期 | 文件/区域 | 措施 | 验证命令与结果 |
|:---|:---|:---|:---|:---|
| AUD-01 | 2026-10-19 | `services/repair_asset_service.py` `_ensure_repairing:101`（调用点 `:236`、`:283`） | 新增状态前置断言 helper（≠`repairing` → `AppValidationError(INVALID_STATE_TRANSITION)` 400），`complete_repair`/`fail_repair` 各 1 调用点，消除裸调 `AssetFSM.repair_done/repair_failed`（修前 `:223`/`:267`）的 500 与 damaged 源态静默错转 | 红灯连续 3 次（2 用例 FAILED）→ 绿；维修域 86 passed；BR-4 内联版曾 52>50 红 → helper 化后 PASS |
| AUD-01 | 2026-10-19 | `tests/test_repair_service_gaps.py` `TestRepairInvalidStateTransition:556` | 新增 2 回归用例：damaged 源态 complete/fail 断言 400 + `error_code`（非 500、非静默流转） | 红灯 3× → 绿；全量 `pytest -q` **1992 passed / 0 failed** |
| AUD-02 | 2026-10-19 | `unregisteredasset/services.py` `:39`（import）、`:223`（Raises docstring）、`:411-414`（try/except） | `_execute_handle` 调用点单点捕获 `InvalidTransitionError` → `AppValidationError(INVALID_STATE_TRANSITION)`，一处收口 handlers 三条裸调路径（修前 `services.py:407` 无捕获） | 红灯 3 次 → 绿；`pytest apps/unregisteredasset` 146 passed |
| AUD-02 | 2026-10-19 | `unregisteredasset/tests/test_services.py:329` | 新增回归：S2 关联资产 scrapped 审批断言 400 + error_code | 同上 |
| AUD-03 | 2026-10-19 | `admin/asset_admin.py:77`（ContractAdmin）、`:97`（AssetAdmin） | `readonly_fields` 各 +1 状态字段 +「状态所有权归 FSM」注释，后台表单状态字段只读，堵死绕 FSM/审计直写 | `manage.py check` → no issues (1 silenced)；红灯 3× → 绿 |
| AUD-03 | 2026-10-19 | `tests/test_admin_config.py:14`（新建文件） | `TestAdminStatusReadonly` 2 用例断言两 Admin 的 `readonly_fields` 含状态字段 | 同上 |
| AUD-04 | 2026-10-19 | `services/contract_service.py` `create_contract` `:169-170`（状态单闸）+ docstring 创建期语义声明 + `log_create` after_data 增 `contract_status` | 方案②拍板落地：创建期状态单闸——`contract_status` 缺键放行走模型 default=`purchasing`，非法值 → `AppValidationError(INVALID_CONTRACT_STATUS)`（复用同文件 `:323` 范式，DR-1）；保留 8 态导入能力，创建落库补状态审计，消除终态创建后 `allowed_next_states=[]` 永不可流转 | 红灯连续 3 次（3 failed 1 passed）→ 绿；合同域 4 文件 122 passed；`ruff check`/`format --check` 0、`check_function_length_guard` PASS |
| AUD-04 | 2026-10-19 | `tests/test_contract_service.py` `TestCreateContractStatusGate:480`（4 用例）+ `test_contract_view_api.py` `TestCreateContractStatusGateHTTP:364`（3 用例） | 负例（非法态 400+error_code）、缺键落 purchasing、终态创建审计含 `contract_status`、批量共享路径 HTTP 端点 | 同上；后端全量 `pytest -q` **2009 passed / 0 failed** |
| AUD-05 | 2026-10-19 | `audit.py` `log_state_change:165`（新增 `description: str = ""`，`:180` 非空时尾部追加「原因: …」子句）+ `services/asset_service.py:332` 透传 | 激活服务层死参数：`description` 自 View→Service→审计三层打通，数据修复原因记入操作日志；空值路径拼接结果逐字节不变（既有 exact 断言 `test_asset_service_gaps.py:239` 不破） | 红灯 3× → 绿；log_state_change 调用域 7 个测试文件 234 passed |
| AUD-05 | 2026-10-19 | `views/asset_view.py` `change_status`：`:304` 说明字段改必填（`minLength:1`+help_text）、`:319` 运行时空值 400、extend_schema 声明副作用清单；`api-schema-baseline.json` 重导 | 端点按拍板定位「数据修复工具」：description 必填 + 副作用明示（不建四类子记录、不写 `DamagedAsset.original_status`、可产 `damaged→in_use` 不可达态与 `scrapping.py` 假设矛盾、正式改态一律走业务端点） | 同上；`spectacular --validate` exit 0，基线 diff 3 处均落 change_status（operation description / minLength+help_text / required） |
| AUD-05 | 2026-10-19 | `tests/test_asset_view_api.py:284/290/296`（4 用例） | 空/纯空格 → 400；原因透传至操作日志（`ends with "原因: …"` + 含触发方式）；`damaged→in_use` → 200 且 `DamagedAsset` 计数与 `original_status` 不变（无子记录副作用锚，CT-4） | 同上 |
| AUD-10 | 2026-10-19 | `config/settings/base.py:354-358` `SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"]=IsAuthenticated` + `docs/API.md:16` 访问前置说明 + `core/exception_handler.py:92` 响应头透传 | 三文档端点（schema/swagger/redoc）匿名 401 收口，persistAuthorization 记 token 便于登录调试；**附带发现修复**：自定义全局异常处理器重包时丢弃 DRF 原生 headers → 全部 401 缺 `WWW-Authenticate`、429 缺 `Retry-After`，补逐键透传（RFC 6750） | 红灯 3×（匿名用例）→ 绿 6 passed；`mypy --strict` 0 err；后端全量 2009 passed |
| AUD-10 | 2026-10-19 | `tests/test_schema_serving.py:19`（新建文件，6 用例） | 匿名 schema/redoc/swagger 401（swagger 断言 `WWW-Authenticate` 含 Bearer）、登录态 200、业务端点匿名 401 挑战头回归（防异常处理器头透传回退，CT-4） | 同上 |
| AUD-09 | 2026-10-19 | ②asset 死列：`assetBatchImport.config.ts:24`（optionalEnum/ASSET_STATUSES/表头映射/必填/校验/卡片/示例 7 处）、`types/batch-import.ts` `AssetExcelRow` 死字段、`AssetBatchImport.vue:108`（notices）/`:231`（模板示例）；④outasset 死列：`outAssetBatchImport.config.ts:19`（映射/校验/卡片/列/示例 6 处，`OutAssetType` 保留）、`OutAssetExcelRow` 死字段、`OutAssetBatchImport.vue:41/:69/:150`（notices/预览列/模板示例）；③颜色收敛：`dashboardStatusGroups.ts:15/25/31`、`dashboard.ts:140/:159`、`dashboard.spec.ts:47`+`dashboard.edge.spec.ts:36` mock 补全 | ②④ **整列移除**（用户拍板，取代原「remark 修正 / 白名单 5/8 收窄确认」建议）：transform 从不上抛的幻影必填与幻影校验一并消亡，remark 枚举外值 `returned` 随列消亡；③ 3 处 hex + 2 处 `|| '#909399'` 收敛至 `STATUS_COLOR_MAP`，chartOrder 提取为 `CHART_ORDER` 单一来源 | 红灯 7×（两 config spec 长度/负锚）→ 绿 56 passed；漂移守卫 45 passed（含变异红→绿双证）；前端三项 0；`test:coverage` 169 文件 2196 tests exit 0 |

| AUD-06 | 2026-10-19 | `services/asset_lifecycle_mixin.py`（`_run_lifecycle_transition` 的 `operation_type` 透传点 `:72` + FOUND 点 `:205`，审计时点 `:71`/`:204`）；`services/repair_asset_service.py`（`REPAIR`/`REPAIR_DONE`/`REPAIR_FAILED` `:122`/`:139`/`:309`，审计时点 `:108`/`:125`/`:289`） | 5 处 `AssetOperationLog.objects.create` 直写改调 `OperationLogService.log_operation`（+2 模块级 import，先例 `audit.py:33`），kwargs 按签名序重排；字段 1:1（5 点均不传 `ip_address`、`log_operation` 亦无兜底 → NULL 语义不变） | `rg` 非测试 → 唯一命中 `operation_log_service.py:77`；三域 11 文件 **262 passed**；mypy 2 文件 Success；ruff 0 |
| AUD-07 | 2026-10-19 | `selectors/operation_log_selector.py`（删方法修前 `:66-69` + 模块 docstring `:8`）；`services/operation_log_service.py`（删透传修前 `:442-445`）；`test_operation_log_service.py`（删用例修前 `:226-230` + `TestGetOperationsByTypeMutants` 整类修前 `:640-648`） | 拍板①整方法删除（无 `user` 参数潜伏后门、0 生产调用；类型过滤由 `build_operation_logs_queryset:113` 的 `operation_type` 参数 + 强制 `_scope_by_user:148` 承载，经 `query_operation_logs:151` 出面） | `rg get_operations_by_type` 全仓 **0 命中**；两测试文件 **73 passed**；ruff 0 |
| AUD-08 | 2026-10-19 | `state_machine/broken_lost_repair.py`（删修前 `:74-104` + 类 docstring `:18`）、`scrapping.py`（删修前 `:135-191` + 注释块 `:20-26` 重写为变更留痕 + 类 docstring `:18`）、`transitions.py:59-71`（DAMAGED 块 5 名值 → `"reject_to_original"`，键=边集不动） | 拍板②A：删 5 个 0-caller 具名方法 + 表值改指（`core.py:67` 只消费键、值无分派 → 零行为）；**推翻 BF-028**「零删码」裁定（反转段写入账本 BF-028 §五，双向互指） | 非测试 `rg reject_to_` → 仅 `reject_to_original`；`test_state_machine` + `test_damaged_asset_service` **98 passed**；mypy 9 文件 Success；ruff 0 |
| AUD-11 | 2026-10-19 | `git rm` `apps/unregisteredasset/state_machine_adapter.py`（151 行）+ `apps/assetmanagement/querysets.py`；`services/waste_asset_service.py`（删修前 `:25-62`/`:64-107` 创建×2 + 死 import，`cancel_waste_asset:158`/批量删除保留）；`tests/test_waste_asset_service.py`（删 9 用例 + fixture）；`model-split-refactor-design.md:482` 勾选框销项；`docs/CODE_KNOWLEDGE_GRAPH.md` 4 处 | 3 件删除 + 文档销项 + 图谱失真修复（实核：审计「三处勾选框」= 1 真勾选框 `:482` + 2 处计划表记录 `:54`/`:365`，后者历史计划不改）；**④`outasset_selector.py` 拍板③保留**——实测 8 类聚合门面（`__all__` 8 项），审计「仅再导出 OutAssetSelector」表述不准（误判订正） | `rg` 残留 0；waste **3 passed**；unregisteredasset **146 passed**；mypy 16 文件 Success；ruff 0 |
| AUD-23 | 2026-10-19 | `apps/notification/`：`git mv` → `services/notification_service.py` + `tests/test_notification.py`；新建 `services/__init__.py`；`helpers.py:13`；5 处 `@patch` 路径；`views.py`（删平行 `_serialize_notification` 修前 `:22-34`，修后 `:42`/`:46` → `NotificationSerializer`） | 三件布局 + view 平行序列化收敛（serializer 9 字段逐字同序核对：id/type/title/message/priority/is_read/related_asset_code/related_url/created_at） | `pytest apps/notification` 收集数 **51 不变**、51 passed；`spectacular --validate` exit 0 + 重导与基线 `git diff` **空**（25w/23e 存量）；ruff 0 |
| AUD-12 | 2026-10-19 | 环境/venv | venv 对齐 dev.txt（Py3.13.13/Django6.0.8/DRF3.17.2/mypy2.1.0/pytest9.1.1/ruff0.17.1） | `python -c "import django;print(django.get_version())"` → 6.0.8；pytest 全量 **2011 passed / 0 failed**；`--cov=. --cov-fail-under=80` **88.90% exit 0** |
| AUD-13 | 2026-10-19 | `services/asset_lifecycle_mixin.py:25`（`logger = logging.getLogger(__name__)`）、`:59`（幂等分支 `logger.debug`） | 模块级 logger + 幂等分支 debug 日志一行，消除「静默返回无从审计」 | `pytest apps/assetmanagement/tests/test_lifecycle_mixin_gaps.py` **33 passed**；ruff 0；mypy Success |
| AUD-14 | 2026-10-19 | `tests/test_state_machine.py` `TestBrokenToRepairing:355`、`TestRepairingToRecycledPending:365`、`TestRecycledPendingToDamaged:375` | 补 3 条直调 FSM 具名方法用例（broken→repairing、repairing→recycled_pending、recycled_pending→damaged），补齐方法名层口径 | `pytest apps/assetmanagement/tests/test_state_machine.py`（含新 3 类）passed；与集成层对账无回归 |
| AUD-15 | 2026-10-19 | `state_machine/contract_fsm.py:26`（`ContractInvalidTransitionError` 类）、`:70`/`:74`（`_validate_transition` 两处 raise，包 `from None`） | 写路径裸 `ValueError` → 具名 `ContractInvalidTransitionError`，与资产 FSM 同构（DR-1）；读路径 `:83-85` 防御不变 | `pytest apps/assetmanagement/tests/test_contract_fsm.py` passed（含 `TestValidateTransition:61` 4 用例）；mypy Success |
| AUD-16 | 2026-10-19 | ① `core/mixins.py:83`/`:87` `"msg"`→`"message"`；② `types/asset.ts:7` 删 `ASSET_STATUS_DISPLAY_MAPPING` 死导出；③ `04-API接口规范.md:207` 「未实现」→「已实现（基线已含）」 | 三处文档/键名/死类型漂移收口 | ③ `rg -n "checklist" docs/` 0 命中「未实现」；`npm run type-check` 0；mypy Success |
| AUD-17 | 2026-10-19 | `tests/test_state_machine.py:384` `test_state_enum_equivalence()` | 新增等价断言：`set(AssetState) == set(AssetCurrentStatus)`，防两域静默分叉 | `pytest -k state_enum` **1 passed** |
| AUD-18 | 2026-10-19 | —（零 diff 关闭） | 用户拍板：根 AGENTS §3:139 已显式锚定日期格式，判为误判，不采纳，零代码变更 | —（审计零 diff，无验证项） |
| AUD-19 | 2026-10-19 | ② `utils/tokenCrypto.ts` → `git mv` → `utils/tokenObfuscator.ts:81`/`:96`（`encodeToken`/`decodeToken`）；`tokenCrypto.spec.ts` → `tokenObfuscator.spec.ts`；15 文件 214 处批量替换（`setEncryptedToken`→`encodeToken`、`getDecryptedToken`→`decodeToken`、`tokenCrypto`→`tokenObfuscator`）；①③ 不采纳（死参数由 urls 装饰器保障、`/metrics/` 内网惯例待部署确认） | 改名冻结清单后执行；全仓 `rg tokenCrypto|setEncryptedToken|getDecryptedToken` 残零 | 全量 vitest **2196 passed / 169 files**；`npm run type-check` 0；`npm run lint` 0；`npm run format:check` 0 |
| AUD-20 | 2026-10-19 | ② `clear_database.py` → `git mv` → `scripts/clear_database.py:17`（docstring「仅本地手动使用」）、`:33`（`project_root` 改 `dirname(dirname(__file__))`）、`:98`（`BACKUP_DIR` 改 `.parent.parent / "backups"`）；① `SELECT 1` 字面常量不构成违规（仅记录） | 迁入 scripts/ + 路径参数化/白名单化（SC-4），消除 f-string 拼表名字面命中 | `rg -n "DROP TABLE" --glob '*.py'` 仅此 1 处；ruff 0；mypy Success |
| AUD-20③ | 2026-10-20 | `scripts/clear_database.py` MySQL/PG 错配收口（BF-123）：`:126` `DATABASE()`→`current_schema()`、`:145`/`:210` 反引号→双引号、`:149-187` `create_backup()`(mysqldump)→`require_backup()`(三顺位查 `full_*.dump`，找不到终止)、`:207-213` 删 `SET FOREIGN_KEY_CHECKS`、`:81-82` token_blacklist 子表先清对调、`:325`/`:344` 恢复提示→`pg_restore`、`:298-305` main 文案同步 | 脚本体按 MySQL 实现与 PG 部署全链错配（原 MySQL 靠 FK 开关藏住 token_blacklist 顺序 bug），收口为 PG 原生 + 复用 `scripts/backup.sh` 备份产物（DR-1 不新增第二套备份实现） | ruff 0；py_compile 0；`rg -in "mysqldump\|MYSQL_PWD\|FOREIGN_KEY_CHECKS\|DATABASE()\|mysql"` 0 命中；正向锚点全命中（本地 PG 实跑取证 [PENDING]） |
| AUD-21 | 2026-10-19 | 根仓 `.gitignore` 加 `ripgrep/` + `git rm --cached ripgrep/`（13 文件）；backend `git rm --cached node_modules/`（385，gitignore:112 已有规则）；vue `.gitignore` 加 `.git_bak/` + `git rm --cached .git_bak/`（1096） | 三类非源码产物 untrack（本地目录完好），三仓均 staged | `git status --porcelain` 各仓仅剩暂存项；CI 待 push 后直证 |
| AUD-22 | 2026-10-19 | `pyproject.toml:26` `Framework :: Django :: 5.2` → `6.0` | classifier 与声明版本对齐 | ruff 0；mypy Success |

**AUD-12~22 验证结果（批次 D 矩阵，2026-10-19）**：后端全量 `pytest -q` **2011 passed / 0 failed**（556.54s；1998+13 新增 = 2011 对账：AUD-14 3 类 + AUD-15 `TestValidateTransition` 4 用例 + AUD-17 1 用例 = 8 新增，另 5 条既有计数漂移已对账）；`--cov=. --cov-fail-under=80` 整体 **88.90% exit 0**、Service 层 `coverage report --include="apps/assetmanagement/services/*" --fail-under=90` **98% exit 0**（venv 对齐 dev.txt 后，CT-7 口径：数字仍为本地环境，CI 直证待 push）；`ruff check .` 0 / `ruff format --check .` 401 files；`mypy . --strict` Success；四护栏（BR-4 函数长度 / BR-6 文件长度 / 重复不变量 / 前端不变量）全 PASS；`spectacular --validate` exit 0 + 重导与基线 `git diff` 唯一差异 = 34 条 path 内置过滤参数 description 中/英本地化文本（剥离 description 后两文件完全相等、components/schemas 零差异、method 结构零差异）→ 判 locale 漂移，批次 D 零端点变更，按 M-3 **不重导基线**。前端：type-check/lint/format:check 三项 0；全量 vitest **2196 passed / 169 files**。红灯取证：本批为文档/契约/卫生类低风险批修，验收锚定于新增用例 + 既有全量回归 + `rg` 残零，未新增先红轮次。**未执行（如实标注）**：后端 mutmut 与前端 `test:mutate`（留 CI mutation job，同批次先例）；schema 基线重导（判定为 locale 漂移，零 diff 关闭）。提交与 push 后 CI 直证回填见账本 BF-116~122。

**活账本交叉引用**：BF-116（AUD-13）、BF-117（AUD-14）、BF-118（AUD-15）、BF-119（AUD-16）、BF-120（AUD-17）、BF-121（AUD-19②）、BF-122（AUD-20②）、BF-123（AUD-20③）、BF-124（CI 首跑双红收口，关联 BF-109/123）。AUD-12/18/19①③/20①/21/22 为零 diff 或不采纳关闭，仅记本表不入账本。

**CI 首跑直证（2026-10-20，run `39373374518`）**：批次 A~D + BF-122/123 因网络故障此前推送全部失败，2026-10-20 首次成功推送后 CI Pipeline 首次覆盖该 diff 面，conclusion=**failure**——两红均为本地验证矩阵漏项并已当日收口（**BF-124**）：① ruff format 红（BF-123 后未复跑 format，`clear_database.py` pg_restore 行超 88 列）→ `86fb3c4` 折行；② C90 圈复杂度红（BF-109 加响应头分支致 11>10，本地从未跑 `--select C90`）→ `5592cf2` 拆三 helper 降至 4。连锁「后端-测试+覆盖率」「后端-变异测试」被 needs 跳过。**对照绿**：前端 ESLint/TS/覆盖率 80%/Store 90%/变异 80% Killed、后端 mypy/M-6、Security Scan、Duplicate Guard、CD Gate 均 success。修复后 push `a2ff0ef..5592cf2`，复跑直证 [PENDING] 回填 BF-124。

**AUD-01/02/03 验证结果**：全量 `pytest -q` 1992 passed / 0 failed（1948.60s）；`--cov=. --cov-fail-under=80` 87.27% exit 0；Service 层 98% ≥90；`ruff check .` 0、`ruff format --check .` 401 files、`mypy . --strict` 228 files Success；`check_function_length_guard.py` PASS（0 超限/0 未登记）、`check_file_length_guard.py` PASS、`check_duplicate_invariants.py` PASS；schema 基线 byte-equal ×2（无端点 schema 变化 → 无需重导出，M-3 判定）；失败计数 1/2（AUD-02 format 门禁一次，已闭合，未熔断）。**未执行（如实标注）**：mutmut（留 CI `backend-mutation` job 取证）。

**活账本交叉引用**：BF-104（AUD-01）、BF-105（AUD-02）、BF-106（AUD-03）。

**AUD-04/05/10/09 验证结果**：后端全量 `pytest -q` **2009 passed / 0 failed**（480.95s）；`--cov=. --cov-fail-under=80` **87.31% exit 0**、Service 层 **98% ≥90**（均本地漂移环境，AUD-12 标注「不代表 CI」）；`ruff check .` 0、`ruff format --check .` 402 files、`mypy . --strict` Success 228 files；四护栏（BR-4/BR-6/重复不变量/前端不变量）全 PASS；`spectacular --validate` exit 0。前端：type-check/lint/format:check 三项 0；`npm run test:coverage` 169 文件 2196 tests exit 0，`.ts` 层 statements 92.79% / branches 86.77%（≥80），`src/stores` 96.87% / 92.48%（≥90）。红灯取证：AUD-04×3、AUD-05×3、AUD-10×3、AUD-09×7 + 守卫变异×1，全部先红后绿。**未执行（如实标注）**：mutmut 与前端 `test:mutate`（留 CI mutation job，同 BF-104~106 先例）。

**活账本交叉引用**：BF-107（AUD-04）、BF-108（AUD-05）、BF-109（AUD-10）、BF-110（AUD-09）。

**AUD-06/07/08/11/23 验证结果（批次矩阵，2026-10-19）**：后端全量 `pytest -q` **1998 passed / 0 failed**（1185.33s；2009−11=1998 删减对账：AUD-11 9 例 + AUD-07 2 例，无 collateral loss）；`--cov=. --cov-fail-under=80` 整体 **87.54% exit 0**、Service 层 `coverage report --include="apps/assetmanagement/services/*" --fail-under=90` **98% exit 0**（均本地漂移环境，CT-7 口径：此数字不代表 CI）；`ruff check .` 0 / `ruff format --check .` 401 files；`mypy . --strict` Success **227 files**（401/227 = 批次 B 402/228 − 删 2 文件 + 1 新包，算术自洽）；四护栏（BR-4 函数长度 / BR-6 文件长度 / 重复不变量 / 前端不变量）全 PASS；`spectacular --validate` exit 0 + 重导后与基线 `git diff` **空**（25 warnings/23 errors 与批次 B 重导一致=存量）。红灯取证：本批为删除/收敛类重构，验收锚定于既有用例（51 收集对账、98/73/262 passed 等）+ `rg` 零引用，未新增先红轮次。**未执行（如实标注）**：后端 mutmut 与前端 `test:mutate`（留 CI mutation job，同批次先例）；前端零改动（无前端矩阵项）。提交与 push 后 CI 直证回填见账本 BF-111~115。

**活账本交叉引用**：BF-111（AUD-06）、BF-112（AUD-07）、BF-113（AUD-08）、BF-114（AUD-11）、BF-115（AUD-23）。

---

## 审计票

```markdown
[审计票 - 必填项]
- 读取规范：已读 根 AGENTS.md §1~§10、backend AGENTS.md、frontend AGENTS.md、Rules_Fiels/backend-business-rules.md、Rules_Fiels/backend-testing-rules.md、Rules_Fiels/frontend-business-rules.md、Rules_Fiels/frontend-testing-rules.md、Project_Requirements/01-业务需求/07-功能需求与验收标准.md
- CT-1[√] CT-3[√ — 批次 D 补 3 条直调 FSM 用例 + `test_state_enum_equivalence`，方法名层缺口闭合] CT-5[√] CT-7[√ — venv 对齐 dev.txt（Py3.13.13/Django6.0.8/DRF3.17.2/mypy2.1.0/pytest9.1.1/ruff0.17.1）；覆盖率数字仍为本地环境，CI 直证待 push]
- DR-1[√(6 处命中已立账 AUD-06/07/08/09/11/17)] DR-5[√ — 护栏 exit 0，最大 475 逻辑行，无豁免标记]
- SC-1[√] SC-3[√ — 2 处字面量记录，无用户输入注入点；AUD-20② 迁入 scripts/ 并参数化]
- 跨端契约：未破坏（Schema 基线唯一差异 = 34 条 description 本地化文本，剥离后完全相等，判 locale 漂移，按 M-3 不重导；4 项契约 3√ + AUD-18 零 diff 关闭）
- 红线触发：无 [HALT]
- 建议提交：是（报告文件 + BF-116~122 + 批次 D 代码/卫生改动；提交后 CI 直证回填）

[审计票 - 自检项]
- 测试：CT-2[√ — 整体 88.90%≥80、Service 分项 98%≥90（venv 对齐 dev.txt 后实测）；前端 store 分项未单独取数（标注）] CT-4[√] CT-6[√]
- DRY：DR-2[√] DR-3[√(唯一例外已立账)] DR-4[√] DR-6[√]
- 安全：SC-2[√ security-scan.yml 6 job] SC-4~SC-8[√（SC-5/6 不适用，见 §2.4）]
- 可观测性：OC-1~OC-3[√] OC-4[~] OC-5[~] OC-6[√] OC-7[~]（QPS<10 豁免）；/metrics 无认证→AUD-19③（不采纳，内网惯例待部署确认）
- AI鲁棒性：AR-1~AR-5[√ — 全程只读，未生成业务代码；门禁逐项实跑]
- AI行为：Fact-1[√]（未取回的信息一律标「未执行」，无编造）
- 写作风格：Style-1~Style-3[√]
- 覆盖率：整体 88.90%（≥80%）/ 核心 Service 分项 98%（≥90%）
- §5.1 状态机旁路：已声明 7 处 + 未声明 2 处（AUD-03/05）
- §5.2 跨端契约：4 项（3√ + 1 P3）
- §5.3 安全分流：SC-1√ SC-3√ SC-5/6 不适用 SC-8 与 CI 豁免吻合
```

**报告完成。** 24 条台账（P1×3 / P2×8 / P3×12 + 1 条不采纳登记）+ 6 条不采纳候选 + §5 五组专项证据。批次 A~D 修复已全部落地，台账已回填「已修复」标记，修复追踪表已追加批次 D 各行，活账本已登记 BF-104~122。提交与 push 后 CI 直证回填见账本对应条目。
