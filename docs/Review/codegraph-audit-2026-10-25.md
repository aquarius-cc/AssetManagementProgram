# CodeGraph 全项目审计报告（2026-10-25）

> 依据：项目专属审计工作流（project-all-code-review 审计模式落地版 v1.2.0）· 全程只读，未改动任何业务代码。
> 背景：上轮 Merge-codegraph-audit-2026-10-20 的 M-01~M-39（BF-125~BF-144）已全部修复闭环（HEAD 5bd2833）。
> 本次定位：①上轮未覆盖域（通知子系统、unregisteredasset、导入/导出链）②上轮修复批次回归面 ③上线就绪判定。
> 方法：CodeGraph 索引健康（1,016 文件 / 18,080 节点 / 40,920 边，sync 后无告警）；6 个 explorer 子代理分域并行探索（共 68 次工具调用）+ 主代理语义综合与 impact 论证。

## §一 项目上下文

- 技术栈：Django 5 + DRF 3.17 + SimpleJWT（后端，230 源文件，五层架构 View→Service→Selector→Model→FSM）；Vue 3 + TS + Pinia + Element Plus（前端，composable/store 分层）。
- 分域清单（本次探索锚点）：

| 分域 | 锚点 | 覆盖历史 |
|---|---|---|
| 资产状态机 | apps/assetmanagement/state_machine/（constants/transitions/core + 4 mixin） | M-30 收紧后首审 |
| 合同状态机 | state_machine/contract_fsm.py | 与资产 FSM 同审 |
| 鉴权/注册/限流 | authusermanagement/、core/throttles.py、core/permissions.py | AUD-21/M-08~10/32 修复后首审 |
| 通知子系统 | apps/notification/（helpers/services/models/selectors/views/consumer） | 首次深查 |
| 未登记资产/导入/导出 | apps/unregisteredasset/、core/excel_export/、core/permissions.py CanExportExcel | 首次深查 |
| 前端请求层/守卫/缓存 | api/request.ts、api/asset.ts、router/guards.ts、composables/useKeepAliveReload.ts | BF-141 修复后首审 |
| BF-139~144 修复面 | contract/employee/department/storage/asset_type service、utils/update_whitelist.py、core/batch_mixins.py、前端三 composable | 回归抽查 |

- 上线相关遗留项承接：O-7（storage/asset_type 字典类读暴露，BF-127 留痕不改）；生产注册入口网络暴露 [待确认]（仓内无部署配置，由 fail-closed 开关兜底）。

