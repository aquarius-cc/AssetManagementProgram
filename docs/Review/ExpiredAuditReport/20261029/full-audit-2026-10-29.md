# 全项目审计报告（架构 / 逻辑 / 前端 / 部署合规）

- 审计日期：2026-10-29
- 审计模式：只读审计（未修改任何业务代码）
- 审计依据：根 `AGENTS.md` v3.7.1、`asset_management_backend/AGENTS.md`、`vue-assetmanagement/AGENTS.md`、`Rules_Fiels/*-business-rules.md`、`Rules_Fiels/*-testing-rules.md`
- 审计执行：project-all-code-review + code-quality-check + ponytail-review 三套方法论合并执行

---

## 一、审计方法与执行证据

| 检查项 | 命令 / 方式 | 结果 |
|---|---|---|
| 后端文件规模（DR-5/LT-1 逻辑行口径） | `python scripts/check_file_length_guard.py --print` | 通过；最大 488 逻辑行（`apps/assetmanagement/views/asset_view.py`） |
| 后端函数规模（BR-4） | `python scripts/check_function_length_guard.py` | 通过 |
| 前端不变量（F11/F12 等） | `python scripts/check_frontend_invariants.py` | 通过 |
| 重复代码不变量 G-1~G-3、G-5 | `python scripts/check_duplicate_invariants.py` | 通过 |
| API 文档一致性 | `python scripts/check_api_doc_consistency.py` | 通过 |
| 迁移一致性（CT-6） | `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| 状态机 + 行级隔离测试 | `pytest -q apps/assetmanagement/tests/test_state_machine.py apps/assetmanagement/tests/test_asset_selector_isolation.py` | 88 passed |
| 后端全量测试 | `pytest -q` | 本地运行到 45% 全绿后被手动终止（约 18 分钟），未取到全量结论；以 CI `backend-test` 为权威 |
| 前端类型检查 | `npm run type-check` | 通过 |
| 前端单元测试 | `npm run test -- --run` | 180 文件 / 2361 用例全部通过（276s） |
| 前端生产依赖漏洞 | `npm audit --omit=dev` | 0 漏洞 |
| 后端依赖漏洞 | `pip-audit -r requirements/base.txt` | 本地网络连接被重置，未取到结果；以 CI `security-scan.yml` 为权威 |
| 路由组件可解析性 | 解析 router 下 73 个动态 `import()` | 73/73 文件存在，0 缺失 |
| 大文件扫描 | 121 个 `.vue` 逐行统计 | 最大 `AssetContentDetails.vue` 物理 552 行 / 约 441 逻辑行，符合 FR-5 |

> 说明：本机 Python 3.13 与 CI/Docker 的 3.12 存在版本漂移，后端相关数字按 CT-7 仅作参考，不作 CI 基线。

---

## 二、整体框架与架构结论

### 2.1 架构分层（结论：健康）

```
前端 Vue3/TS
  router(73 懒加载组件) → views/components → composables(55) → stores(32, createEntityStore 工厂) → api(31, request.ts 统一拦截)
        ↓ HTTPS / Cookie(JWT) / /ws
后端 Django/DRF
  urls → views(权限/参数) → serializers(校验) → services(事务/业务) → selectors(查询收敛) → models(索引/约束)
        ↓
  PostgreSQL 16 + Redis 7 + Channels
