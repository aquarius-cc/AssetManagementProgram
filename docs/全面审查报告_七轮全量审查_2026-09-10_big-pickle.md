# 资产管理系统 全面审查报告（七轮全量）

> **审查 Agent**：big-pickle（opencode/big-pickle）
> **审查日期**：2026-09-10
> **审查范围**：后端 `asset_management_backend`（Django 6 / DRF 3.16）+ 前端 `vue-assetmanagement`（Vue 3.5 / Element Plus / Pinia）+ 根级/子域规范 + CI/安全治理
> **审查方法**：只读静态审查（源码阅读 + grep/路径实证 + 账本核验），不修改任何代码；以 `docs/Review/Review.md` 定义的七轮流程为依据。
> **配套阅读**：本报告为独立交付物，不覆盖 `docs/Review/Review.md`。

---

## 一、审查概要

本轮按七轮流程执行完毕：

| 轮次 | 主题 | 结论 |
|:--|:--|:--|
| R1 | 架构分层 | 通过（五层架构 + 状态机收敛） |
| R2 | 需求与接口契约 | 通过（含用户逐项确认） |
| R3 | 状态机 + CT-3 | 有条件通过（测试 23/25，缺 2 条用例） |
| R4 | 权限与安全 | 发现问题 R4-01（P1）、R4-03（P2）等 |
| R5 | 事务/通知/可观测性 | 通过（R5-04 死指标等小项） |
| R6 | 测试覆盖 + DRY + 规模 | 发现问题 R6-03（P2 死文件）等 |
| R7 | 跨端契约终核 | 通过（R7-01 时间契约措辞偏差） |

总体评价：**架构与代码质量高，测试与 DRY 护栏扎实；存在 1 项安全越权（P1）、3 项高影响问题（P2）需在收尾阶段修复。**

---

## 二、逐轮审查结论

### R1 架构分层

- **五层架构**全部成立：Model（仅字段/元数据）→ Selector（QuerySet 封装 + `get_queryset_for_user` 行级隔离）→ Service（业务逻辑 + `@transaction.atomic`）→ Serializer（校验，禁 DB 操作）→ View（仅接线）。
- **状态机收敛**：资产状态流转唯一实现 `apps/assetmanagement/state_machine/core.py::AssetFSM`（DR-1），分支模块 BrokenLostRepair / Scrapping / Recycle 等。
- **行级隔离**：`core/department_scope.py` 三路径（资产保管人→入库人→仓库管理员）+ 部门级角色最严兜底。
- 未发现跨层调用、重复业务实现。

### R2 需求与接口契约

用户逐项确认/已核实项：

- 前端缺 `changePassword`（`vue-assetmanagement/src/api/auth.ts` 未实现修改密码接口）。
- `AssetTypeTree` 仅作展示用途。
- 取消出库/取消回收与相关导出在前端无入口（后端能力存在）。
- 后端 `apps/usermanagement/views.py`（894 行）为遗留死代码 —— 本轮 R6-03 实证为**包遮蔽死文件**；✅ 已删除（见 R6-03）。
- **R2-10**：`found_and_return` 实现目标为 `recycled_pending`，07 文档 AC-38（找回）与 AC-40（维修完成）误写 `in_store` —— ✅ 已拍板：以状态机语义为准（transition 表 L19-20 明示"已使用资产统一入待发放池，in_store 仅首次入库"）；07 文档两处已同步为 `recycled_pending`。R5-01 结论：业务需求（07 4.11 AC-49/50 + 业务细则 4.5）无"未登记通知"要求 → No-Op，不补代码。

### R3 状态机 + CT-3

- 资产状态枚举八键收敛于 `AssetStatus`（`models/asset.py`）；FSM 转换表触发名与实现方法名整体一致。
- Service 层全部 `@transaction.atomic`，审批拒绝按 `original_status` 回退（业务约束 §三.5）。
- **CT-3 结论**：实现侧全路径成立；测试覆盖 **25/25（100%）**（R3-01 broken→damaged、R3-02 reissue 已补测，2026-09-10）。
- 发现：R3-01~R3-07（详见三、全量发现清单）。