## §二 问题台账

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 |
|---|---|---|---|---|---|---|---|
| AUD-45 | P2 | 可靠性 | apps/notification/helpers.py:58-70 + services/notification_service.py:37 | send_notification_on_commit | 部门审批广播逐收件人 INSERT（无 bulk_create），per-recipient `except Exception` 仅 warning 无重试/死信；on_commit 回调内 DB 抖动持久化失败静默丢失 | 批量化 bulk_create + 失败死信记录/重试；补偿机制单点收敛 —— **已修复 BF-145（2026-10-25：bulk+降级逐条+单次重试+死信日志，域内 54/0 + ruff/mypy 全绿）** | codegraph node send_notification_on_commit |
| AUD-46 | P2 | 分页稳定性（M-02 同型残留） | apps/unregisteredasset/models.py:263、apps/unregisteredasset/views.py:131、apps/notification/models.py:72 | UnregisteredAsset.Meta / Notification.Meta | 三处 ordering 无决胜键（`-created_at` 单键 ×2、`-discovery_date` 单键 ×1），同毫秒/同日并列跨页重复丢行 | 补 `["-created_at","-id"]` / `["-discovery_date","-id"]` 决胜键 + AlterModelOptions 迁移（CT-6 三步）—— **已修复 BF-146（2026-10-25：5 红证转绿 + 域 205/0 + 2 迁移 CT-6 全过；注意 views.py:131 为视图默认序非 Meta，`-id` 不入 ordering_fields 防契约变更）** | codegraph node UnregisteredAsset    |
| AUD-47 | P2 | 缓存失效遗漏（M-19 残留） | vue-assetmanagement/src/api/asset.ts:292 | markAssetAsBroken | mark-broken 仅清详情 key `/assets/assets/{code}/`，列表 key 为 `/assets/assets/?page=...` 不匹配 → 列表 5min 内旧状态（对照 :366 batch-delete 已用前缀 `/assets/assets/`） | mark-broken 追加列表前缀失效 —— **已修复 BF-147（2026-10-25：精确 pattern `/assets/assets/?` 而非宽前缀，cache 三点式单测 + API 层 1 红证转绿，32/32 + type-check/lint 全绿；同型残留 create/update/delete/batch-create 4 端点已登记账本 §六）** | codegraph callers markAssetAsBroken |
| AUD-48 | P2 | 竞态回滚缺失（M-39 修复不完整） | vue-assetmanagement/src/composables/useExportableAssets.ts:35,42-47 | fetchList | 页码请求前乐观写，catch 分支清 list/total 未回滚 currentPage → 失败后停留空页且 :51 早退使该页永久不可达（与账本「失败页码回滚」描述不符） | 记 lastLoadedPage，catch 回滚 currentPage —— **已修复 BF-150（2026-10-26：3 composable 同构落地 lastLoadedPage 回滚锚（含 usePagedList/useGroupedAssetList 两处 rg 直证同型）；4 红证转绿 + 三 spec 61/61 + 全仓 2277/0）** | codegraph node fetchList |
| AUD-49 | P2 | 并发兜底缺口（BF-139 不完整） | apps/usermanagement/services/employee_service.py:256-261 | EmployeeService.create | 兜底仅映射 employee_jobcode 单 token；Employee 另有 unique_employee_phone_not_deleted / unique_employee_auth_user_not_deleted（models.py:234-242），并发撞 phone/auth_user 原样重抛 → 500 | 扩 match_integrity_error_rules 双规则 | codegraph node match_integrity_error_rules |
| AUD-50 | P3 | 锁定投毒（DoS） | core/throttles.py:92 + apps/authusermanagement/views.py:298,316 | LoginLockoutThrottle | login_fail_{username} 仅 username 维度：匿名者对任意用户名发 5 次失败即可锁 15 分钟；用户不存在也计数、空名共享桶 | username+IP 复合键，或不存在用户名不计锁定 | codegraph node LoginLockoutThrottle |
| AUD-51 | P3 | fail-closed 豁免面 | core/permissions.py:235（asset_grouped_view.py:148、unregisteredasset/views.py:139 即传 []） | resolve_viewset_permissions | admin_actions 为空列表时写方法缺省 IsAuthenticated，fail-closed 不生效，未来复用空清单新增写 action 即对全体登录用户开放 | 空清单断言禁止或同走 admin_permission | codegraph callers resolve_viewset_permissions |
| AUD-52 | P3 | 查询一致性 | apps/notification/selectors.py:56 + views.py:55 | list_for_user / unread_count | 全部通知查询不过滤 is_deleted（软删通知仍在列表与未读计数）；unread_count 绕过 Selector 层（DR-3） | 统一 Selector 口径 + is_deleted 过滤 —— **已修复 BF-148（2026-10-25：3 红证转绿 + 域 60/0 + mark_read/mark_all_read 同批口径扩充（写下沉 Service）；全仓无 is_deleted=True 写入者，属防御性一致）** | codegraph node unread_count |
| AUD-53 | P3 | 契约脆弱 | apps/notification/helpers.py:36 等 | send_notification_sync | notification_type/priority 裸字符串传递，未引用模型 TextChoices | 类型化为 Notification.NotificationType/Priority —— **已修复 BF-149（2026-10-25：service 五入口签名+默认值类型化 + 调用方 8 字面量枚举化 + 契约锚 1 条；View query param 保持 str，异步版零调用方仅注解，零运行时契约变化；与 BF-148 同提交）** | codegraph node send_notification_sync |
| AUD-54 | P3 | 开放重定向边角 | vue-assetmanagement/src/views/LogIn.vue:241 | redirect 校验 | 拒绝 `//` 但未拒绝 `/\evil.com`（部分浏览器归一化为协议相对跳转）；现经 router.push 风险低 | 补 `\\` 起始拒绝 —— **已修复 BF-151（2026-10-26：提取 sanitizeRedirect 共享纯函数（src/utils/redirect.ts），LogIn.vue 与 request.ts buildLoginRedirectUrl 两处调用点收敛接线（DR-1）；4 红证转绿 + 消费点 64/64 + 全仓 2277/0）** | codegraph node redirectToLogin |
| AUD-55 | P3 | 缓存失效过宽 | vue-assetmanagement/src/api/asset.ts:366 | batchDeleteAssets | 前缀 `/assets/assets/` 连带清非详情端点缓存（方向安全：只多取不脏读） | 精确化 pattern 或留痕接受 —— **已修复 BF-152（2026-10-26：裁决留痕接受宽前缀（入参 asset_code≠recordcode 无法逐条精确化，方向安全）；同批销 BF-147 残留——update/delete/batchCreate 补列表精确失效 `/assets/assets/?`（create 经拦截器天然覆盖），3 红证转绿 + asset.spec 23/23 + 全仓 2277/0）** | codegraph node batchDeleteAssets |
| AUD-56 | P3 | FSM 例外域（已声明） | apps/assetmanagement/state_machine/unregistered.py:56,88,126 | S1/S2/S3 场景 | 未登记资产直接赋值脱离 VALID_TRANSITIONS 表（自述跳过校验，有前置状态守卫）；表更新时此处不会同步收敛 | 不修，登记例外 + transitions.py 注释互指 | codegraph node VALID_TRANSITIONS |
| AUD-57 | P3 | DR-3 口径 | apps/usermanagement/services/employee_service.py:246 | 预检存在性 | 裸 `Employee.objects.filter().exists()`，同批 storage/asset_type/department 均走 Selector | 统一走 Selector | codegraph callees create |
| AUD-58 | P3 | token 存储（已知取舍） | vue-assetmanagement/src/stores/auth.ts:95 | encodeToken | bearer 通道 token 混淆后落 localStorage（XSS 可还原）；cookie 通道 httpOnly 仅内存——双轨不对称 | 不采纳（留痕）；长期建议收敛单轨 httpOnly | codegraph node encodeToken |
| DOC-1 | 文档 | 账本错位 | core/batch_mixins.py:44 | apply_field_guard | BF-144 账本所述「apply_field_guard 双 helper」全仓零命中；字段守卫实为 utils/update_whitelist.py 两函数——登记与实现错位，非代码缺陷 | 账本订正 BF-144 措辞 | rg "apply_field_guard" |

