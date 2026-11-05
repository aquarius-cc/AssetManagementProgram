# 双源融合审计报告（merge-audit-20261031 × opencode-codegraph-audit-2026-11-01）

> 融合日期：2026-11-01 ｜ 融合方：opencode（本报告只读产出，未改动任何业务代码）
> **本文件 = 两份审计报告的合并台账 + 统一修复顺序**，替代两份单独报告作为修复执行的唯一输入。

**源报告**
| 源 | 文件 | 覆盖面 | 原编号 |
|:--|:--|:--|:--|
| 源A | `docs/Review/merge-audit-20261031.md`（AtomCode + trae + codebuddy 三源融合） | CI 编排 / 业务语义 / 授权模型 / 账本闭环 | `M-01`~`M-24` |
| 源B | `docs/Review/opencode-codegraph-audit-2026-11-01.md`（本 skill CodeGraph 五阶段） | 状态机 / 跨端契约 / RBAC 行级隔离 / 前端架构 / 护栏与覆盖率实跑 | `P1-1`~`P3-18` → 本文改号 `OP-01`~`OP-18` |

**融合方法**
1. **状态复核（Fact-1）**：源A 台账 14 个待修项由融合方逐条 `rg` / 直读当前工作区复核，实际状态与源A 标注不一致处以本次复核为准（见 §二「状态复核差异」）。
2. **去重**：同题条目合并为一条，双源证据并列（§一 同题归并表），不重复计入台账。
3. **编号不复用**：保留源A `M-xx` 原编号（与活账本 BF 条目、历史批次对齐），源B 新增项用 `OP-xx` 前缀，避免与 `merge-audit-20261029` 等其他报告的 `M-xx` 撞号（见 §四 优化建议 9）。

**状态基准（Fact-1，融合方 `git log/status` 实测）**
- 父仓 HEAD `d7e2fa9`｜后端子模块 `5a27ca5`（**+6 文件未提交**）｜前端子模块 `9ba1fb1`（+1 文档未提交）
- 后端工作区未提交改动 = 源A「批次 2」：`dashboard_selector.py`(+46/-…)、`damaged_asset_view.py`(2)、`contract_view.py`(1)、`conftest.py`、`test_base_selector.py`、`test_p2_04_export_endpoints.py` + 2 个未跟踪测试
- 源A 批次 1 已提交：父仓 `1281523`（M-02/M-09/M-10/M-24，BF-167【待验证】）

---

## §一 共识区与同题归并

### 1.1 双源交叉一致（无需再查）

| 结论项 | 源A（三源融合） | 源B（CodeGraph 实跑） | 一致性 |
|:--|:--|:--|:--|
| 状态机 CT-3 | ✅ FSM 外零直写，8 写入点全在 `state_machine/` | ✅ **旁路 0 处**（8 处赋值全在具名方法，逐处判定合法） | **一致，项目最强项** |
| 跨端契约 4 项 | ✅ 三源逐字一致 | ✅ 实测 `+08:00` 序列化 + 分页 7 字段对齐 | **一致，零破坏** |
| 安全红线 SC-1/SC-3 | ✅ 静态面零命中 | ✅ `.env` 未入 git history；raw SQL 全参数化/白名单 | 一致 |
| 文件/函数规模护栏 | ✅ 三护栏 exit 0 | ✅ 五护栏实跑全 PASS（file 483≤500 / function 0 超限 / frontend 三类 0 违规 / duplicate 不变量 PASS） | 一致（源B 多跑 2 个护栏） |
| 覆盖率 | ① 89.33% 本地 / 88.93% CI | **89.40% 本地**（2269 passed）、Service **98%**、前端 Stores **97.21%** | 口径一致，均绿 |
| npm dev 高危 4 项 | M-18 | OP-12 | **同题归并** |
| pip-audit 本地未装 → CI 权威 | M-23 | 源B 未执行项 | **同题归并** |

### 1.2 同题归并表（去重，不重复计入）

| 归并后 | 源A 条目 | 源B 条目 | 归并说明 |
|:--|:--|:--|:--|
| `M-18`（P3） | npm audit 4 high（dev） | `P3-12` | 完全同题，取 M-18 编号；源B 补充了 CI `--audit-level=high --omit=dev` 的决策依据（P2-07 注释） |
| `M-23`（P3） | pip-audit 以 CI 为权威 | 源B §5.3 兜底留痕 | 同题 |
| `OP-04` 关联 `M-12` | Dashboard 合同统计未隔离 | 合同导出绕过 BF-127 | **同主题不同缺陷**，不合并条目，但**同批拍板**（同为「合同读面口径」） |
| `OP-05` 关联 BF-165 | — | 审计快照明文手机号 | 源B 发现；须叠加活账本 **BF-165【WAI 关闭】**（API 侧脱敏被业务否决、维持明文）上下文决策，见 §二 |
| 状态机旁路疑点 | ①②③ 各自提出后排除 | 独立复核为 0 处 | 结论一致，归档 |

### 1.3 源A 状态复核差异（本次 `rg` 实测，覆盖源A 标注）

