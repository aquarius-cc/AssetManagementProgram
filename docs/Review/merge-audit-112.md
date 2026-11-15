---
title: 三份 CodeGraph 审计报告融合报告
date: 2026-11-12
mode: 融合审核（对比 → 取证仲裁 → 合并台账 → 修复路线）
sources:
  - docs/Review/atomcode-codegraph-audit-2026-11-11.md（下称「AtomCode 报告」，台账 A-01~A-08）
  - docs/Review/main-codegraph-audit-2026-11-11.md（下称「Main 报告」，台账 F-01~F-11）
  - docs/Review/codegraph-audit-20261111.md（下称「CG 报告」，台账 F-01~F-05）
status: 融合成文 / 台账终态「待修」/ 不执行修复
---

# 三份审计报告融合报告（merge-audit-112）

## 一、三报告对比总览

### 1.1 方法与证据等级对比

| 维度 | AtomCode 报告 | Main 报告 | CG 报告 |
|:--|:--|:--|:--|
| 证据方式 | CodeGraph 索引 + 命令输出（pytest 覆盖率实测、护栏 --print、rg） | **纯静态阅读，零命令执行**（自declared） | CodeGraph 索引 + 部分命令（vue-tsc 通过、状态机抽样 pytest 全绿；全量覆盖率未跑完） |
| 发现面 | 后端可观测性 + 前端类型/UI 重复（DRY 向） | 前端交互/生命周期 + 后端健康端点/指标安全 + 文档漂移 + 工作区治理 | 前端设计令牌 + 死代码 + 文档漂移 + 覆盖率门禁 |
| P0/P1 | 0 条 | 0 条 | 0 条 |
| 台账 ID 前缀 | A-xx | F-xx（**与 CG 报告撞前缀**） | F-xx（**与 Main 报告撞前缀**） |
| 不采纳项 | A-01（FSM 兜底完整，自审核销） | 无 | 无 |

三份报告在**状态机（CT-3）、跨端契约 4 项、SC-1/SC-3/SC-5/SC-6、OC-6 健康端点、DR-5 规模护栏**五个维度结论一致：全部合规、无未登记旁路、无 P0/P1。融合时这些维度不再重复展开，仅保留登记豁免引用。

### 1.2 冲突清单与仲裁（本次取证复核）

| # | 冲突点 | 各方表述 | 仲裁结论（附本次取证） |
|:--|:--|:--|:--|
| C-1 | 前端类型重复判定 | CG 报告 §3.4 称「前端类型集中于 `types/`，未见重复定义」；AtomCode 报告 A-05 称 `SearchForm` 接口存在三份拷贝 | **采信 AtomCode**。本次 `rg -n "interface SearchForm"` 实测命中 3 处（ScrapableAssetsSearch.vue:164 / RecyclableOutAssetsSearch.vue:176 / WastedAssetsSearch.vue:158）。CG 报告该结论系抽查面不足，已过时。→ M-14 |
| C-2 | 覆盖率数字口径 | AtomCode 报告给出本机实测 90.28%；Main 报告按 CT-7 纪律拒绝引用任何数字；CG 报告标 `[PENDING]` | **按 CT-7 归一**：本机数字与 CI 声明版本是否一致未核实，只能作讨论中间量，不得充当 CI 基线；权威覆盖率以 `ci.yml` 为准。→ 治理项 M-21（✅ 已关闭 2026-11-15：M-21 落地，权威口径归一为 CI run `$GITHUB_STEP_SUMMARY`，红绿直证 PR #2，三份源报告已分别标注） |
| C-3 | 台账 ID 撞前缀 | Main 报告与 CG 报告各自使用 F-01/F-02 等相同编号、语义完全不同 | 融合表**重新编号为 M-xx**，每条附「溯源」列保留原始 ID，禁止跨报告直接引用 F-xx 造成歧义 |
| C-4 | 暗色主色 C-9 归属 | CG 报告将其列为本次新发现 F-02（P2 待产品决策）；Main 报告将其识别为**遗留债 C-9**（活账本已有条目） | **采信 Main**：C-9 为既有台账条目，CG 报告属重复发现。合并为同一条并标注「需产品拍板，工程批次不阻塞」。→ M-07 |
| C-5 | SC-8 / 双 audit | 三份报告均称「本地未跑/未装，以 CI `security-scan.yml` 为权威」 | 无冲突，三份口径一致，直接归一：不再列为问题条目，仅作 CI 依赖项备注 |
| C-6 | 上传面 SC-5/SC-6 | AtomCode 与 Main、CG 均判 N/A（`request.FILES` 零命中、Excel 为前端解析后 POST JSON） | 无冲突，归一为 N/A；若未来新增文件端点需重新评估（沿用 Main 报告偏差说明） |

