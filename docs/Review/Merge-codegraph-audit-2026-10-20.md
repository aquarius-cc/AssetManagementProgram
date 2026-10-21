# CodeGraph 审计融合报告（2026-10-20）

> 融合对象：
> ① `docs/Review/codegraph-audit-2026-10-20.md`（22:33 版，台账 NEW-01~16，来源=并行会话）
> ② `docs/Review/MimoCode-codegraph-audit-2026-10-20.md`（21:07 版，台账 AUD-21~44，来源=本会话，全部条目经本会话实证）
>
> 融合原则（Fact-1）：仅收录经核验的事实；两报告冲突项以实测证据裁决；未逐行复核的条目显式标注来源与核验状态；重复发现合并为一条并保留双 ID 溯源。
> 全程只读，未改动任何业务代码。本文件为唯一融合产物。

---

## §〇 核验方法与事实冲突裁决

### 0.1 本会话对 NEW 台账的抽查核验（只列裁决所需）

| 核验项 | 命令/方法 | 结果 |
|:---|:---|:---|
| 解释器版本 | `.venv\Scripts\python.exe -c "import django,rest_framework"` | **Py 3.13.13 / Django 6.0.8 / DRF 3.17.2**（与 base.txt 声明一致） |
| 全局解释器 | `python -c "import rest_framework"` | Py 3.13.13 / **DRF 3.16.0**（漂移） |
| NEW-01 限流测试 | `.venv` 与全局解释器分别 `pytest apps/authusermanagement/tests/test_create_throttle.py` | **双解释器均 4 passed，失败未复现**；生产限流 `base.py:207 "register": "5/minute"` 证实 |
| NEW-02 无序分页 | `rg -n "ordering" models/{broken_asset,contract,damaged_asset,recycle_asset}.py` | **exit=1，4 文件确无 Meta.ordering**（Asset 对照有 `ordering=["-created_at"]`） |
| NEW-03 状态搁浅 | 直读 `repair_asset_service.py:281-315` | 证实：`from_state = asset.asset_current_status`（=repairing）→ `DamagedAsset.objects.create(original_status=from_state)`，失败单回退将回 repairing 死路 |
| NEW-04 TOCTOU | 直读 `out_asset_service.py:50-85` | 证实：`outasset_previous_status` 在行锁前捕获并先 `OutAsset.objects.create` 落库 |
| NEW-06 刷新竞态 | 直读 `authusermanagement/services.py:191-215` | 证实：`check_blacklist()` 与 `blacklist()` 两步间无事务/锁 |
| NEW-07 fail-open | 直读 `core/permissions.py:192-212` | 证实：未登记 action 缺省 `return [permissions.IsAuthenticated()]` |
| NEW-08 Secure 缺省 | 直读 `cookie_utils.py:15-32` + `rg base.py` | 证实：`JWT_AUTH_COOKIE_SECURE = config(..., default=False)`（base.py:249） |
| 全量测试（HEAD） | 会话内 14:10 实测（git 确认此后无新提交，HEAD=5592cf2@13:43） | **2011 passed / 0 failed / cov 88.91%**；本融合前两次复跑分别超时 300s/900s，标记 `[x] 未复跑成功（环境性挂起，无并发残留进程）`，以 14:10 直证为准 |

### 0.2 事实冲突裁决表

