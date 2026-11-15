# 全项目代码审计报告（CodeGraph 增强）

> 审计日期：2026-11-11
> 审计范围：`asset_management_backend/` + `vue-assetmanagement/src/`（架构、框架、函数、对象、逻辑、UI/界面）
> 审计模式：**只读审计**（全程未改动任何业务代码）
> 规则基线：根 `AGENTS.md` v3.7.7、`Rules_Fiels/backend-business-rules.md`、`backend-testing-rules.md`、`frontend-business-rules.md`、`frontend-testing-rules.md`
> 图谱基线：`codegraph status` → 1,141 files / 19,599 nodes / 45,645 edges，索引 up to date

---

## 一、项目上下文

### 1.1 技术栈

| 端 | 技术 |
|---|---|
| 后端 | Django + DRF，SimpleJWT 双通道（用户 / 员工），Channels，PostgreSQL（生产）/ SQLite（测试） |
| 前端 | Vue 3 + TypeScript + Element Plus + Pinia + Vue Router + ECharts + Vite |

### 1.2 模块边界

- 后端 4 个业务 app：`assetmanagement`、`usermanagement`、`unregisteredasset`、`authusermanagement`，公共层 `core/`、`utils/`。
- 资产域分层：`models → selectors → services → serializers → views`，状态机独立包 `state_machine/`。

### 1.3 分域清单

| 分域 | 锚点 | 本次结论 |
|---|---|---|
| 资产状态机 | `state_machine/constants.py`、`transitions.py`、`core.py` | 与规则文档一致，无未声明旁路 |
| 合同状态机 | `state_machine/contract_fsm.py` | 未被本次改动触及，未见异常 |
| API 响应契约 | `utils/response_utils.py` | 唯一入口，未见手写 dict 旁路 |
| 前端状态枚举 | `types/asset.ts`、`types/outasset.ts` | 与后端 8 态键名一致 |
| 鉴权 / RBAC | `core/permissions.py`、各 views | 权限收口良好，未见仅 `IsAuthenticated` 的写端点 |
| 操作日志 / 批量 | `services/operation_log_service.py`、`asset_lifecycle_mixin.py` | 事务 + 审计 + 并发锁齐备 |
| 前端 UI | `styles/variables.css`、`dark.css`、`stores/app.ts` | 存在主色令牌不一致（见台账） |

---

## 二、问题台账

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 |
|---|---|---|---|---|---|---|---|
| F-01 | P2 | UI / 设计令牌 | `src/store/app.ts:99-103`；`src/styles/variables.css:4`；`src/main.ts:18` | `initAppState` / `--el-color-primary` | 亮色主题未在 CSS 定义 `--el-color-primary`；仅当 `localStorage.primaryColor` 存在时才由 JS 设置。新用户/清缓存首屏 Element Plus 组件回落默认 `#409eff`，与品牌主色 `#2b5fd7` 并存形成双蓝 | 在 `variables.css` 的 `:root` 增加 `--el-color-primary: var(--color-primary)`（含 light-3/5/7/8/9 派生）；或 `initAppState` 在无存储时也调用 `setPrimaryColor(DEFAULT)` | `codegraph node initAppState` |
| F-02 | P2 | 设计令牌 | `variables.css:4-7,94-96`；`dark.css:10`；`variables.css:134-137` | `--color-primary*` | 亮色主色为 `#2b5fd7`，但 `--color-primary-light/-lighter/-light-mid/-light-lighter/-light-border` 仍为 Element 默认蓝族（`#409eff/#ecf5ff/#66b1ff/#79bbff/#d9ecff`）；暗色整体改用 `#4a90e2`，同一"主色"概念多源异色（已知 C-9，文档标注待产品决策，未闭环） | 以 `#2b5fd7` 生成 tint/shade 阶梯（或 `color-mix`）；暗色若需提亮须单独定义并显式登记，避免与亮色色相并列 | `rg -n "--color-primary" src/styles/variables.css` |
| F-03 | P3 | 状态一致性 / 死代码 | `src/stores/app.ts:117-137` | `resetAppState` | 重置只改响应式状态：未移除 `html.dark` class、未复位 `--el-color-primary`、未更新 `document.title`；且全仓仅测试调用，属未接线的公开 API | 复用 `setTheme` / `setPrimaryColor` 完成 DOM 副作用，或删除未使用的方法 | `codegraph node resetAppState` |
| F-04 | P3 | 文档漂移 | `GuideDocumentation/设计审计核验.md:64-67` | — | 文档称 `!important` 63 处，实测全仓仅 8 文件 8 处（C-10 已大幅收敛）；维护者据此估工会失真 | 更新文档或标注"已收敛" | `rg -n "!important" src` |
| F-05 | P3 | 测试 / 覆盖率 | — | — | 本地全量 `pytest --cov` 未取得权威覆盖率（套件执行缓慢，24% 处耗时数分钟；此前并发运行出现 setup 错误）。结论以 CI `ci.yml` 为准，CI 就绪前按 CT-2 标 `[PENDING]`（**【2026-11-15 标注：该 `[PENDING]` 已由 M-21 撤销——门禁已在 ci.yml 固化阻断，见 AGENTS.md v3.7.8 §1.4，绿态 run https://github.com/aquarius-cc/AssetManagementProgram/actions/runs/43623471892 】**） | 在 CI 固化覆盖率门禁（已落地，PR #2）；本地用单模块 `--cov` 增量核对 | `python -m pytest --cov=apps --cov=core --cov-fail-under=80` |