### 1.3 三报告问题分布对比

| 报告 | 有效待修条目 | P2 | P3 | 特点 |
|:--|:--|:--|:--|:--|
| AtomCode | 7（A-01 已销） | 5 | 2 | 唯一覆盖后端审计链路指标与前端 DRY 类型/样式重复 |
| Main | 11 | 5 | 6 | 唯一覆盖部署安全（METRICS_TOKEN）、生命周期泄漏、信息泄露、工作区治理 |
| CG | 5 | 2 | 3 | 唯一覆盖设计令牌体系与覆盖率门禁固化 |

**互补性结论**：三份报告发现面几乎不重叠（冲突仅 C-1/C-4 两处），融合后台账覆盖面完整，共 **21 条有效待修项**（去重后），P2 共 11 条、P3 共 10 条，P0/P1 仍为 0。

---

## 二、融合问题台账（M-01 ~ M-21）

> 编号规则：M-xx 为本次融合新编号；「溯源」列保留原报告 ID。级别沿用原报告判定（冲突项按 §1.2 仲裁后取值）。除标注外，每条 file:line 均经原报告给出，关键冲突点已由本次会话复核。

### 2.1 主表

| ID | 级别 | 类型 | 域 | file:line | symbol | 描述 | 溯源 | 状态 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| M-01 | P2 | 可观测性 | 后端 | `apps/assetmanagement/audit.py:350` | audit 装饰器 | `except Exception` 仅 logger.error 后吞掉；`:103` strict 分支已有 `AUDIT_WRITE_FAILED` 计数，此分支缺失，分渠道计数口径不齐 | AtomCode A-02 | ✅ 已修复（2026-11-12，批次 2/M-01，BF-189：接 `core/audit_failure` `asset_audit_decorator` 渠道） |
| M-02 | P3 | 可观测性 | 后端 | `authusermanagement/audit_adapter.py:33,49,65`；`usermanagement/audit_helper.py:27` | 审计适配器 | 注册/登录/登出宽吞仅日志、无指标，与 M-01 同型 | AtomCode A-03 | ✅ 已修复（2026-11-12，批次 2/M-02，BF-189：三方法 + audit_helper 薄委托 `core/audit_failure` `generic_audit_dispatch` 渠道） |
| M-03 | P2 | 可观测性/敏感信息 | 后端 | `config/urls.py:54-95,121,133` | `health_check`/`ready_check` | `health_check` 异常完全静默零日志；`ready_check` 以 `%s`+`exc_info` 写异常对象，可能带出 DB/Redis 连接信息 | Main F-03 | ✅ 已修复（2026-11-12，批次 2/M-03，BF-189：`core/health_probe` 唯一探测实现，脱敏日志无异常对象；`audit.py:81,105`/`audit_service.py:70` 同型泄露面另挂 D-14） |
| M-04 | P3 | AI 鲁棒性 | 后端 | `config/urls.py:80,128` | 健康探测 | Redis 探测 `socket_timeout=3` 硬编码且无重试（存量代码，AR-3/AR-4 疑点） | Main F-09 | ✅ 已修复（2026-11-12，批次 2/M-04，BF-189：`HEALTH_REDIS_*` 配置化 + `max(0,n)` 兜底；编排层重试豁免，DB 侧/编排侧 urlopen() 留 D-13） |
| M-05 | P2 | 权限安全/部署 | 后端 | `core/metrics.py:81-83`；`settings/base.py:32`；`docker-compose.prod.yml:30` | `_metrics_request_authorized` | `METRICS_TOKEN` 默认空即放行 `/metrics/`（P3-10 已登记设计，非新缺陷）；缺的是**部署期 token 非空 fail-closed 断言** | Main F-04 | ✅ 仓内已落地（2026-11-12，批次 3，BF-190：prod `:?` fail-closed + BR-D1 规则③④ + `--preflight` 自检 + §4.3 六步清单）**部署六步待生产环境**（开发环境无 docker/生产 host，[推测] 3 项待部署期事实化） |
| M-06 | P2 | 设计令牌 | 前端 | `src/store/app.ts:99-103`；`src/styles/variables.css`（无 `--el-color-primary` 定义） | `initAppState` | 亮色主题未在 CSS 定义 `--el-color-primary`，仅当 localStorage 有值时由 JS 设置；新用户/清缓存首屏 EP 组件回落默认 `#409eff`，与品牌主色并存双蓝 | CG F-01 | 已修（2026-11-12，批次1/M-06：`:root` 映射 `--el-color-primary`/`-rgb`，暗色改引令牌，删 `#409eff` 回退；4 例静态断言） |
| M-07 | P2 | 设计令牌 | 前端 | `variables.css:4-7,94-96,134-137`；`dark.css:10` | `--color-primary*` | 亮色派生色仍为 EP 默认蓝族，暗色整体换 `#4a90e2`，同一主色概念多源异色；即活账本 **C-9**，需产品拍板 | CG F-02 + Main 遗留债 C-9（仲裁 C-4） | 已关闭（2026-11-15：工程 BF-192 色阶表 + 设计签字落账；D1-D7 冻结口径执行） |
| M-08 | P3 | 状态一致性/死代码 | 前端 | `src/stores/app.ts:117-137` | `resetAppState` | 重置未移除 `html.dark`、未复位 `--el-color-primary`、未更新 `document.title`；且全仓仅测试调用，属未接线公开 API | CG F-03 | 待修（低优先） |
| M-09 | P2 | 前端交互/DRY | 前端 | `src/views/system/RoleManage.vue:262-269` | `handleDelete` | catch 手写三级消息提取 + `ElMessage.error` 直弹，AxiosError 场景与拦截器双弹；活账本 **B-30** 已登记待修，本次实证仍在（本次复核 `:268` 命中） | Main F-01 | 已修（2026-11-12，批次1/M-09：收编单出口 `notifyCallerError` + `logError`，B-30 关闭；先红后绿） |
| M-10 | P2 | 前端生命周期 | 前端 | `detils/UserBatchImport.vue:275`；`detils/DepartmentBatchImport.vue:292-294` | 导入成功跳转 | 1.5~2s `router.push` 无句柄未清理，用户主动导航会被覆盖、组件卸载后仍执行（本次复核两文件 `setTimeout` 均命中） | Main F-02 | 已修（2026-11-12，批次1/M-10：新增 `useDelayedRoute`，三钩子清理 + 5 例/2 锚点，B-37 关闭） |
| M-11 | P3 | Vue 反模式 | 前端 | `AssetTypeDetails.vue:113-123`；`DashboardStatCard.vue:31`；`BatchImportGuideCard.vue:56` | v-for key | 可增删列表用 `:key="index"` 配 `splice(index,1)` 有状态错位风险；另两处静态列表影响很小 | Main F-06 | 待修（低优先） |
| M-12 | P2 | 前端交互/信息泄露 | 前端 | `src/api/request.ts:312-313,356` | `showStatusMessage`/`readBlobErrorData` | 500 分支把后端原始 `msg` 直弹用户；导出失败把网关错误页原文（截 200 字）写日志 | Main F-05 | 已修（2026-11-12，批次1/M-12：500 固定文案 + trace 前 8 位、完整值入结构化日志；网关原文改 `{content_type, body_length}`；B-33 已关闭——5xx 全族固定文案 + 追踪号，4xx 保留字段级提示（2026-11-12） |
| M-13 | P2 | 类型位置（F15） | 前端 | `DashboardStatCard.vue:44`；`SelectedRecordsTable.vue:28` | `StatItem`/`SelectedRecord` | 跨组件导出的 interface 定义在组件内，违反 F15（应放 `/src/types`） | AtomCode A-04 | 待修 |
| M-14 | P2 | DRY 重复类型（FR-2/DR-2） | 前端 | `ScrapableAssetsSearch.vue:164`；`RecyclableOutAssetsSearch.vue:176`；`WastedAssetsSearch.vue:158` | `SearchForm` | 同一搜索表单接口第 3 份拷贝（本次 rg 取证确认，仲裁 C-1） | AtomCode A-05 | 待修 |
| M-15 | P2 | 重复 UI 面（FR-1/DR-2） | 前端 | `ContactsView.vue:79,88`；`NotificationList.vue:204,259`；`system/AuthUserManage.vue:42,97`；`system/RoleManage.vue` | 页面级 | 4 页面手写 el-table + el-pagination，绕过 CommonList/SmartListContainer 公共表格面 | AtomCode A-06 | 待修（先评估接入成本） |
| M-16 | P2 | 样式覆盖重复（F12） | 前端 | `AssetTypeForm.vue:252,262`；`DepartmentForm.vue:291,303`；`StorageForm.vue:279,291`；`LogIn.vue:401-410`；`CommonList.vue:416-451` | `:deep(.el-input__wrapper…)` | EP 输入框 :deep 覆盖在多组件逐字重复，应收敛全局样式 | AtomCode A-07 | 待修 |
| M-17 | P3 | 文档漂移 | 文档 | 根 `spec.md:5`；根 `tasks.md:6-39`；`vue-assetmanagement/TECHNICAL_DEBT_API_COLLECTION.md:7-11`；`GuideDocumentation/设计审计核验.md:64-67` | 过程文档 | 批次 8（OP-09）已落地但 spec/tasks 仍「待确认后执行」、checkbox 未勾；技术债 31 处清单已收口；设计核验文档 `!important` 63 处数字失真（实测 8 处） | Main F-10 + CG F-04（同型合并） | 待修（低优先） |
| M-18 | P3 | 文档一致性 | 后端 | `config/urls.py:34-50` | `api_root` | 注释称「避免暴露后台入口」，响应体仍返回 `"admin": "/admin/"` | Main F-07 | 待修（低优先） |
| M-19 | P3 | 注释漂移 | 前端 | `src/views/MainView.vue:123-131` | 样式注释块 | 注释称「桌面端优化设计」，模板已实现移动端抽屉与 `100dvh` | Main F-08 | 待修（低优先） |
| M-20 | P3 | 工作区治理 | 治理 | `vue-assetmanagement/.stryker-tmp/sandbox-*` ×5；`vue-assetmanagement/everything-claude-code/` | 本地目录 | 变异测试沙盒残留 + 外部仓库副本，放大索引体积；已被 `.gitignore` 忽略不入库 | Main F-11 | 待修（本地清理） |
| M-21 | P3 | 测试门禁 | CI | `ci.yml`（覆盖率门禁固化点） | — | 覆盖率权威数字本地未取得/未与 CI 版本对齐（仲裁 C-2），CI 就绪前按 CT-2 标 `[PENDING]` | CG F-05 + 三报告口径归一 | ✅ 已修复（2026-11-15，批次 5 / M-21，BF-194：ci.yml 证据 step + 断言七 + PR #2 红绿直证，`[PENDING]` 撤销，AGENTS.md v3.7.8 §1.4 门禁状态订正） |

