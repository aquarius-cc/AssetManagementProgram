---
name: fr6-orphan-delete
description: FR-6 孤儿 composable 删除执行——按台账"孤儿待去重"批次删除零调用方 use*.ts 的完整闭环（引用扫描 0 命中→清理面枚举→git rm+文档头引用清理→guard 先红后绿→vitest+前端三项→rg 残留 0→提交三连→审计票）。Use when 执行 FR-6 台账孤儿批次删除, when asked to 孤儿去重/删除孤儿 composable/清理死代码 composable, or after user says "去重"、"孤儿"。Covers 空 @callers 段整块移除、无 barrel 级联确认、guard 双向断言（已删除未移台账行即红）、批量授权（多孤儿一并）、首跑失败需复跑甄别（vitest 并行抖动 vs 真回归）。
---

# FR-6 孤儿删除执行（Orphan Composable Deletion）

> 目标：按 `Rules_Fiels/FR6_composable_ledger.md` 的批次 O（孤儿待去重）逐批删除**全仓库零调用方**的 composables，且每批走完 **引用扫描→删除→guard 双向→测试→台账留痕→提交** 全闭环。杜绝"删了文件但台账行还在（guard 长红）"、"漏清文档头引用（rg 残留）"、"误删仍在用的 composable（行为回归）"三大断链。口径、判定、登记源严格对齐根级 AGENTS §1.8 与前端 AGENTS FR-6。

## 前置事实（开工前必须核实）

1. **唯一事实源**：`Rules_Fiels/FR6_composable_ledger.md`（表：批次｜文件｜逻辑行｜处置｜测试锚｜消费方证据｜状态）。guard：`scripts/check_frontend_invariants.py`（root 仓库运行）。
2. **孤儿判定**：`rg "use<Orphan>" --glob "*.ts" --glob "*.vue" --glob "*.js" src` 生产 import **0 命中**（仅自身文件 + 自身 spec + 各文件 `@callers` 文档头注释引用）。活组件（如 AssetBatchImport.vue）用**内联实现或 store 链路**，孤儿无能力承接方 → 纯死代码删除。
3. **guard 双向断言**：超限（逻辑行 >200）未登记 → 红；**已删除文件但台账行未移除 → 红**（「台账含已达标条目」逐文件列出）；登记数值 ≤200 → 红（手写非法）。删除与台账移行必须同一提交批次。
4. **计数口径**：逻辑行 = 物理行 − 空行 − 整行注释；**权威数值仅以 `python scripts/check_frontend_invariants.py --print` 为准**，禁止手填台账。
5. **文档头引用去向**：对象为各 store/api/utils/composables 头部 `@callers` 段；删除后若某段仅剩孤儿条目 → **整段 @callers 块移除**（先例：`useBatchImport.ts`），不留空段。
6. **级联检查**：`src/composables/index.ts` barrel 不存在（先例验证 0 级联）；孤儿依赖的 useBatchImport/assetStore/SubmitBatch/extractErrorMessage 等均为存活代码，删除不触发级联。
7. **批量授权**：剩余多孤儿时先向用户确认单删还是**一并删除**（本批 3 孤儿一并 = 6 文件 + 10 处文档头 + 台账 3 行）。
8. **历史快照不动**：`docs/Review/full-review-report-*.md` 与 Bug 活账本的旧验证记录是历史快照，**禁止改写**（仅 FR6 台账与活账本正文活记录留痕）。

## 工作流

### Step 0 — 引用扫描（0 命中断言）

```powershell
# 前端仓库 vue-assetmanagement/
rg -n "use<Orphan>" --glob "*.ts" --glob "*.vue" --glob "*.js" src
```

- 预期命中：仅自身文件（`@module`/`export function`）、自身 spec（`import ... from '../use<Orphan>'`）、各文件 doc 注释。
- 若命中任何 `.vue` 或活 `.ts` 生产 import → **[HALT]**：判定非孤儿，不得删除，回查台账。
- 记录完整引用清单（文件:行号）作为后续清理与留痕依据。

### Step 1 — 清理面枚举

- 每孤儿：**源码 + 自身 spec**（`.spec.ts` 行数实测）+ **文档头引用计数**（非 `@callers` 处的散列引用逐条记录）。
- 检查 `src/composables/index.ts` 是否存在（barrel）；存在则并入删除清单。
- 检查孤儿依赖的所有 import 是否存活（useBatchImport/Store/extractErrorMessage 等）→ 若孤儿自身依赖被删除链，先确认承接方。

### Step 2 — 删除文件 + 清理文档头引用

```powershell
# git rm 孤儿源码 + spec（保留 git 历史，勿用 Remove-Item）
git rm "src/composables/use<Orphan>.ts" "src/composables/__tests__/use<Orphan>.spec.ts"
```

- 逐文件编辑 `@callers` 道记头：删孤儿行；段空 → 整块删 `@callers` 段。
- 每处引用删除前 `read` 上下文，OldString 带邻行确认唯一。

### Step 3 — guard 先红后绿

```powershell
# root 仓库，Library 目录
python scripts/check_frontend_invariants.py
```

