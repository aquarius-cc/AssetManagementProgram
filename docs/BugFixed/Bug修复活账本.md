# Bug 修复活账本

> 唯一事实来源：所有已确认根因并完成修复的 Bug 在此登记。
> 状态：`已关闭` / `待验证` / `降级` / `待核查`
> 登记规则：每条必须包含证据（文件:行号 / 日志原文）、根因、修复方案、验证记录，缺一不予通过审核。

---

## BF-001 【已关闭】开发环境 cookie 通道 token/refresh 返回 403 导致前端误跳登录页

- **发现日期**：2026-XX-XX
- **严重级别**：高（核心登录链路不可用，用户每次页面跳转被踢回登录页）
- **影响范围**：仅开发环境（Vite dev server 代理场景）；生产走 nginx 同源不受影响

### 一、问题现象

1. 前端控制台：`POST http://localhost:5173/api/v1/auth/token/refresh/ 403 (Forbidden)`，调用链 `guards.ts → initAuthState → verifyCookieSession → performRefresh → refreshCookie`
2. 每次点击页面跳转触发路由守卫 → 静默续期失败 → 被重定向回 `/login`
3. 后端日志：`WARNING Forbidden: /api/v1/auth/token/refresh/`

### 二、根因分析

请求链路：浏览器(`localhost:5173`) → Vite 代理 → Django(`127.0.0.1:8000`)

| # | 环节 | 事实 |
|---|------|------|
| 1 | 浏览器 POST 自动携带 `Origin: http://localhost:5173` | 抓包确认 |
| 2 | Vite `changeOrigin: true` 仅改写 Host 头，**不改写 Origin** | vite.config.ts:171-181 |
| 3 | refresh 是唯一的 cookie 通道 + AllowAny 端点，命中 `enforce_csrf_if_cookie_channel` CSRF 兜底 | views.py:389-407 |
| 4 | `enforce_csrf()` 内 CSRFCheck 做 Origin 校验：Origin(5173) ≠ Host(8000)，且项目从未配置 `CSRF_TRUSTED_ORIGINS` | authentication.py:39-49；settings 全量 grep 无该配置 |
| 5 | `PermissionDenied("CSRF Failed: Origin checking failed ...")` → 403 | 响应体实证 |
| 6 | 前端守卫将任何 refresh 失败一律视为会话失效 → 跳转登录页 | auth.ts:159-164, guards.ts:102 |

**关键佐证**：其他 API 不受影响是因为 bearer 通道（带 Authorization 头）被 `enforce_csrf_if_cookie_channel` 显式跳过——只有 cookie 通道的 refresh 踩中此雷。

**排除项**：
- 非 token 过期（无效 token 返回 401，非 403；错误码分布见 views.py:412）
- 非服务未启动（netstat 确认 8000 LISTENING）
- 非 Redis/channel layer 问题（开发环境 InMemoryChannelLayer）

### 三、修复方案

**文件**：`asset_management_backend/config/settings/development.py`

```python
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
```

### 四、安全性论证（对抗审核）

1. **不构成 CSRF 防护降级**：CSRF 校验由两道独立检查构成——Origin 白名单 + X-CSRFToken/cookie 对比。本次仅将已知开发源加入白名单，第二道检查完整保留
2. **恶意源仍被拦截**（实测）：伪造 `Origin: http://evil.example.com` 的请求在修复后依然返回 `Origin checking failed` —— 见验证记录第 2 条
3. **作用域隔离**：仅写入 development.py，production.py 未改动
4. **格式合规**：Django ≥4 要求 origin 带 scheme 且端口精确匹配，未使用通配符

### 五、验证记录

```text
① 配置加载: python -c django.setup()
   → CSRF_TRUSTED_ORIGINS = ['http://localhost:5173', 'http://127.0.0.1:5173'] ✅

② 正向用例: 可信 Origin(http://localhost:5173) + 合法 csrftoken + 匹配 X-CSRFToken
   → enforce_csrf() 通过 ✅（修复前此处抛 "Origin checking failed"）

③ 安全回归用例: 恶意 Origin(http://evil.example.com) + 同样合法 token
   → 仍被拒绝: "CSRF Failed: Origin checking failed - http://evil.example.com
     does not match any trusted origins." ✅（证明无防护回退）

④ 端到端: 待人工执行——重启 runserver 后，浏览器登录 → 点击页面跳转，
   Network 中 refresh 请求应 200 且不再跳转登录页 [待验证]
```

### 六、遗留与关联事项

- **BF-002【待核查】WebSocket 连接失败**（`ws://127.0.0.1:8000/ws/notifications/<jobcode>/`）：
  主因为后端 `consumer.accept()` 未回显前端以 subprotocol 方式传入的 JWT（RFC 6455 要求服务器选择一个子协议应答，否则浏览器掐断连接）；次要因素与本案同源——cookie 按 host 隔离（`localhost` 与 `127.0.0.1` 互不可见）。建议修复时统一为 Vite 代理转发 WS（`/ws` 路径加 `ws: true`），消除双 host 结构
- **改进建议**：前端守卫可区分 403-CSRF 与 401，避免配置类故障被误判为"会话过期"

---

*登记人：ox-alpha ｜ 审核状态：代码级验证通过，端到端验证待人工确认*

---

## BF-002 【待验证】WebSocket 通知连接失败（connection failed / 1006）

- **发现日期**：2026-XX-XX
- **严重级别**：中（实时通知不可用；认证链路本身无缺陷）
- **影响范围**：所有浏览器端 WS 连接（开发与生产同构，均会命中）

### 一、问题现象

