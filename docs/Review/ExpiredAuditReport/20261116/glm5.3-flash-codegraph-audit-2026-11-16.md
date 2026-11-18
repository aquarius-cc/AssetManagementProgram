# CodeGraph 全库上线前审计报告（glm5.3-flash）

> 日期：2026-11-16 ｜ 模式：纯审计不修复（workflow v1.2.0）｜ 基线：根 AGENTS.md v3.7.8
> CodeGraph：up to date，1,159 文件 / 19,952 节点 / 46,496 边（Python 524 + TS 490 + Vue 122）

## §一 项目上下文（阶段 1 结构报告）

### 1.1 技术栈与模块边界

| 端 | 技术栈 | 目录 | 分层 |
|---|---|---|---|
| 后端 | Django 6.0 + DRF 3.16 + PostgreSQL 16 | `asset_management_backend/` | Model→Selector→Service→Serializer→View（五层铁律）；apps：assetmanagement / authusermanagement / usermanagement / unregisteredasset / notification；core/ 框架层（审计、信封、健康探测、指标、护栏） |
| 前端 | Vue 3.5 + TS 6.0 + Element Plus 2.10 + Vite + Pinia | `vue-assetmanagement/` | views / components / composables / stores / api / utils / types |

### 1.2 分域清单（阶段 1 探索结论）

| 分域 | 锚点（file:line 实证） | 状态 |
|---|---|---|
| 资产状态机 | `state_machine/transitions.py:32` VALID_TRANSITIONS（8 态齐全：IN_STORE/IN_USE/RECYCLED_PENDING/BROKEN/REPAIRING/LOST/DAMAGED/SCRAPPED，SCRAPPED 终态空集）；`core.py:112` 唯一写态点 `asset.asset_current_status = target_state.value`；mixin 直写仅限 state_machine 包内（out_recycle.py:74,109 / scrapping.py:80,131 / unregistered.py:56,89,128，均为规则文档 §三「特殊回退操作」已登记的具名旁路：S1 创建即回收/报废、cancel_outasset、cancel_recycle、cancel_damaged、reject_to_original） | 与规则文档 §三逐条比对通过；M-30 双入口共边（repairing→damaged 元组边）已按文档落地 |
| 合同状态机 | `state_machine/contract_fsm.py:57` ContractFSM、`_CONTRACT_TRANSITIONS` 单一事实源；非法态收敛 `ContractInvalidTransitionError`；`allowed_next_states` 脏数据返 []；调用方 `services/contract_service.py`；测试锚 `test_contract_fsm.py` | 8 态单向链与规则文档 §3.1 一致 |
| API 响应契约 | `utils/response_utils.py:23` success_response —— 176 callers 覆盖全部 View；schema 侧 `core/envelope_schema.py` 信封后处理器（OP-09） | 唯一入口成立，待阶段 2 抽查手写 dict 旁路 |
| 前端状态枚举 | `src/types/asset.ts:47` enum AssetCurrentStatus（8 键与后端一致）；`scan.ts` / `outasset.ts` / `repairasset.ts` / `lostasset.ts` 中 asset_current_status 为 string 宽化类型 | 键名契约一致；宽化类型留阶段 2 评估 |
| 鉴权域 | `authusermanagement/`：AuthService / AuthUserSelector / AuthUserBackend / AuthAuditAdapter | 待阶段 2 语义诊断 |
| 操作日志域 | `services/operation_log_service.py:100` OperationLogService、`:424` OperationLogQueryService、`selectors/operation_log_selector.py:28`、`views/operation_log_views.py:144` 导出视图 | 待阶段 2 |
| 批量导入 | 前端 `src/utils/readExcelFile.ts` + `composables/useBatchImport.ts` 客户端解析；后端无文件上传端点（SC-5/6 攻击面不适用——仅 Excel 导出与二维码 PNG 生成，无 InMemoryUploadedFile 接收点） | 导入校验链待阶段 2 |
| 健康端点 OC-6 | `config/urls.py:113-114` `/health/` `/ready/`，探测经 `core/health_probe.py` 唯一收口 | 存在 |
| CI 门禁 | `ci.yml`：ruff / 护栏自测 / BR-4 / BR-6 / BR-D1 / mypy / C90 / 权限码同步 / oasdiff / 文档护栏…；`security-scan.yml`、`migration-check.yml`、`ci-cd.yml`（部署 gate） | 待 §5.4 复核 |

