# CodeGraph 审计融合报告（2026-10-20）

> 融合对象：
> ① `docs/Review/ExpiredAuditReport/codegraph-audit-2026-10-20.md`（22:33 版，台账 NEW-01~16，来源=并行会话）
> ② `docs/Review/ExpiredAuditReport/MimoCode-codegraph-audit-2026-10-20.md`（21:07 版，台账 AUD-21~44，来源=本会话，全部条目经本会话实证）
> （2026-10-21：两份源报告已随 13 份历史报告一并归档至 `docs/Review/ExpiredAuditReport/`，按历史快照只读留存；本文件为唯一现役融合产物）
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
- **[待确认]** 生产注册入口暴露情况（本仓无部署配置可证）——现由 production fail-closed 开关兜底（挂 Gate #3）。~~**残留**：dev/test 开关下 `AuthUserViewSet.create` 匿名建号存量保留（拍板①，单列后续项）~~ **已闭环（2026-10-21 批次3，BF-126）**：create 收口为仅 system_admin 单通道，与 register 门禁同权。
- ~~修复：生产关闭/白名单化注册端点，或 None 语义反转为拒绝。~~（上述两路均已落地）
- 回查：`rg -n "if not employee" core/department_scope.py; rg -n "AUTH_SELF_REGISTRATION_ENABLED" config/settings apps/authusermanagement/views.py`

**M-02 | P1 | 分页稳定性（契约） | [NEW-02] ✅ | `models/broken_asset.py:73-76`、`contract.py:119-122`、`damaged_asset.py:108-111`、`recycle_asset.py:106-109`（4 文件 rg 证实无 `ordering`）** **【✅ 已修复 2026-10-21，登记 BF-128，详见 §五 修复追踪】**
- ~~4 个生命周期模型 Meta 无 ordering，selector 裸 `filter()` 分页 → PG 下 LIMIT/OFFSET 无 ORDER BY，翻页重复/丢行（并行会话 coverage 实测 4 处 UnorderedObjectListWarning）。Asset 有 `ordering=["-created_at"]` 对照。~~
- **修复后事实（2026-10-21 实测）**：warning 机制证实（9 个绕过 `filter_queryset` 的自定义 action 分页点，回归护栏先红 9/9 全捕获 `UnorderedObjectListWarning`）；修复范围经用户拍板由 4 文件扩为 **8 模型全批**（broken/lost/found/damaged/recycle/waste/repair/contract），排序键定为 `["-created_at", "-id"]`（非原建议的 `-created_at` 单键）：`broken_asset.py:77`、`lost_asset.py:80`、`found_asset.py:87`、`damaged_asset.py:112`、`recycle_asset.py:110`、`waste_asset.py:77`、`repair_asset.py:93`、`contract.py:123`。
- **原结论订正（Fact-1）**：① 「补 `-created_at`」的前提无 FieldError 风险——`created_at` 实存于 `core/models.py:66`（`TimestampModel`，auto_now_add），`BaseModel` 继承（`:73`），此前 rg 漏扫基类得出的「字段不存在」为误判；②「仅 4 文件」低估——rg 实测 8 个目标模型均无 `ordering`，按「绕过 `filter_queryset` 的分页点所用模型」全量并入。
- **连带收口**：3 处多行 `.first()` 锁显式 `order_by("id")`（= 修复前无序查询的最早行语义，防 Meta 变序漂移）：`services/asset_lifecycle_mixin.py:189`、`selectors/out_asset_selector.py:224`、`:237`；`waste_asset_service.py:36` 经 `WasteAsset.asset_recordcode` OneToOne（`waste_asset.py:45`）单行证据**降级不动**（前序「多行」判定为误判，订正留痕）。
- 回查：`rg -n 'ordering' apps/assetmanagement/models/*.py`；`pytest apps/assetmanagement/tests/test_pagination_order_stability.py`

**M-03 | P1 | 业务状态搁浅 | [NEW-03] ✅ → 已修复 BF-130 | `services/repair_asset_service.py:284,286,308` + `services/damaged_asset_service.py:214-244,286,357`**
- `fail_repair` 建待报废单时 `original_status=from_state`（=repairing）。报废单被拒/取消 → 回 `repairing`，而维修记录已 FAILED：`complete_repair` 要求 IN_PROGRESS、`create_repair` 要求 broken → 资产滞留「维修中」无用户侧出路。
- 修复（BF-130，2026-10-22）：增量写点改取送修前态 `broken`（确定性推导，零迁移）；存量搁浅单运行时判别自愈——有 IN_PROGRESS 维修记录保持 `repairing`（「维修中直接申请报废」合法路径不误伤），无记录回 `broken` 并留 `[M03-HEAL]` 业务日志供上线核销；reject/cancel 两路径单点接入 `_resolve_revert_target`。
- 前端显示值变更（后端值修正、前端零改动）：待报废单「原状态」列（`damaged_asset_view.py:65`）由「维修中」变「损坏」。
- 回查：`codegraph callers fail_repair`；`rg -n "M03-HEAL" apps`；账本 BF-130

**M-04 | P1 | 筛选/UI 状态脱节 | [AUD-22] ✅ → 已修复 BF-131 | `GroupedAssetTable.vue:340-342` + `useGroupedAssetList.ts:119-124`**
- 分组 `refresh: () => search()` 复用重置语义：`lastFilters = filters ?? {}` 清空筛选并压回第 1 页，SearchBar 表单不被通知 → 界面显示已填筛选但数据已回全量。
- 修复（BF-131，2026-10-22）：评审否决报告原建议 `search(lastFilters)` 组件层透传——`lastFilters` 为 composable 闭包变量、未暴露于返回接口（`GroupedAssetListReturn` 无此项），GAT 层引用不可编译（TS2304）。落地为 composable 内新增 `reload()`（`useGroupedAssetList.ts:132-137`：`currentPage=1 + cache.reset() + fetchSummaries`，闭包读现值保筛选、不写 `lastFilters`——「唯一写入口是 search」不变量保持），`GroupedAssetTable.vue:344` `refresh: reload` 接线。三消费方（保存 flag watch `:235` / 删组 `:350` / 删单条 `:407`）零改动，Expose 签名不变。
- 回查：`rg -n "refresh: \(\) => search\(\)" vue-assetmanagement/src/components/GroupedAssetTable.vue`（实测 0 命中）；账本 BF-131