### 2.2 不采纳项（融合后维持原判）

| 原条目 | 溯源 | 不采纳理由 |
|:--|:--|:--|
| 状态机 `_resolve_revert_target` 空值 500 疑点 | AtomCode A-01 | 自审已复核：FSM 两侧均有兜底（`cancel_damaged` scrapping.py:71-78 空值→recycled_pending；`reject_to_original` docstring 明示兜底）。无缺陷。 |

### 2.3 三报告一致的合规面（不再展开，留档引用）

- **CT-3 状态机**：`VALID_TRANSITIONS` 8 态与规则表逐条一致；直写旁路 0（6 处登记豁免均有前置守卫）；`test_state_machine.py` 覆盖各边（AtomCode 全量 2442 passed / CG 抽样全绿 / Main 静态逐行）。
- **跨端契约 4 项**：响应根结构（`success_response` 唯一入口）、状态枚举 8 键、分页 `page/page_size`、日期 ISO 8601 +08:00 —— 全部一致。
- **SC-1/SC-3**：密钥命中均为测试夹具；raw SQL 均为固定语句或白名单标识符。
- **SC-5/SC-6**：无文件上传落盘端点，N/A。
- **OC-6**：`/health`、`/ready` 存在（但日志质量缺口见 M-03）。
- **DR-5/DR-6**：后端护栏 --print 全 ok（最大 `asset_view.py` 471~485 逻辑行，余量偏薄，后续新增 action 前需先拆分）；前端 FR-6/FR-8 全 ok。

