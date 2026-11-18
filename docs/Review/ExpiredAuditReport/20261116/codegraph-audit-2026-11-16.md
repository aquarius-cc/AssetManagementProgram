# 上线前全库审计报告（codegraph-audit-2026-11-16）

> 审计模式：只读审计，不改业务代码。修复移交 `bug-surgical-fix` / `rigorous-dev`。
> 审计基线：仓库根 `D:/CodeDemo/AssetManagementProgram`，后端子模块 `de115651`、前端子模块 `e3faff22`（均 heads/master）。
> 规范基线：根 `AGENTS.md` v3.7.8、`backend-business-rules.md` v1.27、`backend-testing-rules.md` v1.10、
> `frontend-business-rules.md` v1.8、`frontend-testing-rules.md` v1.10、两端子引擎 `AGENTS.md`。

## §一 项目上下文（阶段 1）

### 1.1 结构与规模

- 图谱：`codegraph status` = up to date，1,159 文件 / 19,952 节点 / 46,496 边（python 524、typescript 490、vue 122）。
- 后端：Django 6 + DRF + Channels，五层分层（Model/Selector/Service/Serializer/View），`apps/` 下
  `assetmanagement`（资产管理，状态机核心）、`usermanagement`（部门/员工/RBAC）、`authusermanagement`（认证）、
  `unregisteredasset`（未登记资产）、`notification`（通知 + WebSocket），公共能力收敛在 `core/`。
- 前端：Vue 3 + Pinia + Vue Router 4 + Element Plus + ECharts，`src/api`（请求层与缓存）、`src/stores`、
  `src/composables`、`src/views`、`src/components`。
- 本次不重复前序两份同日报告的结论（`glm5.3-flash-*`、`MiMo-V2.6-Pro+*`），只登记本次独立复核出的增量项。

### 1.2 实测基线（本机，2026-11-16）

| 门禁 | 命令 | 结果 |
|:--|:--|:--|
| 后端单测 | `python -m pytest --cov=. --cov-report=term-missing:skip-covered -q` | **2455 passed**，总覆盖率 **90.51%**（约 17 分钟） |
| 状态机专项 | `pytest apps/assetmanagement/tests/test_state_machine.py` | **71 passed** |
| 类型检查 | `python -m mypy . --strict` | **0 error**（231 源文件；mypy 2.1.0 / django-stubs 6.1.0 / drf-stubs 3.18.0 / types-channels 4.3.0，与 `requirements/dev.txt` 一致） |
| Lint | `python -m ruff check .` | 0 命中 |
| 复杂度 | `ruff check . --select C90 --config lint.mccabe.max-complexity=10` | 0 命中 |
| 文件/函数规模 | `check_file_length_guard.py --print` / `check_function_length_guard.py --print` | EXIT=0 |
| 前端三项 | `npm run type-check` / `lint:ci` / `format:check` | EXIT=0 |
| 前端测试 | `npm run test:coverage` | **274 文件 / 2711 用例全通过**，EXIT=0（stores 96.82% / api 91.32% / utils 94.81% / composables 95.94%） |
| 依赖漏洞 | `npm audit --audit-level=high --omit=dev` | **0 vulnerabilities** |
| 依赖漏洞（后端） | `pip-audit` | **未执行**：本机未安装，以 CI `security-scan.yml` 为权威门禁 |
| 重复代码/CI 编排护栏 | `check_duplicate_invariants.py` / `check_ci_orchestration.py` | EXIT=0 |

> 按 CT-7：本机覆盖率数字只作讨论中间量，**CI run 的 `$GITHUB_STEP_SUMMARY` 才是权威基线**。

### 1.3 图谱外取证（构建产物实验）

为验证生产构建行为，使用 `npx vite build --outDir dist-audit`（临时目录，验证后已删除，未改源码）。
关键观测：`dist-audit/index.html` 首屏 `modulepreload` 包含 `echarts`（606.7KB，gzip 206.8KB）；
入口 chunk 直接 `import ... from "./echarts-*.js"`；日志工具 `emit()` 在产物中只剩
`JSON.stringify(...)`，console 落点已被 terser 的 `drop_console` 删除。

