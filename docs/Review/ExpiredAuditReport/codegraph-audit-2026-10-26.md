# CodeGraph 全项目审计报告（2026-10-26）

> 依据：项目专属审计工作流 `project-all-code-review`（审计模式落地版 v1.2.0）。**全程只读，未改动任何业务代码**，交付物仅本报告。
> 与前序报告关系：承接 `Merge-codegraph-audit-2026-10-20`（M-01~M-39）与 `atmocode-codegraph-audit-2026-10-25`（AUD-45~55）。本报告**不重复**其域内语义结论，定位为「**门禁实测 + 上线就绪**」：前序两轮多以提交记录/CI 为权威，本会话**逐条实跑**了后端/前端全部本地门禁与两套依赖漏洞扫描。
> 方法：`codegraph status`（审计启动时 1,016 文件 / 18,080 节点 / 40,920 边 `✓ Index is up to date`；定稿复核时 1,022 / 18,161 / 41,105——随本报告等写入增长）→ 分域 `codegraph explore` → 语义诊断 → `rg` 结构事实 → **门禁命令实跑**（pytest 全量×3、ruff、mypy、vitest、prettier、ESLint、pip-audit、npm audit、四护栏、CT-6 两步）。

## §一 项目上下文

- **技术栈**：后端 Django + DRF 3.17.2 + SimpleJWT（五层 Model → Serializer → Service → Selector → View，状态机 `state_machine/` 独立成域）；前端 Vue 3.5 + TS + Pinia + Element Plus（`api/` + `stores/` + `composables/` 分层）。仓库为 superproject + 两个 git 子模块（backend / frontend）。
- **规模**：CodeGraph 索引（定稿复核时）**1,022** 文件（python 484 / ts 387 / vue 120 / js 18 / yaml 13），18,161 节点 / 41,105 边；后端 `.py` 文件 **464**（含 `migrations/` 144，排除 migrations 后 387；`mypy` 口径 230 source files），后端测试全量 **2,196** 用例；前端 **176** 文件 / **2,277** 用例（2026-10-26 10:03 复跑订正：初稿所记「175 / 2,267」为早前时点数据，以本数为准）。
- **分域清单与锚点**：

| 分域 | 图谱锚点 | 本会话查法 |
|---|---|---|
| 资产状态机 | `state_machine/constants.py` AssetState（8 态）、`transitions.py` VALID_TRANSITIONS、`core.py` AssetFSM、4 个 transitions mixin | explore + 规则表逐行比对 + 全仓写点扫描 |
| 合同状态机 | `state_machine/contract_fsm.py`（ContractState / ContractFSM / `_CONTRACT_TRANSITIONS`） | explore 读源码 |
| API 响应契约 | `utils/response_utils.py` success_response | `rg 'return Response({'` 全 View 扫描 |
| 前端状态枚举 | `vue-assetmanagement/src/types/asset.ts`、`types/outasset.ts` | 读源码比对 8 键 |
| 鉴权 / 行级隔离 | `core/permissions.py`、`core/department_scope.py`、各 ViewSet `get_permissions` | `rg permission_classes` + `get_queryset_for_user` 落点统计 |
| 并发与锁 | `core/locks.py`、各 Service `select_for_update` | `rg select_for_update`（18 文件命中） |
| 迁移 | `apps/*/migrations/`（assetmanagement 0001~0024，0019 为 merge 节点） | CT-6 两步实跑 |
| CI 门禁 | `.github/workflows/{ci,security-scan,duplicate-guard,migration-check,ci-cd}.yml` | 逐 job 读 `run:` 与 `if:` |
| 本轮门禁实测 | 后端 pytest/ruff/mypy、前端 vitest/tsc/eslint/prettier、pip-audit/npm audit | 全部本地实跑 |

- **会话期间仓库状态**：superproject HEAD 由 `5bd2833` 前移至 `7cf6f70`（`master...origin/master [ahead 2]`），backend 子模块 HEAD `2cdca12`（与 origin 同步），frontend `bac65a7`。同期另一审计会话在 `docs/Review/` 新增 `atmocode-codegraph-audit-2026-10-25.md` 并删除 `codegraph-audit-2026-10-25.md`。**本报告所有 file:line 以 2026-10-26 09:5x 实读为准，回查前请先 `git log -1` 确认锚点未漂移。**

## §二 问题台账

