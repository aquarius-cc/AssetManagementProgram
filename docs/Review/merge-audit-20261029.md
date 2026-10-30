# 三源审计报告融合件 — AssetManagementProgram

> 融合日期：2026-10-29
> 融合对象：
> - `docs/Review/workbuddy-audit-2026-10-29.md`（下称 **W 件**，project-all-code-review + code-quality-check + ponytail-review）
> - `docs/Review/atomcode-codegraph-audit-2026-10-29.md`（下称 **A 件**，CodeGraph 分域扫描 + 专项维度复核）
> - `docs/Review/full-audit-2026-10-29.md`（下称 **F 件**，架构/逻辑/前端/部署合规）
> 性质：只读融合，未修改任何业务代码。
> 融合方法：逐条对齐 → 冲突取证 → 仲裁定级 → 统一重编号 → 重排批次。
> 本轮额外取证：对 5 处关键冲突做了源码/配置/命令级复核（证据见 §二「复核取证」列），未取证的沿用原件结论并标 `[未复核]`。

---

## §一 融合口径说明

### 1.1 三件互补关系

| 件 | 主要视角 | 独有价值 | 主要盲区 |
|:---|:---|:---|:---|
| W 件 | CI 门禁实证 + 前端交互 + 可删代码 | 唯一实证了「流水线当前必红」的三条命令级证据 | 部署链路（Dockerfile / nginx / 证书）未覆盖；部分结论未做源码复核 |
| A 件 | CodeGraph 全量符号级扫描 | 唯一给出「通过项」的符号级反证（状态机旁路 / 契约 / SC 分流），并锁定 9 条新发现 P2/P3 | 只报新发现，已收口项不重复登记 |
| F 件 | 部署上线合规 + 仓库卫生 | 唯一覆盖 Docker 入口脚本 / TLS 首签 / 镜像卫生 / 隐私脱敏 | 后端测试未取全量，本地 Python 3.13 与 CI 3.12 漂移 |

### 1.2 仲裁原则

1. **实证优先**：有源码行号或命令输出可复现的结论 > 静态推断结论。
2. **范围优先**：两条结论冲突时，先看检索/判定范围是否一致——范围不同则判定为互补而非冲突。
3. **就低不就高**：无法证伪的高危判定不得直接降级；但**已被源码反证**的高危判定必须降级，避免误导排期。
4. **独立互证提级**：两份以上报告独立命中同一处，置信度上调。
5. **Fact-1 留痕**：未复核、未取证的项一律标注，不冒充事实。

---

## §二 三方结论冲突仲裁（11 条）

> 本节是本次融合的核心增值：三份报告对同一对象给出了**互相矛盾**的判定，直接合并会导致排期错配（把已声明的有意设计当成 P0 阻断，或把真实必红项当成「配置齐全」而漏排）。

| # | 冲突对象 | W 件判定 | A 件判定 | F 件判定 | **融合仲裁** | 复核取证 |
|:---|:---|:---|:---|:---|:---|:---|
| C-1 | `force_recycle_from_any` 状态机旁路 | **P0**，「绕过 AssetFSM」，任意非终态可强转 | 生产代码旁路 **0 处**；`unregistered.py` 三处为已声明例外（M-60） | 未发现旁路，`cancel_outasset` 属有意设计 | **降级为 P2（M-16）+ 保留一项 `[待核实]`**。理由：它是 `AssetFSM` 的 mixin 方法（`UnregisteredTransitionsMixin`），**不是绕过 FSM**；自带终态守卫（`unregistered.py:125-126` 拦 scrapped）；行内注释 `:129` 与 `transitions.py` docstring 均已锚定 M-60 例外。两件独立判定「已声明例外」成立。**保留的疑点**：该方法只写 `asset_current_status`，未见前态留痕写入，是否由调用方 `UnregisteredAssetService` 补 OperationLog 需核实 | 已读 `unregistered.py:92-129`，三方法结构一致、均带前置守卫与 M-60 锚点 |
| C-2 | CI 覆盖率命令 | **P0**，`--coverage.threshold` 已失效 | 未覆盖 | 未覆盖 | **维持 P0（M-18）** | 已读 `.github/workflows/ci.yml:422,424` → 两处确为 `npx vitest run --coverage --coverage.threshold=80/90`；`vitest.config.ts:33-37` 已改分层 `thresholds` 键（含注释「无前缀 key 会把 80 拖到 42% 直接假红」），CI 命令未同步 |
| C-3 | CI 门禁总体状态 | ruff 2×I001 + 5 文件未格式化 → 必红 | 未覆盖 | 「ruff / mypy strict … 覆盖完整」列为已达标 | **不构成冲突**：F 件评的是「门禁配置齐全」，W 件评的是「当前是否通过」。**以 W 件为排期依据，M-02 维持 P0** | 本轮实跑：`ruff check . --statistics` → `2 I001`；`ruff format --check .` → `5 files would be reformatted, 418 already formatted`。与 W 件完全一致 |
| C-4 | SC-3 / SC-4 SQL 注入 | **P1**，`scripts/clear_database.py:145,210` f-string 拼表名，判 SC-4 违规 | `.raw(/extra(/cursor.execute` 0 命中 → 通过 | 无 raw SQL → 通过 | **降级为 P3（M-17），SC-4 判「合规」**。理由：A/F 的检索范围为 `apps` + `core`，**不含 `scripts/`**，属范围盲区，W 件的命中真实；但 W 件漏看了守卫——两处调用前均有 `_validate_table_name()`（`clear_database.py:143`、`:203`），该函数做 `ALLOWED_TABLES` 白名单 + `PROTECTED_TABLES` 双重校验。SC-4 原文要求「动态表名必须经过白名单校验」，**已满足**，不构成违规 | 已读 `clear_database.py:120-146,203-213` |
| C-5 | 后端覆盖率 CT-2 | 「未实测」 | 后端全量 **90.09%**（CI run `40466576631`，BF-161 对账闭环） | 后端本地未取全量；前端 `.vue` 语句 12.98% / 分支 11.66% | **采信 A 件为后端权威口径（CT-7 合规，来自 CI 工具链）**；F 件的前端分层数字为**另一层**（`.vue` 组件层），两者不冲突、需并列呈现。融合后 CT-2 判 `[√]`，同时保留 F-03 组件层覆盖率偏低为独立整改项 | `[未复核]` CI run 编号未本轮直连核验，沿用 A 件留痕 |
| C-6 | 前端 RBAC | **P1-3**：两条死键 + 未命中即放行 + HardDiskSN 无门槛 | **FE-1** HardDiskSN 子树漏挂；**FE-5** `'/main/system'` 死条目 | 未覆盖 | **拆分合并为 3 条，HardDiskSN 提级为 P2**。W 与 A 在**互不知情**下独立命中同一处 HardDiskSN 与同一处死白名单 → 置信度上调。死条目清理降为 P3（M-32），默认放行与 HardDiskSN 分列 M-19(P1) / M-20(P2) | 交叉比对两件台账，`routes-main-system.ts:52-70` 与 `guards.ts:42` 指向一致 |
| C-7 | `core/throttles.py` 处置 | ponytail 建议 **delete**（-19 行），「与框架 ScopedRateThrottle 重复实现」 | 未覆盖 | **B-02** 建议新增 `ScopedRateThrottle` + `public_scan: 5/min` | **驳回 W 件的删除建议**。该文件含 `LoginLockoutThrottle`（连续失败 5 次锁 15 分钟，依据 `03-业务规则与状态机.md §4.6`）、原子失败计数 `_increment_fail_count`（M-24）、M-48 单一 IP 信任边界，**删除等于移除登录锁定安全特性**。与 F 件 B-02 不冲突：公开扫码限流用 DRF 原生 `ScopedRateThrottle`，登录锁定保留本文件 | 已读 `core/throttles.py` 全文 153 行 |
| C-8 | 列表页容量与卡顿 | 未覆盖 | **FE-6**：原生 el-table 无虚拟滚动，允许 500 档 → 卡顿 | **F-01**：前端选项含 200/500，后端 `MAX_PAGE_SIZE=100` 会静默截断 → 交互错觉 | **合并为 M-23（P2），并订正 A 件前提**：后端强制分页上限 100，用户选 500 实际只回 100 行，**「渲染 500 行卡顿」的前提不成立**。故主修动作是「前端选项收敛为 [20,50,100]」消除契约矛盾；虚拟滚动降为**可选增强**，不进必做批次 | 两件均载 `core/pagination.py` MAX_PAGE_SIZE=100 与 `core/constants.py` 一致 |
| C-9 | 文件上传 SC-5 / SC-6 | 判「通过」，称有扩展名 MIME 白名单 + 10MB + UUID 重命名 | 判「**N/A**，后端不存在文件上传/Excel 导入端点，批量走 JSON + ChoiceField」 | 判「无文件上传面」 | **采信 A 件**。本轮检索 `apps/` 下 `FileField\|MultiPartParser\|UploadedFile\|MEDIA_ROOT` **0 命中**，无上传落点。W 件所列 SC-5/SC-6 落地证据在后端代码中无可检索落点，标 `[存疑]`。处置：SC-5/SC-6 按「无面可评」计；**未来新增文件导入须从零补扩展名/MIME/大小三校验**（A 件提醒纳入工程备忘） | 本轮 `search_content` 于 `apps/` 全量检索，0 命中 |
| C-10 | 部署上线阻断面 | 只报 CI 侧 3 条必红 + 状态机 1 条 | 明言「新发现均为 P2/P3，不构成上线阻断」 | 报 D-01 / D-02 / B-01 三条 P1 上线阻断 | **并集采纳，去重后共 6 条上线阻断**（见 §五）。三件阻断面几乎不重叠：W 管流水线、F 管部署链路与隐私、A 管代码语义，属互补而非冲突 | — |
| C-11 | 未登记资产 N+1 | **P1-1**：`unregisteredasset/selectors.py` 全文 0 处 `select_related` | 未报 | 称「列表层使用 `select_related` 收敛人员关系」 | **不冲突，范围不同**：F 件泛指资产主模块，W 件特指 `unregisteredasset` 子模块。**M-04 维持 P1** | `[未复核]` 未逐行读该 selector，沿用 W 件 |

