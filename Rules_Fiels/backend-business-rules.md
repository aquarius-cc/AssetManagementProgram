
---

### 📄 文档 4：后端业务规范 `/Rules_Fiels/backend-business-rules.md` (v1.17)

# 后端业务规范与设计思路 (Backend Business Rules)
> 版本：v1.18 | 最后更新：2026-09-29
> 适用范围：Django 6.0 + DRF 3.16 + PostgreSQL 16

## 一、设计思路（防腐与一致性）

| 原则 | 说明 |
|:---|:---|
| **防腐层隔离** | Service 层作为业务核心，隔离 Model 变更对 API 的影响，确保前端无感知数据库结构调整。 |
| **事务边界清晰** | 所有涉及多表写操作或状态流转的方法，强制使用 `@transaction.atomic`，防止数据不一致。 |
| **审计驱动** | 资产状态变更必须记录日志（ActionLog），满足企业合规追溯要求，不可跳过。 |
| **状态机约束** | 资产流转路径预定义（见第三节），非法跃迁必须在代码层面抛出 `ValidationError`。 |

> **测试联动**：本章节所有 B1-B10 规范均有对应的测试用例要求，详见 `backend-testing-rules.md` T1-T8。

## 二、硬性业务规范（B1-B10）

| ID | 规范项 | 约束内容 | 违规补救 |
|:---|:---|:---|:---|
| B1 | **API 响应格式** | 统一为 `{"code": 0, "data": {}, "message": "success"}`，**禁止**直接返回 Model 实例 | 使用统一响应包装器 |
| B2 | **URL 命名** | 资源名使用**复数 snake_case**（如 `/api/assets/`），**禁止**单数或驼峰 | 重构路由 |
| B3 | **HTTP 方法语义** | GET(查询)、POST(创建)、PUT/PATCH(更新)、DELETE(软删，需二次确认) | 修正方法映射 |
| B4 | **分页与过滤** | 列表接口必须集成 `django-filter`，统一使用 `page` 与 `page_size` 参数 | 添加 FilterSet |
| B5 | **状态流转** | 状态变更**必须**调用 Service 层专门方法（如 `checkout()`），**禁止**在 View/Serializer 中直接修改状态字段 | 抽取到 Service |
| B6 | **事务原子性** | 涉及状态变更、多表写操作的方法**必须**添加 `@transaction.atomic`。通知推送**必须**使用 `send_notification_on_commit()` 确保事务提交后执行，**禁止**在事务内直接调用 `notify_dept_managers()` | 添加装饰器；通知改用 on_commit |
| B7 | **审计日志** | 所有状态变更**必须**调用 `audit_log` 记录操作人、时间、变更前后状态 | 补上审计调用 |
| B8 | **模型标准字段** | 所有模型**必须**包含 `created_at`(auto_now_add)、`updated_at`(auto_now)、`is_deleted`(软删) | 继承抽象基类 |
| B9 | **枚举约束** | 状态字段**必须**使用 `models.TextChoices`，**禁止**使用整型或字符串硬编码 | 重构为 TextChoices |
| B10 | **外键约束** | 外键**必须**显式指定 `on_delete`，多对多关系**必须**指定 `db_table` | 补充声明 |

## 三、资产状态机（业务流转路径）

```text
                          ┌─────────────────────────────────────┐
                          │                                     │
in_store ──outasset──→ in_use ──recycle──→ recycled_pending     │
    │                    │    ↑               │                  │
    │ mark_broken        │    │               │ mark_broken      │
    │ mark_lost          │    │               │ mark_lost        │
    ▼                    ▼    │               ▼                  │
 broken/lost         broken/lost          broken/lost           │
    │                    │    │               │                  │
    │ repair             │    │               │                  │
    ▼                    │    │               │                  │
repairing ──repair_done──┘    │               │                  │
    │                         │               │                  │
    │ repair_failed           │               │                  │
    └─────────────────────────┘               │                  │
              │                              │                  │
              ▼                              │                  │
           damaged ──approve──→ scrapped     │                  │
              │                              │                  │
              └──reject──→ broken/lost ──────┘──────────────────┘
                   │         (原状态为broken/lost时)
                   │
                   └──reject──→ in_use          (原状态为in_use时，字段保留)
                   │
                   └──reject──→ recycled_pending (原状态为recycled_pending时，清空申请人/保管人/使用地点)
                   │
                   └──cancel──→ 按original_status回退 (用户取消，与reject同目标，缺失/非法兜底recycled_pending)

遗失的资产找回: lost ──found_and_return──→ recycled_pending (重新进入发放池)
```
**状态转换规则**：

