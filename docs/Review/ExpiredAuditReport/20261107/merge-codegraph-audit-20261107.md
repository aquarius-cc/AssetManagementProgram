# 三报告融合核实审计报告（merge-codegraph-audit-20261107）

> **日期**：2026-11-07 | **模式**：纯只读审计融合（零业务代码改动）
> **融合来源**（同日期、同规范基线 v3.7.5 的三份独立审计）：
>
> | 来源 | 文件 | 台账规模 | 方法特征 |
> |:--|:--|:--|:--|
> | AtomCode | `AtomCode+codegraph-audit-20261107.md` | P1×1 + P3×4 | 本地重跑全量 pytest（2398 passed）+ reviewer subagent 复核 |
> | main | `main-codegraph-audit-20261107.md` | P1×5 + P2×12 + P3×5 + 不采纳×5 | 全门禁矩阵实跑（ruff/mypy/vue-tsc/eslint/护栏）+ 3 explorer 子代理 |
> | TraeCode-KimiK3 | `TraeCode-KimiK3+codegraph-audit-20261107.md` | P3×2 + 误报排除×4 | ponytail（过度工程）视角 + 护栏实跑，覆盖率引用历史留痕 |
>
> **融合方法**：对三份报告的**每一条问题**独立回查源码/命令输出（本会话执行），
> 判定「真实 / 误报 / 数字偏差 / 登记取舍」；冲突点按证据裁决；合并同根问题并统一编号 M-xx。
> **状态口径**：纯审计不产生「已修复」；融合台账状态仅 已确认/待修、待复核、不采纳。

---

## §一 交叉核实与冲突裁决

### 1.1 冲突裁决（5 处，均以本会话回查证据为准）

| # | 冲突点 | 各报告主张 | 裁决证据 | 结论 |
|:--|:--|:--|:--|:--|
| C1 | `.vue` 棘轮阈值 | AtomCode：≥棘轮 12.9（引规则文档）；main：21.1 余量 0.09pt | `vitest.config.ts:54-59` 实际阈值 **21.1/19.0/18.6/21.3**（2026-10-30 重基 M-27/M-25，注释在 :51-53）；规则文档 v1.8 §六所载 12.9 系 2026-10-12 旧基线，**未同步** | main 正确；AtomCode 所引文档值过时。规则文档漂移另立新条 M-27 |
| C2 | 未登记资产域审计失败有无指标 | AtomCode：`_safe_call_audit` 仅 warning 无指标；main：适配器宽 except「累计 AUDIT_WRITE_FAILED 指标」 | `audit_adapter.py:109-113`（log_create，log_update/log_delete 同型 :156/:213）**有** `AUDIT_WRITE_FAILED.labels(channel="unregistered_adapter").inc()`（M-19 注释）；`services.py:89-106` 外层 `_safe_call_audit` 的 except（:102-104）仅 warning **无指标**（该层只捕获 import 失败等极窄路径，真实 DB 失败在内层适配器即被指标捕获） | 两者各对一半：指标在**适配器层**已接线；缺口缩小为「外层包装层无指标 + 失败不阻断主流程的语义本身」。AtomCode AUDIT-002 并入 M-08 并修正表述 |
| C3 | 组件层 `isAxiosError` 直导文件数 | AtomCode/main：7 个 .vue；TraeCode：2 个视图 | `grep -rl "isAxiosError" src --include=*.vue`（排除测试）实测 **7 个**：AssetTypeDetails / AssetBatchImport / AssetTypeBatchImport / DepartmentForm / OutAssetForm / NotificationList / ScanAssetView | AtomCode/main 正确，TraeCode A-01 漏计 5 个组件 |
| C4 | FR-5 `.vue` 最大逻辑行 | AtomCode：318（AssetTypeDetails）；TraeCode：136 | 护栏权威口径 `check_frontend_invariants.py --print`：`.vue` 段最大 **411（UnregisteredAssetForm.vue）**，其次 407/401/401/391… | 两报告数字均不准确（自算口径与护栏口径不一致）；采用护栏值 411，仍 ≤500 PASS，不产生新问题 |
| C5 | 后端全量测试/覆盖率现状 | AtomCode：2398 passed / 89.55%（本次本地实测）；main：319 passed / 2079 setup errors（残留测试库）；TraeCode：历史留痕 89.40% / 2210 passed | 本会话在系统 Python（工具链已对齐 `dev.txt`：mypy 2.1.0 / pytest 9.1.1 / ruff 0.17.1，CT-7）重跑 **2398 passed / 89.55%**；main 的 2079 errors 根因 `psycopg.errors.DuplicateDatabase`（其会话本地残留 `test_asset_management_backend` 库，环境问题非代码缺陷） | 现状数字采 AtomCode 本次实测；main 的环境残留问题独立成条 M-16；TraeCode 数字标注为历史留痕（其报告自身已声明） |

### 1.2 三报告共识（3/3 一致，本会话抽验通过）

| 维度 | 共识结论 | 抽验证据 |
|:--|:--|:--|
| CT-3 资产状态机 | 规则表与实现逐条一致；0 未声明旁路（3 处声明例外均带前置守卫） | `transitions.py:32-85` 22 个转换 cell + scrapped 终态；`unregistered.py:53/87/125` 守卫 |
| 合同状态机 | 8 态单向链与 §3.1 一致；AUD-15 非法态收敛；脏数据 `[]` 防御 | `contract_fsm.py:31-92` |
| 跨端契约 4 项 | 4/4 通过（响应唯一入口 / 枚举 8/8 / 分页 0 混用 / 日期 ISO） | `success_response` 167+ 调用方；`urls.py:142` 命中系 docstring；`types/asset.ts:47-56`；`Format.ts:96-101`（main 扩展出 M-15 [推测] 时区渲染风险） |
| SC-1 / SC-3 | 生产代码 0 硬编码密钥（security-scan 明文串为轮换凭据黑名单，N 项）；raw SQL 仅静态 `SELECT 1` | 业务目录限定扫描；`config/urls.py:70,117` |
| SC-5/SC-6 | N/A（全仓无上传端点、无导入实现；Excel 导入在浏览器解析后 JSON 提交） | `request.FILES/FileField` 零命中（main 口径）；`openpyxl` 仅导出内核 |
| OC-6 | `/health`（DB+Redis）+ `/ready` 已注册 | `config/urls.py:152-153` |
| RBAC / 行级隔离 | 权限类齐备（fail-closed）；13 ViewSet 覆写 `get_queryset`；AUD-21 反转落地 | `core/permissions.py:207`；`department_scope.py:47-88` |
| 规模护栏 | BE 484 / FR-6 199 / FR-8 407 / BR-4 0 超长，全 PASS | 本会话护栏 `--print` 复跑一致 |
| 重复代码护栏 | G-1~G-3、G-5~G-8 PASS | `check_duplicate_invariants.py` 本会话复跑 `[RESULT] PASS`（但见 M-02 BOM 假绿路径） |
| 前端语法纪律 | 0 Options API / 0 组件直发请求 / 0 `@/api` 违规导入（存量豁免清单制） | 三报告一致 + `eslint.config.ts:110-130` 规则在位 |

