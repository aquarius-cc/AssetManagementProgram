---
name: batch-fix-closure
description: M 项批次修复闭环——按融合审查报告（如 docs/Review/merge-audit-20261107.md）执行 M-XX 行为补齐型批次的完整闭环（拍板→执行方案 vN 三锚点复核→Step 1 先红→Step 2 实现→Step 3 十项门禁矩阵→Step 4 报告 M 行划线+BF 账本登记+审计票）。Use when 执行 merge 报告批次修复, when asked to 进入批次 N/按 M 项修复/批次方案/先红后绿补齐/十项门禁, or after user says "进入批次"、"按批次修复"、"封装批次修复闭环"。Covers 先红先证缺失、枚举复用免 HALT 判定、审计载荷单源化拆分应对 BR-4/BR-6 双红、mutmut/前端 CI 项如实标注、CF-7 工具链对齐、schema 基线 diff 零漂移。
---

# M 项批次修复闭环（Batch Fix Closure）

> 目标：把融合审查报告（`docs/Review/merge-audit-*.md`）的 M 项按批次修复固化为单一批次闭环：**拍板 → 方案冻结 → 先红 → 实现 → 十项门禁 → 报告+账本双登记 → 审计票**。杜绝「无红先绿」「门禁漏跑」「仪式绿化」「双登记断链」。批次 2（M-05，BF-184）全链实践沉淀。

## 与相邻 skill 的分工（DR-1，不重复实现）

- **BF 条目六段模板、编号自增（`rg "^## BF-"` 取最大+1）、强制检查项** → 加载并遵循 `resolution-fix-ledger-sync`。
- **AUD 行 12 列边界锚定四段划线（E1~E4）、删除/收敛型批次的 rg 零引用取证、批次矩阵算术自洽** → 加载 `audit-batch-fix-closure`（它管「删代码」型，本 skill 管「补代码」型）。
- **行号/行数取证、guard 口径、台账双向断言** → 加载 `evidence-based-line-metrics`。
- 本 skill 独有：先红→后绿（CT-4 回归屏障）、执行方案多轮复核（v1.1→v1.3 冻结决策）、十项门禁矩阵、§5.2 HALT 免触发判定、BR 红线拆分应对。

## 前置事实（开工前必须核实）

1. **唯一事实源**：报告 M 行（P 级/类型/file:line/描述/状态列）+ 活账本（追加不改历史）+ 该批次执行方案（若已定稿）。
2. **拍板先决**：方案层决策（枚举新增与否、审计枚举选型、批量聚合口径、测试落位）须用户拍板 ≤3 轮（§1.6 ID-1）；已拍板事项不重复问。
3. **§5.2 HALT 免触发判定**：若修复只**复用既有枚举/方法**（如 GenericAuditService 四方法）而零新增枚举值、零契约面变更（spectacular 可证）、零迁移面（makemigrations dry-run 可证），则无需 HALT——此判定结论必须写入方案（先例：M-05 冻结决策①）。
4. **CT-7 工具链对齐**：开工先验 `python -m pytest --version` / `python -m mypy --version` / `ruff --version`（注意 PATH，必要时 `python -m`）与 dev.txt 声明逐字一致；漂移则先对齐再跑门禁。
5. **先红先行**：任何行为补齐项先写失败测试证缺失（红证据留存：failed 断言原文 + 数字），再实现。失败路径参数化用例若异常本无该行为，先红轮只呈「异常路径绿」并如实说明，不编造红灯。

## 工作流

### Step 0 — 方案冻结 + 锚点复核

- 方案文本（vN）每轮修订前，对全部锚点做供给侧直证（read/rg/guard --print，禁记忆行号）；Windows 注意 `rg` 通配 `docs/Review/*.md` 报 os error 123，改 `rg -n "key" docs/Review/ -g "*.md"`。
- `Get-Content` 中文行计数有漂移，行号一律 rg/护栏为准（evidence-based-line-metrics）。
- 逐项 delta（Δ1~Δn）+ 订正（F1~Fn）在方案表格化冻结；执行中不得自行改判拍板项。
- reverse 路由/fixture/既有范式提前实证（Step 0 收口），不留到实现期。

### Step 1 — 先红

- 新测试落位既有测试文件（复用 fixture/范式锚点），先确认目标行为当前失败（FAILED 断言 `0 == N` 类原文留存）。
- todowrite 维护五段 todo：读取现状 / 先红 / 实现 / 门禁 / 收口。

### Step 2 — 实现

- 行为最小实现；服务层新增独立载荷模块时新文件 ≤500 逻辑行（BR-6，2026-07-07 后新文件无豁免），函数 ≤50（BR-4）。
- View 层只动调用段（import 从既有行复用）；类属性/契约面/路由零变更。
- 完成即定向 pytest（域内 + 邻近文件）防交叉回归，再进全量门禁。

