# CodeGraph 全项目审计报告（2026-10-20）

> 模式：纯审计（不修改业务代码） | 基线：`docs/Review/codegraph-audit-2026-10-18.md`（AUD-01~20 已于 10-19/10-20 修复闭合）
> 工具链：CodeGraph 索引（988 文件 / 17,525 节点 / 39,447 边，状态 up-to-date）+ 直读源码 + 门禁命令实测

---

## §一 项目上下文

### 1.1 审计范围与方法

| 项 | 内容 |
|:---|:---|
| 审计对象 | 根仓 `AssetManagementProgram`（后端 `asset_management_backend` / 前端 `vue-assetmanagement` / 脚本 `scripts/` / CI `.github/workflows/`） |
| 审计方法 | 五阶段：框架概览 → 架构/契约 → 逻辑与业务流程 Bug → 完整度 → 部署评估；CodeGraph 供结构事实，语义结论以源码直读为准 |
| 回归复核 | AUD-01~20（10-18 报告）逐条回归验证，结论见 §二.0 |
| 未执行项 | 生产环境实机验证（无生产访问）、E2E 浏览器验证、`mutmut` 变异全量重跑（以 10-20 BF-124 基线记录为准）——均标注 `[x] 未执行+原因` |

### 1.2 门禁命令执行结果（2026-10-20 本机实测）

| 门禁 | 命令 | 结果 |
|:---|:---|:---|
| 后端测试+覆盖率 | `pytest --cov=. --cov-fail-under=80 -q`（.venv / Py 3.13.13 / Django 6.0.8） | **2011 passed，整体 cov 88.91%**，exit 0 |
| 后端类型 | `mypy . --strict` | Success，227 files，0 errors |
| 后端风格 | `ruff check` / `ruff format --check` | 通过 / 401 files 一致 |
| 迁移安全 | `makemigrations --dry-run` | No changes detected（CT-6 ①✓） |
| Service 覆盖率（T6） | 从 `.coverage` 复算 | assetmanagement 98% / usermanagement 98% / authusermanagement 100% / unregisteredasset 96%（均 ≥90 ✓）；**notification/services 65%**（不在 T6 强制清单，记观察项 O-1） |
| 四护栏 | `check_file_length_guard --print` / `check_function_length_guard` / `check_duplicate_invariants` / `check_frontend_invariants` | 全 PASS（最大文件 asset_view.py 483 行 <500） |
| 前端三项 | `npm run type-check` / `lint` / `format:check` | 全部 exit 0 |
| 前端测试 | `npm run test:coverage` | **169 files / 2196 tests passed**，exit 0（阈值块强制通过） |
| 依赖漏洞 | `npm audit --omit=dev` | **0 vulnerabilities** |
| 依赖漏洞 | `pip-audit`（venv 实装） | 1 条：twisted 26.4.0 CVE-2026-106454（CI `--ignore-vuln` 已豁免留痕） |
| OpenAPI 基线 | `spectacular --format openapi-json --validate` 后与 `api-schema-baseline.json` 比对 | **字节级一致**（SHA256 `8dc2c574…`，191 paths，无增删），exit 0；25 Warnings / 23 Errors 均为存量（随基线入库，`--validate` 判定通过） |

### 1.3 专项维度核验

