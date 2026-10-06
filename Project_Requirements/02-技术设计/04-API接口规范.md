# 资产管理系统后端API接口规范

**版本：V2.11**
**日期：2026-10-05**
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

### 2.4b 资产分组查询 `/api/v1/assets/grouped/`、`group_children/`

> 支撑资产台账「分组展开表格」。**纯新增端点**，不修改任何既有端点契约。分组视图由前端开关 `enableGrouping` 控制，默认关闭，关闭时走既有 `/assets/`。

| 方法 | 路径 | 功能 | 请求序列化器 | 响应序列化器 |
|------|------|------|-------------|-------------|
| GET | `/assets/grouped/` | 分组汇总（分页后的分组列表） | - | AssetGroupSummarySerializer |
| GET | `/assets/group_children/` | 单个分组的资产明细（懒加载） | - | AssetDetailSerializer (list) |

**响应信封**（与根级 §3 一致）：`{"code": 0, "message": "查询成功", "data": {分页信封}}`

#### 2.4b.1 汇总端点 `GET /api/v1/assets/grouped/`

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `page` / `page_size` | int | 分页（默认 20 / 上限 100，同 §3） |
| `asset_current_status` | str | 状态精确过滤（复用既有键） |
| `asset_type_recordcode` | str | 类型 recordcode 精确过滤（复用既有键） |
| `asset_storage_recordcode` | str | 仓库 recordcode 精确过滤（复用既有键） |
| `contract_code` | str | 合同编码精确过滤（新增） |
| `no_contract` | bool | `true` 时仅返回无合同哨兵组（新增） |
| `asset_code` | str | 资产编码**模糊**过滤（`icontains`，C 新增） |
| `asset_name` | str | 资产名称**模糊**过滤（`icontains`，C 新增） |
| `asset_brand` | str | 资产品牌**模糊**过滤（`icontains`，C 新增） |
| `asset_specification` | str | 资产规格**模糊**过滤（`icontains`，C 新增） |
| `asset_contract_name` | str | 合同名称**模糊**过滤（走 `asset_contract_recordcode__contract_name`，C 新增） |
| `asset_type_category` | str | 类型分类**精确**过滤（值取 `AssetType.type_code`，C 新增） |

> **筛选键与主列表端点同口径**（C 批，v2.3 §3.12.4）：5 个模糊键走 `_build_fuzzy_q`、分类键走 `_apply_exact_filters` 的分类展开，与 `GET /assets/combine_search` 复用同一对实现，故对同一输入两端命中集必然一致。空串一律视为未传（不把整表过滤成空集）。`asset_type_category` 分类下无类型时**返回空集而非全表**（避免「输入了条件但结果没变」的静默失效）。
>
> ⚠️ **C 批扩的是筛选维度，不是响应字段**：`asset_name` / `asset_brand` / `asset_specification` 既是筛选键，也早已是响应里的分组键字段；`asset_code` / `asset_contract_name` / `asset_type_category` **仅作筛选**，不出现在响应中（响应字段集仍为下方 8 项）。
>
> **排序不可由客户端控制**：本端点排序由契约固定（`asset_count` 降序为主键 → 合同号升序且 null 置末 → 名称 / 规格 / 品牌），**不接受 `ordering` 参数**；亦不支持 `search`（分组维度无全文检索需求）。实现侧已将 `filter_backends` 置空，故 OpenAPI 中不出现这两个参数——若日后有人为分组端点挂上 `OrderingFilter`，即破坏本契约。

**响应（200）**

> ✅ **实现进度：汇总端点契约已全部落地（B5 收口，v2.3 §3.5.1）** —— 本节示例即实际响应，OpenAPI 中 `AssetGroupSummary` 为 8 字段（分组键 4 + `group_key` / `asset_count` / `price_display` / `asset_codes`）。B4 的整合期断点（汇总不输出 `group_key`）已消除。
>
> 📌 **`price_min` / `price_max` 是内部聚合字段，刻意不出现在响应里**：`price_display` 由二者派生。若一并外泄，同一组价格就有「原始区间」与「展示串」两种表达，前端无法判断以哪个为准。

```json
{
  "code": 0,
  "message": "查询成功",
  "data": {
    "count": 120,
    "total_pages": 6,
    "page": 1,
    "page_size": 20,
    "next": null,
    "previous": null,
    "results": [
      {
        "group_key": "[\"HT00001\",\"笔记本电脑\",\"14寸/i5\",\"联想\"]",
        "contract_code": "HT00001",
        "asset_name": "笔记本电脑",
        "asset_specification": "14寸/i5",
        "asset_brand": "联想",
        "asset_count": 3,
        "price_display": "4500.00",
        "asset_codes": ["ZC001", "ZC002", "ZC003"]
      }
    ]
  }
}
```

