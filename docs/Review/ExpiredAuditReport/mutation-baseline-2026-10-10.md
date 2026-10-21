# 变异测试基线归档（P1-1 / P1-2 收口）

> 归档日期：2026-10-10 | 工具：Stryker Mutator（前端）| 状态：✅ 前端达标（82.29 ≥ 80）
> P1-1 关闭条件：CI 实测 score ≥ 80 → 移除 `continue-on-error: true`（ci.yml）。本次达标，假绿解除。
> 数据源：GitHub Actions CI Pipeline run `38034281446`（commit `81285a8`），frontend-mutation job `114161870597`。

## 一、环境与口径

| 项 | 值 |
|:---|:---|
| 运行环境 | GitHub Actions `ubuntu-latest`，Node **v22**（stryker 硬守卫要求 ≥22，ci.yml:438 已单独升级） |
| 配置 | `vue-assetmanagement/stryker.config.json`（mutate `src/stores/**/*.ts` + `src/composables/useGroup*.ts`，`thresholds.break: 80`，vitest related） |
| 命令 | `npm run test:mutate` → `stryker run` |
| 耗时 | 15m34s（Done） |
| 平均测试数/mutant | 7.18 tests per mutant |
| 与本地对照 | 本机 Node v24.19.0 本地得分 82.29 / 82.35（stores），与 CI 完全一致，互证口径 |

## 二、得分表（CI 全量）

```text
-------------------------------|--------|---------|----------|-----------|------------|----------|----------|
                               | % Mutation score |          |           |            |          |          |
File                           |  total | covered | # killed | # timeout | # survived | # no cov | # errors |
-------------------------------|--------|---------|----------|-----------|------------|----------|----------|
All files                      |  82.29 |   83.86 |     1413 |         0 |        272 |       32 |        1 |
 composables                   |  81.86 |   82.27 |      167 |         0 |         36 |        1 |        0 |
  useGroupChildrenCache.ts     |  75.86 |   75.86 |       66 |         0 |         21 |        0 |        0 |
  useGroupedAssetColumns.ts    | 100.00 |  100.00 |        9 |         0 |          0 |        0 |        0 |
  useGroupedAssetList.ts       |  88.89 |   88.89 |       24 |         0 |          3 |        0 |        0 |
  useGroupedAssetSelection.ts  |  79.37 |   80.65 |       50 |         0 |         12 |        1 |        0 |
  useGroupedSessionRestore.ts  | 100.00 |  100.00 |       18 |         0 |          0 |        0 |        0 |
 stores                        |  82.35 |   84.08 |     1246 |         0 |        236 |       31 |        1 |
  app.ts                       |  83.12 |   83.12 |       64 |         0 |         13 |        0 |        0 |
  assetStore.ts                |  80.43 |   88.10 |       37 |         0 |          5 |        4 |        0 |
  assetTypeStore.ts            |  42.86 |   50.00 |        3 |         0 |          3 |        1 |        0 |
  auditLogStore.ts             |  92.06 |   95.08 |       58 |         0 |          3 |        2 |        1 |
  auth.ts                      |  76.44 |   77.18 |      159 |         0 |         47 |        2 |        0 |
  authUserStore.ts             |  76.00 |   82.61 |       19 |         0 |          4 |        2 |        0 |
  brokenAssetStore.ts          |  83.33 |  100.00 |        5 |         0 |          0 |        1 |        0 |
  contractStore.ts             |  63.64 |   70.00 |        7 |         0 |          3 |        1 |        0 |
  createEntityStore.ts         |  88.17 |   88.17 |      298 |         0 |         40 |        0 |        0 |
  damagedAssetStore.ts         |  33.33 |   40.00 |        2 |         0 |          3 |        1 |        0 |
  dashboard.ts                 |  82.37 |   82.37 |      243 |         0 |         52 |        0 |        0 |
  departmentStore.ts           |  85.92 |   88.41 |       61 |         0 |          8 |        2 |        0 |
  entityStoreCache.ts          |  97.22 |   97.22 |       35 |         0 |          1 |        0 |        0 |
  entityStoreRequestControl.ts |  69.70 |   69.70 |       46 |         0 |         20 |        0 |        0 |
  foundAssetStore.ts           |  83.33 |  100.00 |        5 |         0 |          0 |        1 |        0 |
  groupedAssetSession.ts       | 100.00 |  100.00 |        9 |         0 |          0 |        0 |        0 |
  harddiskSnStore.ts           |  44.44 |   57.14 |        4 |         0 |          3 |        2 |        0 |
  lostAssetStore.ts            |  78.57 |   84.62 |       11 |         0 |          2 |        1 |        0 |
  networkStore.ts              | 100.00 |  100.00 |        4 |         0 |          0 |        0 |        0 |
  notificationStore.ts         |  96.88 |   96.88 |       31 |         0 |          1 |        0 |        0 |
  operationLogStore.ts         |  66.67 |   72.73 |        8 |         0 |          3 |        1 |        0 |
  outAssetStore.ts             |  50.00 |   57.14 |        4 |         0 |          3 |        1 |        0 |
  recycleAssetStore.ts         |  83.33 |  100.00 |        5 |         0 |          0 |        1 |        0 |
  repairAssetStore.ts          |  80.00 |   85.71 |       12 |         0 |          2 |        1 |        0 |
  roleStore.ts                 |  71.43 |   78.95 |       15 |         0 |          4 |        2 |        0 |
  storageStore.ts              |  50.00 |   57.14 |        4 |         0 |          3 |        1 |        0 |
  unregisteredAssetStore.ts    |  42.86 |   50.00 |        3 |         0 |          3 |        1 |        0 |
  userStore.ts                 |  88.12 |   89.90 |       89 |         0 |         10 |        2 |        0 |
  wasteAssetStore.ts           |  83.33 |  100.00 |        5 |         0 |          0 |        1 |        0 |
-------------------------------|--------|---------|----------|-----------|------------|----------|----------|
```