| 维度 | 结论 |
|:---|:---|
| CT-3 状态机全路径 | `state_machine/transitions.py` 全表 22 边与 `backend-business-rules.md` §三逐条吻合；生产代码直写 `asset_current_status` 仅 9 处、全在 `state_machine/` 域内（core.py:85 FSM 入口 + 8 处已声明特殊回退）；**FSM 域外直写旁路 0 处**；15 个 FSM 方法均有直调测试（含 `test_reject_to_broken/lost`、`test_state_enum_equivalence`:384） |
| 跨端契约 4 项 | ① 信封 `success_response` 174 callers / `error_response` 100 callers 收口 ✓ ② 前后端 8 态枚举一致 ✓ ③ 前端请求参数全用 `page_size`（`pageSize` 仅本地 UI 态）✓ ④ 日期 ISO 8601（10-18 AUD-18 判不采纳，未重开）✓ |
| SC 安全分流 | SC-1 密钥零硬编码 ✓；SC-3 仅 `clear_database.py` f-string 表名但受 `ALLOWED_TABLES` 白名单 + `_validate_table_name` 约束（AUD-20 已闭合）、`"SELECT 1"` 为字面量 ✓；SC-8 见 §1.2 依赖行 ✓；OC-6 `/health/` `/ready/` 存在（config/urls.py:54/:98）✓ |
| 部署面 | production.py 强制 SECRET_KEY 环境变量 + 弱键拦截 + DEBUG=False + ALLOWED_HOSTS ✓；docker-compose.yml 与 .env.example 齐备 ✓；CI 共 **16 jobs**（backend-lint/type-check/complexity/permission-check/api-schema-check/api-doc-guard/api-doc-generate/backend-test/backend-mutation/frontend-lint/type-check/complexity/test/mutation/ci-summary）+ security-scan / ci-cd / duplicate-guard / migration-check |

### 1.4 AUD-01~20 回归复核（10-18 基线闭合确认）

| ID | 复核结论 |
|:---|:---|
| AUD-01/02/04 | `_ensure_repairing` 前置断言 ✓；approve_and_handle 捕 InvalidTransitionError ✓；BF-107 创建期状态单闸 contract_service.py:168-170 ✓ |
| AUD-03/06/07/08/11 | admin readonly 含 asset_current_status/contract_status ✓；`AssetOperationLog.objects.create` 生产仅 operation_log_service.py:77 ✓；get_operations_by_type / reject_to_* 5 方法 / state_machine_adapter+querysets+create_waste_asset 均已删除 ✓（outasset_selector.py 保留=10-18 拍板②） |
| AUD-09/10/17/19/20 | remark 硬编码 0 命中；STATUS_COLORS 改 STATUS_COLOR_MAP（dashboardStatusGroups.ts:15-26，状态键仍字面量、有测试锚定 → 观察项 O-2）✓；SERVE_PERMISSIONS=IsAuthenticated ✓；test_state_enum_equivalence（test_state_machine.py:384）✓；tokenObfuscator.ts ✓；clear_database 白名单 ✓ |
| AUD-16 | 实现已修（`"msg"` 键 0 命中）；**docstring 残留** employee_view.py:66-70 → 本次登记 AUD-43 |
| AUD-18/20 | 不采纳结论维持，未重开 |

---

## §二 问题台账

字段：`ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令`，P0/P1 附影响面/优先级理由/建议验证方式。状态列：已确认=证据齐备待修；观察项不入台账编号。

### 2.0 总览

| 级别 | 数量 | ID |
|:---|:---|:---|
| P0 | 0 | — |
| P1 | 3 | AUD-21、AUD-22、AUD-23 |
| P2 | 13 | AUD-24~AUD-36 |
| P3 | 8 | AUD-37~AUD-44 |

### 2.1 P1（3 条）

**AUD-21 | P1 | 鉴权/授权 | `asset_management_backend/core/department_scope.py:52-53` + `apps/authusermanagement/views.py:175-230` | `resolve_department_codes_for_user` / `RegisterAPIView`**
- 描述：行级隔离契约规定「无 Employee 绑定的用户返回 None（数据范围不限制）」，依赖 View 层权限兜底；而注册端点 `RegisterAPIView` 为 `AllowAny`（认证类置空、限流 5/min）且代码内无生产开关。自注册账号天然无 Employee 绑定 → 对仅 `IsAuthenticated` + DepartmentScopeMixin 行级隔离的读接口获得**无部门过滤的全量可见性**。
- 影响面：`resolve_department_codes_for_user` 的全部消费方（dept_manager 数据范围链路 `department_scope.py:69` → `get_all_descendants`）；`RegisterAPIView` 经 `authusermanagement/urls.py` 常开挂载，3 跳内无测试锚定。
- 优先级理由：授权可见性缺口，但可利用性取决于生产是否暴露注册入口（网络层/网关），故标 P1 而非 P0。
- 建议验证方式：生产网关探测 `POST /api/v1/auth/register` 可达性；或代码层加 Employee 绑定强制。
- 修复建议：① 生产关闭/白名单化注册端点（配置开关）；② 或 `resolve_department_codes_for_user` 对 None 语义反转为「拒绝」而非「不限制」。**[待确认] 生产注册入口暴露情况——本仓无部署配置可证。**
- 回查命令：`rg -n "if not employee|return None" core/department_scope.py; rg -n "AllowAny" apps/authusermanagement/views.py`
- 状态：已确认

