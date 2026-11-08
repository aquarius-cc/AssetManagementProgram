# 全项目架构与代码质量审计报告（TraeCode / Kimi-K3 + CodeGraph）

> 日期：2026-11-07 | 模式：只读审计（零业务代码改动） | 索引：CodeGraph 1,063 文件 / 18,902 节点 / 43,231 边（up to date）
> 方法：project-all-code-review 五阶段流程（探索→诊断→影响面→成文→自审），融合 code-reviewer（置信度≥80 过滤）、code-quality-check（量化门禁）、code-explorer（分域探索）、ponytail-audit（过度工程）视角。

---

## §一 项目上下文

### 1.1 技术栈与分层

| 端 | 栈 | 分层契约 |
|:--|:--|:--|
| 后端 | Django 6.0 + DRF 3.16 + PostgreSQL 16 + SimpleJWT + drf-spectacular | Model → Selector → Service → Serializer → View（BR-7 纵深 ≤3 层） |
| 前端 | Vue 3.5 + TS 6.0 + Element Plus 2.10 + Vite 8 + Pinia 3 | views → stores/composables → api（F11 禁组件直请求） |
| 工程化 | 根仓 + 双 gitlink 子仓；CI ci.yml / security-scan.yml / duplicate-guard.yml / ci-cd.yml 门禁链 | 护栏即代码（scripts/ + .githooks/pre-commit） |

### 1.2 模块边界（索引实测）

- 后端 apps：`assetmanagement`（资产核心：state_machine/、services/、selectors/、views/、serializers/ 已包化）、`authusermanagement`、`usermanagement`、`unregisteredasset`、`notification`（HTTP+WebSocket）；公共层 `core/`（permissions、batch_mixins、mixins、envelope_schema、department_scope）、`utils/`（response_utils 等）。
- 前端 src：`views/`（页面）、`components/`（commoncomponents/componentsdetails/asset 等）、`stores/`、`composables/`、`api/`、`utils/`（pagination.ts / Format.ts 单一事实源）、`types/`。

### 1.3 量化门禁实测（本次会话直跑，仓库根执行）

| 门禁 | 结果 | 关键数字 |
|:--|:--|:--|
| BR-6 文件 ≤500 逻辑行 | PASS | 最大 `apps/assetmanagement/views/asset_view.py` 484 |
| BR-4 函数 ≤50 逻辑行 | PASS | 0 处超长 |
| FR-5/FR-6/FR-8 前端不变量 | PASS | 全部 ok（最大组件 136 行） |
| G-1~G-8 重复代码回归护栏 | PASS | `[RESULT] PASS: 重复代码回归护栏全部通过` |
| 状态机规则表 | 一致 | `VALID_TRANSITIONS`（transitions.py:32-85）与 backend-business-rules §三逐条吻合 |

> 覆盖率/变异测试本次未重跑（全量 pytest 约 26 分钟）。最近实测留痕：本地全量 2210 passed（`audit-pytest-2026-10-27.log`）；融合报告时点 后端 89.40% / Service 98% / 前端 Stores 97.21%（`merge-codegraph-audit-20261101.md` §五）；mutmut 83.2925% ≥ 基线 83.25676365492598（BF-125）。上述为历史记录值，非本次实测。

---

## §二 问题台账

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 |
|:--|:--|:--|:--|:--|:--|:--|:--|
| A-01 | P3 | F11 边界 | vue-assetmanagement/src/views/NotificationList.vue:18；views/ScanAssetView.vue:87 | `isAxiosError` | 两个视图组件直接从 `axios` 导入运行时守卫 `isAxiosError` 做错误判别。非"直接发请求"硬违规（无 axios 调用），但使组件依赖 axios 包，与 F11"组件不触碰 HTTP 层"的精神有张力；composables/useAssetOperationForm.ts:18 的同款导入属 F11 明示允许范围，不计 | 在 `src/api/` 或 `src/utils/` 导出统一错误判别 helper（如 `isNotFoundError`），视图改引 helper；改动面 2 文件 | `rg -n "isAxiosError" vue-assetmanagement/src` |
| A-02 | P3 | 设计令牌 | src/assets/styles/global-scroll.scss:8-18；global-reset.scss:17-25 | 滚动条/reset 样式 | 全局基础样式硬编码 hex 8+ 处（#f1f1f1/#c1c1c1/#a8a8a8/#2a2a2a/#555/#666/#409eff/#f5f7fa），未走 F1-F5 令牌。风险低（滚动条与 reset 基底，非业务视觉），且暗色切换主链路已走 CSS 变量 | 后续令牌化：灰阶收敛为 `--color-neutral-*` 变量；属渐进优化，不建议单独立项 | `rg -n "#[0-9a-fA-F]{3,6}" src/assets/styles` |

