# AGENTS.md 生产化修复方案（最终版）

> 版本：v1.0 | 日期：2026-07-06
> 基础：用户 8 项修复方案 + 4 处优化改进
> 状态：纯方案，未实施

---

## 执行拓扑（修改顺序）

```
Phase 1（并行，无依赖）:
  ├── P0-1  CT-6 迁移验证命令
  └── P0-2  DR-5 存量豁免条款

Phase 2（并行，无依赖）:
  ├── P1-1  CT-2 覆盖率执行脚本
  ├── P1-2  SC-7 CI 配置模板
  └── P1-3  DR-5 降为 P1（Phase 1 仅加注释，规则文本更新放此处）

Phase 3（并行，无依赖）:
  ├── P2-1  OC-4/OC-7 条件触发
  └── P2-2  AR-2 替换为高风险标注

Phase 4（依赖 Phase 1~3 全部完成）:
  ├── P3-1  审计票拆分（必填/自检折叠）
  ├── P3-2  沙盒期前置条件
  └── P3-3  子引擎审计票同步
```

> Phase 4 必须最后执行，因为它引用了前三个阶段修改后的规则编号和格式。

---

## P0-1：CT-6 迁移验证命令替换

**文件**：`AGENTS.md` §1.4 CT-6 行

**原文**：
```
| CT-6 | **迁移文件可逆性验证**：任何包含数据库迁移（仅适用于后端项目，前端自动豁免）
（`migrations/`）的PR，**必须**执行 `python manage.py migrate --check` 和
`python manage.py migrate <app> zero --dry-run`，确保迁移可逆且不损坏数据。
| 触发 `[HALT]`，修复迁移文件 |
```

**替换为**：
```
| CT-6 | **迁移文件安全性验证**：任何包含数据库迁移（`migrations/`）的 PR，必须执行以下三步验证：<br>
① `python manage.py makemigrations --dry-run 2>&1 | findstr "No changes detected"` — 确认无遗漏迁移<br>
② `python manage.py migrate --plan` — 预览待执行列表，人工确认顺序正确<br>
③ 对本次新增迁移文件执行 `findstr /N "RemoveIndex RemoveField RenameField" <文件名>` — 若命中任一操作，须在 PR 描述中注明"已人工确认数据无损"，并在 Code Review 阶段重点审查。<br>
**禁止**执行 `migrate <app> zero --dry-run` 进行反向迁移验证。 | 触发 `[HALT]`，修复迁移文件 |
```

**改进说明**：
- 第一步从 `makemigrations --check`（退出码不稳定）改为检查输出文本，跨平台兼容
- 第三步使用 Windows `findstr` 替代 `grep`（项目运行在 Windows 环境）
- 明确禁止 `zero --dry-run`，与今日 0013 迁移死锁教训一致

---

## P0-2：DR-5 存量豁免条款

**文件**：`AGENTS.md` §1.5 DR-5 行

**在原文"超限即触发重构拆分。"后追加**：

