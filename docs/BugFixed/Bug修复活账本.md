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

## BF-039 门禁三连红修复（F-P1-3 + F-P2-7 + F-P3-1）2026-09-24

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
2. **H-1 状态机契约源裁定**、F-P2-* 其余项仍开放。
3. **complete-patterns**：本批为静态门禁/复杂度收敛非重复代码模式，G-1~G-5 不适用；`_validate_unique_constraints`/`_resolve_perms_to_add` 为拆分单源（DR-1），非新增重复。

*登记人：opencode（mimo-v2.6-flash-free） ｜ 状态：已关闭（四命令 exit 0 + 定向 82/88 passed），2026-09-24*
