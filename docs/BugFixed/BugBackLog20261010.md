# 未修复 Bug 全景 Backlog（2026-10-10）

> 生成方式：活账本（`Bug修复活账本.md` BF 条目 45+）、`Bug待修复计划-20260929.md`、融合审查报告 / opencode 检查报告交叉核对 + 本轮 rg / eslint / git 直接实测。
> 事实源：BF 状态以活账本为准；重复模式以 `Rules_Fiels/Duplicate_Codes/complete-patterns.md` 为准。
> 口径说明：本文只收「未关闭 / 未修复 / 状态漂移」项；已关闭项不重复罗列。

## 0. 结论速览

| 级别 | 数量 | 一句话 |
|---|---|---|
| P0 | **0** | 原 P0 类（权限旁路、H-1 契约、并发出库 409、代签审批）已全部关闭并有红绿锚，本轮实测无回归 |
| P1 | **4** | 全部围绕「门禁假绿 / 阻断能力缺口」：前端变异不阻断、变异口径双漂移、Docker Hub 凭据缺失、52 处复杂度债挂账 |
| P2 | **9** | 端到端验证待人工、覆盖率 `.vue` 待决策、飞书加签待复核、G-4 护栏未实现等规范漂移 |
| P3 | **12** | 观察项 / 低危（含 1 处 `!important` 残余、13 处注释 console、Q-07~Q-11 规范债） |

## 1. P1 — 门禁假绿 / 阻断能力缺口（建议本周内清零）

### P1-1 前端变异门禁假绿（BF-061 残余）
- **证据**：`ci.yml:441` step 级 `continue-on-error: true`；`:438` 注释「临时：0b 移除，移除条件为 score ≥ 80」；`ci.yml:468` ci-summary 仅阻断 backend-mutation，frontend-mutation 无论死活得 `success`。
- **影响**：CT-2 前端变异分支对合并**零约束**，门禁形同虚设（有意/失败均不可见）。
- **修复**：依赖 P1-2 口径拍板；随后一次性移除 `:441` 并在 ci-summary 增加 frontend-mutation 阻断分支（属 D 批，详见 §1a 修复方案第 3 步）。
- **建议顺序**：第 3 步。

### P1-2 变异测试口径缺口（BF-064，前后端双漂移）
- **证据**（本轮实测复核）：
  - 后端：`mutmut-baseline.json` 实测 `"score": 68.6064`（`95f9458` 修正后精确值）；**账面 70.44 为 WSL 旧口径**（113 个 timeout 因 `/mnt/d` I/O 误计入 killed），修复前需先钉死基线口径（见 §1a 第 2 步第 1 小步）。
  - 前端：账本登记 **60.00**（120 mutants 聚焦），BF-083 实跑 **82.29**（scope=stores + useGroup*）——**scope 不同但未标注**，构成账本卫生问题（见 §4）。
- **影响**：P1-1 无法安全解闸（口径不统一时移除 continue-on-error 会误伤）。
- **修复**：按 §1a 修复方案第 2 步执行（钉基线 → 统一 scope 重跑归档 → 账本卫生 → 拍板 0b → 更新 ci.yml 注释）。
- **建议顺序**：第 3 步（P1-1 前置）。

### P1-3 Docker Hub 凭据缺失（BF-067 §三-5）
- **证据**：`ci-cd.yml:100-104` 使用 `secrets.DOCKERHUB_USERNAME` / `secrets.DOCKERHUB_TOKEN`；`:20` 注明 token 权限须 Read & Delete；BF-067 状态【待修复】仅剩此项（§一~§四、§三-6 已修复，run 106 head `46ef870` 全绿）。
- **影响**：部署 workflow 必失败；且因触发条件限制，补配后只能空提交重跑。
- **修复**：运维一次性配置 secret（详见 §1a 修复方案第 1 步）。
- **建议顺序**：**第 1 步**（约 5 分钟，解锁整条部署链，性价比最高）。

#### §1a P1 修复方案（按顺序）

**第 1 步 — P1-3 Docker Hub 凭据（运维配置，解锁部署链）**
1. 登录 Docker Hub → Account Settings → Security → New Access Token：权限 **Read & Delete**（对齐 `ci-cd.yml:20` 注释）；
2. GitHub 仓库 → Settings → Secrets and variables → Actions → 新增两个 Repository secrets：`DOCKERHUB_USERNAME`、`DOCKERHUB_TOKEN`；
3. 验证：因触发条件限制需空提交（`--allow-empty`）或 `workflow_dispatch` 重跑 `ci-cd.yml`，确认 Login / Build and push 步骤全绿；
4. BF-067 翻【已关闭】，登记 secret 配置日期与 run 链接（**token 值本身不入账本**）。