**M-05 | P1 | 共享 Store 状态污染 | [AUD-23] ✅ → 已修复 BF-132 | `createEntityStore.ts:229-238` + `useAssetFormHelpers.ts:61-63` 等**
- ~~`getList` autoSync 把整段 list/pagination 回写共享 store；表单二次查询（`page_size:100`、autocomplete search）污染后，keep-alive 列表页（全项目 `onActivated` 零命中，实测 rg=0）返回不重取 → 列表显示污染数据。~~
- 修复（BF-132，2026-10-22）：根治于共享工厂——`createEntityStore.ts` `getList` 增 per-call `options?: { silent?: boolean }`（`:201`），`effectiveSync = autoSync && !options?.silent`（`:223`）同时覆盖超界兜底 `handleInvalidPage` 调用（`:234`）与分页同步段（`:239-248`，原 `:229-238`）；silent 编入 `withRequestControl` requestKey（`:205`）防同 params 并发串扰（该层按 key 去重不区分 options，实读 `entityStoreRequestControl.ts:162` 确认）。**11 个非列表查询点 silent 化**（autocomplete 3 + 预载 6 + 详情单条 2）。报告原备选「keep-alive 页补 `onActivated` 重取」未采纳——污染源已断则无须，`onActivated` 全仓仍 0 命中。回退排除：`UserForm.vue:282`/`UserBatchImport.vue:308-309` 依赖 autoSync 写 `departmentStore.list` 供下拉消费，silent 会破坏缓存判据与超限告警（BF-132 §六 [待决策]）。
- 回查：`rg -n "silent: true" vue-assetmanagement/src --glob "!*.spec.ts"`（实测 **11 命中 / 7 文件**，2026-10-22）；账本 BF-132

### 2.3 P2（19 条）

**M-06 | P2 | TOCTOU | [NEW-04] ✅ → 已修复 BF-135 | `out_asset_service.py:60,75`（锁于 :161）**
- `outasset_previous_status` 锁前捕获先落库再锁内 FSM 校验；并发 recycle 后存陈旧前态，`cancel_outasset` 回退到错误状态。修复：前态锁内重读。

**M-07 | P2 | 缓存一致性 | [AUD-26] ✅ → 已修复 BF-135 | `usermanagement/models.py:91-107` + `department_service.py:147,198,226-230`**
- 部门移动仅清新路径祖先 `dept:{code}:descendants` 缓存，旧祖先链不失效（子孙更新走 `.update()` 绕过 save）→ RBAC 数据范围最长 5min 含已移出子树。修复：旧链逐一失效。

**M-08 | P2 | 刷新竞态 | [NEW-06] ✅ → 已修复 BF-135 | `authusermanagement/services.py:197-209`**
- `check_blacklist()` 与 `blacklist()` 两步无事务/锁，并发同 token 刷新存在双发窗口（SimpleJWT `get_or_create` 竞态语义）。修复：`transaction.atomic + select_for_update` 或以黑名单 IntegrityError 为门。

**M-09 | P2 | 越权（缺省 fail-open） | [NEW-07] ✅ → 已修复 BF-135 | `core/permissions.py:192-210`**
- `resolve_viewset_permissions` 对未登记 action 缺省回落 `IsAuthenticated`——新增管理动作漏登记即对全体登录用户开放。修复：admin_actions 非空的 ViewSet 缺省 deny/IsAdminUser。

**M-10 | P2 | 传输安全 | [NEW-08] ✅ → 已修复 BF-135 | `cookie_utils.py:25` + `base.py:249`**
- `JWT_AUTH_COOKIE_SECURE` 缺省 False：漏配环境下 7 天 refresh cookie 走明文 HTTP。修复：缺省改 True，显式 opt-out。

**M-11 | P2 | 管理端旁路 | [NEW-09] ▶ → 已修复 BF-136 | `asset_service.py:323`（docstring `asset_view.py:282-286`；守卫落地 `asset_service.py:327-335` + selector `damaged_asset_selector.py:68`）**
- admin change_status 可打 `reject_to_original` 系边 → 孤儿 DamagedAsset 单据且 API 侧不可取消。机制与本会话 FSM 审计（特殊回退边已声明）兼容；屏蔽 manual 入口该边或强制补录闭环。

**M-12 | P2 | 前端静默降级 | [NEW-10] ▶ → 已修复 BF-134 | `vue-assetmanagement/src/api/request.ts:446-449`**
- GET 失败静默以陈旧缓存当成功返回（仅 logWarn）；后端持续故障时用户无限期看旧数据。修复：回退需标记降级或提示。

**M-13 | P2 | 审计吞没（双 ID 合并） | [AUD-27≡NEW-05] ✅ → 已修复 BF-136 | `core/audit_service.py:39-54` + `unregisteredasset/services.py:89-97`（修复落地 `audit_service.py:27-63` on_commit + `services.py:89-106`）**
- 审计容错在主业务 atomic 内吞宽泛 `Exception`（含 DatabaseError）→ PG 下事务已 aborted 时反向放大为 `TransactionManagementError`/500；且 GenericAuditService 吞掉 vs OperationLogService re-raise 双口径。修复：审计写入 `on_commit`/独立连接，统一失败语义。

**M-14 | P2 | 请求竞态 | [AUD-28] ✅ → 已修复 BF-134 | `usePagedList.ts:69-83`**
- `fetchList` 无 seq 守卫（createEntityStore:209-213 已有范式，本 composable 遗漏）。修复：对齐加 `listRequestSeq`。

**M-15 | P2 | 分页一致性 | [AUD-29] ✅ → 已修复 BF-133 | `createEntityStore.ts:389-402`**
- `remove` 后 `pagination.total` 不减。修复：total-=实际删除数并触发页码校验。

**M-16 | P2 | 竞态/UI | [AUD-30] ✅ → 已修复 BF-133 | `createEntityStore.ts:213` + `RoleManage.vue:162` 等**
- seq 过期响应返回 `[]` 被视图当权威镜像 → 快速连点表体空白。修复：过期返回 undefined + 视图判空。

**M-17 | P2 | 请求竞态 | [AUD-31] ✅ → 已修复 BF-134 | `auditLogStore.ts:37-61`**
- 唯一直连 API 的列表 store，无 seq 守卫。修复：迁 createEntityStore 范式或内联守卫。

**M-18 | P2 | 分页自愈 | [AUD-32] ✅ → 已修复 BF-133 | `createEntityStore.ts:172-178,225`**
- `handleInvalidPage` 改页码清数据不补发，且写值掐断 EP 原生钳制自愈 → 空表。修复：以修正页码重发一次 getList。

**M-19 | P2 | 缓存失效 | [AUD-33] ✅ → 已修复 BF-134 | `api/request.ts:339` + `api/asset.ts:126-143,279,350`**
- 写操作失效仅同名 URL 子串；`mark-broken`/`batch-delete` 不失效 `getAssetByCode` 5min 缓存 → 详情页旧状态。修复：按实体 code 前缀失效或 action 端点禁读缓存。

**M-20 | P2(中) | 状态一致性 | [AUD-34] ✅ → 已修复 BF-133 | `createEntityStore.ts:278-284`**
- `getById` 把非当前页实体 push 进 ids → keep-alive 列表多行。修复：getById 不写 ids。