1. 前端控制台：`WebSocket connection to 'ws://127.0.0.1:8000/ws/notifications/<jobcode>/' failed`
2. 裸连接对照实验：`close code: 1006`（拿不到应用层关闭码）
3. 后端日志对裸连接显示 `WS rejected: missing token → WebSocket REJECT`，但对真实带 token 连接**无任何日志**

### 二、根因分析

前端将 JWT 放入子协议通道，后端握手响应未回显子协议：

| # | 环节 | 证据 |
|---|------|------|
| 1 | 前端 `new WebSocket(url, [token])` → 发送 `Sec-WebSocket-Protocol: <JWT>` | useNotification.ts:103 |
| 2 | 后端 `await self.accept()` 未传 `subprotocol` 参数 | consumer.py:64（修复前）|
| 3 | Daphne `serverAccept(subprotocol=None)` → 101 响应不含 Sec-WebSocket-Protocol 头 | daphne ws_protocol.py:190,222-226 源码级确认 |
| 4 | RFC 6455 §4.1：客户端请求了子协议而服务器未选择时，浏览器必须判定连接失败 | 浏览器行为实证 |

**双症状同源对照表**：

| 连接方式 | 表象 | 机制 |
|---|---|---|
| 裸连接(无token) | close 1006 + 后端 "missing token" REJECT | Channels 中 accept 前 close() → Daphne `ConnectionDeny(403,"Access denied")`(ws_protocol.py:230-236) 拒绝握手，浏览器无法获取应用层 4401 |
| 真实连接(JWT subprotocol) | connection failed、后端零日志 | 认证成功走到 accept()，但 101 响应缺子协议回显 → **浏览器主动掐断**，应用层无从感知 |

**排除项**：
- 非服务未启动（netstat 8000 LISTENING；curl HTTP 正常）
- 非 Origin 校验（curl 实测匹配/不匹配 Origin 均返回相同 403 Access denied——该 403 即 close-before-accept 的 ConnectionDeny）
- 非路由不匹配（后端日志 HANDSHAKING 路径正确解析）
- 非子协议回显以外的 Daphne 拒绝逻辑（ws_protocol.py:235 为唯一 "Access denied" 触发点）

### 三、修复方案

**文件**：`asset_management_backend/apps/notification/consumer.py:67`

```python
# 修复前
await self.accept()

# 修复后：回显客户端请求的子协议(JWT)，满足 RFC 6455 握手契约
await self.accept(subprotocol=self._extract_token())
```

### 四、安全性论证（对抗审核）

1. **无新增信息泄露**：回显值即客户端自行发送的 token，服务端未引入任何新数据外发通道
2. **认证时序不变**：`accept()` 仅在 `_authenticate()` 通过且 jobcode 匹配之后执行（consumer.py:52-64），4401/4403 拒绝路径完全不受影响
3. **防御性兜底**：`_extract_token()` 理论上在此处必非 None（认证已用同一函数取值），若异常返回 None 则等价于修复前行为（不回显），不会崩溃
4. **前端零改动**：契约保持"JWT 作为唯一子协议"，无跨端契约变更（§3）

### 五、验证记录

```text
① 单元测试全量回归: pytest apps/notification/ -q
   → 33 passed ✅（含 test_ws_consumer.py 13 个用例：4401/4403/心跳/群组推送等）

② 待人工端到端验证 [待验证]：
   - 登录后 Network 中 ws 请求状态应为 101 且响应含 Sec-WebSocket-Protocol 头
   - 后端日志应出现 "WS connected" + INFO WebSocket CONNECT
   - 无 token 连接仍应被拒（403 Access denied / 日志 missing token）
   - 伪造 jobcode 仍应 4403
```

### 六、关联事项

- BF-001（CSRF Origin 白名单）已关闭，与本 bug 相互独立但同属"开发环境双 host 结构"衍生症状；生产环境经 nginx 同源转发不存在本问题的 host 隔离变体

---

*登记人：ox-alpha ｜ 状态：代码级验证通过（33 测试全绿），端到端验证待人工确认*

---

## BF-003 【待验证】备份体系缺口收口（S3 出口 / Redis 归档 / 媒体备份 / 演练定时化）

- **发现日期**：2026-XX-XX（5.5 节审计 → 两轮对抗审核后实施）
- **严重级别**：中（数据安全基础设施；原报告"docker/backup 未提交"结论有误，已修正为三项真实缺口 + 终审新增媒体缺口）

### 一、根因与范围修正

| 原报告声明 | 核实结论 |
|---|---|
| docker/backup/ 未提交 | ❌ 误报：Dockerfile/crontab/backup/verify/restore 脚本均已存在且接入 compose |
| S3 未启用 | ✅ aws CLI 未安装于镜像，`command -v aws` 门控永不命中且静默跳过 |
| Redis 归档缺失 | ✅ 仅靠同宿主机 redis_data 卷，无异地副本 |
| （终审新增）媒体文件零备份 | ✅ media_volume 无任何归档逻辑——数据库恢复后资产图片等引用全部悬空 |

### 二、实施清单（对应两轮对抗审核的最终版）

| # | 变更 | 文件 |
|---|------|------|
| 1 | backup.sh 重构：flock 并发锁(缺失时降级执行) + S3 三分支失败语义(配置即必须成功) + AR-3 三次退避重试 + head-object 尺寸完整性校验 + `postgres/$DATE/` 日期分片 | scripts/backup.sh |
| 2 | 新增 redis_backup.sh：redis-cli --rdb 远程快照 + 魔数校验(镜像无 redis-check-rdb 的替代方案) + 保留期清理 + 同一 S3 语义；文档声明 RPO=24h 非关键数据 | scripts/redis_backup.sh |
| 3 | 新增 media_backup.sh：media_volume 只读挂载打包 tar.gz + 同一 S3 语义 | scripts/media_backup.sh |
| 4 | restore_test.sh 开头预清理测试库(dropdb --if-exists)，防上次演练被 kill 残留导致本次失败 | scripts/restore_test.sh:24 |
| 5 | Dockerfile 加装 aws-cli + 纳入新脚本 | docker/backup/Dockerfile |
| 6 | crontab 扩展：2:00 pg / 2:30 redis / 3:00 media / 周日 3:30 verify / 季度首日 4:00 restore drill | docker/backup/crontab |
| 7 | compose backup 服务扩展：S3 凭据注入(可选不强制)、redis 依赖、4 个新卷(含报告持久化)、media 只读挂载 | docker-compose.yml |
| 8 | .env.example 补 S3 占位符 + 90 天轮换提示 | .env.example |

