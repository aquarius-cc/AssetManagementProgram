---
name: audit-batch-fix-closure
description: 审查报告批次修复闭环——按批次执行 codegraph 审计报告 AUD 项的完整闭环（拍板→逐项执行+定向取证→批次矩阵→账本六段登记→报告 AUD 行边界锚定划线+追踪表/验证段→双仓提交→审计票）。Use when 执行审计报告批次修复, when asked to 按审计报告修复/批次修复/修 AUD-XX/批修/执行批次 C/报告划线/写批次追踪/批次矩阵验证, or after user says "进入批次"、"按台账修复"、"封装批次修复闭环"。Covers 拍板先决、rg 零引用与用例对账取证、矩阵算术自洽、边界锚定四段划线法、瞬态错误复跑甄别、门禁 mypy 与目标 mypy 的调用伪影、双仓提交与子模块指针、Fact-1 数字纪律。
---

# 审查报告批次修复闭环（Audit Batch Fix Closure）

> 目标：把 codegraph 审计报告（如 `docs/Review/codegraph-audit-2026-10-18.md`）按批次（A/B/C…）修复的全链路固化为单一批次闭环：**拍板 → 执行 → 矩阵 → 账本 → 报告 → 提交 → 票**。杜绝「修了代码没登记」「划线不配对」「数字虚报」「提交夹带」四类断链。批次 A/B/C（BF-104~115，AUD-01~11/23）三轮同构实践沉淀。

## 与相邻 skill 的分工（DR-1，不重复实现）

- **BF 条目六段模板、编号自增、强制检查项四连、对抗审核段** → 加载并遵循 `resolution-fix-ledger-sync`（账本侧机制唯一实现）。
- **本 skill 独有**：AUD 行 12 列结构的边界锚定划线法（与 `full-review-report` 的 `#N` P 级行格式不同）、批次矩阵与算术自洽、双仓提交编排、拍板先决。
- 行数/行号取证一律走 `evidence-based-line-metrics`；重复模式登记走根 AGENTS §1.8 活账本。

## 前置事实（开工前必须核实）

1. **唯一事实源**：报告 AUD 行（12 列：ID/优先级/类型/file:line/符号/描述/措施/工具/影响面/严重度/验收/状态）+ 活账本 `docs/BugFixed/Bug修复活账本.md`；批次行追加于「修复追踪」表，**不改历史批次行**。
2. **拍板先决**：每个 AUD 的处置方案（删除/保留/改写、A/B/C 选项）须先经用户拍板（根 AGENTS §1.6 ID-1，≤3 轮）；拍板结论（如「②A 推翻 BF-028」「③保留订正」）必须写进账本与报告注记，**执行中不得自行改判**。
3. **矩阵命令集**（批次级验收，全部 exit 0 才算批次完成）：
   ```powershell
   python -m pytest -q                              # 全量；删减项对账 旧数−删例数=新数
   python -m pytest --cov=. --cov-fail-under=80 -q  # 整体 ≥80%
   python -m coverage report --include="apps/assetmanagement/services/*" --fail-under=90   # Service ≥90（须 python -m）
   ruff check . ; ruff format --check .             # 格式 401/402 files 量级
   python -m mypy . --strict                        # 门禁命令（见陷阱②）
   python manage.py spectacular --format openapi-json --file api-schema-baseline.json --validate   # 后重导与基线 git diff 比对
   # 四护栏（根仓提交时 pre-commit 自动跑；手跑兜底）：
   python scripts/check_function_length_guard.py ; python scripts/check_file_length_guard.py
   python scripts/check_duplicate_invariants.py ; 前端不变量护栏
   ```
4. **CT-7**：本地数字为漂移环境产物，凡写入账本/报告/票必须标「本地漂移环境，不代表 CI」；mutmut、前端 `test:mutate`、e2e 留 CI，**如实标注「未执行（留 CI）」**，push 后按账本回填。
5. **Fact-1 数字纪律**：矩阵数字须来自本会话实际执行记录；会话间断层的数字（如子集 passed 数）**必须补跑再写**——本批曾需补核 unregisteredasset 146 passed / waste 3 passed / mypy 227。

