# 未修复 Bug 全景 Backlog（2026-10-10）

> 生成方式：活账本（`Bug修复活账本.md` BF 条目 45+）、`Bug待修复计划-20260929.md`、融合审查报告 / opencode 检查报告交叉核对 + 本轮 rg / eslint / git 直接实测。
> 事实源：BF 状态以活账本为准；重复模式以 `Rules_Fiels/Duplicate_Codes/complete-patterns.md` 为准。
> 口径说明：本文只收「未关闭 / 未修复 / 状态漂移」项；已关闭项不重复罗列。

## 0. 结论速览

| 级别 | 数量 | 一句话 |
|---|---|---|
| P0 | **0** | 原 P0 类（权限旁路、H-1 契约、并发出库 409、代签审批）已全部关闭并有红绿锚，本轮实测无回归 |
| P1 | **0** | ✅ **P1 全部收口（2026-10-13）**：P1-1 前端变异假绿（2026-10-10）、P1-2 变异口径双漂移（2026-10-12）、P1-3 Docker Hub 凭据（→ GHCR 迁移，2026-10-13 BF-067 关闭）均关闭；52 处复杂度债已由 BF-086 清零（2026-10-12） |
| P2 | **9** | 端到端验证待人工、覆盖率 `.vue` 待决策、飞书加签待复核、G-4 护栏未实现等规范漂移 |
| — | — | **【2026-10-13 回写】** P2-9 已收口（D-6 翻已关闭 / D-7 转已核查，见该节）；P2-2/P2-3/P2-4/P2-5/P2-6/P2-7/P2-8 此前已收口。P2 余开放：P2-1 四项人工验证（BF-002~005）、BF-088 观察项（表外）；另见审核报告 `docs/Review/代码多维度审核20261013.md` R-05（CI 取证 502）与 R-02（ci-cd file 路径疑点）。 |
| P3 | **12** | 观察项 / 低危（含 1 处 `!important` 残余、13 处注释 console、Q-07~Q-11 规范债） |

## 1. P1 — 门禁假绿 / 阻断能力缺口（建议本周内清零）

### P1-1 前端变异门禁假绿（BF-061 残余）【已关闭 2026-10-10】
- **证据**：`ci.yml:441` step 级 `continue-on-error: true`；`:438` 注释「临时：0b 移除，移除条件为 score ≥ 80」；`ci.yml:468` ci-summary 仅阻断 backend-mutation，frontend-mutation 无论死活得 `success`。
- **影响**：CT-2 前端变异分支对合并**零约束**，门禁形同虚设（有意/失败均不可见）。
- **修复**：依赖 P1-2 口径拍板；随后一次性移除 `:441` 并在 ci-summary 增加 frontend-mutation 阻断分支（属 D 批，详见 §1a 修复方案第 3 步）。
- **建议顺序**：第 3 步。
- **收口记录（2026-10-10）**：① 前置 Node 22 修复（`ci.yml:433-440`，stryker engines 硬守卫，run 114 实证 Node 20 下启动即崩被吞成假绿）；② CI 实测 score=**82.29** ≥ 80（run 38035803775）后移除 `continue-on-error`（`ci.yml:442-449`）+ 补 `ci-summary` 阻断分支（`ci.yml:484-487`）+ artifact 上传（`ci.yml:450-455`）；③ 先红后绿双证：正向 run 38035803775（82.29 → 全绿）+ 反向 run 38038707562（强制 exit 1 → ci-summary failure）；④ BF-061 翻【已关闭】，归档 `docs/Review/mutation-baseline-2026-10-10.md`。

### P1-2 变异测试口径缺口（BF-064，前后端双漂移）【已收口 2026-10-12，双端均过红线，BF-064 转已关闭】
- **证据**（本轮实测复核）：
  - 后端：`mutmut-baseline.json` 实测 `"score": 68.6064`（`95f9458` 修正后精确值）；**账面 70.44 为 WSL 旧口径**（113 个 timeout 因 `/mnt/d` I/O 误计入 killed），修复前需先钉死基线口径（见 §1a 第 2 步第 1 小步）。**【现状补注 2026-10-13】** 68.6064 为 2026-10-10 快照；C 批补测后现值 **83.25676365492598**（全精度取值规则，CI run 38224467353），以 `mutmut-baseline.json` 现值为准。
  - 前端：账本登记 **60.00**（120 mutants 聚焦），BF-083 实跑 **82.29**（scope=stores + useGroup*）——**scope 不同但未标注**，构成账本卫生问题（见 §4）。**【收口补注 2026-10-13】** scope 双口径注已落 BF-064（2026-10-13 账本卫生补标）与 BF-083 条目；60.00 转历史留痕，后续门禁以 stryker 射程 CI 实跑为准。