> 台账状态：F-01、F-02 **待修**（F-02 需产品决策）；F-03、F-04、F-05 **待修**（低优先；**F-05 已于 2026-11-15 由 M-21 关闭——CI 覆盖率门禁固化、`[PENDING]` 撤销，见 AGENTS.md v3.7.8**）。本报告不产生"已修复"状态（F-05 关闭标注为 M-21 收口留痕，非本报告执行）。

---

## 三、分域结论与修复建议

### 3.1 资产状态机（CT-3）— 合规

- `VALID_TRANSITIONS` 覆盖 8 态全部合法路径，`AssetFSM._transition` 只改 `asset_current_status`，保存/事务/审计由 Service 承担，分层正确。
- 全仓 `asset_current_status =` 赋值仅出现在 `state_machine/` 内（`core.py`、`out_recycle.py` 特殊方法、`scrapping.py` 终态、`unregistered.py` 已声明例外）与只读序列化字段，**未发现 Service/View 层直写旁路**。
- `out_recycle.py` 的 `cancel_outasset`/`cancel_recycle`/`checkout` 均带前置状态断言，`scrapping.py` 强制终态断言，属文档化的特殊回退路径。
- 建议验证：`pytest apps/assetmanagement/tests/test_state_machine.py`（本次抽样运行全绿）。

### 3.2 跨端契约（根 §3）— 合规

- 响应根结构：View 统一走 `success_response`，未见手写 `{"code":...}`。
- 分页：全链路 `page` / `page_size`，前端 `DEFAULT_PAGE_SIZE` 单一常量，`max_page_size` 兜底。
- 枚举：`AssetState` 8 键与 `types/asset.ts`、`types/outasset.ts` 一致。
- 日期：`DATE_FORMAT` 与 `DATETIME_FORMAT` 均为 ISO 8601 含时区偏移。
- `CustomPageNumberPagination` 的 `next/previous` 为绝对地址，部署于反代后需确认 `SECURE_PROXY_SSL_HEADER` 生效（现网已配置，未见问题）。

### 3.3 安全红线（SC-1~SC-8）— 合规