| 冲突点 | 并行会话报告（NEW） | 本会话报告（AUD） | 裁决与证据 |
|:---|:---|:---|:---|
| 全量测试 | 2005 passed / **1 failed** / 5 skipped（43.2s） | **2011 passed / 0 failed**（cov 88.91%） | **采信 2011/0**。NEW 跑在全局漂移解释器（DRF 3.16.0），违反 CT-7「结论须取自声明版本」；其 1 failed 即 NEW-01，本会话在**同一漂移解释器**与 .venv 上复跑均 **4 passed 未复现**；2005+1+5=2011 与本会话采集总数一致，差值为漂移环境跳过/假红 |
| DRF 版本 | 「声明 3.17.2 / 本地实装 3.16.0」 | 未列冲突 | **.venv 实装 3.17.2 = 声明**；3.16.0 是**全局解释器**的版本，NEW 误用非 .venv 解释器得出「漂移」结论 |
| pip-audit | 「本地未装，以 CI 为权威」 | 本会话已实装并跑出 twisted CVE-2026-106454 | **已装且有结果**；结论一致处：CI `security-scan.yml` 为合并权威（SC-8），twisted 豁免留痕 |
| 覆盖率 | 88.88%（SQLite 口径） | 88.91% | 差值 0.03pp 为不同运行采集差，**均 ≥80 达标**，无实质冲突 |
| NEW-01 定级 | P1「测试假红（回归）」+ 上线前置① | 无此项 | **降级为 P2·待复现**。失败不可复现（双解释器 4 passed），「override 覆盖 THROTTLE_RATES 类快照」的脆弱性分析保留为设计注记；**撤销其上线阻断资格** |
| NEW-05 vs AUD-27 | 审计吞没 `audit_service.py:52-54` | 同文件同问题 `:39-54` | **同一缺陷，合并条目**（见 M-16，保留双 ID） |
| NEW-12 vs AUD-26 | move_department 无行锁 | move_department 旧链缓存不失效 | **同一函数两个独立缺陷，均保留**（M-17 / M-07） |

---

## §一 项目上下文（融合后）

| 维度 | 事实（核验后） |
|:---|:---|
| 技术栈 | 后端 Django 6.0.8 + DRF **3.17.2**（.venv，= base.txt 声明）+ PostgreSQL 16；前端 Vue 3 + TS + Pinia + Vitest；全局解释器 DRF 3.16.0 为漂移环境，**不得用于门禁结论**（CT-7） |
| 模块边界 | `apps/` 5 域（assetmanagement / authusermanagement / usermanagement / unregisteredasset / notification）+ `core/` + `utils/`；`state_machine/` 独立包；响应唯一入口 `utils/response_utils.py` |
| 索引 | CodeGraph 1.6.2：988 文件 / 17,525 节点 / 39,447 边，up-to-date（两会话一致） |
| 机械门禁（HEAD，2026-10-20 14:10 直证） | 全量 **2011 passed / 0 failed**，cov **88.91%**（≥80）；Service 四核心域 96~100%（≥90）；mypy --strict 0 errors（227 files）；ruff check/format 绿（401 files）；四护栏 PASS（最大文件 483/500）；前端 2196 tests + type-check/lint/format 全绿；OpenAPI schema 与基线**字节一致**（SHA `8dc2c574…`，191 paths）；`makemigrations --dry-run` 无变更 |
| 依赖漏洞（SC-8） | `npm audit --omit=dev` = 0；pip-audit 1 条 twisted 26.4.0 CVE-2026-106454（CI `--ignore-vuln` 豁免留痕）；npm dev 链 4 high（BF-100 已定性）。权威门禁 = CI `security-scan.yml` |
| 资产专项 | CT-3：22 边表-实现吻合，FSM 域外直写 **0 处**；跨端契约 4 项（信封/枚举/分页/日期）通过；SC-1/SC-3/SC-4/OC-6 通过（`/health` `/ready` 在位） |

---

## §二 问题台账（核实后并集）

编号规则：M-xx 为融合序号；每条标注 `[AUD-xx]` / `[NEW-xx]` 溯源；核验列：✅=本会话直证，▶=并行会话结论（机制兼容性已核对，未逐行复核）。

### 2.1 总览

| 级别 | 数量 | 条目 |
|:---|:---|:---|
| P0 | 0 | — |
| P1 | 5 | M-01~M-05 |
| P2 | 19 | M-06~M-24 |
| P3 | 14 | M-26~M-39 |

### 2.2 P1（5 条）