## §二 问题台账（阶段 2/3）

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 影响面 | 优先级 | 建议验证方式 | 状态 |
|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|:--|
| FE-01 | P2 | 可观测性（OC-2/OC-3） | `vue-assetmanagement/src/utils/logger.ts:69-76`、`vue-assetmanagement/vite.config.ts:183-188`、`vue-assetmanagement/src/main.ts:29-41` | `emit` / `logError` / `createProxyQuietLogger` | 全仓前端日志唯一出口是 `console.error/warn/info`，而生产构建启用 `minify: terser` + `compress.drop_console: true`，产物中日志被整体删除（已实测：`emit` 只保留 `JSON.stringify`，无任何 sink）；同时 `main.ts` 未注册 `app.config.errorHandler`、未监听 `unhandledrejection`/`window.onerror`。结果是**生产环境前端零诊断信息**，白屏/交互异常无法定位。 | ① 日志加持久 sink（`navigator.sendBeacon('/api/v1/client-logs/')` 或 Sentry），或对 logger 模块排除 `drop_console`（`pure_funcs` 白名单）；② `main.ts` 注册 `app.config.errorHandler` 与 `window.addEventListener('unhandledrejection')`，统一转 `logError`；③ 补一条“产物中仍存在 sink”的构建期断言。 | `codegraph node emit`；`codegraph callers logError` | 全部前端页面与全局异常路径；排障能力 | 高（批次 A） | 构建后 `rg -c "console\\." dist/assets/js`，确认仅剩第三方；新增 logger/errorHandler 单测 | 已确认 |
| FE-02 | P2 | 安全/会话隔离 | `vue-assetmanagement/src/api/request.ts:86,500-508,568-576`、`src/api/assetType.ts:52`、`src/api/contract.ts:74`、`src/api/lostAsset.ts:48`、`src/api/storage.ts:53`、`src/stores/auth.ts:60-79` | `MemoryCache` / `buildCacheKey` / `resetAuthState` | 请求层缓存键仅由 `url + querystring` 构成，**不含用户身份**；4 个详情端点启用 `useCache`（TTL 5 分钟），命中发生在发请求之前。`resetAuthState()`（登出/静默登出共用）清 token、清 localStorage、重置 trace_id，但**未清该缓存**。同一标签页 A 退出、B 登录后，B 访问同一详情 URL 会直接拿到 A 的缓存响应，绕过服务端权限判定（含部门数据范围）。 | 导出 `clearAllCache()`（`MemoryCache.clear()`，epoch 自增）并在 `resetAuthState()` 调用；更稳的做法是把角色 + 部门编码并入缓存键，双保险。 | `codegraph node resetAuthState`；`codegraph node MemoryCache` | 4 个详情端点；共享终端/换号场景的数据隔离 | 高（批次 A） | 单测：写入缓存 → `resetAuthState()` → 同 key 读应为 miss；换用户后详情请求必须打到服务端 | 已确认 |
| BE-01 | P2 | 可观测性（OC-4 运维面） | `asset_management_backend/core/prometheus_middleware.py:28-41,56`、`apps/assetmanagement/urls.py:81-82`、`core/audit_log_urls.py:26-31` | `_normalize_path` / `PrometheusMiddleware.__call__` | 指标标签 `endpoint` 由 `request.path` 经正则归一化后得出，但规则只覆盖 UUID 与纯数字段。`<str:asset_code>`、`<str:recordcode>`、`<str:operator_jobcode>`、`<str:logging_id>` 等路径参数（`recordcode` 形如 `PREFIX-YYYYMMDD-XXXXXXXX`）不会被归一化，**每条记录/每个工号生成一组独立时序**，Prometheus 内存随时间线性增长，违背该中间件注释声明的“防高基数”目标。 | 用 `request.resolver_match.route`（如 `/api/v1/assets/assets/<str:asset_code>/history/`）作为 `endpoint` 标签，或补充“非数字/非 UUID 段一律 `{param}`”的兜底替换；为标签集合加护栏断言。 | `codegraph node _normalize_path`；`codegraph callers PrometheusMiddleware` | 所有按业务编码取详情的端点；监控栈稳定性 | 中（批次 A） | 中间件单测：传入 asset_code 路径，断言 label 为模板串；或抓取 `/metrics/` 检查 `endpoint` 取值集合 | 已确认 |
| BE-02 | P3 | 安全日志（OC-3） | `asset_management_backend/core/exception_handler.py:95,100` | `_handle_unhandled_exception` | `IntegrityError` 分支 `logger.warning(f"数据库完整性冲突: {exc}", exc_info=True)`，未处理异常分支 `logger.error(f"未处理异常: {type(exc).__name__}: {exc}", exc_info=True)`。PostgreSQL 的 `IntegrityError` 文本常带 `DETAIL: Key (col)=(value)`，会把业务值写进日志；`exc_info` 还会带出调用栈中的局部变量痕迹。与本仓 `audit_failure.py` 既有“只记类型”的口径不一致（同型问题前序报告 BE-6 已在 `notification/helpers.py` 登记）。 | DB 类异常改为只记 `exception_type` + `trace_id`（保留 Sentry 事件，取消日志 `exc_info`）；非 DB 的未知异常可保留堆栈，但去掉 `str(exc)`。 | `codegraph node _handle_unhandled_exception` | 全部 API 的错误出口 | 中（批次 B） | 构造唯一约束冲突，断言日志行仅含类型与 trace_id、不含字段值 | 已确认 |
| FE-03 | P3 | 性能（首屏） | `vue-assetmanagement/vite.config.ts:196-205` | `manualChunks` | `manualChunks` 把 echarts/zrender/vue-echarts 划为 `echarts` chunk，但打包结果是 Vue 运行时也被并入该 chunk，入口因此静态依赖它；`index.html` 首屏预加载 echarts（606.7KB / gzip 206.8KB）。合计首屏 JS 约 1.28MB（gzip 约 420KB），仅用于内网/移动扫码也会为图表买单。 | 图表组件改 `defineAsyncComponent`（或把 `plugins/echarts` 下沉到 Dashboard 路由 chunk）；在 `manualChunks` 中显式把 `node_modules/vue`、`node_modules/@vue` 固定到 `vendor`，避免其被并入大 chunk。 | `codegraph node manualChunks` | 全部页面首屏；移动端扫码页最明显 | 中（批次 B） | 重新构建后检查 `index.html` 的 `modulepreload` 不再含 echarts；记录首屏 gzip 体积前后值 | 已确认 |
| BE-03 | P3 | 正确性（时区） | `apps/assetmanagement/selectors/dashboard_selector.py:309`、`apps/assetmanagement/selectors/out_asset_selector.py:145` | `get_expiring_assets` / 出库年限阈值 | 项目 `TIME_ZONE="Asia/Shanghai"`、`USE_TZ=True`，但 `Dockerfile` 与 compose 均未设置 `TZ`，容器进程时区通常为 UTC；`date.today()` 取的是**进程本地日期**。每天 00:00–08:00（CST）区间，“今天”会退回前一天，导致保修到期列表的 `days_until_expire` 与 30 天窗口偏一天。 | 统一改用 `django.utils.timezone.localdate()`；或在镜像显式 `ENV TZ=Asia/Shanghai` 并 `tzdata`（二者取其一，前者更稳）。 | `codegraph node get_expiring_assets` | 首页“即将到期”统计；出库年限判定 | 低（批次 C） | 将进程 TZ 固定为 UTC，冻结时间为 CST 00:30，断言窗口按 Asia/Shanghai 的当天计算 | 已确认 |
| BE-04 | P3 | 安全加固（CSP） | `asset_management_backend/core/csp_middleware.py:20-27` | `_DEFAULT_CSP` | 生产 CSP 为 `script-src 'self' 'unsafe-eval'`、`connect-src 'self' ws: wss:`。全仓 `src/` 无 `eval` / `new Function`（Vue 模板已预编译），`unsafe-eval` 无必要却会放大 XSS 后果；`ws:` 放行任意 WebSocket 主机。 | 移除 `'unsafe-eval'`；`connect-src` 收敛为 `'self'` + 明确 `wss://<部署域名>`；先以 Report-Only 观察一周再强制执行。 | `codegraph node _build_csp_header` | 全部响应；CSP 防护强度 | 低（批次 C） | 生产构建加载全站，控制台无 CSP 违规；`rg "eval\\(|new Function" src` 保持 0 命中 | 已确认 |
| BE-05 | P2 | 逻辑缺陷（低概率可达） | `apps/assetmanagement/services/asset_lifecycle_mixin.py:97-98`（对照 `:42-44`） | `_run_lifecycle_transition` | 幂等分支在“状态已是目标状态、但历史记录缺失”时直接 `return record_model.objects.create(...)`，**未 `refresh_from_db()`**。`broken_date`/`lost_date` 是 `DateField(default=timezone.now)`，内存实例携带 `datetime`；创建响应会用 `BrokenAssetCreateSerializer`/`LostAssetCreateSerializer` 回序列化该记录，而 DRF `DateField.to_representation` 对 `datetime` 直接 `assert` 失败（已核对 `rest_framework/fields.py` 源码）。正常路径正是为此补了 `record.refresh_from_db()`（`:43-44` 注释），补建分支漏了同一动作 → 该分支抛 500。现有测试未覆盖此分支。 | 补建分支返回前同样 `refresh_from_db()`（或显式以 `timezone.localdate()` 构造日期字段）；补一条“状态已为目标、记录缺失 → 创建返回 201”的回归用例。 | `codegraph node _run_lifecycle_transition`；`codegraph callers mark_asset_broken` | 损坏/遗失登记的幂等补建路径；批量子项失败会拖累整单提示 | 高（批次 A） | 新增回归：资产状态置 `broken` 且无记录 → POST 创建，断言 201 且 `broken_date` 为 `YYYY-MM-DD` | 已确认 |

