# 全项目代码审查报告（逻辑漏洞与 Bug）

> 日期：2026-10-14（同日追加第二轮专项深审并入，见第六节）
> 审查方式：四路并行审查（后端 Service/Selector 层、后端 View/权限/序列化层、前端 Store/Composable/Router 层、前端 View/Component 层）+ 交叉验证，高危结论经 Read 逐行实测核实，已剔除验证不成立的候选项。
> 第二轮：资金链与通知热点专项深审（contract_service.py 付款/重算链——BF-053/054/055 落地区、notification/views.py），对照 dashboard_view.py / batch_mixins.py / asset_selector.py / FSM 交叉验证；4 项候选经逐行实证，3 项收录、1 项证伪（详见第六节）。
> 审查范围：后端 345 个 Python 文件；前端 481 个 ts/vue 文件。
> 审查基线：后端 `9fe6746`（heads/master），前端 `06653d6`（heads/master）。
> 只读审查，未修改任何代码。
> **更新（2026-10-14）**：P0 批次三项（C-4 / C-3 / I-3）已于审查同日修复并登记 BF-090，详见第七节。P1 批次两项（C-1 / C-2）已于审查同日修复并登记 BF-091，详见第八节。

---

## 一、总体结论

整体架构纪律扎实（FSM 收口、锁模式、401 刷新链、状态映射单点、API 响应契约、SC 安全红线均正确落地），但存在 **4 个确定性高危缺陷（已全部修复）**：

1. 后端生命周期记录**单条 create 绕过 service**（C-1）——状态机/审计/行隔离三重失效；（✅ 已修复）
2. 出库/回收/维修三个写入口**系统性漏掉 BEQ-02 行级隔离**（C-2）——跨部门越权写；（✅ 已修复）
3. 部门 `move` **未纳入管理权限白名单**（C-3）——任意登录用户可重组组织架构；（✅ 已修复）
4. 前端「确认找回」按钮**完全失效**（C-4）——功能瘫痪。（✅ 已修复）

中高危问题中反复出现同一模式：**「正确实现已存在于某处，复制粘贴扩散时遗漏」**（formRef 解构、fetchError 接入、limit 兜底、导出模式、size-change 回页）。修复时应按此模式全局排查同类点，并按 CT-4 补齐回归测试。

第二轮资金链/通知热点深审另收录 2 项 Important（I-10 结算流转不重算金额、I-11 payment_date 零校验），并证伪 1 项候选（create 并发竞态 500 论断——全局 IntegrityError handler 已兜底为 400），详见第五节。

---

## 二、修复优先级排序（推荐执行顺序）

> 排序原则：① 一行即修、立竿见影的越权/瘫痪缺陷最先；② 数据正确性次之；③ 涉及 service 签名变更的系统性收敛随后；④ 体验与健壮性问题最后批量处理。

| 优先级 | 编号 | 问题 | 预估改动量 | 风险等级 |
|:---:|:---:|:---|:---|:---:|
| P0 | C-4 | 「确认找回」按钮完全失效（前端解构漏一行）✅ 已修复 | 1 行 + 1 回归测试 | 🔴 Critical |
| P0 | C-3 | 部门 `move` 未纳入管理权限白名单 ✅ 已修复 | 1 行 + 1 权限测试 | 🔴 Critical |
| P0 | I-3 | 登录页用户名校验规则整体失效 ✅ 已修复 | 1 行 | 🟠 Important |
| P1 | C-2 | 出库/回收/维修创建路径缺失行级隔离 ✅ 已修复 | 3 service + 3 view + 序列化器 | 🔴 Critical |
| P1 | C-1 | BrokenAsset/LostAsset 单条 create 绕过状态机 ✅ 已修复 | 覆写 create 或移除端点 | 🔴 Critical |
| P2 | I-4 | 合同付款记录并发丢失更新 | selector 加锁 + 3 处 service | 🟠 Important |
| P2 | I-10 | 合同结算流转不重算 amount_unpaid，金额滞留旧口径 | 1 处 service + 1 回归断言 | 🟠 Important |
| P2 | I-5 | 出库审计日志 before 状态硬编码 | 1 处 | 🟠 Important |
| P2 | I-6 | 报废审批/拒绝/取消 FSM 异常未捕获 → 500 | 3 处 except | 🟠 Important |
| P2 | I-11 | payment_date 文档声明 DateField、运行时零校验 | 3 行内 | 🟠 Important |
| P2 | I-1 | 「导出全部」被分页上限 100 静默截断并污染列表 | 8+ 处迁移到服务端导出 | 🟠 Important |
| P3 | I-2 | 「重置」不重新拉数，表格与页码错位 | 1 处 composable | 🟠 Important |
| P3 | M-2 | 搜索沿用当前页码，命中不足一页显示空页 | 1 处 composable | 🟡 Medium |
| P3 | M-3 | 三处 el-pagination size-change 不回退页码 | 3 处组件 | 🟡 Medium |
| P3 | I-8 | store getList 无请求序号，慢响应覆盖新数据 | store 层通用加固 | 🟠 Important |
| P3 | I-7 | `/main/departmentmanagement` 无前端 RBAC 门槛 | 4 个路由 meta | 🟠 Important |
| P4 | M-1 | 通知 limit 参数无校验 → 500/负切片 | 1 处对齐先例 | ✅ 已修复（BF-095） |
| P4 | M-4 | 5 个操作视图未接 fetchError/retry | 5 处传参 | ✅ 已修复（BF-095） |
| P4 | M-5 | AssetForm 编辑缺 recordcode 仍导航返回 | 1 处 throw | ✅ 已修复（BF-095） |
| P4 | M-6 | physical_grade_after 无枚举校验 | 1 处 service 校验 | ✅ 已修复（BF-095） |
| P4 | M-7 | ContractPaymentRecord 表单字段丢弃 + 死代码 | 1 处组件 | ✅ 已修复（BF-095） |
| P4 | I-9 | WS 断线重连生命周期缺陷 | 1 处 composable | ✅ 已修复（BF-095） |
| P4 | M-8 | BindAuthUserDialog 选中后误显示「无匹配结果」 | 1 处 | ✅ 已修复（BF-095） |
| P4 | M-9 | autocomplete 建议无防抖/乱序保护 | 1 处 composable | ✅ 已修复（BF-095） |
| P4 | M-10 | 组内子表 loading 中翻页被静默丢弃 | 1 处 composable | ✅ 已修复（BF-095） |

**建议分批提交**：
- **批次 1（P0）**：C-4 + C-3 + I-3——三处各一行级修复 + 各补 1 条回归测试（CT-4）。✅ 已执行（BF-090）
- **批次 2（P1）**：C-2 + C-1——写路径收敛，统一「写路径必须委托 service + 锁内可见性校验」模式。✅ 已执行（BF-091）
- **批次 3（P2）**：I-4 + I-10（合同资金链加固：行锁 + 结算重算，同域一批）/ I-5 / I-6 / I-11 / I-1——并发与审计正确性 + 输入契约 + 导出链路改造。✅ 已执行（BF-092）
- **批次 4（P3-P4）**：交互健壮性批量修复，按复制粘贴同型点一次清干净。✅ P3 部分已执行（I-2/I-8/M-2/M-3/I-7，BF-093）；✅ P4 部分已执行（I-9/M-1/M-4/M-5/M-6/M-7/M-8/M-9/M-10，BF-095）。