| 条目 | 源A 标注 | 本次复核（工作区实测） | 修正后状态 |
|:--|:--|:--|:--|
| **M-03** Dashboard 截断 | 订正「到期预警已修复，维护提醒非 Bug」 | `dashboard_selector.py` 已改为**窗口超集过滤 + 截断后移**（注释明标 `M-03: 修复先截断后过滤的漏报`），含新增 `test_dashboard_alert_window.py` | ✅ **已修 · BF-168** |
| **M-04** 导出空列 | 待修 | `damaged_asset_view.py:67` 已为 `field: "damaged_date"` | ✅ **已修 · BF-168** |
| （未编号）合同导出列 | 未登记 | `contract_view.py:101` `contract_sign_date → contract_start_date` | ✅ **已修 · BF-168（归位登记）** |
| **M-05** 双 toast | 待修 | `usePaginationSearch.ts:113-114` `notifyCallerError` + `ElMessage.error` 并存 | ✅ **已修 · 工作树（批次 4，BF-172）**；同型家族另五处收编见 BF-171/B-29（已提交 39b7118），漏网 1 处已登记 B-30 |
| **M-06** 删除双成功 | 待修 | `disableAutoMessage` 仅存在于 `recycleAssetStore` / `damagedAssetStore` / `operationLogStore`，**broken/lost/found/repair 4 store 仍缺** | ✅ **已修 · 工作树（批次 4，BF-172）** |
| **M-07** 批量字面量 | 待修（8 处） | 生产代码 8 处字面量 + 6 处显式常量实参（实测 14 处；rg 重锚后 asset_service:312 / out_asset:306 等） | ✅ **已修 · 后端 1cc185f（批次 5，BF-173）** |
| **M-08** 枚举硬编码 | 待修（5 处） | 实测 **7 处**（原 5 处 + department_view 白名单 + employee_serializers.py:174 default="active" 漏网并入；providers 归属/行号两处审计误差经 rg 重锚订正） | ✅ **已修 · 后端 1cc185f（批次 5，BF-173）**；护栏 G-8 落地（cd3e49f，AGENTS v3.7.4） |
| **M-11** 宽 except | 待修 | `core/batch_mixins.py:143,216` 仍 `except Exception` | ⛔ 仍开放 |
| **M-12** 合同统计 | 待修 | `dashboard_selector.py:69` `Contract.objects.filter(...)` 仍无 scoped 分支（同函数 :44 资产已 scoped） | ⛔ 仍开放 |
| **M-01** 创建越权 | 待修 [HALT] | `asset_service.py:132` `create_asset(asset_data, operator_jobcode, operator_name)` **仍无 user 参数**；`asset_view.py:135` 调用未传 | ⛔ 仍开放 [HALT] |

---

## §二 合并问题台账（统一编号，含影响面与验证方式四要素）

> 状态口径：⛔ 待修 ｜ ✅ 已修（提交/工作区）｜ 📕 账本在册/立项 ｜ 🔵 [待确认] ｜ ❌ 不采纳

### P1（4 条）

| ID | 源 | file:line / symbol | 问题（双源证据） | 修复建议 | 影响面 | 建议验证方式 | 状态 |
|:--|:--|:--|:--|:--|:--|:--|:--|
| **M-01** | A③F-01 | `views/asset_view.py:132`、`services/asset_service.py:132` | **资产创建路径无部门范围校验**：update 传 `user=` 行级校验，create 不传；三个归属外键 queryset 全量 → asset_admin 可创建挂他部门资产，创建后即脱离可见范围（写侧越权） | 方案 A create 传 user + 三外键比对部门码；方案 B 显式代录白名单。**需产品拍板 [HALT]**（对照未登记资产域仅 system_admin 可代录） | 小：单端点 + Service 加参 | A/B 部门夹具镜像 `test_contract_read_scope.py` 补 `test_asset_create_cross_department_denied` | ⛔ [HALT] |
| **OP-01** | B P1-1 | `views/department_view.py:100` → `selectors.py:188`（`get_employees_by_department_instance`） | **员工域行级隔离旁路**：`employees` 落 `get_permissions` else 分支仅 `IsAuthenticated`（:71），底层裸 `Employee.objects.filter(employee_department=...)`，任意登录用户遍历部门可枚举全公司员工 —— §4.7 明令禁止的 action 内 filter 写法 | 改走 `get_employee_scoped_queryset_for_user(user, ...)`，越权 404；扩展 `test_employee_rbac_scope.py` | **极小（impact=2 符号）** | A 部门 regular_user 请求 B 部门 `employees` → 现状 200 全量，修后 404/空集 | ✅ **已修 · BF-170**（is_department_visible 404 口径 + 5 用例） |
| **OP-02** | B P1-2 | `views/out_asset_view.py:295`、`services/out_asset_service.py:296,307` | **出库批量删除跨部门**：service 不收 user，`_delete_one` 全表 `get_outasset_for_update` 取行；同仓 asset(`asset_service.py:303-310`)/recycle(`:386`)/damaged 三链均已收口，**出库是唯一漏网** | `batch_delete_passes_user=True` + `_delete_one` 补 `ensure_asset_visible`（复用既有助手，DR-1）；**禁止改公共 `batch_delete_execute`（impact=92）** | 中：单 service 链 + 保留 `select_for_update`/TOCTOU | A/B 两部门各 1 条 → A 经理批量删 B 编码：现状静默成功，修后进 `fail_items`；回归 `pytest apps/assetmanagement` | ✅ **已修 · BF-170**（kw-only user + 锁内 ensure，TOCTOU 模板） |
| **OP-03** | B P1-3 | `views/waste_asset_view.py:206`、`services/waste_asset_service.py:57,25` | **报废批量删除跨部门**：`cancel_waste_asset` 按 `asset_recordcode__asset_code` 全表查找、不收 user（与 OP-02 同型） | 同 OP-02：传 user + 逐条 `ensure_asset_visible` | 小（`cancel_waste_asset` impact=6 符号） | 同 OP-02 同构用例 + auditor 调用应 403 | ✅ **已修 · BF-170**（kw-only user + 逐条 ensure + auditor 403） |