- **影响**：P1-1 无法安全解闸（口径不统一时移除 continue-on-error 会误伤）。
- **修复**：按 §1a 修复方案第 2 步执行（钉基线 → 统一 scope 重跑归档 → 账本卫生 → 拍板 0b → 更新 ci.yml 注释）。
- **建议顺序**：第 3 步（P1-1 前置）。
- **收口记录（2026-10-10）**：① 后端基线钉死 CI 口径 **68.6064**（`backend-testing-rules.md` T7 v1.6，70.44 转 WSL 历史留痕）；② 前端 scope 补注（BF-083 条目 + 82.29/82.35 标注 stores+useGroup* 射程）；③ 0b 策略拍板 **C 双端差异化**（后端相对基线 T7 / 前端红线 80 T16，`stryker.config.json` `break:80` 内置）；④ 前端红线 80 已生效并经 CI 双证（见 P1-1 收口记录）。**开放区残留**：后端 68.6064 < 80% 绝对红线，待 C 批盲区补测抬分（BF-064 维持【部分关闭】）。
- **收口记录（2026-10-12 C批终态）**：**后端开放区残留消解**——C 批盲区补测抬分越 80% 绝对红线。B2（`test_operation_log_mutants.py`，40 用例）：`operation_log_service` 存活 181→0，68.6064→77.8458；B3（`test_out_asset_mutants.py`，24 用例）：`out_asset_service` 123→28，→82.6977；B3-二轮（`test_out_asset_mutants_round2.py`，6 用例）：→83.2568（余量 3.2568pt）。终态基线 score **83.2568**（killed 1631 / survived 310 / no_tests 18，1959 mutants，WSL 2026-10-12，CI 实证待补）。前端红线 80 维持（82.29 CI 双证）。**双端均过红线，BF-064 转【已关闭】**。残留 17 个判等价变异（B类，Fact-1）。T7 绝对红线恢复条件本 run 已满足，规则变更另批送审。子仓 `73d8d61` + 父仓 `01ef6be`。

### P1-3 Docker Hub 凭据缺失（BF-067 §三-5）【✅ 已关闭 2026-10-13】
> **关闭指针（2026-10-13）**：方案迁移为 GHCR 后四项关闭口径全部核销（CD 双链四连绿 + registry 匿名标签/manifest 直证 + 联动 source 标签直证 + visibility public），详见 BF-067「关闭回执」。本节下方原文全部保留作历史。
> **【方案迁移 2026-10-13】** 原「配 Docker Hub secrets」方案**作废**——触发事实：Docker Hub 网络不可达（用户实测）。改为 **GHCR 迁移**（`ci-cd.yml` Login/tags/prune + `docker-compose.prod.yml:13` 已改造，零库外 secrets），详见 BF-067「部署仓库迁移决策」补注与审核报告 §5.1 批次 1.2。本节下方第 1 步原文保留作历史，**实际关闭条件已改为**：CD run 双绿 + GHCR 包页标签实证 + 包页联动本仓 + 部署主机 pull 成功。
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

### P1-4 52 处前端高复杂度债挂账未立项（BF-062）→ 【✅已关闭 2026-10-12】
- **证据**：本轮实测 `npx eslint . --ext .vue,.ts --rule 'complexity: [2, 10]'` = **52 errors**（与账本一致）；`ci.yml:388` step 级 `continue-on-error: true`。
- **影响**：门禁仅警告不阻断；债越滚越大（头部：`SubmitBatch.ts:47` 15、`excelExporter.ts:50` 17、`readExcelFile.ts:71` 11、`RoleManage.vue:220` 12）。
- **修复**：立专项——先入 eslint 配置 + 根级 §5.4 沙盒警告期，再分批降复杂度至 ≤10。
- **建议顺序**：第 4 步（与 P2-2 覆盖率决策同批拍板）。
- **关闭回执（2026-10-12）**：本条建议已由 **BF-086 / P1-4** 完整执行——规则先入 `eslint.config.ts`（`complexity: ['warn', 10]` + scripts/测试豁免 override，子仓 `4c6fe84`），随后两批清零至 **remaining complexity issues = 0**（子仓 `b248900`）。32 个文件仅改结构不删分支、错误消息逐字不变、语义逐行等价。**批5 亦同日落地**（子仓 `a683f20` + 父仓 `1e60441`）：`complexity` 升 `'error'`，`ci.yml` frontend-complexity 撤 `continue-on-error` 与 CLI `--rule` 覆盖，改跑 `npm run lint` 读 config。详见 `docs/BugFixed/Bug修复活账本.md` BF-086 §五⑦。
  > **勘误注记**：上方「证据」行的 `--rule 'complexity: [2, 10]'` 系**历史取证快照**，保留原样以保真。该命令现**已废弃**——CLI `--rule` 不读 flat config 的 `app/complexity-exempt` override 块，会绕过豁免并对 `scripts/*.mjs`、`**/__tests__/*.spec.ts` 误报（批5 实测 5 处）。现行唯一口径为 `npm run lint`（走 config）。