**M-01 | P1 | 鉴权/授权 | [AUD-21] ✅ | `core/department_scope.py:52-53` + `authusermanagement/views.py:175-230`** **【✅ 已修复 2026-10-21，登记 BF-125，详见 §五 修复追踪】**
- ~~行级隔离对无 Employee 绑定用户返回 None=不限制，而 `RegisterAPIView` 为 AllowAny 且无生产开关 → 自注册账号获得无部门过滤全量可见性。~~
- **修复后事实（2026-10-21 实测）**：② `core/department_scope.py:56-57` 无 Employee 记录反转为 `[]`（最严兜底；superuser 分支 `:50-51`、system_admin/auditor 全局角色 `:62-63` 语义不变）；① 注册开关 `AUTH_SELF_REGISTRATION_ENABLED`（`base.py:248` 缺省 True / `production.py:69` 生产 fail-closed 缺省 False）+ 双入口 403（`views.py:116-117` create、`:237-238` register，非 system_admin）+ `extend_schema` 403 声明 + 只读核查命令 `manage.py audit_orphan_accounts`。原锚点行号 `:52-53` 为修复前位置；原 AUD-21 源报告函数名误写 `resolve_department_codes_for_user`（实为 `get_department_codes_for_user`）且提及的 `DepartmentScopeMixin` 全仓 rg 零命中——源报告已归档 `ExpiredAuditReport/`，按历史快照豁免不改写，此处留痕（Fact-1）。
- **[待确认]** 生产注册入口暴露情况（本仓无部署配置可证）——现由 production fail-closed 开关兜底。**残留**：dev/test 开关下 `AuthUserViewSet.create` 匿名建号存量保留（拍板①，单列后续项）。
- ~~修复：生产关闭/白名单化注册端点，或 None 语义反转为拒绝。~~（上述两路均已落地）
- 回查：`rg -n "if not employee" core/department_scope.py; rg -n "AUTH_SELF_REGISTRATION_ENABLED" config/settings apps/authusermanagement/views.py`

**M-02 | P1 | 分页稳定性（契约） | [NEW-02] ✅ | `models/broken_asset.py:73-76`、`contract.py:119-122`、`damaged_asset.py:108-111`、`recycle_asset.py:106-109`（4 文件 rg 证实无 `ordering`）**
- 4 个生命周期模型 Meta 无 ordering，selector 裸 `filter()` 分页 → PG 下 LIMIT/OFFSET 无 ORDER BY，翻页重复/丢行（并行会话 coverage 实测 4 处 UnorderedObjectListWarning）。Asset 有 `ordering=["-created_at"]` 对照。
- 修复：4 model 补 `Meta.ordering=["-created_at"]`（最小改动全端点收敛）；Waste/Out/Repair 同类路径并入同批。
- 回查：`rg -n "ordering" apps/assetmanagement/models/broken_asset.py; codegraph impact get_queryset_for_user`

**M-03 | P1 | 业务状态搁浅 | [NEW-03] ✅ | `services/repair_asset_service.py:286,303-307`**
- `fail_repair` 建待报废单时 `original_status=from_state`（=repairing）。报废单被拒/取消 → 回 `repairing`，而维修记录已 FAILED：`complete_repair` 要求 IN_PROGRESS、`create_repair` 要求 broken → 资产滞留「维修中」无用户侧出路。
- 修复：`original_status` 改取送修前状态；reject/cancel 回 `broken`。
- 回查：`codegraph callers fail_repair`

**M-04 | P1 | 筛选/UI 状态脱节 | [AUD-22] ✅ | `GroupedAssetTable.vue:340-342` + `useGroupedAssetList.ts:119-124`**
- 分组 `refresh: () => search()` 复用重置语义：`lastFilters = filters ?? {}` 清空筛选并压回第 1 页，SearchBar 表单不被通知 → 界面显示已填筛选但数据已回全量。
- 修复：`refresh` 改 `search(lastFilters)` 透传，或新增不重置的 `reload()`。
- 回查：`rg -n "refresh: \(\) => search\(\)" vue-assetmanagement/src/components/GroupedAssetTable.vue`

