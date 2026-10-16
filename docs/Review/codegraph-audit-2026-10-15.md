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
| P1-01 | P1 | 状态机旁路 + 审计缺失 | `apps/assetmanagement/serializers/base_model_serializers.py:201-243`；`apps/assetmanagement/views/contract_view.py:123-133` | `ContractUpdateSerializer`；`ContractViewSet.perform_update` | `contract_status` 可写（在 fields:223、不在 read_only:243）。前端 `views/.../ContractForm.vue:394` 编辑恒提交该字段 → 生产路径上 8 个合法状态间任意跳转均被接受：不过 `ContractFSM.transition`、无 `GenericAuditService.log_update`（仅 LoggingMixin logger.info 不落库）、状态变更不触发 `_recalc_paid_amounts` 致 `amount_unpaid` 滞留旧口径。正规 FSM 入口 `update_settlement_status` 前端零调用（死端点）。违反 B7 状态流转审计规则与 BF-092/I-10 约定 | `perform_update` 检测 `contract_status` 变更时改路由 `ContractService.update_settlement_status`（FSM+审计+重算一次收齐），或将该字段设 read_only、流转仅走专用 action | `codegraph explore "ContractUpdateSerializer perform_update"`；回归：PUT 改状态断言 `log_update` 被调、非法跳转抛 `INVALID_CONTRACT_TRANSITION` | 待修 |
| P1-02 | P1 | 跨端契约错位 | `apps/notification/views.py:22-55`；`views/NotificationList.vue:68-79`；`stores/notificationStore.ts:46-48` | `notification_list`；`fetchNotifications` | 后端仅识别 `limit`（默认 20、钳 100）与 `is_read`，返回裸数组；前端发送的 `page/page_size/notification_type/priority/keyword` 全部静默丢弃；store 数组分支 `pagination.total = data.length` → 分页 UI 失效、>20 条通知不可见、四类筛选全死。违反根级 §3 分页参数契约 | 后端对齐 `CustomPageNumberPagination` 并支持 type/priority/keyword 过滤、返回 `{count, results}`；或前端裁剪为 limit 模式并移除假分页 UI（两端同步） | `rg -n "page_size|limit" apps/notification/views.py`（当前仅 limit） | 待修 |
| P1-03 | P1 | 数据一致性（陈旧值可提交） | `views/RecycleAssetView.vue:152-174` | `watch(asset)`；`canSubmit` | watch 无精确匹配出库单时仅 warning、**不清空** `recyclableRecordcode`（全文件无 `= ''` 重置）；`storage_code` 亦仅空时回填（:156）同样残留 → 从「有出库单资产 A」切到「无出库单资产 B」后 `canSubmit` 仍 true，提交将使用 A 的出库单 + 残留 A 仓库，对错误出库单创建回收记录 | watch 无匹配分支补 `recyclableRecordcode.value = ''`；`storage_code` 随 asset 变更重置 | 组件测试：加载 A（有单）→ 切 B（无单）→ 断言 `canSubmit === false` 且 `submitFn` 拒绝 | 待修 |

### P2（8 条）