### R4 权限与安全

**强项**：

- RBAC 四级角色矩阵（`core/permissions.py`：system_admin > dept_manager > asset_admin > regular，auditor 独立只读旁路）。
- 行级隔离：全 Selector 经 `get_queryset_for_user` 收敛；`PermissionViewSet` 只读；配置管理写操作 `IsSystemAdmin`。
- 认证：JWT 双通道（Bearer 优先 / Cookie 兜底），Cookie 通道非安全方法强制 CSRF；refresh 轮换 + 黑名单。
- 节流：注册 5/min、登录 5/min/用户，连续失败 5 次锁 15 分钟。
- 生产安全基线：`production.py` 强约束 SECRET_KEY（≥20 字符 + 弱密钥黑名单）与 ALLOWED_HOSTS。

**SC 核对**：

| ID | 结论 |
|:--|:--|
| SC-1 密钥硬编码 | ✅ 全仓常见密钥模式 grep 无命中 |
| SC-2 CI 密钥扫描 | ✅ 已修复（R4-03）：YAML 合法 + 排除 `.github/.git` + docs 凭据脱敏，本地复现 0 命中 |
| SC-3 SQL 注入 | ✅ 无用户输入拼接（仅 `SELECT 1` 静态健康检查） |
| SC-4 动态表/列名 | ✅ filterset/ordering/search 均白名单 |
| SC-5/6 文件上传 | ✅ N/A（无上传端点；10MB 上限已配置） |
| SC-7 依赖漏洞扫描 | ✅ 已修复（R4-03）：workflow 解析恢复，pip-audit/npm audit 恢复阻断 |
| SC-8 每周扫描 | ✅ 已修复（R4-03）：weekly-report job 恢复 |

### R5 事务 / 通知 / 可观测性

- `send_notification_on_commit`（`apps/notification/helpers.py:73`）：非事务块直接抛错 + `on_commit(robust=True)` + 回调异常容错 —— 语义健壮。
- 通知落点全量：damaged 审批通过/拒绝、repair 创建/完成/失败（5 处事务锚定），均带 mock 测试。
- WebSocket：JWT（Sec-WebSocket-Protocol 子协议）认证，无效→4401、身份与 URL jobcode 不符→4403 防冒充；`mark_read` 限定本人；生产强制 `channels_redis`。
- 可观测性：trace_id（`core/request_context.py` + `X-Request-ID` 透传 + 响应回显 + `TraceIDFilter`）；JSON 日志（`core/json_formatter.py` + 生产 console 切换）；/health、/ready（DB+Redis 探活，503 降级）；Prometheus 指标实现就绪（路径归一化防高基数）。
- QPS < 10 阈值：OC-4/OC-7 按契约 `[~]` 豁免。

### R6 测试覆盖 + DRY + 规模

- 后端测试文件约 70+（服务/接口/状态机/并发/审计/安全全覆盖）；前端 vitest 全量 ~1456 用例。
- **CT-2**：Service 层覆盖率 90.48%（活账本 D-1 实测值）；整体 ≥80% 门禁在只读阶段未复跑（运行 pytest 会写 `.coverage` 产物），留待执行阶段终验。
- **DR-5 扫描（>500 行）**：后端仅 `apps/usermanagement/views.py`（1005 行，见 R6-03）与 `.trae/skills` 工具脚本；前端生产代码仅 `router/index.ts`（752 行，已带 `TECHNICAL_DEBT` 头），其余为 spec 测试文件（见 R6-04）。
- **DRY 账本核验**：`Rules_Fiels/Duplicate_Codes/complete-patterns.md` v2.9.18，四区基本归零；G-1~G-3 护栏 CI `duplicate-guard.yml` 守护，账本记录 PASS；（新发现 R6-03 需登记）。

### R7 跨端契约终核

