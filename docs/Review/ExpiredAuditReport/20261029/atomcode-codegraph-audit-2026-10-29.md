# 资产管理项目 CodeGraph 全面审计报告（atomcode，2026-10-29）

> 审计模式：project-all-code-review v1.2.0（纯审计不修复，全程只读）。
> 索引：CodeGraph 1,030 files / 18,364 nodes / 41,791 edges（后端 484 + 前端 504），status 无陈旧告警。
> 审计范围：项目整体框架/逻辑/架构，前端页面完整性与布局/逻辑/打开性能，后端数据库/函数调用/逻辑，部署上线规范符合性。
> 前提事实：merge-audit-2026-10-27 的 R-1~R-7、M-RC-17 留痕批、M-CACHE-1 已于 2026-10-28/29 全部收口（§3.1.1~§3.1.9），本报告不重复登记已收口项，只报告新发现。
> 探索机制：两路 explore 子代理分域扫描（后端 5 域 / 前端 5 域）+ 主代理 §5 专项维度（CT-3 / 契约 4 项 / SC 分流 / CT-2 / DR-5）复核。

---

## §一 项目上下文与分域结论

| 分域 | 锚点 | 结论 |
|:---|:---|:---|
| 资产状态机 | `state_machine/`（AssetState 8 态 / VALID_TRANSITIONS / AssetFSM / 4 mixin） | ✅ 生产代码旁路 **0 处**：全后端 `asset_current_status =` 逐点判读——`core.py:112` 唯一正规写入口；out_recycle/scrapping mixin 均有前置守卫；unregistered.py 三处为已声明例外（M-60）；services 层 0 处直接赋值（asset_lifecycle_mixin 全部 select_for_update + FSM）；其余命中均为测试夹具/只读巡检 |
| 合同状态机 | `contract_fsm.py` ContractFSM | ✅ 旁路 **0 处**：`contract_fsm.py:79` 唯一赋值点；`contract_service.py:168-170` 创建期单闸；batch 序列化器 ChoiceField 8 态白名单 |
| API 响应契约 | `utils/response_utils.py` success_response | ✅ 真实旁路 **0 处**：`return Response(` 仅 urls.py:142（docstring 教程文本，已排除）；asset_view.py:554 PNG 二进制下载不适用 JSON 信封 |
| 鉴权面 | permission_classes / admin_actions | ✅ 各 ViewSet 均有 IsAuthenticated 或更严；AllowAny 端点（注册/登录/登出/refresh/公开扫码）均显式配限流，属有意设计。两处机制性观察见台账 F-2/L-2 |
| 批量导入 | batch_serializers / 无文件上传 | ✅ 后端**不存在文件上传/Excel 导入端点**（批量走 JSON + ChoiceField 校验），SC-5/SC-6 上传安全 N/A；未来新增文件导入须从零补扩展名/MIME/大小三校验 |
| 数据库与调用 | select_for_update 范式 | ✅ 出库/回收/维修/damaged 审批/删除改态均为「scoped 解析→按主键加锁→锁内 TOCTOU 复检→lock_row_or_409 收敛」，**未发现新 check-then-act 竞态**；循环内单查仅台账 F-1 一例；except...pass 命中均在排除范围（迁移/asyncio/测试） |
| 前端页面完整性 | router/ + views/ | ✅ 17 个视图全部有路由引用（无孤儿视图）；除 LogIn 外全部懒加载；guards requiresAuth 全量覆盖；8 条 `/assets/:code/*` 操作页统一走 AssetOperationLayout |
| 前端布局一致性 | MainView 壳 | ✅ 无绕过布局壳页面；ContactsView 独立顶层渲染为唯一观察项（台账 L-3） |
| 前端打开性能 | vite 分包 / keep-alive | ✅ manualChunks 按域拆分（echarts/exceljs/element-plus/vendor/zrender）正确；keepAlive include 静态派生 + spec 锚定；唯一性能项为台账 P-1（重列表 500 档无虚拟滚动） |
| 状态枚举契约 | types/asset.ts vs constants.py | ✅ 8 键逐键一致（in_store/in_use/recycled_pending/broken/repairing/lost/damaged/scrapped） |
| 分页参数契约 | page/page_size | ✅ 前端 api/utils 层 `pageSize` 零命中（无 camelCase 混用） |
| 健康端点 | config/urls.py | ✅ /health（database+redis checks）存在 |
| 安全红线 | SC-1 / SC-3 | ✅ 密钥硬编码 0 命中（排除测试/空串）；`.raw(/extra(/cursor.execute` 0 命中（全 ORM 参数化） |
| 依赖安全 | npm audit --omit=dev | ✅ 0 vulnerabilities；后端 pip-audit 以 CI `security-scan.yml` 为权威（twisted 等 26.10.0 遗留已在 BF-159 登记不重报） |
| CT-2 覆盖率 | pytest --cov | 后端全量 90.09%（CI run 40466576631 权威口径，BF-161 对账闭环）；本轮本地全量复跑超 300s 转后台，结论以 CI 为准（CT-7） |
| DR-5 行数 | check_file_length_guard | ✅ 222 业务 .py 0 超长（最大 asset_view.py 488/500） |

