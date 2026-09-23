# 全量代码审查报告

> 审查时间：2026-09-23 | 审查方式：7 轮分审（`docs/Review/Review.md` 协议）  
> 审查范围：全项目（`asset_management_backend` + `vue-assetmanagement`）  
> 审计 Agent：mimo-v2.6-flash-free  
> 交叉基线：`docs/Review/full-review-report-2026-09-17.md`（46 项，仅作对照，不替代本轮取证）  
> 执行模式：连续执行第 2~7 轮（用户已确认）；本文件为唯一写操作目标。

---

## 审查计划执行摘要

| 轮次 | 内容 | 状态 |
|:-----|:-----|:-----|
| 1 | 项目理解 + 审查计划（前置阅读 + 4 路并行取证） | 已完成 |
| 2 | 需求功能覆盖 + 接口契约一致性 | 已完成 |
| 3 | 资产状态机 + CT-3 全路径 | 已完成 |
| 4 | 权限 / 行级隔离 / SC-1~SC-8 / 审计留痕 | 已完成 |
| 5 | 事务 / 并发 / 通知 / OC-1~OC-7 | 已完成 |
| 6 | 测试覆盖 CT / DRY DR / 质量门禁实测 | 已完成 |
| 7 | 规范符合性 + 本报告 + 最终审计票 | 已完成 |

**门禁实测（第 6 轮，本地真实执行）**

| 门禁 | 命令/口径 | 结果 | 阈值 | 判定 |
|:-----|:----------|:-----|:-----|:-----|
| 后端整体覆盖 | `pytest --cov=. --cov-fail-under=80` | **1274 passed，84.40%** | ≥80% | **通过** |
| 后端 Service 覆盖 | `pytest --cov=apps.assetmanagement.services --cov-fail-under=90` 等 | **96.97%** | ≥90% | **通过** |
| 前端覆盖 | `npx vitest run --coverage` | **1812 passed，Statements 93.17% / Branches 87.46%** | ≥80% | **通过** |
| 前端 Store 覆盖 | 含 `src/stores/**/*.ts` | **97.89%** | ≥90% | **通过** |
| 前端 type-check | `vue-tsc --build` | 0 error | 0 | 通过 |
| 前端 lint | `eslint .` | 0 | 0 | 通过 |
| 前端 format | `prettier --check src/` | 0 | 0 | 通过 |
| 重复不变量 | `scripts/check_duplicate_invariants.py` | PASS | PASS | 通过 |
| 函数长度护栏 | `scripts/check_function_length_guard.py` | PASS（0 超限） | 0 | 通过 |
| 前端规模护栏 | `scripts/check_frontend_invariants.py` | PASS | PASS | 通过 |
| `ruff check` | apps/core/utils/config/scripts | **7 errors**（5 可自动修复） | 0 | **失败** |
| `ruff format --check` | 仓库根 | **102 files would reformat** | 0 | **失败** |
| `mypy --strict` | `mypy . --strict` | **24 errors / 10 files** | 0 | **失败** |
| `ruff --select C90` | 生产 apps 范围 | **2 处**（`update_user`、`_create_role_permissions`） | 0 | **失败** |
| 后端变异测试 | `mutmut run`（Windows + WSL） | **不可执行**（环境限制） | ≥80% | **[PENDING]** |
| 前端变异测试 | `stryker run` | **未执行**（配置就绪，无结果目录） | ≥80% | **[PENDING]** |

> **CT-5 判定**：本轮本地全量测试 **0 失败**（后端 1274 + 前端 1812），不触发 CT-5 阻塞。  
> **CI 风险**：`.github/workflows/ci.yml` 包含 `ruff check`、`ruff format --check`、`mypy . --strict`、C90、mutmut、vitest threshold 步骤；上述 3 项静态门禁本地已红，**若推送则 CI 大概率失败**（事实推断依据：本地同口径命令非零退出）。

---

## P0 — 阻断级（0 件）

无。

---

## P1 — 严重级（4 件）

