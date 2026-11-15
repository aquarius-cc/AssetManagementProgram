---
title: 资产管理系统 全项目审计报告
date: 2026-11-11
mode: 只读审计
scope: 全项目（架构 / 框架 / 函数 / 对象 / 代码 / 逻辑 / UI / 界面 / 治理）
skills: project-all-code-review, code-quality-check, code-explorer, ponytail, ponytail-audit, frontend-design, vue-best-practices, vue-debug-guides
status: 报告成文 / 台账终态「待修」/ 不执行修复
---

# 资产管理系统 全项目审计报告（2026-11-11）

## 0. 方法边界与阅读须知

本次为纯只读审计，**未执行任何命令**。以下工具均未运行：`codegraph status` / `codegraph explore`、`pytest --cov`、`ruff`、`mypy`、`npm run type-check`、`npm run lint`、`npm audit`、`pip-audit`、`mutmut`、`python scripts/check_file_length_guard.py --print`。全部结论来自静态源码阅读与仓库内既有台账、历史报告。

因此：

- 覆盖率、门禁绿灯、CI 结论、变异分数一律不给出数字，也不引用台账历史数字充当本次结论；
- 审计票中未执行项标记为 `[x] 未执行+原因`；
- 「回查命令」以静态 `rg` 定位为主；若 CodeGraph 索引就绪，附录 A 给出等价的 `codegraph node` 形式；
- 本报告不改动任何业务代码、规范文件与活账本，不产生「已修复」状态。

分级口径：P0 阻断/高危、P1 严重逻辑错误、P2 一般功能缺陷/规范偏离、P3 优化建议。

---

## §一 项目上下文

### 1.1 技术栈与模块边界

| 层 | 选型 | 版本 |
|:--|:--|:--|
| 前端 | Vue 3 + Element Plus + Pinia + TypeScript + Vite | 3.5 / 2.10 / 3.0 / 6.0 / 8 |
| 后端 | Django + DRF + PostgreSQL + SimpleJWT + drf-spectacular | 6.0 / 3.17 / 16 |
| 治理 | 根 `AGENTS.md` v3.7.7 + 前后端子引擎 + `Rules_Fiels/` + 活账本 + 4 护栏 + CI 工作流 | — |

后端五层：`Model → Serializer → Service → Selector → View`（`README.md:204-214`）。后端 `apps/` 五个业务域（assetmanagement / authusermanagement / notification / unregisteredasset / usermanagement），前端 `src/` 下 `api` / `components` / `composables` / `views` / `stores` / `router` / `utils` / `types` / `styles`。

资产域目录规模：`models/` 15 个 `.py`、`selectors/` 17、`serializers/` 13、`services/` 14、`views/` 19、`state_machine/` 9、`tests/` 86。前端 121 个 `.vue`、473 个 `.ts`。

### 1.2 规范基线（本次逐条对照）

`AGENTS.md` §1.4 CT-1~CT-7、§1.5 DR-1~DR-6、§1.8 活账本 G-0/G-1~G-3/G-5~G-8、§1.9 LT-1~LT-3、§3 跨端契约、§6 SC-1~SC-8、§7 OC-1~OC-7、§8 AR-1~AR-5、§9 Fact/Style；`backend-business-rules.md` v1.26（B1-B14 + 状态机 §三）；`frontend-business-rules.md` v1.7（F1-F15 + FR-1~FR-8 + 暗色模式）；`backend-testing-rules.md` / `frontend-testing-rules.md`；`Rules_Fiels/Duplicate_Codes/complete-patterns.md` v2.9.64；`BR6_file_length_ledger.md`。

### 1.3 分域清单与审查覆盖

| 分域 | 锚点 | 覆盖方式 |
|:--|:--|:--|
| 资产状态机 | `state_machine/constants.py` `AssetState`、`transitions.py` `VALID_TRANSITIONS`、`core.py` `AssetFSM`、4 个 Mixin | 逐文件读源码 + 规则表 §三比对 |
| 合同状态机 | `state_machine/contract_fsm.py`（规范 §3.1，未逐行展开） | 文档比对，标 `[部分覆盖]` |
| API 响应契约 | `utils/response_utils.py` `success_response` / `error_response` | 源码 + View 层调用分布 |
| 前端状态枚举 | `types/asset.ts` `AssetCurrentStatus`、`types/outasset.ts` | 逐键比对 |
| 鉴权 / 行级隔离 | `core/permissions.py`、`core/department_scope.py`（间接） | 权限类源码 + View 分发点 |
| 测试 | `apps/assetmanagement/tests/`、`src/**/__tests__/` | 目录与用例名静态清点，未运行 |
| 前端 UI / 交互 | `views/`、`components/`、`styles/`、`api/request.ts` | 反模式检索 + 关键文件读源码 |
| CI / 治理 | `.github/workflows/`、`scripts/`、`Rules_Fiels/` | 配置与台账静态核对 |