## 2. P2 — 功能验证 / 待决策 / 规范漂移

### P2-1 C 批端到端验证清单（全为人工动作，CT-4 回归屏障未完成闭环）
| 条目 | 验证内容 | 状态 |
|---|---|---|
| BF-002 | 浏览器 + devtools 预览 WebSocket 子协议回显 | 【待验证】 |
| BF-003 | 运维 Step 4：拉起 node-exporter、失败注入、飞书送达；`scripts/s3_lifecycle.json` 一次性 apply | 【待验证】代码已收口，运行态未验 |
| BF-004 | vendor chunk 拆分（依赖 ≥10MB 才拆，需构建产物比对） | 【待验证】 |
| BF-005 | 前端回滚流程人工演练 | 【待验证】 |
| BF-083 | 分组子表左固定四列，低端机 / 老安卓外发前复验 | 【✅已关闭 2026-10-12】人工复验 5 项全过 |

### P2-2 覆盖率门禁不含 `.vue`（BF-044 遗留①）→ 【✅已关闭 2026-10-12】
- **证据**：`vitest.config.ts:22` `coverage.include: ['src/**/*.ts']` → CT-2「核心模块覆盖率」在组件层实际不受门禁保护。
- **修复**：并入 `'src/**/*.vue'`；因大量存量组件零覆盖，需拍板「先补测试」或「分阶段设阈值」。属前端 AGENTS §4.1 工程配置自主范围。
- **建议顺序**：第 4 步（与 P1-4 同批）。
- **关闭回执（2026-10-12）**：用户拍板**分层棘轮**方案，已由 **BF-086 / P2-2** 落地——`coverage.include` 并入 `'src/**/*.vue'`（120 组件进入口径），80/90 收进 `'src/**/*.ts'` 前缀块，`.vue` 独立棘轮（语句 12.9 / 分支 11.6 / 函数 10.9 / 行 13.0，取当日实测并向下取整留余量，语义=只升不降）。子仓提交 `100c93f`。详见 `docs/BugFixed/Bug修复活账本.md` BF-086。

### P2-3 飞书加签 `TODO_AI_CONFIRM` 残留（Q-06 / AR-1 受控清单）【已关闭 2026-10-13】
- **证据**：实测 `asset_management_backend/docker/feishu-webhook/app.py:42` 存活 `# TODO_AI_CONFIRM: 上线前对照飞书官方文档复核加签算法与字段名(timestamp/sign)`。
- **影响**：~~若加签算法与飞书现状不符，生产通知会**静默失败**且无复核证据。~~ 措辞订正（2026-10-13）：代码本就有结构化日志 + 502（`app.py:163-166`），非静默；真实风险是「失败无人盯日志」。复核后确认算法与飞书现状一致。
- **修复**：~~上线前人工对照官方文档复核 → 删除标注 → 飞书集成冒烟。~~ **按 B 顺序执行完毕（2026-10-13，用户拍板方案审核后）**：①文档对照复核 6 点全一致（含行号订正 `:113-115`→`:117-120`）；②单测 `test_app.py` 删前删后双跑 **14/14 OK**；③真实冒烟双检通过——正检 HTTP 200 + 群卡片实收、负检错密钥 HTTP 502 + 日志 `code=19021` 实证签名生效；④删标注留痕（官方文档出处 + 复核日期 + 冒烟实证）；⑤`rg TODO_AI_CONFIRM` 全仓零命中，AR-1 受控清单归零。详见 **BF-089**。
- **建议顺序**：~~**第 2 步**（人工 30 分钟，上线阻塞项）。~~ 已执行。

