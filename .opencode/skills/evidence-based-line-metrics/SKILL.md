---
name: evidence-based-line-metrics
description: 行号/行数取证与规模门禁——在任何需要引用 file:line、断言文件规模、判断台账登记或撰写实施方案前执行的三套口径分流流程（BR-6 py 500 / BR-4 函数 50 / FR-5 .vue template+script 500 / FR-6 use*.ts 200 / FR-8 stores 500），含六个已实测命中的系统性陷阱与一次性断言脚本范式。Use when 需要引用代码行号或文件行数, when 写实施方案/审查报告要标注行号锚点, when 判断某文件是否超限, when 准备登记 BR6/BR4/FR6 台账, when 引用「XX行/共N行」, or after user says "核实行数"、"查行数"、"验证行号"、"这个行数对吗". Covers 三套口径不可混用、显式 UTF-8 读取、跨行拼接虚增、PowerShell 引号冲突、台账双向断言、护栏 exit code 复核。
---

# 行号与行数取证（Evidence-Based Line Metrics）

> 目标：让每一个「`file:line`」和「共 N 行」都**可复现、可溯源、口径明确**。杜绝因口径混用产生的幻影数字——根级 **LT-1~LT-3** 已把它列为考核口径纪律，历史上因 `wc -l` 误指 `contract_service.py`(489) 与 `operation_log_service.py`(508) 而错误立项拆分（RF-058 / BF-058，2026-09-29）。

## 前置事实（开工前必须核实）

1. **口径唯一实现（LT-1）**：后端 `.py` 逻辑行 = 物理跨度 − 空行 − 整行 `#` 注释 − 本节点 docstring，唯一收敛于 `scripts/line_metrics.py`。**禁止任何旁路实现**（含自定义速查脚本）。
2. **前端 `.ts` 是第二套实现（非 `.py` 口径）**：`scripts/check_frontend_invariants.py:90` 的**单参** `logical_line_count(source)` 独立实现（AST 不适用于 TS），语义=整文件物理行 − 空行 − 整行注释（行注释 `//` 与块注释 `/* */` 起止行；**行尾注释计入代码行**；模板串内 `//` 不视为注释）。取数入口 = `--print`。
3. **FR-5（`.vue`）没有任何 guard 脚本覆盖** —— `check_file_length_guard.py:62-73` 的 `iter_scope_files()` 经 `line_metrics.iter_py_files()` 只产 `.py`。`.vue` 的 500 行红线**只能手工按口径计**，且**不得登记进 BR-6 台账**（登记必然命中 `:152`「台账含已达标条目」）。
4. **FR-5 只算 `<template>` + `<script setup>`，明确排除 `<style>`**（`Rules_Fiels/frontend-business-rules.md:56`）。这是与 FR-6 最易混的一处：同一个 `.vue` 两种口径会给两个数。
5. **阈值与锚点（实测，勿凭记忆）**：

   | 规则 | 对象 | 阈值 | 常量位置 | 有 guard |
   |:--|:--|--:|:--|:--|
   | BR-6 | 业务 `.py` 文件 | **500** | `check_file_length_guard.py:52` `MAX_LINES` | ✅ |
   | BR-4 | 函数/方法 | **50** | `check_function_length_guard.py:44` `MAX_LINES` | ✅ |
   | FR-5 | `.vue`（template+script） | **500** | 仅文档条文 `:56` | ❌ |
   | FR-6 | `use*.ts` composable | **200** | `check_frontend_invariants.py:42` `MAX_LINES` | ✅ |
   | FR-8 | `stores/*.ts`（非 `use*`） | **500** | `check_frontend_invariants.py:43` `STORE_MAX_LINES` | ✅ 严格模式无豁免 |

6. **台账双向断言（预登记即红）**：

   | 台账 | 断言位置 | 双向含义 |
   |:--|:--|:--|
   | `BR6_file_length_ledger.md` | `:112-115` + `:151-153` | 登记行数须 `>500`；且文件**仍须**在超限集合内 |
   | `BR4_function_length_ledger.md` | `:93-95` + `:140-145` | 登记行数须 `>50`；且函数**仍须**超限 |
   | `FR6_composable_ledger.md` | `:162-165` + `:209-211` | 登记行数须 `>200`；且文件**仍须**超限 |

   **正确顺序**：护栏实际报 OVER → 才登记 → 回填**权威实测值**（禁止手填）→ 重跑转绿。**新文件靠 DR-5「新文件从严」自律，零台账。**
7. **CT-7 门禁复核（根级）**：静态门禁结论必须以 `requirements/dev.txt` 声明版本取得；本地漂移数字不得充当 CI 基线。四护栏仅依赖 stdlib（`ast` / `re` / `pathlib` / `argparse`），**无版本漂移面**，本地 exit code 即 CI 基线；但 `mypy` / `ruff` / 覆盖率**有**漂移面，必须先对齐再下结论。
8. **Windows 宿主约束**：Shell 为 Windows PowerShell 5.1，`$null` 而非 `/dev/null` 重定向；编码须显式 `-Encoding` / `PYTHONIOENCODING=utf-8`。