> **P1 组内排序**：`OP-01`（影响面最小、规则无歧义）→ `OP-03` → `OP-02` → `M-01`（需拍板，与批次 4 并行发起，不阻塞其余）。

### P2（开放 17 条 + 已修 2 条）

| ID | 源 | file:line / symbol | 问题 | 修复建议 | 影响面 | 建议验证方式 | 状态 |
|:--|:--|:--|:--|:--|:--|:--|:--|
| **M-05** | A③F-03 | `src/composables/usePaginationSearch.ts:113-114` | 列表加载失败**双 toast**（`notifyCallerError` + 无条件 `ElMessage.error`），违反 M-RC-09 单出口注释 | 删 `ElMessage.error(messages.loadFailed)` | 单文件 | 模拟 AxiosError/非 AxiosError 各断言仅 1 次 toast | ✅（工作树 · 批次 4） |
| **M-06** | A③F-04 | `stores/{brokenAsset,lostAssetStore,foundAssetStore,repairAssetStore}.ts` + `useAssetLifecycleActions.ts:67-71` | 生命周期详情页删除出现**两条成功提示**（store 自动消息 + composable 手动消息） | 4 store 补 `disableAutoMessage: true`（与 recycle/damaged 对齐） | 4 个配置 | 挂载断言删除流程仅 1 条 toast | ✅（工作树 · 批次 4） |
| **M-07** | A③F-05 | `services/*` 8 处 `max_batch_size=100` | **DR-1 常量旁路**：`core/batch_mixins.py:74 DEFAULT_MAX_BATCH_SIZE` 为唯一真值，8 处字面量旁路 | 8 处删实参走默认回落；按 §1.8 登记账本（与 B-4 同族） | 零行为变更 | `rg 'max_batch_size *= *100'` 生产 0 命中 + 批量 pytest 全绿 | ✅（后端 1cc185f · 批次 5 BF-173；实扩 14 处＝8 字面量＋6 显式常量） |
| **M-08** | A①AUD-31-1 | `notification/helpers.py:54`、`usermanagement/selectors.py:201,236`、`providers.py:37` | **BR-3 枚举硬编码** `role="dept_manager"` / `employee_status="active"` 共 5 处 | 替换为 `Employee.Role.DEPT_MANAGER` / `EmployeeStatus.ACTIVE` | 小，语义零变化 | rg 零字面量 + notification/usermanagement pytest | ✅（后端 1cc185f · 批次 5 BF-173） |
| **M-11** | A③F-06 | `core/batch_mixins.py:143,216` | `batch_execute` 宽 `except Exception` 吞 **DatabaseError**：连接中断/死锁被降级为逐条失败，无 savepoint 时 PG 事务中止会污染 success_items 与落库一致性 | 在 `except Exception` 前显式 `except django.db.DatabaseError: raise`（fail-fast） | 单文件，需核对各调用方 savepoint | 模拟 DatabaseError 断言整体失败而非逐条 fail_items | ⛔ |
| **M-12** | A③F-08 | `selectors/dashboard_selector.py:69` | Dashboard **合同统计未隔离**：同函数资产已 `_scoped_asset_queryset`，合同总数仍全公司口径，而合同读权限已锁 system_admin（BF-127） | 非 system_admin 返回 None/0 并注明；补断言 | 单 Selector 分支 | dept_manager 登录断言合同统计为 None/0 | ⛔（与 M-01、OP-04 **同批拍板**） |
| **M-13** | A③F-07 | `api/assetCache.ts:128-131` vs 18 处 M-RC-08 调用点 | **缓存失效两套时序并存**（删除后失效 14 处 / 状态变更先失效 18 处 fire-and-forget）→ 并发读回填旧数据直到 TTL 5min，诱发重复提交 | M-RC-08 统一 `async` + await 后失效 | 大：前端 7 个 API 模块 | 并发读时序单测 + 关键写路径回归（单独成批） | ⛔ |
| **OP-04** | B P2-1 | `core/permissions.py:229-230`、`views/contract_view.py:80-88` | **合同导出绕过 BF-127**：`resolve_viewset_permissions` 中 `export_excel` 短路**优先于** `action_overrides`，dept_manager/asset_admin/auditor 持 `CanExportExcel` 即可导出全量合同（金额/起止日期） | 首选**局部修**：`ContractViewSet.get_permissions` 对 `export_excel` 返回 `[IsSystemAdmin()]`；**禁改公共函数**（impact=53 符号） | 小（局部改）/ 大（改公共优先级则需全量导出矩阵回归） | auditor 导出合同 → 现状 200 全量，修后 403；回归其余 11 个导出端点 | ⛔（与 M-01/M-12 同批拍板） |
| **OP-05** | B P2-2 | `views/employee_view.py:224,229`、`employee_serializers.py:80`、`employee_audit_adapter.py:35` | **OC-3：审计快照落明文手机号** —— `EmployeeDetailSerializer(fields="__all__")` 的 before/after 整份写入 `AuditLog` | 入库前剥离/脱敏 `employee_phone`（复用 `mask_phone_number`，DR-4）+ 回归断言 | 小（3 符号）；**决策提示**：须与活账本 **BF-165【WAI 关闭·API 侧维持明文】** 一并确认口径，避免与业务决策冲突 | 更新员工 → 查 `AuditLog` 行断言无明文手机号 | ⛔（**先确认与 BF-165 关系**） |
| **OP-06** | B P2-3 | `scripts/check_frontend_invariants.py:74-78` | **护栏盲区**：`is_store_target` 用 `startswith("use")` 排除 composable，**`userStore.ts` 被误排除**（护栏 31 / 实际 32），未来超 500 行将假绿 | 排除条件改显式白名单或目录全量扫描 + 护栏自测证红证绿 | 仅护栏脚本，零业务 | 造 `userStore.ts` >500 行变体断言护栏红 | ⛔ |
| **OP-07** | B P2-4 | `src/composables/useGroupChildrenCache.ts`(126) 等 8 个 | **8 个 composable 零测试引用**（`rg` 复核 0 命中），FR-6 规模榜首区无行为锚 | 按逻辑行降序补 spec（前 4 优先），微小件并入消费方测试 | 仅测试面 | 新增 spec 全绿且 8 个各有独立锚 | ⛔ |
| **OP-08** | B P2-5 | `src/composables/__tests__/batchB.contract.spec.ts:220-298` | `vi.hoisted`/`vi.mock` **位于 describe 块内**（实测 :225/:230/:239 起，均在 `describe('M-12/M-19…')` 内），vitest 4.1.11 警告「future version 将报错」→ 升级即 CT-5 假红 | 全部提升至文件顶层 | 单 spec 文件 | 运行无 `vi.mock` 非顶层警告 | ⛔ |
| **OP-09** | B P2-6 | `utils/response_utils.py:23,37`、`core/mixins.py:91-215` | **OpenAPI 信封仅 8% 建模**：338 响应规格中 27 个含 `{code,message,data}`，211 个裸对象 → 生成客户端拿到错误契约（§4.8 OS-5 同类失真） | 共享 `ENVELOPE_SCHEMA` 后处理器（复用 `core/pagination.py:94-118`），零运行时改动 | 仅 schema 产物 | 重导基线 diff 只落预期端点、CI `api-schema-check` 绿 | ✅ **已修 · BF-178（2026-11-04：提交 e3b8f50 幽灵 8 条 + 30085f6 envelope_postprocessor 四零收编，基线 273→265、19 destroy 204→200 信封，--validate 双跑 identical，8 护栏全绿）** |
| **M-03** | A③F-02 | `selectors/dashboard_selector.py:296-336` | Dashboard 即将到期**先截断后过滤**系统性漏报（维护提醒分支经复核非 Bug） | 已按窗口超集过滤 + 截断后移修复 | — | >50 条夹具断言第 51+ 名次正确入选（新增 `test_dashboard_alert_window.py`，含 2 年保修缩放用例锁死 `12*max_warranty`） | ✅ **已修 · BF-168** |
| **M-04** | A③F-09 | `views/damaged_asset_view.py:67` | 报废导出「损坏日期」列恒为空（field 拼写 `damaged_asset_date` ≠ 模型 `damaged_date`） | 已改 `damaged_date` | — | 单元格行断言在 `test_p2_04_export_endpoints.py`（按表头定位「损坏日期」列，非空且等于 DB 值）；`test_export_columns_contract.py` 为静态字段解析护栏（61 列，61 列全可解析才绿） | ✅ **已修 · BF-168** |
| **M-14** | A②R-03 | `setup.cfg:20-83 [mutmut]` | 变异范围仅 assetmanagement services（≈29%），usermanagement/notification 零覆盖 | 分批扩 source_paths（先 usermanagement），扩前评估耗时 | 立项 | T7 双门禁留痕 | 📕 立项 |
| **M-15** | A②R-08 | 账本 D-2（`complete-patterns.md:887`） | init_production_data 3 个字段名 bug 未闭环 | 按 D-2 修复 + 用例 | 账本在册 | 账本销项 + 命令 dry-run | 📕 |
| **M-16** | A②R-09 | 账本 D-5（`:898`） | getassetbyrecordcode 路径/query 双入口，纯路径调用必 400 | 统一取参或双入口兼容 + 集成测试 | 账本在册 | 集成测试 | 📕 |
| **M-17** | A②R-07 | 账本 B 区 9 项（`:461-676`） | B-1 审计适配器克隆 / B-2 状态映射死副本 / B-3 三重复制 ViewSet / B-4 MAX_BATCH_SIZE×31 / B-5 batch-result 手写 / B-6 批量镜像 / B-7 throttles 三重 / B-12 员工状态双源 / B-26 section-title×5 | 按账本既定批次收敛，**B-4/B-5 面最大先做；M-07 并入 B-4 批次** | 账本在册 | 护栏 + rg | 📕 |