### P2-4 G-4 护栏未实现（F-P3-3）【已关闭 2026-10-13】
- **证据**：本轮 rg 实测 `scripts/check_duplicate_invariants.py` 仅含 `check_g1_closed_patterns_absent` / `check_g2_operation_log_single_impl` / `check_g3_frontend_single_source` / `check_g5_no_shadow_modules`——**无 G-4**（error_code 注册提示）。
- **漂移**：根级 §1.8 声称「沙盒期内 G-1~G-3、G-5 阻断、G-4 仅报告」，与实现不符。
- **修复**：~~补 G-4 实现（报告模式）或在脚本头部显式注明「G-4 为人工执行项」。~~ **按第三选项关闭（2026-10-13，经 §5.2 人工审批）**：不补实现，改根级 AGENTS.md §1.8 定性——G-4（error_code 注册）已定案无需注册（服务层 `error_code` 仅供批量 `fail_items` 日志、前端零消费，账本 `:1700` 留痕），属语义级定性检查，护栏不实现自动化；§1.8 守护枚举改为 G-1~G-3、G-5，「阻断」主语锚定该四条。AGENTS.md 升 v3.7.1 + changelog；`complete-patterns.md:971` 脚注同步补注「未自动化，账本 `:1700` 留痕」。依据链：账本 `:911`（「G-4：无需注册」）+ `:1700`（「无 G-4 实现函数」2026-09-23 已留痕）+ `complete-patterns.md:966/:971`（定案定义与脚注）+ 自测套件 `test_duplicate_invariants.py` 仅测 g1/2/3/5（与「无实现」一致）。

### P2-5 跨部门部门可见性未评估（BF-048 遗留，条目未建）【已关闭 2026-10-13】
- **证据**：BF-048 第三节「`get_department_by_jobcode` 返回部门而非员工档案，跨部门部门可见性未评估，另立条目跟进」——账本未见对应新条目。
- **修复**：建 BF 条目并评估；在评估前，相关可见性行为按「未知风险」对待。
- **关闭回执（2026-10-13）**：已建 **BF-088**【观察项·未评估】（账本 BF-087 之后，无跳号）——元信息双向锚定（BF-088 引 `:2842`「另立」原文 + BF-048 `:2842` 补注「→ 已另立 BF-088 跟进」）；影响段按未知风险落位并点名行为面：① 跨部门员工列表查询与导出（`list`/`export_excel`）经部门过滤后的行集合范围；② `get_department_by_jobcode` 单独调用的返回边界（与 BF-048 `:2842` 原文对齐）。附待评估项清单 3 条 + 对抗审核（与 BF-048 边界切分、BF-049~087 零命中核查、Fact-1 不臆造结论）。**本条仅完成「建条目」，评估本身挂账于 BF-088 按需排期**（Backlog §1.6 类型 E 表 E2 行同步收口）。

### P2-6 `?search=` vs `?keyword=` 语义不一致（BF-049 残余）【已消解 2026-10-13】
- **证据**：A-44 变更日志明确「`?search=` 与 `?keyword=` 语义不一致未处理」。
- **消解认定（2026-10-13）**：本条证据为 A-44 登记时点（v2.9.49，2026-09-26）快照，已被次日 commit `c1ff7dd`（2026-09-27，子仓）解决——双语义**定性为既定设计并护栏化**：新增 `apps/usermanagement/employee_search.py` 专职模块（`?search=` 窄口径=DRF SearchFilter 字段名匹配、`?keyword=` 宽口径=列表查询含部门名与中文状态别名，文案从 selectors 权威常量派生）；`test_employee_search_contract.py` **16 条合同测试**锁死窄/宽口径、AND 交集、「search 单独传 400」等行为为预期设计；`employee_view.py:167` `search_param_description_actions` 限定声明范围；前端实测只发 `keyword`（`user.spec.ts:39/49`）。§3 跨端契约表不含 search/keyword（仅响应根结构/状态枚举/分页/日期），**无 [HALT] 触发点**；强制统一参数名会撞毁这批刻意设计的合同测试且前端零收益。
- **修复**：~~后端统一参数名（建议统一 `keyword`）+ api-schema 基线重导出；或前端收敛调用。~~ 不做参数统一——双语义为既定设计，本条转状态回写收口（配套：`complete-patterns.md:986` 遗留② 与账本 `:2776` 两处 A-44 时代措辞同步补注 c1ff7dd 后现状）。