| 项 | 结论 | 证据 |
|---|---|---|
| SC-1 密钥硬编码 | 仅测试/开发配置有 `SECRET_KEY='test'` 类占位，生产强制读环境变量，无真实密钥 | `config/settings/production.py`、`test.py` |
| SC-3 参数化查询 | 无 `raw()` 拼接；`cursor.execute("SELECT 1")` 与动态表名（`sql.Identifier`）均安全 | `core/health.py`、`scripts/clear_database.py` |
| SC-5/SC-6 上传 | 无文件上传落盘端点（Excel 走内存解析），条目 N/A | `rg "request.FILES\|FileField"` → 无业务命中 |
| SC-8 依赖漏洞 | 本地未复跑 audit，以 CI `security-scan.yml` 为权威门禁 | 见 §五 |
| OC-6 健康端点 | `/health`、`/ready` 存在 | `config/urls.py` 引用的健康视图 |

补充：生产配置 `DEBUG=False`、SSL 重定向、HSTS、安全 Cookie、CORS 白名单且 `allow_credentials=False`、登录限流 5/min、公开扫码独立限流，均符合预期。

### 3.4 架构与 DRY（DR-1~DR-6）— 合规

- 护栏全部通过：`check_file_length_guard`、`check_function_length_guard`、`check_frontend_invariants`、`check_duplicate_invariants`。
- 最大后端文件 `views/asset_view.py` 485/500 逻辑行，余量偏薄；后续新增 action 前需先拆分（DR-5 从紧）。
- 服务层并发与事务：`select_for_update` 覆盖 update/repair/recycle/outasset/damaged/生命周期 mixin；写方法普遍 `@transaction.atomic`。
- 通知仅经 `send_notification_on_commit`，未见事务内直接 `notify`；操作日志异常为"记录后重抛"，不吞没。
- 前端类型集中于 `types/`，格式化集中于 `utils/Format.ts`，未见重复定义。
- 前端 `.vue` 直接 `@/api` 导入仅 `DegradedCacheBanner.vue:26` 一处，且为读取 `degradedCacheKeys` 常量而非发请求，不构成分层违规。

### 3.5 前端 UI / 界面 — 发现 2 项 P2

- 组件化充分：最大视图 `LogIn.vue` 11.7KB，其余均 <9KB；`<script setup lang="ts">` 全覆盖，无 Options API。
- 无组件内直接 axios/fetch；`console.*` 仅存在于 `utils/logger.ts` 包装与测试。
- 定时器（`useDashboardPage`、`useNotificationConnection`、`useMergedDataSources`）均有 `onUnmounted` 清理；`useNotificationConnection` 具备断线重连与退避。
- **F-01 / F-02** 为本次唯一实质性 UI 缺陷：亮色首屏 Element Plus 主色回落默认蓝；主色令牌族亮色不自洽、暗色换色相。二者均可在 `styles/variables.css` 一处收敛，改动面小、回归面可控。

### 3.6 测试与规模（CT-2 / DR-5 / DR-6）

- `npm run type-check`（vue-tsc --build）**通过**，零报错。
- 后端抽样：`core/tests/test_logging_console_trace.py` 7 passed；`apps/assetmanagement/tests` 顺序执行至 24%+ 全绿（无 failure），因套件较慢未跑完。
- 覆盖率权威数字以 CI 为准（F-05）。

---

## 四、修复优先级建议

1. **F-01（P2，先做）**：CSS 层补 `--el-color-primary: var(--color-primary)`，一处改动即消除新用户首屏双蓝。
2. **F-02（P2，需产品决策）**：主色阶梯统一；暗色是否允许提亮需拍板后落地。
3. **F-03（P3）**：`resetAppState` 复用 `setTheme/setPrimaryColor` 或删除。
4. **F-04 / F-05（P3）**：更新文档；CI 固化覆盖率门禁。

---

## 五、报告边界与未执行项（Fact-1）

- `pip-audit` / `npm audit`：本地未执行，以 CI `security-scan.yml` 为权威（SC-8）。
- 后端全量覆盖率：本地未取得（见 F-05），不声称具体百分比。
- 未做运行时/浏览器 UI 走查，界面结论基于源码与既有 `设计审计核验.md` 交叉核对。
- 本报告为只读审计产物，未修改任何业务代码。