```

- 后端严格五层，`services` 未反向依赖 `views`，`selectors` 未依赖 `services`/`serializers`（本次定向检索无命中）。
- 前端以 `createEntityStore` + `SmartListContainer` + `CommonList` 收敛列表逻辑，避免 20+ 个列表页复制粘贴，符合 DR-2/DR-4。
- 三个子模块（root / backend / frontend）以 git submodule 组织，CI 与部署均递归拉取，结构自洽。

### 2.2 资产状态机（结论：无旁路、可验证）

- 8 状态定义：`asset_management_backend/apps/assetmanagement/state_machine/constants.py`；转换表唯一事实源：`state_machine/transitions.py:32`；校验与落状态唯一入口：`state_machine/core.py:62`、`core.py:96`。
- 全库检索 `asset_current_status =` 赋值：仅 `core.py` 内写入，`views`/`services` 无直接写状态，未发现旁路。
- `out_recycle.py` 的 `cancel_outasset` 特殊回退在注释中显式声明「不在 VALID_TRANSITIONS」，与业务规则文档一致，属有意设计而非漏洞。
- CT-3 覆盖：`outasset / recycle / mark_broken / mark_lost / to_damaged / repair_done / repair_failed / found_and_return / reject_to_original` 9 类边在测试中均有引用（`apps/assetmanagement/tests/`，109 个测试文件）。

### 2.3 事务、并发与查询

- `services` 层共 44 处 `@transaction.atomic`、30 处 `select_for_update`，覆盖领用/回收/维修/报废/批量保存等写路径。
- 通知副作用统一走 `transaction.on_commit(..., robust=True)`，避免事务回滚后误发通知。
- 查询统一走 Selector，列表层使用 `select_related` 收敛人员关系，`Asset.Meta.indexes` 与唯一约束覆盖资产编码、状态等高频过滤字段。
- 分页由 `core/pagination.py` 强制分页，`MAX_PAGE_SIZE=100` 在后端生效。

---

## 三、问题台账

> 级别定义：P0 阻断/数据损坏/高危；P1 重要逻辑或上线阻断；P2 一般缺陷/规范偏离；P3 优化建议。

### 3.1 后端

| ID | 级别 | 类型 | 位置 | 问题 | 证据 | 修复建议 |
|---|---|---|---|---|---|---|
| B-01 | **P1** | 隐私/安全 | `asset_management_backend/apps/usermanagement/employee_serializers.py:43`、`:72`；`apps/usermanagement/views/employee_view.py:125` | 员工手机号明文返回给所有已登录用户：列表序列化含 `employee_phone`，详情 `fields = "__all__"`，而列表默认权限仅为 `IsAuthenticated` | `utils/` 已存在 `mask_phone_number` 但未被序列化器使用；导出功能反而刻意排除手机号 | 按角色分级：普通用户返回脱敏值（`138****0000`）；仅资产管理员/系统管理员在确需联系时返回明文；或拆分 `EmployeeContactSerializer` 仅用于授权表单 |
| B-02 | P2 | 安全 | `apps/assetmanagement/views/public_scan_view.py`（`throttle_classes` 仅默认 Anon/User 限流） | 公开扫码接口仅使用全局默认限流（20/min），无独立 scope，资产编码枚举空间在 1 小时内仍可被大量试探 | `config/settings/base.py` `DEFAULT_THROTTLE_RATES` 无 `public_scan` 项 | 新增 `ScopedRateThrottle` + `public_scan: 5/min`，并对连续 404 的 IP 做短时封禁 |
| B-03 | P2 | 代码质量 | `apps/assetmanagement/signals.py`（全文 0 逻辑行） | 文件仅剩历史注释，未被 `apps.py` 或任何模块 import，属死文件 | `grep import signals` 无命中；`line_metrics` 计 0 逻辑行 | 删除文件；如保留迁移说明，移入文档而非源码 |
| B-04 | P2 | 代码质量 | `core/pagination.py:6`、`:120-144` | 模块 docstring 声称「无参数时返回全部数据」，与实现（强制分页到 100）矛盾；末尾 25 行被注释的旧实现 | 模块头注释 vs `CustomPagination` 行为 | 删除 120-144 死代码，修正 docstring 为「强制分页、上限 100」 |
| B-05 | P2 | 测试 | `apps/*/tests/` | 全库仅 1 个测试文件使用 `assertNumQueries`，列表/详情接口缺少 N+1 回归断言，Selector 优化易被后续改动破坏 | `grep assertNumQueries` 命中 1 文件 | 对资产分组列表、生命周期列表补 2-3 条查询数断言 |
| B-06 | P3 | 复用 | `apps/assetmanagement/selectors/outasset_selector.py` | 纯兼容再导出壳（`from .out_asset_selector import *`），实际实现已收敛到 `out_asset_selector.py` | `selectors/__init__.py` 与 3 个测试仍引用旧名 | 更新 import 后删除壳文件，消除双入口 |
| B-07 | P3 | 数据一致性 | `apps/assetmanagement/selectors/asset_selector.py` `get_asset_detail_by_code` | 详情查询未带 `is_deleted=False`；当前唯一调用点（`asset_view.py` retrieve）前置已做可见性过滤，暂不构成漏洞，但属易踩坑的隐式契约 | 调用链：`get_assets_for_list` 先校验可见性 | 在 Selector 内显式过滤软删除，或改名 `get_asset_detail_by_code_including_deleted` 明确语义 |
| B-08 | P3 | 依赖 | `asset_management_backend/requirements/base.txt:115` | `sentry-sdk[django]>=2.0,<3.0` 未锁定精确版本，与其余全量 pin 的依赖策略不一致，影响可复现构建与审计 | 其余依赖均为 `==` | 锁定具体版本并纳入 renovate/周检 |

### 3.2 前端

| ID | 级别 | 类型 | 位置 | 问题 | 证据 | 修复建议 |
|---|---|---|---|---|---|---|
| F-01 | P2 | 契约一致性 | `vue-assetmanagement/src/composables/usePaginationSearch.ts:67`、`components/commoncomponents/CommonList.vue:143` | 可选每页条数含 200/500，而后端 `MAX_PAGE_SIZE=100`；用户选择后会被后端静默截断为 100，选择器跳回，产生「选了没生效」的交互错觉 | 后端 `core/constants.py` `MAX_PAGE_SIZE=100`，`core/pagination.py` 强制截断 | 两处改为 `[20, 50, 100]`；如需更大导出量，走独立导出接口而非列表分页 |
| F-02 | P2 | 打开性能 | `vue-assetmanagement/src/utils/excelExporter.ts:20` 及 6 个列表页静态 import（如 `OutAssetDetails.vue:113`） | ExcelJS（打包后约 1MB 独立 chunk）在每次进入列表页即被拉取，仅为点击「导出」时使用 | `manualChunks` 已将 exceljs 单列，但仍被静态依赖链提前加载 | 将 `import ExcelJS` 改为 `await import('exceljs')` 放入导出函数内部，使导出 chunk 按需加载 |
| F-03 | P2 | 测试覆盖 | `vue-assetmanagement/vitest.config.ts:50-57` | 121 个 `.vue` 中绝大多数零覆盖，组件层基线仅 语句 12.98% / 分支 11.66%；业务逻辑虽已下沉 composables（覆盖良好），但页面渲染/交互回归仍主要依赖人工 | 配置注释记录的实测基线 | 优先为资产详情、发放/回收表单、批量导入 3 类高风险页面补挂载测试；棘轮只升不降 |
| F-04 | P2 | 一致性/健壮性 | `components/DashboardDistribution.vue:9`、`DashboardAssetTrend.vue:9` | 直接 `import VChart from 'vue-echarts'`，绕过 `plugins/echarts.ts` 的按需注册；当前能用是因为同页 `DashboardStatusOverview` 触发了注册副作用，属隐式耦合 | `plugins/echarts.ts` 已导出注册后的 `VChart` | 统一从插件导入，去掉对同页组件加载顺序的依赖 |
| F-05 | P3 | 监控缺口 | 前端护栏 | `check_frontend_invariants.py` 不覆盖 `.vue` 行数，FR-5 仅靠人工；本次人工核算最大 441 逻辑行合规 | 脚本覆盖范围 | 将 `.vue` 逻辑行检查纳入前端护栏，避免后续膨胀无声越线 |

### 3.3 部署与上线合规

| ID | 级别 | 类型 | 位置 | 问题 | 证据 | 修复建议 |
|---|---|---|---|---|---|---|
| D-01 | **P1** | 上线阻断 | `asset_management_backend/docker-entrypoint.sh:5`、`:60`、`:67` | 脚本仅 `set -uo pipefail`（无 `-e`），`migrate` 与 `collectstatic` 未校验退出码；迁移失败后应用仍会启动，线上将以未迁移库对外服务 | 其余步骤（等待数据库、初始化数据）均有显式 `exit 1` | 迁移/静态收集追加 `|| exit 1`，或整体改为 `set -euo pipefail` 并对可容忍步骤显式 `|| true` |
| D-02 | **P1** | 上线阻断 | `docker/nginx/conf.d/default.conf.tpl:31-32`、`docker/nginx/scripts/renew.sh:18-24` | 全新服务器首次部署时 443 证书文件不存在，nginx 配置引用 `ssl_certificate` 将启动失败；certbot 脚本只在「证书已存在」时续期，无首次签发路径；部署文档也未给出签发步骤 | nginx 首次加载硬依赖证书；`renew.sh` 检测不到证书即跳过 | 增加首次签发流程（HTTP-01 webroot 或 DNS-01 `certonly`），并写入部署文档；或在 nginx 启动前生成临时自签证书占位 |
| D-03 | P2 | 镜像卫生/信息暴露 | `asset_management_backend/.dockerignore`；仓库跟踪 `.graphify_*.json`（5 个约 9.66MB）与 `.trae/`（115 个文件） | 生成物与 AI 工具配置被纳入后端仓库，并被 `COPY . /app/` 打进生产镜像，造成镜像膨胀与非业务文件外泄风险 | `git ls-files` 可检索到上述文件；`.dockerignore` 未排除 | 三处同时处理：从仓库移除、加入 `.gitignore`、加入 `.dockerignore` |
| D-04 | P2 | 仓库卫生 | 根目录 `process_image.py`（96 行）、`process_image2.py`（93 行） | 含个人桌面绝对路径的一次性去水印脚本，已被 git 跟踪，与项目无关 | `git ls-files` 命中；文件内容为本地路径处理 | 删除并加入 `.gitignore` |
| D-05 | P2 | 仓库卫生 | `asset_management_backend/package.json`（依赖 `docx` 9.6.1） | 后端仓库内存在无任何 JS/TS 使用方的 npm 依赖清单，属遗留脚本残留 | 全库检索无 `docx` 引用 | 删除 `package.json`、`package-lock.json` 及对应 `node_modules` |
| D-06 | P3 | 文档漂移 | `Project_Requirements/02-技术设计/08-部署与环境配置.md` | 文档中的 nginx 示例（13 行静态配置）与仓库实际生产模板（237+ 行、含 WebSocket/限流/备份）差异巨大；且前端构建小节未说明 `mkdir dist` | 文档与实际模板比对 | 以实际 `default.conf.tpl` 为准重写部署章节，补首次证书签发与备份恢复演练 |
| D-07 | P3 | 安全表述 | `vue-assetmanagement/src/stores/auth.ts`（移动端令牌持久化路径） | 令牌落 `localStorage` 前做的是 XOR 混淆而非加密，密钥随包分发，不能抵御 XSS；Web 端 httpOnly Cookie 通道不受影响 | 混淆函数与硬编码密钥留在前端包内 | 明确定位为「混淆，非安全边界」；移动端改为系统安全存储或短生命周期令牌 |

### 3.4 已达标项（无需整改）

- 生产配置：`DEBUG=False` 默认、`SECRET_KEY`/`ALLOWED_HOSTS` 缺失即 `ImproperlyConfigured` 快速失败；`SECURE_*` Cookie、HSTS/HTTPS 重定向、CORS 白名单均已落地。
- 数据库：PostgreSQL 16，`CONN_MAX_AGE=600`、`CONN_HEALTH_CHECKS=True`；迁移 69 个，`makemigrations --check` 无遗漏；历史迁移（`usermanagement/0015`）含 `RemoveField/RemoveIndex`，属已上线结构升级，回滚需备份，非本次阻断。
- CI：ruff / mypy strict / 复杂度 / 权限码 / API schema 破坏性变更 / 文档护栏 / 后端测试与变异测试 / 前端 lint+类型+复杂度+测试+变异 / 密钥扫描 / 依赖审计 / 汇总门禁，覆盖完整。
- 可观测性：`trace_id` 透传、结构化日志、脱敏、`/health`、`/ready`、Prometheus 指标均已实现（OC-4 实际超出当前 QPS 要求）。
- 安全红线：无硬编码密钥（仅测试用假密钥）、无 `.raw()/extra()/cursor.execute`、无文件上传面、公开接口响应最小化（仅 6 字段）。
- 部署编排：Dockerfile 非 root + HEALTHCHECK + daphne ASGI；compose 含 postgres/redis/nginx/certbot/backup/feishu-webhook；备份 Cron 已配置。

---

## 四、前端页面完整性与布局/交互评估

| 维度 | 结论 | 证据 |
|---|---|---|
| 页面完整性 | 需求文档清单中的登录、看板、资产详情（分组）、发放/回收/损坏/遗失/找回/维修/报废/已报废/未登记、合同、资产类型、仓库、组织/员工/联系人、账号权限、操作日志、通知、公开扫码均有实现 | 路由 4 文件 + 73 个懒加载 `import()` 全部可解析；17 个 views 均有路由引用，无孤儿页面 |
| 布局合理性 | 桌面侧栏 + 移动端抽屉双形态；面包屑、降级提示条、`keep-alive` 页面缓存均具备；样式使用设计令牌，`.vue` 中未检索到硬编码 `#fff/#000` | `src/views/MainView.vue:14/19/35/46/72-79` |
| 列表交互 | 统一 `v-loading`、分页 total/页码/页容量事件、失败提示；删除/批量操作具备二次确认；操作提交有重复提交护栏 | `CommonList.vue:18/85-88`、`SmartListContainer.vue:168-174`、`useOperationGuard` 被操作表单复用 |
| 接口契约 | 统一 `{code, message, data}` 解包；HTTP 层使用 `page/page_size`（`pageSize` 仅是组件内部命名）；CSRF 头由拦截器统一注入 | `src/api/request.ts:62-72` |
| 打开性能 | 路由全懒加载；服务端分页上限 100；打包已按 exceljs/echarts 分包；但 ExcelJS 被列表页静态引用导致提前加载（F-02） | `vite.config.ts:196` manualChunks |
| 数据一致性 | 前端 8 状态键与后端完全一致 | `src/types/asset.ts:44-55` 对齐 `state_machine/constants.py` |

---

## 五、ponytail-review（只删不增）

```
process_image.py / process_image2.py：delete。个人路径一次性脚本，与项目无关。
asset_management_backend/package.json + package-lock.json：delete。docx 依赖无任何使用方。
asset_management_backend/.graphify_*.json（5 个，9.66MB）：delete + gitignore。生成物。
asset_management_backend/.trae/（115 文件）：delete + gitignore。AI 工具配置不应进部署仓库/镜像。
apps/assetmanagement/signals.py：delete。0 逻辑行，无 import。
core/pagination.py:120-144：delete。注释掉的旧实现 25 行；顺带修正 :6 的错误 docstring。
apps/assetmanagement/selectors/outasset_selector.py:1-27：delete。纯再导出壳；更新 4 处 import。
excelExporter.ts:20：native/lazy。改为函数内 await import('exceljs')，页面首屏少 1MB。
CommonList.vue:143 + usePaginationSearch.ts:67：shrink。页容量选项删两项，消除与后端上限的矛盾。
net: 约 -170 行代码、-10MB 生成物、-115 个非业务文件。
```

---

## 六、上线合规结论（Go / No-Go）

**结论：有条件通过（Conditional Go），当前不建议直接上线生产。**

必须在上线前完成（3 项 P1）：

1. **D-01** 入口脚本对迁移/静态收集失败快速退出——否则迁移失败仍对外提供服务，属数据事故风险。
2. **D-02** 首次 TLS 证书签发路径与部署文档——否则全新服务器 nginx 无法启动。
3. **B-01** 员工手机号按角色脱敏——与项目既定隐私约束直接冲突。

建议同批处理（不进阻断门禁，但影响体验/质量评级）：

- F-01 每页条数选项与后端上限对齐；
- F-02 ExcelJS 改为按需加载（列表页首屏体积约降 1MB chunk）；
- D-03/D-04/D-05 仓库与镜像卫生清理；
- F-03 前端组件层覆盖率补强（优先 3 类高风险页面）。

满足以上 3 项 P1 后，项目在架构分层、状态机、事务并发、安全基线、CI 门禁、可观测性、部署编排七个维度均达到生产级要求，可进入灰度发布。

---

## 七、审计票

```markdown
[审计票 - 必填项]
- 读取规范：已读 根 AGENTS v3.7.1 & 后端/前端 AGENTS & Rules_Fiels 业务/测试规范
- CT-1[√] CT-3[√] CT-5[√] CT-7[√] — 状态机 88 用例通过 / 全边覆盖 / 本轮无失败用例 / 已标注本地 3.13 与 CI 3.12 漂移
- DR-1[√] DR-5[√] — 分层唯一实现 / 后端最大 488 逻辑行、前端最大约 441 逻辑行
- SC-1[√] SC-3[√] — 无硬编码密钥 / 无 raw SQL
- 跨端契约：未破坏（响应结构、8 状态键、page/page_size、ISO8601 均一致）
- 红线触发：无（本次为只读审计，无代码变更）
- 建议提交：否（仅产出本报告）

[审计票 - 自检项]
- 测试：CT-2[~]（前端 2361 用例通过、.vue 基线 12.98% 为记录值，本轮未重跑覆盖率）CT-4[√]（无修复）CT-6[√]（makemigrations --check 通过；历史破坏性迁移已识别）
- DRY：DR-2[√] DR-3[√] DR-4[√] DR-6[√]
- 安全：SC-2[√] SC-4~SC-8[~]（npm audit 0；pip-audit 本地网络失败，以 CI security-scan 为权威）
- 可观测性：OC-1~OC-3[√] OC-4[√] OC-5[√] OC-6[√] OC-7[~]（无基线对比）
- AI鲁棒性：AR-1~AR-5[√]（未生成新代码）
- AI行为：Fact-1[√]（所有结论附文件行号或命令输出；未执行项已标注）
- 写作风格：Style-1~Style-3[√]
- 覆盖率：后端未在本轮取得全量（CI 权威）；前端 .vue 基线 语句 12.98% / 分支 11.66%（TS/Store 分层阈值 80/90 已配置）
```