**第 2 步 — P1-2 变异口径统一（P1-1 的前置，解闸条件）**
1. 先钉基线数字：实测 baseline JSON 为 **68.6064** 而非账面 70.44——70.44 出处已定案为 WSL 旧口径（113 timeout 误计入 killed，见 BF-067 §四），统一以当前 JSON 为准修正账本记录；
2. 统一 scope 重跑双端并归档：后端按 mutmut 现有 scope、前端按 `stryker.config.json` 现行 scope（`stores/**` + `useGroup*.ts`）各跑一次，归档 JSON 与分数；
3. 账本卫生修正：BF-083 实跑 82.29 的条目补注 scope 口径（scope=stores+useGroup*，与登记的 60.00/120-mutants 聚焦口径不同源），两数字并存但标注来源；
4. 拍板 0b 策略（**这是决策点**，见下方「待拍板」表）；
5. 更新 `ci.yml:437-440` 注释为已定稿口径。

**第 3 步 — P1-1 移除门禁假绿（依赖第 2 步口径落定）**
1. `ci.yml:441` 删除 `continue-on-error: true` 一行（连带 `:438-440` 临时注释改写为正式口径）；
2. ci-summary 增加分支：`if [ "${{ needs.frontend-mutation.result }}" != "success" ]; then echo "前端变异门禁未通过，阻止合并"; exit 1; fi`（与 `:468` backend 分支同款）；
3. 验证：故意在分支上跑一次 CI，确认 frontend-mutation 失败时 ci-summary 阻断；回滚故意改动；
4. BF-061 残余翻【已关闭】。

#### 待拍板（P1-2 的 0b 策略，决定第 3 步门禁强度）

| 选项 | 机制 | 适用 |
|---|---|---|
| **A. 红线门禁** | score < 80 即阻断 | 口径统一后双端都能稳定 ≥80 时选此 |
| **B. 相对基线门禁** | 低于归档基线（不回归）即阻断，无论绝对分数 | 后端现状 68.6 < 80，只能选此；前端可选更高档 |
| **C. 双端差异化** | 后端 B（相对 68.6），前端 A（红线 80，BF-083 已实证 82.29） | **推荐**：前端已有 ≥80 实证可直接上红线，后端留提升空间，各自如实 |

### P1-4 52 处前端高复杂度债挂账未立项（BF-062）
- **证据**：本轮实测 `npx eslint . --ext .vue,.ts --rule 'complexity: [2, 10]'` = **52 errors**（与账本一致）；`ci.yml:388` step 级 `continue-on-error: true`。
- **影响**：门禁仅警告不阻断；债越滚越大（头部：`SubmitBatch.ts:47` 15、`excelExporter.ts:50` 17、`readExcelFile.ts:71` 11、`RoleManage.vue:220` 12）。
- **修复**：立专项——先入 eslint 配置 + 根级 §5.4 沙盒警告期，再分批降复杂度至 ≤10。
- **建议顺序**：第 4 步（与 P2-2 覆盖率决策同批拍板）。

## 2. P2 — 功能验证 / 待决策 / 规范漂移

### P2-1 C 批端到端验证清单（全为人工动作，CT-4 回归屏障未完成闭环）
| 条目 | 验证内容 | 状态 |
|---|---|---|
| BF-002 | 浏览器 + devtools 预览 WebSocket 子协议回显 | 【待验证】 |
| BF-003 | 运维 Step 4：拉起 node-exporter、失败注入、飞书送达；`scripts/s3_lifecycle.json` 一次性 apply | 【待验证】代码已收口，运行态未验 |
| BF-004 | vendor chunk 拆分（依赖 ≥10MB 才拆，需构建产物比对） | 【待验证】 |
| BF-005 | 前端回滚流程人工演练 | 【待验证】 |
| BF-083 | 分组子表左固定四列，低端机 / 老安卓外发前复验 | 【待验证】 |

### P2-2 覆盖率门禁不含 `.vue`（BF-044 遗留①，[待决策]）
- **证据**：`vitest.config.ts:22` `coverage.include: ['src/**/*.ts']` → CT-2「核心模块覆盖率」在组件层实际不受门禁保护。
- **修复**：并入 `'src/**/*.vue'`；因大量存量组件零覆盖，需拍板「先补测试」或「分阶段设阈值」。属前端 AGENTS §4.1 工程配置自主范围。
- **建议顺序**：第 4 步（与 P1-4 同批）。

### P2-3 飞书加签 `TODO_AI_CONFIRM` 残留（Q-06 / AR-1 受控清单）
- **证据**：实测 `asset_management_backend/docker/feishu-webhook/app.py:42` 存活 `# TODO_AI_CONFIRM: 上线前对照飞书官方文档复核加签算法与字段名(timestamp/sign)`。
- **影响**：若加签算法与飞书现状不符，生产通知会**静默失败**且无复核证据。
- **修复**：上线前人工对照官方文档复核 → 删除标注 → 飞书集成冒烟。
- **建议顺序**：**第 2 步**（人工 30 分钟，上线阻塞项）。