---

## 三、问题清单（按严重度）

### 🔴 Critical

#### C-1. BrokenAsset/LostAsset 单条 create 绕过状态机、审计与行级隔离
- **置信度**：95
- **位置**：`asset_management_backend/apps/assetmanagement/views/_lifecycle_base.py:34-43`（无 create 覆写）；`core/mixins.py:123-137`（ResponseWrapperMixin.create 仅 `serializer.save()`）；`serializers/lifecycle_serializers.py:46-47,134-135`（SlugRelatedField 未按部门 scope）
- **问题**：`AssetLifecycleViewSetBase` 走 DRF 默认 create 直落库 BrokenAsset/LostAsset 记录，不调用 `AssetService.mark_asset_broken/lost`——资产 `asset_current_status` 不变、无 FSM 校验、无审计日志。测试 `test_lifecycle_view_api.py:42-55` 仅断言 201，未校验资产状态，佐证该缺口长期未被发现。
- **触发场景**：asset_admin 调 `POST /broken-assets/`，传任意部门资产 recordcode → 生成损坏记录但资产仍显示在库/在用；对照 batch_create 走 service 有完整 FSM+行隔离（`test_create_row_isolation.py:232-241`），两条路径语义分裂。
- **修复建议**：覆写 `create` 委托 `AssetLifecycleMixin` 对应 mark 方法（与 destroy/batch_delete 委托模式一致），或移除单条 create 端点强制走 batch。同步补 FSM 全路径集成测试（CT-3）。
- **修复状态**：✅ 已修复（2026-10-14，BF-091）。`_lifecycle_base.py` 新增 `create` 覆写 + `create_service_method`/`build_create_kwargs` 钩子；`asset_lifecycle_mixin.py` 加日期参数 + `find_and_return_asset` 返回 `FoundAsset` + 行级隔离；`asset_lifecycle_view.py` 三子类注入。回归测试 17 用例（跨部门 400 + 本部门 201 + FSM 流转 + 记录码错配 400）；门禁 pytest 1894 全绿、ruff / mypy 通过、Service 覆盖率 99%。

#### C-2. 出库/回收/维修创建路径缺失行级隔离（BEQ-02 违规）
- **置信度**：95
- **位置**：`services/out_asset_service.py:44-46`、`services/recycle_asset_service.py:41-42`、`services/repair_asset_service.py:113-120`（均无 `ensure_asset_visible`，无 user 参数）；对应 views `out_asset_view.py:237-248`、`recycle_asset_view.py:118-125`、`repair_asset_view.py:143-158` 不传 user；序列化器 SlugRelatedField 均为全局 queryset
- **问题**：damaged（`damaged_asset_service.py:46-47`）与 lifecycle mixin（`asset_lifecycle_mixin.py:46-48`）均有 BEQ-02 检查，这三个写路径漏掉了——系统性遗漏。
- **触发场景**：甲部门 asset_admin 知道乙部门资产 recordcode（或出库单 recordcode）→ 出库/回收/送修乙部门资产成功，资产主表被改写（status→in_use、storage 置 None 等）。
- **修复建议**：三处 service 签名增加 `user`，锁内调用 `AssetSelector.ensure_asset_visible(asset, user)`（与 damaged 同款），views 同步传入。补跨部门越权回归测试。
- **修复状态**：✅ 已修复（2026-10-14，BF-091）。三 service 加 `user` 参数 + `ensure_asset_visible`；回收校验前移至 `RecycleAsset.objects.create` 之前；6 处 view 传 `user=request.user`。回归测试 12 用例（跨部门 400 + 状态不变 + 本部门 201 + FSM 流转 + superuser 201）；门禁 pytest 1894 全绿、ruff / mypy 通过。

#### C-3. 部门 `move` 未纳入管理权限白名单，任意登录用户可重组部门树
- **置信度**：92（已实测确认）
- **位置**：`apps/usermanagement/views/department_view.py:59`（白名单）、`:274`（move action）、`services/department_service.py:117`（无二次校验）
- **问题**：管理动作白名单 `[create, update, partial_update, destroy, batch_create, batch_delete, sort]` 不含 `"move"` → 落入 else 分支仅 `IsAuthenticated`。`move` 会改写 `parent/level/path` 并级联更新全部子孙节点，属于组织结构变更。违反 `backend-business-rules.md:144`（部门管理仅 system_admin）、AGENTS B11。全仓无任何测试覆盖 move 权限。
- **触发场景**：任一 regular_user 登录后调 `PUT /api/v1/departments/{code}/move/`，body `{"target_parent_department_code": null}` 即可把部门提为根节点。
- **修复建议**：第 59 行白名单加 `"move"`；补权限回归测试（任意非 system_admin 角色调用应 403）。附带：`out_asset_view.py:68` 的 `"cancel_outasset"` 是死配置（真实 action 名为 `cancel`，自带 permission_classes 无漏洞），可顺手清理。
- **修复状态**：✅ 已修复（2026-10-14，BF-090）。白名单补 `"move"`；回归测试 `TestDepartmentMoveGate` 3 用例（dept_manager/regular_user → 403，system_admin → 200）；门禁 pytest 188 全绿、ruff / mypy 通过。

#### C-4. 「确认找回」按钮点击完全失效
- **置信度**：100（已实测确认）
- **位置**：`vue-assetmanagement/src/views/FoundAssetView.vue:20`（模板 `ref="formRef"`）vs `:54-59`（解构列表漏 `formRef`）；根因在 `composables/useAssetOperationForm.ts:107`（`if (!formRef.value) return`）
- **问题**：composable 内部的 `formRef` 未与模板绑定，永远 undefined → 点击「确认找回」静默无反应，无任何提示。8 个使用该 composable 的视图中唯一漏掉的（Scrap/Lost/Repair/MarkBroken/Recycle/RepairDone/RepairFailed 均已解构）。
- **修复建议**：解构列表加 `formRef,` 一行；补回归测试——点击提交后 `submitFn` 必须被调用（CT-4）。
- **修复状态**：✅ 已修复（2026-10-14，BF-090）。解构补 `formRef` + `void formRef` 注释（对齐 Scrap 先例）；回归测试 `FoundAssetView.spec.ts` 3 用例（点击→foundAsset 调用+router.back、表单数据传递、失败分支）；门禁 vitest 161 文件 / 2132 测试全绿。

---

### 🟠 Important