**已排除的误报（验证留痕）**：

1. ~~urls.py 裸 `return Response({'status': 'asset activated'})` 契约旁路~~ → 实为 `apps/assetmanagement/urls.py:115-144` 模块 docstring 内的示例代码（`:144` 闭合 `"""`），非运行时代码。
2. ~~GroupedAssetTable.vue `#4a90e2` 硬编码~~ → 位于 `:409-412` 注释（对比度论证留痕），实际样式用 `var(--color-primary)` / `var(--color-primary-dark)`。
3. ~~前端 `pageSize` 驼峰混用~~ → 命中均为 Element Plus 分页组件 prop（`GroupedAssetChildTable.vue`、`CommonList.vue`）与测试夹具；API 请求层发送 `page_size` 蛇形（api/asset.ts:227、api/authusers.ts:119 等），默认值单一来源 `utils/pagination.ts`（DEFAULT_PAGE_SIZE=20、PAGE_SIZE_OPTIONS）。
4. ~~api/foundAsset.ts 与 wasteAsset.ts URL 重复~~ → 系 `/assets/found-assets/` 与 `/assets/waste-assets/` 两个不同端点，非重复定义。

---

## §三 分域结论与修复建议

### 3.1 CT-3 状态机全路径 —— 通过

- 资产状态机：8 态规则表与文档一致；`repairing→damaged` 双入口共边（repair_failed / to_damaged）在册；`damaged→5 态` 共用 `reject_to_original`（BF-113 已删 5 个具名实现面）。
- 旁路仅 3 处且全部登记于 `transitions.py:9-15` 文件头：`unregistered_create_and_recycle`、`unregistered_create_and_damaged`、`force_recycle_from_any`；未发现未登记的 `asset_current_status` 直写。
- 业务约束抽查：broken→repairing 创建 RepairAsset（repair_asset_service.py:165-219）；repair_done 更新 physical_grade（:221-276）；非法转换收敛为 AppValidationError 非裸 500。
- 测试锚：test_state_machine.py 覆盖终态 scrapped 全操作拒绝（:180-223）、force_recycle 全路径（:225-241）。
- 合同状态机：`_CONTRACT_TRANSITIONS`（contract_fsm.py:30-54）8 态单向链、每态单出边、终态空集；非法态收敛 `ContractInvalidTransitionError`，读路径脏数据返 `[]`（AUD-15）。

### 3.2 跨端契约 4 项 —— 4/4 通过

- 响应根结构：运行时唯一入口 `utils/response_utils.py` + `core/mixins.py` ResponseWrapperMixin；schema 侧 `core/envelope_schema.py` OP-09 单点后处理器（批次 8 已收口，0 残留）。
- 枚举键名：后端 models/asset.py 与前端 types/asset.ts 8 键完全一致；中文映射单一事实源 `utils/Format.ts` ASSET_STATUS_MAP。
- 分页参数：`page`/`page_size` 双向一致（见 §二误报 3）。
- 日期格式：ISO 8601 含时区（抽查通过）。

### 3.3 安全红线 —— 通过

- SC-1：SECRET_KEY/DB_PASSWORD 全部 env 注入；production.py:12-35 对缺失/弱密钥/短密钥 fail-closed 抛 ImproperlyConfigured；仓库无硬编码命中（排除测试与占位）。
- SC-3：`.raw(`/`.extra(`/`cursor.execute` 命中均为参数化或 sql.Identifier 白名单组装（项目记忆教训已固化）。
- SC-5：上传 10MB 限制（base.py:175-179）；公开扫码 `public_scan_view.py:11-20` 显式 `[AnonRateThrottle, UserRateThrottle]`，6 字段白名单（§4.6）。
- OC-6：`config/urls.py:54-153` `/health/`、`/ready/` 均在。
- SC-7/SC-8：以 CI `security-scan.yml` 为权威门禁（依赖变更触发 + 周度全量兜底，fail-closed）。