> `Final mutation score of 82.29 is greater than or equal to break threshold 80`（MutationTestReportHelper，CI 日志原文）。

## 三、关键发现（P1-1 根因）

在本次 Node 22 修复前，CI 上 stryker **从未真正执行过**：

1. `ci.yml:12` 原为 `NODE_VERSION: "20"`，frontend-mutation job 使用 Node 20.20.2；
2. `@stryker-mutator/core` 的 `engines.node = ">=22.0.0"` 是**启动硬守卫**（非 warning）；
3. Node 20 下 `stryker run` 立即抛错 exit 1（`Error: Node.js version v20.20.2 detected. StrykerJS requires version to match >=22.0.0`）；
4. step 级 `continue-on-error: true` 将该崩溃吞成 job 绿（run 114 实证）。

因此 P1-1「假绿」的真实形态不是「分数低被掩盖」，而是「分数根本不存在」。项目自身 `engines` 为 `^20.19.0 || ≥22.12.0`（Node 20 合法），故修复方案为**仅 frontend-mutation job 例外升级 Node 22**（ci.yml:438），其余 6 个 Node job 保持 20 不动。

## 四、低分文件（C 批补测候选，非阻断）

以下文件得分 < 80，是后续补测的优先目标（本次不阻断合并，仅登记）：

| 文件 | 得分 | survived | no_cov |
|:---|---:|---:|---:|
| `damagedAssetStore.ts` | 33.33 | 3 | 1 |
| `unregisteredAssetStore.ts` | 42.86 | 3 | 1 |
| `assetTypeStore.ts` | 42.86 | 3 | 1 |
| `harddiskSnStore.ts` | 44.44 | 3 | 2 |
| `outAssetStore.ts` | 50.00 | 3 | 1 |
| `storageStore.ts` | 50.00 | 3 | 1 |
| `contractStore.ts` | 63.64 | 3 | 1 |
| `operationLogStore.ts` | 66.67 | 3 | 1 |
| `entityStoreRequestControl.ts` | 69.70 | 20 | 0 |
| `roleStore.ts` | 71.43 | 4 | 2 |
| `useGroupChildrenCache.ts` | 75.86 | 21 | 0 |
| `authUserStore.ts` | 76.00 | 4 | 2 |
| `auth.ts` | 76.44 | 47 | 2 |
| `lostAssetStore.ts` | 78.57 | 2 | 1 |

## 五、变更清单（本次）

| 文件 | 变更 |
|:---|:---|
| `ci.yml:433-440` | frontend-mutation job `node-version: "22"`（原 `${{ env.NODE_VERSION }}`=20，stryker 启动崩溃根因） |
| `ci.yml:442-449` | 移除 step 级 `continue-on-error: true`（P1-1 假绿解除，score ≥ 80 达成） |
| `ci.yml:450-455` | 新增 `upload-artifact` 上传 `reports/mutation/`（JSON+HTML 报告存档） |
| `ci.yml:478-487` | ci-summary 新增 frontend-mutation 阻断分支（与 backend-mutation 同构） |
