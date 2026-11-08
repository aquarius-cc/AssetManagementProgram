# 双报告融合审计报告（merge-audit-20261107）

> **日期**：2026-11-07 | **模式**：纯只读审计融合（零业务代码改动）
> **融合来源**（同日期、同规范基线 v3.7.5 的两份独立审计）：
>
> | 来源 | 文件 | 台账规模 | 方法特征 |
> |:--|:--|:--|:--|
> | 报告A（三报告融合版） | `merge-codegraph-audit-20261107.md` | P1×5 + P2×13 + P3×10 + 不采纳×11（M-01~M-27 / X-01~X-11） | 融合 AtomCode/main/TraeCode-KimiK3 三份独立审计，34 条原条目逐条回查 |
> | 报告B（opencode 全项目审计版） | `opencode-codegraph-audit-2026-11-07.md` | P2×7 + P3×10（AUD-B×9 / AUD-F×5 / AUD-C×3） | 五子代理分域（状态机/契约/安全/前端/门禁）+ CodeGraph impact + ponytail 全仓过工程度清单 |
>
> **融合方法**：对报告A的全部 P1/P2 关键主张**逐条独立回查**（本会话 rg/源码直证，见 §1.2）；
> 报告B为本会话逐条产出（自证）；冲突按证据裁决；报告B独有条目续接编号 **M-28~M-45**，
> 保持与报告A的 M-01~M-27 编号连续可交叉引用。AUD-xx ↔ M-xx 影射见 §2.3。
> **状态口径**：纯审计不产生「已修复」；终态仅 已确认/待修、待复核、不采纳（+理由）。

---

## §一 交叉复核与冲突裁决

### 1.1 六处交叉点裁决

| # | 交叉点 | 报告A主张 | 报告B主张 | 本会话复核证据 | 裁决 |
|:--|:--|:--|:--|:--|:--|
| K1 | 状态机未声明旁路 | 「0 未声明旁路（3 处声明例外均带前置守卫）」 | 「旁路 8 处 = 已登记 7 / 未登记 1（seed_grouped_assets.py:218）」 | B 的扫描面含 `management/commands/`，A 未覆盖该目录；seed 命令直写 `in_store` 字面量未走 `create_asset`（业务约束 7 字面义违反），codegraph impact = 本文件+1 测试，无状态完整性危害 | **域差异而非矛盾**：A 结论限于 FSM 调用链（成立）；B 独有发现采纳为新条 **M-28**（P2） |
| K2 | secret-scan 扫描模式 | M-11：模式 `--type py --type js --type ts --type json`（:250 实核）**缺 yaml**，黑名单排 `.github/**` | AUD-C-01：同一 rg 调用**同时无 `-g '!*tests*'` 排除**，按钉 SHA 051d7141 内容复现 5 处测试夹具密码确定性命中 → secret-scan 步骤必红 | 本会话直读 `security-scan.yml:248-256`：`rg -n "$pattern" --type py --type js --type ts --type json -g '!node_modules' -g '!*.lock' -g '!venv/' -g '!dist/' .`——**既无 yaml 类型也无 tests 排除**，两主张同一行代码成立 | **互证互补充**：M-11 维持（yaml 盲区/黑名单面）；AUD-C-01 采纳为新条 **M-34**（tests 假阳性机理已由 workflow 源码直证；唯一未直证的是 CI 现网 run 实际红绿 → 状态「已确认机理/待复核现网」，须 `gh run list` 直证） |
| K3 | var() 回退值口径 | M-24/X-11：`#409eff/#f5f7fa` 系 var() 回退值「合规形态，不计」 | AUD-F-03：`AssetTypeChildList.vue:33` 的 `var(--table-header-bg, #f5f7fa)` 「低风险硬编码，建议移除回退字面量」 | 两处同形态（CSS 变量缺失回退），判定差异仅为处置力度 | **口径统一**：var() 回退值按 M-24 口径属低风险渐进项，收编为 **M-43**（关联 M-24 同批令牌化，不单独成批） |
| K4 | 合同 FSM 测试口径 | 「测试锚齐（48 测试函数 + parametrize 全表）」 | 「合法边 FSM 级直测仅 1/7，CT-3 由集成链 test_contract_view_api.py:569-603 满足，非缺测」 | B 两条均为[√]实读（test_contract_fsm.py:76-78 参数化仅 purchasing→purchase_finished；集成链存在） | **无冲突、互补**：CT-3 双双满足；低层直测灵敏度建议保留为 **M-39**（P3） |
| K5 | 全量门禁数字 | A（C5 裁决）：2398 passed / 89.55%（工具链对齐 dev.txt） | B：2398 passed / 89.55% / Service 98.36%（复跑口径）/ stores 96.83% / 前端 2542 passed | 两会话独立实测同值 | **收敛一致**，互为复证；B 独有的 feishu 波动用例采纳为 **M-31**（P2） |
| K6 | BOM 假绿路径与 line_metrics 收敛 | M-02：护栏 `read_text` 解码序缺 `utf-8-sig`；M-17：前端护栏内联第二份计数函数 | B 未扫护栏代码（B 的扫描面为业务域+ketentuan 维度），护栏自洽问题零覆盖 | 本会话直读 `check_duplicate_invariants.py:41`：`for encoding in ("utf-8", "gbk")`——**BOM 假绿缺口实核成立** | **A 独有发现全盘采纳**（M-01/02/17 均复核过）；补注：B 侧 `check_file_length_guard.py` 权威口径本身无此缺陷（其 read_text 系另实现） |

### 1.2 报告A关键主张本会话抽验明细（全部通过）

