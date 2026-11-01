# 全项目审计报告（CodeGraph 增强 · 只读）

> 日期：2026-10-31 | 执行技能：project-all-code-review v1.2.0 + code-quality-check + code-reviewer + code-explorer
> 范围：asset_management_backend（Django 6.0 + DRF）/ vue-assetmanagement（Vue 3.5 + TS + Pinia）/ CI 与护栏
> 纪律：全程只读，未改动任何业务代码；行数结论一律逻辑行口径（LT-1~LT-3，护栏 `--print` 实测）；
> 覆盖率/变异数字一律引用 CI 实证并标注来源（CT-7，本会话未本地重跑全量套件）。

## §一 项目上下文

- **索引**：CodeGraph 1,030 文件 / 18,364 节点 / 41,791 边，sync 后 up to date。
- **后端**：五层架构（Model→Selector→Service→Serializer→View）；状态机收敛于
  `apps/assetmanagement/state_machine/`（core.py + 4 mixin + constants.py 8 态 + VALID_TRANSITIONS）；
  审计唯一生成点 `apps/assetmanagement/audit.py`（log_state_change :164-195）；
  RBAC 行级隔离唯一口径 `core/department_scope.py`（无第二套解析实现）；
  OC 落地：trace_id 中间件 `core/request_context.py:51-70`、JSON 日志 `core/json_formatter.py:20-42`、
  `/health/` `/ready/` `config/urls.py:54-144`、Sentry `send_default_pii=False`（production.py:125-142）。
- **前端**：统一响应解包 `src/api/request.ts:633-637`（code!==0 抛错）；分页参数标准化
  `stores/createEntityStore.ts:159`（page/page_size，兼容层已订正）；8 态枚举
  `types/asset.ts:31-54`、`types/outasset.ts:37-58` 与后端 AssetState 键名一致；
  路由守卫 RBAC `router/guards.ts:125-159`。
- **门禁**：CI 16 job（ci.yml）+ duplicate-guard.yml 3 job + security-scan.yml（fail-closed）+ ci-cd 部署前置门禁；
  护栏四脚本本会话实测全 PASS（BR-6 / G-1~G-3、G-5 / FR-5·6·8：.vue 121 文件 0 超限）。
- **测试规模**：后端 `apps/**/tests/*.py` 124 文件；前端 `src/**/__tests__/*.spec.ts` 约 190 文件。

## §二 问题台账

> 回查命令统一为 `codegraph node <symbol>` / `codegraph callers <symbol>` 或直接 Read 锚点。
> 状态：已确认 / 待修 / 不采纳（本报告不产生「已修复」状态）。

