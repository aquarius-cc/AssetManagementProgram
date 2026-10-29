# 全项目审核报告（opencode · CodeGraph 增强版 · 2026-10-27）

> 模式：纯审计不修复（skill v1.2.0）。全程只读，未改动任何业务代码，唯一落盘为本文件。
> 范围：框架 / 架构 / 逻辑 / 业务流程 / 完整度 / 可上线性（Django+DRF 后端 + Vue3 前端双端全量）。
> 仓库锚点：superproject `394efce`、backend 子仓 `817a745`、frontend 子仓 `8391217`（工作区干净，`git status` 零改动）。
> 方法：CodeGraph（1,022 文件 / 18,196 节点 / 41,206 边，索引 up to date）符号定位与影响面 + 2 个 explore 子代理分域语义走查 + 门禁命令本地实测 + `gh run list` CI 直证。

---

## §一 项目上下文

### 1.1 技术栈与模块边界

| 层 | 技术 | 边界 |
|---|---|---|
| 后端 | Django + DRF + drf-spectacular，PostgreSQL，Redis（WS/缓存/限流），JWT 双通道（cookie/bearer） | 五层架构：Model → Selector → Service（`@transaction.atomic`）→ Serializer → View，`utils/response_utils.py` 为响应根结构唯一入口 |
| 前端 | Vue3 + TS + Vite + Pinia + Element Plus + ECharts | `api/request.ts` 拦截器单出口、`stores/createEntityStore.ts` 实体工厂、`router/guards.ts` 路由守卫 |
| 状态机 | `state_machine/`（AssetFSM 8 态 + 4 mixin；ContractFSM 8 态） | 所有 `asset_current_status` 写点收敛于 `state_machine/` 包内 |
| 可观测/安全 | `core/request_context.py`（trace_id）、`core/throttles.py`、`.github/workflows/`（ci.yml / security-scan.yml / ci-cd.yml） | 健康端点 `/health/`、`/ready/`（`config/urls.py:152-153`） |

### 1.2 本次分域探索清单与结构事实

| 分域 | 图谱锚点 | 结构结论 |
|---|---|---|
| 资产状态机 | `state_machine/constants.py:27 AssetState`、`transitions.py:28 VALID_TRANSITIONS`、`core.py:31 AssetFSM` | 8 态 + 19 条具名边 + reject/cancel 特殊回退，与 `backend-business-rules.md` §三规则表逐行一致（人工比对） |
| 合同状态机 | `state_machine/contract_fsm.py:15 ContractState / :57 ContractFSM` | 8 态线性链，`allowed_next_states` 读路径防御返回 `[]` |
| API 响应契约 | `utils/response_utils.py:23 success_response` | 174 个调用方；全仓 `return Response(` 扫描仅命中 `urls.py:142`（**docstring 教程示例，非代码**）与 `pagination.py:122`（注释）→ 无手写 dict 旁路 |
| 前端状态枚举 | `types/asset.ts:46-53` | 8 键与后端 `AssetState` 完全同集（`in_store/in_use/recycled_pending/broken/repairing/lost/damaged/scrapped`） |
| 测试锚 | `tests/test_state_machine.py`（48 个用例）、`tests/test_damaged_asset_service.py` 等 | 后端全量 2,210 用例本地实跑通过（§1.3） |
| 鉴权/行级隔离 | `core/permissions.py`、`core/department_scope.py`、各 ViewSet `get_permissions` | 本轮新发现 3 处 update 路径绕过（见 RC-01/03/04） |
| 批量导入/导出 | `core/excel_export/`、前端 `utils/batchImport/` | 结构健康，无上传攻击面（§5.3） |

### 1.3 门禁实测记录（本地，仓库根或子仓内执行）