## 工作流

### Step 0 — 批内盘点与拍板记录

- 读报告批次段与目标 AUD 行，确认本批范围、已有拍板结论、上一批次行尾结构（追加锚点）。
- `git status` 确认两仓（后端 + 根）工作区基线；前端无改动则不动。
- 行号取准：报告行的**行尾细节**（如 col11 是否带闭合反引号）先 `read` 实读，禁止凭记忆写 oldString。

### Step 1 — 逐项执行 + 定向取证

- 每项修复后立即定向取证，四件套按项选用：
  - `rg` **零引用/唯一残留**（删除类：全仓 0 命中；收敛类：仅剩唯一实现点）；
  - 定向 `pytest <files>`（N passed），删除类附**用例对账**（旧总数−删例数=新总数，写明无 collateral loss）；
  - 定向 `mypy <files>` / `ruff check <files>`（仅作开发期快扫，**不充当门禁结论**）；
  - 行为零变化证成：找到「只消费键不消费值」「字段 1:1（含 NULL 语义）」类结构性证据，写进账本。
- 删除/收敛类重构的「先红」由既有用例与 rg 锚定——**未发生先红轮次就在票面如实写**，不编造红灯。

### Step 2 — 批次矩阵（先证后写）

- 按前置事实 3 跑全矩阵；**算术自洽**入档（先例：401/227 = 批次B 402/228 − 删 2 文件 + 1 新包）。
- **瞬态错误甄别**：独立子集首跑报大量 errors（如 146 errors/15s）先复跑——冷启动/DB 未就绪的暂态与真回归必须分开；复跑值才可入档。
- 矩阵任何一项红 → 修复或定位归属后再重跑，**失败即阻塞提交**（CT-5）。

### Step 3 — 账本登记（交接 resolution-fix-ledger-sync）

- BF 编号 = 现有最大 +1（`rg "^## BF-"` 防臆测）；每 AUD 一条六段条目（问题/根因/方案/对抗审核/验证/遗留）。
- 批次特有留痕：**决策反转**（推翻既有 BF 结论 → 在被推翻条目 §五写反转段 + 新条目互指，双向）；**误判订正**（审计表述不准 → 条目内写「审计原表述 > 实测事实」）；**实核措辞**（审计数字/清单先实核再沿用，如「三处勾选框」实为 1 真勾选框 + 2 计划表记录）。

### Step 4 — 报告 AUD 行划线（边界锚定四段法）

- **禁止整行转写**（单元格数千字符，转写必错）。每行 4 个互不重叠的短锚 edit，任意顺序安全：
  1. **E1 行首**：`| AUD-XX | Pn | ` + 原 col3 + ` | ` → 划 col3 `~~…~~` + 插 col4 开 `~~`（oldString 只含 col3，短且确定）；
  2. **E2 锚 col5 全文**（` | <col5> | `）：前置 `~~` 闭 col4，后置 `~~` 开 col6；
  3. **E3 锚 col7 头几个字**（` | <col7 头>`）：前置 `~~` 闭 col6；
  4. **E4 锚行尾**（col11 尾 + ` | 待修 |`）：→ ` | ~~待修~~ ✅ **已修复 <日期>**（详见「修复追踪」） |`。
- 每个锚先 `rg` 验**全文件唯一**（含「追加段文字不得抢锚」检查：同批新写的 note/追踪行若含同字符串，先跑 E4 再写追加，或错开锚）。
- 保留 col5/col7/col8 等审计时点原文（历史快照豁免）；只划 col3 类型、col4 file:line、col6 描述、col12 状态。
- 划完 `rg "AUD-XX \|"` 回读验证：`~~` 成对、列数不变、状态列改写落位。

### Step 5 — 批次注记 + 追踪表行 + 验证段 + 交叉引