| ID | 级别 | 类型 | file:line | symbol | 描述（证据） | 修复建议 | 影响面 | 建议验证方式 | 状态 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| R-01 | P1 | 门禁/CI | `.github/workflows/ci.yml:473-502` | ci-summary | 汇总仅 needs backend-test/backend-mutation/frontend-test/frontend-mutation 4 job；backend-lint、backend-type-check、backend-complexity、backend-permission-check、api-schema-check、api-doc-guard 失败不进汇总。仓库直推 master 且未配 required checks（根 AGENTS §6-③），红 job 可被整体忽略 | 将全部静态门禁 job 纳入 ci-summary needs；或配 GitHub 分支保护 | 仅 CI 编排，零生产代码影响 | 故意注入一处 ruff 违规，断言汇总 job 红 | 待修 |
| R-02 | P1 | 门禁/前端 | `vue-assetmanagement/package.json:9-23`；`ci.yml:345,383` | lint 脚本 | `lint: eslint . --fix`，CI 的 frontend-lint 与 frontend-complexity 均跑 `npm run lint`——--fix 就地改写 runner 副本，可自动修复的违规被静默修好后「通过」，门禁结论失真（检查与修复语义混用） | CI 改用检查模式（`eslint . --max-warnings=0`，不带 --fix）；本地保留 --fix | CI 编排 + package.json scripts；不动业务代码 | 注入一条可自动修复违规，断言 CI 红 | 待修 |
| R-03 | P1 | 测试/T7 | `asset_management_backend/setup.cfg:20-83` | [mutmut] source_paths | 变异范围仅 `apps/assetmanagement/services`；usermanagement 4 个 + notification 1 个业务 Service 零变异覆盖（17 个业务 Service 中 5 个，约 29%）。pytest 专项 90% 已覆盖这些 App（ci.yml:233-238），风险为「有测试但测试锋利度未证」 | 分批扩 source_paths（先 usermanagement），扩前评估 mutmut 全量耗时；属规则执行面扩展，依 T7 留痕 | 仅 dev.txt 工具链与 CI 时长 | 扩后 `mutmut run` 双门禁（≥80 且 ≥基线） | 待修（已知项，规范易错点已声明） |
| R-04 | P2 | 测试/T17 | `ci.yml`（全文） | format:check | 前端三项检查（type-check/lint/format:check）中 Prettier 无 CI job，仅本地约束；T17 的 CI 强制不完整 | 增 frontend-format job 跑 `npm run format:check` | CI 编排 | job 存在且绿 | 待修 |
| R-05 | P2 | 契约/CI | `ci.yml:145-155` | api-schema-check | 破坏性变更阻断（符合 §3），非破坏漂移仅 `::warning::`——漂移可长期累积不重导基线。属规范 §3 明示的既有设计，登记现状 | 维持或升为「漂移 N 次未重导即阻断」的软棘轮 | CI 策略 | — | 不采纳（刻意设计，规范已载） |
| R-06 | P2 | 门禁/CI | `.github/workflows/duplicate-guard.yml:1-38` | — | 3 个护栏 job 无汇总 needs，各自独立红；无统一「护栏汇总」结论节点（与 ci-summary 不同构） | 视 R-01 一并纳入统一汇总 | CI 编排 | — | 待修（低优先） |
| R-07 | P2 | DRY/账本 | `Rules_Fiels/Duplicate_Codes/complete-patterns.md:461-676` | B 区 | 账本未关闭 9 项：B-1 审计适配器克隆、B-2 outassetStatusMapping 死副本、B-3 lifecycle 三重复制 ViewSet、B-4 MAX_BATCH_SIZE×31、B-5 batch-result 手写组装、B-6 批量方法镜像、B-7 throttles 三重复制、B-12 员工状态映射双源、B-26 .section-title×5。G 护栏仅守已关闭模式不复现，不主动消灭存量 | 按账本既定优先级批次收敛（B-4/B-5 面最大先做） | 各条目账本内已注影响面 | 逐条关闭 + G 护栏增补不变量 | 已确认（账本在册，不重复登记） |
| R-08 | P2 | 逻辑/待核查 | 账本 `:887` D-2 | init_production_data | 管理命令 3 个字段名 bug（CT-4 测试发现，待核查区未闭环）——初始化脚本按现状执行会失败或写错字段 | 按 D-2 条目修复并补用例 | 仅管理命令路径 | 命令实跑 + 断言 | 待修（账本在册） |
| R-09 | P2 | 接口/待核查 | 账本 `:898` D-5 | getassetbyrecordcode | 路径与 query 双入口，纯路径调用必 400——对外可用性缺陷 | 统一取参口径或兼容双入口并补 API 测试 | 单端点 | 端点集成测试双形态断言 | 待修（账本在册） |
| R-10 | P3 | 覆盖率/前端 | `vitest.config.ts:28-61` | coverage.thresholds | .vue 层棘轮 21.1/19.0/18.6/21.3 远低于 80——规范 T14 明示的分层过渡态（2026-10-30 重基），非缺口；ts 80 / stores 90 与 CT-2 一致 | 维持棘轮「只升不降」纪律即可 | — | — | 不采纳（规范允许） |
| R-11 | P3 | 安全/SC-1 | `config/settings/test.py:25` | SECRET_KEY | 测试配置硬编码 test-only 密钥；production.py 经 env 读取。判读为 SC-1 豁免（非生产凭据），留痕人工确认 | 可改 `os.environ.get(..., fallback)` 统一形制 | 仅 test settings | grep 确认无生产引用 | 已确认（豁免） |
| R-12 | P3 | 可读性/前端 | `composables/usePaginationSearch.ts:81-88,134-176` | pageSize | 组件层内部变量 `pageSize` 与请求参数 `page_size` 并存，转换收敛在请求层——契约合规（§3 未破坏），仅命名边界提示 | 无需改动 | — | — | 不采纳 |

**专项结论（skill §5）**：
- **CT-3 状态机旁路：0 处**。生产代码 `asset.asset_current_status =` 写入点全部位于
  `state_machine/`（core.py:112、scrapping.py:80/:131、out_recycle.py:74/:109、unregistered.py:56/:89/:128），
  其中 out_recycle/unregistered 为规则文档 §三明示的合法特殊路径；FSM 外无直写。
  force_recycle_from_any（unregistered.py:128）的前态留痕已落：`handlers.py:124-148` 补
  `AuditLogger.log_state_change(trigger="force_recycle")`，回归用例 `tests/test_handlers.py:116`。