状态标记：全部 15 条均为「已确认」（证据直证）；无「不采纳」条目（AUD-58 为留痕性不修、AUD-56 为已声明例外，均给出处置意见）。本 skill 不产生「已修复」状态。

## §三 分域结论与修复建议（按优先级排序，同型归批）

### 分域结论

| 分域 | 结论 | 佐证 |
|---|---|---|
| 资产/合同状态机 | **健康**。M-30 边名必校落地正确（12 处 Mixin 调用全传具名边名，manual 路径查表取值）；19 条主表边全有正向用例；合同 8 键与 FSM 逐值一致、无旁路。仅 2 条 P3（回退族边不校验、unregistered 例外域均已声明） | 探索①「已核对无问题」8 项 |
| 鉴权/注册/限流 | **健康**。AUD-21 收口、M-08/09/10/32 修复全部实证落地；11 个 ViewSet admin_actions 无漏登记。仅 3 条 P3 设计级（AUD-50/51 + 非密码失败计入锁定） | 探索② 8 项核对 |
| 通知子系统 | **首次深查，2 条 P2 + 4 条 P3**。on_commit/权限隔离/WS 认证/索引设计均正确；缺口集中在「失败静默无补偿」（AUD-45）与查询口径（AUD-52） | 探索③ 7 项核对 |
| 未登记资产/导入/导出 | **健康度最高**。无上传攻击面（全仓无文件上传端点）；导出流式 + 行级隔离 + CanExportExcel 全覆盖；批量导入 fail_items 逐行定位、不绕 FSM/审计。2 条 P2 均为 M-02/M-19 同型残留 | 探索④ 9 项核对 |
| 前端请求层/守卫/缓存 | **基本健康**。M-29①②③ 落地正确（code===0 入缓存、degraded 标记、redirect 单飞刷新）；缺口为 mark-broken 失效遗漏（AUD-47）与 2 条 P3 边角 | 探索⑤ 6 项核对 |
| BF-139~144 修复面 | **修复质量高，2 处不完整**（AUD-48/49）+ 1 处账本错位（DOC-1）；storage/asset_type name unique 约束实存、BE-2 定序锁/BE-3 下沉/BE-4 收敛均实证 | 探索⑥ 6 项核对 |

### 修复建议（4 个批次 + 文档订正，可交接修复 skill）

