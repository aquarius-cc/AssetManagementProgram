---
title: 上线前全项目综合审核报告（结构/架构/框架/逻辑/调用/函数/代码）
date: 2026-11-16
mode: 纯审计（只读，不执行修复）
sources:
  - CodeGraph 索引（codegraph status/sync，1142 文件 / 19645 节点 / 130105 边）
  - 六路分域诊断（状态机 / 安全权限事务审计 / 前端架构 / 跨端契约 / 可观测性+AI鲁棒性 / 测试门禁）
  - 非图谱工具链实测（rg 密钥与 SQL 扫描、护栏脚本、pytest --cov、vitest）
  - 前序台账现状核验：docs/Review/merge-audit-112.md（M-01~M-21）
status: 融合成文 / 台账终态「待修」/ 不执行修复
---

# 上线前全项目综合审核报告（MiMo-codegraph-audit-2026-11-16）

> 本报告由 project-all-code-review（审计工作流）+ code-quality-check（16 维度框架）+ code-reviewer（置信度 ≥80 过滤）+ ponytail（最小化建议）四规程合成。全程只读，未改动任何业务代码。

## 一、项目上下文

### 1.1 技术栈与模块边界

| 端 | 技术栈 | 模块边界 |
|:--|:--|:--|
| 后端 | Python 3.13 / Django 6.0.6 + DRF / SimpleJWT / django-filter / drf-spectacular / Channels 4 / psycopg(3) / Redis / Celery | `asset_management_backend/`：`apps/`（assetmanagement、authusermanagement、usermanagement、unregisteredasset、notification）+ `core/`（metrics/auth/permissions/logging/health）+ `utils/` + `config/` |
| 前端 | Vue 3.5 / TS 6 / Vite / Pinia（Setup Store）/ Element Plus / Vue Router / ECharts / Axios | `vue-assetmanagement/src/`：views、components、composables、stores、router、api、utils、types、styles |
| 基础设施 | Docker Compose（Gunicorn+Nginx / PostgreSQL / Redis / Prometheus / Alertmanager / Loki+Promtail） | `asset_management_backend/docker/`、`docker-compose*.yml` |
| 测试 | pytest(+django_db,+cov) 2442+；Vitest(+coverage-v8)；mutmut 变异基线 | `tests/`、`src/__tests__/`、`scripts/tests/` |

### 1.2 分域清单与诊断方式

| 分域 | 诊断方式 | 结论来源 |
|:--|:--|:--|
| 资产/合同状态机（CT-3） | CodeGraph 定位 + 规则表逐条比对 + 测试覆盖盘点 | §2.2 |
| RBAC/行级隔离/事务/审计/并发 | 源码语义判定 + 权限矩阵比对 | §2.2 |
| 前端架构与规范（F1-F15/FR-1~FR-8） | grep 规则扫描 + 批次 4 护栏断言核验 | §2.1/§2.2 |
| 跨端契约 4 项 + API 路径匹配（§3/B1/OS-8） | 双端源码核对 + 路径清单比对 | §2.2 |
| 可观测性（OC-1~OC-7）+ AI 鲁棒性（AR-1~AR-5） | 日志/配置源码核对 + 标注残留扫描 | §2.3 |
| 测试与质量门禁（CT-2/CT-7/DR-5/DR-6） | 护栏脚本 + type-check/lint + 覆盖率实测 | §2.4 |
| 安全红线（SC-1~SC-8） | rg 密钥扫描 + SQL 扫描 + CI 权威门禁引用 | §2.3 |

### 1.3 前序台账现状核验（merge-audit-112，M-01~M-21）

> 依据项目经验教训「批次表与仓库实际状态存在系统性偏差，执行前必须先做现状核验」，本次对昨日融合台账逐项复核（抽测直证 + 护栏断言 + git log 落账记录）。