#### I-1. 「导出全部」被后端 MAX_PAGE_SIZE=100 静默截断并污染列表状态
- **置信度**：90
- **位置**：`src/composables/useAssetLifecycleActions.ts:129-134`；同型复制于 `AssetContentDetails.vue:435`、`OutAssetDetails.vue:362-365`、`ContractDetails.vue:394`、`DamagedAssetDetails.vue:421`、`WasteAssetDetails.vue:224`、`RecycleAssetDetails.vue:373`、`HardDiskSNDetails.vue:408`、`UnregisteredAssetDetails.vue:351`（8+ 处）
- **问题**：`store.getList({page:1, page_size: total})` 超过后端 `MAX_PAGE_SIZE=100`（`core/constants.py:12`）被静默钳位，实际只返回 100 条却提示「导出成功」；同时 `createEntityStore.ts:221-229` 的 autoSync 用返回值覆写 `list/pagination`，导出后表格与分页器被替换成导出快照。项目已有服务端导出方案（`useOperationLogExcelExport.ts:4-6` 注释明说此坑），但这 8 处未迁移——DR-1 违规的复制扩散。
- **触发场景**：任一列表页导出 → 选「导出全部」→ 总数 >100 时文件只含 100 条且提示成功；导出后页面表格状态被污染。
- **修复建议**：统一复用 `useServerExcelExport` 服务端导出，或按 100 条/批循环拉取；无论如何不得把全量拉取结果写回主列表 store。迁移时一次清完 8+ 处同型点。
- **修复状态**：✅ 已修复（2026-10-15，BF-092/I-1）。`useAssetLifecycleActions` 迁移至 `useServerExcelExport` 服务端导出；4 API（broken/lost/found/repair）加 `exportExcel`；4 store 加导出入口（经 store 层消费满足 `no-restricted-imports`）；4 视图改传 `fetchExport`。本批迁移 4 处（生命周期页面），其余 8 处同型点（AssetContentDetails/OutAssetDetails/ContractDetails 等）为独立批次待后续处理。

#### I-2. 「重置」按钮不重新拉数，表格显示旧页数据、页码错位
- **置信度**：85
- **位置**：`src/composables/usePaginationSearch.ts:177-180`（`resetToFirstPage` 只置 `page=1` + `clearSearch`，无 reload）；触发链 `AssetContentDetails.vue:327-334` → `SmartListContainer.vue:180`
- **触发场景**：用户停在第 3 页点「重置」→ 分页器显示第 1 页，表格却仍渲染第 3 页行；主列表页必现。
- **修复建议**：`resetToFirstPage` 改 async 并 `await loadList(1, pageSize.value)`。
- **修复状态**：✅ 已修复（2026-10-15，BF-093/I-2）。`resetToFirstPage` 改 async + `await loadList(1, pageSize.value)`；唯一消费点 `AssetContentDetails.vue:333` 补 `void`；spec 改写断言 loadList 调用。

#### I-3. 登录页用户名校验规则整体失效
- **置信度**：100（已实测确认）
- **位置**：`src/views/LogIn.vue:28` `prop="username"` vs `loginRules` 键 `auth_username`（`:198`）→ `validateUsername`（必填/3-20 位/字符集，`:148-162`）永不触发。密码字段正常。
- **修复建议**：`prop="username"` → `prop="auth_username"`；补一条「空用户名前端拦截不发请求」测试。
- **修复状态**：✅ 已修复（2026-10-14，BF-090）。`prop` 改 `auth_username`；回归测试 `LogIn.spec.ts` 10 用例（prop 对齐验证 + validateUsername 5 条规则 + validatePassword 2 条规则回归确认）。

#### I-4. 合同付款记录并发丢失更新
- **置信度**：90
- **位置**：`services/contract_service.py:214`（add）、`:439`（delete）、`:470`（approve）；`selectors/contract_selector.py:22`（无 select_for_update）
- **问题**：三处均对 `paid_record` JSON 做读-改-写且无行锁，并发下互相覆盖，丢失付款条目或 `amount_paid` 重算错误。资产侧已有 `lock_row_or_409` 模式可复用。
- **修复建议**：`get_contract_by_code` 增加锁版本（或 service 内 `select_for_update` 重取），超时映射 409。
- **修复状态**：✅ 已修复（2026-10-15，BF-092/I-4）。`contract_selector.py` 新增 `get_contract_for_update`（`lock_row_or_409` + `select_for_update` + `is_deleted=False`）；三 service 方法换锁；`add_payment_record` save 收敛为 `update_fields`（4 字段）；并发测试 `test_concurrent_add_payment_no_lost_update`（Postgres 守卫）验证金额累加不丢失。

#### I-5. 出库审计日志 before 状态硬编码
- **置信度**：95
- **位置**：`services/operation_log_service.py:249`（经 `audit.py:190-199` 委托，为线上生效路径）
- **问题**：`before_data` 恒为 `IN_STORE`，但出库源允许 `in_store`/`recycled_pending`（`out_asset_service.py:84`）。reissue（回收件再发放）审计记录 before_status 错误，违反 B7。
- **修复建议**：改传 `asset.asset_current_status` 快照（注意在 FSM 调用前捕获）。
- **修复状态**：✅ 已修复（2026-10-15，BF-092/I-5）。`log_asset_out` 加 `before_status` 参数（缺省回退 `IN_STORE`）；`AuditLogger.log_asset_out` 双层透传；`out_asset_service.py` 传 `outasset.outasset_previous_status`（在 `_apply_outasset_to_asset` 改写前已捕获）。

#### I-6. 报废审批/拒绝/取消的 FSM 异常未捕获 → 500
- **置信度**：90
- **位置**：`services/damaged_asset_service.py:175`（approve）、`:246`（reject）、`:311`（cancel）
- **问题**：`InvalidTransitionError` 是普通 Exception（`state_machine/constants.py:72`），全局 handler 不映射；create 路径有捕获（`:72-75`），审批三处遗漏。资产状态漂移后审批 → 用户收到 500 而非 400 业务错误。
- **修复建议**：三处补 `except InvalidTransitionError → AppValidationError`，与 create 路径同款。
- **修复状态**：✅ 已修复（2026-10-15，BF-092/I-6）。三处 FSM 调用包 try/except，`InvalidTransitionError` → `AppValidationError(INVALID_STATE_TRANSITION)`，与 `:72-75` 已有范式一致。

#### I-7. `/main/departmentmanagement` 无 RBAC 门槛（A-14 同型漏洞）
- **置信度**：85
- **位置**：`src/router/routes-main-system.ts:70-114`（主路由及 `userform`/`userbatchimport`/`departmentbatchimport` 三个子路由 meta 均无 `requiredMinRole`）；`guards.ts:30-46` roleWhitelist 无该前缀；`checkRoleAccess` 未命中时 `return true`（`guards.ts:77`）——对照 roledetails/authusermanage 已按 A-14 补 `requiredMinRole: 'system_admin'`（`routes-main-system.ts:158,170`）
- **触发场景**：任意已登录角色直接输入 `/main/departmentmanagement/userbatchimport` 即可进入通讯录/批量导入页面（后端 API 权限仍拦写操作，但页面与目录数据前端可见）。
- **修复建议**：主路由及三个子路由补 `requiredMinRole: 'system_admin'`；建议全局扫一遍 roleWhitelist 与 routes meta，确认无第三个 A-14 同型遗漏。
- **修复状态**：✅ 已修复（2026-10-15，BF-093/I-7）。父+3 子路由 meta 补 `requiredMinRole: 'system_admin'`（守卫只读 `to.meta`，子路由独立声明）；roleWhitelist 补前缀条目（双重保护）；guards.spec 双表增列 + deny dept_manager + meta 拦截用例。第 5 触点 AsideMenu 已有 `v-if="canManageSystem"` 无需改；后端读侧为有意设计（选项 A，`department_view.py:57`）。

