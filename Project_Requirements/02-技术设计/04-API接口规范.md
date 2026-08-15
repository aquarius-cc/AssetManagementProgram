# 资产管理系统后端API接口规范

**版本：V2.7**
**日期：2026-08-12**
**状态：草案**

---

## 1. 序列化器命名规范

| 序列化器类型 | 命名格式 | 用途 |
|------------|---------|------|
| **ListSerializer** | `{Model}ListSerializer` | 列表展示（核心字段） |
| **DetailSerializer** | `{Model}DetailSerializer` | 详情展示（含嵌套关联） |
| **CreateSerializer** | `{Model}CreateSerializer` | 创建时使用 |
| **UpdateSerializer** | `{Model}UpdateSerializer` | 更新时使用 |
| **BatchCreateSerializer** | `{Model}BatchCreateSerializer` | 批量创建 |
| **BatchDeleteSerializer** | `{Model}BatchDeleteSerializer` | 批量删除 |
| **SimpleSerializer** | `{Model}SimpleSerializer` | 下拉选单（基础信息） |
| **FilterSerializer** | `{Model}FilterSerializer` | 多条件筛选请求（含 query 对象） |

---

## 2. API端点清单

### 2.1 资产类型管理 `/api/v1/assets/asset-types/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/assets/asset-types/` | 类型列表 | - | AssetTypeListSerializer |
| GET | `/assets/asset-types/simple/` | 下拉选单（暂不实现） | - | AssetTypeSimpleSerializer |
| POST | `/assets/asset-types/` | 创建类型 | AssetTypeCreateSerializer | AssetTypeDetailSerializer |
| GET | `/assets/asset-types/{recordcode}/` | 类型详情 | - | AssetTypeDetailSerializer |
| GET | `/assets/asset-types/{recordcode}/full-path/` | 获取完整类型编码和名称路径 | - | AssetTypeFullPathSerializer |
| GET | `/assets/asset-types/tree/` | 获取树形结构数据 | - | AssetTypeTreeNodeSerializer |
| PUT | `/assets/asset-types/{recordcode}/` | 更新类型 | AssetTypeUpdateSerializer | AssetTypeDetailSerializer |
| DELETE | `/assets/asset-types/{recordcode}/` | 删除类型 | - | - |
| POST | `/assets/asset-types/batch-create/` | 批量创建 | AssetTypeBatchCreateSerializer | AssetTypeDetailSerializer (list) |
| POST | `/assets/asset-types/batch-delete/` | 批量删除 | AssetTypeBatchDeleteSerializer | - |
| POST | `/assets/asset-types/filter/` | 多条件联合筛选 | AssetTypeFilterSerializer | AssetTypeListSerializer |

### 2.2 仓库管理 `/api/v1/assets/storages/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/assets/storages/` | 仓库列表 | - | StorageListSerializer |
| GET | `/assets/storages/simple/` | 下拉选单（暂不实现） | - | StorageSimpleSerializer |
| POST | `/assets/storages/` | 创建仓库 | StorageCreateSerializer | StorageDetailSerializer |
| GET | `/assets/storages/{recordcode}/` | 仓库详情 | - | StorageDetailSerializer |
| PUT | `/assets/storages/{recordcode}/` | 更新仓库 | StorageUpdateSerializer | StorageDetailSerializer |
| DELETE | `/assets/storages/{recordcode}/` | 删除仓库 | - | - |
| POST | `/assets/storages/batch-create/` | 批量创建 | StorageBatchCreateSerializer | StorageDetailSerializer (list) |
| POST | `/assets/storages/batch-delete/` | 批量删除 | StorageBatchDeleteSerializer | - |
| POST | `/assets/storages/filter/` | 多条件联合筛选 | StorageFilterSerializer | StorageListSerializer |

### 2.3 合同管理 `/api/v1/assets/contracts/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/assets/contracts/` | 合同列表 | - | ContractListSerializer |
| GET | `/assets/contracts/simple/` | 下拉选单（暂不实现） | - | ContractSimpleSerializer |
| POST | `/assets/contracts/` | 创建合同 | ContractCreateSerializer | ContractDetailSerializer |
| GET | `/assets/contracts/{recordcode}/` | 合同详情 | - | ContractDetailSerializer |
| PUT | `/assets/contracts/{recordcode}/` | 更新合同 | ContractUpdateSerializer | ContractDetailSerializer |
| DELETE | `/assets/contracts/{recordcode}/` | 删除合同 | - | - |
| POST | `/assets/contracts/batch-create/` | 批量创建 | ContractBatchCreateSerializer | ContractDetailSerializer (list) |
| POST | `/assets/contracts/batch-delete/` | 批量删除 | ContractBatchDeleteSerializer | - |
| POST | `/assets/contracts/filter/` | 多条件联合筛选（支持合同编号、名称、供应商、签订年份等） | ContractFilterSerializer | ContractListSerializer |

