---
name: br4-batch-split-execution
description: BR-4 函数长度批次拆分执行——按台账 B1/B2/B3 每批执行拆分的完整闭环（guard 基线→按 helper 设计拆分→guard 清零先红后绿→pytest+覆盖率→台账行号更新/移除→报告追踪+Bug 活账本登记→审计票）。Use when 执行台账中任一批次（B1/B2/B3）的函数拆分, when asked to 拆分长函数/清理 BR-4 超限函数/执行拆分批次, or after user says "按台账拆分"、"进入 B1/B2/B3"。Covers 嵌套 hoist 处理、docstring 压缩口径、弱测试锚先补、行号漂移防漏、每批一提交。
---

# BR-4 批次拆分执行（Batch Split Execution）

> 目标：台账 `Rules_Fiels/BR4_function_length_ledger.md` 中登记的 19 个超长函数按 B1/B2/B3 逐批清零，且每批走完 **拆分→guard→测试→台账→登记** 全闭环。杜绝"拆了代码但 guard 仍红"、"行为走样但测试绿灯"、"行号漂移后台账成旧账"三大断链。计数口径、判定标准、登记源严格对齐根级 AGENTS §1.4/§1.8 与后端 AGENTS BR-4。

## 前置事实（开工前必须核实）

1. **唯一事实源**：`Rules_Fiels/BR4_function_length_ledger.md`，每行含 helper 设计/回归锚/风险（9 列：批次｜文件｜行号｜函数｜逻辑行数｜拆分目标｜回归锚｜风险｜状态）。guard：`scripts/check_function_length_guard.py`。
2. **计数口径**：BR-4 逻辑行 = 物理跨度（`end_lineno-lineno+1`）− 空行 − `#` 注释行；**docstring 计入代码行**。>50 即超限。
3. **双向断言**：超限未登记 → 红；已拆分（≤50）未从台账移除 → 红。**拆分与台账移除必须同一提交**。
4. **台账表结构不可破坏**：guard 解析 `LEDGER_ROW_RE` 只读前 6 列，count 列**必须保持第 5 列**；改表头/插列时先跑 guard 验证。
5. **嵌套函数陷阱**：外层函数逻辑行包含嵌套函数 body（先例：`batch_delete_outasset` total 76 = 外层 5 + 嵌套 `_delete_one` 71）。**必须 hoist（提升）嵌套闭包到类级**，否则线性抽取后外层仍 >50、guard 无法清零。
6. **行号会漂移**：拆分后函数行号必变，登记/台账引用的行号须 `rg` 实测，禁止沿用旧值。
7. **测试锚**：台账「回归测试锚」列已标锚点；标的「无直接行为测试，拆分须先补」的（CT-4 缺口）必须**先加回归用例、后动代码**；状态机关键路径（B1）须有 CT-3 全路径覆盖。

## 工作流

### Step 0 — 批内盘点（guard --print 基线）

```powershell
python scripts/check_function_length_guard.py --print    # 全量函数逻辑行列表
python scripts/check_function_length_guard.py            # 当前应 PASS（台账完整）
```

- 确认本批函数（如 B1 的 6 个）当前逻辑行数与台账一致，无行号/行数漂移；若有漂移先修台账再动代码。
- 确认工作区干净（或仅预先存在的无关改动 `[skip]`）：本批涉及文件拆分前后 `git diff` 必须可控。

### Step 1 — 按台账 helper 设计拆分

- **读台账对应行**的「拆分目标」设计 + 读源码函数区域，helper 名/抽取区间以台账为准，不临场改方案（需改则先改台账再拆，guard 兜底）。
- **嵌套函数**：先 hoist 到类级 staticmethod（行为中性，仅位置迁移），外层收敛后再拆嵌套函数本体。
- **docstring 超长**（部分函数 docstring 占 30-50 行）：压缩为行为无关摘要属合法缩减，语义保留、参数说明移模块级或精简。
- **DR-1 优先**：若同文件存在两条设计复用同一抽取片段（如 bind/replace 共用 `_resolve_bind_targets`、S2/S3 共用 `_create_receive_outasset`），先抽共用 helper 再分别消费。
- 所有抽取保持行为等价：FSM 调用顺序、`save(update_fields=...)` 集合、审计 logger 参数、错误码逐字不变。

### Step 2 — guard 清零验证（先红后绿）

```powershell
python scripts/check_function_length_guard.py
```