### 三、安全性论证

1. **SC-1 合规**：AWS 凭据仅经 .env/compose 注入，`.env.example` 为占位符；实测 `.env` 已被 gitignore 且未被跟踪
2. **最小权限**：media_volume 以 `:ro` 挂载，备份容器无写权限
3. **失败语义**：配置了 S3 即"必须成功"，失败 exit 1 进入容器日志可接告警；未配置则本地保留不误伤开发环境
4. **加密决策记录**：dump 含员工个人信息，建议生产启用 S3 服务端加密(SSE-S3/KMS)；客户端 gpg 方案成本高收益相同，暂缓——如合规另有要求再立项
5. **已知边界**：AWS CLI 无原生限速参数(二审建议中的 timeout 参数系超时非限速)，成本控制依赖 STANDARD_IA + 生命周期策略(部署 bucket 时人工配置)

### 四、验证记录

```text
① shell 语法: bash -n 全部 4 个脚本通过 ✅
② compose 结构: yaml 解析通过，6 services / 10 volumes 无重复定义 ✅
③ 魔数校验双向: 合法 RDB 头通过 / 非法文件被拒 ✅
④ flock 缺失降级: 无 flock 环境下脚本继续执行(宁重复勿漏备) ✅
⑤ 失败语义: pg_dump 连接失败正常报错退出; media 目录缺失明确报错 ✅
⑥ 密钥不入库: .env 被 gitignore 且未跟踪 ✅
⑦ 待人工端到端 [待验证]:
   - 构建镜像 → docker exec 触发 backup.sh → 本地 dump + (配 S3 后)上传成功
   - aws s3api head-object 尺寸一致
   - redis_backup.sh 在 Redis 认证开启后凭 REDIS_PASSWORD 正常拉取
   - 季度演练 cron 触发生成 Markdown 报告且 ASSET_COUNT>0
```

### 五、遗留事项

- 告警闭环(BF-003 Step 4)：node_exporter 当前未部署(monitoring 栈仅 prometheus/grafana/pg-exporter/redis-exporter/alertmanager)，textfile 方案需先加装；短期以容器日志 + exit code 为准，告警去重(状态变化才发)随告警通道一并实施
- S3 bucket 生命周期策略(30d→IA / 90d 删除)需在 AWS 控制台配置，无法代码化于本仓库

---

*登记人：ox-alpha ｜ 状态：静态+降级验证通过，Docker 环境端到端验证待人工确认*

---

## BF-004 【待验证】前端 vendor 巨型 chunk 拆分 + 预压缩产物启用

- **发现日期**：2026-XX-XX（6.1 节审计；原报告 G-4 "nginx 未配置 gzip" 经核实为误报，真实问题为两项）
- **严重级别**：低-中（性能优化，非功能缺陷）

### 一、根因