### 2.4 资产管理 `/api/v1/assets/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/assets/` | 资产列表 | - | AssetListSerializer |
| GET | `/assets/simple/` | 下拉选单（暂不实现） | - | AssetSimpleSerializer |
| POST | `/assets/` | 创建资产 | AssetCreateSerializer | AssetDetailSerializer |
| GET | `/assets/{recordcode}/` | 资产详情 | - | AssetDetailSerializer |
| PUT | `/assets/{recordcode}/` | 更新资产 | AssetUpdateSerializer | AssetDetailSerializer |
| DELETE | `/assets/{recordcode}/` | 删除资产 | - | - |
| POST | `/assets/batch-create/` | 批量创建 | AssetBatchCreateSerializer | AssetDetailSerializer (list) |
| POST | `/assets/batch-delete/` | 批量删除 | AssetBatchDeleteSerializer | - |
| POST | `/assets/{recordcode}/checkout/` | 出库 | OutAssetCreateSerializer | OutAssetDetailSerializer |
| POST | `/assets/{recordcode}/recycle/` | 回收 | RecycleAssetCreateSerializer | RecycleAssetDetailSerializer |
| POST | `/assets/{recordcode}/mark-broken/` | 标记损坏 | BrokenAssetCreateSerializer | BrokenAssetDetailSerializer |
| POST | `/assets/{recordcode}/mark-lost/` | 标记遗失 | LostAssetCreateSerializer | LostAssetDetailSerializer |
| POST | `/assets/{recordcode}/found/` | 找回 | FoundAssetCreateSerializer | FoundAssetDetailSerializer |
| POST | `/assets/{recordcode}/repair/` | 送修 | RepairAssetCreateSerializer | RepairAssetDetailSerializer |
| POST | `/assets/{recordcode}/repair-done/` | 维修完成 | RepairAssetUpdateSerializer | RepairAssetDetailSerializer |
| POST | `/assets/{recordcode}/repair-failed/` | 维修失败 | RepairAssetUpdateSerializer | RepairAssetDetailSerializer |
| POST | `/assets/{recordcode}/apply-scrap/` | 申请报废 | DamagedAssetCreateSerializer | DamagedAssetDetailSerializer |
| GET | `/assets/{recordcode}/logs/` | 状态日志 | - | AssetOperationLogListSerializer |
| POST | `/assets/filter/` | 多条件联合筛选（支持编码、名称、规格、品牌、合同、保管人、部门、状态、使用性质、仓库等） | AssetFilterSerializer | AssetListSerializer |
| GET | `/assets/export/` | 导出资产列表（Excel） | - | 文件流 |

### 2.4a 公开接口（无需认证） `/api/v1/assets/public/`

| 方法 | 路径 | 功能 | 说明 |
|------|------|------|------|
| GET | `/assets/public/scan/{recordcode}/` | 扫码查看资产详情 | 无需 JWT 认证；返回脱敏后的资产信息（价格显示"****"，联系电话前3后4脱敏） |

### 2.5 出库记录 `/api/v1/assets/out-assets/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/assets/out-assets/` | 出库列表 | - | OutAssetListSerializer |
| POST | `/assets/out-assets/` | 创建出库 | OutAssetCreateSerializer | OutAssetDetailSerializer |
| GET | `/assets/out-assets/{recordcode}/` | 出库详情 | - | OutAssetDetailSerializer |
| DELETE | `/assets/out-assets/{recordcode}/` | 取消出库 | - | - |
| POST | `/assets/out-assets/batch-create/` | 批量创建 | OutAssetBatchCreateSerializer | OutAssetDetailSerializer (list) |
| POST | `/assets/out-assets/batch-delete/` | 批量删除 | OutAssetBatchDeleteSerializer | - |
| POST | `/assets/out-assets/filter/` | 多条件联合筛选 | OutAssetFilterSerializer | OutAssetListSerializer |
| GET | `/assets/out-assets/export/` | 导出出库记录（Excel） | - | 文件流 |

