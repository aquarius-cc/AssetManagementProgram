# 融合审计报告（Merge，2026-10-26）

> 融合对象：① `docs/Review/atmocode-codegraph-audit-2026-10-25.md`（下称 **报告①**，台账 AUD-45~58 + DOC-1，共 15 条，方法=6 个 explorer 子代理分域语义探索）② `docs/Review/codegraph-audit-2026-10-26.md`（下称 **报告②**，台账 AUD-56~64，共 9 条，方法=门禁命令实测 + 依赖漏洞扫描）。
> 本文只读融合，不改动任何业务代码；唯一落盘为本文件。可复核命令统一列于 §六。
> 融合时点：2026-10-26 10:0x。仓库锚点：superproject `7cf6f70`（ahead 2）、backend `2cdca12`、frontend `bac65a7`。

## §一 两报告对比与融合处理

| 维度 | 报告①（10-25，语义探索） | 报告②（10-26，门禁实测） | 融合处理 |
|---|---|---|---|
| 优势 | 六域深度语义（状态机/鉴权/通知/导入导出/前端缓存/修复回归），每域有「问题 + 已核对无问题」双向证据 | 本地实跑全部门禁与双端漏洞扫描，数字可复跑 | 语义结论取①，门禁与安全数字取② |
| 短板 | 未跑全量 pytest/vitest（受 300s 工具上限），依赖安全「以 CI 为权威」未实测 | 未做六域逐项语义走查 | 互补，无重叠浪费 |
| 台账规模 | 15 条（P2×5 / P3×9 / 文档×1），其中 **12 条已修复（BF-145~152 + BF-154~157）+ M-51 复核不成立关闭（N 批留痕）** | 9 条（P0×1 / P1×2 / P2×3 / P3×3） | 合并 **24 条 → M-40~M-63** |
| **编号冲突** | **AUD-56/57/58** = FSM 例外域 / DR-3 预检 / token 双轨 | **AUD-56/57/58** = pip-audit / ruff format / npm audit | **必须重编号**：合并台账改用 M-40~M-63，保留「源报告 + 源 ID」列 |
| **上线结论冲突** | 「**有条件可上线**（无阻断项）」，依据多为提交记录与 CI | 「**当前不可直接上线**」，依据本地实测两条 CI 红 | **裁决见 §五：以②的实测为准**，①的结论在其证据边界内并不算错（见冲突裁决表） |
| 源报告内部瑕疵 | 第 45 行状态声明「全部 15 条均为已确认、不产生已修复状态」与表内 8 条「已修复 BF-xxx」标注**自相矛盾** | 无 | 裁决：以表内 BF 留痕 + ②的全量实测为准；建议订正①该行（见 M-63） |
| 数字订正 | — | 初稿「前端 175 文件 / 2,267 用例」为早前时点 | ②已就地订正为 **176 / 2,277**（2026-10-26 10:03 复跑，exit 0） |

## §二 合并问题台账（M-40 ~ M-63）

### 2.1 待修项（12 条，按级别排序）

