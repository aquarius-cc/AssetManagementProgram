# 融合审计报告（merge-audit-20261116）

> 日期：2026-11-16 ｜ 输入源：同日三份独立审计报告交叉比对融合
> A = `glm5.3-flash-codegraph-audit-2026-11-16.md`（14 条）
> B = `MiMo-V2.6-Pro+codegraph-audit-2026-11-16.md`（N-01~N-12 + 存量 M-17~M-20）
> C = `codegraph-audit-2026-11-16.md`（增量 8 条，含构建产物实测）
> 性质：纯审计融合，不改业务代码；修复移交 bug-surgical-fix / rigorous-dev。台账终态均为「已确认（待修）」。

## 一、三源对比结论

### 1.1 交叉重合项（4 组，归并）

| 组 | 来源条目 | 比对结论 |
|:--|:--|:--|
| G1 日志泄露（exc_info） | A-BE-6（notification/helpers.py:110-116）↔ C-BE-02（exception_handler.py:95,100） | 同型问题两个落点：on_commit 通知回调与全局异常处理器均 `exc_info=True` 违反 audit_failure「只记类型」口径。**归并一条，同批一次清干净**（排查是否还有第三处） |
| G2 Prometheus 中间件 | A-BE-11（探针流量计入指标）↔ C-BE-01（`<str:...>` 路径参数致标签高基数） | 同一文件（core/prometheus_middleware.py）两个独立缺陷。**归并一条**：高基数（C，P2）为主、探针排除（A，P3）为辅，同批治理 |
| G3 AuthUser 写权限口径 | A-BE-4（P2：B11 字面偏差，建议收敛具名权限类）↔ B-N-12（P3[推测]：建议产品确认后在 §4.2 补注例外） | **唯一矛盾组**：两报告事实一致（IsAuthenticated + 手工本人/管理员检查、敏感字段 read_only、无提权面），处置方向不同——A 主张改代码归一形态，B 主张文档澄清。**列拍板项 MA-13**：二选一（收敛权限类 / §4.2 矩阵补注例外），产品拍板后执行 |
| G4 /metrics/ 暴露 | A-BE-10（METRICS_TOKEN 默认空 = 匿名放行，无 fail-fast）↔ B 引 M-05（部署六步含 METRICS_TOKEN fail-closed 断言） | 同一风险，两报告落点互补：仓内已落地，**缺口在生产部署期执行与留痕**。归并为部署期必做项 |

### 1.2 时区同型项（跨报告归并）

B-N-03（前端 useDashboardPage.ts:150-160 `toLocaleTimeString` 按浏览器时区渲染，违反 M-15 单源约定）与 C-BE-03（后端 dashboard_selector.py:309、out_asset_selector.py:145 `date.today()` 取进程本地日期，容器 TZ=UTC 时每天 00:00–08:00 窗口偏一天）为**同一业务口径（Asia/Shanghai 单源）的两端缺口**。分批不合并：N-03 纯前端改动、回归面单 composable，列上线前必修；BE-03 涉及容器 TZ 策略决策，列治理批。

### 1.3 各源独有高价值项（本次融合新增覆盖）

- **C-FE-02（P2，最高优先）**：请求层缓存键不含用户身份 + `resetAuthState()` 不清缓存 → 同标签页换号后 4 个详情端点命中前用户缓存，绕过服务端权限判定（含部门数据范围）。唯一发现的**可利用**数据隔离缺口。
- **C-FE-01（P2）**：生产构建 `drop_console` 删除全部前端日志 sink + 无全局 errorHandler/unhandledrejection → 生产前端零诊断信息（C 以 `npx vite build` 产物实测直证）。
- **C-BE-05（P2）**：asset_lifecycle_mixin.py:97-98 幂等补建分支缺 `refresh_from_db()` → DRF DateField 对内存 datetime 断言失败抛 500（正常路径 :42-44 已补，补建分支遗漏）。
- **A-FE-2（P2）**：批量导入链前端无行数/大小上限（readExcelFile.ts:84-107 全量入内存），与导出域 EXPORT_MAX_ROWS 镜像模式不对称。
- **A-FE-3 + B-N-01 + B-N-02**：前端三块 DRY 债（导入提交管线三份同型 / dashboard 8 处内联 catch / 13 文件硬编码 ElMessage.error），同型一次清干净。
- **B-N-09**：factory_boy 已声明依赖全库零使用，测试规范 T2 条文与实践系统性背离，需拍板（整改或修条文）。
- **B-N-11**：.vue 覆盖率棘轮余量仅 0.03pt，微小波动即击穿门禁。

### 1.4 实测数据互证（无矛盾）

三份报告实测门禁互相印证：后端 2455 passed / 90.51%（A=C）；前端 2711 用例全过 / stores 96.82%（B=C）；状态机专项 C 实测 71 passed（A 按 def test 计 48 个函数，差异为参数化用例，不矛盾）；mypy --strict 0 error、ruff 0、前端三项检查 0（C，版本与 dev.txt 一致）；npm audit 0 vulnerabilities（C 本机实测通过，A 本机网络不可达未复现）；pip-audit 两侧均以 CI security-scan.yml 为权威。规模护栏全 PASS。覆盖率口径统一：本机数字仅讨论中间量，权威 = CI `$GITHUB_STEP_SUMMARY`（CT-7）。