**M-21 | P2(中) | 状态一致性 | [AUD-35] ✅ → 已修复 BF-133 | `createEntityStore.ts:355-362`**
- `create` unshift 不加 total（M-15 对称分支）。修复：total+=1 对称处理。

**M-22 | P2(中) | 请求竞态 | [AUD-36] ✅ → 已修复 BF-134 | `useGroupedAssetList.ts:98-124`**
- `fetchSummaries` 无 seq 守卫，快速翻页汇总与页码错配。修复：加守卫。

**M-23 | ~~P2·待复现~~ P2 ✅已消解 2026-10-21（BF-129） | 测试脆弱性 | [NEW-01] ✅裁决 | `test_create_throttle.py:78` + `test.py:126-135`**
- 并行会话报「override_settings 无法覆盖 THROTTLE_RATES 类快照致假红」；本会话双解释器复跑 **4 passed 未复现**，生产限流 `base.py:207 register=5/minute` 健康。撤销 P1/上线阻断；保留为测试设计脆弱性注记（若复发，改 `mock.patch.object(THROTTLE_RATES)`）。
- 回查：`python -m pytest apps/authusermanagement/tests/test_create_throttle.py -q`
- **收口（2026-10-21，BF-129）**：并行会话原报**机制属实**——只读探针直证 DRF 3.17.2 `throttling.py:66` 导入期类快照、override 不回绑；「双解释器未复现」系 settings 口径分流（development 捕获 `base.py:207`=5/minute 偶绿 / `--ds=config.settings.test` 捕获 `test.py:132`=千万级必红）。已按注记等价方案消解：`monkeypatch.setattr(RegisterRateThrottle, "rate", ...)` 替代 override（用例与口径解耦，双口径同绿）。BF-126 时「M-23 已消解」记账属未消解（override 保留即脆弱性存续），以本条为准。

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
| O-7 | storage/asset_type 读面与 §4.2 矩阵 `:144`（类型/仓库/合同=仅 system_admin）不齐：二者经 `resolve_viewset_permissions` 分派（`storage_view` 由 `AdminWritePermissionMixin` 分派，`storage_view.py:61` 的 `permission_classes=[IsAuthenticated]` 为被覆写的类属性；`asset_type_view.py:53-55` 同构），读动作回落 `IsAuthenticated` → 自注册/普通账号可读。本批仅收口 contract（BF-127）；storage/asset_type **裁决留痕不收**（分批处理，不改 rules 条文、不升版——②③ 均为实现向既有 4.2 矩阵对齐） | ID-2 / BF-127 |

---

## §三 分域结论（融合后）

| 分域 | 结论 |
|:---|:---|
| 状态机 | **FSM 零旁路**（双方独立结论一致：22 边吻合、域外直写 0）。**M-11 ✅已修复（2026-10-22 批次 D，BF-136——damaged 出边锁内活跃待审批单拦截）**；遗留 M-30（边名维护）；M-03（fail_repair 前态搁浅）已消解（BF-130） |
| 鉴权/RBAC | 密钥四层 env 驱动 clean。**M-01 ✅已修复（2026-10-21，②None→[] + ①注册开关 fail-closed 双入口 403 组合，BF-125）**；**续收口：BF-126 create 仅 system_admin 单通道 + BF-127 contract 读面按矩阵 `:144` 收至 system_admin（O-7 留痕 storage/asset_type 分批）**；**M-08/M-09/M-10 ✅已修复（2026-10-22 批次 C，BF-135——刷新竞态原子化 / 方法感知 fail-closed / Secure 缺省翻转）**；遗留 M-24（失败计数非原子） |
| 服务层 | 锁/幂等/事务纪律成熟（双方一致）。**M-06 ✅已修复（2026-10-22 批次 C，BF-135——出库前态锁内复检）**；**M-13 ✅已修复（2026-10-22 批次 D，BF-136——审计写入 on_commit 延迟）**；遗留 M-26/M-27（建号/目录树并发）、M-35（Selector 写） |
| API 契约 | 信封零旁路、枚举 8 键一致、分页参数合规（除 dashboard limit=M-28）。**M-02 无序分页为最大契约面问题 → ✅已修复（2026-10-21，8 模型 `Meta.ordering` + 3 处 `.first()` 锁序 + 9 分页点回归护栏，BF-128）** |
| 前端 | 枚举 clean+守卫测试、401 单飞、XSS 零命中。根因模式集中于 createEntityStore 契约缺口（M-05/15/16/18/20/21 同源 → ✅全部闭环 BF-132/BF-133）+ 竞态守卫遗漏（M-14/17/22 ✅已闭环 BF-134，余 M-39）+ 缓存体系（M-12/19 ✅已闭环 BF-134，余 M-29） |
| 机械门禁 | 2011/0 + 88.91% + mypy/ruff/四护栏/前端三项全绿 + schema 字节一致；SC-1/SC-3/SC-6/OC-6 通过；SC-8 CI 权威。**NEW-01 假红撤销**（未复现） |

---

## §四 部署上线评估（融合判定）

### 4.1 结论

**可上线（有条件）**。两份源报告独立得出同向结论；融合后撤销 NEW 报告的「NEW-01 为发布阻断」前置条件（失败未复现，M-23 降级 P2·待复现），新增 M-02 为上线前修复项。**2026-10-21 更新：Gate #1（M-01）已修复闭环（BF-125，见 §五），上线前必办余 #2（M-02）与 #3（环境变量核对）。2026-10-21 再更新：Gate #2（M-02）已修复闭环（BF-128，见 §五），上线前必办余 #3（环境变量核对）。**

### 4.2 上线前必办（Gate）

| # | 项 | 处置 | 依据 |
|:---|:---|:---|:---|
| 1 | ~~**M-01 注册暴露面**~~ ✅ 已修复 2026-10-21 | ~~关闭/白名单化注册端点或 None 语义反转；发布单留痕；或负责人书面确认生产网络隔离~~ **两路均已落地**：① None 语义反转 `[]`（`department_scope.py:56-57`）+ ② production fail-closed 开关（`production.py:69`）双入口 403；发布单仍留痕 | BF-125 / §五 修复追踪 |
| 2 | ~~**M-02 分页排序**~~ ✅ 已修复 2026-10-21 | ~~4 model 补 `Meta.ordering=["-created_at"]`（小改，16 测试文件回归面）~~ **8 模型全批 `Meta.ordering=["-created_at", "-id"]` + 3 处 `.first()` 锁 `order_by("id")`，9 分页点回归护栏先红后绿** | BF-128 / §五 修复追踪 |
| 3 | SECRET_KEY / DB_PASSWORD / `AUTH_SELF_REGISTRATION_ENABLED` 环境变量注入核对 | 部署侧确认（代码已强制；注册开关生产缺省 False fail-closed，置 `true` 须书面确认生产注册面——本子项 2026-10-21 依①档1拍板追加） | `production.py:69` 在位 / BF-125 |

