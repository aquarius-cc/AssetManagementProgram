# CodeGraph 全量审计报告（2026-10-20）

> 依据：项目专属审计工作流（project-all-code-review 审计模式落地版 v1.2.0）＋ 根 AGENTS.md（v3.7.1）。
> 全程只读，未改动任何业务代码。codegraph 1.6.2（988 文件 / 17,525 节点 / 39,447 边，索引 up to date）。

## §一 项目上下文

| 维度 | 事实 |
|---|---|
| 技术栈 | 后端 Django 6.0.8 + DRF（base.txt 声明 3.17.2，本地实装 3.16.0）+ PostgreSQL 16；前端 Vue 3 + TS + Pinia + Vitest |
| 模块边界 | `apps/` 5 域（assetmanagement / authusermanagement / usermanagement / unregisteredasset / notification）+ `core/` + `utils/`；状态机独立包 `state_machine/`；响应根结构唯一入口 `utils/response_utils.py` |
| 机械门禁（阶段 0 实测，本地 SQLite 口径） | 覆盖率 **88.88%**（≥80 达标）｜ **2005 passed / 1 failed / 5 skipped**（43.2s）｜ BR-4 函数长度 PASS（0 超限）｜ BR-6 文件长度 PASS（最大 483/500）｜ SC-1 密钥 clean（四层环境均 env 驱动 + 弱密钥守卫）｜ SC-3 clean（仅字面 `SELECT 1` ×2 + 白名单兜底的 `clear_database.py`） |
| 环境漂移声明（CT-7） | 以上数字在 **Python 3.13.13 + SQLite + DRF 3.16.0** 上测得，**不代表 CI 基线**（CI = Python 3.12 + dev.txt 全量 + PostgreSQL）。SC-8 依赖漏洞：本地 pip-audit 未装，按拍板**留痕：以 CI `security-scan.yml` 为权威门禁** |

分域执行：阶段 2 采用 5 个并行只读子代理（状态机 / 鉴权 / 服务层 / API 契约 / 前端），主代理完成机械门禁、限流失败实证根因与 P1 影响面（阶段 3 `codegraph impact/callers/affected`）。