**M-05 | P1 | 共享 Store 状态污染 | [AUD-23] ✅ | `createEntityStore.ts:229-238` + `useAssetFormHelpers.ts:61-63` 等**
- `getList` autoSync 把整段 list/pagination 回写共享 store；表单二次查询（`page_size:100`、autocomplete search）污染后，keep-alive 列表页（全项目 `onActivated` 零命中，实测 rg=0）返回不重取 → 列表显示污染数据。
- 修复：表单侧走非污染取数（silent 模式）或 keep-alive 页补 `onActivated` 重取。
- 回查：`rg -n "page_size: 100" vue-assetmanagement/src/composables/useAssetFormHelpers.ts`

### 2.3 P2（19 条）

**M-06 | P2 | TOCTOU | [NEW-04] ✅ | `out_asset_service.py:60,75`（锁于 :161）**
- `outasset_previous_status` 锁前捕获先落库再锁内 FSM 校验；并发 recycle 后存陈旧前态，`cancel_outasset` 回退到错误状态。修复：前态锁内重读。

**M-07 | P2 | 缓存一致性 | [AUD-26] ✅ | `usermanagement/models.py:91-107` + `department_service.py:147,198,226-230`**
- 部门移动仅清新路径祖先 `dept:{code}:descendants` 缓存，旧祖先链不失效（子孙更新走 `.update()` 绕过 save）→ RBAC 数据范围最长 5min 含已移出子树。修复：旧链逐一失效。

**M-08 | P2 | 刷新竞态 | [NEW-06] ✅ | `authusermanagement/services.py:197-209`**
- `check_blacklist()` 与 `blacklist()` 两步无事务/锁，并发同 token 刷新存在双发窗口（SimpleJWT `get_or_create` 竞态语义）。修复：`transaction.atomic + select_for_update` 或以黑名单 IntegrityError 为门。

**M-09 | P2 | 越权（缺省 fail-open） | [NEW-07] ✅ | `core/permissions.py:192-210`**
- `resolve_viewset_permissions` 对未登记 action 缺省回落 `IsAuthenticated`——新增管理动作漏登记即对全体登录用户开放。修复：admin_actions 非空的 ViewSet 缺省 deny/IsAdminUser。

**M-10 | P2 | 传输安全 | [NEW-08] ✅ | `cookie_utils.py:25` + `base.py:249`**
- `JWT_AUTH_COOKIE_SECURE` 缺省 False：漏配环境下 7 天 refresh cookie 走明文 HTTP。修复：缺省改 True，显式 opt-out。

**M-11 | P2 | 管理端旁路 | [NEW-09] ▶ | `asset_service.py:323`（docstring `asset_view.py:282-286`）**
- admin change_status 可打 `reject_to_original` 系边 → 孤儿 DamagedAsset 单据且 API 侧不可取消。机制与本会话 FSM 审计（特殊回退边已声明）兼容；屏蔽 manual 入口该边或强制补录闭环。

**M-12 | P2 | 前端静默降级 | [NEW-10] ▶ | `vue-assetmanagement/src/api/request.ts:446-449`**
- GET 失败静默以陈旧缓存当成功返回（仅 logWarn）；后端持续故障时用户无限期看旧数据。修复：回退需标记降级或提示。

**M-13 | P2 | 审计吞没（双 ID 合并） | [AUD-27≡NEW-05] ✅ | `core/audit_service.py:39-54` + `unregisteredasset/services.py:89-97`**
- 审计容错在主业务 atomic 内吞宽泛 `Exception`（含 DatabaseError）→ PG 下事务已 aborted 时反向放大为 `TransactionManagementError`/500；且 GenericAuditService 吞掉 vs OperationLogService re-raise 双口径。修复：审计写入 `on_commit`/独立连接，统一失败语义。