```
<br>**存量豁免**：在 2026-07-07 基线日之前已存在的超限文件，须在文件头部添加
`# TECHNICAL_DEBT: >500 lines` 注释，不触发 `[HALT]`。存量文件后续被修改时，
若本次新增代码量 ≥ 50 行，必须同步将文件拆分至 ≤ 500 行。<br>
**新文件从严**：2026-07-07 之后新建的文件，严格执行 ≤ 500 行红线。
```

**违规后果列**不变，仍为"触发 `[HALT]`，强制拆分"。

---

## P1-1：CT-2 覆盖率执行脚本

**文件**：`AGENTS.md` §1.4 CT-2 行

**在原文"CI失败，**禁止**合并代码"下方追加**：

```
> **执行方式**（CI 配置完成前可本地执行）：<br>
> 1. 首次安装：`pip install coverage pytest-cov`<br>
> 2. 整体覆盖率：`coverage run manage.py test assetmanagement && coverage report --fail-under=80 --show-missing`<br>
> 3. 核心模块专项：`coverage report --include="**/services/*,**/selectors/*" --fail-under=90`<br>
> 4. CI 就绪前，覆盖率检查标记为 `[PENDING]`，不阻断合并；CI 就绪后自动转为硬性门禁。
```

---

## P1-2：SC-7 CI 配置模板

**文件**：`AGENTS.md` §6 SC-7 行

**在原文"阻断CI"下方追加**：

```
> **CI 配置模板**（需在 `.github/workflows/security-scan.yml` 中创建）：<br>
> ```yaml
> name: Dependency Security Scan
> on: [pull_request]
> jobs:
>   security-scan:
>     runs-on: ubuntu-latest
>     steps:
>       - uses: actions/checkout@v4
>       - name: Python dependency audit
>         run: pip install pip-audit && pip-audit --fail-on=high
>       - name: Node dependency audit
>         run: npm audit --audit-level=high
> ```<br>
> **执行状态**：CI workflow 配置完成前标记为 `[PENDING]`，不阻断合并；完成后自动转为硬性门禁。
```

---

## P1-3：DR-5 规则文本确认更新

**说明**：P0-2 已在 DR-5 中追加存量豁免文本。此处确认 DR-5 的违规后果仍为"触发 `[HALT]`，强制拆分"，但审计票标记逻辑调整（见 P3-1）。

DR-5 完整最终文本（P0-2 + 此处合并）：

```
| DR-5 | **文件/函数规模硬上限**：单个源文件（`.py`/`.vue`/`.ts`）**不得超过 500 行**；
单个函数/方法**不得超过 50 行**（不含空行和注释）。超限即触发重构拆分。
**存量豁免**：在 2026-07-07 基线日之前已存在的超限文件，须在文件头部添加
`# TECHNICAL_DEBT: >500 lines` 注释，不触发 `[HALT]`。存量文件后续被修改时，
若本次新增代码量 ≥ 50 行，必须同步将文件拆分至 ≤ 500 行。
**新文件从严**：2026-07-07 之后新建的文件，严格执行 ≤ 500 行红线。 |
触发 `[HALT]`，强制拆分 | 全端 |
```

---

## P2-1：OC-4 / OC-7 条件触发改造

**文件**：`AGENTS.md` §7

**OC-4 原文替换为**：
```
| OC-4 | **Prometheus 指标暴露**：核心业务接口在**实际 QPS > 10** 的场景下，
必须暴露 Prometheus 指标（请求总数、错误总数、耗时直方图含 P50/P90/P99）。
当前阶段（QPS 未达阈值）标记为 `[~]` 豁免。 |
触发 `[HALT]`（若 QPS 达标却未实施） |
```

**OC-7 原文替换为**：
```
| OC-7 | **性能基准门禁**：核心接口在**实际 QPS > 10** 的场景下，P95 响应耗时
不得劣化超过 20%（相比上一次基线）。CI 阶段应自动对比历史数据，若无基线则豁免。
当前阶段标记为 `[~]` 豁免。 |
触发 `[HALT]`，必须优化或调整基线（若 QPS 达标） |
```

---

## P2-2：AR-2 替换为高风险标注规则

**文件**：`AGENTS.md` §8 AR-2 行

**原文整体替换为**：
```
| AR-2 | **高风险代码强制标注**：AI 生成以下三类代码时，必须在代码上方添加
`# AI_REVIEW_NEEDED: <描述>` 注释：<br>
① **第三方库 API 调用**：参数含义、异常类型或返回值不确定时（如 `requests.post(timeout=?)`），
标注 `# AI_REVIEW_NEEDED: verify timeout value`。<br>
② **正则表达式**：所有生成的正则表达式，标注
`# AI_REVIEW_NEEDED: regex validation required`。<br>
③ **复杂条件分支**：`if/elif` 嵌套 ≥ 3 层的逻辑块，标注
`# AI_REVIEW_NEEDED: review branch logic`。<br>
人工复查通过后移除此注释。 | 人工复查 |
```

---

## P3-1：审计票拆分（必填 + 自检折叠）

**文件**：`AGENTS.md` §4

**原文整体替换为**：

```markdown
## §4 最终审计票（全局通用）

AI 在任务完成后，必须输出以下审计票：

### 必填项（每次必须逐项确认，缺一不可）