#### I-8. `getList` 无请求序号，慢响应覆盖新数据（store 层通用竞态）
- **置信度**：80
- **位置**：`src/stores/createEntityStore.ts:192-235`（`withRequestControl` 只对相同参数去重，page1/page2 并发各自独立，后到者覆写 `entities/pagination`）；同族：`usePaginationSearch.ts:89-104`、`auditLogStore.ts:36-61`、`notificationStore.ts:40-56`
- **触发场景**：弱网下快速连点页码 1→2，第 1 页响应晚到 → 表格显示第 1 页数据而分页器停在第 2 页。
- **修复建议**：store 内维护单调递增请求序号，仅应用最新序号的响应。
- **修复状态**：✅ 已修复（2026-10-15，BF-093/I-8）。getList 加 `listRequestSeq` 守卫（范式复用 dashboard trendRequestId）；`usePaginationSearchState.ts` 两搜索函数加 `searchSeq` 三路守卫（成功/失败/finally）；竞态 spec 6 用例（慢响应丢弃、慢失败不清场、finally 不复位）。范围声明：本批覆盖 store getList + 搜索路径；`usePaginationSearch.ts` loadList 经 store.getList 调用已受守卫覆盖，`auditLogStore`/`notificationStore` 自有 fetch 为独立实现待后续。

#### I-9. WS 断线重连在 `disconnect()` 后仍复活；`manualReconnect` 不关旧连接
- **置信度**：85
- **位置**：`src/composables/useNotificationConnection.ts:165-176`（先清 timer 再 `ws.close()`，异步 `onclose` 对 code 1000 仍 `scheduleReconnect()`）；`manualReconnect:152-160` 直接 `connect()` 不关旧 socket；`startHeartbeat:119-125` 不清旧 timer
- **触发场景**：组件卸载/登出调用 `disconnect()` 后 3 秒连接悄悄复活；网络闪断期间点「重新连接」产生并行双连接与双心跳。
- **修复建议**：加 `intentionallyClosed` 标志位在 onclose 中拦截；`connect()` 入口先关旧连接；`startHeartbeat()` 先 `stopHeartbeat()`。

#### I-10. 合同进入结算阶段时 amount_unpaid 不重算，金额滞留旧口径【二轮深审新增】
- **置信度**：80（经二轮逐行实证）
- **位置**：`services/contract_service.py:89-95`（`_recalc_paid_amounts` 结算分支）vs `:310-315`（`update_settlement_status` 流转后仅 `contract.save()`，无重算调用）
- **问题**：`_recalc_paid_amounts` 明文实现「结算三态（settlement_done/final_check/project_finished）且已填 settlemented_price 时，未付 = 结算价 − 已付」——代码自证的业务意图。但该分支只在付款操作时执行；`update_settlement_status` 流转到结算态后不触发重算，`amount_unpaid` 停留在按 `contract_amount` 计算的旧值，直到下一次付款才被纠正。期间前端/报表展示的未付金额错误（结算价 < 合同价时高估欠款）。
- **触发场景**：合同已有多笔付款后，管理员将状态流转至 settlement_done 并已录入 settlemented_price → 合同详情/列表的 amount_unpaid 仍为旧口径。
- **修复建议**：`update_settlement_status` 在 `ContractFSM.transition(...)` 成功后、`contract.save()` 前调用 `_recalc_paid_amounts(contract)`（同一事务内，零新依赖，注意 save 带 `update_fields` 需含金额字段）；补一条「流转到 settlement_done 后 amount_unpaid 基于结算价」的回归断言（CT-4）。
- **修复状态**：✅ 已修复（2026-10-15，BF-092/I-10）。`update_settlement_status` FSM 成功后调 `_recalc_paid_amounts` + 定向 save；新增 `recalculate_amounts_for_update` 公共入口；`ContractViewSet.perform_update` 覆写——PATCH settlemented_price 触发重算；回归测试 5 用例覆盖结算重算 + perform_update。

#### I-11. payment_date schema 声明 DateField、运行时零校验——A-44 同族「声明超前于运行时」失真【二轮深审新增】
- **置信度**：82（经二轮逐行实证）
- **位置**：`views/contract_view.py:230`（inline_serializer 声明 DateField）vs `:256-263`（`payment_date = request.data.get(...)` 后仅 `str()` 直传）；下游 `services/contract_service.py:53`（`_build_payment_entry` 原样落 JSON，无格式验证）
- **问题**：API 文档承诺 YYYY-MM-DD 日期格式，运行时不解析、不验证，任意字符串（"2026-13-99"、"明天"）直接落入 `paid_record` JSON 的 `date` 字段。view 注释（:213-215）自认「此处只声明文档结构」，属有意简化，但 schema/运行时失真仍构成 A-44 同族问题（项目对该类失真有双向红线纪律）。
- **触发场景**：`POST /contracts/{code}/payment_record/` body 带 `"payment_date": "明天"` → 200 成功，明细表日期为非日期字符串，前端日期渲染/排序异常。
- **修复建议**：视图内对 payment_date 做 `datetime.strptime(s, "%Y-%m-%d")` 校验失败返回 400，或复用 schema 已声明的 DateField 走 `is_valid`；改动 3 行内。批量回填路径（`ContractBatchPaymentRecordSerializer`）已有 Serializer 校验，无需处理。
- **修复状态**：✅ 已修复（2026-10-15，BF-092/I-11）。`payment_record` 端点改用 `ContractBatchPaymentRecordItemSerializer`（`is_valid(raise_exception=True)`），消除与批量端点重复校验（DR-1）。行为变更声明：错误响应从手写 400 变为 DRF 统一 400 格式；`DecimalField` 精度要求恰好 2 位小数（与批量端点对齐，旧代码接受 "100.5"）。

---

### 🟡 Medium

