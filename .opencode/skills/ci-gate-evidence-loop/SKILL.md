---
name: ci-gate-evidence-loop
description: CI 门禁变更的取证闭环——改 .github/workflows/ 的门禁/汇总/触发条件后，把「预期路径」拆成两次提交分别用 CI 直证，再把 run ID 与 job 级结论原子地写回活账本。Use when 改动 security-scan.yml / ci-cd.yml / ci.yml 的门禁逻辑、job 级 if、汇总 job、触发条件或 needs 链, when asked to 把扫描结果接入门禁/让 audit 阻断合并/加部署前置门禁/加汇总 job/验证 audit 是否被跳过, or after user says "接入门禁"、"阻断合并"、"验证降噪路径"、"轮询 CI 结果再提交". Covers 触发路径与降噪路径预判、REST 配额降级三档、job 级结论取证、两个必查门禁缺陷、账本回填、未验证项据实标注。
---

# CI 门禁变更的取证闭环

> 目标：门禁改动落地后，把「我以为它会这样工作」变成「CI 实证它确实这样工作」，并把证据原子地写回活账本。落根级 `AGENTS.md` §9 Fact-1（事实基线）与 CT-7（门禁结论必须以 CI 工具链复核）。
>
> **先例**：BF-067 §三-6 后续，head `46ef870` / `7c8328b` / `a944610`，账本 `docs/BugFixed/Bug修复活账本.md` 条目 14。

## 前置事实（开工前必须核实）

1. **门禁改动不产生测试覆盖**。改 workflow 无法用 pytest 证明，**唯一证据是 CI 实跑**。本地任何推断都不算验证。
2. **run 级结论无意义**。一个 workflow `failure` 不说明问题出在本次改动。必须下钻到 **job 级**，失败 job 再下钻到 **step 级**才能定性。
3. **本仓库历史 0 PR、直推 `master`**，GitHub required status checks 空转。故门禁真实落点是「workflow 内汇总 job」+「下游 workflow 的前置 gate job」，而非分支保护。改动前用 `gh` 或 API 复核此前提是否仍成立。
4. **改 `AGENTS.md` 走 §5.2 `[HALT]` 审批**，须先出补丁原文待用户放行，不得先改后报。

## 工作流

### Step 0 — 先预判两条验证路径（最关键，别跳）

门禁改动通常有**两条必须分别实证的路径**。先想清楚「哪个提交验哪条」，再决定提交怎么切：

| 路径 | 含义 | 制造方式 |
|:---|:---|:---|
| **触发路径** | 依赖变更时 audit 真的执行、汇总真的阻断 | commit 1 改一个**在触发清单内**的文件（如 `security-scan.yml` 自身） |
| **降噪路径** | 依赖未变更时 audit 跳过、汇总**不误报红** | commit 2 只改非依赖文件（`AGENTS.md` / `docs/**`） |

- 触发清单**必须含工作流自身**，否则 commit 1 无法自证触发路径。
- 降噪路径是**易错点所在**：若汇总写成无条件的 `result != success → exit 1`，audit 被有意 skip 时会误红。**这一条只有实跑才能证伪。**

### Step 1 — 本地静态校验（能验的先验，别浪费 CI 轮次）

```bash
python -c "import yaml,sys; [yaml.safe_load(open(f,encoding='utf-8')) for f in sys.argv[1:]]" .github/workflows/*.yml
```

逐项确认（缺一不可）：

- `needs` 引用的 job 都存在；被 `if` 读取的 `needs.X.outputs.Y` 都在 X 里**有声明**
- 无 job 同时含 `uses:` 与 `run:` 的同一 step
- 触发路径正则做**正反双向断言**：必命中清单（各类依赖文件）× 必不命中清单（源码 / 文档 / 其他 workflow），并断言「与文件内正则无漂移」
- 对实际改动集跑一次模拟，确认分流符合预期

**边界必须如实标注**：若本机无法执行 shell（如 Windows 上 `bash` 是无发行版的 WSL shim，`uname -a` 为空、`/c` 盘未映射），则 shell 分支逻辑**本地无法验证**，交由 CI 覆盖，并在账本中标注此边界。不得把「静态复核通过」写成「已验证」。

### Step 2 — 必查的两个门禁缺陷（本次实战各踩一个）

**① fail-open：`git diff | grep` 管道**

```bash
# ✗ 错误：git diff 自身报错时管道失败 → 落入 else → 静默跳过审计却报 success
if git diff --name-only "$BASE" "$SHA" | grep -qE 'pattern'; then
# ✓ 正确：把 git 的退出码与 grep 的匹配结果彻底分开，git 失败即 fail-closed
if ! DIFF_OUT="$(git diff --name-only "$BASE" "$SHA")"; then <按全量处理>; exit 0; fi
if printf '%s\n' "$DIFF_OUT" | grep -qE 'pattern'; then
```

`set -e` 不救场——`if` 条件中的失败按 bash 语义不触发 errexit。

**② shell 注入：`${{ }}` 直插 `run:`**