| ID | 严重级别 | 类别 | 文件/行号 | 问题描述 | 证据（代码片段/文档条目） | 影响 | 修复建议 | 验证方法 | 关联规则 |
|:---|:---------|:-----|:----------|:---------|:--------------------------|:-----|:---------|:---------|:---------|
| N-1 | P1 | 权限安全 | `assetmanagement/views/asset_view.py:59-72,95-101,383,396` | `mark_broken` / `mark_lost` **角色校验旁路**：`@action(permission_classes=[IsAssetAdminOrAbove])` 被类方法 `get_permissions()` 整体覆写后失效；两 action 未列入 `admin_actions`，落回 `IsAuthenticated` | `admin_actions` 含 `found_and_return`/`repair` 等但 **无** `mark_broken`/`mark_lost`（:59-72）；`get_permissions` 非 admin_actions 仅返回 `[IsAuthenticated()]`（:101）；权限矩阵要求 regular_user 对「损坏/遗失 登记」为 ❌（`backend-business-rules.md:141`）；`test_create_row_isolation.py:173/196` 断言 regular 用户本部门可 200（仅行隔离，无角色拒绝锚） | 任意已登录用户可对本部门资产调用标记损坏/遗失，**越权写**；与 §4.2 矩阵及 `@action` 声明的意图不一致 | 将 `mark_broken`/`mark_lost` 加入 `admin_actions`；或在 `get_permissions` 显式分支；补 `regular_user → 403` 回归测试（先红后绿） | 新增 API 测试：regular 用户 POST `assets-mark-broken`/`mark-lost` 断言 403；admin 用户仍 200 | B11, §4.2, CT-1, CT-4 |
| N-2 | P1 | 权限安全 | `assetmanagement/views/storage_view.py:31-42,103-112` + `views/_mixins.py:52-64` | **仓库批量写权限缺口**：`StorageViewSet` 继承 `AdminWritePermissionMixin`，其默认 `admin_actions` 仅含 `create/update/destroy/...`，**不含** `batch_create`/`batch_delete`；`batch_create` 落回 `IsAuthenticated`，任意认证用户可批量建仓 | `_mixins.py:52-59` admin_actions 清单；`storage_view.py:103` `@action(... batch-create)` 无类级 `admin_actions` 覆盖；对比 `contract_view.py:57-58` / `asset_type_view.py:49-50` **已显式纳入** batch 两项；§4.2 矩阵「系统配置-仓库」仅 system_admin ✅（`backend-business-rules.md:144`） | 未授权用户批量创建仓库主数据，污染全局配置；同端点族权限不一致 | Storage 补 `admin_actions = [..., "batch_create", "batch_delete"]`（对齐 contract/asset_type）；补 regular→403 / system_admin→201 测试 | 新增 `storage` View RBAC 测试覆盖 batch-create/batch-delete 双向；跑 `test_b5_baseline_snapshot` 确认 200 路径仍绿 | B11, §4.2, CT-1, CT-4 |
| N-3 | P1 | 代码质量/CI | 仓库根 `ruff format --check .`（102 files）、`ruff check`（7 errors）、`mypy . --strict`（24 errors） | **CI 静态门禁三连红**：本地实测与 `ci.yml` 同口径命令均失败；推送 PR 将触发 CI 失败（同命令在 workflow 中为阻断步骤） | `ci.yml`：`ruff check .`、`ruff format --check .`、`mypy . --strict`、C90 步骤；本地：format 102 待重排、ruff 7 errors（含 `scripts/loadtest/*` I001/E402、`notification/tests/test_ws_consumer.py:8` F401）、mypy 24（dateutil stubs、`var-annotated` 等） | 合并流水线不可用；掩盖真实回归信号 | ① `ruff check --fix` + `ruff format .` 单独提交；② mypy 24 条按文件分批消减（优先 `var-annotated` 6 处）；③ C90 两处生产函数拆分（`services.py:220`、`init_production_data.py:186`） | 本地复跑三条命令 exit 0；CI 对应 job 变绿 | BR-4/CT 门禁, DR-5 |
| N-4 | P1 | 状态机/文档一致性 | `docs/Review/Review.md:110-111` vs `state_machine/transitions.py:44-57` vs `Project_Requirements/02-技术设计/03-业务规则与状态机.md` | **审查协议与业务文档、实现三者不一致**：Review.md 写 `broken/lost → repairing`，但实现与 03 需求文档均 **仅** `broken → repairing`；`LOST` 仅可转 `damaged`/`recycled_pending` | `transitions.py:44-47` BROKEN→REPAIRING；`:54-57` LOST 无 REPAIRING 边；03 文档维修入口仅 broken；Review.md L110-111 仍列 lost→repairing | 若以 Review.md 为准则缺实现；若以 03 为准则审查清单有误——**需人工裁定以哪份为契约** | 人工确认：A) 修订 Review.md 删除 lost→repairing；或 B) 视为需求变更走 §5.2 流程加边+测试+迁移（本报告不擅自改状态机） | 确认后：若 A，更新 Review.md；若 B，补 `lost→repairing` 集成测试（CT-3）及前端入口 | §1.3 HALT 相邻, CT-3, Fact-1 |

