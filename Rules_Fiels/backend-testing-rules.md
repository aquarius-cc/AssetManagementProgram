# 后端测试细则 (Backend Testing Rules)
> 版本：v1.5 | 最后更新：2026-09-30
> 适用范围：pytest + pytest-django + factory_boy + mutmut（变异测试）

## 一、测试目录与命名 [T1]
- 每个 Django app 下创建 `tests/` 目录，按层级拆分：
  - `test_models.py`
  - `test_selectors.py`
  - `test_services.py`（重点：业务逻辑）
  - `test_views.py`（API 端到端）
- 测试类命名：`Test<ModelName>Service`、`Test<ViewName>API`
- 测试方法命名：`test_<scenario>_<expected_behavior>`（如 `test_checkout_success`）

## 二、测试数据工厂 [T2]
- **强制**使用 `factory_boy` 定义工厂类（如 `AssetFactory`、`UserFactory`），**禁止**使用原始 `create()` 造数据。
- 工厂类统一放在 `tests/factories.py` 中，并在需要时通过 `@pytest.fixture` 注入。

## 三、Service 层必测场景（宪法 CT-1/CT-3 落地）[T3]
针对每个资产状态变更方法（`checkout`、`recycle`、`mark_damaged` 等），必须覆盖：
- **正常路径**：合法流转，断言状态变更、审计日志生成。
- **异常路径**：非法流转（如从 `in_store` 直接 `scrapped`），断言抛出 `ValidationError`。
- **事务回滚**：模拟中途失败（如审计日志写入异常），断言数据库无脏数据。

## 四、API 端到端测试 [T4]
- 使用 `APIClient`，模拟认证（JWT Token）。
- 测试项目：
  - 鉴权失败返回 401。
  - 参数缺失/格式错误返回 400。
  - 成功请求返回 200，响应结构符合 `{"code":0, "data":..., "message":"success"}`。
  - 分页接口验证 `page`/`page_size` 参数生效。

## 五、断言与代码风格 [T5]
- 推荐使用精确断言（如 `assertEqual(len(qs), 1)`），**避免** `assertTrue(len(qs) == 1)` 等模糊断言。
- 测试 docstring 应直接描述预期行为，**不加** "Tests that" 等前缀（例如：`"""Should raise ValidationError when status transition is invalid."""`）。

## 六、核心模块覆盖率专项检查（宪法 CT-2 落地）[T6]

整体覆盖率 80% 由 `--cov-fail-under=80` 卡住，但**核心模块（Service 层）必须达到 90%**，执行以下专项命令进行验证：

```bash
# 单独检查 Service 层覆盖率（以 assetmanagement 为例）
pytest --cov=apps.assetmanagement.services --cov-fail-under=90
```
- 若核心模块覆盖率 < 90%，即使整体达标，也必须触发 `[HALT] `并补测。

- 在审计票中必须分别报告：整体覆盖率：XX% 与 Service 覆盖率：XX%。

## 七、变异测试（强化测试有效性）[T7]
| 规则ID	| 内容 |
| :--- | :--- |
| T7	| 必须引入变异测试工具（mutmut，已在 `requirements/dev.txt` 钉 `mutmut==3.8.0`），对核心业务代码（Service 层）执行变异测试，变异通过率（Killed Mutants + Timeout）必须保持**不回归**：本 run 得分不得低于 `asset_management_backend/mutmut-baseline.json` 记录的基线。 |

**门禁策略修订（B批，2026-09-30）**：
- **判分口径 = mutmut 官方公式** `(killed + timeout) / (total - skipped) × 100`（timeout 计入杀灭）。
- **绝对红线 80% 暂挂沙盒期（根级 §5.4）**：首基线 70.44%（BF-066 全量首跑，1959 mutants）低于 80%，若立刻用绝对红线会让 CI 恒红且无法补测推进。改为**相对基线不回归**：每轮只拦「跌破基线」的回归，补测抬分后**人工更新 `mutmut-baseline.json`** 抬高基线，直至达 80% 后恢复绝对红线并解除沙盒。
- 沙盒期留痕：本变动登记于 `docs/BugFixed/Bug修复活账本.md` BF-064/BF-066；期满（14 自然日）人工复核后转为绝对红线硬门禁。

**执行命令**（配置唯一事实源为 `asset_management_backend/setup.cfg` 的 `[mutmut]` 段，命令不传任何参数）：
```bash
# 运行变异测试（须在 asset_management_backend 目录下执行）
mutmut run

# 导出并判分（比率真源；`mutmut results` 只列非 killed 且无 total 行，无法算比率）
mutmut export-cicd-stats
python -c 'import json;s=json.load(open("mutants/mutmut-cicd-stats.json"));t=s["total"]-s["skipped"];print(round((s["killed"]+s["timeout"])/t*100,2),"%")'

# 交互式查看明细
mutmut browse
```
得分口径：`(killed + timeout) / (total - skipped) × 100`，与 CI `backend-mutation` 门禁一致。
若得分 < 基线（`mutmut-baseline.json`）或 == 0，触发 `[HALT]`并补充/完善测试用例。

