# CodeGraph 全项目审计报告（2026-10-27）

> 依据：项目专属审计工作流（`project-all-code-review` 审计模式落地版 v1.2.0）+ 根 AGENTS v3.7.1 + Rules_Fiels 四份规范。
> 只读纪律：本审计未改动任何业务代码；唯一写入为本报告文件。
> 审计基准：git `394efce`（BF-161 CI 直证回填后工作树）；CodeGraph 索引 1,022 文件 / 18,196 节点 / 41,206 边，无陈旧告警。

## §一 项目上下文

| 维度 | 事实 |
|:---|:---|
| 技术栈 | Django 6.0.8 + DRF 3.18.3（base.txt 声明=本机实测一致，CT-7 对齐）；前端 Vue 3 + Vite + Pinia |
| 后端模块 | 7 app：assetmanagement（资产/合同/出入库/回收报废）、authusermanagement（JWT 双通道鉴权）、usermanagement、unregisteredasset、notification（HTTP+WS）、core（横切）、config |
| 状态机 | 资产 FSM（8 态，`VALID_TRANSITIONS` :28-81）+ 合同 FSM（8 态线性链）；写状态单闸 `AssetFSM._transition`（core.py:96） |
| 响应契约 | `utils/response_utils.py:23 success_response`，根结构 `{code:0, message, data}`，全后端唯一入口（277 符号依赖，impact 实测） |
| 鉴权 | `JWTCookieAuthentication`（authentication.py:65）Bearer 优先/Cookie 兜底，cookie 通道非安全方法强制 CSRF（:80-81）；SIMPLE_JWT 30min/7d + ROTATE+BLACKLIST |
| 审计日志 | 双链：资产域 `OperationLogService.log_operation`（同步，事务内一致性优先）+ 通用域 `GenericAuditService`（on_commit 异步，robust=True） |
| 批量导入 | 无文件上传端点（前端解析 Excel 后 JSON `items` POST）；`ensure_batch_size`（batch_mixins.py:44-60）+ 逐条独立事务 + fail_items 行级错误回执 |
| 测试基线 | 全量 2210/0，cov 89.35%（≥80）；notification 专项 98.41%（O 批 BF-160）；CI Pipeline 40466576631 四 workflow 全绿 |

分域探索：4 个只读探索 agent（资产状态机域 / 合同 FSM+响应契约域 / 前端契约+鉴权域 / 鉴权+操作日志+批量导入域），主代理执行 §5 专项命令与语义复核。

## §二 问题台账

> 分级 P0 阻断 / P1 重要 / P2 优化 / P3 建议。台账字段：ID/级别/类型/位置/描述/状态。

| ID | 级别 | 类型 | 位置 | 描述 | 状态 |
|:---|:---|:---|:---|:---|:---|
| AUD-1 | P3 | 文档漂移 | `apps/assetmanagement/state_machine/transitions.py:9-10` | docstring 标注 unregistered 三处直写为 `:56/:88/:126`，实际 `:56/:89/:128`（M-60 互指注释后行号偏移 1-2 行） | 已确认 |
| AUD-2 | P3 | 注释漂移 | `vue-assetmanagement/src/types/outasset.ts:30-34` | `OutAssetType` 注释仅列 receive/borrow，代码含 `REISSUE='reissue'`（后端 out_asset.py:59 有该枚举，值契约一致，仅注释漏列） | 已确认 |
| AUD-3 | P3 | 设计差异留痕 | `services/operation_log_service.py:107` vs `core/audit_service.py:63` | 双审计链写入口径不同：资产域同步（事务内，与业务一致优先）vs 通用域 on_commit 异步（robust=True，提交后写）。两链失败均为吞错+logger.error（audit.py:93-104 / audit_service.py:60-61）。属已声明的分层取舍，非缺陷 | 已确认（留痕） |
| AUD-4 | P3 | 异常吞没 | `apps/assetmanagement/views/_mixins.py:33` | `except DoesNotExist: pass`——views 层 get 语义下吞错即 404，可辩护；但无日志留痕，同 M-47 家族 | 待修（低优） |
| AUD-5 | P3 | 待办标记 | 全后端 .py | TODO/FIXME **0 处**（初扫 8 处命中经复核均为编码格式串 `UNR/RECYCLE/OUT-YYYYMMDD-XXXXXX` 的 XXXXXX 字面量，非待办标记；自审阶段订正） | 已确认（零残留） |
| AUD-6 | P3 | 异常吞没 | `apps/assetmanagement/migrations/0010_migrate_paid_record_to_json.py:97-98`、`apps/notification/consumer.py:136-137` | 类型化 `except (json.JSONDecodeError, TypeError): pass`（一次性数据迁移）/ `except asyncio.CancelledError: pass`（asyncio 惯例）——语义合理 | 不采纳（语义合理） |