**[HALT] 判定（N-4）**：本项触及「资产状态机流转路径」认知冲突。按 Review.md 约束与根级 §1.3，**暂停对该路径的任何代码改动**，等待人工在方案 A/B 间拍板。审查报告本身可完成，不阻塞其余结论输出。

---

## P2 — 中等级（8 件）

| ID | 严重级别 | 类别 | 文件/行号 | 问题描述 | 证据（代码片段/文档条目） | 影响 | 修复建议 | 验证方法 | 关联规则 |
|:---|:---------|:-----|:----------|:---------|:--------------------------|:-----|:---------|:---------|:---------|
| N-5 | P2 | 可观测性/测试 | `config/urls.py:150-151`；无 `test*health*`/`test*ready*` | `/health/`、`/ready/` 端点存在，但 **零测试锚定**（全仓 glob 无对应测试文件） | `urls.py` 注释「OC-6 落地」；测试检索仅命中 nginx compose 路径字符串 | 端点回归（如被误删/改 503）无 CT-1 护栏 | 补 2 个冒烟测试：GET `/health/`→200、`/ready/` 依赖就绪时 200/503 语义 | `pytest` 新增用例通过；故意断言错误路径先红 | OC-6, CT-1, CT-4 |
| N-6 | P2 | 可观测性 | `vue-assetmanagement/src/**`（非测试） | 前端非测试代码 `console.error` **160 处**，无结构化、无 trace_id（交叉对照旧报告 #27，**仍开放**） | `Select-String 'console\.error'` 排除 `__tests__`/`.spec.` 计数=160；样本 `src/api/auth.ts:50,52,54,91...`、`src/api/request.ts:117,131` | 前端故障难关联后端 trace；与 OC-2 精神不一致（OC-2 主约束后端，前端属治理项） | 收敛至 `utils/logger.ts`（若无则新建薄封装：结构化 + 可注入 trace_id）；API 层优先改造 | 改造后 `rg 'console\.error'` 生产路径显著下降；lint 可加 no-console 规则渐进收紧 | OC-2（前端治理）, DR-4 |
| N-7 | P2 | AI鲁棒性 | 后端 4 处 + 前端 3 处 `AI_REVIEW_NEEDED` | 高风险标注 **未清零**，人工复查未闭环（`TODO_AI_CONFIRM` 全仓 0，该项达标） | 后端：`state_machine/scrapping.py:135`、`views/_lifecycle_base.py:59`、`core/throttles.py:32`、`docker/feishu-webhook/app.py:41`；前端：`AssetQuickScan.vue:76`、`outAssetFormEditLoader.ts:21`、`ContractDetails.vue:349` | 标注语义为「待人工确认」；长期滞留使标注失效 | 逐条人工确认后删除注释，或改 `# TODO_AI_CONFIRM` 若仍不确定 | `rg AI_REVIEW_NEEDED` 归零（或转受控清单） | AR-2, Fact-1 |
| N-8 | P2 | 测试/变异 | `mutmut`（后端）/ `stryker`（前端） | **T8 变异测试未执行**：Windows 无 mutmut、WSL 未装；stryker 配置就绪（`stryker.config.json`，`test:mutate`，break 80）但无 `mutation_results` | 实测 `mutmut` 不可用；`Test-Path mutation_results`=False；`ci.yml:214-217` 已含 mutmut 步骤 | CT-2/T8 变异分支在本地为 **[PENDING]**，CI 侧依赖 Linux runner | 本地：WSL 安装 mutmut 或跑 CI；前端 `npm run test:mutate` 一次取基线 | 变异得分 ≥80% 报告归档 | CT-2, T8, backend-testing-rules |
| N-9 | P2 | 测试缺口（权限） | `tests/` 无 `*storage*rbac*`；`test_asset_view_api.py:298-314` | Storage View 层 **无 RBAC 测试文件**；`mark_broken`/`mark_lost` 测试 **仅 admin 正向**（`admin_authenticated_client`），无 regular 反向 403 | glob `*storage*` 仅 `test_storage_service.py`（服务层）；asset mark 测试 L298-314 无 403 断言 | N-1/N-2 修复前无红灯、修复后无绿灯锚——违反 CT-4 | 与 N-1/N-2 同 PR 补测试（先红后绿） | 新测试文件过 CI | CT-1, CT-4, B11 |
| N-10 | P2 | 交叉基线残留 | 旧报告 #27；本轮 N-6 | 旧 46 项中经代码复核 **确认仍开放** 项：#27（console.error）；#2/#3/#4/#8 **代码侧已修复但旧报告未标 ✅** | 见下方「旧报告 46 项交叉核对」专节证据 | 基线报告状态漂移，后续审计易误读 | 在旧报告对 #2/#3/#4/#8 补 ✅ 已修复标注（文档级，本报告不改旧文件除非授权） | 人工复核后更新旧报告状态列 | Fact-1, 交叉核对 |
| N-11 | P2 | 规范/复杂度 | `apps/authusermanagement/services.py:220`；`apps/usermanagement/management/commands/init_production_data.py:186` | 生产代码 C90 圈复杂度 **11>10**：`update_user`、`_create_role_permissions` | `ruff check --select C90 --max-complexity 10` 命中（CI 同参数）；另有 13 处命中位于 `.trae/skills/*`、`clear_database.py:254`（非生产 apps，可目录豁免或一并修） | CI C90 job 失败 | 按 BR-4 台账模式拆分两个函数（helper 提取），生产优先 | C90 命令对 apps 输出 0 | BR-4, DR-6, CT 门禁 |
| N-12 | P2 | 安全配置卫生 | `.github/workflows/security-scan.yml` | 旧报告 #8 **已修复**：SC-7/SC-8 workflow 存在且含 weekly cron + `--fail-on=high` | 文件 6883 bytes；`pip-audit --fail-on=high`；`cron: "7 3 * * 1"` | 无（已达标）——列此行仅完成 46 项闭环 | 保持；关注 npm audit job 是否对称存在于 `ci.yml` | SC-7 实测 workflow 文件存在 | SC-7, SC-8 |