### 1.4 已核实合规面（规则符合性矩阵摘要）

| 规则 / 维度 | 符合性 | 证据 |
|:--|:--|:--|
| §3 响应根结构 | 通过 | `success_response` 唯一入口，键 `code/message/data`；View 层无手写响应字典旁路 |
| §3 状态枚举键名 | 通过 | 后端 8 键（`constants.py:44-51`）与前端 `AssetCurrentStatus`（`asset.ts:47-56`）逐键一致 |
| §3 分页参数 | 通过 | 双端 `page` / `page_size`；仪表盘 `limit`/`days` 属 B4 已登记豁免 |
| §3 日期格式 | 通过 | 后端 ISO 8601 +08:00；前端 `Format.ts` 东八区渲染口径见 `frontend-business-rules.md` §3.2 |
| CT-3 状态机全路径 | 通过（静态） | `test_state_machine.py` 逐路径断言；6 处直写均有前置守卫且规范登记例外 |
| DR-1 / DR-3 / 分层 | 通过（静态） | 查询收敛 `selectors/`；`services/` 14 文件均命中 `@transaction.atomic` |
| DR-5 文件规模 | 通过（台账） | BR6 活跃分区零豁免，最大 `asset_view.py` 471 逻辑行 |
| SC-1 密钥硬编码 | 通过（静态扫描） | 19 处命中全为测试夹具与 `config/settings/test.py` |
| SC-3 参数化查询 | 通过（静态核对） | 9 处 `cursor.execute` 均为固定 `SELECT 1` 或白名单标识符拼接，无用户输入拼接 |
| SC-5 / SC-6 上传 | N/A | `request.FILES` 零命中；Excel 导入为前端解析后 POST JSON，请求体上限由 `DATA_UPLOAD_MAX_MEMORY_SIZE=10MB` 约束 |
| 安全响应头 | 通过 | `production.py:71-90` 关闭 Django 侧发射，Nginx `default.conf.tpl:68-73` 唯一下发，`core/tests/test_security_headers.py` 守护 |
| F6 / F10 / F11 前端基础 | 通过 | `v-html` 0、Options API 0、组件内 `axios` 0、`.vue` 中 `from '@/api/` 仅 1 处非请求导入（`DegradedCacheBanner.vue:26`） |
| F1-F5 / 暗色 | 通过（含登记豁免） | `variables.css` 亮色 + `dark.css` 暗色 + `useChartTheme.ts`；5 类 13 个派生色按 §3.1 登记 |
| Vue 运行时健壮性 | 通过 | `RecycleAssetView.vue:159-178` 异步 watch 在 await 后做身份复核；`MainView.vue:82-90` 监听对称清理 |
| OC-6 健康端点 | 通过 | `config/urls.py:152-153` 挂载 `/health/`、`/ready/` |
| OC-4 Prometheus | 已落地 | `core/metrics.py` 请求数 / 耗时直方图 / 错误数 / 审计失败与通知死信计数 |

---

## §二 问题台账

