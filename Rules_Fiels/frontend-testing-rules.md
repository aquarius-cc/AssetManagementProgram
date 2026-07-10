
---

### 📄 文档 7：前端测试细则 `/Rules_Fiels/frontend-testing-rules.md` (v1.3)

# 前端测试细则 (Frontend Testing Rules)
> 版本：v1.4 | 最后更新：2026-07-09
> 适用范围：Vitest + Vue Test Utils + Vue 3.5 + Vitest 变异测试插件

## 一、测试文件位置 [T9]
- 组件测试文件（`*.spec.ts`）与组件同目录存放（推荐），或统一放置在 `src/__tests__/`。
- 命名：`<ComponentName>.spec.ts`，如 `AssetTable.spec.ts`。

## 二、Store 层必测（宪法 CT-1/CT-2 落地）[T10]
针对每个 Pinia Store 的 `actions`（如 `fetchAssets`、`createAsset`），必须覆盖：
- **成功场景**：请求正常返回数据，断言状态（`assets`）更新、`loading` 切换。
- **异常场景**：请求失败，断言错误状态、错误信息提示。
- **边界情况**：空数据、网络超时等。

## 三、组件交互测试 [T11]
- 使用 `@vue/test-utils` 的 `mount` 挂载组件，`trigger` 模拟点击、输入等。
- 测试正向交互（如点击"领用"按钮后触发对应事件）和边界情况（如必填项为空时提示错误）。
- 使用 `emitted()` 检测事件是否触发及携带的参数。
- 对于异步操作（如 `await nextTick()` 或 `flushPromises`），必须等待 DOM 更新后再断言。

## 四、API Mock 强制 [T12]
- **禁止**在单元测试中发起真实网络请求，必须使用 `vi.mock()` 模拟 `axios` / `fetch`。
- 模拟需覆盖成功和失败两种响应。
- 示例：
  ```typescript
  vi.mock('@/api/asset', () => ({
    getAssets: vi.fn().mockResolvedValue({ data: [...] })
  }))
  ```
## 五、设计令牌回归测试（宪法 CT-4 落地）[T13]
- 针对涉及样式变化的组件（如主题色切换），建议编写快照测试（`toMatchSnapshot()`）或显式断言 CSS 变量值。

- 当 F1-F5 设计令牌变更时，运行快照测试可快速发现视觉回归。

## 六、整体覆盖率检查（宪法 CT-2 落地）[T14]
- 整体红线（宪法 CT-2）：`vitest --coverage --threshold 80`
- 若整体覆盖率 < 80%，触发 `[HALT]` 并补测。

## 七、核心 Store 层覆盖率专项检查（宪法 CT-2 落地）[T15]
- 核心模块专项红线（Pinia Store 层）：需在 `vitest.config.ts` 中配置 `coverage.thresholds`，或单独运行带路径的测试：
```bash
vitest --coverage --coverage.include="src/stores/**/*.ts"
```
（运行后人工核对 Store 覆盖率是否 ≥ 90%）

- 若核心 Store 覆盖率 < 90%，即使整体达标，也必须触发 `[HALT]` 并补测。

- 审计票格式：整体覆盖率：XX% | Store 覆盖率：XX%。

## 八、变异测试（强化测试有效性）[T16]
必须使用 Vitest 变异测试插件（`vitest-mutant` 或 `@vitest/mutate`），对核心 Store/Composable 逻辑执行变异测试，**变异通过率必须 ≥ 80%**。

> **工具选型说明**：项目已使用 Vitest 作为测试框架，为保持工具链一致性，**禁止**引入 Stryker 等外部变异测试工具。变异测试插件需在 `vitest.config.ts` 中配置。

执行命令：
```bash
npx vitest --mutate
```
若通过率 < 80%，触发 `[HALT]` 并补充/完善测试用例。

## 九、变更日志
- **v1.4 (2026-07-09)**：修复 T8 ID 冲突——规则编号从 T8-T15 重编号为 T9-T16，消除与后端 T8 的重叠。

- **v1.3 (2026-07-09)**：修复 S-6——拆分 T13/T14 为独立规则，消除编号歧义；明确前端变异测试工具选型为 Vitest 插件，禁止引入 Stryker。

- **v1.2 (2026-07-07)**：补全规则ID T8~T14，使编号体系完整对齐子引擎要求。

- v1.1 (2026-07-07): 新增第七节"变异测试"（T15），提升测试有效性。

- v1.0 (2026-07-07): 初始版本，从综合测试规则中拆分，专供前端使用。