| ID | 级 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 终态 |
|---|---|---|---|---|---|---|---|---|
| P2-01 | P2 | 审计字段污染 | `apps/unregisteredasset/services.py:195`；`apps/unregisteredasset/audit_adapter.py:156-206` | `_log_approve_audit` | `operator_jobcode` 传入 `Employee` 实例，落库为 `str(Employee)`=姓名 → `AssetOperationLog.operator_jobcode` 列存姓名不存工号，按工号过滤/检索该类审批日志全部失配。对照组 `apps/assetmanagement/views/damaged_asset_view.py:164` 传 `auth_username`（正确）→ 仅未登记审批路径污染。mypy 不报（`approver_employee: Any` + `_safe_call_audit` 动态 getattr 双重绕过）；测试无断言 | `operator_jobcode=approver_employee.employee_jobcode`，姓名走 `operator_name`；补回归测试断言 `log_operation` 收到字符串工号 | `rg -n "operator_jobcode=approver_employee" apps/unregisteredasset/services.py` | 待修 |
| P2-02 | P2 | OpenAPI schema 漂移 | `apps/assetmanagement/views/contract_view.py:193-211` vs `services/contract_service.py:307-309` | `update_settlement_status` | schema/inline_serializer 与错误提示声明 choices `["pending","settled"]`，实现按 `Contract.CONTRACT_STATUS_CHOICES`（8 状态，`models/contract.py:26-34`）校验 → 文档宣称取值全部被拒 `INVALID_CONTRACT_STATUS`；前端零调用（死端点 + schema 漂移） | schema choices 改为 8 状态常量；修 schema 后重导出 `api-schema-baseline.json`（§3 M-3 要求） | `python manage.py spectacular --format openapi-json --file api-schema-baseline.json --validate` | 待修 |
| P2-03 | P2 | 限流绕过 + 注释不符 | `apps/authusermanagement/urls.py:22-24`；`apps/authusermanagement/views.py:65-66,172` | `AuthUserViewSet`（create） | DefaultRouter 未限 actions → `POST /auth/users/` 亦开放注册（AllowAny），仅挂全局匿名 20/min，而 `/auth/register/` 为 `RegisterRateThrottle` 5/min → 注册限流口径绕过；urls 注释「仅注册 list/retrieve/update/delete」与实现不符。`RegisterSerializer` S8 校验在位，无提权 → 不及 P1 | `router.register(..., actions=[...])` 排除 create，或 create 挂 `RegisterRateThrottle`；订正注释 | `rg -n "RegisterRateThrottle|router.register" apps/authusermanagement/` | 待修 |
| P2-04 | P2 | 导出截断（已知遗留同型） | `components/componentsdetails/` 下 9 处：`AssetContentDetails.vue:436`、`ContractDetails.vue:394`、`DamagedAssetDetails.vue:421`、`WasteAssetDetails.vue:224`、`AuditLogDetails.vue:223`（`total.value \|\| 1000` 变体）、`HardDiskSNDetails.vue:408`、`OutAssetDetails.vue:364`、`RecycleAssetDetails.vue:373`、`UnregisteredAssetDetails.vue:351`；钳制源 `core/pagination.py:33-35` + `core/constants.py:12` | `fetchAllData` → `page_size: total` | **9 处**（R2 reviewer 自审订正，基线原判 5 处系 grep 口径不完整漏 `page_size: <store>.pagination.total` 写法）客户端导出残留 → `max_page_size=100` 静默钳制 →「导出全部」截断 100 条。BF-092/I-1 账本已知遗留（上批仅迁移 4 个生命周期页；操作日志/员工两域已改服务端导出 `useOperationLogExcelExport`/`useUserExcelExport`），交叉引用不重复立账 | 迁移至 `useServerExcelExport`（生命周期页已有先例） | 导出 >100 行数据集断言行数；`rg -n "page_size:.*pagination\.total\|page_size: total" components/componentsdetails/`（R2 复核仍命中 9 处） | 待修 |
| P2-05 | P2 | RBAC 前后端口径不一致 | `router/routes-main-system.ts:23`；`components/AsideMenu.vue:93`；`apps/assetmanagement/views/operation_log_views.py:63`（对照矩阵 `Rules_Fiels/backend-business-rules.md:146`） | `operationlogdetails` 路由守卫 | 前端 `requiredMinRole:'auditor'` 拦截 regular_user，但 RBAC 矩阵 :146 允许 regular_user 查看本部门操作日志、后端 `_scope_by_user` 亦放行 → 三处口径互斥：regular_user 菜单可见（AsideMenu:93 无条件显示）、点击被拒、API 却允许 | 二选一并同步矩阵：守卫降为 regular_user，或菜单按权限隐藏 | 对照三处 `rg -n "operationlogdetails\|requiredMinRole\|_scope_by_user"` | 待修 |
| P2-06 | P2 | 测试缺口（CT-3 违规） | `apps/assetmanagement/state_machine/contract_fsm.py:26-68` | `ContractInvalidTransitionError`；`ContractFSM.transition` | `ContractInvalidTransitionError` / `INVALID_CONTRACT_TRANSITION` 测试目录零匹配；7 条合法转移仅 `purchasing→purchase_finished` 被测（`test_contract_service.py:105`、`test_contract_view_api.py:155-163`）。CT-3 要求状态机每条流转路径至少一个集成用例。R2 复核：tests/ 源码仍 0 命中（仅 stale `__pycache__` 编译残留，疑为补测后又删） | 补全路径集成测试：7 条合法转移 + 非法跳转分支各至少 1 用例 | `rg -n "INVALID_CONTRACT_TRANSITION|ContractInvalidTransitionError" apps/assetmanagement/tests/` | 待修 |
| P2-07 | P2 | 依赖漏洞（SC-7） | `package.json` / `package-lock.json`（前端子仓） | `npm audit` | 8 漏洞：dev `shell-quote` critical 1 + high 7，含 prod `vue` 3.5.34 XSS advisory、prod `source-map-js` 1.2.1。BF-067 曾双 audit 归零，此后 advisory DB 新增所致，零代码变更；CI `security-scan.yml` 可能转红 | `npm audit fix` / 升级 `vue`；以 CI 为权威门禁复核 | `npm audit --json`（证据：`Temp/opencode/npmaudit.json`） | 待修 |
| P2-08 | P2 | 规模红线（DR-5 / BR-4）（R2 新增） | `apps/assetmanagement/services/repair_asset_service.py:166` | `RepairAssetService.complete_repair` | 护栏实测 53 逻辑行 > 50 上限（BR-4 FAIL），且未在 BR4 函数长度台账登记豁免。影响面小：调用方为 `test_repair_service_gaps.py`（约 15 处）+ `test_asset_lifecycle.py`（3 处）+ 1 个 view 入口 | **必须拆分**（BF-058 教训③：新增超限一律拆分不得豁免）：将通知构造与操作日志写入抽为私有方法（`_build_complete_notification` / `_write_complete_log`），主函数降至 ≤50 行 | `python scripts/check_function_length_guard.py`；拆分后重跑 BR-4 护栏 + 上述两测试文件全绿 | 待修 |