| # | 问题 | 证据 |
|---|------|------|
| 1 | manualChunks 将全部 node_modules 打入单一 vendor chunk | vite.config.ts（修复前）；实测 vendor=2532KB |
| 2 | 构建期已生成 .gz/.br 预压缩文件(vite-plugin-compression)，但 nginx 未启用 `gzip_static`——预压缩产物为死重，运行时实时压缩浪费 CPU | dist/assets/js/*.gz 实测 24 个；nginx.conf grep gzip_static 零命中 |

### 二、修复内容

| # | 变更 | 文件 |
|---|------|------|
| 1 | manualChunks 按域拆分：echarts+zrender+vue-echarts → `echarts`；exceljs → `exceljs`；element-plus+@element-plus → `element-plus`；其余 → `vendor` | vue-assetmanagement/vite.config.ts |
| 2 | nginx http 块追加 `gzip_static on`：优先下发同名 .gz，无 .gz 回落运行时 gzip | asset_management_backend/docker/nginx/nginx.conf:46 |

### 三、构建实测结果

```text
vendor:      2532KB → 80KB   (-96.8%)
index(入口): 36KB（不含任何重库代码）
echarts:     604KB（独立 chunk, 仅进入仪表盘路由时加载）
exceljs:    1036KB（独立 chunk, 仅导入/导出功能时加载）
element-plus:552KB（独立 chunk, 含图标）
入口链路断言: index chunk 中 zrender/exceljs/element-plus 特征代码零命中
  （grep 命中的 "exceljs" 字符串经溯源为 modulepreload 清单 URL, 非库代码）
预压缩: 24 个 .gz 与 js 同 hash 命名, gzip_static 可直接命中
```

### 四、安全性论证与已知边界

1. **无跨端契约影响**：仅构建分块策略与传输层优化，业务逻辑零改动
2. **zrender 同 chunk 约束已满足**：避免 echarts 初始化顺序/循环依赖事故（对抗审核要点①）
3. **Brotli 边界声明**：`.br` 文件已生成但 nginx:1.27-alpine 不含 ngx_brotli 模块，暂无消费方；换镜像或加模块后零成本激活，不在本期范围
4. **exceljs eval() 定性留痕**：库内部实现、非注入风险；当前 CSP 为 `script-src 'self' 'unsafe-eval'`(生产响应头实测)，与之兼容；未来若收紧 CSP 需重新评估
5. **G-4 评级修正记录**："nginx 未配置 gzip"不成立(运行时 gzip 已配置且生效)；改判为"静态预压缩未启用"并已修复

### 五、待人工端到端验证 [待验证]

- 浏览器 Network: 首屏 JS 总传输量应 <300KB(gzip 后)；进入仪表盘才下载 echarts chunk
- 功能冒烟: 登录 → 仪表盘图表渲染 → Excel 导入导出 → 全站表单交互(element-plus)
- build 日志无 Circular dependency 警告 ✅（本次构建输出已确认）

---

*登记人：ox-alpha ｜ 状态：构建级验证通过，浏览器端到端待人工确认*

---

## BF-005 【待验证】发布与回滚体系（迁移不可逆治理 / CD 流水线复活 / 镜像保留）

- **发现日期**：2026-XX-XX（6.5 节审计 → 对抗审核修正后实施）
- **严重级别**：中

### 一、根因修正记录（两轮审核的关键发现）

| 原判断 | 精确复查后的真相 |
|---|---|
| "3 处 RunPython.noop 不可逆点"(0009/0010/notification0002) | ❌ 仅 **1 处**(notification/0002)；assetmanagement 0009 operations 已剥离为空、0010 含完整 backward 函数——初判 grep 归因错误，对抗审核纠偏 |
| "CI 推送双标签致镜像无限累积" | ⚠️ 前提存疑：原 ci-cd.yml 位于 `asset_management_backend/.github/workflows/`，GitHub 只识别仓库根 `.github/`——**该流水线从未运行过** |
| "在 staging 做回滚演练" | ❌ deploy-staging 为 echo 占位，staging 从未存在 |

### 二、实施清单

| # | 变更 | 文件 |
|---|------|------|
| 1 | notification/0002 添加 ROLLBACK_NOOP_REASON 标记 | apps/notification/migrations/0002_*.py |
| 2 | migration-check.yml 新增步骤④：新增迁移含 noop 反向且无标记 → **硬门禁 fail**（机器可判，替代脆弱的 PR 描述解析） | .github/workflows/migration-check.yml |
| 3 | ci-cd.yml 迁移至根 workflows 并重构：剥离与 ci.yml 重复的 lint/test/security(由 ci.yml 与 security-scan.yml 承担)，仅保留 docker build/push；触发分支 main→master 对齐 | .github/workflows/ci-cd.yml |
| 4 | 新增 prune-images job：Docker Hub API v2，保留最近 5 个 sha + latest 永不删 + PROD_IMAGE_SHA repo variable 排除(保证回滚有镜像) | 同上 |
| 5 | 回滚 SOP：标准流程(备份前置/migrate 下界/--plan 预览//health 断言)、回滚下界表、蓝绿暂缓决策、演练延后决策 | docs/RollbackSOP.md |
| 6 | 删除嵌套死配置 asset_management_backend/.github/ | 已删除 |

### 三、安全性论证

1. **prune 不危及回滚**：latest + PROD_IMAGE_SHA 双排除，任何时刻保留 ≥"当前+前一版"两个镜像
2. **noop 门禁为增量约束**：只检查 PR 变更的迁移文件，存量不受影响；标记注释机制使理由留痕于代码旁(优于 PR 描述解析)
3. **token 权限边界**：DOCKERHUB_TOKEN 需 Read & Delete 权限已在 workflow 头部注释与 SOP §6 显式声明
4. **内嵌脚本已实测**：prune 的过滤逻辑(python3 -c)以模拟 JSON 数据验证通过(latest/生产sha 排除、普通 sha 保留)

### 四、验证记录

```text
① notification/0002 语法: ast.parse 通过 ✅
② migration-check.yml YAML 解析通过 ✅
③ ci-cd.yml YAML 解析通过, jobs=[docker, prune-images] ✅
   (实施中拦截并修复: 内嵌 python 顶格行破坏 YAML 块标量)
④ prune 过滤逻辑: 模拟 Docker Hub API 响应实测, 输出符合预期 ✅
⑤ makemigrations --dry-run: 无遗漏迁移 ✅
⑥ 待人工验证 [待验证]:
   - DOCKERHUB_TOKEN 更新为 Read & Delete 权限
   - 手动 workflow_dispatch 触发, 确认 build/push/prune 全链路
   - repo variables 配置 PROD_IMAGE_SHA(首次部署后)
```

### 五、遗留事项

- 回滚演练延后至 staging 落地或 CI 无状态演练方案立项(RollbackSOP.md §4 决策记录)
- deploy-staging 未在新 ci-cd.yml 中注册——真实部署方案确定后补充

---

*登记人：ox-alpha ｜ 状态：静态验证全过，CI 实跑待人工确认*

---

## BF-006 【已关闭】取消报废一律回 recycled_pending，丢失申请前状态

- **发现日期**：2026-09-12（R3-07 评估 → 方案评审 → 实施与对抗审核）
- **严重级别**：中（取消报废后资产状态与申请前不一致，需人工纠偏；与审批拒绝（v1.5 修正）语义割裂）
- **影响范围**：`DamagedAssetService.cancel_asset_recordcode` 单条与批量取消路径；无 API 契约变更（URL/参数/响应结构不变，仅内部回退目标变化）

### 一、问题现象

1. 用户取消待报废申请后，资产一律变为 `recycled_pending`，即使申请前是 `broken/lost/in_use/repairing`
2. 对照组：审批拒绝（`reject_to_original`，v1.5 起已按 `original_status` 回退）与取消行为不一致

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | FSM 层硬编码回退目标 | `scrapping.py` 旧版 `cancel_damaged` 直接赋值 `RECYCLED_PENDING`，未消费 `DamagedAsset.original_status` |
| 2 | 技术设计文档旧约定背书了错误行为 | `03-业务规则与状态机.md` 旧版明写 `cancel_damaged: damaged → recycled_pending` |
| 3 | 服务层未传参 | `damaged_asset_service.py` 调 `cancel_damaged(asset)`，丢弃了记录上的 `original_status` |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | `cancel_damaged` 签名加 `original_status: str \| None = None`，回退逻辑与 `reject_to_original` 同构（`_REJECT_TARGETS` 白名单 + 缺失/非法兜底 `recycled_pending`） | `state_machine/scrapping.py` |
| 2 | 服务层传入 `original_status=damaged_asset.original_status`（在软删后读取——`delete()` 为软删，字段可靠；**保留** `select_for_update` 行锁） | `services/damaged_asset_service.py` |
| 3 | 批量取消零改动：经 `_delete_one` → `cancel_asset_recordcode` 委托自动继承新语义 | 同上（未改动） |
| 4 | 代码内文档同步：`constants.py:10` 流转图注释、`transitions.py` 业务规则注释 | `state_machine/` |
| 5 | 文档同步：状态机规则表补 cancel 行、特殊回退操作表加"取消报废"行、业务约束新增第 6 条、ASCII 图补 cancel 分支、版本 v1.11+变更日志；技术设计 03 文档表行拆分与示例代码修正 | `Rules_Fiels/backend-business-rules.md` 等 |

### 四、对抗审核结论

未发现阻断性缺陷。审核发现并已修复 2 处文档/注释一致性残留（D1：`transitions.py` cancel 注释未同步；D2：技术设计 03 文档示例代码 `TRANSITIONS` 缺 `in_use/repairing` 目标、`_REJECT_TARGETS` 未定义、前置校验写法与实现语义相反）。记录 2 处预存在技术债（D3：cancel/reject 路径未将 `InvalidTransitionError` 转 `AppValidationError`，脏数据单条取消会 500；D4：软删 + OneToOne 唯一约束导致取消后同资产重新申请报废会 IntegrityError）——均非本次引入，另行立项。

### 五、验证记录

```text
① 状态机+服务层目标测试: 68 passed（含新增 TestCancelDamaged 10 例：5 原状态参数化
   + None/in_store/scrapped/unknown_x 兜底参数化 + 非 damaged 抛错；服务层
   test_cancel_success 改断言 in_use + 批量继承用例 broken→broken+success_count） ✅
② 全量回归: apps/assetmanagement/tests/ 分两块 377+249 = 626 passed, 0 failed ✅
③ ruff/mypy: 项目 .venv 未安装（No module named ruff/mypy），未执行——工具缺口登记
④ 调用点核查: cancel_damaged 全仓仅 3 处引用（定义/服务层唯一生产调用点/测试），无漏传 ✅
```

### 六、遗留与关联事项

- **D3（技术债）**：cancel/reject 路径建议统一 `except InvalidTransitionError → AppValidationError(INVALID_STATE_TRANSITION)`（对齐 `create_damaged_asset:53-54`）
- **D4（技术债）**：`DamagedAsset.asset_recordcode` OneToOne 软删后唯一索引仍占用，重新申请会 IntegrityError；建议 partial unique index `WHERE is_deleted = false` 或复用软删行
- 需求文档 01/07 无"取消报废"验收条目；本修复依据技术设计文档 03 旧约定修正 + 业务约束第 6 条（新增产品决策），已在 `backend-business-rules.md` v1.11 变更日志注明

---

*登记人：AtomCode ｜ 状态：目标测试+全量回归通过，代码级验证完成*

---

## BF-007 【已关闭】通用审计日志端点越权：普通用户可读全系统 before/after 快照（审查报告 BE-04）

- **发现日期**：2026-09-13（《审查报告_2026-09-13_AtomCode.md》BE-04）
- **严重级别**：P2 中-高（越权读取审计数据，含变更前后完整快照）
- **影响范围**：`core/audit_log_views.py` 通用审计日志 6 个只读端点；无 API 契约变更（URL/参数/响应结构不变，仅角色拦截收紧）

### 一、问题现象

1. 普通 regular 用户 `GET /api/v1/audit-logs/` 返回 200，可拉取全系统审计明细
2. `before_data/after_data`（变更前后完整快照，含员工姓名等敏感字段）对任意普通用户开放

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 6 个通用审计端点 `permission_classes = [IsAuthenticated]`，只校验登录态 | `core/audit_log_views.py:80`（及 211/243/284/335/383） |
| 2 | `IsAuditorOrAdmin` 类 docstring 明确"审计日志查看(全部数据)"应使用它 | `core/permissions.py:124-135` |
| 3 | 权限面与设计意图不符 → 普通用户越权读全系统审计快照 | 对照 permissions 文档与视图声明 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | 6 个端点 `permission_classes` 统一 `[IsAuthenticated]` → `[IsAuditorOrAdmin]` | `core/audit_log_views.py:80/211/243/284/335/383` |
| 2 | 清理未使用 `IsAuthenticated` import | 同上 |
| 3 | 测试重构为角色化权限矩阵：regular 403 / auditor + system_admin 200，6 端点 × 3 角色全覆盖；业务行为用例（过滤参数校验/404/分页/日期解析）改以审计员视角验证 | `core/tests/test_audit_log_api.py` |

### 四、对抗审核

1. **路由全覆盖**：`core/audit_log_urls.py` 6 条路由逐一对应 6 个视图，全部收紧，无漏网
2. **无越权残留**：grep 全视图 `permission_classes` 6/6 = `[IsAuditorOrAdmin]`，零 `[IsAuthenticated]` 残留；import 已清除
3. **域隔离正确**：BE-03 资产操作日志（`operation_log_views.py`）保持 `IsAuthenticated`——普通用户查自己的操作记录走该域，不属本次收紧范围
4. **唯一失败为测试夹具问题**：`test_permission_control` 首跑 IntegrityError（AuthUser 的 `unique_auth_phone_active` 约束下，空字符串 auth_phone 在不同用户间重复）→ 修复 `_make_user` 生成唯一 `_phone()` + 唯一 email，全绿

### 五、验证记录

```text
① pytest core/tests/test_audit_log_api.py -q          → 36 passed, 0 failed ✅
② ruff check core/audit_log_views.py core/tests/test_audit_log_api.py
                                                     → All checks passed ✅
③ mypy core/audit_log_views.py                        → Success: no issues found ✅
④ 权限矩阵断言：regular 用户 6 端点全部 403；auditor / system_admin 全部 200 ✅
   （修复前普通用户 list 端点 200，修复后 403，先红后绿）
```

### 六、遗留与关联事项

- BE-02（修改密码无旧密码校验）已修复（2026-09-14，commit 235ebe9，见 BF-010）；BE-01/03/04 已闭环
- 审计端点的 401/400/404 等业务语义用例保留于 Service 层测试（auditor 视角），与权限矩阵互补

---

*登记人：big-pickle ｜ 状态：目标测试+静态检查通过，代码级验证完成*

---

## BF-008 【已关闭】出库/待报废更新类操作审计缺操作人/缺日志（审查报告 BE-05）

- **发现日期**：2026-09-13（《审查报告_2026-09-13_AtomCode.md》BE-05）
- **严重级别**：P2（更新类操作无法追责到人，审计链有洞）
- **影响范围**：`views/out_asset_view.py`、`views/damaged_asset_view.py`、`services/damaged_asset_service.py`、`services/operation_log_service.py` + 3 个测试文件；无 API 契约变更

### 一、问题现象

1. `OutAssetViewSet.update` 调 `update_outasset` 未传 operator，审计日志记 `operator_jobcode=None`
2. `DamagedAssetService.update_damaged_asset` 全程无 `AuditLogger` 调用——待报废记录更新不产生任何审计

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | `out_asset_view.py:199-202` 未把 operator context 传给 Service（mixin 已具备 `get_operator_context`） | `OperatorContextMixin` 见 `views/_mixins.py:75` |
| 2 | `damaged_asset_view.py:132/141` update/partial_update 未传 operator，且该 ViewSet 未声明 `OperatorContextMixin`（文件内惯例用 `resolve_operator(request.user)`） | create/destroy 均 `resolve_operator(request.user)` |
| 3 | `damaged_asset_service.py:81-94` 无审计调用 | 方法体仅 setattr+save |
| 4 | 既有审计写链路有 date 序列化雷：`before_data/after_data` 含 `date` 时 Django JSONField 序列化抛 TypeError，被 `AuditLogger._safe_log` 静默吞掉 → 日志从未落库 | `operation_log_service.py` 原无归一化 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | `OutAssetViewSet.update` 追加 `**self.get_operator_context()` | `views/out_asset_view.py:199` |
| 2 | `DamagedAssetViewSet.update/partial_update` 追加 `operator_jobcode=resolve_operator(request.user)[0], operator_name=resolve_operator(request.user)[1]` | `views/damaged_asset_view.py:132/141` |
| 3 | `update_damaged_asset` 签名加 operator 参数；循环内 `setattr` 前快照 `before_data`、后快照 `after_data`；`if update_fields:` 内 save 后补 `AuditLogger.log_asset_update(asset=damaged_asset.asset_recordcode, ...)` | `services/damaged_asset_service.py:70-105` |
| 4 | `OperationLogService.log_operation` 写入前统一幂等归一化 `_to_json_safe`（dict/list 递归、FK→recordcode、Decimal/date/datetime/time/UUID→str）；一次性修复所有调用方（含 recycle 的 `update_recycle_asset` 同雷） | `services/operation_log_service.py` |

### 四、对抗审核

1. **无残留缺口**：grep 全部资产更新入口（asset/out/recycle/damaged/hard_disk）——recycle 与 asset 的 View 早已传 `resolve_operator`，仅 out 与 damaged 为缺口，均已修复
2. **写入点归一化是唯一实现**：归一化逻辑收敛到 `OperationLogService.log_operation`（DR-1），未在 out/damaged service 复制第二处 `_normalize`；`asset_service._normalize`（历史实现、幂等）保留不改，疑似收敛点已记入遗留
3. **审计 asset 关联正确**：damaged 快照经 `damaged_asset.asset_recordcode`（Asset FK 实例）写入，与 out 侧口径一致
4. **测试真实覆盖**：回归用例 5 个先红 3 次（断言失败原因 = 修复前真症状：operator=None / 无 update 日志 / `got an unexpected keyword argument 'operator_jobcode'`），修复后绿 3 次；期间两次失败根因（view 无 mixin、date 序列化雷）均已定位修复，非放宽断言

### 五、验证记录

```text
① 回归 3x：test_update_out_asset + test_update_damaged_asset + TestUpdateDamagedAsset
                                                     → 红 3x(5 failed) → 绿 3x(5 passed) ✅
② pytest apps/assetmanagement/tests/test_out_asset_view_api.py test_damaged_asset_view_api.py test_damaged_asset_service.py
                                                     → 51 passed, 1 存量 warning ✅
③ pytest apps/assetmanagement/tests -q               → 645 passed, 5 存量 warning ✅
④ ruff check 7 文件                                  → All checks passed ✅
⑤ mypy 4 产品文件                                    → Success: no issues found ✅
```

### 六、遗留与关联事项

- `asset_service._normalize`（asset_service.py:173 内嵌局部函数）与 `operation_log_service._to_json_safe` 逻辑可合并，属 DR 收敛候选，本次未改以避免范围蔓延（已按 §1.8 新发现义务登记为关注项）
- BE-02（修改密码无旧密码校验）已修复（2026-09-14，见 BF-010）

---

*登记人：big-pickle ｜ 状态：目标测试+静态检查通过，代码级验证完成，2026-09-16*

---

## BF-009 【已关闭】change_status 废弃端点权限面与文档不符（审查报告 BE-06）

- **发现日期**：2026-09-13（《审查报告_2026-09-13_AtomCode.md》BE-06）
- **严重级别**：P3（规范/文档漂移，废弃端点权限比文档宽，误导安全评审）
- **影响范围**：`apps/assetmanagement/views/asset_view.py` get_permissions + 测试；无 API 契约变更（URL/参数/响应不变，仅角色门槛收紧）

### 一、问题现象

1. `change_status`（废弃的手动状态修复端点）docstring 与 OpenAPI 描述声明"仅供系统管理员数据修复使用"
2. 实际权限为 `IsAssetAdminOrAbove`——资产管理员也能调用，权限面比文档宽

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | `AssetViewSet` 覆写了 `admin_actions` + `get_permissions`，把 `change_status` 从 mixin 默认的 `IsSystemAdmin`（`_mixins.py:57,63`）带入 `[IsAssetAdminOrAbove()]` 分支（`asset_view.py:96-98`） | `admin_actions` L65 含 `change_status` |
| 2 | docstring/schema（`:273-276,280`）仍声明"仅限系统管理员"，权限与声明漂移 | 已验证 asset_admin 角色实测 200 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | `get_permissions` 首行特判 `if self.action == "change_status": return [IsSystemAdmin()]`，优先于 admin_actions 判断 | `views/asset_view.py:96-97` |
| 2 | import 增补 `IsSystemAdmin` | 同上 `:35` |
| 3 | `change_status` 保留在 admin_actions 清单（特判优先级更高，语义无残留），其余 action 权限不变 | 未动 |

### 四、对抗审核

1. **特判无残留**：`change_status` 的唯一 action 消费方为 `AssetViewSet.get_permissions`，特判（L96）先于 admin_actions（L98）命中，无绕过路径；`_mixins.py:57` 默认清单不含此 action 分支（被覆写，不影响）
2. **其它 action 不受影响**：特判仅匹配 `change_status`，其余 admin_actions（create/update/destroy/batch_*/change_outasset_employee/found_and_return/repair*）仍走 `[IsAssetAdminOrAbove()]`
3. **回归真实覆盖**：asset_admin 用户需与资产同部门（`manager` 归属部门）避免行级隔离 404 干扰——用例内建 manager 员工将资产归属到 asset_admin 部门后再断言 403；修复前实测 200（红灯 `assert 200 == 403`），修复后 403（绿灯）
4. **system_admin 锚点未误伤**：现有 `test_change_status`（superuser 夹具）绿，收紧对系统管理员零影响
5. **前端零影响**：前端全仓 grep `change_status` 无调用（deprecated 端点 UI 已切换专用接口）