**AUD-22 | P1 | 筛选/UI 状态脱节 | `vue-assetmanagement/src/components/GroupedAssetTable.vue:340-342` + `src/composables/useGroupedAssetList.ts:119-124` | `defineExpose({refresh})` / `search()`**
- 描述：分组模式对外暴露的 `refresh: () => search()` 复用带重置语义的 `search()`——其首行 `lastFilters = filters ?? {}` 清空当前生效筛选并把页码压回 1。删除成功/refreshFlag 等刷新路径（AssetContentDetails.vue:407/500）触发后数据回到「全量第 1 页」，而 SearchBar 表单是组件内部状态、不会被通知，界面仍显示已填筛选值。
- 影响面：GroupedAssetTable 仅被 AssetContentDetails 渲染（2 处），但 refresh 是该组件主刷新入口；触发即必然（删除成功后必然走 refresh）。
- 优先级理由：用户可感知的数据错误展示（以为筛选仍生效），分组模式主路径。
- 建议验证方式：组件测试——search({status:'in_use'}) 后调 refresh()，断言请求参数仍含 status。
- 修复建议：`refresh` 改为 `search(lastFilters)` 透传保留；或新增不重置语义的 `reload()`。
- 回查命令：`rg -n "refresh: \(\) => search\(\)|lastFilters = filters \?\? \{\}" vue-assetmanagement/src/components/GroupedAssetTable.vue vue-assetmanagement/src/composables/useGroupedAssetList.ts`
- 状态：已确认

**AUD-23 | P1 | 共享 Store 状态污染 | `vue-assetmanagement/src/stores/createEntityStore.ts:229-238` | `getList`（autoSync）**
- 描述：`getList` 默认把整段 list 与 pagination 回写共享实体 store。多处非列表场景借此拉数据：`useAssetFormHelpers.ts:61-63`（assetType/contract/storage，`page_size:100`）、`useUnregisteredFormLinkage.ts:48/108`、`useRecycleFormAssociations.ts:57/96`、DamagedAssetForm/UserForm 的 autocomplete 搜索。表单销毁后 store 的 list/pagination 停留污染值；而受害列表页是 keep-alive 路由（contract/storage/userdetails），唯一取数入口是 `SmartListContainer.vue` `onMounted`，全项目 `onActivated` **零命中**（实测 rg=0），返回缓存页不重取 → 列表直接显示污染数据。
- 影响面：assetTypeStore / contractStore / storageStore / userStore 等被表单二次查询命中的全部实体 store；keep-alive 列表页全部中招路径。
- 优先级理由：跨页面数据错误展示，触发路径日常（表单-列表往返）。
- 建议验证方式：keep-alive 集成测试——先开资产表单（触发 storageStore.getList page_size:100），返回仓储列表页，断言表格行数 == pagination.total 且 ≤ page_size。
- 修复建议：① 表单侧改调不带 autoSync 的取数 API（或 `getList` 增加 `{silent:true}` 旁路）；② keep-alive 列表页补 `onActivated` 重取；两者取其一即可根治，建议 ① 为最小修。
- 回查命令：`rg -n "page_size: 100" vue-assetmanagement/src/composables/useAssetFormHelpers.ts; rg -n "onActivated" vue-assetmanagement/src --glob "*.vue"`（后者应 0 命中）
- 状态：已确认

### 2.2 P2（13 条）

**AUD-24 | P2 | 查询/性能 | `asset_management_backend/apps/assetmanagement/views/operation_log_views.py:128-134` + `services/operation_log_service.py:488` | `list()` 先物化再分页**
- 描述：视图先 `list()` 物化全量再 `paginate_queryset`，service 层 `list()` 同样物化；操作日志量随时间单调增长，列表接口内存与延迟随数据量线性劣化。
- 修复建议：service 改返回 queryset（惰性）交视图分页；保留内存后处理需显式上限。
- 回查命令：`rg -n "paginate_queryset|list\(\)" apps/assetmanagement/views/operation_log_views.py`
- 状态：已确认

