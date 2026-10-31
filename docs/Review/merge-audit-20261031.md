# 三源融合审计报告（AtomCode + trae + codebuddy）

> 融合日期：2026-10-31 | 融合方：AtomCode（本报告只读，未改动任何业务代码）
> **状态更新（2026-10-31，mimo）**：批次 1（M-02/M-09/M-10/M-24）已修复并提交——根仓 `1281523` + 子模块 `9ba1fb1`（本地提交，未推送），台账中四行以 `✅【已修 · BF-167】` 标记；修复细节与验证证据见 `docs/BugFixed/Bug修复活账本.md` BF-167。本报告其余内容保持审计时点原貌。
> 源报告：
> ① `docs/Review/AtomCode-codegraph-audit-2026-10-31.md`（CodeGraph 全谱 + 工具链实跑：pytest 2261 passed / 覆盖率 89.33% / 三护栏 PASS / npm audit）
> ② `docs/Review/trae-audit-20261031.md`（静态 + CI 编排与账本专项：R-01~R-12）
> ③ `docs/Review/codebuddy-audit-20261031.md`（纯源码直读，零执行：F-01~F-20）
>
> **融合方法**：三源互补无冲突——① 强在工具链实证与护栏；② 强在 CI 门禁编排与账本闭环；③ 强在业务逻辑语义与授权模型。融合时对 ③ 的关键条目（F-01/F-02/F-03/F-04/F-05/F-09）由融合方**逐条重新实证**（grep/直读源码），确认全部为真后才入合并台账。统一编号 M-xx，每条标注来源与实证方式。

---

## §一 三源共识区（交叉验证一致，无需再查）

| 结论项 | ①AtomCode | ②trae | ③codebuddy | 一致性 |
|:--|:--|:--|:--|:--|
| 状态机治理（CT-3） | ✅ VALID_TRANSITIONS 与规则表逐条一致；特殊回退均为声明内例外 | ✅ FSM 外零直写，8 写入点全在 state_machine/ | ✅ 唯一入口 + unregistered 显式白名单，全路径单测 | **三源一致，项目最强项** |
| 跨端契约 4 项 | ✅ 全部一致 | ✅ 全部一致 | ✅ 逐字核对一致 | **三源一致，零破坏** |
| 五层/四层架构 | ✅ 无跨层调用 | ✅ 无跨层倒挂 | ✅ 依赖方向正确 | 三源一致 |
| 权限 fail-closed / AUD-21 | — | ✅ core/department_scope 唯一口径 | ✅ 无 Employee 反转为 [] 已修 | 两源一致 |
| 安全红线 SC-1~SC-6 | ✅ 静态面零命中 | ✅ 零命中 | ✅ 零命中 | 三源一致 |
| DR-5/FR-5 文件规模 | ✅ 三护栏 exit 0 实测 | ✅ 护栏 PASS | （未执行，引台账） | 两源实跑一致 |
| 覆盖率/变异 | ① 实测 89.33%（本地）/ ② CI 实证 88.93% + mutmut 83.2568 + stryker 82.29 | — | 未执行不编造 | 数字口径一致（89.33 本地 vs 88.93 CI，差异在未计脚本目录，均为绿） |

**唯一需要人工拍板的分歧**：无。三源在事实层零冲突；在优先级判断上存在侧重差异（②认为 CI 编排最高价值，③认为授权不对称最高风险），融合结论见 §三。

---

## §二 合并问题台账（去重后统一编号）

> 级别：P0/P1/P2/P3。状态：已确认（待修）/ 待修（账本在册）/ 不采纳（理由）。每条含来源、实证方式、影响面、验证方式五要素。

### P1（2 条）

