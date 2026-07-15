
---

### 📄 文档 4：后端业务规范 `/Rules_Fiels/backend-business-rules.md` (v1.3)

# 后端业务规范与设计思路 (Backend Business Rules)
> 版本：v1.3 | 最后更新：2026-07-08
> 适用范围：Django 6.0 + DRF 3.16 + MySQL 8.0

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
| B6 | **事务原子性** | 涉及状态变更、多表写操作的方法**必须**添加 `@transaction.atomic` | 添加装饰器 |
| B7 | **审计日志** | 所有状态变更**必须**调用 `audit_log` 记录操作人、时间、变更前后状态 | 补上审计调用 |
| B8 | **模型标准字段** | 所有模型**必须**包含 `created_at`(auto_now_add)、`updated_at`(auto_now)、`is_deleted`(软删) | 继承抽象基类 |
| B9 | **枚举约束** | 状态字段**必须**使用 `models.TextChoices`，**禁止**使用整型或字符串硬编码 | 重构为 TextChoices |
| B10 | **外键约束** | 外键**必须**显式指定 `on_delete`，多对多关系**必须**指定 `db_table` | 补充声明 |

## 三、资产状态机（业务流转路径）

```text
                          ┌─────────────────────────────────────┐
                          │                                     │
in_store ──outasset──→ in_use ──recycle──→ recycled_pending     │
    │                    │                    │                  │
    │ mark_broken        │ mark_broken        │ mark_broken      │
    │ mark_lost          │ mark_lost          │ mark_lost        │
    ▼                    ▼                    ▼                  │
 broken/lost         broken/lost          broken/lost           │
    │                    │                    │                  │
    │ start_repair       │                    │                  │
    ▼                    │                    │                  │
repairing ──repair_done──┘                    │                  │
    │                                         │                  │
    │ repair_failed                           │                  │
    └─────────────────────────────────────────┘                  │
              │                                                 │
              ▼                                                 │
           damaged ──approve──→ scrapped                        │
              │                                                 │
              └──reject──→ broken/lost ─────────────────────────┘
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
| `in_use` | `damaged` | 申请报废（在用状态） |
| `recycled_pending` | `in_use` | 再次出库 |
| `recycled_pending` | `broken` | 标记损坏 |
| `recycled_pending` | `lost` | 标记遗失 |
| `recycled_pending` | `damaged` | 申请报废（待发放状态） |
| `broken` | `repairing` | 送修（必须创建维修记录） |
| `broken` | `damaged` | 申请报废（损坏状态） |
| `repairing` | `in_store` | 维修完成（更新physical_grade） |
| `repairing` | `damaged` | 维修失败，申请报废 |
| `lost` | `in_store` | 找回入库 |
| `lost` | `damaged` | 申请报废 |
| `damaged` | `scrapped` | 审批通过 |
| `damaged` | `broken` | 审批拒绝（原状态为broken） |
| `damaged` | `lost` | 审批拒绝（原状态为lost） |
| `damaged` | `recycled_pending` | 审批拒绝（原状态为其他） |
| `scrapped` | *无* | 终态，不可转出 |

**特殊回退操作**：

| 操作 | 方法 | 说明 |
|------|------|------|
| 取消出库 | `cancel_outasset(previous_status)` | 根据出库前状态回退 |
| 取消回收 | `cancel_recycle()` | 恢复到在用 |
| 强制回收 | `force_recycle_from_any()` | 管理员特殊操作，跳过常规校验 |

**业务约束**：

1. 仅允许沿规则表中定义的方向流转，逆向或跳跃流转必须抛出 `InvalidTransitionError`。
2. 涉及 `damaged` 状态的变更，必须附加审批记录。
3. 进入 `repairing` 状态必须同时创建 `RepairAsset` 维修记录。
4. 维修完成时必须更新资产的 `physical_grade` 字段。

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
| 报废审批 | 审批通过/拒绝 | ✅ | ✅ 本部门+下级 | ❌ | ❌ | ❌ |
| 未登记资产 | 处理审批 | ✅ | ✅ 本部门+下级 | ❌ | ❌ | ❌ |
| 系统配置 | 类型/仓库/合同/员工/部门/用户 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 审计日志 | 查看 | ✅ | ❌ | ❌ | ❌ | ✅ |
| 操作日志 | 查看 | ✅ | ✅ 本部门 | ✅ 本部门 | ✅ 本部门 | ✅ 全部 |
| 仪表盘 | 查看 | ✅ | ✅ 本部门+下级 | ✅ 本部门 | ✅ 本部门 | ✅ 全部 |
| 导出 | Excel | ✅ | ✅ 本部门+下级 | ✅ 本部门 | ❌ | ✅ 全部 |
| 扫码查看 | 公开查询 | ✅ | ✅ | ✅ | ✅ | ✅ |

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

## 五、后端代码复用与量化规范（DRY 落地）
本细则对应宪法级规则 DR-1、DR-3、DR-5、DR-6，所有后端代码必须遵守。

| ID	| 规范项	| 约束内容	| 违规补救 |
| :--- | :--- | :--- | :--- |
| BR-1	| **查询收敛至 Selector** |	所有带过滤条件的资产查询（如 Asset.objects.filter(status='in_store', is_deleted=False)），必须封装为 Selector 类的方法（如 AssetSelector.available_assets()）。禁止在多个 Service 中重复拼写过滤链。|	重构，将查询逻辑下沉至 Selector |
| BR-2	| **业务逻辑抽取至 Service 基类** |	当两个及以上 Service 出现相同业务操作（如"变更资产状态并记录日志"）时，必须抽取到公共 Service 基类或 Mixin 中，禁止复制方法体。|	抽取公共父类或 Mixin |
| BR-3	| **常量与枚举集中定义** |	资产状态、资产类型等枚举值必须定义在 apps/<app>/constants.py 或 models.py 的 TextChoices 中，禁止在函数内硬编码字符串值。	| 迁移至全局常量定义区 |
| BR-4	| **函数长度红线** |	单个函数/方法（含 Service 方法、工具函数）不得超过 50 行（不含空行和注释）。超过时，必须拆分为多个私有方法（_helper）。|	拆分并分层调用 |
| BR-5	| **圈复杂度管控** |	单个函数的圈复杂度（McCabe）不得超过 10。使用 ruff check --select C90 检查。超过时，必须简化条件分支或使用策略模式。|	重构分支逻辑 |
| BR-6	| **文件行数限制** |	单个 .py 文件（不含迁移文件）不得超过 500 行。超过时，按职责拆分（如 services.py → services/checkout.py + services/recycle.py）。|	拆分为模块包 |
| BR-7	| **调用链验证** |	视图（View）→ 服务（Service）→ 选择器（Selector）的纵深不得超过 3 层（View→Service→Selector 为标准深度）。若出现 View→Service→Service→Selector 等 4 层+，必须扁平化或使用事件驱动解耦。|	合并中间层或引入事件 |

## 六、变更日志
- v1.4 (2026-07-14): 新增第四节 RBAC 权限与行级数据隔离（B11-B14），包含 5 角色定义、功能权限矩阵、行级隔离策略、资产部门动态解析规则。
- v1.3 (2026-07-08): 新增 `repairing`（维修中）状态，更新状态机图，添加 `broken→repairing→in_store/damaged` 转换路径，同步设计文档 V2.1。

- v1.2 (2026-07-07): 增加对根级安全/可观测性契约的引用（已在设计思路中体现），无实质条款变更。

- v1.1 (2026-07-07): 新增第四节"后端代码复用与量化规范"（BR-1~BR-7）。

- v1.0 (2026-07-07): 初始版本，基于项目 README 建立 B1-B10 与状态机。