| # | 位置 | 问题 | 置信度 | 修复建议 |
|---|------|------|:---:|:---|
| M-1 | `apps/notification/views.py:26` | `limit=int(...)` 无兜底：`?limit=abc` → ValueError → 500（应 400）；`?limit=-1` → 负切片触发 Django `AssertionError("Negative indexing is not allowed")` → 500；`?limit=100000000` → 无上限切片全表拉取（DoS 面）。`dashboard_view.py:53/66` 有同构参数的正确范式（try/except 回落 + `min(..., 100)`），DR-1 反例【二轮深审复核确认】 | 85 | 镜像 dashboard 范式：`try: limit = min(int(qp.get("limit") or 20), 100) except (ValueError, TypeError): limit = 20`，另补 `max(limit, 1)`；同文件三条视图一处修完 |
| M-2 | `usePaginationSearchState.ts:91,177` | `performSearch/performSearchWithParams` 沿用当前页码；在第 5 页搜索命中不足一页 → 请求 page=5 → 空表格 + 分页器「第 5/1 页」 | 85 | 搜索入口强制 `page=1`（或按 response.count 钳制后重查）。✅ 已修复（BF-093/M-2）：新增 `searchWithReset` 薄包装（置 1 + 委托），AssetContentDetails 消费点接线；原型不动（翻页契约保护） |
| M-3 | `ContactsView.vue:96`、`AuthUserManage.vue:94`、`RoleManage.vue:81` | `@size-change` 直接拉数不回退页码：第 3 页 20/页改 50/页，总页数 <3 时空列表（`usePaginationSearch.ts:149-156` 有正确实现） | 95 | size-change 时按 totalPages 夹紧 page 后再请求。✅ 已修复（BF-093/M-3）：口径订正为 5 处（composable 钳制改统一置 1 + 3 直连补 handler + NotificationList 已正确无需改） |
| M-4 | `AssetOperationLayout.vue:55-65` | 已支持 `fetchError`/`@retry` UI，但仅 3 个视图接入；Found/Lost/Recycle/Repair/MarkBroken 5 处未传 → 加载失败误导为「资产不存在」且无重试 | 95 | 5 处补传 `fetchError` + `@retry`（同型一次清完） |
| M-5 | `componentsdetails/detils/AssetForm.vue:368-373` | `submitUpdate` 缺 recordcode 仅 ElMessage.error 后 return（未 throw）→ `submitForm:355-356` 继续 `setRefreshFlag(true); router.go(-1)` | 95 | 改为 throw，阻断后续导航 |
| M-6 | `repair_asset_service.py:176-177` + `views/asset_view.py:486` | `physical_grade_after` 从 request.data 裸取，Django save() 不校验 choices，任意字符串写库，破坏前端状态映射 | 90 | service 内按 `Asset.PhysicalGrade.values` 校验，非法抛 AppValidationError |
| M-7 | `detils/ContractPaymentRecord.vue:275-278` | `addPaymentRecord` 只提交 amount/description，表单必填 `date` 与可选 `payment_method` 收集后丢弃；`payments` ref（:165）+ `loadPayments`（:240-255）为死代码，表格实际渲染 props | 95 | 提交带上 date/payment_method；删除死代码 |
| M-8 | `system/BindAuthUserDialog.vue:189-193` | `handleSelectEmployee` 把关键词设为「张三 (JOB001)」→ watch 再触发搜索 → 结果清空 → 模板 :66 显示「无匹配结果」与已选中状态矛盾 | 90 | 选中态挂标志位抑制搜索提示，或设置关键词时跳过 watch |
| M-9 | `useSuggestionFetcher.ts:41-68` | autocomplete 每键一请求，无防抖；慢响应以旧关键词结果覆盖新建议 | 80 | 200-300ms 防抖 + 请求 token 丢弃过期响应 |
| M-10 | `useGroupChildrenCache.ts:133` | loading 中翻页请求直接 return 且 Promise 正常 resolve，目标页未拉取、界面无反馈 | 80 | 记录「最新期望页」，当前请求完成后补跑；或 loading 期间禁用子表分页器 |

---

## 四、已核查排除（非问题，防误报留痕）

- `department_scope` 空部门列表 `__in=[]`：Django 中恒为空集，语义正确。
- `change_asset_status` 绕过 DamagedAsset 记录约束：system_admin 专属数据修复端点，有意为之。
- recycle create 先建记录后锁资产：整体 `@transaction.atomic` 覆盖，FSM 失败即回滚。
- `get_asset_detail_by_code` 缺 is_deleted 过滤：SoftDeleteManager 默认已过滤。
- 401 刷新重试链：`_retryCount` 有界（最多约 3 次后 logout），非死循环；tokenRefresh 单飞 + BroadcastChannel 正确。
- `ASSET_STATUS_MAP` 8 状态齐全且单点派生（`statusMapping.ts:31-43`、`Format.ts:198`），无双份映射。
- 响应契约 `utils/response_utils.py` 严格满足根级 §3；全仓 `.raw()`/`.extra()`、用户输入驱动 `order_by`、硬编码密钥、文件上传面均为零命中。
- 批量删除权限：27 处 `BatchDeleteViewMixin` 逐一比对 admin_actions，写入动作全覆盖。
- 审计日志 5 个端点全部挂 `IsAuditorOrAdmin`；Cookie 通道 httponly + CSRF 强制。
- UnregisteredAssetBasicDetails 审批按钮无前端权限守卫：后端 AC-0 兜底 403，可接受的纵深防御缺口。
- **create_contract 并发重复码返回 500（二轮候选，已证伪）**：check-then-create 竞态窗口真实存在（`contract_service.py:157` exists → `:165` create 无锁），但 `core/exception_handler.py:96-99` 已全局捕获 IntegrityError 并映射为 400 + "数据已存在,请勿重复提交"（unique 关键字命中 `:21-26` 映射表），用户不会收到 500。「batch_mixins 有优雅处理而单条路径没有」亦不成立——两者共用同一全局 handler。剩余瑕疵仅为 error_code 未细化为 `DUPLICATE_CONTRACT_CODE`、消息不含合同编码，属低优先级打磨项，不列入问题清单；其附带的付款三操作缺 `select_for_update` 子论断已由 I-4 覆盖。

---

## 五、第二轮专项深审核查记录（资金链与通知热点）

> 深审范围：`contract_service.py` 付款/重算链（BF-053/054/055 落地区）、`notification/views.py`；对照 `dashboard_view.py`、`batch_mixins.py`、`asset_selector.py`、合同/资产 FSM 交叉验证。前端 BF-080~086 链路前序已多轮审查，本轮不重复。收录阈值 ≥80，全部经源码逐行实证。

| # | 候选发现 | 核查结论 | 处置 |
|---|---------|---------|:---:|
| 1 | notification_list limit 无异常防护/上限钳制（两个 500 路径 + 无界查询） | ✅ 成立——`views.py:26/33` 实证；dashboard 范式对照成立 | 并入 M-1（已按二轮结论更新描述与置信度） |
| 2 | create_contract check-then-create 竞态 → 500 | ❌ **证伪**——全局 IntegrityError handler（`exception_handler.py:96-99`）已转 400 + 用户可读消息；竞态窗口存在但后果非所述 | 移入第四节排除清单；select_for_update 子项由 I-4 覆盖 |
| 3 | payment_date 声明 DateField、运行时零校验（A-44 同族） | ✅ 成立——`contract_view.py:230` vs `:256-263`、`_build_payment_entry:53` 三点实证 | 新增 I-11 |
| 4 | 结算流转不重算 amount_unpaid，金额滞留旧口径 | ✅ 成立——`_recalc_paid_amounts:89-95` 结算分支 vs `update_settlement_status:310-315` 无调用实证 | 新增 I-10（本轮最有价值发现，语义级资金展示错误） |

**低于阈值留痕（不计问题）**：notification `is_read` 词表窄口径（D-7 已收口）；`_parse_paid_record` 非法 JSON 回落空列表致重算归零（BF-055 已规范化迁移，现网风险 ~50）；`mark_all_read` 用 `.update()` 跳过信号（模型无相关信号，无影响 ~30）；合同 FSM 常量、RBAC（通知按 recipient_jobcode 隔离、合同走 AdminWritePermissionMixin）未发现越权路径。

---

## 六、审计票