| 门禁 | 命令 | 结果 |
|---|---|---|
| 后端全量测试 | `pytest -q --no-cov`（backend，26:42） | **2,210 passed / 0 failed**，exit 0 |
| 后端覆盖率 | `pytest --cov=. --cov-fail-under=80` | 本地两轮分别超时/被中止（第一轮达 97% 进度），**本轮未取得本地完整结论**；按 CT-7 引用 CI 权威：Pipeline `40466576631` → backend-coverage **90.09%**（11,220/1,112，210/0） |
| ruff | `ruff check .` / `ruff format --check .` | **All checks passed** / **420 files already formatted** |
| BR-4 函数长度 | `python scripts/check_function_length_guard.py` | **[PASS] 0 超限** |
| BR-6 文件长度 | `python scripts/check_file_length_guard.py --print` | **exit 0**（最大 `asset_view.py` 488 逻辑行 < 500） |
| 重复代码护栏 | `python scripts/check_duplicate_invariants.py` | **PASS** |
| 前端全量测试 | `npx vitest run`（vue-assetmanagement） | **176 files / 2,280 passed / 0 failed**（173s） |
| 前端依赖漏洞 | `npm audit --omit=dev` | **found 0 vulnerabilities**，exit 0 |
| 后端依赖漏洞 | `python -m pip_audit -r requirements/base.txt` | 本地失败两次（GBK 解码→UTF-8 后 **PyPI 连接被重置 10054**，本机网络不可达）→ **留痕：以 CI `security-scan.yml` 为权威门禁**（§5.3 SC-8 兜底条款） |
| CI 直证 | `gh run list` | head `394efce` 上：CI Pipeline `40477939110` ✅、Dependency Security Scan `40477939266` ✅（docs-only push，pip-audit/npm audit job **0s 跳过**，仅密钥扫描+汇总执行）、CD Pipeline `40477970380` ✅（安全门禁校验 + Docker Build & Push 全绿） |

---

## §二 问题台账（20 条：P1×3 / P2×8 / P3×8 / 待确认×1）

> 四要素已并入表内：修复建议（方案方向）+ 影响面（`codegraph impact`/`callers` 实测）+ 建议验证方式。回查命令固定为 `codegraph node/callers <symbol>`。
> 状态口径：本 skill 只产生 **已确认 / 待修 / 不采纳**，不产生「已修复」。

### 2.1 后端（RC-01 ~ RC-06）

| ID | 级别 | 类型 | file:line | symbol | 描述（证据） | 修复建议 | 影响面 | 建议验证方式 | 回查命令 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|
| **RC-01** | **P1** | 行级隔离绕过（越权写） | `views/hard_disk_sn_view.py:97,109,112` → `services/hard_disk_sn_service.py:65,115` → `selectors/hard_disk_sn_selector.py:24` | `HardDiskSNService.update` / `.delete` | update/partial_update/destroy 直接取 `self.kwargs["recordcode"]` 调 Service；Service 经 `get_by_recordcode(recordcode)` 查询，**无 user 参数、无部门过滤**；文件虽有 `get_queryset()`（:67，作用域）与 `RecordcodeLookupMixin`（`get_object()` 作用域），但三方法均未调用。同文件批量路径 `batch_save(..., user=)` 有 `_resolve_asset(user=user)` 行级校验（:142），单条路径缺失 | 三方法改走 `self.get_object()`（作用域内取对象），或 Service 增加 `user=` 参数并复用 `get_queryset_for_user` 过滤 | `codegraph impact HardDiskSNService.update`：9 符号（view update/partial_update + 5 service 测试 + integrity 测试）；越权面：asset_admin A 部门可 PATCH/DELETE B 部门硬盘记录 | 新增跨部门用例：deptA admin PATCH/DELETE deptB 的 recordcode → 期望 404；现有 `test_hard_disk_sn_service.py` 5 例仍绿 | `codegraph callers HardDiskSNService.delete` | **待修** |
| **RC-02** | **P1** | 状态机旁路（维修记录） | `serializers/repair_asset_serializers.py:60-81`（`repair_status` ∈ fields，无 `read_only_fields`、无 `validate_repair_status`）+ `views/repair_asset_view.py:136-142`（`get_serializer_class` → UpdateSerializer）且**无 update/partial_update 覆盖** | `RepairAssetUpdateSerializer` | DRF 默认 `UpdateModelMixin.update` 使 `PATCH {"repair_status":"completed"}` 直接落库：① 绕过 `fail_repair`/`repair_done` 的 `repair_status=IN_PROGRESS` 前置查找（`repair_asset_service.py:278-282`），正常完结流程被写死、无操作审计；② `repair_status:"in_progress"` 撞 `uniq_active_repair_per_asset`（`models/repair_asset.py:95-99`）→ 无 IntegrityError 映射 → **500** | `repair_status` 移入 `read_only_fields`（或覆写 `perform_update` 走 Service），并为该路径补 IntegrityError 映射 | `codegraph impact RepairAssetUpdateSerializer`：17 符号（serializers `__init__`、全部 View 文件 import 链、`repair_asset_view.get_serializer_class`） | 新增用例：PATCH repair_status → 断言字段被忽略（不变）；并发双 in_progress → 4xx 映射消息而非 500 | `codegraph node RepairAssetUpdateSerializer` | **待修** |
| **RC-03** | P2 | 行级隔离绕过（窄面） | `views/recycle_asset_view.py:133-146` → `services/recycle_asset_service.py:297-327` | `RecycleAssetService.update_recycle_asset` | update/partial_update 取 kwargs recordcode 直查 `RecycleAsset.objects.filter(recordcode=…)`，无 user 过滤（同文件 destroy :214 已正确 `get_object()`）。缓解：`RECYCLE_ASSET_UPDATE_ALLOWED_FIELDS`（:24-30）白名单仅日期/类型/描述 3 字段 | 与 destroy 对齐改 `self.get_object()` | `codegraph impact ...update_recycle_asset`：10 符号（view update/partial_update + 7 测试） | 跨部门 PATCH recycle recordcode → 404；`test_recycle_asset_service.py` 更新用例仍绿 | `codegraph callers RecycleAssetService.update_recycle_asset` | **待修** |
| **RC-04** | P2 | 行级隔离缺失（create） | `views/hard_disk_sn_view.py:83-95` → `services/hard_disk_sn_service.py:29-61` | `HardDiskSNService.create` | 单条 create 未对 `data["asset_recordcode"]` 做可见性校验（batch 路径有 `_resolve_asset(user=user)`，:142）；docstring 声称「校验关联资产存在」与实现不符（存在性实际由 Serializer FK → 400 兜底，但**部门可见性**无人校验） | 复用 `_resolve_asset(..., user=user)`（DR-1，与 batch 同一实现） | view create 1 个调用方 + `test_hard_disk_sn_service` create 系列 | 跨部门 asset_recordcode 创建 → 期望 `ASSET_NOT_FOUND`；docstring 与实现一致 | `codegraph callers HardDiskSNService.create` | **待修** |
| **RC-05** | P3 | 审计缺口 | `views/_lifecycle_base.py`（`update`/`partial_update` 未覆写，走 DRF 默认 `serializer.save()`） | `AssetLifecycleViewSetBase.update` | `create/destroy/batch_delete` 均经 AssetLifecycleMixin 落审计，update 留默认路径：日期/原因/描述改动**无操作日志**。缓解：`lifecycle_serializers.py` FK 全 read_only，**状态不可被写**，无状态机风险 | 覆写 update 走 Service+审计（与 create 同范式） | Broken/Lost/Found 三个 ViewSet 的 update 路径 | 新增 update 后断言存在 `AssetOperationLog` 行 | `codegraph node AssetLifecycleViewSetBase` | **待修** |
| **RC-06** | P3 | 并发竞态（500 兜底缺失） | `services/asset_service.py:109-164` | `AssetService.create_asset` | `AssetCodeGenerator.generate_with_unique_check` 为 check-then-act：并发双建同码可通过预检，其一撞 `unique_asset_code_not_deleted` → 未映射 → 500（`@transaction.atomic` 回滚，数据无损）；`qr_code` 非客户端可写，第二唯一约束不可达 | 接 `core/exceptions.py:147 match_integrity_error_rules`（仓内 7 处先例） | create 路径 + `test_asset_service` | 并发 mock 双写断言映射消息（仿 M-45 employee 用例） | `codegraph node AssetService.create_asset` | **待修** |