### 2.1 仲裁结果对排期的影响

| 影响 | 说明 |
|:---|:---|
| **P0 由 4 条降为 3 条** | C-1 将 `force_recycle_from_any` 从 P0 降至 P2——它是已声明例外，不是未登记的旁路。若不仲裁，会把一次「补注释/补测试」的工作量当成「封死高危旁路」排进阻断批 |
| **P1 由 4 条升为 6 条** | C-10 并入 F 件三条部署/隐私阻断，这是 W、A 两件共同缺失的面 |
| **SC-3/SC-4 由「违规」改为「合规」** | C-4 避免了一次误报；同时把 W 件的漏看（白名单守卫）补进台账 |
| **删除清单净减 19 行** | C-7 驳回 `core/throttles.py` 删除，避免误删登录锁定 |

---

## §三 融合后统一问题台账（41 条）

> 级别：P0 阻断（流水线必红/数据事故）· P1 上线阻断 · P2 一般缺陷 · P3 优化。
> 「来源」列保留原报告 ID，便于回溯原件。

### 3.1 后端（17 条）

| 统一 ID | 级别 | 类型 | 位置 | 问题 | 融合修复建议 | 来源 | 验证方式 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| M-01 | **P0** | 类型检查 | `views/_lifecycle_base.py:172,176,184`；`recycle_asset_view.py:140`；`hard_disk_sn_view.py:105,120` | mypy --strict 13 处：None not callable、arg-type 不匹配、`type: ignore` 错误码标错（写 attr-defined，实报 misc/arg-type） | 给 `update_serializer`/`model` 显式类型标注；修正 ignore 错误码 | W P0-2 | `mypy --strict .` 归零 |
| M-02 | **P0** | 代码门禁 | `tests/test_row_level_isolation_r1.py:13`、`views/_mixins.py:9` 等 7 文件 | ruff 2×I001 导入未排序；5 文件未格式化 | `ruff check . --fix` → `ruff format .` | W P0-3 | 本轮已复现，改后双命令 exit 0 |
| M-03 | **P1** | 隐私 | `usermanagement/employee_serializers.py:43,72`；`views/employee_view.py:125` | 员工手机号明文返回所有已登录用户；列表含 `employee_phone`，详情 `fields="__all__"`，而列表权限仅 `IsAuthenticated` | 按角色分级：普通用户返回 `138****0000`；仅资产/系统管理员返回明文；或拆 `EmployeeContactSerializer` 专用于授权场景。复用 `utils/mask_phone_number`（已存在未用） | F B-01 | 普通角色断言脱敏、管理员断言明文两条用例 |
| M-04 | **P1** | 性能 | `apps/unregisteredasset/selectors.py` | 列表/详情/导出三条链跨表取 `discovery_person__employee_name` 等未预加载，全文 0 处 `select_related` | 补 `select_related("discovery_person","approver","related_asset","result_asset")` | W P1-1 | 补 `assertNumQueries` 回归断言（与 M-10 同批） |
| M-05 | P2 | 限流 | `views/public_scan_view.py`；`config/settings/base.py` | 公开扫码仅用全局默认 20/min，无独立 scope；资产编码枚举空间仍可大量试探 | 新增 DRF 原生 `ScopedRateThrottle` + `public_scan: 5/min`；连续 404 IP 短时封禁。**不要动 `core/throttles.py`**（见 C-7） | F B-02 | 第 6 次请求断言 429 |
| M-06 | P2 | 分层 DR-3 | `views/out_asset_view.py:119`、`views/asset_view.py:279-342` | View 层手写 ORM 过滤链，未下沉 Selector | 收敛至 `Selector.get_queryset_for_user` | W P2-3 | Selector 单测 + 视图回归 |
| M-07 | P2 | 权限 | `storage_view.py:61`、`unregisteredasset/views.py:125`、`dashboard_view.py:50` 等 | 写操作仅 `IsAuthenticated`，无角色门槛，与 B11 意图不符 | 按 RBAC 矩阵显式标注 `permission_classes` | W P2-6 | 各端点越权角色断言 403 |
| M-08 | P2 | 死文件 | `apps/assetmanagement/signals.py` | 0 逻辑行，仅剩历史注释，无任何模块 import | 删除；迁移说明移入文档 | F B-03 | `rg import signals` 无命中后删除 |
| M-09 | P2 | 文档/死码 | `core/pagination.py:6`、`:120-144` | docstring 称「无参数返回全部」，与实现（强制分页上限 100）矛盾；末尾 25 行注释掉的旧实现 | 删 120-144，docstring 改为「强制分页、上限 100」 | F B-04 | 人工复核 docstring 与行为一致 |
| M-10 | P2 | 测试 | `apps/*/tests/` | 全库仅 1 个文件用 `assertNumQueries`，缺 N+1 回归断言，Selector 优化易被后续改动破坏 | 资产分组列表、生命周期列表补 2-3 条查询数断言 | F B-05 | 与 M-04 同批落地，互为护栏 |
| M-11 | P3 | 性能/吞异常 | `usermanagement/models.py:100-106` `Department.save` | 按祖先路径逐级 `get(path=…)` 循环单查 O(depth)；`except DoesNotExist: pass` 静默吞脏 path，缓存失效不彻底 | 改单条 `filter(path__in=paths)` 批量取；DoesNotExist 改 `logger.warning` 留痕 | A BE-1 | usermanagement 既有测试 + 脏 path warning 断言 |
| M-12 | P3 | 运维语义 | `management/commands/check_data_consistency.py:24-45` | 一致性巡检仅打印 issues，无退出码语义，接入 CI/定时任务无法据此告警 | 增 `--strict`（issues 非空退出码非 0）或接告警 | A BE-2 | `--strict` 退出码用例 |
| M-13 | P3 | 复用 | `selectors/outasset_selector.py` | 纯兼容再导出壳（`from .out_asset_selector import *`），与 `out_asset_selector.py` 双入口 | 更新 `__init__.py` 与 3 个测试的 import 后删壳 | F B-06 | 删除后全量测试通过 |
| M-14 | P3 | 数据一致性 | `selectors/asset_selector.py` `get_asset_detail_by_code` | 未带 `is_deleted=False`；当前唯一调用点前置已过滤，暂非漏洞，属易踩坑隐式契约 | Selector 内显式过滤软删除，或改名 `..._including_deleted` 明确语义 | F B-07 | Selector 单测断言软删除不可见 |
| M-15 | P3 | 依赖 | `requirements/base.txt:115` | `sentry-sdk[django]>=2.0,<3.0` 未精确 pin，与其余全量 `==` 策略不一致 | 锁定具体版本并纳入周检/renovate | F B-08 | 重装后构建可复现 |
| M-16 | P3 | 状态机 | `state_machine/unregistered.py:128` | `force_recycle_from_any` 只写 `asset_current_status`，未见前态留痕写入（**已声明例外 M-60，非旁路**，见 C-1） | ① 先核实调用方 `UnregisteredAssetService` 是否已补 OperationLog；② 若未补，在 Service 层补前态留痕；③ 不改 FSM 结构 | W P0-4（降级） | 构造 S2/S3 审批断言存在一条含 from_state 的操作日志 |
| M-17 | P3 | 加固 | `scripts/clear_database.py:145,210` | 标识符经 f-string 插值；**已有 `_validate_table_name` 白名单守卫，SC-4 合规**（见 C-4） | 纵深加固：改用 `psycopg2.sql.Identifier` 组合，保留白名单为第一道闸 | W P1-2（降级） | 传入非白名单表名仍抛 RuntimeError |

