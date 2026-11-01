# CodeGraph 全项目审计报告（前端 + 后端）

> 执行引擎：AtomCode（project-all-code-review 审计模式 v1.2.0 + code-quality-check + code-reviewer）
> 日期：2026-10-31 | 索引：codegraph status up to date（1023 files / 18224 nodes / 41491 edges）
> 性质：**纯审计，只读，未改动任何业务代码**。修复执行归 bug-surgical-fix / rigorous-dev。

---

## §一 项目上下文（阶段 1 探索与结构报告）

### 1.1 技术栈与模块边界

| 层级 | 技术 | 位置 |
|:--|:--|:--|
| 前端 | Vue 3.5 + TS 6.0 + Element Plus + Pinia + Vite 8 | `vue-assetmanagement/src/`（components / composables / views / stores / router / utils / types） |
| 后端 | Django 6.0 + DRF 3.16 + PostgreSQL 16 + SimpleJWT | `asset_management_backend/`（apps/ 5 app + core/ + utils/ + config/） |
| API 文档 | drf-spectacular（基线 `api-schema-baseline.json`） | 后端根 |
| 状态机 | `apps/assetmanagement/state_machine/`（AssetFSM + ContractFSM） | 后端 |
| 测试 | pytest（后端）/ Vitest + Stryker（前端）/ mutmut（后端变异） | 双端 |

### 1.2 分域清单（图谱锚点实证）

| 分域 | 锚点（file:line） | 结论 |
|:--|:--|:--|
| 资产状态机 | `state_machine/transitions.py:32` VALID_TRANSITIONS；`constants.py:27` AssetState（8 态）；`core.py:31` AssetFSM（`_validate_transition:62` / `_transition:96`）；4 个 transitions mixin | 见 §三-1 |
| 合同状态机 | `state_machine/contract_fsm.py:15` ContractState（8 态线性链）；`:57` ContractFSM | 见 §三-2 |
| API 响应契约 | `utils/response_utils.py:23` success_response / `:37` error_response（175 + 100 调用方）；`core/mixins.py:79` ResponseWrapperMixin（19 View 挂载） | 见 §三-3 |
| 前端状态枚举 | `src/types/asset.ts:45` AssetCurrentStatus（8 键）；`types/outasset.ts`（outasset_current_status 对齐 8 态） | 见 §三-4 |
| 测试锚 | `tests/test_state_machine.py`、`tests/test_damaged_asset_service.py` 等（tests/ 目录 60+ 文件） | 见 §三-5 |
| 鉴权/操作日志/批量导入 | `apps/authusermanagement/`、`services/operation_log_service.py`、`core/department_scope.py`、公开扫码 `views/public_scan_view.py` | 见 §三-6 |

### 1.3 已核实的图谱外事实

- 通知：`apps/notification/helpers.py` 提供 `send_notification_on_commit`（非事务块调用抛 `TransactionManagementError`；回调体 try/except + 结构化日志 + `transaction.on_commit(..., robust=True)`），符合 B6。
- 健康端点：`config/urls.py:152-153` 存在 `/health/` 与 `/ready/`（OC-6 符合）。
- 异常吞没扫描：`core/token_blacklist.py:50`、`notification/consumer.py:123/140/189`、`core/prometheus_middleware.py:64` 共 5 处 `except Exception`，**均带 `logger.error/exception` 结构化留痕**，非静默吞没（OC-2 符合）。
- 行锁：状态机入口 `state_machine/core.py:46`、`unregistered.py`、`unregisteredasset/handlers.py:138`、`damaged_asset_view.py:144/158` 等关键并发路径均有 `select_for_update`。
- 事务：15 个 Service 文件共 60+ 处 `@transaction.atomic`（B6 符合）。

---

## §二 问题台账（阶段 2 诊断 + 阶段 3 影响面）