---

## P3 — 低级/优化建议（3 件）

| ID | 严重级别 | 类别 | 文件/行号 | 问题描述 | 证据 | 影响 | 修复建议 | 验证方法 | 关联规则 |
|:---|:---------|:-----|:----------|:---------|:-----|:-----|:---------|:---------|:---------|
| N-13 | P3 | 代码质量 | `scripts/loadtest/*`、`notification/tests/test_ws_consumer.py:8` | ruff 7 errors 中 5 处可 `--fix`（import 排序/E402）；测试 F401 冗余 import | `ruff check` 输出 `5 fixable` | 污染 lint 基线 | `ruff check --fix` + 手工删 F401 | `ruff check` 剩 0 或仅剩不可自动修项 | 代码质量 |
| N-14 | P3 | 可观测性 | `core/prometheus_middleware.py`、`core/metrics.py`、`config/urls.py:152-153` | OC-4 Prometheus **已落地**（metrics 端点 + 中间件 + docker/prometheus.yml），QPS<10 场景维持 `[~]` 豁免合理 | urls `path("metrics/", metrics_view)`；存在 `config/prometheus.yml` | 无 | 保持；QPS 达阈后启用告警基线 | 刷新 `/metrics/` 见序列 | OC-4 |
| N-15 | P3 | 文档/清单 | 旧报告状态列 | 旧报告 #2/#3/#4 行内无 ✅ 标记，但代码证据显示已修复（下节展开） | 见交叉核对节 | 读者可能重复立项 | 更新旧报告状态（需授权改旧文件） | 人工确认 | Fact-1 |

---

## 旧报告 46 项交叉核对（`full-review-report-2026-09-17.md`）

> 方法：以 **本轮实测/源码** 为准复核，不以旧报告状态列为准。脚本初筛 OPEN=#2,3,4,8,27，再逐项取证推翻/确认。