- **跨端契约 4 项：全部一致**（响应根结构统一解包 / 8 态枚举键名对齐 / page·page_size 无混用 / ISO8601 解析一致）。
- **SC 分流**：SC-1 仅 R-11 豁免项；SC-3 无字符串拼接查询，`clear_database.py:124-219` 走
  `_build_identifier_sql` + 白名单双闸；SC-7/8 由 security-scan.yml fail-closed + 周度 schedule 落地。
- **批次 6 P3 债抽查 8/8 全部已落地**：M-11（models.py:91-109 收敛至 DepartmentService，
  [M-11] 注释在位）、M-12（--strict + 3 用例）、M-15（sentry-sdk==2.73.0 钉版）、M-16（见上）、
  M-32（guards.ts 死条目已删并留注释）、M-33（Format.ts toLocalDateString 唯一底层）、
  M-34（FR-5 .vue 护栏实现，本会话实测 121 文件 0 超限）、M-35（auth.ts:8-9/:326 已注明
  「XOR 混淆非加密，不构成安全边界」）。
- **账本 B-8/B-10 两个 500 bug 实为已关闭**（2026-08-24，B-8 经 BatchResponseHelper.request_items
  方案、B-10 经 commit d784848），标题区未标注状态系账本格式遗留，建议补标。

## §三 分域结论与优先级排序

1. **后端架构与逻辑**：五层职责清晰，事务/审计/行级隔离均有唯一实现且无旁路；未发现 P0。
   最强正面项：FSM 写路径收敛彻底（8 写入点全在 state_machine/ 包内）。
2. **前端架构与契约**：Setup Store + 统一拦截器 + 枚举单源，契约消费合规；
   遗留集中在账本 B 区 DRY 债（R-07）。
3. **测试与门禁**：宪法级数字门禁（cov/mutmut/stryker）CI 全绿实证——
   整体 88.93% / 四 App Service ≥90（assetmanagement 98%）/ mutmut 83.2568 ≥ 基线 83.25676365492598 /
   stryker 82.29 ≥ 80（来源：backend-business-rules v1.19 变更日志 2026-10-21、
   mutmut-baseline.json、CI run 38220043308 / 38034281446；本会话未重跑，CT-7 留痕）。
   **本批最高价值修复点是 CI 编排层**（R-01/R-02/R-04）：门禁本身强，但汇总链漏收 + lint --fix
   语义混用会稀释门禁效力。
4. **修复顺序建议**：R-01 → R-02 → R-04 → R-06（同批 CI 编排，一次改净）→ R-03（需耗时评估立项）
   → R-08/R-09（账本 D 区闭环）→ R-07（按账本批次）。R-01+R-02 影响面最小、门禁收益最大，先行。

## §四 评审结论（阶段 5 自审，reviewer 规程）

- 证据引用：全部条目具备 file:line 或配置键锚点，可回查；置信度均 ≥80（低于阈值项未收录）。
- 每条 P0/P1 均有 证据 + 影响面 + 修复建议 + 验证方式 四要素；P2/P3 中 R-05/R-10/R-12 标「不采纳+理由」。
- 未执行项如实标注：pip-audit 本地未跑（以 CI security-scan.yml 为权威门禁，留痕）；
  全量 pytest/vitest 未重跑（引用 CI 实证并标来源）；`codegraph explore` 部分域以 rg/Read 补齐图谱外事实。
- 只读纪律：本会话零业务代码改动（唯一新增文件为本报告）。
- 台账终态：P0×0、P1×3（待修）、P2×6（待修 4 / 不采纳 1 / 豁免确认 1）、P3×3（不采纳 2 / 豁免 1）。

[可验证] FSM 零旁路、批次 6 八项已落地、三护栏 PASS、CI job 清单与 needs 图 — 依据：本会话 Grep/Read/脚本实跑输出（§二各条 file:line）。
[可验证] 覆盖率与变异数字 — 依据：规范变更日志 v1.19、mutmut-baseline.json、CI run 编号（非本会话重测，CT-7 已标注来源）。
[推测] R-02「--fix 掩盖违规」的实际发生频率无法从静态配置取证 — 原因：需历史 CI 日志比对，未获取。