> 分级：P0 阻断/高危、P1 重要、P2 优化、P3 建议。「回查命令」按审计工作流 §2 使用 codegraph。

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 影响面 | 优先级 | 建议验证方式 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| AUD-31-1 | P2 | 规范（BR-3） | `apps/notification/helpers.py:54-55` | notify_dept_managers | 通知收件人过滤硬编码字符串 `role="dept_manager"`、`employee_status="active"`，未走 `Employee.Role.DEPT_MANAGER` / `EmployeeStatus.ACTIVE` 枚举（BR-3 要求 `Model.Field.VALUE` 形式）。同类硬编码另见 `apps/usermanagement/selectors.py:201,236` 与 `providers.py:37` 的 `employee_status="active"` | 将字面量替换为 `Employee.Role.DEPT_MANAGER` / `EmployeeStatus.ACTIVE`；同型 4 处同批清理（DR-1） | `codegraph node notify_dept_managers` | 小：仅通知链 7 符号 + 4 处选择器过滤（语义不变，纯常量替换） | 同域批次 1（先于其余 P2） | `rg -n 'role="dept_manager"|employee_status="active"' apps --glob "*.py"` 预期仅剩枚举引用；`pytest apps/notification apps/usermanagement -q` 全绿 |
| AUD-31-2 | P3 | 安全（SC-7 本地复核） | `vue-assetmanagement/package.json`（devDependencies） | — | `npm audit` 本地实测 37 漏洞（4 high：happy-dom、vite→launch-editor、undici、zod），**全部位于 devDependencies**，生产依赖链（dependencies 12 包）零命中；均为构建/测试工具链漏洞，不随产物发布 | 执行 `npm audit fix`（4 high 中 happy-dom/zod 已提示可自动修复；vite 8.2.0-8.2.2 需升级补丁版）；依 AGENTS §6 ③，CI `security-scan.yml` 为权威门禁，仅在依赖文件变更时触发 | `npm audit 2>&1 \| grep Severity` | 小：仅 dev 工具链 | 低（dev-only，且 CI 权威门禁已落地） | `npm audit --audit-level=high` 退出码 0；`npm run build` 不受影响 |
| AUD-31-3 | P3 | 可观测性（OC-8 类留痕） | 本机环境 | — | `pip-audit` 本机未安装，后端依赖漏洞未能本地复核；依审计工作流 §5.3 兜底，以 CI `security-scan.yml`（fail-closed，任意漏洞 exit 1，schedule 每周全量）为权威门禁 | 无需修复；如需本地复核可 `pip install pip-audit` 后重跑 | — | — | — | CI security-scan job 最近一次绿即视为符合 SC-7/SC-8 |

### 已核查但**不采纳**为问题的条目（含理由）