**M-14 | P2 | 请求竞态 | [AUD-28] ✅ | `usePagedList.ts:69-83`**
- `fetchList` 无 seq 守卫（createEntityStore:209-213 已有范式，本 composable 遗漏）。修复：对齐加 `listRequestSeq`。

**M-15 | P2 | 分页一致性 | [AUD-29] ✅ | `createEntityStore.ts:389-402`**
- `remove` 后 `pagination.total` 不减。修复：total-=实际删除数并触发页码校验。

**M-16 | P2 | 竞态/UI | [AUD-30] ✅ | `createEntityStore.ts:213` + `RoleManage.vue:162` 等**
- seq 过期响应返回 `[]` 被视图当权威镜像 → 快速连点表体空白。修复：过期返回 undefined + 视图判空。

**M-17 | P2 | 请求竞态 | [AUD-31] ✅ | `auditLogStore.ts:37-61`**
- 唯一直连 API 的列表 store，无 seq 守卫。修复：迁 createEntityStore 范式或内联守卫。

**M-18 | P2 | 分页自愈 | [AUD-32] ✅ | `createEntityStore.ts:172-178,225`**
- `handleInvalidPage` 改页码清数据不补发，且写值掐断 EP 原生钳制自愈 → 空表。修复：以修正页码重发一次 getList。

**M-19 | P2 | 缓存失效 | [AUD-33] ✅ | `api/request.ts:339` + `api/asset.ts:126-143,279,350`**
- 写操作失效仅同名 URL 子串；`mark-broken`/`batch-delete` 不失效 `getAssetByCode` 5min 缓存 → 详情页旧状态。修复：按实体 code 前缀失效或 action 端点禁读缓存。

**M-20 | P2(中) | 状态一致性 | [AUD-34] ✅ | `createEntityStore.ts:278-284`**
- `getById` 把非当前页实体 push 进 ids → keep-alive 列表多行。修复：getById 不写 ids。

**M-21 | P2(中) | 状态一致性 | [AUD-35] ✅ | `createEntityStore.ts:355-362`**
- `create` unshift 不加 total（M-15 对称分支）。修复：total+=1 对称处理。

**M-22 | P2(中) | 请求竞态 | [AUD-36] ✅ | `useGroupedAssetList.ts:98-124`**
- `fetchSummaries` 无 seq 守卫，快速翻页汇总与页码错配。修复：加守卫。

**M-23 | P2·待复现 | 测试脆弱性 | [NEW-01] ✅裁决 | `test_create_throttle.py:78` + `test.py:126-135`**
- 并行会话报「override_settings 无法覆盖 THROTTLE_RATES 类快照致假红」；本会话双解释器复跑 **4 passed 未复现**，生产限流 `base.py:207 register=5/minute` 健康。撤销 P1/上线阻断；保留为测试设计脆弱性注记（若复发，改 `mock.patch.object(THROTTLE_RATES)`）。
- 回查：`python -m pytest apps/authusermanagement/tests/test_create_throttle.py -q`

**M-24 | P2 | 并发/限流 | [AUD-25] ✅ | `core/throttles.py:92-99`**
- `login_fail_{username}` 非原子 get/set 且仅用户名维度。修复：`incr` 原子 + username+ip 复合 key。

> 注：AUD-27 已完整并入 M-13（同缺陷双 ID 合并），故 P2 有效条目为 M-06~M-24 共 19 条，无编号缺口。

### 2.4 P3（14 条）

**M-26 | P3 | 并发 500 | [NEW-11] ▶ | `contract_service.py:162-177`、`employee_service.py:243-248`、`department_service.py:72-108`、`storage_service.py:51-57`、`asset_type_service.py:95-105`**
- exists→create 无锁无 IntegrityError→DUPLICATE 映射（对照 damaged_asset_service 有），并发重复建号→500（有 partial unique 兜底不脏数据）。修复：`re_raise_or_map_integrity_error` 同批收敛。