| 当前状态 | 允许的目标状态 | 触发操作 |
|---------|---------------|---------|
| `in_store` | `in_use` | 出库（领用/外借） |
| `in_store` | `broken` | 标记损坏 |
| `in_store` | `lost` | 标记遗失 |
| `in_use` | `recycled_pending` | 回收（正常） |
| `in_use` | `broken` | 回收（is_broken=True） |
| `in_use` | `lost` | 回收（is_lost=True） |
| `recycled_pending` | `in_use` | 再次出库 |
| `recycled_pending` | `broken` | 标记损坏 |
| `recycled_pending` | `lost` | 标记遗失 |
| `recycled_pending` | `damaged` | 申请报废（待发放状态） |
| `broken` | `repairing` | 送修（必须创建维修记录） |
| `broken` | `damaged` | 申请报废（损坏状态） |
| `repairing` | `recycled_pending` | 维修完成（更新physical_grade，重新进入发放池） |
| `repairing` | `damaged` | 维修失败，申请报废 |
| `lost` | `recycled_pending` | 找回（重新进入发放池） |
| `lost` | `damaged` | 申请报废 |
| `damaged` | `scrapped` | 审批通过 |
| `damaged` | `broken` | 审批拒绝（原状态为broken） |
| `damaged` | `lost` | 审批拒绝（原状态为lost） |
| `damaged` | `in_use` | 审批拒绝（原状态为in_use） |
| `damaged` | `recycled_pending` | 审批拒绝（原状态为recycled_pending） |
| `damaged` | `repairing` | 审批拒绝（原状态为repairing） |
| `damaged` | `broken`/`lost`/`in_use`/`recycled_pending`/`repairing` | 取消报废（按original_status回退，与reject同目标；缺失/非法兜底recycled_pending） |
| `scrapped` | *无* | 终态，不可转出 |

> **V2.8 业务决策**：`in_use` 状态不可直接申请报废（`in_use → damaged` 已移除）。在用资产须先回收至 `recycled_pending`，再从 `recycled_pending` 申请报废。正确路径：`in_use → recycled_pending → damaged`。

**特殊回退操作**：

| 操作 | 方法 | 说明 |
|------|------|------|
| 取消出库 | `cancel_outasset(previous_status)` | 根据出库前状态回退 |
| 取消回收 | `cancel_recycle()` | 恢复到在用 |
| 取消报废 | `cancel_damaged(original_status)` | **根据申请前状态回退（与 reject 一致）**，original_status 为空/非法时兜底 recycled_pending |
| 强制回收 | `force_recycle_from_any()` | 管理员特殊操作，跳过常规校验 |

**业务约束**：

1. 仅允许沿规则表中定义的方向流转，逆向或跳跃流转必须抛出 `InvalidTransitionError`。
2. 涉及 `damaged` 状态的变更，必须附加审批记录。
3. 进入 `repairing` 状态必须同时创建 `RepairAsset` 维修记录。
4. 维修完成时必须更新资产的 `physical_grade` 字段。
5. 审批拒绝报废时，资产必须回退到申请前的状态（由 `original_status` 字段决定），而非一律回到 `recycled_pending`。即使原员工已离职或调岗，也应先回退到 `in_use`，然后再通过正常回收流程处理。
6. 用户取消报废申请时，资产同样必须回退到申请前的状态（由 `original_status` 字段决定），与审批拒绝行为保持一致。`original_status` 缺失或非法时兜底回退 `recycled_pending`。
7. 资产创建时初始状态**必须**为 `in_store`，且**必须**由 `AssetService.create_asset` 统一注入（引用 `Asset.AssetStatus.IN_STORE` 枚举，非字符串）。创建类 Serializer（如 `AssetCreateSerializer`）**禁止**暴露 `asset_current_status` 写字段(P0-1 回归约束，防止客户端绕过 FSM 直接创建终态资产)。

## 四、RBAC 权限与行级数据隔离（B11-B14）

> 本节对应 P1-4 / P2-11 修复，基于 `01-需求规格说明书.md` §2.2 RBAC 权限矩阵。

### 4.1 角色定义（Employee.role 枚举）

| 角色 | 枚举值 | 说明 |
|:---|:---|:---|
| 系统管理员 | `system_admin` | 拥有全部权限，`is_superuser` 绕过所有检查 |
| 部门经理 | `dept_manager` | 本部门+下级部门的资产操作+审批权限 |
| 资产管理员 | `asset_admin` | 本部门的资产操作权限（无审批权） |
| 普通用户 | `regular_user` | 本部门资产只读 |
| 审计员 | `auditor` | 全部数据只读（审计日志+资产历史） |

### 4.2 功能权限矩阵