### 1.3 图谱外事实（rg / read 补齐）

- **SC-1 密钥扫描**：业务目录（apps/core/config）零命中（`.venv` 命中均为第三方库源码，排除）。
- **SC-3 原生 SQL**：`core/health_probe.py:32` `cursor.execute("SELECT 1")`（常量、无用户输入，安全）；core/tests 1 处（测试夹具）。业务 apps 零 raw()/extra()。
- **分页契约**：前端 api/asset.ts 发送 `page` / `page_size`（组件内 `pageSize` 仅为本地位名，非线参数名）。
- **重复代码活账本**：`Rules_Fiels/Duplicate_Codes/complete-patterns.md` 存在（根 AGENTS §1.8 引用；本次审计发现的重复模式登记义务见 §二/§三）。

## §二 问题台账（阶段 2/3，含影响面与建议验证方式）

> 分级：P0 阻断/高危、P1 重要、P2 一般缺陷/规范偏离、P3 优化建议。全部条目均基于源码证据确认（无推测性条目）；「回查命令」可直达源码。本次审计不改代码，状态不含「已修复」。

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 影响面 | 优先级 | 建议验证方式 |
|---|---|---|---|---|---|---|---|---|---|---|
| BE-1 | P3 | 可观测性 | apps/assetmanagement/state_machine/scrapping.py:72-78,123-129 | cancel_damaged / reject_to_original | original_status 非法/缺失时静默兜底 recycled_pending（行为与规则文档一致），兜底发生时无任何日志痕迹 | 兜底分支补一条 logger.warning（含原值与兜底结果） | `codegraph node cancel_damaged` | 兜底分支仅 2 处；caller: damaged_asset_service.py:356-376 | 低（排障体验） | 单测：传非法 original_status，断言 warning 日志 |
| BE-2 | P3 | 异常处理 | apps/assetmanagement/migrations/0010_migrate_paid_record_to_json.py:113-114 | （数据迁移函数） | `except Exception` 后仅 print 吞错继续跑下一条，不走 logger、不计数 | 改 logger.error + 失败行计数汇总输出 | `codegraph query migrate_paid_record` | 一次性历史迁移脚本，无生产调用面 | 低 | 迁移 dry-run 复跑确认无行为变化 |
| BE-3 | P3 | 数据一致性 | apps/assetmanagement/services/recycle_asset_service.py:213 | （recycle 状态落库） | `save(update_fields=["asset_current_status"])` 缺 `"updated_at"`（其余状态写路径均含），B8 时间戳精度受损 | 补 `"updated_at"` 进 update_fields | `codegraph node recycle` | 单文件单点 | 低 | 单测断言 recycle 后 updated_at 变更 |
| BE-4 | P2 | 规范对齐 | apps/authusermanagement/views.py:67-84 | AuthUserViewSet.get_permissions / check_object_permissions | 写操作（update/partial_update/destroy）用 IsAuthenticated + 手工对象级检查（本人或系统管理员）替代角色权限类，B11 字面偏差；敏感字段已 read_only，无提权面 | 收敛为具名权限类（IsSystemAdminOrSelf），语义不变、形态归一 | `codegraph node AuthUserViewSet` | 3 个写 action；serializers.py:38-45 读侧补偿 | 中（规范一致性） | 权限矩阵回归（test_authusermanagement） |
| BE-5 | P2 | 防御性 | apps/usermanagement/views/employee_view.py:81 | EmployeeViewSet.queryset | 类属性挂未过滤全量 queryset（get_queryset() 已正确覆写，当前无旁路），属"死闸门"：未来任何 `self.queryset` 引用会静默绕过员工域行级隔离（§4.7） | 类属性改 `Employee.objects.none()` 并注释"必须经 get_queryset_for_user"；同型 AuthUserViewSet.queryset（authusermanagement/views.py:55）一并治理 | `codegraph node EmployeeViewSet` | EmployeeViewSet 5 路读端点依赖覆写；grep 全目录当前零 `self.queryset` 直查 | 中（防回归） | grep 护栏或测试断言类属性为 none() |
| BE-6 | P2 | 安全日志（OC-3） | apps/notification/helpers.py:110-116 | _notify_after_commit | `logger.error(..., exc_info=True)`——on_commit 回调异常可能是 DB/Redis 连接异常，traceback 落盘可含连接串，违反项目自身 audit_failure.py:28 明文口径（只记 exception_type） | 去掉 exc_info，改只记 `type(exc).__name__` + channel | `codegraph impact _notify_after_commit` | 10 个受影响符号（helpers.py 2 处 + test_notification.py 3 用例） | 高（先于其余 P2） | 镜像 test_health_ready 零泄露断言写通知侧用例 |
| BE-7 | P2 | 输入校验 | core/request_context.py:53 | RequestContextMiddleware | 外部可控 `X-Request-ID` 未做长度/字符校验即写入日志与响应头（日志膨胀/异常字符风险；响应头换行由 Django 挡） | clamp 长度 + 字符白名单后再采纳 | `codegraph impact RequestContextMiddleware` | trace_id 全链（TraceIDFilter/JSONFormatter/响应回写） | 中 | 单测：超长/特殊字符 trace_id 断言截断与回写 |
| BE-8 | P3 | 日志风格 | apps/notification/services/notification_service.py:51,87,257 | （3 处 logger 调用） | f-string 拼接非 lazy 参数；异常经 `{e}` 字符串化，与 audit_failure「只记 type 不记消息」口径不一致（仍走 JSON formatter，非绕过） | 改 `%s` lazy 参数、异常只记 type | `codegraph node NotificationService` | 3 处调用点，无行为影响 | 低 | 人工复查 + lint（可加自定义规则） |
| BE-9 | P3 | 脱敏覆盖（OC-3） | core/audit_sanitizer.py:17 | SENSITIVE_FIELDS 登记表 | 按字段名精确匹配仅登记 employee_phone；新增 PII 字段（phone 别名/身份证类）必漏（当前身份证字段无审计快照引用，属覆盖面单薄非实际泄露） | 人工确认 PII 面后扩登记表（或前缀/别名策略），保持测试 passthrough 语义同步 | `codegraph node mask_sensitive_snapshot` | core/audit_service.py:51-52 唯一写入点 | 低（前瞻） | 新增 PII 字段脱敏用例 |
| BE-10 | P2 | 上线清单（安全） | core/metrics.py:84-86 | （/metrics/ 视图） | METRICS_TOKEN 默认空 = /metrics/ 完全匿名放行（代码注释自认为已知取舍），无 fail-fast 强制；生产暴露面取决于部署端口策略 | production settings 校验：未设 METRICS_TOKEN 时告警或拒绝启动（或部署 checklist 强制项） | `codegraph node Metrics` | /metrics/ 单端点 + config/prometheus.auth.yml 配套 | 中（上线前必须决策） | production 配置单测 + 部署演练验证 401 |
| BE-11 | P3 | 指标污染（OC-4） | core/prometheus_middleware.py:53 | PrometheusMiddleware | 排除名单仅精确 `/metrics/`；/health/ /ready/ /static 计入 REQUEST_COUNT/ACTIVE_REQUESTS，探针流量（30s×2）污染业务基线 | 排除名单扩展健康端点与静态资源 | `codegraph node PrometheusMiddleware` | 中间件全局 | 低 | 中间件单测断言探针不计入 |
| FE-1 | P3 | 可观测性 | vue-assetmanagement/src/utils/statusMapping.ts:208-220 | getStatusInfo | 后端扩枚举时前端未知键静默降级（英文原值渲染、图表扇区无色）；唯一告警点在 StatusTag.vue:62-65，直调函数绕过 | getAssetStatusText / getAssetStatusTagType 等直调函数补 logWarn（开发期提示即可） | `codegraph callers getStatusInfo` | 直调点如 BasicAssetDetails.vue:200-201、AssetForm.vue:337；ASSET_STATUS_CHART_COLORS 同根因 | 低 | 未知键单测断言 warning |
| FE-2 | P2 | 信任边界 | vue-assetmanagement/src/utils/readExcelFile.ts:84-107 | readExcelFile | 批量导入链前端无行数上限与文件大小前置校验：worksheet.eachRow 全量入内存、previewData 全量响应式数组；文件类型校验仅依赖 el-upload accept（AssetBatchImport.vue:228 未做 raw 校验）；且无「真实拦截在后端」对偶契约注释（导出域 EXPORT_MAX_ROWS 有镜像模式，api/config.ts:28-49） | 与后端对齐导入行数上限，readExcelFile 入口 fail-fast；补 accept 之外的 MIME/大小前置校验；注释对偶契约 | `codegraph impact readExcelFile` | 4 个受影响符号；caller: useBatchImport.ts:51-66 → 3 个导入页 | 高（DoS 面 + 体验） | 上限与大文件单测；后端上限核实留痕 |
| FE-3 | P2 | 重复代码（DR-2/FR-1/FR-2） | vue-assetmanagement/src/components/componentsdetails/detils/AssetBatchImport.vue:274-319、AssetTypeBatchImport.vue:306、ContractBatchImport.vue:222-248 | applyFailedMapToRows / buildFailedMap（三份同型） | 批量导入提交管线 ≥3 处同型复制：failedMap 构建 + 行状态回写函数体逐行等价，基座 useBatchImport.ts:76-145 / SubmitBatch.ts 已有同能力；且映射语义分叉（基座按 idField、组件按行序 idx），改一处漏三处 | 下沉 failedMap 构建与行状态回写到 SubmitBatch/useBatchImport，组件仅留 config；统一映射语义 | `codegraph callers applyFailedMapToRows` | 3 组件 handleSubmit 各 1 caller；FR-1/FR-2 红线关联（按 DR-2 属 [HALT] 强制提取，建议修复批次一次清干净） | 高（活账本新发现义务：登记 complete-patterns.md） | 三页导入失败行回写回归 spec + 活账本登记 |