**M-27 | P3 | 目录树并发 | [NEW-12] ▶ | `department_service.py:117-152,226-230`**
- move_department 读写无 select_for_update（与 M-07 同函数不同缺陷）。修复：行锁 + 前态复检。

**M-28 | P3 | 契约参数 | [NEW-13] ▶ | `views/dashboard_view.py:53,66`**
- 全仓唯一 `limit` 参数消费点，与 page/page_size 契约不一致。修复：改 page_size 或文档豁免。

**M-29 | P3 | 前端缓存/路由 | [NEW-14] ▶ | `request.ts:433-442`、`request.ts:101-103`、`guards.ts:163`**
- ①code!==0 也入缓存；②登出跳转无 redirect 回跳；③守卫仅验 token 真值不验 exp。三处小改。

**M-30 | P3 | 状态机边维护 | [NEW-15] ▶ | `transitions.py:66`、`scrapping.py:37-50` + `core.py:62-68`**
- DAMAGED→IN_USE 业务不可达（仅 admin manual，见 M-11）；to_damaged 与 repair_failed 共用 cell 且边名不参与校验。修复：边名纳入 `_validate_transition`。

**M-31 | P3 | 重复代码 | [NEW-16] ▶ | `core/batch_mixins.py:94,173` vs 各 service 预检；三处字段白名单过滤同形**
- 批量长度预检与 mixin 重复；白名单过滤块三处复制。修复：抽共享 helper（DR-1/DR-2）。

**M-32 | P3 | 限流口径 | [AUD-37] ✅ | `throttles.py:55-59,72-81`**
- 双节流共用 `throttle_login_{username}` key 双计数，实际 ~2.5 次/分（收紧方向）。修复：key 加类名前缀。

**M-33 | P3 | 查询 | [AUD-38] ✅ | `asset_view.py:184-190`**
- `get_asset_by_name` 全库唯一漏分页资产查询入口。修复：对齐同文件 paginate_queryset。

**M-34 | P3 | 安全披露 | [AUD-39] ✅ | `authusermanagement/services.py:285-316` + `usermanagement/models.py:283-290`**
- 改密/改角色黑名单逐 token N+1 + 吞异常（有意取舍，旧 refresh 最长 7 天窗口）。修复：批量 upsert + 失败升 error 告警。

**M-35 | P3 | 架构 | [AUD-40] ✅ | `usermanagement/selectors.py:265-302`**
- Selector 含 atomic+bulk_update 写操作，违五层铁律。修复：下沉 Service。

**M-36 | P3 | 死代码路径 | [AUD-41] ✅ | `createEntityStore.ts:257-268`**
- `navigateToValidPage` 生产零调用方且实现忽略目标页（normalize 默认 page=1）。修复：透传参数或删除 API。

**M-37 | P3 | 错误处理 | [AUD-42] ✅ | `usePaginationSearch.ts:97-100,157-171`**
- EP 事件入口 throw → unhandled rejection。修复：入口吞错。

**M-38 | P3 | 文档漂移 | [AUD-43] ✅ | `authusermanagement/views.py:66-70`**
- AUD-16 修复后 docstring 仍描述旧 `msg` 键。修复：同步为 `message`。

**M-39 | P3 | 竞态 | [AUD-44] ✅ | `useExportableAssets.ts:27-43`**
- 无 seq 守卫且 currentPage 响应后才写。修复：请求前写 + 加守卫。

### 2.5 观察项

| 编号 | 内容 | 来源 |
|:---|:---|:---|
| O-1 | `notification/services.py` 覆盖率 65%（低于核心 90% 指引，不在 T6 强制清单） | AUD |
| O-2 | `dashboardStatusGroups.ts:15-26` 状态键字面量（有测试锚定，维持不采纳） | AUD |
| O-3 | OpenAPI spectacular 25W/23E 存量（schema 字节一致基线，`--validate` exit 0） | 双方 |
| O-4 | 依赖漏洞终态见 §一（twisted 豁免留痕 / npm dev 链 4 high 已定性） | 双方 |
| O-5 | `config/urls.py:70,117` `SELECT 1` 字面量非 SC-3 违规；`clear_database.py` 白名单在位（AUD-20/BF-123 闭环） | 双方 |
| O-6 | 本融合前 HEAD 全量复跑两次超时（300s/900s，无并发残留进程），`[x] 未复跑成功`；以 14:10 直证（2011/0/88.91%）+ 提交链自证（2290d61 验证串）为准 | 融合核验 |

