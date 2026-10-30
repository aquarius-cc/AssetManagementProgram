# M-07 写操作权限门禁只读核查清单（2026-10-30）

> 性质：**只读核查**，本批不改任何权限语义。产出「端点域 → 当前生效写门禁 → 是否有角色门槛 → 结论」。
> 方法：逐 ViewSet 实读 `get_permissions()` / `resolve_viewset_permissions()` / `permission_classes` 覆盖关系，非静态扫描臆断。
> 结论汇总：**零真实缺口**。三处原工单目标均为静态扫描误报（死配置），已在代码处注释去伪；其余 ViewSet 写门禁全部有角色门槛（fail-closed）。
> 关联：`docs/Review/merge-audit-20261029.md` 批次2 M-07 行；`core/permissions.py`（resolve_viewset_permissions / M-09 / M-49 fail-closed）。

## 一、逐域核查表

| # | 端点域（ViewSet） | 写方法门禁（当前生效） | 角色门槛 | 结论 |
|:--|:---|:---|:---|:---|
| 1 | asset_view（资产） | `resolve_viewset_permissions(admin_actions, IsAssetAdminOrAbove)`，`change_status` override → IsSystemAdmin | ✅ asset_admin+ / change_status system_admin | 有门槛；无缺口 |
| 2 | storage_view（仓库） | `AdminWritePermissionMixin.get_permissions` → admin_actions(create/update/partial_update/destroy/change_status/batch_create/batch_delete) → IsSystemAdmin | ✅ system_admin | 有门槛；`permission_classes=[IsAuthenticated]` 为**死配置**（已注释去伪）；test_storage_view_rbac.py 有 403 回归 |
| 3 | asset_type_view（资产分类） | admin_actions → IsSystemAdmin | ✅ system_admin | 有门槛 |
| 4 | contract_view（合同） | admin_actions → IsSystemAdmin（read overrides 放行读） | ✅ system_admin | 有门槛 |
| 5 | hard_disk_sn_view（硬盘序列号） | admin_actions → IsAssetAdminOrAbove；`search_by_serial_number` 显式 override → IsAuthenticated（M-09 fail-closed 豁免，行级隔离兜底） | ✅ asset_admin+ | 有门槛；前端 M-20 已对齐 asset_admin |
| 6 | out_asset_view（发放） | admin_actions → IsAssetAdminOrAbove；cancel action 显式 IsAssetAdminOrAbove | ✅ asset_admin+ | 有门槛 |
| 7 | recycle_asset_view（回收） | 同上（含 cancel/reissue 显式） | ✅ asset_admin+ | 有门槛 |
| 8 | repair_asset_view（维修） | admin_actions(create/update/partial_update/destroy/batch_delete) → IsAssetAdminOrAbove | ✅ asset_admin+ | 有门槛 |
| 9 | waste_asset_view（遗失） | 同 repair | ✅ asset_admin+ | 有门槛 |
| 10 | damaged_asset_view（待报废） | admin_actions(create/update/partial_update/destroy/approve/reject/batch_delete) → IsDeptManagerOrAbove | ✅ dept_manager+ | 有门槛 |
| 11 | 生命周期族（_lifecycle_base / asset_lifecycle_view） | admin_actions → IsAssetAdminOrAbove | ✅ asset_admin+ | 有门槛 |
| 12 | asset_grouped_view / asset_group_children_view | `resolve_viewset_permissions([], IsAssetAdminOrAbove)`（空集全 fail-closed） | ✅ asset_admin+ | 有门槛 |
| 13 | unregisteredasset（未登记资产） | `_ACTION_PERMISSION_OVERRIDES`（4.5 矩阵）；admin_actions 空集时写方法仍 fail-closed 兜底 | ✅ 4.5 矩阵 | 有门槛；`permission_classes=[IsAuthenticated]` 为死配置（注释已强化去伪） |
| 14 | dashboard_view（仪表盘） | 7 个 action 全 `methods=["get"]`，**无写操作** | —（读） | IsAuthenticated 即真实门禁；无越权面（已注释锚定） |
| 15 | employee_view（员工） | get_permissions 分 action：export → CanExportExcel；批量/删除类 → IsSystemAdmin；默认 IsAuthenticated（读） | ✅ 分 action | 有门槛 |
| 16 | department_view（部门） | 分 action：管理类 IsSystemAdmin；读 IsAuthenticated | ✅ 分 action | 有门槛 |
| 17 | role_view（角色） | 类级 `permission_classes=[IsSystemAdmin]` | ✅ system_admin | 有门槛 |
| 18 | permission_view / my_permissions | IsAuthenticated，只读自权查询 | —（读） | 无写操作 |
| 19 | authusermanagement（认证账号） | get_permissions 分 action：写类 IsSystemAdmin、读 IsAuthenticated；注册端点 AllowAny 受 `AUTH_SELF_REGISTRATION_ENABLED` 设置位 + IsSystemAdmin 校验双闸 | ✅ 分 action | 有门槛 |
| 20 | operation_log_views（操作日志，7 个 APIView） | 全部只读（IsAuthenticated / export 加 CanExportExcel），无写方法 | —（读） | 无写操作 |

## 二、三处死配置去伪（本批唯一改动，纯注释）

| 位置 | 误报内容 | 去伪方式 |
|:---|:---|:---|
| `storage_view.py:61` | 「写操作仅 IsAuthenticated」 | 实际被 AdminWritePermissionMixin.get_permissions 覆盖（IsSystemAdmin）；补 [M-07 去伪] 注释指明真实门禁与回归文件 |
| `unregisteredasset/views.py:125` | 同上 | 实际走 4.5 矩阵 + fail-closed 兜底；原注释已去伪，本批补全措辞（指明 override/fail-closed 出处） |
| `dashboard_view.py:50` | 「写操作仅 IsAuthenticated」 | 7 个 action 全 GET，无写操作；补注释锚定 |

## 三、遗留与立项建议

- **零真实缺口**：全部写方法均有角色门槛（fail-closed 语义由 `core/permissions.py` M-09/M-49 保证）。
- **改进项（非缺口，可另行立项）**：`permission_classes = [IsAuthenticated]` 类级死配置在多个 ViewSet 与真实门禁并存，属「双源易误导」形态（本次三处已注释去伪；其余 ViewSet 的类级默认值与 get_permissions 并存模式一致，风险同源，可在后续批次统一审计注释）。
- 若未来新增 ViewSet：必须走 `resolve_viewset_permissions` 或分 action `permission_classes`，禁止裸依赖类级默认值承担写门禁——建议作为新增代码评审项。

*核查人：atomcode ｜ 2026-10-30 ｜ 依据：批次2 M-07 工单 + 实读取证*
