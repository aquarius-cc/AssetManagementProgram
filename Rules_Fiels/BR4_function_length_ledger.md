# BR-4 函数长度台账（Function Length Ledger）

> **唯一事实来源**：`scripts/check_function_length_guard.py` 以 AST 语义节点扫描 `asset_management_backend/apps`（不含 migrations/tests）后的超长函数登记表。
> **计数口径**：BR-4 逻辑行 = 函数物理跨度行数（`end_lineno - lineno + 1`）− 空行 − `#` 注释行；docstring 计入代码行。
> **守则**：① 新增 >50 行函数未登记 → CI 红；② 台账条目已拆分（≤50 行）未移除 → CI 红。台账须与 AST 一一对应。
> **规模说明**：BR-4 语义口径下生产超长函数 **0 处**（物理行口径参考为 38 处，二者差异源于空行/注释行占比）。
> 批次规划：B1 = Top5 高风险（状态机关键路径优先）/ B2 = usermanagement + unregisteredasset / B3 = selectors + services 尾部。
> **新增 3 列语义**（2026-09-21 升格）：`拆分目标（helper）` = 拟抽取/提升的私有方法设计；`回归测试锚` = 该函数拆分前后的既有测试文件；`风险标注` = 拆分时须人工核对的行为要点。
> **嵌套计数口径**：外层函数逻辑行含嵌套函数 body。实测 `batch_delete_outasset` 总逻辑行 76 = 外层 5 + 嵌套 `_delete_one` 71，故该行拆分目标为 **hoist（提升）** 而非线性抽取。
> **hoist 约定**：`_delete_one` 提升至类级 staticmethod 后行号迁移，台账须同提交更新行号/关闭条目，guard「已拆分未移除即红」兜底。
> **B1 已完成**（2026-09-21）：六处全部拆分并移除台账（recycle/out/damaged/department），`pytest apps/assetmanagement -q` 724 passed + `apps/usermanagement -q` 99 passed；`_finalize_broken_or_lost` 合并 broken/lost 双分支（DR-1）。
> **B2 已完成**（2026-09-21）：9 处全部拆分并移除台账（usermanagement assign_role/bind/replace/unbind + unregisteredasset handlers S1/S2/S3 + services create/update/approve + views batch_delete），guard 4/4；unregisteredasset 194 passed + usermanagement 99 passed + assetmanagement 726 passed；mypy 26 存量零新增。
> **B2/B3 拆分设计**（2026-09-21 完成）已固化于各行；helper 名以 guard 实测调整。docstring 计入计数，部分函数设计含「docstring 压缩」（行为无关纯文本，语义保留）。
> **B3 已完成**（2026-09-21）：三处全部拆分并移除台账（asset_type_service create_asset_type / asset_selector combine_search / asset_lifecycle_mixin mark_asset_lost），guard 0/0，BR-4 存量清零；asset_type_service 23 passed、asset_selector 60 passed、asset_lifecycle+state_machine 78 passed；mypy 目标文件零新增（mixin 闭包注解修正 :316/:340 → BrokenAsset/LostAsset，Assistant 新增 no-any-return 以 cast 消除）；双胞胎统一入库 complete-patterns.md B-23 转「已关闭」。
> **测试锚缺口**：`views.batch_delete`、`bind_auth_user`/`replace_auth_user`、`_handle_s1/s3` 无直接行为测试（仅经批量契约快照/审批流间接覆盖，或仅 coverage 一致性测试）→ 拆分前须按 CT-4 补回归用例。
> **测试锚已补齐**（2026-09-21）：新增 `unregisteredasset/tests/test_batch_delete_view.py`（成功/四种失败结构/权限 7 条）、`unregisteredasset/tests/test_handlers.py`（S1/S3 直接 CT-3 锚 + 关联持久化 3 条）、`usermanagement/tests/test_service_coverage.py` 增审计日志锚（bind/unbind/replace 3 条）；P0 定向 35 passed，全量回归 usermanagement+unregisteredasset 188 / assetmanagement 726，ruff/mypy(C90 仅存量) 零新增，guard PASS。B2 拆分可开工，各行回归测试锚见下。

| 批次 | 文件（apps/ 相对路径） | 行号 | 函数 | 逻辑行数 | 拆分目标（helper） | 回归测试锚 | 风险标注 | 状态 |
|:---|:---|:---|:---|:---|:---|:---|:---|:---|