### P2-7 `amount_paid` 重算串行依赖（BF-053 ↔ BF-055）【已失效 2026-10-13】
- **证据**：BF-053 依赖 BF-055 先修（`amount_paid` 重算链路）；BF-055 状态【待验证】。
- **失效认定（2026-10-13）**：本条前提已消解——BF-053（活账本 `:3142`）与 BF-055（`:3242`）均已【已关闭】，同批 2026-09-28 v2.9.53 B-25 子项①③处置；`:3174` 明示「两者须同批处置（B-25 已论证，不单飞）」= 串行依赖已被遵守。本文件 :115「BF-055 状态【待验证】」系登记时点（2026-10-10）的陈旧快照，未随账本关闭同步。
- **修复**：~~排期严格 BF-055 → BF-053，不可颠倒。~~ 无需排期——依赖关系已消解，本条转状态回写收口。

### P2-8 BF-045 状态漂移待收口 【已关闭 2026-10-13】
- **证据**：`vitest.config.ts` 已实测命中 `maxWorkers: 4`（BF-046 落地时顺带），BF-045 仍标【部分关闭】，「环境性成因留账待决策」实际已消解。
- **修复**：复核后将 BF-045 收口为已关闭，或缩小其开放范围至真实未解部分。
- **关闭回执（2026-10-13）**：BF-045 已收口为【已关闭】，范围严格限定 Q-05 两处 flaky——证据链三段闭合（根因表实测锁「15 workers + 4.92GB 内存争用」→ BF-046 落地固化 `vitest.config.ts:20` `maxWorkers: 4`（改动表第 10 行）→ 2026-10-13 复核实测命中）。原「环境性成因留账待决策」开放项失效。**第六节遗留 2（mypy 注解债）、遗留 3（pytest teardown 告警）为独立技术债，不随本条关闭，继续独立挂账**（本条仅收 Q-05）。

### P2-9 D 区待核查项（重复代码账本）【✅ 已收口 2026-10-13】
- **D-6**：~~z-index 无层级令牌（状态【待核查】）~~ → **【✅已关闭】**。2026-10-13 实测已修复：`vue-assetmanagement/src/styles/variables.css:103-108` 存在完整 `--z-*` 阶梯（content 1 / mask 100 / child-container 200 / notification 900 / router-mask 1000 / view-overlay 2000）；全仓 z-index 引用恰 8 处全部 `var(--z-*)`、零裸值。与 `complete-patterns.md:884`「✅ 已修复（2026-09-09）」一致——本行原【待核查】为登记时点漂移，予以收口。
- **D-7**：~~布尔 query 手写解析（`notification/views.py` 一带，状态【待核查】，与 BF-065 布尔解析 DR-1 系同族）~~ → **【✅已核查·低风险观察】**。2026-10-13 完成前端字面量实证核查：`NotificationList.vue:73` `params.is_read = filters.is_read === 'true'` 赋**布尔值**，axios 序列化仅产生 `true`/`false`，与后端 `notification/views.py:31` `== "true"` 词表一致，现实现无隐性 Bug。**重开条件**：前端一旦改发 `1`/`0` 或其他字面量即构成静默错答，须重开并按 `complete-patterns.md` D-7「修复建议」走 §5.2 审批改造（Serializer `BooleanField` 收敛）。证据同步登记于 `complete-patterns.md:900` 状态行。
- **修复**：~~完成核查并关闭或转「待修复」立批次。~~ **已执行**——D-6 翻已关闭、D-7 转已核查（含重开条件），本节收口。执行记录见 `docs/Review/代码多维度审核20261013.md` §5.1 批次 3。

## 3. P3 — 观察项 / 低危（按需排期）