**AUD-25 | P2 | 并发/限流 | `asset_management_backend/core/throttles.py:92-99` | `LoginFailCountThrottle`**
- 描述：`login_fail_{username}` 计数为非原子 `cache.get`+`cache.set`（竞态下少计）；且 key 仅按用户名维度，同用户名多源并发可绕过失败次数阈值语义。
- 修复建议：改 `incr` 原子操作；key 叠加 IP 维度（username+ip 复合）。
- 回查命令：`rg -n "login_fail_" core/throttles.py`
- 状态：已确认

**AUD-26 | P2 | 缓存一致性 | `apps/usermanagement/models.py:91-107` + `services/department_service.py:147,198,226-230` | `Department.save` / `move_department`**
- 描述：部门移动时 `save(update_fields=["parent","level","path"])` 中 path 已是新值，`save()` 只清自身与新路径祖先的 `dept:{code}:descendants` 缓存；旧祖先链缓存不失效。子孙更新走 `QuerySet.update()` 绕过 save()。旧祖先（含 `_move_to_root` 整条旧链）后代缓存最长 5 分钟陈旧，dept_manager RBAC 数据范围可短暂包含已移出子树。
- 修复建议：移动前对旧祖先链逐一失效 descendants 缓存；子批量更新循环内复用同一失效集。
- 回查命令：`rg -n "update\(path=new_child_path" apps/usermanagement/services/department_service.py; rg -n "dept:.*:descendants" apps/usermanagement/models.py`
- 状态：已确认

**AUD-27 | P2 | 事务 | `core/audit_service.py:39-54` + `apps/assetmanagement/audit.py:92-104` + `apps/unregisteredasset/services.py:89-97` | 宽泛 Exception 捕获**
- 描述：审计容错在主业务 `transaction.atomic` 块内捕获宽泛 `Exception`（含 DatabaseError）。PG 下事务内 DB 错误即标记 aborted，捕获后继续 SQL 抛 `TransactionManagementError` → 容错设计反向放大为 500。且两套审计服务行为不一致：OperationLogService 失败 re-raise、GenericAuditService 吞掉。
- 修复建议：审计写入降级为 `transaction.on_commit` 异步或独立连接；统一两套审计失败语义。
- 回查命令：`rg -n "except Exception" core/audit_service.py apps/assetmanagement/audit.py`
- 状态：已确认

**AUD-28 | P2 | 请求竞态 | `vue-assetmanagement/src/composables/usePagedList.ts:69-83` | `fetchList`**
- 描述：无序号守卫（seq），快速翻页/搜索时慢响应后到覆盖新数据（同类点 createEntityStore:209-213 已加守卫，本 composable 遗漏）。
- 修复建议：对齐 createEntityStore 范式加 `listRequestSeq` 守卫。
- 回查命令：`rg -n "listRequestSeq|fetchList" vue-assetmanagement/src/composables/usePagedList.ts`
- 状态：已确认

**AUD-29 | P2 | 分页一致性 | `vue-assetmanagement/src/stores/createEntityStore.ts:389-402` | `remove`**
- 描述：删除实体后 ids/entities 移除但 `pagination.total` 不减，分页器总数与实际不符（与 AUD-35 create 分支对称）。
- 修复建议：remove 成功后 `pagination.total -= 实际删除数`（下限 0），并触发页码有效性校验。
- 回查命令：`rg -n "const remove|pagination.value.total" vue-assetmanagement/src/stores/createEntityStore.ts`
- 状态：已确认

**AUD-30 | P2 | 竞态/UI | `createEntityStore.ts:213` + `views/system/RoleManage.vue:162` 等 | seq 过期响应返回 `[]`**
- 描述：seq 守卫对过期响应返回空数组，但 RoleManage.vue:162 `roles.value = res`、AuthUserManage.vue:197、ContactsView.vue:179 等把返回值当权威数据本地镜像——快速连点时慢响应后到，视图拿到 `[]` 把表格抹成空白，而 total 取自 store（已由快响应更新），分页器正常、表体为空。
- 修复建议：过期响应改返回 `undefined` 并让视图 `if (res) roles.value = res`；或守卫处直接 throw 取消语义。
- 回查命令：`rg -n "return \[\]" vue-assetmanagement/src/stores/createEntityStore.ts; rg -n "= res$" vue-assetmanagement/src/views/system/RoleManage.vue`
- 状态：已确认