### 3.2 前端（18 条）

| 统一 ID | 级别 | 类型 | 位置 | 问题 | 融合修复建议 | 来源 | 验证方式 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| M-18 | **P0** | CI 部署 | `.github/workflows/ci.yml:422,424` | `npx vitest run --coverage --coverage.threshold=80/90`，vitest 4 已移除该参数；`vitest.config.ts` 早已改分层 `thresholds` 却未同步 CI | 两处改 `npm run test:coverage`（走配置文件 thresholds） | W P0-1 | 本轮已读文件确认；改后 CI `frontend-test` 转绿 |
| M-19 | **P1** | 权限 | `router/guards.ts:33-51` | 未命中白名单即**默认放行**，属 allow-by-default；写路由无兜底门槛 | 改 deny-by-default：未显式授权一律拒绝；或统一收口 `hasPermission` | W P1-3 | guards 回归用例覆盖「未登记路径 → 拒绝」 |
| M-20 | P2 | 权限 | `router/routes-main-system.ts:52-70` | HardDiskSN 子树（harddisksndetails/form/basicdetails）既不在 roleWhitelist 也无 `meta.requiredMinRole`；同段 storagedetails/assettypedetails/userdetails 均为 `system_admin`，硬盘序列号属同类系统配置却任意登录角色可读写 | 与 StorageDetails 对齐补 `requiredMinRole: 'system_admin'`；若业务确认开放，加注释锚定意图 | W P1-3 + A FE-1（互证提级） | `codegraph impact HardDiskSNDetails` + guards-rbac 回归 |
| M-21 | P2 | 资源泄漏 | `views/MainView.vue:19-21,46-54`；`AsideMenu.vue:111`；`useNotificationConnection.ts:199-201` | AsideMenu 在 MainView 渲染两处（桌面 aside + 移动 drawer），`useNotification` 每实例独立状态各自 `onMounted(connect())` → 抽屉展开建立第二条 WebSocket，双 onmessage 使未读数重复 +1；`messageHandlers` 在 disconnect 中从不移除 | `useNotification` 改模块级单例连接；`disconnect()` 增加 `offMessage` 清理 | A FE-2 | `useNotificationConnection.spec` 扩「双实例单连接」断言 + 移动端 drawer 手工冒烟 |
| M-22 | P2 | 定时器竞态 | `useNotificationConnection.ts:153-166,75-94` | `scheduleReconnect` 直接覆盖 `reconnectTimer`，`connect()` 入口不清 pending timer → 旧 timer 到期新建第二条并发 socket | `connect()` 入口统一 `clearTimeout(reconnectTimer); reconnectTimer = null` | A FE-3 | 断言重连后仅一条连接 |
| M-23 | P2 | 契约一致性 | `composables/usePaginationSearch.ts:67`；`components/commoncomponents/CommonList.vue:143` | 页容量含 200/500，后端 `MAX_PAGE_SIZE=100` 静默截断，产生「选了没生效」错觉（**A 件所述「渲染 500 行卡顿」前提不成立**，见 C-8） | 主修：两处收敛为 `[20,50,100]`；更大导出量走独立导出接口。虚拟滚动列为可选增强 | F F-01 + A FE-6 | 选项快照 spec + 与后端上限一致性断言 |
| M-24 | P2 | 打开性能 | `utils/excelExporter.ts:20` 及 6 个列表页静态 import（如 `OutAssetDetails.vue:113`） | ExcelJS（约 1MB chunk）每次进入列表页即被拉取，仅点击导出时才用 | 改为导出函数内 `await import('exceljs')` | F F-02 | 构建产物对比：列表页首屏不再含 exceljs chunk |
| M-25 | P2 | 测试覆盖 | `vitest.config.ts:50-57` | 121 个 `.vue` 大多零覆盖，组件层基线 语句 12.98% / 分支 11.66%；业务逻辑已下沉 composables（覆盖良好），但页面渲染回归依赖人工 | 优先为资产详情、发放/回收表单、批量导入 3 类高风险页面补挂载测试；棘轮只升不降 | F F-03 | 覆盖率报告对比基线不回退 |
| M-26 | P2 | 一致性/健壮性 | `components/DashboardDistribution.vue:9`、`DashboardAssetTrend.vue:9` | 直接 `import VChart from 'vue-echarts'`，绕过 `plugins/echarts.ts` 按需注册；当前可用依赖同页 `DashboardStatusOverview` 的注册副作用，属隐式耦合 | 统一从 `plugins/echarts.ts` 导入 | F F-04 | 单独挂载该组件不再报错 |
| M-27 | P2 | 布局 | `views/system/*.vue`、`ContactsView.vue` | `el-table` 无高度约束致 fixed 列错位；`v-if="total>0"` 致零数据无空态 | 复用 `CommonList.vue` 的 flex 容器模式与空态 | W P1-4 | 零数据断言空态渲染 |
| M-28 | P2 | 健壮性 | `api/request.ts:602-608` | 401 处理含副作用且不可重试，并发请求重复触发登出跳转 | 改为抛出可捕获业务错误由上层处理 | W P2-4 | 并发 401 断言仅触发一次跳转 |
| M-29 | P3 | 性能 | `router/routes-auth.ts:14,26` | LogIn 是唯一静态 import 的路由组件，进主入口 chunk，与「路由全量懒加载」约定不符 | 改 `component: () => import('@/views/LogIn.vue')` | W P2-1 + A FE-4（重复项合并） | `rg -n "from '@/views" src/router/` 零静态命中 |
| M-30 | P3 | 路由 | `routes-standalone.ts:128-132`、`routes-main.ts:24-26` | meta 缺 `requiresAuth`/`title`；未登录访问未知路径跳登录而非 404 | 补 meta | W P2-2 | route 快照 spec |
| M-31 | P3 | 工程化 | `router/index.ts` | 使用 `createWebHistory`，需 Nginx `try_files` 配套，否则深链刷新 404 | nginx `location /` 加 `try_files ... /index.html`（与 M-37 同批改 nginx 配置） | W P2-5 | 深链刷新实测 |
| M-32 | P3 | 配置漂移 | `router/guards.ts:42` | `'/main/system': [SYSTEM_ADMIN]` 为死条目，不存在任何 `/main/system` 前缀路由 | 删除死条目或加注释说明保留原因 | W P1-3 + A FE-5（互证） | `rg -n "'/main/system" src/` 后确认无对应路由 |
| M-33 | P3 | 复用 DR-2 | `utils/Format.ts:91-96,427-432`；`NotificationBell.vue:135-141`；`readExcelFile.ts:15-16` | 时间/日期格式化三处重复实现：`Format.ts` 内部有一段与 `formatDate` 重复的 YYYY-MM-DD 拼接；通知铃自写相对时间未复用；`toLocalISODate` 与 `getLocalTodayString` 语义相同 | 收敛到 `Format.ts` 单一事实源 | A FE-7 | `rg -n "padStart" src/` 收敛后仅一处 |
| M-34 | P3 | 护栏缺口 | `scripts/check_frontend_invariants.py` | 不覆盖 `.vue` 行数，FR-5 仅靠人工；本轮人工核算最大约 441 逻辑行合规 | 把 `.vue` 逻辑行检查纳入前端护栏 | F F-05 | 人为造超长 .vue 断言护栏失败 |
| M-35 | P3 | 安全表述 | `stores/auth.ts`（移动端令牌持久化） | 令牌落 localStorage 前为 XOR 混淆而非加密，密钥随包分发，无法抵御 XSS；Web 端 httpOnly Cookie 通道不受影响 | 明确定位为「混淆，非安全边界」；移动端改系统安全存储或短生命周期令牌 | F D-07 | 文档/注释标注到位 |