> 列口径：级别 P0 阻断/高危 · P1 重要 · P2 优化 · P3 建议；「回查命令」为 codegraph 直达符号；状态仅本 skill 允许的三种（已确认 / 待修 / 不采纳），**不含「已修复」**。

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 影响面 | 优先级 | 建议验证方式 | 状态 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AUD-56 | **P0** | 依赖漏洞 SC-7 | `asset_management_backend/requirements/base.txt:13-16,45-46` + CI `security-scan.yml:172-173` | `pip-audit --requirement requirements/base.txt` | pip-audit 实测 **46 个已知漏洞 / 3 个包**：DRF 3.17.2 ×3（fix 3.18.2，其中 2 项 CVSS **7.5**：GHSA-33wh-fxxf-88vv Accept-header CPU DoS、GHSA-3547-9m27-7rxg JSONParser 攻击者指定 codec；另 GHSA-xw6w-gcfp-cf8m TokenProxy.delete 撤销失效 5.9）、pillow 12.3.0 ×37（fix 13.0.0，抽样 GHSA-78g4-xqwv-q3g8 CVSS **8.1**）、twisted 26.4.0 ×6（fix 26.10.0rc1，抽样 CVE-2026-115778 CVSS **7.5**）。CI 为 fail-closed（仅 `--ignore-vuln CVE-2026-106454`），触发即 exit 1。**死结**：`base.txt` 红线明令 DRF「不得升到 3.18.x」（many=True 错误响应 list→dict 破坏根 §3 契约），而修复线恰为 3.18.2 | 分三批走根级 §5 变更流程：① pillow 12.3.0→13.0.0、twisted→26.10.0 正式版（无契约耦合，先解 43 项）；② DRF 3.17.2→3.18.2 需**先**出契约影响评估（many=True 错误响应结构、schema 基线重导、前端 error 消费点回归）再决定升级或补丁策略；③ 升级后重跑 `pip-audit -r requirements/base.txt` 归零 | `codegraph node AssetStatus`（无关符号，用 `pip-audit -r requirements/base.txt` 复验） | 安全门禁（SC-7 阻断合并/部署）+ 跨端响应契约变更流程 | **高**（先无耦合项，后契约项） | `pip-audit -r requirements/base.txt` exit 0；CI security-scan `Python 依赖安全扫描` job 绿 | 待修 |
| AUD-57 | **P1** | 门禁失败（ruff format） | `apps/notification/helpers.py:13`、`apps/notification/selectors.py:77`、`apps/notification/services/notification_service.py:70`、`apps/unregisteredasset/views.py:131` | `ruff format --check .` | 本地实跑（ruff **0.17.1 = dev.txt 钉版 = CI 同版**）：**4 files would be reformatted → exit 1**。四文件最后改动均落在今日提交（`2cdca12` BF-148/149、`f3382de` BF-145/146）且子模块已与 origin 同步。CI `ci.yml:37` 为**无容错** step `ruff format --check .`，故 `backend-lint` job 应为红 | `python -m ruff format .` 仅作用于上述 4 文件 → 复跑 `ruff check .` / `ruff format --check .` / BR-4·BR-6 护栏（format 会重排行数，见 ci.yml 注释）→ 提交 | `codegraph node send_notification_on_commit` | CI 后端静态门禁全红 → **阻断部署链路**（ci-cd 前置门禁） | **高**（一条命令可解） | `ruff format --check .` exit 0 + BR-4/BR-6 护栏 PASS + CI `backend-lint` 绿 | 待修 |
| AUD-58 | **P1** | 依赖漏洞 SC-7 | `vue-assetmanagement/package.json`（`axios@1.20.0` → `follow-redirects@1.16.0`） | `npm audit --omit=dev` | 实测 **1 high**：`follow-redirects 1.16.0`（GHSA-q3jh-wrc6-jgq8 跨域凭据剥离绕过、GHSA-8r9p-f939-6h3c 敏感头正则转义泄露），属**生产依赖**（`--omit=dev` 仍命中）。CI `security-scan.yml:216` 跑 `npm audit --audit-level=high --omit=dev` → exit 1 | `npm audit fix`（或 `overrides` 钉 `follow-redirects >= 1.16.x` 修复版），提交 lockfile 后复跑；若 axios 需连带升版，按依赖变更走提交流程 | `codegraph node requestInterceptor`（无关符号，用 `npm audit --omit=dev` 复验） | 前端供应链安全门禁 → 阻断合并/部署 | **中高** | `npm audit --omit=dev` exit 0；CI `Node.js 依赖安全扫描` 绿 | 待修 |
| AUD-59 | P2 | 门禁失败（T17 format:check） | `vue-assetmanagement/src/api/asset.ts` | `prettier --check src/` | 实测 **exit 1**：`src/api/asset.ts` 存在格式偏差（工作区 clean，即已提交内容）。违反 frontend-testing-rules §九 T17「三项检查」；CI 当前**未接** prettier step（`ci.yml` 仅 ESLint / vue-tsc / complexity），故不会红 CI | `npx prettier --write src/api/asset.ts` → 复跑三项；建议把 `format:check` 补进 `ci.yml` 前端 job（补门禁属新红线，按根 §5.4 走沙盒） | `codegraph node assetAPI` | 本地提交规范；CI 暂不受影响 | 中 | `npx prettier --check src/` exit 0 | 待修 |
| AUD-60 | P2 | CT-7 环境漂移 | 本机 Python 环境 vs `requirements/base.txt` | `importlib.metadata.version` | 实测本机：Django **5.2.17**（声明 6.0.8）、PyJWT **2.10.1**（2.15.1）、requests **2.32.5**（2.33.0）、Pillow **11.3.0**（12.3.0）；而 mypy 2.1.0 / django-stubs 6.1.0 / ruff 0.17.1 / pytest 9.1.1 **与声明一致**。故本报告的 pytest/ruff/mypy 结论成立，但**运行时行为基线不等于 CI**（CT-7） | 本机执行 `pip install -r requirements/base.txt` 对齐 6.0.8 后复跑全量（本次未做，属环境变更，需用户授权） | `codegraph node AssetFSM` | 结论口径可信度（不改代码） | 中 | 对齐后复跑 `pytest -q` 仍 0 失败 | 已确认（留痕） |
| AUD-61 | P2 | 文档/注释失真 | `vue-assetmanagement/src/types/asset.ts:39` | `AssetCurrentStatus` 注释块 | 注释仍写 `in_use → damaged: 提交报废申请`，而 V2.8 业务决策已移除该边（`transitions.py` IN_USE 只有 recycle/mark_broken/mark_lost，backend-business-rules §三 :98 明示）；同文件 :46-53 枚举本身正确 | 删除该行或改写为 `in_use → recycled_pending → damaged` | `codegraph node AssetCurrentStatus` | 无运行时影响；误导后续开发按旧规则写代码 | 中低 | 注释与 `VALID_TRANSITIONS` 逐行一致 | 待修 |
| AUD-62 | P3 | 覆盖率洼地 | `apps/notification/services/notification_service.py:32,220-253,267` | `notification_service` | 实测该文件覆盖 **82%**（61 语句 / 漏 11，集中在 :220-253）。notification 服务**不在** CT-2 核心 90% 清单（后端 testing-rules §九 只列 4 个 app），故不触发红线 | 将 `apps.notification.services` 纳入 §九 专项清单（属规则收紧 → 根 §5.4 沙盒），或直接补测 :220-253 | `codegraph node notification_service` | 通知链路回归保护 | 低 | `pytest --cov=apps.notification.services --cov-fail-under=90` | 待修 |
| AUD-63 | P3 | 静默吞异常 | `apps/usermanagement/services/department_service.py:145-146`、`apps/assetmanagement/selectors/out_asset_selector.py:117-118` | `except Department.DoesNotExist: pass` / `except (ValueError, TypeError): pass` | 两处裸 `pass` 不留日志：前者静默放弃部门引用，后者把日期解析失败静默当空值，排障时无痕迹（对照 `core/exception_handler` 与 v1.10 已清空包的先例） | 补 `logger.debug/warning` 一行（不改控制流），或按语义收敛为显式默认值 | `codegraph callers resolve_asset_department_codes` | 可观测性 OC-2 弱化（非阻断） | 低 | 加日志后跑受影响用例仍绿 | 待修 |
| AUD-64 | P3 | 交付物并发漂移 | `docs/Review/` | `codegraph-audit-2026-10-25.md` | 会话期间另一进程删除旧报告并新增 `atmocode-codegraph-audit-2026-10-25.md`，superproject `ahead 2`；本报告锚点基于 2026-10-26 09:5x 快照 | 修复批次落地后按 `git log` 复核本报告 file:line 是否漂移，再交接修复 skill | `codegraph sync` | 报告可执行性（不影响代码） | 低 | 逐条回查命令可直达 | 已确认（留痕） |