### 4.3 上线后首个迭代

- P1 剩余：无（M-01~M-05 全部闭环，~~M-01/M-02/M-03/M-04 已闭环，见 §五与账本 BF-128/BF-130/BF-131~~；M-05 已闭环 2026-10-22 见 BF-132）
- P2×19（M-23 待复现项已于 2026-10-21 由 BF-129 消解）：~~优先 createEntityStore 契约专项（一次消解 M-15/16/18/20/21，M-05 已由 BF-132 先行闭环）与后端小批（M-06/08/09/10/13）~~ **批次 A/B/C/D 已闭环 2026-10-22（BF-133/134/135/136，消解 M-15/16/18/20/21 + M-12/14/17/19/22/25 + M-06/07/08/09/10 + M-11/13，共 18 项——计划批全部执行完毕）**；余 **M-24（未排批）**
- P3×14：随批次清尾（M-26~M-39）
- **批外新增（M-02 执行中发现，2026-10-21）**：`AuthUserViewSet` 两处分页 `views.py:118/:167` 同属无序分页（注册 `AuthUser` 不继承 `BaseModel`、无 `created_at`——`models.py:99`），排序键须另定（如 `-auth_id`），登记 BF-128 §六待决 → **已收口 2026-10-21（BF-129②）**：定性订正（`models.py:192` `Meta.ordering=["auth_username"]` 自 2026-07-15 已存在，非无序），真残留为并列决胜缺失——Meta 加 `auth_id` 决胜（**不采纳** `-auth_id`，保前端字母序，用户拍板）+ 迁移 `0007_alter_authuser_options` + 护栏 `test_user_pagination_order_stability.py` 先红后绿

### 4.4 融合会话声明

- 本报告仅合并与裁决，未发现需 `[HALT]` 的红线变更；未修改任何业务代码。
- 台账可直接作为修复批次输入：`M-xx` 为唯一流水号，`[AUD-xx]/[NEW-xx]` 可回溯两份源报告对应段落。

---

## §五 修复追踪（M-01 / M-02）

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

- ~~拍板①：dev/test 开关下 `AuthUserViewSet.create` 匿名建号存量行为保留（单列后续项）~~ **已由 BF-126 收口（2026-10-21 批次3）**：create → `IsSystemAdmin` 单通道，`test_self_registration_flag.py` 重写锚定（开态 system_admin 201 / 已认证非 sysadmin 403 / 匿名 401）。
- **[待确认]** 生产注册入口暴露面（本仓无部署配置）；现由 production fail-closed 开关兜底。
- ID-2 洞察：~~storage/asset_type/contract 列表等全局资源对自注册账号仍可见~~ **contract 部分已由 BF-127 收口（2026-10-21 批次4，读面至 system_admin）**；storage/asset_type 裁决留痕 O-7（分批处理，不改 rules 条文）。
- 原 AUD-21 源报告笔误（函数名 / `DepartmentScopeMixin` 零命中）按历史快照豁免不改写，留痕于 M-01 块。

**2026-10-21 续修（BF-126 / BF-127，AUD-21 授权面收口）**：

| 批次 / 提交 | 变更 | 验证（实测） |
|:---|:---|:---|
| 批次3 `55e92a2`（BF-126，5 files，+93/−83） | `authusermanagement/views.py` create `get_permissions` → `IsSystemAdmin`（删 `get_throttles` 覆写与 `BaseThrottle` 导入）+ `extend_schema` 401 新增 / 403 换文案；**`_THROTTLE_TEST_SETTINGS` 镜像补 `DEFAULT_SCHEMA_CLASS`**（跨测试 schema 污染根治：`override_settings(REST_FRAMEWORK=mini)` 窗口内 URLConf 首导入时 `@extend_schema` 回退读 `api_settings.DEFAULT_SCHEMA_CLASS` 回落 DRF 2-arg `AutoSchema` 并固化进 `ExtendedSchema` 基类） | `test_self_registration_flag.py` 重写 8 用例 + `test_create_throttle.py` 重写（429 迁 REGISTER_URL 6 连发）+ 污染红→绿 102 直证；schema `--lang en` 重导 diff 精确 6+/4− |
| 批次4 `d48b283`（BF-127，3 files，+151/−31） | `contract_view.py` 模块级 `_CONTRACT_READ_OVERRIDES`（list / retrieve / getcontractByname / statistics / global_search → `IsSystemAdmin`，经 `resolve_viewset_permissions` `action_overrides` 接入，DR-1 复用既有类；**读权限面=仅 system_admin**——矩阵 `:144` 实测裁决，否决批准文三角色假设）+ `get_permissions` docstring 口径同步 | 新增 `test_contract_read_scope.py` 9 test-id（匿名 401 / sysadmin 200 锚 / regular·dept·asset·auditor 403 / 自定义 3 读 action 403）+ `test_contract_view_api.py` 翻修 10 红；存量 export_rbac / payment_lock / admin_config 零回归；schema **SCHEMA_IDENTICAL** |

**门禁终态（2026-10-21，批次3/4 合并直证）**：全量 **2039 passed / 0 failed**（分块 1288 + 751）；cov **89% ≥80**、Service **98% ≥90**；`mypy --strict` **0 errors（228 files）**；`ruff check .` / `--select C90` / `ruff format --check .`（406 files）全绿；四护栏（BR-4/BR-6/G/FR）PASS；`makemigrations --dry-run` 无变更；**WSL mutmut（3.8.0 = dev.txt 声明版，`rm -rf mutants` 全量重跑 14.05 mutations/s）→ score 83.2925%（红线 80.0 / 基线 83.25676365492598 / delta +0.0357pt），killed=1700 survived=341 timeout=0 skipped=0 tested=2041 → T7 双门禁 PASS（exit 0）**；OpenAPI 基线批次3 `--lang en` 精确重导（6+/4−）、批次4 零漂移（SCHEMA_IDENTICAL）。

**2026-10-21 M-02 修复追踪（BF-128，上线前必办 Gate #2 分页稳定性）**：

> 修复批次：M-02 拍板（2026-10-21，排序键 `["-created_at", "-id"]` + 范围 8 模型全批，用户放行执行）。登记：BF-128。