### 2.1 台账主表

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 |
|:--|:--|:--|:--|:--|:--|:--|:--|
| F-01 | P2 | 前端交互 / DRY | `vue-assetmanagement/src/views/system/RoleManage.vue:262-269` | `handleDelete` | catch 手写三级消息提取 + `ElMessage.error` 直弹；AxiosError 场景拦截器已提示，形成双弹。活账本 B-30 登记「待修复」，本次实证仍存在 | 收编 `notifyCallerError(error, '删除失败')`，删三分支；是否补 `logError` 按 B-30 拍板 | `rg -n "response\?\.data\?\.message" vue-assetmanagement/src` |
| F-02 | P2 | 前端交互 / 生命周期 | `.../detils/UserBatchImport.vue:275`；`.../detils/DepartmentBatchImport.vue:292-294` | （按行号定位） | 导入成功后 1.5~2s 的 `router.push` 无句柄、未清理；用户在该窗口主动导航会被覆盖，组件卸载后仍执行 | 保存 timer 句柄并 `onUnmounted(clearTimeout)`；或改为成功后由用户确认跳转 | `rg -n "setTimeout" vue-assetmanagement/src/components/componentsdetails/detils` |
| F-03 | P2 | 可观测性 | `asset_management_backend/config/urls.py:54-95` | `health_check` / `ready_check` | `health_check` 的 `except Exception` 完全静默、零日志；`ready_check:121,133` 以 `%s` + `exc_info` 写异常对象，可能带 DB/Redis 连接信息 | 两处统一结构化日志（time/level/trace_id/message/module）；异常只留脱敏摘要与类型名 | `rg -n "def health_check|def ready_check|readiness check failed" asset_management_backend/config/urls.py` |
| F-04 | P2 | 权限安全 / 部署 | `core/metrics.py:82-83`；`config/settings/base.py:32`；`docker-compose.prod.yml:30` | `_metrics_request_authorized` / `metrics_view` | `METRICS_TOKEN` 默认空即放行 `/metrics/`；三份 compose 均为 `${METRICS_TOKEN:-}`。**此为 P3-10 已登记设计，不是新缺陷**，缺的是部署期强制校验 | 生产设置或部署清单增加「token 非空」fail-closed 断言；`config/prometheus.auth.yml` 已备 Bearer 抓取配置 | `rg -n "METRICS_TOKEN" asset_management_backend` |
| F-05 | P2 | 前端交互 / 信息泄露 | `vue-assetmanagement/src/api/request.ts:312-313,356` | `showStatusMessage` / `readBlobErrorData` | 500 分支把后端原始 `msg` 直接弹给用户；导出失败把网关错误页原文（截断 200 字）写入日志 | 500 改固定文案 + trace_id；日志只留 trace_id 与状态码 | `rg -n "服务器内部错误|导出错误响应非 JSON" vue-assetmanagement/src/api/request.ts` |
| F-06 | P3 | Vue 反模式 | `.../componentsdetails/AssetTypeDetails.vue:113-123`；`commoncomponents/DashboardStatCard.vue:31`；`commoncomponents/BatchImportGuideCard.vue:56` | `batchAddList` / `stats` / `notices` | 可增删列表用 `:key="index"` 且配合 `splice(index,1)`；另两处静态列表用 `idx`（影响很小） | 每行加稳定 id 作 key | `rg -n ':key="(index|i|idx)"' vue-assetmanagement/src` |
| F-07 | P3 | 文档一致性 | `asset_management_backend/config/urls.py:34-50` | `api_root` | 注释称「避免暴露后台入口」，响应体仍返回 `"admin": "/admin/"` | 删该键，或把注释改为「仅返回文档入口」 | `rg -n "admin" asset_management_backend/config/urls.py` |
| F-08 | P3 | 文档一致性 | `vue-assetmanagement/src/views/MainView.vue:123-131` | （样式注释块） | 注释称「当前为桌面端优化设计，如需移动端适配建议添加媒体查询」，模板已实现移动端抽屉（`:14-21,46-54`）与 `100dvh` | 同步注释 | `rg -n "桌面端优化|100dvh|matchMedia" vue-assetmanagement/src/views/MainView.vue` |
| F-09 | P3 | AI 鲁棒性 | `asset_management_backend/config/urls.py:80,128` | `health_check` / `ready_check` | Redis 探测 `socket_timeout=3` 硬编码且无重试（存量代码，非本次生成） | 复用统一 Redis 客户端配置，超时与重试取自配置 | `rg -n "socket_timeout" asset_management_backend/config` |
| F-10 | P3 | 过程文档漂移 | 根 `spec.md:5`；根 `tasks.md:6-39`；`vue-assetmanagement/TECHNICAL_DEBT_API_COLLECTION.md:7-11` | （文档） | 批次 8（OP-09）已落地（`core/envelope_schema.py` 存在、`dashboard_view.py:56` 已有 `http_method_names`），但 spec 仍写「待确认后执行」、tasks 全部 checkbox 未勾选；技术债清单统计的 31 处组件内直调 API 现已收口 | 归档至 `docs/Review/ExpiredAuditReport/`，或加「已归档」抬头 | `rg -n "待确认后执行|- \[ \]" spec.md tasks.md` |
| F-11 | P3 | 工作区治理 | `vue-assetmanagement/.stryker-tmp/sandbox-*` ×5；`vue-assetmanagement/everything-claude-code/` | （目录） | 变异测试沙盒残留 + 外部仓库副本，显著放大全仓搜索与索引体积；**已被 `.gitignore:18,35` 忽略，不入库** | 清目录；外仓副本移出工作区 | `git status --ignored`（需终端） |

