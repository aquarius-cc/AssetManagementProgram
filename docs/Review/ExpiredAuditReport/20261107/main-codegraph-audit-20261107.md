# 全项目架构 / 逻辑 / 流程 / 调用链 / 代码质量审计报告（CodeGraph 增强）

> 审计日期：2026-11-07
> 交付模式：纯审计（只读）。本次会话未改动任何业务代码，唯一落盘产物为本报告。
> 触发：用户 `/project-all-code-review` + `/code-reviewer` + `/code-quality-check`，要求覆盖架构、框架、逻辑、流程、函数调用、代码质量。
> 规范基线：根 `AGENTS.md` v3.7.5、前后端子引擎 `AGENTS.md`、`Rules_Fiels/` 四份业务与测试细则。
> 报告格式：§一 项目上下文 / §二 问题台账 / §三 分域结论与修复建议 / §评审结论。

---

## §一 项目上下文

### 1.1 图谱与工具口径

| 项 | 事实 |
|:--|:--|
| 工具 | CodeGraph CLI 1.6.2（MCP 图谱服务本次报 `unable to open database file`，已降级为同一套 CLI 命令取证，能力边界未扩展） |
| 索引 | `codegraph init .` 返回「已初始化」；`codegraph status` 显示 1,049 文件 / 18,739 节点 / 42,828 边 / Python 502 + TS 403 + Vue 121；`codegraph sync` 增量刷新 46 文件（+15 / ~30 / −1，992 节点）后进入诊断 |
| 覆盖面 | `codegraph files --filter "asset_management_backend"` = 494 文件；`--filter "vue-assetmanagement/src"` = 524 文件；5 条 workflow `.yml` 在索引内（0 symbols，用文件模式读行号） |
| 分工 | 图谱只提供符号、调用边、影响面；语义诊断由角色读源码判断；密钥/依赖/覆盖率/静态检查分别用 `rg`、`pip-audit`/`npm audit`、`pytest`/`vitest`、`ruff`/`mypy`/`eslint` |
| 探索分派 | 3 个 `code-explorer` 子代理并行覆盖后端架构、前端架构、CI/安全/规范；架构师与评审师角色因 worker 不可用，由主代理分阶段自任（技能 §3 降级路径） |

### 1.2 技术栈与模块边界

- 后端：Django 6.0 + DRF 3.16 + PostgreSQL 16 + SimpleJWT + drf-spectacular。五个业务 app：`assetmanagement`（资产核心）、`authusermanagement`、`usermanagement`、`notification`、`unregisteredasset`；`core/`（权限、批量骨架、审计、信封 schema）、`utils/`、`config/`（settings/urls/health）。
- 前端：Vue 3.5 + TypeScript + Vite + Pinia + Element Plus。`src/api`（请求与端点）、`stores`（含 `createEntityStore` 工厂 + 32 个 store 文件）、`composables`（55 个 `use*.ts`）、`components`（121 个 `.vue`）、`views`、`router/guards.ts`、`utils`。
- 分层约定：Model → Selector → Service → Serializer → View；响应统一 `{code, message, data}`；`AssetFSM` 只改状态字段，事务/锁/审计由 Service 承担。

### 1.3 关键图谱锚点

| 分域 | 锚点 |
|:--|:--|
| 资产状态机 | `state_machine/constants.py:27` `AssetState`；`transitions.py:32-85` `VALID_TRANSITIONS`（8 态 / 20+ 边）；`core.py:31` `AssetFSM`、`core.py:96` `_transition`；4 个 Mixin |
| 合同状态机 | `contract_fsm.py:31` `_CONTRACT_TRANSITIONS`（8 态单向链、终态空集）、`:57` `ContractFSM`、`:82` `allowed_next_states` |
| 响应契约 | `utils/response_utils.py:23` `success_response`（175 callers）、`:37` `error_response`（100 callers）、`core/mixins.py:79` `ResponseWrapperMixin`（18 继承类） |
| 批量骨架 | `core/batch_mixins.py:167` `batch_delete_execute`、`:375` `BatchDeleteViewMixin`（影响面 246 符号） |
| 前端契约 | `api/request.ts:647-653` `unwrapResponse`；`types/asset.ts:47-56` `AssetCurrentStatus`；`stores/createEntityStore.ts:68` |
| 测试锚 | `apps/assetmanagement/tests/test_state_machine.py`（CT-3 全边）、`core/tests/test_batch_delete_view_mixin.py`、`scripts/tests/`（6 文件 / 55 用例） |