| 文件 | 变更 | 验证（实测） |
|:---|:---|:---|
| `apps/assetmanagement/models/{broken_asset,lost_asset,found_asset,damaged_asset,recycle_asset,waste_asset,repair_asset,contract}.py` | 8× Meta 补 `ordering = ["-created_at", "-id"]`（`:77` / `:80` / `:87` / `:112` / `:110` / `:77` / `:93` / `:123`） | 回归护栏 `test_pagination_order_stability.py` **先红 9/9**（每点均捕获 `UnorderedObjectListWarning`）→ **后绿 9 passed**（CT-4） |
| `apps/assetmanagement/migrations/0024_add_lifecycle_model_ordering.py` | 新增 8× `AlterModelOptions`（纯 Meta 状态，**无 DDL**） | CT-6 三步：`makemigrations --dry-run` → No changes detected；`migrate --plan` → 仅 0024；危险操作扫描（RemoveIndex/RemoveField/RenameField）→ 0 命中 |
| `services/asset_lifecycle_mixin.py:189`、`selectors/out_asset_selector.py:224,237` | 3 处多行 `.first()` 显式 `.order_by("id")`（锁「最早」语义，防 Meta 变序漂移） | `apps/assetmanagement` 全量 **1296 passed / 1 skipped**；`waste_asset_service.py:36` 经 OneToOne 单行证据降级不动 |
| `apps/assetmanagement/tests/test_pagination_order_stability.py`（新建，290 行） | 9 个 action 分页稳定性回归：两页覆盖无重复丢行 + 断言 `(-created_at, -id)` 序 + warning 零容忍（`warnings.catch_warnings` 断言清单为空） | 证红 9 failed（UnorderedObjectListWarning×9）→ 证绿 9 passed |

**门禁终态（2026-10-21，M-02 本地 + WSL 直证）**：全量 **2042 passed / 1 failed**——唯一失败 `test_create_throttle.py::TestRegisterRateLimited::test_sixth_anonymous_register_returns_429` 经 `git stash` 回基线复跑**同红**，属存量问题、非本批引入（挂 BF-128 §六遗留）；cov **89.20% ≥80**、Service **98.34% ≥90**；`mypy --strict` **0 errors（228 files）**（CT-7 版本对齐 `dev.txt`：mypy 2.1.0 / django-stubs 6.1.0 / drf-stubs 3.18.0 逐项一致）；`ruff check .` / `ruff format --check .` 全绿；行数/重复护栏 PASS；`makemigrations --check --dry-run` 无变更；**WSL mutmut 3.8.0 全量 → score 83.2925%（红线 80.0 / 基线 83.25676365492598 / delta +0.0357pt），killed=1700 survived=341 tested=2041 → T7 双门禁 PASS（exit 0）**。mutmut 与批次3/4 同数可复现：服务层唯一新增行（`.order_by("id")` @ `mark_asset_lost`）在 `mutants/.../asset_lifecycle_mixin.py.meta`（`exit_code_by_key`）与 `.spans` 中**零 mutant 条目**，mutant 集合未变。**→ 后续（2026-10-21，BF-129）**：唯一失败项即批外存量红，已根因实证修复，全量 **2046 passed / 0 failed**、cov **89.25% ≥80**（权威口径 `--ds=config.settings.test` 复测）。

**M-02 残留与后续**：

- ~~**批外**：`AuthUserViewSet` 无序分页两处（`views.py:118`、`:167`）——`AuthUser` 不继承 `BaseModel`、无 `created_at`（`models.py:99`），排序键须另定，待用户拍板（BF-128 §六 / §4.3）~~ **✅ 已收口 2026-10-21（BF-129②）**：定性订正（`Meta.ordering` 已存在非无序）+ 并列决胜缺失修复（Meta 加 `auth_id` + 迁移 0007 + 护栏先红后绿）。
- ~~**存量测试红**：`test_create_throttle.py` 第六次注册不返 429（基线同红，`git stash` 直证）——疑似注册限流测试环境口径问题，[待决策] 是否独立立项。~~ **✅ 已收口 2026-10-21（BF-129①）**：根因实证为 DRF `THROTTLE_RATES` 导入期类快照 + override 安慰剂 + settings 口径分流（非 cache reset），改 monkeypatch 直设 `rate`，全量 2046 / 0 failed。
- **原报告表述订正**：范围「4 model」→ 实修 8；排序键「`-created_at` 单键」→ 拍板 `-created_at,-id`；「`created_at` 可能不存在」前提误判（rg 漏扫 `core/models.py` 基类）；`waste_asset_service.py:36`「多行」→ OneToOne 单行降级。原 `ExpiredAuditReport/codegraph-audit-2026-10-20.md` NEW-02 行按**历史快照豁免**不改写，订正留痕于 M-02 块与 BF-128。

**2026-10-22 M-04 修复追踪（BF-131，前端分组表 refresh 筛选脱节）**：

> 修复批次：M-04 拍板（2026-10-22，方案 A——composable 内 `reload()`；评审否决报告原建议的组件层 `search(lastFilters)` 透传，因 `lastFilters` 未暴露于返回接口、GAT 层引用 TS2304 不可编译）。登记：BF-131。

| 文件 | 变更 | 验证（实测） |
|:---|:---|:---|
| `vue-assetmanagement/src/composables/useGroupedAssetList.ts` | 接口 `:51` + 实现 `:132-137`（`currentPage=1; cache.reset(); await fetchSummaries()` 三行、无 try/catch——`fetchSummaries` 自带 try/catch/finally 兜底；不写 `lastFilters`）+ 返回暴露 `:157` | `useGroupedAssetList.spec.ts:202` 新增 `describe('reload')` 3 用例：**先红 3 failed（`reload is not a function`）→ 后绿 37/37**（保筛选回第 1 页 / 明细缓存白名单透传 `asset_current_status` 断言 / 清展开留选中） |
| `vue-assetmanagement/src/components/GroupedAssetTable.vue` | 解构 `:193` + `defineExpose` `:344` `refresh: () => search()` → `refresh: reload`（含语义注释）；`GroupedAssetTableExpose` 签名不变，`AssetContentDetails.vue:235/:350/:407` 三消费方零改动 | 回查 `rg "refresh: \(\) => search\(\)"` → **0 命中（exit 1）**；`AssetContentDetails.enableGrouping.spec.ts` 随全量套件绿 |

**门禁终态（2026-10-22 前端直证）**：`npm run type-check`（vue-tsc --build 0 错）、`npm run lint`、`npm run format:check` 全绿；定点 `vitest run useGroupedAssetList.spec.ts` **37 passed**；全量 `npm run test:coverage` **169 files / 2199 tests passed，exit 0**——分层棘轮（`src/**/*.ts` ≥80 / `src/stores/**` ≥90，实测汇总 96.87 / `src/**/*.vue` 基线 12.9~13.0）全达标（汇总表 45.4% 为含 .vue 无前缀全局并集，非门禁口径，见 `vitest.config.ts` P2-2 分层注释）。T16 变异测试本批未跑（单函数微改 + 三用例直断言，如实申报）。

**2026-10-22 M-05 修复追踪（BF-132，共享 Store 状态污染）**：

> 修复批次：M-05 拍板（2026-10-22，五步方案——双口径清点 → `createEntityStore` 加 per-call silent 口 → 11 点收敛 → 先红（手植变异抽证×2）→ 门禁 + 双源登记）。登记：BF-132。