---

## §二 融合问题台账（M-01 ~ M-27）

> 字段：ID / 级别 / 类型 / 位置(file:line / symbol) / 来源(原报告·原 ID) / 描述与核实结论 /
> 修复建议 / 回查命令 / 建议验证方式 / 状态。
> 级别为融合后重裁定（含降级，理由在描述列）；影响面与优先级排序见 §四 修复计划。

### 2.1 P1（5 条）

| ID | 级别 | 类型 | 位置 (file:line / symbol) | 来源 | 描述与核实结论 | 修复建议 | 回查命令 | 建议验证方式 | 状态 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| M-01 | P1 | CI 门禁闭合 | `.github/workflows/ci-cd.yml:40-43,112-157`；`duplicate-guard.yml:40-46`；`migration-check.yml:1-12`；`scripts/check_ci_orchestration.py:35-38` | main P1-01 | 部署 gate 仅监听 `CI Pipeline` 并按 SHA 回查 `Dependency Security Scan`；`duplicate-guard.yml`（G-1~G-8 护栏汇总）与 `migration-check.yml` 是独立 workflow，失败**不阻断部署**；编排断言 `TARGETS` 只覆盖 ci-summary + guard-summary 的 job 完整性，不断言 gate 回查名单。另核实：`migration-check` 为 `on: pull_request` 触发，而本仓直推 master（历史 0 PR，根 AGENTS v3.7.0 记载）——**迁移安全门禁在现行工作流下实际休眠**，比 main 原述更重。已登记取舍（`duplicate-guard.yml:41-42` 注释「跨 workflow 统一汇总只能靠 required checks 或 API 回查，本批不引入」）→ 属风险提示而非隐瞒缺陷 | 将两条 workflow 的汇总结论纳入 gate 回查（复用 :112-157 的 poll + fail-closed 双步），或落地 required checks + PR 流程（根 AGENTS v3.7.0 已列为独立后续项）；`migration-check` 增 `push` 触发或并入 CI 长链 | `codegraph node audit_listener`；`rg -n "workflows:" .github/workflows/ci-cd.yml` | 在 `scripts/tests/test_ci_orchestration.py` 增「gate 回查名单必须包含全部汇总节点」断言（先红后绿）；用一次失败护栏 run 验证 gate 拒绝部署 | 已修复（BF-183 批次 1，2026-11-08：gate 双名单回查 + migration-check push 唤醒，CI 直证见账本 BF-183 §3） |
| M-02 | P1 | 护栏假绿 | `scripts/check_duplicate_invariants.py:41,116-123`；对照 `scripts/line_metrics.py:44-57` | main P1-02 | 重复护栏 `read_text` 解码序 `("utf-8", "gbk")` **缺 `utf-8-sig`**：带 BOM 的 `.py` 使 `ast.parse` 抛 SyntaxError 被静默跳过，G-1~G-3、G-5~G-8 全部可被 BOM 文件绕过。`line_metrics.py:52` 已按 `utf-8-sig` 打头修复同类缺陷（v3.6.1 记载），本脚本未同步——同型缺陷第二实例 | 复用 `line_metrics.read_text`（DR-1/LT-1 单源），补 BOM 证红自测（先红后绿，参照 `test_file_length_guard.py` 既有 BOM 用例） | `codegraph callers read_text`；`rg -n "utf-8-sig" scripts/` | 新增带 BOM 夹具文件断言护栏 exit 1（证红）；替换后现实仓仍 PASS（证绿） | 已修复（BF-183 批次 1，2026-11-08：G-0 fail-closed + BOM 证红自测，CI 直证见账本 BF-183 §3） |
| M-03 | P1 | 调用链深度 | `core/batch_mixins.py:401-424`；`apps/assetmanagement/services/asset_service.py:316-339` | main P1-04 | 资产批量删除链实测 6 层：`View.batch_delete(:402)` → `batch_delete_invoke(:422)` → `AssetService.batch_delete_asset(:316)` → `BatchOperationMixin.batch_delete_execute(:339 调用)` → `_delete_one(:323)` → `AssetSelector`/audit，超 DR-6(≤5) 与 BR-7(≤3)。影响面大：`BatchDeleteViewMixin` 13 域接线（codegraph impact 246 符号），响应键集由 `test_b5_baseline_snapshot`/`test_batch_contract_snapshot` 全仓锁定 | 扁平化：把逐条校验、Selector 查询与审计编排合并进单一 Service 事务方法，收敛为 View→Service→Selector；骨架差异钩子保留 | `codegraph callees batch_delete`；`codegraph impact BatchDeleteViewMixin` | 扁平化后两快照测试全绿 + 增一条调用链深度断言（≤3）防回潮 + 全量 pytest | 已确认/待修 |
| M-04 | P1 | 测试覆盖/回归屏障 | `vue-assetmanagement/vitest.config.ts:54-59`；`coverage/coverage-final.json` | main P1-05 + 本融合扩证 | `.vue` 层棘轮 21.1/19.0/18.6/21.3（C1 裁决实际值），当前语句命中 21.19%，**余量仅 0.09pt**，任何小改动可能 CI 红；本融合重算 `coverage-final.json`：**68 个 .vue 文件 0 语句覆盖**（App/AsideMenu/Dashboard* 系列等，远超 main 所列 3 个），CT-4 回归面薄弱 | 先补 0% 页面（优先 Dashboard 系列/AsideMenu 等高流量）挂载与交互测试，再按 T14「只升不降」手工上移棘轮；`npm run test:coverage` 在干净环境确认四项阈值绿 | `rg -n "statements: 21.1" vue-assetmanagement/vitest.config.ts`；`python -c` 重算 coverage-final.json 零覆盖清单（命令见 §四） | 补测后四项阈值绿 + 棘轮上移复核 CI `frontend-test` | 已确认/待修 |
| M-05 | P1 | 审计缺失（B7） | `apps/assetmanagement/services/contract_service.py:214,265,474,509`；`views/contract_view.py:338,388,396` | AtomCode AUDIT-001（main/TraeCode 未发现） | 合同支付记录 4 个写操作（单条添加/批量回填/软删/审批通过）**均无审计**：方法体逐一核读无 `GenericAuditService` 调用（同域 create:195 / update:350 / delete:407 均有）；`add_payment_record_batch:270-271` 设计注释自述 approve 应承载「谁批准了这笔付款」，但 `paid_record` 无 approver 字段且无审计，审批痕迹不可追溯，与注释意图直接矛盾。影响面：`approve_payment_record` 8 符号（view + 批量 `_add_item` + tests×4）；`delete_payment_record` 8 callers | 4 方法成功写库后补 `GenericAuditService.log_update`（或新增 `log_payment_operation`）：记录操作人/动作/payment_id/金额/状态前后值；方法签名补 `operator_jobcode` 并由 View 从 `request.user` 下传；批量路径逐条记 | `codegraph node approve_payment_record`；`rg -n "GenericAuditService" apps/assetmanagement/services/contract_service.py` | 补审计断言测试（断言 4 操作各生成 AuditLog 记录，参照 `test_contract_service.py` 模式，CT-4 回归屏障）+ 全量 pytest | 已确认/待修 |