### 3.4 RBAC 与行级隔离 —— 通过

- `core/permissions.py:207-238` `resolve_viewset_permissions` 写操作 fail-closed 至 admin_permission，读默认 IsAuthenticated；批次 12 已将其收敛为唯一裁决点（F10/F11 留痕）。
- B14/G-6/G-7 实证：`AssetViewSet.batch_delete_service` + `batch_delete_passes_user = True`（asset_view.py:434-441），`batch_delete_prefilter` 部门预筛；`AssetService.batch_delete_asset`（asset_service.py:317-339）逐条 `ensure_asset_visible`、越权 404——融合报告遗留项 M-01 已闭环。
- 行级隔离：`AssetSelector.get_queryset_for_user` 五角色语义（asset_selector.py:121-140）与 §4.3 一致。

### 3.5 前端质量与过度工程（ponytail 视角） —— 基本通过

- F6（禁 Options API）、F11（无组件直发请求）、FR-3（API 路径无重复定义）均零命中。
- 样式收敛走 mixin 优先（`_dashboard-sections.scss` 等，B-26 已收口）；GroupedAssetTable 暗色对比度处理有注释留痕，属规范鼓励的差异留痕。
- 唯一可优化项即台账 A-01/A-02 两条 P3，影响面小（各 ≤2 文件），无投机性抽象/死代码的高置信发现。

### 3.6 处置建议（排序）

1. A-01、A-02 均标 **待修（P3，可并入下一杂项批次）**，无 P0/P1/P2。建议验证方式：A-01 改后 `npm run type-check && npm run lint:ci` + 相关视图 spec；A-02 改后暗色双主题目检 + `npm run lint:ci`。
2. 无新增重复模式需登记 `complete-patterns.md`（§1.8 新发现义务：本次零新发现）。

---

## §四 审计票

```markdown
[审计票 - 必填项]
- 读取规范：已读 根 AGENTS.md（v3.7.5）+ 后端 AGENTS v9.3.3 + 前端 AGENTS v9.9.1 + backend-business-rules v1.23 + frontend-business-rules v1.5 + backend-testing-rules v1.8
- CT-1[√] CT-3[√ 规则表逐条一致·未登记旁路 0 处·合同 FSM 8 态链] CT-5[√ 最近全量 2210 passed 零失败] CT-7[√ 行数/护栏结论以根仓护栏 --print 实测为准；覆盖率引用历史留痕值未充当新基线]
- DR-1[√ 无新重复模式] DR-5[√ 四护栏实测 PASS]
- SC-1[√ 密钥全 env 注入+生产 fail-closed] SC-3[√ 参数化/白名单]
- 跨端契约：未破坏（4/4 通过）
- 红线触发：无
- 建议提交：是（本报告为纯审计产物）

[审计票 - 自检项]
- 测试：CT-2[√ 留痕值 后端 89.40%/Service 98%/前端 Stores 97.21%，非本次实测] CT-4[√] CT-6[N/A 无迁移变更]
- DRY：DR-2[√] DR-3[√] DR-4[√] DR-6[√]
- 安全：SC-2[√ CI] SC-4[√] SC-5[√] SC-6[√] SC-7[√ CI 权威] SC-8[√ CI 周度兜底]
- 可观测性：OC-1~OC-3[√] OC-4[~] OC-5[~] OC-6[√ /health+/ready] OC-7[~]
- AI鲁棒性：AR-1~AR-5[√ 零代码生成]
- AI行为：Fact-1[√]（台账 4 条误报均二次验证排除；覆盖率标注为历史留痕）
- 写作风格：Style-1~Style-3[√]
- 覆盖率：整体 89.40%（≥80，2026-11-01 留痕）/ Service 98%（≥90，同前）
- 专项结论：状态机旁路 0 处 | 契约 4/4 | SC 全项通过 | RBAC/行级隔离接线完整 | 新增 P3×2 无 P0-P2
```

> 只读纪律确认：本次会话未改动任何业务代码；产出物仅本报告。
