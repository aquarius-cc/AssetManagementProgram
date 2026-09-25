# B-M1/B-M2 变异测试归档（AtomCode, 2026-09-25）

> 工具：mutmut 2.5.1（WSL /tmp 独立副本，SQLite 内存库，runner: pytest -x -q --assert=plain）
> 归档原则：所有数字为命令实报（Fact-1）。**2026-09-25 订正**：本文档初版误将 mutmut 进度条读作「1367 杀灭 / 14 幸存」，经 `.mutmut-cache` 缓存库直查证伪，权威值见同目录 `M1-B2-AUTHORITATIVE-20260925.txt`。初版「本文件取代 results-20260925-1325.txt 的不完整 survivors 抓取」之表述方向颠倒——`results-*.txt` 与 `survivors-*.txt` 的抓取是准确的（Survived 4），失真的是本文档自身数字。

## B-M1 全量基线（assetmanagement/services 全目录，补测前口径）

- 结果（**2026-09-25 订正**）：1385 变异体 → **1365 杀灭 / 4 幸存 / 1 超时 / 3 可疑 / 12 未测**（缓存库直查；初版记「1367 杀灭 / 14 幸存」系误读进度条，已证伪）
- 得分：99.42%（= 1365 / 1373，tested = 1385 − 12 未测）。12 个受测文件中 **9 个 100%**
- M1 副本测试目录快照：48 个测试文件，**不含** B-M2 新增 4 个 *_gaps.py（先同步后补测，属基线口径）
- 口径警示（**2026-09-25 订正**）：与台账历史基线 65.63% 的差异源于 runner/scope/快照状态不同，**两数不可直接对比**。但本轮 M1 亦**不可直接作为回归基线**——其 48 文件快照不含 B-M2 新增的 4 个 gaps 文件，快照已过时；且 M1 为全量套件口径，B-M2 为 per-file 口径，两者数字不可比（详见 `M1-B2-AUTHORITATIVE-20260925.txt` 第三节「口径差异」）。
- 未杀灭变异体明细（20 个，含文件/行号/ID）已完整归档于 `M1-B2-AUTHORITATIVE-20260925.txt`：
  - 幸存 4（全部在 damaged_asset_service.py）：id=1→L29、id=2→L30、id=6→L39、id=1386→L45
  - 超时 1：asset_service.py id=632→L83
  - 可疑 3：out_asset_service.py id=309→L179、id=312→L180、id=319→L186
  - 未测 12：damaged_asset_service.py id=25/26/43/44/60/66/67/77/86/87/95/99

## B-M2 per-file 迭代（补测后干净复跑终局）

> **口径警告（2026-09-25 补注）**：本节全部数字为 **per-file 范围**（仅跑该文件自身测试），与上节 M1 的**全量套件范围**（48 个测试文件）不可直接比较。同一 4 个文件在 M1 全量套件下为 100% / 99.43% / 100% / 100%。故本节「首轮约 50%」反映的是**测试范围收窄的必然结果，而非全量套件下的真实质量缺口**；B-M2 新增 127 用例的实际收益应表述为「提升单文件测试独立性」。

| 文件 | 首轮（per-file） | 终局复跑（per-file） | 幸存者分类 | 新增测试 |
|---|---|---|---|---|
| repair_asset_service.py | 42/79 (53.2%) | **71/79 (89.87% ≥80)** | 8 = 6×@staticmethod 等价 + 2×operator_name（终跑后已补杀断言，30 用例绿，未复跑） | test_repair_service_gaps.py 30 用例 |
| asset_service.py | 90/174 (51.7%) | **145/174 (83.33% ≥80)** | 28（= 总数 174 − 杀灭 145 − 超时 1；**初版复核提出的「应为 29」质疑不成立**）+ 13×等价/低值（@staticmethod×10、RANDOM_* 死常量×3）+ 15×低危留档 | test_asset_service_gaps.py 35 用例 |
| recycle_asset_service.py | 82/166 (50.6%) | **139/166 (83.73% ≥80)** | 27 = 等价/登记类（@staticmethod、docstring、死参数） | test_recycle_service_gaps.py 29 用例 |
| asset_lifecycle_mixin.py | 75/149 (50.3%) | **130/149 (87.25% ≥80)** | 19 = 11×@staticmethod + 4×[HALT] 注释 + 2×use_transaction 近等价 + 2×留档 | test_lifecycle_mixin_gaps.py 33 用例 |

- 终局合计：485 杀灭 / 82 幸存 / 1 超时 / 568 总数 = **85.39%**（算术校验 145+28+1=174、139+27=166、71+8=79、130+19=149，全部自洽）
- runner：`pytest -x -q --assert=plain`；mutmut 2.5.1；环境：WSL /tmp 独立副本 + SQLite 内存库
- 门禁：4 个 gap 文件 127 用例在真实 Windows venv 全绿；ruff 清零（I001/F401/F841 已修）
- 用例数校验：30 + 35 + 29 + 33 = 127。其中 test_asset_service_gaps.py 为 29 个 `def test_` 函数 + 1 个 `@pytest.mark.parametrize`（7 个不可变字段值）= 35 用例，故按函数计数会得 121，非错误。
- 等价变异豁免依据：@staticmethod 删除（Py3 类调用无 self 绑定差异）、[HALT] 注释删除（无运行时行为）、RANDOM_CHARS/RANDOM_LENGTH（被硬编码 uuid.hex[:8] 绕过的死常量）——均已登记，不计入达标口径。**注：此为类别级豁免依据，逐变异体 ID 未单独登记**；如需逐条豁免台账，以 `M1-B2-AUTHORITATIVE-20260925.txt` 的 ID 清单为准。