### 2.6 回收记录 `/api/v1/assets/recycle-assets/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/assets/recycle-assets/` | 回收列表 | - | RecycleAssetListSerializer |
| POST | `/assets/recycle-assets/` | 创建回收 | RecycleAssetCreateSerializer | RecycleAssetDetailSerializer |
| GET | `/assets/recycle-assets/{recordcode}/` | 回收详情 | - | RecycleAssetDetailSerializer |
| DELETE | `/assets/recycle-assets/{recordcode}/` | 取消回收 | - | - |
| POST | `/assets/recycle-assets/batch-create/` | 批量创建 | RecycleAssetBatchCreateSerializer | RecycleAssetDetailSerializer (list) |
| POST | `/assets/recycle-assets/filter/` | 多条件联合筛选 | RecycleAssetFilterSerializer | RecycleAssetListSerializer |
| GET | `/assets/recycle-assets/export/` | 导出回收记录（Excel） | - | 文件流 |

### 2.7 损坏/遗失/找回/维修记录

| 模块 | 路径前缀 | 列表序列化器 | 详情序列化器 | 创建序列化器 | 筛选序列化器 |
|------|---------|-------------|-------------|-------------|-------------|
| 损坏记录 | `/api/v1/assets/broken-assets/` | BrokenAssetListSerializer | BrokenAssetDetailSerializer | BrokenAssetCreateSerializer | BrokenAssetFilterSerializer |
| 遗失记录 | `/api/v1/assets/lost-assets/` | LostAssetListSerializer | LostAssetDetailSerializer | LostAssetCreateSerializer | LostAssetFilterSerializer |
| 找回记录 | `/api/v1/assets/found-assets/` | FoundAssetListSerializer | FoundAssetDetailSerializer | FoundAssetCreateSerializer | FoundAssetFilterSerializer |
| 维修记录 | `/api/v1/assets/repair-assets/` | RepairAssetListSerializer | RepairAssetDetailSerializer | RepairAssetCreateSerializer | RepairAssetFilterSerializer |

**端点清单（以损坏记录为例，其余类似）**：
- `GET /assets/broken-assets/`
- `POST /assets/broken-assets/`
- `GET /assets/broken-assets/{recordcode}/`
- `DELETE /assets/broken-assets/{recordcode}/`
- `POST /assets/broken-assets/batch-create/`
- `POST /assets/broken-assets/filter/`

### 2.8 报废流程 `/api/v1/assets/damaged-assets/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/assets/damaged-assets/` | 待报废列表 | - | DamagedAssetListSerializer |
| POST | `/assets/damaged-assets/` | 提交申请 | DamagedAssetCreateSerializer | DamagedAssetDetailSerializer |
| GET | `/assets/damaged-assets/{recordcode}/` | 详情 | - | DamagedAssetDetailSerializer |
| POST | `/assets/damaged-assets/{recordcode}/approve/` | 审批通过 | - | WasteAssetDetailSerializer |
| POST | `/assets/damaged-assets/{recordcode}/reject/` | 审批拒绝 | - | DamagedAssetDetailSerializer |
| POST | `/assets/damaged-assets/{recordcode}/cancel/` | 取消申请 | - | DamagedAssetDetailSerializer |
| POST | `/assets/damaged-assets/filter/` | 多条件联合筛选 | DamagedAssetFilterSerializer | DamagedAssetListSerializer |

### 2.9 未登记资产 `/api/v1/unregisteredassets/unregistered-assets/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/unregisteredassets/unregistered-assets/` | 列表 | - | UnregisteredAssetListSerializer |
| POST | `/unregisteredassets/unregistered-assets/` | 提交发现 | UnregisteredAssetCreateSerializer | UnregisteredAssetDetailSerializer |
| GET | `/unregisteredassets/unregistered-assets/{recordcode}/` | 详情 | - | UnregisteredAssetDetailSerializer |
| POST | `/unregisteredassets/unregistered-assets/{recordcode}/approve/` | 审批 | - | UnregisteredAssetDetailSerializer |
| POST | `/unregisteredassets/unregistered-assets/{recordcode}/reject/` | 拒绝 | - | UnregisteredAssetDetailSerializer |
| POST | `/unregisteredassets/unregistered-assets/filter/` | 多条件联合筛选 | UnregisteredAssetFilterSerializer | UnregisteredAssetListSerializer |