| ID | 级别 | 源 | file:line | 问题摘要 | 修复 / 优化建议 | 建议验证方式 | 状态 |
|---|---|---|---|---|---|---|---|
| **M-40** | P0 | ②AUD-56 | `requirements/base.txt:13-16,45-46` + `security-scan.yml:172-173` | pip-audit 实测 **46 漏洞 / 3 包**：DRF 3.17.2×3（2 项 CVSS **7.5**：Accept-header CPU DoS、JSONParser 攻击者指定 codec；另 TokenProxy.delete 撤销失效 5.9）、pillow 12.3.0×37（抽样 CVSS **8.1**）、twisted 26.4.0×6（抽样 CVSS **7.5**）；CI fail-closed 即红。死结：DRF 修复线 3.18.2 撞 base.txt「禁升 3.18.x」（many=True 错误响应结构变更＝根 §3 契约） | 分三步：① pillow→13.0.0、twisted→26.10.0（**零契约耦合，先解 43 项**）② DRF→3.18.2 单独立项，走根 §5 变更流程（错误响应结构评估 + `api-schema-baseline.json` 重导 + 前端错误分支回归）③ 升级后 `pip-audit` 归零 | `pip-audit -r requirements/base.txt --ignore-vuln CVE-2026-106454` 双口径 8 项 + CI `Python 依赖安全扫描` 绿（终态需 L② + twisted 正式版） | **L① 已落地（10-26，BF-153）**：pillow→13.0.0 解 37 项，46→8；twisted 5 项等 26.10.0 正式版（rc1 不入生产 ASGI 链路）、DRF 3 项立项 L② 目标 3.18.3 走根 §5 [HALT]；CI python-audit 预期红 8 项，非回归 |
| **M-41** | P1 | ②AUD-57 | `apps/notification/helpers.py:13`、`apps/notification/selectors.py:77`、`apps/notification/services/notification_service.py:70`、`apps/unregisteredasset/views.py:131` | `ruff format --check .` **exit 1**（4 文件待格式化 / 416 已格式化），ruff 0.17.1＝dev.txt 钉版＝CI 同版；子模块已推 origin → CI `backend-lint`（`ci.yml:37`，无容错）**必红** | `python -m ruff format .` 仅上述 4 文件 → 复跑 `ruff check .` / `ruff format --check .` / BR-4·BR-6 护栏（format 会重排行数，见 ci.yml 注释）→ 提交 | `ruff format --check .` exit 0 + 护栏 PASS + CI 绿 | **K 批已落地（10-26）**：ruff format 4 文件（backend 2393c12），CI backend-lint 绿；本地多出 2 个「reformat」为纯 CRLF 行尾差异，提交 LF blob 已验证合规 |
| **M-42** | P1 | ②AUD-58 | `vue-assetmanagement/package.json`（axios 1.20.0 → follow-redirects 1.16.0） | `npm audit --omit=dev` **1 high**（GHSA-q3jh-wrc6-jgq8 跨域凭据剥离、GHSA-8r9p-f939-6h3c 头泄露），**生产依赖**；CI `security-scan.yml:216` 以 `--audit-level=high` 判红 | `npm audit fix`（或 `overrides` 钉修复版）→ 提交 lockfile → 复跑 audit + 全量 vitest | `npm audit --omit=dev` exit 0；CI `Node.js 依赖安全扫描` 绿 | **K 批已落地（10-26）**：follow-redirects 1.16.0→1.16.2（frontend 0240467，仅 lockfile、package.json 零改动；`npm audit fix` 会连带 bump dev 工具链故改 `npm update follow-redirects` 最小 diff），vitest 2277 绿，CI Node 依赖扫描绿 |
| **M-43** | P2 | ②AUD-59 | `vue-assetmanagement/src/api/asset.ts` | `prettier --check src/` **exit 1**（违反 T17）；CI 未接 prettier step（仅 ESLint/vue-tsc/complexity），故不红 CI | `npx prettier --write src/api/asset.ts` → 复跑三项；建议 CI 补 `format:check`（**属新红线 → 根 §5.4 沙盒流程**） | `npx prettier --check src/` exit 0 | **N 批已落地（10-26，BF-158，frontend 0e3189e）**：`npx prettier --write src/api/asset.ts` 单文件（实证全 src 唯一违规文件），T17 三项 0 错 + test:coverage 阈值三层过线（ts 93.37%/stores 96.8%/vue 18.45%）+ 全量 176/2277 绿；CI 补 `format:check` 门禁属新红线 → §5.4 沙盒后续，未入本批 |
| **M-44** | P2 | ②AUD-61 | `vue-assetmanagement/src/types/asset.ts:39` | 注释仍写 `in_use → damaged: 提交报废申请`，V2.8 已移除该边（枚举 8 键本身正确） | 删除或改写为 `in_store/in_use → recycled_pending → damaged`，与 `VALID_TRANSITIONS` 逐行一致 | 注释与后端转移表比对 | **N 批已落地（10-26，BF-158，frontend 0e3189e）**：:39 定稿改为 `recycled_pending → damaged: 提交报废申请（in_use 不可直接报废，须先回收 —— V2.8 业务规则）`——与 :37 行衔接成完整路径、无虚构边（审计建议中 `in_store → recycled_pending` 直达边实表不存在，未照抄）；V2.8 双证据：`ExpiredAuditReport/AtomCode-2026-09-23.md:111` + 10-26 报告 §3.2；其余 7 行注释与 `transitions.py` 实表比对一致 |
| **M-45** | P2 | ①AUD-49 | `apps/usermanagement/services/employee_service.py:256-261` | 兜底仅映射 `employee_jobcode` 单 token；`unique_employee_phone_not_deleted` / `unique_employee_auth_user_not_deleted` 并发冲突原样重抛 → **500**（同批 storage/asset_type/department 已接 `match_integrity_error_rules`，employee 未接） | 扩为多规则接入 `core/exceptions.py:147 match_integrity_error_rules`（范式现成，3 处先例可抄） | 并发双写 mock 断言双消息形 + 域测试全绿 | **M 批已落地（10-26，BF-154）**：接 `match_integrity_error_rules` 三规则（jobcode/phone/auth_user → `DUPLICATE_EMPLOYEE_JOBCODE/PHONE/AUTH_USER`）+ AI_REVIEW_NEEDED 标注 matcher unique-constraint 前提；M-26 锚点同步（phone/auth_user 用例由「原样重抛」断言改映射断言，非映射列 `employee_name` 传播屏障保留，commit `11056b8`）；test_services 真实约束 2 冲突用例（AU01/AU02 显式互异手机号隔离空串干扰）204 绿 |
| **M-46** | P3 | ②AUD-62 | `apps/notification/services/notification_service.py:220-253` | 实测覆盖 **82%**（漏 11 行，集中于 :220-253）；notification 不在 CT-2 核心 90% 清单，不触发红线 | 补测该段，或把 `apps.notification.services` 纳入 §九 专项清单（**规则收紧 → 根 §5.4 沙盒**） | `pytest --cov=apps.notification.services --cov-fail-under=90` | 待修（10-26 实测） |
| **M-47** | P3 | ②AUD-63 | `apps/usermanagement/services/department_service.py:145-146`、`apps/assetmanagement/selectors/out_asset_selector.py:117-118` | 两处 `except ...: pass` 无任何日志，排障无痕迹（弱化 OC-2） | 补 `logger.debug/warning` 一行，不改控制流 | 补日志后受影响用例仍绿 | 待修（10-26 复核仍在） |
| **M-48** | P3 | ①AUD-50 | `core/throttles.py:92` + `apps/authusermanagement/views.py:298,316` | `login_fail_{username}` **仅 username 维度**：匿名者 5 次失败即可锁任意用户名 15 分钟（锁定投毒 DoS）；不存在用户也计数、空名共享桶 | username+IP 复合键，或不存在用户名不计锁定 —— **属设计取舍，需人工拍板**（投毒面 vs 暴破防护强度） | 锁定投毒用例（不同 IP 同用户名互不影响） | **M 批已落地（10-26，BF-155，已拍板）**：拍板方案 = username+IP 复合键；`throttles.py _fail_key` 单点收敛 `login_fail_{username}_{ip}`，allow/record_failure/record_success 三处改用；IP 复用 `RequestContextMiddleware._get_client_ip` 单一信任边界（TRUST_PROXY_HEADERS=False，无 META 回退 `unknown`），日志带 `username@ip`；FAIL_KEY 8 处断言经常量统一改 + 跨 IP 独立计数/record_success 只清当前桶 2 新用例，lockout+keys 17 绿 |
| **M-49** | P3 | ①AUD-51 | `core/permissions.py:235`（`asset_grouped_view.py:148`、`unregisteredasset/views.py:139` 即传 `[]`） | fail-closed 判断为 `if admin_actions and ...`，**空清单时失效** → 落到缺省 `IsAuthenticated`；未来复用空清单新增写 action 即对全体登录用户开放 | 空清单断言禁止，或空清单同走 `admin_permission` | `resolve_viewset_permissions` 用例 + 新增空清单分支用例 | **M 批已落地（10-26，BF-156，已拍板方案 B）**：删 `admin_actions and`，空清单 + 写方法（或 method=None）无条件走 `admin_permission`，读路径缺省 IsAuthenticated 不变（docstring 重写保留只读端点例外条款）；空清单 POST 断言反转为 IsSystemAdmin + 补 GET 读路径屏障用例；schema 基线 `spectacular --validate` 重导**字节零漂移**（drf-spectacular 按 authentication 编码 security、不编码 permission 类，白名单判定空集即过）；test_batch_c_fixes 21 绿 + grouped/children/unregistered 212 绿 |
| **M-50** | P3 | ①AUD-57 | `apps/usermanagement/services/employee_service.py:246` | 裸 `Employee.objects.filter().exists()` 预检，同批 storage/asset_type/department 均走 Selector（DR-3 口径不一致） | 收敛到 `EmployeeSelector` | `rg` 断言该文件无裸预检查询 | **M 批已落地（10-26，BF-157，纯重构行为不变）**：`selectors.py` 新增 `exists_by_jobcode` / `get_employee_by_auth_user` / `exists_by_department` 三方法 + **复用既有 `get_employees_by_jobcodes`（DR-3 不重复实现）**；employee_service 3 处（:67 绑定链、:242 预检、:341 在岗字典）+ department_service :387 下沉；rg 两服务文件 0 裸查询（豁免恰 3 处：`:50` select_for_update 锁读 / `:250` create / `:389` bulk_update）；usermanagement 204 绿 |
| **M-51** | 文档 | ①DOC-1 | `core/batch_mixins.py:44` | BF-144 账本所述「apply_field_guard 双 helper」**全仓零命中**，实际字段守卫在 `utils/update_whitelist.py`——账本与实现错位 | 订正 BF-144 账本措辞 | `rg "apply_field_guard"` 结果与账本一致 | **复核不成立关闭（10-26，N 批处置留痕于本行，账本零改动）**：BF-144 条目（:9648-9695，内容 = M-27/35/38）全文无该措辞，且 `git log -S "apply_field_guard" -- docs/BugFixed/Bug修复活账本.md` 账本史零命中——**DOC-1 指控失实（挂错条目）**，「订正 BF-144」无的放矢；真双 helper 登记 = **BF-142 M-31**（:9558，`utils/update_whitelist.py:18 apply_whitelisted_updates` + `:51 filter_whitelisted_fields` 逐字一致），`batch_mixins.py:44` 实为 `ensure_batch_size`；`rg apply_field_guard` 全仓仅 2 处均为审计指控文本（本行 + 归档报告① DOC-1） |