### 五、验证记录

```text
① 回归红灯 3 连：test_change_status_requires_system_admin → FAILED（assert 200 == 403）✅
② 回归绿灯 3 连：同上 → PASSED（另锚点 test_change_status 亦绿）✅
③ pytest test_asset_view_api.py test_asset_view_rbac.py → 46 passed ✅
④ pytest apps/assetmanagement/tests → 646 passed, 5 存量 warning ✅
⑤ ruff check asset_view.py test_asset_view_api.py → All checks passed ✅
   mypy asset_view.py → Success: no issues found ✅
```

### 六、遗留与关联事项

- BE-02（修改密码无旧密码校验）已修复（2026-09-14，见 BF-010）；BE-01/03/04/05/06 已闭环
- 同类"docstring vs 权限面"漂移未在其它 ViewSet 批量扫描（审查报告仅 BE-06 一行在册），如需全量核查可另立任务

---

*登记人：big-pickle ｜ 状态：目标测试+静态检查通过，代码级验证完成，2026-09-16*

---

## BF-010 【已关闭】修改密码无需验证旧密码且不吊销 refresh token（审查报告 BE-02）

- **发现日期**：2026-09-13（《审查报告_2026-09-13_AtomCode.md》BE-02，P2 权限安全）
- **严重级别**：P2
- **影响范围**：`apps/authusermanagement`（唯一自助改密入口 `PUT /api/v1/auth/profile/`）；无 API 契约变更