### P3（合并后 12 组）

| ID | 源 | 位置 | 问题 / 建议 | 状态 |
|:--|:--|:--|:--|:--|
| M-18 ≡ OP-12 | A+B | `package.json` devDependencies | npm audit **4 high**（happy-dom / undici / vite / zod），全 dev 链、生产链 0 high；CI `--audit-level=high --omit=dev` 为门禁。建议定期 `npm audit fix` 收敛 | ⛔（双源同题） |
| M-19 | A③F-13 | `assetmanagement/audit.py:60-120` | 审计写失败被吞仅记 error → 关键流转（approve/scrap）改强一致或加 `audit_write_failed` 指标告警 | ⛔（与 OP-10 同主题） |
| **OP-10** | B P3-1 | `unregisteredasset/handlers.py:154-222` | S1 场景裸 `Asset.objects.create` + FSM 落态**无资产级 create/state 审计**（S2/S3 已由 M-16 补痕）→ 对齐 M-16 范式补 `log_state_change` | ⛔ |
| **OP-11** | B P3-5 | `serializers/asset_crud_serializers.py:91-127` | `AssetDetailSerializer` 含 `asset_current_status` 但**无 `read_only_fields`**，且是 ViewSet 兜底类（「未上膛的枪」）→ 补 `read_only_fields = fields` 零行为变更 | ⛔（与 M-01 同文件族，可同批） |
| M-20 | A③F-15 | `stores/assetStore.ts:144-147` vs `:173` | getList 无参回落 `page_size:10` 与 `defaultPageSize:20` 不一致 → 统一取 defaultPageSize | ⛔ |
| **OP-13** | B P3-13 | `composables/useExcelExport.ts:165` | `toISOString()` **UTC 时间戳**做导出文件名（本地 16:00 后日期少一天）→ 改 `toLocalDateString`（M-33 单源） | ✅（工作树 · 批次 4） |
| **OP-14 / OP-15** | B P3-14/15 | `types/outasset.ts:126`、`types/asset.ts:321,364` | 类型裸 `string` + 注释只列 4 态 → 改枚举类型 / 注释改 8 态全集 | ✅（工作树 · 批次 4；OP-14 采纳**别名化**拍板：`export { AssetCurrentStatus as OutAssetCurrentStatus }`，非补宽方案） |
| **OP-16/17/18 群** | B P3-2/3/4/6/7 | `backend-business-rules.md` §三 / `state_machine/unregistered.py` / `asset_lifecycle_mixin.py:82-90` | 规则文档三处缺口（特殊回退表缺 S1 两路径、`repairing→damaged` 双边、**合同状态机零文档**）+ lifecycle 审计缺 before/after + S1 裸 create 字面违约 | ⛔（文档批次） |
| **OP-19 群** | B P3-8/9/10 | `employee_query_actions.py:234` / `role_view.py:80` 等 / `config/urls.py:155` | 工号探测存在性、系统配置读面、`/metrics/` 无鉴权 → 前者改 `get_queryset()`，后两者 **[待确认]** 需业务/运维拍板 | 🔵 |
| **OP-20** | B P3-11 | `backend/.env:9,14` | 疑似真实凭据，已核实**从未入库**（`git log --full-history` 空）→ 确认轮换 + pre-commit 强拦截 | ⛔ |
| **OP-21 群** | B P3-16/17/18 | `ContractPaymentRecord.vue:180` / `LogIn.vue:228` / `eslint.config.ts:37` / `coverage-summary.json` | ①组件内局部映射 → **按 §1.8 登记账本待核查区**；②rememberMe 键散落 → 抽 utils；③**FR-7 无 `vue/max-depth` 门禁** → 新规按 §5.4 走 14 日沙盒；④陈旧覆盖率工件含已删文件条目 → 移出仓库根 | ⛔ / 🔵 |
| M-21 / M-22 | A③ | 各处 | 零引用依赖 / dev host 0.0.0.0 / 类型注释漂移 / @action 死配置 / 双端点冗余 / ip_address 可见性 | 低优先迭代 |
| M-23 | A | — | pip-audit 本地未装，后端依赖以 CI `security-scan.yml` 为权威 | ✅ 留痕 |