---

## 三、修复建议与建议验证方式

| ID | 修复建议 | 建议验证方式 |
|:--|:--|:--|
| M-01 | 补 `AUDIT_WRITE_FAILED` 分渠道计数（与 `:103` strict 分支及 unregistered_adapter/unregistered_safe_call 同口径） | 单测：mock 写日志抛异常，断言计数递增且主流程不抛 |
| M-02 | 同 M-01 口径，4 处包装点统一 | 同 M-01，归并同批用例 |
| M-03 | 两端点统一结构化日志（time/level/trace_id/message/module）；异常只留脱敏摘要与类型名，不带连接串 | 单测 mock `connection.cursor`/`redis` 抛错，断言日志字段齐备且不含连接信息 |
| M-04 | 复用统一 Redis 客户端配置，超时与重试取自配置（AR-3/AR-4 收口） | 单测注入超时配置值 |
| M-05 | 生产设置或部署清单增加「METRICS_TOKEN 非空」fail-closed 断言；`config/prometheus.auth.yml` 已备 Bearer 抓取配置。**改生产配置属敏感变更，先走 [HALT] 人工审批**（→ 已批准并落地，BF-190：`docker-compose.prod.yml:30` `:?` 插值 + `check_deploy_invariants.py` 规则③④ + `verify_metrics_deploy.py --preflight` + `08-部署与环境配置.md §4.3` 六步清单） | 部署前自检 + `check_secret_tracking`；核对 Bearer 配置启用（→ 仓内已由 `test_check_deploy_invariants.py` 15 用例 + `test_verify_metrics_deploy.py` 16 用例直证；实机部署六步待生产环境） |
| M-06 | `variables.css` 的 `:root` 增加 `--el-color-primary: var(--color-primary)`（含 light-3/5/7/8/9 派生）；或 `initAppState` 无存储时也调用 `setPrimaryColor(DEFAULT)` | vue-tsc + 首屏截图对比（清 localStorage 场景）；组件测试断言 computed 主色 |
| M-07 | 以品牌主色生成 tint/shade 阶梯（或 `color-mix`）；暗色若需提亮须单独定义并显式登记。**先产品拍板再动手** | 视觉走查 + scrollbarTokens 类等值断言 |
| M-08 | `resetAppState` 复用 `setTheme`/`setPrimaryColor` 完成 DOM 副作用，或删除未使用方法（二选一，建议前者） | store 单测：重置后断言 `html.dark`/CSS 变量/title 均复位 |
| M-09 | catch 收编 `notifyCallerError(error, '删除失败')`，删三级消息提取；是否补 `logError` 按 B-30 拍板 | `errorHandler.spec.ts` + 补一条 AxiosError 双弹断言（CT-4 先红后绿）；rg 三级提取预期 0 命中 |
| M-10 | 保存 timer 句柄并 `onUnmounted(clearTimeout)`；或改为成功后用户确认跳转 | Vitest + fake timers：卸载后推进时钟，断言 `router.push` 调用 0 次 |
| M-11 | 可增删列表每行加稳定 id 作 key；静态列表两处顺带 | 组件测试：删除中间行后断言各行输入值归属正确 |
| M-12 | 500 分支改固定文案 + trace_id；导出失败日志只留 trace_id 与状态码 | 响应拦截器单测断言 `ElMessage.error` 文案与日志参数 |
| M-13 | `StatItem`/`SelectedRecord` 迁移至 `src/types/*.ts`，组件改 import；组件私有类型（AtomCode A-08）不强制、随批处理 | `grep "export interface" src/components` 预期 0 命中；vue-tsc + vitest |
| M-14 | `SearchForm` 收敛到 `src/types` 或共享 composable，三组件改 import | `rg "interface SearchForm"` 预期 0 命中；vue-tsc |
| M-15 | 逐页评估接入 CommonList 成本，能接则接；不能接的至少收敛分页块 | vitest 快照 + 人工 UI 走查 |
| M-16 | 抽取全局 `.form-input` 覆盖类至 `styles/`，组件内删除拷贝 | 视觉走查 + 等值断言模式 |
| M-17 | spec.md/tasks.md/TECHNICAL_DEBT_API_COLLECTION.md 归档至 `docs/Review/ExpiredAuditReport/` 或加「已归档」抬头；设计审计核验.md 更新 `!important` 统计或标「已收敛」 | 人工复核归档位置与统计数字 |
| M-18 | 删 `"admin"` 键，或把注释改为「仅返回文档入口」 | `curl /` 响应体断言 |
| M-19 | 同步 MainView 注释与实际移动端实现 | 人工复核 |
| M-20 | 删 5 个 sandbox-* 目录；外仓副本移出工作区 | `git status --ignored` 复核 |
| M-21 | 在 `ci.yml` 固化覆盖率门禁（整体 80 / Service 90 / stores 90），并确保按 `requirements/dev.txt` 与 `package.json` 声明版本取数（CT-7） | CI run 直证覆盖率 job 生效 |