[审计票 - 必填项]
- 读取规范：已读 [后端/前端] AGENTS & Rules
- CT-1[√] CT-3[√] CT-5[√] — 核心测试覆盖 / 状态机全路径 / 测试失败阻塞
- DR-1[√] DR-5[√/豁免] — 业务逻辑唯一实现 / 文件规模（存量豁免标记）
- SC-1[√] SC-3[√] — 密钥硬编码禁止 / SQL 注入防护
- 跨端契约：未破坏
- 红线触发：无 / [HALT]已确认
- 建议提交：是 / 否

### 自检项（默认通过，仅触发异常时标注 [x] 并附说明）

[审计票 - 自检项]
- 测试：CT-2[√] CT-4[√] CT-6[√]
- DRY：DR-2[√] DR-3[√] DR-4[√] DR-6[√]
- 安全：SC-2[√] SC-4~SC-8[√]
- 可观测性：OC-1~OC-3[√] OC-4[~] OC-5[~] OC-6[√] OC-7[~]
- AI鲁棒性：AR-1~AR-5[√]
- 覆盖率：整体 XX%（≥80%）/ 核心 XX%（≥90%）
```

**审计票必填项从 20+ 压缩到 8 个确认点。自检项分组折叠，不逐条展开。**

---

## P3-2：沙盒期前置条件声明

**文件**：`AGENTS.md` §5.4

**在"当新增或收紧任何红线"段落之前插入**：

```markdown
> **前置条件**：本机制的自动化统计能力依赖以下 CI 基础设施就绪：<br>
> ① GitHub Actions 静态分析 job（集成 ruff / ESLint）<br>
> ② 违规数据采集与存储（GitHub API + 简易脚本）<br>
> ③ 团队通知渠道（钉钉/飞书/邮件 webhook）<br>
>
> **在 CI 就绪前**，沙盒期采用人工替代方案：由项目负责人每周手动运行
> `ruff check . --statistics` 和 `npx eslint . --format json`，
> 生成违规 Top 10 清单，在团队周会中同步。
```

---

## P3-3：子引擎审计票同步

**涉及文件**：
- `asset_management_backend/AGENTS.md` §3
- `vue-assetmanagement/AGENTS.md` §3

**后端审计票替换为**：

```markdown
## §3 最终审计票

### 必填项

[审计票-后端 - 必填项]
- 读取规范：已读 AGENTS & Rules
- 分层架构：Model/Selector/Service/Serializer/View 职责清晰
- 事务装饰器：已添加 / 无需
- CT-1[√] CT-3[√] CT-5[√]
- DR-1[√] DR-5[√/豁免]
- SC-1[√] SC-3[√]
- 跨端契约：未破坏
- 红线触发：无 / [HALT]已确认
- 建议提交：是 / 否

### 自检项

[审计票-后端 - 自检项]
- 测试：CT-2[√] CT-4[√] CT-6[√]
- DRY：DR-2~DR-4[√] DR-6[√]
- 安全：SC-2[√] SC-4~SC-8[√]
- 可观测性：OC-1~OC-3[√] OC-4[~] OC-5[~] OC-6[√] OC-7[~]
- AI鲁棒性：AR-1~AR-5[√]
- 覆盖率：整体 XX% / Service 层 XX%
```

**前端审计票**：将后端模板中的"分层架构"替换为"组件语法 / 设计令牌 / 样式隔离"，其余一致。

---

## 修改文件总览

| 文件 | 修改章节 | 涉及优先级 |
|---|---|---|
| `AGENTS.md` | §1.4 CT-6 | P0-1 |
| `AGENTS.md` | §1.5 DR-5 | P0-2 + P1-3 |
| `AGENTS.md` | §1.4 CT-2（追加执行脚本） | P1-1 |
| `AGENTS.md` | §6 SC-7（追加 CI 模板） | P1-2 |
| `AGENTS.md` | §7 OC-4, OC-7 | P2-1 |
| `AGENTS.md` | §8 AR-2 | P2-2 |
| `AGENTS.md` | §4 审计票 | P3-1 |
| `AGENTS.md` | §5.4 沙盒期 | P3-2 |
| `asset_management_backend/AGENTS.md` | §3 审计票 | P3-3 |
| `vue-assetmanagement/AGENTS.md` | §3 审计票 | P3-3 |

**共 3 个文件，10 处修改。**