| 契约项 | 结果 |
|:--|:--|
| 响应根结构 `{"code":0,"data":{},"message":str}` | ✅ 全局统一（success/error_response + 全局异常 handler） |
| 资产状态枚举八键 | ✅ 后端 `AssetStatus` = 前端 `statusMapping.ts::ASSET_STATUS_MAP`（8/8，spec 锁定） |
| 分页参数 `page` / `page_size` | ✅ `core/pagination.py` 显式声明并全局统一 |
| 日期时间 ISO 8601 | ✅ R7-01 已对齐（2026-09-12）：契约措辞改为"ISO 8601 含时区偏移（±HH:MM，实际输出 +08:00）"，全仓 Z 字面仅 2 处已同步，前端零影响，勿动 UTC（Format.ts 混用第九轮 P2 已记录） |

---

## 三、全量发现统一清单

### P1（安全 / 门禁阻断）

| ID | 位置 | 问题 | 修复建议 |
|:--|:--|:--|:--|
| R4-01 | `selectors/dashboard_selector.py`（全方法）+ `views/dashboard_view.py:19` | 仪表盘所有统计直接 `Asset.objects.filter(...)` **全库统计，无 user/部门范围**，且仅 `IsAuthenticated` —— 任意普通用户可见全公司资产总量/总价值、最近出库/回收记录（含跨部门领用人姓名+部门名）、部门/类型分布、到期/维护清单。与系统其余 Selector 的行级隔离模式不一致。 | **【已修复 2026-09-11】** 复线复用 `core/department_scope.get_department_codes_for_user`：全量角色(system_admin/auditor/superuser/无Employee)→全量；部门级角色→限定部门（dept_manager 含下级）；部门级但无部门→空集。8 个方法全部增加 `user` 参数，`dashboard_view` 各 action 传 `request.user`；OutAsset/RecycleAsset 复用 `get_asset_linked_queryset_for_user`；部门分布仅展示范围内部门（不泄露他部门姓名/名称）。新增 7 条行隔离测试（regular_a/regular_b/dept_manager/空部门/auditor/部门分布不泄露/最近出库隔离），全量 `1073 passed`。 |
| R4-03 | `.github/workflows/security-scan.yml`（~L74-79、L130-132） | checkout 步骤**重复 `with:` 键**导致 workflow YAML 非法；且黑名单三条已轮换凭据明文仍存在于 **`docs/` 两份历史报告**（`docs/项目全面审查报告_融合版_2026-08-26.md:109`、`docs/全面审查报告_补充维度_2026-08-29_AtomCode.md:97`），`rg -F` 黑名单扫描必失败 → SC-2/SC-7/SC-8 三条安全门禁实际失效（含 pip-audit/npm audit 与 weekly-report）。注：`rg` 默认跳过隐藏目录，workflow 自身非"自命中"来源。 | **【已修复 2026-09-11】** ① 合并重复 `with:`（submodules + fetch-depth 共存）；② 黑名单扫描与裸赋值扫描增加 `-g '!.github/**' -g '!.git/**'` 排除；③ docs 两处凭据字面量脱敏（融合版 L109 → `dev_asset_mgmt_xxxx`/`prod_asset_mgmt_xxxx`，补充维度 L97 → `PostgresTerminal@[已脱敏]`）。本地复现 CI 命令三字符串均 0 命中，YAML 解析通过。 |

### P2（高影响 / 契约违例）