---

## 四、修复分类与顺序建议

### 4.1 排序原则

1. **影响面小、回归快者优先**（前端交互/令牌速修批次，每条回归面单文件级）；
2. **同域同型合并一批**（后端可观测性 M-01/M-02 同口径；前端 DRY 四条同属重构面）；
3. **敏感配置单列且前置审批**（M-05 触发 [HALT]，不与任何工程批次混跑）;
4. **外部依赖项不阻塞工程批次**（M-07 产品拍板、M-21 CI 固化，异步推进）;
5. **DRY 重构放后**：M-13~M-16 回归面大（跨组件/跨页面），等速修批次稳定后再动，避免同文件冲突（M-09 与 M-15 都触及 RoleManage.vue，必须先 M-09 后 M-15）。

### 4.2 批次划分（建议执行顺序）

| 批次 | 内容 | 级别 | 理由 | 回归门槛 |
|:--|:--|:--|:--|:--|
| **批次 1：前端速修**（第 1 顺位） | M-06 → M-09 → M-10 → M-12 | P2 | 均为单文件/双文件小改动；M-06 一处 CSS 即消除首屏双蓝；M-09 有 B-30 方案与回归锚 | `errorHandler.spec.ts`、fake timers 用例、拦截器单测、`type-check`/`lint:ci`/`format:check` |
| **批次 2：后端可观测性**（第 2 顺位） | M-01 + M-02 → M-03 + M-04 | P2/P3 | 同口径同批；M-03/M-04 同文件顺带；零契约变更 | 单测断言计数与日志字段；无连接串泄露断言 |
| **批次 3：安全部署配置**（**前置 [HALT]**，可与批次 2 并行审批、批准后单列执行） | M-05 | P2 | 生产配置变更属根 AGENTS §1.3 敏感变更，必须人工审批后动手 | 部署自检 + Bearer 配置核对 |
| **批次 4：前端 DRY 重构**（第 3 顺位，批次 1 稳定后） | M-14 → M-13 → M-16 → M-08 → M-11 → M-15 | P2/P3 | 先类型收敛（机械迁移）→ 再样式收敛 → M-08/M-11 顺带 → M-15 成本最高放最后且需先评估 | vue-tsc + vitest 快照 + UI 走查；DR-2 相关 rg 断言 0 命中 |
| **批次 5：文档与清理**（第 4 顺位，零代码随时插空） | M-17 → M-18 → M-19 → M-20 | P3 | 不触及业务代码，可独立提交 | 人工复核 |
| **治理异步项**（不阻塞任何批次） | M-07（✅ 工程侧已完成 2026-11-15，BF-192；设计签字待办不阻塞）、M-21（✅ 已关闭 2026-11-15，CI 配置独立 PR #2，BF-194） | P2/P3 | 外部依赖（产品决策 / CI 基线） | M-07 拍板后视觉走查（运行时直证 206/206）；M-21 CI 直证（PR #2 绿 43623471892） |