### 1.4 门禁实测矩阵（本次会话真实执行）

| 命令 | 结果 |
|:--|:--|
| `python scripts/check_file_length_guard.py --print` | 最大 `apps/assetmanagement/views/asset_view.py` = **484 逻辑行**（≤500），全部未超限 |
| `python scripts/check_function_length_guard.py` | `[PASS] BR-4 函数长度护栏通过(0 处超长函数)` |
| `python scripts/check_frontend_invariants.py --print` | 全部 `ok`；FR-6 最大 `usePaginationSearch.ts` = **199**（≤200），FR-8 最大 `createEntityStore.ts` = **407**（≤500） |
| `python scripts/check_duplicate_invariants.py` | `[RESULT] PASS: 重复代码回归护栏全部通过` |
| `python scripts/check_ci_orchestration.py` | `[PASS] CI 汇总 needs 已覆盖全部 job，CD 监听名一致` |
| `python -m ruff check . --statistics` | 无违规输出，exit 0（本地 ruff 0.17.1 = `dev.txt` 声明） |
| `python -m mypy . --strict` | `Success: no issues found in 230 source files`（mypy 2.1.0 = 声明版本） |
| `npx vue-tsc --build --noEmit` | 无输出，exit 0 |
| `npx eslint .` | 无输出，exit 0（eslint 10.14.0，在 `package.json` 声明范围内） |
| `python -m pytest --cov=. --cov-fail-under=80 -q` | **319 passed / 2079 errors / 1062.50s**；单用例诊断根因 `psycopg.errors.DuplicateDatabase: test_asset_management_backend 已存在`（setup 阶段创建测试库失败）。属本地环境残留，非代码缺陷；**本次未取得后端覆盖率与全绿结论** |
| `npm run test:coverage` | **197 文件 / 2542 用例全绿 / 64.65s**；覆盖率表格生成，但 V8 `cleanAfterRun` 被宿主安全策略拦截（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`），**最终阈值判定 exit 结论未取得**；`coverage/coverage-final.json`（3.25 MB）已落盘 |
| 覆盖率明细估算（非阈值判定口径） | 基于 `coverage-final.json` 的 V8 `statementMap` 命中数：295 文件；`*.ts` 语句 **93.73%**（4,863）、`stores` **96.83%**（1,168）、`*.vue` **21.19%**（7,840）。此数为命中率估算，不等同 vitest 的 statements/branches/functions/lines 四项阈值判定 |
| CT-7 版本核对 | 本地 pytest 9.1.1 / pytest-cov 7.1.0 / ruff 0.17.1 / mypy 2.1.0 与 `requirements/dev.txt` 精确一致；前端 eslint 10.14.0 / prettier 3.8.3 / vitest 4.1.11 / vue-tsc 3.2.8 均落在 `package.json` caret 范围内（非精确钉版） |

### 1.5 §5 专项维度结论

| 维度 | 结论 | 主要证据 |
|:--|:--|:--|
| CT-3 状态机全路径 | **FSM 层全边覆盖已确认**；Service 层逐边集成覆盖未逐条核对 | `codegraph node VALID_TRANSITIONS`（8 态表）；`test_state_machine.py` 参数化覆盖 `damaged→5 种原状态`（`:27-41`、`:64-78`）、`(in_store\|recycled_pending)→in_use`（`:248`）、`repairing→damaged` 双入口（`:318`、`:442`）、终态 8 条阻断用例（`:184-222`）；`codegraph callers _transition` = 13 个 FSM 具名方法 |
| 状态机旁路 | 未发现未登记旁路；例外均已写入规范 §三 | `codegraph node core.py:112` 为唯一 `_transition` 写点；S1 裸 create（`unregisteredasset/handlers.py:78`）、cancel/reject 回退（`out_recycle.py:74,109`、`scrapping.py:80,131`）属规范登记例外；`objects.update/bulk_update` 直改状态零命中 |
| 跨端契约 ① 响应根结构 | 通过 | `success_response`/`error_response` 为唯一包装入口；前端 `unwrapResponse` 按 `code!==0` 抛错；`api/auth.ts:37-48`、`utils/tokenRefresh.ts` 自判 code 属语义等价旁路；无二次解包 |
| 跨端契约 ② 状态枚举 | 通过 | 后端 `AssetState` 8 键 ↔ 前端 `types/asset.ts:47-56` 8 键逐字一致；`types/outasset.ts` 为 re-export，无第二真值源 |
| 跨端契约 ③ 分页参数 | 通过 | `page` / `page_size` 前后端一致；`pageSize`（`types/common.ts:170`）仅为组件内部 `Ref`，出参经显式转换 |
| 跨端契约 ④ 日期时间 | 序列化格式通过；显示层存在时区风险（见 P2-09，标 `[推测]`） | 后端 `base.py:166,168` `TIME_ZONE=Asia/Shanghai` / `USE_TZ=True`；前端 `utils/Format.ts:46-100` 用 `new Date()` + 本地 `getFullYear/getHours` |
| SC-1 密钥 | 生产代码零命中 | 对 `apps/core/config` 与 `src` 的 `.py/.ts/.vue` 排除 tests 后扫描无命中；workflow 内明文为轮换凭据黑名单与 CI 占位（见 N-03、P2-05） |
| SC-3 / SC-4 | 通过 | `config/urls.py:70,117` 仅 `cursor.execute("SELECT 1")` 常量；`scripts/clear_database.py:134-147` 表名白名单 + `psycopg.sql.Identifier` 双闸 |
| SC-5 / SC-6 上传 | 不适用 | 后端 `request.FILES`/`MultiPartParser`/`FileField`/`upload_to` 扫描零命中；Excel 批量导入在浏览器解析后以 JSON 提交 |
| OC-6 健康端点 | 通过 | `config/urls.py:152-153` 注册 `/health`、`/ready`；实现 `:54-143`（DB+Redis，异常返回 503） |
| DR-5 / FR-6 / FR-8 规模 | 全绿（护栏 `--print` 为权威口径，LT-1~LT-3） | 见 1.4；注意子代理按物理行粗估的「536 行 Store 超限」不成立，权威逻辑行 407 |
| DR-6 / BR-7 调用链 | 部分链路超深（P1-04） | `codegraph callees batch_delete`、`codegraph impact BatchDeleteViewMixin`（246 符号） |

---

## §二 问题台账

> 状态口径：本次为纯审计，**不产生「已修复」**。所有建议项状态为「待修」；误报项状态为「不采纳」并给理由。
> 回查命令列：代码类用 `codegraph node <symbol>` / `codegraph callers <symbol>`；CI 配置类因 yml 在索引中为 0 symbols，补 `codegraph node -f <file>`（文件模式，真实能力）与 `rg` 行号定位。

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 |
|:--|:--|:--|:--|:--|:--|:--|:--|
| P1-01 | P1 | CI 门禁闭合 | `.github/workflows/ci-cd.yml:40-43,112-157`；`ci.yml:513-528`；`duplicate-guard.yml:40-46`；`migration-check.yml:1` | `audit_listener`（`scripts/check_ci_orchestration.py:123`） | 部署 gate 仅监听 `CI Pipeline` 并按 SHA 回查 `Dependency Security Scan`；`duplicate-guard.yml`（护栏汇总）与 `migration-check.yml` 是独立 workflow，其失败不阻断部署 | 把两条 workflow 的汇总结论纳入 gate 回查（复用 `:112-157` 的轮询 + fail-closed），或落地 required checks | `codegraph node audit_listener`；`codegraph node -f .github/workflows/ci-cd.yml` |
| P1-02 | P1 | 护栏假绿 | `scripts/check_duplicate_invariants.py:40-46,116-123`；对照 `scripts/line_metrics.py:44-57` | `read_text` / `_iter_ast_trees` | 重复护栏 `read_text` 仅 `utf-8/gbk`，缺 `utf-8-sig`；带 BOM 的 `.py` 会触发 `ast.parse` SyntaxError 被静默跳过，G-1~G-3、G-5~G-8 全部可被绕过（`line_metrics.py` 已修同类缺陷） | 改为复用 `line_metrics.read_text`（DR-1/LT-1），并补 BOM 证红自测 | `codegraph callers read_text`；`codegraph node _iter_ast_trees` |
| P1-03 | P1 | 分层 / DRY | `apps/assetmanagement/views/waste_asset_view.py:69`；同类见 `storage_view.py:59,88`、`contract_view.py:63,116`、`asset_type_view.py:39`、`recycle_asset_view.py:51,115,117`、`damaged_asset_view.py:53,108`、`out_asset_view.py:54,105`、`asset_view.py:393,403,440` | `WasteAssetViewSet` | ViewSet 类属性直接拼写 `Model.objects.filter(...)`，绕过 Selector 的 `get_queryset_for_user`，与 BR-1/B12 的单一查询入口约定不一致；批量面广（十余处） | 按域分批把 `queryset` 改为 `get_queryset()` 委托对应 Selector，先以低风险字典域试点 | `codegraph node WasteAssetViewSet`；`codegraph callers get_queryset` |
| P1-04 | P1 | 调用链深度 | `core/batch_mixins.py:402` → `services/asset_service.py:316,339` → `_delete_one` → `AssetSelector` → `audit.py:159` | `batch_delete` / `batch_delete_execute` | 资产批量删除链 ≥6 层，同时超 BR-7（≤3）与 DR-6（≤5）；出库/回收/报废审批链亦为 4~5 层 | 把逐条校验、Selector 查询与审计编排合并进单一 Service 事务方法，扁平为 View→Service→Selector | `codegraph callees batch_delete`；`codegraph impact BatchDeleteViewMixin` |
| P1-05 | P1 | 测试覆盖 / 回归屏障 | `vue-assetmanagement/vitest.config.ts:54-59`；`coverage/coverage-final.json` | `createEntityStore` | `.vue` 层语句命中率估算 21.19%，而棘轮阈值 21.1，余量仅 0.09pt；`NotificationList.vue`、`RepairDoneView.vue`、`RepairFailedView.vue` 等多页 0% 覆盖，CT-4 回归面薄弱 | 先补 0% 页面挂载与交互测试，再按 T14「只升不降」手工上移 `.vue` 阈值块 | `codegraph node createEntityStore`；`codegraph node -f vue-assetmanagement/vitest.config.ts` |
| P2-01 | P2 | 行级隔离防退化 | `apps/assetmanagement/services/out_asset_service.py:49,56`；对照 `:242-246` | `create_outasset` | `user` 为可选参数且 `if user is not None` 条件校验；忘传即跳过可见性检查。生产唯一调用方 `out_asset_view.py:230-234` 已传，属防退化缺口而非现网越权 | 与 `update_outasset` 对齐改为 kw-only 必填并去掉空值守卫；测试显式覆盖「忘传即报错」 | `codegraph impact create_outasset`；`codegraph callers create_outasset` |
| P2-02 | P2 | 审计可靠性 | `apps/unregisteredasset/audit_adapter.py:109-113`（同类 `:156,213`、`services.py:102`） | `log_create` | 宽 `except Exception` 仅累计 `AUDIT_WRITE_FAILED` 指标并记日志，主流程继续；极端情况下状态变更可无审计痕（B7） | 明确「审计写入失败即回滚」或「异步补偿队列」二选一，并补失败路径测试 | `codegraph node log_create`；`codegraph callers log_create` |
| P2-03 | P2 | CT-7 口径 | `.github/workflows/ci.yml:384`；`vue-assetmanagement/package.json:14` | — | CI 跑 `npx vue-tsc --noEmit`，本地 `npm run type-check` 为 `vue-tsc --build`；两种形态对 project references 的处理不同 | 统一为 `npm run type-check`，或在 CI 注释登记差异理由 | `codegraph node -f .github/workflows/ci.yml` |
| P2-04 | P2 | CI 效率 | `.github/workflows/ci.yml:454,456` | — | `frontend-test` 连续两次执行同一 `npm run test:coverage`（T15 专项由阈值块兜底），重复约 65s 全量覆盖运行 | 第二次改为 `npx vitest run --coverage --coverage.include="src/stores/**/*.ts"`，或删除并注明阈值块已覆盖 | `codegraph node -f .github/workflows/ci.yml` |
| P2-05 | P2 | 密钥扫描盲区 | `.github/workflows/security-scan.yml:250,276,313` | — | 第一步仅 `--type py/js/ts/json`，第二步显式 `-g '!.github/**'`；workflow 目录自身的凭据形态不被任何 secret 扫描覆盖（含 `ci.yml:220` 的 CI 占位串） | 黑名单改为哈希指纹；扫描覆盖 `.github/**` 并只精确排除黑名单步骤自身 | `codegraph node -f .github/workflows/security-scan.yml` |
| P2-06 | P2 | 依赖审计口径 | `.github/workflows/security-scan.yml:173,216` | — | `pip-audit --ignore-vuln CVE-2026-106454` 白名单与 `npm audit --omit=dev` 使 dev 依赖高危不阻断；与 SC-7「检测到高危组件即阻断」的字面口径有差距（属已登记的降噪取舍） | 在 §6 执行状态中补记两条例外及复核周期，或 schedule 全量时补扫 dev | `codegraph node -f .github/workflows/security-scan.yml` |
| P2-07 | P2 | 前端错误处理 | `UnregisteredAssetDetails.vue:243,246`、`StorageDetails.vue:212,215`、`RecycleAssetDetails.vue:244,247`、`OutAssetDetails.vue:245,248`、`AssetContentDetails.vue:417-418` 等 | — | 多处 `.then()` 无 `catch` / `void loadStorages()`，ESLint 未启用 `no-floating-promises`；失败时 UI 可能停在 loading 或静默无提示 | 统一走 `utils/errorHandler.ts` 的 `notifyCallerError`，并启用类型感知的 floating-promise 规则 | `codegraph node -f vue-assetmanagement/src/utils/errorHandler.ts` |
| P2-08 | P2 | 前端 DRY | `views/system/RoleManage.vue:77-83,145-151`、`AuthUserManage.vue:97-103,186-192`、`ContactsView.vue:88-94,121-131`、`NotificationList.vue:69-103,249-254` | `createEntityStore` 周边 | 4 个页面重复「三 ref + el-pagination + 4 个 handle*」与 `:deep(.el-card__header/body)` 样式；已有 `CommonList.vue`、`SmartListContainer.vue`、`usePagedList.ts`、`usePaginationSearch.ts` 可复用 | 按 FR-1/FR-2 抽为统一列表页组件 + composable，逐页替换并补交互测试 | `codegraph node createEntityStore`；`codegraph callers createEntityStore` |
| P2-09 | P2 | 跨端日期显示 | `vue-assetmanagement/src/utils/Format.ts:46-100` | — | 后端序列化 ISO 8601 `+08:00`，前端全部用本地 `getFullYear/getMonth/getHours` 渲染；非东八区浏览器的「业务日期」可能跨日（**`[推测]`**：未做跨时区实测，且后端时间串样本未取） | 明确产品口径：业务日期按 `Asia/Shanghai` 固定渲染，或全链路改 UTC+展示时区 | `codegraph node -f vue-assetmanagement/src/utils/Format.ts` |
| P2-10 | P2 | 本地可复现性 | `asset_management_backend`（pytest setup） | — | 全量套件因残留测试库 `test_asset_management_backend` 产生 2079 个 setup ERROR，耗时 17m42s 且未产出覆盖率；影响本地复现 CI 结论 | 文档登记 `pytest --keepdb` / 清理残留库的恢复步骤；CI 使用一次性库不受影响 | `codegraph node -f asset_management_backend/conftest.py` |
| P2-11 | P2 | LT-1 / DR-1 | `scripts/check_frontend_invariants.py:179-220`；`scripts/line_metrics.py:94-110` | `logical_line_count` | 前端护栏内联第二份逻辑行计数实现，且 `read_ledger:241-259` 未区分「活跃/已关闭」分区；与「单一实现收敛于 line_metrics.py」的纪律存在张力（前端口径条文另指派本脚本为权威来源，故不判硬违规） | 抽公共 TS 计数函数至 `line_metrics.py`（或明确文档双口径），台账解析复用 `active_ledger_lines` | `codegraph node logical_line_count`；`codegraph callers logical_line_count` |
| P2-12 | P2 | CI 汇总完整性 | `.github/workflows/security-scan.yml:326-330,361-365` | — | `Security 汇总` 的 `needs` 仅 4 个 job，未纳入 `weekly-report`；周报生成失败不被汇总节点发现（SC-8 报告面） | 把 `weekly-report` 纳入 schedule 分支的条件判定，或另设告警 | `codegraph node -f .github/workflows/security-scan.yml` |
| P3-01 | P3 | 规模余量 | `apps/assetmanagement/views/asset_view.py`（484 逻辑行） | — | 距 DR-5 上限 500 仅 16 行，后续新增即触发拆分 | 新增功能前先拆出 action 分组模块 | `codegraph node -f asset_management_backend/apps/assetmanagement/views/asset_view.py --symbols-only` |
| P3-02 | P3 | 规模余量 | `vue-assetmanagement/src/composables/usePaginationSearch.ts`（199 逻辑行） | — | 距 FR-6 上限 200 仅 1 行 | 拆出状态机/请求参数两个 composable | `codegraph node -f vue-assetmanagement/src/composables/usePaginationSearch.ts --symbols-only` |
| P3-03 | P3 | 设计规范 | `views/LogIn.vue:333-418`、`DashboardWelcomeBar.vue:68-93`；7 个 `.vue` 直接 `import { isAxiosError } from axios` | — | px 字面量偏离 F1-F5 的 4px 基数；`eslint.config.ts:110-130` 仅禁 `@/api/*` 未禁 `axios`，F11 规则缺口 | 抽公共间距令牌；ESLint 增加 `no-restricted-imports` 并保留类型导入例外 | `codegraph node -f vue-assetmanagement/eslint.config.ts` |
| P3-04 | P3 | 文档口径 | `core/mixins.py:111,137,206`；`utils/response_utils.py:23` | `success_response` | 默认 message 为「操作成功」，各 View 传「查询成功/创建成功」；B1 示例为 `"success"`。跨端契约只约束根结构，前端按 `code` 判定，不构成契约破坏 | 在规范中补记「message 为展示文案、值不固定」 | `codegraph callers success_response` |
| P3-05 | P3 | OC-2 环境差异 | `config/settings/base.py:346-350`；`production.py:101-104` | — | dev/test 的 console handler 用 `simple` formatter 且未挂 trace_id filter；仅 production 覆写为 JSON + trace_id | dev/test 也挂 `TraceIDFilter`，或明确豁免登记 | `codegraph node -f asset_management_backend/config/settings/base.py` |
| N-01 | 不采纳 | 误报 | `serializers/asset_crud_serializers.py:147-166` 等 | `SlugRelatedField` | 子代理报「Serializer 触碰数据库」；实为 DRF 关系字段的 `queryset` 声明，用于入参校验与 FK 解析，不是 Serializer 执行写库 | 无需修改 | `codegraph node -f asset_management_backend/apps/assetmanagement/serializers/asset_crud_serializers.py` |
| N-02 | 不采纳 | 误报 | `views/employee_view.py:113-123`、`department_view.py:61-71`；`scripts/check_duplicate_invariants.py:27-37` | `G6_G7_EXEMPT` | 子代理报「批量删除缺 user → 行级校验缺口」；实为 G-6/G-7 登记的 system_admin-only 豁免，两个 ViewSet 的 `batch_delete` 均走 `IsSystemAdmin` | 无需修改 | `codegraph node G6_G7_EXEMPT`；`codegraph node -f asset_management_backend/apps/usermanagement/views/employee_view.py` |
| N-03 | 不采纳 | 误报 | `.github/workflows/security-scan.yml:302-323` | — | 三条明文串是「已轮换泄露凭据黑名单」，用途是检测回流，不是在用 AK/SK/Token；扫描步骤自身排除 `.github/**` 才能避免自命中 | 改哈希指纹（并入 P2-05），不按 SC-1 违规处理 | `codegraph node -f .github/workflows/security-scan.yml` |
| N-04 | 不采纳 | 误报 | `vue-assetmanagement/src/router/guards.ts:91-94,102-104` | `checkRoleAccess` | 「未列读路由默认放行」是 M-19 刻意设计：写语义路由兜底 deny，且有 `guards-write-deny.spec.ts` 不变量；真实授权边界在后端 | 无需修改 | `codegraph node checkRoleAccess` |
| N-05 | 不采纳 | 误报 | `asset_management_backend/scripts/clear_database.py:134-147` | `_validate_table_name` / `_build_identifier_sql` | 动态表名经白名单 + `psycopg.sql.Identifier` 双重加固，符合 SC-4 | 无需修改 | `codegraph node _build_identifier_sql` |

---

## §三 分域结论与修复建议（按优先级）

### 3.1 P1 项四要素（证据 / 影响面 / 修复建议 / 建议验证方式）

| ID | 优先级 | 影响面（图谱实测） | 建议验证方式 |
|:--|:--|:--|:--|
| P1-01 | 1（最先） | 部署链路全部 workflow；`codegraph node audit_listener` 显示编排断言只覆盖 `ci-summary` 与 `guard-summary`（`TARGETS:35-38`），`ci-cd.yml` gate 只回查 1 条安全 workflow。`duplicate-guard.yml:40-42` 已注释说明「跨 workflow 统一汇总只能靠 required checks 或 API 回查，本批不引入」——**这是已登记的取舍，本条为风险提示，不是隐瞒缺陷** | 在 `scripts/tests/test_ci_orchestration.py` 增加「gate 回查名单必须包含全部汇总节点」断言，先证红后证绿；再用一次失败护栏 run 验证 gate 拒绝部署 |
| P1-02 | 2 | `codegraph callers read_text`：`scripts/check_duplicate_invariants.py` 版本被 12 处调用（含 G-1/G-2/G-3 与 `_iter_ast_trees`），即所有 G 检查都在绕过面上 | 新增带 BOM 的夹具文件，断言护栏 exit 1（先红）；复用 `line_metrics.read_text` 后断言现实仓仍 PASS（后绿）；对照 `scripts/tests/test_file_length_guard.py` 已有 BOM 证红用例 |
| P1-03 | 3 | `codegraph impact ResponseWrapperMixin` = 56 符号，说明 View 基类改动会波及十余个 ViewSet；`codegraph node WasteAssetViewSet` 显示 `:69` 类属性 + `:103` `get_queryset` 并存，两套取数口径同域共存 | 每个改造域补 `get_queryset()` 行级隔离断言（对照 `test_employee_rbac_scope.py` 14 用例），并跑后端全量 pytest（须先清理残留测试库，见 P2-10） |
| P1-04 | 4 | `codegraph impact BatchDeleteViewMixin` = **246 符号**（13 域接线）；`codegraph callees batch_delete` = 5 个直接被调；`core/batch_mixins.py:392-393` 明示响应键集由 `test_b5_baseline_snapshot` / `test_batch_contract_snapshot` 锁定 | 扁平化后保持两个快照全绿，另增一条调用链深度断言（View→Service→Selector≤3）防回潮 |
| P1-05 | 5 | 121 个 `.vue` 中至少 6 个 0% 覆盖；阈值块 `21.1/19.0/18.6/21.3` 与估算语句命中 21.19% 仅差 0.09pt，任何小改动都可能触发 CI 红 | 在无宿主清理策略干扰的环境执行 `npm run test:coverage`，确认四项阈值绿；补测后按 T14 手工上移棘轮并复核 CI `frontend-test` |

**批次建议**：P1-01 / P1-02 属「护栏与门禁自身正确性」，影响面小、可一次清干净，建议同批；P1-03 / P1-04 属后端架构，涉及十余 View 与 13 域批量骨架，建议按域分批（每批先补回归测试）；P1-05 属测试资产，独立批次。所有批次按 DR-1/DR-2 同型归并，避免零散补丁。

### 3.2 后端：架构、逻辑与流程

- **整体判断**：五层骨架成形。状态字段写操作收敛在 `AssetFSM._transition`，例外全部登记在规范 §三；`@transaction.atomic` + `select_for_update()` 覆盖主要状态变更 Service；通知统一 `send_notification_on_commit`；`clear_database.py` 双闸满足 SC-4。合同 FSM 以 `_CONTRACT_TRANSITIONS` 为单一事实源，非法态收敛 `ContractInvalidTransitionError`、读路径脏数据返回 `[]`。
- **主要缺口**：① View 层类属性直写 ORM 过滤链（P1-03），使 B12 的「Selector 唯一取数入口」在同一域存在两套口径；② 批量删除链过深（P1-04），编排分散在 ViewMixin、Service、`_delete_one`、Selector、audit 五处，排障与变更成本高；③ 审计适配器宽 `except`（P2-02）让 B7 的「不可跳过」依赖指标告警而非事务保证；④ `create_outasset` 的可选 `user`（P2-01）是「忘传即放行」的退化面，虽然现网调用方已传。
- **正面实践**：`BatchDeleteViewMixin` 把 13 域批量删除收敛为差异类属性配置；`core/envelope_schema.py` 后处理器与运行时 `success_response` 互为镜像；`core/department_scope.py` 为部门范围唯一事实源；`api-schema-baseline.json` + `api-schema-check` job 守护 OpenAPI 契约。

### 3.3 前端：架构、流程与代码质量

- **整体判断**：跨端契约消费正确（`unwrapResponse`、8 键枚举、`page/page_size`），无组件直连 `axios` 发请求，Pinia 全为 Setup Store，非 scoped 样式与 Options API 零命中，竞态防护（`listRequestSeq`、`loadingCount` 引用计数）已成型；`createEntityStore` 工厂覆盖 13 个实体。
- **主要缺口**：① `.vue` 层测试覆盖薄弱、棘轮余量极小（P1-05）；② 4 个管理页重复分页/搜索/错误样板（P2-08）；③ 多处 `.then()` 无 catch（P2-07）；④ 日期按本地时区渲染（P2-09，`[推测]`）；⑤ 物理行口径误判已排除——护栏权威值 `createEntityStore.ts` 407、`usePaginationSearch.ts` 199，均未超限，但后者余量仅 1 行（P3-02）。
- **门禁实测**：`vue-tsc --build --noEmit` 与 `eslint .` 均 exit 0；197 个测试文件 / 2542 用例全绿。覆盖率最终阈值判定因宿主清理策略拦截未完成，不能据此宣称 CT-2 通过。

### 3.4 工程化 / CI / 安全

- **门禁全貌**：`ci.yml` 15 个 job 全部纳入 `CI 汇总`；`security-scan.yml` 6 job，`Security 汇总` 按 `deps-changed` 分流且 `secret-scan` 无条件必查；`duplicate-guard.yml` 4 job；`migration-check.yml` 独立。无生效 `continue-on-error`。SC-8 每周 `cron 7 3 * * 1` 全量兜底已落地。
- **闭合缺口**：部署 gate 只回查 CI 结论与 `Dependency Security Scan`（P1-01），其余 workflow 失败仍可部署；`Security 汇总` 未纳入周报 job（P2-12）；`migration-check.yml:83-89` 对危险迁移仅警告，符合 CT-6「人工确认」文本，不判违规。
- **口径与降噪**：后端静态门禁精确钉版且 CI 读 `dev.txt`（CT-7 已对齐）；前端为 caret 范围，且 CI 与本地 type-check 命令形态不同（P2-03）；`--omit=dev` 与 `--ignore-vuln` 是已登记降噪（P2-06）；workflow 目录自身处于密钥扫描盲区（P2-05）。
- **护栏自洽**：四护栏本次全 PASS；但 `check_duplicate_invariants.py` 的 BOM 假绿（P1-02）与前端护栏双实现（P2-11）说明「护栏自身的护栏」仍需补强。

---

## §评审结论

### 自审清单（阶段 5，仅复核报告，不涉及代码改动）

- [x] 索引覆盖：`codegraph status` 有效 + `sync` 成功；MCP 不可用已降级并在 §1.1 留痕，无 missing/陈旧告警
- [x] 台账完整性：每条具备 级别 / 类型 / file:line / symbol / 回查命令 五要素；配置类条目补文件模式定位
- [x] 专项覆盖：§5 各行维度均有命令输出或源码引用（CT-3 / 契约 4 项 / SC 分流 / 覆盖率 / 规模）
- [x] 报告闭环：5 条 P1 均有 证据 + 影响面 + 修复建议 + 建议验证方式；5 条误报均标「不采纳 + 理由」
- [x] 建议可执行性：建议均含 file:line / symbol 去处，修复类 skill 可直接接手
- [x] 只读纪律：本次未改动任何业务代码；唯一新增文件为本报告
- [x] 置信度纪律：子代理的三类高风险结论（Serializer 触碰 DB、批量删除越权、明文凭据）已逐条回读源码复核并降级/不采纳；物理行粗估的规模结论已用护栏 `--print` 纠正

### 台账终态

| 状态 | 数量 | 说明 |
|:--|:--|:--|
| 待修 | 22 | P1 ×5、P2 ×12、P3 ×5；本报告不跟踪修复完成状态 |
| 不采纳 | 5 | N-01~N-05，理由见 §二 |
| 已修复 | 0 | 本 skill 为纯审计，不产生该状态 |

### 事实边界

1. 本次未取得后端全量测试全绿与覆盖率结论（本地测试库残留导致 2079 errors），也未取得前端覆盖率最终阈值判定（宿主安全策略拦截 V8 清理）；相关数字按实测原样记录，覆盖率明细明确标为「基于 V8 statementMap 的命中率估算」。
2. `mutmut` 变异测试、`pip-audit` / `npm audit` 全量扫描、`npm run format:check`、`api-schema-baseline.json` 逐项 diff 本次未执行；依赖漏洞与 API 契约以 CI 既有门禁为权威，报告未对其下通过/失败结论。
3. Service 层逐边集成覆盖、跨时区浏览器行为、运行时 RBAC 拒绝行为未做实测，相关表述标 `[推测]` 或「未覆盖」。
4. 索引中的 5 条 workflow `.yml` 为 0 symbols，图谱无法给出其调用关系；相关结论来自文件行号与命令输出，不归因于图谱。