```
[审计票 - 必填项]
- 读取规范：已读 根/后端/前端 AGENTS & Rules（backend-business-rules、frontend-business-rules）
- CT-1[√] CT-3[√] CT-5[√] CT-7[√] — 审查任务 + P0/P1/P2/P3 批次修复，关键结论经 Read 逐行实测；CT-7 版本对齐已核验（mypy 2.1.0 / django-stubs 6.1.0 / djangorestframework-stubs 3.18.0 / types-channels 4.3.0.20260518）；P3 前端门禁（type-check/lint/format/vitest 2148/coverage 分层）EXIT=0
- DR-1[√] DR-5[√] — P1 批次将 BEQ-02 检查从 damaged/lifecycle 推广至 out/recycle/repair；P2 批次 I-11 消除 payment_record 重复校验（DR-1）；I-1 迁移至统一服务端导出方案（DR-1）；P3 批次 I-8 复用 dashboard seq 竞态范式（DR-1）
- SC-1[√] SC-3[√] — 全仓 .raw()/硬编码密钥零命中
- 跨端契约：未破坏（P0/P1/P2/P3 批次修复未动响应结构与枚举值；schema 基线仅 docstring 非破坏性更新；I-11 行为变更已声明）
- 红线触发：无（P0/P1/P2/P3 批次修复经门禁全绿）
- 建议提交：否（审查产出，修复需另行立项，按第二节批次执行；P0/P1/P2/P3 批次已执行完毕，见第七/八/九/十节）
[审计票 - 自检项]
- AI行为：Fact-1[√] — 所有结论均有 file:line 实测依据；二轮 4 项候选经逐行实证 3 收录 1 证伪（create 并发 500 论断被全局 handler 证伪，见第四节）
- 写作风格：Style-1~Style-3[√]
```

---

## 七、P0 批次修复记录（2026-10-14）

> 按第二节批次 1 执行，三项缺陷一并修复，登记 BF-090（`docs/BugFixed/Bug修复活账本.md`）。

| 缺陷 | 修复文件 | 核心改动 | 回归测试 | 门禁 |
|:-----|:---------|:---------|:---------|:-----|
| C-4 | `FoundAssetView.vue:59,76-78` | 解构补 `formRef` + `void formRef` 注释（对齐 Scrap 先例） | `FoundAssetView.spec.ts` 3 用例 | vitest 161 文件 / 2132 测试全绿 |
| C-3 | `department_view.py:59` | 白名单补 `"move"`（改为多行格式） | `TestDepartmentMoveGate` 3 用例 | pytest 188 全绿；ruff / mypy 通过 |
| I-3 | `LogIn.vue:28` | `prop="username"` → `prop="auth_username"` | `LogIn.spec.ts` 10 用例 | 同上 |

**同型排查**：grep 确认 8 个 `useAssetOperationForm` 调用方（Scrap/Repair/RepairDone/RepairFailed/Recycle/Lost/MarkBroken/Found）全部含 `formRef` 解构，无遗漏。

**测试策略说明（I-3）**：Element Plus async-validator 校验链在 JSDOM 环境下不可靠（provide/inject 与内部事件监听依赖真实 DOM 行为），故采用双层验证——① prop 绑定断言（el-form-item 的 prop 与 loginRules 键一致）；② 经 vm 取校验器函数独立调用。两层合起来证明 prop 对齐后 el-form 能按 prop 找到 rules 并执行校验器。

**前端门禁明细**：type-check（vue-tsc 0 error）/ lint（0 error）/ format:check（通过）/ 定向 vitest 13/13 / 全量 test:coverage 161 文件 2132 测试全绿，Store 层覆盖率 97.97%（≥90% 达标）。

**后端门禁明细**：pytest test_admin_permissions.py 11/11（含新增 3 个 move 门禁用例）/ pytest apps/usermanagement/ 188/188 / ruff 通过 / mypy --strict（department_view.py）零错误。test_admin_permissions.py 存量 25 条未类型化函数告警为原有，非本次引入。

---

## 八、P1 批次修复记录（2026-10-14）

> 按第二节批次 2 执行，两项缺陷一并修复，登记 BF-091（`docs/BugFixed/Bug修复活账本.md`）。

| 缺陷 | 修复文件 | 核心改动 | 回归测试 | 门禁 |
|:-----|:---------|:---------|:---------|:-----|
| C-1 | `_lifecycle_base.py` + `asset_lifecycle_mixin.py` + `asset_lifecycle_view.py` + `asset_view.py` | 新增 `create` 覆写 + `create_service_method`/`build_create_kwargs` 钩子；`find_and_return_asset` 返回 `FoundAsset` + 行级隔离；batch 透传日期 | `test_create_row_isolation.py` 17 用例 + `test_lifecycle_view_api.py` 补 3 断言 | pytest 1894 全绿；ruff / mypy 通过；Service 覆盖率 99% |
| C-2 | `out_asset_service.py` + `recycle_asset_service.py` + `repair_asset_service.py` + 4 个 view | 三 service 加 `user` + `ensure_asset_visible`；回收校验前移；6 处 view 传 `user` | `test_create_row_isolation.py` 12 用例 | 同上 |

**C-1 修复细节**：
- `_lifecycle_base.py`：新增 `create` 覆写（validate → `resolve_operator` → `getattr(AssetLifecycleMixin, self.create_service_method)(...)` → `success_response`）+ `create_service_method` 类属性 + `build_create_kwargs` 钩子。
- `asset_lifecycle_mixin.py`：`mark_asset_broken`/`mark_asset_lost` 加可选日期参数；`find_and_return_asset` 加 `user`/`found_date`、返回 `FoundAsset`（含 `refresh_from_db` 解决 DateField 序列化）、加 `ensure_asset_visible`；batch 透传 `broken_date`/`lost_date`。
- `asset_lifecycle_view.py`：Broken/Lost/Found 三子类注入 `create_service_method`/`build_create_kwargs`；Found 加 `lost_asset_recordcode` 一致性校验（`LOST_ASSET_MISMATCH`）。

**C-2 修复细节**：
- `out_asset_service.py`：`create_outasset`/`batch_create_outasset` 加 `user` + `ensure_asset_visible`。
- `recycle_asset_service.py`：`create_recycle_asset`/`batch_create_recycle_asset` 加 `user`；校验前移至 `RecycleAsset.objects.create` 之前。
- `repair_asset_service.py`：`_lock_asset_for_repair`/`create_repair_asset` 加 `user` + 锁后 `ensure_asset_visible`。
- 4 个 view 6 处传 `user=request.user`；`asset_view.py` found/repair action 适配返回值。

**契约保护**：
- 响应契约不变：create 响应 = 201 + `code:0` + `"创建成功"` + `CreateSerializer(record).data`。
- FSM 不增删节点：`IN_STORE→BROKEN/LOST`、`LOST→RECYCLED_PENDING(found)` 均在合法路径内。
- `user=None` 向后兼容：`reissue_recycle_asset` 不传 user，`ensure_asset_visible(asset, None)` 跳过校验，行为不变。
- schema 基线：仅 3 处 docstring 描述更新（broken/found/lost create），非破坏性。

---

## 九、P2 批次修复记录（2026-10-15）

> 按第二节批次 3 执行，六缺陷一并修复，登记 BF-092（`docs/BugFixed/Bug修复活账本.md`）。

| 缺陷 | 修复文件 | 核心改动 | 回归测试 | 门禁 |
|:-----|:---------|:---------|:---------|:-----|
| I-4 | `contract_selector.py` + `contract_service.py` | 新增 `get_contract_for_update`；三 service 换锁；save 收敛为 update_fields | `test_contract_payment_lock_and_settlement.py` 6 用例 | pytest 1909 全绿；ruff / mypy 通过 |
| I-10 | `contract_service.py` + `contract_view.py` | `update_settlement_status` FSM 后重算；新增 `recalculate_amounts_for_update`；`perform_update` 覆写 | 同上 5 用例 | 同上 |
| I-5 | `operation_log_service.py` + `audit.py` + `out_asset_service.py` | `log_asset_out` 加 `before_status`；双层透传；出库点传实际前状态 | 既有 `test_out_asset_service.py` 回归 | 同上 |
| I-6 | `damaged_asset_service.py` | 三处 FSM 补 except（INVALID_STATE_TRANSITION） | 既有 `test_damaged_asset_service.py` 回归 | 同上 |
| I-11 | `contract_view.py` | payment_record 端点改用 `ContractBatchPaymentRecordItemSerializer`（DR-1） | 既有 `test_contract_view_api.py` 回归 | 同上 |
| I-1 | `useAssetLifecycleActions.ts` + 4 API + 4 store + 4 视图 | 迁移至 `useServerExcelExport` 服务端导出 | `useAssetLifecycleActions.spec.ts` 2 用例 | vitest 2130 / 161 文件全绿 |