### 4.3 关键顺序依赖（防踩线）

- **M-09 必须先于 M-15**：两者都修改 `RoleManage.vue`，先收敛错误处理再评估表格接入，避免同文件两批改动互相冲突。
- **M-06 建议先于 M-07 落地**：M-06 补 CSS 变量是 M-07 阶梯统一的地基，无论 M-07 拍板结果如何，M-06 的兜底修复都成立。
- **M-01 与 M-02 必须同批**：分渠道计数口径若只改一处，口径反而进一步不齐。
- **M-17 与 M-21 有先后语义**：先归档过期文档（M-17）再固化覆盖率门禁（M-21），避免文档中「待执行」表述与门禁落地状态再次漂移。（2026-11-15 留痕：M-21 已固化；M-17 归档项仍未销项，「待执行」表述的漂移面收窄至 M-17 未销项部分。）

---

## 五、遗留债（活账本既有条目，非本次新发现，沿用 Main 报告清点）

| 条目 | 状态 | 与融合台账关系 |
|:--|:--|:--|
| B-30 | 待修复 | 即 M-09 |
| B-31 ④ | 待修复 | 护栏自身 fail-closed 留尾面（融合台账不含，另行走护栏修复通道） |
| B-32 / S12 | 立项 | `fetchNotifications` 双实现收敛，需先补架构决策（契约快照收敛时变红属预期） |
| C-9 | 已签关闭 | 即 M-07（2026-11-15 工程收口 + 设计签字） |
| C-10 | 残余 1 处 | `MainView.vue:205` 的 `padding !important`（M-17 更新文档统计时一并覆盖口径） |
| C-13 | 已登记豁免 | View 层直查 ORM 豁免，无需动作 |