| 旧# | 旧结论（脚本） | 本轮复核结论 | 关键证据 |
|:----|:---------------|:-------------|:---------|
| 1 | 已修复 | 维持已修复 | 旧报告已标 ✅，本轮未回退 |
| 2 | 疑似 OPEN | **已修复（旧报告未标 ✅）** | `out_asset_service.py:115` 快照含 `original_applicant`；`:322` `_restore_asset_fields` 按 `original_*` 还原 |
| 3 | 疑似 OPEN | **已修复（旧报告未标 ✅）** | `asset_selector.py:100` `apply_user_scope`；`:161` `get_available_assets(user=...)`；docstring 显式 B12 |
| 4 | 疑似 OPEN | **已修复（旧报告未标 ✅）** | `recycle_asset_service.py:171` `AuditLogger.log_state_change`（二次 FSM 审计） |
| 5-7,9-26,29-31,33-38,40-41,44-46 | 已修复 | 维持 | 旧报告 ✅ 行，抽查无回退迹象 |
| 8 | 疑似 OPEN（缺文件） | **已修复** | `.github/workflows/security-scan.yml` 存在，含 pip-audit fail-on=high + 周扫描 cron |
| 27 | OPEN | **仍开放** | 生产前端 `console.error` 实测 **160**；本轮升为 N-6（P2） |
| 28,32,42,43 | 误报 | 维持误报 | 旧报告已论证（RBAC 设计、reject 方法归属、SoftDeleteManager、调用链实测） |
| 39 | 重复 | 维持 | 与 #30 同一缺陷已去重 |

**汇总**：46 项中 **36 已修复 + 4 误报 + 1 重复 = 41 关闭**；**1 仍开放（#27→N-6）**；**4 项（#2/#3/#4/#8）代码已修复、旧报告状态列待人工补 ✅**。

---

## 五个矩阵

### 1. 功能覆盖矩阵（核心资产生命周期，节选）

| 功能点 | 需求来源 | 前端入口 | Pinia store | 前端 API | 后端 URL/View | Service | Selector | Model | 测试 | 状态 |
|:-------|:---------|:---------|:------------|:---------|:--------------|:--------|:---------|:------|:-----|:-----|
| 资产列表/筛选 | 07-AC 列表 | AssetList 页 | assetStore | `api/asset.ts` | `assets/` AssetViewSet.list | — | AssetSelector.get_queryset_for_user | Asset | selector_isolation + view | ✅ |
| 资产新增 | 07-AC create | AssetForm | createEntityStore | batch/create | `assets/` create | AssetService.create | AssetSelector | Asset | test_batch_create_asset 等 | ✅ |
| 出库→在用 | 07-AC outasset | OutAsset 页 | outAssetStore | `api/outAsset.ts` | `outassets/` | OutAssetService | OutAssetSelector | OutAsset+Asset FSM | out_asset_service 8 例 | ✅ |
| 回收→待发放 | 07-AC recycle | Recycle 页 | recycleAssetStore | `api/recycle…` | `recycleassets/` | RecycleAssetService | …Selector | Asset FSM | recycle 审计 :171 | ✅ |
| 标记损坏 | 07-AC broken | 资产操作 | assetStore | `markBroken` | `assets/{id}/mark-broken/` | AssetService.mark_asset_broken | ensure_asset_visible | Asset+BrokenAsset | lifecycle 正向有；**403 缺（N-1/N-9）** | ⚠️ 权限 |
| 标记遗失 | 07-AC lost | 同上 | assetStore | `markLost` | `assets/{id}/mark-lost/` | mark_asset_lost | 同上 | Asset+LostAsset | 同上 | ⚠️ 权限 |
| 维修中→完成/失败 | 07-AC repair | Repair 页 | repairAssetStore | `api/…` | `repairassets/` + assets repair* | Repair…/FSM | …Selector | RepairAsset | test_state_machine repair 路径 | ✅ |
| 找回→待发放 | 07-AC found | Found 页 | foundAssetStore | … | `assets/{id}/found` admin_actions | find_and_return | … | Asset | view 正向 | ✅ |
| 报废审批 | 07-AC approve | Damaged 审批 | damagedAssetStore | … | damaged approve/reject | DamagedAssetService | DamagedAssetSelector | DamagedAsset | TOCTOU 已修（旧#15） | ✅ |
| 仓库 CRUD | 07-AC 系统配置 | Storage 页 | storageStore | `api/storage.ts` | `storages/` | StorageService | StorageSelector | Storage | service 有；**RBAC 缺（N-2/N-9）** | ⚠️ 权限 |
| 健康检查 | OC-6 / 运维 | — | — | — | `/health/` `/ready/` | — | — | — | **无测试（N-5）** | ⚠️ |

### 2. 接口契约矩阵（§3 抽样）

