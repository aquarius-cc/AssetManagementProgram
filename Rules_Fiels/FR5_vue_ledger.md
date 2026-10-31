# FR-5 .vue 行数台账（豁免登记表）

> 护栏：`scripts/check_frontend_invariants.py` FR-5 子规则（M-34 落地，2026-10-31）。
> 红线：template 有效行 + script 逻辑行 > 500 的 `.vue`（排除 `__tests__`）必须在此登记；
> 登记条目当前行数必须仍 > 500（已拆分未移除即红，防台账腐烂）；登记行数 ≤ 500 非法即红。
> 基线：2026-10-31 `--print` 实测 121 文件，最大 `components/componentsdetails/detils/UnregisteredAssetForm.vue` 411 行，**存量零超限**，台账初始为空。
> 口径：与 FR-6 同型（物理行 − 空行 − 注释行；template 段另计非空非纯 `<!-- -->` 行）。

| 文件 | 登记逻辑行数 | 断言日期 | 拆分计划 |
|:---|:---|:---|:---|