**AUD-31 | P2 | 请求竞态 | `vue-assetmanagement/src/stores/auditLogStore.ts:37-61` | `loadData`**
- 描述：项目内唯一仍直连 API 的列表 store（其余已下沉 createEntityStore），无 seq 守卫；筛选/页码/页容量变更触发，慢响应后到用旧结果覆盖 tableData/total。
- 修复建议：迁移至 createEntityStore 范式或内联 seq 守卫。
- 回查命令：`rg -n "listRequestSeq|tableData.value = response" vue-assetmanagement/src/stores/auditLogStore.ts`
- 状态：已确认

**AUD-32 | P2 | 分页自愈 | `createEntityStore.ts:172-178,225` | `handleInvalidPage`**
- 描述：删某页最后一行后 refresh 请求旧页码，后端返回空+新总数，`handleInvalidPage` 只改页码、清 entities、`return []` 不补发请求；且 store 在同一批次内把页码写成有效值，掐断 EP pagination 原生钳制自愈（EP 本会改写页码并重发 current-change）→ 表格空白直到用户手动点击。
- 修复建议：handleInvalidPage 后以修正页码重发一次 `getList({page: totalPages})`。
- 回查命令：`rg -n "handleInvalidPage" vue-assetmanagement/src/stores/createEntityStore.ts`
- 状态：已确认

**AUD-33 | P2 | 缓存失效 | `vue-assetmanagement/src/api/request.ts:339` + `api/asset.ts:126-143,279,350` | `clearByPattern`**
- 描述：写操作失效范围只覆盖同名 URL 子串，action 端点不在其中：`getAssetByCode(code, useCache, 300000)` 缓存 5 分钟，而 `markAssetAsBroken`/`batchDeleteAssets` 走 `/mark-broken/`、`/batch-delete/` 路径——报废或批量删除后打开详情页，最长 5 分钟读到变更前状态或已删除实体。实体层 store 全部 `enableCache:false` 不受影响，缺口仅在 API 级 MemoryCache。
- 修复建议：写操作成功后按实体 code 前缀（如 `/assets/assets/{code}`）失效，或 action 类端点统一禁用读缓存。
- 回查命令：`rg -n "clearByPattern|使用缓存" vue-assetmanagement/src/api/request.ts vue-assetmanagement/src/api/asset.ts`
- 状态：已确认

**AUD-34 | P2(中) | 状态一致性 | `createEntityStore.ts:278-284` | `getById`**
- 描述：getById 把取回实体 `ids.push` 追加，而 list 由 ids 派生；调用点含非当前页实体（AssetForm.vue:262、AssetLogsView.vue:89、useOutAssetAssetSelection.ts:61 等）。配合 keep-alive 列表不重取（AUD-23），详情/表单查过非当前页实体后返回列表会多出行，与 total/page_size 对不上。触发需特定导航路径，置信度中。
- 修复建议：getById 不写 ids（仅缓存 entities），或仅当 id 已在当前页集合内才保留。
- 回查命令：`rg -n "entityState.value.ids.push" vue-assetmanagement/src/stores/createEntityStore.ts`
- 状态：已确认（置信度中）

**AUD-35 | P2(中) | 状态一致性 | `createEntityStore.ts:355-362` | `create`**
- 描述：新建成功后 `ids.unshift` 插头部但 `pagination.total` 不加 1——AUD-29 的对称分支；重取完成前可见 page_size+1 行、分页器总数少 1。
- 修复建议：create 成功后 total += 1（与 remove 对称处理）。
- 回查命令：`rg -n "ids.unshift" vue-assetmanagement/src/stores/createEntityStore.ts`
- 状态：已确认（置信度中）

