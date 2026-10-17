---
name: mutmut-kill-loop
description: 后端变异测试回基线闭环——mutmut 双门禁 GATE_FAIL 后，WSL 快照跑全量 → 存活按函数聚类 → 按杀伤范式定向补测 → 先红抽证 → 复跑验线一次过线。Use when 后端 mutmut 不过 / 变异分数低于基线 mutmut-baseline.json（现 83.25676365492598）/ 需要补杀 survived 或 no_tests 变异体 / 变异门禁 GATE_FAIL，when asked to 补杀变异体、mutmut 回基线、变异测试怎么过、T7 双门禁，or after `mutmut run` reports score below baseline。Covers WSL+postgres 环境三件套、与 ci.yml 逐字同口径的门禁脚本、阈值差额算术、mutmut show 聚类优先级、六类杀伤范式、等变体止损、先红抽证与 CT 联动。
---

# 后端变异回基线闭环（mutmut-kill-loop）

> 目标：把「GATE_FAIL 的 338 个存活」变成「一族变异体一条断言、先红后绿、复跑一次过线」的可重复流程。落 `backend-testing-rules.md` **T7 v1.7 双重门禁**（≥80 硬地板 + ≥基线不回归）与根级 **CT-1/CT-4/CT-5/CT-7**。
>
> **先例**：2026-10-16 实战——killed 1667→1698（+31），score 82.3210 → **83.8519 GATE_PASS**（tested 2025，no_tests 20→0），一次复跑过线。

## 前置事实（每轮开工先核，不许凭记忆）

1. **双门禁算术**：`score = (killed + timeout) / (total - skipped) × 100`，通过条件 `score >= 80.0 and score >= baseline`（**全精度 float 比较**；展示保留 4 位仅供人看）。基线在 `mutmut-baseline.json`，**键名 `score`**，现值 83.25676365492598（截断成 83.2568 会误判——BF-067 实证事故）。
2. **口径唯一事实源 = `setup.cfg [mutmut]`**（`source_paths` 只含 Service 层）+ **`ci.yml` backend-mutation job 内联脚本**。`mutmut run` **零参数**，禁止手传任何 CLI 旗标（3.x 口径纪律）。本地门禁脚本拿不准就从 `ci.yml` 重抄，不许自创。
3. **Windows 原生跑不了**：mutmut 3.8.0 拒绝 win32。必须 **WSL**（本机为 `wsl -d Ubuntu`，WSL2）。
4. **环境三件套**（WSL 冷启动后逐个确认）：`~/amp-backend` 源码快照、`~/amp-venv`（`mutmut==3.8.0`，须等于 `requirements/dev.txt` 声明——CT-7）、postgres16（`db=asset_management_backend`，密码 = backend `.env` 的 `DB_PASSWORD`）。
5. **阈值差额换算**：`need_killed = ceil(baseline × total / 100)`。例：83.25676365492598 × 2025 → **killed ≥ 1686**；当前 1667 → 净差 **+19**，**目标留余量 +22~30**（等变体不可全杀，见止损表）。
6. **只有 kill 加分**：`no_tests → survived` 不改分值（分母不变、分子不加）。no_tests 的价值是 **CT-1 零测缺口**与映射建立，别拿它当战果汇报。
7. **基线文件 = 门禁松动开关**：未经用户批准**禁止**修改 `mutmut-baseline.json`。T7 惯例取 **CI 实证**后由用户抬分。
8. 长跑无固定耗时（CI timeout 给 300min；本机实测 16.64 mutations/s 量级），**超时给足 ≥30min**，输出被截断时去读 tool-output 落盘文件。

## 工作流

### Step 0 — 环境同步与保活（快照 + PG，两条命令）