### 2.2 已修复项（8 条，含融合验证）

> 全部来自报告①，标注 BF-145~152。**报告②的两轮全量实测对其构成独立回归验证**：backend `2196 passed / 0 failed`（HEAD 2cdca12 含 BF-145~149）、frontend `176 文件 / 2277 passed`（HEAD bac65a7 含 BF-147/150/151/152）。

| ID | 源 | 问题 | 修复留痕 | 融合验证 |
|---|---|---|---|---|
| M-52 | ①AUD-45 | 部门审批广播逐收件人 INSERT、失败仅 warning 无死信 | **BF-145** bulk+降级逐条+单次重试+死信日志 | ✅ 后端全量绿 |
| M-53 | ①AUD-46 | 3 处 Meta ordering 无决胜键 → 跨页重复丢行 | **BF-146** `-id` 决胜键 + 2 迁移（CT-6 过） | ✅ 后端全量绿 + CT-6 `No changes detected` |
| M-54 | ①AUD-47 | mark-broken 只清详情 key，列表 5min 旧状态 | **BF-147** 精确 pattern `/assets/assets/?` | ✅ 前端全量绿 |
| M-55 | ①AUD-48 | 页码乐观写、catch 不回滚 → 空页永久不可达 | **BF-150** 3 composable 同构 `lastLoadedPage` 回滚 | ✅ 前端全量绿 |
| M-56 | ①AUD-52 | 通知查询不过滤 `is_deleted`、unread 绕过 Selector（DR-3） | **BF-148** Selector 口径统一 + 同批扩充 mark_read/mark_all_read | ✅ 后端全量绿 |
| M-57 | ①AUD-53 | notification_type/priority 裸字符串未用 TextChoices | **BF-149** service 五入口类型化 + 8 调用点枚举化（零契约变更） | ✅ 后端全量绿 |
| M-58 | ①AUD-54 | 开放重定向未拒绝 `/\evil.com` | **BF-151** 提取 `utils/redirect.ts sanitizeRedirect`，两调用点收敛（DR-1） | ✅ 前端全量绿 |
| M-59 | ①AUD-55 | batch-delete 前缀失效过宽 | **BF-152** 裁决留痕接受宽前缀，同批补 update/delete/batchCreate 精确失效 | ✅ 前端全量绿 |

