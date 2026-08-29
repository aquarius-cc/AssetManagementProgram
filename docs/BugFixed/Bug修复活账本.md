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