| 疑点 | 核查证据 | 结论 |
|:--|:--|:--|
| 状态机旁路：`scrapping.py:131/80`、`out_recycle.py:74/109`、`unregistered.py:56/89/128` 直写 `asset_current_status` 未走 `_transition` | 五处均为具名特殊回退（reject_to_original / cancel_damaged / cancel_outasset / cancel_recycle / force_recycle_from_any），有前置状态守卫 + InvalidTransitionError；`transitions.py:72-74` 注释明示 reject 边「不经 _transition 校验，其内部自行回退」为既定设计；`unregistered.py:101-102` 明示仅限管理员审批授权场景；`test_state_machine.py:214-238` 有护栏测试 | **不采纳**：与 `backend-business-rules.md` §三「特殊回退操作」表逐条对应，属声明内例外，非旁路 |
| 合同状态映射漂移 | 前端 `statusMapping.ts` CONTRACT_STATUS_MAP 8 键 = 后端 `contract_fsm.py:15-23` 8 态逐一对齐；详情接口经 `allowed_next_states` 下发出边（P3-04），前端编辑态 ∪ 出边防无效提交 | **不采纳**：契约一致 |
| 分页参数混用 `pageSize` | 前端 `pageSize` 仅出现在**组件 Props**（GroupedAssetTable 等 UI 层）与测试；API 层全部经 `page_size` 下发（`api/user.ts`、`api/harddiskSn.ts`、`assetStore.ts:146` 等）；后端 `core/pagination.py:34` `page_size_query_param="page_size"` | **不采纳**：UI 内部命名与网络契约命名分层，网络层契约一致 |
| 日期格式契约 | 后端 `USE_TZ=True` + `TIME_ZONE="Asia/Shanghai"`，DRF 默认 ISO 8601 输出 `+08:00`；前端 formatDate 系列仅做展示格式化，不做时区重解释 | **不采纳**：符合 §3 契约 |
| `code` 字段含义漂移 | `response_utils.py:29-33/47-52`：成功恒 0、错误恒 HTTP 状态码；`error_response` 已按 v1.7 移除 `business_code` 参数；View 层 4 处类型违规已在 v1.7 修复（`errors={"error_code": ...}`） | **不采纳**：与根 AGENTS §3 契约一致 |
| 密钥硬编码（SC-1） | `rg "(secret\|password\|api_key\|token)\s*=\s*['\"]"` 全后端零命中（测试与环境变量读取除外） | **不采纳**：符合 SC-1 |
| raw SQL / 拼接查询（SC-3） | `rg "\.raw\(|\.extra\(|cursor\.execute"` 零命中，全部 ORM 参数化 | **不采纳**：符合 SC-3 |
| 文件上传安全（SC-5/SC-6） | `rg "upload\|FileField\|ImageField"` 后端零命中，系统当前无文件上传面 | **不采纳**：不适用 |

---

## §三 分域结论与修复建议（阶段 4 成文，按优先级排序）

### 结论 1：资产状态机（CT-3）— 符合

- `VALID_TRANSITIONS`（transitions.py:32-85）与 `backend-business-rules.md` §三规则表**逐条一致**：in_store/in_use/recycled_pending 的出库/损坏/遗失扇出、`in_use→damaged` 已按 V2.8 移除、repairing 双入口共边（M-30 元组 `("repair_failed","to_damaged")`）、damaged 拒绝 5 目标 + approve、scrapped 终态空表。
- 业务约束 3/4（送修须建 RepairAsset、维修完成更新 physical_grade）由 Service 层承接；约束 7（create 注入 in_store 枚举、CreateSerializer 不暴露状态写字段）有 `test_asset_service.py:65` / `test_asset_view_api.py:141` 双向回归锚。
- 状态机全路径测试锚齐全：`test_state_machine.py`（214-238 等覆盖 force_recycle/reject 护栏）、`test_damaged_asset_service.py`（reject 各目标态）、`test_contract_fsm.py`（合同链全路径）。CT-3 符合。

### 结论 2：合同状态机 — 符合

- 8 态线性链（purchasing→…→project_finished）无分叉；非法态收敛为域异常（AUD-15，不再裸 500）；读路径 `allowed_next_states` 对脏值防御返回 []（前端据此禁用下拉）。

### 结论 3：API 响应契约 — 符合

- `success_response`/`error_response` 为唯一入口（275 调用方），19 个 View 挂 ResponseWrapperMixin 兜底包装；exception_handler 三级兜底统一走 error_response。未发现手写 dict 旁路。

### 结论 4：前端状态枚举与映射 — 符合

- `AssetCurrentStatus` 8 键与后端 `AssetState`/`AssetStatus` 完全一致；活账本 A-8 已将 Format.ts 映射收敛至 `statusMapping.ts::ASSET_STATUS_MAP` 单一来源（G-3 护栏 PASS 实证）。

### 结论 5：测试与规模门禁 — 符合（见 §四 待补运行时数据）