- **批次注记**：「修复追踪」表头 blockquote 追加 `> 批次X（AUD-… → BF-…）行于 <日期> 同表追加…` + 拍板要点（推翻/保留/删除类结论）。
- **追踪表行**（5 列：ID｜日期｜文件/区域｜措施｜验证命令与结果）：锚在上一批次末行之后、`**AUD-0x 验证结果**` 段之前；措施列写可复现变更（修前/修后行号、拍板编号、结构证成），验证列只写实跑命令与结果。
- **验证段**（锚上一批交叉引行后插，`---` 之前）：全量 passed/对账、cov 双门槛、ruff/format、mypy 文件数算术、四护栏、spectacular 漂移比对、**未执行项如实标注**（mutmut/前端 CI）。
- **交叉引行**：`**活账本交叉引用**：BF-111（AUD-06）、…` 与账本条目互指成立（双向核）。

### Step 6 — 双仓提交（先码后文，不 push）

1. **后端仓**：`git add -A` → commit（信息格式对齐先例：`fix(backend): BF-1XX~1XX 批次X 批修——AUD-06 … + …（全量 pytest N passed/0 failed, cov X% exit0, Service 98%, ruff/format N files, mypy --strict N files, spectacular --validate+重导diff空, 四护栏全PASS, mutmut 留 CI）`）→ `git status --short` 确认干净，取新 SHA。
2. **根仓**：`git add -A`（账本 + 报告 + 子模块指针；前端无动则不应出现前端指针变化）→ commit → **pre-commit 四护栏**输出须全 `[PASS]`（GBK 乱码仅为显示，认 `[PASS]`/`4 个护栏全部通过`）。
3. `git submodule status` 核指针 = 后端新 SHA、前端指针未动。
4. **禁止 push**（除非用户明示）；push 后 CI 直证回填（mutmut/test:mutate/e2e）按账本逐条执行。

### Step 7 — 审计票

- 必填项照根 AGENTS §4；CT-7 对矩阵数字显式标注本地漂移；CT-3 附「键=边集未动/路径零变化」类证成；未执行项进「建议提交」后的如实清单。

## 反模式（禁止）

- ❌ 未拍板先执行（处置方案是决策项，不是执行项的选择）
- ❌ 整行转写报告长单元格（必须边界锚定 + 锚唯一性验证）
- ❌ 沿用记忆中的行尾/旧行号写 oldString（先 read/rg 取准）
- ❌ 把定向 mypy（显式传文件绕过 config 的 6 假错）当门禁结论（门禁 = `mypy . --strict`）
- ❌ 瞬态 errors 未复跑就入档（146 errors/15s → 复跑 146 passed 先例）
- ❌ 会话间断层数字凭印象写（Fact-1：补跑或删）
- ❌ 划线 `~~` 不配对、改列数、动审计时点保留列
- ❌ 审计措辞未实核就沿用（三处勾选框先例）
- ❌ 反转/订正只写一头（双向互指是硬性）
- ❌ 提交夹带无关文件、前端指针误动、未指示就 push
- ❌ 验证段把「未执行」写成「通过」（mutmut/CI 项如实标注）

## 验证门禁速查（Windows）

```powershell
rg -n "AUD-0[6-9] \||AUD-1[01] \||AUD-23 \|" docs/Review/codegraph-audit-*.md   # 五行划线回读
rg -n "^## BF-" docs/BugFixed/Bug修复活账本.md                                     # 编号唯一、最大+1
rg -n "待修" docs/Review/codegraph-audit-*.md                                      # 本批行无残留「待修」
git status --short ; git submodule status ; git log --oneline -2                  # 两仓干净、指针正确
python -m mypy . --strict                                                          # 门禁（非定向）
```

## 变更记录

- v1.0 (2026-10-19)：按批次 A/B/C（BF-104~115 / AUD-01~11、23）三轮同构实践固化。核心沉淀：边界锚定四段划线法（E1~E4）、矩阵算术自洽、瞬态 errors 复跑甄别、定向 mypy 调用伪影、决策反转双向互指（BF-028）、审计措辞实核（三处勾选框）、Fact-1 补跑纪律、双仓提交与 GBK 护栏输出辨识。账本六段机制交接 `resolution-fix-ledger-sync`，不重复实现（DR-1）。