### P3（3 条）

| ID | 级 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 终态 |
|---|---|---|---|---|---|---|---|---|
| P3-01 | P3 | 序列化缺陷 | `core/excel_export/workbook.py:68` | `coerce_excel_value` | `return coerce_excel_value(value) or ""` 将 0/False 转空串，导出数值/布尔列丢 0 | 改判空逻辑仅对 `None` 生效（`if value is None: return ""`） | 单测：导出含 0 值列断言保留 `0` | 待修 |
| P3-02 | P3 | 死代码 / 注释漂移 | `types/employee.d.ts:62`；`stores/createEntityStore.ts:156` | `pageSize`（类型） | 死类型字段 `pageSize` 与注释漂移，无运行时影响 | 删除死类型、订正注释 | `rg -n "pageSize" types/employee.d.ts` | 待修 |
| P3-03 | P3 | UI 优雅降级（显示瑕疵） | `utils/statusMapping.ts:46-54`；`components/commoncomponents/StatusTag.vue` | `OUTASSET_STATUS_MAP` | 映射仅 4 键、StatusTag 无 default slot → 未知出库状态显示原始值 + logWarn（降级不崩溃） | 补全映射键或加 default slot | 组件测试：传未知 status 断言降级展示 | 待修 |

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

1. **立即**：P1-01、P1-03（注意三案涉改文件均在未提交改动中，修复需与工作区合并）。
2. **本迭代**：P1-02、P2-01（一行修复 + 回归）、P2-02（schema 重导出）、P2-05（三处口径统一）、P2-06（CT-3 补测）、P2-08（BR-4 护栏 FAIL，必须拆分）。
3. **计划**：P2-03、P2-04（9 处，复用 useServerExcelExport 先例）、P2-07（CI 权威，升级依赖）。
4. **低优**：P3-01 ~ P3-03。

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