### 已修区（源A 批次 1，已提交）

| ID | 内容 | 落地 | 状态 |
|:--|:--|:--|:--|
| M-02 + M-09 + M-10 + M-24 | ci-summary 收全 15 job / CI lint 去 `--fix` / 新增 frontend-format / 新增 guard-summary + CD 触发源改 CI Pipeline | 父仓 `1281523` + 前端 `9ba1fb1`，活账本 **BF-167【待验证】** | ✅ 已修（残余取证：推送后 CI 首跑 + 探针注入） |

### 不采纳（融合后维持，附理由）

源A §二不采纳 5 条（api-schema warning 属规范设计 / .vue 棘轮过渡态 / test.py SECRET_KEY 豁免 / 组件层 pageSize 命名 / 三源状态机旁路疑点）+ 源B 无新增不采纳项（2 条 [待确认] 转 🔵）。

---

## §三 统一修复顺序（分批小步验证，根 AGENTS §1.2）

**排序原则**：已改未提交先收口 → 无歧义高危（行级隔离）→ 需拍板项并行发起（不阻塞）→ 用户可见小改 → 零风险 DRY → 健壮性/合规 → 护栏与测试锚 → 文档与账本收尾。**同批一次清干净（DR-1/DR-2）**，每批一提交。

```text
批次 0【收口已改未提交，立即】 M-03 + M-04 + 合同导出列字段（未编号，须归位登记）
  → 工作区 6 文件 + 2 测试已就绪，补跑验证后提交（含 BF 登记）
  验证：pytest apps/assetmanagement -q（含新增 test_dashboard_alert_window /
        test_export_columns_contract）→ 导出 xlsx 列非空 + >50 条夹具入选正确。
  ⚠️ 归位：contract_view.py contract_sign_date→contract_start_date 需在活账本补编号。

批次 1【残余取证，与批次 0 并行】 批次 1（M-02/M-09/M-10/M-24）推送后 CI 首跑
  → 探针注入验证 ci-summary / lint:ci / frontend-format / guard-summary 真红
  → BF-167【待验证】转【已关闭】。
  → ✅ 已完成 2026-11-01：PR 分支探针四门全红 + 首跑 16/16 绿 + CD 门禁双实例
    直证，BF-167 转【已关闭】，明细见活账本 BF-167 §六（master 未污染，PR #1 已关已删）。

批次 2【P1 行级隔离三连，规则无歧义·最高优先】 OP-01 → OP-03 → OP-02
  → 员工枚举旁路（impact=2）先行；出库/报废批量删除收口（复用 ensure_asset_visible，
     禁改公共 batch_delete_execute，impact=92）
  → 配套新增护栏断言：「batch_delete_* 必须接收 user」（防再发，见 §四-1）
  验证：三组跨部门用例（越权 404 / fail_items）+ test_employee_rbac_scope 扩展
        + pytest apps/usermanagement apps/assetmanagement 全绿。

批次 3【授权读面拍板，与批次 2 并行发起 [HALT]，不阻塞】 M-01 + M-12 + OP-04
  → 同一拍板主题：「跨部门代录是否合法」「合同聚合/导出可见性口径」
  → M-01 方案 A/B 拍板 → create 传 user；M-12 非 system_admin 返回 None/0；
     OP-04 局部覆写 ContractViewSet.get_permissions（禁改 resolve 公共优先级）
  验证：CT-4 回归 4 例（create 跨部门拒绝 / 合同统计 None / auditor 导出 403 /
        其余 11 导出端点不受影响）。

批次 4【前端 UX 小改】 M-05 + M-06 + OP-13 + OP-14 + OP-15
  → 双 toast 两处 + 4 store disableAutoMessage + 导出文件名时区 + 类型/注释
  验证：toast 各 1 条断言；16:00 后日期断言；type-check + vitest 全绿。
  ✅ **已执行（2026-11-02，工作树待提交，BF-172）**：12 用例先红后绿 + 三项检查 + 全量 2431 全绿 + 护栏双 PASS。

批次 5【DRY 常量收敛，零行为变更】 M-07 + M-08（并入账本 B-4 批次登记）
  → 8 处 max_batch_size + 5 处枚举字面量
  验证：rg 零字面量 + 相关 app pytest；账本登记留痕（§1.8 新发现义务）。
  ✅ **已执行（2026-11-02，后端 1cc185f + 根仓 cd3e49f，BF-173/A-54）**：
  M-07 实扩 14 处（8 字面量＋6 显式常量）删实参走 DEFAULT 回落；M-08 实测 7 处收编
  （含 :174 default="active" 漏网并入、providers 归属/行号订正）+ CT-1 真库/RBAC/等价
  断言 7 条 + 护栏 G-8 + AGENTS v3.7.4；四域 pytest 1875 全绿 + ruff/mypy + 护栏真仓 PASS
  + 自测 22 passed。批次 5 v1.1 两项拍板（①M-08 并入第 7 处；②G-8 AST 收窄口径）全落地。

批次 6【后端健壮性 + 审计合规】 M-11 + OP-05（先确认与 BF-165 WAI 关系）+ OP-10 + M-19
  → DatabaseError fail-fast（先核对 savepoint）/ 审计快照脱敏 / S1 补痕 / 审计失败告警
  验证：DatabaseError 模拟断言整体失败；AuditLog 无明文手机号断言；S1 状态前后断言。

批次 7【前端护栏与测试锚，零业务代码】 OP-06 + OP-08 + OP-07
  → 护栏盲区修复（先证红后证绿）/ vi.mock 提升顶层 / 8 个 composable 补 spec
  验证：护栏变体证红；vitest 无非顶层警告；186 files 全绿。
  ✅ **已执行（2026-11-03，根仓 3893be1 + vue 86fb829，BF-175）**：
  OP-06 `is_store_target` 收编目录全量（证红 3 failed → 证绿 49，FR-8 stores 31→32 含
  userStore.ts，条文 v1.5 + AGENTS v3.7.5）；OP-08 batchB 11 处 vi.hoisted/vi.mock 提升文件
  顶层（doMock 原位，警告 11→0，9 绿）；OP-07 八件全部锚定（前 4 独立 spec 24 用例 + 后 4
  并入消费方 spec 13 用例），验收 191 files / 2469 passed（较批 4 基线 2432 净 +37）、
  覆盖率阈值（ts 80 / stores 90 / vue 组）无违入、type-check / lint:ci / format:check 全绿、
  护栏 PASS + 自测 49 passed。措辞订正：OP-07 原「零测试引用」按拍板表述为
  「spec 直接引用 0 / 生产消费方真实存在」。

批次 8【OpenAPI 信封建模，纯文档】 OP-09
  → 共享 ENVELOPE_SCHEMA + 重导 api-schema-baseline.json
  验证：spectacular --validate + diff 只落预期端点（OS-6），CI api-schema-check 绿。

  ✅ **已执行（2026-11-04，后端 e3b8f50 + 30085f6，BF-178）**：
  阶段 0 机械分类基线 273 op（27 envelope / 189 bare / 15 非 JSON / 42 no-body）
  → 提交 1 幽灵 CRUD 8 条退场（dashboard×5 去 ResponseWrapperMixin 404 双保险 +
  permissions×3 http_method_names 405，先红后绿 + 双向 grep 零引用）→ 提交 2
  envelope_postprocessor 单点接线（core/envelope_schema.py + POSTPROCESSING_HOOKS，
  x-envelope 标记）；量化四零直证（bare 0 / 嵌套 0 / 15 非 JSON 名单保持 / no-body 名单保持），
  19 真实 destroy 204→200 信封化、qr-code-image image/png 声明、G-1 注释 7 处/3 文件
  267→265、T2.7 statistics/sort 断言下钻、api_schema fixture 上提根 conftest（DR-1）；
  基线重导 --validate 双跑 identical，8 条护栏 core/tests/test_openapi_envelope_contract.py
  全绿、员工域 test_employee_openapi_contract / security / search_contract 回归绿；
  护栏（BR-4/BR-6/duplicate invariants）PASS。
  CI 直证双轮：run 41845268470 暴露批 6 隐债（审计代码先落、metrics.py 未提交）→ 批 6 收端
  `49a3096` 闭合 AUDIT_WRITE_FAILED 四引用方环；run 41853701286 暴露 M-3 配套 4 处信封结构失配
  （statistics×3 + dashboard/overview）→ `88637b2` api_field_reference response 下钻补齐；
  **终线 run 41944228502 success @ 88637b2（16 job 全绿）+ CD run 41948745557 success。**

批次 9【前端缓存时序，大回归面单独成批】 M-13
  → 18 处 M-RC-08 改 await 后失效
  验证：并发读时序单测 + 关键写路径回归。

批次 10【账本/立项/依赖】 M-14 + M-15 + M-16 + M-17 + M-18 + M-20
  → mutmut 扩围立项 / 账本 D 区闭环 / B 区批次（B-4/B-5 先做）/ dev 依赖升级

批次 11【P3 文档与卫生尾巴】 OP-11 + OP-16~OP-21 + M-21 + M-22 + OP-19（[待确认] 拍板）
  → 规则文档三处补（含合同状态机章节）/ read_only_fields 一行 / .env 轮换 /
     组件映射登记账本 / FR-7 门禁按 §5.4 走沙盒 / [待确认] 两项拍板
```