| 模块 | 操作 | system_admin | dept_manager | asset_admin | regular_user | auditor |
|:---|:---|:---:|:---:|:---:|:---:|:---:|
| 资产管理 | 列表/详情 | ✅ 全部 | ✅ 本部门+下级 | ✅ 本部门 | ✅ 本部门 | ✅ 全部 |
| 资产管理 | 新增/编辑/删除 | ✅ | ✅ 本部门+下级 | ✅ 本部门 | ❌ | ❌ |
| 资产管理 | 批量删除 | ✅ 逐条校验 | ✅ 本部门+下级 逐条 | ✅ 本部门 逐条 | ❌ | ❌ |
| 出库/回收 | 操作 | ✅ | ✅ 本部门+下级 | ✅ 本部门 | ❌ | ❌ |
| 损坏/遗失 | 登记/找回/送修 | ✅ | ✅ 本部门+下级 | ✅ 本部门 | ❌ | ❌ |
| 报废审批 | 申请（单条 create）/审批通过/拒绝/批量删除 | ✅ | ✅ 本部门+下级 | ❌ | ❌ | ❌ |
| 未登记资产 | 处理审批 | ✅ | ✅ 本部门+下级 | ❌ | ❌ | ❌ |
| 系统配置 | 类型/仓库/合同/员工/部门/用户 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 审计日志 | 查看 | ✅ | ❌ | ❌ | ❌ | ✅ |
| 操作日志 | 查看 | ✅ | ✅ 本部门 | ✅ 本部门 | ✅ 本部门 | ✅ 全部 |
| 仪表盘 | 查看 | ✅ | ✅ 本部门+下级 | ✅ 本部门 | ✅ 本部门 | ✅ 全部 |
| 导出 | Excel | ✅ | ✅ 本部门+下级 | ✅ 本部门 | ❌ | ✅ 全部 |
| 扫码查看 | 公开查询 | ✅ | ✅ | ✅ | ✅ | ✅ |

> **公开扫码约束（R4-04）**：匿名扫码响应受 §4.6 最小暴露白名单约束（仅 6 字段），敏感字段一律不返回；✅ 表示"仅白名单内信息可见"，非全量可见。

### 4.3 行级数据隔离

| 角色 | 数据范围 | Selector 过滤方式 |
|:---|:---|:---|
| system_admin | 全部 | 无过滤 |
| auditor | 全部 | 无过滤 |
| dept_manager | 本部门+所有下级部门 | `department_code__in = dept_codes`（含子孙） |
| asset_admin | 本部门 | `department_code = user_dept_code` |
| regular_user | 本部门 | `department_code = user_dept_code` |

### 4.4 资产部门归属（动态解析，无冗余字段）

资产归属部门通过运行时动态解析，不存储冗余字段。回退链：

1. `asset_manager_recordcode.employee_department` — 保管人/使用人部门
2. `asset_entry_person_recordcode.employee_department` — 入库人部门
3. `asset_storage_recordcode.storage_manager.employee_department` — 仓库管理员部门
4. `None` — 仅 system_admin 和 auditor 可见

| ID | 规范项 | 约束内容 | 违规补救 |
|:---|:---|:---|:---|
| B11 | **RBAC 权限检查** | 所有写操作（create/update/destroy）**必须**通过权限类校验角色，**禁止**仅用 `IsAdminUser` 作为唯一写权限控制 | 补充角色权限类 |
| B12 | **行级数据隔离** | Selector 层**必须**实现 `get_queryset_for_user(user)` 方法，根据用户角色和部门范围过滤查询结果 | 补充 Selector 方法 |
| B13 | **部门归属动态解析** | 资产的部门归属**禁止**使用冗余字段存储，**必须**通过 `resolve_asset_department_codes()` 动态解析 | 删除冗余字段，改用动态解析 |
| B14 | **批量操作逐条校验** | 批量删除/批量更新**必须**逐条校验权限，无权限的条目跳过并返回错误，**禁止**整体校验 | 改为逐条校验 |

### 4.5 未登记资产细则（增补，4.2 矩阵原文不改）

> 本节为未登记资产（UnregisteredAsset）权限语义的细则澄清，**不修改** 4.2 功能权限矩阵原文。落地背景：P1-1 修复（Selector 接线与行级隔离），对应需求 AC-49/AC-50。

**【列解读】** 4.2 矩阵"未登记资产处理"列 = 审批动作；`asset_admin` 的 ❌ 指无审批权，不排除提交与维护。

**【角色×动作】**

| 动作 | system_admin | dept_manager | asset_admin | regular_user | auditor |
|:---|:---:|:---:|:---:|:---:|:---:|
| 提交发现（create/batch_create） | ✅ 可代录 | ❌ | ✅（本人） | ❌ | ❌ |
| 查看（list/retrieve） | ✅ 全量 | ✅ 本部门+下级 | ✅ 本部门+本人提交 | ❌ | ❌ |
| 编辑/删除（仅待审批） | ✅ 全量 | ❌ 只读 | ✅ 本部门+本人提交 | ❌ | ❌ |
| 审批（approve） | ✅ | ✅ 本部门+下级 | ❌ | ❌ | ❌ |
| 批量删除（batch_delete） | ✅ 全量（B14 逐条） | ❌ | ✅ 本部门（B14 逐条） | ❌ | ❌ |

**【行级隔离】**