**⚠ 回归警示（融合新发现）**：BF-145~149 落地的 **4 个文件正是 M-41 待格式化文件**——即修复批次本身引入了 `ruff format` 回归。批次 K 必须「format → ruff check → BR-4/BR-6 护栏 → 全量 pytest」一次走完，防止再犯（ci.yml 注释已记 `210cfa7` 格式化致函数长度反弹的前科）。

### 2.3 留痕 / 不采纳项（4 条）

| ID | 源 | 内容 | 融合处置 |
|---|---|---|---|
| M-60 | ①AUD-56 | `state_machine/unregistered.py:56,88,126` 直接赋值脱离 `VALID_TRANSITIONS`（已声明例外 + 前置状态守卫） | **不采纳**（已声明例外）；建议 `transitions.py` 注释互指，防后续误判为旁路 |
| M-61 | ①AUD-58 | `stores/auth.ts:95 encodeToken` 混淆后落 localStorage（XSS 可还原），与 httpOnly cookie 通道双轨不对称 | **不采纳**（已知取舍）；长期建议收敛单轨 httpOnly |
| M-62 | ②AUD-60 | CT-7 本机漂移：Django 5.2.17（声明 6.0.8）、PyJWT 2.10.1（2.15.1）、requests 2.32.5（2.33.0）、Pillow 11.3.0（12.3.0）；mypy/ruff/pytest/dev 依赖与声明一致 | **已确认留痕**；优化动作：`pip install -r requirements/base.txt` 对齐后复跑全量，取与 CI 同口径的最终数字 |
| M-63 | ②AUD-64 | 报告并发漂移（会话期间 `codegraph-audit-2026-10-25.md` 被删、根仓 ahead 2）＋ ①报告第 45 行状态声明与表内 8 条「已修复」自相矛盾 | **已确认留痕**；裁决见 §一；建议订正①第 45 行为「表内已修复条目以 BF 提交 + ②全量实测为准」 |