### 2.2 前端（RC-07 ~ RC-18）

| ID | 级别 | 类型 | file:line | symbol | 描述（证据） | 修复建议 | 影响面 | 建议验证方式 | 回查命令 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|
| **RC-07** | **P1** | RBAC 前端权限面缺口 | `router/routes-main-core.ts:84-101`（AssetForm/AssetBatchImport meta 无 `requiredMinRole`）、`routes-main-system.ts:189-196`（AssetFormDirect 同）、`guards.ts:75-82`（roleWhitelist 未列路径 **`return true` 默认放行**）、`components/AsideMenu.vue:45`（资产录入菜单项无 `v-if`，同段其余项均有）、`BasicAssetDetails.vue:28-30`（「编辑」「导出」按钮无 `v-if`，而 :35-70 其余 9 个操作按钮全部 `v-if="canXxx && canOperateAsset"`，主代理已逐行核读） | `checkRoleAccess` | 权限矩阵规定「新增/编辑/删除」「批量导入」对 `regular_user`/`auditor` ❌（`backend-business-rules.md:138-139`），但受限角色可从菜单、详情页编辑按钮、直接输 URL 三条路径进入录入/编辑/批量导入页完整填写，仅提交时被后端 403 拒绝 → 信息暴露 + 误导性可操作界面（后端仍拦截，**非越权写入**） | 三条路由补 `meta.requiredMinRole: 'asset_admin'`（父路由补即可，参照 `contractdetails` 范式）；`AsideMenu.vue:45`、`BasicAssetDetails.vue:34` 补权限 `v-if`；表单 `onMounted` 走 `useOperationGuard.guardOnMounted()` | `codegraph impact checkRoleAccess`：守卫链 `handleAuthenticated → setupAuthGuard`（全路由）；菜单/按钮两处为静态模板改动 | 用例：regular_user 登录 → 直达 `/main/assetform` 被 303 拦截；菜单不渲染「资产录入」；guards.spec 补 deny 断言 | `codegraph callers checkRoleAccess` | **待修** |
| **RC-08** | P2 | 缓存一致性 | `api/request.ts:367-376`（按写 URL 自身清缓存）、全仓 `clearCacheByPattern` 调用点**仅** `api/asset.ts:162,174,300,303,377,394` | `clearCacheByPattern` | 以下改状态写端点未失效 `/assets/assets/{recordcode}/`（`getAssetByCode` useCache 5min）：`repairAsset.ts:126,144,158`（repair/repair-done/repair-failed，**同基路径子路径，key 不匹配**）、`lostAsset.ts:138,159`、`damagedAsset.ts:121,134`（approve/reject，连自身详情 key 也不失效）、`recycleAsset.ts:62`、`outAsset.ts:97`、`wasteAsset.ts:61`、`foundAsset.ts:42`、`brokenAsset.ts:44`。对照组 `asset.ts:300` 对 mark-broken 已显式失效（M-54 仅修了这一处） | 抽共享 helper（DR-1）：状态类写端点成功后统一 `clearCacheByPattern('/assets/assets/${recordcode}/')`；approve/reject 另失效 damaged 详情 key | 15 处 `useCache` 端点中至少 9 个写端点受影响；返回详情页显示旧状态 | 新增用例：repair 成功后 `getAssetByCode` 二次调用实际打网（cache miss） | `codegraph callers clearCacheByPattern` | **待修** |
| **RC-09** | P2 | 提示双发（错误） | `api/request.ts:393 notifyApiError`（非 401 必弹）+ 调用方二次弹窗：`useRecycleFormSubmit.ts:95`、`useAssetOperationForm.ts:122-123`、`usePaginationSearch.ts:99`、`usePaginationSearchState.ts:109,201`、`RoleManage.vue:165`、`AuthUserManage.vue:201`、`SmartListContainer.vue:174` | `notifyApiError` | 400/404/500 场景拦截器先弹、调用方 catch 再弹；`useAssetOperationForm.ts:123` 还用 `options.errorMessage \|\| '操作失败'` **覆盖后端业务消息**；`suppressDefaultError` 已标 `@deprecated` 且生产零调用 | 错误提示收敛为拦截器单一出口（调用方只补上下文），或让 suppress 机制真正生效并全量接入 | 全部非权限类失败路径的 UX；`notifyApiError` 影响面= request.ts 单文件 + 全部 api 调用方 | 抽查用例：mock 400 断言 `ElMessage.error` 只调用 1 次 | `codegraph node notifyApiError` | **待修** |
| **RC-10** | P2 | 提示双发（成功） | `stores/createEntityStore.ts:370`（唯一 `disableAutoMessage` 检查点，在 create 内）、`:388-390` update、`:408-410` remove 无条件 `message.success` | `createEntityStore` | 3 个 store 设了 `disableAutoMessage:true` 但仅 create 分支生效 → update/remove 必双弹；已核实双弹实例 ≥8 处（AssetForm:375→379、StorageForm:177→184、ContractForm:449、UserForm:331、DepartmentForm:190、AssetTypeForm:180、OutAssetForm:426、UnregisteredAssetForm:443 等）。附带：`brokenAssetStore.ts:28 displayName:'Broken Asset'` 英文文案外泄 | 判断上提为 create/update/remove 三处统一守卫；`displayName` 改中文 | `codegraph impact createEntityStore`：**176 符号**（23 个实体 store + 全部列表/表单组件）——建议以「三处守卫」最小 diff 落地 | 新增用例：disableAutoMessage 时 update/remove 不弹；表单组件自身提示仍 1 条 | `codegraph node createEntityStore` | **待修** |
| **RC-11** | P2 | 可观测性（OC-1 断链） | `utils/logger.ts:21-28`（会话级 `sessionTraceId`，`resetTraceId` 生产零调用）、`api/request.ts:343`（每请求 `generateTraceId()` 新 UUID） | `sessionTraceId` | 前端日志 trace_id（会话单值）与发往后端的 `X-Request-ID`（每请求随机）**不同源**；响应拦截器不读取后端回传 `X-Request-ID` 同步 → 拿后端日志 id 到前端 grep 无结果，反之亦然（后端 `core/request_context.py:53` 以 `HTTP_X_REQUEST_ID` 为 trace_id） | 请求拦截器复用 logger 的 sessionTraceId（或响应回填同步）；登录/登出调 `resetTraceId()` | 全部前后端链路排障；单点改动 request.ts + logger.ts | 双端各发 1 请求，断言前端日志 trace_id == 后端日志 trace_id == 响应头 | `codegraph node sessionTraceId`（或 `rg resetTraceId src`） | **待修** |
| **RC-12** | P2 | 错误吞没（降级无标识） | `api/request.ts:400-407`（`tryFallbackCache` 置 `_degraded:true`）、`:494-501`（get 失败静默返回缓存）、`:70` | `tryFallbackCache` | `_degraded` 全仓仅定义+测试，**零生产消费者**（`rg _degraded src` 命中 request.ts:70,406 + 2 spec）：GET 失败时用户收到错误 toast 但页面渲染 5 分钟前旧数据、无任何降级标识，看似加载成功；15 处 useCache 端点受影响 | 视图/store 消费 `_degraded` 统一提示「当前为缓存数据」（或降级时单次 toast） | 15 个 useCache 端点（asset/storage/contract/user 等详情与列表） | 用例：mock GET 失败 + 有缓存 → 断言 UI 出现降级提示 | `codegraph callers tryFallbackCache` | **待修** |
| **RC-13** | P2 | 并发竞态（清空表格） | `stores/createEntityStore.ts:225-227`（过期返回 `undefined`，约定「视图判空保留现有数据」）违例消费端：`RoleManage.vue:162`、`AuthUserManage.vue:197`、`ContactsView.vue:179`、`useAssetListConfig.ts:122`、`useSmartListConfig.ts:84,122`（均 `res ?? []`） | `getList`（seq 作废路径） | 并发两次 getList 中慢的旧请求被 seq 作废 → 返回 `undefined` → `?? []` 翻译成「权威空集」写入 ref → 表格被清空；若新请求同时失败则停留空态 | 消费端对 `undefined` 显式跳过写入（`if (res === undefined) return`） | 5 个列表消费端（角色/用户/通讯录/资产列表/智能列表） | 用例：并发双请求旧响应晚到 → 断言列表数据保持不变 | `codegraph callers syncListToState` | **待修** |
| **RC-14** | P3 | 路由加固 | `router/routes-standalone.ts:89-96`（ScrapAsset meta 仅 title/requiresAuth，同批 :75/:85 等 7 条均有 `requiredMinRole:'asset_admin'`） | `ScrapAsset` 路由 | 报废申请页漏配（实际兜底：`useAssetOperationForm.ts:134 → guardOnMounted()` 提交前拦截）→ 界面暴露，非可利用越权 | 补 `requiredMinRole: 'asset_admin'` | 1 条路由 + 与 RC-07 同批测试 | regular_user 直达 `/assets/:code/scrap` → 303 | `codegraph node ScrapAsset`（或 guards.spec） | **待修** |
| **RC-15** | P3 | 死代码 | `services/assetLifecycleService.ts:31,44,62,75` | `handleAssetOut/Recycle/Damaged/Waste` | `rg -ln assetLifecycleService src` 仅命中自身与 spec：**零生产调用方**；内部 `assetStore.getList()` 无参调用会重置分页，一旦误接入即污染列表态 | 删除模块及其 spec（或迁移到真实调用点） | 1 文件 + 1 spec | 删除后全量 vitest 仍绿 | `codegraph callers handleAssetOut` | **待修** |
| **RC-16** | P3 | 死代码/默认值陷阱 | `stores/createEntityStore.ts:69`（`enableCache=true` 默认开）、`entityStoreRequestControl.ts:51,103` | `enableCache` | 23 个 store 全部显式 `enableCache:false` → 缓存读写恒不生效、`clearCache` 零调用；风险在默认值：未来新 store 忘设即静默启用一条从未被生产验证、无失效策略的缓存 | 默认值翻转为 `false`（或整体移除缓存层与其测试） | `createEntityStore` 工厂（176 符号 blast radius 内的配置项） | 默认值改后全量 store 测试仍绿；新增 store 不带 enableCache 时行为=不缓存 | `codegraph node createEntityStore` | **待修** |
| **RC-17** | P3 | 权限判据双轨 | `AsideMenu.vue:163-166`（权限码 `hasPermission`）vs `guards.ts:59-83`（角色层级 + roleWhitelist） | `checkRoleAccess` / `hasPermission` | 两套判据来源不同（后端权限码 vs JWT 角色）：有码无级→菜单可见进页被拦；有级无码→菜单隐藏但直达可进；且 `guards.ts:69-73` 一旦声明 requiredMinRole 即跳过 roleWhitelist（两白名单互斥）。**是否真实错配取决于后端权限码种子分配 → [待确认]** | 统一单一判据（建议权限码为唯一事实来源），或 CI 加「菜单可见项↔路由可进项」一致性断言 | 全部菜单项与守卫 | 种子数据核对后补一致性用例 | `codegraph callers checkRoleAccess` | **待确认**（证据<80%，不计入缺陷） |
| **RC-18** | P3 | 并发竞态（窄窗） | `stores/createEntityStore.ts:358-368`（create unshift+total+=）、`:398-407`（remove total--）、`:181-194 syncListToState`、seq 仅在 getList 内 bump（:104,221） | `createEntityStore.create/remove` | 写操作改 `pagination.total` 与 ids 但不 bump `listRequestSeq`：在途旧 getList 返回后整体重写 → 已删行复活/新建行抹除/total 回退；窗口窄，`setRefreshFlag` 路径下次刷新自愈 | 写操作成功后 `listRequestSeq++`（作状态版本号） | 23 个实体 store 的列表一致性 | 用例：写操作期间注入在途旧响应 → 断言列表不回滚 | `codegraph node createEntityStore` | **待修** |