| 台账段 | 条目 | merge-audit-112 状态 | 本次核验（2026-11-16） |
|:--|:--|:--|:--|
| 后端可观测性 | M-01 / M-02 / M-03 / M-04 | ✅ 已修复（批次 2） | 维持已修复（health_probe 唯一收口、审计降级渠道接线，git log `dfcb78c` 落账） |
| 安全部署 | M-05 | ✅ 仓内已落地 | 维持；**部署六步仍待生产环境执行**（[推测] 3 项待部署期事实化） |
| 设计令牌 | M-06 / M-07 | 已修 / 已关闭 | 维持（`dadb8e6` BF-193+设计签字落账） |
| 前端速修 | M-09 / M-10 / M-12 | 已修（批次 1） | 维持（B-30/B-37/B-33 关闭留痕） |
| CI 门禁 | M-21 | ✅ 已关闭（2026-11-15） | 维持（PR #2 红绿直证） |
| 前端 DRY | M-08 / M-11 / M-13 / M-14 / M-15 / M-16 | 待修 | **本次核验已全部收敛**（批次 4 落地）：`batch4DryInvariants.spec.ts` 11 断言在场（A1-A11 覆盖六项），`interface SearchForm` 组件侧归零（仅护栏夹具命中）、`export interface` 组件侧 0 命中、`resetAppState` 走 `setTheme/setPrimaryColor` 通路（app.ts:119-127）、`:deep(.el-input__wrapper)` 仅余 LogIn.vue（登记豁免）+ CommonListActions.vue:285 单点（无重复面，非 DR-2） |
| 文档/注释/治理 | M-17 / M-18 / M-19 / M-20 | 待修（P3） | **仍待修**：M-18 `config/urls.py:50` 仍返回 `"admin": "/admin/"`（直证）；M-20 `.stryker-tmp/sandbox-*` ×6 与 `everything-claude-code/` 仍在（直证）；M-17/M-19 文档注释漂移未销项 |

**核验结论**：昨日 21 条待修项中 **17 条已闭环**，存量余留 **4 条 P3**（M-17/M-18/M-19/M-20），无 P2 及以上存量缺口。

---

## 二、问题台账（N-01 ~ N-12，本次新发现）

> 编号 N-xx 为本次新发现（与 merge-audit-112 的 M-xx 不重号）；仅收录置信度 ≥80 的确认问题，推测项单列并标 [推测]。级别：P0 阻断/高危、P1 重要、P2 一般缺陷、P3 优化建议。本次新发现 **P0/P1 = 0**。

### 2.1 主表