---

## §三 分域结论（融合后）

| 分域 | 结论 |
|:---|:---|
| 状态机 | **FSM 零旁路**（双方独立结论一致：22 边吻合、域外直写 0）。遗留 M-03（fail_repair 前态搁浅）、M-11/M-30（admin 旁路面与边名维护） |
| 鉴权/RBAC | 密钥四层 env 驱动 clean。**M-01 ✅已修复（2026-10-21，②None→[] + ①注册开关 fail-closed 双入口 403 组合，BF-125）**；遗留 M-08（刷新竞态）、M-09（fail-open 缺省）、M-10（Secure 缺省）、M-24（失败计数非原子） |
| 服务层 | 锁/幂等/事务纪律成熟（双方一致）。遗留 M-06（出库前态 TOCTOU）、M-13（审计吞没）、M-26/M-27（建号/目录树并发）、M-35（Selector 写） |
| API 契约 | 信封零旁路、枚举 8 键一致、分页参数合规（除 dashboard limit=M-28）。**M-02 无序分页为最大契约面问题** |
| 前端 | 枚举 clean+守卫测试、401 单飞、XSS 零命中。根因模式集中于 createEntityStore 契约缺口（M-05/15/16/18/20/21 同源，建议专项一次消解）+ 竞态守卫遗漏（M-14/17/22/39）+ 缓存体系（M-12/19/29） |
| 机械门禁 | 2011/0 + 88.91% + mypy/ruff/四护栏/前端三项全绿 + schema 字节一致；SC-1/SC-3/SC-6/OC-6 通过；SC-8 CI 权威。**NEW-01 假红撤销**（未复现） |

---

## §四 部署上线评估（融合判定）

### 4.1 结论

**可上线（有条件）**。两份源报告独立得出同向结论；融合后撤销 NEW 报告的「NEW-01 为发布阻断」前置条件（失败未复现，M-23 降级 P2·待复现），新增 M-02 为上线前修复项。**2026-10-21 更新：Gate #1（M-01）已修复闭环（BF-125，见 §五），上线前必办余 #2（M-02）与 #3（环境变量核对）。**

### 4.2 上线前必办（Gate）

| # | 项 | 处置 | 依据 |
|:---|:---|:---|:---|
| 1 | ~~**M-01 注册暴露面**~~ ✅ 已修复 2026-10-21 | ~~关闭/白名单化注册端点或 None 语义反转；发布单留痕；或负责人书面确认生产网络隔离~~ **两路均已落地**：① None 语义反转 `[]`（`department_scope.py:56-57`）+ ② production fail-closed 开关（`production.py:69`）双入口 403；发布单仍留痕 | BF-125 / §五 修复追踪 |
| 2 | **M-02 分页排序** | 4 model 补 `Meta.ordering=["-created_at"]`（小改，16 测试文件回归面） | rg 证实 4 文件无 ordering |
| 3 | SECRET_KEY / DB_PASSWORD 环境变量注入核对 | 部署侧确认（代码已强制） | production.py 在位 |

### 4.3 上线后首个迭代

- P1 剩余：M-03（状态搁浅，方向明确）、M-04、M-05
- P2×19（含 M-23 待复现项）：优先 createEntityStore 契约专项（一次消解 M-05/15/16/18/20/21）与后端小批（M-06/08/09/10/13）
- P3×14：随批次清尾（M-26~M-39）

### 4.4 融合会话声明