**易错点**（配置细节见 `setup.cfg` 内注释，此处仅列使用侧约束）：
- **平台限制**：mutmut 3.x 拒绝在 Windows 原生运行（直接 `sys.exit(1)`），只能在 Linux/macOS 执行。
- **变异范围**：当前 `[mutmut] source_paths` 只含 `apps/assetmanagement/services`。扩大范围须同步
  评估耗时（3.x 首次运行为全量），并确认 `also_copy` 仍能覆盖测试的全部可导入路径。
- **不可手工传 CLI 旗标**：CI 与本地共用 `setup.cfg`，传参会造成双口径。
## 八、迁移验证（宪法 CT-6 落地）[T8]
涉及数据库迁移文件的变更，必须执行以下三步验证（与根级 CT-6 对齐）：
```bash
# ① 确认无遗漏迁移
python manage.py makemigrations --dry-run 2>&1 | findstr "No changes detected"

# ② 预览待执行迁移列表，人工确认顺序正确
python manage.py migrate --plan

# ③ 检查新增迁移文件是否包含危险操作（RemoveIndex/RemoveField/RenameField）
findstr /N "RemoveIndex RemoveField RenameField" <迁移文件名>
```
- 若步骤 ① 未命中 "No changes detected"，说明有遗漏迁移，必须触发 `[HALT]`。
- 若步骤 ③ 命中任一危险操作，须在 PR 描述中注明"已人工确认数据无损"，并在 Code Review 阶段重点审查。
- **禁止**执行 `migrate <app> zero --dry-run` 进行反向迁移验证（根级 CT-6 明令禁止）。

## 九、覆盖率与变异测试执行命令汇总
```bash
# 整体覆盖率检查（红线 80%）
pytest --cov=. --cov-fail-under=80

# 核心 Service 层专项检查（红线 90%，需逐个 App 执行）
pytest --cov=apps.assetmanagement.services --cov-fail-under=90
pytest --cov=apps.authusermanagement.services --cov-fail-under=90
pytest --cov=apps.usermanagement.services --cov-fail-under=90
pytest --cov=apps.unregisteredasset.services --cov-fail-under=90

# 查看详细 HTML 报告
pytest --cov=. --cov-report=html

# 变异测试（配置见 setup.cfg [mutmut]；T7 相对基线不回归，基线见 mutmut-baseline.json）
mutmut run
mutmut export-cicd-stats
python -c 'import json;s=json.load(open("mutants/mutmut-cicd-stats.json"));t=s["total"]-s["skipped"];print(round((s["killed"]+s["timeout"])/t*100,2),"%")'

# 迁移验证（与根级 CT-6 对齐，三步法）
python manage.py makemigrations --dry-run 2>&1 | findstr "No changes detected"
python manage.py migrate --plan
findstr /N "RemoveIndex RemoveField RenameField" <迁移文件名>
```

## 十、变更日志
- **v1.5 (2026-09-30)**：T7 门禁口径修订（B批决策，人工审批）——判分公式改为 mutmut 官方公式 `(killed+timeout)/(total-skipped)×100`（timeout 计入杀灭）；绝对红线 80% 暂挂沙盒期（根级 §5.4），改为**相对基线不回归**（基线存 `asset_management_backend/mutmut-baseline.json`，首基线 70.44% 取自 BF-066 全量首跑），补测抬分后人工更新基线直至恢复 80% 绝对红线。同步修订 §九 变异命令为官方口径。配套改动：`.github/workflows/ci.yml` backend-mutation 门禁（移两处 `continue-on-error`、ci-summary 纳入 result 判定）。
- **v1.4 (2026-09-29)**：T7 与 §九 命令汇总改写为 mutmut 3.8.0 口径——删除 2.x 的 `pip install mutmut`、`--paths-to-mutate`（3.x 已弃用并发 DeprecationWarning）、`mutmut results`（只列非 killed 且无 total 行，无法算比率）；改为 `mutmut run`（配置唯一事实源改为 `setup.cfg` 的 `[mutmut]` 段，命令不传参，消除 CI/本地双口径）+ `mutmut export-cicd-stats` 判分。补充得分口径公式（`killed/(total-skipped)`，与 CI 门禁一致）与三条易错点（Windows 拒绝运行、变异范围扩评耗时、不可手工传旗标）。依据后端 AGENTS §4.2，经人工审批后应用；配套改动见 `docs/BugFixed/Bug待修复计划-20260929.md` §3.10。

- **v1.3 (2026-07-09)**：修复 S-1——T8 和命令汇总中移除被根级 CT-6 禁止的 `migrate <app> zero --dry-run` 命令，替换为 CT-6 许可的三步验证法；补充多 App 覆盖率检查命令。

- **v1.2 (2026-07-07)**：新增第八节"迁移验证（T8）"，落地宪法 CT-6。

- v1.1 (2026-07-07): 新增第七节"变异测试"（T7），提升测试有效性。

- v1.0 (2026-07-07): 初始版本，从综合测试规则中拆分，专供后端使用。