### 2.3 不采纳 / 留痕

| ID | 内容 | 处置与理由 | 状态 |
|---|---|---|---|
| RC-19 | `fail_repair` 的 DamagedAsset insert 无 IntegrityError 映射 | 子代理自评置信度 <80%（无法构造资产 repairing 时存在活动 DamagedAsset 的可达路径，M-11 与 reject 软删已挡）→ 按置信度门槛**不报告为缺陷**，留痕备查 | **不采纳**（置信度不足） |
| RC-20 | `urls.py:142 return Response({'status':...})` 疑似响应契约旁路 | 人工核读：该行位于模块尾部**教程 docstring 内**（示例代码），非可执行路径；`pagination.py:122` 同为注释 → 响应根结构**无旁路** | **不采纳**（误报排除） |

---

## §三 分域结论与修复建议（按优先级排序）

### 3.1 分域结论

| 分域 | 结论 | 依据 |
|---|---|---|
| 资产/合同状态机 | **健康（双证）** | 生产代码 `asset_current_status` 写点 100% 收敛于 `state_machine/`（rg 实测，旁路 **0 处**；`unregistered.py:56/88/126` 三处直写为已声明例外+前置守卫，M-60/BF-161 留痕）；`VALID_TRANSITIONS` 与规则 §三逐行一致；`test_state_machine.py` 48 用例；Serializer 层 `asset_current_status` 仅出现在查询 serializer（CombineSearch/GroupQuery，读语义）与 update 白名单外（`utils/update_whitelist.py` 零命中） |
| 行级隔离（View→Service） | **发现 3 处缺口（RC-01/03/04）** | 焦点在「update 路径不用 `get_object()`」模式；其余 ViewSet（asset/damaged/out/unregistered/contract/storage/asset_type）已核对走 `get_object()` 或 Selector user 参数（子代理反向核对清单 + 本轮抽查） |
| 维修状态机外围 | **1 处旁路（RC-02）** | `repair_status` 客户端可写，绕过 Service 完结流程与审计，且可触发唯一约束 500 |
| API 跨端契约 4 项 | **全部通过** | ① 响应根结构：`success_response` 唯一入口，`return Response(` 扫描无生产旁路（RC-20 误报排除）；② 状态枚举：前后端 8 键同集（`types/asset.ts:46-53` vs `AssetState`）；③ 分页：业务调用全部 `page_size`（`pageSize` 仅组件内部状态，wire 层零命中）；④ 日期：`USE_TZ=True` + `TIME_ZONE=Asia/Shanghai` → DRF ISO 8601 含 `+08:00`，前端 `Format.ts` 本地时区解析（规避 toISOString UTC 偏移，:84 注释） |
| 安全红线 SC-1~SC-8 | **通过（SC-8 以 CI 为权威）** | SC-1：后端仅 `.env.example` 入库（占位符），`production.py:14-34` 强制环境变量+弱密钥拒绝；前端入库 `.env.production/.env.production.test` 均无密钥（`VITE_TOKEN_CRYPTO_KEY` 仅注释行），真实值 `.env.development` 被 `.gitignore:20` 忽略 → **仓库零硬编码密钥**；SC-3：raw SQL 仅 `config/urls.py:70,117` 静态 `"SELECT 1"` 与运维脚本 `scripts/clear_database.py`（f-string 表名来自 DB introspection，非用户输入，SC-4 语义满足，建议后续参数化留痕）；SC-5/6：**不适用**（全仓无 `FileField/request.FILES/MultiPartParser`，rg 零命中）；SC-8：本地 pip-audit 因网络不可达失败（留痕），`npm audit --omit=dev` 0 漏洞；CI security-scan head 全绿（最近一次完整 pip-audit 红为 run `40438959499`，即 BF-159 记录的 twisted 5 项待 26.10.0，此后 docs-only push 均路径跳过） |
| 可观测性 | **OC-6 ✓ / OC-1 跨端断链（RC-11）** | `/health/`、`/ready/` 存在（`config/urls.py:152-153`）；前端日志结构化 5 字段齐（OC-2 ✓）；但 trace_id 前后端不同源（RC-11） |
| 测试与规模 CT/DR | **全绿（本地实测）** | 2,210/0 后端、2,280/0 前端、BR-4 0 超限、BR-6 exit 0、重复护栏 PASS、ruff 双 0；覆盖率本轮本地未取得完整结论，按 CT-7 引用 CI 90.09%（见 §1.3） |
| 前端 RBAC/业务流程 | **1 P1 + 6 P2**（RC-07~RC-13） | 界面权限面缺口（后端仍拦）、缓存失效不全、提示双发、降级无标识、过期响应清空表格 |