### 2.1 已知设计确认（复核后不列问题）

| 项 | 结论 | 依据 |
|:--|:--|:--|
| WebSocket JWT 经 `Sec-WebSocket-Protocol` 传递 | 沿用既有 H-1 设计；token 不落 URL/访问日志。若需进一步降险，可让客户端多 offer 一个 `jwt` 占位协议，避免代理看到真实 token | `src/composables/useNotificationConnection.ts:108`、`apps/notification/consumer.py` |
| token 本地存储为 XOR 混淆 | 代码与文档均声明“非加密”，仅为防随意查看；构建产物可还原密钥属预期，不应作为加密能力对外承诺 | `src/utils/tokenObfuscator.ts:18-50` |
| 公开扫码接口可枚举 | `recordcode = 前缀-YYYYMMDD-8位十六进制`（`core/models.py:28`），随机空间 16^8；另有 20 次/分匿名限流，枚举不可行 | `apps/assetmanagement/urls.py:98`、`core/models.py:28` |
| 状态流转并发安全 | 关键 Service 均为 `@transaction.atomic` + `select_for_update`（出库/回收/损坏/维修/生命周期） | `out_asset_service.py:171,237,260,338`、`damaged_asset_service.py:47,177,285,356`、`asset_lifecycle_mixin.py:79,214` |
| 列表 N+1 | 列表 Selector 均带 `select_related`（资产主表聚合 3 个外键） | `asset_selector.py:185,210,244,282,408` |
| 金额精度 | 合同/资产/维修金额全为 `DecimalField`，未发现 `FloatField` | `models/contract.py:61,64,97,106`、`models/asset.py:114` |
| 导出资源守卫 | 全量导出有 `EXPORT_MAX_ROWS=10000` + `limit/offset` 分批 + 流式响应 | `core/excel_export/streaming.py:39`、`views/operation_log_views.py:152-175` |
| 生产静态/媒体 | `MEDIA`/`STATIC` 仅 `DEBUG=True` 时由 Django 托管，生产由 Nginx 承担 | `config/urls.py` 末尾、`docker/nginx/conf.d/default.conf.tpl:208,222` |
| 安全响应头 | HSTS/`nosniff`/`X-Frame-Options`/`Referrer-Policy`/`Permissions-Policy` 由 Nginx 唯一下发，且代理层 `proxy_hide_header` 防双发；CSP 由 Django 中间件下发，未被隐藏 | `production.py:63-105`、`default.conf.tpl:67-88` |
| 生产配置 fail-closed | `SECRET_KEY`/`ALLOWED_HOSTS`/`DB_PASSWORD`/`REDIS_URL` 缺失即 `ImproperlyConfigured`；弱密钥黑名单 + 长度 ≥20；自助注册默认关闭 | `config/settings/production.py:14-121` |