| 文件 | 变更 | 验证（实测） |
|:---|:---|:---|
| `vue-assetmanagement/src/stores/createEntityStore.ts` | `getList` 签名增 `options?: { silent?: boolean }`（`:201` + JSDoc 双职责声明）；`effectiveSync = autoSync && !options?.silent`（`:223`）同时覆盖超界 `handleInvalidPage` 调用（`:234`）与分页同步段（`:239-248`）；silent 编入 requestKey（`:205`，`list:silent:...`）——实读 `entityStoreRequestControl.ts:162` 确认该层按 key 去重不区分 options，防同 params 并发串扰 | `createEntityStore.spec.ts:160` 新增 `describe('getList silent')` 2 用例（返回值双职责断言 + 超界零副作用）：**手植变异先红 2 failed（`effectiveSync = autoSync`）→ 还原后绿**；定点双 spec 79 passed |
| `vue-assetmanagement/src/composables/useAssetFormHelpers.ts` | 结构化最小接口三签名补第二参（`:51/:54/:57`）+ 三调用点 silent（`:68-70`） | spec 断言翻转 `toHaveBeenCalledWith({...}, { silent: true })`×3：**手植变异先红 1 failed（调用去 silent，`:53` 断言失配）→ 还原后绿** |
| `useUnregisteredFormLinkage.ts` / `useRecycleFormAssociations.ts` | 接口 `UnregisteredFormLinkageStores`（`:25`，getList 签名 `:28/:34`）两签名补第二参（**type-check 实测 TS2554，报错点为修复前 `:51/:115`**）；autocomplete `:57/:121`、预载 `:58/:94` 共 4 点 silent | `useUnregisteredFormLinkage.spec:128/:236`、`useRecycleFormAssociations.spec:54/:122` 断言同步翻转（CT-4 回归屏障，首跑全量实测 4 failed → 补齐后绿） |
| `AssetTypeDetails.vue:224` / `DamagedAssetForm.vue:305` / `DamagedAssetBasicDetails.vue:205` / `WasteAssetBasicDetails.vue:177` | 预载 1 + autocomplete 1 + 详情单条 2 silent 化；渲染源均实读核实为本地状态（`allData` ref / `formData` / `detailData`），零 store state 读取、不触发回退条款 | 回查 `rg -n "silent: true" src --glob "!*.spec.ts"` → **11 命中 / 7 文件** |

**门禁终态（2026-10-22 M-05 前端直证）**：`npm run type-check`（vue-tsc --build 0 错）、`npm run lint`、`npm run format:check` 全绿；全量 `npm run test:coverage` **169 files / 2201 tests passed，exit 0**——分层棘轮全达标（`src/stores/**` 实测 **96.88 ≥90**；汇总 45.41% 为含 .vue 非门禁口径）；FR-8 前端护栏 `check_frontend_invariants.py` **PASS**（`createEntityStore.ts` **398 逻辑行 ≤500**，stores 31 文件 0 超限）。T16 变异测试本批未跑（以手植变异×2 证红替代，如实申报）；schema 不涉（纯前端内部取数口径，免重导）。

**M-05 排除与遗留**：`UserForm.vue:282` / `UserBatchImport.vue:308-309` 显式依赖 autoSync 写 `departmentStore.list` 供下拉消费（`UserForm.vue:236/:281/:290-294` 实读），silent 化会破坏缓存判据与超限告警——回退不动，**[待决策]** 是否以「预载专用 API / 本地缓存」消解其跨页污染（departmentStore 与部门管理页共享）；`listRequestSeq` 共享序竞态（既有 [待决策]）与 keep-alive 返回即最新（`onActivated` 独立增强）均不混入本批，见 BF-132 §六。**✅ [待决策] 已消解 2026-10-22（批次 B M-25，BF-134）**：`UserForm.vue:286-291` / `UserBatchImport.vue:309-315` 实测均已 silent + 本地 `departmentOptions` ref、零写 `departmentStore.list`（M-25 由 vue `a368848` 引入；`git show a368848~1:UserForm.vue` rg `silent: true|M-25` 0 命中）——原「显式依赖 autoSync 供下拉消费」为**批次 B 提交前状态**，Fact-1 订正留痕。

**2026-10-22 P2 批次 A 修复追踪（BF-133，createEntityStore 契约专项 M-15/16/18/20/21）**：

> 修复批次：P2 批次计划 A（2026-10-22，用户拍板「每批一提交」）。提交：vue `1ea7aed`（21 files，+478/−63）。登记：BF-133。

| 文件 | 变更 | 验证（实测） |
|:---|:---|:---|
| `src/stores/createEntityStore.ts` | M-15 `remove`（`:411`）成功后 `pagination.total` 递减：单删 `:421` `Math.max(0, total-1)`、批删 `:464` `−successCount`；M-21 `create`（`:369`）成功后 `:383` `total += items.length`（对称分支） | 新增 `createEntityStore.contract.spec.ts` **9 用例先红后绿**（total 双向 / seq 过期 / 越界补发 / 详情不入 ids） |
| 同上 | M-16 seq 过期响应 `return undefined`（`:224`，替代 `[]`）——`listRequestSeq` 守卫 `:219`；配套 **15 处消费方 `?? []` 判空**、6 处既有测试断言更新（提交消息留档） | contract spec 过期用例 + 全量 vitest 回归 |
| 同上 | M-18 `handleInvalidPage`（`:172`）超界页以修正末页**补发一次 `getList`**（`:230` totalPages 重算 / `:238` 校验链，非空表） | contract spec 超界补发用例 |
| 同上 | M-20 `getById`（`:291`）**仅写 entities 映射、不写 ids**（`:301` 注释锚定详情查询不入列表） | contract spec 详情不污染用例 |
| `entityStoreTypes` / `SmartStore` / `AssetLifecycleStore` / `FormLinkageOptions` / `SuggestionFetcherOptions` | 类型签名放宽（过期 `undefined` 语义传导，提交消息留档） | `vue-tsc --build` 0 错 |

**门禁终态（2026-10-22 复跑，含后续 B/M-04/M-05 同树）**：`type-check` / `lint` / `format:check` 全绿；全量 `npm run test:coverage` **171 files / 2218 tests passed，exit 0**——分层棘轮达标（`src/stores/**` **96.82 ≥90**，汇总 45.52% 为含 `.vue` 非门禁口径）。T16 变异测试本批未跑（如实申报，以 contract spec 先红后绿证红）。

**2026-10-22 P2 批次 B 修复追踪（BF-134，竞态/缓存/静默降级 M-12/14/17/19/22/25）**：

> 修复批次：P2 批次计划 B（2026-10-22）。提交：vue `a368848`（11 files，+515/−35；根指针 `88bbb7e`）。登记：BF-134。