1. **角色白名单优先**：仅 `system_admin`（含 is_superuser）的 `dept_codes=None` 解释为全量；`dept_manager`/`asset_admin` 的 `None`/空列表一律收敛为空集（防 data_scope 配置错误绕过）。
2. **部门过滤**：`discovery_person.employee_department.department_code ∈ dept_codes`。
3. **本人提交例外**：`discovery_person = 当前用户` 的记录恒可见（兜底无部门员工与边界场景）。
4. **审计员**：未登记资产接口不可见（矩阵 ❌）；其操作日志可见属审计日志矩阵授权，不视为矛盾。

**【接口语义】**

1. 提交权包含待审批草稿的自维护（编辑/删除）。
2. `discovery_person`：默认 = 当前操作人（AC-49"资产管理员发现"语义）；仅 `system_admin` 可代录（传其他有效工号）。
3. `approve` 的 `approver` 强制 = 当前审批人（后端覆盖传入值，防代签）。
4. 越权访问一律返回 404（不泄露存在性）。
5. 审计日志 `operator` = 当前操作人，与业务字段 `discovery_person` 解耦。
6. 审批产出资产的归属（`asset_manager_recordcode`）属资产模块独立议题，不在本细则范围。

### 4.6 公开扫码细则（R4-04 最小暴露收敛）

> 本节约束匿名扫码接口 `GET /api/v1/assets/public/scan/{recordcode}/`（`public_scan_view`）。

**【响应白名单】** 仅返回 6 字段：`asset_code`、`asset_name`、`asset_specification`、`asset_brand`、`asset_current_status`、`physical_grade`。测试以 `set(data.keys()) == 白名单` 严格断言，回归新增字段即失败。

**【禁暴露清单】** 价格（`asset_purchase_price`）、仓库、分类、保管人姓名/电话、使用地点、入库日期——匿名响应中禁止出现，`mask_phone_number` 遮罩方案已废弃（遮罩仍属暴露，直接不返回）。

**【审计】** 成功查询记录 `public_scan` 操作日志（`AssetOperationLog.OperationType.PUBLIC_SCAN`），仅记客户端 IP（`get_current_ip()`），无操作人；404 不记审计（防匿名刷日志，由 anon 限流兜底）。

**【限流】** 视图级显式声明 `[AnonRateThrottle, UserRateThrottle]`：匿名 20/minute、登录用户 100/minute（均取自 `base.py` `DEFAULT_THROTTLE_RATES`）；前端已不再为登录用户调用此接口，登录限流为纵深防御。Selector 免 JOIN（无 `select_related`）。

**【登录态分流】** 已登录用户扫码由前端直接走认证详情接口获取全量信息；公开接口仅服务未登录场景。

### 4.7 员工域细则（增补，4.2 矩阵原文不改）

> 本节为员工（Employee）域权限语义的细则澄清，**不修改** 4.2 功能权限矩阵原文。落地背景：BF-048 修复——B12「Selector 层必须实现 `get_queryset_for_user(user)`」此前在员工域**从未落地**（`EmployeeViewSet` 直接用 `queryset` 属性，全量返回），导致 `dept_manager` 持 `CanExportExcel` 即可导出全公司员工档案。

**【三态数据范围】** 委托 `core.department_scope.get_department_codes_for_user(user)`，与操作日志侧（`OperationLogSelector._scope_by_user`）**完全同语义**，禁止另立规则：

| 返回值 | 适用角色 | 员工域效果 |
|:--|:--|:--|
| `None` | system_admin / auditor / is_superuser / 无 Employee 记录 | 不限部门 |
| 空列表 | 部门级角色但未挂部门（最严兜底） | 零行，且写类/导出类权限一并降级（`get_user_role` 降为 `None`） |
| 部门列表 | dept_manager | 本部门 + 全部下级部门 |
| 部门列表 | asset_admin / regular_user | 仅本部门 |

**【收窄入口唯一】** 必须覆写 `EmployeeViewSet.get_queryset()`（委托 `EmployeeSelector.get_queryset_for_user`），**禁止**以下三种写法：① 只在某个 action 里 `filter`；② 改 `self.queryset` 类属性；③ 用 `self.queryset` 绕过 `get_queryset()`。因 DRF `get_object()` 内部即 `filter_queryset(get_queryset())`，覆写 `get_queryset()` 可一次覆盖 list / retrieve / search / statistics / export 五条路径。

**【已收窄端点（8 个）】**

| 端点 | 收窄方式 |
|:--|:--|
| `GET /employees/`（list）· `/search/` · `/export/` · `/statistics/` · `GET /employees/{jobcode}/`（retrieve） | 经 `get_queryset()` 自动覆盖 |
| `GET /employees/active_employees/` | 原裸 `get_active_employees()`，显式经 `get_employee_scoped_queryset_for_user` |
| `GET /employees/by-auth-user/{auth_id}/` | 原裸 `Employee.objects.get`，改走 `get_queryset()`；且 `auth_id` 非法值返回 404（原为 500） |
| `GET /employees/employees/{jobcode}/` | 原用未收窄的 `self.queryset`，改走 `get_queryset()` |