## §三 分域结论融合

| 分域 | ① 语义结论（10-25） | ② 实测补充（10-26） | 融合结论 |
|---|---|---|---|
| 资产/合同状态机 | 健康；19 条主表边全有正向用例；2 条 P3 均已声明（M-60） | **旁路 0 处**：`asset_current_status` 写点仅在 `state_machine/` 包内；`VALID_TRANSITIONS` 与规则表逐行一致；13 条边测试命中≥3；Serializer 排除该字段 | **健康（双证）**，无待修项 |
| 鉴权/注册/限流 | 健康；3 条 P3 设计级（M-48/49 + 非密码失败计锁） | 11 ViewSet `get_permissions` 行级隔离核对一致；`/health` `/ready` 存在（OC-6 ✓） | **健康（双证闭环：M-48 复合键 + M-49 fail-closed 均已落地 10-26，BF-155/156）** |
| 通知子系统 | 首查：2 P2 + 4 P3，2 P2 已修（M-52/56/57） | 该域 **恰是 M-41 四个待格式化文件的所在地**；`notification_service.py` 覆盖 82%（M-46） | **功能面已闭环，工程面欠三笔**（格式/覆盖率/日志） |
| 未登记资产 / 导入导出 | 健康度最高；2 P2 已修；无上传攻击面 | `views.py:131` 即 M-41 之一；SC-5/6 **确认不适用**（全仓无 `request.FILES/FileField`） | **健康（双证）** |
| 前端请求层 / 守卫 / 缓存 | 基本健康；缓存类 P2 已修（M-54/59） | vitest **176/2277 全绿**、vue-tsc 0 错、eslint 0 错；原三处欠账**全销**：prettier（M-43 → N 批 10-26 format:check exit 0）、npm audit（M-42 → K 批）、注释失真（M-44 → N 批） | **功能面 + 供应链 + 规范面闭环**（CI 补 prettier 门禁建议留 §5.4 沙盒后续项） |
| BF-139~144 修复面 | 修复质量高，2 处不完整 + 1 账本错位 | ①所列 8 条已修复项**经②全量复跑间接验证通过** | **修复有效；余笔全收口（M-45/M-50 → BF-154/157；M-51 复核不成立关闭，N 批 10-26）** |
| 全局门禁/规模 | ruff check + mypy ✓、三项 ✓（本次跑）；测试/变异引用提交记录 | pytest 2196/0、cov 89.77%、Service 97~100%、四护栏 PASS、CT-6 ✓；**format 红、双端 audit 红** | **规模与测试全绿；静态格式已解红（K 批）、依赖安全余 8 项（L① 后已知未清）** |