| 文件 | 变更 | 验证（实测） |
|:---|:---|:---|
| `src/api/request.ts` | M-12 GET 失败回退标记 `_degraded: true`（类型 `:69` / 回退点 `:376`），消费方可据标提示而非静默当成功 | `request.responseHandler.spec.ts` `_degraded` 断言 |
| `src/composables/usePagedList.ts` | M-14 `fetchList` seq 守卫：`:70` 定义 / `:74` 递增 / `:78` 成功路径 / `:82` 错误路径 / `:88` loading 收口——旧响应不覆盖新响应 | batchB spec seq 用例（先红后绿） |
| `src/stores/auditLogStore.ts` | M-17 `loadData` 迁 createEntityStore `listRequestSeq` 范式（`:38` 注释锚定） | 同上 |
| `src/api/asset.ts` + `src/api/request.ts` | M-19 写后失效 `getAssetByCode` 5min 缓存：`markAssetAsBroken`（`asset.ts:292`）、`batchDeleteAssets`（`:366`）经 `clearCacheByPattern`（定义 `request.ts:414`） | `asset.spec.ts` mock `clearCacheByPattern` 断言 |
| `src/composables/useGroupedAssetList.ts` | M-22 `fetchSummaries`（`:103`）seq 守卫（`:96` 范式注释） | batchB spec 竞态用例 |
| `UserForm.vue` + `UserBatchImport.vue` | **M-25**（**报告无此行**——批次计划新增编号，锚点以代码为准）：部门下拉改 silent + **本地 `departmentOptions` ref**（`UserForm.vue:236/:286-291`、`UserBatchImport.vue:309-315`），零写 `departmentStore.list/pagination`；`page_size:100` 显式取上限（后端 `MAX_PAGE_SIZE` 钳位，注释 `UserForm.vue:288-289`） | batchB spec `describe('M-25 departmentStore silent 模式不污染共享状态')`（spec `:377`，注释锚 `:358`） |

**门禁终态（2026-10-22 复跑）**：`type-check` / `lint` / `format:check` 全绿；全量 `test:coverage` **171 files / 2218 tests passed，exit 0**（stores 96.82 ≥90）；提交消息另留档批次时门禁四件套全过。**已知瑕疵**：`batchB.contract.spec.ts` 内嵌 describe 的 `vi.hoisted`/`vi.mock` vitest 警告（vitest 升版将成 error）——登记 BF-134 §六后续项。

**2026-10-22 P2 批次 C 修复追踪（BF-135，后端五项 M-06/07/08/09/10）**：

> 修复批次：P2 批次计划 C（2026-10-22）。提交：backend `61625f0`（23 files，+505/−36；根指针 `a87caa8`）。登记：BF-135。

| 文件 | 变更 | 验证（实测） |
|:---|:---|:---|
| `apps/assetmanagement/services/out_asset_service.py` | M-06 `_apply_outasset_to_asset`（`:158`）增 `outasset` 参数（缺省 `None` 向后兼容）；**锁行后**重读状态写回 `outasset_previous_status`（`:169`）定向 save；`create_outasset` 传入（`:77`） | `test_batch_c_fixes.py` 锁内前态 2 用例 + 向后兼容（`None`）用例 |
| `apps/usermanagement/services/department_service.py` | M-07 `_collect_ancestor_recordcodes`（`:117`，strip 重建补前导 `/`）+ `_invalidate_ancestors_cache`（`:180`）；`move_department` 捕获旧链（`:153`），根移动（`:158`）与普通移动（`:175`）两路径失效 | batch C 缓存失效 2 用例（`cache.delete` 断言） |
| `apps/authusermanagement/services.py` | M-08 `refresh_tokens` 轮换+黑名单包 `transaction.atomic`（`:215`）；`blacklist()` `IntegrityError`（`:219`）→ `TokenError`；import `:11` | batch C 竞态 2 用例（`IntegrityError→TokenError` 映射断言） |
| `core/permissions.py` + 14 生产调用点 | M-09 **方法感知 fail-closed**：`_SAFE_METHODS`（`:194`）+ `request_method`（`:197`）+ `resolve_viewset_permissions` 增 `method` 参数（`:207`）与 fail-closed 分支（`:235`，方法未知按不安全）；14 调用点统一 `method=request_method(self)`；唯一 POST-as-read 豁免 `hard_disk_sn_view.py:79` `action_overrides={"search_by_serial_number": IsAuthenticated}`（行级隔离 `get_queryset` 兜底） | batch C 方法感知 **11 用例**（写方法/小写方法/方法未知 fail-closed、GET 读面不变、overrides/export 优先级、`request_method` 三态）+ `test_rbac.py::test_default_is_authenticated` 补 `method="GET"`（`action=None→IsAuthenticated` 既有契约保留） |
| `config/settings/{base,development,test}.py` | M-10 `JWT_AUTH_COOKIE_SECURE`：base 缺省 `True`（`base.py:258`）+ `development.py:69` / `test.py:122` 显式 `False` | batch C 设置 3 用例（源码断言三环境口径） |

**M-09 方案演进留痕（Fact-1）**：首版按「未登记非读 action 即 deny」名单法（`_READ_ACTIONS={list,retrieve}`）→ 全量 **47 red**；`git stash` 隔离本批 7 文件后基线子集 **137 passed** 直证红系首版过宽（`by_asset`/`statistics`/`recyclable` 等**读语义 action** 被误升 admin），非存量回归 → 推翻重做为**按 HTTP 方法 fail-closed**（写方法/方法未知 → admin_permission；GET/HEAD/OPTIONS 读面零变化）。原 M-09 行「修复：缺省 deny/IsAdminUser」为**计划表述**，实际落地为方法感知方案（读面开放面不变、写面收口，写 action 本就全部登记于 admin_actions）。**schema 影响：无需重导**——drf-spectacular 只对 `AllowAny`/`IsAuthenticatedOrReadOnly` 作响应成员推断（openapi.py 实测），本修复不返回二者。

**门禁终态（2026-10-22 后端直证）**：**提交内容证绿**——`git stash push -u` 隔离 22 个 BF-128~130 遗留文件后（= 提交树纯度验证）全量 **2059 passed / 0 failed**；工作树全量 `pytest --cov=. --cov-fail-under=80` **2076 passed，cov 89.30% ≥80 exit 0**；`mypy --strict` **0 errors（228 files）**（CT-7 对齐 `dev.txt` mypy 2.1.0 / django-stubs 6.1.0 / drf-stubs 3.18.0）；`ruff check .` / `--select C90 --config lint.mccabe.max-complexity=10` / `ruff format --check .`（409 files）全绿；四护栏 PASS（BR-4 0 超限 / BR-6 0 超限·最高 `asset_view.py` 484/500 / G 重复不变量 / FR 前端不变量）；RBAC 子集回归 **137 passed**；新增 `test_batch_c_fixes.py` **20 用例** + `test_rbac.py` 40 用例全绿。T7 mutmut 本批未跑（如实申报）。