### 2.2 影响面、优先级与建议验证方式（阶段 3 增补四要素）

| ID | 影响面 | 排序优先级 | 建议验证方式 | 台账状态 |
|:--|:--|:--|:--|:--|
| F-01 | 单文件、单 catch；`errorHandler.ts` 单出口契约已有回归锚，无跨端影响 | 批次 A 第 1 位 | `npx vitest run src/utils/__tests__/errorHandler.spec.ts`；`rg` 预期 0 命中；补一条 AxiosError 双弹断言（CT-4 先红后绿） | 待修（即 B-30） |
| F-02 | 2 个批量导入组件；只改本地 timer 生命周期，无 API 契约变化 | 批次 A 第 2 位 | Vitest + fake timers：卸载后推进时钟，断言 `router.push` 调用 0 次 | 待修 |
| F-03 | 2 个健康端点函数；生产日志格式由 `production.py:101-105` 统一接管，改动局部 | 批次 B 第 1 位 | 单测 mock `connection.cursor` / `redis` 抛错，断言日志字段齐备且不含连接串 | 待修 |
| F-04 | 部署配置层；改 production settings 会改变启动行为，属敏感配置变更 | 批次 B 单列 | 部署前自检 + `check_secret_tracking`；核对 `prometheus.auth.yml` 被启用 | 待修（**[HALT] 待人工确认**，本次不执行） |
| F-05 | 全局响应拦截器；文案与日志参数变更会影响全部页面的错误提示 | 批次 B 第 2 位 | 响应拦截器单测断言 `ElMessage.error` 文案与 `logWarn` 参数 | 待修 |
| F-06 | 3 个组件模板；仅 key 表达式变化 | 批次 A 第 3 位 | 组件测试：删除中间行后断言各行输入值归属正确 | 待修（低优先） |
| F-07 | 单函数响应体，注释与 JSON 键 | 批次 C | `curl /` 响应体断言 | 待修（低优先） |
| F-08 | 纯注释 | 批次 C | 人工复核 | 待修（低优先） |
| F-09 | 2 个健康探测点 | 批次 C | 单测注入超时配置值 | 待修（低优先，存量） |
| F-10 | 3 份文档，零代码影响 | 批次 C | 人工复核归档位置 | 待修（低优先） |
| F-11 | 本地忽略目录，仓库零影响 | 批次 C | `git status --ignored` 复核 | 待修（低优先） |

**不采纳项**：无。本次未发现需要「不采纳+理由」判定的条目。

### 2.3 资产专项维度结论（§5 查法分流）

| 维度 | 结论 | 支撑方式 | 偏差说明 |
|:--|:--|:--|:--|
| CT-3 状态机全路径 | 无未登记旁路；`VALID_TRANSITIONS` 8 态与规则表 §三一致；`scrapped` 终态空集 | 源码逐行 + `test_state_machine.py` 用例清点 | 未运行 pytest，用例「通过」与否未验证 |
| 跨端契约 4 项 | 全部一致（见 §1.4） | 源码逐键比对 | 未做运行时联调 |
| SC-1 密钥硬编码 | 19 处静态命中均为测试夹具 / test settings | `rg` 静态扫描 | CI 密钥扫描未运行 |
| SC-3 参数化查询 | 9 处 raw SQL 均为固定语句或白名单标识符 | 源码逐处判读 | — |
| SC-5 / SC-6 上传 | N/A（`request.FILES` 零命中） | `rg` 静态扫描 | 若未来新增文件端点需重新评估 |
| SC-8 依赖漏洞 | **未执行** | — | `pip-audit` / `npm audit` 未运行，以 CI `security-scan.yml` 为权威门禁 |
| OC-6 健康端点 | `/health/`、`/ready/` 存在 | `config/urls.py:152-153` | — |
| CT-2 / DR-5 / DR-6 | 覆盖率未取得；BR6 台账零豁免，最大 471 逻辑行 | 台账静态读取 | 未运行 `check_file_length_guard.py --print`，按 LT-3 本次不自行数行 |
| 前端 16 维审查 | 已覆盖 1/2/3/4/5/6/8/12/13/14/15/16；7/9/10/11 为部分覆盖 | 源码与配置静态核对 | 事务/通知/审计的动态行为、WebSocket 推送未做运行时验证 |