### 3.3 部署与仓库（6 条）

| 统一 ID | 级别 | 类型 | 位置 | 问题 | 融合修复建议 | 来源 | 验证方式 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| M-36 | **P1** | 上线阻断 | `docker-entrypoint.sh:5,60,67` | 仅 `set -uo pipefail`（无 `-e`），`migrate` 与 `collectstatic` 未校验退出码 → 迁移失败后应用仍启动，线上以未迁移库对外服务 | 迁移/静态收集追加 `\|\| exit 1`，或整体改 `set -euo pipefail` 并对可容忍步骤显式 `\|\| true` | F D-01 | 人为让 migrate 失败，断言容器不启动 |
| M-37 | **P1** | 上线阻断 | `nginx/conf.d/default.conf.tpl:31-32`；`nginx/scripts/renew.sh:18-24` | 全新服务器首次部署时 443 证书不存在，nginx 引用 `ssl_certificate` 启动失败；`renew.sh` 只在证书已存在时续期，无首签路径；部署文档亦未给签发步骤 | 增加首次签发流程（HTTP-01 webroot 或 DNS-01 `certonly`）并写入部署文档；或 nginx 启动前生成临时自签证书占位 | F D-02 | 全新环境空证书目录实测部署链路 |
| M-38 | P2 | 镜像卫生 | `asset_management_backend/.dockerignore`；仓库跟踪 `.graphify_*.json`（5 个 ~9.66MB）与 `.trae/`（115 文件） | 生成物与 AI 工具配置进仓库，且被 `COPY . /app/` 打进生产镜像，致镜像膨胀与非业务文件外泄 | 三处同时处理：仓库移除 + `.gitignore` + `.dockerignore` | F D-03 | 构建后镜像内 `ls` 无上述文件 |
| M-39 | P2 | 仓库卫生 | 根目录 `process_image.py`(96 行)、`process_image2.py`(93 行) | 含个人桌面绝对路径的一次性去水印脚本，已被 git 跟踪，与项目无关 | 删除并加入 `.gitignore` | F D-04 | `git ls-files` 无命中 |
| M-40 | P2 | 仓库卫生 | `asset_management_backend/package.json`（依赖 `docx` 9.6.1） | 后端仓库内存在无任何 JS/TS 使用方的 npm 依赖清单，属遗留脚本残留 | 删除 `package.json`、`package-lock.json` 及对应 `node_modules` | F D-05 | 全库检索无 `docx` 引用后删除 |
| M-41 | P3 | 文档漂移 | `Project_Requirements/02-技术设计/08-部署与环境配置.md` | 文档 nginx 示例 13 行静态配置 vs 仓库实际模板 237+ 行（含 WebSocket/限流/备份）；前端构建小节未说明 `mkdir dist` | 以实际 `default.conf.tpl` 为准重写部署章节，补首次证书签发（与 M-37 联动）与备份恢复演练 | F D-06 | 文档与实际模板逐节比对 |