**未采纳/不适用项（留痕）**

| 项 | 结论 | 理由 |
|---|---|---|
| SC-5 / SC-6 文件上传 | 不适用 | 全仓 `rg "request.FILES\|FileField\|ImageField\|upload_to"`（排除 tests/migrations）**0 命中**，无上传端点 |
| `scripts/clear_database.py:145,210` f-string 表名 | 不采纳 | 已由 `_validate_table_name` 白名单 + 保护表双重校验（SC-4 合规），非注入面 |
| `config/urls.py:70,117` `cursor.execute("SELECT 1")` | 不采纳 | 静态常量语句，无用户输入 |

## §三 分域结论与修复建议（按优先级排序）

### 3.1 上线就绪判定：**当前不可直接上线（两条 CI 红线在途）**

| 维度 | 实测结论 | 证据 |
|---|---|---|
| 后端静态门禁 | **红** | `ruff format --check .` exit 1（AUD-57，4 文件，backend 子模块已推 origin） |
| 后端类型/复杂度 | 绿 | `mypy . --strict` → `Success: no issues found in 230 source files`；`ruff check .` / `C90 max-complexity=10` 全通过 |
| 后端功能测试 | 绿 | 全量 `pytest -q` → **2196 passed / 0 failed**（1167.9s） |
| 后端覆盖率 CT-2 | 绿（**本地漂移口径，见 AUD-60**） | `--cov=. --cov-fail-under=80` → **89.77%**；Service 专项同轮派生：assetmanagement **98.43%** / authusermanagement **100%** / usermanagement **97.94%** / unregisteredasset **97.32%**（均 ≥90） |
| 后端依赖安全 SC-7 | **红** | `pip-audit -r requirements/base.txt` → 46 vulns / 3 pkgs，含 CVSS 7.5~8.1（AUD-56） |
| 前端功能测试 | 绿 | `vitest run --coverage` 及 10:03 定稿复跑 `vitest run` → **176 文件 / 2277 passed, 0 failed**（exit 0），`vitest.config.ts` 分层阈值（`src/**/*.ts` 80 / `src/stores/**` 90 / `.vue` 棘轮 stat 12.9·br 11.6·fn 10.9·lines 13.0）无一报错 |
| 前端类型/规范 | 类型+ESLint 绿，**Prettier 红** | `vue-tsc --noEmit` exit 0；`eslint .` exit 0；`prettier --check src/` exit 1（AUD-59） |
| 前端依赖安全 SC-7 | **红** | `npm audit --omit=dev` → 1 high（AUD-58） |
| 量化护栏（DR-5/DR-6/FR-6/FR-8） | 全绿 | `check_file_length_guard.py --print` 最长 `asset_view.py` **488 < 500**；`check_function_length_guard.py` `[PASS] 0 超限`；`check_frontend_invariants.py` composables 最长 196/200、stores 最长 394/500 |
| 重复治理护栏 G-1~G-5 | 绿 | `check_duplicate_invariants.py` → `[PASS]` |
| 迁移 CT-6 | 绿 | `makemigrations --dry-run` → `No changes detected`；`migrate --plan` 可正常输出（assetmanagement 0001~0024，0019_merge 收敛双分支） |