### 3.2 修复批次建议（可直接交接 bug-surgical-fix / rigorous-dev）

| 批次 | 条目 | 动作摘要 | 验证门槛 | 预期收益 |
|---|---|---|---|---|
| **R-1 行级隔离收口（最高优）** | RC-01 → RC-03 → RC-04 | RC-01 三方法改 `get_object()`（同文件 destroy/batch 已有范式，diff 极小）；RC-03 对齐 destroy；RC-04 复用 `_resolve_asset(user=)` | 新增 3 个跨部门 404 用例 + `test_hard_disk_sn_*`/`test_recycle_asset_service` 全绿 + 全量 pytest | 消除 2 个跨部门越权写入口 |
| **R-2 维修状态机外围** | RC-02 | `repair_status` → `read_only_fields`（或 update 走 Service）+ 唯一约束 IntegrityError 映射 | PATCH repair_status 断言被忽略 + 并发双 in_progress 断言 4xx 映射 | 消除状态机旁路与 500 |
| **R-3 前端权限面** | RC-07 + RC-14（同型合并） | 4 条路由补 `requiredMinRole` + 菜单/编辑按钮 `v-if` + 表单 guardOnMounted | guards.spec 新增 deny 断言；regular_user 直达 URL 被拦 | 受限角色不再看到不可用操作界面 |
| **R-4 缓存与竞态** | RC-08 + RC-13 + RC-18（同域合并） | 共享失效 helper 铺开至 9 个状态写端点；5 处 `?? []` 改跳过写入；写后 bump seq | 缓存失效用例 + 并发清空用例；全量 vitest | 消除「操作后详情 5 分钟旧状态」「表格偶发清空」 |
| **R-5 提示与降级 UX** | RC-09 + RC-10 + RC-12 | 错误提示单出口；`disableAutoMessage` 三处统一守卫；`_degraded` 消费提示 | ElMessage 调用次数断言；降级提示用例 | 消除双弹与静默旧数据 |
| **R-6 观测与整洁** | RC-11 + RC-15 + RC-16 + RC-05 + RC-06 | trace_id 同源；删死代码；缓存默认值翻转；lifecycle update 补审计；create_asset 接 matcher | 双端 trace_id 一致性断言；删除后全量绿；审计行断言；并发映射用例 | 可观测性闭环 + 死代码清零 |
| **留痕** | RC-17（待确认）、RC-19/20（不采纳） | RC-17 需先核对后端权限码种子分配再定；RC-19 置信度不足不修；RC-20 已排除 | — | — |