### 2.10 部门管理 `/api/v1/users/departments/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/users/departments/` | 部门列表 | - | DepartmentListSerializer |
| GET | `/users/departments/simple/` | 下拉选单（暂不实现） | - | DepartmentSimpleSerializer |
| GET | `/users/departments/tree/` | 树形数据 | - | DepartmentDetailSerializer |
| POST | `/users/departments/` | 创建部门 | DepartmentCreateSerializer | DepartmentDetailSerializer |
| GET | `/users/departments/{recordcode}/` | 详情 | - | DepartmentDetailSerializer |
| PUT | `/users/departments/{recordcode}/` | 更新部门 | DepartmentUpdateSerializer | DepartmentDetailSerializer |
| DELETE | `/users/departments/{recordcode}/` | 删除部门 | - | - |
| POST | `/users/departments/batch-create/` | 批量创建 | DepartmentBatchCreateSerializer | DepartmentDetailSerializer (list) |
| POST | `/users/departments/batch-delete/` | 批量删除 | DepartmentBatchDeleteSerializer | - |
| POST | `/users/departments/filter/` | 多条件联合筛选 | DepartmentFilterSerializer | DepartmentListSerializer |

### 2.11 员工管理 `/api/v1/users/employees/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/users/employees/` | 员工列表 | - | EmployeeListSerializer |
| GET | `/users/employees/simple/` | 下拉选单（暂不实现） | - | EmployeeSimpleSerializer |
| GET | `/users/employees/by-department/{dept_code}/` | 按部门查询 | - | EmployeeListSerializer |
| POST | `/users/employees/` | 创建员工 | EmployeeCreateSerializer | EmployeeDetailSerializer |
| GET | `/users/employees/{recordcode}/` | 详情 | - | EmployeeDetailSerializer |
| PUT | `/users/employees/{recordcode}/` | 更新员工 | EmployeeUpdateSerializer | EmployeeDetailSerializer |
| DELETE | `/users/employees/{recordcode}/` | 删除员工 | - | - |
| POST | `/users/employees/batch-create/` | 批量创建 | EmployeeBatchCreateSerializer | EmployeeDetailSerializer (list) |
| POST | `/users/employees/batch-delete/` | 批量删除 | EmployeeBatchDeleteSerializer | - |
| POST | `/users/employees/filter/` | 多条件联合筛选 | EmployeeFilterSerializer | EmployeeListSerializer |

### 2.12 用户认证 `/api/v1/auth/`

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| POST | `/auth/login/` | 登录 | LoginSerializer | LoginResponseSerializer |
| POST | `/auth/logout/` | 登出 | - | - |
| POST | `/auth/token/refresh/` | 刷新令牌 | RefreshTokenSerializer | LoginResponseSerializer |
| POST | `/auth/change-password/` | 修改密码 | ChangePasswordSerializer | - |
| GET | `/auth/profile/` | 获取当前用户 | - | AuthUserDetailSerializer |
| PUT | `/auth/profile/` | 更新个人信息 | AuthUserUpdateSerializer | AuthUserDetailSerializer |
| GET | `/auth/users/` | 用户列表 | - | AuthUserListSerializer |
| GET | `/auth/users/simple/` | 下拉选单（暂不实现） | - | AuthUserSimpleSerializer |
| POST | `/auth/users/` | 创建用户 | AuthUserCreateSerializer | AuthUserDetailSerializer |
| PUT | `/auth/users/{id}/` | 更新用户 | AuthUserUpdateSerializer | AuthUserDetailSerializer |
| DELETE | `/auth/users/{id}/` | 删除用户 | - | - |
| POST | `/auth/users/filter/` | 多条件联合筛选 | AuthUserFilterSerializer | AuthUserListSerializer |

---

## 3. 分页与过滤参数

**分页参数**（适用于所有列表及筛选接口）：
- `page`：页码，默认1
- `page_size`：每页条数，默认20，最大100

**通用过滤参数**（适用于 GET 列表接口）：
- `search`：模糊搜索（编码、名称、规格）
- `ordering`：排序字段（`created_at`、`updated_at`等）
- `is_deleted`：软删除过滤（默认false）

**筛选端点（POST /filter/）**：
- 请求体为 JSON 对象，包含 `query` 字段，其具体可过滤字段见各模型对应的 `FilterSerializer` 定义。
- 支持分页参数（`page`、`page_size`）和排序参数 `ordering`（可在请求体中或作为 URL 查询参数传递）。
- 各筛选条件之间为 **AND 逻辑**，同一字段内（如 `asset_code`）为模糊匹配（`icontains`）或精确匹配（取决于设计）。
- 若 `query` 为空对象 `{}`，则返回所有未删除记录（`is_deleted=False`），并按默认排序（如 `-created_at`）。