## 二、融合问题台账（MA-01 ~ MA-24）

> 编号 MA-xx；「溯源」列标注来源报告与原编号。级别沿用：P0/P1 无（三源一致），P2 一般缺陷、P3 优化建议。

| ID | 级别 | 溯源 | file:line | 描述 | 修复建议 | 验证方式 |
|:--|:--|:--|:--|:--|:--|:--|
| MA-01 | P2 | C-FE-02 | vue-assetmanagement/src/api/request.ts:86,500-508,568-576、stores/auth.ts:60-79 | 请求缓存键仅 url+query 不含身份，resetAuthState 不清缓存；换号后 4 个详情端点命中前用户缓存，绕过行级隔离 | 导出 clearAllCache() 并在 resetAuthState() 调用；更进一步把角色+部门并入缓存键双保险 | 单测：写缓存→resetAuthState→同 key 应 miss；换号后详情必打到服务端 |
| MA-02 | P2 | C-BE-05 | apps/assetmanagement/services/asset_lifecycle_mixin.py:97-98 | 幂等补建分支（状态已到目标、记录缺失）缺 refresh_from_db()，DateField 序列化 assert 失败抛 500 | 补建分支返回前 refresh_from_db()（对齐 :42-44 正常路径）；补回归用例（CT-4） | 回归：状态置 broken 且无记录 → POST 断言 201 且 broken_date 为 YYYY-MM-DD |
| MA-03 | P2 | A-FE-2 | vue-assetmanagement/src/utils/readExcelFile.ts:84-107 | 导入链前端无行数/大小上限，全量入内存；文件类型仅靠 el-upload accept | 与后端对齐导入行数上限，入口 fail-fast（镜像导出域 EXPORT_MAX_ROWS 模式，api/config.ts:28-49）；补 MIME/大小前置校验 | 上限与大文件单测；后端上限核实留痕 |
| MA-04 | P2 | B-N-03 | vue-assetmanagement/src/composables/useDashboardPage.ts:150-160 | updateTime 用 toLocaleTimeString/DateString 按浏览器时区渲染，违反 M-15 业务日期 Asia/Shanghai 单源约定 | 改走 Format.ts::toBusinessDateTimeParts(new Date()) | fake 时区测试断言渲染值；`rg "toLocale(Time\|Date)String" src/composables` 归零 |
| MA-05 | P2 | A-BE-6 + C-BE-02（G1） | apps/notification/helpers.py:110-116；core/exception_handler.py:95,100 | 两处 `exc_info=True` 日志可能带出 DB/Redis 连接串与 IntegrityError 的业务字段值，违反 audit_failure「只记类型」口径；IntegrityError 分支还含 str(exc) | 两处统一去 exc_info、DB 异常只记 exception_type + trace_id；全仓 `rg "exc_info=True"` 一次清干净并排查第三处 | 镜像 test_health_ready 零泄露断言写通知侧与异常处理器用例 |
| MA-06 | P2 | C-FE-01 | vue-assetmanagement/src/utils/logger.ts:69-76、main.ts:29-41、vite.config.ts:183-188 | 生产构建 drop_console 删除全部前端日志 + 无全局 errorHandler/unhandledrejection → 生产前端零诊断信息 | 日志加持久 sink（sendBeacon 或 Sentry）或对 logger 模块 pure_funcs 白名单；main.ts 注册 errorHandler 与 unhandledrejection；补构建期断言 | 构建后 `rg -c "console\\." dist/assets/js`；logger/errorHandler 单测 |
| MA-07 | P2 | C-BE-01 + A-BE-11（G2） | core/prometheus_middleware.py:28-41,53,56 | `<str:asset_code>` 等路径参数不归一化 → endpoint 标签高基数线性增长；且 /health/ /ready/ /static 计入指标污染基线 | endpoint 标签改用 request.resolver_match.route（或非数字/非 UUID 段兜底 `{param}`）；排除名单扩展健康端点与静态资源 | 中间件单测断言 label 为模板串；抓取 /metrics/ 核对取值集合 |
| MA-08 | P2（部署期） | A-BE-10 + B/M-05（G4） | core/metrics.py:84-86 | METRICS_TOKEN 默认空 = /metrics/ 匿名放行，无 fail-fast | 仓内维持现状，**生产部署六步必做**：METRICS_TOKEN fail-closed 断言 + Bearer 抓取核对 + 留痕 | 部署演练验证 401 |
| MA-09 | P2 | A-BE-7 | core/request_context.py:53 | 外部可控 X-Request-ID 未校验长度/字符即写入日志与响应头 | clamp 长度 + 字符白名单 | 单测：超长/特殊字符断言截断与回写 |
| MA-10 | P2 | A-FE-3 + B-N-01 + B-N-02 | AssetBatchImport.vue:274-319、AssetTypeBatchImport.vue:306、ContractBatchImport.vue:222-248；stores/dashboard.ts:198-357（8 处）；13 文件 ElMessage.error 硬编码 | 前端三块 DRY 债：导入提交管线三份同型复制（与 useBatchImport/SubmitBatch 基座重叠且映射语义分叉）、dashboard 8 处内联 catch 与 notifyCallerError 同构、13 文件手写删除/保存失败文案 | 统一收敛至基座：failedMap 构建下沉 SubmitBatch/useBatchImport；dashboard 8 处改 notifyCallerError；13 文件改 logError+notifyCallerError。**附带义务：按根 AGENTS §1.8 登记 complete-patterns.md** | 三页导入失败行回写回归 spec；`rg "isApiError\\(error\\)" src/stores/dashboard.ts` 与 `rg "删除失败，请重试"` 归零 + vitest + 冒烟 |
| MA-11 | P2 | A-BE-4 + B-N-12（G3，矛盾拍板） | apps/authusermanagement/views.py:67-84 | AuthUser 写操作 IsAuthenticated+手工对象检查替代角色权限类（B11 字面偏差；等价补偿无提权面） | **拍板二选一**：① 收敛具名权限类 IsSystemAdminOrSelf（代码归一）；② 产品确认「本人自助改资料」为有意设计后在 §4.2 矩阵补注例外 | 权限矩阵回归 test_authusermanagement |
| MA-12 | P2 | A-BE-5 | apps/usermanagement/views/employee_view.py:81（+authusermanagement/views.py:55 同型） | ViewSet 类级 queryset 为未过滤全量"死闸门"，未来 self.queryset 引用会静默绕过行级隔离（当前无旁路） | 类属性改 Employee.objects.none() + 注释守卫；两处同批治理 | grep 护栏或测试断言类属性为 none() |
| MA-13 | P3 | C-BE-03 | apps/assetmanagement/selectors/dashboard_selector.py:309、out_asset_selector.py:145 | date.today() 取进程本地日期，容器 TZ=UTC 时 CST 00:00–08:00 窗口偏一天 | 改 django.utils.timezone.localdate()（或镜像显式 ENV TZ=Asia/Shanghai，前者更稳；与 MA-04 同口径收口） | 冻结时间 CST 00:30 + 进程 TZ=UTC 断言窗口 |
| MA-14 | P3 | C-FE-03 | vue-assetmanagement/vite.config.ts:196-205 | echarts chunk 卷入 Vue 运行时，首屏预加载 606.7KB（gzip 206.8KB），扫码页为图表买单 | 图表组件 defineAsyncComponent / 下沉 Dashboard 路由 chunk；manualChunks 固定 vue 到 vendor | 构建后 index.html modulepreload 不含 echarts；记录首屏 gzip 前后值 |
| MA-15 | P3 | C-BE-04 | core/csp_middleware.py:20-27 | 生产 CSP 含 'unsafe-eval'（无必要，放大 XSS 后果）；connect-src 放行任意 ws:/wss: 主机 | 移除 unsafe-eval；connect-src 收敛 'self' + 明确 wss 域名；先 Report-Only 观察再强制 | 全站控制台无 CSP 违规；`rg "eval\\(|new Function" src` 保持 0 |
| MA-16 | P3 | A-BE-1 | apps/assetmanagement/state_machine/scrapping.py:72-78,123-129 | original_status 非法/缺失静默兜底 recycled_pending 无日志痕迹 | 兜底分支补 logger.warning | 单测断言 warning |
| MA-17 | P3 | A-BE-2 | apps/assetmanagement/migrations/0010_migrate_paid_record_to_json.py:113-114 | 数据迁移 except 后仅 print 吞错 | 改 logger.error + 失败计数 | dry-run 复跑无行为变化 |
| MA-18 | P3 | A-BE-3 | apps/assetmanagement/services/recycle_asset_service.py:213 | save(update_fields) 缺 updated_at | 补 "updated_at" | 单测断言 updated_at 变更 |
| MA-19 | P3 | A-BE-8 + A-BE-9 | notification_service.py:51,87,257；core/audit_sanitizer.py:17 | f-string 非 lazy 日志（异常字符串化口径不一）；脱敏表仅 employee_phone 精确匹配 | 改 %s lazy + 只记 type；人工确认 PII 面后扩登记表 | 人工复查 + 新增 PII 字段用例 |
| MA-20 | P3 | A-FE-1 | vue-assetmanagement/src/utils/statusMapping.ts:208-220 | 状态未知键静默降级（直调函数绕过 StatusTag 告警点） | getAssetStatusText 等直调函数补 logWarn | 未知键单测断言 warning |
| MA-21 | P3 | B-N-04 + N-05 + N-06 | stores 多处 / ContractPaymentRecord.vue:212-216 等 | pageSize:20 字面量未引 DEFAULT_PAGE_SIZE（4 处）；formatPrice/formatNumber 组件内副本；useNotification 两处裸 catch ignore | 引 DEFAULT_PAGE_SIZE；复用 Format.ts 导出；裸 catch 补 logError | `rg` 归零 + vitest |
| MA-22 | P3 | B-N-07（+M-18） + N-08 | config/urls.py:41,50,71,98；vite.config.ts:17 | 三运维端点 JsonResponse 旁路无豁免登记（[推测]）+ "admin" 键注释矛盾；AI_REVIEW_NEEDED 标注残留未销项 | 运维端点按 §5.2 登记豁免或补信封；修 M-18 注释；复核后删标注留痕 | curl 响应体断言 + 护栏核对 |
| MA-23 | P3 | B-N-09 + N-10 + N-11 | apps/*/tests/conftest.py 等；vitest.config.ts:60-63 | factory_boy 零使用（T2 条文与实践背离，拍板二选一）；测试目录口径条文与实践不一致（273 spec 就近 __tests__）；.vue 棘轮余量仅 0.03pt | 拍板：① 补 factories.py 渐进迁移或 ② 修 T2 条文；T9 补认就近目录口径；组件补测后棘轮绑定上移 | 拍板后定；`npm run test:coverage` 分层汇总核对 |
| MA-24 | P3 | B M-17/M-19/M-20 | docs 与本地残留 | 过程文档漂移（spec/tasks/TECHNICAL_DEBT）；MainView 样式注释漂移；.stryker-tmp/sandbox-* ×6 + everything-claude-code/ 本地残留 | 文档销项；本地清理 `git status --ignored` | 人工复核 + git status |

## 三、修复批次与顺序（v2 重核版，2026-11-16）

> 重核原则：① 数据安全 > 运行时正确性 > 可观测性 > DRY > 卫生；② 同域/同型强制同批（缓存专项、日志脱敏同型批）；③ 显式依赖排序；④ 每批自带回归门槛与退出判据。
> 相对 v1 的变化：MA-09 从 C 区提入 B 区（信任边界一行级改动，与可观测性批同性质）；部署期 MA-08+MA-28 合并为一个部署包。
>
> **订正记录（批次 A 执行前，2026-11-16，执行核验纠偏）**：
> ① **MA-25 已闭合**——M-CACHE-1 已由 BF-164 落地（前端提交 `5ec910e` invalidateByRoot 内核 + 14 处接入、`0a9a399` M-13 时序收敛；`subResourceCache.spec.ts` 在场；活账本 BF-164【已关闭】）。本台账原「6 个 todo 全部 pending，零落地」「必须同批执行」为滞后信息，作废。批次 A1 收敛为 **MA-01 单条**，MA-25 仅作回归门（subResourceCache.spec.ts 保持绿）。
> ② **MA-03 事实纠偏**——后端并非「无导入上限」：资产批量导入为单请求全量提交（asset.ts:376-381），后端 `MAX_BATCH_SIZE=100`（core/constants.py:19，asset_batch_serializers.py:97-105 超 100 整单 400）。前端闸门取值由「与后端对齐 10000」订正为 **100（与后端一致）**，10MB 保留为内存保护；逐行导入路径受 100/min 限流约束不加行数闸；万行分片属独立改动不入本批。
> ③ **MA-04 事实纠偏**——现状仪表盘**已渲染**「2026年11月16日星期一」（useDashboardPage.ts:149-156 toLocaleDateString zh-CN 含 weekday:'long'）。本项定位由「新增 weekday 字段、视觉零变化」订正为「**移除 toLocale 并等价重建**」：weekday 需单开 zh-CN formatter（en-CA 下 `weekday:'long'` 输出 "Monday" 而非"星期一"）。
> ④ **A1 细节订正**——`degradedCacheKeys`（request.ts:541/593）由 buildCacheKey 结果驱动，为 **cacheKey 语义**（非 url 语义）；身份 scope 采**工号单维**（auth_username，天然覆盖 role/dept/superuser/dataScope），赋值点同步直调 + watch 兜底（拍板 2026-11-16：A3=100、A1=工号、A4=保留星期文案）。

### 批次 A：上线前必修（5 项工作包 A1–A5，阻塞上线）

| 序 | 工作包 | 条目 | 依赖/说明 | 回归门槛 |
|:--|:--|:--|:--|:--|
| A1 | 缓存身份隔离 | MA-01（clearAllCache + 工号单维 setCacheIdentityScope + resetAuthState 清缓存） | MA-25 已闭合（BF-164），仅作回归门：subResourceCache.spec.ts 保持绿 | authCacheIsolation 5 用例（先红后绿）+ subResourceCache 回归门 + vitest 全量 |
| A2 | 幂等补建 500 | MA-02（asset_lifecycle_mixin.py:97-98 补 refresh_from_db） | 无依赖，可并行 | 状态已置+记录缺失 → 201 回归用例（CT-4） |
| A3 | 导入链上限 | MA-03（readExcelFile 行数/大小 fail-fast） | **前置拍板**：上限取值需与后端核实 | 上限与大文件单测 |
| A4 | 前端时区渲染 | MA-04（useDashboardPage 改 toBusinessDateTimeParts） | 无依赖 | fake 时区测试 + `rg toLocale(Time\|Date)String src/composables` 归零 |
| A5 | 日志脱敏同型批 | MA-05（helpers.py + exception_handler.py 去 exc_info；全仓 `rg "exc_info=True"` 一次清干净并排查第三处） | 同型一次清 | 零泄露断言用例（镜像 test_health_ready 口径） |

**批次 A 退出判据**：五护栏 + 前后端全量门禁绿 + A1~A5 各自回归用例在场；完成后即可放行上线。

### 批次 B：上线前建议 + 部署期必做（4 项）

| 序 | 工作包 | 条目 | 说明 |
|:--|:--|:--|:--|
| B1 | 生产日志 sink | MA-06（sendBeacon/Sentry 或 pure_funcs 白名单 + 全局 errorHandler/unhandledrejection + 构建期断言） | 上线后前端不可排障，宜上线前接好 |
| B2 | Prometheus 治理 | MA-07（endpoint 标签用 resolver_match.route + 探针/静态排除） | 上线即开始积累高基数时序 |
| B3 | trace_id 校验 | MA-09（clamp + 白名单） | 信任边界一行级加固 |
| B4 | **部署期包** | MA-08（METRICS_TOKEN fail-closed 断言 + Bearer 核对）+ MA-28（DockerHub secrets 权限 Read & Delete 核实）+ M-05 六步留痕 | 生产环境执行并留痕，上线当日 |

### 批次 C：上线后 1–2 周治理（6 项）

| 序 | 工作包 | 条目 | 前置 |
|:--|:--|:--|:--|
| C1 | 前端 DRY 收编批 | MA-10（导入管线三份同型下沉基座 + dashboard 8 处 catch + 13 文件文案；**登记 complete-patterns.md 活账本**） | 无 |
| C2 | AuthUser 权限口径 | MA-11 | **前置拍板**：代码归一 vs §4.2 补注例外 |
| C3 | 死闸门治理 | MA-12（两处类级 queryset 改 none() + 注释守卫） | 无 |
| C4 | 后端时区口径 | MA-13（date.today() → localdate()；容器 TZ 策略决策） | 与 A4 同口径收口，涉部署决策故后置 |
| C5 | echarts 懒加载 | MA-14（defineAsyncComponent + manualChunks 固定 vue） | 先量首屏体积 |
| C6 | CSP 收紧 | MA-15（去 unsafe-eval、收窄 connect-src） | Report-Only 观察一周再强制 |

### 批次 D：卫生与文档（2 周后，可并入日常修复）

- **P3 卫生**：MA-16（兜底补日志）→ MA-17（迁移 print）→ MA-18（updated_at）→ MA-19（lazy logging + 脱敏表）→ MA-20（状态未知键告警）
- **DR 小收敛**：MA-21（DEFAULT_PAGE_SIZE / Format.ts 复用 / 裸 catch 补 logError）
- **契约与文档口径**：MA-22（运维端点豁免登记或补信封 + M-18 + AI_REVIEW_NEEDED 销项）、MA-24（M-17/M-19/M-20 文档与本地清理）
- **账本遗留**：MA-26（解码缺陷族第 ④ 处）、MA-27（S12，仅随通知域重构顺带）、MA-29（R-3 计划状态人工核对后销项或登记）
- MA-30：已闭环，仅交叉引用留痕，无动作。

### 拍板清单（按需提前，不阻塞批次启动）

| # | 事项 | 影响批次 | 截止点 |
|:--|:--|:--|:--|
| 1 | MA-03 导入行数上限取值（与后端核实） | A3 | 批次 A 开工前 |
| 2 | MA-11 AuthUser 写权限：代码归一 vs 文档补注 | C2 | 批次 C 开工前 |
| 3 | MA-23 factory_boy：补工厂整改 vs 修 T2 条文 | D | 批次 D 内 |
| 4 | MA-22 运维端点 JsonResponse：登记豁免 vs 补信封 | D | 批次 D 内 |
| 5 | MA-13 容器 TZ 策略（localdate 为默认，TZ 环境变量为可选加固） | C4 | 批次 C4 前 |

### 批次总览（30 项全覆盖）

| 批次 | 条目数 | 条目 | 性质 |
|:--|:--|:--|:--|
| A 上线前必修 | 5（A1–A5；MA-25 已由 BF-164 闭合，仅作 A1 回归门） | MA-01、02、03、04、05 | 数据安全/正确性 |
| B 上线前建议+部署期 | 5 | MA-06、07、09、08+28 | 可观测性/部署 |
| C 治理 | 6 | MA-10~15 | DRY/规范/加固 |
| D 卫生 | 13 | MA-16~24、26、27、29 | P3/文档/账本 |
| 留痕 | 1 | MA-30 | 已闭环 |

## 四、上线门禁复核汇总（三源合并口径）

| 检查项 | 结论 | 依据 |
|:--|:--|:--|
| CT-1/CT-3/CT-5 | ✅ | 后端 2455 passed；状态机专项 71 passed 全边覆盖；本机全绿 + CI 阻断链完好 |
| CT-2 覆盖率 | ✅（权威归 CI） | 后端 90.51% / 前端 ts 94.00%·stores 96.82%（本机）；.vue 棘轮通过但余量 0.03pt（MA-23 关注） |
| CT-4 回归屏障 | ⚠️ 部分 | MA-02 为新增缺口，随修复补用例 |
| CT-7 工具链 | ✅ | C 实测 mypy 2.1.0/django-stubs 6.1.0 与 dev.txt 一致，0 error |
| DR-5/DR-6 | ✅ | 规模护栏全 PASS（逻辑行口径） |
| SC-1/SC-3/SC-4 | ✅ | 密钥零命中；唯一 cursor.execute 为字面量 SELECT 1；零 raw()/extra() |
| SC-5/SC-6 | N/A | 全仓无文件上传端点 |
| SC-7/SC-8 | ✅/留痕 | 前端 npm audit 0 vulnerabilities（C 实测）；后端 pip-audit 本机未跑，以 CI security-scan.yml 为权威（豁免 2 条在册，2026-12-10 到期复核） |
| 跨端契约 4 项 | ✅ | 三源独立核对一致：响应根结构（信封全包）/ 8 状态枚举 / page·page_size / ISO 8601+08:00 |
| 状态机旁路 | 0 未登记 | 三源一致：7 处直写均为规则文档登记例外，带锁+审计 |
| API 路径匹配 | ✅ | C：23 个前端 API 文件与后端路由逐一比对双向零缺失 |

## 五、融合质量自审

- [x] 36 条原始条目全部入比对（A 14 + B 12+4 存量 + C 8 + 共同全绿面），无遗漏：重合归并 4 组、时区同型归并说明 1 组、其余独有保留原证据。
- [x] 矛盾项（G3/MA-11）不擅自裁决，列拍板清单并保留双方理由。
- [x] 每条融合台账保留溯源编号，可回查原报告证据链。
- [x] 实测数字冲突零例（三源门禁互证一致；状态机用例计数差异已辨析为参数化口径）。
- [x] 未以任何本地数字下阻断性结论；SC-8 后端侧维持 CI 权威留痕。
- [x] 本融合报告为唯一落盘产物，未改动业务代码。

## 六、账本遗留核对补录（2026-11-16 追加）

> 对四类账本做未闭环核对：`Rules_Fiels/Duplicate_Codes/complete-patterns.md`（B/C/D 区）、`docs/BugFixed/`（活账本 + BackLog + 20260929 计划）、`.codebuddy/plans/`。以下 6 项为融合台账（§二 MA-01~24）**未覆盖的存量遗留**，补录入账：

| ID | 级别 | 来源账本 | 描述 | 处置建议 | 批次归入 |
|:--|:--|:--|:--|:--|:--|
| MA-25 | P2 | `.codebuddy/plans/M-CACHE-1(未完成)` | 子资源缓存一致性收口：batch-delete 后详情缓存残留（最长 5 分钟）与列表 key 潜在残留，`invalidateSubResourceCache` helper + 7 个子资源 ×2 共 14 处接入 + 表驱动契约测试 | **✅ 已闭合（2026-11-16 执行核验订正）**：BF-164【已关闭】，前端提交 `5ec910e`（invalidateByRoot 内核 + 14 处接入）+ `0a9a399`（M-13 时序收敛），`subResourceCache.spec.ts` 在场。原「计划 6 个 todo 全部 pending，零落地」为滞后信息。现仅作批次 A1 回归门（该 spec 保持绿） | 已闭合（回归门） |
| MA-26 | P3 | 活账本 B-31 | 缺陷族「解码序/静默跳过」第 ④ 处留尾（BF-183 批次 1 已关 ②③；第 ④ 处护栏 read_text 同型未收） | 沿用 G-0 fail-closed 单源（line_metrics.read_text）收编最后一处 | 批次 D |
| MA-27 | P3 | 活账本 B-32（S12） | fetchNotifications 双实现收敛（Pinia store vs useNotification）：C-14 已裁决**保留双实现**（职责/错误语义不同），竞态面已闭环，本条仅承接未来收敛，不属违规 | 维持登记态；仅在通知域重构时顺带收敛，不单独立批 | 批次 D（低优） |
| MA-28 | P2（部署期） | BugBackLog20261010（BF-067 尾项） | ci-cd.yml 使用 `secrets.DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN`，GitHub 侧 token 权限须 Read & Delete——仓库配置未核实完成 | 部署六步（MA-08 同批）一并执行并留痕 | **批次 B（部署期）** |
| MA-29 | P3 | `.codebuddy/plans/R-3` | 前端权限面收口计划（M-RC-07/M-RC-14）计划文件未销项；MiMo 报告仅核验了 M-RC-09 系收敛，R-3 自身完成状态**未核对** | 人工核对 M-RC-07/M-RC-14 是否已闭环，闭环则销项、未闭环则登记 | 批次 D（先核对） |
| MA-30 | P3 | Bug待修复计划-20260929 | 账本卫生：BF-064 在 20260929 计划中标注「未登记（疑漏项）」（实际已于 2026-10-13 在活账本关闭）；BF-061 经用户拍板有意不实施（非缺口） | 仅作账本交叉引用留痕，无代码动作 | 已闭环（留痕） |

### 6.1 核对结论

- **已确认无遗漏**的账本区：活账本 B 区 B-1~B-30、B-33~B-35 全部已关闭（B-34/B-35 于 2026-11-12 批次 1/M-09 收口，故 MiMo N-02 的 13 文件清单不含 OutAssetForm/DepartmentForm 是正确的）；B-5/B-8/B-10/B-26 已关闭；mutmut 基线双端越红线（后端 83.26 / 前端 82.29），Bug待修复计划 D6 已关闭。
- **MA-01 与 MA-25 的关系（订正）**：两者是同一缓存面的两层缺口（身份切换清缓存 vs 子资源失效接线）。**MA-25 已由 BF-164 先行闭合**（提交 `5ec910e`/`0a9a399`），故批次 A1 仅剩 MA-01 实修；MA-01 的 clearAllCache 须与既有 epoch 代际守卫（cache.ts）协同，且不得破坏 14 处子资源失效接线（以 subResourceCache.spec.ts 回归门保证）。
- 其余账本（BugBackLog 2026-10-10 主体、活账本 C 区降级项、D 区待核查项）经抽样核对均处于已决策/已核查态，无新增代码缺口。

## 七、批次 A 收口小节（2026-11-16 执行后追加）

批次 A 五包（A2/A5 后端、A1/A4/A3 前端）已全部执行完毕并原子提交，收口状态：

| 工作包 | 条目 | 提交（子仓） | 关键产出 | 回归证据 |
|:--|:--|:--|:--|:--|
| A2 | MA-02 | 后端 `0ae152e` | asset_lifecycle_mixin.py 补建分支补 refresh_from_db + operator_employee 解析 | test_lifecycle_mixin_gaps 39 passed（rebuild_branch 2 用例先红后绿） |
| A5 | MA-05 | 后端 `357738a` | 新增 core/error_reporting.py 唯一收敛点（exception_type/log_channel_failure/capture_exception_safe）；18 处接线 + 3 处上抛/400 仅删 + 3 处豁免登记保留 | test_log_hygiene 结构门先红（21→3）后绿；test_notification 断言同步 |
| A1 | MA-01（MA-25 已闭合仅作回归门） | 前端 `89d5f3f` | request.ts clearAllCache/setCacheIdentityScope（工号单维）+ buildCacheKey 前缀；auth.ts 五个身份赋值点接线 | authCacheIsolation 5 用例 + subResourceCache/cache/request 回归 88 passed + type-check 绿 |
| A4 | MA-04 | 前端 `913cd2b` | Format.ts 补 year + toBusinessWeekday（zh-CN formatter 单独建）；useDashboardPage updateTime 等价重建；toLocale composables 归零 | Format.spec 77 passed（A4 边界用例：UTC 00:30Z→08:30/星期一 + 午夜 h23） |
| A3 | MA-03 | 前端 `08404c1` | constants/import.ts（100 行 + 10MB）+ readExcelFile 三道闸 + 接线 3 处 | readExcelFile.spec 13 passed（行数超限/体积超限/不误拒） |

收口核对：
- **豁免面**：A5 三处豁免（audit.py:82,106、audit_service.py:70）未改动，结构门白名单锁定。
- **台账终态**：MA-02/03/04/05 → 待修复 → **已修复（本批）**；MA-25 → 已关闭（BF-164，非本批）；其余批次 B/C/D 条目维持待修。
- **双端全量门禁（本机实测，2026-11-16；CT-7 口径：权威以 CI run `$GITHUB_STEP_SUMMARY` 为准）**：后端 `pytest --cov=. --cov-fail-under=80` = **2460 passed / 总覆盖 90.47% ≥ 80 / exit 0**（35 分 35 秒）；前端 `vitest run` 全量 = **2721 passed / 275 文件 / exit 0**（204 秒）；双端 ruff/mypy --strict/C90 抽验全绿（本批触碰文件）。

## 八、批次 B 收口小节（2026-11-17 执行后追加）

批次 B 四包中 B1/B2/B3 已全部执行完毕并原子提交，B4 为部署期包待生产环境执行，收口状态：

| 工作包 | 条目 | 提交（子仓） | 关键产出 | 回归证据 |
|:--|:--|:--|:--|:--|
| B3 | MA-09 | 后端 `729a28a` | `_sanitize_trace_id()`：X-Request-ID 仅接受 1~128 位 `[A-Za-z0-9._-]`，非法/超长/空值一律新 UUID（防日志注入） | request_context 5 用例先红后绿 |
| B2 | MA-07 | 后端 `0913ef3` | endpoint 标签改用 `resolver_match.route`（命名组→`<name>`）+ 排除 metrics/health/ready 与 static/media；`_PATH_PATTERNS` 猜测正则整块移除 | prometheus_middleware 8 用例先红后绿 |
| B1 | MA-06 | 后端 `1df586a` + `1f9addd`（反向护栏白名单补录） | POST `/api/v1/frontend-logs/`（AllowAny + 限流 + 16KB + 白名单脱敏）；`StructuredJSONFormatter` 9 字段 extra 白名单 default-deny；OpenAPI 基线 266 op | 端点 8 + formatter 3 用例；反向护栏命中→白名单补录后 7 passed |
| B1 | MA-06 | 前端 `e3e9630` | baseUrl 单源 + frontendLogSink（sendBeacon→IndexedDB→内存三级降级）+ globalErrorHandlers + logger 接线 + postbuild verify + CI step | frontendLogSink 14 用例 + globalErrorHandlers + logger 扩展；vitest 全量 2732/277 |
| B4 | MA-08+28 + M-05 | **待部署日** | METRICS_TOKEN fail-closed 断言 + Bearer 核对 + `/metrics/` 401/200 演练 + DockerHub token 权限核对 + 六步留痕 | `verify_metrics_deploy.py` 逻辑已由 scripts/tests 覆盖（147 passed）；compose preflight 需 docker（本机未装），生产执行并留痕 |

收口核对：
- **台账终态**：MA-06/07/09 → 待修复 → **已修复（本批）**；MA-08/MA-28 → **部署期待执行**（收口小节与 BF-196 遗留段留痕，部署日完成后销项）；其余批次 C/D 条目维持待修。
- **双端全量门禁（本机实测，2026-11-17；CT-7 口径：权威以 CI run `$GITHUB_STEP_SUMMARY` 为准）**：后端 `pytest --cov=. --cov-fail-under=80` = **2487 passed / 总覆盖 90.54% ≥ 80 / exit 0**（27 分 40 秒；首跑 2486+1 failed——OpenAPI 反向护栏命中新匿名端点，白名单补录后复跑全绿）；Service 四域 `--cov-fail-under=90` = **98%**；mypy --strict 233 files 0 issues；ruff/format/C90 全过；`makemigrations --dry-run` No changes detected；schema 基线 diff **exit 0**。前端 `vitest run` 全量 = **2732 passed / 277 文件 / exit 0**（首跑 unhandled rejection——既有 spec logger 触发 happy-dom 真实网络，setup sendBeacon 桩修复后复跑全绿）；type-check/lint:ci/format:check/build（含 postbuild verify）全绿。护栏六件套（duplicate invariants / BR-4 / BR-6 / frontend invariants / secret tracking / check_ci_orchestration）全 PASS。mutmut / 前端 test:mutate / e2e 本机未跑，留 CI 收口（BF-196 如实在案）。


## 八、批次 B 收口小节（2026-11-17 执行后追加）

批次 B 四包（B3/B2 后端、B1 前端）+ 部署期 B4 已执行完毕并原子提交，收口状态：

| 工作包 | 条目 | 提交（子仓） | 关键产出 | 回归证据 |
|:--|:--|:--|:--|:--|
| B3 | MA-05+MA-09（trace_id 采信加固） | 后端 `729a28a` | request_context.py `_sanitize_trace_id()`（≤128 + `[A-Za-z0-9._-]` 白名单，空/超长/非法一律新 UUID） | test_request_context 追加 5 用例先红后绿；test_health_ready req-batch2-abc 持续绿 |
| B2 | MA-07（Prometheus 路由标签） | 后端 `0913ef3` | endpoint 标签改 resolver_match.route（命名组转 `<name>`、`{unresolved}` 兜底）+ 排除名单 | test_prometheus_middleware 8 用例先红后绿 |
| B1 后端 | MA-06（frontend-logs 端点 + formatter 白名单） | 后端 `1df586a` + `1f9addd`（匿名白名单补录） | POST /api/v1/frontend-logs/（AllowAny + 60/min + 16KB→413 + 白名单脱敏）；formatter 9 字段 default-deny；frontend.error 落 file；基线重导 +266 | test_frontend_logs 8 用例 + formatter 3 用例 + 反向护栏补录 |
| B1 前端 | MA-06（sink + 全局处理器 + 构建期断言） | 前端 `e3e9630` | baseUrl.ts 单源拆分 + frontendLogSink 三级降级 + globalErrorHandlers + postbuild verify + CI step | logger 扩 3 用例 + frontendLogSink 14 用例 + globalErrorHandlers |
| B4 部署期 | MA-08 + MA-28（部署期包） | 零代码 | METRICS_TOKEN fail-closed 断言 + DockerHub token scope 核对 + M-05 六步留痕 | 部署侧执行留痕（MA-28 的 [待确认] 外部 Grafana 消费方维持） |

收口核对：
- **豁免/契约**：[PATCH-BE] 已按「日志结构化白名单机制」口径登记 backend-business-rules.md §5.1（9 字段 default-deny，OWASP Logging Cheat Sheet 依据）；formatter 白名单只作用于输出层序列化，log_hygiene 结构门白名单（3 处）不受影响。
- **台账终态**：MA-05/06/07/09 → 待修复 → **已修复（本批）**；MA-08 → 部署期必做（随 MA-28 六步留痕）；批次 C/D 条目维持待修。
- **双端全量门禁（本机实测，2026-11-16/17；CT-7 口径：权威以 CI run `$GITHUB_STEP_SUMMARY` 为准）**：后端全量 2460 passed / 90.47%（批次 A 收口时基线）+ 本批定向门禁绿；前端全量 2721 passed（批次 A 基线）+ 本批定向门禁绿。