**顺序**：R-1 → R-2（安全相关，先落）→ R-3 → R-4 → R-5 → R-6。R-1/R-2 完成前不建议对外暴露写接口给受限部署环境。

### 3.3 可上线性综合判定

**结论：有条件可上线（无 P0 阻断项，但有 2 个 P1 建议修复后再放量）。**

| 维度 | 状态 | 证据 |
|---|---|---|
| 功能回归 | ✅ 全绿 | 本地后端 2,210/0 + 前端 2,280/0（今日实测） |
| 静态门禁 | ✅ 全绿 | ruff check/format 0、BR-4/BR-6/重复护栏 PASS；vue-tsc/eslint 以子仓提交记录 `8391217`「三项 0」+ 今日 vitest 复跑为据 |
| 覆盖率 | ✅（CI 权威） | CI Pipeline `40466576631` → 90.09% ≥ 80%；本地本轮未取得（CT-7：以 CI 为准） |
| 依赖安全 | ⚠️ 条件绿 | head 上 security-scan/CD 全绿（`40477939266`/`40477970380`）；但最近一次**完整** pip-audit（`40438959499`）红于 twisted 5 项（BF-159，等 26.10.0 正式版），此后 docs-only push 均路径跳过 → **下次依赖文件变更或每周定时全量扫描会再次红**，属已知遗留非新发现 |
| 安全越权 | ⚠️ 2×P1 | RC-01（跨部门硬盘改删）、RC-02（维修状态可写）——均需已认证 asset_admin 角色，**非匿名面**；内网/低敏部署可带风险上线，多部门隔离场景建议先修 R-1/R-2 |
| 跨端契约 | ✅ | 4 项全通过（§3.1） |
| 状态机完整性 | ✅ | 旁路 0 处（声明例外 3 处有留痕） |