**字段说明**

- `group_key`：JSON 编码四元组 `[contract_code|null, asset_name, asset_specification|null, asset_brand|null]`，供前端缓存 / 展开标识（避开分隔符撞值）。⚠️ 三个可为 null 的维度必须写 JSON `null`，**不得写空串或字符串 `"null"`** —— 空串匹配不到任何行（模型存的是 NULL），字符串 `"null"` 则会真的去查名为 `null` 的合同。中文保持原文（不转义为 `\uXXXX`），与本节示例一致。
- `asset_count`：**组内资产条数**（COUNT 口径），≡ 录入倍数 N
- `price_display`：`min==max` → `"4500.00"`；否则 → `"4500.00~5000.00"`（`~` 分隔，两位小数，升序）。单条资产或多条同价均为单值态。
- `asset_codes`：该组全部资产编码，供级联全选
- **无 `contract_name`**：`contract_code` 已是分组键，合同名属分组级纯展示冗余。若聚合该字段，等于在「汇总只展示分组键 + 数量 + 价格」的口径外引入一个**非分组键**列（组内若合同名不一致还需额外定合并规则）。前端按 `contract_code` 映射合同类型字典（与 `asset_type_recordcode` 同构）即可。

⚠️ **`data.count` 是分页总记录数（分组总数），与 `data.results[i].asset_count`（组内资产条数）不是同一概念**，命名已刻意区分。

#### 2.4b.2 明细端点 `GET /api/v1/assets/group_children/`

| 参数 | 类型 | 说明 |
|:---|:---|:---|
| `group_key` | str | **必填**，`grouped` 原样回传。后端 `json.loads` 解析四元组后转精确过滤 |
| `asset_current_status` / `asset_type_recordcode` / `asset_storage_recordcode` | str | **必须与 grouped 相同的筛选** |
| `asset_code` / `asset_name` / `asset_brand` / `asset_specification` / `asset_contract_name` | str | 模糊过滤，**必须与 grouped 相同的筛选**（C 新增，5 键） |
| `asset_type_category` | str | 分类精确过滤，**必须与 grouped 相同的筛选**（C 新增） |
| `page` / `page_size` | int | 组内分页（默认 20 / 上限 100） |

> **本端点不声明 `contract_code` / `no_contract`**（R-1 已取消）：合同由 `group_key` 首元素表达，null 亦无损。若保留这两个参数，前端一旦沿用 v2.2 习惯误传，就会与 `group_key` 做交集导致整组展开失败。实测：多传 `contract_code=C002`（与 `group_key` 的 `C001` 矛盾）时后端**忽略**该参数并按 `group_key` 返回，结果正确（`test_contract_code_and_no_contract_are_not_filter_params`）。
>
> **C 批要求两端筛选键集逐字相等（契约不变量 I-1）**：本端点除 `group_key` 外的全部筛选键 = 汇总端点键集 − {`contract_code`, `no_contract`} = **9 个**。漏扩任一端即漂移：前端把 active 筛选原样透传时，某一端少认一个键就会「多返回数据」，而 `data.count` 仍可能与汇总数巧合相等直到某组边界出现。该等式由 `test_pass_through_filters_match_summary_endpoint`（键集）+ `test_i1_holds_when_c_batch_filters_active`（全链路 I-1）双向钉住。

**响应（200）**：`AssetDetailSerializer` 分页（含 `harddisk_sns`），信封同 §2.4b.1。

> **明细排序固定为 `recordcode` 升序，不接受客户端指定**。原因：`group_key` 的四个维度对组内所有资产**完全相同**，故不存在有意义的组内排序维度；而组内翻页用 LIMIT/OFFSET，排序键若非唯一（哪怕只按价格排序），同一 OFFSET 在不同请求下顺序不定，前端「加载更多」必然出现重复项与漏项。`recordcode` 全局唯一（`core/models.py:93`）⇒ OFFSET 分页是全序。

**错误契约**：`group_key` 形状非法（非法 JSON / 非数组 / 长度 ≠ 4 / `asset_name` 为 null / 元素非字符串）一律 **400**，不回退为空集。理由：若把非法 `group_key` 当作「不过滤」，会退化成返回整个筛选集（明细数远大于汇总数），错答方向是**多给数据**，比 400 危险得多。形状合法但无命中的 `group_key` 返回 **200 + `count: 0`**（正常业务结果，如资产被并发删除），二者刻意区分。页码越界返回 **404**（DRF `NotFound`），前端据此停止「加载更多」。

**契约不变量 I-1**：同一次筛选下，`group_children` 返回总数 **===** 对应组的 `grouped.asset_count`。前端展开 / 组内翻页时**必须原样透传当前 active 筛选参数与 `group_key`**，否则汇总数与明细数会漂移。