### 一、问题现象

1. 改密请求只需提交 `password`，无需验证旧密码，无二次认证
2. 改密成功后已签发的 refresh token 不吊销，会话劫持者可静默改密并永久占据账号

### 二、修复情况（2026-09-14，commit 235ebe9 落库，代码与测试均已提交）

| # | 变更 | 文件 |
|---|------|------|
| 1 | `UserProfileUpdateSerializer` 新增 `old_password` 字段；`validate()` 强制校验：提交 `password` 时缺旧密码或 `check_password` 失败均 400，成功后从 attrs 移除 `old_password` | `serializers.py:56-94` |
| 2 | `update()` 改密后调用 `AuthService.invalidate_user_refresh_tokens(instance)` 作废全部 refresh token | `serializers.py:104-108` |
| 3 | `invalidate_user_refresh_tokens` 将用户全部 OutstandingToken 加入黑名单（异常兜底不中断主流程） | `services.py:269-312` |
| 4 | 空密码/空白/None 由 CharField `allow_blank=False` 在字段层拒绝，杜绝 `set_password("")` | `serializers.py:80-84` 备注 + `test_serializers.py:52-57` |

### 三、对抗审核

1. **绕过路径核查**：全局检索改密入口——仅 `views.py:325-335 ProfileAPIView.put`；Django admin（`admin.py:41` 用 password1/password2）与 `AuthService.update_user`（`services.py:244` forbidden_fields 含 password）均禁止改密，无绕过
2. **空密码边界**：`""`/纯空白/`None` 在字段层被拒（0x 复现测试 L52-57），不会进入 `set_password("")`
3. **吊销副作用**：仅改联系方式不触发吊销（`test_serializers.py:71-77` 回归护栏，防新副作用）
4. **唯一文档缺口（本次同步）**：审查报告 L27/L111/L140 与活账本 3 处遗留行仍标"待修复"，已同步为"已修复（2026-09-14，见本条目）"