---

## §四 可复核命令（本报告全部结论的取证入口）

```bash
# 索引与结构
codegraph status
codegraph explore "资产状态机 AssetState VALID_TRANSITIONS AssetFSM" --max-files 8
codegraph node VALID_TRANSITIONS; codegraph node success_response

# 状态机旁路（生产写点收敛验证）
rg -n "\.asset_current_status\s*=" asset_management_backend -g '*.py'   # 期望：仅 state_machine/ 与 tests

# RC-01/03/04 取证
codegraph node HardDiskSNService.update; codegraph node RepairAssetUpdateSerializer
rg -n "def update|get_object" asset_management_backend/apps/assetmanagement/views/recycle_asset_view.py
rg -n "repair_status" asset_management_backend/apps/assetmanagement/serializers/repair_asset_serializers.py

# RC-07 取证
rg -n "requiredMinRole" vue-assetmanagement/src/router/routes-main-core.ts
sed -n '59,83p' vue-assetmanagement/src/router/guards.ts        # 默认放行 return true

# 契约 4 项
rg -n "return Response\(" asset_management_backend/apps -g '*.py'   # 期望仅 docstring
rg -n "page_size" vue-assetmanagement/src/api | head               # wire 层无 pageSize
rg -n "IN_STORE|SCRAPPED" vue-assetmanagement/src/types/asset.ts    # 8 键

# 门禁
cd asset_management_backend && python -m pytest -q --no-cov        # 2210 passed
python scripts/check_file_length_guard.py --print                  # exit 0
python scripts/check_duplicate_invariants.py                       # PASS
cd vue-assetmanagement && npx vitest run && npm audit --omit=dev   # 2280 passed / 0 vulns
gh run list --limit 6                                             # CI/CD 直证
```