## §三 分域结论与修复建议（按优先级）

### 批次 A：上线前建议修复（4 项）

1. **FE-01 生产日志保活**：先接 sink 与全局错误处理，再谈性能指标——目前线上前端等于“黑盒”。
2. **FE-02 身份切换清缓存**：一行 `clearAllCache()` 即可堵住跨会话数据串号；顺带把用户维度并入缓存键更稳。
3. **BE-01 指标标签归一**：换用 `resolver_match.route` 后，`/metrics/` 的 `endpoint` 基数从“随记录增长”降为“随路由数”。
4. **BE-05 补建分支补刷新**：与正常路径对齐，消除隐藏 500；同时补回归用例（CT-4）。

### 批次 B：上线后 1–2 周（2 项）

1. **BE-02 异常日志脱敏**：与既有 `audit_failure` 口径统一，避免 DB 业务值进日志。
2. **FE-03 图表懒加载**：先量首屏体积，再拆分 echarts；移动扫码页收益最大。

### 批次 C：卫生项（2 项）

1. **BE-03 时区口径**：`date.today()` → `timezone.localdate()`，并决定容器 TZ 策略。
2. **BE-04 CSP 收紧**：去 `unsafe-eval`、收窄 `connect-src`，Report-Only 观察后再强制执行。