### 四、验证记录

```text
① pytest apps/authusermanagement/tests → 80 passed ✅
② test_serializers.py 覆盖：缺旧密码拒绝 / 旧密码错误拒绝 / 正确通过且 old_password 不进 validated_data /
  空白密码字段层拒绝 / 改密哈希+吊销（mock 断言 invalidate 恰好调用 1 次且新哈希生效）/ 仅改联系方式不吊销 ✅
```

### 五、遗留与关联事项

- access token（10 分钟有效）改密后短期内仍可用，属已知取舍（仅吊销 refresh 已满足报告要求）；如需彻底防劫持可另立增强项
- 本条目为状态核实型闭环：修复代码在 commit 235ebe9 已存在，本次仅同步文档状态，未改动任何代码

---

*登记人：big-pickle ｜ 状态：文档状态同步完成（代码修复于 2026-09-14 已落库），2026-09-16*

---

## BF-011 【已关闭】送修创建无通知触发（审查报告 BE-07）——拍板 No-Op，口径更正

- **发现日期**：2026-09-13（《审查报告_2026-09-13_AtomCode.md》BE-07，P3 通知）
- **严重级别**：P3（口径漂移）
- **影响范围**：无代码；决策清单回写（通知覆盖范围）

### 一、问题现象

1. `repair_asset_service.py:120-162 create_repair_asset`（broken→repairing）内无 `send_notification_on_commit`，资产送修后 dept_manager 无感知
2. 历史报告（七轮全量审查）口径"5 处（含 repair 创建）且均带 mock 测试"，与代码实际 4 处不符