**§5 覆盖偏差（阶段 5 自审必须留痕）**：技能要求「§5 各维度结论有命令输出支撑」，本次因只读模式无终端，全部改为静态源码/台账证据，无一维度有命令输出。此偏差不影响结论的事实性，但**不得将本报告结论当作 CI 门禁绿灯依据**。

---

## §三 分域结论与修复建议

### 3.1 修复批次（同域合并 → 级别优先 → 影响面小者先行）

**批次 A｜前端交互三处，一次清干净**

- F-01：把 `handleDelete` catch 收编 `notifyCallerError`，与 B-29 已收编的 8 触点同构；补 `logError` 与否按 B-30 拍板。
- F-02：两个批量导入页各加 timer 句柄 + `onUnmounted` 清理，或改为用户确认跳转。
- F-06：可增删列表改稳定 id key。
- 回归：`errorHandler.spec.ts`、新增卸载/删行用例、`npm run type-check` / `lint:ci` / `format:check` / `test:coverage`（stores ≥90）。

**批次 B｜可观测性与安全**

- F-03 + F-05 先行：纯日志/文案，零契约变更。
- F-04 单列：涉及生产配置，触发根 `AGENTS.md` §1.3 与 `README.md` 安全边界的 `[HALT]`，须人工审批后才可动手。

**批次 C｜零风险清理**

- F-07~F-11 与 §3.3 清单；注释、归档、本地忽略目录，可独立提交，不触及业务代码。

### 3.2 遗留债（活账本未关闭项，非本次新发现）

| 条目 | 状态 | 说明 |
|:--|:--|:--|
| B-30 | 待修复 | 即 F-01，本次实证仍在 |
| B-31 ④ | 待修复 | `check_function_length_guard.py` / `check_file_length_guard.py` 的「非空文件不可解码 → 跳过」fail-closed 留尾面 |
| B-32 / S12 | 立项 | `fetchNotifications` 双实现收敛；账本**已裁定当前双实现非违规**，需先补齐 WS 归属、`fetchError` 归属、分页契约等架构决策；`src/__tests__/notificationDualImpl.contract.spec.ts` 为契约快照，收敛时必然变红属预期 |
| C-9 | 待产品拍板 | 暗色主色色相统一（`#4a90e2` vs `#2b5fd7`） |
| C-10 | 残余 1 处 | `MainView.vue:205` 的 `padding ... !important`，与表格样式战争无关 |
| C-13 | 已登记豁免 | `contract_view.py` / `storage_view.py` View 层直查 ORM；全局资源无部门归属，写面仍走 Service |

### 3.3 ponytail-audit 精简清单（按可删收益排序）

- `delete:` 5 个 `.stryker-tmp/sandbox-*` 完整副本，变异测试结束即无用途，直接删目录。[`vue-assetmanagement/.stryker-tmp/`]
- `delete:` 外部 `everything-claude-code/` 仓库副本（已 ignore、零引用），移出工作区。[`vue-assetmanagement/everything-claude-code/`]
- `delete:` 批次 8 的 `spec.md` / `tasks.md`（实现已落地），归入过期报告目录。[根]
- `delete:` `TECHNICAL_DEBT_API_COLLECTION.md` 的 31 处债务清单（已收口），归入过期报告目录。[`vue-assetmanagement/`]
- `shrink:` `RoleManage.vue` 三级消息提取 6 行 → `notifyCallerError(error, '删除失败')` 1 行。[`RoleManage.vue:263-268`]
- `yagni:` `api_root` 响应体中的 `"admin"` 键，与其「不暴露后台入口」注释冲突，删键即可。[`config/urls.py:49`]
- `native:` 无重大发现。超时/重试已集中 `api/config.ts`，状态机、分页、批量执行均有单一实现，未见单实现接口、单产品工厂或只做委托的包装层。

`net:` 约 −10 行生产代码、−4 类过程产物、−0 依赖（估算，未执行删除；已忽略目录不计入仓库体积）。

### 3.4 主动洞察与 SKILL 建议