**2026-10-22 P2 批次 D 修复追踪（BF-136，后端两项 M-11/M-13：damaged 出边活跃单拦截 + 审计 on_commit 延迟）**：

> 修复批次：P2 批次计划 D（2026-10-22）。提交：backend `2abd578`（14 files，+322/−94；根指针 `07d086a`）。登记：BF-136。

| 文件 | 变更 | 验证（实测） |
|:---|:---|:---|
| `apps/assetmanagement/selectors/damaged_asset_selector.py` | M-11 新增 `has_pending_approval`（`:68`，`asset_recordcode` + `approval_status=PENDING` + `is_deleted=False`，DR-3 查询收敛唯一入口） | `test_asset_service` 参数化 6 出边拦截 |
| `apps/assetmanagement/services/asset_service.py` | M-11 `change_asset_status` 锁内守卫（`:327-335`：`old_status==damaged && 新态!=旧态 && has_pending_approval` → `ACTIVE_SCRAP_ORDER_EXISTS`；决策注释 `:322-326` 含用户拍板「全出边拦截」；单据闭环/无单据放行维持既有 manual 语义） | 先红后绿 **9 用例**（6 出边参数化拦截 + rejected/软删闭环放行 + 无单据放行，断言 `test_asset_service.py:290`）+ API 锚 `test_asset_view_api.py:322` 拆双例（待审批 400+error_code / 驳回闭环 200，AUD-05 锚保留） |
| `core/audit_service.py` | M-13 `log_operation`（`:27`）闭包 `_write_audit`（`:47`）经 `transaction.on_commit(_write_audit, robust=True)`（`:63`）延迟至主事务提交后执行；恒返回 None（rg 核 0 调用点消费返回值） | `test_batch_d_fixes.py`（`:20`）deferred/executed/swallowed 3 用例（红阶段 `DID NOT RAISE` 实证） |
| `apps/unregisteredasset/services.py` | M-13 `_safe_call_audit`（`:89`）闭包 `_run_audit`（`:97`）同构 `transaction.on_commit(_run_audit, robust=True)`（`:106`，B6 范式）；保留 P2-10 `logger.warning` 语义 | 同文件 safe_call deferred/swallowed 2 用例（红阶段 `assert 0` / `assert_not_called` 实证） |
| 7 测试文件 M-13 fallout 对齐 | on_commit 后回调不再即时执行 → `captureOnCommitCallbacks(execute=True)` 包裹 **26 用例**（asset_type/storage/contract_service/contract_view/unregistered/role/coverage；`with` 块退出时填充并执行回调故断言一律放块外；contract_view put 3 测试补早期回调 flush 保夹具基线口径 3 条） | 全量复跑 2091 passed / 0 failed；feishu `test_unknown_path_404` 单点首跑失败复跑 14/14 绿（瞬态甄别，非回归） |

**门禁终态（2026-10-22 后端直证）**：全量 `pytest --cov=. --cov-fail-under=80` **2091 passed / 0 failed，cov 89.33% ≥80 exit 0**；`mypy --strict` **0 errors（228 files）**（CT-7 对齐 `dev.txt` mypy 2.1.0 / django-stubs 6.1.0 / drf-stubs 3.18.0 / types-channels 4.3.0.20260518）；`ruff check .` / `--select C90 --config lint.mccabe.max-complexity=10` / `ruff format --check .`（410 files）全绿；四护栏 PASS（BR-4 0 超限 / BR-6 0 超限·最高 `asset_view.py` 484/500 / G 重复不变量 / FR 前端不变量）；`makemigrations --dry-run` 无遗漏。**T7 mutmut 本批实跑（WSL PG16）**：`rm -rf mutants && mutmut run` 全量 2068/2068 → gate exit 0，**83.4623% ≥80 且 ≥基线 83.25676365492598（+0.2055pt）**，killed=1726 / survived=342 / timeout=0 / no_tests=0 / suspicious=0；**观察（Fact-1）**：`change_asset_status` 整函数零变异体，属批次 D **前既有盲区**（批次 D 前后 totals 逐字节一致 2068 直证非本次引入——守卫为纯新增行、未删改既有行），守卫由 13 个行为测试覆盖（CT-1），盲区成因 [待核查] 入 BF-136 §六。

---

*融合生成：2026-10-20 | 核验方：本会话（对 NEW 条目抽查 9 项，全部落定：7 证实 / 1 未复现降级 / 1 环境裁决）| 2026-10-21 追加 §五：M-01 修复追踪（BF-125）；2026-10-21 续：BF-126 create 单通道 + BF-127 contract 读收口（O-7 留痕）——**AUD-21 授权面全链闭环**（批次1 数据层根治 codes None 消费方 → 批次2 register fail-closed → 批次3 create 单通道 → 批次4 contract 读收口），仓外唯一 [待确认] 生产注册面由 fail-closed 兜底挂 Gate #3；2026-10-21 再续：**M-02 分页稳定性修复闭环（BF-128，Gate #2 销项——8 模型 `Meta.ordering` + 3 处 `.first()` 锁序 + 9 分页点护栏先红后绿，上线前必办余 #3 环境变量核对）**，批外发现 AuthUser 无序分页与 `test_create_throttle` 存量红登记 BF-128 §六；2026-10-21 续：**批外双遗留收口（BF-129）**——throttle 存量红根因实证清零（全量 2046/0）+ AuthUser 登记定性订正与 `auth_id` 决胜键修复，BF-128 全项关闭，AUD-21 → BF-125/126/127/128/129 整链零未决；2026-10-22 续：**M-04 筛选/UI 脱节修复闭环（BF-131——composable 内 `reload()` 保筛选出口替换 `refresh: () => search()`，先红后绿 + 前端门禁四件套直证，P1 余 M-05）**；2026-10-22 续：**M-05 共享 Store 状态污染修复闭环（BF-132——`getList` 增 per-call `silent` 口 + 11 个非列表查询点收敛，手植变异先红×2 后绿 + 门禁四件套 + FR-8 护栏直证，P1 五条全部闭环）***；2026-10-22 续：**P2 批次 A/B/C 修复闭环（BF-133/134/135——批次 A createEntityStore 契约专项 M-15/16/18/20/21 + 批次 B 竞态/缓存/静默降级 M-12/14/17/19/22/25（含报告外 M-25 编号，连带销项 BF-132 §五 [待决策]）+ 批次 C 后端五项 M-06/07/08/09/10，共 16 项；M-09 首版名单法 47 red 经基线 137 甄别后重做为方法感知 fail-closed）**；2026-10-22 续：**P2 批次 D 修复闭环（BF-136——M-11 damaged 出边锁内活跃待审批单拦截 + M-13 审计写入 on_commit 延迟，先红后绿 + 26 测试 capture 对齐 + 全量 2091/0 + T7 实跑 83.4623% gate exit 0）——P2 计划批 A~D 全部闭环（18/19），余 M-24（未排批）**