| ID | 位置 | 问题 | 修复建议 |
|:--|:--|:--|:--|
| R3-03 / R4-02 | `services/asset_lifecycle_mixin.py:109-121` + `views/asset_view.py:410-420` | `find_and_return_asset` 抛原生 `LostAsset.DoesNotExist`，View 层无捕获，全局 handler 兜底 → **500 通用错误**（应 400 + 业务 error_code）。 | ✅ 已修复：Service 层三处转换（`ASSET_NOT_FOUND` / `NO_LOST_RECORD` / `INVALID_STATE_TRANSITION`）→ 400；`core/exception_handler.py` 保持不透传 error_code（既有设计）；补 2 测试。全量 1074 passed。 |
| R6-03 | `apps/usermanagement/views.py`（1005 行） | 与同名包 `views/` 共存，`views/__init__.py` re-export 包内活实现（`views/department_view.py:35`、`views/employee_view.py:42`），`urls.py:13` 走包 —— **views.py 为 B-11 同型遮蔽死文件**，含过期契约示例（`'code': 200`），持续"改不生效"误导。 | ✅ 已修复：确认无路径级引用后整文件删除（对齐资产域 `c64675c`）；账本 B-14 登记并关闭；`manage.py check` + 全量 1074 passed。 |
| R2-10 | 07 文档 AC-38 vs `recycled_pending` | `found_and_return` 实现目标为 `recycled_pending`，验收文档写 `in_store`。 | ✅ 已拍板（改文档）：AC-38（找回）+ AC-40（维修完成）同步为 `recycled_pending`；其余 in_store 出现点核对与实现一致，未动。 |
| R5-01 | `apps/unregisteredasset/services.py::approve_and_handle` 及出库/回收 | 未接入 `send_notification_on_commit`；若业务要求"未登记审批通过/出库/回收后通知部门经理"则属覆盖缺口。 | ✅ 结论：No-Op —— 业务需求（07 4.11 + 细则 4.5）无通知要求；approve_and_handle 已 @transaction.atomic（L315-316），若未来补需求可直接按 damaged 先例接入。 |

### P3（质量 / 防护 / 一致性）