| # | 项 | 证据 / 位置 | 建议 |
|---|---|---|---|
| 1 | ~~side-tab accent border（BF-072）~~ | ~~`GroupedAssetTable.vue:285`~~ | **【✅ 2026-10-13】** 批次 D2 拍板**选项 D**（取代 A/B/C，原定义错位）：六处统一 `var(--color-primary)`（#2b5fd7）+ 宽度 4px（仅 `UnregisteredAssetBasicDetails.scss:87` 3px→4px），`common-forms.scss:85` 基准不动；复扫 `border-left.*primary-light` 清零、7 处 primary accent 齐整；行号 `:285`→`:396`；三项门禁绿；BF-072 翻【已关闭】；目验归行10 |
| 2 | ~~keepAlive + componentName 死配置（BF-079）~~ | ~~路由配置~~ | **【✅ 2026-10-13】** 用户改按**方案②**执行（取代 2026-10-08「维持观察」拍板）：删资产详情条 `keepAlive`+`componentName` 死配置（`routes-main-core.ts` 原 :71-72）+ grouped 段注释显式声明「有意不缓存」（`:46-49`）+ spec 回归锚先红后绿（`index.spec.ts:130-141`，12/12）；五条同构路由（Contract/AssetType/Storage/User/Department，实测缓存活）零触碰；全量 vitest **2119 passed**、三项门禁绿；BF-079 翻【已关闭】；**零行为变化**（死配置本就从未生效） |
| 3 | ~~`asset_view.py` 512 行存量豁免（BF-018）~~ | `views/asset_view.py` | **【✅ 2026-10-13 口径订正】** 512 系物理行口径（LT-2 禁用，RF-058/BF-058 同型第三次）；护栏 `--print` 权威值 **471 逻辑行 < 500，0 违规**（2026-10-13 实测；2026-09-29 计划 D3 批已同结论取消拆分）→ **不立项**；触发条件改按逻辑行口径：新增 ≥50 逻辑行时同步拆分至 ≤500 |
| 4 | ~~dev 连通性探测裸 fetch（Q-07）~~ | ~~`src/api/network.ts:83`~~ | **【✅ 2026-10-13】** 批次 B1：OPTIONS 预检补 `signal: AbortSignal.timeout(TIMEOUT)`，`TIMEOUT=15s` import 自 `api/config.ts:17`（零扩导出面）；spec 先红（`timeout` 0 calls / exit=1）后绿 **7/7**；三项门禁绿 |
| 5 | ~~业务接口内联 `.vue` 未下沉 types（Q-09）~~ | ~~`DepartmentTree.vue:92` 等 ~12 处~~ | **【✅ 2026-10-13】** 批次 C1 分流执行：真手写 EP 内部类型**仅 DepartmentTree 三件**（`ElTreeNode:92`/`ElTreeStore:114`/`DropType:120`）→ 迁入 `types/form-helpers.ts`（该文件树三件死导出同名异构、全仓零调用，一并清除并删死 `AssetTypeTreeNode`）；「~12 处」其余为单文件业务类型（`SearchForm`×3 / `FormDataType`×4 **形状全异**，跨文件不同构）按批准分流**留原地**；EP 官方 `TreeNode`=useDragNode 包装、`Node` 类未公开导出故手写不可避免；type-check 绿 + `departmentTree.spec` **16/16**；执行中顺带发现 `.section-title` 同款样式 ×5 重复，已按 §1.8 新发现义务登记 `complete-patterns.md` **B-26**（待修复） |
| 6 | ~~API JSDoc 指向不存在视图（Q-10）~~ | `foundAsset.ts:8` 等 | **【✅ 2026-10-13】** 批次 A2 实测 29 文件 72 目标、失效 **28**（原「11 处」低估）：15 处视图改真实路由页（`componentsdetails/*Details` / `views/*View`）、`stores/authStore`→`stores/auth`、network 拆 `stores/networkStore`+`views/LogIn`、roles.ts 自引用 ×7 → `stores/roleStore`+`UserDetails.vue`、`api/userAPI`→`api/authusers.ts`；余 4 为有意保留伪目标（index.ts 通配 ×3、request.ts「全局」描述），复扫 missing=4 全部留痕 |
| 7 | ~~设计 token 偏移（Q-11）~~ | ~~`DashboardStatusOverview.vue:90` 等~~ | **【✅ 2026-10-13】** 批次 D1：自写扫描（间距 %4≠0 + 圆角 ∉{0,4,8}px，`var()/calc()/50%` 豁免）实测 **14 处 / 8 文件**（间距 6/10/14/18/22/2px + 圆角 3/6px）全部收敛（就近 4 倍数、tie 取小、2→4 特例）；复扫 **CLEAN**；三项门禁绿；`status-bar` radius 3→4 为胶囊半高、浏览器钳制回 3px **渲染零变化已留痕**；14 处全列目验单 |
| 8 | ~~C-10 残余 1 处 `!important`~~ | ~~**实测** `MainView.vue:205`~~ | **【✅ 2026-10-13】** 批次 B2：**整行删除** `padding: var(--el-main-padding) !important`——EP `.el-main` 自消费该 var（`theme-chalk/index.css` 实测 `padding:var(--el-main-padding)`），`:204` 设 8px 后特异性 0,2,0 > EP 0,1,0，`:205` 整行冗余；修法为「CSS 变量 + scoped 继承」原建议，且避开 `variables.css:111`「禁写 :deep+!important」禁令；三项门禁绿 |
| 9 | ~~BF-041 残余 console~~ | **实测 13 处** | **【✅ 2026-10-13】** 批次 A1 拆分订正：13 = **10 注释行 + 3 logger 合法唯一出口**（`logger.ts:58/60/63`，`:62` 带 `eslint-disable no-console` 豁免），**0 active**——原「8 注释 + 3 logger + 2 待逐条判定」口径不成立；10 处注释已全删，复扫仅剩 logger 3 处 |
| 10 | BF-014 遗留：暗色态浏览器目验 | `NotificationBell.vue` / `BindAuthUserDialog.vue` / `LogIn.vue` | 拉起 dark 主题逐页目验，有偏差回开条目 |
| 11 | ~~G-4 error_code schema 观察项~~ | 护栏脚本 | **【✅ 2026-10-13】** P2-4 按第三选项收口：改 AGENTS.md §1.8 定性（G-4 已定案无需注册，不实现自动化），不补报告模式 |
| 12 | ~~`?search=`/`?keyword=` 文档口径~~ | 后端 api-schema | **【✅ 2026-10-13】** P2-6 已消解：双语义为既定设计（`c1ff7dd` + `employee_search.py` + 16 条合同测试护栏化），前端 keyword-only，不做参数统一 |

