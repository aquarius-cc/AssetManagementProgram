# 变异测试基线归档（F-P2-4）

> 归档日期：2026-09-24 | 工具：Stryker Mutator（前端）+ mutmut 2.5.1（后端）| 状态：🟡 部分完成
> F-P2-4 关闭条件：得分≥80 归档 —— 前端 60.00、后端 65.63，均未达标，基线存档供补测对照。

## 一、前端 Stryker 基线

### 1.1 环境与口径

| 项 | 值 |
|:---|:---|
| 配置 | `vue-assetmanagement/stryker.config.json`（mutate `src/stores/**/*.ts`，thresholds break 80，vitest related，concurrency 4） |
| 聚焦范围 | 7 个 store：`brokenAssetStore` / `entityStoreCache` / `foundAssetStore` / `networkStore` / `recycleAssetStore` / `wasteAssetStore` / `dashboardStatusGroups`（mutate 参数列 7 文件，Stryker Instrumented 7） |
| Dry-run | 519 tests / 1m09s，perTest coverage |
| 耗时 | 3m51s（Done） |
| 全量预估 | 7318 mutants / ETA ~280h → **不可行**，需分批或 ignoreStatic |

### 1.2 得分表（全量行摘录）

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

## 二、后端 mutmut 基线

### 2.1 环境与口径

| 项 | 值 |
|:---|:---|
| 工具 | mutmut 2.5.1（WSL Ubuntu 24.04 / Python 3.12.3，venv `/tmp/mutmut-venv`，pip 源阿里云 mirrors.aliyun.com） |
| 执行环境 | **Linux 原生 FS** 暂存副本 `/tmp/am-backend-mutmut`（源 `/mnt/d/.../asset_management_backend` rsync + CRLF→LF）；在 `/mnt/d`（9p/DrvFs）上跑会因 `.bak` 文件可见性崩溃 |
| 变异范围 | `--paths-to-mutate apps/assetmanagement/services`（12 个 Service 文件，与 ci.yml:214 同口径） |
| 测试发现 | `--tests-dir apps/assetmanagement/tests`（项目无顶层 `tests/`，默认 `tests/:test/` 会 FileNotFoundError） |
| Runner | `/tmp/mutmut-venv/bin/python -m pytest -x --assert=plain --ds=config.settings.test`（绝对路径；sqlite `:memory:`；pytest.ini 默认 development/PG 本地不可达） |
| 基线 suite | 1373 passed / ~19.6s（原生 FS；`/mnt/d` 同套约 80s） |
| 耗时 | 16:22:21 → 20:37:07 ≈ **4h15m**（约 11s/mutant） |
| Mutants | **1385**（无 timeout/skip/untested；全部 ok_killed 或 bad_survived） |
| 结果缓存 | 暂存区 `.mutmut-cache`（跑后已删，勿入库）；本表为唯一归档数字 |

### 2.2 得分表（按文件）

```text
file                                              tot  kill  surv   rate%
asset_lifecycle_mixin.py                          149    90    59   60.40
asset_service.py                                  174   107    67   61.49
asset_type_service.py                              71    51    20   71.83
contract_service.py                               145    90    55   62.07
damaged_asset_service.py                           99    73    26   73.74
hard_disk_sn_service.py                           133    95    38   71.43
operation_log_service.py                           90    54    36   60.00
out_asset_service.py                              192   143    49   74.48
recycle_asset_service.py                          166   100    66   60.24
repair_asset_service.py                            81    43    38   53.09
storage_service.py                                 36    22    14   61.11
waste_asset_service.py                             49    41     8   83.67
ALL                                              1385   909   476   65.63
```

- **总体 mutation score = 65.63%**（killed 909 / survived 476 / timeout 0 / untested 0）
- 低于 T7 / ci.yml 门禁 **≥80%** → 未达关闭条件，作基线存档
- 唯一 ≥80 文件：`waste_asset_service.py` 83.67；最低：`repair_asset_service.py` 53.09
- Survived 行号清单：见 `.tmp/mutmut-results.txt`（同内容 `mutmut results` 输出，会话临时件）

### 2.3 执行备注（口径偏差与坑）

1. **必须在原生 FS 跑**：mutmut `run_mutation` 的 `finally: move(file.bak, file)` 在 `/mnt/d` 下会因 9p 缓存丢 `.bak` 抛 FileNotFoundError；原生 FS 全程无残留 `.bak`。
2. **Runner 必须绝对路径**：`shlex.split` 后无 shell，裸 `python` 依赖 PATH 且曾出现 `pytest: command not found` 类环境丢失。
3. **并发测试与 `-x`**：全量含 `test_concurrent.py`（SQLite 多线程）；原生 FS 单跑与 mutmut 基线均绿，`/mnt/d` 上曾 flake（database table is locked）。
4. **与 CI 口径**：CI 同样 `--paths-to-mutate apps/assetmanagement/services`，但 runner 为默认 `python -m pytest -x --assert=plain` 且使用 PostgreSQL service；本地为 sqlite+`--ds`，kill 率可能与 CI 有小幅偏差（属预期，基线以本表为准）。
5. **hash_of_tests**：`--tests-dir` 只影响 discovery/hash，实际每次 mutant 跑的是 runner 命令的全量 collect（1373），与 CI 默认全量一致。

## 三、结论与后续

1. F-P2-4 维持 **🟡 部分完成 2026-09-24**：前端 60.00、后端 65.63 双基线均已跑通归档；均 <80，不满足「得分≥80 归档」终态。
2. 后端差距主因（按 survived 数）：`asset_service` 67、`recycle_asset_service` 66、`asset_lifecycle_mixin` 59、`contract_service` 55；`repair_asset_service` 率最低（53.09）。
3. 后续动作（不在本轮）：
   - 后端：针对 survived 行号补 Service 层失败/边界/回滚用例，复跑 `mutmut run` 逼近 80；
   - 前端：四 CRUD store 补失败/边界 + ignoreStatic 分批，stryker 逼近 break 80；
   - 补测后重跑本归档命令，更新本文件得分表。

### 复跑命令（后端，WSL）

```bash
# 一次性：rsync 到原生 FS（见 .tmp/stage-native.sh 思路）
# 然后：
export PATH="/tmp/mutmut-venv/bin:$PATH"
cd /tmp/am-backend-mutmut
rm -f .mutmut-cache
mutmut run \
  --paths-to-mutate apps/assetmanagement/services \
  --tests-dir apps/assetmanagement/tests \
  --runner "/tmp/mutmut-venv/bin/python -m pytest -x --assert=plain --ds=config.settings.test" \
  --no-progress --simple-output --CI
mutmut results
```

*归档人：opencode（mimo-v2.6-flash-free）｜关联：F-P2-4 / BF-042 / T7(T8)｜后端基线完成 2026-09-24*