### 二、事实核查（对抗审核前置）

| # | 核查项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 通知落点计数 | **实际 4 处**：damaged approve/reject、repair done/failed | `damaged_asset_service.py:175-184,243-252`、`repair_asset_service.py:214-223,277-286` |
| 2 | `create_repair_asset` 无通知 | 属实 | `repair_asset_service.py:120-162` 全文无 `send_notification` |
| 3 | repair done/failed 断言测试 | **已存在**（先前勘察误判"无断言"，实为 mock 名为 `notify_dept_managers` 致 `grep "Notification"` 漏检；已按 Fact-1 更正，本轮未补测试） | `test_asset_lifecycle.py:308-326,370-387`，`test_asset_lifecycle.py` 24 passed |
| 4 | 业务依据 | 07 需文档全文无"送修/维修"通知条目 | `Project_Requirements/01-业务需求/07-功能需求与验收标准.md` |
| 5 | 同源决策 | R5-01 已对出库/回收/未登记审批拍板 No-Op（业务需求无通知要求） | 七轮报告 L119/R5-01 |

### 三、决策（2026-09-16）

**方案 B（No-Op），拍板依据**：
- 业务需求（07 文档 + 业务细则 4.5）对送修/维修事件无通知要求——唯一拍板依据
- 现存 4 处通知均为**结果/审批**类事件（审批通过/拒绝、维修完成/失败），dept_manager 是结果接收方；送修创建是**流程启动**，操作者即 dept_manager/资产管理员本人，自通知价值低
- 与 R5-01 事件分类保持一致：中段流程事件（出库/回收/送修）统一不通知，避免同性质事件一个通知一个不通知的矛盾

**生产代码零改动**。

### 四、文档回写（本条目动作）

| 文档 | 位置 | 改动 |
|---|---|---|
| 七轮全量审查报告 | L80 | "5 处（含 repair 创建）+ 均带 mock 测试" → "4 处+断言全部在位" |
| 同上 | L167 决策 3 选项 A | "5 类" → "4 类（damaged 审批通过/拒绝、repair 完成/失败）" |
| 同上 | L190 | 决策清单补充 BE-07 口径更正与闭环 |
| 审查报告 | BE-07 行 | 修复方案列 → ✅ 已拍板 No-Op |
| 审查报告 | BEQ-03 行 | 决策清单标已拍板，闭环记录 |

### 五、验证记录

```text
① pytest apps/assetmanagement/tests/test_asset_lifecycle.py → 24 passed ✅
   （含 test_repair_done_registers_notification_on_commit / test_repair_failed_registers_notification_on_commit,
    证明 done/failed 通知断言在位，无测试缺口）
② 生产代码零改动（git status 无 services 文件变更）
```

### 六、遗留与关联事项

- "均带 mock 测试"系七轮报告虚标（approve/reject 断言在 `test_damaged_asset_service.py`、done/failed 在 `test_asset_lifecycle.py`，全部在位且通过）——已在 L80 更正为事实陈述
- 通知机制健全性（WS 节流/合并/回灌 R5-02）不受本次拍板影响

---

*登记人：big-pickle ｜ 状态：No-Op 决策已拍板 + 口径回写完成（生产代码零改动），2026-09-16*