---

## §五 评审结论（阶段 5 · 报告质量自审）

| 检查项 | 结论 |
|---|---|
| 索引覆盖 | ✅ `codegraph status`：1,022 文件 / up to date，无 missing 告警后才进入诊断 |
| 台账完整性 | ✅ 20 条均具备 级别/类型/file:line/symbol/回查命令 五要素（RC-17/19/20 为待确认与不采纳，按口径不计入缺陷） |
| 专项覆盖 §5 | ✅ 5.1 旁路扫描（rg 全量写点）+ 规则表逐行比对 + 48 用例；5.2 契约 4 项逐条命令取证；5.3 SC-1（git ls-files + settings 源码）/SC-3（rg raw SQL）/SC-5-6（rg FILES，零命中=不适用）/SC-8（npm audit 实测 0 + pip-audit 网络失败留痕 + CI 直证）/OC-6（rg urls）；5.4 两护栏+重复护栏实测 + 测试双端实跑（覆盖率按 CT-7 引 CI） |
| 报告闭环 | ✅ 3 条 P1 全部具备 证据+影响面（codegraph impact 实测）+修复建议+建议验证方式；无遗漏 P0（本轮 0 个 P0） |
| 建议可执行性 | ✅ 每条含 file:line + symbol + 方案方向 + 验证方式，R-1~R-6 批次可被修复 skill 直接接手 |
| 置信度 ≥80 | ✅ 全部入账条目经主代理二次源码核读（RC-01/02/03 逐行读源码、RC-07 读 guards/路由/菜单三处）；<80% 的 RC-19 已剔除至不采纳 |
| 只读纪律 | ✅ 本会话未改动任何业务代码；唯一写入为本报告文件；测试运行产生的 `.coverage`/缓存属工具产物 |
| 与前序审计（Merge-audit-2026-10-26 M-40~M-63）关系 | ✅ 无重复条目：M 系列聚焦门禁/依赖/通知/缓存(mark-broken 单点)，本轮 20 条均为**新发现**（RC-08 与 M-54 同域但覆盖其余 9 个写端点，属扩展非重复） |