---

## 六、融合结论

- 三份报告互补性强、冲突仅 2 处实质分歧（C-1 类型重复判定、C-4 暗色主色归属），均已凭本次取证仲裁；覆盖率口径冲突（C-2）按 CT-7 归一为「以 CI 为权威」。
- 融合台账 **21 条有效待修项**（P2 × 11 / P3 × 10），P0/P1 为 0；另有 1 条不采纳项（A-01）维持原判。
- 建议执行顺序：**批次 1（前端速修）→ 批次 2（后端可观测性）→ 批次 3（M-05，[HALT] 前置）→ 批次 4（前端 DRY 重构）→ 批次 5（文档清理）**，治理异步项（M-07/M-21）并行推进。
- 本报告为融合审核产物，未修改任何业务代码、规范文件与活账本；所有行号引用以三份源报告为准，关键冲突点已由本次会话 rg 直证。

[审计票 - 必填项]
- 读取规范：已读根 AGENTS.md（融合审核只读，未触碰业务代码）
- CT-1[~] 本报告不含代码变更，测试义务随各批次执行时承担 CT-3[~] 三报告一致结论已归一留档 CT-5[√] 无测试失败可阻塞项 CT-7[√] 覆盖率数字一律未引用为基线（C-2 仲裁）
- DR-1[√] 冲突条目已合并、无重复立项 DR-5[√] 零代码
- SC-1[√] SC-3[√] 零代码、无新增查询
- 跨端契约：未破坏
- 红线触发：无（M-05 的 [HALT] 为源报告既有标记，已显式转入批次 3 前置条件）
- 建议提交：是（仅本报告文件）

[审计票 - 自检项]
- Fact-1[√]（冲突点均经 rg 直证后仲裁；未复核行号沿用源报告并显式标注）
- Style-1~Style-3[√]
- 未执行项留痕：各条修复建议的验证命令均未执行（属各批次义务）；M-15 接入成本未评估（批次 4 前置动作）