- **先红**：拆分后（台账未移除）应 FAIL「台账条目已拆分」列出本批已 ≤50 的函数。
- **后绿**：从台账移除/更新本批已达标行（同提交），再次运行 → PASS。
- 每拆一个就验证一个，禁止整批拆完才跑（定位回归困难）。

### Step 3 — pytest + 覆盖率（CT-2/CT-3）

```powershell
pytest apps/assetmanagement -q          # assetmanagement 侧
pytest apps/usermanagement -q           # usermanagement 侧（B2）
pytest apps/unregisteredasset -q        # unregisteredasset 侧（B2）
# 覆盖率（Service 层硬门槛 ≥90%）
pytest --cov=apps.<模块>.services --cov-fail-under=90 -v
```

- 弱锚函数拆分前先补用例（CT-4/CT-3）：`views.batch_delete`、`bind_auth_user`/`replace_auth_user`、`_handle_s1/s3` 等。
- B1 状态机路径（broken/lost 二次 FSM 转换、hoist 后快照恢复、approve 审批链）须有断言锚。

### Step 4 — 台账行号更新/移除（与拆分同提交）

- 本批已达标的函数 → 整行移除（状态不再「待拆分」）。
- 因拆分致使**其他行**（含其他批次）行号漂移 → 用 `guard --print` 新行号更新对应行；hoist 导致嵌套函数行号迁移 → 同步更新其行及外层行。
- 运行 `rg -o "\|\s*[0-9]+\s*\|"` 核对数字列完整（行数 × 行号）。

### Step 5 — 登记同步（交接 resolution-fix-ledger-sync）

每批完成后将本轮拆分登记到两份文档（加载并遵循 `resolution-fix-ledger-sync` skill）：
- 审查报告 `docs/Review/full-review-report-*.md`「修复追踪」追加该批 `#21` 行（每文件一行）。
- Bug 活账本 `docs/BugFixed/Bug修复活账本.md` 追加 BF 条目（编号最大+1，防重号）。
- 若改变对外行为/响应结构 → 同步 M-3 schema 重导出；售后端规则口径变化 → `[PATCH-BE]` 留痕。

### Step 6 — ruff/mypy/复杂度 + 审计票

```powershell
ruff check .          # 目标文件 0 新增错误（存量错误区分标注）
ruff check . --select C90 --max-complexity 10   # 复杂度门禁（后端 AGENTS）
mypy . --strict       # 区分"目标文件 0 新增"与"存量"
```

- 输出后端/根级审计票（CT-1[√] CT-3[√] CT-5[√]、DR-1[√] DR-5[√]、契约未破坏等），EFC 逐项照实。
- 全量 pytest 未跑必须如实标注「未运行（批次内定向已过）」禁写通过（Fact-1）。

## 反模式（禁止）

- ❌ 不读台账 helper 设计临场自创拆分方案（台账是唯一事实源）
- ❌ 嵌套函数线性抽取不 hoist（外层永难清零）
- ❌ 拆分与台账移除分提交（guard「已拆分未移除」长红）
- ❌ 弱测试锚函数先拆后补（违反 CT-4 回归屏障）
- ❌ 沿用旧行号登记（拆分必然移行）
- ❌ 破坏 count 列第 5 位或表格列数（guard 解析静默失效，必须跑 guard 验证）
- ❌ 一次拆整批再统一验证（回归定位困难）
- ❌ 虚报 pytest/覆盖率数字（Fact-1；未跑必须标注）
- ❌ 顺手"优化"无关函数或触碰批量外的预存脏文件
- ❌ 拆分同时改对外契约而不做 M-3 schema 重导

## 验证门禁速查（Windows / 仓库根目录）

```powershell
python scripts/check_function_length_guard.py                      # 后绿 = exit 0
python scripts/check_function_length_guard.py --print              # 看拆后实际逻辑行
rg -o "\|\s*[0-9]+\s*\|" Rules_Fiels/BR4_function_length_ledger.md | Measure-Object   # 数字列完整性
rg -n "def <目标函数>" <拆分文件>                                    # 行号实测，登记前提
rg -n "^## BF-" docs/BugFixed/Bug修复活账本.md                       # BF 编号唯一
# 每批结束 git diff 自审：剥离无关改动，仅提交本批文件 + 台账 + 文档登记
```

## 变更记录

- v1.0 (2026-09-21)：按首个真实样本固化（窗口期 3 次台账迭代 + guard 先红后绿经验）。固化要点：嵌套 hoist 先例（batch_delete_outasset 76=5+71）、docstring 压缩口径、弱锚（batch_delete/bind·replace/S1·S3）先补 CT-4、count 列第 5 位约束、每批一提交与登记闭环。