### 2.2 P2（13 条）

| ID | 级别 | 类型 | 位置 (file:line / symbol) | 来源 | 描述与核实结论 | 修复建议 | 回查命令 | 建议验证方式 | 状态 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| M-06 | P2（原 P1 降级） | 双取数口径/DR-1 | `waste_asset_view.py:69` 等 8 处（storage:59,88 / contract:63,116 / asset_type:39 / recycle:51,115,117 / damaged:53,108 / out_asset:54,105 / asset:393,403,440） | main P1-03 | ViewSet 类属性 `queryset = Model.objects.filter(...)` 与 Selector `get_queryset_for_user` 两套取数口径同域共存。本融合核实：**8 处中 7 处已覆写 `get_queryset()`**（运行时行级隔离不受影响），`asset_type_view` 未覆写但属 §4.2.1 字典域读面豁免（无 PII）→ 无现网越权面，降级为 DR-1 一致性问题（潜在风险：类属性是未覆写路径下的活口径） | 按域分批把类属性 `queryset` 删除或改为委托 Selector（与 `get_queryset()` 同源），先低风险字典域试点 | `rg -n "^    queryset = " apps/assetmanagement/views/` | 每域补 `get_queryset()` 行级隔离断言（参照 `test_employee_rbac_scope.py` 14 用例）+ 后端全量 pytest | 已确认/待修 |
| M-07 | P2 | 行级隔离防退化 | `apps/assetmanagement/services/out_asset_service.py:49,56-57` | main P2-01 | `create_outasset(user: Any \| None = None)` + `if user is not None` 守卫：忘传即跳过 `ensure_asset_visible`；`ensure_employees_in_scope`（department_scope）对 `user is None` 亦放行（docstring 明示「沿用可选设计」）。生产唯一调用方 `out_asset_view.py:230-234` 已传 `user=request.user` → 防退化缺口而非现网越权 | 与 `update_outasset` 对齐改 kw-only 必填并去空值守卫；测试显式覆盖「忘传即 TypeError」 | `codegraph callers create_outasset` | 新增 `user=None` 路径单测（改造前为放行、改造后为报错，先红后绿）+ 出库域全量测试 | 已确认/待修 |
| M-08 | P2（2 条合并） | 审计可靠性 | `apps/unregisteredasset/audit_adapter.py:109-113,156,213`；`services.py:89-106` | main P2-02 + AtomCode AUDIT-002（C2 裁决合并） | 审计失败「容错不阻断主流程」：适配器层 3 处宽 except 有 `AUDIT_WRITE_FAILED` 指标（M-19）但主流程继续；外层 `_safe_call_audit`（on_commit 包装）except 仅 warning 无指标（极窄的 import 失败路径）。极端情况下状态变更可无审计痕，B7「不可跳过」依赖指标告警而非事务保证 | 二选一拍板：①「审计写入失败即回滚」（strict 口径，与 `OperationLogService` 对齐）②「异步补偿队列」；外层包装补同型指标；补失败路径测试 | `codegraph node log_create`；`rg -n "AUDIT_WRITE_FAILED" apps/ core/` | 拍板后补失败路径测试（审计异常时断言回滚或补偿入队）+ 指标递增断言 | 已确认/待修 |
| M-09 | P2 | CT-7 口径 | `.github/workflows/ci.yml:384`；`vue-assetmanagement/package.json:14` | main P2-03 | CI 跑 `npx vue-tsc --noEmit`，本地/规则口径 `npm run type-check` = `vue-tsc --build`（:14 实核）；两形态对 project references 处理不同，存在 CI 与本地结论不一致的窗口 | 统一为 `npm run type-check`，或在 CI 注释登记差异理由 | `rg -n "vue-tsc" .github/workflows/ci.yml vue-assetmanagement/package.json` | 改后 CI `frontend-type-check` 与本地 `npm run type-check` 双绿 | 已确认/待修 |
| M-10 | P2 | CI 效率 | `.github/workflows/ci.yml:453-456` | main P2-04 | `frontend-test` 连续两次执行同一 `npm run test:coverage`（整体 + Store 专项各 ~65s，Store 口径已由 :42-47 阈值块强制），重复全量运行 | 第二次改 `npx vitest run --coverage --coverage.include="src/stores/**/*.ts"`，或删除并注明阈值块已覆盖 | `sed -n '450,458p' .github/workflows/ci.yml` | 改后 CI `frontend-test` 绿且时长下降约 65s | 已确认/待修 |
| M-11 | P2 | 密钥扫描盲区 | `.github/workflows/security-scan.yml:250,313`；`ci.yml:220` | main P2-05 | 模式扫描 `rg --type py --type js --type ts --type json`（:250 实核）**不含 yml**；黑名单检查显式 `-g '!.github/**'`（:313，避免自命中，N-03 登记设计）→ workflow 目录自身凭据形态（含 `ci.yml:220` CI 占位串）不被任何 secret 扫描覆盖 | 黑名单改哈希指纹（可安全扫全仓）；模式扫描补 `--type yaml` 并只精确排除黑名单步骤自身 | `sed -n '248,256p;311,314p' .github/workflows/security-scan.yml` | 注入测试 yml 夹具（模拟 workflow 内明文）断言 secret-scan 红 | 已确认/待修 |
| M-12 | P2 | 依赖审计口径 | `.github/workflows/security-scan.yml:172-173,216` | main P2-06 | `pip-audit --ignore-vuln CVE-2026-106454`（twisted 不可修项，:166-171 注释含复审条件）与 `npm audit --omit=dev`（BF-100 人工审批 2026-10-17，braces dev 链不可修）与 SC-7 字面口径有差距——均属**已登记降噪取舍**，非违规 | 在根 AGENTS §6 执行状态补记两条例外及复审周期；schedule 每周全量时补扫 dev 链（仅报告） | `rg -n "ignore-vuln|omit=dev" .github/workflows/security-scan.yml` | 补记后 §6 与 workflow 注释一致（文档核对） | 已确认/待修 |
| M-13 | P3 级待复核（原 P2 证据不成立） | 前端 floating promise | main 引 `StorageDetails.vue:212,215` / `RecycleAssetDetails.vue:244,247` / `OutAssetDetails.vue:245,248` / `UnregisteredAssetDetails.vue:243,246` | main P2-07（本融合降级） | main 所引 4 处删除链**均有 `.catch`**（本融合逐处核读 + then/catch 计数 2/4：catch 多于 then，链尾 `.catch((error) => { if (error !== 'cancel')…` 与 `UnregisteredAssetDetails.vue:249` 实读一致）→ 具体证据不成立；「存在 floating promise」的一般性主张未独立复核 | 不依人工点查立账：启用类型感知 `no-floating-promises` 规则，以规则输出为准立账/销账 | `npx eslint . --rule 'no-floating-promises: error'`（临时评估，勿提交） | 规则输出 0 命中即销账；有命中则按输出补 catch/void 并立条目 | ~~待复核~~ **评估面已销项（BF-188，2026-11-11；C-14/S7 评估 115 处命中，D13 不启用规则）** |
| M-14 | P2 | 前端 DRY（FR-1/FR-2） | `views/system/RoleManage.vue:77-87,143-148`；同型 `AuthUserManage.vue:97-103,186-192`、`ContactsView.vue:88-94,121-131`、`NotificationList.vue:69-103,249-254` | main P2-08 | 4 个管理页重复「多 ref + el-pagination + handle*」样板（RoleManage 实核：:77-87 分页块 + :143-148 六 ref + 防抖搜索）；`CommonList.vue`/`SmartListContainer.vue`/`usePagedList.ts`/`usePaginationSearch.ts` 已有可复用件 | 抽统一列表页组件 + composable，逐页替换并补交互测试（与 M-04 补测合并推进） | `rg -n "el-pagination" src/views -l` | 替换后各页交互测试绿 + `npm run lint:ci` + 页面快照不回退 | 已确认/待修 |
| M-15 | P2 [推测] | 跨端日期显示 | `config/settings/base.py:166-168`；`vue-assetmanagement/src/utils/Format.ts:46-100` | main P2-09（AtomCode 判「0 旁路」的延伸） | 后端 `TIME_ZONE=Asia/Shanghai` + `USE_TZ=True` 序列化 `+08:00`，前端全部用本地 `getFullYear/getHours` 渲染；**非东八区浏览器「业务日期」可能跨日**（影响面 [推测]：未做跨时区实测） | 明确产品口径：业务日期按 Asia/Shanghai 固定渲染（推荐，改动集中 Format.ts），或全链路 UTC+展示时区 | `rg -n "TIME_ZONE" asset_management_backend/config/settings/base.py` | 双时区浏览器（Intl 模拟）目检关键日期字段；Format.ts 单测补跨时区用例 | 已确认/待修 |
| M-16 | P2 | 本地可复现性 | `asset_management_backend`（pytest setup）；`conftest.py` | main P2-10 | main 会话全量套件因残留测试库 `test_asset_management_backend` 产生 2079 个 setup ERROR（`psycopg.errors.DuplicateDatabase`，17m42s 无覆盖率）；本会话本地无残留（2398 passed）→ 环境差异实证，影响他人本地复现 CI 结论 | 文档登记恢复步骤（删残留库或 `pytest --create-db`/`--keepdb` 口径）；CI 一次性库不受影响 | `psql -lqt | grep test_asset_management` | 残留库存在时按文档恢复后全量 pytest 绿 | 已确认/待修 |
| M-17 | P2 | LT-1/DR-1 护栏自洽 | `scripts/check_frontend_invariants.py:179-220,241-259`；对照 `scripts/line_metrics.py` | main P2-11 | 前端护栏内联第二份 TS 逻辑行计数（:179-220 实核，41 行完整实现）；`read_ledger:241-259` 解析台账**不区分「活跃/已关闭」分区**（与 BR-4/BR-6 台账双分区制不一致）。FR-6/FR-8 条文另指派本脚本为权威来源 → 属文档化双轨，不判硬违规，但与 LT-1 单源纪律有张力 | 抽公共 TS 计数函数至 `line_metrics.py`（或文档明确双口径分工）；台账解析复用分区感知函数 | `codegraph node logical_line_count`；`rg -n "def logical_line_count" scripts/` | 计数函数单测（含 BOM/字符串内注释边界）+ 双护栏同值比对 | 部分修复（BF-183 批次 1：read_text 收编单源；计数口径收编留独立批次） |
| M-18 | P2 | CI 汇总完整性 | `.github/workflows/security-scan.yml:326-330,361-364` | main P2-12 | `security-summary` 的 `needs: [changes, python-audit, node-audit, secret-scan]`（:364 实核）**未纳入 `weekly-report`**（:326-330，仅 schedule 触发）：周报生成失败不被汇总节点发现（SC-8 报告面） | `weekly-report` 纳入 schedule 分支条件判定（`if: always()` + 按 event 分流），或另设告警 | `rg -n "needs:" .github/workflows/security-scan.yml` | 模拟 weekly-report 失败 run，断言 Security 汇总红（先红后绿） | 已修复（BF-183 批次 1，2026-11-08：needs 纳入 weekly-report + 判定外部化六态纯函数，CI 直证见账本 BF-183 §3） |