**关键判断（融合方）**
1. **批次 0 最优先**：工作区已有 3 处修复未提交（含 2 个未跟踪测试），久置会与后续批次混杂、且 `damaged_asset_view.py`/`dashboard_selector.py` 正是 M-03/M-04 的修复载体。
2. **OP-01~OP-03 是本次新增的最实质风险**（授权缺口），且规则明确、无需拍板 → 早于源A 的批次 6（授权拍板）执行；源A 把 M-01 排在批次 6 是因需 [HALT]，两者不冲突，**拍板与修复并行**。
3. **M-01 / M-12 / OP-04 必须同一场拍板**：三者同为「合同/部门可见性」授权口径，拆开会导致口径二次漂移。
4. **禁改公共件的两处红线**：`batch_delete_execute`（impact=92）、`resolve_viewset_permissions`（impact=53）——一律**局部收口**，影响面各收敛到 1~2 个符号。
5. **OP-05 有决策前置**：活账本 BF-165 已把员工手机号 API 侧脱敏判为 WAI，日志侧（OC-3）虽是不同暴露面，仍应并案确认，避免推翻已拍板口径。

---

## §四 修复优化建议（结构性 / 流程性，超出单条修复）

1. **加「批量删除必须传 user」护栏断言**（防 OP-02/OP-03 类再发）：`asset/recycle/damaged/lifecycle` 四链各自收口、出库/报废漏网，说明收口靠逐条人工推进。建议在 `scripts/check_duplicate_invariants.py` 同构新增不变量：*所有 `batch_delete_*` / `_delete_one` 签名须含 `user` 或显式豁免登记*，CI 阻断。
2. **导出端点权限矩阵表驱动测试**：`ExportExcelMixin` 13 个消费方 + `resolve_viewset_permissions` 的 `export_excel` 短路是全局单点，任何新增导出都可能绕过 `action_overrides`。建议以 §4.2 权限矩阵「导出行」为数据源生成参数化用例（12 导出面 × 5 角色），一次兜住 M-12/OP-04 同类。
3. **护栏盲区修复必须配套护栏自测**：OP-06 证明前缀排除式启发式会假绿；修后在 `scripts/tests/` 增「变体证红」用例（先红后绿），与已有护栏自测套件同构。
4. **规则文档补齐两处事实源缺口**：合同状态机零文档（OP-16 群）、特殊回退表缺 S1 两路径 —— 文档缺失正是当年资产状态机漂移的根因；随下次规则修订一并收口。
5. **OpenAPI 信封建模走共享片段**：与 `core/pagination.py:94-118` 同构，禁止逐端点手写（§4.8 OS-3/OS-4）；重导基线随 PR 提交。
6. **审计快照脱敏统一 helper**：手机号脱敏收敛到 `utils/string_utils.mask_phone_number`（DR-4），供 AuditLog / 导出 / 日志三处共用，避免第三处再手写。
7. **CI 依赖策略对齐 SC-7 条文**：`--omit=dev` 是刻意决策（P2-07），但 dev 链 4 high 长期悬挂与 SC-7「CVSS≥7.0 阻断」条文存在张力 → 建议 schedule 周度 job 单列 dev 审计**报告不阻断**，并把该差异写入 AGENTS §6 执行状态说明（去伪）。
8. **工作区/批次卫生**：未编号的 `contract_sign_date` 修复须归位编号；后续批次一律「一批一提交 + 活账本 BF 登记 + 报告行同步」，避免出现源A 与工作区状态不一致（本次复核出 2 处）。
9. **报告编号治理（ID-2 主动洞察）**：`M-xx` 编号已被 ≥3 份报告复用（`merge-audit-20261029` / `20261031` / 后端提交信息），已出现**跨报告撞号**（后端提交中的 M-09/M-13/M-40 属 1029 报告，与 1031 的 M-09 无关）。建议后续报告统一 `<报告前缀>-<序号>`（本文件已对新条目用 `OP-xx`），活账本 BF 条目作为唯一跨报告主键。
10. **SKILL 建议（§1.7）**：`[SKILL 建议] 封装「行级隔离批量收口核查」` — 触发：新增 `batch_delete_*` / `*_export` 端点后；步骤：① service 签名含 user？② `_delete_one` 调 `ensure_asset_visible`？③ 权限矩阵行一致？④ 补跨部门回归用例；收益：本报告 3 条 P1 全属此类漏网。

