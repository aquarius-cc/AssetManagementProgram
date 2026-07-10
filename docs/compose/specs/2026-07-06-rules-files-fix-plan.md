# Rules_Fiels 四文件修复方案

> 日期：2026-07-06 | 状态：纯方案，未实施
> 审查发现 10 处问题，按优先级分 3 批修复

---

## 修复总览

| 优先级 | 编号 | 目标文件 | 修复动作 |
|---|---|---|---|
| P0 | 1 | backend-testing-rules.md | T8 迁移命令替换 |
| P1 | 2 | backend-testing-rules.md | T2 工厂强制降级 |
| P1 | 3 | backend-business-rules.md | 状态机图补全两条路径 |
| P1 | 4 | backend-business-rules.md | BR-6 追加存量豁免 |
| P1 | 5 | backend-business-rules.md | B8 补充 recordcode/version |
| P1 | 6 | frontend-business-rules.md | F13 暗色模式降级为建议 |
| P1 | 7 | frontend-business-rules.md | F15 类型位置修正 |
| P2 | 8 | frontend-business-rules.md | FR-5 追加存量豁免 |
| P2 | 9 | frontend-testing-rules.md | T13 vitest 命令修正 |
| P2 | 10 | frontend-testing-rules.md | T15 变异测试标注 PENDING |

---

## P0-1：T8 迁移命令同步根级 CT-6

**文件**：`backend-testing-rules.md`

**修改位置**：第八节（T8）全文 + 第九节命令汇总中的迁移验证部分

**修改内容**：

第八节替换为：
```markdown
## 八、迁移文件安全性验证（宪法 CT-6 落地）[T8]
涉及数据库迁移文件的变更，必须执行以下三步验证：
```bash
# 步骤①：确认无遗漏的迁移文件
python manage.py makemigrations --dry-run 2>&1 | findstr "No changes detected"

# 步骤②：预览待执行迁移列表，人工确认顺序正确
python manage.py migrate --plan

# 步骤③：检查是否包含高风险操作
findstr /N "RemoveIndex RemoveField RenameField" <新增迁移文件名>
```
若步骤③命中任一操作，须在 PR 描述中注明"已人工确认数据无损"，并在 Code Review 阶段重点审查。

**禁止**执行 `python manage.py migrate <app> zero --dry-run` 进行反向迁移验证。

若任一步骤失败或发现未审查的高风险操作，触发 `[HALT]` 并修复迁移文件。
```

第九节命令汇总中删除旧的迁移验证两条命令，替换为上述三条。

---

## P1-2：T2 工厂强制降级

**文件**：`backend-testing-rules.md`

**修改位置**：第二节（T2）

**修改内容**：

将"**强制**使用 factory_boy……**禁止**使用原始 create() 造数据"替换为：

```markdown
## 二、测试数据工厂 [T2]
- **推荐**使用 `factory_boy` 定义工厂类（如 `AssetFactory`、`UserFactory`），新编写的测试**优先**采用工厂模式。
- 现有测试若使用 `TestCase` + 直接 `create()`，保持不变，不触发违规。
- 工厂类统一放在 `tests/factories.py` 中，并在需要时通过 `@pytest.fixture` 注入。
```

核心变化：强制→推荐，禁止→优先。存量测试不追溯。

---

## P1-3：状态机图补全

**文件**：`backend-business-rules.md`

**修改位置**：第三节状态机图 + 规则列表

**替换为**：

```text
                    ┌──────────────────────────────┐
                    │                              │
                    ▼                              │
             in_store ──outasset──→ in_use ──recycle──→ recycled_pending
                │  ▲                 │  ▲                    │
                │  │                 │  │                    │
          broken/lost          broken/lost                   │
                │  │                 │  │                    │
                ▼  │ found_and_return│  │                    ▼
             damaged ◄───────────────┘  └────────────→ damaged
                │
                ▼
             scrapped（终态）
```

完整流转规则：

1. `in_store` → `in_use`：出库（领用/外借）
2. `in_use` → `recycled_pending`：正常回收
3. `in_use` → `broken`：损坏回收（RecycleAsset.is_broken=True）
4. `in_use` → `lost`：遗失回收（RecycleAsset.is_lost=True）
5. `in_store` → `broken`：在库资产直接标记损坏
6. `in_store` → `lost`：在库资产直接标记遗失
7. `recycled_pending` → `in_use`：重新出库
8. `broken` → `damaged`：提交报废申请
9. `lost` → `damaged`：提交报废申请
10. `lost` → `in_store`：找回入库（通过 FoundAsset）
11. `damaged` → `scrapped`：审批通过
12. `damaged` → `broken`：审批拒绝（original_status=broken）
13. `damaged` → `lost`：审批拒绝（original_status=lost）
14. `scrapped`：终态，不可转出