| 主张 | 回查证据（本会话命令 → 结果） |
|:--|:--|
| M-02 BOM 假绿 | `rg "read_text\|utf-8" check_duplicate_invariants.py` → `:41 ("utf-8","gbk")` ✅ |
| M-05 支付域 4 写方法 | `rg "def (add\|delete\|approve)_payment_record"` → :214/265/474/509 ✅（方法体无 GenericAuditService，与 A 逐行核读一致） |
| M-07 user 可选守卫 | `rg "create_outasset\|user is not None\|ensure_asset_visible" out_asset_service.py` → :45/56-57/340 ✅ |
| M-09 CI type-check 分叉 | `rg "vue-tsc" ci.yml` → `:384 npx vue-tsc --noEmit`（本地 = `vue-tsc --build`）✅ |
| M-10 重复覆盖率运行 | `rg "test:coverage" ci.yml` → :454/:456 两连跑 ✅ |
| M-11/M-34 扫描模式缺陷 | `Get-Content security-scan.yml -Skip 247 -First 10` → :250 一行两处缺陷齐证 ✅ |
| M-01 部署 gate 监听面 | `Get-Content ci-cd.yml -Skip 38 -First 8` → `workflows: ["CI Pipeline"]` 单一监听 ✅ |
| M-03 批删链 6 层 | `rg "def batch_delete"` → batch_mixins.py:402 batch_delete / :422 invoke / :167 execute + asset_service.py:316 batch_delete_asset / :323 _delete_one → 6 层链成立 ✅ |
| M-04 棘轮值 | `rg "thresholds\|statements: 21" vitest.config.ts` → :33-58 阈值块 21.1/19.0/…/21.3 ✅（C1 裁决被本会话复证） |

---

## §二 融合问题台账

> 编号规则：M-01~M-27 = 报告A条目（状态经本会话抽验确认，明细以 A 报告 §二 为准，本表收窄为复核摘要）；
> M-28~M-45 = 报告B独有条目（全字段，本会话自证）。两段均含 **终态** 列。

### 2.1 报告A条目复核摘要（M-01~M-27）