## 工作流

### Step 0 — 判定本次要产出什么

| 产出类型 | 走 |
|:--|:--|
| 单个 `file:line` 锚点 | Step 1 |
| 「共 N 行」/ 是否超限 | Step 2 |
| 「全仓零命中」类断言 | Step 3 |
| 台账登记判断 | Step 2 + Step 4 |
| 方案/报告的锚点密集段落 | Step 5（**批量，一次性脚本**） |

### Step 1 — 取行锚点（显式 UTF-8，逐行读取）

```powershell
$env:PYTHONIOENCODING="utf-8"
python -X utf8 -c "import io;L=io.open(r'<path>',encoding='utf-8').read().splitlines();print(len(L),'lines');print(repr(L[<n-1>]))"
```

- `read` 工具的 `N:` 前缀是 1-indexed，可作交叉印证，但**结论行号以显式 UTF-8 脚本为准**。
- 引用范围（如 `:303-306`）时，必须确认模式串落在该范围内，而非恰好落在区间的首行/末行——**验证脚本要对整段做 join 断言，不能只打区间首行**。

### Step 2 — 取规模（先分流口径，再调函数）

| 文件类型 | 取数方式 |
|:--|:--|
| `.py` | `lm.logical_line_count(lm.read_text(Path(p)), lm.parse_module(lm.read_text(Path(p))))` |
| `.ts`（FR-6 / FR-8 口径） | `cfi.logical_line_count(source)` — 整文件 |
| `.vue`（FR-5 口径） | 手工：定位 `<template>`/`<script setup>` 起止行，对两段分别剔除空行与整行注释后相加 |

`.vue` 手工计的剔除集合：空行、以 `//` / `/*` / `*` 开头的行。**行尾注释计入**（与 FR-6 语义一致）。

```python
def fr5(lines, a, b):                       # a..b 闭区间，1-indexed
    return sum(1 for l in lines[a - 1:b]
               if l.strip() and not l.strip().startswith(("//", "/*", "*")))
fr5_count = fr5(lines, t_start, t_end) + fr5(lines, s_start, s_end)
```

**引用行数时必须写明口径名**（如「359 物理行 / FR-5 口径 204 逻辑行」），否则下一个人必然重踩混用。

### Step 3 — 全文检索断言（基于原始文本）

- 一律用 `io.open(p, encoding="utf-8").read()` 的**原始文本**做正则 / 子串判定。
- **禁止 `''.join(lines)` 后再检索**（见陷阱 ③）。
- `rg` 适合定位，**不适合产出「零命中」结论以外的东西**；且 `rg` 输出的行号在多字节文件上曾与真实行号不符（陷阱 ⑥）。

### Step 4 — 护栏复核（exit code，非人眼读 PASS）

```powershell
python scripts/check_file_length_guard.py --print   > $null 2>&1; "BR-6 exit=$LASTEXITCODE"
python scripts/check_function_length_guard.py       > $null 2>&1; "BR-4 exit=$LASTEXITCODE"
python scripts/check_frontend_invariants.py --print > $null 2>&1; "FR   exit=$LASTEXITCODE"
python scripts/check_duplicate_invariants.py        > $null 2>&1; "G    exit=$LASTEXITCODE"
```

- 判定以 **exit code** 为准。终端输出为 mojibake 时，`Select-String "PASS"` 会匹配不到——**不要因过滤为空就断定失败或成功**。
- 若需登记台账：先跑出 OVER → 登记权威值 → 重跑确认 FAIL 原因已消失（先红后绿）。

### Step 5 — 锚点密集段落：一次性断言脚本

超过约 20 条断言时**必须**落独立 `.py` 执行（见陷阱 ④）：

```python
# 位置：仓库外临时目录（不污染工作区），UTF-8 写入，执行后删除
REPO = Path(r"D:\CodeDemo\AssetManagementProgram")
sys.path.insert(0, str(REPO / "scripts"))
import line_metrics as lm, check_frontend_invariants as cfi

ok, fails = 0, []
def chk(label, cond):
    global ok
    ok += 1 if cond else 0
    if not cond: fails.append(label)

for label, path, n, pat in ANCHORS:            # 行锚点
    L = rd(path)
    chk(label, n <= len(L) and (pat == "" or pat in L[n - 1]))

for label, pat in KEYWORDS:                    # 零命中
    chk(label, pat not in raw(path))

print("TOTAL: %d passed, %d failed" % (ok, len(fails)))
for f in fails: print("  -", f)
```

- **必须跑完并把失败项逐个查清**，禁止为了让 tally 好看而放宽断言——本次即靠此抓出 5 处自身事实错误（`AssetForm.vue` 409 非 365、唯一 AC-ID 86 非 88、locustfile 路径漏 `scripts/`、FR-5 口径 204 非 ≈205、W-4 机制是 500 非 201）。
- 断言失败时**先判断是文档错还是脚本错**：本轮 3 次失败全是我把模式串打在了区间的错误行（如 `:91` 实为 `if purchase_number < 1`、`必须 >= 1` 在 `:92`），文档的 `:91-92` 区间引用是对的。**改脚本，不改正确的文档。**