## 4. 账本卫生（先清理的 4 处漂移，半小时内可完成）【✅ 全部完成 2026-10-13】

| # | 漂移 | 处理 |
|---|---|---|
| 1 | ~~BF-064 前端基线 60.00 vs BF-083 实跑 82.29（scope 不同但未标注）~~ | ~~在 BF-064 补注「scope=聚焦 120 mutants」与「scope=stores+useGroup* 全量」的区分；以全量口径为后续门禁基线~~ **【✅ 2026-10-13 完成】** BF-064 已落 2026-10-13 账本卫生补标：60.00 标注为 2026-09-24 聚焦口径历史留痕；后续前端门禁以 `stryker.config.json` 射程 CI 实跑为准（现行 82.29） |
| 2 | ~~后端变异基线 70.44（账面/WSL 旧口径）vs 68.6064（`mutmut-baseline.json` 实测，`95f9458` 修正精确值）~~ | ~~70.44 系 WSL 旧口径（113 timeout 因 `/mnt/d` I/O 误计入 killed）；以 JSON 68.6064 为准，账本补注口径切换历史（BF-067 §四已定案，Backlog 引用需同步）~~ **【✅ 2026-10-13 完成】** 口径史七段已落 BF-064 补标（70.44→68.6064→77.8458→82.6977→83.2568→**83.25676365492598**）；权威现值 **83.25676365492598**（全精度取值规则，CI run 38224467353）；现状级引用（本文件 :27/:173、实施方案-v2.3.md:1056）已补注现值指针；`ci.yml:270` 实测已同步不改 |
| 3 | ~~BF-045 状态未随 `vitest.config.ts` maxWorkers 落地收口~~ | ~~复核后关闭（见 P2-8）~~ **【✅ 2026-10-13 完成】** BF-045 已翻【已关闭】（范围限定 Q-05），P2-8 已附关闭回执；遗留 2/3 独立挂账 |
| 4 | ~~计划 D1「mypy 27 errors」已被推翻~~ | ~~Q-08 实测 `.venv` **0 errors / 209 files**；`dev.txt:35-44` 钉 mypy 2.1.0 + django-stubs 6.1.0 + drf-stubs 3.18.0；CI 同口径成功 → 关闭 D1，避免下次审计误判~~ **【✅ 2026-10-13 完成】** D1 已按 Q-08 关闭（计划 D1 行 + 顺序表第 2 行 + §8.1 可验证行均已补注推翻与根因=工具链钉版非代码修复）；`complete-patterns.md:430` 遗留项同步订正 |

## 5. 修复顺序（推荐）

