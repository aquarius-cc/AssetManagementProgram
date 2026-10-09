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
  主因为后端 `consumer.accept()` 未回显前端以 subprotocol 方式传入的 JWT（RFC 6455 要求服务器选择一个子协议应答，否则浏览器掐断连接）；次要因素与本案同源——cookie 按 host 隔离（`localhost` 与 `127.0.0.1` 互不可见）。建议修复时统一为 Vite 代理转发 WS（`/ws` 路径加 `ws: true`），消除双 host 结构【已落地 → BF-032】
- **改进建议**：前端守卫可区分 403-CSRF 与 401，避免配置类故障被误判为"会话过期"【已落地 → BF-032】

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
- BF-002 两条改进建议（Vite `/ws` 代理统一双 host + 403-CSRF 误判分流）已落地，详见 BF-032

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

- 告警闭环(BF-003 Step 4)：✅ 代码/编排侧已收口(2026-09-22)——node-exporter 已定义于 docker-compose.monitoring.yml:63-78 并以 backup_status_data 共享卷采集 textfile 指标；alertmanager send_resolved 已存在(config/alertmanager.yml:32/:37)，adapter resolved 恢复卡已实现且测试覆盖(docker/feishu-webhook/app.py:57-63, test_app.py:30)；M-5C 组新增 BackupMetricsMissing 数据源自活守卫。⚠️ 运行态部署验证(拉起 node-exporter + 失败注入 + 飞书送达)待运维执行，步骤见 10-监控告警SOP §6
- S3 bucket 生命周期策略：✅ 已代码化(2026-09-22)——scripts/s3_lifecycle.json + scripts/apply_s3_lifecycle.sh(30d→STANDARD_IA / 90d 删除，需 s3:PutLifecycleConfiguration)；一次性基础设施应用操作待运维执行，见 08-数据备份恢复方案 §6

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

- **D3（技术债）** ✅ **已修复（2026-09-22 复核，无需代码改动）**：cancel/reject 路径建议统一 `except InvalidTransitionError → AppValidationError(INVALID_STATE_TRANSITION)`（对齐 `create_damaged_asset:53-54`）。复核证据：全仓 11 处 `except InvalidTransitionError` 均已统一映射 `error_code="INVALID_STATE_TRANSITION"`——asset_lifecycle_mixin.py:64/:168、asset_service.py:57、damaged_asset_service.py:74、out_asset_service.py:140/:254、recycle_asset_service.py:166/:214/:328、repair_asset_service.py:88、waste_asset_service.py:50；无 `ILLEGAL_STATUS`/裸 raise/吞异常残留；6 个测试锚点断言该 error_code（test_asset_lifecycle.py:65/118/193、test_asset_service.py:236、test_recycle_asset_service.py:365、test_damaged_asset_service.py:162）。报告行标"已修复"
- **D4（技术债）** ✅ **已修复（2026-09-22 复核，对齐 #15 PR-2 交付）**：`DamagedAsset.asset_recordcode` OneToOne 软删后唯一索引仍占用，重新申请会 IntegrityError；建议 partial unique index `WHERE is_deleted = false` 或复用软删行。复核证据：`apps/assetmanagement/models/damaged_asset.py:113-118` 已为部分唯一索引 `UniqueConstraint(fields=["asset_recordcode"], condition=Q(is_deleted=False), name="uq_damaged_asset_active_asset", violation_error_message=...)`，迁移 `0023_alter_damagedasset_asset_recordcode_and_more.py:22` 同步落地；软删行不再占用唯一槽位，重新申请不会 IntegrityError。报告行标"已修复"
- 需求文档 01/07 无"取消报废"验收条目；本修复依据技术设计文档 03 旧约定修正 + 业务约束第 6 条（新增产品决策），已在 `backend-business-rules.md` v1.11 变更日志注明（2026-09-22 复核：现行规则文件已演进至 **v1.13**（2026-09-17），v1.11 条目仍保留于变更日志 :242，业务约束第 6 条现位于 :116）

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

- access token（ACCESS_TOKEN_LIFETIME=2 小时，base.py:217——报告原写"10 分钟"有误，2026-09-22 实测复核）改密后最长仍可用 2 小时，属已知取舍（仅吊销 refresh 已满足报告要求）；【2026-09-22 A2】生产窗口已压缩至 30 分钟（base.py:217，test 环境仍 pin 5min 不受影响），改密后旧 access 残留上限降至半小时；彻底防劫持（每请求 claims 比对 / access 黑名单校验）增强项仍保留
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

*登记人：big-pickle ✅ 状态：No-Op 决策已拍板 + 口径回写完成（生产代码零改动），2026-09-16*

---

## BF-012 【已关闭】`change_outasset_employee`/`transfer_asset_to_storage` 审计 operator 硬编码 None（审查报告 #5 B7）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P1 #5）
- **严重级别**：P2（更新类操作的审计链无法溯源到操作人）
- **影响范围**：`services/asset_service.py`、`views/asset_view.py` + `tests/test_asset_service.py`；无 API/DB 契约变更

### 一、问题现状

1. `change_outasset_employee`（服务层审计日志）：`log_asset_update(..., operator_jobcode=None, operator_name=None)`——更新申请人/保管人不知是谁改的
2. `transfer_asset_to_storage`：同款硬编码 `None`
3. 两方法签名无 `operator_jobcode/operator_name` 形参，View/调用方想传也传不进，审计 `OperationLog.operator_jobcode` 为 NULL

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | `asset_service.py` 两方法审计处硬编码 `None` | `:410-411`、`:441-442`（基线为 `:397-398`/`:418-419`）|
| 2 | 签名无 operator 形参 | `:387`（change_outasset_employee）、`:418`（transfer_asset_to_storage）|
| 3 | View 有现成管道未用 | `asset_view.py:38` 引入 `import resolve_operator`，`create/update/destroy/change_status` 均用，唯 `change_outasset_employee`（`:316`）漏用 |
| 4 | 对照组证明缺失 | 同文件 `change_asset_status`（`:351-356`）带 operator 形参并透传 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | `change_outasset_employee`/`transfer_asset_to_storage` 签名追加可选 `operator_jobcode: str/None = None`、`operator_name: str/None = None`（置于 `*, user` 前，排布对齐 `change_asset_status`）| `services/asset_service.py` |
| 2 | 两处 `log_asset_update` 由硬编码 `None` 改为透传形参 | `services/asset_service.py` |
| 3 | `change_outasset_employee` View 调用补 `operator_jobcode=resolve_operator(request.user)[0], operator_name=resolve_operator(request.user)[1]`（复用既有 `:138-139` 写法）| `views/asset_view.py` |
| 4 | `transfer_asset_to_storage` 零调用方（死代码），仅补服务层参数做防御性透传，不改动任何调用方 | — |

### 四、对抗审查

1. **零破损**：参数可选默认 `None`，既有 3 个调用方（View + 2 测试）均不受影响；`OperationLog` 表结构与 API 响应不变，仅 operator 字段由 NULL 变有值
2. **B12 隔离未动**：两方法 `user` 参数、`select_for_update`、`ensure_asset_visible` TOCTOU 兜底原样保留（diff 逐行核对）
3. **回归先红后绿**：先红 3 次——`change_employee` 断言 `None==adminuser`、`transfer` pre-fix `TypeError: unexpected keyword argument 'operator_jobcode'`（修复前 View 想传传不进的实证）；修复后绿
4. **发现两个相关但超范围问题（仅登记未修复）**：
   - ① `transfer_asset_to_storage` 全仓库零调用方（死代码，用户拍板仍做防御性补全）
   - ② `change_outasset_employee` View 传 `employee_jobcode` 字符串，赋给 Service `FK(to_field="recordcode")` 报实测 `ValueError: must be a "Employee" instance` → 500；该端点无前端调用方，属既有独立功能性 bug（比 B7 更严重），待独立修复

### 五、验证记录

```text
① 回归 3x：test_change_employee_success + TestTransferAssetToStorage
                                                       → 3x(2 failed) → 2 passed ✅
② pytest test_asset_service.py + test_asset_view_api.py + test_asset_selector_isolation.py
                                                       → 76 passed ✅
③ pytest -q（全量）                                   → 1166 passed ✅
④ ruff check 3 文件                                   → All checks passed ✅
⑤ mypy asset_service.py + asset_view.py               → 目标文件 0 错误（仅 2 存量错误在其他文件）✅
```

### 六、遗留与关联事项

- **候补 P0 已修复 2026-09-22**：`change_outasset_employee` jobcode→recordcode FK 映射 bug —— Service 经 `EmployeeSelector.get_employee_by_jobcode` 解析为实体后赋值（先例：damaged/recycle/repair），员工不存在升 `core.exceptions.NotFoundError` 404（决策：传 jobcode，参数名不变）；解析置于 `ensure_asset_visible` 之后保 B12 隔离语义。commit `6aa8300`。测试：视图层从"容忍 500"收紧为精确 200 + FK 落库断言，新增 jobcode 不存在→404 用例；教训注：Service 测试曾传 Employee 实例掩盖 jobcode 路径、视图测试曾容忍 500
- `transfer_asset_to_storage` 死代码处置：零调用方核实成立 → **已删除 2026-09-22**（方法体 + `StorageSelector` 孤儿 import + 测试类），收尾 grep 0、79 passed。commit `52f6a99`。operator 透传锚（B7）由 `change_outasset_employee` 的 `test_change_employee_success` 继续承载

---

*登记人：big-pickle ✅ 状态：目标测试+前端三项检查通过，代码级验证完成，2026-09-20*

---

## BF-013 【已关闭】外借资产编辑提交 key 不匹配（payload `asset_recordcode` vs store 期望 `recordcode`）（审查报告 #6 CT-4）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P1 #6）
- **严重级别**：P1（编辑外借资产的更新请求必定失败，功能不可用）
- **影响范围**：`components/componentsdetails/detils/OutAssetForm.vue`、`composables/useOutAssetForm.ts` + 两处 spec；纯前端请求体内部键名，无后端/DB/跨端契约变更
- **登记来源**：审查报告 #6；靶点修正——审查报告原靶点 `useOutAssetForm.ts:286-289` + `createEntityStore.ts:340`，实测真实生产路径另有 `OutAssetForm.vue:413` 同款 bug（组件重构后 `submitForm` 已内联，`useOutAssetForm` 变为零调用方遗留代码）

### 一、问题现状

1. 编辑外借资产、修改后点保存，界面提示成功但数据未更新，或更新请求直接失败
2. `createEntityStore.update` 以 `idKey = "recordcode"` 取主键（`outAssetStore.ts:44`），payload 无该键则 `createEntityStore.ts:340-341` 取不到 ID 并 `throw new Error('Missing ID for update')`
3. `api/outAsset.ts:116` 进一步要求 `data.recordcode || data.outasset_recordcode`，旧键名 `asset_recordcode` 两者都不是
4. 两处生产代码（组件 + 遗留 composable）写的是同款错误键名 `asset_recordcode`

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 生产提交处键名错误 | `OutAssetForm.vue:413`（修复前 `asset_recordcode: recordcode`）；`useOutAssetForm.ts:287`（修复前 `asset_recordcode: route.query.code`）|
| 2 | store 契约以 `recordcode` 取主键 | `stores/outAssetStore.ts:44` `idKey` 配置；`libraries/createEntityStore.ts:340-341` `data[config.idKey]` 缺失即抛出 |
| 3 | API 层同契约 | `api/outAsset.ts:116` `data.recordcode \|\| data.outasset_recordcode` |
| 4 | 审查报告原靶点不完整 | 原报告只提 `useOutAssetForm.ts` + `createEntityStore.ts`，漏了真实生产路径 `OutAssetForm.vue:413` |
| 5 | 旧测试被 mock 掩盖 | `useOutAssetForm.spec.ts:478/:489` 断言 `asset_recordcode`（store 被 mock，故一直「绿」），未捕获此 bug |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | 编辑分支 `outAssetStore.update({ asset_recordcode: recordcode, ...outAssetForm.value })` → `{ recordcode, ...outAssetForm.value }` | `components/componentsdetails/detils/OutAssetForm.vue:413` |
| 2 | 同款键名 `asset_recordcode` → `recordcode` | `composables/useOutAssetForm.ts:287` |
| 3 | 修正两处被 mock 掩盖的错误断言 `asset_recordcode` → `recordcode`（回到正确契约，非放宽断言）| `composables/__tests__/useOutAssetForm.spec.ts:478,489` |
| 4 | 新增组件级回归用例：真实挂载组件 → 编辑模式改描述 → 点保存 → 断言 `update` 收到 `recordcode` 且不含 `asset_recordcode` | `components/.../__tests__/OutAssetForm.spec.ts`（新增，`:167/:169`）|

### 四、对抗审查

1. **同款键名残留扫描**：全仓库 `asset_recordcode` 其余命中均属不同业务语义（待报废/回收/硬盘/丢失/损坏等的「关联资产编码」字段，非出库本条记录主键）；出库编辑路径除本次两处外无遗漏。`OutAssetForm.vue` 已无 `asset_recordcode`
2. **payload 键冲突排除**：`{ recordcode, ...outAssetForm.value }` 中 `outAssetForm` computed（`OutAssetForm.vue:301-315`）映射键为 `outasset_code/number/applicant/manager/date/type/using_location/description`，**不含** `recordcode`，不存在被 spread 覆盖成 undefined 的风险；组件测试 `objectContaining({recordcode:'OUT001'})` 通过即实证
3. **靶点修正留痕**：审查报告 #6 行已补注真实靶点 `OutAssetForm.vue:413`，未删除原表述
4. **契约影响**：仅前端请求体内部键名；后端 `OutAssetUpdateSerializer.recordcode` 为 `read_only`（`out_asset_serializers.py:174`），请求体不含该主键，schema 基线无需重导出
5. **测试真实性**：修复前红灯各连跑 3 次（composable spec `2 failed`、组件 spec `1 failed`），非时红时绿；修复后绿

### 五、验证记录

```text
① 红灯（预，修复前）useOutAssetForm.spec.ts（断言已先改为 recordcode）
   npx vitest run src/composables/__tests__/useOutAssetForm.spec.ts
                                                      → 3x(2 failed \| 30 passed）✅
② 红灯（预，修复前）新增组件回归 OutAssetForm.spec.ts
   npx vitest run .../detils/__tests__/OutAssetForm.spec.ts
                                                      → 3x(1 failed，实收 asset_recordcode）✅
③ 绿灯（补丁后）回归
   npx vitest run useOutAssetForm.spec.ts + OutAssetForm.spec.ts
                                                      → 33 passed(2 files）✅
④ 相关套件
   npx vitest run createEntityStore.spec.ts + createEntityStore.edge.spec.ts +
                  detils/__tests__/ + useOutAssetForm.spec.ts
                                                      → 254 passed(10 files）✅
⑤ npm run type-check                                → 通过（vue-tsc，无错误）✅
⑥ npm run lint                                      → 通过（eslint --fix）✅
⑦ npm run format:check                              → 首轮 2 文件（本次新增/编辑）报格式 → prettier --write → All matched files use Prettier code style ✅
```

### 六、遗留与关联事项

- **DR-2 遗留（已闭环 2026-09-22）**：`composables/useOutAssetForm.ts` 零生产调用方核实成立 → **已删除**（连同自身 spec + 7 处文档头引用，能力由 useAssetFormHelpers/useEmployeeSuggestionFetcher/useAutocompleteField 承接）。commit 前端 `7a3137d`；FR6 台账去行，guard `check_frontend_invariants.py` PASS（50→49 文件 / 4→3 孤儿）；vitest composables 41 文件 576 passed、type-check 0
- **[已闭环 2026-09-22] 编辑时人员/地点不落库（A 选项全口径）**：create+update 序列化器（`OutAssetCreateSerializer`/`OutAssetUpdateSerializer`）新增 `outasset_applicant`/`outasset_manager` 写字段（`SlugRelatedField(slug_field="employee_jobcode")`，缺 jobcode→400）；`update_outasset` 循环前特判映射 FK，抽 `_build_asset_people_update`（create/update 共用，DR-1）并**同步 Asset 主表**（锁定实例 `save(update_fields=...)`，锁序 outasset→asset）；实测补正：`outasset_using_location` 编辑曾"半生效"（仅写 OutAsset、详情/主表读 Asset 侧仍旧值）→ 本轮一并联动；**create 同病一并修**（原序列化器 create() 还 pop 掉 using_location，验证 create 同样静默丢弃）;快照不重写（保历史，编辑走审计 before/after）。commit `bbb3049`；4 新测试 + B8 补强，红→绿 4 failed→9 passed，相关 4 套件 32 passed，ruff/mypy 0；schema 基线重导出 `489e907`。前端零改动
- **[核实 by design] 编辑态资产不可更换**：两端一致封死——更新序列化器 `recordcode`/`asset_recordcode` 均 `read_only=True`（:174-175），前端出库资产名称/编码 `:disabled="isEditMode"`（OutAssetForm.vue:45/:68）；换资产仅能走新增，符合 PROTECT FK + 快照语义，无需修复

---

*登记人：big-pickle ✅ 状态：目标测试+前端三项检查通过，代码级验证完成，2026-09-20*

---

## BF-014 【已关闭】组件内直连 `request.post` 重复定义批量创建端点、绕过 unwrapResponse（审查报告 #7 FR-3/F11）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P1 #7）
- **严重级别**：P1（组件层绕过统一请求封装与端点单一来源，违反 FR-3/F11，存在重复维护与错误处理分叉风险）
- **影响范围**：`components/componentsdetails/detils/AssetBatchImport.vue` + 新增 spec；纯前端请求路径收敛，无后端/DB/跨端契约变更
- **登记来源**：审查报告 #7

### 一、问题现状

1. `AssetBatchImport.vue` 在组件内直接 `request.post('/assets/assets/batch-create/', { items })`，同一端点 `api/asset.ts:353` 已有 `batchCreateAssets` 封装
2. 组件手动取 `res.data`，等同于绕过 `unwrapResponse`，丢失统一的 `code !== 0` 校验
3. 原注释声称「避免 unwrapResponse 丢失详细错误」与实际不符——400 由 axios 响应拦截器直接 reject，`unwrapResponse` 不参与，标准链路同样能拿到明细

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 端点重复定义 | 组件 `:269` 硬编码 `/assets/assets/batch-create/`，与 `api/asset.ts:353-359` 冲突（FR-3 违反）|
| 2 | 组件层直连请求 | `:146` 直接 import `request`，违反 F11「异步必须走 Store/Composables」|
| 3 | 错误处理分叉 | 手动 `res.data`（`:270-277`）绕过 `unwrapResponse`（`request.ts:413-419`）的 `code !== 0` 校验 |
| 4 | 注释误导 | `:260` 理由错误，导致后人认为必须绕过封装 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | 删除内层 try 的手动 `request.post` + `res.data` 拆包，改为 `let result: Awaited<ReturnType<typeof assetStore.batchCreateAssets>>` + `result = await assetStore.batchCreateAssets(apiDataList)`；外层 400 明细 catch 原样保留 | `components/componentsdetails/detils/AssetBatchImport.vue:259-262` |
| 2 | 删除误导注释，替换为正确说明（统一走 store，端点仅存于 api 层定义，400 由 axios 拦截器 reject）| `components/componentsdetails/detils/AssetBatchImport.vue:259` |
| 3 | 删除 `import { request } from '@/api/index'`（全组件唯一引用）| `components/componentsdetails/detils/AssetBatchImport.vue:146` |
| 4 | 新增组件级回归：mock store 后真实挂载 → 点提交，覆盖全成功/部分失败/400 明细三路径 + 反证不调 `request.post` | `components/.../__tests__/AssetBatchImport.spec.ts`（新增）|

### 四、对抗审查

1. **端点残留扫描**：`AssetBatchImport.vue` 内 `request` 与 `batch-create` 均已零命中；全仓库 `/assets/assets/batch-create/` 仅剩 `api/asset.ts:355` 单一来源
2. **store 运行时可用**：`assetStore.ts:196` 在 `useAssetStore` 内**无条件**挂载 `batchCreateAssets`，`:259` 由 `extendedStore` 返回；接口声明在 `:75`，非条件式懒挂载
3. **400 错误透传**：响应拦截器 `request.ts:302-303` 调 `notifyApiError`（内部 `:187-217` 纯字符串拼接、不抛异常）后 `Promise.reject(error)`，抛出的是**原始 axios 错误**（`isAxiosError === true` 且保留 `.response.status/data`），组件 400 分支照常命中；`unwrapResponse` 不参与 catch，不改变错误类型
4. **成功路径等价性**：`unwrapResponse` 返回 `res.data`（`request.ts:413-419`）；组件原先手动拆出的 `res.data` 类型为 `AssetBatchCreateResult` 为原匿名类型的超集，下游 `fail_count/fail_items/success_count` 用法兼容
5. **行为正向变化**：修复后新增 `code !== 0` 校验（原直连路径会静默把 `code != 0` 当成功），属修复而非回归
6. **测试真实性**：修复前红灯连跑 3 次（`3 failed`，均为 `batchCreateAssets` 未被调用），非时红时绿；修复后 3 passed

### 五、验证记录

```text
① 红灯（预，修复前）新增组件回归 AssetBatchImport.spec.ts
   npx vitest run .../detils/__tests__/AssetBatchImport.spec.ts
                                                      → 3x(3 failed \| 0 passed）✅
② 绿灯（补丁后）回归
   npx vitest run .../detils/__tests__/AssetBatchImport.spec.ts
                                                      → 3 passed ✅
③ 相关套件
   npx vitest run detils/__tests__/ + composables/__tests__/useAssetBatchImport.spec.ts
                  + stores/__tests__/assetStore.spec.ts
                                                      → 225 passed(10 files）✅
④ npm run type-check                                → 通过（vue-tsc，无错误）✅
⑤ npm run lint                                      → 通过（eslint --fix）✅
⑥ npm run format:check                              → 首轮仅新增 spec 报格式 → prettier --write → All matched files use Prettier code style ✅
```

### 六、遗留与关联事项

- **DR-1/DR-2 遗留（2026-09-22 复核后消解）**：`composables/useAssetBatchImport.ts`（:167 走链路、:169-194 解析 400 明细）为全仓库零生产调用方的孤儿 composable。复核证据：① 生产 import 0 命中（仅自身 spec + 3 处 doc 注释：assetStore.ts:9/useBatchImport.ts:8/SubmitBatch.ts:12）；② 组件提交已全部走 store 链路（AssetBatchImport.vue:262 → assetStore.ts:195-196 → assetAPI.batchCreateAssets），其 400 明细解析内联于组件 :263-296，无第三方承载；③ 两份 handleSubmit 文本仍近同构，但**活性重复已消解、仅剩死代码孤儿本体**。结论：**合并任务撤销**，处置归 FR-6 孤儿台账（useAssetBatchImport.ts，228 逻辑行，待去重）独立批次删除
- **`AssetBatchImport.vue` 其它同类风险（2026-09-22 已全量复查，F11 归零）**：全组件审计——import 区（:137-157）零 `@/api`、零 request，`isAxiosError`（:148）仅用于 400 catch 类型收窄（:265）；无第二处 request import、无端点字符串；`handleExportTemplate` → `downloadExcelTemplate`（templateExport.ts）仅 ExcelJS 客户端生成，无网络。结论：直连请求为零，无需任何动作

---

*登记人：big-pickle ✅ 状态：目标测试+前端三项检查通过，代码级验证完成，2026-09-20*

---

## BF-015 【已关闭】`delete_asset` 与 `batch_delete_asset` 删除守卫重复 + 批量框架手写、错误码分叉（审查报告 #9 DR-1）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P1 #9）
- **严重级别**：P1（删改核心业务逻辑重复实现，错误码分叉，违反 DR-1；批量路径出库守卫零测试）
- **影响范围**：`services/asset_service.py`、`tests/test_asset_service.py`；纯后端 Service 内部收敛，响应结构与跨端契约不变
- **登记来源**：审查报告 #9；靶点修正——原报告错误码分叉述为 `IN_USE` vs `ASSET_IN_USE`（实测两处均为 `ASSET_IN_USE`），真实分叉为 `ASSET_HAS_OUTASSET`（单条）vs `HAS_OUTASSET_RECORDS`（批量）

### 一、问题现状

1. `delete_asset` 与 `batch_delete_asset` 各自逐条实现同一套删除前置校验与删除动作（状态非在库 / 有出库记录 / 有待报废记录 / 审计+软删除）
2. 出库记录错误码两处不一致：单条 `ASSET_HAS_OUTASSET`，批量 `HAS_OUTASSET_RECORDS`
3. `batch_delete_asset` 还手写了整套批量执行框架（BATCH_SIZE 校验、循环、异常分类、结果 dict 组装），与 `core/batch_mixins.py::batch_delete_execute` 重复；其余 6 个服务的批量删除均已复用该 mixin（B-5 收敛），唯独 asset 遗漏
4. 批量-出库失败路径全仓无任何测试断言（仅单条路径 `test_asset_service.py:124` 固化 `ASSET_HAS_OUTASSET`）

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 守卫逻辑双份 | 修复前 `delete_asset:217-242` 与 `batch_delete_asset:273-347` 控制流不同（抛异常 vs 收集 fail_items），逻辑被手抄而非复用 |
| 2 | 错误码抄写不一致 | 单条 `:231` 为 `ASSET_HAS_OUTASSET`，批量 `:314` 为 `HAS_OUTASSET_RECORDS` |
| 3 | 批量框架未复用 | `batch_delete_asset` 手写循环，未用 `BatchOperationMixin.batch_delete_execute`（B-5 收敛遗漏 asset）|
| 4 | 测试盲区 | 批量出库失败路径零覆盖，分叉长期未被发现 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | 新增 `_delete_guarded(asset, operator_jobcode, operator_name)`：状态/出库/待报废守卫 + `log_asset_delete` + `asset.delete()` 的唯一实现（`@staticmethod`，带 `# [HALT]`）| `services/asset_service.py:207-232` |
| 2 | `delete_asset` 保留 `ASSET_NOT_FOUND`/TOCTOU 段后改为调用 `_delete_guarded` | `services/asset_service.py:234-249` |
| 3 | `batch_delete_asset` 整段手写循环替换为闭包 `_delete_one` + `BatchOperationMixin.batch_delete_execute`；闭包内保留 B12 NOT_FOUND 映射，`ensure_asset_visible` 的 except 仅包住该调用，`_delete_guarded` 置于 try 之外防误映射 | `services/asset_service.py:272-296` |
| 4 | 顶层收编 `DamagedAsset, OutAsset` import，移除冗余 `MAX_BATCH_SIZE` import | `services/asset_service.py:17,23` |
| 5 | 新增 3 用例：批量出库失败码统一 / 混合成功失败逐条独立 / TOCTOU 锁内不可见归为 NOT_FOUND | `tests/test_asset_service.py:166-208` |

### 四、对抗审查

1. **错误码统一方向**：批量向单条收敛（`ASSET_HAS_OUTASSET`）。`HAS_OUTASSET_RECORDS` 全仓 `*.py` 0 残留；前端 `vue-assetmanagement/src` 两码均 0 命中，`error_code` 仅供 fail_items 且前端不消费（活账本 G-4：无需注册）
2. **对外可见性**：批量 `fail_items[].error_code` 值与批量出库失败 `error_message` 文案变化属对外数据值变化，非结构变更；响应结构、端点、状态枚举均不变，`api-schema-baseline.json` 无需重导出
3. **except 范围（本次重点）**：`ensure_asset_visible` 的 try 只包住该调用；`_delete_guarded` 在 try 之外，故 `ASSET_IN_USE`/`ASSET_HAS_OUTASSET`/`HAS_DAMAGED_RECORDS` 原样上抛给 mixin 的 `except AppValidationError`，不被误映射为 NOT_FOUND——由「批量出库失败码统一」用例实证
4. **BATCH_SIZE 行为等价**：mixin 默认 `DEFAULT_MAX_BATCH_SIZE = core.constants.MAX_BATCH_SIZE = 100`，原手写用同一常量；`BATCH_SIZE_EXCEEDED` 同码、文案同为「单次批量删除不能超过 100 条」
5. **异常分层**：mixin 先 `except AppValidationError`，再 `serializers.ValidationError`，后 `Exception`；`AppValidationError` 是 DRF ValidationError 子类，路由正确
6. **单条路径零漂移**：`:115/:124/:134` 单条断言未改，全绿；`delete_asset` 守卫顺序不变
7. **BR-7 调用链**：仅一个 Service 类（AssetService 继承 mixin），`_delete_one`/`_delete_guarded` 均为同类内静态闭包，非 View→Service→Service；到 Selector 纵深不增加
8. **存量原样保留**：`_delete_guarded` 内的 `OutAsset/DamagedAsset.objects.filter` 裸查询沿用既有实现（DR-3 属审查 #10，超出本次边界）
9. **历史文档**：`asset_management_backend/docs/batch-create-optimization-plan/*.html` 仍含旧码，属历史方案快照（非活文档），不改写历史

### 五、验证记录

```text
① 红灯（预，修复前）批量新增用例
   pytest test_asset_service.py -k "batch_delete_has_outasset or batch_delete_mixed_success_and_outasset"
                                                      → 3x(2 failed，实收 HAS_OUTASSET_RECORDS）✅
② 绿灯（补丁后）
   pytest apps/assetmanagement/tests/test_asset_service.py -q
                                                      → 30 passed ✅
③ 隔离/视图/快照
   pytest test_asset_selector_isolation.py test_asset_view_api.py
          test_b5_baseline_snapshot.py test_batch_contract_snapshot.py
                                                      → 68 passed ✅
④ 全量
   pytest apps --cov=apps --cov-fail-under=80 -q     → 972 passed，整体 84.16%（≥80%）✅
⑤ Service 层覆盖率
   pytest apps/assetmanagement --cov=apps.assetmanagement.services --cov-fail-under=90
                                                      → 95.00%（asset_service.py 96%）✅
⑥ ruff check apps/assetmanagement core               → All checks passed ✅
⑦ mypy apps/assetmanagement core --strict            → asset_service.py 0 错误（其余 10 条存量）✅
⑧ rg HAS_OUTASSET_RECORDS apps core --glob "*.py"    → 0 残留 ✅
⑨ python scripts/check_duplicate_invariants.py       → PASS ✅
```

### 六、遗留与关联事项

- **DR-3 存量（属审查 #10，未在本次范围）**：`_delete_guarded` 内 `OutAsset.objects.filter` / `DamagedAsset.objects.filter` 仍为 Service 层裸查询，未下沉 Selector
- **历史方案文档**：`batch-create-optimization-plan.html` 的 error_code 示例保留旧码 `HAS_OUTASSET_RECORDS`，属历史快照，未改写

---

*登记人：big-pickle ✅ 状态：目标测试+全量回归+覆盖率+静态检查通过，代码级验证完成，2026-09-20*

---

## BF-016 【已关闭】approve/reject/cancel 手写「过滤+判空+加锁」绕过 Selector，且该 Selector 在 PostgreSQL 不可用（审查报告 #10 DR-3）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P1 #10）
- **严重级别**：P1（DR-3 数据查询未收敛 + 目标抽象在 PostgreSQL 必然报错）
- **影响范围**：`selectors/damaged_asset_selector.py`、`services/damaged_asset_service.py`（approve/reject/cancel，含批量取消委托）、`tests/test_recycle_damaged_waste_selector.py`；纯后端，契约零变化
- **登记来源**：审查报告 #10；靶点修正——原报告仅述「绕过 Selector」，实测真正阻塞项是 Selector 自身不可用

### 一、问题现状

1. `approve_asset_recordcode`/`reject_asset_recordcode`/`cancel_asset_recordcode` 三处逐字重复同一段取数：`filter(asset_recordcode__recordcode=..., is_deleted=False).first()` → 判空 `DAMAGED_ASSET_NOT_FOUND` → `select_for_update().get(pk=...)` 重取加锁
2. 已有 `DamagedAssetSelector.get_asset_recordcode_for_update` 可一条查询完成「过滤 + 行锁」，但全仓 0 调用方（含测试），是零覆盖死代码

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 逻辑三份 | 三处手抄同一 9 行模式，仅靠错误码文案对齐 |
| 2 | 孤儿抽象 | Selector 从未接入任何调用方，其缺陷长期隐藏 |
| 3 | **Selector 自身不可用** | `with_asset_details().select_for_update()` 对可空 `asset_recordcode`（OneToOneField null=True）与 `approver` 生成 LEFT OUTER JOIN；PostgreSQL 禁止 `FOR UPDATE` 作用于外连接可空侧 |
| 4 | 附带低效 | 手写模式两条查询（`first` + `select_for_update` 重取），且未消除检查→加锁之间的 TOCTOU 窗口 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | `get_asset_recordcode_for_update` 去掉 `with_asset_details()`，改为 `DamagedAsset.objects.select_for_update().get(asset_recordcode__recordcode=..., is_deleted=False)`；加注释禁止叠加 `select_related` | `selectors/damaged_asset_selector.py:43-49` |
| 2 | 三处统一替换为 `try/except DamagedAsset.DoesNotExist → AppValidationError(DAMAGED_ASSET_NOT_FOUND) from None`；未改任何方法签名 | `services/damaged_asset_service.py`（3 处）|
| 3 | 复用既有 `TestDamagedAssetSelector` 新增 3 用例（命中加锁实例 / 缺失 / 软删）| `tests/test_recycle_damaged_waste_selector.py`（+22 行）|

### 四、对抗审查

1. **前置缺陷成立**：实测 `django.db.utils.NotSupportedError: FOR UPDATE 不能应用于外连接的可空侧`，SQL 以 `... LIMIT 21 FOR UPDATE` 结尾（PostgreSQL，`config.settings.development→base`）
2. **错误码/文案逐字不变**：`detail=f"待报废记录 {code} 不存在"`、`error_code="DAMAGED_ASSET_NOT_FOUND"`；既有 `:169/:267/:383` 断言为语义锁，全绿
3. **`from None`**：仅抑制链式 `DoesNotExist` 上下文，响应体与日志错误码不变
4. **唯一性**：`asset_recordcode` 是 OneToOneField，`.get()` 不会 `MultipleObjectsReturned`；软删记录被 `is_deleted=False` 排除，与旧「先查再锁」语义一致
5. **锁范围**：旧加锁查询本就不带 `select_related`，新查询同样仅锁 `am_damaged_asset` 主表，锁足迹不变
6. **取舍**：不再预取关联，调用方访问 `damaged_asset.asset_recordcode.pk` 会多 1 次懒加载——与修复前行为一致，无回归；若日后要预取，改为 `select_for_update(of=("self",))` 并重新实测
7. **TOCTOU**：单查询在锁内同时校验 `is_deleted`，比旧两步更严格
8. **BR-7/DR-6**：View→Service→Selector = 3 层，合规
9. **签名未动**（用户备注）：三方法均无 `user` 参数，未改签名与返回类型
10. **全局唯一风险点已清零**：全仓仅此一处 `select_for_update` + `select_related` 组合，其余均为仅锁主表

### 五、验证记录

```text
① 红灯（修复前，新增 Selector 用例）
   pytest ...test_recycle_damaged_waste_selector.py::TestDamagedAssetSelector
                          → 3 failed，实收 NotSupportedError(FOR UPDATE ... nullable side) ✅
② 绿灯（补丁后，目标三文件）
   pytest test_recycle_damaged_waste_selector.py test_damaged_asset_service.py test_damaged_asset_view_api.py
                          → 54 passed ✅
③ 全量
   pytest apps --cov=apps --cov-fail-under=80 -q   → 975 passed，整体 84.17%（≥80%）✅
④ Service 层覆盖率
   pytest apps/assetmanagement --cov=apps.assetmanagement.services --cov-fail-under=90 -q
                          → 684 passed 95.15%（≥90%）✅
⑤ ruff check（变更 3 文件）                        → All checks passed ✅
⑥ mypy --strict（变更两文件）                      → 0 错误（1 条为存量）✅
⑦ rg "asset_recordcode__recordcode=" apps/assetmanagement/services → 0 残留 ✅
```

### 六、遗留与关联事项

- **未预取关联（有意为之）**：如需 `with_asset_details` 的预取收益，应改为 `select_for_update(of=("self",))` 并补实测；本次按最小正确口径未采用
- **行级隔离**：本 Selector 未加 `user` 参数，DamagedAsset 写路径的行级隔离策略为独立议题，本次未扩散

---

*登记人：big-pickle ✅ 状态：目标测试+全量回归+覆盖率+静态检查通过，代码级验证完成，2026-09-20*

---

## BF-017 【已关闭】`apps/usermanagement/services.py` 影子死代码（与同级 `services/` 包并存，包优先解析致其永不生效）（审查报告 #11 DR-1）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P1 #11）
- **严重级别**：P1（DR-1 同一业务逻辑两处实现；`.py` 版为维护误导：改了不生效）
- **影响范围**：`apps/usermanagement/services.py`、`apps/usermanagement/__pycache__/services.cpython-313.pyc`；纯后端，契约零变化
- **登记来源**：审查报告 #11；靶点修正——影子**可正常导入**（`BusinessLogicError` 存在于 `core/exceptions.py:72`，`ValidationError` 为其别名 `:119`），死因纯系包优先解析；`services.py:527/182/391-418` 等旧行号属更老 527 行版本快照，早已失效

### 一、问题现状

1. `apps/usermanagement/services.py`（277 行）与同级 `services/` 包并存，各存一套 `EmployeeService`/`DepartmentService`
2. 实测 `FileFinder.find_spec('services')` 返回 `services/__init__.py`、`is_package=True`，包优先解析，`.py` 版永不参与生产导入（存留 `__pycache__/services.cpython-313.pyc` 编译残留）

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 同名遮蔽 | 模块与包同名，Python 导入系统包优先，`services.py` 为影子死代码（B-11 应用级同型）|
| 2 | 双套实现 | `.py` 版（277 行）与包内 4 文件各实现一套 Service，违反 DR-1 |
| 3 | 维护误导 | 改影子不生效；编译残留 `services.cpython-313.pyc` 表明其曾是实时文件 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | 删除影子 `services.py`（277 行），纯文件删除、零行为影响 | `apps/usermanagement/services.py` |
| 2 | 删除其编译产物 | `apps/usermanagement/__pycache__/services.cpython-313.pyc` |
| 3 | 包内 4 个 service（`department/employee/permission/role_service.py` + `__init__.py`）与既有未提交改动（`services/employee_service.py`、`tests/test_service_coverage.py`）不动 | — |

### 四、对抗审查

1. **解析优先级实测**：删除前 `FileFinder.find_spec('services')` 返回 `services/__init__.py`、`is_package=True`；删后符号冒烟（`DJANGO_SETTINGS_MODULE=config.settings.development`）`apps.usermanagement.services.__file__` = `...\services\__init__.py`，识别路径不变
2. **10 个 import 落点全落包**：5 处生产（`views/employee_view.py:26`、`employee_auth_mixin.py:19`、`department_view.py:27`、`role_view.py:30`、`my_permissions_view.py:17`）+ 5 处测试（`test_services.py`、`test_department_service.py`、`test_role_service.py`、`test_service_coverage.py`、`apps/authusermanagement/tests/test_my_permissions.py:27`）；全仓无模块属性式 `import apps.usermanagement.services` 用法
3. **方法清单超集 diff**：影子 `EmployeeService`={create_employee, change_employee_status}、`DepartmentService`={create_department, move_department, _update_children_level, _get_max_child_depth, batch_update_sort_order}；包内 `EmployeeService` 另含 bind/unbind/replace_auth_user/batch_create_employee/batch_delete_employee，`DepartmentService` 另含 batch_create_department/batch_delete_department，且 `_update_children_level` 包版为 `_update_children_paths_and_levels`（含 path 维护）增强替代。影子零独有逻辑，无需抢救
4. **门禁 4 连**：`ruff check apps/usermanagement` 0→0（`All checks passed!`）；`mypy apps/usermanagement --strict` 仅存量 `models.py:122`（`checked 30 source files`，零新增）；`pytest apps/usermanagement -q` 99 passed（基线 99）；`python manage.py check` no issues
5. **残留清理**：全仓 `apps/usermanagement` 内 `services.py` 无残留、`services*.pyc` 清空；`.github/workflows`、`pyproject.toml`、`setup.cfg` 零引用
6. **mypy 非 duplicate-module**：删除前后均正常核验 30 文件（mypy 同样以包为准），删除不会改变类型检查面
7. **回归护栏（建议项，本次未做）**：`scripts/check_duplicate_invariants.py` 已存在但缺 `services.py` 不复现检查；建议仿 G-2 加 `if (BACKEND/"apps"/"usermanagement"/"services.py").exists(): BLOCK`（约 5 行），另立任务实施

### 五、验证记录

```text
① 删除前基线
   pytest apps/usermanagement -q      → 99 passed ✅
   ruff check apps/usermanagement     → All checks passed!（0 错）✅
   mypy apps/usermanagement --strict  → 1 处存量（models.py:122）✅
② 删除后门禁
   pytest apps/usermanagement -q      → 99 passed（净变化 0）✅
   ruff check apps/usermanagement     → All checks passed!（0）✅
   mypy apps/usermanagement --strict  → 仅 models.py:122（零新增）✅
   python manage.py check             → System check identified no issues ✅
③ 符号冒烟（DJANGO_SETTINGS_MODULE=config.settings.development）
   apps.usermanagement.services.__file__ = ...\services\__init__.py ✅
   EmployeeService / DepartmentService 方法全集 = 包版（覆盖影子全集）✅
④ 变更范围（嵌套仓 git status --short -- apps/usermanagement）
   D apps/usermanagement/services.py（本次）+ 2 处既有 M（employee_service / test_service_coverage，未触碰）✅
```

### 六、遗留与关联事项

- **建议项（本次未做）**：护栏脚本补 `services.py` 不复现检查（仿 G-2，约 5 行），可同时覆盖 `apps/assetmanagement`（B-11 已删 5 死文件）防同类 `.py` 复现
- **旧文档行号失效**：`docs/综合审查报告*.md` 引用的 `services.py:527/182/391-418/420-543/498-527` 等行号属更老 527 行版本快照，文件已删除、行号早已失效（历史快照不改写）

---

*登记人：big-pickle ✅ 状态：门禁 4 连全过 + 符号冒烟通过，代码级验证完成，2026-09-20*


## BF-018 【已核实】`views/asset_view.py` 超 DR-5 500 行上限且「无标注」（审查报告 #12 DR-5）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P2 #12）
- **严重级别**：P2（DR-5 文件规模红线）
- **影响范围**：`apps/assetmanagement/views/asset_view.py`；零代码改动
- **登记来源**：审查报告 #12；核实结果——报告描述两点均过时：①「无 `# TECHNICAL_DEBT` 标注」不成立，第 1 行已有 `# TECHNICAL_DEBT: >500 lines`（B12 实施时顺手补上）；②行数 502 非现值，现为 **512**

### 一、核实结论

1. **行数**：`asset_view.py` 共 512 行，确实超 DR-5 500 行上限（超限幅度 2.4%，即 12 行）
2. **标注已存在**：文件第 1 行 = `# TECHNICAL_DEBT: >500 lines`，逐字命中 DR-5「存量超限文件须在头部添加该标注、不触发 `[HALT]`」的豁免条件。存量判定：内容方法可追溯至 2026-07-15 及更早 commit（`--follow`），构成存量基础
3. **无质量热点**：28 个 `def`、20 个 `@action`、平均每方法约 12 行；无巨型函数、无深嵌套
4. **拆分基础设施已存在**：`views/` 包内 `_export_mixin.py`、`_lifecycle_base.py`、`_mixins.py`、`asset_lifecycle_view.py` 为既有拆分先例

### 二、决策（方案 A，用户拍板）

- **采用方案 A（最小达标）**：标注已满足 DR-5 豁免条件，本问题实质已关闭；仅做文档登记，零代码改动
- **方案 B（真拆分）留档**：按 URL 职责切 `_asset_mutation_actions.py`（写操作：change_status / change_outasset_employee / mark_broken / mark_lost / found / repair 三件套，约 `:281-483`），主文件预计降至 ~290 行。**触发条件**：下一次对该文件新增 ≥50 行的功能改动时执行——DR-5「存量文件后续被修改时，若本次新增代码量 ≥ 50 行，必须同步将文件拆分至 ≤ 500 行」条款将其设为强制边界，届时边际成本最低。执行时需同步：mixin 挂载顺序（MRO）、`test_asset_view_api.py` / `test_asset_view_rbac.py` / `test_asset_selector_isolation.py` 全量回归、schema 装饰器与 OpenAPI 文档位置核对

### 三、验证记录

```text
行数                       → 512（超 12 行 / 2.4%）✅
第 1 行标注               → # TECHNICAL_DEBT: >500 lines（存在）✅
方法规模                  → 28 def / 20 @action，无巨型函数 ✅
存量判定                  → --follow 追溯至 2026-07-15 及更早 ✅
代码改动                  → 零（仅报告+活账本登记）✅
```

### 四、遗留与关联事项

- **建议项**：方案 B 拆分，触发条件「下次对 asset_view.py 新增 ≥50 行时强制执行」
- **关联**：#23（`stores/createEntityStore.ts` 501 行）仍为待拆分项，不属本次

---

*登记人：big-pickle ✅ 状态：核实完成、零代码改动、豁免成立，2026-09-20*

---

## BF-019 【已闭环】CT-3 状态机 5 条合法路径零测试覆盖（审查报告 #13）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P2 #13）
- **严重级别**：P2（CT-3 宪法级测试红线）
- **影响范围**：`apps/assetmanagement/tests/test_state_machine.py`（仅追加）；生产代码零改动
- **登记来源**：审查报告 #13；要点——`VALID_TRANSITIONS`（`state_machine/transitions.py:22`）声明 in_store→in_use/broken/lost 等合法的 `outasset`/`cancel_outasset`/`cancel_recycle` 路径，`test_state_machine.py` 原仅覆盖 in_use→broken/lost、recycled_pending→broken/lost 等，余 5 条路径显式用到

### 一、核实结论

1. **原清单 5 条全部确认为真缺失**（非报告过时）：in_store→broken、in_store→lost、outasset（in_store/recycled_pending 双源 → in_use）、cancel_outasset（in_use→previous_status∈{in_store,recycled_pending}）、cancel_recycle（recycled_pending→in_use）。
2. **此前争议澄清**：`TestMarkBrokenFromInUse` / `TestMarkLostFromInUse` 源态为 `in_use`（旧 `test_state_machine.py:99/:122`），与报告所述 in_store 源态缺口无关。
3. **实现要点**：FSM 方法不调 `save()`（`state_machine/core.py:_transition`），直调测试断言内存态（与既有 6 条 direct-call 风格一致）；outasset 终态为 `in_use`（“出库”）。

### 二、修复方案（2026-09-20）

`test_state_machine.py` 追加 10 用例（54 = 基线 44 + 10）：
- `TestOutAssetTransition`：in_store/recycled_pending 双源 → in_use（参数化）。
- `TestCancelOutAsset`：恢复 in_store/recycled_pending（参数化）+ 2 负路径（非法 previous_status="scrapped" / 非 in_use 源态，抛 `InvalidTransitionError`）。
- `TestCancelRecycle`：recycled_pending → in_use + 非 pending 负路径。
- `TestMarkBrokenFromInStore`、`TestMarkLostFromInStore`：in_store → broken/lost 显式路径。

### 三、验证记录

```text
定向 pytest 两文件           → 62 passed（本文件 54）✅
test_out_asset_view_api.py  → 13 passed 零回归 ✅
Service 层覆盖率            → 95.22%（≥90%）✅
顺序全量 1190 passed（并行冲突后重跑恢复）✅
ruff（新增/改动文件）       → All checks passed! ✅
mypy                        → 测试目录在 pyproject exclude=(.*test.*) 豁免 ✅
生产代码 / FSM / 契约       → 零改动，api-schema-baseline.json 无需重导出 ✅
```

### 四、遗留与关联事项

- 并行跑 2 个 pytest 会共享测试库冲突（曾遇 1096 条无误 ERROR），CI/本机须顺序执行。
- 关联 #14（同批 CT-1 补测），已同步闭环。

---

*登记人：big-pickle ✅ 状态：门禁 4 连全绿，代码级验证完成，2026-09-20*


## BF-020 【已闭环】out_asset_service 核心逻辑无独立单测（审查报告 #14 CT-1）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P2 #14）
- **严重级别**：P2（CT-1 宪法级测试红线）
- **影响范围**：`apps/assetmanagement/tests/test_out_asset_service.py`（新建）；生产代码零改动
- **登记来源**：审查报告 #14；要点——`OutAssetService` 无独立单测文件，仅被快照/API 测试间接覆盖；取消出库恢复契约（快照 original_*）在 `test_out_asset_view_api.py` 仅断言 HTTP 200，零数据断言

### 一、核实结论

1. **确无 `test_out_asset_service.py`**；`test_out_asset_view_api.py::test_cancel_outasset:162` 只断言 HTTP 200，快照恢复契约零验证。
2. **`OutAssetService` 的 cancel 方法**：取消走 `batch_delete_outasset([recordcode], ...)`（`out_asset_service.py:199-299`）——`_delete_one` 调 `AssetFSM.cancel_outasset` + 从快照恢复 `original_applicant/manager/using_location` + 仅当 `previous_status==in_store` 且有快照 storage 才恢复仓库（`:280`）。
3. create 契约：`create_outasset(outasset_data, ...)`（`:41`，@staticmethod + @transaction.atomic），非法源态抛 `ILLEGAL_OUTASSET`（`:48-52`）、缺 asset 抛 `MISSING_ASSET_CODE`（`:44-46`）、快照 `original_*` 构建于 `:85-101`、出库后 `asset_storage_recordcode=None`（`:114`）。

### 二、修复方案（2026-09-20）

新建 `tests/test_out_asset_service.py`（63 行 / 8 用例）：
- create 双源成功：previous_status 记录 + `original_*` 快照 + storage 清空 + in_use 流转。
- `ILLEGAL_OUTASSET`（in_use 源态）/ `MISSING_ASSET_CODE` 负路径。
- cancel 恢复契约：in_store → 恢复状态/仓库/原人员/原地点；recycled_pending → 状态回退且不恢复仓库。
- 批量 fail_items 结构：create `ILLEGAL_OUTASSET`、delete `NOT_FOUND`+`id` 键（`core/batch_mixins.py:108-218` 逐字段对齐）。

### 三、验证记录

```text
定向 pytest 两文件           → 62 passed（本文件 8）✅
test_out_asset_view_api.py  → 13 passed 零回归 ✅
Service 层覆盖率            → 95.22%（≥90%）✅
ruff（新增文件）            → All checks passed! ✅
mypy                        → 测试目录豁免 ✅
生产代码 / 契约             → 零改动，api-schema-baseline.json 无需重导出 ✅
```

### 四、遗留与关联事项

- 补充了 `batch_delete_outasset` 对「不存在记录 → NOT_FOUND」的 fail_items 结构断言，为 CT-4 回归护栏。
- 关联 #13（同批 CT-3 补测），已同步闭环。

---

*登记人：big-pickle ✅ 状态：门禁 4 连全绿，代码级验证完成，2026-09-20*


## BF-021 【已闭环】create_damaged_asset TOCTOU 并发竞态 + 唯一槽位软删冲突（审查报告 #15 B5）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P2 #15，靶点 `services/damaged_asset_service.py:51,54`）
- **严重级别**：P2（并发竞态 + Data Integrity）
- **影响范围**：`services/damaged_asset_service.py`、`models/damaged_asset.py`、`migrations/0023_*`（新 FK/约束迁移）、`tests/test_damaged_asset_service.py`
- **登记来源**：审查报告 #15；要点——`DamagedAsset.objects.create`（:51）先于 `select_for_update`（:54）执行，查重（:46）未上锁，窗口 1 并发能插入两条 → 违背 OneToOne 唯一约束。

### 一、核实结论

1. **顺序实证**：`create_damaged_asset` = 查重（:46，无锁）→ create（:51）→ 加锁（:54）。
2. **Window-1 后果修正**：不是 500——全局 `core/exception_handler.py` 捕获 IntegrityError → **400 + 通用文案「数据已存在,请勿重复提交」且丢失业务 error_code `DUPLICATE_DAMAGED_RECORD`**（窗口 2 同理）。防御先例：`hard_disk_sn_service.py:46-55` IntegrityError→业务码。
3. **唯一槽位 × 软删冲突（用户定案方案 X 依据）**：`asset_recordcode` 是 **OneToOneField**（models/damaged_asset.py:60-69），无条件唯一；cancel 软删（`:297`）后行仍在（tombstone）→ `exists_by_asset_code`（is_deleted=False）虽放行，内部 create 仍被唯一约束拦截 → 取消/驳回后**无法重新申请报废**。
4. **其他来源判断修正**：broken/lost 子记录为入口即锁（`asset_lifecycle_mixin.py:37/:101`），非「先 create 后锁」，已合规。
5. **方案 X 语义**：拒绝记录软删 + 拒绝理由留存在 DB（tombstone）；`AssetOperationLog(trigger="reject")` 资产级审计完整；UI 列表/统计/by_asset/导出不再展示已拒绝记录（既定取舍，用户拍板）。

### 二、修复方案（2026-09-20，双 PR）

**PR-1（TOCTOU 重排，零 schema 风险）**——`create_damaged_asset`：
1. `select_for_update` 前置于行首（并发串行于资产行锁）。
2. RBAC `ensure_asset_visible` 移入锁内（锁后实例）。
3. 查重移至锁后（消除窗口 1）。
4. `original_status` 锁后服务端权威覆盖写入 `damaged_data`。
5. 内层 `with transaction.atomic()` + `except IntegrityError`：命中 `asset_recordcode` 键 → `AppValidationError(DUPLICATE_DAMAGED_RECORD) from exc`，其余 `raise`。
6. 删除 `:57-58` 锁后回填 `save`。

**PR-2（唯一槽位释放，含迁移）**：
1. `asset_recordcode`：`OneToOneField` → `ForeignKey(unique=False)`（其余属性保留；反向访问名 `damaged_assets` 全仓零使用面已核实）。
2. `Meta.constraints` 增加 `UniqueConstraint(fields=["asset_recordcode"], condition=Q(is_deleted=False), name="uq_damaged_asset_active_asset")`——仅非软删行参与唯一。
3. `reject_asset_recordcode` 追加 `damaged_asset.delete()`（软删，与 cancel 对齐，标注 `# [HALT]`）。
4. CT-6 三步：① `makemigrations --dry-run` → `No changes detected`；② `migrate --plan` 顺序正确；③ 新迁移含 `AlterField`（隐含 Drop 旧 OneToOne 唯一索引 `am_damaged_asset_asset_recordcode_id_key`）——已人工确认数据无损（dev 0 条，旧约束保证全表每资产至多 1 行）；`findstr RemoveConstraint/RemoveField/RemoveIndex` 无显式命中。

### 三、验证记录

```text
PR-1: 定向 damaged 双套件     → 40 passed ✅
PR-2: 定向 damaged 双套件     → 46 passed（含 6 新用例）✅
邻域套件（recycle/waste/out/lifecycle/selector） → 95 passed ✅
全量 pytest apps              → 1001 passed ✅
Service 层覆盖率             → 95.24%（damaged_asset_service 100%，≥90%）✅
manage.py check              → no issues ✅
ruff（变更 4 文件）           → All checks passed! ✅
mypy（目标文件）             → 0 新增错误（1 条为既有存量）✅
重复护栏 check_duplicate_invariants.py → PASS ✅
CT-6 迁移三步                → ①②③ 全过，迁移已应用 ✅
新用例先红证据               → cancel/reject 形参误传 damaged recordcode；陈旧实例 is_deleted 断言，已修正 ✅
```

### 四、遗留与关联事项

- 新用例覆盖：重提（cancel/reject 后）、软删 tombstone 共存、已批准记录仍阻塞重提、IntegrityError 兜底映射（mock 约定复用 `test_hard_disk_sn_service_integrity.py:27-48`）。
- 对抗审核登记（DR-1 待核查）：`create_damaged_asset` 的 IntegrityError→业务码兜底与 `hard_disk_sn_service.py:46-55` 同构，为全仓第二实例，已按 §1.8 新发现义务登记至 `Rules_Fiels/Duplicate_Codes/complete-patterns.md` 待核查区，建议后续提取公共兜底 helper。
- 「拒绝记录软删 + 拒绝理由留守 DB」决策：已同步报告 #15 行 + 本登记；前端「已拒绝」状态筛选项将因数据源消失而恒空，属方案 X 既定取舍。
- 关联 #13/#14 同批闭环。

---

*登记人：big-pickle ✅ 状态：门禁全绿，代码级验证完成，2026-09-20*

---

## BF-022 【已闭环】View 的 update/partial_update 裸传 request.data 绕过 Serializer 输入校验（审查报告 #16 B8）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P2 #16，靶点 `views/damaged_asset_view.py:130-150` + `views/out_asset_view.py:197-203`）
- **严重级别**：P2（输入校验失效 + 行级 RBAC 缺口 + 契约漂移风险）
- **影响范围**：`views/damaged_asset_view.py`、`views/out_asset_view.py`、`serializers/out_asset_serializers.py`、`serializers/damaged_asset_serializers.py`、`tests/test_damaged_asset_view_api.py`、`tests/test_out_asset_view_api.py`、`api-schema-baseline.json`
- **登记来源**：审查报告 #16；要点——update/partial_update 把 `request.data` 直塞 Service，Serializer 仅用于响应渲染；非法数据类型/未知字段全部绕过 DRF 校验（Service 层再兜 400，重复处理且语义漂移）；out_asset 侧未走 `get_object()`，行级 RBAC 过滤缺失。

### 一、核实结论

1. **反模式范围（全仓共 3 处，本次修 2 处）**：`rg update_data=request.data` 共 3 命中——damaged ×2 + out_asset ×1；`asset_view.py:146-149`、`hard_disk_sn_view.py:77-79`、`recycle_asset_view.py:131-133` 均已正确走 serializer，修复目标即与全仓既有约定对齐。
2. **缺口 A（out_asset）**：`outasset_using_location` 不在 `OutAssetUpdateSerializer.fields`，但 Service 白名单 `OUTASSET_UPDATE_ALLOWED_FIELDS` 含之 → 已声明的可写字段在 API 层静默失效（前端 PUT 携带即被 `FIELD_NOT_ALLOWED` 拦截 400）。
3. **缺口 B（未知字段语义漂移）**：damaged 侧旧无 serializer 门禁存在 → 未知字段 200 静默忽略；out_asset 走 Service `FIELD_NOT_ALLOWED` → 400。两端输入语义不一致。
4. **RBAC 缺口（out_asset update/partial_update）**：直接调 `OutAssetService.update_outasset(recordcode, request.data, ...)`，未走 `get_object()` → 拥有更新权限者可跨数据范围写任意 `recordcode`；damaged 侧 update 已走 `get_object()`，为对照正确实现。
5. **零回归前提核实**：OutAsset 模型 `outasset_description`/`return_date`/`outasset_using_location` 均 `null/blank=True`，`outasset_number/type/date` 有 default + extra_kwargs `required=False`；damaged 的 `damaged_asset_description` 为 blank 且 ModelSerializer 自动 `required=False`，既有 PUT 单字段用例不会转 400。

### 二、修复方案（2026-09-20）

1. `damaged_asset_view.py` update/partial_update：`self.get_serializer(obj, data=request.data, partial=(self.action == "partial_update"))` + `is_valid(raise_exception=True)` → `serializer.validated_data` 给 Service；响应序列化器不变。
2. `out_asset_view.py` update/partial_update：同样 serializer 门禁 + 补 `self.get_object()`（行级 RBAC）；`partial_update` 独立实现 `partial=True`，不再转调 `update`。
3. `OutAssetUpdateSerializer`：`fields` 追加 `outasset_using_location`（Gap A 决策：保留可写，用户拍板）——Serializer 可写集 == Service 白名单逐字段对齐，`FIELD_NOT_ALLOWED` 分支变不可达纯兜底。
4. `DamagedAssetUpdateSerializer`：`extra_kwargs` 加 `asset_recordcode`/`is_active` 为 `read_only`（可写集收窄至 Service 白名单 3 字段）。
5. 未知字段（Gap B）决策：**静默忽略**（DRF 默认 + Service 强制兜底），两端统一；out_asset 的 `FIELD_NOT_ALLOWED` 400 → 200 语义变更已随测试锁定并留痕。

### 三、验证记录

```text
既有 view 套件（4）→ 新 6 用例   → 30 passed ✅
全量 pytest apps                → 1007 passed ✅
Service 层覆盖率                → 95.24%（damaged_asset_service 100%，≥90%）✅
ruff（4 文件，含 C90 max-complexity 10）→ All checks passed! ✅
manage.py check                 → no issues ✅
mypy（改 4 源文件）             → 0 新增错误（仅 out_asset_serializers.py:216/219 存量）✅
重复护栏 check_duplicate_invariants.py → PASS ✅
rg update_data=request.data     → 全仓 0 残留 ✅
api-schema-baseline.json        → 已重导（M-3），diff 逐字段符合预期 ✅
新 6 用例                       → 一次全绿（负路径 400×2 + is_active 只读 + using_location 可写 + 未知字段忽略×2）✅
```

### 四、遗留与关联事项

- 校验后置依赖已消除：本修复前「Service 白名单负责输入约束」为契约漂移（合法字段 outasset_using_location 被误拦，非法字段被误放）。修复后校验单一来源 = Serializer 声明（DR-1 对齐）。
- `FIELD_NOT_ALLOWED` 分支保留为不可达纯兜底（不删除，防 Service 被其他入口直调时静默吞字段）。
- 存量单模块覆盖率缺口（out_asset_service 83% / recycle_asset_service 88%，整体已 ≥90% 达标）：本次改动仅涉及 View/Serializer 与输入契约，未触及 Service 代码路径，缺口非本次引入，另立任务跟进。
- 关联 #15 同批闭环；报告行 16 已划线。
- [SKILL 建议] 活账本 BF 登记流程（发现→核实结论→方案→验证记录→留痕）已在 BF-020/021/022 重复三次，建议封装为可复用 skill：「bug-ledger-entry」（触发：任一审查报告条目闭环并需活账本登记）。
  > 已落地为 `.opencode/skills/resolution-fix-ledger-sync`（2026-09-23，原「bug-ledger-entry」提案差额并入该 skill）

---

*登记人：big-pickle ✅ 状态：门禁全绿，代码级验证完成，2026-09-20*

---

## BF-023 【已闭环】View 层 batch_delete 业务编排违反分层（审查报告 #17 §1.2）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P1 #17，靶点 `views/_lifecycle_base.py:100-134`）
- **严重级别**：P1（分层违例 + 批量框架与错误分类在此视图重复实现，DR-1/三视图集一致性风险）
- **影响范围**：`views/_lifecycle_base.py`、`views/repair_asset_view.py`、`services/asset_lifecycle_mixin.py`、`tests/test_batch_contract_snapshot.py`、`tests/test_asset_lifecycle_service.py`（新建）、`tests/test_lifecycle_view_api.py`、`api-schema-baseline.json`
- **登记来源**：审查报告 #17；要点——`batch_delete` 在 View 层手写 `for` 循环 + 三类异常分类 + dict 组装（total/success_count/fail_count/success_ids/fail_items），独立于全仓批量框架（`core/batch_mixins.py` `BatchOperationMixin`/`BatchResponseHelper`）手写第三套实现。

### 一、核实结论

1. **反模式确认**：`_lifecycle_base.py:99-134` 为手写循环（`except DoesNotExist → NOT_FOUND "Record not found"`、裸 `except Exception → INTERNAL_ERROR "Server error"`）；全仓 8 端点（asset/out/recycle/waste/storage/contract/damaged 等）早已统一走 `BatchOperationMixin.batch_delete_execute` + `BatchResponseHelper.delete_response`（标准文案 `批量删除完成,成功 X 条,失败 Y 条` 锁于 `test_b5_baseline_snapshot.py`）。
2. **事实修正**：报告「批量删除唯独留在 View」不准确——`repair_asset_view.py:174-192` 已直接调 `BatchOperationMixin.batch_delete_execute`，其 `_delete_one` 闭包与错误分类仍内联于 View（同款反模式）→ 用户拍板一并收敛。
3. **单删正确实现为收敛基底**：`delete_broken_asset`/`delete_lost_asset`/`delete_found_asset`（`asset_lifecycle_mixin.py:239/262/285`）为原子+`select_for_update`+审计的唯一实现，抛 `model.DoesNotExist`，**无 user/RBAC 参数**。
4. **契约快照风险**：`test_batch_contract_snapshot.py:56/:71` 锁定旧英文文案；`RepairAssetViewSet` 零批量删除测试覆盖。
5. **前端零依赖**：仅消费 data 键集 + 载荷 `{ids}`，无 message 文案硬编码；`createEntityStore.removeBatch` 做结构校验。
6. **global handler**：`AppValidationError(error_code=...)` 的 error_code **不暴露**响应体（`core/tests/test_exception_handler.py:33-38`），400 语义安全。

### 二、修复方案（2026-09-20，用户拍板①中文统一文案 ②repair 一并收敛）

1. `services/asset_lifecycle_mixin.py`：新增 `@staticmethod` `batch_delete_lifecycle_asset`/`batch_delete_repair_asset`（`# [HALT]`），逐条 `transaction.atomic` 调既有 `delete_*_asset`；`DoesNotExist → AppValidationError(NOT_FOUND, "记录 X 不存在")`；`REPAIR_IN_PROGRESS` 原样透传（不重定义业务文案，DR-1）；Exception 兜底 `logger.error` + `INTERNAL_ERROR`。
2. `views/_lifecycle_base.py`：整段收敛至 Service 入口 + `BatchResponseHelper.delete_response`；保留 `if not ids → 缺少 ids 参数`。
3. `views/repair_asset_view.py`：收敛 `batch_delete_repair_asset` + `BatchResponseHelper.delete_response`；移除内联 `_delete_one` 与 `BatchOperationMixin` import。
4. 行为变更清单（已留痕）：lifecycle 文案英文→中文；repair 文案静态→动态；repair 缺失记录 `INTERNAL_ERROR`→`NOT_FOUND`；lifecycle >100 条静默→400 `BATCH_SIZE_EXCEEDED`；补 `logger.error`。

### 三、验证记录

```text
定向 3 套件                                → 47 passed ✅（新 7 服务用例 + 1 视图冒烟）
先红证据                                   → git stash 反转旧英文断言对新代码 2 FAILED ✅
邻域套件（状态机 + 生命周期 selector）       → 47 passed ✅
全量 pytest apps                          → 1015 passed（#16 基线 1007 净增 8）✅
Service 层覆盖率                           → 95.32%（≥90%）✅
ruff（含 C90 max-complexity 10）           → All checks passed! ✅
mypy（3 源文件）                           → 0 新增错误（22 条为依赖/存量方法行）✅
manage.py check                           → no issues ✅
重复护栏 check_duplicate_invariants.py    → PASS ✅
grep 收尾（success_ids/fail_items/BatchOperationMixin in _lifecycle_base）→ 0 残留 ✅
api-schema-baseline.json                  → 已重导（M-3），仅非破坏性 description 变更 ✅
```

### 四、遗留与关联事项

- `delete_*_asset` 系列无 user/RBAC 参数：单删行级守卫依赖 View `get_object()`，批量入口亦无 RBAC 参数；与 Service 层 `select_for_update` 组合仅做存在性/合法性守卫，未做跨数据范围校验——留档后续统一（不进本次范围）。
  - **更正（2026-09-23）**：已闭环——四个 delete 方法（`asset_lifecycle_mixin.py:194/:234/:263/:292`）均已加 `user` 尾参 + `ensure_asset_visible` 行级校验，批量闭包透传 `user`（:385/:411）；View 侧 destroy/批量均传 `request.user`。见 complete-patterns **A-31**（批次①，v2.9.39）。
- destroy 硬删 vs batch 软删语义不对称（destroy 走物理删除、batch 走 `is_deleted` 软删）；broken/lost/found 无 BatchDeleteSerializer，`if not ids` 守卫与 repair 的 serializer 门禁不对称——建议后续统一批量入口校验（`RepairAssetBatchDeleteSerializer` 复用点）。
  - **更正（2026-09-23）**：已闭环——`_lifecycle_base.py:105-114` 显式覆写 `destroy`（软删+审计+`user=request.user`），替代原物理删除（A-31 批次②a，v2.9.40）；broken/lost/found 各有 BatchDeleteSerializer（`asset_lifecycle_view.py:59/:92/:127`），底层统一 `BaseBatchDeleteSerializer`。见 complete-patterns **A-32**（批次③，v2.9.42）。
- 标准文案稳定性：`test_b5_baseline_snapshot.py` 锁定全仓 13 端点 `批量删除完成,成功 X 条,失败 Y 条`，后续任何端点改动不得触碰此处。
  - **复核（2026-09-23）**：护栏在位无动作——`test_batch_contract_snapshot.py:62` 断言 message 逐字锁定 `批量删除完成,成功 1 条,失败 0 条`，:7-12 头部明确"断言失败=契约破坏需回滚"；批次③（A-32）骨架 message 模板统一复用，未触碰快照契约。
- [SKILL 建议] 活账本 BF 登记已在 BF-020/021/022/023 重复四次，复用 BF-022 已提的「bug-ledger-entry」skill 建议，本次不再重复。
  > 已落地为 `.opencode/skills/resolution-fix-ledger-sync`（2026-09-23，原「bug-ledger-entry」提案差额并入该 skill）
- 关联：报告行 17 已划线。

---

*登记人：big-pickle ｜ 状态：门禁全绿，代码级验证完成，2026-09-20*

---

## BF-024 【已闭环】BR-4 长函数治理无门禁兜底——函数行数门禁固化 + 台账分批拆分规划（审查报告 #21）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P2 #21）
- **严重级别**：P2（规则级：函数 >50 行超限靠评审/报告人工发现，无 CI 兜底，新增回潮无拦截）
- **影响范围**：`scripts/check_function_length_guard.py`（新增）、`Rules_Fiels/BR4_function_length_ledger.md`（新增）、`asset_management_backend/pyproject.toml`、`Rules_Fiels/backend-business-rules.md`、`.github/workflows/duplicate-guard.yml`
- **登记来源**：审查报告 #21；要点——报告点名 4 处超长函数但计数过时，实测口径需修正，且 ruff 无函数**行数**规则（`PLR0915` 为语句口径，偏差可达 40%+），纯靠复审无门禁。

### 一、问题现象

1. `backend-business-rules.md:233` BR-4 明文「>50 行须拆 _helper」，但 `pyproject.toml:79-100` `lint.select` 仅 E/W/F/I/B/C4/UP/RUF，无 PLR/C90 → 超限**零 CI 拦截**。
2. 报告 #21 原「13 处」计数口径不统一且过时：AST 实测物理行口径 **38 处**、BR-4 语义逻辑行口径 **19 处**（差异源于空行/注释/ docstring 计数方式）。
3. `PLR0915`(too-many-statements) 属语句口径，与 BR-4 行数语义最大偏差可达 40%+（如 `_delete_one` 物理 94 行 ↔ 语句 ~57），不可直接用作 BR-4 门禁。

### 二、根因（表格式）

| # | 环节 | 事实 |
|---|------|------|
| 1 | 规则配置 | `pyproject.toml:79-100` 未启用任何函数长度/复杂度规则；`RUF` 已选中且 `fixable=["ALL"]`，若具名 noqa 而无对应启用规则会触发 RUF100 |
| 2 | 规则语义 | `backend-business-rules.md:233` 定义「不含空行和注释」的行数口径；ruff `PLR0915` 为语句数口径，两者不等价 |
| 3 | 计数失真 | 报告 #21 原「13 处」为偏小口径；实测物理行 38 / 逻辑行 19（guard `--print` 全量 835 函数抽样） |
| 4 | 无门禁 | 此前无 AST 扫描脚本，无台账，超限仅靠人工评审报告记录 |

### 三、修复方案（2026-09-21，门禁先行）

| # | 变更 | 文件 |
|---|------|------|
| 1 | 新增 BR-4 guard：AST 语义节点扫描 `apps/`（不含迁移/tests），逻辑行口径（物理跨度 − 空行 − `#` 注释，docstring 计行）>50 即超限；台账双向断言（超限未登记即红、已拆分未移除即红）；`--print` 全量导出 | `scripts/check_function_length_guard.py` |
| 2 | 19 条台账（B1 状态机关键路径 6 / B2 usermanagement+unregisteredasset 9 / B3 selectors+services 尾部 4），行号由 guard 生成不手抄 | `Rules_Fiels/BR4_function_length_ledger.md` |
| 3 | `lint.ignore` 显式加 `PLR0915`（防御性，防未来启用 PLR 被存量淹没；避免双轨口径） | `asset_management_backend/pyproject.toml` |
| 4 | v1.14 changelog：计数口径定义 + guard 实施方式 + `[PATCH-BE]` 留痕（实施固化，非规则文本修改） | `Rules_Fiels/backend-business-rules.md` |
| 5 | CI 追加 `function-length-guard` job（stdlib-only，push/PR 执行） | `.github/workflows/duplicate-guard.yml` |

### 四、对抗审核

- **行号漂移**：台账行号全部由 guard `--print`（AST `node.lineno`）导出，非手工复制报告旧行号；`rg` 抽查 `recycle_asset_service.py:41`/`out_asset_service.py:204`/`asset_selector.py:307` 等 5 处全部一致 ✅
- **虚报验证**：guard PASS、负向 A/B、ruff 通道均已实际执行；⚠️ 全量 `pytest` **未运行**——本提交零业务 `.py` 变更，如实标注而非虚报"通过"
- **口径发现（超越原任务）**：实测暴露报告「13 处」口径失真 → 已同步修正报告 #21 行、台账头部规模说明、v1.14 changelog（物理 38 / 逻辑 19）
- **契约影响**：无跨端契约、无迁移、无 schema 变更；纯门禁 + 文档
- **登记遗漏检查**：同步三处（报告 #21 行 + 修复追踪 5 行 + 本 BF-024）；`complete-patterns.md`（§1.8 重复代码活账本）**不适用**——函数长度非重复模式，明确排除 ✅

### 五、验证记录

```text
① guard 正常跑                          → PASS（19 个超长函数 / 13 个文件全部登记，exit 0）✅
② 负向 A：台账剔除 create_recycle_asset  → FAIL「未登记超长函数」19 处全报教训后回归 PASS ✅
③ 负向 B：台账插入"行数 45"条目           → FAIL「台账条目非法 45<=50」+ 其余未登记 17 处 ✅
④ guard --print 全量                     → 835 函数中逻辑行>50 恰为 19 条，与台账一一对应 ✅
⑤ ruff check（完整后端）                 → 7 处存量（test_ws_consumer F401 + loadtest E402/I001），目标目录 0 新增 ✅
⑥ workflow YAML 结构                     → duplicate-guard.yml 校验通过 ✅
⑦ 全量 pytest                           → 未运行（零业务代码变更，如实标注，非"通过"）
```

### 六、遗留与关联事项

- **19 处拆分（后续提交，台账驱动）**：B1 Top5 状态机关键路径（create_recycle_asset/create_outasset/batch_delete_outasset+_delete_one/approve_asset_recordcode/move_department）→ B2 usermanagement+unregisteredasset → B3 selectors+services 尾部；每批拆前/拆后跑 `pytest apps/assetmanagement -q` + `apps/usermanagement -q` 与覆盖率 ≥90%，guard 5 处出台账。
- ruff 存量 7 处（tests+loadtest）非本项射程，另立清理。
- [待确认] BR-4 口径明确定义：docstring 计入代码行（`#` 注释行不计）。若后续裁决 docstring 亦不计入，guard `logical_line_count` 一处即可调整，台账计数随之重导。
- 关联：报告 #21 行已划线、修复追踪 5 行已追加。

---

*登记人：big-pickle ｜ 状态：门禁落地全绿，验证完成（拆分部分按台账分批推进），2026-09-21*

---

## BF-025 【已闭环】BR-4 函数拆分全批次（B1 状态机关键路径六函数 / B2 usermanagement+unregisteredasset 9 处 / B3 selectors+services 尾部 4 处）拆至 ≤50 行

- **发现日期**：2026-09-21（BF-024 遗留「19 处拆分（后续提交，台账驱动）」→ 本项为 B1 执行部分）
- **严重级别**：P2（规则级：函数 >50 行超限；本项为拆分执行，非新增缺陷）
- **影响范围**：`asset_management_backend/apps/assetmanagement/services/{out_asset,recycle_asset,damaged_asset}_service.py`、`apps/usermanagement/services/department_service.py`、`tests/test_recycle_asset_service.py`、`Rules_Fiels/BR4_function_length_ledger.md`
- **登记来源**：台账 B1 六条（guard `--print` 逻辑行：create_recycle_asset 103 / create_outasset 85 / batch_delete_outasset 76 / _delete_one 71 / approve_asset_recordcode 56 / move_department 55）

### 一、问题现象

guard 语义口径下六函数逻辑行 >50，且 `batch_delete_outasset`（76）内含嵌套闭包 `_delete_one`（71），嵌套 body 计入外层计数，线性抽取无法清零外层 → 必须 hoist。

### 二、拆分方案（台账驱动，helper 名以 guard 实测为准）

| 原函数（逻辑行→拆后） | helper 产物 |
|:---|:---|
| create_recycle_asset（103→38） | `_normalize_recycle_input`（+`OUTASSET_ASSET_MISSING` 防御守卫）→ `_normalize_recycle_refs`；`_finalize_broken_or_lost`（broken/lost 双分支 **DR-1 合并**，trigger/to_state/子记录类 & fallback_jobcode 语义保持） |
| create_outasset（85→26） | `_validate_outasset_source`、`_build_outasset_snapshot`（P0-2 快照契约纯函数）、`_apply_outasset_to_asset`（锁+FSM+定向 save，返回新锁定 asset 供审计） |
| batch_delete_outasset（76→10） | **hoist**：`_delete_one` 提升类级 staticmethod（operator 参数化，外层 lambda 适配 `batch_delete_execute`） |
| _delete_one（71→27） | `_restore_asset_fields`（original_* 优先/落空置 None/in_store 才恢复仓库，loop 化降复杂度 13→7）+ `_resolve_snapshot_employee` |
| approve_asset_recordcode（56→44） | `_notify_waste_approved`（P1-8 transaction.on_commit 通知，不提前） |
| move_department（55→25） | `_validate_move_hierarchy`（循环/深度校验返回 new_level）、`_move_to_root`（根移动+子孙级联） |

### 三、对抗审核

- **先红后绿**：拆分落码但台账未移除 → guard FAIL（6 条「已拆分未移除」+ `_finalize_broken_or_lost` 51 行未登记）→ docstring 压缩至 49 + 台账同提交移除后 PASS ✅
- **类型修复**：mypy 曝光 recycle 返回注解 `OutAsset`→`Asset` 错误（FK 可空），补 None 守卫置 `Asset`；dept 参数 `str|None`→`str`（调用处已收窄）；`_restore_asset_fields` 参数 `AssetStatus`→`str`（DB 字段实际 str）零行为影响 ✅
- **C90 复杂度**：`_restore_asset_fields` 13>10 → loop+`_resolve_snapshot_employee` 拆分至 7/5；`_normalize_recycle_input` 11>10 → `_normalize_recycle_refs` 拆分至 9 ✅
- **DR-1 双分支合并等价性**：broken/lost 审计断言（trigger/to_state/子记录类/fallback_jobcode）与合并前逐字一致，`test_recycle_asset_service.py` 原样通过 ✅
- **契约影响**：纯 Service 层内部重构，API 响应/端点/状态枚举/schema 零变化，`api-schema-baseline.json` 无需重导出 ✅
- **Test 数据库残留**：首跑 `test_asset_management_backend` 已存在（环境残留）→ `--create-db` 重建后全绿，非代码问题 ✅

### 四、验证记录

```text
① guard FAIL→PASS                  → 先红 6 条「已拆未移除」→ 台账移除后 PASS（13 函数/9 文件）✅
② 全量 pytest apps                 → 1017 passed（assetmanagement 724 + usermanagement 99 定向 + 其余含 unregisteredasset）✅
③ Service 层覆盖率                 → 96%（≥90%；recycle 91 / out 90 / damaged 100 / department 100）✅
④ ruff / C90                       → 0 新增；mypy 4 目标文件 0 新增（存量 asset_lifecycle_mixin 6 与本次无关）✅
⑤ 防御分支补测                     → TestDefensiveBranches 2 用例（二次 FSM 失败 INVALID_STATE_TRANSITION / 无关联资产 OUTASSET_ASSET_MISSING），recycle 覆盖 89%→91% ✅
⑥ 台账同步                         → B1 六行移除、头部 19→13、行号零漂移，guard 双向断言一致 ✅
```

### 五、遗留与关联事项

- **B2（usermanagement+unregisteredasset 9 处）/ B3（selectors+services 尾部 4 处）**：设计已固化于台账，按批推进，每批拆前/拆后跑定向套件 + 覆盖率 ≥90% + guard 出台账。
- **弱测试锚（拆分前须补，CT-4）**：`views.batch_delete`、`bind_auth_user`/`replace_auth_user`、`_handle_s1/s3` 无直接行为测试 → B2 前补回归用例。
- 关联：报告 #21 追踪追加 4 行、台账 B1 六行移除、BF-024 遗留项部分闭环；commit/push 待用户确认后执行。

### 六、B2/B3 收口补充（2026-09-23 状态订正）

> 本条目登记于 09-21 B1 完成时点，后续 B2/B3 已于同日（2026-09-21）完成并经人工分批落地，此处回写收口证据（含 commit），状态由【进行中】转【已闭环】。

**B2 落地**（usermanagement 4 + unregisteredasset 5，共 13 函数拆分 + 1 新增）：

- 弱测试锚先补（CT-4/CT-3）：`test_batch_delete_view.py`（views.batch_delete 成功/四种失败结构/权限 7 条）、`test_handlers.py`（`_handle_s1`/`_handle_s3` 直接行为锚 + 三表/result_* 关联持久化 3 条）、`test_service_coverage.py` 增 bind/unbind/replace 审计日志锚 3 条 —— commit `9191c6e`（backend）。
- 拆分落码：`66c77fb`（handlers S1/S2/S3 拆分 + DR-1 共享 helper）、`0090f43`（bind/replace/unbind 拆分 + 共享 helper）、`8595605`（assign_role 拆分 + helper）、`729f541`（unregistered services create/update/approve 拆分 + `batch_delete_unregistered`）、`43f8997`（视图 batch_delete 下沉薄封装）。
- 回归：usermanagement+unregisteredasset 定向 49 passed + 全量 assetmanagement 726 / usermanagement 99 / unregisteredasset 194；guard FAIL→PASS（先红「已拆分未移除」逐条命中后同提交移除）；mypy 全仓 26 存量零新增；`views.batch_delete` 拆分目标已由 A-32（`BatchDeleteViewMixin` 13 端点统一骨架）取代，见台账 B2 注记。

**B3 落地**：

- `48ae68a`（log_operation 65→36）、`6a5ceb2`（create_asset_type 59→36）、`666ad77`（combine_search 55→18）、`d0a3b52`（mark_asset_broken/lost 双胞胎统一 `_run_lifecycle_transition`，B-23 关闭）+ `eab74dd`（B-22 审计留痕 `_safe_call_audit` 收敛）。
- 回归：全量 pytest apps 914 passed；guard **0/0，BR-4 存量清零**；mypy 20 存量全与他文件相关；duplicate invariants PASS。
- 台账：B2 九行 + B3 四行全部移除，头部「19 处」→「0 处」；`Rules_Fiels/BR4_function_length_ledger.md` line 12/14 完成注记。

**当前实证**：`python scripts/check_function_length_guard.py` → PASS（0 未登记 / 0 台账超限，exit 0）；B2 九个目标函数现逻辑行全 ≤50（assign_role 27 / bind 35 / replace 37 / unbind 33 / S1 29 / S2 28 / S3 31 / batch_create_unregistered 35 / batch_delete_unregistered 34 / approve_and_handle 28）。

**跨端契约**：均为纯 Service/视图层内部重构，API 响应/端点/状态枚举/schema 零变化，`api-schema-baseline.json` 无需重导出（B1/B2/B3 三批均确认）。

*登记人：big-pickle ｜ 状态：B1/B2/B3 全批次拆分完成 + 门禁全绿（guard 0/0、pytest 全量、Service 覆盖率 ≥90%、ruff/C90/mypy 零新增），2026-09-21 落地、2026-09-23 由【进行中】收口为【已闭环】*

## BF-026 【已关闭】`LoginDialog.vue` 死代码孤儿组件——登录弹窗表单从未提交（审查报告 #29 SC-1）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P2 #29）
- **严重级别**：P2（SC-1 指控；核实后定性修正为「死代码孤儿组件」，非安全隐患）
- **影响范围**：`vue-assetmanagement/src/components/LoginDialog.vue`（93 行，删除）；连带清理 `src/App.vue:7` doc 注释、根 `components.d.ts`（:123/:277）、`src/components.d.ts`（:57/:124）
- **登记来源**：审查报告 #29；核实结果——「安全隐患」不成立（SC-1 误定性），根因为无意义死代码

### 一、核实结论

1. **纯死 ref**：`userName`/`userPassword`（:16-17）自创建以来从未被读取/提交/校验；唯一动作 `toLogin()`（:19-24）仅 `visible=false + router.push('/login')`。输入值只存在于内存 ref，点「登录」即丢弃。
2. **SC-1 误定性**：值不发网络、不落 localStorage/console，无泄露通道；真风险为 UX 欺骗（弹窗让用户以为在此登录，实际空操作后跳 /login 重新输入）。
3. **孤儿组件**：@usedBy 自述「当前未被引用，预留登录入口组件」；全仓 src **0 运行时 import/模板使用**（仅 App.vue:7 doc 注释 + 两个 unplugin 生成的 components.d.ts 声明 + 设计审计文档历史记录）。
4. **预留被证伪**：真实登录链路 = /login 路由（LogIn.vue 完整表单含 auth_username/password/rememberMe + guards.ts 白名单），与本组件无交互；弹窗式登录无接入计划。

### 二、决策（方案 B，彻底删除）

- 死代码 + 孤儿 + 误导 UX，无保留价值 → 整文件删除。
- `components.d.ts` 手清悬空声明：**type-check（vue-tsc）不触发 vite 插件再生**，`src/components.d.ts` 被 tsconfig include，悬空 `typeof import('./components/LoginDialog.vue')` 会致 TS2307，必须手动移除后再跑 type-check；根 `components.d.ts` 不在 include 范围，为干净起见一并手清；下次 dev/build 插件再生自动保持干净。
- **可逆留证**：单文件删除可从 git 历史随时恢复；未来真需弹窗登录时大概率走 authStore.logIn，此壳无复用价值。

### 三、验证记录

```text
npm run type-check              → 0 错误（手清两 d.ts 悬空声明后，先清后查）✅
npm run lint / format:check     → 0 / Prettier 全绿 ✅
vitest 冒烟 src/components+views → 205 passed（14 文件）✅
全量 npm test                   → 1912 passed（135 文件，零回归）✅
grep LoginDialog                → 源码与生成 d.ts 零残留；仅 3 处历史文档留档 ✅
路由/契约                       → /login + LogIn.vue + guards.ts 白名单零触碰 ✅
```

### 四、遗留与关联事项

- 设计审计核验.md:35/:113 与 style-optimization-proposal.md:432 为历史记录，保留留档（记录组件曾存在于对应核查时点）。
- 无契约变化，`api-schema-baseline.json` 无需重导出；前端三项检查 + 全量测试门禁已全绿，提交待用户确认。

*登记人：big-pickle ｜ 状态：已关闭（删除完成 + 门禁全绿），2026-09-21*

## BF-027 【已关闭】recyclable 未分页 fallback 返回裸列表，与 list 响应形状不一致（审查报告 #30 §3）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P2 #30）
- **严重级别**：P2（§3 响应形状不一致；核实后定性为「不可达死代码的形状不对称」，非活动缺陷）
- **影响范围**：`apps/assetmanagement/views/out_asset_view.py:172`（单行对齐）；连带修正 `core/pagination.py:27` 陈腐 docstring；新增/加固 `apps/assetmanagement/tests/test_out_asset_view_api.py` 2 用例
- **登记来源**：审查报告 #30；核实结果——代码级不一致成立，但「触发条件」不成立（见下）

### 一、核实结论

1. **代码级不一致真实存在**：recyclable 未分页 fallback（:171-172）返回裸列表 `data=serializer.data`；同文件 list（:181-182）返回 `data={"count": queryset.count(), "results": serializer.data}`。
2. **触发条件不成立（关键纠偏）**：`CustomPageNumberPagination.paginate_queryset`（core/pagination.py:39-60）无 `page`/`page_size` 时注入 `page=1` 后强制 super() 分页；DRF `get_page_number` 缺参默认 1、`get_page_size` 恒回落默认 20；`paginate_queryset` 仅于 `not page_size` 时返回 None——**对任何 HTTP 请求绝不返回 None**，裸列表分支为不可达死代码。报告原「任何不带 page 的调用都会踩中裸列表」不会发生。
3. **误导源**：core/pagination.py:27 docstring「无分页参数时返回全部数据（不分页）」为 P2-28 修复前旧行为，现与 :47-57 实际行为自相矛盾。
4. **前端契约**：`usePagedList.ts:24/:72-73` 无条件读 `response.results`/`count`；若裸列表真到达会静默坏数据——该风险在现行分页实现下不可触发，但死分支保留错误形状会随未来分页行为变更随时引爆。

### 二、决策（方案 B：单行对称对齐 + 陈腐文档修正）

- 死代码分支防御性对称：fallback 与 list 逐字节对齐（DR-3 契约一致性），未来若分页行为允许返回 None 时形状即正确。
- 修正 pagination.py:27 陈腐 docstring，消除误导源。
- 前端零改动（契约已按 PaginatedResponse 声明）。

### 三、验证记录

```text
先红后绿                    → stash 还原旧码，mock.patch.object(OutAssetViewSet,'paginate_queryset',
                              return_value=None) 直驱分支 FAIL（裸列表）→ 恢复修复 PASS（envelope）✅
定向 pytest --create-db      → test_out_asset_view_api.py 17 passed（原 15 +2）✅
全量 pytest apps --create-db → 1031 passed ✅
ruff check                  → 0（1 处 import 顺序 --fix）✅
manage.py check             → 0 ✅
mypy scoped                 → 目标文件 0 错误；存量 16 vs 修复后 16，零新增 ✅
带 page 正常分页路径         → 逐字节不变；schema 无变化，api-schema-baseline.json 无需重导出 ✅
```

### 四、遗留与关联事项

- pagination.py:27 陈腐 docstring 系本次登记根因之一；全仓其余 list 端点（对照组）fallback 同为不可达死代码但形状已正确，无需改动。
- 无契约变化，前端零改动；跨端契约未破坏。

*登记人：big-pickle ｜ 状态：已关闭（单行对齐 + 测试 + 门禁全绿），2026-09-21*

## BF-028 【已关闭】状态机 docstring 漏 in_use 源态 + reject_to_* 死代码误报纠正（审查报告 #31/#32）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P3 #31/#32）
- **严重级别**：P3（#31 纯文档缺陷；#32 误报纠正）
- **影响范围**：`state_machine/broken_lost_repair.py:27/:44`（docstring 2 行）；`state_machine/scrapping.py:20-21`（防误报注释）；报告/追踪/活账本
- **登记来源**：审查报告 #31/#32；核实结果——#31 属实、纯文档补齐；#32 结论「不删」成立但论据需修正（见下）

### 一、核实结论（#31）

1. **属实**：`mark_broken`（:27）/`mark_lost`（:44）方法 docstring 仅列 `(in_store|recycled_pending)`，漏 `in_use`。
2. **权威对照**：transitions.py 三源态均定义 mark_broken/mark_lost（IN_STORE :26-27 / IN_USE :33-34 / RECYCLED_PENDING :39-40）；constants.py:13-14 模块图已含 `in_use`；CT-3 显式 in_use 路径测试（test_state_machine.py:95-137）；消费侧 asset_lifecycle_mixin.py:101/:127、recycle_asset_service.py:162/:164。
3. 类 docstring :18 仅列方法名，无状态枚举，无需改。

### 二、核实结论（#32，误报纠正）

1. **归属不准**：scrapping.py"131-186 5 个"不实——scrapping.py 仅 3 个（in_use :132 / recycled_pending :157 / repairing :173）；reject_to_broken/lost 在 broken_lost_repair.py:74-104。
2. **论据修正**：「经 _REJECT_TARGETS+_transition 动态分派到达 5 方法」不成立——`core.py:_transition`（:71-85）仅校验后直接赋值、`reject_to_original`（:98-128）亦直接赋值；transitions.py:61-65 的 `"reject_to_*"` 仅为文档元数据字符串，全仓无方法名分派。
3. **不删论据（成立）**：5 方法为 `VALID_TRANSITIONS[DAMAGED]`（transitions.py:59-66）的具名转换实现面，与 B12 无入边孤儿 selector（可删）本质不同；AI_REVIEW_NEEDED（scrapping.py:130-144）已裁定保留（reject_to_in_use 为未来"in_use 直报废"扩展位）；5 目标状态已全量行为锚定——test_reject_to_broken:239 / test_reject_to_lost:266 / test_reject_returns_to_original_status:308（参数化 in_use/recycled_pending/repairing + None/in_store 兜底），原方案"补 2 条未测目标"冗余、无需新增。

### 三、决策与实施

- #31：docstring 两行补 `in_use` → `(in_store|in_use|recycled_pending)`（零行为变更）。
- #32：**零删码**；`_REJECT_TARGETS` 定义处补防误报注释（按实际机制："经 reject_to_original 按 original_status 回退，5 目标已测试锚定；reject_to_* 为具名转换实现面、无方法名分派，勿判死代码删除"）。

### 四、验证记录

```text
ruff check                    → 0（两目标文件）✅
定向 pytest                   → test_state_machine.py + test_damaged_asset_service.py 89 passed ✅
行为变更                      → 零（纯 docstring + 注释）✅
跨端契约                      → 未破坏；api-schema-baseline.json 无需重导出 ✅
```

*登记人：big-pickle ｜ 状态：已关闭（纯文档 + 零删码 + 门禁绿），2026-09-21*

## BF-029 【已关闭】安全加固 + DRY 收口批量（审查报告 #33~#37）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P3 #33~#37）
- **严重级别**：P3（#34 SC-1 跨环境 key 泄漏最高，其余防御收口/DRY）
- **影响范围**：`clear_database.py`；`config/settings/{development,production,test}.py`；`core/request_context.py`；`config/settings/base.py`；`core/constants.py`；`apps/assetmanagement/views/asset_view.py`；`apps/assetmanagement/services/asset_service.py`；新增 2 测试文件
- **登记来源**：审查报告 #33~#37；核实全部属实，方案微调后按批次实施

### 一、各条核实与决策

1. **#33（SC-3/SC-4）**：get_table_count(clear_database.py:127) 独立顶层函数无自白名单；clear_table 内白名单(:191-192)+PROTECTED(:194) 先于 count(:197)/DELETE(:205) 执行，现状安全但依赖调用方自觉。实施 `_validate_table_name` helper 双入口自保证（fail-closed），与内联检查 DR-1 收敛。
2. **#34（SC-1）**：旧 dev 默认 key（62 字符）不在开发/生产/测试三处 `_INSECURE_KEYS`，被复制进 prod env 时长度 62≥20 且不在黑名单 → 校验拦不住（真实风险路径）。实施默认 key 轮换（`get_random_secret_key()`）+ 旧值入三环境黑名单。**回归实证**：`DJANGO_ENV=production`+旧 key → `ImproperlyConfigured`（exit=1）；dev 默认新值启动正常。
3. **#35（SC）**：`_get_client_ip` 无条件取 XFF 首值，无配置守卫。实施 `TRUST_PROXY_HEADERS=False`（base 默认 fail-closed）→ False 仅信 REMOTE_ADDR（伪造 XFF 无效），True 才解析首值；`get_current_ip()` 消费面零变化。新增 `core/tests/test_request_context.py` 6 用例。
4. **#36（DR-1）**：core/constants.py:15-24 重复 8 元组；Model `Asset.ASSET_STATUS_CHOICES`(:109) 权威；唯一消费 asset_view.py:33。删除重复块（不触碰 core>apps 依赖方向），asset_view 改 `dict(Asset.ASSET_STATUS_CHOICES)`；新增 `test_status_choices_singleton.py` 单一来源护栏。
5. **#37（DR-4）**：create_asset_batch 循环内 `import json`(:135)，文件顶部无。上移模块顶部 import 区，零行为变更。

### 二、验证记录

```text
全量 pytest apps core --create-db → 1172 passed ✅
定向 core/tests                → 27 passed（新增 request_context 6 + 黑名单 2）✅
定向 资产 view/batch/service/type → 96 passed ✅
ruff check（13 目标文件）        → 0（首轮 import 顺序 4 处 --fix）✅
mypy 全仓                       → 存量 16=16，零新增 ✅
DJANGO_ENV=production + 旧 key  → ImproperlyConfigured 拒绝（exit=1）✅
dev 默认新 key 启动              → OK，TRUST_PROXY_HEADERS=False ✅
```

### 三、遗留与关联事项（观察登记）

- core/constants.py 其余 *_STATUS_CHOICES（ASSET_APPEARANCE/EMPLOYEE/DEPARTMENT/APPROVAL/CONTRACT/STORAGE/HARDDISK）疑似同病（DR-1），本次仅处置被点名的 ASSET_STATUS_CHOICES，其余登记观察，后续审查处置。
- **残余风险（ID-2 主动提示）**：仓库内任何硬编码默认 SECRET_KEY（含已验证的新值）都可从源码泄露；生产已是 env 必填 `os.getenv`，dev 默认值仅随 repo 分发，SC-1 严格口径下建议长期迁往 `.env`/密钥管理。
- 无契约变化，前端零改动；跨端契约未破坏，api-schema-baseline.json 无需重导出。

*登记人：big-pickle ｜ 状态：已关闭（安全加固 + DRY 收口 + 门禁全绿），2026-09-21*

## BF-030 【已关闭】手动状态收口 + 导出防护 + error_code 单条透传（审查报告 #38~#42）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P3 #38~#42）
- **严重级别**：P3（#38 潜藏 500 行为修复为本批最高；#41 单条通道 error_code 丢失；#40 OOM 风险；#39/#42 误报/重复）
- **影响范围**：`services/asset_service.py`；`views/_export_mixin.py`；`config/settings/base.py`；`core/exception_handler.py`；`core/tests/test_exception_handler.py`；`apps/assetmanagement/tests/test_export_excel.py`（新增）；`apps/assetmanagement/tests/test_asset_service.py`；`apps/assetmanagement/tests/test_models.py`
- **登记来源**：审查报告 #38~#42；#38/#40/#41 属实，#39 与 #30 重复、#42 误报（均按实证标记）

### 一、各条核实与决策

1. **#38（AR-1 收口，行为修复）**：`change_asset_status` 为全仓唯一访问 FSM 私有 `_transition` 的散点（asset_service.py:321）；无 try/except → `InvalidTransitionError` 裸异常逃出服务层，全局 handler 不识别 → 手动改非法状态实为 **500**。实施模块级 `_run_manual_transition`（`AssetFSM._transition` 单点 + `InvalidTransitionError→AppValidationError(error_code="INVALID_STATE_TRANSITION")`）。行为变化（用户已确认 500→400）：既有 `test_change_status_invalid_transition` 断言同步更新。错误码纠偏：全仓规范性 code 为 `INVALID_STATE_TRANSITION`，方案初稿 `LEGACY_STATUS_INVALID` 不存在。
2. **#39（重复条目）**：与 #30（BF-027）同一缺陷，`out_asset_view.py:172` 现行源码已与 `:182` 逐字节对齐，仅去重标记，零代码。
3. **#40（OC-7 资源防护）**：`_export_mixin.py:51/:69` 无界全量导出。实施 `EXPORT_MAX_ROWS=10000`（base `config(cast=int)`）+ 导出前 count 超限 400 + `queryset.iterator()` 流式；此前全仓 0 export 测试，新增 4 用例。
4. **#41（B1，方案纠偏）**：原判「分支不可达」不成立——`AppValidationError(APIException)` 必走 DRF 路径进 :55-78 块，单条通道 error_code 丢失（与批量通道 batch_mixins fail_items 已带 error_code 不一致），真实可达。实施 DRF 路径 `getattr(exc,"error_code")` 并入 `errors` → `data.error_code` 透传，**根 envelope 零变化**（方案 A：不扩 error_response 签名、不动 §3 根结构；用户确认执行）。测试：删旧 not-exposed 断言 → 新透传 + 字段级合并双断言。
5. **#42（误报反证）**：`RepairAsset.objects = SoftDeleteManager.from_queryset(RepairAssetQuerySet)()`（:86），`get_queryset`（core/models.py:54-56）恒追加 `filter(is_deleted=False)` 且 from_queryset 保留该覆写 → :62/:176/:237 三处查询本就排除软删；「默认 manager 不过滤」不实。用户红用例不可构造（delete_repair_asset 拒软删 IN_PROGRESS）。处置：过滤零改动 + `TestRepairAssetSoftDeleteGuard` 护栏守护组合语义。

### 二、验证记录

```text
全量 pytest apps core --create-db → 1178 passed ✅（基线 1172 + 净增 6）
定向 25 passed（export 4 / exception_handler 12 / models 8 / TestChangeAssetStatus）✅
ruff check（8 目标文件）        → 0 ✅
mypy 全仓                      → 存量 16=16 零新增（stash 基线对比）✅
manage.py check                → no issues ✅
```

### 三、遗留与关联事项（观察登记）

- #41 单条 `data.error_code` 为新增加法字段，处置 = 台账观察项，零代码动作（2026-09-23 复核更正引证：前端源码在本仓可验证——`vue-assetmanagement/src` 中 error_code 仅出现于 batch fail_items 类型/测试夹具 `common.ts:40-48`、`entityStoreTypes.ts:77`、`AssetBatchImport.spec.ts:158`，单条零消费成立；G-4 仅声明于 AGENTS.md:100 与账本 687 行，`scripts/check_duplicate_invariants.py` 无 G-4 实现函数；schema 实测零漂移——当前 spectacular 导出与 `api-schema-baseline.json` 均不含 error_code，运行时注入不进 OpenAPI schema）；后续前端做精细化错误提示时可按 error_code 分支。
- `_export_mixin.py:90-91` mypy 错误为存量（`for col in ws.columns` 变量遮蔽）——**2026-09-23 已修复**：`:72/:80` 枚举循环改 `column_idx, col_config`、`:89` 列宽循环改 `column_cells`，消除 `int` 遮蔽；`mypy apps/assetmanagement/views/_export_mixin.py` 由 2 错误归零（全仓 20 errors/8 files → 18/7，零新增）、`ruff` 0、`test_export_excel.py` 4 passed。
- 无迁移变更（CT-6 N/A）；根 envelope 未变，api-schema-baseline.json 无需重导出；前端零改动；无 `[HALT]`。

*登记人：big-pickle ｜ 状态：已关闭（收口 + 防护 + 契约零变化 + 门禁全绿），2026-09-21*

## BF-031 【已关闭】前端样式双轨收敛 + 暗色渐变补全 + useChartTheme 专属测试（审查报告 #43~#46）

- **发现日期**：2026-09-17（《full-review-report-2026-09-17.md》P3 #43~#46）
- **严重级别**：P3（#44 设计令牌双轨 DR-1/F1；#45 暗色渐变缺失 F13；#46 CT-1 测试缺口；#43 BR-7 误报）
- **影响范围**：`src/assets/styles/common-forms.scss`；`src/styles/variables.css`；`src/composables/__tests__/useChartTheme.spec.ts`（新增）
- **登记来源**：审查报告 #43~#46；#44/#45/#46 属实，**#43 误报**（BR-7 深层链不成立）、**#46 范围大幅收窄**（10 具名中 8 已有 spec，仅 useChartTheme 缺专属 spec）

### 一、各条核实与决策

1. **#43（BR-7 误报反证）**：链路实测 = `recycle_asset_view.py:240-255` cancel_recycle → `RecycleAssetService.batch_delete_recycle_asset(recordcodes=[recycle.recordcode], ...)`（:300，单元素复用批入口，与 #17 同模式）→ 内部闭包 `_delete_one` → `AssetFSM.cancel_recycle`（:326）。View→Service→FSM 恰为 3 层，BR-7 禁的 4 层+（Service→Service）链不存在。原指控行号误指：`:348` 为 `_delete_one` 内 AuditLogger 的 `trigger="cancel_recycle"`，`batch_delete_execute` 返回在 `:353`。处置：❌误报，仅文档注记，零代码。
2. **#44（DR-1/F1 双轨收敛）**：`common-forms.scss:11-30` 与 `variables.css` 重复维护同一套颜色令牌。实测全仓**无任何外部 SCSS 颜色变量引用**（40 个 `@use as *` 消费组件仅用 mixin，`.vue` 中 `$x` 符号全为 Vue 内建 `$attrs/$emit` 等）→ 删除 `$primary/success/warning/danger/$text-*/$border/$background/$white/$card-shadow/$card-hover-shadow` 15 个 SCSS 变量块，约 40 处 `var(--xx, $yy)` SCSS-fallback 剥离为纯 `var(--xx)`（CSS 变量亮/暗双态均已定义，行为零变化）；保留 `$breakpoint-mobile/tablet`（媒体查询在用）。字面量 fallback 与 `_dashboard-sections.scss` 的 `$section-*` 零触碰。
3. **#45（F13 暗色梯度缺失）**：`variables.css:72-74` 三个 `--gradient-card-{purple,cyan,green}`（DashboardPage.vue:217/:221/:225 消费）在 `html.dark` 无覆盖，暗色下仪表盘卡片仍显亮色渐变。补暗色变体（收敛冷静版降饱和：purple `#3d3a66→#44306a` / cyan `#1f4a70→#1d5761` / green `#1f533f→#1c5349`），消费端零改动。
4. **#46（CT-1 范围收窄）**：报告「7 个 composable 无测试」经 `__tests__` 实况核对不成立——10 个具名 composable 中 8 个已有专属 spec，`useEmployeeLinkage` 由 `useAssetFormHelpers.spec.ts:212` 覆盖，**仅 `useChartTheme` 缺专属 spec**（间接依赖 useDashboardCharts.spec）。新增 `useChartTheme.spec.ts` 5 用例：亮色令牌映射 / pieColors 拼接 / 亮暗 tooltip·divider·lineArea 切换（mock getComputedStyle + `useDarkMode().setDark` 驱动）/ CSS 变量缺失回退 FALLBACK。

### 二、验证记录

```text
npm run build-only                          → ✓ 全组件 SCSS 编译通过（40 use @use as * 消费方）
npx vitest run useChartTheme.spec.ts        → 5 passed ✅
全量 composables vitest                     → 608 passed（原 603 +5）✅
npm run type-check                          → 0 错误 ✅
npx eslint useChartTheme.spec.ts            → 0 ✅
npx prettier --check                        → ✓ ✅
grep 残留（common-forms.scss `, \$|^\$[a-z]`）→ 仅剩 $breakpoint-* 两行 ✅
grep gradient-card                          → 亮/暗双态各 4 条齐备 ✅
```

### 三、遗留与关联事项（观察登记）

- `common-forms.scss` 内 `:57-80 form-container .card-header` 与 `:664-692 独立 card-header mixin` 的同体样式双写（DR-2 隐患）——**2026-09-23 已修复**：内嵌 24 行替换为 `.card-header { @include card-header; }`（3 行，保留外层包裹防子选择器作用域污染），独立 mixin 成为唯一实现；第三处 `info-card` 简化头部（无渐变底、text-dark）判定保留不合并。验证：`build-only`/`type-check`/`lint`/`format:check` 全绿，编译 CSS 抽查值一致（DamagedAssetForm/UserBatchImport/DamagedAssetBasicDetails）。账本登记 A-35/v2.9.45。
- `_dashboard-sections.scss` 的 `$section-*` 局部变量为本文件私有且已用于 F3/F5 令牌，保持不动（2026-09-23 复核确认：4 变量仅本文件 mixin 内消费、色值全走 CSS 令牌，系布局参数化非 DR-2 跨文件双写）。
- 无迁移变更（CT-6 N/A）；纯前端样式 + 测试新增，无 API/端点/状态枚举变化，api-schema-baseline.json 无需重导出；无 `[HALT]`。

*登记人：big-pickle ｜ 状态：已关闭（双轨收敛 + 暗色补全 + 测试收口 + 门禁全绿），2026-09-22*

---

## BF-032 【已关闭】BF-002 改进建议落地：Vite `/ws` 代理统一双 host + 403-CSRF 误判分流（登记来源：BF-001 遗留段两条建议）

- **发现日期**：2026-09-22（BF-001/BF-002 遗留待办 → 人工确认采纳后实施）
- **严重级别**：P3（均为结构统一与误判分流，非现行故障；其中「生产 WS 直连容器内网地址」为部署前置隐患）
- **影响范围**：`vue-assetmanagement/vite.config.ts`；`src/composables/useNotificationConnection.ts`；`.env.development`；`.env.development.example`；`src/composables/__tests__/useNotification.spec.ts`；`src/api/request.ts`；`src/api/__tests__/request.responseHandler.spec.ts`
- **契约影响**：无（WS 认证仍走 subprotocol JWT，`/ws/notifications/<jobcode>/` 路径不变；403/500 响应结构未动；无 API 端点、状态枚举、schema 变化）

### 一、问题现象（两条建议对应的事实基线）

1. **双 host 结构（建议 1）**：HTTP 走 `localhost:5173`、WS 走 `ws://127.0.0.1:8000` 直连，cookie 按 host 隔离互不可见；且 `.env.production` 未配 `VITE_WS_BASE_URL`，运行时 fallback 为 `ws://127.0.0.1:8000`（容器内网地址，浏览器不可达）——一旦部署，生产 WS 必连不上（nginx `location /ws/` 已就绪，default.conf.tpl:141-159）。
2. **403-CSRF 误判（建议 2）**：`request.ts:206` 403 一律提示"没有权限访问该资源"，而 DRF CSRF 校验失败为 `PermissionDenied("CSRF Failed: ...")`（authentication.py:51）→ 403 detail 含 "CSRF" 关键字，被误判为权限问题而非会话校验失败。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | WS 无代理 | `vite.config.ts` proxy 仅 `/api`（修复前 :156-166），无 `/ws` + `ws: true` |
| 2 | 前端硬编码直连地址 | `useNotificationConnection.ts:21`（修复前）：`const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL \|\| 'ws://127.0.0.1:8000'` |
| 3 | dev env 显式覆盖 | `.env.development:11`（修复前）`VITE_WS_BASE_URL=ws://127.0.0.1:8000`，使优化前的相对路径方案不生效 |
| 4 | 生产 WS 配置缺失 | `.env.production` 无 `VITE_WS_BASE_URL` → 生产 fallback = 容器内网直连地址 |
| 5 | 403 不区分 CSRF | `request.ts` 403 分支固定文案（修复前 :206-208），未读取 `msg` |
| 6 | 后端 CSRF 失败特征 | `authentication.py:51` `raise PermissionDenied(f"CSRF Failed: {reason}")` → DRF 403 body `detail` 含 "CSRF" |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | proxy 追加 `'/ws': { target: env.VITE_API_TARGET \|\| 'http://127.0.0.1:8000', ws: true, changeOrigin: true, secure: false }`（复用 `/api` 同款 target，DR-4） | `vue-assetmanagement/vite.config.ts:166-173` |
| 2 | WS 基础地址改同源相对路径：`import.meta.env.VITE_WS_BASE_URL \|\| ''`，去掉硬编码 fallback；`/ws/notifications/<jobcode>/` dev 经 5173 代理、生产经 nginx `/ws/` | `src/composables/useNotificationConnection.ts:24` |
| 3 | dev env 注释 `VITE_WS_BASE_URL`（保留直连方式示例注释，避免代理失效；grep 确认无其他消费者） | `.env.development:11-12`、`.env.development.example:11-12` |
| 4 | 测试断言同步：mock 原样存 url，相对路径断言改为 `toContain('/ws/notifications/')` | `src/composables/__tests__/useNotification.spec.ts:118` |
| 5 | 403 分支按 `msg` 是否含 "csrf"（小写 includes，规避 AR-2 正则标注）分流：CSRF → "页面会话校验失败，请刷新页面后重试"；否则保持"没有权限访问该资源"；401 已由拦截器 :298-300 提前接管，不受影响 | `src/api/request.ts:206-212` |
| 6 | 新增用例：403 `{detail:'CSRF Failed: Origin checking failed.'}` → 引导刷新文案；普通 403 用例（:195-199）保留不回退 | `src/api/__tests__/request.responseHandler.spec.ts:201-204` |

### 四、对抗审核（自反清单）

1. **行号漂移**：登记行号以 `rg` 实测为基准（vite.config.ts:166-173 / request.ts:209-210 / useNotificationConnection.ts:24 / 两处测试 :118、:201），与工作区一致 ✓
2. **验证实况**：type-check / lint / format:check 与 2 个目标 spec（66 用例全绿）均已实际执行；**WS 端到端 101 握手冒烟未运行**（需后端 + 登录态，属人工验证项）——如实标注待验证，不虚报 ✓
3. **契约影响复核**：WS 路径、subprotocol JWT 认证、403/500 响应结构均未变；`api-schema-baseline.json` 无需重导出（前端侧纯配置 + 文案分流）；无迁移（CT-6 N/A）✓
4. **范围克制**：仅改前端 4 文件 + 2 测试 + 2 env；未触碰 `consumer.py`（BF-002 主因已闭环，consumer.py:82-83），未扩改请求拦截器结构与 401 流程 ✓
5. **残留引用核对**：`rg 'ws://127.0.0.1:8000|VITE_WS_BASE_URL'` 全部命中为注释/示例/工具函数，无活动代码路径 ✓
6. **自动化护栏**：`scripts/check_duplicate_invariants.py` PASS（G-1~G-4 未回归）；`useOperationGuard.ts:34` 的 403 注释在普通 403 场景仍成立 ✓

### 五、验证记录

```text
① npm run type-check            → 0 错误 ✅
② npm run lint  (eslint . --fix) → 通过 ✅
③ npm run format:check          → 全部通过 ✅
④ npx vitest run src/api/__tests__/request.responseHandler.spec.ts
   src/composables/__tests__/useNotification.spec.ts
                                → 2 files / 66 passed ✅（含新增 403-CSRF 用例）
⑤ npm run dev                   → VITE v8.2.2 ready（proxy 配置解析通过）✅
⑥ python scripts/check_duplicate_invariants.py → PASS ✅（前端 WS/错误文案无重复实现新增）
⑦ WS 端到端 101 握手经 5173（wscat/浏览器 WS 面板）→ [待验证]（需后端 + 登录态，人工执行）
```

### 六、遗留与关联事项

- **[待确认] 生产 CI 是否注入 `VITE_WS_BASE_URL`**：若注入则生产 WS 走显式端点；若未注入，改动后生产将走 nginx `/ws/` 同源（已就绪，default.conf.tpl:141-159）——两种路径均在方案覆盖内。
- **[待验证] 端到端冒烟**：登录 → 后端推送通知 → NotificationBell 实时到达 + 101 握手经 5173；另补 wscat `ws://localhost:5173/ws/notifications/<jobcode>/` 带 token 子协议验证。
- **[观察登记] dev 直连脚本**：若本地存在依赖 `VITE_WS_BASE_URL=ws://127.0.0.1:8000` 的手工 wscat 脚本，注释后需改用 `ws://localhost:5173/ws/...`。
- BF-002 主因（subprotocol 回显）修复保持不动，本条目仅落地其两条改进建议；BF-001 遗留段已补指针（见 :78/:80）。

*登记人：big-pickle ｜ 状态：已关闭（代码级验证通过，端到端冒烟 [待验证] 人工执行），2026-09-22*

## BF-033 【已闭环】批量出库 batch-create 全量失败——`outasset_asset` 键名错位 + `row_number` 残留（测试容忍掩盖 100% 失败）

- **发现日期**：2026-09-22（`test_out_asset_view_api.py` 遗留"已知 bug"注释与 try/except 容忍块触发排查）
- **严重级别**：P1（`POST /api/v1/asset/out-assets/batch-create/` 端点 100% 失败，批量出库功能整体不可用）
- **影响范围**：`apps/assetmanagement/services/out_asset_service.py:240-252`（`_create_item` 归一）；`apps/assetmanagement/tests/test_out_asset_view_api.py:222-246`（测试转正）；`apps/assetmanagement/tests/test_out_asset_service.py:169-183`（部分失败独立性断言）
- **契约影响**：无（对外请求键名仍为 `outasset_asset`，响应结构仍走 `BatchResponseHelper`，前端零改动、`api-schema-baseline.json` 无需重导出）

### 一、问题现象与事实基线

1. **全量失败是真实状态**：`OutAssetBatchItemSerializer`（`out_asset_serializers.py:231-235`）以 `outasset_asset`（SlugRelatedField，Asset 实例）输出资产键，`validated_data["items"]` 原样直传 Service（`out_asset_view.py:223-224`）；`create_outasset` 只认 `asset_recordcode`（`out_asset_service.py:46-48`）→ 每条 MISSING_ASSET_CODE → 响应为 **HTTP 200 + `success_count==0`**，批量出库从未成功过。
2. **旧注释的"500"臆测不实**：`batch_execute` 三条捕获分支均经 `_normalize_input_data`（`batch_mixins.py:118/:132/:145` + `:221-241`）归一化实例后入 fail_items，成功项由 `BatchResponseHelper.create_response` 以 `OutAssetCreateSerializer` 序列化处理结果对象（`:270`），**任何路径都不渲染 500**；"Asset object not JSON serializable"注释系误判。
3. **row_number 残留为潜在 TypeError**：`OutAssetBatchItemSerializer` 解出 `row_number`（`out_asset_serializers.py:230`），若仅修键名不过滤，`OutAsset.objects.create(**outasset_data)`（`:67`）会收到多余键抛 TypeError → INTERNAL_ERROR。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 键名无归一 | `batch_execute` 直传 serializer 契约键 `outasset_asset`；单条入口 `create_outasset` 期望 `asset_recordcode`（`out_asset_service.py:46`） |
| 2 | 框架元数据残留 | `row_number` 非 `OutAsset` 模型字段，透传至 `OutAsset.objects.create` 触发 TypeError |
| 3 | 测试掩盖 | 旧 `test_batch_create` try/except 吞异常 + 容忍 200/400/500，将"100% 失败"粉饰为"已知 bug" |

### 三、修复方案

| # | 变更 | 位置 |
|---|------|------|
| 1 | `_create_item` deepcopy 后键名归一：`outasset_asset` 存在则映射为 `asset_recordcode`，并 `pop("row_number", None)`；直接调用方以 `asset_recordcode` 直传时保持透传（服务契约不变，条件适配而非强制替换） | `out_asset_service.py:240-252` |
| 2 | 测试转正：全成功用例（`asset` + `asset2` 两条独立 in_store → `success_count==2`、FK 落库、主表 IN_USE）；HTTP 重复资产 ×2 → 400 锁定 `validate_items` 去重（`out_asset_serializers.py:254-261`）；服务级部分失败扩展首条状态联动断言；删除 try/except 与"已知 bug"注释 | 两个测试文件 |
| 3 | 活账本登记（本条） | `docs/BugFixed/Bug修复活账本.md` |

### 四、对抗审核（自反清单）

1. **先红后绿实据**：重写测试先跑（成功用例断言 `success_count==0 == 2` → AssertionError 0==2，即未打补丁时 `success_count==0`），打补丁后转绿 ✓
2. **服务契约边界**：`batch_create_outasset` 直接调用方（服务级测试 `_outasset_payload` 以 `asset_recordcode` 手建 dict）不受影响——键名归一为"缺则映射、有则透传"的条件适配，交付后确认 `rg batch_create_outasset` 调用方仅 view（serializer 键）+ 测试 ✓
3. **两轮评审修正过程**：首轮误判"`validate_items` 去重已不存在"（读取截断于 :253）——实测存在于 `out_asset_serializers.py:254-261`，重复资产在 serializer 层 400，**部分失败不可经 HTTP 构造**，改为服务级直测；同资产×2 因去重拦截故未采用 ✓
4. **重复键安抚**：`outasset_asset` 仅存在于 serializer 定义（契约键名）与 view→service 链路，再无第二实现（`rg outasset_asset` 服务层 0 残留）✓
5. **门禁全过**：相关 2 套件 29 passed、全量 `1253 passed`、`ruff` 0、mypy 涉改文件 0 新增、`manage.py check` no issues ✓

### 五、验证记录

```text
① python -m pytest apps/assetmanagement/tests/test_out_asset_view_api.py test_out_asset_service.py -q → 29 passed ✅
② python -m pytest -q（全量）→ 1253 passed ✅
③ ruff check 涉改 3 文件 → All checks passed ✅
④ mypy 单文件 follow-import → 无新错误（残留为既有 models/dateutil 噪声）✅
⑤ python manage.py check → System check identified no issues ✅
```

### 六、教训注记

- **测试对"已知 bug"的容忍会掩盖功能整体不可用**：try/except 吞异常 + 多状态码宽容让批量出库 100% 失败长期潜伏；回归测试应断言真实成功语义（本条现断言 `success_count==2`）。
- **注释臆测不可留**："Asset object not JSON serializable"系推断，实测 200+全 fail 而非 500——修复后已删除。
- **服务契约与序列化器契约分离**：服务入口键（`asset_recordcode`）与端点契约键（`outasset_asset`）按层次适配，避免在 Service 强制覆盖直接调用方语义。

*登记人：big-pickle ｜ 状态：已闭环（代码级验证通过，先红后绿全程记录），2026-09-22*

## BF-034 【已关闭】batch-delete 跨部门横向越权：A 部门 dept_manager 可取消 B 部门资产待报废记录并连带恢复其资产状态

- **发现日期**：2026-09-22（A-29 观察项收口复核时经实证检出）
- **严重级别**：高（横向越权写，绕过 View 层单对象 404 作用域兜底）
- **影响范围**：`damaged_asset_view.py:211-225`（batch-delete 端点）；`damaged_asset_selector.py:28-49/68-75`（两锁查询）；`damaged_asset_service.py`（approve/reject/cancel/update/batch）；`damaged_asset_serializers.py:257`（help_text）

### 一、问题现象与事实基线

1. A 部门 `dept_manager` 向 `POST /api/v1/damaged-assets/batch-delete/` 提交 B 部门资产 recordcode，待报废记录被取消（软删+墓碑）且资产状态被恢复到申请前状态
2. 单对象写路径（destroy/approve/reject/update）同场景经 `RecordcodeLookupMixin.get_object()`（views/_mixins.py:24-42）返回 404；批量路径却成功——部门作用域兜底在批量分支缺位
3. `ids` 由 serializer 携带、view 原样透传 Service → `cancel_asset_recordcode` → `get_asset_recordcode_for_update`，**零 user 零作用域**；`BatchDeleteValidationMixin.validate_ids` 仅验长度/去重，无部门校验
4. 权限门控为角色级 `IsDeptManagerOrAbove`（非部门范围），故任意部门经理可命中

### 二、根因

批量写路径在 A-22（#10）部门作用域加固时遗漏。单对象路径的隔离由 View 层作用域 QuerySet + 404 兜底完成，而 batch 直接调用 Service 锁内查询，未透传请求用户 → 部门边界失效。

### 三、修复方案

| # | 变更 | 位置 |
|---|------|------|
| 1 | `get_asset_recordcode_for_update`/`get_for_update` 增加 `user=None`，user 提供时经 `get_asset_linked_queryset_for_user` 过滤（B12 模式：越界≡不存在） | `damaged_asset_selector.py` |
| 2 | 两锁查询改 `select_for_update(of=("self",))`：作用域 Q 对可空 `asset_recordcode` 生成 LEFT OUTER JOIN，裸 `select_for_update()` 会复现 A-22 NotSupportedError（可空外连接侧封锁） | `damaged_asset_selector.py` |
| 3 | Service 四方法 + `batch_delete_asset_recordcodes` 增加 `user=None` 并透传（approve/reject/update 调用点同步） | `damaged_asset_service.py` |
| 4 | View 六写动作（approve/reject/destroy/update/partial_update/batch_delete）传 `user=request.user` | `damaged_asset_view.py` |
| 5 | ids help_text 修正为「关联资产 recordcode 列表」（原「待报废记录编码列表」误导；spectacular 不输出 ListField child help_text，schema 逐字节无 diff） | `damaged_asset_serializers.py:257` |

**否决 ids 预筛（Option A）**：`batch_delete_execute`（core/batch_mixins.py:157）`total=len(ids)` 且 `success_count+fail_count==total`（:203-204），预筛剔除合格条目会破坏批量响应语义，且预筛不在锁内、存在 TOCTOU 窗口；Service 锁内取消天然守护计数契约。

### 四、对抗审核（自反清单）

1. **先红后绿实据**：5 条用例先行——跨部门批删修复前 `success_count==1`（越权取消成功）→ 修复后 fail `DAMAGED_ASSET_NOT_FOUND`；update/approve 带 `user=` 签名修复前 TypeError（红）
2. **`of=("self",)` 必要性铁证**：作用域过滤 SQL 为 LEFT OUTER JOIN（可空 OneToOneField），PostgreSQL 对 OF 缺省的外连接可空侧执行 FOR UPDATE 抛 NotSupportedError（A-22 :157 实证）——`of=("self",)` 是启用前置而非可选优化
3. **非回归**：无 user 直调（既有全部调用）行为等价——无 JOIN 时 `of=("self",)` 与原语义一致；既有 49 条 damaged 用例 + 全量 1048 全过
4. **serializer help_text 不产生 schema diff**：spectacular 不发射 ListField child 的 help_text，`api-schema-baseline.json` 重导出逐字节一致

### 五、验证记录

```text
① 定向 damaged 两套件（service + view_api）：先红 5 failed → 修复后 54 passed ✅
② python -m pytest apps -q → 1048 passed（+5 新用例）✅
③ pytest --cov=. --cov-fail-under=80 → 整体 81.12% ✅
④ pytest --cov=apps.assetmanagement.services --cov-fail-under=90 → 96.44% ✅
⑤ ruff scoped 5 文件 → All checks passed ✅
⑥ mypy（4 生产文件）→ 0 错（test 文件缺口为既有类别噪声）✅
⑦ python scripts/check_duplicate_invariants.py → PASS ✅
⑧ spectacular 重导出 → 无 diff（byte-identical）✅
```

### 六、教训注记

- **批量/框架通用路径是作用域加固的盲区**：单对象路径 GetObject 404 兜底完备，批量路径直达 Service 锁内查询——每次新增批量端点都要核对用户作用域与部门边界。
- **安全修复会改变"可选优化"的现实优先级**：`of=("self",)` 从可选增强变必修——优化清单里的条目可能是后续安全/行为修复的启用前置，账本应以启用技术留存。
- **作用域过滤 JOIN 与行锁的交互要先于编码验证**：数据库方言差异（PostgreSQL FOR UPDATE 限制）应作为实现前置条件在方案阶段确认，而非测试阶段发现。

*登记人：big-pickle ｜ 状态：已闭环（5 用例先红后绿 + 全量门禁全过），2026-09-22*

---

## BF-035 【已闭环】BR-4 护栏红灯回潮：`update_outasset` 未登记超长（53>50）且 `using_location` 落库三段手工实现重复

- **发现日期**：2026-09-23（BR-4 状态核查 + 拆分复用审查，guard `exit 1` 实证）
- **严重级别**：中（护栏红 + DR-1 重复实现）
- **影响范围**：`apps/assetmanagement/services/out_asset_service.py`（`update_outasset` :198、`_build_asset_people_update` :135、`_build_update_audit_snapshot` 新增 :167）

### 一、问题现象与事实基线

1. `python scripts/check_function_length_guard.py` 退出码 1：`update_outasset() 逻辑行 53 > 50` 未登记台账——BR-4 台账头部自称「0 处」失效；为全仓唯一超限函数
2. `update_outasset` 函数体 :214-217 手工重写 `using_location` 落库三段逻辑（`if using_location is not None: asset.asset_using_location=...`），与同文件 `create_outasset` 路径已收敛的公共 helper `_build_asset_people_update`（:135-147，含 using_location 参数 :144-146）语义重复——违反 DR-1「业务逻辑唯一实现」，且未登记入 `complete-patterns.md`（rg 零命中）
3. 19 处拆分（B1/B2/B3）本身已闭环（台账清空、BF-025 已登记）；本回潮系 `bbb3049`（出库人员/地点写入贯通）拆分后新增回归，未重新入账

### 二、根因

拆分完成于 `e4e97a6`（B1），此后 `bbb3049` 在 `update_outasset` 新增 using_location 落库时**误传 `None` 给 helper 再在函数体手工补写**——既复制造了三段重复代码，又把函数物理长度推到 53 行且未触发任何门禁（护栏只报未登记超长，无人复核的静默红灯）。

### 三、修复方案

| # | 变更 | 位置 |
|---|------|------|
| 1 | `update_outasset` 改传 `update_data.get("outasset_using_location")` 至 `_build_asset_people_update`，删除函数体内手工三段重复（净删 3 行） | `out_asset_service.py` |
| 2 | before/after 审计快照内联（原 :182-190 + :205-209）抽为 `_build_update_audit_snapshot`（26 行，jobcode 口径，含 FK 字段名重映射） | `out_asset_service.py` |
| 3 | `complete-patterns.md` 登记 A-33（DR-1 新发现义务 + 已修复关闭，v2.9.43） | `Rules_Fiels/Duplicate_Codes/complete-patterns.md` |

**否决新建 `_sync_asset_main_table` helper（原方案）**：既有 `_build_asset_people_update` 已支持 using_location，新建即 DR-1 二次违反；`_to_json_safe`（operation_log_service.py:134）不可复用（pk 降级语义 vs recordcode/jobcode 语义，AR-1 不猜）。

### 四、对抗审核（自反清单）

1. **行为等价**：改传 `update_data.get(...)` 与原 `if ... is not None` 分支逐字条件相同（helper 内 :144-146 同条件）；before_data/after_data 构建顺序、键值、jobcode 口径全同——快照不重写断言（`test_update_out_asset_with_people_and_location`）通过佐证
2. **护栏先红后绿**：拆分前 guard exit=1（53 行未登记）→ 拆分后 exit=0（`update_outasset` 37 行 + 新 helper 26 行，均 ≤50，0 未登记/0 台账）
3. **无新增覆盖缺口**：基准（stash HEAD）与拆分后 misses 同 14 行（错误分支 + statistics），`update_outasset` 主路径/双表同步/审计快照全部命中
4. **复用收敛单点**：`rg "_build_asset_people_update"` 全仓仅 3 处（def :135 + create :161 + update :227）

### 五、验证记录

```text
① python scripts/check_function_length_guard.py → PASS (exit=0, 0 未登记/0 台账) ✅
② python scripts/check_duplicate_invariants.py → PASS (G-1~G-5) ✅
③ pytest apps/assetmanagement/tests/test_out_asset_service.py + test_out_asset_view_api.py + test_outasset_snapshot.py → 31 passed ✅
④ pytest apps/assetmanagement -q → 749 passed ✅
⑤ pytest --cov=apps.assetmanagement.services.out_asset_service → 92.00%（≥90）✅
⑥ ruff check out_asset_service.py → All checks passed ✅
⑦ mypy out_asset_service.py --strict → 7 errors 全为他文件存量（stash 前后一致，零新增）✅
⑧ manage.py check 契约零变化，无迁移 → schema 无需重导出 ✅
```

### 六、教训注记

- **护栏红灯不能静默承载**：拆分后新增代码把函数顶回超长时，必须同步登记台账或现场拆分，禁止放任 guard 长时间红。
- **复用判断要先于新 helper 设计**：审查阶段先问「是否已有可复用实现」，本 case 的 `_sync_asset_main_table` 若落地即成 DR-1 反例——答案是对既有 `_build_asset_people_update` 做参数透传而非重造。
- **回归断言比新代码重要**：两次 write-path 同步（create/update）必须共用同一落库 helper，测试锚点应同时锁定双表字段，防再出现"两路径各自实现"的漂移。

*登记人：big-pickle ｜ 状态：已闭环（护栏红→绿 + 定向/全量测试全过 + 覆盖率达标），2026-09-23*
---

## BF-036 【已关闭】三处 RBAC 权限旁路批量修复：mark-broken/lost、storage batch、lifecycle batch_create（审查报告 F-P1-1/F-P1-2/F-P1-8/F-P2-5）

- **发现日期**：2026-09-23（融合审查报告 F-P1-1/2/8 + F-P2-5；F-P1-8 为本批修复时经用户拍板 A 并入）
- **严重级别**：高（任意登录用户可写本应 asset_admin+/system_admin 独占的端点）
- **影响范围**：`assetmanagement/views/asset_view.py`、`storage_view.py`、`_lifecycle_base.py` + 三个测试文件；跨端契约零变更（schema 基线无漂移）

### 一、问题现象

1. **F-P1-1**：`mark_broken`/`mark_lost` 的 `@action(permission_classes=[IsAssetAdminOrAbove])` 被类方法 `get_permissions()` 覆写后失效；两 action 不在 `admin_actions`，落回 `IsAuthenticated`——任意登录用户可对本部门资产标记损坏/遗失。
2. **F-P1-2**：`StorageViewSet` 继承 `AdminWritePermissionMixin`，其默认 `admin_actions` 不含 `batch_create`/`batch_delete`——任意认证用户可批量建仓/批删，污染全局主数据（矩阵仓库仅 system_admin，`backend-business-rules.md:144`）。
3. **F-P1-8**（本批新增）：`_lifecycle_base.get_permissions` 原写死元组 `("create","update","partial_update","destroy","batch_delete")`，**漏 `batch_create`**——regular 可批量创建损坏/遗失/找回记录（矩阵 regular 生命周期写 ❌，`:141`）。
4. **F-P2-5**：上述三处均无 regular→403 反向测试锚，修复无先红后绿护栏。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | DRF 权限解析顺序 | `get_permissions()` 整类覆写，`@action(permission_classes=...)` 被架空（asset_view 原 :383/:396） |
| 2 | Mixin 默认清单不完整 | `_mixins.py:52-59` 仅 CRUD+change_*，无 batch；contract/asset_type/recycle 已类级补全，Storage 漏 |
| 3 | lifecycle 手写元组漂移 | `_lifecycle_base` 原 get_permissions 硬编码元组，未随 `batch_create` 端点出现同步（子类已有 batch_create 实现） |
| 4 | 测试只写正向 | `test_asset_view_api` 仅 admin 200；无 storage rbac 文件；row_isolation 仅断本部门 200 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | `admin_actions` 追加 `"mark_broken","mark_lost"`；删除两处 `@action(permission_classes=)` 死参数 | `asset_view.py:59-73` |
| 2 | 类级全量 `admin_actions`（create/update/destroy/change_status/change_outasset_employee/**batch_create/batch_delete**），经 Mixin `get_permissions` 落 `IsSystemAdmin` | `storage_view.py:45-54` |
| 3 | 类属性 `admin_actions = [create, update, partial_update, destroy, batch_create, batch_delete]`；`get_permissions` 改读 `self.admin_actions` 返回 `IsAssetAdminOrAbove()`（**否决**继承 Mixin 的 `IsSystemAdmin`，对齐矩阵 asset_admin+） | `_lifecycle_base.py:73-99` |
| 4 | 新增/改写三组先红后绿测试（见验证） | `test_asset_view_api.py:359` / `test_storage_view_rbac.py:34` / `test_create_row_isolation.py:159` |

**否决**：lifecycle 继承 `AdminWritePermissionMixin` 整类复用——Mixin 返回 `IsSystemAdmin`，矩阵要求 asset_admin 即可写，收紧过头会破坏 asset_admin 正常用例（用户拍板方案 A 已预判此点）。

### 四、对抗审核（自反清单）

1. **权限方向**：全部为收紧（IsAuthenticated→更高），无放宽；regular 从可写变 403，admin/system_admin 正向 200/201 保持。
2. **Mixin 遮蔽面**：Storage 全量列清单而非只补两项——只补两项会遮蔽 CRUD 导致非 admin 无法增删改（`AdminWritePermissionMixin.admin_actions` 被整体覆盖）。
3. **死参数清除**：`@action(permission_classes=)` 保留会误导后续维护（以为装饰器生效），一并删除并在 admin_actions 单源。
4. **相邻同类未修**（不并入，报告已留痕）：`export_excel` 的 `@action(permission_classes)` 同样被架空；damaged 单条 `create` 不在清单。
5. **契约**：仅权限类收紧，端点路径/响应形状/枚举零变更；`spectacular` 重导 diff 空。

### 五、验证记录

```text
① 先红（修复前）：F-P1-1 定向 4红/2绿；F-P1-2 3红/2绿；F-P1-8 4红/4绿 ✅
② 修复后定向：
   pytest test_asset_view_api.py → 38 passed
   pytest test_storage_view_rbac.py → 5 passed
   pytest test_create_row_isolation.py → 11 passed
   pytest test_lifecycle_view_api.py → 29 passed
   pytest test_batch_contract_snapshot.py + test_b5_baseline_snapshot.py → 19 passed
   pytest core/tests/test_rbac*.py 三件套 → 66 passed
③ 全量（串行单进程）：pytest -q → 1289 passed / 0 failed (810s) ✅
④ ruff check（6 改动/新增文件）→ All checks passed ✅
⑤ mypy（三 view）→ Success: no issues found ✅（全仓仅 2 存量无关错）
⑥ schema：manage.py spectacular --validate → EXIT=0；api-schema-baseline.json 无漂移 ✅
⑦ export_excel 回归：原 500 系 .venv 缺 openpyxl（ImportError 走 500），pip install openpyxl==3.1.5 后 4 passed
```

### 六、遗留与关联事项

1. **openpyxl 依赖声明缺口**：`requirements/base.txt` 未声明 openpyxl，但 `_export_mixin.py` 运行时强依赖——建议补入 base.txt（非本批红线，待授权）。
2. **export_excel 权限旁路**：`@action(permission_classes=[IsAuthenticated])` 同样被 `get_permissions` 架空（矩阵 regular 导出 ❌）——建议登记 F-P1-9 或并入后续权限批次。
3. **damaged 单条 create**：不在 `damaged_asset_view.admin_actions`，regular 可 201——矩阵口径待确认。
4. **F-P1-3/4/5/6/7 与 H-1** 仍开放，见融合审查报告。
5. **complete-patterns**：权限旁路属 RBAC 配置缺陷非重复代码模式，G-1~G-5 护栏不适用，无需登记台账。

*登记人：opencode（mimo-v2.6-flash-free） ｜ 状态：已关闭（先红后绿 + 全量 1289 passed + schema 无漂移），2026-09-23*
---

## BF-037 【已关闭】export_excel 权限旁路 + damaged 单条 create 收紧 + openpyxl 依赖补录（BF-036 相邻遗留三件套）

- **发现日期**：2026-09-23（BF-036 遗留段 #1/#2/#3 + 用户授权执行）
- **严重级别**：高（export 任意登录可导全表；damaged create regular 可 201）
- **影响范围**：`core/permissions.py`、`views/_export_mixin.py`、11 个 View 接线、`damaged_asset_view.py`、`repair_asset_view.py`、`requirements/base.txt`、规则 `:142` v1.15、4 个测试文件；跨端契约零变更（schema 基线零 diff）

### 一、问题现象

1. **export_excel 权限旁路**：`@action(permission_classes=[IsAuthenticated])` 被类级 `get_permissions()` 架空——矩阵 regular 导出 ❌（`:148`）但实际任意登录可导。
2. **damaged 单条 create 收紧缺口**：`create` 不在 `admin_actions`，落回 `IsAuthenticated`——regular 可 201 提交报废申请（矩阵报废审批行 dept_manager+ 才 ✅）。
3. **openpyxl 依赖声明缺口**：`_export_mixin` 运行时 `import openpyxl`，但 `requirements/base.txt` 未声明——新环境部署即 ImportError→500。
4. **导出真 bug**：真实 queryset 带 `prefetch_related` 时 `iterator()` 缺 `chunk_size` → TypeError→500（修复 openpyxl 后暴露）。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | DRF 权限解析顺序 | 同 BF-036：`get_permissions()` 整类覆写，`@action(permission_classes=)` 架空 |
| 2 | damaged admin_actions 不全 | `damaged_asset_view.py:58` 原清单无 `create` |
| 3 | 依赖声明漏 | `requirements/base.txt:66` 补录前无 openpyxl 行 |
| 4 | Django ORM 约束 | `prefetch_related` 后 `iterator()` 必须传 `chunk_size`（Django 文档约束） |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | `openpyxl==3.1.5` 补入 `:66`（prometheus-client `:63` 之后） | `requirements/base.txt:66` |
| 2 | 新增 `CanExportExcel`（矩阵 :148 四角色）+ `resolve_viewset_permissions`（export→CanExport / overrides / admin_actions / 默认 IsAuthenticated 四分支） | `core/permissions.py:152,168` |
| 3 | 11 处 `get_permissions` 接线公共函数；删 `_export_mixin` 死参数 `permission_classes=[IsAuthenticated]`；修 `iterator(chunk_size=1000)` | `_export_mixin.py:40,82` + 11 view |
| 4 | `admin_actions` 补 `"create"`（方案 A / 规则 :142 同批）；repair 补全五项 `[create,update,partial_update,destroy,batch_delete]` | `damaged_asset_view.py:58` / `repair_asset_view.py:121` |
| 5 | 规则 `:142` 操作列扩展为「申请（单条 create）/审批通过/拒绝/批量删除」，header v1.15 + changelog | `backend-business-rules.md:142,239` |
| 6 | 先红后绿四组测试（见验证） | `test_export_excel_rbac.py` / `test_damaged_asset_view_api.py:209` / `core/tests/test_rbac.py:318` / `test_create_row_isolation.py:105,151` |

### 四、对抗审核（自反清单）

1. **权限方向**：全部收紧或补依赖，无放宽；export regular 200→403，damaged create regular/asset_admin 201→403，dept_manager 保持 201。
2. **修复过程自生 bug 两起（已闭环）**：① `resolve` 写成 `[cls]()` 调用 list → TypeError，改 `[cls()]`；② `_FakeQueryset.iterator()` 签名不收 `chunk_size` → 3 用例 TypeError，补 kwarg。
3. **行级隔离测试语义保持**：`test_create_row_isolation` 两用例改用 `dept_manager`（角色收紧后 regular 到不了行级层），另补 `test_regular_create_denied` 403 锚——行级隔离 400/404 语义不变。
4. **repair admin_actions**：用户修正要求逐项保留原五项，实测 `repair_asset_view.py:121` 五项齐，无漏项放宽。
5. **契约**：`spectacular --validate` EXIT=0 且 `api-schema-baseline.json` **SCHEMA_ZERO_DIFF=YES**；仅权限类与依赖，端点/响应/枚举零变更。

### 五、验证记录

```text
① 先红（修复前）：定向 9 failed（export regular 200≠403；damaged regular/asset_admin 400≠403；
   export 允许角色 500=chunk_size bug；damaged create 400=ASSET_NOT_VISIBLE 夹具问题）✅
② 修复后定向（串行）：
   pytest test_export_excel.py + test_export_excel_rbac.py + test_damaged_asset_view_api.py + core/tests/test_rbac.py
   → 67 passed ✅
   pytest test_create_row_isolation.py → 12 passed ✅
③ 全量（串行单进程）：pytest -q → 1312 passed / 0 failed (1540s) ✅
④ ruff check（本批 17 改动/新增文件）→ All checks passed ✅
⑤ mypy apps core → 1 存量错（unregisteredasset:138 union-attr，非本批）；本批 _export_mixin/_mixins/permissions 0 新增 ✅
⑥ schema：spectacular --validate EXIT=0；api-schema-baseline.json SCHEMA_ZERO_DIFF=YES ✅
⑦ manage.py check → System check identified no issues ✅
⑧ openpyxl：import openpyxl → 3.1.5 ✅；_export_mixin mypy Success（3 行重命名取消）✅
```

### 六、遗留与关联事项

1. **ruff 全仓 7 错**（F-P1-3 存量：`notification/tests/test_ws_consumer.py` F401 + `scripts/loadtest/*` I001/E402）——非本批引入，仍开放。
2. **mypy 存量 1 错**：`unregisteredasset/views.py:138` union-attr——非本批。
3. **F-P1-3/4/5/6/7 与 H-1** 仍开放，见融合审查报告。
4. **complete-patterns**：权限旁路属 RBAC 配置缺陷非重复代码模式，G-1~G-5 护栏不适用；`resolve_viewset_permissions` 为本批新抽公共入口（DR-1 收敛，非新增重复）。

*登记人：opencode（mimo-v2.6-flash-free） ｜ 状态：已关闭（先红后绿 + 全量 1312 passed + schema 零 diff），2026-09-23*

---

## BF-038 【已关闭】未登记资产权限三连：approver 可代签 / discovery_person 可冒名 / 读写路径无行级隔离 + 门禁未按 4.5 矩阵（AtomCode P1-1/2/3 = 融合 F-P1-5/6/7）

- **发现日期**：2026-09-23（AtomCode P1-1/2/3；融合二次取证 V-1~V-3 确认成立）
- **修复日期**：2026-09-24（用户裁定：F-P1-7 扩到读写全路径并对齐 4.5 角色矩阵；dept_manager update 一并收紧为 403 只读）
- **严重级别**：高（代签审批审计链失真；冒名提交发现记录；跨部门横向越权改删审）
- **影响范围**：`core/permissions.py`、`core/department_scope.py`、`apps/unregisteredasset/{views,selectors,services}.py`、5 个测试文件（新建 `test_matrix_permissions.py`）、`api-schema-baseline.json`（仅 create 端点 docstring 描述 1 行，非破坏）；跨端契约零破坏

### 一、问题现象

1. **F-P1-5 approver 可代签**：`approve` 取 `serializer.validated_data.get("approver") or operator_jobcode`——请求传任意有效工号即被采纳，违反 4.5 第 3 条「approver 强制=当前审批人」（`backend-business-rules.md:206`）。
2. **F-P1-6 discovery_person 可冒名**：`create` 优先取 `request.data`，无角色白名单，违反 4.5 第 2 条「默认=本人；仅 system_admin 可代录」（`:205`）。
3. **F-P1-7 写路径无行级隔离 + 门禁不符矩阵**：update/destroy/approve 经 `get_by_code()`（无 user 参数）取对象，跨部门/跨本人可改删审；`get_permissions` 未按 4.5 矩阵（`:187-193`）分发——dept_manager 实际拥有 update/delete 写权限（矩阵为 ❌ 只读），list/create 等角色门禁与矩阵不符。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | View 取值来源 | `approver = validated.get(...) or operator` 把请求值当一等公民 |
| 2 | 代录语义 | `Service.create` 以 operator 兼作 target_jobcode，View 直读 `request.data` 无守卫 |
| 3 | Selector 签名/门禁 | `get_by_code(code)` 不收 user——读侧已隔离、写侧未接；门禁走 `admin_actions` 默认分支而非矩阵映射 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| 1 | `_get_user_role`→公开 `get_user_role`（5 调用点 + department_scope docstring 同步）；新增 `is_system_admin`、`IsSystemAdminOrAssetAdmin` | `core/permissions.py` |
| 2 | 模块级 `_ACTION_PERMISSION_OVERRIDES`（list/retrieve→`IsAssetAdminOrAbove`；create/batch_create/update/partial_update/destroy/batch_delete→`IsSystemAdminOrAssetAdmin`；approve→`IsDeptManagerOrAbove`）；`get_permissions` 走 `resolve_viewset_permissions`——**dept_manager update 403 收紧（用户拍板对齐矩阵）** | `views.py` |
| 3 | F-P1-6：create 恒 `resolve_operator(request.user)`；`discovery_person` ≠本人且非 system_admin → `PermissionDenied` 403；Service `create` 增 `discovery_person_jobcode`（默认=operator，审计 operator 与代录人解耦） | `views.py` + `services.py` |
| 4 | F-P1-5：approve 服务端 `approver = operator_jobcode` 无条件覆盖；serializer `required=True` 不动（零 schema 字段变更，传值被忽略） | `views.py` |
| 5 | F-P1-7 读：`Selector.get_queryset_for_user`（规则1：仅 system 的 None=全量，dm/aa 无部门→空集；规则2 部门+下级；规则3 本人恒可见；规则4 auditor/regular 空集）接入 View `get_queryset` | `selectors.py` + `views.py` |
| 6 | F-P1-7 写：update/destroy/approve 改 `get_by_code_for_user`，越权 `NotFound` 404（4.5「越权一律 404」） | `views.py` |
| 7 | F-P1-7 批删 B14：`batch_delete_passes_user=True` → Service 逐条 scoped 查询，越权同构 `NOT_FOUND`（保 `test_b5` 契约、不泄露存在性） | `views.py` + `services.py` |
| 8 | 测试：conftest 三工厂（`make_role_user` 唯一 auth_phone / `make_dept` 带 path+level / `make_plain_employee`）；新建 `test_matrix_permissions.py`（30 格矩阵 + 行级 + P1-5/6）；selectors +10；services +2；`test_api` 切 `admin_client` + approve 前置 dm | 5 个测试文件 |

### 四、对抗审核（自反清单）

1. **方向全收紧无放宽**：dm update 403（收紧）、代录 403（收紧）、越权 404（收紧）；无部门 asset_admin destroy 403 属 `get_user_role` 既有降级设计（与 `test_api:219` 断言一致，非本次放宽）。
2. **越权形态**：单条走 `NotFound` 404 对齐 4.5；批删走既有 `NOT_FOUND`→400 框架形状（`test_b5` 契约锚定），语义同为「不可见即不存在」，均不泄露存在性。
3. **契约**：响应根结构/枚举/分页/时间零变更；serializer 字段集未动（approver 仍 required=True，仅服务端覆盖值）；schema 基线仅 docstring 描述 1 行（M-3 重导随改，非破坏）。
4. **自生问题三起（已闭环）**：① `views.py` request.data union-attr mypy 错 → `# type: ignore[union-attr]`；② `make_dept` 漏物化 `path` 致 2 条下级部门用例红 → 按既有测试模式补 `path`/`level`（真实先红后绿）；③ `ruff format` 折行致类声明 `# type: ignore[misc]` 错位 3 错 → 移回 `class ... (` 行清零。
5. **规模**：改动文件最大 `services.py` 414 行 ≤500（DR-5）；调用链 ≤3（DR-6）；`views.py` 类 docstring 权限段同步更正为 4.5 矩阵口径。

### 五、验证记录

```text
① 修复前留档：AtomCode P1-1/2/3 + 融合 V-1~V-3 代码取证（先红证据=审查报告；安全用例与修复同批落地）
② 模块（format 后复跑）：pytest apps\unregisteredasset -q → 142 passed ✅
③ 全量（串行单进程，format 前）：pytest -q → 1368 passed / 0 failed (1063s，较 BF-037 基线 +56) ✅
④ ruff check：全仓 7 错均为存量（notification F401 + loadtest I001/E402）；本批 10 文件 + apps\unregisteredasset + core → All checks passed ✅
⑤ ruff format：本批 10 文件已对齐（全仓 117 待格式化存量归口 F-P1-3 独立批）✅
⑥ mypy .：208 文件 0 错——顺带消除 BF-037 记录的 views.py:138 存量 union-attr ✅
⑦ schema：spectacular --validate EXIT=0；基线 diff 仅 create docstring 1 行 ✅
⑧ manage.py check → no issues ✅；根仓 scripts/check_duplicate_invariants.py → PASS (G-1~G-5) ✅
⑨ 覆盖率（模块+permissions）：TOTAL 89.86%（services 97 / selectors 97 / views 99 / models 100；core.permissions 65% 为单模块口径，其余权限类由 core/tests 覆盖）✅
```

### 六、遗留与关联事项

1. **ruff format 全仓 117 文件待格式化、ruff check 7 错**——F-P1-3 存量独立批（format+fix 单独提交），非本批红线。
2. **变异测试 T8 / mutmut**——F-P2-4 开放基线，执行环境待定（WSL/CI），本批未跑（与既往批次一致）。
3. **H-1 状态机契约源裁定**、F-P2-* 其余项仍开放。
4. **complete-patterns**：本批为权限/隔离缺陷非重复代码模式，G-1~G-5 不适用；`get_user_role`/`get_queryset_for_user`/`resolve_viewset_permissions` 为收敛单源（DR-1），非新增重复。

*登记人：opencode（mimo-v2.6-flash-free） ｜ 状态：已关闭（全量 1368 passed 0 failed + schema 仅 docstring 漂移 + 护栏 PASS），2026-09-24*

---

## BF-039 【已关闭】门禁三连红修复（F-P1-3 + F-P2-7 + F-P3-1）2026-09-24
> 状态补标（2026-09-29）：依本条收尾登记人行「已关闭（全量 1368 passed 0 failed + schema 与 docstring 零漂移 + 护栏 PASS）」补齐。

### 一、问题概述

CI 静态门禁三连红（`ruff format --check` 102 文件、`ruff check` 7 错、`mypy --strict` 24 错）+ 生产 C90 超标（`update_user`、`_create_role_permissions` 各 11>10）+ loadtest/test 存量 F401/I001，导致 backend-lint 与 C90 两个 CI job 失败，合并流水线不可用。

### 二、四提交拆分

| # | commit | 内容 | 验证 |
|---|--------|------|------|
| 1 | `9fecb97` fix(ruff) | 删 `test_ws_consumer.py` 未用 asyncio(F401)；两 loadtest locustfile `import json` 上移+I001 | `ruff check .` exit 0 |
| 2 | `210cfa7` style | backend 内 `ruff format .` 107 文件纯格式化零语义 diff | `ruff format --check .` exit 0 |
| 3 | `272f8e6` fix(mypy) | types-channels 新增；`models.py:122` 自引用校验真缺陷修复（**行为变化**）；employee_audit_adapter `str\|None`；删错位/unused ignore；带原因 type: ignore；CT-4 红测锚 | `mypy . --strict` 208 文件 0 错 + 定向 82 passed |
| 4 | `3377c91` refactor(complexity) | `update_user` 抽 `_validate_unique_constraints`；`_create_role_permissions` 抽 `_resolve_perms_to_add`；pyproject ruff exclude 加 `.trae`；`clear_database.py` per-file 加 C901；`ci.yml` C90 命令改 `--config`；`AGENTS.md:29` 同步 | C90 exit 0 + 定向 88 passed |

### 三、关键决策（用户已确认）

1. `.trae` 12 处 + `clear_database.py` 1 处 C90 → CI+配置双 exclude（非生产代码，不拆分）。
2. `ci.yml:67` C90 命令改 `ruff check . --select C90 --config lint.mccabe.max-complexity=10`（防 CLI `--exclude` 整体替换 pyproject ruff exclude 顶掉 `*/migrations/*`）。
3. mypy 以装 `types-channels==4.3.0.20260518` 为主（非批量 type: ignore）。

### 四、models.py:122 行为变化（Commit 3 显式标注）

原逻辑 `parent_id == self.pk` 恒 False：parent FK `to_field="recordcode"`（models.py:49），`parent_id`(str) 与 `pk`(int) 类型与语义均不匹配，自引用校验从未生效。修复后比对 `self.recordcode` + `Department.objects.filter(recordcode=self.parent_id)`，校验**从永假→生效**。CT-4 锚 `test_department_clean_self_parent_rejected` 先红后绿（stash 回滚实测 RED_EXIT=1）。脏数据扫描 0 条。

### 五、验证记录

```text
① ruff check . → All checks passed (exit 0) ✅
② ruff format --check . → 449 files already formatted (exit 0) ✅
③ mypy . --strict → Success: no issues found in 208 source files (exit 0) ✅
④ ruff check . --select C90 --config lint.mccabe.max-complexity=10 → exit 0（15→0）✅
⑤ 定向 test_department_service+test_services+test_service_coverage+notification → 82 passed（串行单进程）✅
⑥ 定向 apps/authusermanagement+test_init_production_data → 88 passed（串行单进程）✅
⑦ 无迁移（CT-6）；schema 无端点变更（M-3 不需重导）✅
```

### 六、遗留与关联事项

1. **变异测试 T8 / mutmut**——F-P2-4 开放基线，执行环境待定（WSL/CI），本批未跑。
2. ~~**H-1 状态机契约源裁定**~~ ✅ 已裁定 A（BF-040）；F-P2-* 其余项仍开放。
3. **complete-patterns**：本批为静态门禁/复杂度收敛非重复代码模式，G-1~G-5 不适用；`_validate_unique_constraints`/`_resolve_perms_to_add` 为拆分单源（DR-1），非新增重复。

*登记人：opencode（mimo-v2.6-flash-free） ｜ 状态：已关闭（四命令 exit 0 + 定向 82/88 passed），2026-09-24*

---

## BF-040 【已关闭】H-1 状态机契约源裁定（F-P1-4）2026-09-24
> 状态补标（2026-09-29）：依本条收尾登记人行「已关闭（裁定 A 方案2，纯文档 1+1 文件）」补齐。

### 一、问题概述

`lost→repairing` 在 Review.md（L110-111 列 `broken/lost→repairing`）、`03-业务规则与状态机.md`（仅 `broken→repairing`）、`transitions.py:44-57`（LOST 无 REPAIRING 边）三方不一致，触发根级 §1.3 `[HALT] H-1`，裁定前禁止改状态机边。

### 二、裁定与方案

- **用户裁定：A（改文档）+ 方案2（显式写出找回后送修链）**，2026-09-24。
- 理由：`03` + `transitions.py` + `02-数据模型:444`（维修记录仅 broken 可创建）+ `09-数据字典:245`（RepairAsset 约束必须 broken）四方一致；Review.md 系审查清单对称归组笔误。语义上 `lost`=找不到，须先 `found_and_return` 找回。

### 三、改动面

| # | 文件 | 改动 |
|---|------|------|
| 1 | `docs/Review/Review.md` L110-116 | L110-111 删 `lost` 仅保留 `broken→repairing` 两行；新增 `lost→found_and_return→recycled_pending→（若损坏）broken→repairing→…` 显式链；语义约定补「遗失资产仅可 found_and_return 或申请 damaged，送修前置状态必须为 broken（须先找回）」 |
| 2 | `docs/Review/融合审查报告-2026-09-23.md` | F-P1-4 行修复建议划线标 ✅；人工确认清单/修复顺序 H-1 行闭环；必填审计票红线行改「已裁定 A」 |
| 3 | `docs/BugFixed/Bug修复活账本.md` | 本条 BF-040 |

**不改**：`transitions.py`、`03-业务规则与状态机.md`、`02/09`、Service/Mixin、前端、backend 子模块——零改动。

### 四、验证

```text
① rg -n "broken.*lost.*repairing|lost.*/.*repairing" docs/Review/Review.md → 裸 lost 直连 repairing 0 命中（新增为 found_and_return 链式行）✅
② 融合报告 F-P1-4 含 ✅ 已裁定 A（方案2）；人工清单/修复顺序闭环 ✅
③ 状态机边未变 → CT-3 无需补测；无迁移（CT-6）✅
```

### 五、遗留

F-P2-* 其余项、变异测试 T8 仍开放（与 H-1 无关）。

*登记人：opencode（mimo-v2.6-flash-free） ｜ 状态：已关闭（裁定 A 方案2，纯文档 1+1 文件），2026-09-24*

---

## BF-041 【部分关闭】F-P2-1/2/3 可观测性与 AI 标注批 2026-09-24
> 状态补标（2026-09-29）：依本条收尾登记人行「首批已关闭，后续批开放」补齐为【部分关闭】——不可记「已关闭」。

### 一、问题概述

融合审查报告 F-P2 三项：F-P2-1 `/health//ready/` 零测试；F-P2-2 前端 174 处 `console.error/warn` 无结构化（A 方案首批收敛 api/stores/router）；F-P2-3 全仓 7 处 `AI_REVIEW_NEEDED` 滞留（AR-2 要求人工复查后删除或转 TODO）。

### 二、改动面

| # | 项 | 提交 | 内容 |
|---|-----|------|------|
| 1 | F-P2-1 | backend `cb7d409` | 新建 `core/tests/test_health_ready.py` 4 用例（health 200/503、ready 200/503 + H-3 不泄露异常详情；假 redis 模块注入） |
| 2 | F-P2-3 后端 | backend `3e0f165` | throttles/_lifecycle_base/scrapping 删标注改普通注释（docstring 已覆盖）；feishu `build_sign` 转 `TODO_AI_CONFIRM`（上线前核验） |
| 3 | F-P2-2 首批 + F-P2-3 前端 | frontend `0ca00bc` | 新建 `utils/logger.ts`（JSON: time/level/trace_id/module/message，DR-4 单一 console 出口）；迁 api×3 + stores×4 + router×1 共 36 处；AssetQuickScan/ContractDetails/outAssetFormEditLoader 删/改标注 |

### 三、验证

```text
① 后端：pytest core/tests/test_health_ready.py → 4 passed；ruff check/format 4 文件双绿 ✅
② rg AI_REVIEW_NEEDED 全仓 → 0 命中；TODO_AI_CONFIRM → 1（feishu 受控）✅
③ 前端：type-check/lint/format:check 三项 exit 0；vitest src/utils+src/stores → 748 passed ✅
④ rg "console\.(error|warn)" src/api src/stores src/router → 0 残留；全局 174→138（首批 -36）✅
```

### 四、遗留

- F-P2-2 后续批：composables/views/components 约 138 处（用户已批 A 分批）。
- F-P2-4 变异基线、F-P2-8~13 AC 修订仍开放（见融合报告人工清单）。

*登记人：opencode（mimo-v2.6-flash-free） ｜ 状态：首批已关闭，后续批开放，2026-09-24*

---

## BF-042 【部分关闭】F-P2-2 后续批 + F-P2-6 旧报告补标 + F-P2-4 变异基线 2026-09-24
> 状态补标（2026-09-29）：依本条收尾登记人行「F-P2-2/F-P2-6 已关闭，F-P2-4 前后端双基线归档完成（均 <80 待补测）」补齐为【部分关闭】。
> 其中 F-P2-4 的「均 <80 待补测」缺口已于 2026-09-29 独立登记为 **BF-064**（并附 BF-059 / BF-060 / BF-061 三条工具链根因），本条不再承担该缺口。

### 一、问题概述

三项收尾：① F-P2-2 后续批——`console.error/warn` 仍余 138 处散布 composables/views/components/utils；② F-P2-6——旧报告 #2/#3/#4/#8 代码已修但未标 ✅，基线状态漂移；③ F-P2-4——stryker 配置就绪但未实际跑出变异得分。

### 二、改动面

| # | 项 | 提交/产物 | 内容 |
|---|-----|------|------|
| 1 | F-P2-2 后续批 | frontend `9b49888` | `scripts/migrate-console-logger.mjs` codemod 迁 68 文件/136 处；修 3 处多行 import 插错；RecycleAssetForm `logWarn→logError`；4 处 spec 断言改 `expect.stringContaining` 对齐 JSON logger |
| 2 | F-P2-6 | 父仓（本轮） | 旧报告 #2/#3/#4/#8 补删除线 + ✅已修复 2026-09-23 + 交叉核对证据（`out_asset_service.py:115/:322`、`asset_selector.py:100`、`recycle_asset_service.py:171`、`security-scan.yml`） |
| 3 | F-P2-4 基线 | `docs/Review/mutation-baseline-2026-09-24.md` | stryker 聚焦 7 store / 120 mutants / 3m51s：score **60.00**（72 killed / 44 survived / 4 no-cov），break 80 未达 exit 1；后端 mutmut 首跑 WSL pip Errno 101 [PENDING] → 同日镜像装通后补跑 |
| 4 | F-P2-4 后端 mutmut 基线（补） | 同上文档 §二 | 阿里云 pip 镜像装 mutmut 2.5.1；原生 FS 暂存 `/tmp/am-backend-mutmut` 跑通（`/mnt/d` 9p 丢 `.bak` 崩溃）；`apps/assetmanagement/services` **1385 mutants / 4h15m：65.63%**（909 killed / 476 survived，0 timeout/untested）；runner 绝对路径 + `--ds` + `--tests-dir` |

### 三、验证

```text
① 前端全量：npx vitest run → 132 files / 1812 tests / EXIT=0 ✅（单跑口径）
② 前端三项：type-check / lint / format:check → exit 0 ✅
③ rg "console\.(error|warn)" src（非 logger、非测试）→ 生产路径残留 0；仅 logger.ts 出口×2+注释×2 ✅
④ 旧报告：rg "已修复 2026-09-23" → #2/#3/#4/#8 共 4 行 ✅
⑤ stryker 聚焦：Done in 3m51s；All files 60.00 / break 80 → exit 1（基线预期）✅；reports/mutation/mutation.html 已生成（gitignored）
⑥ WSL mutmut 首跑：pip install Network unreachable（Errno 101）→ 改阿里云镜像 `https://mirrors.aliyun.com/pypi/simple/` 装通 mutmut 2.5.1 ✅
⑦ 后端 mutmut 全量（原生 FS）：MUTMUT_RUN_EXIT=0；1385 mutants 全测完；killed 909 / survived 476 → **65.63%**；suite 基线 1373 passed ~19.6s ✅
⑧ 暂存区与 `.bak` 清理：`rm .mutmut-cache`、无残留 `*.bak`；Windows 侧 backend 仍仅 3 个修复文件未提交 ✅
```

### 四、遗留

- F-P2-4 终态：前端 60→≥80、后端 65.63→≥80（后端按 survived 行号补 Service 失败/边界/回滚；前端四 CRUD store + ignoreStatic 分批）。
- F-P2-8~13 AC 修订仍待产品确认。

*登记人：opencode（mimo-v2.6-flash-free） ｜ 状态：F-P2-2/F-P2-6 已关闭，F-P2-4 前后端双基线归档完成（均 <80 待补测），2026-09-24*

## BF-043 【已关闭】F-P2-8~13 AC 修订批量（行锁 409 收敛 + usage_type + FSM 锚 + 零代码闭环）2026-09-24
> 状态补标（2026-09-29）：依本条收尾登记人行「F-P2-8~13 全部关闭/闭环」补齐。

### 一、问题概述

F-P2-8~13 六票批量执行（用户拍板 D1 补实现 / D2 取消不回退 / D3 扫码头对齐 4.6）：F-P2-8 出库行锁超时 409 收敛为公共助手；F-P2-9 出库写 usage_type=used；F-P2-11 补 4 条 FSM 正向锚；F-P2-10/12/13 零代码闭环（证据链 / 计数更正 / 文档对齐）。

### 二、改动面

| # | 项 | 提交/产物 | 内容 |
|---|-----|------|------|
| 1 | F-P2-8 | `core/locks.py` 新增 + repair×3 / out×3 锁收敛 | `lock_row_or_409(qs, **filters)` + `ASSET_LOCKED` 常量（DR-1 单一实现）；create_repair 行为等价，complete/fail_repair 与 out_asset 3 路径**新增** 409（行为增强）；`batch_execute`/`batch_delete_execute` 捕获 `ResourceConflictError` → fail_items（保留 error_code，不中断批量） |
| 2 | F-P2-9 | `out_asset_service.py` | `_apply_outasset_to_asset` 写入 `usage_type`（BR-3 枚举 `Asset.UsageType.USED`）并入 `update_fields`；取消/删除不回退；无 API/schema 变更 |
| 3 | F-P2-11 | `test_state_machine.py` | 补 4 条 FSM 正向锚：repair_failed→damaged、found_and_return→recycled_pending、approve→scrapped、recycle→recycled_pending（mark 403 由 F-P2-5 覆盖不重复） |
| 4 | F-P2-10 | 零代码 | 证据链闭环：`base.py:153-159` 5 组 validators 含 ComplexPasswordValidator；`serializers.py:57/:129` 均挂 `validators=[validate_password]`；refresh 吊销 `test_dual_channel_auth.py:426` |
| 5 | F-P2-12 | 零代码 | 计数更正：后端生产 **8 命中 / 3 文件 / 唯一锚 AC-30/32/33/61/65**（repair×4 含 AC-61/65、recycle×3 含 AC-32/33、out_asset×1 为 F-P2-9 补 AC-30）；AC-27 落 test 锚；前端 0 维持 |
| 6 | F-P2-13 | 零代码 | AC-60f/g 文案对齐 §4.6（6 字段白名单、遮罩废弃改「直接不返回」）；实现 `public_scan_view.py:39-46` 不动 |
| 7 | 文档 | AC-29/30/60f/g/65 + 融合审查报告 | AC-29 补「usage_type 不回退」；AC-30/65 文案对齐实际 409 消息与 error_code；融合报告六票 ✅ + 清单 4/5 + 顺序 6 |
| 8 | 登记 | `complete-patterns.md` A-36 + 本条目 | 行锁 409 映射 ×6 与 batch fail_items 组装 ×3 双收敛（DR-1）；`check_duplicate_invariants.py` 复跑 |

### 三、验证

```text
① 先红后绿：test_out_asset_service 3 新用例（409 / usage_type fresh query / cancel fail_items）先 3 failed 后绿 ✅
② 定向批量：99 passed（batch 契约快照 / out / recycle / lifecycle / usermanagement batch）✅
③ 全量单测：1374 passed + 2 环境性 flaky（test_concurrent sqlite 线程锁、feishu-webhook 本地 socket 10053，隔离复跑均绿）✅
④ ruff check / format --check / C901：All checks passed（core/batch_mixins 与两 service 收敛后均 ≤10 默认阈值）✅
⑤ mypy --strict：本次 5 处改动文件 0 新增（仓库存量 27 项分布于未触达文件，含环境缺 types-python-dateutil）✅
⑥ makemigrations --dry-run：No changes detected ✅
⑦ spectacular --validate：schema 生成通过；无端点变更，baseline 不重导出 ✅
⑧ check_duplicate_invariants.py：PASS（G-1~G-5 不变量守护）✅
```

### 四、遗留

- F-P2-4 变异双基线仍 🟡（前端 60.00 / 后端 65.63，均 <80）。
- F-P2-8 收敛范围台账注明：`out_asset_service:205` OutAsset 行锁 + `out_asset_selector:172` 经 Selector 加锁路径，本批未纳入 `lock_row_or_409`（语义为「经 Selector 预筛 + 锁行」，后续批按需评估）。

*登记人：opencode ｜ 状态：F-P2-8~13 全部关闭/闭环，2026-09-24*

## BF-044 【已关闭】审查报告 Q-01/Q-02 整改（共享列表组件 script setup 泛型化 + 员工搜索端点 DRY 收敛）2026-09-25

### 〇、元信息

- **发现日期**：2026-09-25（来源：`docs/Review/opencode-2026-09-25-检查报告.md` Q-01 / Q-02，均 P2）
- **严重级别**：P2（规范偏离 + 契约失真；无 P0/P1）
- **影响范围**：
  - Q-01：`src/components/commoncomponents/CommonList.vue`、`SmartListContainer.vue`、`src/types/common.ts`（`SmartListContainerExpose`）；**间接受影响的 10 个 `*Details.vue` 消费方最终零改动**。
  - Q-02：`src/api/user.ts`、`src/api/authusers.ts`、`src/types/authuser.ts`、`src/stores/authUserStore.ts`、`src/components/system/BindAuthUserDialog.vue`。
  - 新增测试：`src/components/commoncomponents/__tests__/CommonList.spec.ts`、`SmartListContainer.spec.ts`。
  - **跨端契约变更：无**（未增删改端点、响应结构、状态枚举、分页参数名、日期格式）。

### 一、问题现象

1. **Q-01（F6 规范）**：`CommonList.vue`（原 L83）与 `SmartListContainer.vue`（原 L46）以 `export default defineComponent` 编写，未采用项目强制的 `<script setup lang="ts">`；两组件被 284 处引用。
2. **Q-02（FR-3 / DR-1）**：端点 `GET /users/employees/search/` 在 API 层三处独立 `request.get` 实现（同文件 2 处 + 跨文件 1 处）。
3. **连带缺陷 a（类型失真）**：跨文件那份 `searchEmployees` 把 DRF 分页对象当数组直接返回；`unwrapResponse`（`src/api/request.ts:418-424`）只解包 `res.data`、不碰 `.results`，故返回值不可用。
4. **连带缺陷 b（虚构字段）**：`EmployeeBrief` 类型与 `auth_user_username` 字段在前端存在，但后端全仓（含 `api-schema-baseline.json`）零命中；`BindAuthUserDialog` 依赖该字段渲染「绑定用户」栏，导致**恒显示「无」**。
5. **连带缺陷 c（被掩盖的类型漏洞）**：迁移使 vue-tsc 暴露 **11 处** `selectedRows: object[]` 传入各实体数组（`AssetDetail[]` / `Contract[]` / …）的类型错误——原 Options API 组件的插槽 props 被推断为 `any`，长期掩盖。

### 二、根因

| # | 环节 | 事实 |
|:--|:-----|:-----|
| 1 | 组件写法 | `CommonList.vue` 原 L90 `export default defineComponent({...})`、`SmartListContainer.vue` 原 L97 同构；违反 `vue-assetmanagement/AGENTS.md` §1.2「强制 `<script setup lang="ts">`，禁止 Options API」 |
| 2 | 端点重复 | `api/user.ts:66`（`getFuzzySearch`）、`api/user.ts:98`（`getUserByName`）、`api/authusers.ts:111`（`searchEmployees`）各自 `request.get` 同一 URL；违反 FR-3 唯一实现 |
| 3 | 分页解包 | 后端 `apps/usermanagement/views/employee_view.py:301` `global_search` 经 `paginate_queryset` + `get_paginated_response`（L316/L319）→ 返回 `{count,next,previous,results}`；search 路径 `get_serializer_class`（L154-162）返回 `EmployeeSerializer`（`employee_serializers.py:14-49`，字段集**不含** `auth_user`） |
| 4 | 绑定员工序列化 | by-auth-user 路径 `employee_view.py:178` 用 `EmployeeDetailSerializer`（`employee_serializers.py:70-72`，`fields = "__all__"`）→ 含 `auth_user`，指向 `authusermanagement/models.py:110` `auth_id = AutoField(primary_key=True)`，故序列化为 **number** |
| 5 | 虚构字段成因 | 前端按「嵌套 username」直觉自造 `auth_user_username`，后端从不返回；`EmployeeBrief` 亦为自造类型 |
| 6 | 类型漏洞成因 | Options API 组件的插槽 props 推断为 `any`，掩盖 `object[]` → 实体数组的不兼容；`<script setup>` 会精确推断插槽 props 类型，故漏洞现形 |

### 三、修复方案

| # | 变更 | 文件 |
|:--|:-----|:-----|
| 1 | Options API → `<script setup lang="ts" generic="T extends object">`；21 props → 类型化 `Props` + `withDefaults`（默认值逐项对齐原声明）；10 emits → 类型化 `defineEmits`（顺带消除 3 处 `@typescript-eslint/no-explicit-any` 豁免）；`expose()` → `defineExpose()`；模板 `$emit(...)` → `emit(...)`；泛型 `T` 贯通 `data`/`selectionChange`/`edit`/`delete`/`detail` | `CommonList.vue`（L83/L115/L134/L224） |
| 2 | `getRowKey` 等价重构：提取模块级 `ROW_KEY_FALLBACK_FIELDS` + 纯函数 `asRowKey`，主函数降为单循环（复杂度 11→4，消解迁移触发的 `complexity: 10` 门禁命中） | `CommonList.vue`（L163/L189） |
| 3 | `setup(props, { slots, expose })` 整体并入顶层；3 props → 类型化声明 + `withDefaults`；`usePaginationSearch<object>` → `<T>`；删除 setup 返回值中的 `slots`（模板只用 `$slots`，该项冗余） | `SmartListContainer.vue`（L46/L104/L125/L178） |
| 4 | `SmartListContainerExpose` → `SmartListContainerExpose<T = unknown>`，`data: Ref<unknown[]>` → `Ref<T[]>`；**默认参数保证 10 个消费方 `ref<SmartListContainerExpose \| null>` 零改动** | `types/common.ts`（L131） |
| 5 | `getUserByName` 改为委托唯一实现 `userAPI.getFuzzySearch({ keyword })`，保留 `try/catch + logError` | `api/user.ts`（L95/L97） |
| 6 | `searchEmployees` 改为复用 `userAPI.getFuzzySearch`，**正确取 `.results`** 返回 `Employee[]` | `api/authusers.ts`（L118） |
| 7 | 删除虚构 `EmployeeBrief`；新增 `BoundEmployee extends Employee { auth_user: number \| null }`；`getBoundEmployee` 返回类型改为 `BoundEmployee` | `types/authuser.ts`（L189）、`api/authusers.ts`（L61） |
| 8 | Store 签名同步：`searchEmployees: (keyword: string) => Promise<Employee[]>`、`getBoundEmployee: (authId: number) => Promise<BoundEmployee>` | `stores/authUserStore.ts`（L32/L39） |
| 9 | 「绑定用户」栏由 `boundEmployee.auth_user_username \|\| '无'` 改为 `props.authUser?.username \|\| '无'`（修真实 UI bug） | `system/BindAuthUserDialog.vue`（L34） |
| 10 | 补测试锚：两组件迁移前**零覆盖**却共 284 处引用（CT-1/CT-4 强制）。`CommonList.spec.ts` 15 例（默认值/分页事件桥/选择·编辑·删除·详情事件桥/搜索透传/`getRowKey` 三类语义/expose 委派与 API 面/插槽透传）；`SmartListContainer.spec.ts` 12 例（自动加载参数优先级 `initialPageSize` > `defaultPageSize` > 20 / `autoLoad=false` / 加载失败双通道与消息回落 / 默认插槽 18 项契约 / 选中行追踪 / 命名插槽透传 / expose 委派） | 两处 `__tests__/` 新建 |

### 四、对抗审核

- **行号漂移**：登记行号均以修复后工作区 `Select-String` 实测（`CommonList.vue` L83/L115/L134/L163/L189/L224、`SmartListContainer.vue` L46/L104/L125/L178、`types/common.ts` L131、`api/user.ts` L60/L95/L97、`api/authusers.ts` L61/L118、`types/authuser.ts` L189、`authUserStore.ts` L32/L39、`BindAuthUserDialog.vue` L34），**未沿用报告第 2 节原始定位**（原 L83/L46/L66/L98/L111 已因迁移漂移，报告该两行已划线标注）。
- **虚报验证**：本条目「五、验证记录」所列命令与数字**全部实际执行**，无「未运行」项通过声称。首轮 `type-check` 曾报 11 errors、`vitest` 曾 2 failed、Prettier 曾 1 warn，均为真实失败并已修复，非事后美化。
- **扫描对抗点（发现更深问题，未静默吞掉）**：
  1. **覆盖率门禁盲区**——`vitest.config.ts:22` 的 `coverage.include` 为 `['src/**/*.ts']`，**不含 `.vue`**，故所有组件覆盖率对 80%/90% 门禁**结构性不可见**。本条两个组件的真实覆盖率（`CommonList.vue` 100% 行/语句/函数、95% 分支；`SmartListContainer.vue` 92.59% 行、92.85% 语句、100% 函数）系定向 `--coverage.include` 实测所得，**不在官方门禁口径内**。详见「六、遗留」①。
  2. **`CommonList` expose 的可选链只防 null 不防缺方法**——`actionsRef.value?.search()` 在子实例存在但未 expose `search` 时抛 `TypeError`。生产环境 `CommonListActions.vue`（已是 script setup）确有 expose，故非现网缺陷；但该写法**不构成「子实例缺失即安全」的保证**。曾误写为测试预期并失败，已改为锁定真实契约（expose API 面为函数）。详见「六、遗留」②。
  3. **复杂度门禁为仓外存量欠债**——`npx eslint . --rule "complexity: ['error', 10]"` 全仓 53 errors，其中**仅 1 处属本次触及文件**（`CommonList.vue:163`，已修）；其余 52 处分布于 20+ 未触达文件，属存量。详见「六、遗留」③。
- **契约影响**：**无跨端契约变更**。未新增/修改/删除任何端点，未改 `code`/`data`/`message` 根结构、状态枚举键名、分页参数名、日期格式。Q-02 仅复用既有端点并修正前端类型与解包；Q-01 为组件内部写法与类型泛化。故 **api-schema 基线不需重导出**（与报告 L28「本次审查无端点变更，基线未变化」口径一致）。
- **登记遗漏**：本条三处登记源已互查——报告 Q-01/Q-02 行（划线 + 指向「7. 修复追踪」）↔ 报告「7. 修复追踪」2 小节 12 行 ↔ 台账 A-37/A-38 + v2.9.46 三行变更记录 ↔ 本 BF-044。台账 v2.9.45 及历史条目未改写（历史快照豁免）。

### 五、验证记录

```text
① npm run type-check（vue-tsc --build）                → 0（首轮 11 errors，已由泛型化消解）
② npm run lint（eslint . --fix）                        → 0
③ npm run format:check（prettier --check src/）         → 0（首轮 SmartListContainer.spec.ts 1 warn，--write 后复跑全绿）
④ npx vitest run（整改面 src/components+api+stores）      → 74 files / 996 tests passed
⑤ npx vitest run（全量）                                → 136 files / 1860 tests passed
   （基线 133 files / 1831 tests → 净增 3 files / 29 tests）
⑥ npx eslint <CommonList|SmartListContainer>.vue --rule "complexity: ['error', 10]" → 0
   （全仓同规则 53 errors，本次触及文件迁移前 1 → 迁移后 0）
⑦ npx vitest run --coverage（项目官方口径）              → 0；整体 93.15% stmts / 87.54% branch / 87.45% func / 93.93% lines（≥80%）；Store 97.89% / 92.17% / 94.55% / 98.38%（≥90%）
⑧ npx vitest run --coverage --coverage.include="src/components/commoncomponents/**"（定向）→ CommonList.vue 100% stmts/funcs/lines、95% branch；SmartListContainer.vue 92.85% stmts、90.9% branch、100% funcs、92.59% lines；authUserStore.ts 94.11% stmts / 92.85% funcs / 96.96% lines
⑨ python scripts/check_duplicate_invariants.py           → PASS（G-1~G-5 全部通过）
⑩ python scripts/check_frontend_invariants.py            → PASS（FR-6 composables 46 文件 0 孤儿；FR-8 stores 30 文件 0 超限）
⑪ 端点 DRY grep：生产代码 `/users/employees/search` 的 request.get → 1 处（api/user.ts:66）；另 3 处命中均在 api/__tests__/user.spec.ts 断言文本
⑫ EmployeeBrief 全仓 grep                                → 0 命中
⑬ auth_user_username 后端仓库 grep（含 api-schema-baseline.json）→ 0 命中
⑭ Options API 全仓清零：117 个 .vue 中 `export default defineComponent` = 0、`methods: {`（2 空格缩进）= 0、`<script lang="ts">` = 0
⑮ 规模红线（DR-5）：CommonList.vue 359 行、SmartListContainer.vue 204 行、两 spec 290/230 行，均 ≤500
```

### 六、遗留与关联事项

1. **[待决策] 覆盖率门禁不含 `.vue`**：`vitest.config.ts:22` `coverage.include: ['src/**/*.ts']` 使组件覆盖率对 80%/90% 门禁不可见，CT-2「核心模块覆盖率」在组件层实际未受门禁保护。修法为并入 `'src/**/*.vue'`，但会立即拉低整体数值（大量存量组件零覆盖，如 `commoncomponents/InfoCard.vue`、`NotificationBell.vue` 等实测 0%），需先补测试或分阶段设阈值。属工程配置标准变更（前端 AGENTS §4.1 自主范围），**本次未擅自改动**，提请决策。
2. **[已记录·不改] expose 可选链语义**：`CommonList.vue` 的 `actionsRef.value?.search()` 仅在子实例为 null 时短路；子实例存在但缺方法时抛错。生产 `CommonListActions.vue` 已 expose `search`/`clearSearch`，当前无实际风险；如未来该子组件 expose 面变化需同步复核。
3. **[待决策] 复杂度存量欠债 52 处**：全仓 `complexity: 10` 门禁 53 errors，本次触及文件已清零，其余 52 处分布于 `AssetForm.vue`、`*BatchImport.config.ts`、`useOutAssetDetailCards.ts`、`createEntityStore.ts`、`request.ts` 等未触达文件。规范未把该规则写入 eslint 配置（`npm run lint` 不含），故为人工核验项。建议纳入后续批次并考虑先入 eslint 配置 + 沙盒警告期（根级 §5.4）。
4. **关联未处理项**：报告 Q-03（页面绕过 store/api 直连请求层）、Q-05（两处 flaky 测试）本次未动，仍在「6. 结论与后续建议」待办清单中。Q-05 前端项（`src/router/__tests__/index.spec.ts`）在本次全量跑（③④⑤）中 136 files 全绿通过，但隔离复跑亦通过，**未复现**，故仍按存量 flaky 挂账不关闭。
5. **提交状态**：本条目登记时全部改动仍在工作区未提交（type-check/lint/format/test/coverage/护栏均已绿）。按规范需用户显式要求才提交。

*登记人：opencode ｜ 状态：已关闭，完成验证，2026-09-25*

---

## BF-045 【部分关闭】审查报告 Q-05 两处 flaky 测试（前端 router spec mock 竞态 + 后端 SQLite 行级锁）2026-09-26

### 〇、元信息

- **发现日期**：2026-09-25（来源：`docs/Review/opencode-2026-09-25-检查报告.md` Q-05）；**关闭日期**：2026-09-26
- **严重级别**：P2（测试可靠性；不污染生产代码）
- **状态口径**：**部分关闭**。仓内潜在竞态已消除并加固；但触发超时的**环境性成因未在仓内修复**（见"六、遗留"第 1 条），故不宣称 Q-05 全面关闭。
- **影响范围**：
  - 前端：`src/router/__tests__/index.spec.ts`（mock 机制重写，10 用例语义不变）。
  - 后端：`apps/unregisteredasset/tests/test_concurrent.py`（新增 `requires_row_lock` 守卫 + 4 处装饰器；串行锚 `test_approve_then_approve_fails` 不受影响）。
  - **跨端契约变更：无**。

### 一、问题现象

1. **前端**：`npx vitest run`（默认并行）下 `src/router/__tests__/index.spec.ts` 间歇失败，报 `TypeError: vueRouter.__getCapturedConfig is not a function`；同批次 `usePermission.spec.ts`、`useDarkMode.spec.ts`、`assetLifecycleService.spec.ts` 亦出现超时失败。
2. **后端**：`test_concurrent.py` 4 个多线程用例在 SQLite 下"恰好一个成功"类断言随机抖动。

### 二、根因（实测取证，非推测）

| # | 环节 | 事实 |
|:--|:-----|:-----|
| 1 | 前端·超时非阈值问题 | 隔离运行 3 轮，10 用例峰值 **157/183ms**，全绿；默认并行下文件耗时放大至 **18.2s / 74s**，且同时出现 60s、45s 的其他文件超时——**多文件同时劣化**，非单 spec 慢 |
| 2 | 前端·环境成因 | 本机 16 逻辑核、15.73GB 内存但**仅 4.92GB 空闲**；vitest v4 默认 `maxWorkers ≈ cores-1 = 15`，15 个 happy-dom worker + coverage 在该内存下必然争用 |
| 3 | 前端·反证（关键） | `npx vitest run --maxWorkers=4` → **137 files / 1867 tests 全绿**（64.81s、74.02s 两次复跑稳定）；默认并行 3 跑 2 败 |
| 4 | 前端·timeout 无效（已实测否决） | 曾加 `vi.setConfig({ testTimeout: 15_000 })`，默认并行下仍 `4 failed | 74s`（74s ≫ 15s）→ 证明放宽阈值**不能**解决，且属掩盖。**已撤回** |
| 5 | 前端·真实竞态 | 原 mock 以 `__getCapturedConfig` 导出配合 `vi.resetModules()`；reset 后可能返回不含该导出的模块实例 → `__getCapturedConfig is not a function` |
| 6 | 后端·成因 | SQLite 不支持 `select_for_update` 行级锁，多线程写入退化为库级写锁争用，断言时序不可靠 |

### 三、修复内容

| # | 变更 | 文件 |
|:--|:-----|:-----|
| 1 | 全部 mock 提升至 `vi.hoisted()` 持有器（`mockCapturedConfig` / `mockCreateRouter` / `mockCreateWebHistory` / `mockSetupAuthGuard`），`resetModules()` 不再影响 mock 身份 | `src/router/__tests__/index.spec.ts` |
| 2 | `loadRouter()` 不再 `import('vue-router')` 取 mock（消除 reset 后取到非 mock 实例的路径），直读持有器；删除 `__getCapturedConfig` 机制 | 同上 |
| 3 | **不**放宽 `testTimeout`（依据根因第 4 条实测否决），文件头注释留证 | 同上 |
| 4 | 新增 `requires_row_lock = pytest.mark.skipif(connection.vendor == "sqlite", ...)`，标注 CI 为 `postgres:16` 故守卫不生效 | `apps/unregisteredasset/tests/test_concurrent.py` |
| 5 | 4 个真并发用例加该装饰器；串行语义用例保持无条件执行 | 同上 |

### 四、验证命令与结果

```text
① npx vitest run src/router/__tests__/index.spec.ts（隔离）        → 10 passed（tests 299ms）
② npx vitest run --maxWorkers=4（全量，两次复跑）                 → 137 files / 1867 tests passed（64.81s / 74.02s）
③ npx vitest run（默认并行，对照组）                              → 3 跑 2 败（18.2s/74s/60s/45s 多文件超时）→ 确认为环境争用
④ npm run type-check / npm run lint / npm run format:check        → 均 0
⑤ npx vitest run --maxWorkers=4 --coverage --coverage.threshold=80 → 137/1867 passed；整体 93.11% stmts / 87.56% branch / 87.32% func / 93.89% lines（≥80%）
⑥ npx vitest run --maxWorkers=4 --coverage --coverage.include="src/stores/**/*.ts" --coverage.threshold=90 → Store 97.72% / 92.17% / 93.91% / 98.19%（≥90%）
⑦ python -m pytest apps/unregisteredasset/tests/test_concurrent.py -v → 5 passed（skipif 未触发）
⑧ connection.vendor 探针                                        → postgresql（本地与 CI 同为 PG，守卫为防御性空操作）
⑨ python -m pytest apps/unregisteredasset -q                     → 142 passed
⑩ python -m ruff check .                                          → All checks passed（修 1 处 I001 import 顺序）
⑪ python -m ruff check . --select C90 --config lint.mccabe.max-complexity=10 → All checks passed
⑫ mypy --strict 回归对比（git stash 基线法）                     → HEAD 35 errors / 当前 35 errors → **零回归**（存量债务）
⑬ DR-5 规模：test_concurrent.py 337 行、index.spec.ts 123 行，均 ≤500
```

### 五、关联登记

- 仓内重复模式侧同步登记 `Rules_Fiels/Duplicate_Codes/complete-patterns.md` A-39（Q-03）、A-40（Q-04）。
- Q-04 同型遗留另立 **BF-046**。

### 六、遗留与关联事项

1. **[未修复·待决策] 环境性超时成因**：本机空闲内存仅 4.92GB，默认 15 workers 下仍会随机超时。**本次刻意未把 `maxWorkers` 写入 `vitest.config.ts`**——为迁就单机内存状况改共享工程配置不妥，且 CI（GitHub Actions 通常 4 核）会自动取 `maxWorkers=3`，无此问题。**本地跑全量请用 `npx vitest run --maxWorkers=4`**。若需固化，属前端 AGENTS §4.1 工程配置自主范围，须先决策（可考虑按 `os.cpus()` 与可用内存动态取值）。
   > **【2026-09-29 决策反转·本条已被推翻并落地】** 上述「刻意未固化」决策其后被**推翻**，并已在 BF-046 落地：`vue-assetmanagement/vitest.config.ts:19` 现为 `maxWorkers: 4`（含 `:14-18` 共 5 行【Q-05】注释），落地记录见 **BF-046 改动表第 10 行（本文件 :2600）**。
   > 原文保留为历史快照，**现行口径以 BF-046 / `vitest.config.ts:19` 为准**；本条「未修复·待决策」标记随之失效（实测 2026-09-29：`vitest.config.ts` 命中 `maxWorkers: 4`）。
2. **[存量债务·未处理] `mypy --strict` 本文件 28 errors**：经 `git stash` 基线对比，HEAD 与当前在系统 Python 下**同为 35 errors / 6 files → 零回归**。另注：解释器不同结论不同——用项目 `.venv` 跑为 **28 errors / 1 file**（系统 Python 多出的 5 文件 7 处系环境解析差异，与报告 Q-08「.venv 复跑归零」口径一致）。即本文件 28 处**为真实存量注解债**（集中在测试体缺返回标注，如 L301/L303/L315），非本次引入；不在本批范围，避免范围蔓延。
3. **[存量·未处理] pytest teardown 告警**：`test_concurrent.py` 结束时报 `Error when trying to teardown test databases ... 6 个会话仍占用`——线程用例连接未显式关闭所致，为告警非失败（exit 0）。属独立技术债。
4. **提交状态**：本条目登记时全部改动仍在工作区未提交。按规范需用户显式要求才提交。

*登记人：opencode ｜ 状态：部分关闭（仓内竞态已消除；环境性成因留账待决策），2026-09-26*

---

## BF-046 【已关闭】导出族 Excel 导出分页被后端 MAX_PAGE_SIZE 静默截断（Q-04 同型遗留）2026-09-26

### 〇、元信息

- **登记日期**：2026-09-26（来源：Q-04 整改核查中发现的同型缺陷；**非**报告原条目）
- **严重级别**：P1（数据不完整导出，且**静默无提示**；影响财务/台账类交付物）
- **状态**：✅ 已关闭（2026-09-26，服务端流式导出落地；原「待决策事项」已由用户拍板，见第三节）
- **影响范围**：`src/composables/useOperationLogExcelExport.ts`、`src/composables/useUserExcelExport.ts`（前端）；`core/excel_export/`、`apps/assetmanagement/operation_log_*.py`、`apps/usermanagement/views/employee_view.py`、`config/settings/base.py`、`api-schema-baseline.json`（后端）

### 一、问题现象

两处导出以「当前筛选下的总条数」作为 `page_size` 传入后端：

- `useOperationLogExcelExport.ts:59` → `page_size: store.pagination.total`
- `useUserExcelExport.ts:75` → `page_size: userStore.pagination.total`

后端 `core/constants.py:12 MAX_PAGE_SIZE = 100`、`core/pagination.py:35` 静默钳位，故当 `total > 100` 时导出结果**只含前 100 条**，且不报错、不告警。

### 二、根因

与 Q-04 已关闭部分（`page_size: 9999`，登记为 `complete-patterns.md` A-40）**同型**：前端对分页上限的假设与后端钳位不一致。区别在于 A-40 是「硬编码超大值意图取全量」，本条是「动态传 total，同样被钳位」——故 Q-04 整改时**未覆盖**到这两处。

### 三、决策（用户 2026-09-26 拍板）

原「待决策事项」三问的结论：

1. **导出语义 → 选"导出全部匹配数据"**，实现路径为**新增服务端导出端点**（而非循环翻页）——循环翻页仍受每页 100 条钳位且需多次往返，绕不开根因。已新增 `GET /api/v1/assets/operation-logs/export/` 与 `GET /api/v1/users/employees/export/`，流式生成 xlsx。
2. **前端防御 → 已落**，但升级为**前置拦截**而非事后告警：超上限时 `ElMessageBox.confirm` 询问是否仅导出前 `EXPORT_MAX_ROWS` 条，用户取消即中止，不再静默产出残缺文件。
3. **循环翻页 → 不采用**，理由同上；分页能力改由导出端点的 `?limit=` / `?offset=` 提供（缺省为全量，任一存在即启用分批）。

配套安全兜底（防"全量导出打爆内存"这一原待决策未覆盖的新风险）：

- 后端 `EXPORT_MAX_ROWS`（`config/settings/base.py`，默认 10000）：省略 `limit`/`offset` 的全量导出若总行数超限 → **400 明确报错**；`limit` 超过上限时钳制到上限。
- 前端 `VITE_EXPORT_MAX_ROWS` 镜像同值（`src/api/config.ts`），使前端能在发请求前就给出提示。
- 响应头 `X-Export-Max-Rows` / `X-Export-Total-Count` 回传实际上限与本次实际导出条数，并加入 `CORS_EXPOSE_HEADERS` 供浏览器读取。

### 四、证据与不确定性标注

- **可验证**：两处 `page_size` 取 `pagination.total`（源码直读）；后端 `MAX_PAGE_SIZE = 100` 与 `core/pagination.py:35` 钳位（源码直读）。
- **[推测·未实测]** "导出结果实际只含前 100 条"系由上述两事实**推导**，本次**未构造 >100 条数据做端到端复现**。修复前应先补一个 >100 条的回归测试确认现象。
- 测试 mock 中的 `2000/200/1500` 字面量（`useOperationLogExcelExport.spec.ts` 等）属测试数据，不构成生产缺陷，但会掩盖真实上限，建议同步对齐。

### 五、修复内容

| # | 端 | 内容 |
|---|-----|------|
| 1 | 后端 | 新建 `core/excel_export/`（`widths.py` / `workbook.py` / `streaming.py` / `mixin.py` / `schema.py`）：write-only 工作簿 + 临时文件落盘 + ZIP worksheet XML 注入列宽 + `StreamingExcelResponse`（`close()` 清理临时目录，避免 Windows 文件占用）；`build_excel_export_response(..., params=...)` 统一解析 `limit`/`offset`，Mixin 与 APIView 共用同一分批语义 |
| 2 | 后端 | `_export_mixin.py` 删除，11 个 ViewSet（含 `EmployeeViewSet`）统一改用 `core.excel_export.ExportExcelMixin`——员工导出原因跨 app 无法 import 而会形成第二份实现（DR-4 工具单一仓库） |
| 3 | 后端 | `OperationLogSelector.build_operation_logs_queryset()` + `OperationLogQueryService.query_operation_logs_queryset()` 承载行级 scope（`_scope_by_user`：部门列表含子部门，空列表 `.none()`，`None` 不限）；`parse_operation_log_filters` 成为列表/导出参数解析单一入口 |
| 4 | 后端 | `EmployeeViewSet` 补显式 `get_permissions()` 分支（`export_excel` → `CanExportExcel`，否则会落回通用 `IsAuthenticated`）；导出列不含 `employee_phone`（最小化批量落盘 PII） |
| 5 | 后端 | `parse_operation_log_filters` 返回类型由 `(filters | None, error | None)` 二元组改为抛 `InvalidOperationLogFilters`——二元组无法在类型层表达关联不变量，调用方 `filters.as_selector_kwargs()` 必触发 `mypy --strict` 的 `union-attr`（CI 门禁） |
| 6 | 后端 | `core/excel_export/schema.py` 提供 `EXPORT_PAGINATION_PARAMETERS` / `XLSX_EXPORT_RESPONSES` 复用片段；Mixin 首挂 `@extend_schema`（见第七节契约变更） |
| 7 | 前端 | 新建 `src/utils/fileDownload.ts::downloadBlobFile()` 收敛 `excelExporter.ts` 与 `batchImport/templateExport.ts` 两套 Blob 下载（DR-4），含 `Content-Disposition` 的 `filename` / `filename*` 解析 |
| 8 | 前端 | `request.ts` 新增 `getBlob`；错误响应为 JSON-in-Blob 时经 `readBlobErrorData` 解析后走统一 `showErrorMessage`（否则 400/403 的中文提示会被当 Blob 丢弃） |
| 9 | 前端 | 新建 `src/composables/useServerExcelExport.ts`（空数据拦截 → 超上限确认 → >1000 条二次确认 → `getBlob` → `downloadBlobFile` → 读 `X-Export-Total-Count`）；两个实体 composable 改为薄壳；`OperationLogDetails.vue` 抽取 `buildQueryParams()` 供列表与导出共用（DR-1） |
| 10 | 配置 | `vitest.config.ts` 写入 `maxWorkers: 4` 与 `VITE_EXPORT_MAX_ROWS`（Q-05 的「刻意未固化」决策由本次落地，见 BF-045 第六节遗留 1） |

### 六、验证

```text
① pytest apps/assetmanagement apps/usermanagement core -q   → 1229 passed / 0 failed（794s，串行单进程）
② 定向四套件（test_excel_export / test_export_excel /
   test_operation_log_export_scope / test_employee_export）    → 50 passed
③ 覆盖率：--cov=core.excel_export → __init__ 100% / schema 100% /
   workbook 100% / streaming 96% / mixin 89% / widths 89%；
   operation_log_service.py 99%；整体 97.37%（CT-2 门槛 80%）✅
④ ruff check . --config lint.mccabe.max-complexity=10（含 C90）→ All checks passed
⑤ mypy . --strict → 27 errors in 12 files，逐文件比对与本次 22 个
   改动/新增文件**零交集** → 零新增（存量债见 BF-045 第六节遗留 2）
⑥ manage.py spectacular --format openapi-json --file api-schema-baseline.json --validate
   → 端点 183 → 185；新增 2、删除 0、components 零漂移
⑦ oasdiff breaking（HEAD 基线 vs 当前，v1.29.1）→ 10 × response-media-type-removed
   （即第七节已人工确认项）；oasdiff diff 另报 1 处 description 漂移，
   系 unregistered-assets 端点 docstring 早于本次未重导的存量漂移
⑧ check_duplicate_invariants.py → PASS（G-1~G-5）
⑨ 前端 npx vitest run → 138 files / 1878 tests passed
⑩ 前端 type-check / lint / format:check → 均 0
⑪ 前端覆盖率 → statements 92.7% / branches 87.33% /
   functions 87.14% / lines 93.49%，无阈值错误
```

### 七、契约变更（已人工确认，§1.3 红线）

`ExportExcelMixin` 首次挂 `@extend_schema`，致 **10 个既有资产导出端点**的 200 响应声明由 `application/json` 更正为 xlsx 二进制。事实依据：该 10 个端点运行时本就 `as_attachment=True` + xlsx Content-Type，旧声明是**失真文档**；`components` 与响应体结构零变化。

- `oasdiff breaking` 判定为 10 × `response-media-type-removed`（破坏性）。
- 无运行时消费方依赖旧声明：全仓仅 CI 与文档引用基线；前端这 10 个资产导出仍走客户端 `useExcelExport.ts` 路径。
- CI `api-schema-check` 该步实测**不拦截**（本地 v1.29.1 对合成真破坏用例 `request-parameter-removed` 亦退出 0），但工具判定为权威结论，故按 §1.3 走人工确认。
- **用户 2026-09-26 拍板：完整修正并留痕**（备选方案"仅加参数、media type 另立 BF-048"已被否决）。

### 八、遗留

1. **BF-047**：员工导出不接受列表搜索/状态/部门筛选（见下条）。
2. 变异测试（`mutmut`）未覆盖本次新增的 `core/excel_export/`，沿用 BF-042 记录的 65.63% 全局基线，未单独提分。

*登记人：opencode ｜ 状态：已关闭（2026-09-26），BF-047 遗留待办*

---

## BF-047 【已关闭】员工导出未接列表筛选条件（BF-046 衍生）2026-09-26

### 〇、元信息

- **登记日期**：2026-09-26（来源：BF-046 落地核查中发现的衍生缺口）
- **严重级别**：P2（导出内容 ≠ 列表所见；不静默、不丢数据，但预期不符）
- **状态**：✅ 已关闭（2026-09-26，取行口径单一入口落地；原「待决策事项」已由用户拍板，见第三节）
- **影响范围**：`core/excel_export/mixin.py`、`apps/usermanagement/employee_filters.py`（新建）、`apps/usermanagement/selectors.py`、`apps/usermanagement/views/employee_view.py`、`api-schema-baseline.json`（后端）；`src/composables/useUserExcelExport.ts`、`src/composables/usePaginationSearchState.ts`、`src/stores/userStore.ts`、`src/components/componentsdetails/UserDetails.vue`（前端）
- **衍生缺口**：BF-048（导出行级 RBAC 缺失，本次登记未修）、BF-049（导出端点 OpenAPI 未声明其实际支持的筛选参数，本次登记未修）

### 一、问题现象

员工列表支持 `search`（`global_search`）、状态、部门等筛选，但**导出端点不接受任何筛选参数**——用户在列表页筛选出 20 条后点击导出，得到的仍是全量员工（受 `EXPORT_MAX_ROWS` 兜底）。

核对范围后确认该现象是**三个口径分叉的共同结果**，而非单点缺陷：

| 路径 | `keyword` | `employee_status` | `department_code` |
|---|:---:|:---:|:---:|
| 列表 `list` | ❌ 不消费（只认 DRF `search=`） | ✅ | ⚠️ 只认别名 `employee_department__department_code` |
| 搜索 `search` | ✅ | ❌ | ❌ 静默失效 |
| 统计 `statistics` | ❌ | ❌ 忽略 | ❌ 忽略 |
| 导出 `export` | ❌ | ❌ | ❌ 忽略 |

其中 `department_code` 两分支静默失效的成因：`filterset_fields` 的值必须是**模型字段路径**，而 `department_code` 挂在关联对象上（`Employee` 上无此字段），写 `filterset_fields = ["department_code"]` 会在构造 filterset 时抛 `FieldDoesNotExist`，于是前端只能按 ORM 路径传别名；搜索端点则压根不跑 `filter_queryset`。

对照：操作日志侧已由 `parse_operation_log_filters` 让列表与导出共用同一参数入口，**无此缺口**。

### 二、根因

`EmployeeViewSet.get_queryset()` 不读取 `request` 的筛选参数（列表的筛选在 `get_serializer_class` / 分页链中另行处理），而 `ExportExcelMixin` 直接复用 `self.get_queryset()`——可见性一致（BF-046 的设计目标），但**筛选一致性**未随之实现。

更深一层：员工域的筛选解析散落在 4 条路径里各自实现，`ExportExcelMixin` 又是**全 app 共享**的单点，二者叠加即必然分叉。故本次不补第 N 处解析，而是**建立唯一入口**（DR-1/DR-3）。

### 三、决策（用户 2026-09-26 拍板）

原「待决策事项」两问的结论：

1. **导出是否需要支持筛选 → 需要**，且筛选参数契约与列表端点**逐字对齐**（B2 方案：前端保持只传 `department_code`，后端同时接受业务名与 ORM 别名，不改前端调用方）。
2. **是否在 UI 上标注"导出为全量" → 不需要**，改为让导出真正跟随当前可见范围，从根上消除误解可能。

关键取舍（均经用户确认）：

- **不采用**「把 `mixin.py` 改成 `self.filter_queryset(self.get_queryset())`」这一看似一行的修法：全局 `DEFAULT_FILTER_BACKENDS` 生效，`filter_queryset` 对资产端点**并非 no-op**，该改法会让 10 个资产导出端点的行序/搜索行为同步改变（越界）。改为新增 `get_export_queryset()` 钩子、**只由 `EmployeeViewSet` 覆写**，其余 11 个端点默认行为字节级不变。
- **统计端点按「列表当前可见范围的聚合」修复**（而非保持全量），使其 OpenAPI 已声明的筛选参数不再形同虚设。
- **BF-048 单独登记**：行级数据权限（RBAC）与筛选口径是两件事，不在本次夹带修复。

### 四、修复内容

| # | 端 | 内容 |
|---|-----|------|
| 1 | 后端 | `core/excel_export/mixin.py` 新增 `get_export_queryset()` 钩子（默认 `return self.get_queryset()`），`export_excel` 改走该钩子；11 个未覆写端点行为不变（`test_export_excel.py` 3 条契约测试锁定） |
| 2 | 后端 | 新建 `apps/usermanagement/employee_filters.py`，定义**本项目首个 FilterSet 类** `EmployeeFilterSet`——`department_code` 显式 `field_name` 映射到关联字段路径，兼收 ORM 别名；`employee_status` 用 `ChoiceFilter` 保住既有的取值校验与 OpenAPI enum 文档（改 `CharFilter` 会静默降级，见第六节） |
| 3 | 后端 | `EmployeeSelector.search_employees(keyword, base=None)`：传 `base` 时在调用方 queryset 上叠搜索条件，保留调用方的 `select_related`/行基准 |
| 4 | 后端 | `EmployeeSelector.get_employee_statistics(queryset=None)`：三处独立 `Employee.objects` 收为单一 `base`，`None` 时行为与历史等价 |
| 5 | 后端 | `EmployeeViewSet._filtered_employee_queryset(keyword)` 成为员工域取行口径唯一实现，供 `list` / `global_search` / `get_export_queryset` / `statistics` 四条路径共用；`filterset_fields` 换为 `filterset_class` |
| 6 | 后端 | 顺带订正 `get_queryset_with_bind_status()` docstring（原称"供列表接口展示绑定状态"，实际该字段由 `EmployeeDetailSerializer` 的详情路径消费） |
| 7 | 前端 | `usePaginationSearchState` 新增**可选** `onSearchStateChange` 回调，在 `search.value` 的每次真实变更后派发（含 `clearSearch`）——`performSearch` 收不到空串（内部提前走 `loadList`），无此出口则清空后搜索词残留 |
| 8 | 前端 | `userStore.ts` 新增模块级 `currentKeyword` + `useUserCurrentKeyword()` / `setUserCurrentKeyword()`（trim 归一化），为「当前搜索词」建立单一事实来源 |
| 9 | 前端 | `UserDetails.vue` 的 `search` 配置挂 `onSearchStateChange`；`useUserExcelExport.ts` 按搜索词转发 `params: { keyword }`，并改写原「已知限制 BF-047」注释为已闭环 + BF-048 仍存限制 |

### 五、验证

```text
① 先红后绿取证：git stash 仅回退 3 个后端源文件（保留测试）后
   pytest test_employee_filters + test_employee_export + test_export_excel
   → 15 failed / 22 passed（三类缺陷逐条命中；department_code 静默失效、
     statistics 忽略全部筛选、导出忽略 keyword/状态/部门、钩子不存在）
   恢复源文件后同三套件 → 37 passed
② 前端先红后绿：git stash 仅回退 useUserExcelExport.ts 后同 spec
   → 3 failed（keyword 透传三例）；恢复后 → 14 passed
③ pytest --cov=. → 1581 passed / 0 failed，整体 85.86%（CT-2 门槛 80%）✅
④ ruff check . → All checks passed；ruff check . --select C90
   --config lint.mccabe.max-complexity=10 → All checks passed
⑤ mypy . --strict → Success: no issues found in 216 source files
⑥ manage.py spectacular --validate → components 零漂移、paths 零增删；
   参数差异仅 +department_code ×3（list / search / statistics），无删除项
   —— 收尾复查修正：首版曾在 `global_search` 的 `@extend_schema` 里手工声明
   `employee_status` / `department_code`，其中 `employee_status` **覆盖**掉
   FilterSet 自动注入的 title/enum/逐项说明（基线中被削平成裸 string）。
   已删除这两条手工声明（保留 keyword/page/page_size），重导出后
   `employee_status` 与 HEAD 逐字一致（enum×3 + title 回归），`department_code`
   由自动注入补回（形态 `{"type":"string"}`，与 /list 一致）；基线 diff 的
   13 处删除**全部**是 description 字符串，零 schema/参数/响应删除。
   该机制与 BF-049、BF-050 同源，教训已记入 BF-050 第二节。
⑦ 告警归因（收尾核实）：`spectacular --validate` 报 287 warnings / 24 errors，
   **与本次改动零交集**——6 个 unique error 全为非 GenericAPIView 的
   "unable to guess serializer"，分布在 public_scan_view / authusermanagement /
   notification 三个模块；唯一触及本次文件的告警是 `employee_view.py:45`
   "could not resolve authenticator JWTCookieAuthentication"（项目未注册
   OpenApiAuthenticationExtension 的全局存量，permission_view 等同样命中）。
   dev 与 production 两套 settings 下计数完全一致（287/61、24/6），
   **证伪**了"环境差异"假设；`--validate` exit code = 0，故 CI 的
   "Generate schema" 步骤可通过，CI 真门禁是 `oasdiff breaking`
   （ci.yml:115；本地未安装 oasdiff，breaking 判定交由 CI 复核）。
   注：JWTCookieAuthentication 缺 OpenApiAuthenticationExtension 属新发现，
   尚未登记（OpenAPI 不声明认证方案，影响生成客户端），待评估。
⑦ check_duplicate_invariants.py → PASS（G-1~G-5）
⑧ check_frontend_invariants.py → PASS（FR-6 composables 47 文件 0 超限；
   FR-8 stores 30 文件 0 超限）
⑨ check_function_length_guard.py → FAIL，但为**存量且与本次无交集**：
   assetmanagement/services/recycle_asset_service.py _finalize_broken_or_lost()
   53 行、create_recycle_asset() 52 行未登记台账（该文件本次未改动，
   工作树 == HEAD，故为 HEAD 既有问题，留待 BR-4 批次拆分处理）
⑩ 前端 npx vitest run --coverage → 138 files / 1893 tests passed；
   statements 92.72% / branches 87.34% / functions 87.17% / lines 93.51%；
   userStore.ts 98.46%（Store 层门槛 90%）✅
⑪ 前端三项检查 → type-check / lint / format:check 均 0 错误
```

新增测试（CT-1/CT-4 回归屏障）：

- `apps/usermanagement/tests/test_employee_filters.py`（新建，14 例）：列表双名等价、搜索 `department_code`/`employee_status` 生效且与 keyword 取交集、统计四维度（`total` / `active` / `by_status` / `by_department`）随筛选收窄、组合筛选下统计条数 == 列表可见条数、统计在默认 ordering 下不碎组。
- `apps/usermanagement/tests/test_employee_export.py`（+6 例）：搜索态导出与 `/search/` 端点逐行同集合、keyword 与部门叠加收窄、状态/部门筛选、别名等价、空 keyword 不得清空结果。
- `apps/assetmanagement/tests/test_export_excel.py`（+3 例）：默认实现原样委托 `get_queryset()`、覆写钩子后导出走覆写口径、超限判定基于钩子口径行数。

### 六、契约变更

**纯增量，未触发 §1.3 红线**：

- 新增请求参数 `department_code`（`list` / `search` / `statistics` 三处），`components` 与响应体结构零变化。
- **不删除** `employee_department__department_code` 别名：删参数属请求参数删除，须 §1.3 人工审批，故保留为兼容别名（历史调用方与文档仍可用）。已在此登记该技术债并说明退场条件。
- `employee_status` 保持 `ChoiceFilter`，`schema` 中该参数的 `enum` / `title` / 描述**未丢失**——实现过程中曾一度改用 `CharFilter`，重导出基线时发现 enum 消失即回退，故 `employee_filters.py` 内写明"不得降级"的注释。

### 七、遗留

1. **BF-048**：员工导出为全公司口径，无行级数据权限（本次未修，见下条）。
2. **BF-049**：导出端点的 OpenAPI 未声明其实际支持的 `keyword` / `employee_status` / `department_code`（本次未修，见下条）。
3. `employee_department__department_code` 兼容别名暂无退场计划；若将来下线，须按 §1.3 走人工审批并同步前端与文档。
4. `?search=`（DRF `SearchFilter` 的窄口径，不含部门名匹配与状态别名映射）与 `?keyword=`（列表口径）两套搜索语义并存，前端只用后者；后端未拒绝 `search`，属文档层遗留。

*登记人：opencode ｜ 状态：已关闭（2026-09-26）*

---

## BF-048 【已修复】员工域无行级数据权限（部门经理可导出全公司员工档案）2026-09-26

### 〇、元信息

- **登记日期**：2026-09-26（来源：BF-047 核查中发现的**独立**安全缺口）
- **修复日期**：2026-09-26
- **严重级别**：**P1**（越权读取个人信息，批量落盘放大泄露面）
- **状态**：✅ 已修复（回归屏障：`apps/usermanagement/tests/test_employee_rbac_scope.py` 14 用例）
- **影响范围**：`core/department_scope.py`、`apps/usermanagement/selectors.py`、`apps/usermanagement/views/employee_view.py`（后端）

### 一、问题现象

`EmployeeViewSet.get_queryset_with_bind_status()` 返回**全量员工**（仅 `select_related`），不做行级收窄。BF-047 修复后导出行集合 = 列表可见行集合，但**列表本身亦为全量**——因此：

- 持有 `CanExportExcel` 的 `dept_manager` 可导出**全公司**员工档案（含工号、姓名、状态、部门、位置等列；手机号已被导出列刻意排除）。
- BF-046 的「最小化 PII」只收敛了**列**，未收敛**行**，批量导出使泄露面从「逐条查询可见」放大为「一次拖走全量」。

### 二、根因

员工域从未实现行级数据权限。对照：操作日志侧有 `OperationLogSelector._scope_by_user`（部门列表含子部门、空列表 `.none()`、`None` 不限），**员工域无对应实现**——即「列表口径」与「权限口径」从未分离设计，默认全量。

### 三、人工决策（2026-09-26 拍板，原「待决策事项」已闭环）

| # | 议题 | 决策 |
|:--|:--|:--|
| 1 | 部门经理可见范围 | **仅本部门 + 全部下级部门**，与 `OperationLogSelector._scope_by_user` 完全对齐（不新造范围规则） |
| 2 | `statistics` 聚合语义随之收窄 | **接受**为对外行为变更。逐条核对根级 §1.3 四项红线（无迁移 / 响应结构不变 / 不碰 FSM / 不改枚举）后判定**不构成 [HALT]**，但按 P1 走轻量审批包后实施 |
| 3 | `active_employees` 是否一并收窄 | **收窄**。前端实测 0 消费方，收窄零破坏面；不收窄等于留一个「批量 PII 导出」口子，与本条修复自相矛盾 |

### 四、修复内容

1. **`core/department_scope.py` 新增 `get_employee_scoped_queryset_for_user(user, qs)`**：完全委托既有 `get_department_codes_for_user` + `filter_queryset_by_department(qs, codes, "employee_department")`，**零新业务规则**（DR-1），命名镜像既有 `get_asset_linked_queryset_for_user`。
2. **`EmployeeSelector.get_queryset_for_user(user)`**：与 `UnregisteredAssetSelector.get_queryset_for_user` 同型，查询留在 Selector 层（分层铁律）。
3. **`EmployeeViewSet.get_queryset()` 覆写**为唯一收窄入口。因 DRF `get_object()` 内部即 `filter_queryset(get_queryset())`，一处覆写即覆盖 **list / retrieve / search / statistics / export 五条路径**——其中 **`retrieve`（`lookup_field=employee_jobcode`）是本条新发现的第 4 个旁路**：它原先只经声明式筛选，任何登录用户可按工号枚举读取任意员工档案，收窄后自动受保护。
4. **三个绕开取行口径的旁路显式收窄**：
   | 旁路 | 原实现 | 收窄方式 |
   |:--|:--|:--|
   | `active_employees` | 裸 `EmployeeSelector.get_active_employees()`（全公司批量 PII） | 经 `get_employee_scoped_queryset_for_user` |
   | `by_auth_user` | 裸 `Employee.objects.select_related(...).get(...)`（ID 可枚举） | 改走 `self.get_queryset()` |
   | `get_employee_by_jobcode` | 用 `self.queryset`（未 `filter_queryset`，工号可枚举） | 改走 `self.get_queryset()` |

### 五、修复中发现的两个附带缺陷（已一并处理）

1. **`by_auth_user` 畸形 ID 返回 500**：`auth_id` 是 URL 捕获组（str），原实现直接交给 ORM 做 FK lookup，非法值触发 `ValueError` → 500。现改为先 `isdigit()` 校验再 `int()`，非法值收敛为 **404**。
2. **实现过程中被自己的测试抓到的真 bug**：首版把转换失败的 `auth_id` 回落为 `None`，而 `filter(auth_user_id=None)` 会去匹配「**未绑定账号的员工**」并误返 **200**（等于开了一个新的越权读）。已改为非法值直接 404，并由 `test_by_auth_user_with_malformed_id_returns_404` 锚定。
   —— 教训：**「显式收窄」的代码本身也要被负例测试覆盖**，否则收窄实现可能自己成为泄露面。

### 六、验证

- 新增 `apps/usermanagement/tests/test_employee_rbac_scope.py` **14 用例全通过**：三态语义（dept_manager 本部门+子部门 / regular_user 仅本部门 / system_admin+auditor 不限 / 部门级无部门→零行且导出 403）、statistics 聚合 == 列表可见行数、**导出行集合 == 列表行集合**、search 关键词不可越权、三个旁路收窄、retrieve 越权 404、by_auth_user 正反两面 + 畸形 ID。
- 回归：`pytest apps/usermanagement` 153 passed；`pytest`（全量）**1594 passed**；`ruff check .` / `ruff format --check .`(328 files) / C90 三门禁 exit 0；BR-4 guard `[PASS] 0 超长`；`mypy --strict` 改动文件零错误。
- **1 处既有测试因语义变更而订正**：`test_employee_export.py::test_export_respects_keyword` 的对照组 `EXP-OTHER` 在另一部门，收窄后正确不可见，期望集已更新并注明「收窄语义的三态断言在 rbac_scope 文件，本用例只守『导出 == 搜索可见集』」。
- **契约**：`api-schema-baseline.json` 重导出后仅 description 文本变化 + 增量参数，**零 schema/响应/参数删除**（statistics 响应结构不变，仅数值范围随调用者权限变化）。

### 七、对外行为变更声明（供外部消费方自查）

`GET /api/v1/users/employees/{list,search,statistics,export,active-employees,by-auth-user,employees-by-jobcode,detail}` 的**返回行集合**现随调用者部门范围收窄。`statistics` 的 `total_employees` / `by_department` 等聚合数值同步收窄。**响应结构与字段名均未变化。** 若有外部脚本消费这些端点，需按「以调用者身份为准」重新核对预期数值。

### 八、遗留（不在本条范围）

- `get_department_by_jobcode` 返回部门而非员工档案，跨部门部门可见性未评估，另立。
- `mypy . --strict` 全量仍有 **27 errors / 12 文件**存量（`dateutil` stubs 等，含提交自述的「27 存量不变」），与本条无关，未处理。

*登记人：opencode ｜ 状态：已修复，2026-09-26*

---

## BF-049 【已修复·部分】导出端点 OpenAPI 未声明其实际支持的筛选参数 2026-09-26

### 〇、元信息

- **登记日期**：2026-09-26（来源：BF-047 收尾时新发现）
- **修复日期**：2026-09-26
- **严重级别**：P3（文档失真，不影响运行时行为）
- **状态**：✅ 已修复（**部分修复**，见「六、边界与未修部分」；回归屏障：`apps/usermanagement/tests/test_employee_openapi_contract.py`）
- **影响范围**：`core/schema.py`（新增）、`core/excel_export/{mixin,schema}.py`、`apps/usermanagement/views/employee_view.py`（后端）
- **提交**：`18c22c7`

### 一、问题现象

BF-047 后 `GET /api/v1/users/employees/export/` **实际接受并生效** `keyword` / `employee_status` / `department_code`，但其 OpenAPI 声明中**不含**这三个参数。

即"接口支持但文档未声明"，与 BF-050（已声明却忽略，属反向失真）同源、成因不同。

### 二、根因（原登记判断有误，已订正）

**原登记判断**：「Mixin 的 `@extend_schema(parameters=EXPORT_PAGINATION_PARAMETERS)` 会**覆盖** drf-spectacular 对该 action 自动注入的 filterset 参数」。

**订正后（实测）**：覆盖不是根因。真正机制在 drf-spectacular 0.29 的 `AutoSchema.get_filter_backends()`：

```python
def get_filter_backends(self):
    if not self._is_list_view():
        return []          # ← 非 list 响应直接不返回任何 filter backend
    return ...
```

xlsx 二进制响应触发 `_is_list_view() == False` → **整个筛选参数发现被关闭**，此时 Mixin 的 `parameters=` 根本没有机会与自动注入竞争（同一 ViewSet 的 `list` 端点同样带 `parameters`，但 4 个筛选参数完好，佐证覆盖不成立）。

补充证据：`operation-logs/export/` 手工声明了 6 个业务参数且正常产出，说明「手工 `parameters=` 本身不抑制自动注入」。

**因此 BF-050 登记的「同名覆盖非互补合并」机制对 BF-049 不适用**——它是**另一条机制**（启发式门控 vs 覆盖语义）。两条机制都真实存在，但解释的是不同现象；混用会导致误修。

### 三、人工决策（2026-09-26 拍板，原「待决策事项」已闭环）

| # | 议题 | 决策 |
|:--|:--|:--|
| 1 | 扩展点形式 | **不加 `export_query_parameters` 类属性**。加类属性后 Mixin 仍需在运行时拼装 `parameters`，而 `@extend_schema` 是静态装饰器参数——反而引入"两条声明路径"。改用 drf-spectacular 官方扩展点 `AutoSchema` 子类 + ViewSet 显式 opt-in 名单 |
| 2 | 是否改全局启发式 | **不改**。`ForceFilterDiscoverySchema` 仅在 ViewSet 显式列入 `frozenset` 的 action 上放宽，避免影响全仓 100+ 端点 |
| 3 | 是否把 `keyword` 加进 Mixin 共享片段 | **不加**。`keyword` 是员工域特有语义（`get_export_queryset()` 读 `?keyword=`），加进去会污染另外 10 个不消费该参数的端点 |
| 4 | 其余 10 个导出端点 | **不动**（见第六节，属如实的"少声明"而非失真） |

### 四、修复内容

1. **新增 `core/schema.py::ForceFilterDiscoverySchema`**（通用件，非员工域专用）：仅当 `view.action` 命中 ViewSet 类属性 `force_filter_discovery_actions` 时绕过 `_is_list_view()` 门控。名单是**显式 opt-in**，未列入的端点行为完全不变。
2. **`EmployeeViewSet` 配置**：`schema = ForceFilterDiscoverySchema()` + `force_filter_discovery_actions = frozenset({"export_excel", "statistics"})`。
   - **坑点记录**：名单里是 **action 方法名**（`export_excel`），**不是 `url_path`**（`export`）。DRF 的 `action_map` 值即方法名，`view.action == "export_excel"`。首版误写 `{"export", ...}` 时表现为**静默不生效**（无报错、无警告），是本次最容易复发的坑，已在代码注释中标注。
3. **员工导出局部重声明 action**：`keyword` 无法由 FilterSet 表达，故在 `EmployeeViewSet` 重声明 `export_excel` 并 `super().export_excel(request)` 委托 Mixin 实现（**不复制实现体**，DR-1），只补 `keyword` 声明。
4. **`EXPORT_ACTION_SCHEMA` 抽为 Mixin `@extend_schema` 的单一来源**：子类重声明同一 action 时必须复用同一份 `summary` / `responses` / 分页参数，否则 Mixin 与子类漂移。

### 五、验证

- **重导出后实测** `/api/v1/users/employees/export/` 参数 = `keyword` + `limit` / `offset` + 自动找回的 `department_code`（含 `employee_department__department_code` 别名）/ `employee_status` / `ordering` / `search`，**与运行时实际消费项一一对应**。
- **反向验证**：`/list` 与 `/search` 的 4 个筛选参数**零变化**；其余 11 个导出端点**零变化**（基线 diff 仅 2 个目标端点）。
- **enum 未被削平**：`employee_status` 仍为 `enum: [active, left, retirement]`——证明"追加 `keyword`"是叠加而非覆盖（BF-047 回归防线）。
- 门禁：全量 **1601 passed**（新增 6 护栏）；ruff check/format、C90、BR-4 全过；改动文件 mypy --strict 零错误。

### 六、边界与未修部分（故标注"部分修复"）

其余 10 个资产导出端点走 Mixin 默认 `get_export_queryset()`，**运行时不执行 `filter_queryset`，确实不消费筛选参数**——只声明 `limit` / `offset` 是如实的，非文档失真。

**真正的可选改进**（不在本条范围）：若将来这些端点也接入筛选，应先改运行时（覆写 `get_export_queryset()` 跑 `filter_queryset`），再让文档追上；**禁止**反向操作（只给文档加参数）。新增护栏 `test_bare_asset_exports_not_overstated` 负责在"文档超前于运行时"时报警。

### 七、遗留

- 本地无 `oasdiff`，breaking 判定依赖 CI `api-schema-check` job。
- `securitySchemes` 为空（全局 `SECURITY` 却引用 `BearerAuth`）属**存量**缺陷（HEAD 即如此），另立条目跟进。

*登记人：opencode ｜ 状态：已修复（部分），2026-09-26*

---

## BF-050 【已修复】员工统计端点 OpenAPI 契约三重错误（响应结构 + 多余 path 参数 + 虚假分页参数）2026-09-26

### 〇、元信息

- **登记日期**：2026-09-26（来源：BF-047 收尾时全量扫描 `api-schema-baseline.json` 发现）
- **修复日期**：2026-09-26
- **严重级别**：P3（文档层失真，运行时行为正确；当前无消费方受害）
- **状态**：✅ 已修复（回归屏障：`apps/usermanagement/tests/test_employee_openapi_contract.py`）
- **影响范围**：`apps/usermanagement/views/employee_view.py`（拆出 `employee_query_actions.py`）、`api-schema-baseline.json`（后端）
- **提交**：`18c22c7`

### 一、问题现象

`GET /api/v1/users/employees/statistics/` 的 OpenAPI 声明与实际返回**三处不符**：

| # | 声明 | 实际 |
|---|:--|:--|
| 1 | 200 响应 = `PaginatedEmployeeDetailList`（员工对象**分页数组**） | `{code, data:{total_employees, active_employees, by_status, by_department}, message}` 聚合字典 |
| 2 | 必填 **path** 参数 `name`（"员工名称"） | 该 action 是 `detail=False`，路径中**无任何占位符**，此参数无处可填 |
| 3 | `page` / `page_size` 查询参数 | 端点不分页，返回裸字典，二者无效 |

### 二、根因

`statistics` action 上的 `@extend_schema` 残留了一份「详情/列表页」模板：

```python
@extend_schema(
    parameters=[OpenApiParameter(name="name", location=PATH, required=True),   # ← ②
                OpenApiParameter(name="page", ...), OpenApiParameter(name="page_size", ...)],  # ← ③
    responses={200: EmployeeDetailSerializer(many=True)},                        # ← ①
)
```

**机制一：手工声明只替换、不校正。** drf-spectacular 中 `@extend_schema(parameters=…)` / `responses=…` 与自动注入是「同名覆盖」而非「互补合并」，且**不负责补全或校正**。一旦手工写错（张冠李戴的模板、错误的 serializer），spectacular 不会纠正，错误直接进基线。

**机制二：响应形态决定筛选参数发现（BF-049 修复时才发现的第二条机制）。** 把手工 `responses` 改成聚合字典后，`_is_list_view()` 由 `True` 翻为 `False`，**4 个运行期生效的筛选参数会随之全部消失**——修对一处会引出新一处。BF-049 登记的「同名覆盖」对导出端点并不成立（已订正，见 BF-049 第二节），此处的连锁效应才是本条的真实陷阱。

**教训（可推广）**：
1. 凡 FilterSet / 分页器 / 认证类已能自动产出的声明，不要手工再写一遍；手工声明只在自动注入**确实无法表达**时使用（如 `keyword` 这类自定义语义）。
2. 改 `@extend_schema(responses=…)` 时必须重跑基线 diff：响应形态变化会静默翻转筛选参数的自动发现，两类缺陷互为因果。

### 三、人工决策（2026-09-26 拍板，原「待决策事项」已闭环）

| # | 议题 | 决策 |
|:--|:--|:--|
| 1 | 聚合结构如何描述 | **采用 `inline_serializer`** 显式声明 4 字段（§3 约定：响应体即 payload，`code`/`message` 属响应包装不入 schema）。不新增 `EmployeeStatisticsSerializer`——该响应无写入/校验需求，新增序列化器只会让人误以为存在写入路径 |
| 2 | 删掉 3 条幽灵参数后的参数集 | 确认为 `employee_status` / `department_code` / `ordering` / `search`，**与运行时实际生效行为一致** |
| 3 | 是否把「手工声明须经基线 diff 校对」写入后端规则 | **写入** `Rules_Fiels/backend-business-rules.md` §4.8（决策 3 采纳） |

### 四、修复内容

1. **新增 `EmployeeStatisticsDataSchema`**（`apps/usermanagement/views/employee_query_actions.py`），生成 `EmployeeStatistics` 组件；200 响应指向该组件。
2. **删除** `name`(path) / `page` / `page_size` 三条幽灵参数。
3. **删除 `PaginatedEmployeeDetailList` 组件**：全局检索确认 `statistics` 是它**唯一**引用点（`/list` 用 `PaginatedEmployeeList*`），无悬挂引用。
4. **连带修复**（机制二连锁）：统计端点的 4 个筛选参数经 `ForceFilterDiscoverySchema` 找回，与 BF-049 同一机制、同一 opt-in 名单，不新增第二套方案。
5. **DR-5/BR-6 强制拆分**：`employee_view.py` 505 行（拆出后仍需新增内容，必然突破 500 行红线）→ 只读查询 action 迁至 `EmployeeQueryActionsMixin`（260 行），主类降至 **376 行**。拆分是修复的前置条件，非顺手重构。

### 五、验证

- 基线 diff **仅限 statistics 一个端点** + 组件 `+EmployeeStatistics` / `-PaginatedEmployeeDetailList`，**零其他端点变化**。
- 导出/列表/search 等既有端点参数零变化。
- 护栏 6 用例（`test_employee_openapi_contract.py`）全绿：响应结构、幽灵参数消失、运行期筛选参数在位、enum 未被削平、10 个裸资产导出端点未被过度声明。
- 门禁：全量 **1601 passed**；ruff check/format、C90、BR-4 全过；改动文件 mypy --strict 零错误。

### 六、为什么这类缺陷能长期潜伏（已转护栏）

BF-050 的三处错误在 **1595 个用例全绿**的情况下长期存在——因为既有测试全部断言 **HTTP 行为**，**没有任何一处断言文档**。`test_employee_rbac_scope.py` 能证明 `statistics` 的聚合值等于列表可见行数，却无法发现"文档把它说成分页数组"。

新增的 `test_employee_openapi_contract.py` 填补这一空白。**分工已明确写入文件头**（避免 DR-1 重复造测试）：本文件只守护「文档声明」侧；「参数真的生效」侧由既有 DB 级用例守护（`test_employee_export.py:196/226/231/258`）。

### 七、遗留

- `?search=` 门禁内的匹配行为与 `?keyword=` 不一致（`search` 命中 `search` 字段名、`keyword` 命中半角昵称），属语义设计问题，**未在本条处理**。
- 本地无 `oasdiff`，breaking 判定依赖 CI `api-schema-check` job。

*登记人：opencode ｜ 状态：已修复，2026-09-26*

---

## BF-051 【已修复】`JWTCookieAuthentication` 缺 `OpenApiAuthenticationExtension`，cookie 认证不出现在 OpenAPI 2026-09-26
> **【2026-09-29 标题订正】** 原标题为【待修复·已延后】，与本条正文矛盾：`:3006` 元信息已记「✅ 已修复（2026-09-26，后端 commit `5ed31d6`）」，收尾登记人行亦为「已修复」。据正文事实订正为【已修复】，原措辞保留于本注。

### 〇、元信息

- **登记日期**：2026-09-26（来源：BF-049 / BF-050 收尾时全量扫描生成告警）
- **严重级别**：**P2**（文档契约层缺陷：全 API 100% 端点引用未声明的 scheme）
- **状态**：✅ 已修复（2026-09-26，后端 commit `5ed31d6`）
- **影响范围**：`apps/authusermanagement/`（后端）、`config/settings/base.py`、`components.securitySchemes` 与全 API 每个 operation 的 `security` 引用关系

### 一、问题现象

`python manage.py spectacular` 输出中，**所有使用 `JWTCookieAuthentication` 的视图**都带同一条告警：

```
Warning [XxxView]: could not resolve authenticator
<class 'apps.authusermanagement.authentication.JWTCookieAuthentication'>.
There was no OpenApiAuthenticationExtension registered for that class. Ignoring for now.
```

即：cookie 认证**在 OpenAPI 中完全不可见**，凭 cookie 调用的客户端不会被文档告知。

### 二、根因（本条初次登记时误判为「附带发现」，已订正）

`config/settings/base.py` 曾写 `"SECURITY_SCHEMES": {"BearerAuth": {...}}`，但 **drf-spectacular 0.29 没有 `SECURITY_SCHEMES` 这个设置项**（其 `settings.py` 中 security 相关只有 `'SECURITY': []`），未知键被**静默忽略、不报错**。

而库的实际行为是（0.29.0 源码）：

- `openapi.py:352-360`：`components.securitySchemes` 的条目**只**由匹配到的 `OpenApiAuthenticationExtension` 注册，**没有第二个来源**；
- `openapi.py:362`：`"SECURITY"` 只往 operation 注入**裸引用**，**不物化**任何 scheme。

两者叠加的后果（实测基线）：

1. `components.securitySchemes` 键**整体缺失**——**不是**空对象 `{}`（初次登记写 `{}`，已订正）；
2. 而 `"SECURITY": [{"BearerAuth": []}]`（`base.py:361`）照常注入，于是**全部 267 个 operation 引用了一个从不存在于 components 的 `BearerAuth`**，即**悬空 scheme 引用，面 = 100% 端点**（261 个 `[{BearerAuth:[]}]` + 6 个 AllowAny 端点 `[{BearerAuth:[]},{}]`）；
3. 全仓 `OpenApiAuthenticationExtension` 数量为 **0**，认证类只有 `JWTCookieAuthentication` 一个。

故本条不是「文档少一个 cookie scheme」这么局部，而是**认证声明链路整体缺失**。

### 三、订正记录：初次登记的修法是错的（已拦下）

初次登记的修法写的是「新增一个 `name = "cookieJWT"` 的扩展」。**该修法会留下 267 处 `BearerAuth` 悬空引用**——只新增一个 scheme 解决不了「已被引用 267 次的 `BearerAuth` 从未物化」这个真问题，等于没修。

实施前核对库源码时发现并纠正：扩展的 `name` **必须沿用 `BearerAuth`**，让既有 267 处引用真正解析掉。用户拍板「双 scheme 注册、operation 不引用」（即两个通道都出现在 `components.securitySchemes` 供 Swagger UI 授权，但不改 267 个 operation 的 `security` 数组）。

### 四、修复内容

1. 新增 `apps/authusermanagement/schema.py::JWTCookieAuthenticationExtension`，`name = ["BearerAuth", "cookieJWT"]` 物化两个 scheme。**BearerAuth 沿用原名**（已有 267 处按名引用）。
2. cookie 通道的 `name` 取自 `settings.JWT_AUTH_COOKIE_ACCESS`（= `asset_access_token`，`base.py:243`），**不硬编码字面量**。初次登记标注的「实施前须核对真实 cookie 名，不得凭印象填」已完成核对。
3. **显式覆写 `get_security_requirement` 返回 `None`**：只物化定义、不注入 operation。基类默认返回 `{name: []}`，对多 name 是 **AND** 语义（两通道须同时提供），与运行时「Bearer 优先、Cookie 兜底，任一即可」相反。
4. `apps.py::ready()` 显式 import 扩展模块——drf-spectacular 靠 `__init_subclass__` 入 `_registry` 但**不做模块自动发现**（全库无 `import_module`/`pkgutil`），漏 import 即**静默失效**。
5. 删除 `base.py` 的 `SECURITY_SCHEMES` 自造配置块，description 文案迁入扩展（DR-4 单一口径）。`"SECURITY"` 保留不动。

### 五、证据

- **可验证**：`components.securitySchemes` 键**整体缺失**（非 `{}`），267 个 operation 全部引用 `BearerAuth`——均由 `api-schema-baseline.json` 实测。
- **可验证**：全仓 `OpenApiAuthenticationExtension` 计数为 0；`base.py` 的 `SECURITY_SCHEMES` 无对应设置项。
- **可验证（修复后）**：基线 diff **仅 +13 行 / 0 删除** = 新增 2 个 scheme，**operation 层零变化**；`could not resolve authenticator` **0 命中**，warnings 287 → 23，errors 24（6 unique）与存量一致。

### 六、护栏（7 用例，含先红后绿实测）

`apps/usermanagement/tests/test_openapi_security_schema.py`。核心是 `test_no_dangling_security_references`：**遍历全量 operation 的 security，每个 scheme 名都必须能在 components 中解析**——直击根因，未来新增认证类造成的同类悬空也会被它抓住。

**先红后绿已实测**：临时移除 `ready()` 后 3 条用例转红，其中该核心用例逐条列出全部悬空 operation（复现本条原始缺陷）；恢复后 13 passed。

两处设计取舍值得留档：

- `test_extension_resolves_auth_class` **刻意不在测试里 import** 本项目的 schema 模块——否则 `ready()` 被误删时扩展仍会在 import 那一刻注册，本用例照样通过，恰好漏掉要防的失效模式。
- `test_no_unresolved_authenticator_warning` 查 `GENERATOR_STATS._warn_cache` 而非 `recwarn`：告警走 `drainage.warn` → `GENERATOR_STATS`，**不是** Python `warnings` 模块。

### 七、为何当初延后（现已实施，理由复盘）

1. **影响面判断错了方向**：初判「会让全 API 每个 operation 的 `security` 数组变化」而搁置；实际根因（悬空引用）**比预想更严重**，而修法可以做到 operation 数组零变化——**问题大小与修复成本是两个独立维度**，初判把二者混为一谈。
2. **本地无 `oasdiff`**：breaking 判定仍只能靠 CI `api-schema-check` job 回填。
3. 触 B11/B12 认证域 + §6 安全红线，与 BF-049/BF-050（纯文档层、读写行为零变化）分批确有必要。

### 八、验收标准核对

| 标准 | 结果 |
|:---|:---|
| ① 告警消失 | ✅ `could not resolve authenticator` 0 命中 |
| ② cookie scheme 存在且 `name` 与真实 cookie 名逐字一致 | ✅ `asset_access_token` == `settings.JWT_AUTH_COOKIE_ACCESS` |
| ③ `oasdiff breaking` 通过 | ⏳ 待 CI `api-schema-check` 回填（本地无该工具） |
| ④ 补 schema 断言用例 | ✅ 7 用例，含全量悬空引用扫描 |

*登记人：opencode ｜ 状态：已修复，2026-09-26（后端 commit `5ed31d6`）*

---

## BF-052 【已修复】前端回落搜索把任意筛选值当 keyword，筛选值被当搜索词发出 2026-09-26

### 〇、元信息

- **登记日期**：2026-09-26（来源：BF-047 收尾时前端侧复盘；用户批准计划中的 D1）
- **修复日期**：2026-09-26
- **严重级别**：P2 潜在缺陷（逻辑错误，但**当前影响面为 0**，见第四节）
- **状态**：✅ 已修复（回归屏障：`usePaginationSearch.spec.ts` 3 条新用例 + `UserDetails.spec.ts` 4 用例）
- **影响范围**：`src/composables/usePaginationSearchState.ts`（前端）
- **提交**：`dcea08b`（前端仓）

### 一、问题现象

`performSearchWithParams(params)` 在视图**未实现** `performSearchWithParams` 时的回落分支原为：

```ts
const keyword = params.keyword || Object.values(params).find((v) => v && v.trim()) || ''
await performSearch(keyword)
```

即「取第一个非空筛选值当搜索词」。只传 `department_code: 'DEPT-F1'` 时会发出 `?keyword=DEPT-F1`。

### 二、根因

后端 `keyword` 匹配的是**员工昵称**（`search_employees` 半角昵称口径），与 `search` 字段名、与部门编码都不是一回事（见 BF-050 遗留：三种匹配语义本就不一致）。前端这一行把「筛选」与「搜索」两种语义混为一谈：既没有类型约束，也没有注释说明，等于**假设所有筛选值都是可搜索的字符串**。任何新增的非文本筛选（状态码、部门编码、日期区间）都会踩中。

### 三、修复内容

1. 只上报真正的 `keyword`（`params.keyword?.trim()`）；无 keyword 时**如实回落为列表加载 + 告警**，由接入方补 `performSearchWithParams`。
2. **明确禁止反向操作**：把筛选值塞进 `keyword` 去迁就缺失的实现。
3. 抽出 `resetSearchState()` 与 `fallbackSearchWithoutMultiParam()`：新增分支使该函数圈复杂度达 **11**，超 FR-5 上限 10，抽取后恢复合规（不是顺手重构，是门禁要求）。

### 四、影响面实测为 0（但缺陷真实）

全仓检索 `performSearchWithParams` 的调用点：仅 `usePaginationSearch.ts` 转出，**无任何组件调用**。故本条是**潜在缺陷**而非在线故障——但它是一颗定时炸弹：第一个实现「带筛选的列表页」的开发者会直接踩中。

### 五、验证（含先红后绿）

- **先红后绿已实测**：临时还原旧实现后，「非关键字筛选不得被当成搜索词」用例**转红**（`performSearch` 被误调 1 次）；恢复后 40 全绿。
- 另 2 条新用例（keyword 与筛选并存取 keyword、纯空白 keyword 不拿其他值凑数）在旧实现下**同为绿**——它们是**语义边界锁**，防未来改动回退，不是回归锚点。如实标注，不充作锚点。
- 全量：139 files / 1900 tests passed；覆盖率整体 92.8% statements（阈值 80）、stores 97.73%（阈值 90）；type-check / lint / format:check 三项 0；复杂度 ≤10；`check_frontend_invariants.py` PASS。

### 六、附带产出：首个 `UserDetails` 接线测试（D2）

BF-047 的「搜索后导出 = 搜索结果」是一条**跨三跳的隐式链**：`search.onSearchStateChange` → `userStore.currentKeyword` → `createUserExcelExport(userStore)` 读该值转发后端。任一环被重构误删都**不报错**，只有导出行集合悄悄变回全量；而既有测试全是 composable / store 层单测，**覆盖不到组件这一跳**。

新增 `src/components/componentsdetails/__tests__/UserDetails.spec.ts`（4 用例）补上这一跳：搜索态变更写入 currentKeyword、卸载清空（防残留词）、`performSearch` 透传分页、导出 composable 收到同一 store 实例。**范围克制**：只测接线，不测渲染/交互/样式，不做全量快照。

*登记人：opencode ｜ 状态：已修复，2026-09-26*

## BF-053 【已关闭】删除/审核付款不重算金额——amount_paid 软删后永不回落（v2.9.53，B-25 子项①）2026-09-28

### 〇、元信息

- **登记日期**：2026-09-28（补登：v2.9.53 修复时仅在重复模式台账 B-25 内使用了编号，未按活账本格式登记条目；本次由 BF-056 §六.1 冲突扫描发现后补齐）
- **修复日期**：2026-09-28（随 v2.9.53 合同支付重算收敛一并落地）
- **严重级别**：P1（数据一致性：软删一笔付款后 `amount_paid` 仍含该笔且永不回落，金额与明细长期不一致）
- **影响范围**：`apps/assetmanagement/services/contract_service.py`（后端）
- **契约影响**：零

### 一、问题现象

`delete_payment_record` 与 `approve_payment_record` 只把 `status` 改为 `deleted`/`approved` 并 `save(update_fields=["paid_record", "updated_at"])`，**完全不触碰 `amount_paid`/`amount_unpaid`**；而 `add_payment_record` 是唯一做「增量 + 重算」的路径。软删一笔后 `amount_paid` 仍含该笔且永不回落，与 `paid_record` 明细长期不一致。

### 二、根因

| # | 环节 | 事实 |
|:--|:--|:--|
| 1 | 重算只在一处 | 修复前仅 `add_payment_record` 增量累加并重算；delete/approve 只改明细不改金额 |
| 2 | 反规范化字段承诺自动计算 | `models/contract.py:97` 附近 `amount_unpaid.help_text` 明写「未支付金额(自动计算)」，与「只在 add 时算」的实现矛盾 |

### 三、修复方案

| # | 变更 | 文件 |
|:--|:--|:--|
| 1 | 抽 `_recalc_paid_amounts`（:80）为单一重算实现，内部经 `_parse_paid_record`（:25）+ `_sum_active_paid`（:62，含脏 JSON 三段容忍：金额非数字、数组型纯文本、缺 payments 键）| `contract_service.py` |
| 2 | `add_payment_record`（:217）/ `delete_payment_record`（:439）/ `approve_payment_record`（:473）三处统一走 `_recalc_paid_amounts` | `contract_service.py` |
| 3 | Q-A 口径：pending 已计入 `amount_paid`，故 delete 扣减、approve 不变（:62-77 / :471-473 注释留痕）| `contract_service.py` |

### 四、对抗审核

- **行号漂移**：引用的 service 行号为当前工作区 `rg` 实测（`_recalc_paid_amounts` :80 等）。
- **修复前置依赖**：BF-053 的重算语义依赖 BF-055 已把 `amount_paid` 规范化（期初已付转 approved 付款记录），否则会把「无明细但有 amount_paid」的旧合同归零——两者须同批处置（B-25 已论证，不单飞）。
- **虚报验证**：验证记录见下，80 passed 为本次实跑输出，与此前 complete-patterns 记录一致。

### 五、验证记录

```text
.venv\Scripts\python.exe -m pytest apps/assetmanagement/tests/test_contract_service.py apps/assetmanagement/tests/test_contract_view_api.py -q
> 80 passed, 2 warnings in 54.38s
# 关键锚点: test_contract_service.py:281 test_delete_payment_reduces_amount_paid
#            test_contract_service.py:298 test_approve_keeps_amount_paid_unchanged
```

### 六、遗留与关联事项

- B-25 依赖链：与 BF-054 / BF-055 同根因族（`amount_paid` 反规范化多写入者、无单一真值来源），关闭记录见 `Rules_Fiels/Duplicate_Codes/complete-patterns.md` B-25。

*登记人：opencode ｜ 状态：已关闭，完成验证，2026-09-28*

## BF-054 【已关闭】无法回填历史付款——payment_date/payment_method 硬编码 + 无批量入口（v2.9.53，B-25 子项②）2026-09-28

### 〇、元信息

- **登记日期**：2026-09-28（补登，见 BF-053 §〇）
- **修复日期**：2026-09-28（随 v2.9.53 一并落地）
- **严重级别**：P2（能力缺失：上传已执行合同时真实付款日期/支付方式无法录入，每笔历史付款须额外发一次 approve）
- **影响范围**：`apps/assetmanagement/services/contract_service.py` + `apps/assetmanagement/views/contract_view.py`（后端）
- **契约影响**：增量（单条付款端点新增可写 `payment_date`/`payment_method`、新增批量端点）——已随 v2.9.53 重导出 schema 基线

### 一、问题现象

`add_payment_record` 原实现在明细中硬编码 `date=timezone.now()`、`payment_method="bank_transfer"`、`status="pending"`，View 层只读 `amount` 与 `description`。上传**已执行**合同时真实付款日期与支付方式无法录入；若需批量回填历史付款，只能逐笔调用再逐笔 approve。

### 二、根因

| # | 环节 | 事实 |
|:--|:--|:--|
| 1 | 构造函数硬编码 | `_build_payment_entry` 修复前 `payment_date`/`payment_method`/`status` 无入参，恒为当天/`bank_transfer`/`pending` |
| 2 | 无批量路径 | Service 与 View 均只有单条 add，批量回填须 2N 次请求 |

### 三、修复方案

| # | 变更 | 文件 |
|:--|:--|:--|
| 1 | `_build_payment_entry` 开放 `payment_date`/`payment_method` 入参，`date` 缺省才取当天（:38-59）| `contract_service.py` |
| 2 | `add_payment_record` 接收 `payment_date`/`payment_method`（:178-185）| `contract_service.py` |
| 3 | 新增 `add_payment_record_batch`（:224）：批量端点，内部 add→approve 收敛为一次请求，`status` 不开放为用户输入（维持 `approved` 单一入口 + 审批留痕，决策 Q-C）| `contract_service.py` |
| 4 | 单条付款端点接受 `payment_date`/`payment_method`（contract_view.py:216-264）、批量端点 `POST /contracts/{recordcode}/payment_record/batch/`（:280）| `contract_view.py` |

### 四、对抗审核

- **行号漂移**：service/view 行号均为当前工作区实测。
- **决策留痕**：`status` 不开放为用户输入是用户 2026-09-28 拍板方向之一；需保留 pending 的历史条目时由调用方改用单条 add 端点（:232 注释）。
- **虚报验证**：80 passed 实跑，见下。

### 五、验证记录

```text
.venv\Scripts\python.exe -m pytest apps/assetmanagement/tests/test_contract_service.py apps/assetmanagement/tests/test_contract_view_api.py -q
> 80 passed, 2 warnings in 54.38s
# 关键锚点: test_contract_view_api.py 批量回填/日期/支付方式用例(spec 断言覆盖 payload 构造)
```

### 六、遗留与关联事项

- 与 BF-055 前端批量导入断链同批修复（后端接收后 spec 断言本就覆盖 payload 构造）。

*登记人：opencode ｜ 状态：已关闭，完成验证，2026-09-28*

## BF-055 【已关闭】三条 amount_paid 写入路径全部静默失效——前后端断链（v2.9.53，B-25 子项③）2026-09-28

### 〇、元信息

- **登记日期**：2026-09-28（补登，见 BF-053 §〇）
- **修复日期**：2026-09-28（随 v2.9.53 一并落地）
- **严重级别**：P1（前后端断链：UI 有输入/校验/映射，后端无接收，DRF 静默丢弃，全程无报错；另造成「无明细但有 amount_paid」形态，阻塞 BF-053 重算语义）
- **影响范围**：后端 `serializers/base_model_serializers.py` + `serializers/batch_serializers.py` + `services/contract_service.py`；前端 `ContractForm.vue`
- **契约影响**：增量（Create `amount_paid` 转可写、Create 的 `paid_record`/`amount_unpaid` 转只读、Update 三字段只读、批量 item 补 `amount_paid`）——已随 v2.9.53 重导出 schema 基线

### 一、问题现象

前端三条路径（单条创建 / 单条编辑 / 批量导入）都能构造 `amount_paid`，但没有一条能送到后端：

| 路径 | 前端构造点 | 断链位置 |
|:--|:--|:--|
| 单条创建 | `ContractForm.vue:188-202` 输入框存在 | `submitData` 为显式白名单，不含 `amount_paid` |
| 单条编辑 | 同一输入框未绑定 `:disabled="isEdit"` → 用户改了以为生效 | 同上 |
| 批量导入 | `contractBatchImport.config.ts` 构造 | `ContractBatchCreateItemSerializer` 未声明 `amount_paid`，View 序列化阶段丢弃 |

唯一可用路径是裸 API 客户端直接 POST。

### 二、根因

| # | 环节 | 事实 |
|:--|:--|:--|
| 1 | front 构造无后端接收 | `submitData` 白名单与后端序列化器字段集之间**无任何一致性护栏**，同域三处各自断链 |
| 2 | DRF 静默丢弃 | 系列化器未声明的请求键被静默忽略，无报错提示，天然隐藏 |
| 3 | 测试盲区 | 前端 spec 只断言 payload 构造，后端测试不覆盖该键——断链点在两侧测试缝隙里 |

### 三、修复方案

| # | 变更 | 文件 |
|:--|:--|:--|
| 1 | Create：`amount_paid` 语义定为「期初已付金额」并通过 Service 规范化为一条 `approved` 期初付款记录（`payment_method="opening_balance"`），再无条件重算——`amount_paid` 恒等于「Σ 非 deleted 付款」，重算恒等无损（无 DB 迁移）| `contract_service.py:131-159` |
| 2 | `ContractCreateSerializer.amount_paid` 转可写（help_text 明示期初语义，base_model_serializers.py:152-155）；Create 的 `paid_record`/`amount_unpaid` 只读；Update 三字段全只读（:243）| `base_model_serializers.py` |
| 3 | 批量创建 item 声明 `amount_paid`（batch_serializers.py:34）| `batch_serializers.py` |
| 4 | `ContractForm.vue`：Create `submitData` 补 `amount_paid`（:399-403）；Edit 输入绑定 `:disabled="isEdit"` + tooltip 指引走付款记录 UI（:188-202）| `ContractForm.vue` |
| 5 | `perform_create` 改道 Service（修复 REST 绕过 Service 的既有缺陷，contract_view.py:106 注释留痕）| `contract_view.py` |

### 四、对抗审核

- **行号漂移**：service/serializers 行号为当前工作区实测；前端 `ContractForm.vue` 行号为 `rg` 实测。
- **[推测] 引入时点**：该失效自 `amount_paid` 加入这些前端界面时即存在，非近期回归；引入时点未考证。同类断链在其他域可能复发——前端 `submitData` 白名单与后端字段集无一致性护栏，已进 B-25 [推测] 段（本条只登记已实证的合同域 3 处）。
- **虚报验证**：80 passed 实跑；前端验证引自 v2.9.53 记录（1898 passed / 92.8%）——本次未重跑前端套件，如实标注。

### 五、验证记录

```text
.venv\Scripts\python.exe -m pytest apps/assetmanagement/tests/test_contract_service.py apps/assetmanagement/tests/test_contract_view_api.py -q
> 80 passed, 2 warnings in 54.38s
# 关键锚点: test_contract_view_api.py:273 test_create_contract_amount_paid_becomes_opening_record
#            test_contract_view_api.py:290 test_update_contract_amount_paid_is_read_only
#            test_contract_service.py:445-472 期初已付规范化 + amount_paid 弹出后不残留

# 前端（v2.9.53 原记录，本次未重跑）:
# 1898 passed | 整体覆盖率 92.8% | type-check / lint / format:check 全绿
```

### 六、遗留与关联事项

- 依赖链：BF-055 修完（期初已付有真实入口）之后 BF-053 的重算语义才安全（B-25 三者须一并处置）。

*登记人：opencode ｜ 状态：已关闭，完成验证，2026-09-28*

## BF-056 【已关闭】AllowAny 登录/注册端点被残留毒 access Cookie 拒绝（SIGNING_KEY 变更后无法登录）2026-09-28

### 〇、元信息

- **登记日期**：2026-09-28（来源：线上复现——dev 重启后残留 Cookie 致登录接口恒定 401「此令牌对任何类型的令牌无效」）
- **修复日期**：2026-09-28
- **严重级别**：P2（在线故障：dev 环境 SECRET_KEY 轮换 + 残留 Cookie 并存时，登录/注册被认证类在视图前拦截，凭据正确也无法登录）
- **影响范围**：`apps/authusermanagement/views.py`（LoginAPIView / RegisterAPIView）+ `tests/test_dual_channel_auth.py`（后端）
- **契约影响**：零（API 响应结构、端点、状态码语义均不变；`authentication_classes=[]` 属 DRF 声明级配置）
- **提交**：待提交（本会话工作区改动）

### 一、问题现象

1. 页面加载时 `/api/v1/auth/token/refresh/` 返回 401——残留旧 refresh Cookie 已失效，**属预期路径**（`RBACTokenRefreshView` 认证类已置空，401 来自视图自身 TokenError 处理，非 bug）。
2. 用户随后输入正确凭据登录，`/api/v1/auth/login/` 同样返回 401，且文案是 **「此令牌对任何类型的令牌无效」**——这是 simplejwt `InvalidToken`（`AuthenticationFailed` 子类）被全局异常处理器转出的 detail 文案，**在进入 `LoginSerializer`/凭据校验之前就把请求打死**，"用户名或密码错误"分支根本走不到。
3. `RegisterAPIView` 同型隐患（未实测触发，由登录证据推导，防御性同修）。

### 二、根因

| # | 环节 | 事实 |
|:--|:--|:--|
| 1 | 认证类全局生效 | `config/settings/base.py:181` `DEFAULT_AUTHENTICATION_CLASSES = [JWTCookieAuthentication]`，`LoginAPIView`/`RegisterAPIView` 未声明 `authentication_classes=[]` |
| 2 | AllowAny 不豁免认证 | DRF `APIView.initial()→perform_authentication()` 无条件运行认证类，`permission_classes=[AllowAny]` 只豁免鉴权不豁免认证 |
| 3 | 毒 Cookie 触发 TokenError | `authentication.py:72-82` `authenticate()` 读取 `asset_access_token` Cookie → `get_validated_token` 验签失败抛 `InvalidToken`(401) |
| 4 | 文案指向验签失败 | 「此令牌对任何类型的令牌无效」对应 PyJWT `InvalidTokenError`（签名/算法分支）；若仅为过期会是另一分支「令牌无效或已过期」——故根因是 **SIGNING_KEY 变更** |
| 5 | SIGNING_KEY 每次重启随机 | `config/settings/development.py:27` `SECRET_KEY = config("SECRET_KEY", default=get_random_secret_key())`——dev 未在 `.env` 固定时，每次进程冷启换密钥，旧签名 Cookie 全部验签失败 |
| 6 | 毒 Cookie 得不到清理 | access/refresh Cookie 均 `httponly=True`（cookie_utils.py:23），JS 无法删除；`verifyCookieSession` 失败仅走 `silentLogout`（stores/auth.ts:158-169）不清服务端状态 |

### 三、修复方案

| # | 变更 | 文件 |
|:--|:--|:--|
| 1 | `LoginAPIView` 声明 `authentication_classes: list[Any] = []`——登录不解析任何入站令牌（含残留毒 Cookie） | `apps/authusermanagement/views.py:228` |
| 2 | `RegisterAPIView` 同款声明 | `apps/authusermanagement/views.py:170` |
| 3 | 不透传 Bearer/Cookie 通道认证信息（`request.auth_channel` 仅用于日志观测，`getattr` 安全兜底，全仓无其他读取点） | 无额外改动 |
| 4 | **前端不做 Cookie 清理**：HttpOnly 限制 JS 无法删除，且修复 1/2 落地后毒 Cookie 对 login/register/refresh（认证类均置空）失效，重新登录时 `set_auth_cookies` 亦会覆盖——原始方案中的前端改动项判定为不必要 | 无 |
| 5 | 护栏测试 3 条：毒 Cookie + 正确凭据 → 200；毒 Cookie + 错误密码 → 401「用户名或密码错误」；毒 Cookie + 注册 → 201 | `tests/test_dual_channel_auth.py:218-240, 421-438` |

### 四、对抗审核

- **行号漂移**：本条目引用的 views.py 行号为**修复后**实测（`rg` 复核），测试行号 218-240 / 421-438 亦为当前工作区实测定位。
- **虚报验证**：下述验证命令全部实际执行，`41 passed` / `83 passed` 为真实输出。
- **扫描对抗点**：`RBACTokenRefreshView`（views.py:425）与 `LogoutAPIView`（views.py:358）此前已置空认证类并有护栏锚 `test_refresh_does_not_require_valid_access`——本次只是补齐 login/register 两处同型缺口，不是新发现。
- **契约影响**：零；未触发 schema 重导出（无端点/响应变化）。
- **登记遗漏**：`rg "BF-056"` 复核唯一；同题无已有关闭条目。
- **CSRF 权衡**：login 从「毒 Cookie 存在时才偶发强制 CSRF」变为恒不强制 CSRF；登录反 CSRF 仍保留 `X-Requested-With` 校验，前端亦始终发送 `X-CSRFToken` 头——整体风险面不扩大。

### 五、验证记录

```text
# 1) authusermanagement 专项
.venv\Scripts\python.exe -m pytest apps/authusermanagement/tests/test_dual_channel_auth.py -q
> 41 passed in 93.25s   (含新增 3 条毒 Cookie 护栏用例)

# 2) authusermanagement 全量
.venv\Scripts\python.exe -m pytest apps/authusermanagement/ -q
> 83 passed in 159.07s

# 3) 静态检查
.venv\Scripts\python.exe -m ruff check apps/authusermanagement/views.py apps/authusermanagement/tests/test_dual_channel_auth.py
> All checks passed!
.venv\Scripts\python.exe -m mypy apps/authusermanagement/views.py
> Success: no issues found in 1 source file
```

### 六、遗留与关联事项

1. **[已解决 2026-09-28] BF 编号冲突扫描**：`Rules_Fiels/Duplicate_Codes/complete-patterns.md` B-25（v2.9.53，2026-09-28）在合同支付金额修复中使用了 **BF-053 / BF-054 / BF-055** 三个编号（作为子问题标签），但 Bug 活账本中原本**不存在这三条 `## BF-` 条目**（最大为 BF-052）。为保唯一，本条登记时曾跳号取 BF-056；随后按用户指示**已于 2026-09-28 补登 BF-053 / BF-054 / BF-055** 三条完整条目（现状：现象/根因/修复方案/对抗审核/验证记录/遗留齐全），编号顺序 BF-052 → 053 → 054 → 055 → 056 连续无断档。
2. **前端 root-cause 加固建议（可选）**：dev 环境在 `.env` 固定 `SECRET_KEY`（development.py:119 已有指引），避免每次重启全量会话失效；属运维口径，非代码缺陷。
3. **关联模式**：AllowAny 端点「认证类残留」属于全局性模式风险，同类端点应按 `rg "permission_classes = \[permissions.AllowAny\]"` 全量复核是否都显式置空认证类。

*登记人：opencode ｜ 状态：已关闭，完成验证，2026-09-28*


## BF-057 【已关闭】员工批量排序端点 OpenAPI 响应形状失真：基线声明单对象、运行时返裸数组 2026-09-29

### 〇、元信息

- **登记日期**：2026-09-29
- **来源**：本轮 OpenAPI 契约复核（前序会话遗留条目，非新发现）
- **关键程度**：P3（文档层失真，运行时正确）
- **影响范围**：`apps/usermanagement/views/employee_view.py::EmployeeViewSet.batch_sort` + `api-schema-baseline.json` + `apps/usermanagement/tests/test_employee_openapi_contract.py`
- **契约影响**：无（运行时响应字节级不变，仅修正文档声明）
- **跨端契约**：未变更（前端 `vue-assetmanagement/src/api/user.ts:169` 的 `batchUpdateSort` 声明 `Promise<EmployeeExtended[]>`，与修正后的裸数组一致）

### 一、问题现象

`PUT /api/v1/users/employees/sort/` 的 200 响应在基线中声明为单个 `Employee` 对象，
而运行时返回的是**裸员工数组**（`success_response` 包装下的 `serializer.data`）。
消费方按 OpenAPI 生成的客户端会预期收到单个对象，实际拿到数组。

前序会话曾把该现象误记为「基线为 `PaginatedEmployeeList`」，并据此在代码注释中留痕；
实测基线为 `{"$ref": "#/components/schemas/Employee"}`（单对象），**不是**分页对象。
该错误注释本身即本次修复的一部分（已删除）。

### 二、根因

这是继 BF-049 / BF-050 之后的**第三个、且相互独立**的 OpenAPI 失真机制。

前序会话已实测并留痕：显式 `responses={200: EmployeeSerializer(many=True)}` **不生效**——
声明会被 ViewSet 的分页推断覆盖成 `PaginatedEmployeeList`，故当时未写该声明（「不写无效声明」）。
该结论本身正确，但由此推断出的「基线是分页对象」是错的。

真实成因是**两个不同失败模式的叠加**：

1. **未声明 `responses` 时**（修复前的实际状态）：`_get_response_for_code` 的
   `_is_list_view(serializer)`（`openapi.py:1486`）对 `batch_sort` 求值——
   `get_response_serializers()` 返回 `get_serializer_class()` 的回退结果
   `EmployeeSerializer`（非 list），`is_list_serializer` 判 False；再落到
   `self.view.action == 'list'` 亦判 False（action 名为 `batch_sort`）。
   于是 `:1485-1518` 的**数组 + 分页推断分支整体被跳过**，退回普通 `is_serializer`
   分支，产出单对象 `$ref`。
2. **补上 `many=True` 时**：走 `:1492-1518` 分支，`_get_paginator()` 返回
   `CustomPageNumberPagination`，裸数组被**重新包成** `PaginatedEmployeeList`。
   前序会话实测确认此覆盖行为成立。

即：两条路都错——不声明是单对象，声明 `many=True` 是分页对象，**都不是**裸数组。

**旁路解法（本次采用）**：`responses` 传 **raw dict** 而非序列化器实例时，
命中 `openapi.py:1471-1475` 的 `isinstance(serializer, dict)` 分支，该分支显式
`serializer = None`；随后 `:1486` 的 `_is_list_view(None)` 恒判 False，
整条「数组 + 分页」推断分支一并跳过，raw dict 原样透传为响应 schema。

**连带副作用（必须一并规避）**：`many=True` 会翻转 `_is_list_view()`，
进而打开 `AutoSchema.get_filter_backends()`（`openapi.py:545-549`），
给该端点凭空加上 5 条**运行时从不消费**的查询参数：
`department_code` / `employee_department__department_code` / `employee_status` /
`ordering` / `search`。`batch_sort` 是 `methods=["put"]`，直接调
`EmployeeSelector.batch_update_sort()`，**全程不跑 `filter_queryset`**。
这属于 OS-5 双向红线所述的「文档超前于运行时」反向失真。
raw dict 旁路同时跳过该分支，故副作用不产生。

### 三、修复方案

1. **`apps/usermanagement/views/employee_view.py`**——`batch_sort` 的
   `@extend_schema` 补 `responses={200: {"type": "array", "items": {"$ref": "#/components/schemas/Employee"}}}`，
   同时删除前序会话的遗留注释（含「基线为 PaginatedEmployeeList」错误陈述），
   改为写明 dict 旁路机理、完整 ref 路径与 `EmployeeSerializer` 的耦合点、护栏指向。
   **`core/schema.py` 零改动**（raw dict 是库内建旁路，无需自定义 `AutoSchema` 覆写）。
2. **`apps/usermanagement/tests/test_employee_openapi_contract.py`**——追加 3 条护栏
   （追加而非新建文件，DR-1）：
   - `test_sort_response_is_bare_array`：断言 `type == "array"` 且
     `items["$ref"] == "#/components/schemas/Employee"`（**完整路径**，不用子串匹配），
     并断言 `Employee` 组件确实存在于 `components.schemas`。
   - `test_sort_declares_no_runtime_unused_params`：sort 端点参数集为空（OS-5 反向护栏）。
   - `test_sort_change_does_not_affect_list`：`list` 仍为 `PaginatedEmployeeList`
     且保留 `page` / `page_size`（拦截 raw dict 被误提为类级或改走全局豁免）。
3. **`api-schema-baseline.json`** 重导出，与代码改动**同 commit**。

### 四、对抗审核

1. **「子串匹配会不会更稳」**——不会。raw dict 是**字面量**，组件名拼错时
   drf-spectacular **不报错**（实测写成 `EmployeeTYPO` 照常生成、退出码 0、
   组件不存在）。子串匹配 `in` 会漏过 `EmployeeExtended` 之类的前缀撞名，
   故必须用完整路径断言，并**额外**断言组件存在，把悬空 ref 这个静默失败面堵死。
2. **「raw dict 会不会不跟随序列化器改名」**——会，这是本方案的**已知耦合点**。
   已在代码注释中显式标注，并在护栏中以完整 ref 路径锁定。
   备选方案（自定义 `AutoSchema` 覆写 `_get_paginator()` / `get_filter_backends()`）
   可自动跟随组件名，但需改 2 个文件、引入库私有方法依赖与新名单概念；
   经权衡取改动面更小、无私有方法依赖者。
3. **「3 条新护栏与既有护栏是否重复」**——`test_employee_search_contract.py:75`
   的 `NON_SEARCH_EMPLOYEE_OPERATIONS` **已含** `("/api/v1/users/employees/sort/", ("put",))`，
   已覆盖 `search` 一项泄漏。但它只挡 `search`，挡不住 department_code /
   employee_status / ordering；且第 3 条（`list` 未受波及）是其完全不覆盖的方向。
   故非重复，补齐。
4. **「是否只改了文档，掩盖了运行时问题」**——否。运行时 `batch_sort`
   返回 `success_response(data=response_serializer.data)` 确为裸数组，
   前端 `unwrapResponse` 后拿到 `EmployeeExtended[]`，前后端已对齐。
   本次是文档追认运行时事实，未改任何运行时行为。
5. **「oasdiff breaking 会不会挂」**——本地无 oasdiff 工具（CI 用 Linux 二进制），
   无法本地验证判定结果。**基线重导出与代码改动同 commit** 是唯一安全做法：
   CI `api-schema-check` 比对的是「仓库内基线 vs 现场重生成」，两侧同 commit 即一致。

### 五、验证记录

- **先红后绿**：`git checkout` 还原 `employee_view.py` 后，
  `test_sort_response_is_bare_array` **FAILED**（1 failed, 8 passed），
  证明护栏能捕获原缺陷；恢复后 9 passed。
- **错误解法的反向验证**（证明第 2 条护栏非摆设）：把 `responses` 换成
  `EmployeeSerializer(many=True)` 后实测，响应变为 `PaginatedEmployeeList`，
  且参数集变为 7 条（含上述 5 条泄漏 + `page` / `page_size`）——两条护栏均可捕获。
- `pytest apps/usermanagement -q` → **185 passed**
- `pytest apps/usermanagement/tests/test_employee_openapi_contract.py -v` → 9 passed
- `pytest apps/usermanagement/tests/test_employee_search_contract.py -q` → 16 passed（无回归）
- `ruff check .` → All checks passed；`ruff format --check .` → 335 files already formatted
- `ruff check . --select C90 --config lint.mccabe.max-complexity=10` → All checks passed
- `mypy . --strict` → 27 errors / 12 files，与存量基线**一致**（改动文件零错误）
- `spectacular --validate` → Warnings 23 (17 unique) / Errors 23 (6 unique)，与存量基线一致
- **基线逐叶子 diff**：全库仅 **3 处**变化，全部落在 sort 端点
  （`schema/$ref` 删、`schema/items/$ref` 增、`schema/type` 增），
  其余端点 / components / parameters **零漂移**
- `scripts/check_duplicate_invariants.py` → PASS
- `scripts/check_api_doc_consistency.py` → V-1~V-4 全通过（违规 0）

### 六、遗留与关联事项

1. **响应信封层缺失（另立条目）**：运行时返回 `{"code":0,"message":"...","data":[...]}`，
   而基线声明为裸数组、缺 `code` / `message` 信封层。这**不是本端点独有**——
   `batch-create` / `change_status` 等同样只声明裸对象，属**全基线 20+ 端点的共性问题**。
   经用户拍板，本轮只对齐既有裸对象 / 裸数组约定（改动面最小、不引入新模式），
   「响应信封缺失」另立系统性条目。若混入本端点修复会把 1 个文件的 diff 变成基线全量重写。
2. **raw dict 方案的固有耦合**：见「对抗审核」第 2 条。组件名变更需同步改
   `@extend_schema` 中的字面量，护栏会以红提示。
3. **机制教训登记**：本条为 A-44（BF-049 / BF-050）之后的**第三个独立机制**，
   已在 `Rules_Fiels/Duplicate_Codes/complete-patterns.md` 登记为 **A-46**。

*登记人：opencode ｜ 状态：已关闭，完成验证，2026-09-29*


## BF-058 【已关闭】功能提交顶穿 BR-4 函数长度红线、CI 兜底拦下——master 一度红灯 2026-09-29

### 〇、元信息

- **登记日期**：2026-09-29
- **来源**：本地复跑 `scripts/check_function_length_guard.py` 时暴露
- **关键程度**：P1（CI 红灯，阻塞后续合并；非功能缺陷）
- **影响范围**：`apps/assetmanagement/services/contract_service.py::ContractService.create_contract` + `Rules_Fiels/BR4_function_length_ledger.md`
- **契约影响**：无（纯结构重构，运行时行为零变化，无 API 变更，基线不需重导出）
- **跨端契约**：未变更

### 一、问题现象

`python scripts/check_function_length_guard.py` 报：

```
[FAIL] BR-4 函数长度护栏失败:
  - 未登记超长函数: assetmanagement/services/contract_service.py create_contract() 逻辑行数 52 > 50
```

该护栏挂在两处 CI——`ci.yml:39`（`backend-lint` job）与 `duplicate-guard.yml:28`（`submodules: true`），
故 `master` 自 `ed9487a` 起**一直是红的**。

### 二、根因

`ed9487a`（合同支付链路统一重算，BF-053~055）落实「决策 2a：创建入口的 `amount_paid`
规范化为 approved 期初付款记录」时，在 `create_contract` 体内**内联**了 16 个逻辑行：

```python
if opening_paid and Decimal(str(opening_paid)) > 0:
    contract.paid_record = json.dumps({...}, ensure_ascii=False)   # 15 行
    contract.save(update_fields=["paid_record", "updated_at"])
```

把该函数从 **36 顶到 52**，越过 BR-4 的 50 红线。提交前**未跑本地长度护栏**，
因此 CI 直接拦下。

**这不是存量豁免问题**（这是判定的关键）：

- 台账表格**是空的**——B1 / B2 / B3 三批已全部收口，header 明写「生产超长函数 **0 处**」，
  guard 复测输出亦为 `[PASS] 0 超长`；
- BR-4 规则原文明确「超限必须抽离，触发重构，**不得豁免**」；
- guard 是**双向**的：第 1 条「未登记即红」防新增回潮，第 2 条「已拆分未移除即红」防台账腐烂。
  故把它登记进台账表不仅绕过防线，还会与第 2 条语义冲突。

结论：**只能拆分**。这也再次证明台账是**兜底通道**而非豁免通道。

### 三、修复方案

1. **`contract_service.py`**——把上述 16 行抽为模块级私有 helper
   `_apply_opening_paid(contract: Contract, opening_paid: str | int | float | Decimal | None) -> None`，
   落位于既有 4 个 helper（`_parse_paid_record` / `_build_payment_entry` /
   `_sum_active_paid` / `_recalc_paid_amounts`）之后、类定义之前。
   守卫由 `if ... > 0:` 改为**卫语句早返回**，语义等价。
   `create_contract` 内 16 行塌缩为 1 行调用。
   `create_contract` **52 → 37 逻辑行**，`_apply_opening_paid` 25 逻辑行。
2. **原位保留「为什么」注释**（本条最易做错的一步）：`create_contract:160-163` 的 4 行
   【BF-055 / 决策 2a】论证**不在**待抽块内部，而是位于 `pop` 之前，解释的是
   「pop → 规范化 → 重算」**跨三处的完整链路**。塌缩后该三步仍连续可见于
   `create_contract`，故注释**原位不动**（注释行不计入 guard 逻辑行，保留零成本）；
   helper 的 docstring 只承接自身实现语义，**不复制**那段长论证，避免同一段文字双份维护。
3. **`BR4_function_length_ledger.md`**——header 追加事故注记（与 `210cfa7` 格式化事故同类并列），
   含「文件余量告急 489/500」提示。**台账表格不加行**（拆完即达标，加行反而触发第 2 条断言）。
   > ⚠️ **后续订正（2026-09-29）**：该「489/500」提示**已于 BR-6 护栏落地批次改写为作废声明**
   > （逻辑行口径实为 399/500，未违规）。此处为 BF-058 当时动作的历史记录，故原文保留不改；
   > 现行结论以 `BR4_function_length_ledger.md:21` 与本条 §六 遗留① 的订正为准。

### 四、对抗审核

1. **「为什么不登记台账豁免掉」**——BR-4 明文「不得豁免」；且台账双向化设计决定了
   登记新条目会引入「已拆分未移除即红」的维护负担，而本函数拆完即达标，登记纯属倒退。
2. **「为什么不压缩 docstring 凑行数」**——`create_contract` docstring 14 行**计入** guard 逻辑行
   （口径见台账 header 第 4 行），压缩确可减行，但那是**纯文本规避**、丢失接口文档。
   台账记载 B2/B3 拆分设计曾含「docstring 压缩」，但本条存在真结构解法，不取。
3. **「为什么不抽审计日志块（12 行）代替」**——`GenericAuditService.log_create(...)`
   只是一次委托调用，套壳价值薄；且该样板在全仓多服务重复，属**另一个 DR-1 议题**，
   不应混入本次范围（范围蔓延）。
4. **「卫语句真的等价吗」**——原式 `opening_paid and Decimal(str(opening_paid)) > 0`
   与新式 `if not opening_paid or Decimal(str(opening_paid)) <= 0: return` 短路顺序一致：
   falsy 值（含 `None`）先短路，**不会**走到 `Decimal(str(None))` 这条 `InvalidOperation` 路径。
   非数值字符串（如 `"abc"`）两侧同样抛 `InvalidOperation`，**非本次引入**，由 Serializer 先行校验兜底。
5. **「抽 helper 会不会让 DR-1 变差」**——不会。全仓 grep `opening_balance` / `期初已付`
   得 15 处命中，其中**实现点仅 1 处**（原 `:144-146`），其余均为注释、`help_text`、
   docstring 与测试断言。即本次是**纯搬移**而非「合并两处重复」。
   `batch_create_contract` 经 `_create_item` 直接调 `create_contract`，无重复实现，
   helper 一处即单条与批量两条路径共同受益。
6. **「类型标注 `Any` 会不会触发 strict 报错」**——已实测：`pyproject.toml` 的 mypy 段
   设 `warn_return_any = true`，但该 flag **只在 `return Any` 时触发**；helper 返回 `None`，
   `Decimal(str(...))` 是内联表达式不回传，故不触发。仍采用精确 union
   `str | int | float | Decimal | None`（比 `Any` 更贴实际入参；`float` 覆盖 API JSON 数值入参），
   实测目标文件 **0 错误**。

### 五、验证记录

- **重构前后行为等价**：`test_contract_service.py::TestCreateContractOpeningPaid` 5 条
  改动前 5 passed、改动后 5 passed，用例名与顺序逐字一致（纯重构零行为差异）
- **护栏**：`python ../scripts/check_function_length_guard.py` → `[PASS] 0 超长函数 / 0 未登记台账`；
  `--print` Top10 中 `create_contract` 已消失（现最高为 49 行 `complete_repair`）
- **行数实测**：`create_contract` 52 → **37**（余量 13）；`_apply_opening_paid` 25
- **文件行数**：475 → **489**（DR-5 上限 500，余量 11 —— 已记入台账告警）
- **静态**：`ruff check` → All checks passed；`ruff format --check` → 1 file already formatted；
  `C90 --config lint.mccabe.max-complexity=10` → All checks passed
- **类型**：`mypy apps/assetmanagement/services/contract_service.py --strict` → 该文件 **0 错误**；
  `mypy . --strict` → **27 errors / 12 文件，与存量基线一致，零新增**
- **域回归**：`pytest apps/assetmanagement -q` → **955 passed**

### 六、遗留与关联事项

1. ~~**文件余量告急**~~ **订正（2026-09-29，BR-6 护栏落地批次）**：本条原记「`contract_service.py` 489/500，仅余 11 行…BR-6 拆 `payment_service.py` 另立议题」，**该结论建立在 `wc -l`（含空行）口径上，予以作废**。BR-6 口径统一为**逻辑行**（排空行 / 纯 `#` 注释行 / 模块 docstring）后，`contract_service.py` 实为 **399 逻辑行**，**未超 500，无需拆分，原拆分议题取消**；`add/delete/approve_payment_record` 三方法（38/23/25 行）保持在 `contract_service.py` 内不动。**教训**：行数类指标必须显式定义口径——同一文件 `wc -l` 读 489、逻辑行读 399，差 90 行（22%），足以把「余量 11 行」误读成「已越线」。参见 `Rules_Fiels/BR6_file_length_ledger.md` 与 `Rules_Fiels/BR4_function_length_ledger.md:21` 同源订正。「合同域功能优先新建文件」可保留为风格偏好，但**不再是红线驱动**。
2. **临界函数观察**：`complete_repair`（49）与 `reject_asset_recordcode`（49）**距红线仅 1 行**，
   后续任何加行都会触发护栏红。建议在动手改这两个函数前先跑 `--print` 确认余量。
3. **机制教训**：详见 `Rules_Fiels/BR4_function_length_ledger.md` header 的
   「功能提交顶穿红线事故 + 教训（2026-09-29）」注记——本条是 `210cfa7` 之后**第二次同型事故**
   （「功能/格式化改动会改变长度类指标」），教训已固化为「在既有大函数内追加 ≥ 10 行须复跑护栏」。

*登记人：opencode ｜ 状态：已关闭，完成验证，2026-09-29*


## BF-059 【部分关闭】后端变异测试门禁空转：mutmut 未声明依赖、统计口径错误、无阈值断言 2026-09-29

### 〇、元信息

- **登记日期**：2026-09-29
- **来源**：CI 门禁失效排查（方案见 `docs/BugFixed/Bug待修复计划-20260929.md` §1-A①、§3.1）
- **关键程度**：P1（门禁看似存在、实则空转，风险不外显）
- **影响范围**：`.github/workflows/ci.yml:218-257`（job `backend-mutation`）、`asset_management_backend/requirements/dev.txt`、`asset_management_backend/setup.cfg`
- **契约影响**：无（已改动均为 CI/构建配置，零运行时代码）
- **跨端契约**：未变更
- **当前阶段**：**第 0a 批已落地**（2026-09-29）——6 项修复全部实施并本地验收通过；**0b（真实得分与阈值）待 CI 首跑**
- **状态补标（2026-09-29）**：依 0a 落地结果回填。原登记【待修复】→【部分关闭】，未关闭部分为 0b 的阈值拍板（依赖 CI 首跑真实得分，现本机 Windows 无法运行 mutmut 3.8.0）。

> **⚠️ 行号引用通用说明（适用于 BF-059 ~ BF-064 六条）**：本组六条登记于 0a 执行**之前**，
> 其 §一 / §二 / §五 中的 `ci.yml` 行号是 **0a 前的快照**。0a 在 `ci.yml` 两处变异 step 与
> `ci-summary` 插入了 3~5 行注释、+3 个 `timeout-minutes`、+2 个 `continue-on-error`，
> 行号整体下移，总行数 384 → **434**。**当前**关键位置（2026-09-29 实测）：
>
> | 对象 | 0a 前引用 | 当前实测 |
> |:---|:---|:---|
> | 后端 job `backend-mutation` | `:218-257` | `:218`（job 未动，**仍为 218**） |
> | 后端变异 step | `:251` | `:251`（`continue-on-error` `:255`、`timeout-minutes` `:256`） |
> | 后端判分 step | — | `:258`（`continue-on-error` `:264`、`timeout-minutes: 5` `:265`、`THRESHOLD` `:272`、`score` `:287`、`sys.exit` `:293`） |
> | 前端复杂度 step | `:314-316` | `:351`（`continue-on-error` `:356`） |
> | `frontend-test` needs | `:321` | `:363` |
> | 前端 job `frontend-mutation` | `:346-364` | `:389`（step `:405`，`continue-on-error` `:409`、`timeout-minutes` `:410`） |
> | `ci-summary` job | `:367-383` | `:415`（needs `:417`、gate `:430-431`、0a TODO 注释 `:432-434`） |
> | 后端 C90 step | `:73` | `:72` |
>
> 下文引用未逐条改写，以免破坏登记时的取证原貌；**以本表为当前真值**。

### 一、问题现象

1. `ci.yml:218` 定义 job `后端 - 变异测试`（`needs: [backend-test]`），`:251` 名为「变异测试（红线 80% Killed）」的 step
2. 该 step 的命令为 `ci.yml:253`：`mutmut run --paths-to-mutate apps/assetmanagement/services`
3. 但 `asset_management_backend/requirements/dev.txt` **零次命中 `mutmut`**（全文 46 行，`Select-String` 计数 = 0），
   `:250` 只执行 `pip install -r requirements/dev.txt` → 该 step 必然以「命令不存在」告终
4. 即使命令可用，`:255`/`:256` 用 `grep -c` 统计**文本行数**、`:257` 仅 `echo`，**全 step 无任何阈值断言**
5. 真实得分基线为 **65.63%**，低于 `Rules_Fiels/backend-testing-rules.md` T7 要求的 80% 红线（规则 ID 订正 2026-09-30：原误记 T8，该 ID 为迁移验证；变异红线实名 T7）

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 依赖缺失 | `requirements/dev.txt` 与其 `-r base.txt` 链均未声明 mutmut——T8 所需工具从未真正接入 |
| 2 | 配置缺失 | `setup.cfg` 仅含 `[coverage:run]`(`:1`) 与 `[coverage:report]`(`:16`)，**无 `[mutmut]` 段** |
| 3 | CLI 用的是 2.x 口径 | `:253` 的 `--paths-to-mutate` 对应的配置键在 mutmut 3.8.0 源码中已标记 deprecated |
| 4 | 口径错误 | `grep -c "killed"` / `grep -c "total"` 统计的是 `mutmut results` 输出的**匹配行数**，与 mutant 总数无换算关系；无论何种输出版本都得不到比率 |
| 5 | 断言缺失 | step 内无 `if:` 条件、无显式非零退出，job 恒为 success |
| 6 | 规则未落地 | T8 的 80% 在 CI 中**没有任何环节**被转成退出码 |

### 三、修复方案（0a 已执行，2026-09-29）

| # | 变更 | 文件 | 落地状态 |
|---|------|------|------|
| 1 | 增 `mutmut==3.8.0` | `requirements/dev.txt` | ✅ 已落地 |
| 2 | 新增 `[mutmut]` 段：`source_paths` / `pytest_add_cli_args` / `pytest_add_cli_args_test_selection` / `also_copy`；弃用 `paths_to_mutate`、`tests_dir`；**不写** 2.x 的 `runner` / `CI` 键（3.x 无此二键） | `setup.cfg` | ✅ 已落地（**方案原文有误，见下**） |
| 3 | 变异 step 增 `timeout-minutes: 300` | `ci.yml` | ✅ 已落地（**位置修正为 step 级**） |
| 4 | step 增 `continue-on-error: true`（0a 临时闸）；`ci-summary` 补 `backend-mutation.result` 判定（见 BF-061）；0b 得分达标后移除 | `ci.yml` | ⏸️ 部分落地（**`ci-summary` 经用户拍板 0a 阶段仅输出不阻断**，见 BF-061） |
| 5 | 后端 `ruff C90` 门禁（`ci.yml:73`）**不动** | `ci.yml` | ✅ 确认未动 |
| 6 | 增 `mutants/` 到 `.gitignore` | `.gitignore` | ✅ 已落地（0a 计划外补充：实测 mutmut 工作目录名为 `mutants`，不入忽略会污染 `git status`） |

> **方案原文第 2 项的 3 处错误（对抗审核查实，以实测为准）**：
> ① 原写 `pytest_add_cli_args = -x --assert=plain --ds=config.settings.test` **单行**——mutmut 3.8.0 的 list 型配置键按**每行一个元素**解析，单行会被当成**单个 argv 字符串**（实测 `config()` 返回 `['-x --assert=plain --ds=config.settings.test']`），pytest 无法识别；已改为多行写法。
> ② 原方案**未提 `also_copy`**，但只配 `source_paths` 会导致 mutants 环境 import 崩溃——`also_copy` 默认为空，仅复制 tests/test/setup.cfg 等，**不含**本仓 `apps/*/tests/`、`config/`、`core/`、`utils/`。已显式配 `also_copy = apps / core / config / utils / conftest.py / pytest.ini`。
> ③ 原方案未提 `pyproject.toml` 优先级——该文件当前**无** `[tool.mutmut]` 段，但一旦有人新增，mutmut 会**完全忽略 `setup.cfg`**。已在 `setup.cfg` 注释中留此警示。
>
> **方案原文第 3/4 项的位置修正**：`timeout-minutes` 与 `continue-on-error` 均改为 **step 级**（原方案写作 job 级位置），经用户拍板确认。

### 四、对抗审核

1. **为何不用 `--fail-under 80` 一刀切**——mutmut 无该 flag；且 2.5.1 冷启动基线 4h15m，300 分钟上限仅余 45 分钟。
   先实测耗时再谈硬阻断，否则门禁会从「空转」直接跳到「恒超时」。
2. **为何钉 3.8.0 而非追最新版**——AR-1：3.8.0 的 `pytest_add_cli_args_test_selection` 对目录的展开语义、
   `also_copy` 对本仓 `apps/*/tests/` 的覆盖行为**均未首跑实证**；钉死版本是为了让首跑结果可复现，不是判断 3.8.0 为最优。
3. **加 `continue-on-error` 算不算放水**——不算：0a 期间 `ci-summary` 仍把 `backend-mutation.result` 纳入阻断条件（BF-061），
   即「job 内红、汇总处也红」，step 级豁免仅用于避免红灯阻断后续无关 job 的长跑，不改变最终合并判定。
4. **为何不顺带改 C90**——后端圈复杂度是独立硬门禁，与变异测试正交；同批改两个指标会让「哪个改动导致红灯/变绿」不可归因。

### 五、验证记录

**登记时（只读取证，2026-09-29）**：

```text
① 依赖缺失：Select-String "mutmut" requirements/dev.txt → 命中 0（文件 46 行）
② 配置缺失：Select-String "^\[" setup.cfg → 仅 :1 [coverage:run]、:16 [coverage:report]
③ CI 现状：rg "mutmut run|grep -c" ci.yml → :253 run、:255 KILLED、:256 TOTAL、:257 echo；:251-257 内无 if/exit
④ 后端基线：docs/Review/mutation-baseline-2026-09-24.md → 1385 mutants / 4h15m / 65.63%（909 killed、476 survived）
⑤ 3.8.0 配置键现状：本机 mutmut 3.8.0 源码内 paths_to_mutate、tests_dir 标记 deprecated；无 runner / CI 配置键
```

**0a 落地后（2026-09-29，共 20 项全 PASS）**：

```text
① mutmut 3.8.0 真实 _load_config() 实跑（PYTHONUTF8=1）→ 加载成功、无弃用键 DeprecationWarning
② list 型键切分：pytest_add_cli_args 实测返回 ['-x', '--assert=plain', '--ds=config.settings.test']（3 元素）
③ also_copy 探针：tests / 跨 app import / models·selectors·serializers·state_machine / config·core·utils 全部 0 遗漏
④ 判分脚本 8 场景回归：85% / 65.63% / 80% 边界 / 零分母 / 全部 skipped / 缺展示字段 / 缺 JSON —— 全 PASS
   （首版对展示字段硬取键，回归抓到 KeyError → 改 .get 兜底，计分输入仍严格；缺陷由自己的测试抓出）
⑤ CI heredoc 经真实 Git Bash 执行：达标 exit 0 / 未达标 exit 1 —— 双向可证
⑥ setup.cfg 解析、ci.yml YAML 解析、stryker.config.json 解析 —— 全 PASS
⑦ dev.txt 恰好 1 个 mutmut 版本钉（mutmut==3.8.0）
⑧ step 级 timeout-minutes：backend-mutation=300、frontend-mutation=90
⑨ 4 处容错点齐全（backend-mutation 两 step + frontend-mutation + frontend-complexity）
⑩ backend-complexity（ruff C90）确认未被顺带放宽
⑪ check_duplicate_invariants.py PASS（G-1~G-5）
⑫ check_frontend_invariants.py PASS
⑬ mutmut 3.8.0 requires_python >=3.10，兼容 CI Python 3.12
未执行（受本机 Windows 限制，mutmut 3.8.0 对原生 Windows 直接 sys.exit(1)）：
⑭ mutmut run 首跑、⑮ 耗时实测、⑯ 得分复测 —— 三项均待 CI 首跑（0b）
```

### 六、遗留与关联事项

1. 关联 **BF-061**（ci-summary 漏判 mutation job）、**BF-064**（80% 口径缺口）。
2. `asset_management_backend/pytest.ini` 现为 `DJANGO_SETTINGS_MODULE = config.settings.development`；
   mutation 跑测试须显式传 `--ds=config.settings.test`，否则复用开发 settings（**已写入 `[mutmut]` 配置**）。
3. `also_copy` 显式配齐（0a 已做）：实测默认集合不含本仓 `apps/*/tests/`、`config/`、`core/`、`utils/`，
   故按探针结果补 `apps / core / config / utils / conftest.py / pytest.ini`。
4. **`pyproject.toml` 优先级风险（0a 新增留档）**：该文件现无 `[tool.mutmut]`；一旦有人新增，mutmut 将**静默忽略** `setup.cfg` 全部配置（无警告），表现为「配置写了但不生效」。`setup.cfg` 已加注释警示。
5. **`timeout-minutes: 300` 余量风险（0a 新增留档）**：冷启动基线 4h15m（255 min），距 300 min 上限**仅余 45 分钟**；`also_copy` 扩容后首跑可能更慢。若 CI 首跑超时，正确处置是**分片**（按 service 子包切分 `source_paths`）而非放宽上限。
6. 0b 待办：依 CI 首跑真实得分与耗时，拍板 80% 阈值是否下调、是否移除 4 处 `continue-on-error`。

*登记人：opencode ｜ 状态：0a 已落地并本地验收通过（20 项），0b 待 CI 首跑（阈值与容错拍板），2026-09-29*


## BF-060 【部分关闭】前端变异测试命令非法：`npx vitest --mutate` 被 CAC 拒绝，job 恒红 2026-09-29

### 〇、元信息

- **登记日期**：2026-09-29
- **来源**：CI 门禁失效排查（方案见 `Bug待修复计划-20260929.md` §1-A②、§3.3）
- **关键程度**：P1（变异测试从未真正执行）
- **影响范围**：`.github/workflows/ci.yml:346-364`（job `frontend-mutation`）、`vue-assetmanagement/stryker.config.json`
- **契约影响**：无
- **跨端契约**：未变更
- **当前阶段**：**第 0a 批已落地**（2026-09-29）；**0b（31 store 全量得分与耗时）待 CI 首跑**
- **状态补标（2026-09-29）**：依 0a 落地结果回填。【待修复】→【部分关闭】，未关闭部分为 0b 的耗时/得分拍板。

### 一、问题现象

1. `ci.yml:346` job `前端 - 变异测试`（`needs: [frontend-test]`），`:363` step 名「变异测试（红线 80% Killed）」
2. `:364` 的命令为 `npx vitest --mutate`
3. 实跑该命令 → `CACError: Unknown option \`--mutate\``
4. 项目真实变异工具是 **Stryker**（`package.json` 已定义 `"test:mutate": "stryker run"`；
   `stryker.config.json:4` `"testRunner": "vitest"`），Vitest 本身**不提供** mutation 能力
5. 后果：job 每次必红；又因 `ci-summary` 未判该 job（**BF-061**），红灯**不阻断** →
   变异测试实际处于「长期红灯但无人拦截」的假绿状态

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 命令写错 | 把 Vitest 当作变异测试运行器；`--mutate` 不是 Vitest 的合法 flag |
| 2 | 与项目工具链脱节 | `@stryker-mutator/*` 与 `test:mutate` 脚本均已就位，CI 却未调用 |
| 3 | 静默失败 | `ci-summary` 只 gate `backend-test`/`frontend-test`，本 job 红灯不传导（`ci.yml:380-381`） |

### 三、修复方案（0a 已执行，2026-09-29）

| # | 变更 | 文件 | 落地状态 |
|---|------|------|------|
| 1 | `:364` 改为 `npm run test:mutate`（走 `stryker run`，与本地口径一致） | `ci.yml` | ✅ 已落地 |
| 2 | 删 `concurrency: 4`（`:18`）解除内存争用；代价是耗时上升 | `stryker.config.json` | ✅ 已落地 |
| 3 | step 增 `timeout-minutes: 90`；0a 临时 `continue-on-error: true`，0b 移除 | `ci.yml:363` | ✅ 已落地（**位置修正为 step 级**） |
| 4 | `break: 80`（`:10`）**暂不动**，0b 依真实得分决策 | `stryker.config.json` | ✅ 确认未动 |

> **方案原文第 3 项的位置修正**：`timeout-minutes` 与 `continue-on-error` 均改为 **step 级**（原方案写作 job 级位置），经用户拍板确认。

### 四、对抗审核

1. **「升级 vitest 就能用 --mutate 吗」**——不能。mutation 是独立运行器能力，Vitest 未内置该 flag；
   换运行器是唯一路径，不是版本问题。
2. **「删 concurrency 会不会让 CI 更慢甚至超时」**——会，耗时上升。取舍是「宁慢不 flaky」：
   既有基线（7 store / 3m51s）本身就是低并发下才稳定的。删并发后耗时须以 0a 首跑实测为准，
   若逼近 90 分钟上限再议分片，而非把并发调回去换不确定性。
3. **「把 break 从 80 降到 60 基线行不行」**——不行。60.00 是**聚焦 7 store** 口径，
   而 `stryker.config.json:6` 的 `mutate` 覆盖 `src/stores/**/*.ts`（实测 31 个 store）；
   拿聚焦分当全量红线会制造假绿，正是本次要清除的病根。

### 五、验证记录

**登记时（只读取证，2026-09-29）**：

```text
① 命令非法实证：npx vitest --mutate → CACError: Unknown option `--mutate`
② 工具链事实：package.json → "test:mutate": "stryker run"；stryker.config.json:4 testRunner=vitest、:6 mutate=["src/stores/**/*.ts"]
③ store 基数：Get-ChildItem src/stores -Filter *.ts → 31 个；既有基线仅覆盖 7 store / 120 mutants
④ 配置行号：rg '"break"|"concurrency"' stryker.config.json → :10 break 80、:18 concurrency 4
⑤ 前端基线：mutation-baseline-2026-09-24.md → 7 store / 120 mutants / 3m51s / score 60.00（72 killed、44 survived、4 no-cov）
```

**0a 落地后（2026-09-29）**：

```text
① stryker.config.json JSON 解析 PASS；'concurrency' 键已移除、'thresholds.break' 仍为 80 ✅
② ci.yml 中 frontend-mutation 命令已改 npm run test:mutate；step 级 timeout-minutes=90、continue-on-error=true ✅
③ check_frontend_invariants.py PASS
④ 0a 判分脚本 8 场景回归全 PASS（含前端 score 口径边界）
未执行（受本机 Windows 限制 / 耗时）：
⑤ stryker run 实跑、⑥ 删并发后的真实耗时、⑦ 全量 31 store 真实得分 —— 待 CI 首跑（0b）
```

### 六、遗留与关联事项

1. 全量 31 store 的真实得分与耗时**未知**，第 0b 批决策直接依赖该数据。
2. 基线中 4 个 no-cov mutants 说明存在零覆盖代码，可作为后续补测的目标清单来源。
3. 关联 **BF-061**（漏判导致本条红灯不外显）、**BF-064**（80% 口径缺口）。
4. **删并发后的耗时未知（0a 新增留档）**：既有 3m51s 基线是**并发 4** 下的耗时，删并发后必然上升；`timeout-minutes: 90` 是否够用**尚无实测支撑**。若 CI 首跑超时，正确处置是分片而非把 `concurrency` 加回（对抗审核第 2 条的取舍在此生效）。

*登记人：opencode ｜ 状态：0a 已落地并本地验收通过，0b 待 CI 首跑（31 store 全量得分与耗时），2026-09-29*


## BF-061 【待修复】ci-summary 漏判两个 mutation job——红灯不阻断，存在假绿通道 2026-09-29

### 〇、元信息

- **登记日期**：2026-09-29
- **来源**：CI 门禁失效排查（方案见 `Bug待修复计划-20260929.md` §1-A③、§3.4）
- **关键程度**：P1（合并闸门存在缺口）
- **影响范围**：`.github/workflows/ci.yml:367-383`（job `ci-summary`）
- **契约影响**：无
- **跨端契约**：未变更
- **当前阶段**：**0a 阶段有意不实施**（2026-09-29，用户拍板）——门禁补判整体延至 0b
- **状态补标（2026-09-29）**：本条**未关闭**，仍为【待修复】。原方案要求 0a 即补入阻断条件，经**用户拍板偏离**：0a 阶段 `ci-summary` 只 echo 输出两个 mutation job 的 result，**不纳入阻断条件**。理由见下方 §四第 4 条（补记）。0a 仅在 `ci-summary` 留 TODO 注释标记此处缺口。

> **⚠️ 假绿通道在 0a 阶段依然存在**：本条是 BF-059 / BF-060 能长期共存而不被发现的结构性成因。
> 0a 已修好两个 job 本身（BF-059 / BF-060），但**汇总闸门仍未覆盖它们**——即 0a 结束后，
> 变异测试若再变红，仍不会阻断合并。此为**已知且被明确接受**的临时状态，0b 必须收口。

### 一、问题现象

1. `ci.yml:370` `ci-summary` 声明 `needs: [backend-test, backend-mutation, frontend-test, frontend-mutation]`
2. `:376-379` **echo 了全部四个** job 的 result
3. 但真正的阻断条件 `:380-381` **只判两个**：

   ```bash
   if [ "${{ needs.backend-test.result }}" != "success" ] || \
      [ "${{ needs.frontend-test.result }}" != "success" ]; then
   ```

4. 后果：`backend-mutation` / `frontend-mutation` 无论红绿都**不影响合并判定**。
   这是 BF-059（后端变异空转恒绿）与 BF-060（前端变异恒红）能长期共存而不被发现的结构性原因。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 判定面 < 采集面 | `needs` 收集 4 个 result，`if` 只消费 2 个——**echo 与 gate 不对称** |
| 2 | 门禁语义退化 | job 层面的失败被降级为「信息展示」，闸门实际只覆盖测试与覆盖率 |
| 3 | 与规则脱节 | T8（后端 80%）/ T16（前端 80%）是硬性规则，但无任何汇总环节承接 |

### 三、修复方案（**0a 未实施，整体延至 0b**）

| # | 变更 | 文件 | 落地状态 |
|---|------|------|------|
| 1 | 阻断条件补入两个 mutation job 的 result 判定 | `ci.yml:380-381` | ⏸️ **未实施**（用户拍板延至 0b） |
| 2 | 与 BF-059 / BF-060 的 `continue-on-error` 配套：0b 达标后双双移除 | `ci.yml` | ⏸️ 随 0b 一并执行 |
| 3 | `ci-summary` 留 TODO 注释标记此处缺口 | `ci.yml` | ✅ 已落地（0a 唯一改动） |

### 四、对抗审核

1. **「加了判定不就等于给未跑通的变异测试判死刑吗」**——正是设计意图。当前状态下**不该**合并：
   门禁空转（BF-059）与命令非法（BF-060）都是真缺陷，先让它们红着、修复后转绿，
   比让它们安静地绿着更安全。
2. **「0a 期间是否会造成必然红的 master」**——会，但这是**如实反映**。
   与 BF-062 的 `frontend-complexity` step 豁免不同：那条豁免的是「已知会红且需专项治理」的复杂度债（52 处存量），
   本条不留豁免，因为变异测试失效属可快速修复的工具链问题，不应长期挂红。
3. **「能否只判 `backend-mutation` 不判 `frontend-mutation`」**——不能只挑一个。
   双源变异测试是 T8 + T16 的明确要求，单边 gate 等于把缺口从两侧挪到一侧。
4. **【2026-09-29 补记·与上述第 2 条相反，用户拍板】**——0a 阶段**仍不补判**，理由：
   0a 的两个变异 job 均带 `continue-on-error: true`，其红绿信号在首跑取证前**不可信**
   （后端 65.63% / 前端 60.00 双双未达 80%，见 BF-064；`timeout-minutes: 300` 余量仅 45 分钟亦未验证）。
   在信号未验证时把不确定结果接入合并闸门，会产生「因未验证因素卡住合并」与「红灯被当噪声忽略」
   两头都不好的局面。**先取真实数据，再一次性收口**（0b 同时补判 + 拍板阈值 + 移除容错）。
   **代价已明确接受**：0a→0b 期间假绿通道敞开，故本条不得被视作已修复。
   *（第 2 条的「本条不留豁免」是 0a 之前的判断，已被本次拍板取代，保留原文以留痕。）*

### 五、验证记录

**登记时（只读取证，2026-09-29）**：

```text
① needs 采集面：ci.yml:370 → [backend-test, backend-mutation, frontend-test, frontend-mutation]（4 项）
② echo 面：ci.yml:376-379 → 4 行 echo 齐全
③ gate 面：ci.yml:380-381 → 条件仅含 backend-test、frontend-test（2 项），两个 mutation 未判
④ 交叉印证：BF-060 记录的 CACError 使 frontend-mutation 恒红，而该红灯不影响合并判定
```

**0a 落地后（2026-09-29）**：

```text
① ci.yml YAML 解析 PASS
② 确认阻断条件仍仅含 backend-test / frontend-test 两项（0a 未补判，符合拍板）✅
③ 确认 echo 面仍输出全部 4 个 job result（信息面未收窄）✅
④ 确认 ci-summary 内已留 TODO 注释标记 0b 待补判处
⑤ 两个 test job 的既有阻断判定未被削弱 ✅
未执行：
⑥ 故意让某 mutation job 失败并确认 ci-summary exit 1 的行为实测 —— 门禁尚未实施，0b 才可验
```

### 六、遗留与关联事项

1. 本条是 BF-059 / BF-060 的**结构性成因**，三者应同批修复、同批验证。
2. 修复后需实测：故意让某 mutation job 失败，确认 `ci-summary` 确实 `exit 1`（不得只做静态核对）。
3. **0b 验收清单（本条的唯一收口条件）**：① 阻断条件含 4 个 job；② 4 处 `continue-on-error` 依 0b 结论处理；③ 行为实测（非静态核对）确认 mutation 红 → `ci-summary` exit 1。三项齐备方可改【已关闭】。

*登记人：opencode ｜ 状态：**待修复**（0a 经用户拍板有意不实施，仅留 TODO 注释；0b 必须收口），2026-09-29*


## BF-062 【部分关闭】前端复杂度 error 级门禁：52 处存量失败并连带跳过后续 job 2026-09-29

### 〇、元信息

- **登记日期**：2026-09-29
- **来源**：CI 门禁失效排查（方案见 `Bug待修复计划-20260929.md` §1-A④、§3.2）
- **关键程度**：P1（阻断链扩散：一条 lint 规则失败会跳过测试与变异测试）
- **影响范围**：`.github/workflows/ci.yml:314-316`（job `frontend-complexity`）、`vue-assetmanagement/AGENTS.md §1.3`
- **契约影响**：无
- **跨端契约**：未变更
- **当前阶段**：**0a 已落地临时缓解**（step 级 `continue-on-error`），**阻断链断开但 52 处债未清**
- **状态补标（2026-09-29）**：【待修复】→【部分关闭】。方案第 1 项（止血）已落地；第 2/3 项（规范文本不动 + 52 处债另立专项）为**长期待办**，第 4 项（0b 评估解绑阻断链）待 CI 数据。

### 一、问题现象

1. `ci.yml:314-316` step「复杂度检查（上限10）」执行
   `npx eslint . --ext .vue,.ts --rule 'complexity: [2, 10]'`
2. 本地实跑该命令 → **52 errors**，退出码 **1**
3. 连带效应（阻断链）：
   - `ci.yml:321` `frontend-test` 的 `needs: [frontend-lint, frontend-type-check, frontend-complexity]`
   - `ci.yml:349` `frontend-mutation` 的 `needs: [frontend-test]`
   → 复杂度失败 ⇒ **测试被跳过** ⇒ **变异测试被跳过**（这也是 BF-060 的红灯长期无人处理的旁证）

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 规则为 error 级 | `AGENTS.md §1.3` 将该复杂度上限定为**硬红线**（与后端 `ci.yml:73` 的 C90 同级） |
| 2 | 存量未清 | 52 处超限代码**先于该门禁存在**，门禁上线时无过渡期，一次性把存量与增量同时判红 |
| 3 | 无区分机制 | 门禁不区分「新增超限」（必须阻断）与「存量超限」（需专项治理），二者混在同一退出码里 |
| 4 | 缺少阻断链设计 | `needs` 是硬依赖，任一前置红则后续**整体跳过**而非「跳过但照常汇报」，信息量损失 |

### 三、修复方案（0a 已执行止血部分，2026-09-29）

| # | 变更 | 文件 | 落地状态 |
|---|------|------|------|
| 1 | step 增 `continue-on-error: true`（**仅 step 级**，0a 临时闸） | `ci.yml:314` | ✅ 已落地 |
| 2 | `AGENTS.md §1.3` 的 error 级措辞**不改** | `vue-assetmanagement/AGENTS.md` | ✅ 确认未改 |
| 3 | 52 处复杂度债另立台账专项治理（0b 消解或依 §5.4 沙盒期降级） | 台账待建 | ⏳ **长期待办**（0a 未建） |
| 4 | 0b 依 0a 的前端 mutation 真实数据，评估是否解绑阻断链 | `ci.yml:321`、`:349` | ⏳ 待 CI 数据 |

> **step 级 vs job 级的可验证差别**（0a 落地时复核）：两者都会让 `frontend-complexity` 的
> `needs` 消费方看到 `success`（断链效果一致），差别在**豁免范围**——
> **step 级**只豁免「复杂度检查」这一个 step：该 job 其余步骤（依赖安装、配置加载等）失败**仍判 job 失败**；
> **job 级**会把整个 job 的**一切**失败一并吞掉，导致除复杂度外的真故障（如 `npm install` 断网）
> 也被伪装成绿灯，故障域被不必要地放大。故 0a 采用 step 级，以将豁免收窄到确知的那一点债上
> （用户拍板的两处位置修正之一）。
>
> *本条仅断言 YAML 语义层面的差别；GitHub 各级别的**视觉呈现**差异未经实测，不作断言（Fact-1）。*

### 四、对抗审核

1. **「加 continue-on-error 是不是把红线废了」**——规则文本未动，语义未降级；
   变的只是**step 级执行顺序**（不因它跳过无关 job），而 `ci-summary` 的阻断判定独立于本 step（BF-061）。
   红线是否生效由规范文本与最终 gate 决定，不由阻断链的 skip 行为决定。
2. **「为什么不直接把 52 处分批改掉」**——52 处跨越多个 store 与视图，属独立专项（0b），
   与 CI 工具链修复（0a）混在一批会同时改变「工具链是否可用」与「代码风格达标率」两个指标，不可归因（AR-5 静态自检同理）。
3. **「为什么后端 C90 不加豁免」**——后端 C90 **当前是绿的**（`ci.yml:72` 通过），
   无需豁免；豁免只对已知红且需专项治理的项开。
4. **「52 这个数会不会是环境差异」**——规则为纯静态圈复杂度计算，与运行时/依赖版本无关，
   数字可复现（命令与退出码见验证记录）。

### 五、验证记录

**登记时（只读取证，2026-09-29）**：

```text
① 复杂度失败实证：npx eslint . --ext .vue,.ts --rule 'complexity: [2, 10]' → 52 errors，exit 1
② 阻断链：ci.yml:321 frontend-test needs [frontend-lint, frontend-type-check, frontend-complexity]
③ 二级连带：ci.yml:349 frontend-mutation needs [frontend-test]
④ 后端对照：ci.yml:73 ruff check . --select C90 --config lint.mccabe.max-complexity=10（当前通过，无需豁免）
⑤ 规范定位：vue-assetmanagement/AGENTS.md §1.3 复杂度上限为 error 级硬红线
```

**0a 落地后复跑（2026-09-29，当日实测）**：

```text
① 前端复杂度复跑：npx eslint . --ext .vue,.ts --rule 'complexity: [2, 10]'
   → "52 problems (52 errors, 0 warnings)"，exit 1 —— 数字与登记时逐字相符，52 处债未变 ✅
② 后端 C90 复跑：python -m ruff check . --select C90 --config "lint.mccabe.max-complexity=10"
   → "All checks passed!"，exit=0 —— 佐证 §四第 3 条「后端当前是绿的」属实 ✅
③ 阻断链已断：frontend-complexity step 现带 continue-on-error（当前 :356），job 成功
   → frontend-test needs 满足（当前 :363）→ 测试不再被跳过 ✅
未执行：0a 首跑后的复杂度 CI 实跑、52 处逐处消解 —— 后者属 0b 专项，52 处债台账尚未建立
```

> 行号说明：**登记时**区块 ②③④ 与 §四第 3 条中的 `:321 / :349 / :73` 为 0a 前快照，
> 当前值见 BF-059 顶部的行号对照表；**0a 落地后复跑**区块内的 `:356 / :363` 为当前实测值。

### 六、遗留与关联事项

1. 52 处复杂度债**台账尚未建立**；建立时须明确标注「不覆盖后端 Ruff C90」（两者是不同规则的同名概念）。
2. 与 **BF-060** 存在间接因果：复杂度红 → 变异测试被跳过 → `npx vitest --mutate` 的非法命令长期无人察觉。
3. `complete_repair`（49 行）与 `reject_asset_recordcode`（49 行）距 BR-4 红线仅 1 行（见 BF-058 第六节），
   治理 52 处时若触及这两个函数需先复跑长度护栏。

*登记人：opencode ｜ 状态：部分关闭（0a 止血已落地并本地验收通过；52 处债台账待建，0b 评估阻断链），2026-09-29*


## BF-063 【部分关闭】ci.yml 全无 timeout-minutes / continue-on-timeout 兜底，失败无边界 2026-09-29

### 〇、元信息

- **登记日期**：2026-09-29
- **来源**：CI 门禁失效排查（方案见 `Bug待修复计划-20260929.md` §1-A⑤、§3.5）
- **关键程度**：P2（可靠性问题，非正确性问题）
- **影响范围**：`.github/workflows/ci.yml`（登记时 384 行）
- **契约影响**：无
- **跨端契约**：未变更
- **当前阶段**：**0a 已给两个重任务设边界**（后端 300 min / 前端 90 min，另判分 step 5 min），**其余 job 仍无超时**
- **状态补标（2026-09-29）**：【待修复】→【部分关闭】。方案第 1/2/3 项已落地，第 4 项（依实测重标超时值）待 CI 首跑；「全文无 timeout-minutes」这一登记时的事实**已不再成立**，但「全 job 都有边界」尚未达成。

### 一、问题现象

> **补标（2026-09-29）**：以下 1~3 条为**登记时**事实，0a 后已部分变化——`ci.yml` 现有
> `timeout-minutes` ×3（backend-mutation 300 / 其判分 step 5 / frontend-mutation 90）、
> `continue-on-error` ×4（两个 mutation step + 前端复杂度 step）。其余 job 仍无边界。

1. `ci.yml` 全文 384 行，**无任何** `timeout-minutes` 声明
2. 全仓库亦无 step 级 `continue-on-error` 兜底
3. 后果：变异测试这类耗时数小时的任务（后端基线 4h15m）**无上界**——
   挂死时只能等 GitHub 自身 6 小时硬上限，且失败原因与「真的跑不完」无法区分

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 缺超时 | 无 job/step 级 `timeout-minutes`，重任务无边界 |
| 2 | 缺降级 | 单一工具链故障（如 BF-060 的非法命令）会直接阻断整条链，无「记录但放行」档位 |
| 3 | 观测缺失 | 失败是超时、OOM 还是断言不通过，日志里无统一标记 |

### 三、修复方案（0a 已执行核心部分，2026-09-29）

| # | 变更 | 文件 | 落地状态 |
|---|------|------|------|
| 1 | `backend-mutation` step 增 `timeout-minutes: 300` | `ci.yml:251` | ✅ 已落地（step 级） |
| 2 | `frontend-mutation` step 增 `timeout-minutes: 90` | `ci.yml:363` | ✅ 已落地（step 级） |
| 3 | 两个 mutation step 0a 临时增 `continue-on-error: true` | `ci.yml:251`、`:363` | ✅ 已落地（step 级；另增**后端判分 step `timeout-minutes: 5`**，为原方案外补充——判分是纯 JSON 计算，5 分钟足够） |
| 4 | 0b 依实测耗时**重新标定**两个超时值（300/90 为初始估计，非实测） | `ci.yml` | ⏳ 待 CI 首跑 |
| 5 | 其余 job（test / lint / type-check / coverage / complexity 等）补边界 | `ci.yml` | ⏳ **未做**（原方案本就未列入，见 §四第 4 条） |

### 四、对抗审核

1. **「超时值怎么定的」**——后端 300 分钟来自 2.5.1 基线 4h15m（255 分钟）加冗余，但该基线是**全量 1385 mutants**、
   3.8.0 行为未实测，故 300 是**估计值**；0a 首跑后必须重新标定，否则门禁会以「超时」掩盖「得分不足」两种不同故障。
2. **「为什么不直接给全局 job 默认超时」**——前端覆盖率、eslint、mypy 等步骤正常耗时以分钟计，
   统一设大值会掩盖真正的挂死；只给重任务设边界更精准。
3. **`continue-on-error` 与 BF-061 是否重复**——不重复：前者管**执行**（超时/失败后是否继续跑后续 job），
   后者管**判定**（是否阻止合并）。两者都要，缺一则出现「跑了但没人看」或「看了但跑不完」。
   *（本条成立的前提是 BF-061 的 gate 0b 已补判；0a 阶段 BF-061 未实施，故「判定」侧仍缺口——见 BF-061 §四第 4 条。）*
4. **【0a 落地后补记】**——方案只给重任务设超时，**其余 10 余个 job 仍无边界**。这不是遗漏而是取舍：
   这些 job 正常以分钟计，且各自会被 GitHub 默认 6 小时上限兜住（不设值 ≠ 无界），
   本期真正风险是「小时级重任务无界」而非「分钟级 job 挂死」。若要补齐，宜在**有了重任务超时的实测数据后**再定值，
   否则也同 300/90 一样是拍脑袋数字。登记为 0b 观察项，非本期缺陷。

### 五、验证记录

**登记时（只读取证，2026-09-29）**：

```text
① 全文核对：ci.yml 共 384 行；rg "timeout-minutes|continue-on-error" → 0 命中
② 耗时事实：docs/Review/mutation-baseline-2026-09-24.md → 后端 4h15m（1385 mutants）、前端 3m51s（7 store）
```

**0a 落地后（2026-09-29，YAML 解析 + 断言校验）**：

```text
① timeout-minutes 计数 0 → 3：backend-mutation 变异 step=300、判分 step=5、frontend-mutation step=90 ✅
② continue-on-error 计数 0 → 4：两个 mutation step + 其判分 step + frontend-complexity step ✅
③ 均确认为 step 级（0a 用户拍板的两处位置修正之一）✅
④ 位置修正核对：原方案写作 job 级位置（ci.yml:251/:363），实际落点为对应 step ✅
⑤ 其余 job 的 timeout-minutes：0 命中（按 §四第 4 条取舍，未列本期）
未执行：超时值实测标定 —— 待 CI 首跑（0b）
```

### 六、遗留与关联事项

1. 300 / 90 两个超时值为**初始估计**，0a 完成后须以实测重标（写入修复计划第 0b 批决策项）。
2. 若后端 3.8.0 首跑逼近 300 分钟，需考虑按 `source_paths` 分片，而非单纯上调超时。
3. **登记标题的定性偏重（0a 补记）**：原标题「失败无边界」不完全准确——未设 `timeout-minutes` 的 job
   仍受 GitHub 默认 6 小时上限约束，**不是无界**；真实问题应表述为「小时级重任务与分钟级任务共用同一
   6 小时上限，前者贴边、后者挂死不可区分」。P2 定级不变，但措辞已知有偏，避免后续据标题误判严重度。

*登记人：opencode ｜ 状态：0a 已落地超时/容错（2 重任务 + 判分 step），0b 待实测重标 + 评估是否补齐其余 job，2026-09-29*


## BF-064 【待修复】变异测试口径缺口：后端 65.63% / 前端 60.00，双双未达 80% 红线 2026-09-29

### 〇、元信息

- **登记日期**：2026-09-29
- **来源**：CI 门禁失效排查（方案见 `Bug待修复计划-20260929.md` §1-D①、§4）
- **关键程度**：P1（规则要求与实际能力之间的真实差距，此前被 BF-059/BF-060 的工具链缺陷掩盖）
- **影响范围**：`Rules_Fiels/backend-testing-rules.md` T7、`Rules_Fiels/frontend-testing-rules.md` T16、`docs/Review/mutation-baseline-20260924.md`
- **契约影响**：无
- **跨端契约**：未变更
- **当前阶段**：**本条是能力缺口而非配置缺陷，修复靠补测，不靠改配置**——0a 未改任何分数
- **状态补标（2026-09-29）**：**仍为【待修复】**。0a 只完成了本条的**前置条件**（方案第 1 项：修好工具链 BF-059/BF-060），但因本机 Windows 无法运行 mutmut 3.8.0、CI 首跑未发生，**「真实全量得分」尚未取得**。故第 1 项处于「工具链已修 / 数据未取」的中间态，第 2/3/4 项全部未动。**本条是整个 0a→0b 链路的终点，也是 0b 的核心内容。**
- **状态补标（2026-09-30）**：**真实全量分 70.44%（1959 mutants）已取得**（mutmut 3.8.0，16 核 WSL ~22 min，详见 BF-066），**< 80% 红线**；门禁口径决策转 B 批。本条维持【待修复】——分数到了，修复=补测或调阈值，尚未发生。
- **状态补标（2026-09-30 B批决策）**：**门禁口径定为「相对基线不回归」**——① 判分公式改为 mutmut 官方口径 `(killed+timeout)/(total-skipped)×100`（timeout 计入杀灭，与 BF-066 登记的 70.44% 一致）；② 基线存 `asset_management_backend/mutmut-baseline.json`（首基线 70.44）；③ CI 移除两处 `continue-on-error` 并将 `backend-mutation.result` 纳入 `ci-summary` 阻断；④ 80% 绝对红线暂挂沙盒期（根级 §5.4），补测抬分后人工更新基线直至恢复绝对红线。配套改动见 `backend-testing-rules.md` T7 v1.5。本条维持【待修复】——得分缺口由 C 批盲区补测抬分。

> **0a 对本条的实质贡献（但不足以关闭）**：① 门禁现在**会算分了**——判分公式
> `killed / (total - skipped) * 100` 且**有阈值断言**（< 80 即 exit 1），根因表第 1 行「门禁不产分数」已消解；
> ② 新增 `mutmut export-cicd-stats` 输出 JSON，为根因第 4 行「补测无驱动清单」提供了**稳定清单来源**。
> 但**分数本身一分未涨**，差距 −14.37 pt（后端）/ −20.00 pt（前端，且口径仅 7 store）维持原样。

### 一、问题现象

| 侧 | 规则红线 | 实测基线 | 差距 | 覆盖范围 |
|---|:---|:---|:---|:---|
| 后端 | 80%（T7，B批改为相对基线 70.44%） | **65.63%** | −14.37 pt | `apps/assetmanagement/services`，1385 mutants |
| 前端 | 80%（T16，`stryker.config.json:10` `break: 80`） | **60.00** | −20.00 pt | **仅 7 store**、120 mutants（全量为 31 store） |

两项均**未达标**。此前之所以无人处置：后端门禁空转（BF-059）、前端命令非法（BF-060），
「红灯」与「绿灯」都不携带得分信息，缺口被工具链故障整体掩盖。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 门禁不产分数 | 后端 `grep -c` 不做除法（BF-059）；前端从未跑出分数（BF-060）——**红绿都是噪音** |
| 2 | 工具链缺位 | 即使想补测也跑不起来，见 BF-059 / BF-060 |
| 3 | 覆盖不完整 | 前端基线仅 7 store，`mutate` 目标为 31 store，**基线不代表全量** |
| 4 | 补测无驱动清单 | 缺「哪些 survived mutants」的稳定清单来指导补测 |

### 三、修复方案（第 1 项已完成工具链半边，其余待 0b）

| # | 变更 | 文件 | 落地状态 |
|---|------|------|------|
| 1 | 先修工具链（BF-059 / BF-060），取得**真实全量**得分 | `ci.yml`、`dev.txt`、`setup.cfg`、`stryker.config.json` | ⏳ **工具链已修；真实全量分已于 2026-09-30 取得**（70.44%，1959 mutants，见 BF-066）；CI 变异首跑仍未触发 |
| 2 | 后端按 survived mutants 的行号补 Service 层失败/边界/回滚用例 | `apps/assetmanagement/tests/` | ⏳ 未动（**无 survived 行号清单，至今依赖 0a 的 `export-cicd-stats`**） |
| 3 | 前端四 CRUD store 优先补测 + 复核 `ignoreStatic` 口径 | `src/stores/__tests__/` | ⏳ 未动 |
| 4 | 0b 依真实数据决策：达标则移除 `continue-on-error`；未达标则依 §5.4 走沙盒期降级或下调红线并留痕 | `ci.yml`、`stryker.config.json:10` | ⏳ 待真实数据 |

> **第 1 项的可完成性判据（0a 落地后补正）**：原写「取得真实全量得分」是一个不可验证的笼统条件。
> 现在 0a 的判分已带 `THRESHOLD = 80.0` 与 `sys.exit(0 if score >= THRESHOLD else 1)`（`ci.yml:272`、`:293`）
> 且前端 `break: 80`（`stryker.config.json:10`），**判据已机器化**：
> - 后端：`CI job backend-mutation 通过 = 得分 ≥ 80%`（`export-cicd-stats` 产出 JSON，口径 `killed/(total-skipped)*100`）
> - 前端：`CI job frontend-mutation 通过 = score ≥ 80`（stryker `break`）
> 但**当前两个 job 都带 `continue-on-error: true`，红绿不传导到 `ci-summary`**（BF-061 §四第 4 条的拍板），
> 故 0a 阶段**不得**用「job 变绿」当作达标的信号，只可读它输出的分数文本。

### 四、对抗审核

1. **「能不能把红线降到 60 让门禁转绿」**——技术上可行，但**必须**同时满足两条件才可考虑：
   ① 分母是**全量**（前端 31 store、后端全 services），不是 7 store 聚焦口径；
   ② 依根级 §5.4 走 14 日沙盒期 + 人工复核。
   直接把 60.00 当新红线 = 用聚焦分冒充全量能力，是本条要根除的同类错误。
2. **「变异测试 80% 现实吗」**——可达但昂贵。本条只登记**差距事实**并给出补测路径，
   不预设达成时间；任何降级决策须由项目负责人拍板并留痕（§1.8 活账本义务）。
3. **「与 CT-2 覆盖率门槛是否重复」**——不重复。CT-2 管**行覆盖**（当前整体 93.11% / Store 97.72%，已达标），
   变异测试管**断言强度**（行被覆盖不等于能检出变异）。二者正交，本条不因覆盖率达标而降级。
4. **「为何现在登记而不等 0a 跑完」**——本条的「差距事实」来自已归档基线，可独立成立；
   0a 的作用是把「已归档的旧分」升级为「可复现的当前分」。二者不冲突。
5. **【0a 落地后补记·关于两个数字的口径差】**——表中后端 −14.37 pt 是**全量**口径（1385 mutants），
   前端 −20.00 pt 是**7 store 聚焦**口径。0b 拿到全量分之前，**这两个差距不可直接横向比较**，
   前端的全量差距很可能**大于** 20 pt（31 store 中大量未经补测）。0b 若做「先补哪边」的优先级决策，
   须以全量分为准，不得沿用本表的前端数字。

### 五、验证记录（只读取证，修复后需重跑）

```text
① 后端基线：docs/Review/mutation-baseline-20260924.md → 65.63%（909 killed / 476 survived，1385 mutants，4h15m）
② 前端基线：同上 → score 60.00（72 killed / 44 survived / 4 no-cov，7 store / 120 mutants，3m51s）
③ 红线出处：stryker.config.json:10 break 80；Rules_Fiels/backend-testing-rules.md T7 = 80%（ID 订正 2026-09-30：原误记 T8）
④ 覆盖范围对照：stryker.config.json:6 mutate = src/stores/**/*.ts；实测 src/stores 共 31 个 .ts → 基线仅覆盖 7 个
⑤ 覆盖率对照（说明正交性）：BF-045 遗留①记录整体 93.11% / Store 97.72%，已达 CT-2
未执行：全量 stryker run、任何补测 —— 均属第 0a / 0b 批执行阶段。
mutmut 3.8.0 全量已于 2026-09-30 跑出（70.44%（1959 mutants），见 BF-066）；前端全量 stryker 与任何补测仍未执行。
```

### 六、遗留与关联事项

1. 本条**必须**在 BF-059 / BF-060 之后处理，否则补测无法验证。
2. 4 个 no-cov mutants 提示存在零覆盖代码，补测时应优先于「提高分」处理。
3. 若最终选择下调红线，须在 `Rules_Fiels/Duplicate_Codes/complete-patterns.md` 留痕（§1.8 新发现义务），
   并按 §5.4 走沙盒期，不得直接改小数字了事。
4. **3.8.0 唯一现场值（n=1，不可外推）**：waste_asset_service.py 16 只 → 6 killed / 10 survived = **37.5%**（exit_code_by_key 直读 {1:6, 0:10}，见 BF-065 §五）。与 2.5.1 全仓 65.63% 口径不同、不可比；65.63% 已按 BF-065 §六第 2 条作废。**0b 阈值决策不得再引用 65.63% 作为「当前水平」**。

*登记人：opencode ｜ 状态：**待修复**（能力缺口，0a 仅完成「工具链已修」的前置半边；已取得 3.8.0 单文件参考值（37.5%，n=1 不可外推），全量分仍未取；0b 核心内容），2026-09-29*

---

## BF-065 【已关闭】mutmut 3.8.0 迁移陷阱——also_copy 缺 manage.py，致变异测试静默失真（分数无意义且不报错）2026-09-29

### 〇、元信息

- **登记日期**：2026-09-29
- **来源**：0b 首跑（WSL /tmp/mut38 全量 `mutmut run`）触发；修复方案经三轮计划评审定稿
- **关键程度**：P1（不报错、测试全过、分数完全无意义——静默失真是门禁类缺陷中最危险形态）
- **影响范围**：`asset_management_backend/setup.cfg`（[mutmut] also_copy）；关联 BF-059（其记录的「变异测试三重失效」中，also_copy 缺 manage.py 是第 4 重失效，在本条得到最终答案）
- **契约影响**：无
- **跨端契约**：未变更

### 一、发现

0b 首跑触发。**2.5.1 未复现**（当时确实产出 1385 只变异体）——差异原因已查明：2.5.1 为原地改写 + .bak 恢复机制，不依赖 also_copy 布局；3.x 改为 mutants/ 目录架构，测试对源码的解析完全取决于 also_copy 内容与 pytest-django 的路径发现，陷阱由此暴露。

### 二、现象

- `mutmut run` 16 秒 exit 1，报 `Stopping early, because we could not find any test case for any mutant`；
- 同期 pytest 侧 **955 个测试全部通过**（10 秒、exit 0）——测试执行的是外层原版代码，零变异命中；
- mutants/ 产物结构正常（13 个文件的变异体与 .meta 齐全，trampoline 结构完好）。

### 三、根因

pytest-django 4.12 `find_django_path` 的**绝对 cwd 分支**（plugin.py:203-219）从 cwd（= mutants/，绝对路径）逐级向上找含 manage.py 的目录，mutants/ 内无 manage.py → 命中**外层仓库根** → `sys.path.insert(0, /tmp/mut38)`（:224）→ early hook（`pytest_load_initial_conftests`）内 `django.setup()` 按 INSTALLED_APPS 导入 apps.*，此刻根 conftest（会插入 mutants/apps 路径）**尚未加载**，`sys.modules['apps']` 被钉死在外层原版代码——之后再改 sys.path 顺序也不再生效。
args 分支因 arg 为相对路径、parents 止于 `.`，不会逃逸——**修复点唯一**：also_copy 补 manage.py。

### 四、修复

`setup.cfg` [mutmut] also_copy 追加 `manage.py`（同时新增「易错点 5」注释，记录机制/时序/症状/旁证/验证命令）。
副作用两处已查证无害：① mutants/logs/ 由 FileHandler._open() 的 os.makedirs 自动创建；② 16 worker 并发写 RotatingFileHandler 属既有风险，非本条引入。

### 五、验证

```text
闸门：mutmut print-time-estimates（约 20 秒，不跑变异体）
判据（①自我循环，仅证明关联非空；有效判据为②③）：
  ① N_total=16 条，与单文件变异体总数同量级（16 条对 16 只，自我循环）
  ② N_none（<no tests> 行数）= 0
  ③ 两条 Stopping early 文案零出现，RC=0
单文件真实判定：waste_asset_service.py 全部 16 只变异体
  mutmut run <16 keys> → killed 6 / survived 10 = 37.5%
  （exit_code_by_key 直读 {1:6, 0:10}，按 status_by_exit_code 映射；此前的
  emoji 计数法混入了非本批 key，已废弃）
  ——真实分数首次产出，测试确证命中变异版代码。机制侧成立（N_none=0 +
  6 只被杀 = 静默失真确已消除）；分数侧反向（全仓最小文件 168 行仅 37.5%，
  远低于 2.5.1 全仓 65.63%——但两者算子集不同不可比，见 §六第 2 条）
```

### 六、遗留

1. **全量耗时与增量追踪（分环境）**：
   - **本地**：`mutants/*.meta` 即结果缓存，同工作树跨 run 保留，提供增量重跑——PR 内重跑只覆盖变更函数，预期缩短（待实测）。
   - **CI**：runner 工作区每次 job 后丢弃，`.meta` 不跨 run 保留 → 现状每次全量；若要 CI 增量需新增缓存步骤（待 0b 决策）。
   - 时长预算：预期显著超过 2.5.1 的 4h15m（16 核口径）；3.8.0 换 libcst 算子、变异体数量未知，CI 实际时长待首跑测量后再回填 `timeout-minutes`——**300 分钟预算未经验证，不作为已确认值引用**。
2. **基线作废声明**：65.63%（2.5.1 / 1385 只）已作废——3.8.0 换 libcst 算子，变异体集合不同，不可与 2.5.1 数字直接对比；0b 阈值决策只能基于 3.8.0 现场参考值。
3. **timeout 预算需重估**：`timeout-minutes: 300` 的「余量 45 分钟」论证源自 2.5.1 算子集（BF-059 记录的 4h15m/16 核）；3.8.0 变异体集合不同，余量未知，需首跑实测后重估。

*登记人：AtomCode ｜ 状态：**已关闭**（setup.cfg 修复 + 闸门判据通过 + 单文件真实分数 37.5%（n=1 不可外推）产出），2026-09-29*

---

## BF-066 【已关闭】mutmut 3.8.0 全量基线取得：70.44% 未达 80% 红线（附首跑死因定案 + 盲区清单）2026-09-30

### 〇、元信息

- **登记日期**：2026-09-30
- **来源**：0b 全量基线首跑（WSL `/tmp/mut38`，mutmut 3.8.0，16 核，~22 min）实证结果
- **关键程度**：P1（T7 规则红线 80% 与实际能力的真实差距，首次取得可复现的全量基线）
- **影响范围**：`Rules_Fiels/backend-testing-rules.md` T7；关联 BF-059（分片预案）、BF-064（口径决策）、BF-065（timeout 预算封板）
- **契约影响**：无
- **跨端契约**：未变更

### 一、首跑死因定案

| # | 观察 | 结论 |
|---|------|------|
| 1 | 首个后台 run 进程凭空消失，日志冻结于 08:46:07，`mutmut-timings.json` / `mutmut-cache.json` 均未落盘 | 非 OOM（当时约 7.1G 内存空闲），与集中分析强相关的信号为工具会话回收 |
| 2 | 以 `setsid nohup python -m mutmut run >/tmp/mut38_fullv2.log 2>&1 </dev/null &` 重启，脱离会话后全程存活并跑完 | **死因 = 工具会话回收**，坐实 |
| 3 | 首跑日志文件现不存在 | 与「会话回收」旁证一致；timings/cache 缺失属当时观察，登记保留原样，无需补证 |

### 二、全量基线数字（实证结果）

| 项 | 值 | 证据 |
|---|:---:|---|
| killed | 1267 | `.meta` 直读 `exit_code_by_key`：`{1:1267}` |
| survived | 561 | `.meta` 直读：`{0:561}` |
| timeout | 113 | `.meta` 直读：`{-24:113}` |
| no_tests | 18 | `.meta` 直读：`{33:18}` |
| total | 1959 | 1267+561+113+18=1959（自洽） |
| **score（官方口径）** | **70.44%** | `__main__.py:772` `(killed+timeout)/tested*100` = 1380/1959 |
| 严格 killed 口径 | 64.68% | 1267/1959 |
| 速率 / 耗时 | 1.30 mut/s / ~22 min | 16 核 WSL |
| 分片研判 | 无需分片 | 全量 ~22 min，BF-059 分片预案保持存档 |

### 三、BF-065 §六「timeout 预算需重估」封板

- 实测 **timeout 113/1959 = 5.8%**，全量 ~22 min 完成 → **非超时死因**；
- `timeout-minutes: 300` 对本地 16 核口径余量充足，但 **CI runner 核数不同，`timeout-minutes` 回填仍以 CI 变异首跑实测值为准**（BF-065 §六第 3 条闭环于此）。

### 四、盲区清单（C 批 CT-4 靶点）

| 类别 | 计数 | 明细 |
|---|:---:|---|
| 函数级盲区 | 1 | `RecycleAssetService.batch_create_recycle_asset`（`apps/assetmanagement/services/recycle_asset_service.py`） |
| 模块/类级盲区 | ~17 | `mutmut-stats.json` 78 被变异函数 vs 77 有测试映射，差额即函数级盲区；其余为模块/类级 mutant |
| 存活热区（CT-4 优先） | — | `asset_lifecycle_mixin`（batch_create_*/batch_delete_*）、`repair_asset_service`、`waste_asset_service.batch_delete_waste_assets`、`damaged_asset_service` |

### 五、对抗审核

1. **数字口径**：score 仅用官方公式（`__main__.py:772`），严格 killed 口径单列不混用；`export-cicd-stats`（`mutmut-cicd-stats.json`）与 `.meta` 直读（`{1:1267, 0:561, -24:113, 33:18}`）交叉一致。
2. **与 65.63% 不可比**：65.63% 系 2.5.1 算子集（1385 mutants，BF-065 §六第 2 条已作废）；3.8.0 换 libcst 算子，本条目为 3.8.0 官方口径全量基线，禁止与 2.5.1 数字做差。
3. **不构成门禁达标**：70.44% < T8 80% 红线，属能力缺口事实登记；门禁口径三选（维持 80% 分阶段补测 / 相对基线不回归 / [PENDING] 登记不阻断）挂 B 批 `[待确认]`。

### 六、验证记录

```text
① mutmut export-cicd-stats → mutmut-cicd-stats.json
   killed 1267 / survived 561 / timeout 113 / no_tests 18 / total 1959 / skipped 0 / suspicious 0 ✅
② .meta 直读 exit_code_by_key = {1:1267, 0:561, -24:113, 33:18}，求和 = 1959 ✅
③ 公式核对：__main__.py:772 (killed + timeout) / tested * 100 = 1380 / 1959 = 70.44% ✅
④ 交叉自洽：1267 + 561 + 113 + 18 = 1959 ✅；严格口径 1267 / 1959 = 64.68% ✅
⑤ 死因：首跑日志冻结 08:46:07 + timings/cache 未落盘 + 非 OOM；setsid 重启存活 ✅
```

### 七、遗留与关联事项

- **门禁口径三选**：挂 B 批 `[待确认]`（BF-064 转出）。
- **盲区补测**：挂 C 批（CT-3/CT-4 锚 + ~17 模块/类级 mutant 逐条枚举）。
- **前端 stryker 全量基线**：31 store 仍未跑，挂 D 批。

*登记人：big-pickle ｜ 状态：**已关闭**（基线数据事实登记，非修复），2026-09-30*

---

## BF-067 【待修复】master 存量 CI 三红：ci.yml 4 失败 job + 3 skip / ci-cd Docker Hub 登录 / security-scan npm audit 2026-09-30
> **当前状态（2026-10-01 更新）**：§一~§三-1~§三-4 与 **§三-6 已修复并经 CI 直证**（run 106 head `f753d75`，双 audit 归零）；**§三-6 后续「依赖审计接入合并/部署门禁」亦已落地并 CI 直证**（head `46ef870`，`Security 汇总` success + CD `安全门禁校验` success）。**仅剩 §三-5 ci-cd Docker Hub 登录凭据缺失**。详见下方第 12/13/14 条。

### 〇、元信息

- **登记日期**：2026-09-30
- **来源**：A 批（护栏批次）CI 核验——head `1a29991` 对应 runs：ci.yml `36654451114` / ci-cd.yml `36654451063` / security-scan.yml `36654451058`
- **关键程度**：P1（master 主分支持续红灯；但**与护栏批次无关**，属存量问题）
- **影响范围**：`ci.yml`、`ci-cd.yml`、`security-scan.yml`
- **契约影响**：无
- **跨端契约**：未变更

### 一、现象

**ci.yml（run `36654451114`，15 jobs）**：

| 类别 | job | 失败/跳过步骤 |
|---|---|:---|
| ✅ 成功 7 | 后端圈复杂度 C90 / 前端 ESLint / 前端复杂度 / 前端 TS / 后端 mypy / 后端 ruff（含护栏自测、BR-4、BR-6）/ B4 API 文档一致性护栏 | — |
| ❌ 失败 5 | M-6 权限码同步检查 | 步骤「权限码同步校验」失败 |
| ❌ | M-3 API Schema Diff (oasdiff) | 步骤「Generate schema」失败 |
| ❌ | M-3 配套 API 字段/枚举生成器同步核验 | 步骤「API 字段/枚举生成器同步核验（差异即失败）」失败 |
| ❌ | 前端 - 测试 + 覆盖率 | 步骤「整体覆盖率检查（红线 80%）」失败 |
| ❌ | CI 汇总 | 上游 job 失败传导 |
| ⏭️ 跳过 3 | 后端 - 变异测试 / 后端 - 测试 + 覆盖率 / 前端 - 变异测试 | 无步骤执行 |

**ci-cd.yml（run `36654451063`）**：Docker Build & Push → 「Login to Docker Hub」步骤失败（Docker Hub 凭据/环境）。
**security-scan.yml（run `36654451058`）**：npm audit → 「执行安全审计（高危阻断）」失败（存量依赖高危项）。

### 二、判定（与护栏批次无关的证据）

| # | 证据 | 结论 |
|---|------|------|
| 1 | jobs API 逐 job 核对：护栏批次新增/改动的 `scripts/`、docs、对 ci.yml 的单步改动（护栏自测 + BR-4 + BR-6）全部在「后端 - 代码规范 (ruff)」job 内成功 | 本批次改动自身门禁全绿 |
| 2 | 先前 head `1fa7cc5` 的 runs 列表：duplicate-guard success，ci.yml / CD / security 同为三红 | 存量即红，非本次引入 |
| 3 | 4 个失败 job（M-6 / M-3×2 / 前端覆盖率）执行的是仓库既有脚本与依赖，未触碰本批 `scripts/`+docs | 与本批改动无触点 |

### 三、修复方案（另立批次，[待确认] 归属）

| # | 项 | 候选动作 |
|---|------|------|
| 1 | M-6 权限码同步失败 | 定位「权限码同步校验」步骤失败根因（生成器/基线漂移）后修复 |
| 2 | M-3 oasdiff「Generate schema」失败 | 修复 schema 生成；通过后重导出 `api-schema-baseline.json`（存在漂移则提交） |
| 3 | M-3 配套生成器同步核验失败 | 对齐 API 字段/枚举生成器输出 |
| 4 | 前端整体覆盖率 < 80% | 补测至 80%（现有 Store 97.72% 属聚焦口径，整体口径缺口另计） |
| 5 | ci-cd Docker Hub 登录失败 | 核查 DOCKERHUB_TOKEN 凭据/过期 |
| 6 | npm audit 高危阻断 | 按 SC-7 治理存量高危依赖（升级/替换）后豁免 |

### 四、对抗审核

1. **未按「护栏批次失败」登记**：本批全部自增/自改门禁绿，红项均落在既有 CI 域，定性为存量。
2. **不因护栏绿灯稀释三红**：即使 duplicate-guard 与「护栏自测」绿，master 上 ci.yml/C D/security 三个 workflow 持续 fail 依旧成立，须单独立项修复。
3. **skip 的 3 个变异/测试 job**：与 B 批（变异 CI 接入）衔接——当前 CI 未产出变异分数，B 批接管后需点亮 backend-mutation 并移除 `continue-on-error`（BF-064 转出项）。

### 五、验证记录

```text
① jobs API（run 36654451114）逐 job 核对：成功 7 / 失败 5 / 跳过 3，与上文一致 ✅
② runs 列表对照 head 1fa7cc5：duplicate-guard success / ci、CD、security failure ✅
③ 本批护栏相关门禁：护栏自测 / BR-4 / BR-6 / ruff / mypy / ESLint / TS / C90 / B4 全绿 ✅
```

### 六、遗留与关联事项

- 修复方案另立批次（本条目只登记现象 + 判定证据）；§三候选动作供批次立项引用。
- 与 BF-064、BF-066 衔接：CI 变异 job 当前 skip，B 批接入后以 70.44% 为基线做口径决策。

### 七、修复记录（2026-09-30 修复批，父仓 `785c612`）

**1. M-6 权限码同步检查（①，backend 子仓提交）**

- **根因（实证）**：`asset_management_backend/.gitignore:134` 的 `constants/` 为一整目录排除，`constants/permission_constants.py` 因此**从未入库**（`git rev-list --all -- <path>` 空输出；`git ls-files` 0 命中）。CI 干净检出缺文件 → `check_be` 的 `be_path.exists()` 为假 → 步骤秒败 exit 1。本地过是因工作树存有该未跟踪文件。**与子模块指针无关**（GitLink 核实 `9850a34`→backend `0093467` 与 origin/master 一致）。
- **gitignore 机制教训**：父目录被排除后 git 不干扰下探，`!constants/permission_constants.py` 否定例外对**整目录排除**不生效（git 文档原话 "It is not possible to re-include a file if a parent directory of that file is excluded"）。**正确写法**：`constants/` 改 `constants/*`（排除内容而非目录本身）+ `!constants/permission_constants.py`。
- **修复**：backend `.gitignore:134` 按上改两行；`git add constants/permission_constants.py` 验证白名单生效（此前 `git add` 静默丢弃）；提交子仓 `d9acb34`（入库）+ `49a8bc7`（gitignore），push backend→`49a8bc7`；父仓 gitlink 更新。
- **回归**：backend 子仓 `python scripts/generate_permission_codes.py --check` → `[M-6] PASS (FE/BE in sync)`。

**2. M-3 配套 API 字段/枚举生成器同步核验（②，父仓 ci.yml）**

- **根因（实证）**：ci.yml `api-doc-generate` job **无任何 pip install**，而生成器经 `scripts/api_field_reference/codesource.py:_setup_django()` 执行 `import django` + `django.setup()`——CI 全新 runner 无 Django → `SourceError("无法导入 Django")` → exit 2（主流程 `generate_api_field_reference.py:200` 捕获 SourceError 返回 2）。原注释「仅依赖标准库」不实（生成器读模型 choices）。
- **修复**：该 job 补 `pip install -r asset_management_backend/requirements/base.txt`；注释订正为「依赖 Django 读取模型 choices」。
- **回归**：本地带 Django 环境跑 `python scripts/generate_api_field_reference.py --check` → 输出「文档与真值一致，无需同步」，RC=0（受限于本地已装依赖，CI 全量待重跑验证）。

**3. M-3 oasdiff 「Generate schema」失败（③，挂起）**

- **最新进展**：失败发生在 **Generate schema** 步骤（`manage.py spectacular ... --validate`），oasdiff diff 步骤从未执行——排除「基线漂移」假设。本地以 CI 相同 env（`DJANGO_SETTINGS_MODULE=config.settings.production` + SECRET_KEY/ALLOWED_HOSTS/DB_PASSWORD/REDIS_URL dummy）+ `PYTHONIOENCODING=utf-8` 复现 `spectacular --validate` **RC=0**（生成+校验通过）；`--validate` 仅依赖 `jsonschema`（drf-spectacular 硬依赖，已在 dev.txt 传递安装）。**真实报错文本锁在需登录的 CI 日志**，待提供后分段定位（settings 加载 / 依赖解析 / 生成崩溃）。
- **待办**：用户提供 Generate schema step 原始日志 → 定修法；通过后重导出基线检查漂移。

**4. 前端测试 + 覆盖率（④，frontend 子仓提交）**

- **根因（实证）**：非 `--coverage.threshold` CLI 旗标问题（与 BF-060 同族嫌疑已排除）——annotation 确认失败为**断言** `outAssetFormEditLoader.spec.ts:116`：expected `'2025-01-02'` got `'2025-01-01'`。mock 数据 `outasset_date: '2025-01-02T00:00:00+08:00'`，`src/utils/Format.ts:formatDate` 用 `new Date()` + 本地时区 `getFullYear/getMonth/getDate` → GitHub runner(UTC) 将 +08 午夜折回前一天。本地 +08 时区过、CI UTC 挂，属**时区依赖测试**。
- **修复**：`vue-assetmanagement/vitest.config.ts` 首行注入 `process.env.TZ = 'Asia/Shanghai'`（config 加载期、worker 派生前生效），CI/本地确定性对齐，业务侧以 +08 为唯一口径；不改生产逻辑。
- **回归**：① 正常跑 + ② **强制 `$env:TZ=UTC` 模拟 runner**，目标 spec 均 5 passed；三分支项 `type-check` / `lint` / `format:check` 全绿。提子仓 `c9a2959`，push frontend→`c9a2959`；父仓 gitlink 更新。

**5. 汇总状态**

- ci.yml 4 失败项中 3 项已出修复提交（M-6 / M-3 配套 / 前端 TZ），M-3 schema 留 ③ 待日志；
- ci-cd Docker Hub 登录（⑤/§三-5）与 security-scan npm audit（⑥/§三-6）属**独立 workflow 存量项**，本批未触及，仍待立项。

**6. CI 复跑核验（run 91，head `62933f3`，父仓）**

- **回落核验**：M-6 权限码同步 **SUCCESS** ✅（① 修复被 CI 证实）；前端 4 job（测试+覆盖率 / TS / ESLint / 变异）**全绿** ✅（④ TZ 注入在 Ubuntu UTC runner 下通过，非本地时区侥幸）。
- **新失败**：**backend-lint（ruff）FAIL** —— annotation 仅「exit code 1」，本地复现为 ruff 0.15.20 `I001`（Import block 未排序/未格式化）+ `ruff format`（docstring 后缺空行）双拦 `constants/permission_constants.py`：生成器 `BE_HEADER` 模板仅 1 空行接顶层定义，且 docstring 与 `from __future__ import annotations` 直接相连。
- **其余 skip 定性**：M-3 oasdiff / B4 护栏 / M-3 配套 / backend-test / backend-mutation 全部 `needs: [backend-lint]`，系 ruff 失败级联，**非 M-3 修复无效**。
- **修复（回归护栏）**：改生成器 `scripts/generate_permission_codes.py:BE_HEADER` 模板（docstring 后补 1 空行 + import 后补 2 空行），**重新生成**产物而非手改 `permission_constants.py`（保持「勿手动编辑」约束与 MF 单一真值）；M-3 配套的 base.txt 修复提示——该 job 在 run 91 被 skip，**其修复仍未在 CI 全量验证**。
- **回归**：`ruff check .` All checks passed / `ruff format --check .` 336 files already formatted / `generate_permission_codes.py --check` → FE/BE in sync 全 PASS。
- **提交**：backend 子仓 `16687a4`（生成器模板 + 再生成产物）已 push（`49a8bc7..16687a4`），父仓 gitlink 同步中。
- **延续修复（backend `72abefe`，run 91 复跑时发现生成器自身两处格式债）**：① `FE_FOOTER` 带分号 `} as const;`——仓库 prettier `.prettierrc.json semi:false`，生成产物 vs 落库文件（已删分号版）非单源，补齐为 `} as const`；② `Path.write_text` 未指定 `newline`，Windows 下默认输出 CRLF，与仓库 LF 归一冲突导致再生成即脏树——两处写出均显式 `newline="\n"`。修后重新生成：FE 子仓清零、BE `permission_constants.py` EOL 归一后索引无变更，`ruff check/format` 与 M-6 --check 全绿。已 push `16687a4..72abefe`。

**7. CI 复跑核验 2（run 92，head 45babe3，父仓）——M-3 配套首跑暴露 baseline 缺失**

- **回落核验**：backend-lint（ruff）**SUCCESS** ✅（`16687a4` 模板修复生效）；M-6 ✅、B4 ✅、前端 4 job 全绿 ✅。riff/生成器相关全部转绿。
- **剩余两红**：① **M-3 配套 --check exit 2**（pip install base.txt 步骤已 SUCCESS，② 的「缺 Django」根因确已解决，失败后移到更深的 `django.setup()`）；② **M-3 oasdiff Generate schema exit 1**（③ 老问题未变，仍待 CI 日志）。
- **M-3 配套根因（结构性证据，非日志取证）**：`config/settings/base.py:82` 按 P1-38 **无条件**加载 `django_extensions`，而 base.txt 未含该包 → CI 仪装 base.txt 时 Django app registry 装载 `django_extensions` 抛 ImportError → `codesource._setup_django()` 的 `django.setup()` 失败 → `SourceError` → exit 2。本地全栈（dev.txt 含 django-extensions 3.2.3）RC=0 佐证。**连带发现**：base.txt 缺此包等于「仅装 base.txt 无法启动任一 settings（dev/prod/test 均继承 base.py）」——潜在生产部署缺陷。
- **修复（backend `7bc44af`）**：`django-extensions==3.2.3` 的 pin 从 dev.txt **上移对齐**至 base.txt（附 P1-38 + BF-067 注释）；dev.txt 删重（经 `-r base.txt` 继承，保 DR-1 单源）。CI 重跑后 M-3 配套应首绿；若仍有后续缺失依赖将以同样方式暴露。
- **③ M-3 oasdiff Generate schema**：仍未定位，阻塞于登录日志——**待用户提供该步骤原始日志**（settings 加载 / 依赖解析 / 生成崩溃三段定位）。

**8. CI 复跑核验 3（run 94，head efa7efa，父仓）——2 保留红只乘 M-3 schema**

- **M-3 配套首绿 ✅**：`--check` exit 2 根因（base.txt 缺 django_extensions）修复后首次通过；**backend-lint(ruff) / mypy / C90 / M-6 / B4 / 前端 4 job 全绿**。
- 仅剩 `M-3 - API Schema Diff (oasdiff)` **Generate schema** 步骤失败（exit 1，③ 未变）；backend-test/mutation 因 `needs: [api-schema-check]` 继续级联 skip。
- **下一步**：等待用户提供 Generate schema 原始日志 → 分段定位。

**9. CI 复跑核验 4（run 96，head 4a742af，父仓）——根因确诊：python-dateutil 未声明**

- 用户提供 Generate schema 日志，traceback 精确定位：`out_asset_selector.py:11 from dateutil.relativedelta import relativedelta` → `ModuleNotFoundError: No module named 'dateutil'`。
- 只读取证：生产代码 2 处 dateutil（`out_asset_selector.py:11` 模块级 = 炸点、`dashboard_selector.py:294` 函数级）；base.txt/dev.txt 均未声明。AST 全应用扫描确认 **生产代码无其他未声明第三方依赖**。`types-python-dateutil` 曾误加入 dev.txt 且验证为多余（后端 AGENTS v9.3.0 已在案），本修复不需要 stub。
- run 96 逐 job 结论：**唯一失败 = M-3 oasdiff**；mypy/ruff/C90/M-6/B4/M-3配套/前端 ESLint/前端 complexity/前端 TS/前端测试/前端变异 全绿；后端测试/后端变异 仍级联 skip；CI 汇总红纯由后端测试 skipped 触发。ESLint complexity 10 处高复杂度均为存量告警（该 job success，非阻断），前端变异 step 退出码 1 被 continue-on-error 掩盖（D 批 stryker 基线未取前既有状态）。
- 修复：base.txt 追加 `python-dateutil==2.9.0.post0`（生产依赖，注释溯源加注 BF-067）。后端 commit `2d9eeef` 已 push。
- **预期**：M-3 首绿 → 后端测试/变异首次真正执行 → 若暴露新失败再定位。

**10. CI 复跑核验 5~7 + 后端测试/变异收口（run 97/98/99，父仓）——变异基线环境切换 + M-3 漂移 warning 判空缺陷**

- **run 97（head `f3d06b6`）**：M-3 oasdiff **首绿**（dateutil 修复生效）；新暴露 **postgres:16 容器启动失败**（"Failed to initialize container postgres:16"），级联 backend-test / backend-mutation 仍 skip。
- **run 97 根因（纯结构取证，无猜测）**：backend-test/backend-mutation/migration-check 三 job 的 postgres 服务 `POSTGRES_PASSWORD` 与 job env `DB_PASSWORD` 均用 `${{ secrets.DB_PASSWORD }}`。该组合**从未真正执行过**（backend-test 一直级联 skip、migration-check 无历史 run），secret 缺失即展开为空字符串 → postgres 官方镜像拒空 superuser 密码 → 容器秒退。M-3 schema job 用内联 `ci-dummy-not-real` 且无 postgres 服务 → 成功，此为对照。
- **修复（父仓 `943dcd9`，push `f3d06b6..943dcd9`）**：ci.yml 两 job + migration-check.yml 统一改内联 `ci-dummy-not-real`，与 M-3 schema job 同口径；非生产凭据，仅供 CI 一次性容器，SC-1 合规（secret 不落仓）。**未新建仓内 secret**（PR/分支环境拿不到仓级 secret，参见 GitHub 官方说明）。
- **run 98（head `943dcd9`）**：**后端测试+覆盖率 首跑首绿**（容器修复生效）；M-3 oasdiff / M-3配套 / B4 / mypy / ruff / C90 / M-6 / 前端 4 job 全绿。唯一红 = **后端变异 step 7「变异得分门禁」exit 1**。
- **run 98 变异失败根因（用户提供 step 7 stdout 一锤定音）**：`变异得分 68.61%（基线 70.44%，-1.83pt）（killed=1344 survived=597 timeout=0 no_tests=18 tested=1959）`。**tested=1959 全量无截断**，排除"CI 未跑完/半成品"假说。差异**全部**来自 timeout 归类：WSL 基线 113 个变异体因跨 `/mnt/d` 慢 I/O 触发超时被判 killed（+113 加分），CI 原生磁盘下这些变异体正常结束 → timeout=0。**CI pure-kill 68.61% 反高于 WSL pure-kill 64.68%**，且 `apps/assetmanagement/services`、tests、setup.cfg 自 `0093467`（基线 commit）起**零变更** → 判定为**基线取环境与门禁执行环境不一致的假性回归，非代码回归**。
- **修复（后端 `b0aec84`，已 push `2d9eeef..b0aec84`）**：`mutmut-baseline.json` 切至 CI 执行环境实测值 —— `score 68.61 / killed 1344 / timeout 0 / survived 597 / no_tests 18 / mutants 1959`，`environment` 注明 CI ubuntu-latest，补齐 `survived`/`no_tests` 字段使基线与门禁输出口径完全对齐，`note` 记录完整根因链与"基线环境须与门禁执行环境同源"教训。门禁「相对基线不回归」此后与执行环境自洽。
- **M-3 非破坏性漂移核实（并入本次，结论：零漂移，warning 系护栏自身缺陷）**：按根级 §3 要求在 CT-7 一致工具链下重导出（WSL 原生 venv `~/be-venv` + dev.txt 全文，Django 6.0.5 / drf-spectacular 0.29.0 / Python 3.12.3），exit 0、23 warnings/6 unique errors 与 CI 同款（属 schema 内容级提示，不阻塞）。生成结果与仓库现有 baseline **字节级一致**（`git hash-object` = `0c5193f8`，1006041 字节）→ **baseline 无需重导出**。再以 oasdiff 1.29.1 比对 baseline vs CI 同口径 current（`--format openapi`）：`breaking: No changes detected` / `summary: diff: false` / `diff: {}` → **确认零漂移**，run 98 的 warning 是**假阳性**。
- **假阳性根因（护栏判空缺陷）**：ci.yml 原判据 `if ! oasdiff diff ... || [ -s /tmp/drift.txt ]` —— oasdiff diff 无差异时输出 `{}`（单行非空），`[ -s ]` 恒为真 → **只要 diff 命令正常执行就必然报漂移**。
- **修复（父仓 ci.yml，BF-067）**：判据改用 `oasdiff summary ... | grep -qx "diff: false"`。已实测区分能力：零漂移→NO_DRIFT，注入伪端点 → DRIFT。warning 分支仍回显 `oasdiff diff` 详情与重导出命令，护栏意图不变、误报消除。
- **提交**：后端 `b0aec84`（mutmut-baseline.json 单文件；api-schema-baseline.json 无变化故不入提交）；父仓 `943dcd9` 之后的本次提交含 ci.yml 判据修复 + gitlink 同步。

**11. run 99 双验证 + 基线取值浮点陷阱（后端 `95f9458`）——68.61% 对 68.61% 却 exit 1**

- **run 99（head `ece7d9d`）逐 job 结论**：13/14 job 全绿，含此前唯一红的 **后端测试+覆盖率**（首跑即 success）与 **M-3 oasdiff**（漂移 warning 消除，验证 §十 ci.yml 判据修复生效）。前端变异/前端测试/mypy/ruff/C90/M-6/B4/M-3配套/前端 TS/前端 ESLint/前端 complexity 全绿。
- **仍红 = 后端变异**：step 6 `mutmut run` success（4分36秒 / 276s），step 7 门禁 1 秒 exit 1。
- **根因（用户提供 step 7 stdout + 本地精确复算）**：输出 `变异得分 68.61%（基线 68.61%，-0.00pt）` 却 exit 1 —— 显示相同、实际不等。真值 `(1344+0)/(1959-0)*100 = 68.60643185298622`，而 §十 写入基线的 `68.61` 是**四舍五入值**，故 `score >= baseline` 为 False（差 -0.003568pt）。**这是基线取值的精度 bug：门禁精确比较，基线却存四舍五入显示值，必然恒红**。
- **复现验证**：run 98 与 run 99 两轮 CI 的 stats 逐字段完全一致（killed=1344 survived=597 timeout=0 no_tests=18 suspicious=0 tested=1959），**CI 变异结果可稳定复现**，证明 §十 环境归因（timeout 归类差异）成立且已收敛，非随机噪声。
- **修复（后端 `95f9458`）**：`mutmut-baseline.json` 的 `score` 改为**实测精确值向下取整 4 位小数 = 68.6064**（严格 ≤ 真值，门禁必过），`environment` 补「run 98/99 复现一致」，`note` 增补**取值规则**：存实测精确值向下取整、**禁用四舍五入值**（含本次事故记述）。
- **修复（父仓 ci.yml）**：门禁 print 精度 `:.2f` → `:.4f`（score/baseline/delta 三处），避免 `:2f` 把 68.60643 与 68.6064 同渲染为 68.61 造成「显示相同却 exit 1」的误导现场再次出现。
- **WSL 复现实验（已放弃，非必需）**：曾在 WSL 原生 venv（dev.txt 一致、16 核）起全量 mutmut 交叉验证，取得 run 98/99 双次一致数据后判定实验目的已达成，pkill 终止并清理 mutants 目录。结论：环境复现不再是瓶颈，CI 双轮直接证据优先。
- **教训**：门禁阈值类常量（score 基线、覆盖率阈值）**一律存精确值、禁用展示用四舍五入值**；展示精度可读性 ≠ 存储精度正确性，二者必须分离。

**12. run 100 checkout 失败（非代码，gitlink 未推送）→ run 101 全绿收口**

- **run 100（head `d0528f6`）全 job 秒败（8 秒内级联失败）**：`backend-lint` 系（ruff/mypy/C90/M-6）与前端 lint 系全 failure、其余 skipped。**根因 annotation 明示**：`remote error: upload-pack: not our ref 95f94581bff...` —— **后端子模块 commit `95f9458` 只在本地未 push**，父仓 gitlink 指向不可达 commit，`actions/checkout@v4` 直接失败并级联。与本轮代码/门禁改动无关。
- **修复**：补推后端 `b0aec84..95f9458`（gitlink 现可达）；父仓空提交 `0d50ee9` 重触发。
- **教训（流程级）**：父仓改 gitlink 前**必须**先确认子模块 commit 已推到远端；子模块 commit 缺失属可预见的 checkout 级联失败，判据是「秒败 + not our ref」annotation，与真实代码失败（步数多、耗时正常）形态完全不同。
- **run 101（head `0d50ee9`）终验证：15/15 job 全绿 ✅**（CI 汇总 job 亦 success）：
  - **后端变异测试**：step 6 `mutmut run` **success**（4分04秒）+ step 7「变异得分门禁」**success**（基线 `68.6064` 生效，此前唯一红点消解）。
  - **后端测试+覆盖率** success；**M-3 oasdiff** success（无漂移 warning，§十 判据修复持续生效）；**B4 / M-3配套 / mypy / ruff / C90 / M-6** 全 success；**前端 4 job**（测试+覆盖率 / 变异 / TypeScript / ESLint / complexity）全 success。
- **BF-067 主修复批收口达成**：run 91→101 累计修复并经 CI 直证的根因 —— ① `base.txt` 缺 `django-extensions`（M-3 配套 exit 2）；② `base.txt` 缺 `python-dateutil`（M-3 schema 崩）；③ CI 凭据用 `secrets.DB_PASSWORD` 致 postgres 容器从未真跑过；④ 变异基线取环境与门禁执行环境不一致（WSL timeout 伪象）；⑤ M-3 漂移 warning 判空缺陷恒假阳性；⑥ 基线存四舍五入值致门禁恒红（浮点）；⑦ 子模块 commit 未推送致 checkout 级联失败。**另立未做**：ci-cd Docker Hub 登录（§三-5）、security-scan npm audit/pip-audit（§三-6）。下一步可进入 **C 批（补测抬分 → 恢复 80% 绝对红线）** 与 **D 批（前端 stryker 基线）**。

**13. §三-6 依赖安全批：axios 1.20.0 + PyJWT 2.15.1，run 102→106 双 audit 归零**

- **§三-6 现象（run 102 / `36743014025`）**：`security-scan` 的 `Python 依赖安全审计` 与 `Node.js 依赖安全审计` 双红。同一批触发的 `ci.yml` run 104 / `36743014190` 中，mypy / M-3 oasdiff / M-3 配套三个 job 均在 **`pip install` 阶段**硬失败（`Process completed with exit code 1`），后续测试与变异 job 被 skipped。
- **第一次根因（自造事故）**：误钉 `Django==6.0.9`。`docs.djangoproject.com` 的 6.0 发布索引页列有 6.0.9，但 **PyPI 无此发行版**（`https://pypi.org/pypi/Django/6.0.9/json` 返回 404）→ 四个 job 安装步骤全红。**查版本存在性一律以 PyPI JSON API 为准，勿以文档索引页为据**。修正为 `Django==6.0.8`（PyPI 上 6.0.x 最高补丁），后端 `a9d639d`、父仓 `9360661`。
- **run 103（head `9360661`）实测结论**：**多数门禁直接转绿** —— mypy ✅（证明 runtime 3.16→3.17.2 + stubs 3.18.0 + django-stubs 6.1.0 组合在真实工具链下 0 error，无需降 stubs）、M-3 oasdiff ✅（**drf-spectacular 0.29.0 与 DRF 3.17.2 共存，零破坏性漂移，0.29 刻意不升的决策成立**）、M-3 配套 ✅、ruff / C90 / M-6 / B4 / BR-4 / FR-6 / 重复代码护栏 / 密钥扫描 / 前端四项 全绿。**但两侧 audit 仍双红**，且前端 node-audit 从 run 102 的绿转红。
- **npm 侧根因**：`npm audit --audit-level=high` 本地复现输出 `1 high severity vulnerability` —— **axios 1.19.0 命中 7 条高危 advisory**（GHSA-vh66-26gq-q6x8 / 9fr6-4gfg-395g / c29m-xwm3-cm6r / mghh-pgcx-3jjj / x97p-jq2g-jp4f / 3pq3-5fj3-cg6v / 542g-h47m-68v8：原型链污染 gadget、ReDoS、HTTP/2 adapter 绕过 DNS/proxy 控制等），影响范围 `1.0.0 - 1.19.0`，修复线 **1.20.0**。**先绿后红属 npm advisory DB 时序**（同一 lockfile 在 run 102 通过，run 103 才红），**非回归** —— 判定须以「重跑 audit」为准。修复：`package.json` `^1.11.0`→`^1.20.0`，`npm install axios@^1.20.0 --package-lock-only` 更新 lockfile（1.19.0→1.20.0，diff 仅 4 行、未波及其他包）。本地 `npm audit --audit-level=high` → **`found 0 vulnerabilities`，exit 0**。
- **Python 侧根因**：`PyJWT==2.14.0` 为「当时最新」但**非修复线终点**，仍报高危（GHSA-ffc3-869f-jxw9 crit 等）。**教训：latest ≠ 修复线终点**。先在 PyPI 核实 `2.15.0`/`2.15.1` 均存在（latest = 2.15.1），取 **`PyJWT==2.15.1`**。
- **本地 audit 归零验证（CT-7 工具链）**：新建独立 venv 装 `pip-audit 2.10.1`（走清华镜像 `--index-url https://pypi.tuna.tsinghua.edu.cn/simple`）。注意两个本地环境坑（**CI 为 ubuntu/UTF-8 不受影响，勿据此改 CI**）：① Windows 下 `pip_requirements_parser` 按 GBK 解码 UTF-8 requirements 文件抛 `UnicodeDecodeError`，须设 `PYTHONUTF8=1`；② `pip-audit` 2.x 的索引参数是 `--index-url` 长选项，`-i` 会被当作 `project_path` 与 `-r` 冲突报错。结果：`base.txt` 与 `dev.txt` 均 **`No known vulnerabilities found`，exit 0**。
- **一次方法论纠错**：中途用 `https://api.osv.dev/v1/query` 逐包查询，**该端点未对 version 做有效过滤** —— 给 `Django==6.0.8` 返回了 PYSEC-2007-1 等 2007 年漏洞，输出整体不可信，**已按 Fact-1 全部丢弃**，改用 pip-audit 权威结果。
- **提交**：前端 `fce16a0`（axios 1.20.0）；后端 `03c1c7f`（PyJWT 2.15.1）；父仓 `f753d75`（同步两个 gitlink）。文档同步另计：`CheckReport.md`（Django 6.0.5→6.0.8、DRF 3.16.0→3.17.2、drf-spectacular 0.28.0→0.29.0）、`docs/README.md`、`GuideDocumentation/后端API.md` 三处版本注记一并校正。
- **run 106（head `f753d75`）终验证：22/23 job 全绿 ✅**（CI 汇总 job 亦 success）—— **`Python 依赖安全审计 (pip-audit)` success**、**`Node.js 依赖安全审计 (npm audit)` success**、密钥泄露扫描 success、每周安全报告 skipped（仅 push to default 触发）；后端测试+覆盖率 / 变异测试 / ruff / mypy / C90 / M-6、M-3 oasdiff / M-3 配套、B4、前端测试+覆盖率 / 变异 / ESLint / complexity / TypeScript、重复代码回归护栏 全 success。**§三-6 完成**。
- **唯一红项不在本批**：`Docker Build & Push`（ci-cd.yml）—— 登录 Docker Hub 失败，属 **§三-5 凭据缺失**，需 `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN` secret，与 §三-6 无关。
- **三重依赖声明同时通过实测**（`djangorestframework-stubs==3.18.0` 相对 runtime 3.17.2 刻意错配、drf-spectacular 0.29.0 刻意不升、Django 6.0.8 为 6.0.x 上限），后续升版前须重跑 mypy + M-3 + B4 三项。

**14. §三-6 后续：依赖安全扫描接入合并/部署门禁（head `46ef870`）**

- **立项依据**：第 13 条把 audit 从红转绿即收口，但 SC-7 文义要求「阻断合并」，而实际链路里 audit 与 CD 各自独立触发 —— 审计红着也能照常构建推送镜像，门禁形同虚设。本条把结论前移到部署链路并收敛为单一 check。
- **落地方案（两层，因仓库历史 0 PR 直推 master，GitHub required checks 空转）**：① `security-scan.yml` 新增 `Security 汇总` job（与 `ci.yml` 的 `CI 汇总` 同构）；② `ci-cd.yml` 改由 `workflow_run` 监听并新增 `security-gate` job 前置。**分支保护（required checks + 强制 PR）列为独立后续项**，需管理员 token 且待团队改用 PR 流程。
- **audit 降噪与 job 级 if 的硬约束**：audit 是重活而 advisory DB 持续新增（axios run 102 绿 / run 103 因 DB 新增转红，同一 lockfile 零代码变更），若直接全量门禁，任何新 advisory 都会把所有在开 PR 一起变红。故改为「依赖文件变更才审计 + schedule 每周全量兜底（SC-8）+ `workflow_dispatch` 手动重扫」。**必须用 job 级 `if:` 而非触发级 `paths:`** —— 后者会让 workflow 整体不运行、check 永不出现，日后列入 required checks 将使 PR 永久挂起（GitHub 不把「未上报」当通过）。
- **实施中发现并修掉的两个真实缺陷（均非本次引入，但本次新代码会放大）**：
  - **fail-open**：`git diff --name-only BASE SHA | grep -qE` 的管道写法下，若 `git diff` 自身报错（force-push 致 base sha 不可达 / 浅克隆未取到该 commit），`pipefail` 使管道失败 → 落入 else → `deps-changed=false` → **审计被静默跳过而汇总照报 success**。改为把 git 退出码与 grep 匹配结果分开，git 失败即按全量审计处理。
  - **shell 注入**：`security-gate` 原将 `${{ github.event.workflow_run.head_branch }}` 直插 `run:`。`head_branch` 可被 fork PR 的分支名影响，而 git ref 仅禁止 ``空格 ~ ^ : ? * [ \`` 与控制字符 —— **双引号 / 分号 / 管道 / 美元 / 反引号全部合法**，会被 bash 在解析整行时先执行（`||` 只短路求值、不短路解析），而 `workflow_run` 触发的 workflow 默认可访问 secrets，构成 pwn-request 面。改为门禁值一律经 `env:` 传入后以 `$VAR` 引用（值不被二次解析），并显式收窄 `permissions: contents: read`。
- **`workflow_run` 的 SHA 语义（实施前实测官方事件表确认）**：该事件下 `GITHUB_SHA` 是「**默认分支的最新提交**」而非被触发 run 的 head sha。若只校验 `conclusion` 不校验提交一致性，`docker` job 的 `actions/checkout`（默认检 `github.sha`）会检出 master tip —— 两次推送间隔时**构建到未经审计的新提交**。故 gate 强制四项：`event=push`、`head_branch=master`、`conclusion=success`、`head_sha == GITHUB_SHA`（该相等同时保证了 checkout 与 `tags:` 里的 `github.sha` 都指向被审计的 commit）。另按官方载明，`workflow_run` 无论前序结论如何都会触发，故不能靠 job 级 `if` 让 docker 静默 skipped，必须自己判失败。
- **移除 `workflow_dispatch` 的代价（已知并接受）**：该触发下 `github.event.workflow_run` 上下文为空，gate 必然失败，留着只会制造永久红的误导入口。代价是 §三-5 凭据就绪后无法手动重跑部署，只能推空提交触发。
- **CI 直证（head `46ef870`，commit 仅两个 workflow 文件）**：
  - `Dependency Security Scan` run **`37005012168` = success**，job 级：依赖变更探测 success（`security-scan.yml` 自身在触发清单内 → 走审计路径，自证）、`Python 依赖安全审计 (pip-audit)` success、`Node.js 依赖安全审计 (npm audit)` success、密钥泄露扫描 success、每周安全报告 skipped（push 下预期）、**`Security 汇总` success** ← 新门禁生效。
  - `CI Pipeline` run **`37005012100` = success**，15/15 job 全绿、0 failure（耗时 43m15s；后端测试+覆盖率 20m47s、后端变异测试、前端变异测试、`CI 汇总` 均 success）。
  - `Duplicate Code Regression Guard` run **`37005012215` = success**。
  - `CD Pipeline` run **`37005117969` = failure**，job 级：**`安全门禁校验` success** ← 四项校验全过；`Docker Build & Push` failure，**step 级定位为 step 4 `Login to Docker Hub`**（step 2 `actions/checkout` success，佐证 checkout 落在被审计 commit 上），即 **§三-5 凭据缺失，与本条无关**；`Prune Old Images` skipped（`needs: [docker]` 正确跳过）。
- **本地校验与其边界**：PyYAML 校验两文件语法、needs 图闭合、outputs 声明均可解析；`wf_regex_test` 对触发正则做 8 条必命中 + 11 条必不命中断言并校验与文件内正则无漂移，**RESULT OK**；`changes` 的 git diff 对实际改动集模拟出「`security-scan.yml`→AUDIT / `ci-cd.yml`→skip」的预期分流。**边界（据实标注）**：本机 `bash` 不可用（无发行版的 WSL shim，`uname -a` 空、`/c` 盘未映射），故 shell 分支逻辑**未能本地执行验证**，改由上述 CI 实跑覆盖。另 `wf_check.py` 残留一条 `self-reference missing` 告警系该脚本自身按字面量匹配 `security-scan.yml$`（实际文件为转义形式 `security-scan\.yml$`）的误报，已由 `wf_regex_test` 的按行抽取交叉确认无漂移。
- **降噪路径的独立直证（head `7c8328b`，仅文档提交）**：`Dependency Security Scan` run **`37009744504`（#107）= success，耗时 17s**（审计路径约 90s）。job 级：依赖变更探测 **success**、`Python 依赖安全审计` **skipped**、`Node.js 依赖安全审计` **skipped**、密钥泄露扫描 **success**、每周安全报告 skipped、**`Security 汇总` success**。**最关键一条成立**：两个 audit 被有意跳过的同时汇总判 success 而非误报失败 —— 这正是「job 级 `if:` + 汇总按 `deps-changed` 分流」要解决的易错点。**据实标注**：`deps-changed` 输出的字面值 `false` 未能直证（job 日志需登录，未认证抓取拿不到步骤输出）；可观测旁证是两条 audit 被 job 级 `if:` 跳过，二者一致，但不以间接证据充作直证。
- **CD 链路在文档提交上重复验证（head `7c8328b`）**：`CD Pipeline` run **`37009777737`（#89）**：**`安全门禁校验` success**、`Docker Build & Push` **failure** 且失败步骤确认为第 4 步 `Login to Docker Hub`、报错原文 **`Username and password required`**、`Prune Old Images` skipped。**该报错原文直接坐实 §三-5 为 Docker Hub 凭据缺失**，而非本次改动引入的回归（`安全门禁校验` 已先行 success，审计通过后才走到登录步骤）。
- **历史文档证据纠错（§1.8 新发现义务）**：`docs/Review/mimo-v2.6-flash-free-2026-09-23.md`（79 / 104 / 195 行）与 `docs/Review/full-review-report-2026-09-17.md`（25 行）共 4 处，把 `--fail-on=high` 当作 SC-7「已修复」的**证据**引用，而该参数在 pip-audit 2.x 不存在。**结论无误**（fail-closed 确实满足 SC-7），错的只是证据字符串。已在各行末单元格加 `<br>2026-10-01 补注`，原结论与删除线一律未动。`融合审查报告-2026-09-23.md:84` 只引「pip-audit+cron」无需处理；`docs/compose/specs/2026-07-06-*.md` 按带日期方案存档惯例不动。
- **一处方法论漂移（教训）**：同一事实在两处文档结论相反 —— 根 `AGENTS.md` 长期写「配置完成前标记 `[PENDING]`，不阻断合并」，而 `mimo` 审查报告已判 SC-7 为 **√**。根因是工作流落地后**无人回写根级配置**，属文档漂移而非实现缺失。本条已随 v3.7.0 补丁一并修正（见下条）。
- **§5.4 适用性判定**：不触发沙盒期。audit 的 exit 条件与阻断阈值**一字未改**（仍为「发现任意漏洞即 exit 1」），本次仅将既有结论汇入 `Security 汇总` 并前移至部署链路，属阻断结论的执行搬运而非红线收紧。
- **未验证项（据实标注，不冒充已验证）**：门禁的**红路径**（audit 真失败时应阻断）无法 CI 直证 —— 需故意注入漏洞才能观测，本次未做；`security-gate` 的四条拒绝分支同理未实跑，仅验证了通过分支。

*登记人：big-pickle ｜ 状态：**§三-6 后续完成**（head `46ef870`：security-scan `37005012168` `Security 汇总` success、CI `37005012100` 15/15 success、CD `37005117969` `安全门禁校验` success 且仅 Docker 登录红于 §三-5；降噪路径另经 head `7c8328b` run `37009744504` 直证：audit 双 skipped 而 `Security 汇总` 仍 success；根 `AGENTS.md` 升 v3.7.0 去伪 + 4 处历史报告证据纠错；**红路径未验证**），2026-10-01*

## BF-068 【已关闭】create fan-out 落库值重复：N 条资产各存 N，使 SUM 口径得 N²（登记来源：资产分组展开表格实施方案 v2.3 阶段1 R-11② / Q-7 / W-2）

### 〇、元信息

- **登记日期**：2026-10-03
- **来源**：`docs/资产分组展开表格-实施方案-v2.3.md` 阶段1 缺陷 R-11②、Q-7；修复项 W-2，回归 T1
- **关键程度**：P1（每次 N>1 的创建都写入错误数量，任何按该字段汇总的统计口径失真 N 倍）
- **影响范围**：`apps/assetmanagement/services/asset_service.py`（`create_asset`）；测试 `tests/test_services.py`、`tests/test_batch_create_asset.py`
- **契约影响**：无 —— 请求字段名/类型/默认值与响应结构均未变，仅落库值纠正回设计意图
- **跨端契约**：未变更

### 一、现象

1. 单次创建传 `asset_purchase_number=3`，`Asset.objects.count()` 正确为 3（fan-out 条数无误），但三条记录的 `asset_purchase_number` **全为 3** 而非 1。
2. 故「Σ实物数量」= 3×3 = 9 = **N²**，按该字段求和的统计与台账口径虚高。
3. N=1 时不显现（1×1=1），故长期未被察觉。

### 二、根因

| # | 环节 | 事实 |
|---|---|---|
| 1 | 入参未剥离 | 修复前 `create_asset` 仅 `pop("asset_code")`，`asset_purchase_number=N` 原样留在 `asset_data` |
| 2 | fan-out 循环 | 循环内 `single_data = {**asset_data, "asset_code": code}` 继承 N → 每条明细都带 N |
| 3 | 落库 | `Asset.objects.create(**single_data)` 直接写入 N |
| 4 | **缺陷逃逸根因** | 修复前全仓**无任何测试断言 create 后的落值**（`test_services.py` 既有用例只断言 `len(assets)==3` 与 code 后缀），故该缺陷在测试全绿下长期存活 |

### 三、修复方案

| # | 变更 | 文件 |
|---|---|---|
| 1 | 在 fan-out **之前**覆写 `asset_data["asset_purchase_number"] = 1`，使循环内 `single_data` 自然为 1（不在循环内重复赋值） | `services/asset_service.py:137`（`create_asset` 在 `:127`，`@transaction.atomic` 在 `:126`） |
| 2 | T1 补落值断言 `assert [a.asset_purchase_number for a in assets] == [1, 1, 1]` | `tests/test_services.py:110`（N=3 入参 `:91`） |
| 3 | T1c 补批量落值断言 `sorted(...) == [1, 1, 1]` | `tests/test_batch_create_asset.py:236`（用例 `test_batch_create_should_handle_purchase_number`，N=3 入参 `:227`） |

### 四、对抗审核

1. **是否改动 API 契约**：否。字段名、类型、默认值、响应结构均未变；改动只把落库值纠正回「每台 1 台」的设计意图，COUNT 口径随之成立。
2. **覆写位置是否安全**：置于 `@transaction.atomic`（`:126`）内、fan-out 循环前，单事务生效。`asset_data` 为函数内 `dict(asset_data)` 副本（`:130`），覆写不污染调用方传入对象。批量路径 `batch_create_asset`（`:255`）经 `_create_item` 复用同一函数，故**一处改动覆盖单条与批量两条路径**（DR-1）。
3. **是否掩盖了更深的 bug**：未。`purchase_number` 仍作瞬态入参决定 fan-out 条数（`:133` 读取 → `:143` 传生成器），覆写只作用于写入侧，读取侧与写入侧职责已分离且各有断言锚定。
4. **不可变性配套**：仅修 create 落值不足以保证该字段不被事后改写，故另立 **BF-071**（PATCH 可自由改写）。二者根因与代码路径不同，**不并入本条**。
5. **口径选择依据**：`rg` 确认全仓无 `Sum("asset_purchase_number")`，故采用 COUNT；修复后恒等式 `asset_count = N = Σ实物数量` 成立。

### 五、验证记录

```text
① 后端全量 pytest：958 passed, 6 warnings in 494.00s（基线 955，净增 3，与新增用例数一致）✅
② ruff check .：All checks passed ✅
③ 四项护栏 EXIT=0：check_file_length_guard / check_function_length_guard /
   check_frontend_invariants / check_duplicate_invariants ✅
④ T1/T1c 落值断言实测转绿（test_services.py:110、test_batch_create_asset.py:236）✅
```

**验证边界（据实标注，不冒充已验证）**：以上全部为**本地**执行，**未经 CI 直证** —— 相关改动当前未提交（父仓 `git status` 显示子模块 ` m`），无对应 CI run ID 与 job 级结论。按 CT-7，CI 基线须以 `requirements/dev.txt` 声明工具链在 CI 侧取得，**本条目数字不代表 CI 水平**。

### 六、遗留与关联事项

- 关联 **BF-071**（同字段 PATCH 可写缺陷，W-3 关闭）、**BF-070**（同字段缺 `min_value` → 500，W-4 关闭）、**BF-069**（「行/条」口径误判为少算 → 改判非缺陷）。
- 快照护栏 G-1~G-5 未受扰：本次无新增重复实现、无影子死文件。

*登记人：big-pickle ｜ 状态：已关闭（W-2 + T1/T1c；本地验证通过，CI 未直证），2026-10-03*

## BF-069 【已关闭】批量创建「上报条数少算」改判为非缺陷：success_count 按行计即设计语义（登记来源：v2.3 阶段1 W-5）

> **本条为「非缺陷改判」登记**，目的为留痕改判结论、防止后续重复上报（对齐 BF-028 / BF-029 / BF-030 的误报纠正先例）。本条**不含代码缺陷修复**，所涉改动为界面口径消歧。

### 〇、元信息

- **登记日期**：2026-10-03
- **来源**：`docs/资产分组展开表格-实施方案-v2.3.md` 阶段1；修复项 W-5（前端双计数）
- **关键程度**：P3（界面表述易误导，非数据缺陷）
- **影响范围**：`vue-assetmanagement/src/components/componentsdetails/detils/AssetBatchImport.vue` 及其 spec
- **契约影响**：无 —— 后端响应结构与字段语义**均未改动**
- **跨端契约**：未变更

### 一、核实结论（原表述 > 实测事实）

**原表述**：批量创建成功提示「成功 N 条」少于实际生成的资产数 → 少算，疑似丢数据。

**实测事实**：

| # | 事实 | 依据 |
|---|---|---|
| 1 | `"success_count": len(success_items)` —— 按**成功行**计 | `core/batch_mixins.py:134` |
| 2 | `_create_item` 返回 `result[0]` —— 每行只回一个代表元素，故 `success_items` 每行一个 | `services/asset_service.py:266` |
| 3 | `success_items: T[]` + 元素类型注释 | `src/types/common.ts:63`（注释 `:56`） |
| 4 | 1 行 / N=3 → 断言 `success_count == 1` 且 `count == 3` | `tests/test_batch_create_asset.py:233` / `:234` |
| 5 | **数据无丢失**：`create_asset` 带 `@transaction.atomic`（`:126`），单行 fan-out 全有或全无；`success_count == 1` 即该行 N 条全部落库 | `services/asset_service.py:126` |

**结论**：`success_count` 按行计是**被测试主动锁定的既定契约**（事实 4），不是疏漏；数据未丢失（事实 5）。真实缺口在**界面未区分「行」与「条」** —— 用户看到「成功 1 条」而实际生成 3 台资产，易误判为少算。

### 二、根因（真实缺口）

| # | 环节 | 事实 |
|---|---|---|
| 1 | 后端语义正确 | `success_count` 按行、`success_items` 每行一代表元素，两者一致且有测试锚定 |
| 2 | 界面口径单一 | 导入页全成功提示只显示行数（`success_count`），未同时给出实际生成的资产条数，用户无从区分「行」与「条」 |
| 3 | 前端可推算 | 因单行全有或全无（`@transaction.atomic`），「该行成功」必然意味着「该行录入数量 N 条全部落库」，故前端可据成功行准确推算条数 |

### 三、修复方案（前端双计数，后端零改动）

| # | 变更 | 文件 |
|---|---|---|
| 1 | 新增 `validAssetCount` computed = Σ(有效行的录入数量)，用于提交前预览与全成功提示 | `AssetBatchImport.vue:191`（模板消费点 `:57`、按钮 `:128`） |
| 2 | 按钮文案改为「提交有效数据（X 行 / Y 条资产）」 | `AssetBatchImport.vue:128` |
| 3 | 全成功提示改为「成功 X 行，生成 Y 条资产」 | `AssetBatchImport.vue:356` |
| 4 | 部分失败提示给出成功/失败**行数**，且 Y **仅累加成功行**的录入数量 | `AssetBatchImport.vue:362`（排除逻辑 `:347-351`，设计注释 `:344-346`） |
| 5 | 400 校验失败分支明确「未创建任何资产」 | `AssetBatchImport.vue:314` |
| 6 | 表头/校验文案统一「录入数量」 | `AssetBatchImport.vue:77` / `:111-112` |

### 四、验证记录

```text
① 前端受影响 11 个 spec：222 passed ✅
② AssetBatchImport.spec.ts：7 passed（原有 3 + 新增 4：1/2/3→6 条、失败行排除、
   提交前双计数、非法 N 兜底）✅
③ 变异敏感性实测：删除「排除失败行」逻辑后，部分失败用例如期转红；恢复后全绿；
   无 MUTATION_SENTINEL_W5 残留 ✅
④ 前端 type-check / format:check 通过；本次涉及文件定向 ESLint 通过 ✅
⑤ 四项护栏 EXIT=0 ✅
```

**验证边界（据实标注）**：全量 `npm run lint` 仍被遗留 `.stryker-tmp/sandbox-*` 目录污染（约 1994 条 parser/tsconfigRootDir 错误），属**环境基线问题**而非本次代码失败，故以定向 lint 为准；且全部为**本地**执行，**未经 CI 直证**。

### 五、对抗审核

1. **为何登记非缺陷**：不登记则改判结论无留痕，同一「少算」质疑会被重复上报。登记为【已关闭】并附反证，既保留审计链又不污染缺陷计数。
2. **是否掩盖了真丢数据**：否。`@transaction.atomic` + `test_batch_create_asset.py:233/234` 双断言（`success_count == 1` 且 `count == 3`）证明数据完整。
3. **前端推算是否可靠**：可靠但**依赖单行原子性**。若未来去掉 `@transaction.atomic` 允许行内部分成功，前端推算即失效。故在 `AssetBatchImport.vue:182-185` 以注释固化该前提；此依赖是**已知耦合**，非隐式假设。
4. **partial 分支的 M 值**：必须排除失败行，否则把未创建行的录入数量计入总数，产生**误导性虚高**。已由变异测试锁定。

### 六、遗留与关联事项

- 耦合前提：`create_asset` 的 `@transaction.atomic` 是前端条数推算成立的基础。移除该装饰器须同步改本条推算逻辑（已留注释锚点）。
- 关联 **BF-068**（同批落值修复）、**BF-070**、**BF-071**。
- 快照护栏 G-1~G-5 未受扰。

*登记人：big-pickle ｜ 状态：已关闭（改判为非缺陷，结论由 W-5 界面口径消歧落地；本地验证通过，CI 未直证），2026-10-03*

## BF-070 【已关闭】asset_purchase_number 缺 min_value：N<1 的客户端错误被渲染为 500 而非 400（登记来源：v2.3 阶段1 R-11 / W-4）

### 〇、元信息

- **登记日期**：2026-10-03
- **来源**：`docs/资产分组展开表格-实施方案-v2.3.md` 阶段1；修复项 W-4，回归 T3
- **关键程度**：P2（错误分类错误 + 掩盖真实原因，无数据损坏）
- **影响范围**：`apps/assetmanagement/serializers/asset_crud_serializers.py`
- **契约影响**：无（错误响应由 500 前移为 400，属**纠正**而非变更；`code`/`message`/`data` 根结构不变）
- **跨端契约**：未变更

### 一、现象

创建请求传 `asset_purchase_number=0`（或负数），客户端收到 **HTTP 500**，而非语义正确的 400。排障时 500 指向「服务端异常」，掩盖了真实原因（入参非法）。

### 二、根因

| # | 环节 | 事实 |
|---|---|---|
| 1 | 服务层守卫存在 | `AssetCodeGenerator.generate` 抛 `ValueError("purchase_number 必须 >= 1")` —— `services/asset_service.py:94-95` |
| 2 | 生成器不包装 | `generate_with_unique_check`（`:108`）在 `:110` 原样调用 `generate`，**无 try/except**，异常原样上抛 |
| 3 | **序列化层缺校验** | 创建序列化器 `serializers/asset_crud_serializers.py` 的 `extra_kwargs` 对该字段**原无 `min_value`**（`:305` 注释处即本次补入位置） |
| 4 | **View 未捕获** | `views/asset_view.py:135 def create` 全文件**无 `except ValueError`**（`rg` 确认零命中） |

**缺陷机制**：非法入参穿透序列化层 → 服务层守卫抛 `ValueError` → View 未捕获 → DRF 全局处理器按未处理异常渲染为 **500**。

> **口径纠错（对齐 v2.3 Q-7）**：本文档初稿曾写「建 0 行仍返 201」，**不成立** —— 服务层守卫本就存在，真实表现是未捕获异常导致的 500。W-4 的作用是**把 500 前移为 400**，**不是**新增校验。

### 三、修复方案

| # | 变更 | 文件 |
|---|---|---|
| 1 | 创建序列化器 `extra_kwargs` 补 `"asset_purchase_number": {"required": False, "default": 1, "min_value": 1}` | `serializers/asset_crud_serializers.py:306` |
| 2 | T3 补 API 用例：N=0 → 400，且 `Asset.objects.count() == 0`（零落库） | `tests/test_asset_view_api.py:166`（`test_create_asset_rejects_zero_purchase_number`） |

**刻意不改（防误改）**：`CombinedAssetSerializer`（`asset_crud_serializers.py:321`，该字段声明在 `:326`）是**纯输出用**序列化器（`get_asset_details_data` 返回 `AssetDetailSerializer(...).data`），`min_value` 只在输入校验生效，加了无效且误导。批量序列化器 `asset_batch_serializers.py:62` 原本已有 `min_value`，无需改。

### 四、对抗审核

1. **是否该在 View 加 `except ValueError`**：不加。View 兜底会把所有 `ValueError` 一律转 400，反而掩盖真正的服务端编程错误；在序列化层拦下入参更精准，且错误信息能直达字段。
2. **是否影响已有合法请求**：`min_value=1` 与服务层守卫 `:94-95` 同阈值，不存在「序列化层放行但服务层拒绝」的缝隙；`default=1` 与 `required=False` 保持不变，未传该字段的既有行为不变。
3. **500 路径是否仍在**：结构上仍在（`asset_view.py` 仍无 `except ValueError`），但**该字段**的非法入参已在序列化层被拦下，不再走到服务层抛 `ValueError`。其他 `ValueError` 来源不在本条范围。
4. **契约影响复核**：500→400 是把错误分类纠正到语义正确状态，非破坏性变更；响应根结构 `{"code","data","message"}` 不变，故**无需重导出 schema 基线**（亦无端点/字段增删）。

### 五、验证记录

```text
① 后端全量 pytest：958 passed, 6 warnings in 494.00s（基线 955，净增 3）✅
② T3 实测：N=0 → 400 且 Asset.objects.count() == 0 ✅
③ ruff check .：All checks passed ✅
④ 四项护栏 EXIT=0 ✅
```

**验证边界（据实标注）**：均为**本地**执行，**未经 CI 直证**（改动未提交，无 run ID）；本地数字不代表 CI 水平（CT-7）。

### 六、遗留与关联事项

- 遗留：`asset_view.py` 仍无 `except ValueError` 兜底，其他未预期 `ValueError` 仍会渲染 500。是否加全局兜底属**独立议题**，本条不扩范围。
- 关联 **BF-068**、**BF-069**、**BF-071**（同字段）。
- 快照护栏 G-1~G-5 未受扰。

*登记人：big-pickle ｜ 状态：已关闭（W-4 + T3；本地验证通过，CI 未直证），2026-10-03*

## BF-071 【已关闭】asset_purchase_number 未列入不可变集：PATCH 可任意改写实物台数（登记来源：v2.3 阶段1 R-11③ / W-3 / W-3a）

> **本条为 v2.3 缺陷台账的补漏登记**：v2.3 的 BF 规划（BF-068/069/070）**未为 R-11③ 分配编号**，而该项是已定位、已修复、已补测试的真实缺陷，故按 `rg` 实测末位 **BF-067** 之后顺序补登为 BF-071。

### 〇、元信息

- **登记日期**：2026-10-03
- **来源**：`docs/资产分组展开表格-实施方案-v2.3.md` 阶段1 缺陷 R-11③、Q-7；修复项 W-3 + W-3a，回归 T2/T4
- **关键程度**：P1（客户端可任意篡改资产实物数量，属台账数据完整性缺口）
- **影响范围**：`services/asset_service.py`（`ASSET_UPDATE_IMMUTABLE_FIELDS` / `update_asset`）；前端 `AssetForm.vue`、`AssetBasicInfo.vue`
- **契约影响**：PATCH 该字段由 **200 静默写入** 变为 **400 `FIELD_NOT_ALLOWED`** —— 属**收紧非法写入**，合法请求不受影响
- **跨端契约**：未变更（合法 PATCH 载荷形状不变）

### 一、现象

对既有资产发 PATCH，请求体带 `asset_purchase_number=3` 即被静默接受并落库为 3 —— 该字段本应是不可变的**实物台数**，任何客户端都能改写它。

### 二、根因

| # | 环节 | 事实 |
|---|---|---|
| 1 | 不可变集缺项 | `asset_purchase_number` 原不在 `ASSET_UPDATE_IMMUTABLE_FIELDS`（修复前该集合 `:29-39` 仅含 code / recordcode / qr_code / version / is_deleted / 时间 / status） |
| 2 | Service 不拦截 | `update_asset`（`:167`，`@transaction.atomic` 在 `:166`）按传入 `validated_data` 直接写库，无该字段的任何校验 |
| 3 | 序列化层放行 | Update 序列化器字段集含该字段，故 `validated_data` 携带它进入 Service |
| 4 | **前端亦会主动提交** | 编辑表单复用 create 的构造器，原样携带该字段 → **不修前端则每次编辑提交都会被新拦截打回 400** |

### 三、修复方案

| # | 变更 | 文件 |
|---|---|---|
| 1 | `"asset_purchase_number"` 加入 `ASSET_UPDATE_IMMUTABLE_FIELDS`（集合 `:29`，新增项 `:41`，结束 `:42`）→ PATCH 命中即抛 `FIELD_NOT_ALLOWED` | `services/asset_service.py:41` |
| 2 | W-3a 前端配套：新增 `getAssetUpdateForm` computed（`{...getAssetCreateForm.value}` 后 `delete` 该字段） | `AssetForm.vue:177-181`（consume 点 `:312-315`；create 构造器 `:149-170`，该字段在 `:157`） |
| 3 | W-3a 前端配套：编辑态数量字段置灰只读 + 显示「录入数量」 | `AssetBasicInfo.vue:52-60` |
| 4 | T2 补双层用例：service 层 + API 层均断言 400 `FIELD_NOT_ALLOWED` | `tests/test_asset_service.py:51` / `tests/test_asset_view_api.py:153`（均名 `test_update_asset_rejects_purchase_number_change`） |
| 5 | T4 修正既有整表单 PATCH 用例：`test_asset_view_api.py::test_update_asset` 载荷**移除**该字段（否则必红） | `tests/test_asset_view_api.py` |

### 四、验证记录

```text
① 后端全量 pytest：958 passed, 6 warnings in 494.00s（基线 955，净增 3）✅
② T2 实测：service 层与 API 层 PATCH 该字段均 400 FIELD_NOT_ALLOWED ✅
③ 前端 11 个 spec：222 passed ✅；type-check / format:check 通过；定向 ESLint 通过 ✅
④ 四项护栏 EXIT=0 ✅
```

**验证边界（据实标注）**：均为**本地**执行，**未经 CI 直证**（改动未提交）；全量 `npm run lint` 因 `.stryker-tmp/sandbox-*` 污染不可用，以定向 lint 为准。

### 五、对抗审核

1. **W-3 与 W-3a 为何必须同批**：缺 W-3a 则前端每次编辑提交都 400（可用性全面断裂）；缺 W-3 则不可变约束可被绕过。二者任缺即回归，已作为 W-3 行的「两半缺一即回归」记录在 v2.3。
2. **是否影响 FSM**：否。`rg` 实测 `services/` + `state_machine/` 全树对 `asset_purchase_number` 的引用**仅 1 处**（`asset_service.py:137` 写入侧），FSM 与生命周期零引用，故该字段不可变化**不阻断任何状态流转**。
3. **是否属越权收紧**：属。资产数量为台账核心字段，可任意改写即数据完整性缺口；收紧后合法编辑流程不受影响（前端已同步剔除）。
4. **是否掩盖了其他可写字段问题**：不可变集与 Update 序列化器字段集**逐字段对齐**问题在本项目另有登记（见本账本既有 `FIELD_NOT_ALLOWED` 相关条目），本条只覆盖 `asset_purchase_number` 单一字段，不扩范围。
5. **审计双计风险**：本字段的 create 侧落值缺陷独立登记为 **BF-068**；二者虽同字段但**代码路径不同**（`create_asset` 写入 vs `update_asset` 改写）、根因不同（未剥离 vs 未列入不可变集），故分立登记而非合并。

### 六、遗留与关联事项

- `asset_current_status` 同在不可变集内（`:41`）但仍可被 FSM 修改 —— 属 FSM 专用后门，为既有设计，非本条范围。
- 关联 **BF-068**（create 落值）、**BF-069**、**BF-070**。
- 快照护栏 G-1~G-5 未受扰。

## BF-072 【追踪中】GroupedAssetTable.vue side-tab accent border（impeccable 引入后首跑实证产出）

> **登记来源**：impeccable v4.5.0（opencode 发行版）引入计划 Step6 首跑实证——`impeccable detect --json` 输出。
> **性质说明**：此为**设计质量告警（非功能缺陷）**，依用户拍板"接受该告警并录入追踪（不豁免）"。不改代码。

### 〇、元信息

- **登记日期**：2026-10-07
- **来源**：`impeccable detect --json src/components/GroupedAssetTable.vue`（detector 退出码 2）；critique/audit 首跑快照 `.impeccable/critique/2026-10-07T03-56-29Z__ment-src-components-groupedassettable-vue-1c377064.md`
- **关键程度**：P3（设计 polish，无功能影响；detector 归类为 `slop` 类 warning）
- **影响范围**：`vue-assetmanagement/src/components/GroupedAssetTable.vue:285`
- **跨端契约**：无影响（CSS 层视觉声明）

### 一、现象

detector 报告的 antipattern：`side-tab`（`Side-tab accent border`），指向 `GroupedAssetTable.vue:285` 的 `border-left: 4px solid var(--color-primary-light)`，属于 `.group-children` 展开区卡片样式的活声明（选 `@`.group-children` 命中模板 L37，scoped 样式真实生效，非注释/非死代码/非字符串）。

### 二、核验

- 全文 `border[a-z-]*` 声明仅此 1 条（其余为 `border-radius` L286/L303），无误报。
- Assessment A（设计审查）曾把该左竖条评为"层级语言亮点"，Assessment B / detector 判其为 "最明显的 AI 生成 UI tell"，二者结论不一致且均有据——故**接受记录而不豁免**是稳妥口径。
- critique 得分 24/40（Acceptable），audit 得分 15/20（Good）；本告警无贡献于两份总分的失分项（side-tab 未被计入任一评分维度，属确定性扫描佐证项）。

### 三、处置方案（待用户决策，登记为"追踪中"）

| 选项 | 动作 | 命令 |
|---|---|---|
| A（推荐） | 保留竖条但弱化：4px→2px 或改 `--color-primary-lighter`，维持层次语言同时规避 tell | /impeccable layout |
| B | 完全移除竖条，仅靠背景色与间距区分展开区 | /impeccable distill |
| C | 暂不改动，保持现状（既有拍板"接受，不豁免"即指向此态，但登记为待核查） | 无 |

### 四、验证记录

```text
① detector：impeccable detect --json → exit 2，单条 side-tab:285（完整 JSON 见 critique 快照）✅
② 双 agent 核验：Assessment B 附文件:行号与引文，确认真实命中 ✅
③ 行数：template+script 逻辑行 ≈197 < FR-5 500 上限，文件 322 物理行 ✅
④ 跨代理结论冲突已记录（A 评亮点 vs B 评 tell）✅
```

### 五、关联事项

- impeccable v4.5.0 安装落位 `D:\CodeDemo\AssetManagementProgram\.opencode\skills\impeccable\`（58 文件），引擎二进制 v0.1.11 缓存于 `%USERPROFILE%\.impeccable\bin\0.1.11`，`~/.impeccable` 运行时数据目录承载 critique 快照。
- 引入计划全部 7 步已执行（SL 基础→安装→校验→清理→.gitignore→首跑→审计票）。

*登记人：big-pickle ｜ 状态：追踪中（首跑实证产出，待用户选择处置项 A/B/C），2026-10-07*

*登记人：big-pickle ｜ 状态：已关闭（W-3 + W-3a + T2/T4；本地验证通过，CI 未直证），2026-10-03*

*登记人：big-pickle ｜ 状态：**BF-068~BF-071 登记完成**（末位由 BF-067 推进至 BF-071；BF-071 为 v2.3 台账补漏；四条均本地验证通过、**CI 未直证**，改动未提交），2026-10-03*

*登记人：big-pickle ｜ 状态：**§三-6 完成**（run 106 双 audit 归零 CI 直证，axios 1.20.0 + PyJWT 2.15.1 落地；仅剩 §三-5 Docker Hub 凭据未做），2026-09-30*

*登记人：big-pickle ｜ 状态：**修复批已收口**（run 101 15/15 全绿终验证，变异基线 68.6064 + M-3 判据修复 + 门禁显示精度三项均生效；ci-cd/security 两 workflow 另立，下一步 C/D 批），2026-09-30*

*登记人：big-pickle ｜ 状态：**修复批收口中**（run 99 后端测试首绿 + M-3 漂移 warning 消除已 CI 直证；变异基线浮点取值 bug 已修 `95f9458` + 门禁显示精度提升，待 run 100 终验证；ci-cd/security 两 workflow 另立），2026-09-30*

*登记人：big-pickle ｜ 状态：**修复批收口中**（run 98 后端测试首绿；变异基线已切 CI 环境 `b0aec84`、M-3 漂移 warning 判空缺陷已修、待 run 99 双验证；ci-cd/security 两 workflow 另立），2026-09-30*

*登记人：big-pickle ｜ 状态：**待修复→修复批已落地**（①②④ 提交，③ 待日志；②④ 已 CI 直证，①经 run 91 直证后 ruff 回归已修 `16687a4`；ci-cd/security 两 workflow 另立），2026-09-30*


## BF-073 【已关闭】分组展开页 21~100 条组后续数据不可达：分页条判据固定 `>100` 与实际页长 20 脱钩（登记来源：impeccable audit 2026-10-07 P1 / 方案 v2.3 决策 6 修正）

> **登记来源**：impeccable audit 报告 `.impeccable/audit/2026-10-07T04-00Z__GroupedAssetTable.md` P1（原文引 `useGroupedAssetColumns.ts:50-52`，修复后实测 `:51-52`）。
> **性质说明**：**功能缺陷**（数据可达性缺口），非设计告警。经用户拍板「本批修复 + 同步改验收标准 AC-67d」。

### 〇、元信息

- **登记日期**：2026-10-07
- **来源**：audit P1（critique 32/40 / audit 15/20 同一目标文件两份报告）
- **关键程度**：P1（用户基于不完整数据决策；种子场景 5 的验证链路被整体阻断）
- **影响范围**：`src/composables/useGroupedAssetColumns.ts:51-52`（判据）、`src/components/GroupedAssetTable.vue:61`（模板传参）、3 个 spec 文件、`AC-67d`、方案书 8 处锚点
- **跨端契约**：**无影响**（纯前端显示判据；后端分页参数 `page`/`page_size` 与响应结构未动）

### 一、问题现象

1. `shouldShowChildPagination` 旧判据为 `asset_count > CHILD_PAGINATION_THRESHOLD`（常量 =100），而组内 `page_size` 默认 20（可切 50/100）——**21~100 条组只显首页 20 条，无「加载下一页」按钮**，后续数据 UI 不可达（后端翻页能力实测在：25 条组 page2 返回 5 条、total_pages=2）。
2. 方案书场景 5 专设 **25 条**种子组验证组内分页（后端实测直证通过），被旧阈值挡住 → 该场景的 UI 链路从未真正可达。
3. 判据与页长脱钩的双向错判：页长切 50 时 51~100 条组需分页却无条（缺口）、页长 100 时 101 条组恒显条但首屏 100 条本就快满（语义仍对，属运气对齐而非设计对齐）。

### 二、根因

| # | 环节 | 事实 |
|---|---|---|
| 1 | 决策落码 | 决策 6 原文以「超长组才分页」定性表达，实现落为固定阈值常量 `CHILD_PAGINATION_THRESHOLD = 100`（旧 `useGroupedAssetColumns.ts:21-22`），未与 `childPageSize` 建立联动 |
| 2 | 页长可变 | `CHILD_PAGE_SIZE_OPTIONS = [20,50,100]`（现 `:22`）支持切页长，阈值仍写死 100 → 页长 20 下 21~100 档全部静默 |
| 3 | 测试固化错误规格 | 原用例 12 只断言「120 显示 / ≤100 不显示」，把错误判据当规格测，缺口被双向钉死；种子 25 条组无 UI 层断言 |
| 4 | 文档同误 | AC-67d Given 写 `asset_count > 100`、方案书 8 处沿用（`:420/:438/:458/:466/:498/:924/:937/:42`），规格层与实现层同错 |

### 三、修复方案

| # | 变更 | 文件 |
|---|---|---|
| 1 | 判据改双参 `shouldShowChildPagination(row, pageSize)` = `row.asset_count > pageSize`；删除 `CHILD_PAGINATION_THRESHOLD` 定义与导出 | `useGroupedAssetColumns.ts:51-52`（常量原 `:21-22` 已删，导出原 `:74` 已删） |
| 2 | 模板传入 `childPageSize`（`el-pagination` v-model:page-size 同源解包） | `GroupedAssetTable.vue:61` |
| 3 | spec 先红后绿：单元边界改双参断言（20/21/100/101/99/50/0），组件侧用例 12 改题 + 新增 `asset_count=50` 回归用例 | `useGroupedAssetColumns.spec.ts`、`GroupedAssetTable.spec.ts:348` |
| 4 | 文档同步：AC-67d Given 改 `> page_size（默认 20）` 并注明修正缘由；方案书 8 处锚点标注 BF-073 修正；新增 §3.12.11 | `07-功能需求与验收标准.md:281`、`docs/资产分组展开表格-实施方案-v2.3.md` |

### 四、对抗审核

- **行号漂移**：本条所有 `文件:行号` 为修复后 `rg` 实测（见五-①），非沿用 audit 旧行号。
- **越权/红线**：改 AC 文本属验收标准修订，**已获用户显式拍板**（「本批修复 + 同步改验收标准」）；非跨端契约、非状态机路径。
- **audit P1 附带引用 `useGroupChildrenCache.ts:154-155` 核验**：实为 `ensureChildren` 缓存命中早返 + 拉首页（`rg` 实测见五-②），与阈值判据**无耦合**，无需改动——audit 引用它是在说明「翻页数据并入缓存」的链路位置，非指其含缺陷。
- **是否掩盖更深 bug**：反向确认无第二处阈值依赖——`rg CHILD_PAGINATION_THRESHOLD` 全仓 0 命中（三处消费点：定义、判据、其 spec 断言，均在本批清理）。
- **先红后绿**：改 spec 先跑红（3 failed：2 单元边界 + 1 组件 50 条缺口用例），改实现后 20/20 绿，缺口用例真实复现过失败。
- **契约影响**：请求/响应形状、分页参数名、状态机零变化；schema 无需重导出（纯前端）。

### 五、验证记录

```text
① 行号实测（rg）：shouldShowChildPagination 定义 :51、判据 :52、模板调用 :61、回归用例 spec :348、CHILD_PAGE_SIZE_OPTIONS :22 ✅
② useGroupChildrenCache.ts:154-155 实读 = ensureChildren 缓存早返/拉首页，与分页判据无关 ✅
③ 残留扫描：rg CHILD_PAGINATION_THRESHOLD（src/，*.ts,*.vue）= 0 命中；AC 文件 asset_count > 100 = 0 命中；方案书残留 3 处均为「原述→BF-073 改为」的刻意修正表述 ✅
④ 先红：npx vitest run <两 spec> → 3 failed / 17 passed（缺口真实复现）✅
⑤ 后绿：同命令 → 20 passed；全量 npx vitest run → 147 files / 2033 tests passed ✅
⑥ 门禁：type-check exit 0；eslint . exit 0；format:check exit 0；complexity 改动文件 0 命中（全仓 52 = CI 既有存量）；coverage 整体 92.99% / Stores 97.82%；check_frontend_invariants.py PASS ✅
⑦ 变异（定向）：npx stryker run --mutate src/composables/useGroupedAssetColumns.ts → Mutation score 100.00 ≥ break 80，4 个 `>` 边界突变全部被新用例击杀 ✅
（全量 test:mutate 本地 30min 超时未出分；按方案书 §6.1「全量 CI 跑 + 本地不跑」口径处置，ci.yml frontend-mutation 仍 continue-on-error）
```

### 六、遗留与关联事项

- audit 的 P2×2（全选「仅本页」提示、勾选无出口）与 P3×3（aria-label/aria-live/title 可达性）、width 55→56 **本批未执行**，待用户点单；side-tab 10 处处置 A/B/C 亦待批（见 BF-072 追踪中）。
- 方案书决策 6 表、D-2 行、场景 5 表与偏差注记、修订清单行均已加 BF-073 修正标注；AC-67d 为规格层同步修订。
- 同组件既有追踪条目：BF-072（side-tab，待用户选 A/B/C）。

*登记人：big-pickle ｜ 状态：已关闭（先红后绿 + 7 项门禁 + 定向变异 100.00 实证，改动未提交），2026-10-07*


## BF-074 【已关闭】分组展开表两处 WCAG AA 对比度失败：删除按钮常态灰 3.08:1、数量胶囊白字 2.78:1（登记来源：impeccable critique 2026-10-07 P2）

> **登记来源**：impeccable critique 报告 `.impeccable/critique/2026-10-07T04-55-19Z__ment-src-components-groupedassettable-vue-1c377064.md` 「缺口」P2 行（原文 #909399 2.84:1 / #409eff 3.05:1，为估算值；本条记录实算值）。
> **性质说明**：**无障碍缺陷**（WCAG 2.1 AA 正文文本 4.5:1 未达），代码修复，经用户拍板随美化欠账批执行（A1/A2）。

### 〇、元信息

- **登记日期**：2026-10-07
- **来源**：critique P2（方案审查缺口清单第 2 项）
- **关键程度**：P2（可读性/无障碍，非功能断裂）
- **影响范围**：`src/components/GroupedAssetTable.vue`（`:329` `.group-delete-btn`、`:318/:322` `.asset-count-tag` 双主题）
- **跨端契约**：无影响（CSS 变量声明层）

### 一、问题现象

1. 删除按钮常态文字色 `--text-secondary`（亮 #909399）白底 **3.08:1**，低于 AA 4.5:1。
2. 数量胶囊 `el-tag effect=dark` 用 EP 默认 `--el-color-primary`（#409eff）配白字 **2.78:1**；暗色下 `--color-primary` #4a90e2 白字 **3.29:1**——两主题均不达 AA。

### 二、根因

| # | 环节 | 事实 |
|---|---|---|
| 1 | 按钮色选型 | `.group-delete-btn` 取 `--text-secondary`（设计初衷「常态低调、hover 才危险色」），未验算对比度 |
| 2 | EP 默认色直用 | `el-tag type="primary" effect="dark"` 背景走 EP 内建 `--el-color-primary` #409eff，项目令牌 `--color-primary` #2b5fd7 未接入 el-tag |
| 3 | 暗色更暗 | `variables.css:129` 暗色 `--color-primary` #4a90e2 比亮色更浅，白字对比进一步劣化至 3.29:1 |

### 三、修复方案

| # | 变更 | 文件 |
|---|---|---|
| A1 | 删除按钮常态色 `--text-secondary` → `--text-regular`（亮 #606266），注释记录实算对比 | `GroupedAssetTable.vue:329-333` |
| A2 | 胶囊加 `.asset-count-tag` class：亮 `--el-tag-bg-color: var(--color-primary)`（#2b5fd7）；`:global(html.dark)` 覆盖 `var(--color-primary-dark)`（暗色块实为 #2b5fd7，`variables.css:132`） | `GroupedAssetTable.vue:318-324` |

### 四、对抗审核

- **行号漂移**：`:318/:322/:329` 为格式化回修后 `rg` 实测。
- **取值陷阱核验**：`--color-primary-dark` 在**亮**主题是 `#1e429f`（`variables.css:7`）、**暗**主题才是 `#2b5fd7`（`:132`）——故暗覆盖必须写在 `html.dark` 作用域内取值，不能在亮色规则里引用，当前选择器结构正确。
- **暗底方向未劣化**：删除按钮暗色经 `--text-regular` 解析为 #cfd3dc（`variables.css:157`），对暗底 #141414/#1d1e1f 为 12.29:1 / 11.13:1；旧值 #a3a6ad 亦达 AA，修复在两主题下均不回退。
- **验证边界（诚实标注）**：对比度为 **WCAG 公式算术实算**（node 实算，见五-③），**未跑浏览器暗色态截图实测**——`:global` 选择器编译形态与 el-tag 变量继承链由 vitest 无法覆盖，属 `[推测]→已算术验证，浏览器渲染待目验`。
- **是否同类重复登记**：`rg "对比度|409eff|text-secondary"` 活账本 0 命中，无既有条目。

### 五、验证记录

```text
① 行号实测（rg）：.asset-count-tag :318、html.dark 覆盖 :322、.group-delete-btn :329 ✅
② 方案书/AC 影响：无（纯视觉层，未涉规格文本）✅
③ WCAG 实算（node）：亮按钮 #606266/#fff = 6.11（旧 #909399 = 3.08）；胶囊亮 #fff/#2b5fd7 = 5.64（旧 #fff/#409eff = 2.78）；胶囊暗 #fff/#2b5fd7 = 5.64（旧 #fff/#4a90e2 = 3.29）；按钮暗 #cfd3dc/#141414 = 12.29 ✅ 全部 ≥4.5
④ 回归：npx vitest run GroupedAssetTable.spec.ts → 通过；format:check / eslint exit 0 ✅
⑤ 浏览器暗色态目验：未执行（无浏览器工具），见四-「验证边界」
```

### 六、遗留与关联事项

- critique 同批 P2 中「方案三处自相矛盾」「2 文件 vs 7 文件」两项属**文档缺陷**，在方案书 §3.12.11 修复（非代码，不另立 BF）；critique P1「验证清单漏 mutate/complexity」同在 §3.12.11 完整验证清单补齐。
- 暗色态浏览器目验列为待办，若有偏差回开本条。
- 关联 BF-073（同批 A/B 批次产出）。

*登记人：big-pickle ｜ 状态：已关闭（算术实算达标 + 单测/门禁绿；浏览器暗色目验未做，已如实标注），2026-10-07*

---

## BF-075 【已关闭】列表页 el-table 横向滚动条埋底 + 详情页 min-height:100vh 双滚动条——四模块同批布局修复（登记来源：style-optimization-proposal §4.7 新增 / §6.3 重写，执行 2026-10-08）

> **登记来源**：`vue-assetmanagement/docs/style-optimization-proposal.md` §6.3（原建议条，本次按实际改动重写为修复记录）与 §4.7（本次新增记录）；起因为用户 UI bug 任务「列表页横向滚动条埋底」，方案经三轮迭代定为 v3（四模块 + 门禁 + 文档收尾）。
> **性质说明**：**布局缺陷**（可用性受损，非功能断裂），纯前端模板/样式层修复，无 API 与枚举变更。

### 〇、元信息

- **登记日期**：2026-10-08
- **来源**：style-optimization-proposal §6.3/§4.7 + EP 2.13.7 源码取证
- **关键程度**：P1（16 个 CommonList 列表页 + 分组汇总/子表 + 8 个详情页站点 + 2 个系统页，合计 ~27 页受影响）
- **影响范围**：`CommonList.vue`、`GroupedAssetTable.vue`、`GroupedAssetChildTable.vue`、`common-forms.scss`、6 个详情 .vue、`UnregisteredAssetBasicDetails.scss`、`BasicAssetDetails.scss`、`RoleManage.vue`、`AuthUserManage.vue` 及 4 个 spec（含新建 `asset/__tests__/GroupedAssetChildTable.spec.ts`）+ 孤儿 spec 修复
- **跨端契约**：无影响（纯前端；无端点/字段/枚举变更 → **无需重导出 schema 基线**）

### 一、问题现象

1. 16 个列表页 el-table 横向滚动条锚在页面内容最底端，须先纵向滚到底才能拖动（本条主诉）。
2. 资产分组汇总表与其展开子表同型：横条埋在展开区内容底部。
3. 8 个详情页站点双滚动条：父容器 `AssetDetails.vue` 已 `height:100% + overflow-y:auto`，页面自身仍 `min-height:100vh`。
4. `RoleManage` / `AuthUserManage` 视口级 `100vh` 与 `.common-main{overflow:hidden}` 冲突：内容在主区外溢而非主区内自滚。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 列表页横条埋底 | el-table 未钉 height → EP 根 `height: fit-content`（EP `theme-chalk/src/table.scss:15`），body-wrapper = 内容全高；横条 `position:absolute; bottom:2px`（`scrollbar.scss:58/:60`），而纵向滚动发生在祖先容器 → 横条随内容沉底 |
| 2 | 修复路径约束 | EP `style-helper.mjs:191` `props.height` 分支直接返回 `{height:"100%"}` 无扣减；`:192` 数值 maxHeight 走减法；`:193` 字符串 maxHeight 走 `calc(值 - 表头)` —— 百分比入 calc 无参照系 = 双重扣减死带，故**弃用百分比 max-height、子表取数值 500** |
| 3 | CSS-only 不可行 | 无 height/max-height prop 时 EP `updateScrollY` 因 `layout.height=null` 直接返回（前置会话取证 `table-layout.mjs:29-35`）→ 必须用 EP prop，不能纯样式钉 |
| 4 | 详情页双滚 | mixin `common-forms.scss:127` `min-height:100vh` + 7 处本地同值冗余覆盖，均与父容器自滚叠加 |
| 5 | 系统页偏差（执行中发现） | `routes-main-system.ts:156/:168` 两页 `showPageHeader:true` → `.common-main` 内页头/面包屑为先行 flex 兄弟，`height:100%` 会把页面顶出被 `overflow:hidden` 裁掉（原计划字面写法有缺陷） |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| M1 | el-table 钉 `height="100%"`（单一咽喉点，覆盖 16 页）；spec stub 补 `height` prop + 新增回归断言 | `CommonList.vue:20`、`CommonList.spec.ts:109-113`、`CommonList.selection.spec.ts` |
| M2 | 分组汇总方案 A：根盒 flex/overflow（`:284/:286`）+ `__body` 包裹层 `flex:1;min-height:0;overflow:auto`（`:25/:291-292`）+ 表 `height="100%"`（`:34`）+ 分页 `flex-shrink:0`（`:350-351`）；子表 `max-height="500"`（`:36`）；汇总 spec 新增 3 断言，新建子表 spec | `GroupedAssetTable.vue`、`GroupedAssetChildTable.vue`、`GroupedAssetTable.spec.ts`、**新** `asset/__tests__/GroupedAssetChildTable.spec.ts` |
| M3 | mixin `:127` → `min-height:100%`（8 处 include 统一生效）；删 7 处本地冗余 `100vh`；无 mixin 的 `BasicAssetDetails.scss:7` → `100%` | `common-forms.scss`、6 详情 .vue、`UnregisteredAssetBasicDetails.scss`、`BasicAssetDetails.scss` |
| M4 | `min-height:100vh` → `flex:1; min-height:0; overflow-y:auto`（对根因 5 的修正形，占页头下剩余空间、自滚、横条可达） | `RoleManage.vue:279`、`AuthUserManage.vue:345` |
| M5 | 门禁阶段发现的孤儿 spec 修复（方案 A，用户拍板）：按同目录 EP stub 模式重写，4 条占位/崩溃用例全部转真断言 | **新** `__tests__/GroupedAssetTable.statusTag.spec.ts`（untracked，从未入库） |

### 四、对抗审核

- **行号漂移**：上表全部 `file:line` 为本日 `rg` 实测（CommonList:20、GAT:25/34/284/286/291-292/350-351、child:36、common-forms:127、RoleManage:279、AuthUserManage:345、routes-main-system:156/168、EP table.scss:15、scrollbar.scss:58/60、style-helper.mjs:191/192/193、defaults.mjs:77、CommonList.spec:109-113）。
- **计划偏差两处（均已向用户显式报告）**：① M4 原计划 `height:100%`，实测 `showPageHeader:true` 兄弟节点事实后改 flex 等价形；② 孤儿 spec 经 `git stash` HEAD 对照证明**非本批回归**、`git log --all` 无记录、创建时间 13:23:55 落在 coverage 窗口但全仓无写文件测试代码 → **创建者无法确认（Fact-1）**，未臆断。
- **同类重复登记**：`rg "滚动条|min-height: 100vh|100vh" 活账本` 0 命中，无既有条目。
- **契约影响**：无请求/响应形状变更；schema 基线无需重导出（纯前端样式/模板）。
- **变异测试豁免**：经用户拍板（2026-10-08）——本批仅 template/styles/specs，与 stryker 范围（`src/stores/**`、`src/composables/useGroup*.ts`）零交集。
- **验证边界（诚实标注）**：全部自动化门禁已执行（见五）；**浏览器视觉目验未执行**，`min-height:100%` 在 auto-height 父级的退化、固定列表格 tooltip 定位 `[推测]` 两项依赖目验，见六。

### 五、验证记录

```text
① 模块级 vitest：M1=24 passed、M2=15 passed、M3 相关 74 passed、孤儿 spec 修复后 4/4 passed ✅
② 前端三项：type-check exit 0 / lint exit 0（--fix 无额外改动）/ format:check exit 0 ✅
③ build（SCSS 真编译，含 M3 mixin 修改）：成功 ✅
④ 全量 test:coverage：exit 0，150/150 files、2049/2049 tests；
   statements 92.97% / branches 87.62% / functions 87.64% / lines 93.78%（整体≥80 ✓，stores 90 glob 无 threshold error）✅
⑤ 残留 grep：detils/ 下 min-height:100vh = 0；RoleManage/AuthUserManage 100vh = 0 ✅
⑥ 浏览器视觉验收：未执行（无浏览器工具），清单见六
```

### 六、遗留与关联事项

- **[待确认] 视觉验收清单**（需浏览器执行）：≥2 个代表页长短表格各一（短表格背景变化波及全部 16 页）；分组汇总+子表横条位于可视底边、固定列、三态复选、分页完好；详情页无双滚动条；RoleManage/AuthUserManage 矮页填满/高页可达/窄窗内滚可达；固定列 + show-overflow-tooltip 表格内滚时 tooltip 定位 `[推测]`；`min-height:100%` 在 auto-height 父级是否退化。**2026-10-08 尝试执行受阻**：computer-use 运行时（PowerShell `Add-Type`）被 Machine 级 `LIB` 失效路径（`C:\Program Files\MySQL\MySQL Server 8.0\lib`，目录不存在）打断，且该环境固化于 8:37 启动的 Orca 常驻进程组——修复需重启 Orca（会终止当次会话），经用户裁定改期人工目验，继续挂账。
- **暂缓项 1（本次刻意不动）**：`common-forms.scss:23` form-container 的 `min-height:100vh`（约 5 站点），需逐父级审计后另立任务。
- **暂缓项 2**：RoleManage/AuthUserManage 表格 fit-content 不吃满根高的同权优化（与列表页 CommonList 形态对齐）。
- 孤儿 spec `GroupedAssetTable.statusTag.spec.ts` 创建者无法确认（见四）；文件为 untracked，本次方案 A 修复后随批提交入库。
- 关联登记：`style-optimization-proposal.md` §4.7 新增 / §6.3 重写 / 优先级表 P1 布局缺陷行标注；`complete-patterns.md` **A-48**（v2.9.57，「详情页样式块重复 mixin」值级重复已关闭）。

*登记人：opencode ｜ 状态：已关闭（四模块落地 + 门禁全绿；浏览器目验与两项暂缓未做，已如实标注），2026-10-08*

---

## BF-076 【已关闭】详情页状态列缺值 StatusTag 告警 + 分组子表 el-pagination 弃用属性 small——同一展开验收会话双修复（EP 渲染告警域，用户裁定合并登记）

> **登记来源**：BF-075 手工验收会话衍生（用户先回执「告警消失」，随后展开分组发现 el-pagination 弃用告警；两条同属「EP 渲染告警」根因域、同一验收会话，经用户裁定合并为本条）。
> **性质说明**：纯前端模板层防御/兼容修复，无 API、枚举、样式视觉变更（`size="small"` 与布尔 `small` 在 EP 内部产出同一 `_size` 值）。

### 〇、元信息

- **登记日期**：2026-10-08
- **来源**：用户手工验收 Console 输出 + EP 2.13.7 实装源码取证（声明 `^2.10.5` / 实装 `2.13.7`）
- **关键程度**：P2（①防御性消噪 + 契约金丝雀保留；②第三方弃用告警，EP 3.0.0 将移除）
- **影响范围**：`AssetContentDetails.vue`（2 插槽）、`GroupedAssetChildTable.vue`（1 属性）、2 个 spec；受影响页面 = 资产详情页平铺/分组两态 + 全部分组展开场景
- **跨端契约**：无影响（纯前端模板；无端点/字段/枚举变更 → 无需重导出 schema 基线）

### 一、问题现象

1. 展开资产分组时 Console 出现 `[StatusTag] Invalid status "undefined"` 告警（BF-075 验收会话中发现，证据回顾确认后端 `group_children` 全部行含 `asset_current_status: "in_store"`，数据链路无缺失）。
2. 同一会话点击展开图标后新增：`[el-pagination] [API] small is about to be deprecated in version 3.0.0, please use size instead`（堆栈落在 `useDeprecated → watch.immediate → debugWarn`）。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | StatusTag 缺值告警 | `AssetContentDetails.vue` 两处 `#asset_current_status` 插槽将 `row.asset_current_status` 直传 `StatusTag`，缺值时 `props.status=undefined` → `StatusTag.vue:62-66` `Object.keys(map).includes(undefined)` 判否 → `logWarn`。**观测真源的证据链在修复前未钉死**（汇总行不消费该槽——`AssetGroupSummary` 无此字段且汇总列走 `summaryCell` 文本渲染；6 组 children 全有值），属防御缺口（陈旧状态/异常路径兜底） |
| 2 | `?? 'unknown'` 方案否决 | `'unknown'` 不在 `ASSET_STATUS_MAP` 键集，传入仍触发 logWarn（仅改文案）→ 唯一零告警解是 v-if 条件渲染（不实例化），同时保留金丝雀：真值但未映射的新状态仍会 logWarn |
| 3 | el-pagination 弃用告警 | `GroupedAssetChildTable.vue:89` 裸布尔属性 `small` → EP `pagination.mjs:120-122` `useDeprecated({...}, computed(() => !!props.small))` immediate watch 即告警；**存量代码**（真分页子表提交引入，非 BF-075 批回归——该批仅改本文件 `:36` max-height），在本批展开验收时首次被观察到 |
| 4 | 等价性依据 | EP `pagination.mjs:115` `_size = computed(() => props.small ? "small" : props.size ?? _globalSize.value)` → `size="small"` 与布尔 `small` 产出同值 `"small"`，视觉零变化；仓内先例 `DepartmentEmployeeList.vue:183` 已用 `size="small"` |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| R1 | 两插槽加 `v-if` 守卫 + `—` 占位（缺值不实例化 StatusTag，零告警；占位与项目 NULL_DISPLAY 形制一致）；守卫收口渲染出口，链路不加映射（DR-1，避免第二状态处理点） | `AssetContentDetails.vue:35-36`（分组槽，经真实 GAT `$slots` 转发覆盖子行）、`:88-89`（平铺槽） |
| R2 | 裸 `small` → `size="small"`（全仓裸 `small` 站点仅此一处，`^\s+small\s*$` 单命中） | `GroupedAssetChildTable.vue:89` |
| R3 | CT-4 回归屏障：① enableGrouping.spec 补 `vi.mock('@/utils/logger')`（importOriginal 兜底，logWarn/logError 收 spy）+ 可变行源 `activeRows`/`activeChildRows` + GAT 桩 `$slots` 透传渲染 + 两条缺值用例（平铺 `:284`、分组 `:299`）；② child spec 补分页属性用例（`:70`，组件级 `findComponent` 断言 `size="small"` 且无 `small` 属性，复用 `total:120` 既有夹具） | `AssetContentDetails.enableGrouping.spec.ts`、`GroupedAssetChildTable.spec.ts` |

### 四、对抗审核

- **分组用例落点偏差（对批准计划的一处修正，已报告）**：原计划分组子行用例放 `statusTag.spec`——实查该文件 `:167-168` 的插槽是**复刻副本**（`?? ''` 包装），在彼处断言锁的是桩而非生产代码（CT-4「绿而无效」陷阱）。改放 enableGrouping.spec：GAT 桩以 `$slots` 透传渲染真实 AssetContentDetails 模板，语义对齐真实 `GroupedAssetTable.vue:45-47` 转发。
- **先红后绿两轮实证**：① StatusTag——`git stash` 仅还原本组件（HEAD=修复前）→ 2 条新用例 FAIL（StatusTag 数 3≠2 / 2≠1，既有 14 条不受扰）→ pop → 16/16 绿；② 分页——先加用例跑红（`attributes('size')` 收 undefined，spec:74 FAIL）→ 改属性 → 绿。
- **行号漂移**：全部 `file:line` 为本日实测（插槽 :35-36/:88-89、child :89、spec :70/:284/:299、EP pagination.mjs:115-122、DepartmentEmployeeList:183）；修复后裸 `small` 残留 grep `^\s+small\s*$` = **0**。
- **影响面**：无任何 spec 断言 `small` 属性（仅 `cache.spec.ts` 含无关 "small" 词）；既有分页断言只查 `.child-pager` 存在性，不受影响——实测 4 spec 36 passed 佐证。
- **同类重复登记**：活账本 `rg "Invalid status|about to be deprecated"` 登记前 0 命中（无既有条目）；非重复代码模式，`complete-patterns.md` 无需登记（G-1~G-5 不适用）。
- **契约影响**：无；schema 基线无需重导出。**变异测试豁免**：沿用 2026-10-08 用户拍板口径（template/specs 与 stryker 范围零交集；门禁值 80 出处 `stryker.config.json:15-19`）。

### 五、验证记录

```text
① 先红后绿×2（见四，含 stash 对照与 spec:74 红态输出）✅
② 定向 vitest：child/GAT/statusTag/enableGrouping 4 文件 36 passed ✅
③ 前端三项：type-check exit 0 / lint exit 0 / format:check exit 0 ✅
④ 全量 test:coverage：exit 0，150/150 files、2052/2052 tests（2051+1 新增）；
   statements 92.97% / branches 87.62% / functions 87.64% / lines 93.78%（≥80 ✓）✅
⑤ 手工验收（用户 Console 回执）：① StatusTag 告警确认消失（2026-10-08 回执，
   据此因果闭环——观测告警确系本页插槽出口之一）；② el-pagination 告警确认消失
   （2026-10-08 用户「验收通过」同批涵盖回执，见 BF-077 §五⑦）
```

### 六、遗留与关联事项

- **[✅已回执] ②号告警**：2026-10-08 用户「验收通过」同批涵盖本项（告警消失、分页条尺寸观感不变），回执记录见 BF-077 §五⑦。
- **可疑路径留档**：若 StatusTag 告警再现，按 module 字段排查 `AssetLogsView.vue:51`（`item.status`，经 `getAssetTimeline` 映射）与 `ScanAssetView.vue:45`——本次未动（用户回执消失后主诉已闭环）。
- **计划偏差存档**：分组用例落点由 statusTag.spec 改为 enableGrouping.spec（见四，理由充分且已报告）。

*登记人：opencode ｜ 状态：已关闭（①②均已回执消失，2026-10-08 同批验收涵盖），2026-10-08*

---

## BF-077 【已关闭】详情页二维码恒 404：getQrCodeImageUrl 漏写 router 前缀层，单层 /assets/ 不匹配真实 /assets/assets/ 路由（登记来源：用户详情页报障 Console 404，Q-03 收敛产物后续修正）

> **登记来源**：用户报障「详情页二维码不显示，Console `GET .../qr-code-image/ 404`——没生成还是生成了没取到？」；系审查报告 Q-03（2026-09-26 收敛至 API 层）产物的后续缺陷，双向交叉引用见 `docs/Review/opencode-2026-09-25-检查报告.md` 修复追踪 Q-03。
> **性质说明**：纯前端 URL 构造修复（构造器 1 行 + 注释），后端零改动，无 API/枚举/响应结构变更。

### 〇、元信息

- **登记日期**：2026-10-08
- **来源**：用户手工验收 Console 输出 + Django 路由层 curl / `reverse()` 双分实测
- **关键程度**：P2（详情页二维码展示与下载整链路不可用；资产主数据流不受影响）
- **影响范围**：`src/api/asset.ts:373/:375-376/:381`（构造器与注释）、`src/api/__tests__/asset.spec.ts:211`（断言）
- **跨端契约**：无破坏——前端向后端既有 `reverse()` 真实路由对齐；后端零改动（`git status --short asset_management_backend` 为空）→ 无需重导出 schema 基线

### 一、问题现象

1. 详情页二维码区域空白，Console：`GET http://localhost:5173/api/v1/assets/ASSET-20261004-3D35550B/qr-code-image/ 404 (Not Found)`。
2. 用户设问「未生成 or 已生成未取到」——实测**两者皆否**（见根因 #4：该端点按需实时生成、无存量图片；404 发生在路由层，请求未进视图、未到生成环节）。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 真实路由为双 `assets` 段 | `config/urls.py:159` `path("api/v1/assets/", include(...))` + `apps/assetmanagement/urls.py:49` `router.register(prefix="assets", ...)` 自带 `^assets/` 前缀 → `manage.py shell` 实测 `reverse('assets-qr-code-image')` = `/api/v1/assets/assets/ASSET-X/qr-code-image/` |
| 2 | 构造器漏一层 | 修复前 `asset.ts:379` 写 `${BASE_URL}/assets/`（单层）→ 拼出 `/api/v1/assets/{code}/qr-code-image/`，Django 解析层不匹配 → DEBUG 技术 404（curl 实测 `text/html`、99355 字节、`Page not found at ...`），**未达 get_object、未达生成环节** |
| 3 | 全站孤例 | 全仓 `/assets/assets/` 字面量 98 处、跨 9 文件（`asset.ts:92/:129/:157` 等），唯原 QR 构造器为单层；且 `<img src>` 不经 request 实例（原注释 `:374`），request 层路径校验覆盖不到该 raw 拼串 |
| 4 | 二维码按需生成 | PNG 由 `asset_service.py:380-407 generate_qr_code_image` 请求时实时生成，无落库无存量 → 「生成了没取到」不成立；`qr_code` 字段（`models/asset.py:208`）存扫码内容 JSON，与本端点无关 |
| 5 | 认证非因 | 登录设 `asset_access_token` Cookie（`cookie_utils.py:38`，SameSite=Lax `config/settings/base.py:250`）同域自动携带；双前缀探测返回 401 JSON（已达视图认证层）佐证 404 属路由层而非鉴权层 |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| R1 | CT-4 先红：断言期望改双层 `https://api.test/api/v1/assets/assets/RC001/qr-code-image/` | `asset.spec.ts:211` |
| R2 | 构造器 `${BASE_URL}/assets/` → `${BASE_URL}/assets/assets/`；同步修正 JSDoc 端点 URL 并加双段来历注释（config 挂载点 + router 前缀） | `asset.ts:373/:375-376/:381` |
| R3 | 调用点全量 grep `getQrCodeImageUrl` = 5 处（实现 1、store 代理 1、消费 1、断言 1、接口声明 1），单一出口确认，改断言一处即覆盖 | — |

### 四、对抗审核

- **先红后绿实证**：改期望 → targeted vitest **1 failed**（红态原文 `Expected: .../assets/assets/RC001/...` / `Received: .../assets/RC001/...`，`asset.spec.ts:211`）→ 修构造器 → **22/22 passed**。
- **行号漂移**：全部 `file:line` 为修复后/当日实测（`asset.ts:381` return、`:373` 注释、`asset.spec.ts:211`；根因侧 `config/urls.py:159`、`assetmanagement/urls.py:49`、`asset_service.py:380-407`、`models/asset.py:208`、`cookie_utils.py:38`、`base.py:250`）。
- **残留扫描**：raw `BASE_URL}` 构造器全仓 4 处复核——`asset.ts:381` ✓ 双层；`tokenRefresh.ts:79/:116` `/auth/token/refresh/` 实测 `GET → 405`（路由存在、POST-only，正确）；`useNotificationConnection.ts:80` 为 WS 非 HTTP。修复后单层 `/assets/` raw 拼串 **0 处**。
- **同类重复登记**：活账本 `rg "qr-code-image|二维码"` 登记前 0 命中；URL 缺层是缺陷而非重复模式，`complete-patterns.md` 不登记（G-1~G-5 不适用，同 BF-076 口径）。
- **交叉引用**：审查报告「修复追踪 Q-03」已追加后续修正行 + 修正段，与本条互指；Q-03 收敛本身成立，缺陷在收敛产物的路径字面值。
- **变异测试**：stryker 范围（`src/stores/**` + `src/composables/useGroup*.ts`，`stryker.config.json:8-19`）与本次文件零交集 → 沿用 2026-10-08 用户拍板豁免口径。
- **契约影响**：无；schema 基线无需重导出（后端零改动）。

### 五、验证记录

```text
① 先红后绿：targeted vitest 改期望后 1 failed（Received 单层 / Expected 双层）→ 修构造器后 22/22 passed ✅
② 前端三项：type-check exit 0 / lint exit 0 / format:check exit 0 ✅
③ 全量 vitest run：150/150 files、2052/2052 tests，exit 0 ✅
④ 全量 test:coverage：exit 0；statements 92.97% / branches 87.62% / functions 87.64% / lines 93.78%（≥80 ✓）✅
⑤ 路由双分实测（修复前取证）：单前缀 /api/v1/assets/{code}/qr-code-image/ → 404 HTML；
   双前缀 /api/v1/assets/assets/{code}/qr-code-image/ → 401 JSON；
   reverse('assets-qr-code-image') = /api/v1/assets/assets/{code}/qr-code-image/ ✅
⑥ 残留 grep：raw BASE_URL 单层 /assets/ 拼串 0 处 ✅
⑦ 手工验收：✅ 已回执（2026-10-08 用户验收通过——二维码显示、下载可用、Console 无 404；
   同批验收涵盖 BF-076② 分页告警项）
```

### 六、遗留与关联事项

- **[✅已回执] 手工验收**：2026-10-08 用户验收通过（二维码显示、下载可用、Console 无 404）；同批验收涵盖 BF-076②。
- **观察项① 双 `assets/assets/` URL 形态**：系 config 挂载点与 router 注册前缀叠加的历史 wart（`config/urls.py:159` + `apps/assetmanagement/urls.py:49`）；修正需动任一侧挂载 = **§3 跨端契约变更（HALT）**，且全仓 98 处字面量与后端 reverse 测试均依赖现状 → 本次不动，留档待架构决策。
- **观察项② 陈旧注释缺 `v1`**：JSDoc 中 `/api/assets/`（应为 `/api/v1/assets/`）**48 处、跨 13 文件**（`asset.ts` 15、`contract.ts` 6、`lostAsset.ts` 5、`repairAsset.ts` 5、`outAsset.ts` 4、`harddiskSn.ts` 3、`recycleAsset.ts` 3、`assetType.ts` 2、`damagedAsset.ts` / `storage.ts` / `wasteAsset.ts` / `types/operationlog.ts` / `types/recycleasset.ts` 各 1）——纯注释不改行为，不属本票范围，待批后统一刷新（用户最初提示 `:97/:118` 两处，实测全量 48 处）。

*登记人：opencode ｜ 状态：已关闭（自动化门禁全绿 + 手工验收已回执 2026-10-08），2026-10-08*

---

## BF-078 【已关闭】分组表四需求批：汇总列序勾选前置（需求1）+ onExpandChange 归一化不连带展开（需求2）+ 分组页返回状态恢复（需求3）+ 单条组取消自动展开（需求4）（登记来源：用户四需求点单，方案经批准后分四阶段执行）

> **登记来源**：用户对分组展开表格的四需求点单（跨 2026-10-07/08 两轮会话）。其中需求2 用户裁定为 Bug（「不应连带展开」），需求3 的验收条目 AC-67j 用户拍板「补」，需求4 对既有 AC-67e 做反向修订。方案批准后按阶段1（需求4）→ 阶段2（需求1）→ 阶段3（需求2）→ 阶段4（需求3）执行，本条为整批收口登记。
> **性质说明**：纯前端改动（组件 / composable / 新增 Pinia store / 路由守卫一行），后端零改动 → 不触碰 API 响应根结构、状态枚举、分页参数名、日期格式四契约，schema 基线无需重导出。

### 〇、元信息

- **登记日期**：2026-10-08
- **来源**：用户四需求点单 + 批准方案（含用户裁定：需求2=Bug、AC-67j=补）
- **关键程度**：P2（分组视图交互一致性与导航往返体验；资产主数据流与后端 API 不受影响）
- **影响范围**：vue 子仓 10 文件修改（408+ / 57−）+ 4 新文件；根仓文档 A 档四处（本条 + 方案书 §3.12.12 + AC-67e/67j + complete-patterns A-49）
- **跨端契约**：无破坏——纯前端；`git status` 后端目录为空 → 无需重导出 schema 基线

### 一、问题现象

1. **需求1（列序）**：汇总表列序为 展开 → 勾选 → 序号，勾选列不在最左，与平铺列表（勾选列最左）的操作起点不一致。
2. **需求2（连带展开）**：折叠分组 A 后展开分组 B，A 被连带复活。用户裁定：不应连带展开，属 Bug。
3. **需求3（返回恢复）**：分组视图进入资产详情 / 编辑表单 / 批量导入子路由再返回，筛选、页码、展开态、组内子页、勾选、滚动位置全部丢失（grouped 子路由不在 keep-alive 覆盖内，返回即重挂载重新首载）。
4. **需求4（单条组自动展开）**：`asset_count === 1` 的组首载自动展开（F2 设计），用户点单取消该行为。

### 二、根因

| # | 环节 | 事实 |
|---|------|------|
| 1 | 模板列序 | 勾选列（`width=55 fixed=left`）排在展开列（`type=expand`）之后（HEAD 实测 `GAT` 旧模板：展开块在前、勾选块随后） |
| 2 | `expand-change` 载荷未归一化 | 处理器直接消费 EP 回调 `(row, expandedRows)`，`expandedRows` 集合在「用户点击 vs 受控回放」两场景语义不一致，折叠态被重新写入；且两 spec 的 `expandGroup` helper 共载与真实 element-plus@2.13.7 不符的 `true` 载荷（真实为 `[row]`），桩宽容掩盖了缺陷（测试侧重复登记 A-49） |
| 3 | 路由重挂载无状态保持 | `/main/assetdetails/grouped` 无 keep-alive，状态只存于组件内存，返回即重建首载 |
| 4 | F2 自动展开 | `useGroupedAssetList` 的 `autoExpandSingletons()` 在 `fetchSummaries` 成功后对 `asset_count === 1` 的组逐个 `setExpanded(k, true)` |

### 三、修复方案

| # | 变更 | 文件 |
|---|------|------|
| R1 | 勾选列模板块移至展开列之前（列序 = 勾选 → 展开 → 序号），`GAT:41` 注释留痕 | `GroupedAssetTable.vue:41-60` |
| R2 | `onExpandChange` 载荷归一化（仅目标行翻转，不连带）；两 spec `expandGroup` helper 统一为真实载荷 `(row, [row])` 并注释实证 | `GroupedAssetTable.vue`、两 spec |
| R3 | 会话快照三件套：新增 `groupedAssetSession` store（save / clearPending / clear + `GroupedPageSnapshot`）；新增 `useGroupedSessionRestore` 恢复编排（顺序契约 ①搜索→②页码→③展开→④子页→⑤勾选 + DOM 滚动存取）；`AssetContentDetails` 分组模式 `onBeforeRouteLeave` 存档 + setup 期读取传 `initialSnapshot`；`guards.ts` afterEach 导航出 `/main/assetdetails` 前缀时失效会话 | 2 新文件 + `AssetContentDetails.vue` + `guards.ts` + `GroupedAssetTable.vue`（prop/expose/水合） |
| R4 | 删除 `autoExpandSingletons()` 及其 `fetchSummaries` 调用，单条组一律默认折叠；`useGroupChildrenCache` 注释同步摘除「自动展开」字样 | `useGroupedAssetList.ts`、`useGroupChildrenCache.ts` |
| R5 | 两 spec 头部覆盖清单同步（GAT 补用例 15~19，enableGrouping 补 BF-078 会话 ×4） | 两 spec 头注释 |

### 四、对抗审核

- **先红后绿实证**：① 需求4——`git stash push` 暂存修复后的 `useGroupedAssetList.ts`（还原 HEAD 自动展开实现）跑反向锁，**2 failed / 32 passed**（`does not auto-expand groups with asset_count === 1` / `> 1` 双双转红）→ `stash pop` 恢复后全量 2075 全绿。② 需求2——阶段3 先做 helper 归一化（红）再改 `onExpandChange`（绿）。③ 需求3——`useGroupedSessionRestore.spec` 以调用顺序断言 + `changePageSpy` 屏障锁死恢复次序。
- **变异测试（本轮复跑，2026-10-08）**：`npm run test:mutate` 总分 **82.29 ≥ break 80**（37 文件 / 2002 mutants / 18m11s）。新文件全在 `stryker.config.json` 射程（`src/stores/**` + `src/composables/useGroup*.ts`）：`groupedAssetSession.ts` **9 killed / 0 survived**（1 Ignored，与前轮一致）；`useGroupedSessionRestore.ts` **18 killed / 0 survived**——前轮 2 个幸存突变（`if snapshot.page > 1` 的等价变形 `"true"` / `>= 1`）经 `changePageSpy` 断言（页码 1 时不得调 changePage、页码 2 时须 `toHaveBeenCalledWith(2)`）**全部击杀**，新文件幸存清零。
- **行号漂移**：本条全部 `file:line` 为 2026-10-08 当日实测；根因侧 HEAD 旧行为经 `git show HEAD` 取证（GAT 旧模板列序、两 spec 旧载荷 `row, true`、`autoExpandSingletons` 函数体）。
- **残留扫描**：`autoExpandSingletons` / `自动展开` 语义在 `src/` 残留仅 AC 无关的注释同步处（`useGroupedAssetList.ts` docstring 已改为「同样默认折叠」）；`(row, true)` 旧载荷 0 处。
- **重复登记**：测试侧双份 `expandGroup` helper 收敛入 **complete-patterns A-49**（v2.9.58）；本条缺陷本身非重复模式，不单列。
- **规模与护栏**：`check_frontend_invariants.py` PASS（composables 53 文件 / stores 31 文件 0 违规，FR-6/FR-8 达标）；`check_duplicate_invariants.py` PASS（G-1~G-5 未受扰）。
- **契约影响**：无——不触碰 §3 四项跨端契约；后端零改动。

### 五、验证记录

```text
① 前端三项：type-check exit 0 / lint exit 0 / format:check exit 0 ✅
② 全量 vitest run：152/152 files、2075/2075 tests，exit 0（较 BF-077 同日基线 2052 净增 23）✅
③ 全量 test:coverage：exit 0；statements 93.01% / branches 87.66% / functions 87.69% / lines 93.81%
   （≥80 ✓）；src/stores/** 97.84 / 92.39 / 94.37 / 98.22（≥90 ✓）✅
④ 前端双护栏：check_frontend_invariants.py PASS（composables 53 / stores 31 文件 0 违规）；
   check_duplicate_invariants.py PASS（G-1~G-5）✅
⑤ 变异复跑：npm run test:mutate → 82.29 ≥ 80（37 文件 / 2002 mutants / 18m11s）；
   groupedAssetSession.ts 9 killed / 0 survived（1 Ignored）、useGroupedSessionRestore.ts 18 killed /
   0 survived（前轮 2 幸存经 changePageSpy 断言击杀）✅
⑥ 先红后绿：需求4 stash 还原 HEAD 实现 → 反向锁 2 failed；恢复后绿。
   需求2 阶段3 helper 归一化红 → onExpandChange 归一化绿 ✅
⑦ 浏览器目验：一轮（2026-10-08）需求2 ✓ 需求4 ✓、需求1 ✗ 需求3 ✗（详见 §七）；二轮修复后复验
   需求1 ✓ 需求3 ✓（用户回执 2026-10-08，硬刷新实测）——四需求全部通过 ✅
```

### 六、遗留与关联事项

- **手工目验**：已闭环——一轮 需求2/4 ✓、需求1/3 ✗；二轮修复后复验需求1 ✓ 需求3 ✓（用户回执 2026-10-08），本条翻转【已关闭】。
- **观察项① 滚动恢复走 DOM 直读**：element-plus 表格只暴露 `setScrollTop()` 无 getter，存档只能读 `.el-scrollbar__wrap.scrollTop`；EP 后续若提供 getter 应收敛（当前注释留痕）。
- **观察项② 分组/平铺两套状态保持机制并存**：设计意图上平铺视图靠 keep-alive、分组视图靠会话快照（组件无缓存）。注意：平铺侧 keep-alive 配置**实为死配置**（include 名永不匹配，从未生效，见 **BF-079**）——平铺当前实际无缓存，状态保持只有分组快照在工作。两机制的边界（`/main/assetdetails` 前缀失效规则）由 `guards afterEach` 统一裁决，后续若第三种视图引入需复用该裁决而非自设。
- **关联**：**A-49**（测试侧 helper 收敛）、**AC-67e 反向修订 + AC-67j 新增**（`07-功能需求与验收标准.md:287/:317`）、方案书 **§3.12.12** 落地证据。

### 七、目验一轮失败与二轮修正（2026-10-08）

**一轮目验结果（用户浏览器实测）**：需求2 ✅ 折叠 A 展开 B 不连带；需求4 ✅ 单条组默认折叠；需求1 ✗ 列序实测仍为 勾选→序号→展开（模板搬移无可见效果）；需求3 ✗ 返回分组页 = 初始状态（展开全收起）。

**二轮根因（读源码核验，非推测）**：

| # | 现象 | 根因事实 |
|---|------|---------|
| 需求1 | 模板搬移无效 | Element Plus 固定列渲染序 ≠ 声明序：`element-plus/es/components/table/src/store/watcher.mjs` `updateColumns` 按 `[fixed-left 组（声明序）] + [非 fixed 组] + [fixed-right 组]` 重排（`fixedColumns = filter(fixed∈[true,'left'])` → `originColumns = concat(fixed, notFixed, right)`，实测该文件 86-88 行区域）。展开列无 `fixed` → 沉入非固定组 → 可见序 = [勾选, 序号] + [展开…]，与用户实测逐字吻合。用例15 断言的是桩的声明序 → 假绿（桩/EP 语义漂移，A-49 同族问题） |
| 需求3 | 「无 keep-alive 即重挂」假设错误 | `AssetDetails.vue:12` 的 `<router-view>` 无 `:key`；vue-router `h(ViewComponent, …)` 亦不带 key（`dist/vue-router.js:1107`）→ grouped 与 `:asset_code?` 两条子路由同组件、同 router-view 位置 → Vue patch 复用实例、setup 永不重跑 → `initialSnapshot` const 冻结为首挂时的 `null` → GAT 重挂走常规 `search()` 首载。此前把复用风险归因 keep-alive 的注释（`routes-main-core`）与真实机制不符；且 MainView keep-alive include 名与实渲染 vnode 名不匹配（死配置，登记 **BF-079**） |

**二轮修复（R6/R7）**：

| # | 变更 | 文件 |
|---|------|------|
| R6 | 展开列补 `fixed="left"`（左冻结栈 55+48+80=183px）；`GAT:41` 注释订正为「声明序仅在 fixed-left 组内生效，三列必须全为 left-fixed」；用例15 重写为 EP 重排口径断言 | `GroupedAssetTable.vue:41/60`、`GroupedAssetTable.spec.ts` |
| R7 | 方案 A″：`AssetDetails` 的 `<router-view :key="childViewKey">`，`childViewKey = matched[findIndex('AssetDetails')+1].name`——grouped/详情互换必重挂，孙路由 assetform 不变 key（扁平→表单既有复用保留）；消费守卫 `props.enableGrouping && session.pendingRestore && session.snapshot`（分组→表单直跳时平铺挂载不摘旗）；`routes-main-core:44-49` 归因注释订正 | `AssetDetails.vue`、`AssetContentDetails.vue:200`、`routes-main-core.ts`（仅注释） |

**二轮红绿取证（先证红后证绿）**：

- **T-R1**：用例15 改为「按 EP 重排规则计算可见序后断言」→ 红（`expected '' to be 'left'`，333 行）→ R6 → 绿（GAT spec 18/18）。
- **T-R2**：预置恢复旗 + `enableGrouping:false` 挂载 → 红（`expected false to be true`，现码提前摘旗）→ 消费守卫 → 绿（enableGrouping spec 21/21）。
- **T-R3a**：真 router（`createMemoryHistory`，路径镜像真路由）grouped→详情→grouped 断言 setup 计数 =3 → 红（`expected 1 to be 2`，实例复用实证）→ key → 绿（AssetDetails spec 3/3）。
- **T-R3b/c**（用户拍板要求的两条不变量锁，双侧绿）：b 扁平→assetform→扁平 ACD 层 setup 计数不变（防 key 误伤孙路由）；c 真 `setupAuthGuard` + 真 session store——分组→表单直跳与返回分组均保留恢复旗、出 `/main` 子树清除（guards.spec:278-291 为 mock 级同断言，此为真接线收口）。

**二轮门禁（2026-10-08）**：前端三项 type-check / lint / format:check 全 exit 0；全量 vitest **153/153 files、2079/2079 tests** exit 0（较一轮 +4 用例 +1 文件）；coverage exit 0（statements 93.01 / branches 87.66 / functions 87.69 / lines 93.81，`src/stores` 97.85 / 92.39 / 94.37）；双护栏 PASS。变异：本轮改动（3 `.vue` + `routes-main-core.ts` 注释）均在 `stryker.config.json` mutate 射程（`src/stores/**` + `src/composables/useGroup*.ts`）**之外** → 82.29 基线沿用（CT-7 同工具链声明）。

**T-R1 语义边界声明（用户拍板要求，如实标注）**：用例15 把 EP 重排规则镜像进测试，防的是「改回声明序 / 去掉 fixed」这类回归；**EP 升级若改变重排语义，本用例防不住**——最终裁决以浏览器目验为准，本节即为该层留痕。

**二轮目验**：✅ 通过——用户浏览器实测（硬刷新）需求1 列序与左冻结三列、需求3 返回状态恢复均符合预期（回执 2026-10-08）；需求2/4 一轮已验 ✓ 且二轮改动不触及其路径。

*登记人：opencode ｜ 状态：已关闭（门禁全绿 + 两轮浏览器目验闭环），2026-10-08*

---

## BF-079 【观察项·未修复】detail 路由 keepAlive + componentName 死配置：MainView keep-alive 的 include 名永不匹配实渲染 vnode，「扁平详情列表缓存」意图从未生效（登记来源：BF-078 需求3 二轮诊断附带发现，用户拍板「立账本条目、本次不动代码」）

> **登记来源**：BF-078 二轮诊断中核验「返回分组页为何不重挂」时发现——当时旧注释把实例复用归因于 keep-alive，读码后确认真实机制是 router-view 无 key（已随 BF-078 §七 修复），而 keep-alive 侧则根本不匹配、从未缓存。用户拍板（2026-10-08）：**立账本条目登记观察，本次不改代码**——删 include 或删 keep-alive 涉及 MainView 缓存策略意图考证（波及 Contract/AssetType/Storage/User 等同构路由），与 BF-078 范围无关，登记观察项成本最低。

### 〇、元信息

- **登记日期**：2026-10-08
- **来源**：BF-078 需求3 二轮诊断（读码核验）
- **关键程度**：P3（当前零功能损伤——死配置等价于「不缓存」，行为可预期；风险在于未来依赖误解）
- **影响范围**：零代码变更（纯登记）
- **跨端契约**：无涉（纯前端路由配置层）

### 一、事实（全部 file:line 可静态查证）

| # | 事实 | 证据 |
|---|------|------|
| 1 | MainView 的 keep-alive include 列表 = 当前路由 matched 中 `meta.keepAlive` 记录的 `meta.componentName` | `MainView.vue:105-112` |
| 2 | detail 路由声明 `keepAlive: true` + `componentName: 'AssetContentDetails'` | `routes-main-core.ts:68-69` |
| 3 | keep-alive 按被缓存 vnode 的组件 `name`/`__name` 匹配 include；MainView 层 router-view 实渲染的 vnode 是容器 `AssetDetails`（`<script setup>` SFC 推导 `__name='AssetDetails'`，无显式 name） | `AssetDetails.vue`（无 name 选项）、Vue keep-alive include 匹配规则 |
| 4 | `'AssetDetails' ≠ 'AssetContentDetails'` → **永不匹配 → 该子树从未被缓存**；grouped 路由无 keepAlive（include 空）时同样零缓存 | 1+2+3 推论 |
| 5 | 连带影响：`routes-main-core` 旧注释曾把分组/扁平复用风险归因 keep-alive——所依赖的机制不存在；真实复用机制（router-view 无 key）已随 BF-078 R7 修复，注释已订正 | `routes-main-core.ts:44-52`（订正后）、`vue-router.js:1107` |

**证据强度声明**：以上为静态读码 + 框架规则推论，**未做运行时断点/DevTools 缓存命中取证**（观察项级别，不值得为登记单独起运行时验证；若立项修复则修复前后各取一次运行时证据）。

### 二、影响

- 原始意图「平铺详情列表 keep-alive 缓存」从未生效：详情/子路由切换始终全新挂载。当前与 BF-078 分组会话快照机制无冲突（快照机制本就不依赖缓存）。
- 隐藏坑：后续开发者若看到 `keepAlive: true` 而以为该子树有缓存并依赖之（如往组件实例塞状态期待跨路由存活），会踩空。

### 三、处置（用户拍板）

- **本次不动代码**：修复方向二选一——① 修匹配（为 AssetDetails 设显式 `name` 或改 componentName 对齐）② 删死配置（MainView include 与各路由 meta 同步清理）。两者都需先考证 MainView 缓存策略的原始意图及其对 Contract/AssetType/Storage/User 四条同构路由的影响，属独立小立项。
- 关联：**BF-078 §七**（复用真相与注释订正）、BF-078 观察项②（已标注 keep-alive 实为死配置）。

*登记人：opencode ｜ 状态：观察项（未修复，待立项考证后决定修匹配或删配置），2026-10-08*

---

## BF-080 【已关闭】分组子区固定操作列缩窗遮挡：父汇总表横滚裁掉展开行右段，子表 sticky 钉在屏幕外的子滚动口（登记来源：用户目验报障，根因读源码核验）

> **登记来源**：用户目验报障（2026-10-09）——窗口缩小到一定量后，group-children 子区的固定操作列（fixed=right）被遮挡，左右滑动**子表**滚动条也不出现；父汇总表的固定操作列却始终贴屏幕右缘。
> **性质**：纯前端布局缺陷；后端零改动 → 四项跨端契约无涉，schema 基线无需重导出。

### 〇、元信息

- **登记日期**：2026-10-09
- **来源**：用户浏览器目验
- **关键程度**：P2（组内操作入口可达性；不触资产主数据流）
- **影响范围**：vue 子仓 3 文件（`useGroupedAssetColumns.ts`、`GroupedAssetTable.vue`、其 spec）
- **跨端契约**：无破坏——纯前端列宽数值与测试

### 一、现象

窗口缩至约 1400px 以下时，子区操作列被裁出屏幕；子表横滚条滑到底也救不回来；同窗口下父汇总表操作列正常贴右。

### 二、根因（嵌套滚动口裁剪，读源码核验非推测）

| # | 事实 | 证据 |
|---|------|------|
| 1 | EP 固定列 = `position: sticky` + 内联 `right:0`——sticky 只对**最近的滚动口**生效 | `element-plus/theme-chalk/src/table.scss:338`；`table/src/util.mjs:318 getFixedColumnOffset` |
| 2 | 父汇总表 Σ 列宽 = 1193 + 页面开销 ≈233px（侧栏200+主区16+滚动条17）→ 窗口 ≲1426px 时父表内容超宽、自身出横滚 | 列宽实测；`GroupedAssetTable.vue:358-361` `.grouped-asset-table__body { overflow:auto }` |
| 3 | 展开行 td colspan = 全表内容宽 → 父横滚时其右段被父滚动口裁出屏幕，子表滚动口右缘随之在屏幕外 | EP 展开行结构 |
| 4 | 子表 sticky 操作列钉在**子滚动口右缘**（屏幕外）；子表自己的滚动条只移内容、移不动滚动口本身 → 怎么滑都不出现 | sticky 规范 + 1~3 推论，与用户实测吻合 |
| 5 | 父表操作列正常，因父滚动口右缘 = 屏幕右缘 | 对照现象 |

### 三、修复（列宽预算，Σ 1193 → 1031）

| # | 变更 | 文件 |
|---|------|------|
| R1 | 汇总数据列压缩：contract 150→128、name 180→144、spec 180→144、brand 120→96、price 140→112；**asset_count 100 不动**（数量胶囊）；汇总表 tooltip 保持（扫描面不换行，与前轮口径一致） | `useGroupedAssetColumns.ts` |
| R2 | 汇总序号 80→64（与子表同款），模板注释留痕 | `GroupedAssetTable.vue:91` |
| R3 | **预算回归锁（CT-4）**：GAT spec 新用例 `mountTable()`（默认空汇总，子表列零渲染污染）→ 读**模板真实渲染 props** `Σ(width || minWidth) ≤ 1031`——composable 列集与模板硬编码结构列（55/48/64/140）同口径计数，加列/加宽/序号回改即红；`ElTableColumnStub` props 补 `minWidth`（1 行） | `GroupedAssetTable.spec.ts` |

**预算物理式**：`Σ1031 + 开销≈233 → 父横滚阈值 ≈1264px`——1280/1366 常规窗口父表不出横滚 → 展开行恒在屏内 → 子表 sticky 行为与父一致；折叠侧栏再 +136px。富余宽度由 fit 摊回长文本列，全屏观感更宽。

**否决留痕**：① 子区整体 sticky 右移——整块子区会相对汇总列左移错位、与父固定左列叠放语义冲突；② 重构 EP 展开结构（子表抽离展开行）——改动面过大。

### 四、对抗审核（先红后绿）

- **红①（结构列计数证明，用户补充关切点）**：序号临时回 80 → 预算用例红 `expected 1047 to be ≤ 1031` → 恢复 64。
- **红②（composable 计数）**：name 临时回 180 → 红 `expected 1067 to be ≤ 1031` → 恢复 144。
- **绿**：恢复后 GAT spec 19/19、全量 2081 全绿。
- **测试面**：`useGroupedAssetColumns.spec` 只锁 label、GAT spec 原无宽度断言（grep 实证）→ 改宽度零回归冲突。
- **断言口径**：读渲染 props 而非常量——不为测试重构模板字面量为共享常量，且更贴现实（模板被改回即红）。

### 五、验证记录

```text
① 前端三项：type-check 0 / lint 0 / format 0（首轮 format 红 → prettier --write 修复复绿）✅
② 全量 vitest：153/153 files、2081/2081 tests，exit 0（+1 预算用例）✅
③ 复杂度：eslint complexity ≤ 10 → 0（三改动文件）✅
④ 变异（CT-7 全量补跑，2026-10-09）：`npm run test:mutate` → **82.35 ≥ 80**，24min10s，exit 0（基线 82.29 → +0.06，新预算用例增杀 mutant）✅
⑤ 浏览器目验：一审回执 2026-10-09——1366/1280 全屏第 1/2 项通过；≲1264（侧栏展开）第 3 项**否决**（要求子操作列与父组同机制常驻贴右）→ 见 §七 二轮
```

**CT-7 变异声明**：`useGroupedAssetColumns.ts` **匹配** `stryker.config.json` mutate 模式 `src/composables/useGroup*.ts`（非射程外），故本轮已按 `package.json` 声明工具链**全量复跑** `npm run test:mutate`：**82.35 ≥ 80**，exit 0（2026-10-09 实测）。

### 六、遗留与边界

- **~~物理下限~~（一轮结论，已被二轮推翻，2026-10-09 留痕）**：原判「≲1264px 遮挡复现为列集总宽所限、无法压到 0，1024 级需另行点单」——**一审目验否决**（用户拍板：任意宽度下子区操作列必须与父组操作列同机制常驻贴右），二轮以面板锚定消除，见 §七；「1024 另行点单」边界同步作废。
- **[✅已闭环] 目验**：一审 1/2 通过、3 否决 → 二轮面板锚定修复后用户回执**通过**（2026-10-09，清单①-④见 §七），本条翻转【已关闭】。
- **关联**：**BF-078 §七**（同表格嵌套链路的上一轮根因）、B1 轻压（子表阈值）、方案书 **§3.12.12 补三行/补四行**。

### 七、二轮修复（2026-10-09：目验否决物理下限 → 面板锚定，任意宽度子操作列常驻）

**根因再定位（读源码复核，非推测）**：

| # | 事实 | 证据 |
|---|------|------|
| 1 | EP 固定列 `position: sticky !important` + `z-index: calc(var(--el-table-index)+1)`，钉**最近滚动口** | `element-plus/theme-chalk/src/table.scss:330-340` |
| 2 | 展开格 `td.el-table__expanded-cell` 无 overflow 裁剪（仅背景） | `table.scss:104-105` |
| 3 | 父横滚发生在 **EP 内部滚动口**（el-table 盒宽恒 100%，Σ1031 溢出在 EP wrap 内）；`.grouped-asset-table__body` 自身不横滚 | `GroupedAssetTable.vue` 样式段 + 一审红态实证 |
| 4 | 子操作列钉**子表自滚动口**（`max-height=500` 的 body-wrapper）右缘——该口随面板被裁出屏即失守 | `GroupedAssetChildTable.vue:36,80` |

**结论**：子表滚动口右缘 ≡ `.group-children` 面板右缘 → 只要面板恒 ≤ 可视宽，子表 sticky 即与父列同机制贴屏右。**修面板，不动子表、不动列宽，一轮预算锁零触碰。**

**修复（方案甲，纯 CSS 2 行）**：

1. `.grouped-asset-table__body` += `container-type: inline-size`——cqw 值恒等于该容器内容盒宽 = EP 滚动口可视宽；`inline-size` 不含 block 轴，`flex:1/min-height:0`/分页链路不受影响（containment 理论核验 + 目验③回归）。
2. `.group-children` += `position: sticky; left: 0; width: min(100cqw, 100%)`——宽屏（未横滚）取 `100%` = td 内容宽，与一审通过项**逐像素一致**；窄屏取 `100cqw` 收为可视宽 → 子表滚动口全在屏内，子操作列、子左列同步免遮挡。

**补充核验（用户三点补充落位）**：
- **右缘溢出**：`global-reset.scss:9-13` 对 `*` 全局 `box-sizing: border-box`，面板 padding16 + border4 含于宽度、无 margin（`.child-wrap` 亦无）→ 右缘**零像素溢出**；残余 ≤32px 缝仅在 `visible∈(999,1031)` 且已滚动时出现，露 `expanded-cell` 不透明底（非内容渗漏），归目验①观察。
- **containment 安全**：`inline-size` 仅行内轴，`flex:1/min-height:0` 高度链与分页条无涉（目验③覆盖）。
- **锁口径**：jsdom 无布局 → `?raw` 读 SFC 源断言三关键串 + 目验兜底，诚实组合。

**CT-4 源码锁（先红后绿）**：红证 = 临时删 `width: min(100cqw, 100%)` 行 → `AssertionError: expected '<!--...' to contain 'min(100cqw, 100%)'` → 恢复后 20/20 绿。首版 `import.meta.url` 路径方案因 vitest 下非 file scheme 报 `TypeError: The URL must be of scheme file`，改 `?raw` 导入修复（机制红亦留痕）。

**二轮门禁（2026-10-09 实测）**：前端三项 type-check / lint / format **0/0/0**；complexity ≤10 → 0；全量 vitest **153/153 files、2082/2082 tests** exit 0（+1 源码锁）；变异：改动为 `.vue` 样式 + spec，在 `stryker` 射程（`src/stores/** + src/composables/useGroup*.ts`）**之外** → **82.35 基线沿用**（CT-7 声明）。

**[✅] 二轮目验：通过**——用户浏览器实测回执「通过」（2026-10-09）：① 侧栏展开 1280/1024 子操作列贴屏右可点；② 全屏与一审通过态一致；③ 父横滚/分页/子表横滚/勾选/编辑正常；④ 暗色模式正常。

**回退预案**：目验若发现 cq 异常 → 方案乙 `ResizeObserver → --gat-visible-w`，宽度改 `min(var(--gat-visible-w), 100%)`，其余不变。

*登记人：opencode ｜ 状态：已关闭（两轮门禁全绿 + 双红/源码锁取证 + 两轮浏览器目验闭环），2026-10-09*
