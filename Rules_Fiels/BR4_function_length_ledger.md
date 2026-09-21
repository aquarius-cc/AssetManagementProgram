# BR-4 函数长度台账（Function Length Ledger）

> **唯一事实来源**：`scripts/check_function_length_guard.py` 以 AST 语义节点扫描 `asset_management_backend/apps`（不含 migrations/tests）后的超长函数登记表。
> **计数口径**：BR-4 逻辑行 = 函数物理跨度行数（`end_lineno - lineno + 1`）− 空行 − `#` 注释行；docstring 计入代码行。
> **守则**：① 新增 >50 行函数未登记 → CI 红；② 台账条目已拆分（≤50 行）未移除 → CI 红。台账须与 AST 一一对应。
> **规模说明**：BR-4 语义口径下生产超长函数 **19 处**（物理行口径参考为 38 处，二者差异源于空行/注释行占比）。
> 批次规划：B1 = Top5 高风险（状态机关键路径优先）/ B2 = usermanagement + unregisteredasset / B3 = selectors + services 尾部。

| 批次 | 文件（apps/ 相对路径） | 行号 | 函数 | 逻辑行数 | 状态 |
|:---|:---|:---|:---|:---|:---|
| B1 | assetmanagement/services/recycle_asset_service.py | 41 | create_recycle_asset | 103 | 待拆分 |
| B1 | assetmanagement/services/out_asset_service.py | 41 | create_outasset | 85 | 待拆分 |
| B1 | assetmanagement/services/out_asset_service.py | 199 | batch_delete_outasset | 76 | 待拆分 |
| B1 | assetmanagement/services/out_asset_service.py | 204 | _delete_one | 71 | 待拆分 |
| B1 | assetmanagement/services/damaged_asset_service.py | 136 | approve_asset_recordcode | 56 | 待拆分 |
| B1 | usermanagement/services/department_service.py | 117 | move_department | 55 | 待拆分 |
| B2 | unregisteredasset/services.py | 317 | approve_and_handle | 88 | 待拆分 |
| B2 | unregisteredasset/views.py | 272 | batch_delete | 79 | 待拆分 |
| B2 | usermanagement/services/employee_service.py | 158 | replace_auth_user | 56 | 待拆分 |
| B2 | usermanagement/services/employee_service.py | 40 | bind_auth_user | 54 | 待拆分 |
| B2 | usermanagement/services/role_service.py | 46 | assign_role | 53 | 待拆分 |
| B2 | unregisteredasset/services.py | 121 | create | 54 | 待拆分 |
| B2 | unregisteredasset/services.py | 245 | update | 51 | 待拆分 |
| B2 | unregisteredasset/handlers.py | 63 | _handle_s1_create_and_recycle | 55 | 待拆分 |
| B2 | unregisteredasset/handlers.py | 257 | _handle_s3_correct_and_recycle | 51 | 待拆分 |
| B3 | assetmanagement/services/operation_log_service.py | 59 | log_operation | 65 | 待拆分 |
| B3 | assetmanagement/services/asset_type_service.py | 38 | create_asset_type | 59 | 待拆分 |
| B3 | assetmanagement/selectors/asset_selector.py | 307 | combine_search | 55 | 待拆分 |
| B3 | assetmanagement/services/asset_lifecycle_mixin.py | 89 | mark_asset_lost | 52 | 待拆分 |