涉及 damaged 状态的变更，必须附加审批记录。

新增了规则 5、6、8、9、10、12、13，覆盖了后端代码已实现但文档未体现的路径。

---

## P1-4：BR-6 追加存量豁免

**文件**：`backend-business-rules.md`

**修改位置**：第四节 BR-6 行

**在"超过时，按职责拆分"后追加**：

```
**存量豁免**：2026-07-07 基线日前已存在的超限文件，须添加 `# TECHNICAL_DEBT: >500 lines` 注释，不触发违规。后续修改时若新增 ≥ 50 行，须同步拆分。新文件严格执行上限。
```

---

## P1-5：B8 补充 recordcode 和 version

**文件**：`backend-business-rules.md`

**修改位置**：第二节 B8 行

**替换为**：
```
| B8 | **模型标准字段** | 所有模型**必须**包含 `created_at`(auto_now_add)、`updated_at`(auto_now)、`is_deleted`(软删)、`recordcode`(全局唯一编码)、`version`(乐观锁，默认1)。Department/Employee/AssetOperationLog 除外 | 继承 BaseModel |
```

新增了 recordcode 和 version，与实际 BaseModel 实现一致。

---

## P1-6：F13 暗色模式降级

**文件**：`frontend-business-rules.md`

**修改位置**：第二节 F13 行

**替换为**：
```
| F13 | **暗色模式（规划中）** | 未来实施暗色模式时，必须使用 `useDark` + CSS 变量驱动，**禁止**写死 `#fff`/`#000`。当前阶段为规划项，不强制执行。 | 未来实施时改用 useDark |
```

核心变化：从"必须"改为"规划中"，当前不强制。

---

## P1-7：F15 类型位置修正

**文件**：`frontend-business-rules.md`

**修改位置**：第二节 F15 行

**替换为**：
```
| F15 | **类型定义位置** | 接口/类型统一放 `src/utils/` 目录下按业务域拆分（如 `Asset.ts`、`OutAsset.ts`），**禁止**组件内定义全局接口 | 迁移至 `src/utils/` |
```

将 `/src/types` 改为 `src/utils/`，与项目实际结构一致。

---

## P2-8：FR-5 追加存量豁免

**文件**：`frontend-business-rules.md`

**修改位置**：第四节 FR-5 行

**在"必须将子模板拆分为独立组件"后追加**：

```
**存量豁免**：2026-07-07 基线日前已存在的超限文件，须添加 `<!-- TECHNICAL_DEBT: >500 lines -->` 注释，不触发违规。后续修改时若新增 ≥ 50 行，须同步拆分。新文件严格执行上限。
```

---

## P2-9：T13 vitest 命令修正

**文件**：`frontend-testing-rules.md`

**修改位置**：第六节 T13 行

**将** `vitest --coverage --threshold 80` **替换为** `vitest --coverage --coverage.threshold=80`

同时更新第六节和第八节变更日志中涉及此命令的所有引用。

---

## P2-10：T15 变异测试标注 PENDING

**文件**：`frontend-testing-rules.md`

**修改位置**：第七节（T15）

**在"必须引入变异测试工具"段落末尾追加**：

```markdown
> **执行状态**：stryker-mutator 尚未安装，本条规则当前标记为 `[PENDING]`。
> 安装命令：`npm install -D @stryker-mutator/core @stryker-mutator/vitest-runner`。
> 安装后须创建 `stryker.conf.json` 配置文件。安装前不阻断合并。
```

---

## 版本号更新与变更日志

### backend-testing-rules.md：v1.2 → v1.3

版本号行改为 `> 版本：v1.3 | 最后更新：2026-07-07`

变更日志末尾追加：
```
- v1.3 (2026-07-07): T8 迁移命令同步根级 CT-6（禁止 zero --dry-run）；T2 工厂强制降级为推荐，存量测试不追溯。
```

### backend-business-rules.md：v1.2 → v1.3

版本号行改为 `> 版本：v1.3 | 最后更新：2026-07-07`

变更日志末尾追加：
```
- v1.3 (2026-07-07): 状态机图扩展至 14 条流转规则；BR-6 追加存量豁免；B8 补充 recordcode/version 字段。
```

### frontend-business-rules.md：v1.2 → v1.3

版本号行改为 `> 版本：v1.3 | 最后更新：2026-07-07`

变更日志末尾追加：
```
- v1.3 (2026-07-07): F13 暗色模式降级为规划中；F15 类型位置修正为 src/utils/；FR-5 追加存量豁免。
```

### frontend-testing-rules.md：v1.2 → v1.3

版本号行改为 `> 版本：v1.3 | 最后更新：2026-07-07`

变更日志末尾追加：
```
- v1.3 (2026-07-07): T13 vitest 命令参数修正；T15 变异测试标注 PENDING。
```

---

## 执行顺序

四个文件互不依赖，可并行修改。修改完成后运行一次交叉检查：

1. 确认 backend-testing T8 命令与根级 CT-6 一致
2. 确认 backend-business BR-6 / 前端 business FR-5 存量豁免文本与根级 DR-5 一致
3. 确认 backend-testing T2 降级后不与现有测试冲突

---

## 收尾检查清单（执行后逐项验证）

### 检查 1：根级与子域迁移命令一致性

- [ ] `AGENTS.md` §1.4 CT-6 命令为 `makemigrations --dry-run ... | findstr` + `migrate --plan` + `findstr RemoveIndex`
- [ ] `backend-testing-rules.md` 第八/九节命令与 CT-6 完全一致
- [ ] 全文搜索 `zero --dry-run` 和 `migrate --check`，两个旧命令均已从 `backend-testing-rules.md` 中删除

### 检查 2：存量豁免三处同步

- [ ] `AGENTS.md` §1.5 DR-5 含 `# TECHNICAL_DEBT` 存量豁免
- [ ] `backend-business-rules.md` BR-6 含相同豁免文本
- [ ] `frontend-business-rules.md` FR-5 含相同豁免文本（用 `<!-- TECHNICAL_DEBT -->` HTML 注释格式）
- [ ] 三处日期均为 2026-07-07，均含"新增 ≥ 50 行须同步拆分"条件