| 功能 | 前端 API 函数 | 方法/路径 | 请求参数 | 响应结构 | 后端 View | Serializer | 错误码 | 一致性 |
|:-----|:-------------|:----------|:---------|:---------|:----------|:-----------|:-------|:-------|
| 登录 | `api/auth.ts` | POST `/api/v1/auth/token/` | username/password | `{code,data,message}` | auth URLs | Token serializer | 网关 code | ✅ |
| 资产分页列表 | assetStore.getList | GET `/api/v1/assets/` | `page`,`page_size` | data.`{count,results,…}` | AssetViewSet+CustomPage | List serializer | 0/业务码 | ✅ |
| 批量删除资产 | assetStore.batchDelete | POST `.../batch-delete/` | `{ids:[...]}` | `{total,success_count,fail_count,fail_items}` | AssetViewSet batch_delete | BatchDeleteSerializer | B14 逐条 | ✅（B5 基线测试） |
| 标记损坏 | assetStore | POST `.../mark-broken/` | broken_reason 等 | data=详情 | mark_broken | Detail | code=0 | ⚠️ 权限见 N-1；结构本身 ✅ |
| 健康检查 | — | GET `/health/` | — | 环形 JSON（urls 内联） | health_check | — | 200/503 | 结构非业务 envelope，**文档未见强制 §3**——[推测] 运维端点豁免，需人工确认是否要求 code 字段 |

> 跨端契约抽检：`code/data/message` 根结构、`page/page_size`、状态枚举键名与 §3 一致，**未发现单方破坏**（无 HALT）。

### 3. 状态机覆盖矩阵（CT-3）

| 状态转换 | 触发动作 | 权限 | 后端实现 | 前端入口 | 审计 | 测试（代表） | CT-3 |
|:---------|:---------|:-----|:---------|:---------|:-----|:-------------|:-----|
| in_store→in_use | outasset | admin_actions | VALID_TRANSITIONS + service | 出库页 | 有 | out_asset + state_machine | ✅ |
| in_use→recycled_pending | recycle | admin | recycle service | 回收 | :171 log_state_change | recycle tests | ✅ |
| in_store/in_use/recycled_pending→broken | mark_broken | **IsAuthenticated 缺角色（N-1）** | transitions BROKEN 源三态 | 损坏登记 | BrokenAsset 审计 | lifecycle 正向；**403 缺** | ⚠️ 路径有、权限测试缺 |
| 同上→lost | mark_lost | 同上 | LOST 源三态 | 遗失 | Lost 审计 | 同上 | ⚠️ |
| broken→repairing | repair | repair admin_actions（:69 含 repair） | BROKEN→REPAIRING | 维修单 | FSM | test_state_machine repair | ✅ |
| **lost→repairing** | （协议要求） | — | **边不存在** | — | — | — | **冲突 N-4 [HALT]** |
| repairing→recycled_pending | repair_done | admin_actions | REPAIRING 出边 | 维修完成 | FSM | 有 | ✅ |
| repairing→damaged | repair_failed | admin | 同上 | 失败 | FSM | 有 | ✅ |
| damaged→scrapped | approve | approve 权限 | DAMAGED→SCRAPPED | 审批 | 审批审计 | damaged tests | ✅ |
| damaged→broken/lost | reject | reject | reject_to_* | 审批拒绝 | FSM | reject 锚 :239+:266 | ✅ |
| lost→recycled_pending | found_and_return | found 在 admin_actions | LOST→RECYCLED_PENDING | 找回 | FSM | view 正向 | ✅ |
| scrapped | 终态 | — | `{}` | — | — | 有 | ✅ |

### 4. 权限矩阵（§4.2 关键行 + 实测）

| 角色 | 资源 | 操作 | 规范要求 | 后端实现（本轮） | 前端路由/按钮 | 测试 | 状态 |
|:-----|:-----|:-----|:---------|:-----------------|:--------------|:-----|:-----|
| regular_user | 资产 | 列表/详情 | 本部门 | Selector.apply_user_scope | 菜单可见 | isolation 多例 | ✅ |
| regular_user | 资产 | 新增/编辑/删除 | ❌ | get_permissions→admin_actions | 按钮 v-if | update/destroy 403 已有（rbac 测试） | ✅ |
| regular_user | 资产 | **mark-broken/lost** | **❌** | **落 IsAuthenticated（N-1）** | 可能仍显示 | **缺反向 403** | ❌ P1 |
| regular_user | 仓库 | **batch-create** | **❌（系统配置）** | **Mixin 未含 batch（N-2）** | — | 缺 | ❌ P1 |
| system_admin | 仓库 | CRUD | ✅ | AdminWrite→IsSystemAdmin | 管理菜单 | service 层有；view 403 缺 | ⚠️ 测试 |
| system_admin | change_status | 废弃修复 | 专属 | `IsSystemAdmin` 分支 | — | 403 asset_admin 已有（:224-247） | ✅ |
| auditor | 审计日志 | 查看 | ✅ 全部 | 审计模块 | 菜单 | 有 | ✅ |
| dept_manager | 损坏审批 | approve/reject | ✅ 本部门+下级 | damaged admin_actions | 审批页 | damaged rbac | ✅ |
| 全员 | health/ready | GET | OC-6 | urls 暴露 | — | **无（N-5）** | ⚠️ |