| ID | 级别 | 类型 | file:line | symbol | 描述与证据 | 修复建议 | 影响面 / 建议验证方式 | 回查命令 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| N-01 | P2 | 前端交互 / DR-1 | `vue-assetmanagement/src/stores/dashboard.ts:198,222,245,272,296,316,337,357` | fetchOverview 等 8 个 catch | 8 处内联重复 `logError + if(!isApiError(error)) ElMessage.error(...)`，与 `utils/errorHandler.ts` 的 `notifyCallerError` 语义同构，DR-1 同一错误处理逻辑双实现 | 8 处统一改调 `notifyCallerError(error, fallback)` | 单文件调用点收敛，不动公共函数行为，回归面小 | `rg "isApiError\(error\)" src/stores/dashboard.ts` 归零 + vitest |
| N-02 | P2 | 前端交互 / DR-2 | `AssetTypeDetails.vue:402,438`、`ContractDetails.vue:203,213,228,254`、`StorageDetails.vue:222`、`RecycleAssetDetails.vue:255`、`HardDiskSNDetails.vue:290`、`RolePermDialog.vue:212,228`、`UserRoleAssignDialog.vue:113,155,190,233`、`BindAuthUserDialog.vue:138,182`、`useDepartmentEmployeeActions.ts:123`、`UserBatchImport.vue:301` | 各 delete/save catch | 13 文件手写 `ElMessage.error('删除失败，请重试'…)` 硬编码且重复（DR-2 同文案 2+ 处）、缺 `logError`；同文件内与 `notifyCallerError` 用法并存（AssetTypeDetails.vue:463）不一致。系 B-30 同型残留面（批次 1 仅收编 RoleManage） | 收敛至 `logError + notifyCallerError`，文案走 fallback 参数 | 跨 13 文件但均为机械替换；建议同批一次清干净（零 Bug 收口，防同型回潮） | `rg "删除失败，请重试"` 归零 + vitest + 删除/保存冒烟 |
| N-03 | P2 | 前端交互 / 时区正确性 | `vue-assetmanagement/src/composables/useDashboardPage.ts:150-160` | updateTime | `toLocaleTimeString/toLocaleDateString` 按浏览器时区渲染当前时刻，违反业务日期格式工具单源约定（Format.ts `toBusinessDateTimeParts`），非沪时区浏览器显示漂移 | 改走 `toBusinessDateTimeParts(new Date())` | 单 composable，消费方仅 `DashboardPage.vue` + 自身 spec（codegraph callers 直证）；**建议上线前修复**（唯一影响运行时正确性的新发现） | fake 时区测试断言渲染值 + `rg "toLocale(Time|Date)String" src/composables` 归零 |
| N-04 | P3 | 数据一致性 / DR-1 | `stores/notificationStore.ts:32`、`stores/auditLogStore.ts:24`、`stores/app.ts:35`、`createEntityStore.ts:119` | pagination.pageSize | 手写 `page_size/pageSize: 20` 字面量，未引 `utils/pagination.ts` 的 `DEFAULT_PAGE_SIZE`（FR-4 单源约定） | 引用 `DEFAULT_PAGE_SIZE` | 机械替换 4 处 | `rg "page_size: 20\|pageSize: 20" src/stores src/composables` 归零 |
| N-05 | P3 | 代码质量 / DR-4 | `componentsdetails/detils/ContractPaymentRecord.vue:212-216`、`stores/dashboard.ts:403-417` | formatPrice / formatNumber+formatCurrency | 组件/Store 内手写数值格式化，`Format.ts:501-502` 已有同名 `formatPrice/formatNumber` 导出（数值精度处理必须在 utils） | 复用 Format.ts 导出，删除本地副本 | 机械替换 | `rg "const formatPrice\|const formatNumber" src/components src/stores` 归零 |
| N-06 | P3 | 前端交互 | `useNotification.ts:175`、`useNotificationConnection.ts:57` | fetchUnreadCount / getJobcode | 裸 catch 仅 `// ignore`，未读数拉取失败无痕（可观测性缺口） | 至少补 `logError`（`:120` 的 WS parse 容错可保留） | 单文件 | vitest + 断言 logError 调用 |
| N-07 | P3[推测] | 接口契约 / B1 | `asset_management_backend/config/urls.py:41,71,98` | api_root / health_check / ready_check | `JsonResponse` 裸返回绕过 `response_utils` 信封（B1 无豁免条款文本）；三者为运维/探针端点，疑为刻意豁免但**未见豁免登记** | 二选一：按 §5.2 登记豁免口径，或补信封；与 M-18（同文件 `"admin"` 键）合并处置 | 运维端点，无业务消费方解析信封，回归面极小 | `curl /health/` 响应体断言 + 护栏核对 |
| N-08 | P3 | AI 鲁棒性 / AR-2 | `vue-assetmanagement/vite.config.ts:17` | vite proxy 过滤判据 | `# AI_REVIEW_NEEDED` 标注残留（活账本 `:6064` 已登记「待人工复查后移除」未销项），上线前 AR-2 标注应清零 | 人工复核过滤判据后删标注留痕 | 构建配置，无运行时影响 | `rg "AI_REVIEW_NEEDED" --glob '!docs/**'` 归零 |
| N-09 | P2 | 测试规范 / T2 | `asset_management_backend/apps/*/tests/conftest.py` 等 | 测试造数 | factory-boy 3.3.3 已在 `requirements/dev.txt/test.txt` 声明但**全库零使用**，测试数据全用 `Model.objects.create` 原始造数，违反 backend-testing-rules T2「强制 factory_boy」 | 二选一（需拍板）：① 补 `tests/factories.py` 渐进迁移；② 按 §5.2 审批修订 T2 条文与依赖声明对齐 | 规范债务，不影响运行时；CT-4 含义下越晚越贵 | `rg "factory_boy\|Factory"` 全库命中计数 |
| N-10 | P3 | 测试规范 / 文档 | `vue-assetmanagement/src/**/__tests__/`（273 个 spec） | 测试目录口径 | 条文字面仅认可「同目录或统一 `src/__tests__/`」，实际 273/274 spec 用「就近 `__tests__` 子目录」组织——实践与条文口径不一致 | frontend-testing-rules T9 条文补认「就近 `__tests__` 子目录」口径 | 零代码，文档修订 | 人工复核条文 |
| N-11 | P3 | 测试门禁 | `vue-assetmanagement/vitest.config.ts:60-63` | .vue 棘轮 | .vue 棘轮余量极薄：实测 funcs 27.03 vs 阈值 27.0（余 0.03pt），微小波动即击穿门禁 | 组件补测后按 T14 绑定上移棘轮值 | 门禁余量管理 | `npm run test:coverage` 分层汇总核对 |
| N-12 | P3[推测] | 权限安全 / 文档口径 | `apps/authusermanagement/views.py:66-70,79-86` | AuthUserViewSet | update/destroy 为「IsAuthenticated+本人/管理员」，与 §4.2「用户管理 system_admin 专有」措辞有张力；但敏感字段 read_only、RegisterSerializer 强制 `auth_is_staff=False`，**无实际提权面** | 由产品确认「本人自助改资料」是否为有意设计；若是，在 §4.2 矩阵补注例外 | 仅文档澄清，不动代码 | 人工复核 §4.2 |