### 2.1 明确「未发现问题」的维度（16 维度中已核证部分）

- **功能完整性/跨端契约 4 项**：响应根结构 success_response 唯一入口（176 callers）+ schema 侧信封后处理器；状态枚举 8 键两端一致；分页 page/page_size 两端一致；日期 ISO 8601 +08:00 契约未变。M-22（按 code 判定）与 F11（组件禁直连 axios）零违规。
- **状态机**：7 处直写旁路全部为规则文档登记的具名例外且带锁+审计；CT-3 全路径 48 用例覆盖；无未登记旁路。admin readonly + serializer 写字段排除双保险（P0-1 回归约束）成立。
- **事务/并发**：全部状态写入口 @transaction.atomic；通知唯一入口 send_notification_on_commit（robust on_commit），无事务内 WS 直发；TOCTOU 模板统一（select_for_update + 锁内复检）。
- **审计留痕（B7）**：状态转换后 AuditLogger.log_state_change 全覆盖；strict 语义符合 M-19 口径。
- **RBAC（B11-B14）**：除 BE-4 字面偏差外无越权面；未登记资产 approve 防代签、越权 404 语义成立；公开扫码 6 字段白名单 + 双限流成立；读面豁免仅 3 条登记项；自注册生产 fail-closed 成立。
- **前端权限面**：路由守卫 write 默认 deny + 双层兜底；F6/F10/F12/F13 零违规。
- **异常吞没**：生产代码零裸 except；3 处 except Exception 均合规（计数+日志）。