**AUD-36 | P2(中) | 请求竞态 | `useGroupedAssetList.ts:98-124` | `fetchSummaries`**
- 描述：分组汇总走独立加载函数，无 seq 守卫；快速翻页慢响应覆盖 summarize/totalCount，summaryLoading 由先结束请求提前置 false，出现汇总与页码不匹配中间态。同类列表加载点均已加守卫，唯此处遗漏。
- 修复建议：加 listRequestSeq 守卫（范式同 createEntityStore:209-213）。
- 回查命令：`rg -n "fetchSummaries|listRequestSeq" vue-assetmanagement/src/composables/useGroupedAssetList.ts`
- 状态：已确认（置信度中）

### 2.3 P3（8 条）

**AUD-37 | P3 | 限流口径 | `core/throttles.py:55-59,72-81` | `LoginRateThrottle` / `LoginLockoutThrottle`**
- 描述：两节流实例对同一登录视图同时生效且 cache key 同为 `throttle_login_{username}`——每次请求双计数，实际有效限速约 2.5 次/分，与 H-4 文档口径（5 次/分）不符。方向是收紧（合法用户被提前限流），属可用性缺陷。
- 修复建议：两实例 key 加类名前缀区分，或合并为单一节流。
- 回查命令：`rg -n "throttle_login_" core/throttles.py`

**AUD-38 | P3 | 查询 | `apps/assetmanagement/views/asset_view.py:184-190` | `get_asset_by_name`**
- 描述：`AssetDetailSerializer(assets, many=True)` 直接全量序列化未走 `paginate_queryset`——全库唯一漏分页的资产查询入口；同文件其余查询（combine_search/search/list）均分页。
- 修复建议：对齐同文件范式接 paginate_queryset。
- 回查命令：`rg -n "def get_asset_by_name" -A 7 apps/assetmanagement/views/asset_view.py`

**AUD-39 | P3 | 安全披露 | `apps/authusermanagement/services.py:285-316` + `apps/usermanagement/models.py:283-290` | `invalidate_user_refresh_tokens` / `_blacklist_user_tokens`**
- 描述：改密/改角色后逐 token `get_or_create` N+1 + 吞异常——黑名单写失败仅日志，旧 refresh token 可续期至自然过期（最长 7 天）；已签发 access token 的 RBAC claims 陈旧有「刷新重注入」缓解。属有意取舍的风险披露（注释自证），非缺陷定性。
- 修复建议：批量 upsert 替代逐条；黑名单失败升 error 级告警。
- 回查命令：`rg -n "def invalidate_user_refresh_tokens" -A 8 apps/authusermanagement/services.py`

**AUD-40 | P3 | 架构 | `apps/usermanagement/selectors.py:265-302` | `batch_update_sort`**
- 描述：Selector 层内含 `transaction.atomic` 与 `bulk_update` 写操作（且 employees 在 atomic 外取、bulk_update 在 atomic 内），违反后端 AGENTS §1.2 五层架构铁律（Selector 仅查询）。非运行时 bug。
- 修复建议：写路径下沉 Service 层。
- 回查命令：`rg -n "def batch_update_sort" -A 6 apps/usermanagement/selectors.py`

**AUD-41 | P3 | 死代码路径 | `vue-assetmanagement/src/stores/createEntityStore.ts:257-268` | `navigateToValidPage`**
- 描述：导出 API `navigateToValidPage(page)` 先设 `pagination.page = page` 再调 `getList()` 无参——而 `getList` 只读入参（`normalizePaginationParams({})` 默认 page=1），意图页码被忽略；随后 step-4 又用响应覆盖 pagination.page。实测生产代码**零调用方**（仅 5 处测试引用），属带缺陷的潜在 API。已降级 P3。
- 修复建议：`getList()` 改传 `{ page, page_size }` 透传；或删除该 API 与测试（若确无规划用途）。
- 回查命令：`rg -n "navigateToValidPage\(" vue-assetmanagement/src --glob "!**/__tests__/**"`