### 2.2 存量待修项（沿用 merge-audit-112 编号，本次核验仍在）

| ID | 级别 | 描述 | 核验依据 |
|:--|:--|:--|:--|
| M-17 | P3 | 过程文档漂移（spec/tasks/TECHNICAL_DEBT/设计审计核验统计） | 未销项 |
| M-18 | P3 | `config/urls.py:50` `"admin": "/admin/"` 与注释矛盾 | 本次 rg 直证仍在 |
| M-19 | P3 | MainView.vue 样式注释与移动端实现漂移 | 未销项 |
| M-20 | P3 | `.stryker-tmp/sandbox-*` ×6 + `everything-claude-code/` 本地残留 | 本次 Test-Path 直证仍在 |

### 2.3 需人工确认（[推测]，不入台账）

| 项 | 描述 | 待确认点 |
|:--|:--|:--|
| N-07 | 三运维端点 JsonResponse 旁路 | 是否经审批豁免；无登记则按 B1 补信封或登记例外 |
| N-12 | AuthUser 自助更新权限 | 产品口径确认后 §4.2 补注 |
| — | `DashboardWelcomeBar.vue:52` 问候语按浏览器小时取早/午/晚 | 纯 UI 语义，时区漂移可否接受 |

### 2.4 分域合规结论（全绿面留档）