## §三 分域结论与修复建议（按优先级排序）

> 排序规则：同域合并 → 级别优先 → 影响面小者先行；同型问题归并批次一次清干净。

### 批次 1：上线前安全决策项（P2，先决）
| 项 | 去处 | 方案方向 |
|---|---|---|
| BE-6 日志泄露面 | helpers.py:110-116 | 去 exc_info 只记 exception_type（1 行级改动 + 1 用例） |
| BE-10 /metrics/ 匿名放行 | core/metrics.py:84-86 + production settings | fail-fast 或部署清单强制 METRICS_TOKEN（需产品/运维拍板暴露面） |
| FE-2 导入链无上限 | readExcelFile.ts:84-107 | 与后端对齐行数上限 + 入口 fail-fast（需后端上限核实） |

### 批次 2：规范对齐与防回归（P2）
- BE-4 权限形态归一（authusermanagement/views.py:67-84）
- BE-5 死闸门治理（employee_view.py:81 + authusermanagement/views.py:55，同型一并）
- FE-3 导入提交管线去重（3 组件 → 基座下沉；**附带义务：按根 AGENTS §1.8 新发现义务登记 complete-patterns.md 活账本**）

### 批次 3：P3 卫生批（可并入日常修复）
- BE-1（兜底补日志）/ BE-2（迁移 print 规范化）/ BE-3（update_fields 补字段）/ BE-7（trace_id 校验）/ BE-8（lazy logging）/ BE-9（脱敏表扩展）/ BE-11（探针指标排除）/ FE-1（未知键告警）