**【聚合端点】** `statistics` 的口径 **恒等于** 当前可见行范围（此前固定全量聚合，导致已声明的 `employee_status` / `department_code` 形同虚设）。改动的只是数值范围，**响应结构不变**。

**【越权响应】** 越权访问一律 **404**（不泄露存在性），与 §4.5 接口语义第 4 条一致。

**【回归屏障】** `apps/usermanagement/tests/test_employee_rbac_scope.py` 锁定上述全部语义（14 用例）；新增员工域端点或旁路时**必须**同步扩展该文件。

**【不在本细则范围】** `get_department_by_jobcode` 返回部门而非员工档案，跨部门部门可见性未评估。

### 4.8 OpenAPI 契约声明细则（增补，不改其他节原文）

> 本节为「文档必须与运行时一致」的落地纪律，**不修改** B1-B10、§4.2 矩阵与第五节 BR 条文。落地背景：BF-049 / BF-050——两处端点文档失真在 **1595 个用例全绿**的情况下长期存在，因为既有测试只断言 HTTP 行为，**没有任何一处断言文档**。

**【机制一：响应形态决定筛选参数发现】** drf-spectacular 0.29 的 `AutoSchema.get_filter_backends()` 受 `_is_list_view()` 门控：响应非 list（聚合字典、xlsx 二进制）时**整体关闭** FilterSet / Search / Ordering 参数的自动发现。故非 list 端点若运行期确实消费筛选参数，**必须显式补回**。

| 反面 | 现象 |
|:--|:--|
| 漏声明 | 端点支持筛选但文档没有（BF-049 导出端点） |
| 连锁 | 修对 `responses`（改成分页数组 → 聚合字典）会**静默翻转**该门控，把原有筛选参数全部抹掉（BF-050 修第 ① 项时触发） |

**【机制二：手工声明只替换、不校正】** `@extend_schema(parameters=…)` / `responses=…` 与自动注入是「同名覆盖」而非「互补合并」，写错不会被 spectacular 纠正，直接进基线（BF-050 修第 ②③ 项、BF-047 回归均由是）。

**【补回方式：显式 opt-in，禁止改全局】** 使用 `core.schema.ForceFilterDiscoverySchema` + ViewSet 类属性 `force_filter_discovery_actions`（`frozenset`）。

| ID | 规范项 | 约束内容 |
| :--- | :--- | :--- |
| OS-1 | **显式 opt-in** | 禁止覆写 `_is_list_view()` 或全局 `AutoSchema`。只有**运行期确实消费筛选参数**的 action 才可列入名单；未列入的端点行为完全不变 |
| OS-2 | **名单取 action 方法名** | `view.action` 取自 DRF `action_map`，其值是**方法名**（`export_excel`）而非 `url_path`（`export`）。写错不报错、**静默不生效**，是本机制最易复发的坑 |
| OS-3 | **能自动产出的一律不手写** | FilterSet / 分页器 / 认证类已能产出的声明禁止手工重写（会削平 `enum` / `title` / 选项说明）。手工声明只用于自动注入**确实无法表达**的语义（如 `keyword`） |
| OS-4 | **重声明同一 action 必须复用共享片段** | 子类重声明 Mixin 的 action 时，`summary` / `responses` / 分页参数一律从共享字典取（如 `EXPORT_ACTION_SCHEMA`），且只 `super()` 委托、不复制实现体（DR-1） |
| OS-5 | **双向红线** | 「文档超前于运行时」同样是失真：禁止为迁就文档去改运行时口径，也禁止给不消费参数的端点硬加参数声明 |
| OS-6 | **校对义务** | 任何改动 `@extend_schema` / 新增端点的 PR，必须重导出 `api-schema-baseline.json` 并 diff，确认变更**只落在预期端点**；无消费方的失真同样要修（它坑未来接入方与生成客户端） |
| OS-7 | **契约类端点必须有 schema 护栏** | 仅 HTTP 行为测试无法发现文档失真。涉及 OpenAPI 声明的端点须有用例**对照运行时事实**断言（响应结构 / 参数集 / enum），且**必须包含反向护栏**（OS-5）；断言值取自权威源（如 `TextChoices`），禁止硬编码字面量 |

**【聚合响应结构】** 响应体即 payload，`code` / `message` 属响应包装、**不入 schema**。无写入/校验需求的聚合端点用 `inline_serializer` 显式声明字段；不得为「文档需要」新增一个存在误导的 Serializer（会让读者误以为存在写入路径）。

## 五、后端代码复用与量化规范（DRY 落地）
本细则对应宪法级规则 DR-1、DR-3、DR-5、DR-6，所有后端代码必须遵守。