### Step 3 — 十项门禁矩阵（全部证后写，一红即修即重跑）

```powershell
# workdir: asset_management_backend
python -m pytest -q --cov=. --cov-fail-under=80 --cov-report=term   # 全量+整体 ≥80%（11 分钟量级）
# term 报告抽 services 行核 ≥90（contract_service 95% 级）；新模块 100% 加注
python manage.py makemigrations --dry-run 2>&1 | Select-Object -Last 1   # CT-6① "No changes detected"
python -m mypy . --strict          # 0 错 + 文件数（2.1.0 版本对齐后跑）
python -m ruff check . ; python -m ruff format --check . ; python -m ruff check . --select C90 --config lint.mccabe.max-complexity=10
python ../scripts/check_function_length_guard.py   # BR-4（后 2 共 4 护栏）
python ../scripts/check_file_length_guard.py       # BR-6（belt：--print 查逻辑行口径，LT-3）
python ../scripts/check_duplicate_invariants.py    # G 护栏（先证红后证绿自测在 ci.yml）
python ../scripts/check_frontend_invariants.py ; python ../scripts/check_secret_tracking.py
python manage.py spectacular --format openapi-json --file ../tmp_schema.json --validate
git diff --no-index --quiet api-schema-baseline.json ../tmp_schema.json ; echo "diff_exit=$LASTEXITCODE"   # 0=零漂移；用后删临时文件
# 分级测试（域内）先行：pytest <域文件> -q → N passed 零回归（会计校验=旧数+新增例数）
```

- **mutmut / 前端 `test:mutate` / e2e**：本地跑不动（Windows 平台限制 + 前端门禁），账本内如实标注「留 CI 收口」，不虚报。
- **BR-4/BR-6 双红应对**（先例：M-05 实增量比预估大 → 522>500/51>50）：新抽独立单源模块（审计载荷/工具），调用点一行化 + DR-1 注释指针；抽后 BR-4/BR-6/文件计数三项复测入档。**结论以 guard --print 输出为准**。
- 瞬态 errors / GBK 乱码仅显示问题，认 `[PASS]`/`passed` 数字本体；首跑异常先复跑再定性（瞬态甄别纪律同 audit-batch-fix-closure）。

### Step 4 — 双登记 + 审计票

1. **报告登记**（merge 报告短行，单锚划线即安，不同于 AUD 12 列四段法）：
   - M 行状态列 → `~~已确认/待修~~ **已关闭（批次 N，BF-XXX，日期）**`；
   - 批次表下追加 `> **批次 N 执行回执（日期，BF-XXX）**：先红 N failed → 后绿 …；枚举零新增（无 §5.2 HALT）；契约零漂移（diff exit 0）；门禁细目见 BF-XXX §三`。
2. **账本登记**（交接 resolution-fix-ledger-sync 六段）：核实结论（锚点直证）/ 修复方案（冻结决策）/ 验证记录（codeblock 矩阵数字）/ 对抗审核（单源化 DR-1、值捕获时机、失败路径零审计=设计行为等）/ 遗留（文件余量、批次拆分、他批不串）+ `*登记人：AtomCode ｜ 状态：…*` 尾行。
3. **审计票**照根 AGENTS §4（必填+自检+覆盖率+mutmut 如实清单）；输出 SKILL 建议按 §1.7。
4. **不 push 不 commit**（除非用户明示）；变更面清单落票（backend X 文件 + docs X 文件）。

## 反模式（禁止）

- ❌ 未拍板先实现枚举/契约面变更（HALT 面判定要先写要证）
- ❌ 跳过先红直接绿（CT-4 回归屏障失效 = 审查打回）
- ❌ 门禁漏跑（十项逐一入档；「没跑的」写明原因，不许沉默跳过）
- ❌ 用首次超估的行数预算替代 guard --print 实测（LT-2/LT-3）
- ❌ 载荷/工具第 2 处复制（DR-1 单源化；触发 BR 双红时拆模块而非复制）
- ❌ mutmut「大概过了」→ 必写「留 CI 收口」
- ❌ 记忆行号写 oldString（rg 取准；编辑后行号下移要 fresh read）
- ❌ 会话间断层数字凭印象写（Fact-1 补跑再入档）
- ❌ 与相邻 skill 重复造轮子（AUD 四段划线/六段模板直接引用）

## 变更记录

- v1.0 (2026-11-08)：按批次 2（M-05，BF-184）全链实践固化（先红 4 failed → 2405 passed / 89.65% / mypy 231 files 0 / schema diff exit 0 / BR-4/BR-6 双红拆分收口）。核心沉淀：十项门禁矩阵、§5.2 免触发判定、单源化拆分应对 BR 双红、白名单式明细记录、mutmut 如实在案。AUD 删除型批次归 `audit-batch-fix-closure`，账本机制归 `resolution-fix-ledger-sync`。
