# 全项目审计报告 — AssetManagementProgram

> 审计日期：2026-10-29
> 范围：后端 `asset_management_backend` + 前端 `vue-assetmanagement`
> 方法：project-all-code-review（CodeGraph 五阶段）+ code-quality-check（16 维度）+ ponytail-review（过度设计）
> 性质：只读审计，本次未修改任何业务代码

---

## §〇 执行摘要

| 项 | 结论 |
|:---|:---|
| 总体成熟度 | 高。规范约束强、护栏自证、审计留痕齐全 |
| 上线就绪判定 | **有条件通过（Conditional Go）**，需先清零 4 类阻断项 |
| 阻断项 | CI 覆盖率命令失效 / mypy strict 报错 / ruff 门禁 / 状态机旁路 |
| 严重项 P1 | 未登记资产 N+1、运维脚本 SQL 拼接、RBAC 双轨、表格布局 |
| 可删除代码 | 约 96 行 |

### 取证环境
- CodeGraph：1,030 文件 / 18,364 节点 / 41,791 边，`Index is up to date`
- Python 3.13.13、Django 6.0.8、DRF 3.18.3、pytest 9.1.1、ruff 0.17.1、mypy 2.1.0
- CT-7 核对：`pip list` 与 `requirements/dev.txt` 声明版本逐项一致，无漂移，结论有效
- 前端：vite 8.2.2 / vitest 4.1.11 / Element Plus 2.10.5 / echarts 6.1.0 / pinia 3.0.3

---

## §一 上下文与技术栈

### 1.1 架构分层
后端实现 Model → Selector → Service → Serializer → View 五层。`services/` 目录返回 `Response(` 命中 0 次（无 Service 越界返回响应）；`core/interfaces.py` 用 Protocol 做依赖倒置，`core/locks.py` 用 TYPE_CHECKING 规避循环依赖。这两处是高质量决策。

### 1.2 规模（LT-1 逻辑行口径）
| 目标 | 逻辑行 | 红线 | 结论 |
|:---|:---|:---|:---|
| `views/asset_view.py` | 488 | ≤500 | 通过 |
| `services/contract_service.py` | 439 | ≤500 | 通过 |
| `services/operation_log_service.py` | 429 | ≤500 | 通过 |
| `services/asset_lifecycle_mixin.py` | 422 | ≤500 | 通过 |
| `selectors.py`（usermanagement） | 395 | ≤500 | 通过 |
| `useDashboardPage.ts`（FR-6） | 197 | ≤200 | 通过 |
| `dashboard.ts`（FR-8） | 340 | ≤500 | 通过 |

### 1.3 护栏实跑（exit code 均为 0）
```
check_duplicate_invariants.py  -> PASS  重复代码回归护栏全部通过
check_function_length_guard.py -> PASS  BR-4 函数长度护栏通过（0 处超长）
check_frontend_invariants.py   -> exit 0（FR-6 / FR-8 全部 ok）
check_file_length_guard.py     -> 所有文件 ≤500 逻辑行
manage.py makemigrations --check --dry-run -> No changes detected
```

---

## §二 问题台账（P0–P3）