1. **治理设施自身的投入产出**：根 `AGENTS.md` 373 行、活账本千余行、8 个不变量、4 个护栏脚本、CI 多工作流，B-31 ④ 恰是「护栏自身缺陷族」第四实例。规范体系的维护成本值得单列一次评估，属架构洞察而非代码缺陷。
2. **豁免机器可读性**：B-32 与 C-13 都是「经裁决保留、非违规」。若不做机器可读标记，后续按 DR-1/B12 一刀切的自动化审查会反复误报，每轮都要人工解释。建议为已裁决豁免加结构化标记。
3. **[SKILL 建议] 文档漂移巡检（doc-drift-scan）**：触发场景为每批落地后或全项目审查前；步骤为扫描根级过程文档 → 抽取其中「待办/违规统计/文件行号」断言 → 与源码现状比对 → 输出「已过期 / 仍有效」清单；预期收益是避免过期文档误导 AI 与新人（本次 F-10 需 3 份文件交叉核实）。

---

## §四 评审结论（阶段 5 报告自审）

| 检查点 | 结论 |
|:--|:--|
| 索引覆盖 | `[x]` CodeGraph 索引状态未检查（无终端），改用文件清单 + `rg` 静态定位 |
| 台账完整性 | `[√]` 11 条均具备 级别 / 类型 / file:line / symbol / 回查命令 五要素；不确定符号显式标「按行号定位」，未编造 |
| 专项覆盖 | `[x]` 偏差见 §2.3：无一维度有命令输出支撑，静态证据已逐项留痕 |
| 报告闭环 | `[√]` 本次无 P0/P1；5 条 P2 均备齐 证据 + 影响面 + 修复建议 + 建议验证方式（F-04 另标 `[HALT]`）；无不采纳项 |
| 建议可执行性 | `[√]` 每条均含 file:line / symbol 去处，修复 skill 可直接接手；F-01 已有 B-30 方案与回归锚 |
| 只读纪律 | `[√]` 本次会话未改动任何业务代码、规范文件、活账本；仅产出本报告文件 |
| 置信度 | `[√]` 报告项均为源码直证或「[推测]」显式标注，无可疑推断按事实陈述 |

**总体结论**：项目架构与规范执行度处于高位，未发现阻断性问题。建议按批次 A → B → C 推进 11 项修复，其中 F-04 须先完成 `[HALT]` 人工审批。

---

## §五 审计票

[审计票 - 必填项]

- 读取规范：已读 根 `AGENTS.md` / 前后端 `AGENTS.md` / `backend-business-rules.md` / `frontend-business-rules.md` / 两份 testing rules / 活账本 / BR6 台账 / `README.md`
- CT-1[√ 静态]（86 个后端测试文件 + 前端 `__tests__` 全目录，核心路径有对应用例）CT-3[√ 静态]（逐路径断言 + 6 处旁路前置守卫）CT-5[x] 未执行+只读会话无终端，未运行任何测试
- CT-7[x] 未执行+未做 `pip list` 与 `requirements/dev.txt` / `package.json` 版本对齐，覆盖率与门禁数字一律不引用。**【2026-11-15 标注：取数证据已由 M-21（Q3=B）补齐——CI 现于覆盖率 step 前打印生效版本（后端 `pip show` / 前端 `npm ls --depth=0`），权威数字以 CI run 的 $GITHUB_STEP_SUMMARY 为准，绿态 run https://github.com/aquarius-cc/AssetManagementProgram/actions/runs/43623471892 】**
- DR-1[√ 静态] DR-5[√ 静态]（BR6 活跃台账零豁免，最大 471 逻辑行）
- SC-1[√ 静态]（19 处命中全为测试夹具 / test settings）SC-3[√ 静态]（9 处 raw SQL 均为固定语句或白名单标识符）
- 跨端契约：未破坏（4 项逐条静态核对）
- 红线触发：`[HALT]` 1 项待确认（F-04 生产 `METRICS_TOKEN` 配置变更），本次未执行
- 建议提交：不适用（仅产出报告文件，零业务代码改动）

[审计票 - 自检项]