### 5. 规则符合性矩阵

| 规则 ID | 检查项 | 符合性 | 证据 | 备注 |
|:--------|:-------|:------:|:-----|:-----|
| CT-1 | 核心路径测试覆盖 | **√** | 后端 1274 + 前端 1812；FSM/Selector/权限正向锚充分 | 权限**反向**缺口见 N-9 |
| CT-2 | 覆盖率 ≥80/90 | **√**（覆盖率）/[PENDING]（变异） | 84.40%/96.97%/93.17%/97.89% 实测 | mutmut/stryker 见 N-8 |
| CT-3 | 状态机全路径 | **√**（实现内边）/ **[HALT]**（lost→repairing 协议冲突） | transitions 全边 + test_state_machine | N-4 待人工裁定 |
| CT-4 | 回归屏障 | **√** | 旧报告修复多带回归测试；护栏三件 PASS | 新 P1 修复须同 PR 补测 |
| CT-5 | 测试失败即阻塞 | **√** | 本轮 0 failed | 不触发阻塞 |
| CT-6 | 迁移三步验证 | **[~]** | 本轮无新增迁移；CI `migration-check.yml` 存在 | 有迁移 PR 时执行三步 |
| DR-1 | 业务逻辑唯一实现 | **√** | duplicate invariants PASS；活账本持续更新 | — |
| DR-2 | UI 原子化 | **√** | frontend invariants PASS | — |
| DR-3 | 查询统一 Selector | **√** | asset_selector 收敛 + 旧#3 已修 | — |
| DR-4 | 工具单一仓库 | **√** | utils 结构 + 旧#37 修 | N-6 logger 收敛后更完整 |
| DR-5 | 文件/函数规模 | **√**（护栏 0 超限） | function_length_guard PASS；存量 asset_view TECHNICAL_DEBT | C90 见 N-11 |
| DR-6 | 调用链/嵌套 | **√**（护栏） | 旧#43 误报已澄清 | — |
| SC-1 | 无硬编码密钥 | **√** | 根 `.gitignore:39 .env`；backend 子模块 `.env` 不在 git ls-files | 子模块路径需人工再确认一次 |
| SC-2 | CI 密钥扫描 | **[~]** | security-scan 偏依赖审计；专用密钥扫描步骤未单列 | 建议后续加 gitleaks 类步骤 |
| SC-3 | 参数化 SQL | **√** | ORM 为主；旧#33 clear_database 白名单已修 | — |
| SC-4 | 动态表名白名单 | **√** | `_validate_table_name` 已加 | — |
| SC-5~6 | 上传校验 | **[~]** | 本轮未见大文件上传主流程详录 | 需人工确认上传功能范围 |
| SC-7 | 依赖高危阻断 | **√** | security-scan.yml `--fail-on=high`（旧#8 已修） | — |
| SC-8 | 每周扫描 | **√** | cron `7 3 * * 1` | — |
| OC-1 | trace_id 透传 | **√** | `TraceIDFilter` + production json filter | — |
| OC-2 | 结构化日志 | **√**（后端）/[x]（前端 160 console） | `StructuredJSONFormatter`；前端 N-6 | 后端达标 |
| OC-3 | 敏感信息脱敏 | **√** | §4.6 六字段白名单（rules v1.12） | — |
| OC-4 | Prometheus | **√** / QPS `[~]` | metrics 端点 + 中间件存在 | 豁免合理 |
| OC-5 | DB/Redis 耗时 | **[~]** | 未见直方图专项 | 建议议 |
| OC-6 | health/ready | **√**（端点）/[x]（测试） | urls:150-151 | N-5 |
| OC-7 | 性能基准 | **[~]** | QPS<10 豁免 | 合理 |
| AR-1 | <90% 不猜 | **√** | TODO_AI_CONFIRM=0 | — |
| AR-2 | 高风险标注 | **[~]** | 7 处 AI_REVIEW_NEEDED 待清 | N-7 |
| AR-3~4 | 超时+重试+配置 | **√*** | 子代理取证外部调用集中在 webhook/通知；*完整逐调用审计需人工抽样 | *标为需抽查 |
| AR-5 | 虚拟编译自修 | **√** | 本轮先跑门禁再写报告 | — |
| Fact-1 | 不编造 | **√** | 全部结论附文件:行号或命令输出 | — |
| Style-1~3 | 写作风格 | **√** | 原创表述、短句、有主语 | — |