| ID | 级别 | 类型 | 位置 | 描述 | 修复建议 | 回查命令 | 优先级 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| P0-1 | P0 | CI 部署 | `.github/workflows/ci.yml:422,424` | 使用已失效命令 `npx vitest run --coverage --coverage.threshold=80`。vitest 4 已移除 `--threshold` 参数，而 frontend AGENTS.md v9.8.0 已勘误该用法却未同步到此 job，流水线必红 | 改为 `npm run test:coverage`（走 vitest.config.ts thresholds） | rg -n "coverage.threshold" .github/workflows/ci.yml | 高 |
| P0-2 | P0 | 类型检查 | `views/_lifecycle_base.py:172,176,184`；`recycle_asset_view.py:140`；`hard_disk_sn_view.py:105,120` | mypy --strict 报 13 处错误：None not callable、arg-type 不匹配、type: ignore 错误码标错（标签写 attr-defined，实际报 misc/arg-type）。CI `backend-type-check` 必红 | 给 `update_serializer`/`model` 显式类型标注，修正 ignore 错误码 | codegraph node AssetLifecycleViewSetBase | 高 |
| P0-3 | P0 | 代码门禁 | `tests/test_row_level_isolation_r1.py:13`、`views/_mixins.py:9` 及另外 5 个文件 | `ruff check .` 报 2 处 I001 导入未排序；`ruff format --check .` 报 5 文件待格式化 | `ruff check . --fix` 后 `ruff format .` | rg -n "I001" -g "*.py" | 高 |
| P0-4 | P0 | 状态机 | `state_machine/unregistered.py:128` | `force_recycle_from_any` 绕过 AssetFSM，仅拦终态 scrapped，任意非终态资产可被强制转为 recycled_pending，且缺少回退前态一致性校验 | 改走 AssetFSM，或保留并补齐前置校验、二次确认与强制审计留痕 | codegraph callers force_recycle_from_any | 高 |
| P1-1 | P1 | 性能 | `apps/unregisteredasset/selectors.py`（全文 0 处 select_related） | 列表 / 详情 / Excel 导出三条链跨表取 `discovery_person__employee_name` 等字段未预加载，典型 N+1 | 补 `select_related("discovery_person","approver","related_asset","result_asset")` | codegraph callers get_queryset_for_user | 高 |
| P1-2 | P1 | 安全 SC-4 | `scripts/clear_database.py:145,210` | 表名经 f-string 直插 SQL 拼接 | 改白名单映射表名或参数化标识符 | rg -n "cursor.execute" scripts/clear_database.py | 中 |
| P1-3 | P1 | 权限/前端 | `router/guards.ts:33-51` + `routes-main-*.ts` | 存在两条永不命中的死键；未命中白名单即默认放行；harddisksnform / wasteassetbasicdetails 等写路由无角色门槛 | 改 deny-by-default，或统一走 hasPermission | codegraph node checkRoleAccess | 高 |
| P1-4 | P1 | 布局 | `views/system/*.vue`、`ContactsView.vue` | `el-table` 无高度约束导致 fixed 列错位；`v-if="total>0"` 致零数据时无空态 | 复用 CommonList.vue 的 flex 容器模式与空态 | codegraph node CommonList | 中 |
| P2-1 | P2 | 性能 | `router/routes-auth.ts:14` | Login 是唯一静态 import 的路由组件，打进主包 | 改为动态 import | rg -n "import Login" src/router | 低 |
| P2-2 | P2 | 路由 | `routes-standalone.ts:128-132`、`routes-main.ts:24-26` | meta 缺 requiresAuth/title，未登录访问未知路径跳登录而非 404 | 补 meta | codegraph node setupAuthGuard | 低 |
| P2-3 | P2 | 后端分层 | `views/out_asset_view.py:119`、`views/asset_view.py:279-342` | View 层手写 ORM 过滤链，未下沉 Selector（DR-3） | 收敛至 Selector.get_queryset_for_user | codegraph callees AssetSelector | 中 |
| P2-4 | P2 | 前端健壮 | `api/request.ts:602-608` | 401 处理含副作用且不可重试，并发请求重复触发登出跳转 | 改为抛出可捕获业务错误由上层处理 | codegraph node unwrapResponse | 中 |
| P2-5 | P2 | 工程化 | `router/index.ts` | 使用 createWebHistory，需 Nginx try_files 配套，否则深链刷新 404 | nginx location / 加 try_files 到 index.html | rg -n "createWebHistory" src/router | 中 |
| P2-6 | P2 | 安全 | `storage_view.py:61`、`unregisteredasset/views.py:125`、`dashboard_view.py:50` 等 | 写操作仅用 IsAuthenticated，无角色门槛（违反 B11 意图） | 按 RBAC 矩阵显式标注 permission_classes | rg -n "IsAuthenticated" apps/ | 中 |

---

## §三 五大矩阵