## 六个已实测命中的系统性陷阱

| # | 陷阱 | 实测证据 | 正确做法 |
|:-:|:--|:--|:--|
| ① | PowerShell `(Get-Content f).Count` | `CommonList.vue` 得 **356**（真值 359）、`07-功能需求与验收标准.md` 得 **495**（真值 687）、`08-...md` 得 **176**（真值 361）；少计 3/192/185 行 | 显式 UTF-8 Python 读取；`Get-Content` 默认编码把多字节序列误判为行尾 |
| ② | `Measure-Object -Line` | 跳空行，低估约 **12%**（LT-2） | 同 ① |
| ③ | `''.join(lines)` 后再正则 | 唯一 AC-ID 真值 **86**，join 后虚增为 **88**（被换行隔断的片段被接成合法匹配） | 零命中/计数断言基于**原始文本** |
| ④ | PowerShell 单行 `python -c "…"` | Shell 把 `-c` 整体包进双引号，脚本内任何 `"` 破坏解析；连续两次 SyntaxError（`\"` 转义与 `chr(34)` 混用） | **>20 条断言落独立 `.py`**；必须用双引号串时改用 `chr(34)` 构造 |
| ⑤ | FR-5 / FR-6 口径混用 | 同一 `CommonList.vue`：FR-5 口径 **204**，FR-6 口径 **314**（含 `<style>`） | 引用必带口径名；`.vue` 不可用 FR-6 函数 |
| ⑥ | `Select-String` 行号 | 曾报 `</style>` 在第 **359** 行而文件仅 **359** 行（越界矛盾） | 行号结论以显式 UTF-8 逐行读取为准 |

## 反模式（禁止）

- ❌ 用 `wc -l` / `Measure-Object -Line` / `(Get-Content).Count` / `Select-String` 行号**充当结论**（LT-2；物理口径仅可作讨论中间量且须标注）
- ❌ 手填台账行数（必须用 `--print` 权威值，否则 `:112-115` 判「登记行数 <= 阈值」红）
- ❌ **预登记**台账（先红后绿是流程，不是可跳步；预登记直接双红）
- ❌ 把 `.vue` 登记进 BR-6 台账（`.vue` 永不在扫描集合，登记必命中 `:152`）
- ❌ 新写旁路行数统计脚本（LT-1 判 `[HALT]`；用 `line_metrics.py` / `check_frontend_invariants.py`）
- ❌ 引用「XX 行」不标口径（物理 vs 逻辑、哪个规则集、含不含 `<style>`）
- ❌ 因终端 mojibache 导致 `Select-String "PASS"` 匹配为空就下结论（看 exit code）
- ❌ 断言失败时放宽断言来凑绿（必须查清是文档错还是脚本错）
- ❌ 把本地 `mypy` / 覆盖率数字当 CI 基线（CT-7）

## 验证门禁速查（Windows）

```powershell
# 规模（权威值）
python scripts/check_file_length_guard.py --print      # BR-6 py > 500
python scripts/check_frontend_invariants.py --print    # FR-6 use*.ts > 200 / FR-8 stores > 500
python scripts/check_function_length_guard.py          # BR-4 函数 > 50

# 四护栏 exit code
python scripts/check_file_length_guard.py    > $null 2>&1; $LASTEXITCODE   # 期望 0
python scripts/check_function_length_guard.py> $null 2>&1; $LASTEXITCODE   # 期望 0
python scripts/check_frontend_invariants.py  > $null 2>&1; $LASTEXITCODE   # 期望 0
python scripts/check_duplicate_invariants.py > $null 2>&1; $LASTEXITCODE   # 期望 0

# 显式 UTF-8 取行（单点）
$env:PYTHONIOENCODING="utf-8"
python -X utf8 -c "import io;L=io.open(r'<path>',encoding='utf-8').read().splitlines();print(len(L))"
```

## 变更记录

- v1.0 (2026-10-03)：按真实样本固化——`docs/资产分组展开表格-实施方案-v2.3.md`（592 行）全量锚点复核，146 项断言 0 失败，过程中抓出 5 处自身事实错误。固化要点：三套口径分流表（py→`line_metrics` 双参 / `.ts`→`check_frontend_invariants:90` 单参 / `.vue`→FR-5 手工 template+script 且**无 guard**）；五个阈值常量锚点（`:52`=500 / `:44`=50 / `:42`=200 / `:43`=500）与 FR-5 文档锚点 `frontend-business-rules.md:56`；三台账双向断言行号；六个陷阱的**实测数字**（`(Get-Content).Count` 少计 3/192/185 行、`''.join()` 使 86→88、单行 `-c` 引号冲突两次 SyntaxError、FR-5/FR-6 同文件 204 vs 314、`Select-String` 越界行号）；>20 断言须落独立 `.py` 的范式；判定以 exit code 而非人眼读 PASS。