**[推测]** 上述两条红是否已反映在 GitHub Actions 上无法确认——`gh run list` 连续返回 HTTP 502（GitHub API 侧故障）。推断依据：backend 子模块 HEAD 与 `origin/master` 同步且 CI step 无容错。
**[可验证] 本地四门禁实测结论 — 依据：本会话命令输出（ruff 0.17.1 / mypy 2.1.0 / vitest 4.1.11 / pip-audit 2.x，均与声明版本或 CI 同版）。**

**建议的上线前动作顺序**（修复执行归 bug-surgical-fix / rigorous-dev，本 skill 不改码）：
1. **AUD-57**：`ruff format` 4 文件 → 复跑格式 + 两护栏 → 提交（解除 CI 红）。
2. **AUD-58**：`npm audit fix` → 复跑 `npm audit --omit=dev` + 全量 vitest → 提交（解除前端安全红）。
3. **AUD-56**：pillow/twisted 先行升级（43 项、零契约耦合）；DRF 3.18.2 单独立项做根 §3 契约影响评估（`api-schema-baseline.json` 重导 + 前端错误分支回归）。
4. **AUD-59/61/62/63**：随下一批次收尾；AUD-60 对齐本机 Django 6.0.8 后复跑全量，取得与 CI 同口径的最终数字。