```powershell
# ① 源码快照同步到 WSL（排除运行时/缓存，--delete 保持一致；本地有未跑的改动必须先同步）
wsl -d Ubuntu -- bash -lc "rsync -a --delete --exclude '.venv' --exclude 'node_modules' --exclude 'mutants' --exclude '__pycache__' --exclude '.pytest_cache' --exclude '.coverage' --exclude '.coverage.*' --exclude 'htmlcov' --exclude '*.log' --exclude '.mypy_cache' --exclude '.ruff_cache' --exclude '*.egg-info' --exclude 'reports' /mnt/d/CodeDemo/AssetManagementProgram/asset_management_backend/ ~/amp-backend/ && echo SYNC_OK"
# ② postgres 冷启动 + 就绪检查（WSL 休眠后服务会停）
wsl -u root -- service postgresql start
wsl -d Ubuntu -- bash -lc "pg_isready -h 127.0.0.1 -p 5432 || pg_isready"
```

### Step 1 — 全量跑 + CI 同口径判分

```powershell
wsl -d Ubuntu -- bash -lc "cd ~/amp-backend && rm -rf mutants && ~/amp-venv/bin/python -m mutmut run; echo MUTMUT_EXIT=\$?"
wsl -d Ubuntu -- bash -lc "cd ~/amp-backend && ~/amp-venv/bin/python -m mutmut export-cicd-stats"
```

判分脚本（与 `ci.yml` backend-mutation 内嵌脚本逐字同口径；**若 ci.yml 演进以 ci.yml 为准**）。用法：落成 `~/gate.py` 后 `~/amp-venv/bin/python ~/gate.py`（cwd 必须 `~/amp-backend`），exit 0 = 过线。

```python
import json, sys
RED_LINE = 80.0
BASELINE_FILE = "mutmut-baseline.json"
STATS = "mutants/mutmut-cicd-stats.json"
try:
    with open(BASELINE_FILE, encoding="utf-8") as handle:
        baseline = json.load(handle).get("score")
except (FileNotFoundError, json.JSONDecodeError) as exc:
    print(f"基线读取失败：{exc}"); sys.exit(1)
if not isinstance(baseline, (int, float)):
    print("基线 score 字段缺失或非法"); sys.exit(1)
try:
    with open(STATS, encoding="utf-8") as handle:
        stats = json.load(handle)
except FileNotFoundError:
    print("stats 缺失：mutmut run 未执行"); sys.exit(1)
tested = stats["total"] - stats["skipped"]
if tested <= 0:
    print(f"无有效 mutant：total={stats['total']} skipped={stats['skipped']}"); sys.exit(1)
score = (stats["killed"] + stats["timeout"]) / tested * 100
breakdown = " ".join(f"{k}={stats.get(k, 0)}" for k in ("killed", "survived", "timeout", "no_tests", "suspicious"))
print(f"得分 {score:.4f}%（红线 {RED_LINE:.1f}% / 基线 {baseline:.4f}%，距基线 {(score - baseline):+.4f}pt）{breakdown} tested={tested}")
sys.exit(0 if (score >= RED_LINE and score >= baseline) else 1)
```