| ID | 来源 | file:line | 问题（已实证） | 修复建议 | 影响面 | 建议验证方式 |
|:--|:--|:--|:--|:--|:--|:--|
| **M-01** | ③F-01（融合方实证：`asset_view.py:132-139` create 不传 user；`asset_service.py:132-134` create_asset 无 user 参数） | `views/asset_view.py:132`、`services/asset_service.py:132`、`serializers/asset_crud_serializers.py:246-273` | **资产创建路径无部门范围校验**：update 传 `user=` 做行级校验，create 不传；`asset_storage/asset_manager/asset_applicant` 三个 SlugRelatedField queryset 全量。asset_admin 可创建挂到他部门保管人/仓库的资产，资产经三路径动态解析后立刻脱离创建者可见范围（「创建成功但列表看不到」），构成写侧越权面（读侧已隔离、写侧未隔离） | 方案 A：create 传 `user=request.user`，`create_asset` 内对三个归属外键比对 `get_department_codes_for_user(user)`；方案 B：若代录为合法业务，显式白名单（system_admin 放行）。**触发 [HALT]：需产品确认资产管理员代他部门录入是否为合法业务**（对照：未登记资产域有显式代录白名单且仅限 system_admin，主资产域无） | 小：单端点 + Service 签名加参 | A/B 部门夹具镜像 `test_contract_read_scope.py` 范式补 `test_asset_create_cross_department_denied`（CT-4） |
| **M-02** ✅【已修 · BF-167】 | ②R-01 | `.github/workflows/ci.yml:473-502` | **ci-summary needs 不全**：汇总仅收 backend-test/backend-mutation/frontend-test/frontend-mutation 4 job；backend-lint、backend-type-check、backend-complexity、backend-permission-check、api-schema-check、api-doc-guard 失败不进汇总。仓库直推 master 且无 required checks，红 job 可被整体忽略（门禁稀释） | 将全部静态门禁 job 纳入 ci-summary needs；或落地 GitHub 分支保护（required checks） | 仅 CI 编排，零生产代码 | 注入一处 ruff 违规，断言汇总 job 红 |

### P2（11 条）