### 3.2 资产专项维度（§5）结论

- **5.1 CT-3 状态机**：**0 处旁路**。全仓 `asset_current_status =` 写点仅存在于 `state_machine/` 包内（core.py:112、scrapping:80/131、out_recycle:74/109、unregistered:56/88/126）与模型字段定义；Serializer 侧 `asset_crud_serializers.py:134` 明示「更新排除 asset_current_status」、create 字段表不含该字段（B7 业务约束 7 合规）。`VALID_TRANSITIONS` 与 `backend-business-rules.md §三` 规则表**逐行一致**（含 V2.8 移除 `in_use→damaged`、repairing→damaged 双边元组、damaged 6 个 reject 目标、scrapped 终态）。13 条边在 `apps/assetmanagement/tests/` 全部有测试命中（最少者 `cancel_damaged` 3 次、`found_and_return` 4 次、`reject_to_original` 6 次）→ CT-3 满足。`cancel_outasset/cancel_recycle/cancel_damaged` 特殊回退与规则表「特殊回退操作」一致。
- **5.2 跨端契约 4 项**：① 响应根结构——全 View 无手写 dict 旁路（`rg 'return Response\({'` 仅命中 `urls.py:142`，位于模块 docstring 示例内，非代码路径）；② 状态枚举——后端 8 键与前端 `types/asset.ts` `AssetCurrentStatus` **完全一致**（注释失真见 AUD-61）；③ 分页——后端 `page_size_query_param="page_size"`（max 100），前端 api/stores/composables 一律 `page_size`，`pageSize` 仅作本地响应式状态、未入请求参数；④ 日期——`USE_TZ=True` + `TIME_ZONE=Asia/Shanghai` → DRF 输出 ISO 8601 带 `+08:00`，前端 `utils/Format.ts` 统一解析。
- **5.3 安全分流**：SC-1 无硬编码密钥（`.env` / `.env.development` 均 gitignore，`git check-ignore` 直证；`tokenObfuscator.ts` 无内置兜底 key，缺失即抛错）；SC-3 纯 ORM，无 `.raw()/.extra()`；SC-4 动态表名白名单；SC-5/6 无上传端点（不适用）；SC-7 **双端均红**（AUD-56/58）；OC-6 `/health/`、`/ready/` 存在（`config/urls.py:152-153`，含 DB/Redis 探活与 503 语义）。
- **5.4 测试与规模**：见 3.1 表（CT-2 绿、DR-5/DR-6/FR-6/FR-8 全绿、四护栏 PASS）。**本会话环境注记**：首次两次全量 pytest 出现 177 failed / 117 errors，隔离复跑与清理本地残留测试库连接后**第三次全量 2196/0 全绿**；[推测] 失败根因为本地 `test_asset_management_backend` 残留连接占用（`pg_stat_activity` 实测 1 个 blocking pid），非代码缺陷——已用「隔离复跑 + 清理后全量复跑」双重证据排除。

### 3.3 影响面与交接说明

- 台账 9 条中 **P0×1 / P1×2 / P2×3 / P3×3**，全部具备「file:line + symbol + 回查命令 + 建议验证方式」，可直接被 bug-surgical-fix / rigorous-dev 接手，无需二次定位。
- 排序建议：同域合并后按 **AUD-57（单命令）→ AUD-58（单依赖）→ AUD-56（分三批，含契约评估）→ 其余 P2/P3**；AUD-57 与 AUD-58 完成前不建议触发部署链路。
- 本 skill 不产生「已修复」状态；修复完成后由 resolution-fix-ledger-sync 登记 BF 条目并回写审查报告状态。

---

> 附：本报告证据命令清单（可复跑）
> `python -m pytest --cov=. --cov-fail-under=80 -q` ｜ `python -m ruff check .` / `ruff format --check .` / `ruff check . --select C90 --config lint.mccabe.max-complexity=10` ｜ `python -m mypy . --strict` ｜ `npx vitest run --coverage` ｜ `npx vue-tsc --noEmit` ｜ `npx eslint .` ｜ `npx prettier --check src/` ｜ `pip-audit -r requirements/base.txt`（需 `PYTHONUTF8=1`）｜ `npm audit --omit=dev` ｜ `python scripts/check_{file,function}_length_guard.py` ｜ `python scripts/check_frontend_invariants.py --print` ｜ `python scripts/check_duplicate_invariants.py` ｜ `python manage.py makemigrations --dry-run` / `migrate --plan`