### 上线门禁复核结论（§5.4 口径）

| 检查 | 结论 | 证据 |
|---|---|---|
| SC-1 密钥 | ✅ 零命中 | 业务目录 grep（apps/core/config） |
| SC-2 CI 密钥扫描 | ✅ 必查 | security-scan.yml（任何情况下均必查） |
| SC-3 SQL 注入 | ✅ 无拼接点 | 唯一命中 health_probe.py:32 常量 SELECT 1 |
| SC-4 动态表名 | ✅ 无 | apps/core 零 raw()/extra() |
| SC-5/SC-6 上传 | N/A | 后端无文件上传接收点（仅导出与二维码 PNG 生成） |
| SC-7/SC-8 依赖漏洞 | ⚠️ 本地不可达，以 CI 为权威 | pip-audit 2.10.1 无法连 PyPI feed；npm audit registry 端点网络失败——均留痕，权威门禁 = CI security-scan.yml（含 2 条豁免登记在册，失效日 2026-12-10） |
| CT-2 覆盖率 | ✅ 本地 90.51%（≥80），2455 passed | pytest --cov 本地实测（CT-7：仅讨论中间量，权威 = CI run $GITHUB_STEP_SUMMARY；Service 层 4 项 90% 门禁由 ci.yml backend-test 固化） |
| CT-3 状态机全路径 | ✅ 48 用例全边覆盖 | test_state_machine.py 清单核对 |
| DR-5/DR-6 规模 | ✅ 护栏 PASS（exit 0，最大 485 逻辑行） | check_file_length_guard.py --print（LT-3 唯一口径） |
| OC-6 健康端点 | ✅ /health/ /ready/ 存在 | config/urls.py:113-114 |
| 变异测试 T7/T16 | 未执行（本地） | mutmut Windows 拒绝运行（T7 平台限制）；以 CI backend-mutation 为权威 |
| 前端三项检查 T17 | 未执行（本地） | 以 CI frontend-type-check/lint/format 为权威（lint:ci 检查模式） |

## §评审结论（阶段 5 质量自审）

- **证据回查**：台账 14 条全部具备 file:line / symbol / 回查命令五要素；抽查 4 条 P2 条目（BE-6 / BE-10 / FE-2 / FE-3）的源码引用与 on-disk 代码逐一一致。
- **闭环检查**：本次台账无 P0/P1 条目；全部 11 条 P2/P3 均具备 证据 + 影响面 + 修复建议 + 建议验证方式。无「不采纳」条目。
- **置信度纪律**：4 路 subagent 诊断均按置信度 ≥75 过滤上报；未达门槛的疑点（如 channels_redis 超时参数、generic_audit_dispatch 样本不足）未列入台账，仅在过程记录中留痕。
- **台账终态**：14 条均为「已确认（待修）」；本审计不产生「已修复」状态，修复交接按批次 1→2→3 排序可直接接手（bug-surgical-fix / rigorous-dev）。
- **活账本新发现义务**：FE-3（批量导入提交管线三份同型）须按根 AGENTS §1.8 登记 `Rules_Fiels/Duplicate_Codes/complete-patterns.md`，本报告不代登记（属写入义务，移交修复批次时同步）。
- **本地环境漂移声明（CT-7）**：覆盖率 90.51% 为本机实测讨论中间量；pip-audit/npm audit 本地网络不可达未取得结论——以上均以 CI run 为权威，未以本地数字下阻断性结论。
- **只读纪律**：本次会话唯一落盘产物为本报告文件，未改动任何业务代码。