- **先红**：删除后（台账行未移）→ FAIL「台账含已达标条目」逐文件列出（实证截图进提交信息/审计票）。
- **后绿**：FR6 台账移除对应行 + 追加留痕注记（2026-09-22，删除文件+spec+文档头引用数；更新孤儿计数/清零声明）→ 重跑 → PASS。
- **每孤儿删一个移动一行**，禁止整批删完才移（guard 定位困难；批量场景可逐删逐移后统一跑绿）。

### Step 4 — vitest + 前端三项

```powershell
npx vitest run src/composables     # 删除后套件数下降，存活套件全绿
npx vitest run                     # 全量，防跨套件 dangling import
npm run type-check  # eslint . --fix → 0
npm run lint
npm run format:check
```

- **首跑若失败：复跑一次甄别**。实测全量 vitest 偶发并行 transform 抖动（3 文件 6 失败→复跑 132/1812 全绿）。复跑仍失败同一集才判真回归，按失败集逐一定位；禁止以抖动为由无视真实失败（CT-5）。
- 全量复跑必须 `Out-File` 到临时文件再 `rg` 提取失败集（vitest 终端 ANSI 转义会吞 Select-String）。

### Step 5 — 残留断言

```powershell
rg "use<Orphan>" --glob "*.ts" --glob "*.vue" --glob "*.js" src   # = 0
```

- 历史报告 `full-review-report-*.md` / 活账本旧验证块保留原文（快照），不视为残留。

### Step 6 — 提交三连（每批 1 个前端 + 2 个 root）

```powershell
# 前端 vue-assetmanagement/
git add -A; git status --short   # 核对仅预期 D/M 文件（孤儿+spec+文档头文件），无无关改动
git commit -m "refactor(composables): 删除 FR-6 孤儿 use<Orphan> + spec，清理 N 处文档头引用"
# root  仓库
git add "Rules_Fiels/FR6_composable_ledger.md"
git commit -m "chore(ledger): FR-6 台账移除 use<Orphan> 孤儿行并留痕"
git add vue-assetmanagement
git commit -m "chore(submodule): bump vue-assetmanagement → <hash>（FR-6 孤儿删除批次）"
```

- 提交信息含：删除证据（guard 红列文件）、文档头引用数、vitest 全量通过数。
- 批量场景（多孤儿）：前端整数批量 1 commit，root ledger 1 commit（多行齐移 + 计数清零），指针 bump 1 commit。

### Step 7 — 留痕 + 审计票

- FR6 台账注记必须含：删除日期、文件逻辑行数、各自 spec 行数、文档头引用总数、能力承接声明（"活组件均内联实现，能力零依赖"）、guard 双向红>绿实证。
- 输出前端 + 根仓库双审计票：CT-2 删除类覆盖中性（删死代码+死 spec 抵消）、CT-4[~]（无新功能无新用例）、CT-6[N/A]、DR-5 删除非新增、跨端契约未破坏、schema 免重导。

## 反模式（禁止）

- ❌ 未做引用扫描断言 0 命中就删除（可能误删在用 composable）
- ❌ 删除文件与台账移行分提交（guard「已删除未移除」长红）
- ❌ 遗留文档头 `@callers` 引用不清理（rg 残留，下轮审查被当现存引用）
- ❌ `@callers` 段清空后不整块删除
- ❌ 手填台账行数字（必须以 guard `--print` 权威值）
- ❌ 改写 `full-review-report-*.md` / 活账本历史验证块（快照只读）
- ❌ vitest 首跑失败不甄别直接放过（CT-5；复跑甄别抖动 vs 真回归必须白纸黑字）
- ❌ 批量时一次删完才统一移台账行（guard 定位困难）
- ❌ 提交囊括无关文件（`git status` 不核对就 commit）

## 验证门禁速查（Windows）

```powershell
# root 仓库
python scripts/check_frontend_invariants.py                # 后绿 = exit 0；删文件未移行应 FAIL 列出文件
python scripts/check_frontend_invariants.py --print        # 权威逻辑行数值（登记前提）
# 前端仓库
rg "use<Orphan>" --glob "*.ts" --glob "*.vue" --glob "*.js" src   # = 0
npx vitest run src/composables                             # 存活套件全绿
npx vitest run                                             # 全量，失败先复跑甄别
npm run type-check & npm run lint & npm run format:check   # 前端三项全绿
```

## 变更记录

- v1.0 (2026-09-22)：按两个真实样本固化——单删先例 useOutAssetForm（frontend `7a3137d` / root `10ec8f7` + `4cc22b1`）与三孤儿批量先例 useContractBatchImport/useAssetBatchImport/useDepartmentEmployeeList（frontend `72f54ed` / root `0923980` + `c7a250c`，净删 1977 行）。固化要点：guard 双向断言实证（删文件后 FAIL 3 条"台账含已达标条目"→移行 PASS）、空 @callers 段整块移除、无 barrel 级联、vitest 首跑 6 失败=并行抖动（复跑 132/1812 全绿）须先甄别、批量授权确认、提交三连。