| 批次 | 条目 | 优先级理由 | 建议验证方式 |
|---|---|---|---|
| 批次 G — M-02 同型收尾 | AUD-46（3 模型 Meta 决胜键 + 迁移） | 与 M-02/BF-128 同型，修复范式现成（authusermanagement 已有先例），一次迁移收敛 | 分页稳定性护栏用例（两页无重复丢行）+ CT-6 三步 + PG 分页用例 |
| 批次 H — 通知可靠性 | AUD-45（bulk_create + 死信）+ AUD-52/53（查询口径/类型化） | 通知是审批流程关键触达路径，静默丢失直接影响业务闭环；影响面 `codegraph impact send_notification_on_commit` = 39 符号（含 3 个测试锚点） | test_notification.py 既有 on_commit 用例保持绿 + 新增「持久化失败留死信」用例 |
| 批次 I — 前端残留 | AUD-47（失效前缀）+ AUD-48（页码回滚）+ AUD-54/55 顺手 | AUD-47/48 均为上轮修复的直接残留，回归面小、契约零变更 | mark-broken 后列表重取断言；失败回滚页码用例 |
| 批次 J — 后端余量 | AUD-49（Employee 双规则）+ AUD-50/51/57 + AUD-56/58 留痕 | AUD-49 是并发 500（与 BF-139 同型，范式现成）；AUD-50 属设计裁决需拍板（投毒面 vs 暴力破解防护的权衡） | 并发双写 mock 双消息形；锁定投毒用例（不同 IP 同用户名互不影响） |
| 文档订正 | DOC-1 | 账本与实现错位会误导后续回查 | BF-144 措辞订正 + rg 验收 |

## §四 上线就绪判定

**结论：有条件可上线（无阻断项）。**

| 检查项 | 结果 | 证据 |
|---|---|---|
| 后端测试/覆盖率 | ⚠️ 本次未重跑全量（pytest 超会话工具 300s 上限）——引用最近提交门禁记录：BF-144（dc5d6ca）2184/0 全绿、cov 89.71%、双 Service 98.43%/97.34% | Fact-1 留痕，CI 为权威门禁 |
| 后端 ruff + mypy --strict | ✅ 本次新跑：All checks passed / 0 issues in 230 files | 本次执行输出 |
| 前端 type-check + lint | ✅ 本次新跑：vue-tsc --build 0 错、eslint 0 错 | 本次执行输出 |
| 前端测试/变异 | ⚠️ 未重跑——引用 BF-143/144 记录：2267 用例 0 failed、stryker 80.02 ≥80 | Fact-1 留痕 |
| 生产配置 | ✅ base.py:258 JWT_AUTH_COOKIE_SECURE default=True + production.py:66 硬编码 True；AUTH_SELF_REGISTRATION_ENABLED fail-closed（生产默认 false）+ 注册双通道收口（域②实证） | 本次源码核对 |
| 数据库迁移 | ✅ BF-139~144 五批均无迁移；makemigrations --check 由各批门禁覆盖 | 提交记录 |
| SC-1 密钥 / SC-3 SQL 拼接 | ✅ 六域探索零命中（本次未单独复扫，CI security-scan.yml 为权威门禁） | 探索综合留痕 |
| 已知接受项 | O-7 字典类读暴露（BF-127 留痕）；生产注册入口网络暴露 [待确认]（fail-closed 兜底）；AUD-58 token 双轨 | 账本留痕 |
| 本次新发现 P2 | AUD-45~49 共 5 条——**均不阻断上线**（可靠性/体验/边缘并发面，无数据损坏与越权），建议纳入下一修复周期（批次 G~J） | §二台账 |

**上线前置动作（建议）**：①生产网关确认注册端点暴露情况（AUD-21 [待确认] 销项）；②上线后观察通知触达（AUD-45 修复前，审批通知存在静默丢失可能，关键审批建议辅以列表内红点提醒——现 unread 徽标已可兜底感知）。

## 评审结论

- 探索阶段 6/6 域完成，68 次工具调用，每域均产出「问题清单 + 已核对无问题清单」双向证据。
- 台账 15 条全部满足五要素（级别/类型/file:line/symbol/回查命令）+ 修复建议 + 影响面/优先级/验证方式，置信度 ≥80（低置信候选已被子代理自滤）。
- 专项维度结论：CT-3 状态机旁路 = 0 处未声明旁路（2 处已声明例外留痕）；跨端契约 4 项 = 枚举键/分页参数/响应根结构/日期格式全部一致（域①③⑤核对）；SC 分流 = 密钥/SQL/上传零命中，SC-8 依赖审计以 CI 为权威；CT-2/DR-5/DR-6 = 全量门禁引用最近提交记录 + 快口径全新复跑双通过。
- 只读纪律：本会话未改动任何业务代码；唯一落盘为本报告文件。
