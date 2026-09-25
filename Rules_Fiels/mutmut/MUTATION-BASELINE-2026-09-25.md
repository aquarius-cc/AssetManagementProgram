# B-M1/B-M2 变异测试归档（AtomCode, 2026-09-25）

> 工具：mutmut 2.5.1（WSL /tmp 独立副本，SQLite 内存库，runner: pytest -x -q --assert=plain）
> 归档原则：所有数字为命令实报（Fact-1）；本文件取代同目录 results-20260925-1325.txt 的不完整 survivors 抓取

## B-M1 全量基线（assetmanagement/services 全目录，补测前口径）

- 结果：1385 变异体 → **1367 杀灭 / 14 幸存 / 1 超时 / 3 可疑 / 12 未测**（日志计数）
- M1 副本测试目录快照：48 个测试文件，**不含** B-M2 新增 4 个 *_gaps.py（先同步后补测，属基线口径）
- 口径警示：M1 得分（≈98.7% 按 killed/total）与台账历史基线 65.63% 差异显著——历史基线的 runner/scope/快照状态与本轮不同，**两数不可直接对比**，后续变异回归以本轮 M1 为新基线
- 幸存者明细：damaged_asset_service.py（results 分组列出 1-2, 6, 1386 行区 + 12 个未测）；asset_service.py 超时 1 个（#632）；out_asset_service.py 可疑 3 个（309/312/319）

## B-M2 per-file 迭代（补测后干净复跑终局）

| 文件 | 首轮 | 终局复跑 | 幸存者分类 | 新增测试 |
|---|---|---|---|---|
| repair_asset_service.py | 42/79 (53.2%) | **71/79 (89.87% ≥80)** | 8 = 6×@staticmethod 等价 + 2×operator_name（终跑后已补杀断言，30 用例绿，未复跑） | test_repair_service_gaps.py 30 用例 |
| asset_service.py | 90/174 (51.7%) | **145/174 (83.3% ≥80)** | 28 = 13×等价/低值（@staticmethod×10、RANDOM_* 死常量×3）+ 15×低危留档 | test_asset_service_gaps.py 35 用例 |
| recycle_asset_service.py | 82/166 (50.6%) | **139/166 (83.7% ≥80)** | 27 = 等价/登记类（@staticmethod、docstring、死参数） | test_recycle_service_gaps.py 29 用例 |
| asset_lifecycle_mixin.py | 75/149 (50.3%) | **130/149 (87.2% ≥80)** | 19 = 11×@staticmethod + 4×[HALT] 注释 + 2×use_transaction 近等价 + 2×留档 | test_lifecycle_mixin_gaps.py 33 用例 |

- 门禁：4 个 gap 文件 127 用例在真实 Windows venv 全绿；ruff 清零（I001/F401/F841 已修）
- 等价变异豁免依据：@staticmethod 删除（Py3 类调用无 self 绑定差异）、[HALT] 注释删除（无运行时行为）、RANDOM_CHARS/RANDOM_LENGTH（被硬编码 uuid.hex[:8] 绕过的死常量）——均已登记，不计入达标口径