---

## [HALT] 汇总

| # | 触发点 | 规则依据 | 状态 |
|:--|:-------|:---------|:-----|
| H-1 | N-4：`lost → repairing` 在 Review.md / 03 需求 / `transitions.py` 三方不一致 | 根级 §1.3 状态机流转；Review.md 重点检查清单；CT-3 | **[HALT] 待人工在「改文档」与「改实现」间拍板**；在裁定前禁止修改状态机边或据此改测试 |
| — | §3 跨端契约破坏 | — | 未发现 |
| — | SC 红线（SC-1 硬编码密钥等） | — | 未发现新增 |
| — | CT-5 测试失败 | — | 本轮 0 failed，不触发 |

**除 H-1 外，无其他 [HALT]。** 报告交付不依赖 H-1 裁定。

---

## 缺失文件/信息（需人工补充）

1. **变异测试基线报告**（mutmut results / stryker report）——环境受限，见 N-8。  
2. **health/ready 行为规格**（期望状态码与依赖清单）——用于 N-5 测试断言。  
3. **SC-5/SC-6 是否在范围内**（上传功能是否存在）——本轮未取证。  
4. **N-4 裁定结果**（Review.md vs 03 文档谁为准）。  
5. 旧报告 #2/#3/#4/#8 是否授权由维护者补 ✅ 标记（本报告未改旧文件）。

---

## 最终审计票

```markdown
[审计票 - 必填项]
- 读取规范：已读 根/后端/前端 AGENTS & Rules（backend/frontend business+testing、complete-patterns、03/04/07 需求）
- CT-1[√] CT-3[√/H-1冲突] CT-5[√] — 核心测试覆盖 / 状态机全路径（实现内 √，协议 lost→repairing [HALT]） / 测试失败阻塞（0 failed）
- DR-1[√] DR-5[√] — 业务逻辑唯一实现 / 文件规模（护栏 0 超限；存量 asset_view TECHNICAL_DEBT 维持豁免）
- SC-1[√] SC-3[√] — 密钥硬编码禁止 / SQL 注入防护
- 跨端契约：未破坏
- 红线触发：[HALT] H-1（状态机协议冲突，待人工）；其余无
- 建议提交：否（先处理 N-1/N-2 权限 P1 + N-3 门禁红灯；H-1 裁定前不改状态机）

[审计票 - 自检项]
- 测试：CT-2[√覆盖率/PENDING变异] CT-4[√] CT-6[~ 无新迁移]
- DRY：DR-2[√] DR-3[√] DR-4[√] DR-6[√]
- 安全：SC-2[~] SC-4[√] SC-5[~] SC-6[~] SC-7[√] SC-8[√]
- 可观测性：OC-1[√] OC-2[√后端] OC-3[√] OC-4[~] OC-5[~] OC-6[√端点/x测试] OC-7[~]
- AI鲁棒性：AR-1[√] AR-2[~ 7处待清] AR-3[√*] AR-4[√*] AR-5[√]
- AI行为：Fact-1[√]（事实基线）
- 写作风格：Style-1[√] Style-2[√] Style-3[√]
- 覆盖率：整体 84.40%（≥80%）/ Service 96.97%（≥90%）/ 前端 93.17% / Store 97.89%
```

---

## 建议修复顺序（不改动代码，仅建议）

1. **N-1 + N-9**：`mark_broken`/`mark_lost` 入 `admin_actions` + 先红后绿 403 测试。  
2. **N-2 + N-9**：Storage `admin_actions` 补 batch 两项 + RBAC 测试。  
3. **N-3 + N-11 + N-13**：ruff/format/mypy/C90 一次门禁修复提交（避免 CI 红）。  
4. **H-1 人工裁定** → 据结果改 Review.md 或走状态机变更协议。  
5. **N-5** health/ready 冒烟；**N-8** 变异测试跑通一次；**N-6/N-7** 前端 logger 与标注清零。

---

*报告结束。生成 Agent：mimo-v2.6-flash-free | 2026-09-23*