**AUD-42 | P3 | 错误处理 | `vue-assetmanagement/src/composables/usePaginationSearch.ts:97-100,157-171` | `loadList` / `handleCurrentChange`**
- 描述：`loadList` 在 ElMessage.error 后继续 `throw`，而 handleCurrentChange 是 EP 分页器事件入口（EP 不消费返回 Promise）→ 网络异常时控制台必有 unhandled rejection。
- 修复建议：事件入口吞错（仅依赖 onError 回调），或 catch 后不 rethrow。
- 回查命令：`rg -n "throw err" vue-assetmanagement/src/composables/usePaginationSearch.ts`

**AUD-43 | P3 | 文档漂移 | `apps/authusermanagement/views.py:66-70` | docstring**
- 描述：10-18 AUD-16 修复后实现已无 `"msg"` 键（0 命中），但该处 docstring 仍描述旧 `msg` 字段——文档与实现漂移。
- 修复建议：docstring 同步为 `message`。
- 回查命令：`rg -n '"msg"' apps/authusermanagement/views.py`（实现应 0 命中）；`sed -n '60,75p' apps/authusermanagement/views.py`

**AUD-44 | P3 | 竞态 | `useExportableAssets.ts:27-43` | `fetchList`**
- 描述：无 seq 守卫且 `currentPage` 在响应成功后才写（`currentPage.value = page` 于 try 尾部）——请求在途时 pager 停留旧页、重复点击同页会双发请求；慢响应乱序完成时 list/currentPage 由最后完成者决定。触发窗口窄（本地弹窗搜索列表），影响轻。
- 修复建议：请求发起前写 currentPage + 加 seq 守卫（对齐 createEntityStore 范式）。
- 回查命令：`rg -n "currentPage.value = page" vue-assetmanagement/src/composables/useExportableAssets.ts`

### 2.4 观察项（不入台账）

| 编号 | 内容 |
|:---|:---|
| O-1 | `notification/services.py` 测试覆盖率 65%——低于核心模块 90% 指引，但不在 T6 强制清单（仅 asset/user/auth/unregistered 四域）。建议下轮纳入 T6 或补测。 |
| O-2 | `dashboardStatusGroups.ts:15-26` 状态键仍为 8 个字面量（颜色映射已收敛 STATUS_COLOR_MAP）；有测试锚定键集合，漂移会被测试拦截。维持 10-18 AUD-09 不采纳结论。 |
| O-3 | OpenAPI spectacular 输出 25 Warnings / 23 Errors（均为 APIView 无法猜测 serializer 的存量项，随基线入库，`--validate` exit 0、schema 字节一致）。非门禁失败，属 schema 质量注记。 |
| O-4 | 依赖漏洞终态：pip-audit 1 条 twisted CVE-2026-106454（CI `--ignore-vuln` 豁免留痕）；`npm audit`（含 dev）4 条 high 全在 dev 工具链（braces/fast-glob，BF-100 已定性），生产依赖 `--omit=dev` 为 0。 |

---

## §三 分域结论与修复建议

### 3.1 后端

- **状态机域健康**：22 边与规范逐条吻合、FSM 域外直写 0 处、全方法有直调测试——CT-3 实质满足，本域 0 新发现。
- **授权链路是唯一 P1**（AUD-21）：行级隔离的 None 语义与常开注册端点组合形成可见性缺口，上线前必须处置或书面确认生产隔离。
- **性能类集中在操作日志**（AUD-24 物化分页）与**缓存一致性**（AUD-26 部门移动旧链、AUD-27 事务内审计容错）——均为长尾劣化，不阻塞上线但应进首个迭代。
- 限流双计数（AUD-37）方向是收紧，优先级让位于正确性类问题。

### 3.2 前端

- **根因模式高度集中**：`createEntityStore` 的 autoSync/seq/total 三件套被多个消费方绕过或未对齐——AUD-23（表单污染共享 store）、AUD-30（`[]` 镜像）、AUD-32（自愈掐断）、AUD-34/35（getById/create 的 total 失配）同源。**建议一次性专项**：为 createEntityStore 补「非污染取数模式 + 过期响应语义 + total 双向同步」三条契约并全消费方对齐，可一次消解 6 条 P2。
- 分组模式两条独立问题（AUD-22 refresh 重置筛选、AUD-36 汇总无守卫）影响主路径体验。
- keep-alive 列表页 `onActivated` 全局缺失是 AUD-23/34 的放大器，可作为契约修复的配套项。