### 检查 3：状态机规则与代码对齐

- [ ] `backend-business-rules.md` 第三节规则列表已扩展到 14 条
- [ ] 规则 8（broken→damaged）在 AssetFSM 代码中有对应方法
- [ ] 规则 9（lost→damaged）在 AssetFSM 代码中有对应方法
- [ ] 规则 10（lost→in_store）在 found_and_return action 中有对应实现
- [ ] 规则 12/13（damaged→broken/lost 审批拒绝）在 reject_to_broken/reject_to_lost 中有对应

### 检查 4：待实施项状态标记

- [ ] `frontend-testing-rules.md` T15 含 `[PENDING]` + npm install 命令
- [ ] `backend-testing-rules.md` T2 含"存量测试不追溯"字样
- [ ] 全文搜索 `PENDING` 列出所有待实施项，确认团队已知悉

### 检查 5：版本号与变更日志

- [ ] 四个文件版本号均已更新至 v1.3
- [ ] 每个文件变更日志末尾有对应 v1.3 条目

### 检查 6：命令汇总一致性

- [ ] `backend-testing-rules.md` 第九节命令汇总中无旧迁移命令
- [ ] `frontend-testing-rules.md` T13 vitest 命令为 `--coverage.threshold=80`（非 `--threshold 80`）
- [ ] `frontend-testing-rules.md` 第八节变更日志中无旧命令引用

---

## 方案审查补充（第二轮自查）

### 已确认无遗漏的项

- P0-1 迁移命令替换：方案文本与根级 CT-6 v3.2.0 完全一致
- P1-3 状态机 14 条规则：每条均可在后端代码中找到对应方法或 action
- P1-5 B8 字段补充：recordcode 和 version 与 BaseModel 实现一致
- P1-7 F15 类型位置：`src/utils/` 与项目 15 个类型文件的实际位置一致

### 方案中需追加说明的 1 处

**P1-3 状态机图的 ASCII 图格式**：方案中提供的 ASCII 状态机图较为复杂，在 Markdown 中可能对齐不良。建议实施时改用纯文本规则列表（已在方案中提供了 14 条文字规则），ASCII 图仅作辅助参考。

### 方案中 1 处边界条件补充

**P1-2 T2 降级后的影响范围**：T2 从"强制"改为"推荐"后，`backend-testing-rules.md` 中引用 T2 的其他章节不受影响——T3（Service 必测场景）和 T4（API 端到端测试）不依赖 factory_boy，使用 `TestCase` + `create()` 即可满足。无级联修改需求。

### 交叉依赖确认

- `backend-testing-rules.md` T8 修改后，`backend-testing-rules.md` 第十节变更日志需追加 v1.3 条目说明"同步根级 CT-6 迁移命令"
- `backend-business-rules.md` 第五节变更日志需追加 v1.3 条目说明"状态机图扩展至 14 条 + BR-6 存量豁免 + B8 字段补充"
- `frontend-business-rules.md` 第五节变更日志需追加 v1.3 条目说明"F13 降级 + F15 修正 + FR-5 存量豁免"
- `frontend-testing-rules.md` 第八节变更日志需追加 v1.3 条目说明"T13 命令修正 + T15 PENDING 标记"

### 最终确认

方案覆盖了审查发现的全部 10 项问题，每项均有明确的文件、位置、替换文本和验证标准。收尾检查清单共 6 大类 17 个子项，执行后可确保修复质量。无遗留问题。