## §四 修复与优化建议（统一批次计划，可交接修复 skill）

| 批次 | 条目 | 动作摘要 | 流程要求 | 验证门槛 | 预期收益 |
|---|---|---|---|---|---|
| **K — 门禁解红（立即）** ✅ 已落地 10-26 | M-41 + M-42 | `ruff format .`（4 文件，backend 2393c12）+ follow-redirects 1.16.2（frontend 0240467，`npm update` 最小 diff） | 常规修复，无契约变更 | `ruff format --check .` 0、BR-4/BR-6 PASS、`npm audit --omit=dev` 0、vitest 2277 绿 | 解除 CI `backend-lint` 与 `Node 依赖扫描` 两条红（✅ 均绿） |
| **L — 依赖安全（分三步，含契约评估）**（L① ✅ 已落地 / L② 待审批） | M-40 | ① pillow 12.3.0→13.0.0 解 37 项（BF-153）✅；twisted 5 项等 26.10.0 **正式版**（现仅 rc1，不入生产 ASGI 链路）② DRF 3.17.2→**3.18.3** **走根 §5**：契约影响评估（many=True 错误响应，实测 4 条证据见 BF-153 §五）+ schema 基线重导 + 前端错误分支回归 ③ 复扫归零 | ②属跨端契约变更 → **[HALT] 审批** | CI 镜像口径双跑（`--ignore-vuln CVE-2026-106454`）各 8 项 + 全量 pytest + `manage.py spectacular --validate`（原「exit 0」为不可达口径，已订正） | 解除安全门禁，消除 2×CVSS7.5 DoS 攻击面 |
| **M — 后端余量** ✅ 已落地 10-26 | M-45 + M-48 + M-49 + M-50 | Employee 多规则接入（**BF-154**）；锁定投毒改复合键（**BF-155**，拍板 = username+IP）；fail-closed 空清单收敛（**BF-156**，拍板 = 方案 B）；预检下沉 Selector（**BF-157**，纯重构，复用既有 jobcodes 方法） | 常规修复，无契约变更（M-49 schema 基线字节零漂移；M-45 同步改造 M-26 锚点属测试契约对齐） | 并发双写用例、锁定投毒用例、`rg` 无裸查询、全量 **2202/0**（feishu-webhook 404 用例复跑甄别为瞬态）+ Service cov 98% + 四护栏 PASS | ✅ 消除 1 个并发 500 面 + 1 个 DoS 面 + 1 个越权隐患 |
| **N — 前端与文档余量** ✅ 已落地 10-26 | M-43 + M-44 + M-51 | prettier 单文件格式化（M-43）；:39 注释按 `transitions.py` 实表 + V2.8 规则定稿（M-44）；M-51 **复核不成立关闭**（BF-144 无该措辞、账本史 `git log -S` 零命中，真登记位 = BF-142 M-31 :9558——原「订正 BF-144」无的放矢，**账本零改动**） | 常规修复 + 文档留痕，无契约变更；CI 补 format:check 门禁建议留 §5.4 沙盒后续 | 前端三项 0 + `test:coverage` 三层过线（ts 93.37/stores 96.8/vue 18.45）+ 176/2277 绿（frontend 0e3189e）；`rg apply_field_guard` 仅 2 处文档命中 | 规范闭环，误导项清零 |
| **O — 质量优化（低优）** | M-46 + M-47 | 补 notification 覆盖盲区；两处 `pass` 补日志 | 纳入 CT-2 清单属规则收紧 → §5.4 | cov≥90、用例仍绿 | 可观测性与回归保护增强 |
| **留痕跟踪** | M-60~M-63 | 例外互指注释、token 单轨长期项、CT-7 依赖对齐、源报告状态行订正 | 不阻断 | — | 结论可追溯 |