| ID | 位置 | 问题 | 修复建议 |
|:--|:--|:--|:--|
| R3-01 | `test_state_machine.py` | `broken → damaged`（to_damaged）FSM 层与 Service 层均无测试（CT-3 缺口）。 | ✅ 已修复：`TestBrokenToDamaged`（FSM）+ `test_create_from_broken_success`（Service）。 |
| R3-02 | `test_recycle_asset_service.py` 等 | `RecycleAssetService.reissue_recycle_asset`（recycled_pending→in_use）全仓零测试（CT-3 缺口）。 | ✅ 已修复：`TestReissueRecycleAsset` 3 用例（正向/记录不存在/状态前置校验）。 |
| R3-04 | `services/asset_lifecycle_mixin.py:271 / :293` | 批量载荷键不一致：`batch_create_broken_assets` 用 `asset_recordcode`，`batch_create_lost_assets` 用 `asset_code`。 | ✅ 已修复：两端统一为 `asset_code`（后端序列化器 :177 + 读取键 :271；前端 brokenasset.ts 批量项类型）；补 2 用例，全量 1082 passed。 |
| R3-05 | 状态机转换表 | 触发名 `to_damaged` 与实现方法名 `damaged()` 不一致（可读性）。 | ✅ 已修复：方法 `damaged()` → `to_damaged()`，调用 4 处同步，全量 1084 passed，状态机一致性达 100%。 |
| R3-06 | `scrapping.py::reject_to_in_use` | 常规流程不可达（防御代码）。 | ✅ 已处理：保留并重写 docstring（论证修正：DAMAGED 入边不含 in_use → original_status 永不为 in_use，区分"转换表合法"与"业务不可达"），方法上方已标注 `# AI_REVIEW_NEEDED`（AR-2），待人工复查后移除；57 相关测试 passed。 |
| R3-07 | `damaged_asset_service.py` cancel 流 | `cancel_damaged` 一律回 `recycled_pending`（即使原为 broken/lost/repairing）。 | ✅ 已修复（2026-09-12，产品拍板按申请前状态回退）：`cancel_damaged` 加 `original_status` 参数，回退逻辑与 `reject_to_original` 同构（`_REJECT_TARGETS` 白名单 + 缺失/非法兜底 `recycled_pending`）；服务层传入 `original_status`（保留 `select_for_update` 行锁），批量取消经委托自动继承；技术设计 03 文档旧约定同步修正，业务规范升 v1.11（业务约束新增第 6 条）；新增/改造测试 12 例，目标 68 passed，全量 626 passed。登记 `Bug修复活账本.md` BF-006。 |
| R4-04 | `views/public_scan_view.py` | `AllowAny` + 限流，可未认证枚举 recordcode（404/200 探测），返回保管人姓名/仓库名（电话已脱敏）。 | ✅ 已修复（2026-09-12，拍板=B 收窄字段）：响应收敛为 6 字段白名单（编码/名称/规格/品牌/状态/成色，敏感字段一律不返回，删 `mask_phone_number` 遮罩方案）+ 新增 `public_scan` 审计（成功记 IP，404 不记，anon 20/minute 兜底）+ Selector 免 JOIN；同步 0021 迁移（PUBLIC_SCAN choices，`migration-check.yml` path filter 补 `**/models/**` 堵门禁缺口）；前端三合一：ScanAssetView 登录态直达全量详情（未登录公开 6 字段+登录引导，redirect 回跳由 LogIn.vue 消费）、新增 AssetQuickScan 侧边栏兜底入口（三态解析：recordcode 直查→asset_code 组合搜索→两败 warning）。对抗审核发现 B1（assetStore 导出缺失致主应用崩溃）/B2（扫码路径缺 /assets 前缀必 404）/H1（迁移漂移）/M1（redirect 未消费）均已修复；低危 L1（登录用户无视图级限流→补 `UserRateThrottle`，§4.6 限流说明同步）/L2（qr_code help_text 宣称 JSON 与纯 URL 实现失实→help_text 对齐 + 0022 迁移 + `extractRecordcode` 增 JSON 解析分支 + spec 用例）亦已闭环。后端目标 43 passed、全量 626 passed；前端 type-check/lint/format 过、vitest 1469 passed。 |
| R4-05 | `views/asset_view.py:420` | found 成功文案"遗失资产已找回并入库"与目标 `recycled_pending` 语义不符。 | ✅ 已修复（2026-09-12）：文案改为"遗失资产已找回，已进入待发放"；同源修正 FSM docstring（`broken_lost_repair.py:61` "找回入库"→"找回(重新进入发放池)"）及审核发现的 2 处活文档残留（`业务流程说明书.md:77` lost→in_store 错误行、`设计需求文档_V2.1.md:696` "找回入库"措辞）；目标测试 51 passed；前端成功文案走本地常量（FoundAssetView.vue），后端 message 变更零影响。 |
| R5-02 | `apps/notification/consumer.py::receive` | 无频率限制，大量 ping/mark_read 可刷 DB。 | ✅ 已修复（2026-09-12）：① pong 固定窗口节流（5 次/10s，前端心跳 30s/次余量 15 倍，超限静默丢弃——前端对 pong 无依赖）；② mark_read 消息合并（pending set 去重 + 0.5s 延迟冲刷 + MAX_PENDING=200 超限即冲，批量 UPDATE 保留 recipient_jobcode 越权过滤）；③ disconnect 收尾（shield 等待在途 flush 超时才 cancel + flush 失败 ids 回灌重试 + group_discard 异常兜底防 channel 泄漏）；④ notification_id 整数类型校验（防非可哈希值拆连接）。对抗审核发现 F1-F4 竞态/丢失路径已全部修复（flush 循环取空、cancel 竞态改 shield+回灌、DB 异常不阻断 discard、失败回灌），F5 死代码已删、F6 类型校验已加；测试 22 passed（6 存量零改动 + 3 新增，合并用例经计数断言验证"单次批量写"）；前端零改动（协议不变）。 |
| R5-04 | `core/metrics.py:50-59` | `DB_QUERY_COUNT/DB_QUERY_LATENCY` 定义后**无任何埋点** → OC-5 未落地，/metrics/ 恒为 0 误导。 | ✅ 已修复（2026-09-12，拍板=方案 B 删除）：删除两本未埋点指标定义（全库零引用，`core/prometheus_middleware.py` 仅依赖请求类 4 指标，不受影响）；/metrics/ 不再输出恒 0 的 db 指标（generate_latest 冒烟断言 False/False，HTTP 指标 True）。对抗审核通过：零残留、无测试依赖、结构完整、ruff 全绿、mypy 无新增报错（production.py:95 为存量基线）、core 129 passed。OC-5 保持 [~] 豁免；未来 OC-4/OC-7 转强制时按 CursorWrapper 子类或 django-prometheus 重建并附性能评估（已备注禁用伪 `connection.execute` 信号——Django 无此符号）。 |
| R6-01 / R6-02 | 见上（R3-01/R3-02 复证） | —— | —— |
| R6-04 | `vue-assetmanagement/src/**/__tests__` | 9 个 spec 文件 >500 行缺 `TECHNICAL_DEBT: >500 lines` 头（guards.spec.ts 有标记，其余无；common-forms.scss 664 行不在规则列举后缀内）。 | ✅ 已修复（2026-09-12）：实测超限 spec 共 **11 个**（报告原记 9，实测不含 guards 的缺失为 **10 个**），`guards.spec.ts` 已有标记，对缺失的 10 个文件（api/request、composables/useNotification·useOutAssetForm·usePaginationSearch、stores/auth·createEntityStore·dashboard·departmentStore·userStore、utils/Format）**首行插入与 guards 一致的存量豁免注释**（`// TECHNICAL_DEBT: >500 lines（存量文件，2026-07-07 基线前已超限；本次修改新增 <50 行，暂不拆分）`），零行为影响（纯注释，无 import/逻辑改动）。另核查：`router/index.ts`（752 行）已标记、`common-forms.scss`（664 行）按 DR-5 后缀（.py/.vue/.ts）豁免，均无需处理。前端三项检查 type-check / lint / format:check 全绿。 |
| R6-05 | `vue-assetmanagement/src/router/index.ts`（752 行，存量 TECHNICAL_DEBT 标记） | DR-5 存量超限，标记暂缓拆分。 | ✅ 已拆分（2026-09-12，按 DR-5 新文件从严）：764 行拆为 6 个纯数据路由模块 + 瘦身 index.ts（30 行，删 TECHNICAL_DEBT 标记）——`routes-auth.ts`（32 行，/ + /login，静态 import LogIn.vue 随迁）/ `routes-main.ts`（29 行，/main 外壳 children 组合）/ `routes-main-core.ts`（231 行，children 前段 7 项）/ `routes-main-operations.ts`（207 行，中段 9 项）/ `routes-main-system.ts`（188 行，后段 8 项，children 共 24）/ `routes-standalone.ts`（130 行，9×/assets/:code/* + /scan + /org/contacts + NotFound catch-all 最后）；纯移动零改写（name 73 处无重复[MainViews 重名为死代码注释误报]、props 7 处、requiredMinRole 15 处逐一对码，全部 ≤500 行）；消费链零改动（main.ts/navigation.ts 默认导入不变）。验证：type-check ✅、vitest router 68 passed（index.spec 10 + guards.spec 58）、lint ✅、format:check ✅（3 文件 prettier 格式化）。 |

### P4（观察 / 契约措辞）

| ID | 位置 | 问题 | 建议 |
|:--|:--|:--|:--|
| R7-01 | `config/settings/base.py:136-138` | 未设 `DATETIME_FORMAT`，DRF 默认 ISO8601 + `TIME_ZONE=Asia/Shanghai` → 输出 `+08:00`，契约字面为 `Z`（解析兼容）。 | ✅ 已修复（2026-09-12）：选措辞修正（零行为变化）——契约字面改为"ISO 8601 含时区偏移（±HH:MM，实际 +08:00）"，全仓 Z 字面仅根 AGENTS.md:122 与 docs/Review/Review.md:124 两处（同步走根级 §5.2 补丁流程）；前端无该字面零改动；不动 UTC（避免破坏 Format.ts 解析）。 |
| R4-06 | `config/settings/development.py` | 开发环境有弱密钥 fallback（有 `_INSECURE_KEYS` 校验，生产强制走 `production.py`）。 | ✅ 已修复（2026-09-12，决策 4=B 保留并注明）：README 环境变量段 SECRET_KEY 行扩展注明 dev fallback 仅限本地调试、生产强制 env 注入 + ≥20 字符 + 黑名单，违规启动即抛 `ImproperlyConfigured`；零代码改动。 |
| — | `config/urls.py:153` | `/metrics/` 无认证暴露。 | ✅ 已修复（2026-09-12）：`default.conf.tpl` 443 server 新增 `location = /metrics/` ACL（allow 10.0.0.0/8 + deny all，精确匹配对齐挂载面）。暴露面实态=SPA catch-all 回 index.html（不代理、指标不外泄），ACL 属纵深防御；`prometheus.yml:16` 直抓 web:8000 容器网络不经 Nginx，抓取链路零影响（块注释已注明）。 |

---

## 四、合规矩阵汇总

```
CT-1[√] CT-2[√ 兼容待复跑：Service 90.48%↑（已补 R3-01/R3-02），整体执行阶段终验] CT-3[✅ 25/25（100%），R6-01/R6-02 已补测] CT-4[√] CT-5[√] CT-6[√（无迁移变更）]
DR-1[√（R6-03 已删，完全归零）] DR-2[√] DR-3[√] DR-4[√] DR-5[√ 存量标记补齐（R6-04）] DR-6[√ 调用链 ≤5 / 嵌套 ≤4]
SC-1[√] SC-2[x→R4-03] SC-3[√] SC-4[√] SC-5[√N/A] SC-6[√N/A] SC-7[x→R4-03] SC-8[x→R4-03]
OC-1[√] OC-2[√] OC-3[√] OC-4[~ QPS未达阈值，实现已就绪] OC-5[~ 死指标已移除（R5-04 ✅），DB 监控留待 OC 转强制后按 CursorWrapper 启用] OC-6[√ /health /ready] OC-7[~ 豁免]
AR-1~AR-5[√] Fact-1[√] Style-1~Style-3[√]
```

---

## 五、待拍板决策项（4 项）

| # | 事项 | 选项 |
|:--|:--|:--|
| 1 | R2-10：**found 找回目标状态** | A) 改实现为 `in_store`（直入库）；B) 改文档 AC-38 为 `recycled_pending`（推荐，符合"待发放"流程） |
| 2 | R4-04：**公开扫码枚举可接受性** | A) 接受现状（限流已保护）；B) 收窄返回字段/加验证码 | ✅ 已拍板并落地（2026-09-12）：选 B——6 字段白名单 + public_scan 审计，见 R4-04 行 |
| 3 | R5-01：**通知覆盖范围** | A) 仅现 5 类审批/维修事件；B) 扩至出库/回收/未登记审批 |
| 4 | R4-06：**dev 弱密钥 fallback** | A) 保留（仅本地）；B) 删除，改为必须显式注入 | ✅ 已拍板落地（2026-09-12，方案 A'）：保留 + README 注明仅限本地（见 R4-06 行） |

---

## 六、执行阶段分批计划（收尾修复建议顺序）

- **Batch 1（后端 P1/P2 + 测试补栏）** —— 已完成 1~5；仅剩第 6 项（覆盖率终验）
  1. ✅ R4-01 仪表盘行级隔离（Selector 加 user 范围 + 7 条隔离测试）
  2. ✅ R4-03 `security-scan.yml` 修复（YAML 合并 + `.github/.git` 排除 + docs 脱敏）
  3. ✅ R3-03 `find_and_return_asset` 错误码化 + 测试（1074 passed）
  4. ✅ R6-03 删除 `apps/usermanagement/views.py` 死文件并登记账本（B-14 已关闭）
  5. ✅ 补 R6-01 / R6-02 两条 CT-3 用例（broken→damaged、reissue）→ CT-3 转 25/25
  6. ⏳ 复跑 `pytest --cov=. --cov-fail-under=80` 终验 CT-2

- **Batch 2（后端 P3）**
  - R3-04 批量键统一 ✅ 已修复
  - **A6（R3-04 对抗发现，存量）`mark_asset_broken:33 / mark_asset_lost:75`**：`.get()` 缺失资产抛原生 DoesNotExist、非法转换抛 InvalidTransitionError → 单条/批量均 500。✅ 已修复（复用 R3-03 范式：`.filter().first()`+`ASSET_NOT_FOUND`、FSM 包 try/except+`INVALID_STATE_TRANSITION`），合规对齐 `constants.py:76`（"Service层应捕获并转换为 AppValidationError"）；改 2 测试断言 + 新增 2 用例，全量 1084 passed，Service 覆盖率 93.98%
  - R3-05 触发名对齐 ✅ 已修复：`damaged()` → `to_damaged()`，11 个转换命名一致性达 100%
  - R4-05 ✅ 已修复（见上）、R5-02 ✅ 已修复（见上）、R5-04 ✅ 已修复（见上，方案 B 删除）— Batch 2 待办清零

- **Batch 3（文档 / 前端 P3/P4 + 决策落地）**
  - R6-04 ✅ 已修复 · R6-05 ✅ 已拆分 · R7-01 ✅ 已修复（契约措辞对齐）· R4-06 ✅ 已修复（README 注明）
  - 落实待拍板决策 1~4 全部闭环（R2-10 ✅ / R4-04 ✅ / R5-01 ✅ No-Op / R4-06 ✅）+ R3-04 ✅ 已修复（Batch 2 首项）
  - 将 R6-03（新发现）登记入 `Rules_Fiels/Duplicate_Codes/complete-patterns.md` 活账本并关闭

---

## 七、证据索引（关键文件:行号）

| 主题 | 位置 |
|:--|:--|
| 状态机唯一实现 | `apps/assetmanagement/state_machine/core.py`（AssetFSM） |
| FSM 分支 | `state_machine/broken_lost_repair.py`、`state_machine/scrapping.py`、`state_machine/recycle.py` |
| find_and_return（R3-03） | `apps/assetmanagement/services/asset_lifecycle_mixin.py:109-121` |
| found 动作（R4-02/R4-05） | `apps/assetmanagement/views/asset_view.py:410-420`（admin_actions L67） |
| 批量键不一致（R3-04） | `apps/assetmanagement/services/asset_lifecycle_mixin.py:264 / :286` |
| 行级隔离核心 | `core/department_scope.py` |
| 权限类 | `core/permissions.py` |
| 仪表盘越权（R4-01） | `apps/assetmanagement/selectors/dashboard_selector.py`、`views/dashboard_view.py:19` |
| JWT 双通道 | `apps/authusermanagement/authentication.py` |
| 限流/锁定 | `core/throttles.py` |
| 安全设置 | `config/settings/base.py`、`production.py`、`development.py` |
| 异常兜底（500 路径） | `core/exception_handler.py` |
| 审计 | `apps/assetmanagement/audit.py`、`core/audit_service.py` |
| 公开扫码脱敏（R4-04） | `apps/assetmanagement/views/public_scan_view.py` |
| 事务通知 | `apps/notification/helpers.py:73`、`services/damaged_asset_service.py:157/225`、`services/repair_asset_service.py:214/277` |
| WS 消费者 | `apps/notification/consumer.py`、`config/asgi.py` |
| trace_id | `core/request_context.py`、`core/logging_filters.py` |
| JSON 日志 | `core/json_formatter.py`、`config/settings/production.py:94-97` |
| 指标 | `core/metrics.py`、`core/prometheus_middleware.py`、`config/urls.py:153` |
| 健康检查 | `config/urls.py:54-142` |
| CI 门禁（R4-03） | `.github/workflows/security-scan.yml`、`ci.yml`、`migration-check.yml`、`duplicate-guard.yml` |
| DRY 活账本/护栏 | `Rules_Fiels/Duplicate_Codes/complete-patterns.md`（v2.9.18）、`scripts/check_duplicate_invariants.py` |
| 死文件（R6-03） | `apps/usermanagement/views.py`（1005 行）vs `apps/usermanagement/views/__init__.py` + `urls.py:13` |
| 分页契约 | `core/pagination.py:33-37` |
| 跨端映射 | `apps/assetmanagement/models/asset.py:85-109`、`vue-assetmanagement/src/utils/statusMapping.ts:35-42` |

---

*本报告基于 2026-09-10 只读审查完成；修复落地后建议回读更新本报告相应条目状态。*