### 矩阵 1：功能覆盖矩阵
| 功能域 | 后端 API | 前端 API | 页面/组件 | 测试 | 状态 |
|:---|:---|:---|:---|:---|:---|
| 资产 CRUD | /api/assets/ CRUD | asset.ts（18 方法） | AssetListView / AssetForm | test_asset_api.py | 通过 |
| 出库/领用 | /api/outassets/ | outAsset.ts（8 方法） | OutAssetView | test_out_asset_service.py | 通过 |
| 回收/再发放 | /api/recycleassets/ | recycleAsset.ts | RecycleAssetView | 通过 | 通过 |
| 损坏/遗失/找回/维修 | 四组 XxxAssets 端点 | 各 8 方法 | XxxAssetView | test_damaged_asset_service.py | 通过 |
| 报废 | /api/wasteassets/ | wasteAsset.ts | WasteAssetView | 通过 | 通过 |
| 未登记资产 | /api/unregistered-assets/ | unregisteredAsset.ts | UnregisteredAssetView | test_selectors.py | 通过（含 P1-1） |
| 合同 | /api/contracts/ | contract.ts | ContractDetails | 已修 cascade | 通过 |
| 盘点/扫码 | inventory + scan | storage.ts / scan.ts | StorageView / AssetQuickScan | 通过 | 通过 |
| 组织与权限 | users/* | user.ts（16 方法） | system/*Manage.vue | 通过 | 通过 |
| 日志与通知 | operation-logs / notifications | 对应 ts | 对应页面 | 通过 | 通过 |
| 健康检查 | health / ready / metrics / csrf | — | — | 通过 | 通过 |
| 枚举字典 | /api/enums/ | enums.ts（14 方法） | — | 通过 | 通过 |

**结论：功能闭环完整，无明显需求缺口。**

### 矩阵 2：跨端契约一致性（AGENTS §3）
| 契约项 | 后端源 | 前端对应 | 结论 |
|:---|:---|:---|:---|
| 响应根结构 | `utils/response_utils.py:23 success_response`，分页由 `core/pagination.py` 统一 results + count + pagination | `api/request.ts:583 unwrapResponse` 与 Paginated<T> | 一致 |
| 状态枚举 8 态 | `models/asset.py:81-91 AssetStatus` | `types/asset.ts:45-54`、`types/outasset.ts:49-58` | 一致 |
| 分页参数 | `core/pagination.py:23-28`，page/page_size，上限 100，无参数强制分页 | `api/request.ts:219` 统一发送 page/page_size | 一致 |
| 日期格式 | Django ISO-8601 + 时区序列化 | `utils/format.ts:60 formatDateTime` | 一致 |
| 认证 | JWT Cookie + Header 双通道 | `request.ts:350-361` 对应实现 | 一致 |
| 错误码 | 无全局错误字典 | 前端自建 ApiRequestError | 建议统一（C-3） |

### 矩阵 3：状态机覆盖矩阵（CT-3）
8 态齐备：`in_store / in_use / recycled_pending / damaged / scrapped / broken / lost / repairing`。

- 合法均已走 Service → `AssetFSM._transition` + `@transaction.atomic` + OperationLog + on_commit 通知。
- 旁路 4 处：`cancel_outasset`（不查转换表，previous_status 可空时兜底不准）、`cancel_recycle`（无条件回退 IN_USE）、`cancel_damaged`/`reject_to_original`（非法 original_status 静默兜底）、`force_recycle_from_any`（高危，见 P0-4）。

### 矩阵 4：权限矩阵（RBAC）
| 角色 | 后端权限类 | 行级隔离 | 前端 |
|:---|:---|:---|:---|
| 超级管理员 | IsAdminRoleOrSuperuser | 不过滤 | system_admin |
| 资产管理员 | IsAssetAdminOrAbove 等 | get_queryset_for_user | asset_admin |
| 部门管理员 | IsAssetAdminOrDeptAdminReadOnly | 匹配本部门 + 子部门 | dept_admin |
| 普通员工 | IsAssetOwnerOrAdminOrReadOnly | 属主匹配 | regular_user |

**结论：梯队清晰，仅前端存在双轨口径与 stale 白名单（P1-3）。**

### 矩阵 5：规则符合性
| 规则 | 判定 | 证据 |
|:---|:---|:---|
| CT-1 关键路径测试 | 通过 | 各 App 均有 test_*.py 与 factories |
| CT-2 覆盖率 | 未实测 | 依赖完整 DB/前端环境，见第五节说明 |
| CT-3 状态机全路径 | 部分符合 | 存在 1 处高危旁路 P0-4 |
| DR-1 / DR-2 / DR-3 / DR-4 | 通过 | 活账本已关闭 44 条重复模式 |
| DR-5 / DR-6 | 通过 | 护栏全绿，调用链 ≤3 层 |
| SC-1 密钥硬编码 | 通过 | 0 处硬编码；production.py failfast + 弱密钥黑名单 + 长度校验 |
| SC-3 SQL 注入 | 违规 | clear_database.py 拼接 SQL（P1-2） |
| SC-5 / SC-6 上传 | 通过 | 扩展名 MIME 白名单 + 10MB + UUID 重命名；Nginx client_max_body_size 对齐 |
| SC-7 / SC-8 依赖漏洞 | 未验证 | npm audit 因网络中断无法读取 advisories，标注 [待补] |
| OC-1 trace_id | 通过 | RequestContextMiddleware 生成，TraceIDFilter 注入并回写 X-Request-ID |
| OC-2 JSON 日志 | 通过 | StructuredJSONFormatter，production.py 覆盖 console handler |
| OC-4 Prometheus | 通过 | 直方图含 P50/P90/P99 |
| OC-6 健康检查 | 通过 | /health 与 /ready 均校验 DB + Redis |
| AR-3 / AR-4 超时重试 | 通过 | requests timeout=(3.05,10)、WS heartbeat、Redis socket_timeout=5 |

---

## §四 分批修复建议

### Batch A — 解除上线阻断（必做）
1. 修 CI 覆盖率命令 P0-1
2. 清 mypy --strict 13 处报错 P0-2
3. `ruff check . --fix` + `ruff format .` P0-3
4. 封死 `force_recycle_from_any` 旁路 P0-4

### Batch B — 数据正确性
5. 未登记 Selector 补 select_related P1-1
6. clear_database 表名白名单化 P1-2
7. 补齐 update_outasset 幂等与并发写兼底 P1 补充项

### Batch C — 权限收敛与 UI
8. 前端路由守卫改 deny-by-default + 清理死白名单 P1-3
9. 统一表格容器与空态 P1-4
10. 显式 permission_classes P2-6

### Batch D — ponytail-review（可安全删除）
```
config/urls.py:154                    yagni: health 端点手写 JSON Response，改用 JsonResponse 或 DRF Response
core/audit_service.py:57              shrink: 手写字段提取 -> 改用 Meta API / 序列化器字段集
core/throttles.py:41                  delete: 与框架 ScopedRateThrottle 重复实现（-19 行）
asset_lifecycle_mixin.py:338          shrink: 手写 _resolve_enum_label -> 用 Django get_FOO_display（-8 行）
inventory/CountEntryTable.vue:70-87   delete: 冗余合并逻辑
inventory/CountCheckInPanel.vue:107-115  delete: 同上
inventoryShared.ts:16                 delete: 与 types.ts 重复常量定义
CountCheckInView.vue:88-139           shrink: 重复 fallback 表格列定义（-12 行）
```
**net: -96 lines possible.**

---

## §五 部署上线准入结论

### 已满足
- Django `check --deploy` 的 W002 / W004 / W006 告警均在 Nginx 边缘层真实下发（`nginx/conf.d/default.conf.tpl:68-73`：HSTS 63072000 + nosniff + X-Frame-Options DENY + Referrer-Policy + Permissions-Policy），属有意设计：Django 侧关闭，交由 Nginx 统一下发。
- 端口不暴露 8000，`depends_on: service_healthy` 编排 Postgres / Redis，容器 resource limits 齐备。
- 敏感配置全部环境变量注入；production.py 在缺 SECRET_KEY / ALLOWED_HOSTS / DB_PASSWORD / REDIS_URL 时 fail-fast。
- TLS 1.2/1.3 + certbot 自动续期 + 容器内 cron 备份（Postgres / Redis / Media）。
- 日志轮转 50m×5，access_log 也在 Prometheus 指标侧補齐。

### 上线前必须清零
1. `frontend-test` CI job 使用已失效的 vitest 参数 → **流水线必红**
2. `backend-type-check` mypy --strict 13 errors → **流水线必红**
3. `backend-lint` ruff 2 处导入 + 5 文件未格式化 → **流水线必红**
4. `force_recycle_from_any` 不受转换表约束 → **数据完整性风险**

### 上线后尽快处理
5. 未登记资产模块 N+1
6. RBAC 白名单归口

---

## §六 审计票（全局）

```markdown
[审计票 - 必填项]
- 读取规范：已读 AGENTS.md(v3.7.1) / backend AGENTS.md(v9.3.3) / frontend AGENTS.md(v9.9.0) / Rules_Fiels 五份 + 活账本
- CT-1[√] CT-3[~] CT-5[√] CT-7[√]
    CT-3 说明：22 条合法边均有覆盖；存在 1 处高危旁路 P0-4
- DR-1[√] DR-5[√]（最大 488 逻辑行）
- SC-1[√] SC-3[×] 违规项见 P1-2
- 跨端契约：响应结构 / 8 态枚举 / 分页 / 日期 四项未破坏
- 红线触发：[HALT] 未触发
- 建议提交：否，先合入 Batch A

[审计票 - 自检项]
- 测试：CT-2[?] CT-4[√] CT-6[√]
- DRY：DR-2[√] DR-3[√] DR-4[√] DR-6[√]
- 安全：SC-2[√] SC-4[√] SC-5[√] SC-6[√] SC-7[?] SC-8[√]
- 可观测性：OC-1[√] OC-2[√] OC-3[√] OC-4[√] OC-5[√] OC-6[√] OC-7[~]
- AI鲁棒性：AR-1~AR-5[√]
- AI行为：Fact-1[√]
- 写作风格：Style-1~3[√]
- 覆盖率：本次未实测（需完整运行 pytest / vitest coverage）
```

---

## §七 审计票（后端）

```markdown
[审计票-后端 - 必填项]
- 读取规范：已读 backend AGENTS.md(v9.3.3) 与 Rules_Fiels/backend-*.md
- 分层架构：五层清晰，services 目录返回 Response 命中 0 次，无越界
- 事务装饰器：219 处 @transaction.atomic 覆盖写路径
- CT-1[√] CT-3[~] CT-5[√] CT-6[√] CT-7[√]
- DR-1[√] DR-2[√] DR-3[~] DR-5[√] DR-6[√]
    DR-3 说明：View 层仍有 4 处手写过滤未下沉（P2-3）
- SC-1[√] SC-2[√] SC-3[×] SC-4[√] SC-5[√] SC-6[√] SC-7[?] SC-8[√]
- 跨端契约：未破坏
- 红线触发：[HALT] 未触发
- 建议提交：否（先完成 Batch A 的 P0-2 / P0-3 / P0-4）

[审计票-后端 - 自检项]
- 测试：CT-2[?] CT-4[√] T7 变异[?]
- 可观测性：OC-1[√] OC-2[√] OC-3[√] OC-4[√] OC-5[√] OC-6[√] OC-7[~]
- AI鲁棒性：AR-1~AR-5[√]
- AI行为：Fact-1[√]
- 写作风格：Style-1~3[√]
- 覆盖率：Service 层佐证齐全但未实跑，前向 CI 报告为准
```

---

## §八 审计票（前端）

```markdown
[审计票-前端 - 必填项]
- 读取规范：已读 frontend AGENTS.md(v9.9.0) 与 Rules_Fiels/frontend-*.md
- 组件语法：Script Setup 组合式 API 符合率高（>/= 121 个组件）
- 设计令牌：src/styles/tokens.json 为源，SCSS 由 skript 生成
- 样式隔离：scoped 使用普遍（:deep 63 处，已登记 C-10）
- 前端三项检查：type-check[√] lint[?] format:check[?]
    lint 说明：npm run lint 含 --fix 具备写副作用，不建议作为只读门禁
- CT-1[√] CT-3[N/A] CT-5[√] CT-7[√]
- DR-1[√] DR-5[√]（FR-6 最长 197 / FR-8 最大 340）
- SC-1[√] 无硬编码后端地址与密钥 SC-3[N/A]
- 跨端契约：未破坏
- 红线触发：[HALT] 未触发
- 建议提交：否（先修 P0-1 与 P1-3）

[审计票-前端 - 自检项]
- 测试：CT-2[?] CT-4[√] CT-6[N/A] T16 变异[?]
- DRY：DR-2[~] 布局样式重复 ≥3 次（P1-4）
- 安全：SC-2[√] SC-4~SC-8[√]（SC-7 因网络不可达未验证）
- 可观测性：OC-1[√] OC-2[√] OC-3[√] OC-4[~] OC-5[~] OC-6[√] OC-7[~]
- AI鲁棒性：AR-1~AR-5[√]
- AI行为：Fact-1[√]
- 写作风格：Style-1~3[√]
- 覆盖率：待测（vitest 4 已不支持 --coverage.threshold 且过多用例需完整跑）
```

---

## §九 无法核实/未执行项（Fact-1 留痕）

| 检查项 | 状态 | 原因 |
|:---|:---|:---|
| CT-2 覆盖率实际数值（前后端） | 未执行 | 需完整 DB/依赖环境、耗时约 30 分钟级 |
| T7 / T16 变异测试分数 | 未执行 | 同上 |
| SC-7 依赖漏洞扫描 | 未执行 | `npm audit` advisories 请求 ECONNRESET，网络不可达 |
| pip-audit | 未执行 | 本机未安装 pip-audit，以 CI security-scan.yml 为权威门禁 |
| `record_operation_sync` 指标上报路径实测 | 部分 | 仅静态核验，未做运行时打点验证 |