`workflow_run.head_branch` 可被 fork PR 的分支名影响，而 git ref 仅禁止 ``空格 ~ ^ : ? * [ \`` 与控制字符——**双引号 / 分号 / 管道 / 美元 / 反引号全部合法**。直插会被 bash 在**解析整行时**先执行（`||` 只短路求值、不短路解析），而 `workflow_run` 触发的 workflow 默认可访问 secrets。

```yaml
# ✗ 错误
run: if [ "${{ github.event.workflow_run.head_branch }}" != "master" ]; then
# ✓ 正确：值经 env: 传入，shell 只引用 $VAR（不被二次解析）
env:
  WR_HEAD_BRANCH: ${{ github.event.workflow_run.head_branch }}
run: if [ "$WR_HEAD_BRANCH" != "master" ]; then
```

配套显式收窄 `permissions: contents: read` 作为爆炸半径兜底。

### Step 3 — `workflow_run` 的 SHA 语义陷阱

落笔前查官方事件表确认，**勿凭直觉**：该事件下 `GITHUB_SHA` 是「**默认分支的最新提交**」而非被触发 run 的 head sha。

因此下游 gate 必须校验 `head_sha == GITHUB_SHA`。否则 `actions/checkout`（默认检 `github.sha`）会检出 master tip——**两次推送间隔时会构建到未经审计的新提交**。该相等同时保证 `tags:` 里的 `github.sha` 也指向被审计 commit。

另：官方载明 `workflow_run` **无论前序结论如何都会触发**，故不能靠 job 级 `if` 让下游 job 静默 skipped，必须自己判失败。

### Step 4 — 提交与取证（REST 配额三档降级）

**未认证 REST 配额 60 次/小时**，高频轮询会把自己锁死。按此顺序降级：

| 档 | 手段 | 用法 |
|:--|:---|:---|
| 一 | REST API | `/actions/runs?head_sha=` 拿 run；`/actions/runs/<id>/jobs` 拿 **job 级**结论。**每次轮询只调这 2 个端点，间隔 ≥60s**，不要每 20s 轮询十几分钟 |
| 二 | `webfetch` 抓页面 | 遇 403/429 立即切换：`https://github.com/<owner>/<repo>/actions/runs/<id>`。**输出极长，直接吃满上下文** |
| 三 | 派 subagent 轮询 | 二档输出过长时用 `general` agent 代为轮询并回报压缩结论。派单必须写明「**预期 job 级结论表**」与「**据实回报、不许把未完成猜成 success**」 |

其他纪律：

- 门禁类 workflow 耗时差异极大（本次 17s vs 43m），**别用固定超时**；轮询窗口按最长的那个 job 计。
- 若 job 长时间 `in_progress`，取 `started_at` + 当前 step 名区分「真在算」与「卡死」，不要盲等。
- 一次轮询里用一条 `$j.total_count`/`$fail` 汇总行替代逐 job 罗列，显著省配额与上下文。

### Step 5 — job 级定性（本次实战范例）

拿到结论后**逐条对照预期**，不符即停下定位，**禁止**用 run 级 `failure` 一笔带过：

- 触发路径：探测 job `success` + 两个 audit job `success`（**必须是 success 而非 skipped**，否则说明分流判反了）+ 汇总 job `success`
- 降噪路径：两个 audit `skipped` + 密钥类扫描 `success` + **汇总 job 仍 `success`** ← 最关键一条
- 下游 gate：gate job `success` + 失败 job 的**失败 step 原文**

**失败定性三分类**：

1. 本次改动引入 → 回滚修
2. 既存无关项 → step 级定位原文后明确写「与本条无关」
3. 无法归因 → **据实标注不归因**，不硬套「大概无关」

范例：`安全门禁校验 success` + `Docker Build & Push failure@step4`，报错原文 `Username and password required` → 直接坐实凭据缺失为既存项，**而非**推断。

### Step 6 — 账本回填（证据三要素不可缺）

复用 `resolution-fix-ledger-sync` skill 的条目骨架，本 skill 只补充门禁特有的四项：

1. **每个 run 的 id + 逐 job 结论**（不是 run 级）
2. **失败 step 的 step 号与报错原文**
3. **未验证项显式列出**，并说明为何无法验证（红路径需故意注入漏洞；step 输出值需登录才能看）
4. **本地校验边界**（哪些验了、哪些因环境限制没验）

严禁把「静态复核通过」「预期会跳过」写成「CI 已直证」。

### Step 7 — 诚实性自检（提交前最后一道）

- [ ] 有没有把间接证据当直证？（旁证 ≠ 观测）
- [ ] 有没有把「未出结论」写成 success？
- [ ] 未验证项是否逐条列出并给出原因？
- [ ] 依据不明的日期/数字是否已核对？（如系统日期与 CI 时区窗口不一致时需显式确认）
- [ ] 工作区有无**非本次任务产生的未跟踪文件**？——发现即**原样保留、绝不提交或删除**，并在汇报中单独告知来源存疑
- [ ] commit 是否用 `-F <文件>` 传入？中文 commit message 内含 `|` `$` `{` 时 PowerShell 会解析失败，**必须走文件**

## 反面模式（本次实战避免）

| 反面 | 后果 |
|:---|:---|
| 触发级 `paths:` 做降噪 | workflow 不运行 → check 永不出现 → 日后列入 required checks 时 PR 永久挂起（GitHub 不把「未上报」当通过） |
| 汇总写无条件 `result != success` | audit 有意 skip 时误红 |
| 靠 job 级 `if` 让下游 job 静默跳过失败判定 | 门禁形同虚设，还制造「没报错」的假象 |
| `git diff \| grep` 单管道 | git 报错时静默放行 |
| `${{ }}` 直插 `run:` | pwn-request 注入面 |
| 高频轮询 REST API | 自己耗尽 60 次/小时配额，被迫降级浪费回合 |
| 只记 run 级结论 | 无法区分「门禁生效」与「别的 job 红了」 |
| 一次提交改门禁 + 改文档 | 只能验一条路径，另一条路径的证据永远缺失 |