**I-4/I-10 修复细节**：
- `contract_selector.py:28-41`：`get_contract_for_update` = `lock_row_or_409(Contract.objects.select_for_update(), contract_code=..., is_deleted=False)`，锁超时映射 409。
- `contract_service.py`：add/delete/approve 三方法换 `get_contract_for_update`，`DoesNotExist` 翻译为 `CONTRACT_NOT_FOUND`；`update_settlement_status` FSM 成功后调 `_recalc_paid_amounts` + save 收敛为 `update_fields`（含 `updated_at`）；新增 `recalculate_amounts_for_update` 公共入口供 View 层调用。
- `contract_view.py:123-136`：`perform_update` 覆写——serializer.save 后若 `settlemented_price` ∈ validated_data 则调 `recalculate_amounts_for_update` + `refresh_from_db`。
- **测试守卫**：并发用例复用 `requires_row_lock = pytest.mark.skipif(connection.vendor == "sqlite", ...)`，SQLite 环境自动跳过，CI（postgres:16）照常执行。

**I-5/I-6/I-11 修复细节**：
- I-5：`log_asset_out` 加可选 `before_status`（缺省回退 `IN_STORE`）；`out_asset_service.py` 在 `_apply_outasset_to_asset` 改写前捕获 `outasset_previous_status` 传入。
- I-6：`damaged_asset_service.py:174-178, 245-249, 310-314` 三处 FSM 补 `except InvalidTransitionError → AppValidationError(INVALID_STATE_TRANSITION)`。
- I-11：**行为变更声明**——错误响应从手写 400 变为 DRF 统一 400 格式；`DecimalField` 要求恰好 2 位小数（旧代码接受 "100.5"，与批量端点对齐后收紧）。

**I-1 修复细节**：
- `useAssetLifecycleActions.ts`：`handleExportExcel` 从客户端 `exportToExcel` 迁移至 `useServerExcelExport.exportFromServer`；接口新增必填 `fetchExport` 参数，移除 `fileNamePrefix`/`exportColumns`。
- 4 API（broken/lost/found/repair）各加 `exportExcel` → `getBlob(.../export/, ...)`。
- 4 store（broken/lost/found/repair）各加 `xxExportExcel` 导出函数（独立函数，经 store 层消费满足 `no-restricted-imports` 分层约束——ESLint 禁止组件/视图直接 import `@/api/*`）。
- 4 视图改传 `fetchExport: xxAssetExportExcel`，import 从 `@/api/*` 改为 `@/stores/*AssetStore`。
- **本批迁移范围**：4 处生命周期页面（broken/lost/found/repair）；其余 8 处同型点（AssetContent/OutAsset/Contract/DamagedAsset/Waste/Recycle/HardDiskSN/UnregisteredAsset）为独立批次待后续处理。

**契约保护**：
- 响应契约不变：`payment_record` 成功响应结构不变；schema 基线仅 docstring 更新。
- FSM 不增删节点：I-10 仅在既有流转成功后追加重算，不改变流转路径本身。
- `before_status` 向后兼容：缺省回退 `IN_STORE`，既有调用方行为不变。
- 权限矩阵不变：I-1 仅迁移前端实现路径（客户端→服务端），后端 export 端点权限仍受保护。

**前端门禁明细**：type-check（0 error）/ lint（0 error）/ format:check（通过）/ vitest 2130 测试（161 文件）全绿。

**后端门禁明细**：pytest 全量 1909 passed（8 分 45 秒）/ ruff 通过 / mypy --strict 0 errors（226 files）/ schema 重导出非破坏性。

**后端门禁明细**：pytest 全量 1894 passed（21 分钟）/ Service 层覆盖率 99%（≥90% 达标）/ ruff check 通过 / mypy --strict 零错误（CT-7 版本对齐：mypy 2.1.0 / django-stubs 6.1.0 / djangorestframework-stubs 3.18.0 / types-channels 4.3.0.20260518 与 dev.txt 声明一致）/ schema 重导出验证通过。

---

## 十、P3 批次修复记录（2026-10-15）

> 按第二节批次 4（P3 部分）执行，五缺陷一并修复，登记 BF-093（`docs/BugFixed/Bug修复活账本.md`）。P4 部分（I-9 / M-1 / M-4 / M-5 / M-6 等）开放待后续批次。

| 缺陷 | 修复文件 | 核心改动 | 回归测试 | 门禁 |
|:-----|:---------|:---------|:---------|:-----|
| I-8 | `createEntityStore.ts` + `usePaginationSearchState.ts` | getList seq 守卫 + 两搜索函数 seq 三路守卫（成功/失败/finally） | `createEntityStore.edge.spec.ts` 2 用例 + `usePaginationSearch.spec.ts` 4 用例 | vitest 2148 / 161 文件全绿 |
| I-2 | `usePaginationSearch.ts` + `AssetContentDetails.vue` | resetToFirstPage 改 async + await loadList(1) | `usePaginationSearch.spec.ts` 1 用例改写 | 同上 |
| M-2 | `usePaginationSearch.ts` + `SmartListContainer.vue` + `types/common.ts` + `AssetContentDetails.vue` | 新增 searchWithReset 薄包装（置 1 + 委托）；消费点接线 | `usePaginationSearch.routing.spec.ts` 2 用例 + `SmartListContainer.spec.ts` 委托断言 | 同上 |
| M-3 | `usePaginationSearch.ts` + ContactsView/RoleManage/AuthUserManage | handleSizeChange 统一置 1；3 直连补 handleSizeChange 包装 | `usePaginationSearch.spec.ts` 1 用例改名 | 同上 |
| I-7 | `routes-main-system.ts` + `guards.ts` | 4 处 meta 补 requiredMinRole + roleWhitelist 前缀条目 | `guards.spec.ts` 双表增列 + 2 新增用例 | 同上 |

**I-8 修复细节**：
- `createEntityStore.ts:104`：闭包级 `let listRequestSeq = 0`（per-store）；`:208-213` getList 回调内 seq 自增（try 前声明），await 后过期即 `return []`，跳过页码校验/状态写回。
- `usePaginationSearchState.ts`：composable 实例级 `let searchSeq = 0`；performSearch（`:97-120`）/ performSearchWithParams（`:189-212`）成功路径过期跳过结果写回；catch 仅最新请求才清结果（过期失败仍 rethrow 不清场）；finally `if (seq === searchSeq)` 守卫 isSearching。
- 范式复用 `dashboard.ts:61/:268-293` trendRequestId（DR-1）。

**I-2 修复细节**：
- `usePaginationSearch.ts:177-183`：resetToFirstPage 改 async，clearSearch 后 `await loadList(1, pageSize.value)`；消费点补 `void`。