**无 P0 / P1 / P2 条目。**

## §三 分域结论与修复建议

| 分域 | 结论 | 证据 |
|:---|:---|:---|
| 资产状态机 | **健康**。外部旁路 0 处（services/views/selectors/models 全扫，仅 filter/字段声明）；state_machine 内部 9 处直写全部有前置守卫且 3 处为已声明例外 | 探索 agent A 全量扫描 + transitions.py docstring 声明 |
| 合同状态机 | **健康**。`contract_status =` 直接赋值仅 FSM 自身 :79 一处；业务侧经 `ContractFSM.transition` 单闸（contract_service.py:343-345 转 AppValidationError） | 探索 agent B |
| 响应契约 | **健康**。生产代码绕过 success_response 直返 0 处（唯一 grep 命中为注释文本）；分页统一经 CustomPageNumberPagination 包装 | 探索 agent B |
| 跨端契约 4 项 | **全部一致**：① 根 `{code,message,data}` 前端 `src/api/request.ts:586-592` unwrapResponse 严格 code!==0 即抛；② 8 状态键前后端逐一相同（asset.ts:45-54 = transitions.py 8 态 = outasset.ts:48-57）；③ 分页仅 `page_size` snake_case 传后端（UI camelCase 有显式转换，createEntityStore.ts:157-159）；④ 日期 ISO-8601，USE_TZ=True + Asia/Shanghai，前端 Format.ts:84-88 明确规避 UTC 偏移 | 探索 agent B/C + 本地 settings 实读 |
| 鉴权 | **健康**。JWT 双通道 + cookie 通道强制 CSRF + ROTATE/BLACKLIST + 登录限流（M-48 复合键）+ token 黑名单；生产 settings：DEBUG=False、SECRET_KEY env 强制缺失即拒启、<20 字符/已知弱键拒绝（production.py:10-32）、ALLOWED_HOSTS 缺失抛异常 | 探索 agent D + production.py 实读 |
| 操作日志/批量导入 | **健康**（AUD-3 口径差异留痕）。批量链 ensure_batch_size + 逐条事务 + fail_items 分类回执；上传面为零（无 request.FILES/FileField），10MB 上限仅约束 JSON 体积 | 探索 agent D |
| 安全红线 | SC-1 密钥硬编码后端 0 / 前端 0 命中；SC-3 原生 SQL 0 命中；SC-5/6 上传面 0（无端点即无风险面）；OC-6 `/health`（urls.py:54，DB+Redis 探测，503 语义）+ `/ready`（:98）齐备；SC-8 沿 CI security-scan 权威（DRF 已清，twisted 5 项待 26.10.0） | 本地 rg 实测 |

### 修复建议（P3，低优，可交修复 skill 直接接手）

1. **AUD-1**：`state_machine/transitions.py:9-10` docstring 行号订正为 `:56/:89/:128`；验证：rg 比对实际赋值行。影响面小（纯注释）。
2. **AUD-2**：`types/outasset.ts:30-34` 注释补 `reissue`；验证：`npx vue-tsc --noEmit` 无影响，纯注释。
3. **AUD-4**：`views/_mixins.py:33` 补 `logger.debug`（对齐 M-47 三行范式：import+getLogger+调用，caplog 用例同款）；验证：`pytest apps/assetmanagement/ -k mixin` + cov 不回退。

### 上线判定

**可部署（无新增阻断项）**。Merge-audit 五批（K/L①②/M/N/O）已全部落地并 CI 直证（Pipeline 40466576631 四 workflow 全绿，backend-mutation 83.59% 过双门禁）；本次审计**未发现新 P0/P1/P2**。遗留项不变：twisted 5 项 CVE 待 26.10.0 正式版（唯一安全阻断，现仅 rc1 不入生产 ASGI 链路）；P3 三条建议不阻断。

## 评审结论

- 证据可回查：台账 6 条均有 file:line 与命令/扫描出处；4 域探索为只读 agent 实测。
- 置信度：状态机旁路、契约 4 项、SC-1/3/5/6 为全量扫描直证（≥80）；AUD-3/AUD-4 为语义判读，置信度 80-85。
- 局限：竞态类问题仅覆盖审计留痕过的热点（分页回滚 BF-150、锁冲突 locks.py）；未做渗透级测试；SC-8 以 CI 为权威（本机 pip-audit 未装，留痕）。