- 本报告仅合并与裁决，未发现需 `[HALT]` 的红线变更；未修改任何业务代码。
- 台账可直接作为修复批次输入：`M-xx` 为唯一流水号，`[AUD-xx]/[NEW-xx]` 可回溯两份源报告对应段落。

---

## §五 修复追踪（M-01）

> 修复批次：AUD-21「③ 组合」拍板（2026-10-21，用户放行「执行，并同步相关文档」），两批提交。登记：BF-125。规则同步：`Rules_Fiels/backend-business-rules.md` v1.19（§4.7 三态表订正 + 头部/包装/变更日志）。

| 文件 | 变更 | 验证（实测） |
|:---|:---|:---|
| `core/department_scope.py` | `:56-57` 无 Employee `None→[]`（AUD-21 反转）+ docstring `:40-47` 记录语义 | `test_no_employee_read_scope_api.py` 5 用例；无 Employee 视角测试翻转对齐（rbac_edge_cases / rbac / my_permissions / role_service / operation_log 族 / selector jobcode 等 15+ 处） |
| `config/settings/base.py:248`、`config/settings/production.py:69` | 开关缺省 True；生产 fail-closed 缺省 False（显式 `from decouple import config` + `cast=bool`，mypy `--no-implicit-reexport` 约束） | `test_self_registration_flag.py` 7 用例（关→匿名/普通 403、system_admin 双入口 201；开→201 存量固化） |
| `apps/authusermanagement/views.py` | create `:116-117`、register `:237-238` 双入口 403（复用 `IsSystemAdmin` 范式）+ `extend_schema` 403（`:105`/`:226`，create 同时显式保留 `201: RegisterSerializer`） | 同上；schema 基线 `--lang en` 重导 diff 精确 7+/1−（2×403 + 1×description） |
| `apps/usermanagement/management/commands/audit_orphan_accounts.py` | 新增只读孤儿账号核查（Exists 子查询、与 `get_employee_for_user` 同口径、`--json`/`--active-only`） | `test_audit_orphan_accounts.py` 5 用例（含软删员工计孤儿、只读断言） |
| `Rules_Fiels/backend-business-rules.md` | v1.19：§4.7 三态表「无 Employee 记录」移入空列表行 + 头部/包装/变更日志 | 本条 BF-125 登记 + 本报告 §五 |

**门禁终态（2026-10-21 本地 + WSL 直证）**：全量 **2029 passed / 0 failed**（553+197+501+455+323 分块）；cov **88.93% ≥80**、Service **98% ≥90**；`mypy --strict` **0 errors（228 files）**；`ruff check .` / `--select C90` / `ruff format --check .`（405 files）全绿；四护栏（BR-4/BR-6/G/FR）PASS；`makemigrations --dry-run` 无变更；**mutmut 83.2925% ≥ 80 红线且 ≥ 基线 83.25676365492598（delta +0.0357pt，killed 1700 / survived 341 / tested 2041，T7 双门禁 exit 0，WSL 三件套直证）**；OpenAPI 基线以 `manage.py spectacular --format openapi-json --lang en` 重导（本地 zh-hans 回退不提交，账本 :6739 先例）。

**残留与后续**：

- 拍板①：dev/test 开关下 `AuthUserViewSet.create` 匿名建号存量行为保留（单列后续项）。
- **[待确认]** 生产注册入口暴露面（本仓无部署配置）；现由 production fail-closed 开关兜底。
- ID-2 洞察（另立条目，不在本批范围）：storage/asset_type/contract 列表等全局资源对自注册账号仍可见。
- 原 AUD-21 源报告笔误（函数名 / `DepartmentScopeMixin` 零命中）按历史快照豁免不改写，留痕于 M-01 块。

---

*融合生成：2026-10-20 | 核验方：本会话（对 NEW 条目抽查 9 项，全部落定：7 证实 / 1 未复现降级 / 1 环境裁决）| 2026-10-21 追加 §五：M-01 修复追踪（BF-125）*