---

## §五 证据与可验证性（Fact-2）

- [可验证] M-01 仍开放 — 依据：`asset_service.py:132` 签名直读（无 `user` 参数）+ `asset_view.py:135` 调用实测。
- [可验证] M-03/M-04 已修于工作区 — 依据：`dashboard_selector.py` 窗口过滤实现 + `damaged_asset_view.py:67` 字段名 + `git diff --stat`（6 文件未提交）。
- [可验证] M-05/M-06/M-07/M-08/M-11/M-12 仍开放 — 依据：本次 `rg`/直读（双 toast 并存 :113-114；4 store 缺 `disableAutoMessage`；8 处字面量逐行列出；`helpers.py:54`+`selectors.py:201,236`+`providers.py:37`；`batch_mixins.py:143,216`；`dashboard_selector.py:69`）。（**2026-11-02 续记**：其中 M-05/M-06 已修于工作树，见 BF-172；**M-07/M-08 已修于后端 1cc185f（批次 5，BF-173/A-54），M-07 收敛规模实扩 14 处、M-08 实测 7 处并配 G-8 护栏；M-11/M-12 维持仍开放。**）
- [可验证] 批次 4 已修于工作树（M-05/M-06/OP-13/OP-14/OP-15）— 依据：定向 12 用例先红后绿 + type-check/lint:ci/format:check 全过 + 全量 2431/2431 exit 0 + 护栏双 PASS；`git -C vue-assetmanagement status` 实测 15 文件未提交（含 1 新增集成 spec）；同型家族收编批已提交（前端 `39b7118`，BF-171/B-29）。
- [可验证] 批次 5 已提交（M-07/M-08）— 依据：后端 `1cc185f`（20 文件，四域 pytest 1875 passed / ruff / `mypy . --strict` 0 issues / 触碰面 format 清零）+ 根仓 `cd3e49f`（护栏 G-8 + 自测 22 passed + 真仓 PASS + AGENTS v3.7.4）；预提交钩子 4 护栏全过；CT-7 网络期 CI 直证待补（本地 ruff==mypy 版本与 dev.txt 声明一致无漂移）。
- [可验证] OP-01~OP-03 — 依据：`codegraph node` 直出源码（department_view.py:100/71、selectors.py:188、out_asset_service.py:307、waste_asset_service.py:57）+ `codegraph impact`（2/6/92 符号）。
- [可验证] 覆盖率/护栏 — 依据：源B 本机实跑（pytest 2269 passed / 89.40%；Service 98%；前端 Stores 97.21%；五护栏 exit 0）。
- [可验证] M-18 dev 高危 4 项与生产 0 high — 依据：本次 `npm audit --omit=dev`（7 moderate / 0 high）与全量输出（37 / 4 high，均 dev）。
- [推测] M-01 属遗漏而非设计 — 原因：主资产域无代录白名单，与未登记资产域对照，缺产品口径文档。
- [推测] 工作区 3 处未提交修复来自源A「批次 2」 — 原因：改动内容与批次 2 清单（M-03/M-04）精确吻合，但无提交信息可证；合同导出列字段属额外发现。