> I-1 不是靠约定保证的，而是靠实现：明细端点与汇总端点在 Selector 层复用**同一个** `_scoped_queryset`（同筛选集 + 同 RBAC 范围）与**同一个** `_build_group_q`（null-safe 组键过滤），故两端口径无法各自漂移。

> **契约 bug 修正（R-1）**：本端点用 `group_key` **单参直传**，而非为每个维度设独立参数。理由：`asset_brand` / `asset_specification` 为 null 时无法用 `str` 类型参数表达；`group_key` 经 JSON 往返**无损**，null 元素得以保留，无需为「null 表达」另造参数或开 `no_contract` 特例。

> **排序规则**：`asset_count` **降序（主键）** → 合同号升序（**null 置末**）→ `asset_name` → `asset_specification` → `asset_brand`，保证翻页稳定。
>
> ⚠️ 「合同 null 置末」是**次级排序键**：仅在 `asset_count` **相等**的分组之间生效。故无合同哨兵组**不一定排在最后** —— 当其 `asset_count` 高于其他分组时，仍按数量降序排在前面。此点前端不得假设哨兵组恒在末位。

> **`api-schema-baseline.json`**：本节端点尚未实现，基线文件待实现落地后在阶段 4 重导出（提前重导出产出与现状字节一致，无意义）。

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
| POST | `/auth/change-password/` | 修改密码（规划占位，未实现；实际改密走 `PUT /auth/profile/`，携带 `old_password` + `password`） | ChangePasswordSerializer | - |
| GET | `/auth/profile/` | 获取当前用户 | - | AuthUserDetailSerializer |
| PUT | `/auth/profile/` | 更新个人信息/修改密码（改密须提供 `old_password` 校验原密码，成功后吊销该用户全部 refresh token） | UserProfileUpdateSerializer | AuthUserDetailSerializer |
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
| V2.8 | 2026-10-03 | 新增 §2.4b 资产分组查询（`GET /assets/grouped/`、`GET /assets/group_children/`）：汇总/明细端点参数与响应契约、`asset_count`、`price_display`、`group_key` 单参直传（R-1）、契约不变量 I-1、排序规则（合同 null 置末为**次键**，仅数量相等时生效）；`api-schema-baseline.json` 待实现落地后重导出 |
| V2.9 | 2026-10-04 | **明细端点 B4 落地**：§2.4b.2 补「不声明 `contract_code`/`no_contract`（R-1 取消，实测忽略旧参数不影响结果）」、明细排序固定 `recordcode` 升序及其理由（组内维度恒同 + OFFSET 需全序）、**错误契约**（`group_key` 形状非法 400 / 形状合法无命中 200+count 0 / 页码越界 404，三者刻意区分）；§2.4b.1 收口注记更新，并新增**整合期断点**警示：B5 未落地前汇总端点不输出 `group_key`，前端无法构造展开参数，B5 是两端的必需桥梁 |
| V2.10 | 2026-10-04 | **汇总端点 B5 落地，§2.4b 契约全部实现**：汇总行由 6 字段扩为 **8 字段**（新增 `group_key` / `price_display`），§2.4b.1 示例即实际响应，B4 的整合期断点消除；补 `price_min`/`price_max` 为内部字段不外泄的理由、`group_key` null 位须写 JSON `null`（空串/字符串 `"null"` 均错）与中文不转义约定。⚠️ 本次为**新增字段**（向后兼容），但**已存在的** `AssetGroupSummary` 若被前端按固定字段集消费需同步（前端 F1/F2 尚未开工，无存量消费方） |
| V2.11 | 2026-10-05 | **筛选键 C 批落地（9 键）**：§2.4b.1 参数表由 6 键扩为 **12 键**（新增 `asset_code` / `asset_name` / `asset_brand` / `asset_specification` / `asset_contract_name` 五个**模糊**键 + `asset_type_category` 分类**精确**键）；§2.4b.2 同步扩为 **9 个非组键筛选**，并写明「两端键集逐字相等」为 I-1 的硬要求。补三条口径：① 筛选链与主列表 `combine_search` 复用同一对实现（`_build_fuzzy_q` / `_apply_exact_filters`），同输入必然同命中集；② 空串视为未传；③ 分类无类型时**返回空集而非全表**。⚠️ 明确 **C 扩的是筛选维度、不是响应字段**——`asset_code` / `asset_contract_name` / `asset_type_category` 仅作筛选，响应字段集仍为 8 项（`asset_name` / `asset_brand` / `asset_specification` 因早已是分组键字段而"看似重复"，实为一键两用）。⚠️ 契约变更属跨端：前端分组 UI（B 批）**必须在本版本之后**才可启用 9 键，否则新键被 DRF 静默丢弃、筛选无声失效 |