**顺序**：K（单命令解红）→ L① → M → N → O → L②（契约项单独立项）。K、L① 完成前不建议触发部署链路。

## §五 上线就绪综合判定（冲突裁决）

**融合结论：暂不可上线，先清 K 批（M-41/M-42），L 批按①的安全上线标准处理。**

| 检查项 | 报告①结论（依据） | 报告②实测（命令） | 融合裁决 |
|---|---|---|---|
| 上线总判定 | 有条件可上线、无阻断项（引提交记录/CI） | 不可直接上线（本地实测） | **以②为准**：两条 CI 红在途即为阻断 |
| 后端测试 | ⚠ 未重跑，引 BF-144 记录 2184/0 | `pytest -q` → **2196/0**（1167.9s） | 采用实跑数字 |
| 后端覆盖率 | 引记录 89.71% | `--cov-fail-under=80` → **89.77%**，Service 98.43/100/97.94/97.32% | 采用实跑（M-62 标注本地漂移口径） |
| 后端 `ruff check` + `mypy --strict` | ✅ 本次跑 | ✅ 一致（0/230） | **双证通过** |
| 后端 `ruff format` | 未测该项 | ❌ **exit 1（4 文件）→ CI backend-lint 必红** | **阻断**（M-41） |
| 依赖安全 SC-7 | 「以 CI 为权威」未实测 | ❌ pip-audit **46 漏洞/3 包**；npm audit **1 high** | **阻断**（M-40/M-42），且 ①② 均未覆盖此项，属本轮新增关键发现 |
| 前端测试 | ⚠ 引记录 2267 用例（其表内修复标注另引 2277） | `vitest run` → **176 文件 / 2277 passed**（10:03，exit 0） | 采用实跑，双报告数字在此对齐 |
| 前端 type-check/lint | ✅ 本次跑 | ✅ 一致 | **双证通过** |
| 前端 prettier（T17） | 未测 | ❌ `src/api/asset.ts`（CI 未接，不红 CI） | 非阻断 → **已解（N 批 10-26，`prettier --check src/` exit 0）** |
| 生产配置 / 注册入口暴露 | ✅ JWT cookie secure、注册 fail-closed；网络暴露 [待确认] | 未重复核查 | 沿用①，**上线前置动作保留** |
| 迁移 CT-6 | 引提交记录 | `makemigrations --dry-run` → `No changes detected` | 采用实跑 |

**合并后的上线前置动作**：
1. **代码**：清 K 批（M-41/M-42）→ `ruff format --check .` / `npm audit --omit=dev` 双 0。
2. **安全**：L①（pillow 37 项）✅ 已落地 10-26（BF-153，同口径 45→8）；L②（DRF 3 项，目标 3.18.3）按契约流程立项待 [HALT] 审批；twisted 5 项等 26.10.0 正式版——**不建议在 8 项已知未清状态上线**（待 L② + twisted 正式版归零）。
3. **运维**（沿用①）：生产网关确认注册端点暴露情况（AUD-21 [待确认] 销项）；上线初期观察通知触达（相关缺陷 M-52 已修，观察期可缩短）。
4. **口径**：以 CI（声明版本工具链）为权威复核 CT-7；本机依赖对齐（M-62）。