### 3.4 已确认通过项（三方一致，无需整改）

| 维度 | 结论 | 证据来源 |
|:---|:---|:---|
| 架构分层 | 五层清晰，`services` 返回 `Response(` 0 命中，无越界；`selectors` 未反向依赖 | W §1.1 / F §2.1 |
| 资产状态机主体 | 8 态齐备；`asset_current_status =` 写入仅 `core.py` 一处；合法路径均走 FSM + `@transaction.atomic` + OperationLog + on_commit | A §一 / F §2.2 |
| 合同状态机 | `contract_fsm.py:79` 唯一赋值点，旁路 0 | A §一 |
| API 响应契约 | `success_response` 唯一出口（`urls.py:142` 为 docstring、`asset_view.py:554` 为 PNG 二进制，均属正当例外） | A §一 |
| 跨端契约 4 项 | 响应结构 / 8 态枚举键 / `page`+`page_size` / ISO-8601 全部一致；前端 `pageSize` 零命中 | A §一 / F §四 / W 矩阵 2 |
| 事务与并发 | 44~219 处 `@transaction.atomic` + 30 处 `select_for_update`；「scoped 解析→按主键加锁→锁内复检→lock_row_or_409」范式，无新 check-then-act 竞态 | A §一 / F §2.3 |
| SC-1 密钥 | 0 处硬编码；`production.py` 缺 SECRET_KEY/ALLOWED_HOSTS/DB_PASSWORD/REDIS_URL 即 fail-fast | 三方一致 |
| SC-3 SQL 注入 | `apps`/`core` 内 `.raw()/extra()/cursor.execute` 0 命中；`scripts/` 两处已白名单校验（C-4） | A + F + 本轮仲裁 |
| SC-4 动态标识符 | `clear_database.py` 表名为白名单校验，合规 | 本轮复核 |
| SC-5 / SC-6 上传 | **无上传面**（`apps/` 内 FileField/MultiPartParser/UploadedFile 0 命中），N/A；未来新增须从零补三校验 | A + 本轮复核（C-9） |
| DR-5 / DR-6 | 222 个业务 `.py` 0 超长（最大 488/500）；`.vue` 最大约 441 逻辑行；调用链 ≤3 层 | A §一 / F §一 |
| 重复代码护栏 | G-1~G-3、G-5 全 PASS | W §1.3 / F §一 |
| 迁移一致性 | `makemigrations --check --dry-run` → No changes detected | W §1.3 / F §一 |
| 可观测性 | trace_id 透传 + JSON 结构化日志 + 脱敏 + `/health` + `/ready` + Prometheus（含 P50/P90/P99） | W 矩阵 5 / F §3.4 |
| AR-3 / AR-4 | 外部调用显式 timeout + 重试，配置化管理 | W 矩阵 5 |

---

## §四 分批修复建议

> 排序原则：**先解阻断，再修数据正确性，然后权限，最后性能与卫生**。同域合并以减少回归面，单点快清项穿插在低风险批次。

### 批次 1 — 解除流水线必红（P0，3 项，必做且最优先）

| 项 | 内容 | 预估 |
|:---|:---|:---|
| M-18 | `ci.yml:422,424` 改 `npm run test:coverage` | 极小（2 行） |
| M-02 | `ruff check . --fix` + `ruff format .` | 极小（机械修复，7 文件） |
| M-01 | mypy --strict 13 处类型标注与 ignore 错误码修正 | 小 |

**出口条件**：CI `frontend-test` / `backend-lint` / `backend-type-check` 三个 job 全绿。
**说明**：这三项是唯一被实证的「流水线必红」，其余所有项都建立在流水线可信的前提上，故排在最前。

### 批次 2 — 上线阻断清零（P1，4 项）

| 项 | 内容 | 说明 |
|:---|:---|:---|
| M-36 | `docker-entrypoint.sh` 迁移/静态收集失败快速退出 | 数据事故风险，最高优先 |
| M-37 | 首次 TLS 证书签发路径 + 部署文档（与 M-41 联动） | 全新服务器 nginx 无法启动 |
| M-03 | 员工手机号按角色脱敏 | 与既定隐私约束直接冲突 |
| M-04 | 未登记资产 Selector 补 `select_related` | 数据量大时导出/列表超时 |

**出口条件**：可进入灰度发布。M-04 可随本批的 `assertNumQueries`（M-10）一起落地，互为护栏。

### 批次 3 — 权限与前端资源域（P2-A，5 项）

| 项 | 内容 |
|:---|:---|
| M-19 | 路由守卫改 deny-by-default |
| M-20 | HardDiskSN 子树补 `requiredMinRole`（需先与业务确认门槛） |
| M-21 | `useNotification` 单例化 + handler 清理 |
| M-22 | `connect()` 入口清理 pending 重连定时器 |
| M-07 | 写操作显式 `permission_classes` |

**说明**：M-21/M-22 同属通知连接域，合并改造避免两次改同一文件。M-20 需业务确认「硬盘序列号是否仅系统管理员可写」，确认前不要盲改。

### 批次 4 — 契约、性能与交互质量（P2-B，7 项）

| 项 | 内容 |
|:---|:---|
| M-23 | 页容量选项收敛 `[20,50,100]`（消除与后端上限的矛盾） |
| M-24 | ExcelJS 改按需加载（首屏约降 1MB chunk） |
| M-27 | 表格高度约束 + 零数据空态 |
| M-28 | 401 处理改为可捕获业务错误 |
| M-26 | `vue-echarts` 统一从插件导入 |
| M-06 | View 层手写 ORM 下沉 Selector |
| M-25 | 高风险页面补挂载测试（棘轮只升不降） |

### 批次 5 — 仓库/镜像卫生与死码清理（P2-C，5 项 + 删除清单）

| 项 | 内容 |
|:---|:---|
| M-38 | `.graphify_*.json` + `.trae/` 三处处理（移除 + gitignore + dockerignore） |
| M-39 | 删除 `process_image.py` / `process_image2.py` |
| M-40 | 删除后端 `package.json` / `package-lock.json` |
| M-08 | 删除 `apps/assetmanagement/signals.py` |
| M-09 | 删 `pagination.py:120-144` 死码 + 修正 `:6` docstring |

**并入本批的 ponytail 删除清单**（来自 W Batch D，已剔除被驳回项）：

```
config/urls.py:154                      yagni:    health 端点手写 JSON Response → 用 JsonResponse/DRF Response
core/audit_service.py:57                shrink:   手写字段提取 → Meta API / 序列化器字段集
asset_lifecycle_mixin.py:338            shrink:   _resolve_enum_label → Django get_FOO_display（-8 行）
inventory/CountEntryTable.vue:70-87     delete:   冗余合并逻辑
inventory/CountCheckInPanel.vue:107-115 delete:   同上
inventoryShared.ts:16                   delete:   与 types.ts 重复常量
CountCheckInView.vue:88-139             shrink:   重复 fallback 列定义（-12 行）
apps/.../selectors/outasset_selector.py delete:   再导出壳（= M-13，更新 4 处 import）
```