## §二 问题台账

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 |
|---|---|---|---|---|---|---|---|
| NEW-01 | P1 | 测试假红（回归） | `apps/authusermanagement/tests/test_create_throttle.py:78`；`config/settings/test.py:126-135` | TestCreateRateLimited.test_sixth_anonymous_create_returns_429 | `override_settings` 无法覆盖 DRF `SimpleRateThrottle.THROTTLE_RATES` **类属性快照**：实测快照 register=10000000/minute，override 后新实例 rate 仍为 10000000/minute；隔离运行仍失败（非测试污染）。回归由 `fa252a7`（test.py 关限流类保 rates）引入。**生产限流无恙**：`base.py:207 register=5/minute` + `get_throttles` 装配单测通过 | 测试内 `mock.patch.object(RegisterRateThrottle, "THROTTLE_RATES", {...register:5/minute})` 替代 override rates；或 rates 不走 override | `codegraph node RegisterRateThrottle` |
| NEW-02 | P1 | 分页稳定性（契约） | `models/broken_asset.py:73-76`、`models/contract.py:119-122`、`models/damaged_asset.py:108-111`、`models/recycle_asset.py:106-109`；`selectors/broken_asset_selector.py:21,25`、`contract_selector.py:20,46`、`damaged_asset_selector.py:21,25`、`recycle_asset_selector.py` | get_queryset_for_user / get_all_contracts / search_contracts | 4 个生命周期模型 Meta 无 `ordering`，selector 返回裸 `filter()`，分页点（`damaged_asset_view.py:95,213`、`contract_view.py:209,355`、`recycle_asset_view.py:152`、`_lifecycle_base.py:169`）LIMIT/OFFSET 无 ORDER BY → 翻页重复/丢行（coverage 实测 4 处 UnorderedObjectListWarning）。对照：Asset 有 `ordering=["-created_at"]`（`models/asset.py:234`） | 4 个 model 补 `Meta.ordering=["-created_at"]`（最小改动、全端点收敛）；Waste/Out/Repair 的 by_asset 路径同类并入同批 | `codegraph impact get_queryset_for_user` |
| NEW-03 | P1 | 业务状态搁浅 | `services/repair_asset_service.py:303-307`（from_state 于 :286） | fail_repair | `fail_repair` 建待报废单时 `original_status=from_state`（=repairing，应为**报修前状态 broken**）。报废申请被拒/取消 → `reject_to_original/cancel_damaged` 回 `repairing`，而 RepairAsset 已 FAILED：`complete_repair/fail_repair` 要求 IN_PROGRESS、`create_repair_asset` 要求 broken → 资产滞留「维修中」且无任何用户侧出路（仅 admin force-recycle 或二次报废） | `original_status` 改取送修前状态（RepairAsset 记录或状态机历史），reject/cancel 回 `broken` | `codegraph callers fail_repair` |
| NEW-04 | P2 | TOCTOU | `services/out_asset_service.py:60,75`（锁于 :161） | create_outasset | `outasset_previous_status` 取自锁前序列化器实例并先落库，再于锁内 FSM 校验 → 并发 recycle 后存了陈旧前态；后续删除出库 `cancel_outasset` 将资产回退到错误状态 | 前态改在行锁内重读 | `codegraph node _apply_outasset_to_asset` |
| NEW-05 | P2 | 审计吞没 | `core/audit_service.py:52-54`；`apps/unregisteredasset/services.py:89-97` | GenericAuditService.log_operation | `except Exception → logger.error → return None`，非资产域审计写失败仅留服务端日志；与 `operation_log_service.py:95-97`（re-raise）口径不一致 | 失败重抛或结构化降级策略二选一，全仓统一 | `codegraph node log_operation` |
| NEW-06 | P2 | 刷新竞态 | `apps/authusermanagement/services.py:197-209` | refresh_tokens | `check_blacklist` 与 `blacklist` 两步非原子，并发同 token 刷新可双发新令牌，绕过轮换重用检测 | `transaction.atomic + select_for_update`（OutstandingToken）或以黑名单插入 IntegrityError 为门 | `codegraph callers refresh_tokens` |
| NEW-07 | P2 | 越权（缺省 fail-open） | `core/permissions.py:192-210` | resolve_viewset_permissions | 未登记进 `admin_actions` 的自定义 @action 缺省回落 `IsAuthenticated` → 新增管理动作漏登记即对全体登录用户开放（漏配即越权） | admin_actions 非空的 ViewSet 缺省改 deny/IsAdminUser，显式 opt-in | `codegraph callers resolve_viewset_permissions` |
| NEW-08 | P2 | 传输安全 | `apps/authusermanagement/cookie_utils.py:25`；`config/settings/base.py:249` | set_auth_cookies | `JWT_AUTH_COOKIE_SECURE` 缺省 False：漏配环境（预发/误配生产）下 7 天 refresh cookie 走明文 HTTP | 缺省改 True，显式 opt-out | `codegraph node set_auth_cookies` |
| NEW-09 | P2 | 管理端旁路 | `services/asset_service.py:323`（docstring `asset_view.py:282-286`） | _run_manual_transition | admin change_status 仅校验 (current,target) 对，可打 `reject_to_original` 系边 → 孤儿 DamagedAsset 单据且 API 侧不可取消（cancel 要求 asset=damaged），只能二次改状态或 DB 手术 | 屏蔽 manual 入口的 reject_to_original 边或强制补录闭环 | `codegraph callers _run_manual_transition` |
| NEW-10 | P2 | 前端静默降级 | `vue-assetmanagement/src/api/request.ts:446-449` | useCache 回退 | GET 失败静默以陈旧缓存当成功返回（仅 logWarn，无错误标记），后端持续故障时用户无限期看旧数据 | 失败回退需在 ApiResponse 标记降级或提示 | — |
| NEW-11 | P3 | 并发 500 | `contract_service.py:162-177`、`employee_service.py:243-248`、`department_service.py:72-108`、`storage_service.py:51-57`、`asset_type_service.py:95-105` | create_* 系列 | exists→create 无锁且无 IntegrityError→DUPLICATE 映射（对照 `damaged_asset_service.py:43-69` 有锁+映射）；并发重复建号 → 未映射 500。有 partial unique 兜底，数据不脏 | 补 `re_raise_or_map_integrity_error` 同批收敛（DR-2） | `codegraph callers create_contract` |
| NEW-12 | P3 | 目录树并发 | `usermanagement/services/department_service.py:117-152,226-230` | move_department | 读+写+子孙 path/level 批量更新无 select_for_update（atomic 有），并发移动可写坏物化路径 | 行锁 + B12 TOCTOU 复检 | `codegraph node move_department` |
| NEW-13 | P3 | 契约参数 | `views/dashboard_view.py:53,66` | dashboard | 用 `limit` 参数（全仓唯一非导出消费点），与 page/page_size 契约不一致 | 改 page_size 或文档标注豁免 | — |
| NEW-14 | P3 | 前端缓存/路由 | `request.ts:433-442`、`request.ts:101-103`、`guards.ts:163` | get/redirectToLogin/auth gate | ①code!==0 也入缓存；②登出跳转丢当前路由（无 redirect 回跳）；③守卫仅验 token 真值不验过期 | 三处小改：缓存前验 code、带 redirect 参数、守卫解码 exp | — |
| NEW-15 | P3 | 状态机边维护 | `state_machine/transitions.py:66`、`scrapping.py:37-50` + `core.py:62-68` | — | ①DAMAGED→IN_USE 边业务不可达（in_use→damaged 禁止，仅 admin manual 可触发，见 NEW-09）；②to_damaged 与 repair_failed 共用 (repairing→damaged) cell、边名不参与校验，未来 caller 可借 to_damaged 绕过 repair-failure 语义 | 边名纳入 `_validate_transition` 或 docstring 收紧 | `codegraph node _validate_transition` |
| NEW-16 | P3 | 重复代码 | `core/batch_mixins.py:94,173` vs 各 service `MAX_BATCH_SIZE` 预检；`out_asset_service.py:227-231`/`recycle_asset_service.py:312-316`/`unregisteredasset/services.py:109-113` | — | ①批量长度预检与 mixin 内检重复（错误文案保留理由）；②字段白名单过滤块三处同形复制 | 抽共享 helper（DR-1/DR-2，同批清） | `codegraph callers batch_execute` |