| 序 | 动作 | 预估 | 收益 |
|---|---|---|---|
| 1 | **配置 Docker Hub secrets**（P1-3 / BF-067 §三-5） | 运维 5 分钟 | 解锁整条部署链 |
| 2 | **飞书加签人工复核**（P2-3 / Q-06） | 人工 30 分钟 | 消除上线静默失败风险 |
| 3 | **统一变异口径 → 移除 `ci.yml:441` + ci-summary 加前端阻断**（P1-2 → P1-1，详见 §1a 第 2/3 步；0b 策略见「待拍板」表） | 半天 | 收口最大门禁假绿通道 |
| 4 | ~~**覆盖率 `.vue` 决策 + 52 处复杂度立项**（P2-2 + P1-4）~~ | 一次拍板 | **【✅已完成 2026-10-12】**两道门禁补全落地，见 BF-086（P1-4 清零 + P2-2 分层棘轮）。后续项：批5 `warn`→`error` + `.vue` 棘轮上移 |
| ~~**5**~~ | ~~**账本卫生 4 处**（§4）~~ | 半小时 | 避免下次审计误判 **【✅已完成 2026-10-13】** §4 四处全部收口：BF-064 门禁口径补标（前端 60.00 转历史留痕 + 后端口径史七段）、BF-045 翻【已关闭】（P2-8 回执）、后端基线现状级引用补注（Backlog :27/:173 + 实施方案-v2.3:1056）、计划 D1/D6 关闭 + complete-patterns:430 遗留订正。改动留工作区待用户审阅提交 |
| 6 | **C 批端到端清单**（P2-1） | 人工 1~2 天 | CT-4 回归屏障闭环 |
| ~~**7**~~ | ~~**P2 其余（G-4、BF-048 建条目、参数统一、BF-055→BF-053 串行）**~~ | 分批 | 规范漂移清零 **【✅ 2026-10-13 全部收口】** 四项分别由 P2-4（G-4 改 §1.8 定性，已关闭）、P2-5（BF-048 建条目 → 新建 BF-088）、P2-6（参数统一已消解——双语义为既定设计 `c1ff7dd`，不做统一）、P2-7（BF-055→BF-053 串行已失效——双 BF 同批关闭 2026-09-28）收口；本行整行 ✅ |
| 8 | **P3 项按需** | 随迭代 | 低危清理 |

## 6. 取证记录（本轮实测命令与结果）

| 结论 | 命令 / 依据 | 结果 |
|---|---|---|
| 前端复杂度债 | `npx eslint . --rule 'complexity: [2,10]'` | 52 errors **（历史快照，2026-10-10 口径；BF-086 批5 已清零，现行口径 `npm run lint`）** |
| frontend-mutation 假绿 | 读 `ci.yml:437-471` | `:441` continue-on-error；`:438` 注释「临时：0b 移除」；summary 仅阻断 backend |
| 后端变异基线 | 读 `asset_management_backend/mutmut-baseline.json` | `"score": 68.6064`（run_date 2026-09-30，CI 环境精确值 `95f9458`）；账面 70.44 系 WSL 旧口径，不一致 **【2026-10-13 补注：本行为 2026-10-10 取证快照；JSON 现值已升至 83.25676365492598（C批 B2/B3/B3-二轮 + 全精度取值规则，CI run 38224467353），后续引用以现值为准】** |
| G-4 未实现 | `rg "def check_g" scripts/check_duplicate_invariants.py` | 仅 g1/g2/g3/g5 |
| 飞书 TODO 存活 | `rg TODO_AI_CONFIRM` | `docker/feishu-webhook/app.py:42` 唯一命中 **【2026-10-13 补注：已收口——单测 14/14 + 冒烟双检（正检 200/群卡片、负检 502/code=19021）通过后删标注留痕，源码零命中；详见 BF-089】** |
| `!important` 残余 | `rg "!important" vue-assetmanagement/src` | `MainView.vue:205` 为唯一真实残余（其余为注释） |
| console 残余 | `rg "console\.(error\|warn\|log)"`（排除 logger/测试） | 13 处，多为注释行 |
| Docker Hub 凭据 | `rg DOCKERHUB .github/workflows/ci-cd.yml` | `:100-104` 引用 secrets，`:20` 注明 token 权限 Read & Delete，凭据未配置（BF-067 登记） |
| mypy 结论 | `dev.txt:35-44` + Q-08 `.venv` 复跑 + CI | 0 errors / 209 files，计划 D1 失效 |
| 前端变异得分 | BF-083 实跑记录 | 82.29 ≥ 80（scope 受限，见 §4-1） |
| 后端 70.44 出处定案 | BF-067 §四 + BF-066 | WSL 113 timeout 因 `/mnt/d` I/O 误计入 killed；CI 原生 pure-kill 68.61，`b0aec84` 切基线、`95f9458` 修精度 |

---

> 后续动作建议：按 §5 顺序执行；每完成一项，回写对应 BF 条目状态（[待验证] → [已关闭]），并同步更新本 Backlog 的状态列。