### 2.3 P3（10 条）

| ID | 级别 | 类型 | 位置 (file:line / symbol) | 来源 | 描述与核实结论 | 修复建议 | 回查命令 | 建议验证方式 | 状态 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| M-19 | P3 | 规模余量 | `apps/assetmanagement/views/asset_view.py`（484 逻辑行） | main P3-01 | 距 DR-5 上限 500 仅 16 行（护栏 `--print` 权威值），后续新增即触发拆分立项 | 新增功能前先拆出 action 分组模块（与 M-03 扁平化同批评估） | `python scripts/check_file_length_guard.py --print | head -5` | 护栏 PASS 且该文件 <480 | 已确认/待修 |
| M-20 | P3 | 规模余量（双报告互证） | `vue-assetmanagement/src/composables/usePaginationSearch.ts`（199 逻辑行） | main P3-02 + AtomCode AUDIT-005 | 距 FR-6 上限 200 仅 1 行（护栏 `--print` 实测，两报告数字一致） | 拆出状态初始化/请求参数部分至 `usePaginationSearchState.ts`（156 行同域文件可承接） | `python scripts/check_frontend_invariants.py --print | head -5` | 护栏 composables 段 <200 | 已确认/待修 |
| M-21 | P3（3 项合并） | F11 执行缺口 + 设计令牌 | 7 个 .vue 直导 `isAxiosError`（AssetTypeDetails:145 / AssetBatchImport:152 / AssetTypeBatchImport:94 / DepartmentForm:95 / OutAssetForm:235 / NotificationList:18 / ScanAssetView:87）；`eslint.config.ts:110-130`；`views/LogIn.vue:333-418` | main P3-03 + TraeCode A-01（C3 裁决：TraeCode 漏计 5 个） | ① 7 个组件直接 `import { isAxiosError } from 'axios'`（rg 实核；api 层 3 文件属合规层）——非直发请求硬违规，但组件依赖 axios 包，与 F11 精神有张力；② ESLint `no-restricted-imports` 仅禁 `@/api/*`（:120 正则），**未禁 `axios` 包**，F11 无自动化守卫；③ LogIn.vue:333-418 含 14px/6px（及 1px 描边）偏离 F4 4px 基数（px 清单实核：100/12/14/16/1/20/24/32/40/480/4/6/8） | ① 在 `src/utils/` 导出统一错误判别 helper（如 `isNotFoundError`），7 文件改引；② `no-restricted-imports` 增 `axios` 模式并保留类型/helper 例外；③ 抽公共间距令牌 | `rg -n "isAxiosError" vue-assetmanagement/src --include=*.vue`；`sed -n '110,130p' vue-assetmanagement/eslint.config.ts` | 改后 `npm run type-check && npm run lint:ci` + 相关视图 spec 绿；临时启用规则输出 0 命中 | ~~已确认/待修~~ **已收口（BF-188，2026-11-11）：7 视图 + 4 个 .ts 复用 `isApiError`、F11 独立 ESLint 块、LogIn F4 复核已合规** |
| M-22 | P3 | 文档口径 | `core/mixins.py:111,137,206`；`utils/response_utils.py:23` | main P3-04 | 实际 message 为「查询成功/创建成功/删除成功」（三处实核），B1 示例为 `"success"`；跨端契约只约束根结构、前端按 `code` 判定 → 不构成契约破坏，属规范表述漂移 | 在 backend-business-rules B1 补记「message 为展示文案、值不固定」 | `rg -n "message=" core/mixins.py | head -5` | 文档核对（无代码改动） | 已确认/待修 |
| M-23 | P3 | OC-2 环境差异 | `config/settings/base.py:346-350`（对照 :338-345） | main P3-05 | dev/test 的 console handler `formatter: simple` 且**未挂 trace_id filter**（file handler 为 json+trace_id）：开发期日志无 trace_id，OC-1 透传链在非生产环境断链 | dev/test 的 console 也挂 `TraceIDFilter`，或明确豁免登记 | `sed -n '338,350p' asset_management_backend/config/settings/base.py` | 本地 runserver 请求日志含 trace_id 字段 | 已确认/待修 |
| M-24 | P3 | 设计令牌（范围修正） | `src/assets/styles/global-scroll.scss:8-19` | TraeCode A-02（本融合修正范围） | 滚动条 `:root`/`html.dark` 主定义 6 处裸 hex（#f1f1f1/#c1c1c1/#a8a8a8/#2a2a2a/#555/#666，实核）未走 F1-F5 令牌；`global-reset.scss:17-25` 的 #409eff/#f5f7fa 系 **var() 回退值（合规形态，不计）**——TraeCode「8+ 处」高计，修正为 6 处。风险低（滚动条基底，暗色链路走 CSS 变量） | 后续令牌化：灰阶收敛为 `--color-neutral-*` 变量；渐进优化，不单独成批 | `rg -n "#[0-9a-fA-F]{3,6}" vue-assetmanagement/src/assets/styles` | 改后暗色双主题目检 + `npm run lint:ci` | 已确认/待修 |
| M-25 | P3 | 流程健壮性 | `apps/notification/services/notification_service.py:99-139` | AtomCode AUDIT-003（main/TraeCode 未列） | 通知持久化 bulk 失败降级逐条、2 次重试后死信，仅 error 级完整字段日志 +「请人工补偿」注释，无死信持久化/自动重试/告警接线；属显式设计契约（非缺陷） | 死信落表/队列 + 定时重试管理命令；最低要求「通知持久化失败(死信」关键字接入告警 | `codegraph node _persist_individually` | 死信分支测试断言（告警/落库）+ 人工核对日志字段完整性 | 已确认/待修 |
| M-26 | P3 | 文档漂移 | `vue-assetmanagement/src/utils/Format.ts:19` | AtomCode AUDIT-004（main/TraeCode 未列） | 模块注释引用旧名 `outassetStatusMapping`（已更名 `ASSET_STATUS_MAP`，全仓该旧名零定义） | 删除旧名引用或更新为 `ASSET_STATUS_MAP` | `rg -n "outassetStatusMapping" vue-assetmanagement/src` | 修复后 rg 旧名零命中 | 已确认/待修 |
| M-27 | P3（融合新发现） | 文档漂移 | `Rules_Fiels/frontend-testing-rules.md` §六（:43）；对照 `vitest.config.ts:50-53` | 本融合 C1 裁决衍生 | 规则文档 §六记载棘轮「2026-10-12 实测基线：12.9/11.6/10.9/13.0」，实际配置为 2026-10-30 重基值 21.1/19.0/18.6/21.3（M-27/M-25 重基时未同步规则文档）→ 按文档执行会误判阈值余量 | 同步 §六棘轮值（仅数值同步，不收紧阈值；依子域 §4.2 流程 `[PATCH-FE]` 留痕） | `sed -n '50,59p' vue-assetmanagement/vitest.config.ts` | 文档与配置逐值一致 | 已确认/待修 |

### 2.4 不采纳/排除项（汇总三报告，均经本融合复核维持排除）

| # | 来源 | 主张 | 排除理由（复核证据） |
|:--|:--|:--|:--|
| X-01 | main N-01 | Serializer「触碰数据库」违规 | `SlugRelatedField` 的 `queryset` 为 DRF 关系字段入参校验/FK 解析声明，非 Serializer 执行写库（五层架构 Serializer 禁 DB 操作指 perform 写库） |
| X-02 | main N-02 | 员工/部门批量删除缺 user → 行级校验缺口 | G-6/G-7 登记的 system_admin-only 豁免名单（`check_duplicate_invariants.py` G6_G7_EXEMPT），两 ViewSet `batch_delete` 走 `IsSystemAdmin`，无越权面 |
| X-03 | main N-03 | security-scan 三条明文凭据 = SC-1 违规 | 系「已轮换泄露凭据黑名单」用于回流检测（:302-323 实核），非在用 AK/SK；其暴露面问题已由 M-11 承接 |
| X-04 | main N-04 | 前端路由未列读路由默认放行 | guards.ts `checkRoleAccess` M-19 刻意设计：写语义路由兜底 deny + `guards-write-deny.spec.ts` 不变量，真实授权边界在后端 |
| X-05 | main N-05 | `clear_database.py` 动态表名 SC-4 违规 | 白名单 + `psycopg.sql.Identifier` 双闸（:134-147），符合 SC-4 |
| X-06 | TraeCode fp-1 | `urls.py` 裸 `Response({'status':…})` 契约旁路 | 系 `apps/assetmanagement/urls.py:115-144` 模块 docstring 内示例（:144 闭合三引号），非运行时代码（AtomCode 独立同判） |
| X-07 | TraeCode fp-2 | `GroupedAssetTable.vue` #4a90e2 硬编码 | 位于 :409-412 注释（对比度论证留痕），实际样式用 `var(--color-primary)` |
| X-08 | TraeCode fp-3 | 前端 `pageSize` 驼峰混用 | 命中均为 Element Plus 分页组件 prop 与测试夹具；API 层发送 `page_size` 蛇形（`utils/pagination.ts` 单一默认值源） |
| X-09 | TraeCode fp-4 | `api/foundAsset.ts` 与 `wasteAsset.ts` URL 重复 | 系 `/assets/found-assets/` 与 `/assets/waste-assets/` 两个不同端点 |
| X-10 | AtomCode | SC-5/SC-6 判违规 | N/A：全仓无文件上传端点、无导入实现（`request.FILES`/`FileField` 零命中），红线无适用对象；`FILE_UPLOAD_MAX_MEMORY_SIZE` 10MB 配置在位（base.py:175-179，预备性） |
| X-11 | 本融合 | 对 AtomCode/TraeCode 两处的数字更正 | FR-5 最大行（C4：318/136 → 权威 411）与 TraeCode 审计票「backend-testing-rules v1.8」版本号笔误（实为 frontend-testing-rules v1.8 / backend-testing-rules v1.6）——更正留痕，不立问题条目 |

---

## §三 分域融合结论

| 分域 | 三报告一致性 | 融合结论 |
|:--|:--|:--|
| 资产状态机（CT-3） | 3/3 一致 | 合规。22 转换 cell + 终态与规则表逐条一致；0 未声明旁路；P0-1 Serializer 防上膛在位；测试锚齐（48 测试函数 + parametrize 全表）。**无需修复** |
| 合同状态机 | 3/3 一致 | FSM 本身合规（8 态单向链/AUD-15/脏数据 []）。**但合同支付域缺审计 → M-05（P1）**，为三报告中仅一份发现的业务 P1 |
| API 响应契约 4 项 | 3/3 一致 | 4/4 通过（旁路 0/枚举 8/8/分页 0 混用/日期 0 组件旁路）；显示层时区渲染风险 → M-15 [推测] |
| 安全红线（SC） | 3/3 一致（口径互补） | 业务代码 0 违规；SC-5/6 N/A；CI 侧 3 个加固缺口 → M-11/M-12/M-18 |
| RBAC/行级隔离 | 3/3 一致 | 接线完整；防退化缺口 → M-06（双口径）/M-07（user 可选） |
| 操作日志/审计 | 2/3（main+AtomCode 互补） | 资产/用户域合规；合同支付域缺审计（M-05）；失败容错语义待拍板（M-08）；通知死信（M-25） |
| 前端质量 | 3/3 一致（数字互补） | 语法纪律全绿；测试资产薄弱（M-04，68 个 0% 页面）+ 样板重复（M-14）+ F11 守卫缺口（M-21）+ 令牌杂项（M-20/M-24/M-26） |
| CI/工程化 | main 独深 | 门禁矩阵总体健全；5 个闭合/口径缺口（M-01/M-09/M-10/M-12/M-17/M-18）+ 护栏自洽 2 项（M-02/M-17） |

---

## §四 修复计划（6 批次）

> 排序原则：①护栏/门禁自身正确性优先（假绿比红更危险）；②业务 P1（M-05）独立成批；
> ③后端架构类按域分批且以「先补回归测试」为先导；④前端测试资产与组件重构合并推进；
> ⑤低文档/低风险杂项收尾。所有批次不触发 §1.3 [HALT] 红线（均为非重构级局部变更，
> M-03 除外——其按 DR-6 属结构性扁平化，需单批独立评估）。

### 批次 1：护栏与门禁自身正确性（建议最先）

| 项 | 范围 | 依赖 | 验证 |
|:--|:--|:--|:--|
| M-02 | `check_duplicate_invariants.py` 复用 `line_metrics.read_text` + BOM 证红自测 | 无 | BOM 夹具先红后绿；G 护栏现实仓仍 PASS |
| M-01 | 部署 gate 回查名单纳入 `guard-summary`/`migration-check`（或 required checks 决策）；`migration-check` 增 `push` 触发 | 无（若选 required checks 则需仓库设置权限） | `test_ci_orchestration.py` 新断言先红后绿；失败护栏 run 验证 gate 拒绝 |
| M-18 | `security-summary` 纳入 `weekly-report`（schedule 分流） | 无 | 模拟 weekly-report 失败 run 断言汇总红 |

### 批次 2：合同支付域审计（业务 P1，仅 1 条）

| 项 | 范围 | 依赖 | 验证 |
|:--|:--|:--|:--|
| M-05 | `contract_service.py` 4 方法补审计（operator 签名下传）+ View 3 处传参 + 4 组审计断言测试 | 无 | 审计断言测试全绿（CT-4 回归屏障）+ 全量 pytest + 两契约快照不回归 |

### 批次 3：后端架构（按域分批，先低风险域）

| 项 | 范围 | 依赖 | 验证 |
|:--|:--|:--|:--|
| M-06 | 8 处类属性 `queryset` 收敛为 Selector 委托（试点：asset_type/contract 字典域 → 其余域） | 每域先行补行级隔离断言 | 各域 RBAC 断言绿 + 全量 pytest |
| M-07 | `create_outasset` user 改 kw-only 必填 | 无 | 「忘传即报错」单测先红后绿 + 出库域测试绿 |
| M-08 | 审计失败语义拍板（回滚 vs 补偿队列）+ 外层包装补指标 | 需人工拍板（二选一） | 失败路径测试（回滚/入队断言）+ 指标断言 |
| M-03 | 批量删除链扁平化（View→Service→Selector） | 建议 M-06 先行（同域取数口径先统一）；13 域接线，快照锁定 | 两快照测试全绿 + 深度断言 ≤3 + 全量 pytest（高风险，独立 PR/批次） |

### 批次 4：前端测试资产与组件重构

| 项 | 范围 | 依赖 | 验证 |
|:--|:--|:--|:--|
| M-04(a) | 0% 覆盖 68 页分三档补测：①高流量（Dashboard 系列/AsideMenu/NotificationBell）②详情页 ③其余 | 无 | 各档 `npm run test:coverage` 阈值绿 |
| M-14 | 4 管理页抽统一列表页组件 + composable（逐页替换，与 M-04 补测合并） | M-04(a)① 先行（新组件需测试覆盖） | 各页交互测试绿 + lint:ci |
| M-04(b) | 棘轮按 T14 手工上移（补测后） | M-04(a) 完成 | 上移后 CI `frontend-test` 绿 |
| M-20/M-26 | `usePaginationSearch` 拆分（199→<200 留余量）；`Format.ts:19` 旧名注释 | 无 | 护栏 composables 段绿 + rg 旧名零命中 |
| M-21 | 7 文件改引统一错误 helper + ESLint 禁 `axios` 包 + LogIn px 令牌化 | 无（helper 先行） | `npm run type-check && npm run lint:ci` + 视图 spec |
| M-13 | 启用 `no-floating-promises` 评估（临时规则跑一遍） | 建议 M-21 后（同属 ESLint 面） | 规则输出 0 命中→销账；有命中→按输出补 catch 并回立条目 |
| M-24 | 滚动条 6 处 hex 令牌化 | 无 | 双主题目检 + lint:ci |

### 批次 5：CI 流水线与口径

| 项 | 范围 | 依赖 | 验证 |
|:--|:--|:--|:--|
| M-09 | CI type-check 统一为 `npm run type-check`（或登记差异） | 无 | CI 与本地双绿 |
| M-10 | `frontend-test` 第二次覆盖运行改专项路径/删除 | 无 | CI 绿且时长下降 ~65s |
| M-11 | secret-scan 补 yaml 覆盖 + 黑名单哈希指纹化 | 无（与 M-01 同属门禁面，可同批） | 注入 yml 夹具断言红 |
| M-12 | §6 执行状态补记 2 条例外及复审周期 | 无 | 文档核对 |
| M-17 | 前端计数函数收敛 `line_metrics` + 台账分区感知 | 建议与 M-02 同批（同属护栏自洽） | 计数函数单测 + 双护栏同值比对 |

### 批次 6：文档与低风险杂项（可合并一批杂项）

| 项 | 范围 | 验证 |
|:--|:--|:--|
| M-15 | 日期渲染产品口径拍板（推荐 Asia/Shanghai 固定渲染，改动集中 Format.ts） | 双时区目检 + Format 单测跨时区用例 |
| M-16 | 本地残留测试库恢复步骤文档化 | 按文档恢复后全量 pytest 绿 |
| M-19 | `asset_view.py` 拆分（建议并入批次 3 M-03 同域评估） | 护栏 <480 |
| M-22 | B1 补记「message 值不固定」 | 文档核对 |
| M-23 | dev/test console 挂 `TraceIDFilter`（或豁免登记） | 本地日志含 trace_id |
| M-25 | 通知死信告警接线（最低要求：关键字告警） | 死信分支测试断言 |
| M-27 | `frontend-testing-rules.md` §六棘轮值同步 21.1/19.0/18.6/21.3 | 文档与配置逐值一致 |

**批次依赖图**：批次 1 独立 → 批次 2 独立 → 批次 3（M-06→M-03；M-07/M-08 独立）→ 批次 4（a→b 棘轮；M-21→M-13）→ 批次 5（M-17 可与批次 1 合并）→ 批次 6 收尾。
预计节奏：批次 1+2+5+6 为小改动（合计 <3 天工作量级）；批次 3 按域 2~3 个子批；批次 4 按覆盖档位 3 个子批。

---

## §五 台账终态与统计

| 级别 | 数量 | 条目 | 状态分布 |
|:--|:--|:--|:--|
| P0 | 0 | — | — |
| P1 | 5 | M-01 ~ M-05 | 全部已确认/待修 |
| P2 | 13 | M-06 ~ M-18 | 12 已确认/待修 + 1 待复核（M-13，证据降级） |
| P3 | 10 | M-19 ~ M-27 | 全部已确认/待修 |
| 不采纳/排除 | 11 | X-01 ~ X-11 | 维持排除（含 2 处数字/版本更正留痕） |
| **合计** | **28 条问题** | 融合自 3 报告 34 条原条目（去重合并 6 对：AUDIT-002↔P2-02、P3-02↔AUDIT-005、P3-03↔A-01、P2-07 降级、A-02 范围修正、C1 衍生 M-27） | 已修复 0（纯审计） |

**独有发现归属**：M-05 合同支付审计（仅 AtomCode 发现）；M-01~M-04/M-06~M-19 主体（仅 main 发现，本融合全部复核通过，其中 M-01 加重、M-04 扩证 68 文件、M-06 降级、M-07 补证 docstring、M-13 降级）；M-24/M-21 半项（仅 TraeCode 发现，范围/计数经修正）；M-27（融合过程新发现）。

> **时点快照注（2026-11-11）**：本表为审计时点（2026-11-07）统计快照，不回溯改写；批次 1~6 落地后的逐项终态以 `docs/Review/merge-audit-20261107.md` §2 状态列与 `docs/BugFixed/Bug修复活账本.md`（BF-183/BF-184/BF-185/BF-187 等）为准。
>
> **修复回执（BF-188，2026-11-11）**：M-13 评估面（C-14/S7 一次性评估 115 处命中；D13 裁定不启用规则、不新增红线，复审挂 C-14）与 M-21 执行面（独立 ESLint 块闭合 F11 + 4 点守卫收敛 `isApiError` + 6 infra 豁免 + LogIn F4 复核已合规）已收口，终态见本报告 §2 两行状态列、`docs/Review/merge-audit-20261107.md` §2、C-14 与 BF-188。本报告 §五统计表（:203/:206）、§六自审清单与事实边界（:221/:224）以及 M-13/M-21 行的原始描述均为**审计时点历史记载，不回溯改写**；「已修复 0（纯审计）」数字按上条时点快照注保持不变。

---

## §六 评审结论（融合自审）

### 自审清单

- [x] **逐条回查**：3 报告 34 条原条目 100% 独立回查（源码行号/命令输出），无一条仅凭报告原文采信
- [x] **冲突裁决**：5 处冲突（C1-C5）均给出裁决证据与来源标注，未取平均、未和稀泥
- [x] **数字修正留痕**：FR-5 最大值（318/136→411）、TraeCode 审计票版本号笔误、A-02 范围（8+→6 处）、A-01 计数（2→7）均修正并留痕（X-11）
- [x] **降级有理**：M-06（P1→P2，7/8 已覆写 get_queryset + 字典域豁免）、M-13（P2→待复核，4/4 引用点均有 catch）降级均附证据
- [x] **只读纪律**：本融合会话未改动任何业务代码；唯一新增文件为本报告
- [x] **建议可执行**：28 条均含 file:line/symbol 去处 + 回查命令 + 验证方式，修复 skill 可直接接手
- [x] **事实边界**：M-13 标「待复核」（未独立复核全部 floating promise）；M-15 影响面标 [推测]；覆盖率现状数字注明实测环境（系统 Python，工具链对齐 dev.txt）

### 审计票

```markdown
[审计票 - 必填项]
- 读取规范：根 AGENTS.md v3.7.5 + 后端 AGENTS v9.3.3 + 前端 AGENTS v9.9.1
  + backend-business-rules v1.23 + frontend-business-rules v1.5
  + backend-testing-rules v1.6 + frontend-testing-rules v1.8
- CT-1[√] CT-3[√ 规则表逐条一致·未声明旁路 0·合同 FSM 8 态链·支付域缺审计 M-05]
- CT-5[√ 本会话重跑 2398 passed 零失败] CT-7[√ 行数/护栏以护栏 --print 实测为准]
- DR-1[~ M-06 双取数口径/M-08 双审计实现面] DR-5[√ 四护栏 PASS（M-02 BOM 假绿路径除外）]
- SC-1[√ 业务代码 0 命中] SC-3[√ 参数化/白名单] SC-5/6[N/A 无上传/导入端点]
- 跨端契约：4/4 通过（M-15 显示层时区风险 [推测] 单列）
- 红线触发：无
- 建议提交：是（本报告为纯审计产物）

[审计票 - 自检项]
- 测试：CT-2[√ 本次实测 后端 89.55%/Service 98%/前端 .vue 21.19%·余量 0.09pt M-04]
  CT-4[~ 合同支付域 4 写操作无审计断言 M-05] CT-6[N/A 无迁移变更]
- DRY：DR-2[√] DR-3[√] DR-4[~ M-14 四页样板重复] DR-6[~ M-03 批量删除链 6 层]
- 安全：SC-2[√ CI] SC-4[√] SC-7[~ M-12 已登记例外] SC-8[~ M-18 汇总缺周报]
- 可观测性：OC-1~OC-3[√] OC-4[~ M-25 死信无告警] OC-5[~] OC-6[√] OC-7[~ M-23 dev 无 trace_id]
- 融合专项：三报告 34 条逐条复核 | 冲突 5 处全部裁决 | 合并 6 对 | 新增 1 条（M-27）
- AI行为：Fact-1[√]（全部结论附本会话回查证据；[推测] 项显式标注）
- 写作风格：Style-1~Style-3[√]

[融合统计]
- 三报告原条目：AtomCode 5 + main 32 + TraeCode 2 = 39 条（含 main 5 不采纳 / TraeCode 4 误报排除）
- 问题条目：P0×0 / P1×5 / P2×13（1 待复核）/ P3×10 = 28 条
- 不采纳/排除：11 条（X-01~X-11）
```

> 只读纪律确认：本融合会话未改动任何业务代码；产出物仅本文件。