## §六 融合可复核命令

```bash
# 门禁
python -m pytest --cov=. --cov-fail-under=80 -q        # 后端全量（10-26 M 批后 2202/0，cov 89.77%）
python -m ruff check . && python -m ruff format --check .   # M-41（K 批后 exit 0，10-26）
python -m mypy . --strict                              # 0/230
ruff check . --select C90 --config lint.mccabe.max-complexity=10
cd vue-assetmanagement && npx vitest run               # 176 文件 / 2277 passed
npx vue-tsc --noEmit && npx eslint . && npx prettier --check src/   # N 批后 exit 0（10-26）
# 安全（M-40/M-42）
$env:PYTHONUTF8="1"; pip-audit --requirement requirements/base.txt --ignore-vuln CVE-2026-106454 --timeout 60   # L① 后：8 vulns / 2 pkgs（DRF×3 + twisted×5，待 L②/正式版；exit 1 为已知未清非回归，dev.txt 同口径同 8）
npm audit --omit=dev                                   # K 批后 0（10-26）
# 护栏与迁移
python scripts/check_file_length_guard.py --print      # max 488 < 500
python scripts/check_function_length_guard.py && python scripts/check_frontend_invariants.py --print
python scripts/check_duplicate_invariants.py
cd asset_management_backend && python manage.py makemigrations --dry-run   # No changes detected
```

## §七 审计票

```markdown
[审计票 - 必填项]
- 读取规范：已读 根 AGENTS v3.7.1 / backend AGENTS v9.3.3 / frontend AGENTS + 四份 Rules（业务+测试）
- CT-1[√] CT-3[√] CT-5[√] CT-7[√*]（*mypy/ruff/pytest/dev 与声明一致；Django/PyJWT/requests/Pillow 漂移见 M-62）
- DR-1[√] DR-5[√]（最长 488<500，无豁免）
- SC-1[√] SC-3[√]
- 跨端契约：未破坏（响应根结构 / 状态 8 键 / 分页 page·page_size / ISO8601+08:00 四项一致；DRF 升级项 M-40 已标 [HALT] 走 §5）
- 红线触发：无（本文只读；唯一写入为本文件与报告②的数字订正）
- 建议提交：是（建议提交本融合报告与报告②订正；业务代码修复按 §四 批次另行执行）
[审计票 - 自检项]
- 测试：CT-2[√] 89.77%/核心 Service 97~100%（本地口径） CT-4[√] CT-6[√]；mutmut(T7)/stryker(T16)[×] 未在本会话执行 → 以 CI/提交记录为权威
- DRY：DR-2[√] DR-3[√]（残留 M-50） DR-4[√] DR-6[√]
- 安全：SC-2[√] SC-4[√] SC-5/6[不适用·无上传端点] SC-7[× → M-40/M-42] SC-8[~]
- 可观测性：OC-1~OC-3[√] OC-4/5/7[~] OC-6[√]（/health /ready）
- AI鲁棒性：AR-1~AR-5[√]；AI行为 Fact-1[√]（数字均取本轮命令输出，未证项标 [推测]/[待确认]）；Style-1~Style-3[√]
- 覆盖率：整体 89.77%（≥80）/ 核心 Service 97~100%（≥90）
- §5 专项：状态机旁路 0 处（M-60 为已声明例外）；跨端契约 4 项全一致；SC 分流 = SC-1√ SC-3√ SC-4√ SC-5/6 N/A SC-7 双端红
[统计] 台账 24 条 = 待修 12（P0×1/P1×2/P2×3/P3×5/文档×1）+ 已修复 8（BF-145~152，经全量实测回归验证）+ 留痕不采纳 4
```

> 事实边界：GitHub API 本轮持续 502，CI 实际运行状态未能直证；「CI 必红」为本地同版本工具链（ruff 0.17.1 = dev.txt 钉版）与 CI step 无容错配置的**推断**，已在报告②标注 [推测]。其余数字均为本轮命令直接输出。