### P2-4 G-4 护栏未实现（F-P3-3）
- **证据**：本轮 rg 实测 `scripts/check_duplicate_invariants.py` 仅含 `check_g1_closed_patterns_absent` / `check_g2_operation_log_single_impl` / `check_g3_frontend_single_source` / `check_g5_no_shadow_modules`——**无 G-4**（error_code 注册提示）。
- **漂移**：根级 §1.8 声称「沙盒期内 G-1~G-3、G-5 阻断、G-4 仅报告」，与实现不符。
- **修复**：补 G-4 实现（报告模式）或在脚本头部显式注明「G-4 为人工执行项」。

### P2-5 跨部门部门可见性未评估（BF-048 遗留，条目未建）
- **证据**：BF-048 第三节「`get_department_by_jobcode` 返回部门而非员工档案，跨部门部门可见性未评估，另立条目跟进」——账本未见对应新条目。
- **修复**：建 BF 条目并评估；在评估前，相关可见性行为按「未知风险」对待。

### P2-6 `?search=` vs `?keyword=` 语义不一致（BF-049 残余）
- **证据**：A-44 变更日志明确「`?search=` 与 `?keyword=` 语义不一致未处理」。
- **修复**：后端统一参数名（建议统一 `keyword`）+ api-schema 基线重导出；或前端收敛调用。

### P2-7 `amount_paid` 重算串行依赖（BF-053 ↔ BF-055）
- **证据**：BF-053 依赖 BF-055 先修（`amount_paid` 重算链路）；BF-055 状态【待验证】。
- **修复**：排期严格 BF-055 → BF-053，不可颠倒。

### P2-8 BF-045 状态漂移待收口
- **证据**：`vitest.config.ts` 已实测命中 `maxWorkers: 4`（BF-046 落地时顺带），BF-045 仍标【部分关闭】，「环境性成因留账待决策」实际已消解。
- **修复**：复核后将 BF-045 收口为已关闭，或缩小其开放范围至真实未解部分。

### P2-9 D 区待核查项（重复代码账本）
- **D-6**：z-index 无层级令牌（状态【待核查】）。
- **D-7**：布尔 query 手写解析（`notification/views.py` 一带，状态【待核查】，与 BF-065 布尔解析 DR-1 系同族）。
- **修复**：完成核查并关闭或转「待修复」立批次。

## 3. P3 — 观察项 / 低危（按需排期）

| # | 项 | 证据 / 位置 | 建议 |
|---|---|---|---|
| 1 | side-tab accent border（BF-072） | `GroupedAssetTable.vue:285` | 待用户选 A/B/C 方案后再动 |
| 2 | keepAlive + componentName 死配置（BF-079） | 路由配置 | 用户已拍板不动代码，维持观察 |
| 3 | `asset_view.py` 512 行存量豁免（BF-018） | `views/asset_view.py` | 触发条件：下次新增 ≥50 行时按方案 B 拆分 |
| 4 | dev 连通性探测裸 fetch（Q-07） | `src/api/network.ts:83` | 加 AbortController + 超时，或标注 dev-only |
| 5 | 业务接口内联 `.vue` 未下沉 types（Q-09） | `DepartmentTree.vue:92` 等 ~12 处 | 迁移至 `src/types/`，.vue 仅留 Props/Emits |
| 6 | API JSDoc 指向不存在视图（Q-10） | `foundAsset.ts:8` 等 11 处 | 更新或删除过时 JSDoc |
| 7 | 设计 token 偏移（Q-11） | `DashboardStatusOverview.vue:90` 等 | 收敛为 4 的倍数、4/8px 圆角 |
| 8 | C-10 残余 1 处 `!important` | **实测** `MainView.vue:205` | 改用 CSS 变量 + scoped 继承模式（对齐 C-10 其余 8 处做法） |
| 9 | BF-041 残余 console | **实测** 13 处（多为注释掉的调试行） | 批量删除注释行即可，低风险 |
| 10 | BF-014 遗留：暗色态浏览器目验 | `NotificationBell.vue` / `BindAuthUserDialog.vue` / `LogIn.vue` | 拉起 dark 主题逐页目验，有偏差回开条目 |
| 11 | G-4 error_code schema 观察项 | 护栏脚本 | 与 P2-4 同批处理 |
| 12 | `?search=`/`?keyword=` 文档口径 | 后端 api-schema | 与 P2-6 同批处理 |