| ID | 级别 | 类型 | 位置 | 描述精要 | 本会话复核 | 终态 |
|:--|:--|:--|:--|:--|:--|:--|
| M-01 | P1 | CI 门禁闭合 | ci-cd.yml:40-43 等 | 部署 gate 不含 duplicate-guard/migration-check 回查；migration-check 仅 PR 触发、直推模式下休眠 | :40-43 单一监听直证 ✅ | 已确认/待修 |
| M-02 | P1 | 护栏假绿 | check_duplicate_invariants.py:41 | read_text BOM 解码缺口，G-1~G-8 可被绕过 | :41 直证 ✅ | 已确认/待修 |
| M-03 | P1 | 调用链深度 | batch_mixins.py:402→167 + asset_service.py:316→323 | 批删链 6 层，超 DR-6(≤5)/BR-7(≤3)，13 域接线 | 链路符号定位直证 ✅ | 已确认/待修 |
| M-04 | P1 | 测试资产薄弱 | vitest.config.ts:52-58 | .vue 棘轮 21.1/19.0/18.6/21.3，余量 0.09pt；68 个 .vue 0% 覆盖 | 阈值块直证 ✅（0-覆盖清单以 A 的 coverage-final.json 重算为准） | 已确认/待修 |
| M-05 | P1 | 审计缺失(B7) | contract_service.py:214,265,474,509 | 合同支付 4 写操作无审计，审批痕迹不可追溯 | 4 符号定位直证 ✅ | 已确认/待修 |
| M-06 | P2 | 双取数口径 | assets 等 8 ViewSet 类属性 queryset | 7/8 已覆写 get_queryset，字典域豁免 → DR-1 整洁度问题 | 采纳 A 逐处核读（未见反证） | 已确认/待修 |
| M-07 | P2 | 行级隔离防退化 | out_asset_service.py:49,56-57 | create_outasset user 可选，忘传跳过可见性校验（生产唯一调用方已传） | :45/56-57 直证 ✅ | 已确认/待修 |
| M-08 | P2 | 审计可靠性 | unregisteredaudit 适配器外层 _safe_call_audit | 外层包装无指标；失败容错语义需拍板（回滚 vs 补偿） | 采纳 A/C2 裁决（C2 本身含两轮独立核读） | 已确认/待修 |
| M-09 | P2 | CT-7 口径 | ci.yml:384 vs package.json | CI `vue-tsc --noEmit` ≠ 本地 `--build` | 两行直证 ✅ | 已确认/待修 |
| M-10 | P2 | CI 效率 | ci.yml:453-456 | 同一 test:coverage 连跑两次 | :454/:456 直证 ✅ | 已确认/待修 |
| M-11 | P2 | 密钥扫描盲区 | security-scan.yml:250,313 | 模式缺 yaml + 黑名单排 .github/** | :250 直证 ✅ | 已确认/待修 |
| M-12 | P2 | 依赖审计口径 | security-scan.yml:172-173,216 | 已登记降噪例外（ignore-vuln/omit=dev）需 §6 补记 | 文档级，A 已核读 | 已确认/待修 |
| M-13 | P3级 | floating promise 证据不成立 | main 引 4 处（有 .catch） | A 逐处核读均有 catch → 具体证据不成立，改规则评估 | 采纳 A 复核 | 待复核 |
| M-14 | P2 | 前端 FR-1/FR-2 样板 | RoleManage/AuthUserManage/ContactsView/NotificationList | 4 管理页分页/搜索样板重复，公共件已在位 | 采纳 A 核读 | 已确认/待修 |
| M-15 | P2[推测] | 日期显示时区 | base.py:166-168 / Format.ts | 非东八区浏览器业务日期可能跨日 | 双报告 K4/K5 日期契约一致；影响面保持 [推测] | 已确认/待修 |
| M-16 | P2 | 本地可复现性 | backend conftest | main 会话残留测试库 2079 setup errors（环境差异非代码缺陷） | 采纳 A（B 侧会话无残留，旁证） | 已确认/待修 |
| M-17 | P2 | LT-1/DR-1 护栏自洽 | check_frontend_invariants.py:179-259 | 内联第二份计数函数 + 台账不分区 | 采纳 A 核读（K6 复核无反证） | 已确认/待修 |
| M-18 | P2 | CI 汇总完整性 | security-scan.yml:364 | security-summary 未纳入 weekly-report | 采纳 A 核读 | 已确认/待修 |
| M-19 | P3 | 规模余量 | asset_view.py 484 行 | 距上限 16 行（护栏权威值，B 侧同值复证） | 一致 ✅ | 已确认/待修 |
| M-20 | P3 | 规模余量 | usePaginationSearch.ts 199 行 | 距 FR-6 上限 1 行 | B 护栏同值复证 ✅ | 已确认/待修 |
| M-21 | P3 | F11 执行缺口+令牌 | 7 个 .vue 直导 isAxiosError 等 | eslint 未禁 axios 包；LogIn px 偏离 F4 | 采纳 A（C3 裁决已修正计数） | 已确认/待修 |
| M-22 | P3 | 文档口径 | core/mixins.py:111,137,206 | message 为展示文案非 "success"，B1 补记 | 采纳 A 核读 | 已确认/待修 |
| M-23 | P3 | OC-2 环境差异 | base.py:346-350 | dev/test console 无 trace_id filter | 采纳 A 核读 | 已确认/待修 |
| M-24 | P3 | 设计令牌 | global-scroll.scss:8-19 | 6 处裸 hex（范围经 A 修正） | 采纳 A | 已确认/待修 |
| M-25 | P3 | 通知死信 | notification_service.py:99-139 | 死信仅日志无告警/落库接线 | 采纳 A 核读 | 已确认/待修 |
| M-26 | P3 | 文档漂移 | Format.ts:19 | 注释引用旧名 outassetStatusMapping | 采纳 A | 已确认/待修 |
| M-27 | P3 | 文档漂移 | frontend-testing-rules.md §六:43 | 棘轮文档值 12.9 系旧基线，配置实为 21.1/19.0/18.6/21.3 | 与 K1/M-04 数字互证一致 ✅ | 已确认/待修 |

### 2.2 报告B独有条目（M-28~M-45，全字段）

| ID | 级别 | 类型 | 位置 (file:line / symbol) | 来源 | 描述与核实结论 | 修复建议 | 回查命令 | 建议验证方式 | 状态 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| M-28 | P2 | 状态机旁路(未登记) | apps/assetmanagement/management/commands/seed_grouped_assets.py:218 | B·AUD-B-01 | demo seed 命令 `Asset.objects.create(asset_current_status="in_store")` 未走 `create_asset`（业务约束 7 唯一入口），字符串字面量非法枚举引用（B9/BR-3），无创建审计。缓解：目标值=模型默认 in_store 无完整性危害；本域其余 7 处旁路均已登记（K1 裁决域差异） | 二选一：① 改走 `create_asset` 或至少换 `Asset.AssetStatus.IN_STORE` 枚举；② 在 backend-business-rules「特殊回退操作」表登记 demo 注入豁免行。与产品侧拍板 | `rg -n "asset_current_status" asset_management_backend/apps/assetmanagement/management/commands/seed_grouped_assets.py`；`codegraph impact seed_grouped_assets`（=2 符号） | 改造后 `pytest assetmanagement/tests/test_seed_grouped_assets.py` | 已确认/待修 |
| M-29 | P2 | 分层违规(View 内联业务守卫) | apps/usermanagement/views/role_view.py:87-101 | B·AUD-B-02 | `RoleViewSet.destroy` 内联删除守卫（is_system 不可删 + 已分配用户 400）+ 直接 ORM 查询，绕过 RoleService；同文件 perform_* 均 Service 路由，口径不一致 | 下沉 `RoleService.delete_role()` + `@transaction.atomic`，View 仅参数解析 | `codegraph node RoleViewSet.destroy`；`rg -n "is_system" apps/usermanagement -g "!*migrations*" -g "!*tests*"`（确认守卫无 Service 版实现） | 下沉后跑 test_role_service.py + 按需补守卫负面用例 | 已确认/待修 |
| M-30 | P2 | DR-1 双实现+分层 | apps/usermanagement/department_serializers.py:151-235 ↔ services/department_service.py:230-258 | B·AUD-B-03 | 部门移动校验（循环引用+层级上限）双实现：Serializer 版锁外读 DB 且无 `select_for_update`，error_code 与 Service 分叉（纯文案 dict vs CIRCULAR_REFERENCE 等）；codegraph impact `_validate_move_hierarchy` = 17 符号（含 11 测试锚） | Serializer 只做格式校验，跨实体业务校验收敛 Service 单实现；或双闸保留则两处注释声明意图并统一 error_code | `codegraph impact _validate_move_hierarchy` | 收敛/对齐后 `pytest apps/usermanagement/tests/test_department_service.py`（12 用例锚在位） | 已确认/待修 |
| M-31 | P2 | 回归稳定(CT-4) | docker/feishu-webhook/test_app.py::test_unknown_path_404 | B·AUD-B-04 | 覆盖率专项 ×4 中 1 跑失败（404 波动），复跑通过 4/5；判定波动用例非环境问题，疑似夹具时序/端口耦合；裂纹未阻断门禁但 CT-4 要求回归屏障 | 连跑 N 次定位失败模式 → 补确定性夹具（端口/时序注入）或标注 `@pytest.mark.flaky` 并登记 | `rg -n "test_unknown_path_404" docker/feishu-webhook/test_app.py` | 同用例连跑 3 轮绿+记录 | 已确认/待修 |
| M-32 | P2 | 竞态保护缺失+FR-2 双实现 | src/stores/notificationStore.ts:40-56 ↔ composables/useNotification.ts:141 | B·AUD-F-02 | `fetchNotifications` store/composable 双实现（CodeGraph impact 双定义各 8 影响符号）；store 版无 seq 守卫/并发去重——多事件触发路径（NotificationList 6 处 + NotificationBell 双通道）存在过期响应覆盖风险；19 个实体 store 走 createEntityStore + auditLog/dashboard 自建守卫，本 store 是唯一裸奔） | 二选一：store 版补 listRequestSeq 序号守卫（范式同 auditLogStore:38-42）；或收敛 createEntityStore/usePagedList 范式并消双实现 | `codegraph impact fetchNotifications`；`rg -n "fetchNotifications" src/views/NotificationList.vue src/components/commoncomponents/NotificationBell.vue` | 竞态用例（双请求交错断言后写不覆盖新写）+ `npm run test:coverage` 相关 spec 全绿 | 已确认/待修 |
| M-33 | P2 | 状态映射游离(G-3 精神) | src/components/componentsdetails/detils/ContractPaymentRecord.vue:72,180-184 | B·AUD-F-01 | 支付记录审核状态内联映射（待审核/已审核/已删除）与 statusMapping.APPROVAL_STATUS_MAP 标签用语不一致；真值源 contract.ts:76 字面量联合类型，未入类型化枚举；G-3 护栏仅锁 Format 资产状态不拦该域 | 映射收编 statusMapping.ts 增 `PAYMENT_STATUS_MAP` + PaymentStatus 枚举；模板字面量比较改常量 | `codegraph node ContractPaymentRecord` | `npx vitest run src/components/componentsdetails/__tests__` + rg 内联映射零命中 | 已确认/待修 |
| M-34 | P2 | CI 扫描假阳性（机理已证/现网待复核） | .github/workflows/security-scan.yml:250（PATTERNS 循环同段） | B·AUD-C-01 | workflow :250 的 `rg -n "$pattern" --type py --type js --type ts --type json -g '!node_modules' -g '!*.lock' -g '!venv/' -g '!dist/'` **无 `!*tests*` 排除**：按钉 SHA 051d7141 内容复现 5 处夹具密码命中（config/tests/test_base_settings_guard.py:25 等）→ `FOUND=1 → exit 1`，secret-scan 步骤该版本必红；CI 现网 run 实际红绿未直证（本环境无 GitHub 连通）——历史账面「2026-10-01 双 audit 归零」与该机理存在时间线矛盾，故存疑。与 M-11 同行互证 | ① `gh run list --workflow security-scan.yml` 直证最近 secret-scan conclusion；② 模式追 `-g '!*tests*'`（或 tests 命中降级 warn 不阻断）；③ 员工夹具密码非密钥判读规则登记 PR 模板 | `Get-Content .github/workflows/security-scan.yml | Select-Object -Skip 247 -First 10`；`gh run list --workflow security-scan.yml`（网络可用时） | 步骤 ① 输出直证 + 注入 tests 夹具 yml/py 断言修复后通过 | 已确认机理 / 待复核现网 |
| M-35 | P3 | 死代码文件 | asset_management_backend/core/validators.py:17-100 | B·AUD-C-02 | 4 个校验函数（validate_asset_code/validate_phone_number/validate_id_card/validate_non_negative_number）生产零引用（rg 全仓剔除自身后仅命中 docstring 与定义；含测试仍零引用） | 删除整文件（同步删自测段），pytest 全量,ruff/mypy兜底 | `rg -n "validate_asset_code" asset_management_backend -g "*.py"` | 删除后全量 pytest + 门禁绿灯 | 已确认/待修 |
| M-36 | P3 | 死依赖 | backend requirements + vue package.json | B·AUD-C-03 | ponytail 依赖扫描：requests/urllib3/chardet（后端全仓零 import，连 scripts/loadtest 亦无）+ less/less-loader（0 个 .less 文件）+ jsdom（vitest environment=happy-dom）+ lodash-es（仅 useDebouncedSearch 一个 debounce 用途）。[推测] urllib3 或为传递 pin 守卫 | 逐包 npm/pip remove 前跑全量门禁兜底；urllib3 留待复核 pip-audit 口径后再删（或为传递 pin 守卫） | `rg -n "requests\|urllib3\|chardet" asset_management_backend -g "*.py"` · `rg "lodash\|less\|jsdom" vue-assetmanagement/src --glob "!*config*"` | 每删一包全量测试（前后端各一轮） | 已确认/待修 |
| M-37 | P3 | 文档漂移(README 图缺边) | README.md:218-241 | B·AUD-B-06 | README 状态机导航图缺 3 个 to_damaged 入口边 + 3 个 reject 目标 + cancel 边 + 双入口共边标注，与 transitions.py 陈旧脱节 | 补边或加「完整规则见 backend-business-rules.md §三」导航免责声明 | `rg -n "to_damaged\|cancel" README.md` | 文档核对 | 已确认/待修 |
| M-38 | P3 | 业务口径[待确认] | apps/assetmanagement/services/repair_asset_service.py:253-255 | B·AUD-B-08 | `repair_done` 的 physical_grade 更新为可选（调用方不传即不更新，None 落库留痕），与约束 4「维修完成必须更新」字面语义弱化；[推测] 宽容历史数据的刻意设计 | 产品拍板：约束 4 口径落文档「有值必验、缺值可略」，或把空值升级为必传校验 | `codegraph node repair_done` | 拍板后改文档或校验逻辑 + 补用例 | 已确认/待拍板 |
| M-39 | P3 | 合同 FSM 低层直测 | assetmanagement/tests/test_contract_fsm.py:76-78 | B·AUD-B-07 | 合法边 7 条仅 1 条 FSM 级直测参数化；CT-3 由集成链 test_contract_view_api.py:569-603 满足非缺测（K4 裁决互补） | `_validate_transition` 合法边参数化为 7 条，提升表漂移单测先红灵敏度 | `rg -n "test_edges_match_transition_table\|_validate_transition" assetmanagement/tests/test_contract_fsm.py` | 参数化后 test_contract_fsm 全绿 | 已确认/待修 |
| M-40 | P3 | DRY 跨文件同构块 | core/audit_log_filters.py:66-102 ↔ apps/assetmanagement/operation_log_filters.py:59-102 | B·AUD-B-05 | `_parse_date`/`_validate_operation_type`/Invalid* 异常类 37 行逐字同构复制，唯一消费面差异可收敛 core 侧共用 helper | 抽 core 共用 helper（或与 M-17 收敛批次合并） | `rg -n "_parse_date" asset_management_backend --glob "*.py"` | 抽取后 diff 输出等价 + 双域过滤测试绿 | 已确认/待修 |
| M-41 | P3 | View 直查 ORM（部分带注释豁免） | role_view.py:209-217 / employee_auth_mixin.py:61-74 / contract_view.py:114-116、storage_view.py:86-96 | B·AUD-B-09 | UserRoleViewSet.get_queryset 手写过滤链未走 Selector（usermanagement 无 RoleSelector）；employee_auth_mixin 在 View 层 `AuthUser.objects.get`；contract/storage 为全局资源已注释豁免（合规形态，仅挂账） | Role 域补 `RoleSelector`（与 M-29 同批）；authuser 域挪进 PermissionService 助手；contract/storage 维持挂账或补软删 base 单点化 | `rg -n "objects\.filter" apps/usermanagement/views -g "*.py"` | 补 Selector 后跑相关 view 测试 | 已确认/待修 |
| M-42 | P3 | 设计令牌逸出[推测] | composables/useChartTheme.ts:37-47,81-83；utils/statusMapping.ts:232-236 | B·AUD-F-04 | 8 个派生色（PIE_EXTRA `#8B5CF6`/`#6B7280`、divider `#1d1e1f/#ffffff`、tooltip rgba、3 个状态散点色）不在 F1-F2 四色令牌集内；[推测] 图表 palette 派生色豁免口径无书面确认 | 设计/产品确认图表 palette 豁免口径（书面化）或收编进 variables.css 令牌 | `rg "#8B5CF6\|#13C2C2\|#F759AB\|#FA8C16" vue-assetmanagement/src` | 确认后文档化 | 已确认/待拍板口径 |
| M-43 | P3 | var() 回退字面量（口径与 M-24 统一） | componentsdetails/components/AssetTypeChildList.vue:33 | B·AUD-F-03（K3 裁决） | `var(--table-header-bg, #f5f7fa)` 属变量缺失回退形态，与 M-24 对 global-reset.scss 的口径一致（渐进项，不计硬违规），仅该变量确已在 variables.css 定义时可移除字面量 | 与 M-24 同批令牌化时顺带清理 | `rg -n "f5f7fa" vue-assetmanagement/src` | 双主题目检 | 已确认/待修（并入 M-24 批） |
| M-44 | P3 | 路由守卫前瞻加固[推测] | src/router/guards.ts:84-87 | B·AUD-F-05 | roleWhitelist 用 `startsWith(prefix)` 无 path-boundary 保护：未来新增以现有白名单为前缀的路由会被误命中；当前路由集零影响；与 X-04（默认读放行系刻意设计+负向断言）不冲突，属另一个独立加固面 | 白名单前缀判定改为「prefix === path 或 prefix + '/'」边界匹配 + 负向断言侧 spec 展开 | `codegraph node guards`；`rg -n "startsWith" src/router/guards.ts` | guards 负向断言（模拟新路由）先红后绿 | 已确认/待修 |
| M-45 | P3 | ponytail 死代码批量（M-35/M-36 之外） | date_utils.py 全文 / string_utils.py:11-50,73-99,121-139 / Image.ts:54-158 / usermanagement/providers.py:44-108 / core/models.py:107,135-155 / assetmanagement/interfaces.py:63-117 / utils/reactiveAccess.ts:18-42 | B·§三F（ponytail-audit+review） | ① date_utils 5 个日期函数生产零调用（唯一消费是自测+re-export，实际解析用两处本地 _parse_date）；② string_utils 5/6 函数死代码（唯一活的 mask_phone_number）；③ Image.ts 5/7 死导出（唯一活的 lazyLoadDirective，main.ts:10 注册）；④ providers Mock 三件套 docstring 声称测试用、实际零引用；⑤ BaseModel.restore()/hard_delete() 全仓生产零调用（all_objects 仅 role_service.py:225 一处可平替）；⑥ EmployeeProvider 注册中心唯一产品 + Mock 已死（yagni）；⑦ reactiveAccess readReactive/readStoreValue 三元访问语义双实现。**净可减 ~-570 行（-7 依赖单列 M-36）**；每条均经 rg 全仓剔除自身/测试复核零外部调用 | 按模块分小批删除/坍缩；每批全量前后端测试兜底；interfaces 注册中心若删需同步 apps.py ready 钩子 | `rg -n "restore\(\)" asset_management_backend -g "*.py"` 等（各条独立命令已入 B 报告） | 每小批全量 pytest + 前端 type-check/lint/test / ruff mypy | 已确认/待修（低风险批量，每批可独立） |

### 2.3 来源影射表（AUD-xx ↔ M-xx）

| AUD | →M | AUD | →M | AUD | →M |
|:--|:--|:--|:--|:--|:--|
| AUD-B-01 | M-28 | AUD-B-06 | M-37 | AUD-C-01 | M-34 |
| AUD-B-02 | M-29 | AUD-B-07 | M-39 | AUD-C-02 | M-35 |
| AUD-B-03 | M-30 | AUD-B-08 | M-38 | AUD-C-03 | M-36 |
| AUD-B-04 | M-31 | AUD-B-09 | M-41 | AUD-F-01 | M-33 |
| AUD-B-05 | M-40 | AUD-F-02 | M-32 | AUD-F-03 | M-43 |
| — | — | AUD-F-04 | M-42 | AUD-F-05 | M-44 |

### 2.4 排除项

报告A X-01~X-11 维持原排除（本会话无新增反证）。报告B侧无新增排除项；其「不采纳+理由」条目（AUD-B-05 记录性等）已在融合中按登记取舍重新分档（M-40 为 P3 已确认/待修，属处置力度差异，非新证据）。

---

## §三 分域融合结论（升级版）

| 分域 | 报告A | 报告B | 融合结论 |
|:--|:--|:--|:--|
| 资产状态机 CT-3 | 规则表一致，0 未声明旁路（限 FSM 调用链） | 22 边零漂移；旁路 8 处=已登记 7/未登记 1 | 合规 + **1 处未登记 demo 旁路（M-28，P2）**；业务约束 1-7 全落实（双报告互证） |
| 合同状态机 | FSM 合规；合同支付域缺审计（M-05 P1） | 8 态链一致/异常收敛/脏数据 []；低层直测 1/7（P3） | FSM 合规；**M-05 为全链最高优先事项**；M-39 P3 建议在案 |
| 跨端契约 4 项 | 4/4 通过（M-15 时区渲染风险） | 4/4 逐项直证（成功响应唯一入口/枚举 8/8/分页 0 混用/日期 +08:00） | **4/4 双报告互证通过**；M-15 显示层口径保持 [推测] |
| 安全红线 SC | 业务 0 违规；CI 3 加固缺口 | 12 项通过；SC-1/3/4 干净直证 | 业务面干净；**CI 面 4 个缺口合并**：M-11（yaml盲区）+ M-34（tests 假阳性）+ M-01（部署 gate 回查面）+ M-18（周报汇总） |
| RBAC/行级隔离 | 防退化缺口 M-06/M-07 | B11/B12/B14 全通过 + G 护栏 PASS；usermanagement 3 处分层违例 (M-29/M-30/M-41) | 隔离面接线完整；**usermanagement 是唯一多违例模块**（4 条，与 M-06 同域分批） |
| 操作日志/审计 | 资产/用户域合规；M-05/M-08/M-25 | B7 抽查通过；审计留痕 8 组批删接线全绿 | 合规 + M-05/M-08 在案 |
| 前端质量 | M-04（68 个 0% 页面）/M-14/M-21 等 | 语法纪律全绿；规模护栏全 PASS；M-32/M-33 竞态/映射两处 P2 + 令牌杂项 | **最大短板 = 测试资产（M-04）**；语法/契约/规模面健康 |
| CI/工程化 | M-01/09/10/12/17/18 | M-34 secret-scan 疑点；BOM 假绿（M-02） | **护栏/门禁自身正确性是修复最高优先级**（假绿比红更危险） |
| 死代码/过工程度 | 三源仅 TraeCode 2 条 | ponytail 净 ~-570 行、-7 依赖 | **M-35~M-36/M-45 低风险批量清理项**，批次末段执行 |

---

## §四 融合修复计划（批次升级版，含修复顺序）

> 排序原则（承 A）：①护栏/门禁自身正确性最先（M-02 假绿、M-34 扫描模式）；②业务 P1（M-05）独立成批；
> ③后端架构按域分批且以「先补回归测试」为先导（usermanagement 域合并一子批）；④前端测试资产与组件重构合并推进；
> ⑤CI 及依赖批次后置；⑥文档/低风险/拍板项收尾。**已确认需人工拍板的 3 项前置**：M-08（失败语义）、M-38（成色口径）、M-42（palette 豁免口径）。

### 批次 1：护栏与门禁自身正确性（最先，零业务代码）

| 顺序项 | 内容 | 依赖 | 验证 |
|:--|:--|:--|:--|
| M-02 | check_duplicate_invariants 复用 line_metrics.read_text + BOM 证红自测 | 无 | 先红后绿；现实仓 G 护栏仍 PASS |
| M-17 | 前端护栏计数函数收敛 line_metrics + 台账分区感知 | 与 M-02 同批（同属护栏自洽） | 计数单测 + 双护栏同值 |
| M-01 | 部署 gate 回查名单纳入 guard-summary/migration-check；migration-check 增 push 触发 | 无 | test_ci_orchestration 新断言先红后绿 + 失败 run 验证 gate 拒绝 |
| M-18 | security-summary 纳入 weekly-report | 无 | 模拟 weekly-report 失败 run 断言汇总红 |

### 批次 2：合同支付域审计（业务 P1）

| 顺序项 | 内容 | 依赖 | 验证 |
|:--|:--|:--|:--|
| M-05 | contract_service 4 方法补审计 + View 传参 + 4 组审计断言测试 | 无 | 审计断言绿（CT-4）+ 全量 pytest + 契约快照不回归 |

### 批次 3：后端架构（按域分批；usermanagement 域合并）

| 顺序项 | 内容 | 依赖 | 验证 |
|:--|:--|:--|:--|
| M-06 | 8 处类属性 queryset 收敛 Selector（字典域试点先行） | 每域先补行级隔离断言 | 各域 RBAC 断言 + 全量 pytest |
| M-29 | RoleViewSet.destroy 守卫下沉 RoleService.delete_role | 无 | 删除守卫负面用例 + role 域测试 |
| M-30 | 部门移动校验收敛 Service 单实现（或双闸意图注释 + error_code 对齐）[二选一拍板] | M-06 同域先行 | test_department_service 12 锚 |
| M-41 | RoleSelector 新建 + employee_auth_mixin 查询挪 Service（contract/storage 挂账不批） | M-29/M-30 之后同域收尾 | 相关 view 测试 |
| M-07 | create_outasset user 改 kw-only 必填 | 无（独立） | 忘传即 TypeError 先红后绿 + 出库域测试 |
| M-08 | 审计失败语义拍板（回滚 vs 补偿队列）+ 外层包装补指标 | 需拍板 | 失败路径测试 + 指标断言 |
| M-03 | 批删链扁平化（View→Service→Selector，13 域） | M-06 先行（取数口径统一） | 两快照全绿 + 深度断言 ≤3 + 全量 pytest（高风险独立批次） |
| M-28 | seed_grouped_assets 旁路治理（改 create_asset/枚举 或 登记豁免行）[待确认] | 无 | test_seed_grouped_assets 绿 |
| M-31 | feishu 波动用例定位+确定性夹具 | 无 | 同用例连跑 3 轮绿 |

### 批次 4：前端测试资产与组件重构

| 顺序项 | 内容 | 依赖 | 验证 |
|:--|:--|:--|:--|
| M-04(a) | 68 个 0% 页面分三档补测（高流量 Dashboard/AsideMenu 先行） | 无 | 各档 coverage 阈值绿 |
| M-32 | notificationStore 竞态守卫 + 双实现收敛 | 无 | 竞态交错用例 + 相关 spec 绿 |
| M-14 | 4 管理页抽统一列表组件 + composable | M-04(a)① 先行 | 各页交互测试 + lint:ci |
| M-33 | ContractPaymentRecord 状态映射收编 statusMapping | 无 | 组件 spec + rg 内联零命中 |
| M-04(b) | 棘轮手工上移（T14 只升不降） | M-04(a) 完成 | CI frontend-test 绿 |
| M-20/M-26 | usePaginationSearch 拆分 + Format.ts:19 旧名注释 | 无 | 护栏 composables 段绿 + rg 零命中 |
| M-21 | isAxiosError 统一 helper + eslint 禁 axios 包 + LogIn px 令牌化 | 无（helper 先行） | type-check + lint:ci + 视图 spec |
| M-13 | 启用 no-floating-promises 评估 | M-21 后（同 ESLint 面） | 0 命中→销账；有命中→立条目 |
| M-24/M-43 | 滚动条 6 处 hex 令牌化 + var() 回退清理（同批） | 无 | 双主题目检 + lint:ci |
| M-44 | guards 前缀 path-boundary 加固 | 无 | 负向断言先红后绿 |

### 批次 5：CI 流水线、依赖与死代码

| 顺序项 | 内容 | 依赖 | 验证 |
|:--|:--|:--|:--|
| M-09 | CI type-check 统一 npm run type-check | 无 | CI/本地双绿 |
| M-10 | frontend-test 去第二次重复覆盖运行 | 无 | CI 绿且时长 -65s |
| M-34 | secret-scan 模式追 `!*tests*`（或 tests 降级 warn） | 先 gh run list 直证现网 | 注入夹具断言修复前红后绿 |
| M-11 | secret-scan 补 yaml 覆盖 + 黑名单哈希指纹化 | 与 M-34 同 job 同批 | yml 夹具断言红 |
| M-12 | §6 执行状态补记 2 例外及复审周期 | 无 | 文档核对 |
| M-36 | 死依赖清删（requests/urllib3+chardet → less/less-loader → jsdom → lodash-es；urllib3 待 pip-audit 口径复核） | 每删一包全量测试 | 删除后全量门禁绿 |
| M-35/M-45 | 死代码批量删除（validators.py → date_utils → string_utils 死函数 → Image.ts 死导出 → providers Mock → BaseModel restore 三件套 → EmployeeProvider 注册中心 → reactiveAccess 坍缩；分小批） | 每批全量 pytest + 前端三检查 | 每批门禁绿灯 |

### 批次 6：文档与拍板/杂项收尾

| 顺序项 | 内容 | 验证 |
|:--|:--|:--|
| M-15 | 日期渲染产品口径拍板（推荐 Asia/Shanghai 固定渲染） | 双时区目检 + Format 跨时区单测 |
| M-38 | repair_done physical_grade 口径拍板（推荐「有值必验、缺值可略」入文档） | 拍板后文档/校验用例 |
| M-42 | 图表 palette 豁免口径书面化 | 设计确认留痕 |
| M-16 | 本地残留测试库恢复步骤文档化 | 按文档恢复后全绿 |
| M-19 | asset_view.py 拆分（并入 M-03 同域评估） | 护栏 <480 |
| M-22 | B1 补记 message 文案不固定 | 文档核对 |
| M-23 | dev/test console 挂 TraceIDFilter 或豁免登记 | 本地日志含 trace_id |
| M-25 | 通知死信告警接线（最低关键字告警） | 死信分支测试 |
| M-27 | frontend-testing-rules §六棘轮值同步 21.1/19.0/18.6/21.3 [PATCH-FE] | 文档/配置逐值一致 |
| M-37 | README 状态机图补边或导航免责 | 文档核对 |
| M-39 | test_contract_fsm 合法边参数化 7 条 | 合同 FSM 测试绿 |

**修复顺序总览**：
批次 1（M-02→M-17→M-01→M-18，护栏自身）→ 批次 2（M-05）→ 批次 3（M-06→M-29→M-30→M-41→M-07→M-08→M-03→M-28→M-31）→ 批次 4（M-04a→M-32→M-14→M-33→M-04b→M-20/26→M-21→M-13→M-24/43→M-44）→ 批次 5（M-09→M-10→M-34→M-11→M-12→M-36→M-35/45）→ 批次 6（拍板与文档收尾）。
预计节奏：批次 1/2/5/6 合计 ~3 天工作量级；批次 3 按域 2~3 子批（usermanagement 域 M-06/29/30/41 单列一子批）；批次 4 按档位 3 子批。全程无 [HALT] 红线变更（M-03 除外——属结构性扁平化，需独立评估批次）。

---

## §五 台账终态与统计

| 级别 | 数量 | 条目 | 状态分布 |
|:--|:--|:--|:--|
| P0 | 0 | — | — |
| P1 | 5 | M-01~M-05 | 全部已确认/待修（本会话 5/5 抽验直证） |
| P2 | 20 | M-06~M-18（13）+ M-28~M-34（7） | 已确认/待修 ×19；待复核 ×2（M-13 证据降级、M-34 现网待 `gh run list` 直证）；待拍板 ×0（M-08 拍板含于修复中） |
| P3 | 21 | M-19~M-27（9）+ M-35~M-45（11）+ — | 已确认/待修 ×19；待拍板口径 ×2（M-38/M-42） |
| 合计 | **46 条** | 报告A 28 + 报告B 17 + ponytail 汇总条 M-45（1） | 已修复 0（纯审计） |
| 不采纳/排除 | 11 | X-01~X-11 | 维持排除（本会话无新增反证） |

**融合明细**：报告B 17 条原 AUD 条目 100% 融合入 M-28~M-44（含 1 条口径统一降级 M-43）；ponytail 死代码/依赖清单落为两条（M-36 依赖 / M-45 代码）；报告A 28 条全部保留原编号与状态（5 条 P1 本会话逐条直证）。K1~K6 六处交叉点裁决：采纳 4（M-28/M-34/M-39/M-43 新条目化）、口径统一 1（K3 var() 回退域）、互证无冲突 1（K5 门禁数字）。

**独有发现归属**：M-05（合同支付审计，仅 A 报告链发现）为最高优先业务 P1；M-01/02/04（门禁/护栏正确性）为最高优先工程 P1；M-28~M-34（报告B：状态机旁路/分层/竞态/CI 扫描）；M-35~M-45（死代码/依赖/文档域，报告B ponytail 链）。

---

## §六 评审结论（融合自审）

### 自审清单

- [x] **双向逐条复核**：报告A 5 条 P1 全部本会话独立直证（rg/源码读，见 §1.2 表）；报告B 17 条为本会话子代理产出并经 impact 验证，均为双源。
- [x] **交叉裁决**：6 处交叉点（K1~K6）均给出双方主张与裁决证据；无一处按「听起来对」和稀泥。
- [x] **数字互证**：全量测试 2398/89.55% 双会话同值；护栏权威数值（484/199/407）双报告一致；.vue 棘轮四阈值本会话直读复证。
- [x] **域差异显式标注**：K1（A 未扫 management/commands、B 未扫护栏代码）作为融合边界记入，不作为对方缺陷。
- [x] **只读纪律**：本融合会话未改动任何业务代码；唯一产出物 = 本文件。
- [x] **建议可执行**：46 条均含 file:line/symbol 去处 + 回查命令 + 建议验证方式；修复顺序含依赖关系与批次边界，修复 skill（bug-surgical-fix / audit-batch-fix-closure / br4-batch-split-execution 等）可直接按批次接手。
- [x] **事实边界**：M-34 [推测] 干 CI 现网 run 结论（机理已由追加直证）；M-15/M-42/M-44 影响面 [推测]；M-13 维持「待复核（勿再按报告原文直接取证）」。

### 审计票（根 AGENTS.md §4 格式）

```markdown
[审计票 - 必填项]
- 读取规范：已读根 AGENTS v3.7.5 + 后端 AGENTS v9.3.3 + 前端 AGENTS v9.9.1
  + backend-business-rules v1.23 + backend-testing-rules v1.8 + frontend-business-rules v1.5 + frontend-testing-rules v1.8
- CT-1[√] CT-3[√ 规则表逐条一致·未声明旁路 1 处已登记 M-28·合同 FSM 一致] CT-5[√ 双会话 2398 passed 零失败]
- CT-7[√ 门禁数字于 dev.txt 对齐版工具链取得（mypy 2.1.0 / django-stubs 6.1.0 / drf-stubs 3.18.0 / types-channels / ruff 0.17.1 一致）]
- DR-1[~ M-06/M-08/M-17/M-30/M-40/M-45 双实现面在案] DR-5[~ 四护栏 PASS（M-02 BOM 假绿路径 + M-19/45 余量）]
- SC-1[√ 业务代码 0 命中] SC-3[√ 零注入面直证] SC-5/SC-6[N/A 无上传接收面双报告互证]
- 跨端契约：4/4 双报告互证通过（M-15 显示层时区 [推测] 单列）
- 红线触发：无
- 建议提交：是（本报告为审计融合产物）

[审计票 - 自检项]
- 测试：CT-2[√ 后端 89.55% / Service 98.36% / 前端 stores 96.83% / .vue 棘轮余量 0.09pt(M-04)]
  CT-4[~ M-05 支付域无审计断言 / M-31 feishu 波动 / M-04 0% 页面] CT-6[N/A 无迁移变更]
- DRY：DR-2[~ M-14] DR-3[√ 资产查询收敛完好] DR-4[√ M-45 均在 utils/外残留→清批] DR-6[~ M-03 批删链 6 层]
- 安全：SC-2[~ M-11/M-34 CI 扫描面两个缺口在案] SC-4[√] SC-7[~ M-12] SC-8[~ M-18]
- 可观测性：OC-1~OC-3[√] OC-4[~ M-25 死信告警] OC-5[~] OC-6[√ 双报告直证] OC-7[~ M-23 dev 无 trace]
- AI鲁棒性：AR-1~AR-5[√]（零业务代码变更）
- AI行为：Fact-1[√]（CI 现网结论与 BOM 现网红绿等 [推测]/[待直证] 项显式标注，未编造）
- 写作风格：Style-1~Style-3[√]
- 质量管控检查点：索引无陈旧[√] 台账五要素完整[√] 证据可回查[√] 报告闭环[√] 修复可接手[√] 只读纪律[√]
```

> **只读纪律确认**：本融合会话未改动任何业务代码；产出物仅本文件（`docs/Review/merge-audit-20261107.md`）。