### 上线门禁复核结论

| 检查项 | 结论 | 证据 |
|:--|:--|:--|
| CT-1 核心业务有测试 | 通过 | 2455 用例；状态机专项 71 用例（唯一缺口见 BE-05 补建分支） |
| CT-2 覆盖率 | 通过（口径以 CI 为准） | 后端本机 90.51%；前端分层阈值全过（stores 96.82 / api 91.32 / utils 94.81 / composables 95.94） |
| CT-3 状态机全路径 | 通过 | `test_state_machine.py` 71 passed；过渡表与用例对照无空洞 |
| CT-4 回归屏障 | 部分 | BE-05 属新增缺口，需随修复补用例 |
| CT-5 失败即阻塞 | 通过 | 本机全绿；CI 阻断链完好 |
| CT-6 迁移安全 | 本次无迁移变更 | — |
| CT-7 工具链复核 | 通过 | 版本与 `dev.txt` 一致，mypy/ruff 0 命中；覆盖率权威归 CI |
| 依赖漏洞 | 部分 | 前端 0；后端 `pip-audit` 本机未装，以 CI `security-scan.yml` 为准（**未在本机复核**） |

### 质量自审（阶段 5）

- 台账每条均有 `file:line` 与可复核命令；构建产物体检结论来自实际构建（`dist-audit` 已删除，未污染工作区）。
- 已避开前序两份报告已登记项（状态机兜底日志、通知 `exc_info`、dashboard 内联错误处理等）。
- 未执行项如实标注：后端 `pip-audit`、`mutmut` 未在本机运行；覆盖率权威数字以 CI 为准。
- 规模口径：全部文件/函数检查走 `scripts/` 护栏（逻辑行口径），未使用 `wc -l` 等物理口径。

[可验证] 前端生产日志被删除，依据：`npx vite build --outDir dist-audit` 产物中 `emit()` 仅剩 `JSON.stringify`，无 console 落点；`index.html` 预加载 echarts — 依据：本次构建产物实测。
[可验证] 认证缓存不清空，依据：`src/stores/auth.ts` `resetAuthState()` 无缓存调用，`src/api/request.ts` 缓存键不含用户维度 — 依据：源码直读。
[可验证] Prometheus 标签未归一化 `str` 路径参数，依据：`core/prometheus_middleware.py` 正则仅覆盖 UUID/数字 + 路由表实存 `<str:...>` — 依据：源码直读。
[可验证] 补建分支会触发 DRF `DateField` 断言，依据：`rest_framework/fields.py` 源码 + 模型 `DateField(default=timezone.now)` + 序列化器字段表 — 依据：本机解释器读取源码。
[推测] BE-05 的实际触发概率取决于是否存在“状态已置但记录缺失”的历史数据；本机无生产库，故只判“可达且未覆盖”，不估频次。

[审计票 - 必填项]
- 读取规范：已读 后端/前端 AGENTS & Rules
- CT-1[√] CT-3[√] CT-5[√] CT-7[√] — 核心测试覆盖 / 状态机全路径 / 测试失败阻塞 / 门禁结论已按 dev.txt 工具链复核
- DR-1[√] DR-5[√/豁免] — 业务逻辑唯一实现 / 文件规模（护栏 EXIT=0，无新增超限）
- SC-1[√] SC-3[√] — 密钥硬编码禁止 / SQL 注入防护（未发现字符串拼接 SQL；`raw()/extra()` 无命中，唯一 `cursor.execute` 为 `health_probe.py:32` 的字面量 `SELECT 1`）
- 跨端契约：未破坏
- 红线触发：无
- 建议提交：否（审计报告本身可提交；业务修复需另行评审）

[审计票 - 自检项]
- 测试：CT-2[√] CT-4[x]（BE-05 缺口待补） CT-6[√]（无迁移）
- DRY：DR-2[√] DR-3[√] DR-4[√] DR-6[√]
- 安全：SC-2[√（CI）] SC-4~SC-8[√]（SC-8 后端本机未跑，标 [x] 未执行+原因：pip-audit 未安装）
- 可观测性：OC-1~OC-3[x]（FE-01/BE-02 待修） OC-4[x]（BE-01 高基数） OC-5[~] OC-6[√] OC-7[~]
- AI鲁棒性：AR-1~AR-5[√]
- AI行为：Fact-1[√]（事实基线）
- 写作风格：Style-1~Style-3[√]
- 覆盖率：整体 90.51%（后端本机，≥80%）/ 核心 stores 96.82%（≥90%，前端本机）