> **已驳回（不要执行）**：`core/throttles.py:41 delete`（W Batch D 原提案）。理由见 C-7——该文件承载登录锁定业务安全特性，删除会造成安全回退。

**净收益**：约 **-96 行**代码（W 件清单剔除 throttles 的 19 行后）+ F 件清单约 **-170 行** + **-10MB 生成物** + **-115 个非业务文件**。

### 批次 6 — P3 优化（可排期，不阻断）

| 组 | 项 |
|:---|:---|
| 后端 | M-11（Department.save 批量化 + 脏 path 留痕）、M-12（`--strict` 退出码）、M-14（软删除显式过滤）、M-15（sentry pin）、M-16（force_recycle 前态留痕核实）、M-17（标识符纵深加固） |
| 前端 | M-29（LogIn 懒加载）、M-30（补 meta）、M-31（nginx try_files）、M-32（删死白名单）、M-33（时间格式化单源化）、M-34（.vue 行数入护栏）、M-35（混淆定位标注） |
| 部署 | M-41（部署文档重写，与 M-37 联动） |

### 批次依赖关系

```
批次1（P0 流水线）
   └─> 批次2（P1 上线阻断）
         ├─> 批次3（权限域）
         └─> 批次4（质量域）
                └─> 批次5（卫生清理）
                       └─> 批次6（P3 优化）
M-37 ──联动──> M-41
M-04 ──配套──> M-10（assertNumQueries 护栏）
M-24 ──同源──> M-31（均涉 nginx/构建配置）
```

---

## §五 上线准入结论

### 结论：有条件通过（Conditional Go）—— 当前不建议直接上线生产

**必须在上线前清零（6 项）**：

| # | 项 | 不清零的后果 |
|:---|:---|:---|
| 1 | M-18 CI vitest 参数失效 | `frontend-test` 必红，无法验证前端质量 |
| 2 | M-02 ruff 门禁 | `backend-lint` 必红 |
| 3 | M-01 mypy strict 13 处 | `backend-type-check` 必红 |
| 4 | M-36 入口脚本迁移失败不退出 | 线上以未迁移库对外服务，数据事故 |
| 5 | M-37 首次 TLS 证书签发 | 全新服务器 nginx 启动失败 |
| 6 | M-03 手机号明文 | 与既定隐私约束直接冲突 |

> 第 4~6 项来自 F 件，是 W、A 两件的共同盲区；第 1~3 项来自 W 件，是 F 件「门禁配置齐全」结论下的实际欠账。融合后阻断面才完整。

**建议同批处理**：M-04（N+1）、M-19/M-20（RBAC 归口）、M-23/M-24（契约与首屏体积）。

**灰度放行判断**：满足上述 6 项后，项目在架构分层、状态机、事务并发、安全基线、CI 门禁、可观测性、部署编排七个维度均达到生产级要求，可进入灰度。

### 收口记录回填（2026-10-30，批次 1~3 落地后补记）

三批整改已全部落地并推送（backend 至 `74bda81`、frontend 至 `1d74bb0`、父仓至批次 3 gitlink bump），逐项收口如下。各commit 均含先红后绿取证与全量护栏验收，细目见各仓 commit message 与 `docs/BugFixed/Bug修复活账本.md` BF-165。

**批次 1 — 流水线必红清零（P0）**：

| 项 | 状态 | 收口证据 |
|:---|:---|:---|
| M-18 CI vitest 参数失效 | `[已收口]` | ci.yml:422/424 改 `npm run test:coverage`（配置文件分层阈值驱动，vitest 4 兼容）；本地 coverage exit 0（store 层 96.8/92.4/91.2/97.2 ≥90） |
| M-02 ruff 门禁 | `[已收口]` | 2×I001 --fix + 5 文件 format；`ruff check .` / `format --check .` 双 exit 0 |
| M-01 mypy strict 13 处 | `[已收口]` | 13 处注释级收口（172/184→[misc]、176→[arg-type]、6 处删失效 ignore、:374 新增 [attr-defined] + AR-2 标注）；`mypy . --strict` 230 文件 0 错误 |

**批次 2 — 上线阻断清零（P1）**：

| 项 | 状态 | 收口证据 |
|:---|:---|:---|
| M-36 入口脚本失败快速退出 | `[已收口]` | `set -euo pipefail` + migrate/collectstatic 显式 `|| exit 1` + 超管变量 `${X:-}` 兜底；新增 BR-D1 部署入口护栏挂 CI（变异体 3 处违规先红） |
| M-37 首次 TLS 签发链路 | `[已收口]`（staging 实测项除外，见下） | CERT_PATH 对齐 certbot 产出点 + 三态渲染状态机（HTTP-only 引导态=完整配置去 TLS 块，签发窗口业务不断）+ cert-watch 变更监视者 + renew.sh 首签/退避；setup-https.sh 下线；文档见 08-部署与环境配置.md §5（V1.1） |
| M-03 手机号明文 | `[已收口·WAI]` | 业务确认「通讯录对任何已登录账号明文可见」；活账本 BF-165 留痕 + 序列化器口径锚点注释 + 三读路径一致性绊线测试 |
| M-04 未登记 Selector N+1 | `[已收口]` | `get_queryset_for_user` 补 `select_related("discovery_person")`（分层裁决：approver/related_asset/result_asset 不加）；`assertNumQueries` 列表/导出/详情三链先红（3→8）后绿 |

**批次 3 — 权限与前端资源域（P2-A）**：

| 项 | 状态 | 收口证据 |
|:---|:---|:---|
| M-19 路由守卫 allow-by-default | `[已收口]` | 仅写 deny 口径（业务确认）：`checkRoleAccess` 新增 write 兜底拒绝；25 条写叶子路由 `meta.write:true` 脚本化推导标注；完整性不变量测试（漏标门槛→CI 红）+ 死循环防御锚点；guards.spec(76)/rbac-r3(25) 既有断言零改动 |
| M-20 HardDiskSN 子树门槛 | `[已收口]` | 口径订正为 `harddisksnform` 补 `asset_admin`（对齐后端 IsAssetAdminOrAbove），弃用原「子树 system_admin」跨端不一致方案；只读父/详情页不加固；订正「父级 meta 不自动继承」错误注释 ×3 |
| M-21 useNotification 泄漏 | `[已收口]` | 连接层单例（detached scope）+ refcount（0→1 建连/归零断连）+ `offMessage` 唯一注销入口；数据态维持实例级；三 spec 47 passed |
| M-22 重连定时器竞态 | `[已收口]` | `connect()` 入口清 pending timer + scheduleReconnect 先清后置（定性：连接 churn + 计数污染）；2 用例先红后绿 |
| M-07 写操作显式 permission_classes | `[已收口·去伪]` | 20 域只读核查零真实缺口（`docs/Review/M07-write-permission-audit-20261030.md`）；三处原目标为静态扫描误报（死配置），已注释去伪 |