> 传命令纪律：**pwsh↔bash 引号会炸**——含 `$`/长 heredoc 的命令一律先写成临时 `.sh`/`.py` 脚本文件（`%TEMP%\opencode\` 或 `~/`）再执行，不内联。

### Step 2 — 算差额，定目标

用前置事实 5 的公式算出 `need_killed - killed = 净差`，**向上加 3~10 余量**写进本轮目标。汇报与决策只认 gate 脚本输出的 breakdown 五字段 + tested。

### Step 3 — 存活聚类与打靶优先级

1. 导出存活清单（结果行格式 `    apps....__mutmut_N: survived`），**按函数名聚类**统计族大小（如 `_write_complete_log`×8、`batch_create_recycle_asset`×20）。
2. 对嫌疑簇逐个 `mutmut show <全名>` 读变异 diff（可配 `mutmut tests-for-mutant <全名>` 查映射测试）。
3. **打靶优先级**：① `no_tests` 零测方法（补测一举两得：CT-1 + 建立映射）→ ② **本次工作区改脏的文件**（是你自己的改动稀释了分数，责任所在）→ ③ 「未断言字段/参数」大族（每行测试杀伤比最高）→ ④ 大簇函数（`mutmut show` 显示结构/kwargs 丢失型，任何成功路径即杀）。

### Step 4 — 六类杀伤范式（每条都是本轮实证过红的机制）

| # | 范式 | 机制与要点 | 实证产出 |
|:--|:---|:---|:---|
| 1 | **日志字段族** | 对日志行 `asset_name / asset_specification / operator_jobcode / operator_name` **全字段逐字断言**；造值必须互异（name≠spec≠code≠人名），None/空串/换源变体一网打尽 | 一测杀 8 + 4 |
| 2 | **错误文案族** | **动态捕获**同源异常：先 `pytest.raises(FSM异常) → str(e)` 拿 expected，再断言 service 的 `detail == expected`。**禁止硬编码含中文箭头/特殊字的原文**（编码猜错即假红） | 杀 detail None/缺省/"None" ×3 |
| 3 | **kwarg 透传族** | patch **被局部 import 的边界函数源模块属性**（`from X import y` 发生在调用时刻 → patch `X.y`，不是调用方模块），断言 `call_args.kwargs` 的实体与枚举（如 `asset`、`priority`） | 杀 ×2 |
| 4 | **operator 行值族** | 断言 DB 行而非 mock：`log_operation` 会把 `None` 归一成 `""`，故断言 `行值 == jobcode` 同时杀「None 替换」与「kwarg 删除」两种变体 | 杀 ×2 |
| 5 | **update_fields 白名单** | 直调私有 helper（测试调 `Service._private` 有先例）：先落库合法状态 → **内存里改脏无关字段**（不 save）→ 调 helper → `refresh_from_db()` 断言脏值未落库。变体为 `update_fields=None` 或整参删除时即红 | 杀 ×1 |
| 6 | **过滤丢失族** | 构造「真实代码必须成功、丢过滤后必抛错」三场景：**双资产**（`get()` 无参 → MultipleObjectsReturned）、**他资产在途维修**（丢 `asset_recordcode` → exists 误拦）、**本资产 completed 历史**（丢 `repair_status` → 误拦）——断言成功，变体抛错即红 | 杀 ×3 |
| 补 | **deepcopy 族** | 入参埋**标记键**（如 `is_broken`），调用后断言标记键仍在原字典。删除 deepcopy 时归一化/pop 会篡改入参（实测还会**回写** `asset_recordcode` 等新键，污染面更大） | 杀 ×1+ |
| 补 | **批量数值边界** | `N+1` 必须 `raise BATCH_SIZE_EXCEEDED`（杀放宽变体）+ `N` 必须通过（杀收紧变体）。判分口径里这类数字变异只在 `+1/-1` 家族，成对边界即可全覆盖 | 杀 ×1~2 |

**补测落点**：新文件仿 `test_*_mutants.py` 范式（`@pytest.mark.django_db` 类式、复用 `conftest` fixture、精确断言）；也可**追加到同域已有测试文件复用其 fixture**（DR-4，免重复 fixture）。函数 <50 行、文件 <500 逻辑行。

### Step 5 — 先红抽证（CT-4，2 分钟，别跳）

从本族挑 1~2 个**机制最关键**的变异手植进源码（如字段→`None`、删 `deepcopy`）→ 只跑对应新测试 → **必须 FAIL（断言原文可见 None/缺键）** → 立即回滚 → `rg` 校验零残留 → 复跑该测试转绿。红都没红过的范式 = 未验证推理，禁止直接进 WSL 全量跑（一轮全量很贵）。

### Step 6 — 本地快反馈与全量证据刷新

```powershell
# ① 新/改测试文件快反馈
& ".\.venv\Scripts\python.exe" -m pytest <目标测试文件> -q --no-header -p no:cacheprovider
# ② ruff（注意 format 会要求重排新文件）
python -m ruff check . ; python -m ruff format <新改文件>
# ③ 全量 + 覆盖率（CT-2 证据在补测后必须刷新：整体 ≥80 / Service ≥90）
& ".\.venv\Scripts\python.exe" -m pytest --cov=. --cov-fail-under=80 -q --no-header -p no:cacheprovider
# ④ 三护栏（行数红线用护栏口径，禁 wc -l / Measure-Object——LT-1/LT-2）
python ..\scripts\check_file_length_guard.py ; python ..\scripts\check_duplicate_invariants.py
```

任何测试红 = **CT-5 阻断**，修完再进 Step 7。

### Step 7 — 复跑验线

回到 Step 0 ①（只改了测试也要同步！）→ Step 1 全量复跑 → gate exit 0 即收口。**仍差额** → 回 Step 3 换更富矿（下一层大簇：如批量方法 `_do_xxx_update`×19 级别），不要在一个等变体簇上死磕。

### Step 8 — 汇报与留档

- 报 breakdown 五字段 + tested + 距基线 pt + **杀灭增量**（如 1667→1698），不报四舍五入截断值充当门禁结论。
- 新补的测试若覆盖了此前零测方法，显式标注 **CT-1 缺口修复**。
- 本地分数是**本地结论**；CI 才是 push 后的权威留档（CT-7）。基线是否抬分 → 提交用户拍板（T7 惯例：CI 实证后抬、全精度）。
- 收尾审计票按根级 §4：`CT-1[√] CT-4[√]（先红抽证）CT-5[√] CT-7[√]`。

## 等变体止损表（识别即停，用余量覆盖）

| 等变体形态 | 为什么杀不动 |
|:---|:---|
| `x or DEFAULT` 的 None 替换 | 回落默认值与传 None 同值（如 `max_batch_size=None → DEFAULT 100`） |
| 流程开关标志（如 `use_transaction`） | 测试单事务环境下两条路径观察面相同 |
| dict 单层 pop 场景的浅/深拷贝 | 只动顶层键时 `copy.copy` 与 `deepcopy` 对入参影响相同（除非埋标记键） |
| 操作人透传但调用方已给等价来源 | fallback 分支根本不触发（fixture 已提供人员字段时） |

→ 做法：**先数一遍理论可杀上限**，上限 < 差额就立刻扩到其他函数族；汇报时如实区分「已杀」与「等变体放弃」。

## 反面模式

| 反面 | 后果 |
|:---|:---|
| Windows 原生 `mutmut run` | 3.x 直接拒绝，浪费一轮 |
| 手传 `--paths-to-mutate` / 用 `mutmut results` 算比率 | 3.x 口径唯一走 setup.cfg；`results` 无 total 行会算出恒 0 |
| 基线用截断值 83.2568 比较 | BF-067：比真实值高 → 门禁恒红 |
| 把 no_tests→survived 当战果 | 分数一分不涨，虚报进度 |
| 范式没抽证就进全量 | 一轮全量几十分钟，等变体/假断言全靠猜 |
| 手植树回滚不干净 | `rg` 残留检查必做，否则污染生产代码 |
| 报行数用 `wc -l` / `Measure-Object -Line` | LT-1/LT-2 红线；一律护栏 `--print` |
| 拿 `%TEMP%\pytest_full.log` 当长期证据 | 会消失；改覆盖率用 `coverage report` 重算 |
| 自行改 `mutmut-baseline.json` | 未经批准改基线 = 擅自松动门禁 |
| 补测后只跑新文件 | CT-2/CT-5 证据过期，全量必须刷新 |

## 诚实性自检（收口前）

- [ ] gate 结论出自 exit 0 的同口径脚本，而非目测日志？本地结论有没有被写成「CI 已过」？
- [ ] 每个主打范式都先红过、且回滚后 `rg` 零残留？
- [ ] 补测后全量 pytest + 覆盖率 + ruff + 三护栏全部复跑？
- [ ] 等变体是否已识别并如实标注（不冒充「全部杀灭」）？
- [ ] 基线文件一字未动？差额与 breakdown 五字段原样入汇报/审计票？
- [ ] 若带提交：中文 message 含 `|` `$` `{` 时用 `git commit -F <文件>`（PowerShell 内联会解析失败）。