- 三个规模护栏（BR-4 函数 / BR-6 文件 / FR 前端）在仓库根实测 **exit 0 全 PASS**；重复代码回归护栏（G-1~G-3、G-5）**PASS**。DR-5/DR-6 无违规。
- 覆盖率与测试结果见 §四 运行时数据（本节待后台测试完成后回填）。

### 结论 6：安全与权限 — 符合（两条非阻断提示）

- SC-1~SC-6 静态面全部通过；OC-6 健康端点存在；公开扫码白名单/限流机制在位（§4.6 落地）。
- 非阻断提示见台账 AUD-31-1（BR-3 枚举硬编码）、AUD-31-2（dev 依赖 4 high 漏洞）、AUD-31-3（pip-audit 本地未装）。

### 修复建议排序（可直接交接修复 skill）

1. **批次 1（AUD-31-1，P2）**：`notification/helpers.py:54-55` + `usermanagement/selectors.py:201,236` + `providers.py:37` 共 5 处字面量 → 枚举常量。影响面小、语义零变化、有现成测试护栏。验证：rg 零字面量 + 两个 app 的 pytest 全绿。
2. **批次 2（AUD-31-2，P3）**：`npm audit fix` 升级 happy-dom/zod；vite 升 8.2.3+ 补丁版。验证：`npm audit --audit-level=high` exit 0。
3. **批次 3（AUD-31-3）**：无需修复，CI 门禁为权威。

---

## §四 运行时数据（CT-2 / CT-7）

- 后端全量 `pytest --cov=. --cov-fail-under=80`（2026-10-31 本机实测）：**2261 passed, 0 failed**（1650s）；整体覆盖率 **89.33%**（≥80 达标，`--cov-fail-under=80` 通过）。核心 Service 层单项 90% 未在本轮单独复跑，以 CI 逐 App 专项 job 与 v1.19 变更日志所载 98% 为最近权威数据（[推测] 本轮代码未变更，Service 覆盖率应不低于该记录，需 CI 复核确认）。CT-7 口径说明：本机 pip 环境未与 `requirements/dev.txt` 逐包比对，该数字标注为「本地环境，不代表 CI 基线」；测试通过/失败结论不受工具链漂移影响（pytest 为行为断言）。
- 变异测试（mutmut/T7）、Stryker（T16）本次未执行（重活，属 CI 权威门禁范畴；基线 83.25676365492598 记录于 mutmut-baseline.json）。

---

## §评审结论（阶段 5）

reviewer 复核（只读，未改动业务代码）：

- **证据回查**：3 条问题条目均满足五要素（级别/类型/file:line/symbol/回查命令），全部可在会话中凭 `codegraph node` / `rg` / `npm audit` 复现；7 条不采纳条目均附命令输出或源码行号。
- **置信度过滤**：按 code-reviewer 规程，仅保留置信度 ≥80 的条目——AUD-31-1（95）、AUD-31-2（95）、AUD-31-3（100）；低于 80 的疑点（如分页参数组件层命名、空 catch 分支）经核查后列为不采纳，未计入台账。
- **闭环检查**：无 P0/P1 条目；3 条 P2/P3 均含影响面 + 修复建议 + 建议验证方式，修复 skill（bug-surgical-fix / rigorous-dev）可直接接手。
- **§5 维度覆盖**：状态机全路径（5.1）、跨端契约 4 项（5.2）、SC-1~SC-8 分流（5.3）、CT-2/DR-5/DR-6 护栏（5.4）均有命令输出支撑；OC-4/OC-7 按 AGENTS §7 处于 QPS 豁免期（`[~]`），未构成发现。
- **未执行项留痕**：变异测试（mutmut/T7、Stryker/T16）与 OpenAPI 基线 diff 本次未执行，属 CI 权威门禁范畴，已在 §四 标注。
- **台账终态**：AUD-31-1 已确认（待修）；AUD-31-2 已确认（待修，dev-only 低风险）；AUD-31-3 已确认（不采纳为缺陷，留痕为环境事实）。本报告不产生「已修复」状态。