## 4. 账本卫生（先清理的 4 处漂移，半小时内可完成）

| # | 漂移 | 处理 |
|---|---|---|
| 1 | BF-064 前端基线 60.00 vs BF-083 实跑 82.29（scope 不同但未标注） | 在 BF-064 补注「scope=聚焦 120 mutants」与「scope=stores+useGroup* 全量」的区分；以全量口径为后续门禁基线 |
| 2 | 后端变异基线 70.44（账面/WSL 旧口径）vs 68.6064（`mutmut-baseline.json` 实测，`95f9458` 修正精确值） | 70.44 系 WSL 旧口径（113 timeout 因 `/mnt/d` I/O 误计入 killed）；以 JSON 68.6064 为准，账本补注口径切换历史（BF-067 §四已定案，Backlog 引用需同步） |
| 3 | BF-045 状态未随 `vitest.config.ts` maxWorkers 落地收口 | 复核后关闭（见 P2-8） |
| 4 | 计划 D1「mypy 27 errors」已被推翻 | Q-08 实测 `.venv` **0 errors / 209 files**；`dev.txt:35-44` 钉 mypy 2.1.0 + django-stubs 6.1.0 + drf-stubs 3.18.0；CI 同口径成功 → 关闭 D1，避免下次审计误判 |

## 5. 修复顺序（推荐）

| 序 | 动作 | 预估 | 收益 |
|---|---|---|---|
| 1 | **配置 Docker Hub secrets**（P1-3 / BF-067 §三-5） | 运维 5 分钟 | 解锁整条部署链 |
| 2 | **飞书加签人工复核**（P2-3 / Q-06） | 人工 30 分钟 | 消除上线静默失败风险 |
| 3 | **统一变异口径 → 移除 `ci.yml:441` + ci-summary 加前端阻断**（P1-2 → P1-1，详见 §1a 第 2/3 步；0b 策略见「待拍板」表） | 半天 | 收口最大门禁假绿通道 |
| 4 | **覆盖率 `.vue` 决策 + 52 处复杂度立项**（P2-2 + P1-4） | 一次拍板 | 两道门禁补全，债进入治理轨道 |
| 5 | **账本卫生 4 处**（§4） | 半小时 | 避免下次审计误判 |
| 6 | **C 批端到端清单**（P2-1） | 人工 1~2 天 | CT-4 回归屏障闭环 |
| 7 | **P2 其余（G-4、BF-048 建条目、参数统一、BF-055→BF-053 串行）** | 分批 | 规范漂移清零 |
| 8 | **P3 项按需** | 随迭代 | 低危清理 |

## 6. 取证记录（本轮实测命令与结果）

| 结论 | 命令 / 依据 | 结果 |
|---|---|---|
| 前端复杂度债 | `npx eslint . --rule 'complexity: [2,10]'` | 52 errors |
| frontend-mutation 假绿 | 读 `ci.yml:437-471` | `:441` continue-on-error；`:438` 注释「临时：0b 移除」；summary 仅阻断 backend |
| 后端变异基线 | 读 `asset_management_backend/mutmut-baseline.json` | `"score": 68.6064`（run_date 2026-09-30，CI 环境精确值 `95f9458`）；账面 70.44 系 WSL 旧口径，不一致 |
| G-4 未实现 | `rg "def check_g" scripts/check_duplicate_invariants.py` | 仅 g1/g2/g3/g5 |
| 飞书 TODO 存活 | `rg TODO_AI_CONFIRM` | `docker/feishu-webhook/app.py:42` 唯一命中 |
| `!important` 残余 | `rg "!important" vue-assetmanagement/src` | `MainView.vue:205` 为唯一真实残余（其余为注释） |
| console 残余 | `rg "console\.(error\|warn\|log)"`（排除 logger/测试） | 13 处，多为注释行 |
| Docker Hub 凭据 | `rg DOCKERHUB .github/workflows/ci-cd.yml` | `:100-104` 引用 secrets，`:20` 注明 token 权限 Read & Delete，凭据未配置（BF-067 登记） |
| mypy 结论 | `dev.txt:35-44` + Q-08 `.venv` 复跑 + CI | 0 errors / 209 files，计划 D1 失效 |
| 前端变异得分 | BF-083 实跑记录 | 82.29 ≥ 80（scope 受限，见 §4-1） |
| 后端 70.44 出处定案 | BF-067 §四 + BF-066 | WSL 113 timeout 因 `/mnt/d` I/O 误计入 killed；CI 原生 pure-kill 68.61，`b0aec84` 切基线、`95f9458` 修精度 |

---

> 后续动作建议：按 §5 顺序执行；每完成一项，回写对应 BF 条目状态（[待验证] → [已关闭]），并同步更新本 Backlog 的状态列。