**批次 2 M-37 残留（灰度环境人工项，不阻断代码收口）**：真实域名 Let's Encrypt 生产首签 + `openssl s_client` 指纹一致性验证，须按 08-部署与环境配置.md §5.2~§5.3 在灰度环境执行一次（staging 全链验证口径已写入 §5.4）。

**批次 3 遗留**：M-07 核查产出「类级 `permission_classes` 与 `get_permissions` 双源易误导」改进项（非缺口），建议后续批次统一审计注释；真实缺口为零。

**批次 4 — 契约、性能与交互质量（P2-B，2026-10-30 落地）**：

| 项 | 状态 | 收口证据 |
|:---|:---|:---|
| M-26 echarts 引入收敛 | `[已收口]` | 两组件（DashboardAssetTrend/DashboardDistribution）改从 `@/plugins/echarts` 导入 VChart；option 构造器前置审计全命中注册清单（useDashboardCharts 饼/趋势含 area 渐变 series 级样式、useDashboardPage tooltip/legend/pie+graphic）；`rg "from 'vue-echarts'"` 全仓仅剩 plugins/echarts.ts:26 一处；独立挂载冒烟 2 例绿（jsdom 无 canvas 以最小 2D 桩注入，断言 echarts init 成功） |
| M-24 ExcelJS 按需加载 | `[已收口]` | 3 处静态导入（excelExporter/readExcelFile/templateExport）改函数体内 `await import('exceljs')`；4 份 spec（含 useBatchImport 漏点名补录）mock 形态天然兼容零改动 33 passed；构建产物 exceljs 独立 chunk（1,059.55 kB / gzip 245.50 kB），index 主包 0 处引用 |
| M-23 分页选项收敛 | `[已收口]` | `PAGE_SIZE_OPTIONS=[20,50,100]` + `MAX_PAGE_SIZE=100` 镜像常量落 utils/pagination.ts；四处散点改引用 + CHILD alias；pageSize getter 就近向下吸附（500→100、40→20）；3 份硬断言随批 + 上限一致性断言 + 归一化 2 例，70 passed；消费面 5 页点检清单入 A-50 账本（关联 A-18 豁免关闭 / A-40 上限口径） |
| M-06 关键词查询下沉 Selector | `[已收口]` | `AssetSelector.apply_keyword_filter`（TypeVar 透传保 select_related 链类型）+ `OutAssetSelector.apply_keyword_filter`（5 分支）唯一实现，两 View 一行调用、孤儿 Q import 清理、icontains 归零；新增单测 9 例（命中/不命中/空串短路/分支隔离）；mypy strict 230 文件 0 错误；账本 B-28 登记与关闭 |
| M-28 401 登出幂等 | `[已收口]` | 两登出点三连收敛进 `performSessionLogout()` 幂等旗 + `redirectToLogin` 可注入模块；logError 留块外（reason 各异/等待者数排障信号，决策留档）；重试链零改动；3 新用例 + responseHandler spec 幂等旗 reset 钩子（全量实测暴露的跨用例泄漏回归修复）；变异体先红后绿取证 |
| M-27 fixed 列错位 | `[已收口]` | 交付面 = `fixed="right"` 全仓仅两页（RoleManage/AuthUserManage；ContactsView 经核实仅门控分页、表格常驻 EP 默认空文案在场，移出交付面）；表格区包 `.table-container` 弹性自滚容器（复用 CommonList flex 模式）+ 分页 flex-shrink:0 常驻；两页挂载测试各 3 例（空态断言）6 passed |
| M-25 .vue 挂载测试补强 | `[已收口]` | 只补缺口（既有 9 视图 spec + AssetDetails/AssetBatchImport 零重写）；.vue 层四指标实测 21.14/19.03/18.66/21.36（121 文件，两页零覆盖→~48%），远超基线 12.98/11.66/10.95/13.11；棘轮阈值上调 21.1/19.0/18.6/21.3 并重基注释（2026-10-12/10-30 两版留痕，只升不降） |

**批次 4 验收**：前端 type-check/lint/format:check 全 0 + 全量 185 files / 2411 tests passed + `test:coverage`（新棘轮）exit 0 + build exit 0；后端 ruff 双绿 + mypy strict 0 错误 + 相关 pytest 面全绿 + 双护栏 PASS。账本新增 A-50（M-23）、B-28（M-06）均已关闭。

**批次 4 哈希勘误（2026-10-30 补记）**：父仓批次 4 gitlink bump（`c238a24`）的 commit message 记载「backend 259fac6」有误——`259fac6` 是 M-06 落地时 11:42:55 的重写前旧 SHA，非 backend HEAD 祖先，与终版相差 `out_asset_selector.py` 1+/3-；`c238a24` 实际记录的 gitlink 与 backend 历史真值均为 **`5d1a9b4`**（11:43:40 的 M-06 终版，`0c40101` 之父）。指针本身正确，仅 message 笔误。frontend `f8151da` 的 message/记录/HEAD 三者一致；backend 指针已随后续 `d601881` bump 至 `0c40101`。核验口径：`git ls-tree c238a24` + `merge-base --is-ancestor` + `git diff 259fac6 5d1a9b4 --stat`。

**批次 5 — 仓库/镜像卫生与死码清理（P2-C，2026-10-30 落地）**：

| 项 | 状态 | 收口证据 |
|:---|:---|:---|
| M-38 graphify/trae 生成物退版 | `[已收口]` | 6 个 `.graphify_*`（5 json + `.graphify_uncached.txt`）+ `.trae/` 115 文件 `git rm --cached` 退版（本地文件保留）；后端 `.gitignore` 增 `.graphify_*`/`.trae/`，`.dockerignore` 增 `.graphify_*`/`.trae`；`git ls-files ".graphify_*" ".trae" ".trae/*"` 归零（`run_graphify*.py` 两个脚本属保留项不计）；docker CLI 本机不可用 → 以 `.dockerignore` 三路径 + `COPY . /app/` 生效位置静态核对降级验证，镜像内 `ls` 实证留作 CI/有 docker 环境补证 |
| M-39 process_image 死脚本 | `[已收口]` | 根仓 `process_image.py`（96 行）、`process_image2.py`（93 行）删除 + 根 `.gitignore` 增 `process_image*.py` 规则；`git ls-files "*process_image*"` 归零 |
| M-40 后端 npm 依赖清单 | `[已收口]` | `package.json`/`package-lock.json` 删除 + 本地 `node_modules` 清理（85.9MB）；后端 `.gitignore` Node 段改写（去 docx 字面措辞，防门禁自伤）+ `.dockerignore` 增 `package.json`；`git grep docx` 全仓归零 |
| M-08 signals 死模块 | `[已收口]` | `apps/assetmanagement/signals.py`（0 逻辑行纯历史注释）删除 + `unregisteredasset/apps.py` 清 2 行延迟导入注释（`ready()` 骨架保留）；窄口径 `git grep "import signals"` 与 `"assetmanagement\.signals"` 双 0；CHANGELOG 加 Removed 留痕 |
| M-09 分页死码与 docstring 矛盾 | `[已收口]` | `core/pagination.py:120-144` 注释旧实现删除（护栏口径逻辑行 86），`:6` docstring 改「无参数强制第一页（单页上限 100）」与实现一致；冒烟 `test_asset_view_api.py` 46 passed（无参强制分页 + `page_size=1` 有参两路径在场） |
| M-13 outasset_selector 再导出壳（并入 ponytail 清单） | `[已收口]` | 壳文件删除，5 处 import 收敛为逐模块导入（`selectors/__init__.py` 直连 8 名 + 3 个测试文件）；`git ls-files "selectors/outasset_selector.py"` 归零；三 selector 测试 57 passed；包级 `__all__` 14 名不变 |