### 台账终态

| ID | 状态 |
|---|---|
| NEW-01 ~ NEW-10 | **已确认 / 待修**（P1×3、P2×7，均具四要素：证据+影响面+修复建议+建议验证方式） |
| NEW-11 ~ NEW-16 | **已确认 / 待修**（P3，同批收敛即可） |
| 记录项 | `config/urls.py:70,117` `SELECT 1` 字面常量 → **非 SC-3 违规**；`scripts/clear_database.py` PG 化已在位（BF-123 闭环，反引号/`current_schema()`/token_blacklist 对调均已验证）；`RegisterSerializer` 批量赋值 clean（S8 在位）；`tokenObfuscator` 改名后安全声明与实现一致 |

## §三 分域结论与上线判定

| 分域 | 结论 |
|---|---|
| 状态机（资产+合同） | **FSM 零旁路**：全仓 `asset_current_status`/`contract_status` 写点逐一归类，全部经 AssetFSM/ContractFSM 或 serializer 同值 no-op；22 条边表-实现双向完备；锁纪律（select_for_update+B12 TOCTOU）全域一致。遗留 NEW-03（fail_repair 前态）、NEW-09/NEW-15（admin 旁路面） |
| 鉴权/RBAC | 密钥四层环境 clean；RBAC 类内无升级路径；cookie 毒化回退严格 401。遗留 NEW-06/07/08（轮换竞态、fail-open 缺省、Secure 缺省） |
| 服务层 | 锁/幂等/事务纪律成熟；遗留审计吞没（NEW-05）、并发建号 500（NEW-11）、目录树无锁（NEW-12） |
| API 契约 | 响应根结构**零旁路**（唯一 raw Response 在 docstring）；枚举 8 键前后端一致；分页参数合规（除 dashboard limit，NEW-13）；**分页排序缺口为最大契约面问题（NEW-02）** |
| 前端 | 8 键枚举 clean + 漂移守卫测试；401 刷新单飞（refreshPromise 单例）；XSS 零命中。遗留 NEW-10/14 |
| 机械门禁 | 覆盖率 88.88% ✓｜BR-4/BR-6 ✓｜SC-1/SC-3 ✓｜SC-8 留痕（CI security-scan.yml 权威）｜**测试 1 failed（NEW-01，假红非生产缺口）** |

### 上线判定：**有条件上线**

无 P0；SC 红线全绿、契约根结构与枚举全绿、状态机零旁路、覆盖率与规模护栏达标。上线前置条件（按序）：
1. **修复 NEW-01**（测试假红，恢复全量绿门禁——不修则每次 CI 必红，属发布阻断）；
2. **修复 NEW-02**（分页排序，model 补 Meta.ordering 最小改动，16 测试文件回归面）；
3. NEW-03 评估排期（低频但用户可触发的状态搁浅，修复方向明确）；
4. P2/P3 各项随批次收敛（NEW-04~16），不构成单独上线阻断。

### 评审结论（阶段 5 自审）

- 证据可回查：P1×3 全部经主代理实证或 `codegraph impact/callers/affected` 论证（fail_repair：13 callers/15 符号；分页：16 测试文件；限流假红：隔离运行+override 实验双重实证）；
- 置信度：全部条目 ≥80% 置信方予收录；子代理结论经主代理抽查核验（FSM 旁路 clean 判定、契约零旁路均复核 grep 输出）；
- 只读纪律：本次会话未改动任何业务代码，仅新增本报告文件。
