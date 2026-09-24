# 变异测试基线归档（F-P2-4）

> 归档日期：2026-09-24 | 工具：Stryker Mutator（@stryker-mutator/vitest-runner）| 范围：frontend 聚焦基线
> 后端 mutmut：WSL pip 网络不可达（Errno 101），本地 [PENDING]，兜底走 CI（`.github/workflows/ci.yml` mutmut 步骤）

## 一、环境与口径

| 项 | 值 |
|:---|:---|
| 配置 | `vue-assetmanagement/stryker.config.json`（mutate `src/stores/**/*.ts`，thresholds break 80，vitest related，concurrency 4） |
| 聚焦范围 | 7 个 store：`brokenAssetStore` / `entityStoreCache` / `foundAssetStore` / `networkStore` / `recycleAssetStore` / `wasteAssetStore` / `dashboardStatusGroups`（mutate 参数列 7 文件，Stryker Instrumented 7） |
| Dry-run | 519 tests / 1m09s，perTest coverage |
| 耗时 | 3m51s（Done） |
| 全量预估 | 7318 mutants / ETA ~280h → **不可行**，需分批或 ignoreStatic |

## 二、得分表（全量行摘录）

```text
----------------------|--------|---------|----------|-----------|------------|----------|----------|
File                  |  total | covered | # killed | # timeout | # survived | # no cov | # errors |
----------------------|--------|---------|----------|-----------|------------|----------|----------|
All files             |  60.00 |   62.07 |       72 |         0 |          44 |        4 |        0 |
 brokenAssetStore.ts  |  52.63 |   55.56 |       10 |         0 |          8 |        1 |        0 |
 entityStoreCache.ts  |  75.68 |   75.68 |       28 |         0 |          9 |        0 |        0 |
 foundAssetStore.ts   |  52.63 |   55.56 |       10 |         0 |          8 |        1 |        0 |
 networkStore.ts      |  80.00 |   80.00 |        4 |         0 |          1 |        0 |        0 |
 recycleAssetStore.ts |  50.00 |   52.63 |       10 |         0 |          9 |        1 |        0 |
 wasteAssetStore.ts   |  50.00 |   52.63 |       10 |         0 |          9 |        1 |        0 |
----------------------|--------|---------|----------|-----------|------------|----------|----------|
```

- **总体 mutation score = 60.00**（killed 72 / survived 44 / no-cov 4 / timeout 0 / errors 0）
- 低于 thresholds.break=80 → Stryker exit 1（符合预期，作为基线存档）
- HTML 报告：`vue-assetmanagement/reports/mutation/mutation.html`（gitignored）

## 三、结论与后续

1. F-P2-4 标记为 **🟡 部分完成 2026-09-24**：前端聚焦基线已跑通并归档；得分 60 < 80，不满足「得分≥80 归档」终态。
2. 差距主因：static mutants 56/120（47%）占预估 87% 耗时；`broken/found/recycle/waste` 四 store 仅正向 CRUD 断言，边界/失败分支 survived 偏多。
3. 后续动作（不在本轮）：
   - stryker 开 `ignoreStatic` 或按文件分批（entityStoreCache 已 75.68、network 已 80，优先补四 CRUD store 的失败/边界用例）；
   - 后端 mutmut 待网络恢复或 CI 产出 `mutation_results`；
   - 全量 `src/stores/**/*.ts` 分批跑，逐步逼近 break 80。

*归档人：opencode（mimo-v2.6-flash-free）｜关联：F-P2-4 / BF-042 / T16*