| ID | 来源 | file:line | 问题（已实证） | 修复建议 | 影响面 | 建议验证方式 |
|:--|:--|:--|:--|:--|:--|:--|
| **M-03** | ③F-02（融合方实证：`dashboard_selector.py:296-300` 先 `order_by("asset_purchase_date")[:50]` 后 Python 内筛 `0<=days_remaining<=days`；`:332-336` 维护提醒同型） | `selectors/dashboard_selector.py:296-336` | **Dashboard「即将到期/维护提醒」先截断后过滤**：升序取最老 50 条再筛剩余天数，最老资产保修普遍已过期被丢弃；资产数 >50 时系统性漏报（越新越不可能入选），用户看到空列表 | 过滤下推 DB：到期预警按 `asset_purchase_date + 保修期` 表达式过滤后再 `[:limit]`；维护提醒按 `asset_entry_date__lte=now-24mo`。补内容断言测试（当前该维度零断言） | 纯 Selector，零迁移 | 构造 >50 条夹具，断言未过期的第 51+ 名次资产正确入选 |
| **M-04** | ③F-09（融合方实证：`damaged_asset_view.py:67` 导出列 field=`damaged_asset_date`，模型字段实为 `damaged_date`（models/damaged_asset.py:72）） | `views/damaged_asset_view.py:67` | **报废导出「损坏日期」列恒为空**：字段名拼写错误 + `get_nested_value` 容错 `getattr(..., None)` → 静默输出空列（现有测试只断言权限不断言单元格） | 改 field 为 `damaged_date`；补单元格内容断言测试 | 单端点导出 | 导出 xlsx 断言该列非空且与 DB 值一致 |
| **M-05** | ③F-03（融合方实证：`usePaginationSearch.ts:110-115` notifyCallerError 后又无条件 `ElMessage.error`） | `src/composables/usePaginationSearch.ts:110-115` | **列表加载失败双 toast**：注释声明 M-RC-09 单出口，实现却再弹一次（AxiosError 已由拦截器提示 + 本行 = 双提示） | 删除 `ElMessage.error(messages.loadFailed)`，保留 `notifyCallerError` 单出口 | 单文件 | 模拟非 AxiosError/AxiosError 两种失败，各断言仅 1 次 toast |
| **M-06** | ③F-04（融合方实证：4 个生命周期 store 均未设 `disableAutoMessage`，仅 recycleAssetStore.ts:56 设置；`useAssetLifecycleActions.ts:67-71` 再弹成功） | `stores/{brokenAsset,lostAssetStore,foundAssetStore,repairAssetStore}.ts` + `composables/useAssetLifecycleActions.ts:67-71` | **生命周期详情页删除出现两条「成功」提示**：store 自动消息 + composable 手动消息并存 | 4 个 store 补 `disableAutoMessage: true`（与 recycle 对齐） | 4 个 store 配置 | 挂载断言删除流程仅 1 条成功 toast |
| **M-07** | ③F-05（融合方实证：8 处 `max_batch_size=100` 字面量，rg 全命中） | `services/asset_service.py:287`、`asset_lifecycle_mixin.py:426,454`、`storage_service.py:180`、`out_asset_service.py:291`、`recycle_asset_service.py:365`、`contract_service.py:472`、`asset_type_service.py:223` | **DR-1 常量旁路**：`core/batch_mixins.py:74` 已有 `DEFAULT_MAX_BATCH_SIZE` 且 `max_batch_size=None` 自动回落，8 处仍显式传 100。当前无数值差异，但唯一真值被旁路 | 8 处删实参走默认回落；按 §1.8 新发现义务登记入账本（与账本 B-4「MAX_BATCH_SIZE×31」同族，合并一个批次清） | 零行为变更 | rg 零字面量 + 批量路径 pytest 全绿 |
| **M-08** | ①AUD-31-1（融合方实证） | `notification/helpers.py:54-55`、`usermanagement/selectors.py:201,236`、`providers.py:37` | **BR-3 枚举硬编码**：`role="dept_manager"`、`employee_status="active"` 共 5 处字面量，未走 `Employee.Role.DEPT_MANAGER` / `EmployeeStatus.ACTIVE` | 5 处替换为枚举引用（同批清理） | 小，语义零变化 | rg 零字面量 + notification/usermanagement pytest 全绿 |
| **M-09** ✅【已修 · BF-167】 | ②R-02 | `vue-assetmanagement/package.json:9-23`、`ci.yml:345,383` | **CI lint 带 --fix**：frontend-lint 与 frontend-complexity 跑 `npm run lint`（=`eslint . --fix`），可自动修复的违规被静默修好后「通过」，检查与修复语义混用 | CI 改检查模式（`eslint . --max-warnings=0` 不带 --fix）；本地保留 --fix | CI 编排 + scripts | 注入可自动修复违规，断言 CI 红 |
| **M-10** ✅【已修 · BF-167】 | ②R-04 | `ci.yml`（全文） | **format:check 无 CI job**：前端三项检查仅本地强制，Prettier 缺 CI 强制 | 增 frontend-format job | CI 编排 | job 存在且绿 |
| **M-11** | ③F-06 | `core/batch_mixins.py:143-148` | **batch_execute 宽 except 吞 DatabaseError**：连接中断/死锁与业务异常同样降级为「单条失败」继续循环；若无 savepoint，PG 事务中止后失败日志被污染为 `transaction is aborted`，success_items 与落库结果可能不一致 | `except Exception` 之前显式捕获 `django.db.DatabaseError` 并 raise（fail-fast） | 单文件，需核对批量调用方 savepoint 情况 | 模拟 DatabaseError 断言整体失败而非逐条 fail_items |
| **M-12** | ③F-08 | `selectors/dashboard_selector.py`（get_statistics 内 Contract.objects.filter 全量） | **Dashboard 合同统计未按部门隔离**：资产统计经 `_scoped_asset_queryset` 收窄，合同总数/金额为全公司口径；合同读权限已锁 system_admin，聚合数字却对 dept_manager/asset_admin 可见，与授权模型矛盾 | 非 system_admin 返回 None 或按部门过滤（合同无部门字段则返回 0 并注明）；补断言测试。**与 M-01 同属授权不对称，可同批拍板** | 单 Selector 分支 | 以 dept_manager 登录断言合同统计为 None/0 |
| **M-13** | ③F-07 | `api/assetCache.ts:128-131` vs 18 处 M-RC-08 调用点（brokenAsset/damagedAsset/lostAsset/foundAsset/repairAsset/recycleAsset/outAsset 各 ts） | **缓存失效两套时序并存**：删除类 await 后失效（14 处），状态变更类先失效后请求（18 处 fire-and-forget）——并发读可回填写前数据直到 TTL 5min，表现为「操作成功但数据未变」，诱发重复提交 | M-RC-08 统一改 `async` + await 后失效；前端大范围改动需回归 | 前端 7 个 API 模块 | 并发读时序单测 + 关键写路径 E2E |

### P2（账本在册 / 立项类，4 条）

| ID | 来源 | 位置 | 问题 | 修复建议 | 状态 |
|:--|:--|:--|:--|:--|:--|
| **M-14** | ②R-03 | `setup.cfg:20-83` [mutmut] source_paths | 变异范围仅 assetmanagement services（5/17 业务 Service ≈29%），usermanagement/notification 零变异覆盖 | 分批扩 source_paths（先 usermanagement），扩前评估全量耗时；T7 留痕 | 立项（规范易错点已声明） |
| **M-15** | ②R-08 | 账本 D-2（complete-patterns.md:887） | init_production_data 管理命令 3 个字段名 bug，待核查区未闭环 | 按 D-2 修复 + 补用例 | 待修（账本在册） |
| **M-16** | ②R-09 | 账本 D-5（:898） | getassetbyrecordcode 路径/query 双入口，纯路径调用必 400 | 统一取参或兼容双入口 + 集成测试 | 待修（账本在册） |
| **M-17** | ②R-07 | 账本 B 区 9 项（:461-676） | B-1 审计适配器克隆 / B-2 状态映射死副本 / B-3 三重复制 ViewSet / B-4 MAX_BATCH_SIZE×31 / B-5 batch-result 手写 / B-6 批量镜像 / B-7 throttles 三重 / B-12 员工状态双源 / B-26 .section-title×5 | 按账本既定批次收敛，B-4/B-5 面最大先做；M-07 并入 B-4 批次 | 已确认（账本在册） |