- **状态机（CT-3）**：`VALID_TRANSITIONS` 与规则 §3 逐条一致（含 `("repair_failed","to_damaged")` 双入口共边与 reject/cancel 多目标回退+兜底）；FSM 直写旁路 0（`unregistered.py:56/89/128`、`scrapping.py:80/131`、`out_recycle.py:74/109`、`seed_grouped_assets.py:218` 均为文档登记豁免）；合同状态机三处同步无漂移；`test_state_machine.py` 全路径覆盖（含 scrapped 终态全阻断、双入口共边用例）。
- **安全/权限/事务/审计**：写端点全经 `resolve_viewset_permissions`（fail-closed）；行级隔离三域（Employee 八端点 / unregistered §4.5 / operation_log §4.1）全收窄；状态变更全 `@transaction.atomic` + `send_notification_on_commit`；审计留痕全覆盖；并发 `select_for_update` + `lock_row_or_409` + 锁内 `ensure_asset_visible`；SC-5/6 N/A（全仓无文件上传端点）。
- **跨端契约 4 项**：响应根结构（业务 View 全信封、`apps/**` 零 JsonResponse 旁路）、状态枚举 8 键双端一致（`OutAssetCurrentStatus` 别名收敛）、分页 `page/page_size` 一致且 ≤ max 100、日期 ISO8601+08:00 与 `toBusinessDateTimeParts` 一致（零直接渲染点）。
- **API 路径匹配**：23 个前端 API 文件与后端路由逐一比对，双向零缺失；`batch-save` 历史错配已消除；`api-schema-baseline.json` 存在且被 `check_api_doc_consistency.py` 引用为权威源。
- **可观测性**：OC-1 trace_id 全链路（RequestContextMiddleware + TraceIDFilter）；OC-2 StructuredJSONFormatter 五字段（file handler 权威载体，§5.1 登记口径）；OC-3 敏感明文日志零命中；OC-6 `/health//ready/` 在册；OC-4/5/7 按 QPS<10 维持 `[~]` 豁免。
- **AI 鲁棒性**：AR-3/AR-4 超时重试配置化（health_probe `HEALTH_REDIS_*`、feishu-webhook `ADAPTER_*` 环境变量）；后端零裸 `requests.*`；AR-2 残留仅 N-08 一处。
- **代码质量门禁（本地实测、非 CI 基线）**：后端 2455 passed / 整体 90.51%（≥80）；前端 2711 用例全过 / ts 94.00%（≥80）/ stores 96.82%（≥90）/ .vue 棘轮通过（余量 0.03pt 见 N-11）；type-check / lint:ci / format:check 全 0 错误；五护栏（行数/函数长度/重复不变量/CI 编排/前端不变量）全 PASS；mutmut 基线 83.2567（双重门禁满足，未重跑）。

---

## 三、分域结论与修复建议（按优先级排序）

### 3.1 总体结论：**有条件上线**

- **P0/P1 = 0**，核心面（状态机、鉴权、行级隔离、事务、审计、并发、跨端契约、API 路径）全绿，具备上线基础。
- **上线前建议修复**：N-03（时区渲染漂移，唯一影响运行时正确性的新发现，回归面单 composable）。
- **部署期必做**：M-05 部署六步（METRICS_TOKEN fail-closed 断言 + Bearer 抓取核对）在生产环境执行并留痕。
- **不阻断、排期治理**：N-01/N-02（错误处理收编，同型一次清干净）→ N-04/N-05/N-06（DR 小收敛）→ N-07+N-18（config/urls.py 合并处置）→ N-08/N-10/N-12（标注与文档口径）→ M-17/M-19/M-20（文档与本地清理）。
- **需拍板**：N-09（factory-boy：整改或修 T2 条文，二选一）；N-11（.vue 棘轮随下次组件补测绑定上移）。

### 3.2 批次建议

| 批次 | 内容 | 性质 | 回归门槛 |
|:--|:--|:--|:--|
| 上线前速修 | N-03 | 运行时正确性 | fake 时区用例 + vitest |
| 治理批 A（错误处理收编） | N-01 + N-02 | DR-1/DR-2 一次清干净 | `rg` 归零断言 + vitest + 冒烟 |
| 治理批 B（DR 小收敛） | N-04 + N-05 + N-06 | 机械替换 | `rg` 归零 + vitest |
| 治理批 C（契约与文档） | N-07 + M-18 + N-08 + N-10 + N-12 + M-17 + M-19 | 零/低代码 | 人工复核 |
| 本地清理 | M-20 | 治理 | `git status --ignored` |
| 拍板项 | N-09、N-11 | 规范/门禁 | 拍板后定 |

### 3.3 质量自审（阶段 5）

- [x] 台账完整性：N-01~N-12 均含 级别/类型/file:line/symbol/描述/建议/影响面/验证方式；
- [x] 证据可回查：每条附回查命令或源码行号；[推测] 项单列；
- [x] 置信度过滤：仅收录 ≥80 确认问题；拦截器 code 处理疑点经复核有 `unwrapResponse` 兜底，判非缺陷不入账；
- [x] 只读纪律：本次会话未改动任何业务代码（仅产出本报告）；
- [x] 覆盖率数字均标注「本地实测、非 CI 基线」，权威口径归 CI `$GITHUB_STEP_SUMMARY`（CT-7 / M-21 纪律）。