**批次 5 验收**：采集层五门禁（graphify/trae 生成物、process_image、docx、signals 窄口径、outasset_selector 残留）全 0 + `manage.py check` 0 issue；后端 ruff 双绿（含 C90）+ mypy --strict 0 错误（228 文件）+ 全量 2246 passed 覆盖 90.34%（Service 层 98%）+ mutmut 双门禁 83.4532%（红线 80 / 基线 83.2568，+0.1965pt，tested=2085，WSL 同口径）+ schema 基线重导零漂移 + 双护栏 PASS。**附带**：发现基线存量漂移（M-RC-02/M-RC-05 改后未重导，6+/24- 非破坏性，CI oasdiff 实证）随批重导归零。

**批次 5 附带发现（存量红，不阻断本批）**：master CI 自 2026-10-29 起连续 5 次 push 红，唯一失败 job = 前端变异测试 **79.70 < 80**（上绿为 10-27 的 80.02，仅 +0.02 边界余量；两次红跑同为 79.70，确定性而非抖动；批次 1~4 push 均带此红）。本批零前端变更、后端 job 全绿，与本批无因果。**[待决策]** 另立专项：查 80.02→79.70 转折成因（前端批次改动 vs 环境漂移）并补杀回 ≥80。

### 与三件原结论的差异

| 件 | 原结论 | 融合后 |
|:---|:---|:---|
| W 件 | 4 项 P0 阻断 | **3 项**（`force_recycle_from_any` 降级为 P2 待核实） |
| A 件 | 「新发现均为 P2/P3，不构成上线阻断」 | **不成立**——A 件未覆盖部署链路，融合后新增 M-36/M-37/M-03 三条 P1 阻断 |
| F 件 | 3 项 P1 阻断 | 补充 W 件 3 条 P0 后共 **6 项** |

---

## §六 融合审计票

```markdown
[审计票 - 必填项]
- 读取规范：已读 根 AGENTS.md(v3.7.1) / 后端 AGENTS / 前端 AGENTS / Rules_Fiels 业务与测试规范 / 活账本
- CT-1[√] CT-3[√] CT-5[√] CT-7[√]
    CT-3 说明：88 用例通过（test_state_machine + test_asset_selector_isolation），
    8 态 22 条合法边全覆盖；原 W 件判定的 P0 旁路经复核为已声明例外 M-60，
    降级为 M-16(P3) 并保留一项 [待核实]
    CT-7 说明：M-02 结论由本轮本地 ruff 实跑取得，工具版本与 requirements/dev.txt 一致；
    M-01(mypy) 未本地复跑，结论沿用 W 件，标 [未复核]
- DR-1[√] DR-5[√] — 后端最大 488 逻辑行 / 前端最大约 441 逻辑行（LT-1 逻辑行口径）
- SC-1[√] SC-3[√] — 密钥 0 硬编码；apps/core 无 raw SQL，scripts/ 两处经白名单校验（C-4 仲裁）
- 跨端契约：未破坏（响应结构 / 8 态枚举 / page+page_size / ISO-8601 四项一致）
- 红线触发：[HALT] 未触发（本次为只读融合，无代码变更）
- 建议提交：否（仅产出本融合报告；修复按 §四 批次执行）

[审计票 - 自检项]
- 测试：CT-2[√]（后端 90.09%，CI run 40466576631 权威口径；前端组件层 12.98% 为偏低项 M-25）
        CT-4[√] CT-6[√]（makemigrations --check 通过）
- DRY：DR-2[√]（M-33 为残留项）DR-3[√]（M-06 为残留项）DR-4[√] DR-6[√]
- 安全：SC-2[√] SC-4[√] SC-5[N/A 无上传面] SC-6[N/A] SC-7[~] SC-8[√]
        SC-7 说明：npm audit 0 vuln（F 件实证）；pip-audit 本地网络失败，以 CI security-scan 为权威
- 可观测性：OC-1[√] OC-2[√] OC-3[√] OC-4[√] OC-5[√] OC-6[√] OC-7[~]
- AI鲁棒性：AR-1~AR-5[√]（未生成业务代码）
- AI行为：Fact-1[√]（§二 每条仲裁附复核取证；§七 逐项留痕未核实内容）
- 写作风格：Style-1~Style-3[√]
- 覆盖率：后端 90.09%（CI 权威）/ 前端组件层 语句 12.98% · 分支 11.66%（待补强）
```

---

## §七 未核实 / 存疑项留痕（Fact-1）

| 项 | 状态 | 说明 |
|:---|:---|:---|
| M-01 mypy 13 处报错 | `[已复核]`（批次1 收口时补证） | 批次1 落地时本地实跑 `mypy . --strict`（2.1.0 与 dev.txt 钉版一致），13 处分布与错误码逐条对上；收口后 230 文件 0 错误，见 §五 收口记录回填 |
| M-04 未登记 Selector N+1 | `[已复核]`（批次2 收口时补证） | 批次2 逐行读 `unregisteredasset/selectors.py` 确认全文 0 处 select_related；`assertNumQueries` 三链先红（3→8）后绿，见 §五 收口记录回填 |
| M-16 force_recycle 前态留痕 | `[待核实]` | 已确认该方法为 M-60 已声明例外、非旁路；但「调用方是否已补 OperationLog」未追踪，需核实后再决定是否改动 |
| CI run `40466576631`（90.09%） | `[未复核]` | 未直连核验该 run，沿用 A 件留痕 |
| W 件 SC-5/SC-6「上传校验已实现」 | `[存疑]` | 本轮检索 `apps/` 下 `FileField/MultiPartParser/UploadedFile/MEDIA_ROOT` 0 命中，无上传落点；按 A 件判定为无面可评（C-9） |
| W 件「错误码无全局错误字典」建议（C-3） | `[未纳入]` | 三件中仅 W 件提及且未定级，无第二方互证，未进台账，留痕备查 |
| A 件低置信度项 L-1 / L-2 / L-3 | `[不采纳]` | A 件已自行判定不采纳（双审计链取舍 / 抽查零实例 / 疑似有意设计），本融合维持原判；其中 L-2「新增 @action 必须显式权限」守卫建议随批次 3 顺带登记 |
| T7 / T16 变异测试分数 | `[未执行]` | 三件均未提供实测值 |
| `pip-audit` 本地扫描 | `[未执行]` | 网络连接重置，以 CI `security-scan.yml` 为权威 |