### P3（低优先 / 留痕，7 条）

| ID | 来源 | 位置 | 问题 | 建议 |
|:--|:--|:--|:--|:--|
| M-18 | ①AUD-31-2 | `package.json` devDependencies | npm audit 4 high（happy-dom/vite/undici/zod），全部 dev 依赖，生产链干净 | `npm audit fix` + vite 升补丁；CI security-scan.yml 为权威门禁 |
| M-19 | ③F-13 | `assetmanagement/audit.py:60-120` | 审计写失败被吞仅记 error，合规场景「审计缺行」需权衡 | 关键流转（approve/scrap）改强一致或加 `audit_write_failed` 指标告警 |
| M-20 | ③F-15 | `stores/assetStore.ts:144-147` vs `:173` | getList 无参回落 page_size:10 与 defaultPageSize:20 不一致 | 统一取 defaultPageSize |
| M-21 | ③F-16/F-17/F-18/F-19/F-20 | 各处 | 零引用依赖 @vue/server-renderer / dev host 0.0.0.0 / 类型注释漂移 / operation_log_views 位置 / BR-4 存量两函数（53/52 行） | 低优先迭代批次；F-20 账本在册 |
| M-22 | ③F-10/F-11/F-12/F-14 | asset_view.py 等 | @action permission_classes 死配置（fail-closed 兜底无越权）/ 函数内重复 import + 英文 message / 双端点冗余 / 操作日志 ip_address 字段可见性 | 主入口收敛 + deprecated 标注；ip 字段限 admin/auditor |
| M-23 | ①AUD-31-3 / ② | — | pip-audit 本地未装，后端依赖审计以 CI security-scan.yml 为权威 | 留痕，无需修复 |
| M-24 ✅【已修 · BF-167】 | ②R-06 | duplicate-guard.yml | 3 护栏 job 无统一汇总节点 | 并入 M-02 同批做 |

### 不采纳（附理由，融合后维持）

| 来源条目 | 理由 |
|:--|:--|
| ②R-05 api-schema 非破坏漂移仅 warning | 规范 §3 明示的既有设计 |
| ②R-10 .vue 棘轮低阈值 | T14 明示分层过渡态（2026-10-30 重基），棘轮只升不降即可 |
| ②R-11 test.py SECRET_KEY | 测试专用凭据，SC-1 豁免（production.py 经 env 注入） |
| ②R-12 / ③F-15 相关组件层 pageSize 命名 | UI 内部命名与网络契约分层，§3 未破坏（M-20 仅留默认值不一致这一小点） |
| ①②③ 各自的「状态机旁路」疑点 | 三源交叉证实为声明内特殊回退（transitions.py:72-74 注释 + 守卫 + 护栏测试） |

---

## §三 修复顺序建议（分批小步验证，§1.2）

**排序原则**：零风险高收益先行 → 用户可见缺陷次之 → 需产品拍板的授权项单独成批（避免阻塞其余修复）→ 大回归面项靠后 → 账本批次收尾。同批一次清干净（DR-1/DR-2）。