---

## 4. 接口幂等性

| 接口类型 | 幂等性 | 实现方式 |
|:---|:---:|:---|
| POST 创建（单条） | 否 | 重复提交会创建多条记录 |
| POST 批量创建 | 否 | 逐条处理，部分失败不影响已成功条目 |
| PUT 更新 | 是 | 基于 version 乐观锁，重复更新不会产生副作用 |
| DELETE 软删除 | 是 | 重复删除不会改变数据状态 |
| POST 状态变更（出库/回收等） | 否 | 重复操作会触发状态校验拒绝 |
| POST 审批 | 是 | 重复审批被 approval_status 校验拒绝 |

**前端防重复提交**：按钮点击后 disable + loading，请求完成后恢复。

---

## 5. API 版本策略

- 当前版本：`/api/v1/`
- 版本升级触发条件：破坏性变更（字段删除、响应结构变化、枚举值变更）
- 共存策略：新版本发布后，旧版本保留 **6 个月**，期间标记为 Deprecated
- 版本协商：客户端通过 URL 路径指定版本，不支持 Accept Header 协商

---

## 6. 实时通知（WebSocket）

### 6.1 适用场景

| 场景 | 通知内容 | 接收角色 |
|:---|:---|:---|
| 报废审批结果 | "您的报废申请已通过/拒绝" | 申请人 |
| 新报废待审批 | "有新的报废申请待审批" | 部门经理 |
| 资产状态异常 | "资产 XXX 状态与记录不一致" | 系统管理员 |

### 6.2 WebSocket 端点

```
ws://api.example.com/ws/notifications/
```

### 6.3 消息格式

```json
{
  "type": "scrap_approved",
  "title": "报废审批通过",
  "message": "资产 ThinkPad-A1 的报废申请已审批通过",
  "asset_code": "IT-NB-A3F9B2E1",
  "timestamp": "2026-07-09T14:30:00Z"
}
```

### 6.4 认证方式

- WebSocket 连接时通过 URL 查询参数传递 JWT Token：`ws://api.example.com/ws/notifications/?token=<access_token>`
- 服务端在握手阶段验证 Token 有效性，无效则拒绝连接（HTTP 401）
- Token 过期后连接自动断开，前端需使用 Refresh Token 获取新 Token 后重连

### 6.5 断线重连策略

| 重连次数 | 等待时间 | 说明 |
|:---:|:---|:---|
| 第 1 次 | 1 秒 | 立即重试 |
| 第 2 次 | 3 秒 | 指数退避 |
| 第 3 次 | 9 秒 | 指数退避 |
| 第 4 次+ | 30 秒（上限） | 停止重连，提示用户"连接已断开，请刷新页面" |

### 6.6 心跳机制

- 客户端每 **30 秒**发送一次 Ping 帧
- 服务端收到 Ping 后回复 Pong 帧
- 若 **90 秒**内未收到 Pong，客户端判定连接丢失，触发重连

### 6.7 消息可靠性

- 服务端为每个用户维护未读消息队列（Redis List，保留 24 小时）
- 用户重连后，服务端推送队列中的未读消息
- 前端通过 `last_message_id` 字段记录已接收的最后一条消息，避免重复显示

---

## 修订历史

| 版本 | 日期 | 修订内容 |
|------|------|---------|
| V2.0 | 2026-07-08 | 初始版本 |
| V2.1 | 2026-07-08 | 新增维修相关端点 |
| V2.2 | 2026-07-08 | 完善API端点清单 |
| V2.3 | 2026-07-08 | 新增部门/员工/认证端点 |
| V2.4 | 2026-07-08 | 补充AssetType/Storage/Contract端点；关联序列化器 |
| V2.5 | 2026-07-09 | 新增 AssetType 全路径和树形接口；为所有核心模块增加 `/filter/` 多条件联合筛选端点；新增对应 FilterSerializer 序列化器 |
| V2.6 | 2026-07-11 | 以实际实现路径为准更新所有API路径前缀；标注 `/simple/` 端点为暂不实现 |
| V2.7 | 2026-08-12 | 状态日志接口 `/assets/{recordcode}/logs/` 序列化器由 AssetStateLogListSerializer 更正为 AssetOperationLogListSerializer（与实际实现一致） |