**部署上线规范符合性总评**：核心阻断面（越权写、状态机旁路、响应契约、密钥、依赖漏洞、竞态）全部通过；新发现问题均为 P2/P3 优化项，不构成上线阻断。建议按 §二 台账排期修复后放量。

---

## §二 问题台账（新发现，9 条）

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 |
|:---|:---|:---|:---|:---|:---|:---|:---|
| FE-1 | P2 | RBAC 漏挂 | `vue-assetmanagement/src/router/routes-main-system.ts:52-70` | HardDiskSN 子树 | 硬盘序列号管理（harddisksndetails/form/basicdetails）既不在 roleWhitelist、也无 meta.requiredMinRole；同段 storagedetails/assettypedetails/userdetails 均为 system_admin 门槛，硬盘序列号属同类系统配置数据却任意登录角色可读写 | 与 StorageDetails 对齐补 `requiredMinRole: 'system_admin'`（业务确认开放则加注释锚定） | `codegraph impact HardDiskSNDetails` |
| FE-2 | P2 | 资源泄漏/重复连接 | `src/views/MainView.vue:19-21,46-54` + `AsideMenu.vue:111` | NotificationBell / useNotification | AsideMenu 在 MainView 渲染两处（桌面 aside + 移动端 el-drawer），useNotification 每实例独立状态各自 onMounted(connect())——抽屉展开后建立第二条 WebSocket，双 onmessage 使未读计数重复 +1；useNotificationConnection.ts:199-201 messageHandlers 在 disconnect() 中从不移除，卸载后 handler 驻留 | useNotification 改模块级单例连接，或 disconnect() 增加 offMessage 清理 | `codegraph impact useNotificationConnection` |
| FE-3 | P2 | 定时器竞态 | `src/composables/useNotificationConnection.ts:153-166,75-94` | scheduleReconnect / connect | scheduleReconnect 直接覆盖 reconnectTimer 且 connect() 入口不清 pending timer：断线挂起重连定时器 → token watch 等路径再触发 connect → 旧 timer 到期新建第二条并发 socket，双 onmessage 分发 | connect() 入口统一 `clearTimeout(reconnectTimer); reconnectTimer = null` | `codegraph node connect -f useNotificationConnection.ts` |
| BE-1 | P3 | 性能/N+1 + 吞没 | `apps/usermanagement/models.py:100-106` | Department.save（缓存失效段） | 按祖先路径逐级 `Department.objects.get(path=…)` 循环单查（O(depth) 查询/save）；且 `except Department.DoesNotExist: pass` 静默吞掉脏 path 数据，缓存可能失效不彻底 | 改单条 `filter(path__in=paths)` 批量取祖先；DoesNotExist 时 logger.warning 留痕 | `codegraph node Department.save` |
| BE-2 | P3 | 运维语义 | `apps/assetmanagement/management/commands/check_data_consistency.py:24-45` | handle | 一致性巡检命令仅打印 issues，无退出码语义——接入 CI/定时任务时无法据此告警失败 | 增加 `--strict` 参数（issues 非空退出码非 0）或接告警 | `codegraph node handle -f check_data_consistency.py` |
| FE-4 | P3 | 性能/一致性 | `src/router/routes-auth.ts:14,26` | routesAuth | LogIn 是唯一静态 import 的路由组件，与「路由全量懒加载」约定不一致（登录页进主入口 chunk） | 改 `component: () => import('@/views/LogIn.vue')` | `rg -n "from '@/views" src/router/` |
| FE-5 | P3 | 配置漂移 | `src/router/guards.ts:42` | roleWhitelist | `'/main/system': [SYSTEM_ADMIN]` 为死条目——不存在任何 `/main/system` 前缀路由（实际路径走 meta.requiredMinRole），留置误导维护 | 删除死条目或加注释说明保留原因 | `rg -n "'/main/system" src/` |
| FE-6 | P3 | 打开性能 | `src/components/commoncomponents/CommonList.vue:95-101` | CommonList | 原生 el-table 无虚拟滚动，但页码档位允许 500 行（`[20,50,100,200,500]`）——重列表页选 500 档渲染 500 行×多列+固定列易卡顿 | el-table 换 el-table-v2 或限制最大 page_size | `codegraph node CommonList` |
| FE-7 | P3 | 重复实现（DR-2 观察项） | `src/utils/Format.ts:91-96,427-432` vs `NotificationBell.vue:135-141` vs `readExcelFile.ts:15-16` | 时间/日期格式化 | 通知铃自写相对时间/短时间格式未复用 Format.ts；Format.ts:427-432 内部还有一段与 formatDate 重复的 YYYY-MM-DD 拼接；readExcelFile.toLocalISODate 与 Format.getLocalTodayString 语义相同 | 收敛到 Format.ts 单一事实源（DR-2 批次一次清干净） | `rg -n "padStart" src/ --glob "*.{ts,vue}"` |