---

## §六 审计票（融合报告）

```markdown
[审计票 - 必填项]
- 读取规范：已读 根 AGENTS.md（v3.7.2）+ 双端 AGENTS & Rules + 源A/源B 两报告 + 活账本 BF-165/166/167 关联段
- CT-1[√] CT-3[√ 双源一致·旁路 0 处] CT-5[√ 2269+2420 passed 零失败] CT-7[√ 本地 DRF 3.17.2≠声明 3.18.3 已标注，未用作门禁结论]
- DR-1[~ M-07/M-08 字面量旁路在册待清] DR-5[√ 五护栏实跑 PASS]
- SC-1[√ .env 未入 history] SC-3[√ 全参数化/白名单]
- 跨端契约：未破坏（双源一致）
- 红线触发：无（M-01 落地需 [HALT] 拍板，本次仅报告未改码）
- 建议提交：是（本报告作为融合审查记录与修复执行输入）

[审计票 - 自检项]
- 测试：CT-2[√ 后端 89.40%/Service 98%/前端 Stores 97.21%] CT-4[~ 批次 2 内容断言已随工作区测试补] CT-6[N/A]
- DRY：DR-2[√] DR-3[√] DR-4[~ OP-13/OP-21] DR-6[√]
- 安全：SC-2[√CI] SC-4[√] SC-5/SC-6[N/A 后端无上传面] SC-7[~ dev 4 high 见 §四-7] SC-8[√ CI 权威]
- 可观测性：OC-1~OC-3[√×2 + OP-05 一条待修] OC-4[~豁免] OC-5[~] OC-6[√] OC-7[~豁免]
- AI鲁棒性：AR-1~AR-5[√ 零业务代码生成]
- AI行为：Fact-1[√]（状态复核差异表 §一-1.3 全部实测；[推测] 项已标注）
- 写作风格：Style-1~Style-3[√]
- 覆盖率：后端 89.40%（≥80）/ Service 98%（≥90）/ 前端 Stores 97.21%（≥90）
- 专项结论：状态机旁路 0 处 | 跨端契约 4/4 通过 | SC 分流 SC-1/SC-3 合规·SC-5/6 N/A·SC-7 生产 0 high·SC-8 CI 权威
- 合并完备性：源A 24 条 + 源B 27 条 → 去重后 4 P1 / 19 P2 / 12 P3 / 5 已修 / 5 不采纳，无遗漏 P0-P1
```