### 3.3 契约与安全

- 跨端契约 4 项实测无破坏；OpenAPI 基线字节一致——M-3 配套完好。
- SC-1/SC-3/SC-4/SC-8/OC-6 全部通过；唯一授权类风险即 AUD-21，无注入/密钥/上传类问题。
- 审计票口径：CT-1[√]（核心路径测试齐）CT-2[√]（88.91%/98%+）CT-3[√] CT-5[√]（本会话无失败测试）CT-7[√]（全部结论取自 dev.txt 声明工具链）。

### 3.4 修复排期建议

| 批次 | 内容 | 预估性质 |
|:---|:---|:---|
| 上线前 | AUD-21 处置（配置开关或语义反转）+ 负责人确认注册暴露面 | 决策+小改 |
| 迭代 1-A | createEntityStore 契约专项：AUD-23/29/30/32/34/35（+配套 onActivated 或 silent 模式） | 前端集中重构 |
| 迭代 1-B | AUD-22/36/28/31/33/44（分组 refresh、各 composable seq 守卫对齐、action 端点缓存失效） | 前端补丁集 |
| 迭代 1-C | AUD-24/26/27（物化分页、部门缓存失效、审计事务语义） | 后端补丁集 |
| 迭代 2 | AUD-25/37/38/39/40/41/42/43（限流、漏分页、架构、死代码、文档） | 清尾 |

---

## §四 部署上线评估

### 4.1 结论

**可上线（有条件）**。无 P0；3 条 P1 中 1 条（AUD-21）为**上线前必须处置项**（决策或代码二选一），其余 2 条为前端数据展示一致性问题（无数据丢失/损坏/崩溃风险），可带条件上线并在首个迭代修复。

### 4.2 依据矩阵

| 维度 | 状态 | 证据 |
|:---|:---|:---|
| 功能测试 | ✅ 全绿 | 后端 2011 passed / 前端 2196 passed（2026-10-20 实测） |
| 类型/静态 | ✅ 全绿 | mypy --strict 0 errors（227 files）；前端 type-check/lint/format exit 0 |
| 覆盖率门槛 | ✅ 达标 | 整体 88.91%（≥80）；四核心 Service 域 96~100%（≥90）；Store 层阈值强制通过 |
| 变异测试 | ✅ 基线维持 | BF-124 批次 10-20 复核记录在案（本次未重跑全量，`[x] 未执行+原因：以最近基线记录为准`） |
| 数据库迁移 | ✅ 无待迁 | `makemigrations --dry-run` = No changes detected |
| API 契约 | ✅ 一致 | OpenAPI schema 与基线字节一致（SHA `8dc2c574…`，191 paths）；信封/枚举/分页/日期 4 项实测通过 |
| 安全 | ⚠️ 1 项待处置 | SC-1/3/4/6/8 通过；**AUD-21 注册暴露面需上线前决策**；twisted CVE 已 CI 豁免留痕 |
| CI 门禁 | ✅ 就绪 | 16 jobs + security-scan + duplicate-guard + migration-check + ci-cd 部署前置门禁 |
| 运行时基础设施 | ✅ 齐备 | `/health` `/ready` 端点存在；production.py 强制 SECRET_KEY 环境变量+弱键拦截+DEBUG=False；docker-compose + .env.example |
| 已知问题承载 | ⚠️ 带条件 | P1×2（AUD-22/23）+ P2×13 进入迭代 1；均不涉数据损坏 |

### 4.3 上线前必办（Gate）

1. **AUD-21 处置**：关闭/白名单化生产注册端点（推荐，改配置或网关），或修改 `resolve_department_codes_for_user` 对无 Employee 绑定返回拒绝语义；处置后在发布单留痕。
2. 确认生产环境 `SECRET_KEY`/`DB_PASSWORD` 经环境变量注入（代码已强制，需部署侧核对）。

### 4.4 上线后首个迭代承诺项

AUD-22、AUD-23（P1）+ §3.4 迭代 1-A/1-B/1-C 全部批次（P2×13）。P3 清尾进迭代 2。

---

*报告生成：2026-10-20 | 审计模式：纯只读 | 配套审计票见会话输出*