**低置信度备查（<80%，不列正式问题）**：

| ID | 位置 | 描述 | 置信度 |
|:---|:---|:---|:---|
| L-1 | `apps/assetmanagement/audit.py:99-104` | AuditLogger._safe_log 吞异常返回 False（有 logger.error 留痕）——create 等路径审计静默失败仅落文件日志、无 DB 可观测信号；已声明「双审计链分层取舍」（M-AUD-3），可能属有意 | ~70% |
| L-2 | `views/asset_view.py` 等 admin_actions | 自研 RBAC 白名单机制：新增 @action 若忘登记且不在显式权限列表，普通用户可写；抽查未见遗漏实例，建议补「新增 @action 必须显式权限」守卫测试 | ~65% |
| L-3 | `routes-standalone.ts:119-126` ContactsView | 通讯录独立顶层渲染无 MainView 壳（无侧边栏/通知/降级 Banner），与 /main/departmentmanagement 并存两套入口；若为移动端/扫码场景属有意 | ~60% |
| FE-C1 复核 | MainView 移动端 drawer | FE-2 双连接仅在 <960px 且抽屉展开后触发（el-drawer 惰性渲染），逻辑链成立但未运行验证 | ~75% |

---

## §三 分域修复建议（按优先级排序，可交接修复 skill）

**排序原则**：同域合并 → 级别优先 → 影响面小者先行。

| 批次 | 条目 | 影响面 | 建议验证方式 |
|:---|:---|:---|:---|
| 批 A（P2 前端 RBAC + 通知域） | FE-1 / FE-2 / FE-3 | FE-1 影响 HardDiskSN 全部 3 路由（codegraph impact 3 symbols）；FE-2/FE-3 影响 useNotificationConnection（7 affected symbols，含 useNotification 全链） | FE-1：guards-rbac 回归（对齐 §3.1.3 范式）；FE-2/3：useNotificationConnection.spec 扩展（双实例单连接断言 + reconnectTimer 清理断言）+ 移动端 drawer 手工冒烟 |
| 批 B（P3 快清） | BE-1 / BE-2 / FE-4 / FE-5 | 均单文件单点 | BE-1：usermanagement 既有测试 + 脏 path warning 断言；BE-2：--strict 退出码用例；FE-4/5：route 快照 spec |
| 批 C（P3 性能与 DR-2） | FE-6 / FE-7 | FE-6 影响 CommonList 全消费面（16 列表页）；FE-7 三文件 | FE-6：el-table-v2 试点或 page_size 上限调整 + CommonList.spec；FE-7：Format.ts 单源化 + NotificationBell/readExcelFile 回归 |

**通过项证据命令**（复核入口）：状态机旁路 `rg -n "asset_current_status\s*=" asset_management_backend/apps`；契约 8 键 `codegraph node AssetState`；SC-1 `rg -n "(secret|password|api_key|token)\s*=\s*['\"]" --iglob '!*.md'`；SC-3 `rg -n "\.raw\(|extra\(|cursor\.execute" apps core`；依赖 `npm audit --omit=dev`（0 vulns）；DR-5 `python scripts/check_file_length_guard.py --print`。

---

## §四 台账终态与评审结论

**台账终态**（本 skill 不产生「已修复」状态，修复执行归 bug-surgical-fix / rigorous-dev）：

| ID | 终态 |
|:---|:---|
| FE-1 / FE-2 / FE-3 | **待修**（P2，批 A；FE-1 需业务确认硬盘序列号门槛后落地） |
| BE-1 / BE-2 / FE-4 / FE-5 / FE-6 / FE-7 | **待修**（P3，批 B/C，均为单点优化） |
| L-1（_safe_log 吞异常） | **不采纳**（已声明双审计链分层取舍 M-AUD-3；update 路径已走 OperationLogService 直调，残余面为 create 类，留痕备查） |
| L-2（admin_actions 漏挂机制） | **不采纳**（抽查零实例；「新增 @action 必须显式权限」守卫建议随批 B 顺带登记） |
| L-3（ContactsView 独立壳） | **不采纳**（疑似移动端/扫码有意设计，建议加注释锚定意图即可） |
| 通过项（状态机旁路 0 / 契约 4 项 / SC 分流 / 分页 / 依赖 / 健康端点） | **已确认**（证据命令见 §三 尾部复核入口） |

**评审结论**：报告覆盖 §5 全部专项维度且每行有命令输出或源码引用支撑；9 条正式问题均具备 级别/类型/file:line/symbol/回查命令 五要素，P2 三条均有影响面（codegraph impact 实证）+ 修复建议 + 建议验证方式。**部署上线规范符合性：符合**（核心阻断面零残留，新发现均为 P2/P3 优化项，不构成阻断；建议批 A 修复后放量）。CT-2 覆盖率以 CI `40466576631`（90.09%，BF-161 对账口径）为权威；本地全量复跑超时转后台未出数，按 CT-7 不据此下结论。