- 测试：CT-2[x] 未执行+无覆盖率数字 CT-4[x] 未执行+修复建议已附回归用例要求 CT-6[x] 未执行+本次无迁移变更
- DRY：DR-2[√ 静态] DR-3[√ 静态] DR-4[√ 静态] DR-6[√ 静态]
- 安全：SC-2[x] 未执行+CI 密钥扫描未跑 SC-4[√ 静态] SC-5/SC-6[N/A]（`request.FILES` 零命中）SC-7[x] 未执行+双 audit 未跑 SC-8[x] 未执行
- 可观测性：OC-1[√ 静态]（`X-Request-ID` 前端生成、后端透传）OC-2[√ 静态，F-03 局部缺口] OC-3[√ 静态，F-03/F-05 为疑点] OC-4[~] OC-5[~] OC-6[√] OC-7[~]
- AI鲁棒性：AR-1[√] AR-2[√ 静态] AR-3/AR-4[疑点 F-09] AR-5[x] 未执行+未做虚拟编译
- AI行为：Fact-1[√]（未执行项全部显式标注）
- 写作风格：Style-1~Style-3[√]
- 覆盖率：整体 未取得 / 核心 未取得（禁止以台账历史数字充当本次结论）
- 专项结论：状态机旁路 6 处（均为已登记例外）/ 契约 4 项一致 / SC 分流结果见 §2.3

---

## §六 可验证性说明（Fact-2）

- `[可验证]` 后端 `AssetState` 与前端 `AssetCurrentStatus` 8 键完全一致、6 处状态直写均有前置守卫 — 依据：`state_machine/constants.py:44-51`、`types/asset.ts:47-56`、`out_recycle.py` / `scrapping.py` / `unregistered.py` 源码。
- `[可验证]` 前端组件层已无直接 API 调用、无 `v-html` / Options API / 组件内 axios — 依据：本次对 `src/**/*.vue` 的静态检索，命中 0 或仅 1 处非请求导入。
- `[可验证]` F-01 与 F-02 的代码形态仍存在于当前工作区 — 依据：`RoleManage.vue:262-269`、`UserBatchImport.vue:275`、`DepartmentBatchImport.vue:292-294`。
- `[可验证]` 批次 8（OP-09）已落地 — 依据：`core/envelope_schema.py` 存在、`dashboard_view.py:56` 已有 `http_method_names = ["get","head","options"]`，而 `spec.md:5` 与 `tasks.md` 仍为未执行态。
- `[推测]` F-04 在真实生产环境存在无鉴权抓取面 — 原因：仅能确认默认值与 compose 模板为空，无法读取实际部署环境变量；活账本亦把「生产 env 设真实 `METRICS_TOKEN`」记为待办，故标为部署期风险而非既成漏洞。
- `[推测]` F-06 会造成可见的输入错位 — 原因：`v-model` 绑定对象属性，重渲染会刷新值；风险主要在组件内部状态（焦点、IME 组合输入），需组件测试复现，故定 P3。

---

## 附录 A：CodeGraph 等价回查命令（索引就绪后使用）

本次未建立索引，下列命令**未执行**，仅供 craft / CI 环境补齐证据链：

| 台账 ID | 等价命令 |
|:--|:--|
| F-01 | `codegraph node handleDelete -f vue-assetmanagement/src/views/system/RoleManage.vue` |
| F-03 / F-09 | `codegraph node health_check -f asset_management_backend/config/urls.py`、`codegraph node ready_check` |
| F-04 | `codegraph node _metrics_request_authorized`、`codegraph callers metrics_view` |
| F-05 | `codegraph node showStatusMessage`、`codegraph node readBlobErrorData` |
| F-07 | `codegraph node api_root` |
| 状态机复核 | `codegraph node VALID_TRANSITIONS`、`codegraph node AssetState`、`codegraph node AssetFSM` |
| 契约复核 | `codegraph node success_response`、`codegraph node AssetCurrentStatus` |

## 附录 B：本次未执行但应由 CI 复核的门禁清单

`pytest --cov=. --cov-fail-under=80 -v`；`pytest --cov=apps.assetmanagement.services --cov-fail-under=90 -v`；`npm run test:coverage`（整体 80 / `src/stores/**` 90）；`mutmut run`（≥80 且 ≥ `mutmut-baseline.json`）；`npm run test:mutate`（≥80）；`ruff check .` / `ruff format --check .` / `mypy . --strict`；`npm run type-check` / `lint:ci` / `format:check`；`python scripts/check_file_length_guard.py --print` / `check_duplicate_invariants.py` / `check_frontend_invariants.py`；`pip-audit` / `npm audit`。以上结论一律以 `requirements/dev.txt` 与 `package.json` 声明版本为准（CT-7）。