| ID	| 规范项	| 约束内容	| 违规补救 |
| :--- | :--- | :--- | :--- |
| BR-1	| **查询收敛至 Selector** |	所有带过滤条件的资产查询（如 Asset.objects.filter(status='in_store', is_deleted=False)），必须封装为 Selector 类的方法（如 AssetSelector.available_assets()）。禁止在多个 Service 中重复拼写过滤链。|	重构，将查询逻辑下沉至 Selector |
| BR-2	| **业务逻辑抽取至 Service 基类** |	当两个及以上 Service 出现相同业务操作（如"变更资产状态并记录日志"）时，必须抽取到公共 Service 基类或 Mixin 中，禁止复制方法体。|	抽取公共父类或 Mixin |
| BR-3	| **常量与枚举集中定义** |	资产状态、资产类型等枚举值必须定义在 apps/<app>/constants.py 或 models.py 的 TextChoices 中，禁止在函数内硬编码字符串值。Service 层比较/赋值必须使用 `Model.Field.VALUE` 形式（如 `Asset.AssetStatus.IN_USE`、`DamagedAsset.ApprovalStatus.PENDING`）。|	迁移至全局常量定义区 |
| BR-4	| **函数长度红线** |	单个函数/方法（含 Service 方法、工具函数）不得超过 50 行（不含空行和注释）。超过时，必须拆分为多个私有方法（_helper）。|	拆分并分层调用 |
| BR-5	| **圈复杂度管控** |	单个函数的圈复杂度（McCabe）不得超过 10。使用 ruff check --select C90 检查。超过时，必须简化条件分支或使用策略模式。|	重构分支逻辑 |
| BR-6	| **文件行数限制** |	单个 .py 文件不得超过 500 **逻辑行**。口径：物理跨度行数 − 空行 − 纯 `#` 注释行 − 本文件模块 docstring（唯一实现见 `scripts/line_metrics.py`，BR-4/BR-6 共用）。**不纳入**测试文件（文件名含 `test`/`conftest` 或路径含 `tests/`、`test/` 段）与 `migrations/`。⚠️ 禁止用 PowerShell `Measure-Object -Line` 数行——它跳过空行，可低估约 12%。超过时按职责拆分（如 services.py → services/checkout.py + services/recycle.py）。护栏 `scripts/check_file_length_guard.py`，台账 `Rules_Fiels/BR6_file_length_ledger.md`。|	拆分为模块包 |
| BR-7	| **调用链验证** |	视图（View）→ 服务（Service）→ 选择器（Selector）的纵深不得超过 3 层（View→Service→Selector 为标准深度）。若出现 View→Service→Service→Selector 等 4 层+，必须扁平化或使用事件驱动解耦。|	合并中间层或引入事件 |