**M-2 修复细节**：
- `usePaginationSearch.ts:186-194`：`searchWithReset(params)` = `currentPage.value = 1` + 委托 `performSearchWithParams`；**不动原型**（翻页/刷新契约，routing.spec:50-65 钉死）。
- SmartListContainer slot/expose + types/common.ts 类型 + AssetContentDetails 消费点接线。

**M-3 修复细节**：
- `usePaginationSearch.ts:149-156`：handleSizeChange 删钳制改统一置 1（业界惯例）。
- 3 直连（ContactsView/RoleManage/AuthUserManage）各加 handleSizeChange 包装（置 1 + fetch）。
- **口径订正**：原审查标注 3 处，实测 5 处（composable + 3 直连 + NotificationList 已正确）。

**I-7 修复细节**：
- 4 处 meta（父+3 子）补 `requiredMinRole: 'system_admin'`（守卫只读 `to.meta`，子路由独立声明）。
- roleWhitelist 加 `'/main/departmentmanagement'` 前缀条目（双重保护）。
- 留痕：AsideMenu 已有 `v-if="canManageSystem"`（UI 层隐藏）；后端读侧为有意设计（选项 A）。

**契约保护**：
- 跨端契约不变：P3 批次纯前端修复，未动 API 响应结构/枚举/分页参数名。
- 状态机不变：I-8 仅加响应序号守卫，不改状态流转逻辑。
- 搜索态路由不变：M-2 新增薄包装不改 performSearchWithParams 原型，BF-083 搜索态路由契约（参数态/关键词态/列表态分流）不受影响。

**前端门禁明细**：type-check（0 error）/ lint（0 error）/ format:check（通过）/ vitest 2148 测试（161 文件）全绿 / 覆盖率分层（ts 层 93.03% / stores 层 97.64% / .vue 基线棘轮）EXIT=0 达标。

---

## 十一、P4 批次修复记录（2026-10-15）

> 按第二节批次 4（P4 部分）执行，九缺陷一并修复，登记 BF-095（`docs/BugFixed/Bug修复活账本.md`）。7 批顺序执行（批 1=M-1 → 批 2=M-4 → 批 3=M-5+M-7 → 批 4=M-6 → 批 5=I-9 → 批 6=M-8+M-9 → 批 7=M-10+门禁+文档），全部改动留工作区待用户审阅（未 commit）。

| 缺陷 | 修复文件 | 核心改动 | 回归测试 | 门禁 |
|:-----|:---------|:---------|:---------|:-----|
| M-1 | `apps/notification/views.py` | limit try/except + `min(..., 100)` + `max(limit, 1)` | `test_notification_views.py` 3 用例 | 后端 pytest 1915 passed / Service 覆盖率 97.91% |
| M-4 | 5 视图（Found/Lost/Recycle/Repair/MarkBroken） | 补 `:fetch-error` + `@retry` | 5 spec 各 2 用例 | 同上 |
| M-5 | `AssetForm.vue` | 缺 recordcode 分支改 throw | `AssetForm.spec.ts` 1 用例 | 同上 |
| M-6 | `repair_asset_service.py` | `Asset.PhysicalGrade.values` 校验 + fail-fast | `test_repair_service_gaps.py` 3 用例 + 5 处既有测试订正 | 同上 |
| M-7 | `ContractPaymentRecord.vue` + `api/contract.ts` | 载荷补 payment_date/method + 删死代码 + 类型抽取 | `ContractPaymentRecord.spec.ts` 2 用例 | 同上 |
| I-9 | `useNotificationConnection.ts` | intentionallyClosed + 旧连清理 + 心跳去重 + token watch | `useNotificationConnection.spec.ts` 6 用例 | 前端 vitest 2183 passed |
| M-8 | `BindAuthUserDialog.vue` | suppressNextSearch + 模板空态守卫 | `BindAuthUserDialog.spec.ts` 1 用例 | 同上 |
| M-9 | `useSuggestionFetcher.ts` | 闭包级 fetchSeq 乱序守卫 | `useSuggestionFetcher.spec.ts` 2 用例 | 同上 |
| M-10 | `GroupedAssetChildTable.vue` | el-pagination `:disabled="loading"` | `GroupedAssetChildTable.spec.ts` 1 用例 | 同上 |

**I-9 修复细节**：
- `useNotificationConnection.ts`：闭包级 `let intentionallyClosed = false`；`connect()` 入口先关旧连（`onclose=null; onerror=null; close(); ws=null`）+ `stopHeartbeat()` + 重置标志；`ws.onclose` 见 `intentionallyClosed` 直接 `return`；`startHeartbeat()` 前置 `stopHeartbeat()`；`disconnect()` 先置标志再关连；文件尾加 `watch(() => authStore.access_token, ...)` exhausted 且 token 非空时复位重连。

**M-1 修复细节**：
- `apps/notification/views.py`：`try: limit = min(int(qp.get("limit", 20) or 20), 100) except (ValueError, TypeError): limit = 20`，再 `limit = max(limit, 1)`。

**M-6 修复细节**：
- `repair_asset_service.py` `complete_repair`：校验块插入 `AssetFSM.repair_done` 之前（fail-fast 不触发状态流转）。
- 既有测试订正：5 处用「良好」非法值改「good」合法枚举（`test_asset_lifecycle.py:290`、`test_repair_service_gaps.py:136/310/333/338`）。

**M-7 修复细节**：
- `ContractPaymentRecord.vue`：提交补 `payment_date`/`payment_method`；删死代码（`payments`/`loadPayments`/`loading`/v-loading）；类型抽至 `api/contract.ts` `PaymentRecordPayload`（DR-1）。

**M-8 修复细节**：
- `BindAuthUserDialog.vue`：`suppressNextSearch` 标志抑制程序化回填触发的防抖检索；模板 `&& !selectedEmployee` 守卫空态提示。

**M-9 修复细节**：
- `useSuggestionFetcher.ts`：闭包级 `fetchSeq` 守卫，成功/失败路径均检查 `seq === fetchSeq` 才 `cb`；空输入自增使在途请求过期。

**契约保护**：
- 跨端契约不变：I-9/M-4/M-5/M-7/M-8/M-9/M-10 纯前端修复；M-1/M-6 后端 Service/View 层修复，未动 API 响应结构/枚举/分页参数名。
- 状态机不变：M-6 仅收紧 `physical_grade_after` 枚举校验，`Asset.PhysicalGrade` 枚举本身未变；fail-fast 置于状态流转前，非法值不触发迁移。

**门禁明细**：
- 后端：pytest 全量 1915 passed + 1 failed（`docker/feishu-webhook/test_app.py::HttpEndpointTests::test_unknown_path_404`，账本 :2371 已登记为已知环境性 flaky，隔离复跑绿，与本批零交集）/ 整体覆盖率 87.05%（≥80% 达标）/ Service 层覆盖率 97.91%（≥90% 达标）/ ruff check 通过 / C90 复杂度通过 / schema `--validate` 的 23 Errors 均为 APIView 无 serializer 的既存结构性回退，非本批引入。
- 前端：type-check（0 error）/ lint（0 error）/ format:check（通过）/ vitest 2183 测试（167 文件）全绿，exit 0，分层阈值（ts 80 / stores 90 / .vue 基线棘轮）达标。