```text
批次 1【CI 门禁加固，零业务代码】 M-02 + M-09 + M-10 + M-24  ✅【已完成 2026-10-31 · BF-167】
  → ci-summary 收全 needs / CI lint 去 --fix / 增 format job / 护栏汇总
  验证：故意注入违规断言汇总与对应 job 均 红→绿；全程零生产代码。
  落地：根仓 1281523 + 子模块 9ba1fb1（本地提交，未推送）。M-02 部署门禁采用方案 A
  （CD 触发源改 CI Pipeline + actions: read 按 SHA 回查安全扫描 + 短轮询 fail-closed
  + 监听名一致性护栏 check_ci_orchestration.py）；M-09 落地为 lint:ci = eslint .
  （未加 --max-warnings=0，沿用现行告警口径）。本地验证：护栏先红后绿、pytest
  29 passed、eslint/format 切换前置实测全绿。残余取证：推送后 CI 首跑 + 探针注入测试。

批次 2【用户可见逻辑缺陷，小改】 M-03 + M-04
  → Dashboard 截断缺陷 + 导出空列（均为后端单文件，各补内容断言测试）
  验证：>50 条夹具断言入选正确；导出 xlsx 列非空。

批次 3【前端 UX】 M-05 + M-06
  → 双 toast 两处（纯前端小改）
  验证：模拟失败/成功各断言仅 1 条提示。

批次 4【DRY 常量收敛】 M-08 + M-07（并入账本 B-4 批次登记）
  → 枚举硬编码 5 处 + max_batch_size 字面量 8 处（零行为变更）
  验证：rg 零字面量 + 相关 app pytest 全绿；账本登记留痕。

批次 5【后端健壮性】 M-11
  → batch_execute DatabaseError fail-fast（先核对各批量调用方 savepoint）
  验证：DatabaseError 模拟断言整体失败。

批次 6【授权口径，需产品拍板 [HALT]】 M-01 + M-12
  → 写侧部门校验 + Dashboard 合同统计口径（同一拍板：跨部门代录与合同聚合可见性）
  拍板后按 §5.2 轻量审批落地；补 CT-4 回归测试。

批次 7【前端缓存时序统一】 M-13
  → 18 处 M-RC-08 改 await 后失效（大回归面，单独成批）
  验证：并发读时序单测 + 关键写路径回归。

批次 8【账本与立项批次】 M-14 + M-15 + M-16 + M-17 + M-18
  → mutmut 扩围立项 / 账本 D 区闭环 / B 区批次 / dev 依赖升级。
```

**关键判断**（融合方）：② 将 CI 编排列为最高价值（门禁稀释是系统性风险），③ 将 F-01 列为唯一 P1。融合结论：**批次 1 先行**（零风险、防止后续修复的红 job 被吞），**批次 6 紧随其后发起拍板**（M-01 是唯一确定的写侧越权面，拍板不阻塞其余批次并行推进）。

---

## §四 证据与可验证性（Fact-2）

- [可验证] M-01/M-03/M-04/M-05/M-06/M-07：融合方本轮 grep/直读实证（create 无 user 参数、先截断后过滤、字段名 damaged_asset_date vs damaged_date、双 toast 源码、8 处字面量 rg 命中）— 依据：§二各行号。
- [可验证] 后端 2261 passed / 覆盖率 89.33%（≥80）、三护栏 exit 0、npm audit 4 high 全在 devDependencies — 依据：① AtomCode 报告 §四 本机实跑输出（2026-10-31）。
- [可验证] mutmut 83.2568 / stryker 82.29 / CI 四 App Service ≥90 — 依据：② trae 报告所引 CI run 编号与 mutmut-baseline.json（非融合方重测）。
- [推测] M-01 属遗漏而非设计 — 原因：主资产域无代录白名单，与未登记资产域显式白名单对照，无产品口径文档。
- [推测] M-03 漏报的实际影响程度取决于资产基数与保修分布 — 原因：逻辑方向确定（先截断后过滤），规模未用真实数据验证。

---

## §五 审计票（融合报告）

```markdown
[审计票 - 必填项]
- 读取规范：已读 根 AGENTS.md / 双端 AGENTS & Rules / 活账本（本会话链路）
- CT-1[√] CT-3[√三源一致] CT-5[√ 2261 passed 零失败] CT-7[~ 数字已标本地/CI 双口径]
- DR-1[~ M-07/M-08 两处字面量旁路在册待清] DR-5[√ 护栏 exit 0]
- SC-1[√] SC-3[√]
- 跨端契约：未破坏（三源一致）
- 红线触发：无（M-01 若落地需 §5.2 审批，本次仅报告未改码）
- 建议提交：是（本报告作为审查记录）

[审计票 - 自检项]
- 测试：CT-2[√ 89.33%本地 / 88.93%CI] CT-4[~ M-03/M-04 缺内容断言已列入修复] CT-6[N/A]
- DRY：DR-2[√] DR-3[√] DR-4[√] DR-6[√]
- 安全：SC-2[√CI配置] SC-4[√不适用] SC-5/SC-6[√不适用] SC-7[~ dev依赖4 high] SC-8[~CI周度]
- 可观测性：OC-1~OC-3[√] OC-4[~豁免] OC-5[~] OC-6[√] OC-7[~豁免]
- AI鲁棒性：AR-1~AR-5[√ 零代码生成]
- AI行为：Fact-1[√]（未执行项显式标注，未编造数字）
- 写作风格：Style-1~Style-3[√]
- 覆盖率：整体 89.33%（本地实跑）/ 核心 Service 以 CI 逐 App 专项为权威（≥90，assetmanagement 98%）
```