## 六、变更日志
- v1.18 (2026-09-29): **BR-6 条文实质修订**——「500 行」补齐口径定义（原条文只写「不含迁移文件」，未定义行数口径，是 D3 连续两次误判的根因）。① 口径统一为**逻辑行**＝物理跨度 − 空行 − 纯 `#` 注释行 − 模块 docstring，唯一实现 `scripts/line_metrics.py`，**BR-4/BR-6 共用**（DR-1 消重）；② **测试文件不再纳入** BR-6（与 BR-4 护栏既有 `is_test()` 排除对齐，用户 2026-09-29 拍板）；③ 新增护栏 `scripts/check_file_length_guard.py` + 台账 `Rules_Fiels/BR6_file_length_ledger.md` + CI `backend-lint` job 内 step，**零存量债，上线即阻断**，不适用 §5.4 沙盒期；④ 明令禁用 PowerShell `Measure-Object -Line`（跳空行，`operation_log_service.py` 真实 508 会被报成 447，低估约 12%）。**连带影响**：BR-4 口径同步剔除 docstring（原为「docstring 计入代码行」），因其台账当时为空表且 0 违规，实测无行为变化，已回归验证。误判纠正记录：D3 先按 `wc -l` 误判 `operation_log_service.py`(508) 违规、继而误判 `contract_service.py`(489) 为唯一目标，两次均系口径未定义所致；按逻辑行口径二者实为 432 / 399，**均不违规，故取消全部拆分动作**，交付物转为「护栏 + 口径定义」。另修复护栏 `read_text` 的 BOM 假绿缺陷：原 `utf-8` 解码遇 BOM 产生 U+FEFF 致 `ast.parse` 失败、文件被静默跳过，超限文件可蒙混过关；改为 `utf-8-sig` 打头（由负向测试发现）。
- v1.17 (2026-09-26): 新增 §4.8 OpenAPI 契约声明细则（增补）——BF-049 / BF-050 落地。① 记录两条实测机制：`AutoSchema.get_filter_backends()` 的 `_is_list_view()` 门控（非 list 响应静默关闭筛选参数发现，且改 `responses` 会连锁翻转）、`@extend_schema` 手工声明「只替换不校正」；② OS-1~OS-7：显式 opt-in（`ForceFilterDiscoverySchema` + `frozenset`，禁改全局启发式）、名单取 action **方法名**（OS-2，附"写错静默不生效"坑点记录）、自动可产出的不手写、重声明复用共享片段、**文档超前于运行时同属失真**、PR 须 diff 基线、契约端点必须有对照运行时事实的 schema 护栏；③ 明确聚合响应用 `inline_serializer` 且不新增误导性 Serializer。附带订正：v1.16 只更新了变更日志、未升头部版本号（两处均为 v1.15），本次同步至 v1.17。本节属细则增补，不修改 B1-B10、§4.2 矩阵与 BR 条文。
- v1.16 (2026-09-26): 新增 §4.7 员工域细则（增补，4.2 矩阵原文不改）——B12 行级隔离在员工域首次落地（BF-048）：`EmployeeViewSet` 此前直接用 `queryset` 类属性全量返回，`dept_manager` 持 `CanExportExcel` 可导出全公司员工档案。① 收窄口径完全委托既有 `get_department_codes_for_user`（三态语义与操作日志侧同源，零新业务规则）；② 收窄入口唯一化为覆写 `get_queryset()`，一次覆盖 list/retrieve/search/statistics/export，并显式收窄 `active_employees` / `by-auth-user` / `employees/{jobcode}` 三个旁路；③ 附带修正 `by-auth-user` 畸形 ID 返回 500（`ValueError`）为 404；④ `statistics` 聚合口径改随权限收窄（数值范围变化，响应结构不变）；⑤ 越权一律 404；⑥ 回归屏障 `test_employee_rbac_scope.py` 14 用例。本节属细则增补与既有规则的落地记录，不修改 4.2 矩阵原文。
- v1.15 (2026-09-23): `[PATCH-BE]` 权限矩阵 :142「报废审批」行修订——操作列从「审批通过/拒绝」扩展为「申请（单条 create）/审批通过/拒绝/批量删除」，与实现对齐（`DamagedAssetViewSet.admin_actions` 纳入 `create`，走 `IsDeptManagerOrAbove`；方案 A：asset_admin 对单条 create ❌）。同步 `test_damaged_asset_view_api.py::TestDamagedCreateRBAC` 三角色测试同批落地（BF-037）。
- v1.14 (2026-09-21): BR-4 函数长度红线实施方式固化（门禁先行，对应审查报告 #21）——① 新增 `scripts/check_function_length_guard.py`：以 AST 语义节点扫描 `apps/`（不含迁移/tests），BR-4 逻辑行口径 = 物理跨度行 − 空行 − `#` 注释行（docstring 计入代码行），>50 行即超限；台账 `Rules_Fiels/BR4_function_length_ledger.md` 为唯一豁免源，guard 断言"超限未登记即红、已拆分未移除即红"；② `pyproject.toml` `lint.ignore` 显式加入 `PLR0915`（ruff 无函数行数规则，此防御性关闭防未来启用 PLR 被存量淹没）；③ 计数口径说明：BR-4 语义口径下生产超长函数 19 处（物理行口径参考 38 处，差异源于空行/注释行占比较高）；④ 本变更属实施方式固化，非规则文本修改，`[PATCH-BE]` 留痕；⑤ CI 接入 `function-length-guard` job。
- v1.13 (2026-09-17): 新增业务约束第 7 条——资产创建初始状态必须为 `in_store` 且由 `AssetService.create_asset` 统一注入（枚举引用），创建类 Serializer 禁止暴露 `asset_current_status` 写字段（P0-1 FSM 绕过修复的文档同步，含回归确认：`serializers/asset_crud_serializers.py` 移除写字段、`service` 注入枚举、schema baseline 重导出、测试 655 passed）。
- v1.12 (2026-09-12): 公开扫码最小暴露收敛（R4-04）——匿名扫码响应从 12+ 字段（含价格/仓库/分类/保管人姓名/电话/入库日期，价格仅电话遮罩）收敛为 6 字段白名单；新增 `public_scan` 审计日志（成功查询记 IP，404 不记）；Selector 免 JOIN；新增 §4.6 公开扫码细则；同步 schema baseline 与前端（登录态直达全量详情、未登录公开 6 字段 + 登录引导）。
- v1.11 (2026-09-12): 取消报废回退语义修正——`cancel_damaged` 从"一律回 recycled_pending"改为"按 `DamagedAsset.original_status` 回退申请前状态"，与审批拒绝（`reject_to_original`，v1.5）保持一致；缺失/非法兜底 recycled_pending。同步实现（`scrapping.py` 签名+回退逻辑、`damaged_asset_service.py` 传参（保留行锁）、批量取消经委托自动继承）与文档（状态机规则表/特殊回退操作表/ASCII 图/业务约束新增第 6 条）与技术设计文档 `03-业务规则与状态机.md` 旧约定修正。业务约束第 6 条为新增产品决策。
- v1.10 (2026-08-15): 通知事务安全补全（B6 审计落地）——① `damaged_asset_service` 的 `approve_asset_recordcode`/`reject_asset_recordcode` 事务内直调 `notify_dept_managers()` 统一改用 `send_notification_on_commit()`，并删除无效的 `try/except Exception: pass` 空包（修正 v1.6 声称"所有事务内通知已统一改用"但 damaged 未迁移的遗漏）；② `send_notification_on_commit` 加固：非事务块调用抛 `TransactionManagementError`（阻止通知过早发送）、回调体 `try/except` + 结构化日志（含 asset_code/notification_type）、`transaction.on_commit(..., robust=True)`（回调异常不传播为 500、不连锁丢弃同事务其余回调）；③ 测试补全：`send_notification_on_commit` 3 个单测（注册+提交后发送/异常吞没并记日志/非 atomic 抛错）+ approve/reject/complete/fail 四路径 on_commit 行为断言（提交前不发送、提交后发送、参数正确）+ 异常路径红→绿回归护栏（stash 回退旧实现实测护栏由红转绿）。
- v1.9 (2026-08-12): 维修/找回目标状态修正——`repairing → recycled_pending`（维修完成）、`lost → recycled_pending`（找回）：已使用过的资产修好/找回后统一重新进入发放池，仅首次入库新资产为 `in_store`。同步实现（`core.py` `_TRANSITIONS`）与测试。
- v1.8 (2026-08-12): 新增 4.5 节"未登记资产细则"——角色×动作矩阵、行级隔离（角色白名单优先+本人提交例外）、接口语义（discovery_person 默认本人/approver 强制当前人/越权 404/审计解耦）。不修改 4.2 矩阵原文，仅澄清"处理"列=审批动作的解读。
- v1.7 (2026-07-21 → 修正 2026-08-17): 错误码体系清理——原声称 D-015 重构（`BizCode` 类 + `ERROR_CODE_TO_BIZ` 映射 + `EXCEPTION_TO_ERROR_TYPE` 语义化映射 + `exception_handler.py` 三级兜底 + `code` 字段改为业务码）**均未实际落地**，属虚构变更日志。修正后实际方案：① 删除 `core/constants.py` 中从未引用的 `ERROR_CODES` 字典；② `response_utils.py` 中 `BusinessCode` 仅保留 `SUCCESS=0`，删除 6 个 HTTP 映射码（与 `status.HTTP_*` 恒等）和 5 个从未使用的业务码（`INVALID_TRANSITION`/`RESOURCE_CONFLICT`/`ASSET_NOT_FOUND`/`PERMISSION_DENIED`/`BUSINESS_LOGIC_ERROR`）；③ `error_response` 删除 `business_code` 参数（无调用方传此参数），`code` 字段直接使用 `status_code`；④ 服务层 `error_code` 字符串（如 `ASSET_NOT_FOUND`/`ILLEGAL_OUTASSET` 等 80+ 处）保持现状——仅用于批量操作 `fail_items` 日志，不进入单条错误响应体，前端不消费。View 层 4 处 `business_code=fail_item.get("error_code")` 类型违规（string→int）已修复为 `errors={"error_code": ...}`。
- v1.6 (2026-07-21): 审计修复落地——① B9 枚举约束强化：`damaged_asset_service`/`waste_asset_service`/`recycle_asset_service`/`out_asset_service`/`repair_asset_service`/`asset_lifecycle_mixin` 共 6 个 Service 文件的硬编码字符串已替换为 `Asset.AssetStatus.*` 和 `DamagedAsset.ApprovalStatus.*` 枚举引用；② 通知事务安全：所有 `@transaction.atomic` 内的通知调用统一改用 `send_notification_on_commit()`，确保事务提交后才发送 WebSocket 推送；③ DRY 权限检查：`DamagedAssetService` 新增 `_check_approval_permission()` 私有方法，`approve_asset_recordcode` 和 `reject_asset_recordcode` 的重复权限校验块（~40 行）已合并；④ 批量操作优化：`hard_disk_sn_service.batch_save` 从逐条 `save()`/`create()` 改为 `bulk_create`+`bulk_update`，减少 N 次 DB 写入为 1-2 次；⑤ Selector 性能：`get_assets_by_status`/`get_assets_by_type`/`get_assets_by_storage`/`combine_search` 补充 `select_related` 预加载 3 个 FK 关联。
- v1.5 (2026-07-21): 报废审批拒绝回退语义修正——将 `damaged → recycled_pending`（原状态为其他）拆分为 `damaged → in_use`（原状态为in_use）和 `damaged → recycled_pending`（原状态为recycled_pending），新增业务约束第5条：审批拒绝必须回退到申请前的状态。
- v1.4 (2026-07-14): 新增第四节 RBAC 权限与行级数据隔离（B11-B14），包含 5 角色定义、功能权限矩阵、行级隔离策略、资产部门动态解析规则。
- v1.3 (2026-07-08): 新增 `repairing`（维修中）状态，更新状态机图，添加 `broken→repairing→in_store/damaged` 转换路径，同步设计文档 V2.1。

- v1.2 (2026-07-07): 增加对根级安全/可观测性契约的引用（已在设计思路中体现），无实质条款变更。

- v1.1 (2026-07-07): 新增第四节"后端代码复用与量化规范"（BR-1~BR-7）。

- v1.0 (2026-07-07): 初始版本，基于项目 README 建立 B1-B10 与状态机。
