# 前端字段对齐后端修复方案（已审查修正版）

> 生成时间：2026-07-06
> 审查修正时间：2026-07-06
> 状态：纯方案，未实施
> 原则：前端 TS 类型、枚举、显示映射与后端序列化器输出字段精确匹配
> 审查发现：7 处问题（2 处事实错误 + 5 处遗漏），已全部修正

---

## 修改范围总览

共 14 批次，涉及约 35 个文件（修改 12 个 + 新建 21 个 + 审查补充 2 个）。

| 批次 | 类别 | 文件数 | 优先级 |
|------|------|--------|--------|
| 1 | 枚举值补齐 | 4 | P0 |
| 2 | Asset 模块类型重写 | 3 | P0 |
| 3 | OutAsset 类型 + API 层确认 | 2 | P1 |
| 4 | RecycleAsset 类型重写 | 1 | P0 |
| 5 | DamagedAsset 类型 + 审批对齐 | 2 | P1 |
| 6 | WasteAsset 类型 | 1 | P1 |
| 7 | Contract 类型 | 1 | P1 |
| 8 | Storage / HardDiskSN 微调 | 2 | P2 |
| 9 | V4.0 三个新模块（21 个新文件） | 21 | P0 |
| 10 | RecycleAsset 表单新增字段（需后端配合） | 1 | P0 |
| 11 | 全局显示映射更新 | 4 | P1 |
| 12 | 资产详情页操作按钮（mark_broken/lost/found） | 2 | P0 |
| 13 | AssetSimpleReturn 接口清理 | 1 | P2 |
| 14 | OutAsset API 层字段重命名确认 | 1 | P1 |

---

## 第一批：枚举值补齐

### 1.1 `src/utils/Asset.ts` — AssetCurrentStatus

当前值：IN_STORE, RECYCLED_PENDING, IN_USE, DAMAGED, SCRAPPED

新增：
- `BROKEN = 'broken'`
- `LOST = 'lost'`

ASSET_STATUS_DISPLAY_MAPPING 同步追加 `broken:'已损坏'` `lost:'已遗失'`。

### 1.2 `src/utils/Contract.ts` — ContractSettlementStatus

当前值：PENDING, SETTLED

新增：`SETTLING_UP = 'settling_up'`

### 1.3 `src/utils/Storage.ts` — StorageType

当前值：NEWASSET, RECYCLE, DAMAGED

新增：`BROKEN = 'broken'`

### 1.4 `src/utils/OutAsset.ts` — OutAssetCurrentStatus

当前值：IN_USE, RECYCLED_PENDING, DAMAGED, SCRAPPED

新增：`BROKEN = 'broken'` `LOST = 'lost'`

outassetStatusMapping 同步追加。

---

## 第二批：Asset 模块类型重写

### 2.1 `src/utils/Asset.ts` — Asset 接口

后端 AssetDetailSerializer 输出字段：
```
recordcode, asset_code, asset_name, asset_brand, asset_unit,
asset_purchase_number, asset_specification, asset_purchase_price,
asset_purchase_date, asset_warranty_period, asset_current_status,
asset_description, asset_using_location, asset_entry_date,
asset_type(嵌套), asset_contract(嵌套), asset_storage(嵌套),
asset_entry_person(嵌套), asset_applicant(嵌套), asset_manager(嵌套),
harddisk_sns, is_active, version
```

前端 Asset 接口需调整：
- 删除：asset_type_code, asset_contract_code, asset_storage_code,
  asset_entry_person_jobcode, asset_applicant_jobcode, asset_manager_jobcode
  （后端 Detail 不返回扁平 FK 码）
- 新增：is_active: boolean, version: number

### 2.2 `src/utils/Asset.ts` — AssetListItem 对齐 AssetListSerializer

后端 List 输出：
```
recordcode, asset_code, asset_name, asset_brand, asset_unit,
asset_purchase_number, asset_specification, asset_purchase_price,
asset_purchase_date, asset_warranty_period, asset_current_status,
asset_description, asset_using_location, asset_entry_date,
type_category, asset_type_name, contract_code, contract_name,
storage_code, storage_name, entry_person_name, applicant_name,
manager_name, is_active, version
```

AssetListItem 需修改：
- asset_storage_name → storage_name
- asset_contract_name → contract_name
- asset_applicant_name → applicant_name
- asset_manager_name → manager_name
- 新增 entry_person_name, type_category, is_active, version

### 2.3 `src/components/componentsdetails/detils/BasicAssetDetails.vue`

保修期格式化：`个月` → `年`（后端存年数，不是月数）。

---

## 第三批：OutAsset 类型 + API 层确认

### 3.1 `src/utils/OutAsset.ts`

OutAssetListSerializer 输出：
```
id, recordcode, asset_recordcode, asset_code, asset_name,
asset_specification, asset_brand, outasset_number, outasset_date,
outasset_type, outasset_current_status, outasset_description,
outasset_applicant_name, outasset_manager_name,
outasset_manager_jobcode, outasset_manager_department,
return_date, outasset_previous_status
```

前端 OutAsset 接口需补充：
- asset_brand
- outasset_manager_jobcode
- outasset_manager_department
- outasset_previous_status

OutAssetDetailSerializer 额外输出 outasset_snapshot（JSON），
前端 Detail 接口需声明此字段。

### 3.2 `src/api/asset.ts` — createOutAsset 函数确认

**需检查项**：后端 OutAssetCreateSerializer 接收的 FK 字段名是
`asset_recordcode`（SlugRelatedField），而前端表单传统字段名是
`outasset_code`。API 层的 createOutAsset 函数是否已包含从
`outasset_code` 到 `asset_recordcode` 的字段重命名逻辑？

若已有：在代码注释中明确标注映射来源。
若无：需补充重命名步骤，否则创建请求会因缺少必填字段而失败。

---

## 第四批：RecycleAsset 类型重写

### 4.1 `src/utils/RecycleAsset.ts`

RecycleAssetListSerializer 输出：
```
recordcode, outasset_recordcode, asset_recordcode, asset_code,
asset_name, asset_specification, contract_code, storage_name,
recycle_asset_date, recycle_asset_description,
recycle_person_jobcode, recycle_person_name,
using_person_jobcode, using_person_name,
recycle_asset_number, recycle_type, is_active
```

RecycleAssetCreateSerializer 接收：
```
recordcode(只读), outasset_recordcode(SlugRelatedField),
asset_recordcode(只读自动关联), storage_code(SlugRelatedField),
recycle_asset_date, recycle_asset_description,
recycle_asset_number, recycle_type, is_active
```

前端接口修改：
- recycle_asset_storage_code → storage_name（列表）/ storage_code（创建）
- recycle_asset_recycle_person_jobcode → recycle_person_jobcode
- operator_jobcode → using_person_jobcode
- 新增 asset_code, asset_name, contract_code, recycle_person_name

RecycleDetailSerializer 输出嵌套 asset 对象，
前端需声明嵌套类型。

### 4.2 跨端依赖声明

后端当前 RecycleAssetCreateSerializer 的 fields 列表**不含**
is_broken / is_lost。模型上虽有这两个字段，但序列化器未声明，
前端发送后端会静默丢弃。

若要支持回收时标记损坏/遗失，需先在后端
RecycleAssetCreateSerializer 的 Meta.fields 中添加
`is_broken` 和 `is_lost`。此修改属于后端变更，
应在后端先行完成后再执行第十批（前端表单）。

---

## 第五批：DamagedAsset 类型 + 审批对齐

### 5.1 `src/utils/DamagedAsset.ts`

DamagedAssetCreateSerializer 接收：
```
id(只读), recordcode(只读), asset_recordcode(SlugRelatedField),
damaged_asset_number, damaged_date, damaged_asset_description, is_active
```

DamagedAssetListSerializer 输出：
```
recordcode, asset_recordcode, approval_status, approver,
damaged_date, damaged_asset_number, damaged_asset_description,
is_active, damaged_asset_name, damaged_asset_contract_code,
damaged_asset_contract_name, damaged_asset_storage_code,
damaged_asset_storage_name, damaged_asset_specification
```

前端修改：
- DamagedAssetCreateForm.damaged_asset_code → asset_recordcode
- 删除 damaged_asset_contract_code / damaged_asset_storage_code
  （ListSerializer 中有但 CreateSerializer 不接收写入）
- DamagedAsset 接口补充 version
- lookup 字段 damaged_asset → asset_recordcode

### 5.2 审批序列化器对齐

后端 DamagedAssetAproveSerializer 输出字段与 ListSerializer
基本一致：id, recordcode, asset_recordcode, approval_status,
approver, damaged_date, damaged_asset_number,
damaged_asset_description, is_active, damaged_asset_name,
damaged_asset_contract_code, damaged_asset_contract_name,
damaged_asset_storage_code, damaged_asset_storage_name,
damaged_asset_specification。

前端 DamagedAsset 审批详情页的展示字段需与此对齐，
特别是 approval_status（审批状态下拉选项）和
approver（审批人选择器）。

---

## 第六批：WasteAsset 类型

### 6.1 `src/utils/WasteAsset.ts`

WasteAssetCreateSerializer 接收：
```
id(只读), recordcode(只读), asset_recordcode(SlugRelatedField),
damaged_recordcode(SlugRelatedField), waste_asset_number,
waste_asset_date, waste_asset_description, is_active,
asset_code(只读), asset_name(只读),
waste_asset_contract_code(只读), waste_asset_specification(只读)
```

WasteAssetListSerializer 输出：
```
id, recordcode, asset_recordcode, waste_asset_contract_code,
waste_asset_date, waste_asset_description, asset_code, asset_name,
contract_name, waste_asset_specification, is_active
```

前端修改：
- WasteAssetCreateForm.waste_asset_code → asset_recordcode
- 保留 waste_asset_contract_code（后端接收，不删除）
- 新增 damaged_recordcode
- WasteAsset 接口 waste_asset → asset_recordcode，补充 version

---

## 第七批：Contract 类型

### 7.1 `src/utils/Contract.ts`

ContractCreateSerializer 接收：
```
recordcode(只读), contract_code, contract_name, contract_type,
contract_price, contract_supplier, contract_signing_date,
contract_warranty_period, contract_settledment_status,
contract_settledment_price, contract_paid_count_number,
contract_paid_price, contract_paid_record, is_active
```

ContractUpdateSerializer 额外接收：
```
contract_preliminary_acceptance_date, contract_final_acceptance_date
```

前端修改：
- ContractCreateForm 确认包含 contract_paid_record
- Contract 接口补充 version: number
- 确认拼写 contract_settledment_status（非 contract_settlment_status）

---

## 第八批：Storage / HardDiskSN 微调

### 8.1 `src/utils/Storage.ts`

后端 StorageSerializer 输出 recordcode, storage_code, storage_name,
storage_address, storage_type, storage_description, is_active。

前端 Storage 接口有 create_time/update_time/is_delete，
后端不返回。确认是否使用了不同序列化器。
若确实不返回则从 TS 接口中移除或标记为可选。

### 8.2 `src/utils/HardDiskSN.ts`

后端 HardDiskSNSerializer 输出 asset_recordcode，
前端用 harddisksn_asset。统一命名。

---

## 第九批：V4.0 三个新模块（21 个新文件）

**前置条件**：后端 urls.py 已注册 broken-assets/lost-assets/
found-assets 路由。创建前需确认路由可达。

### BrokenAsset（7 个文件）

类型定义 `utils/BrokenAsset.ts`：
接口字段匹配 BrokenAssetListSerializer — recordcode,
asset_recordcode, broken_date, broken_reason,
broken_description, operator_employee_name, asset_code,
asset_name, asset_specification, is_active。

Create 接收 asset_recordcode, broken_date,
broken_reason, broken_description。

API `api/brokenAsset.ts`：GET 列表, POST 创建,
GET 详情, PUT/PATCH 更新, DELETE 删除。

Store `stores/brokenAssetStore.ts`：idKey = 'recordcode'。

视图文件路径：`src/components/componentsdetails/`
- BrokenAssetDetails.vue（列表页，参照 DamagedAssetDetails.vue）
- BrokenAssetForm.vue（创建/编辑表单）
- BrokenAssetBasicDetails.vue（详情展示）

路由路径：`/main/broken-assets`、`/main/broken-assets/add`、
`/main/broken-assets/:recordcode`

侧边栏：资产管理分组下追加"已损坏资产"菜单项。

### LostAsset（7 个文件）

类型定义匹配 LostAssetListSerializer — recordcode,
asset_recordcode, lost_date, lost_reason,
last_known_location, lost_description,
operator_employee_name, asset_code, asset_name, is_active。

Create 接收 asset_recordcode, lost_date, lost_reason,
last_known_location, lost_description。

路由路径：`/main/lost-assets`、`/main/lost-assets/add`、
`/main/lost-assets/:recordcode`。

侧边栏追加"已遗失资产"菜单项。

### FoundAsset（7 个文件）

类型定义匹配 FoundAssetListSerializer — recordcode,
asset_recordcode, lost_asset_recordcode, found_date,
found_location, found_description, operator_employee_name,
asset_code, asset_name, is_active。

注意双 FK：asset_recordcode + lost_asset_recordcode。

路由路径：`/main/found-assets`、`/main/found-assets/add`、
`/main/found-assets/:recordcode`。

侧边栏追加"资产找回"菜单项。

---

## 第十批：RecycleAsset 表单新增字段

**前置条件**：后端 RecycleAssetCreateSerializer 需先添加
is_broken 和 is_lost 到 Meta.fields（见第四批跨端依赖声明）。

`src/components/componentsdetails/detils/RecycleAssetForm.vue`

新增两个互斥复选框：
- is_broken（是否损坏回收）
- is_lost（是否遗失回收）

互斥逻辑：勾选其中一个时自动取消另一个。

若后端尚未修改序列化器，前端先加 UI 控件但提交时暂不
发送这两个字段（避免被静默丢弃造成用户困惑），
待后端就绪后开启发送。

---

## 第十一批：全局状态映射更新

需在以下 4 处追加 broken/lost 状态的中文映射和标签颜色：

1. `src/utils/Format.ts` — assetCurrentStatusMapping
2. `src/components/componentsdetails/AssetContentDetails.vue`
   — 列表筛选下拉选项 + 状态列标签
3. `src/components/componentsdetails/detils/BasicAssetDetails.vue`
   — 详情页状态标签
4. `src/composables/useAssetInfoCards.ts`
   — 信息卡片状态字段

---

## 第十二批：资产详情页操作按钮

### 12.1 `src/api/asset.ts` — 新增三个 API 调用函数

```
markBroken(assetCode, data: {broken_reason, broken_description})
markLost(assetCode, data: {lost_reason, last_known_location, lost_description})
foundAndReturn(assetCode, data: {found_location, found_description})
```

对应后端端点：
- POST /api/assets/assets/{asset_code}/mark_broken/
- POST /api/assets/assets/{asset_code}/mark_lost/
- POST /api/assets/assets/{asset_code}/found_and_return/

### 12.2 资产详情页操作入口

`src/components/componentsdetails/detils/BasicAssetDetails.vue`

在资产详情页的操作按钮区域，根据资产当前状态动态显示：
- 当 asset_current_status 为 in_store/in_use/recycled_pending 时：
  显示"标记损坏"和"标记遗失"按钮
- 当 asset_current_status 为 lost 时：
  显示"找回入库"按钮

点击后弹出对话框收集参数，调用对应 API，
成功后刷新详情页数据。

---

## 第十三批：AssetSimpleReturn 接口清理

### 13.1 `src/utils/Asset.ts` — AssetSimpleReturn

当前此接口包含 13 个字段（return_asset_category,
return_asset_type_code, return_asset_type_name,
return_contract_code, return_contract_name,
return_storage_code, return_storage_name 等），
与后端任何已知序列化器均不匹配。

处理策略：
- 在接口定义上方添加注释标注 `@deprecated — 待确认数据来源`
- 若全局搜索发现仅在 search_available 相关逻辑中使用，
  保留但标注为遗留接口
- 若完全无引用，从文件中移除

---

## 第十四批：OutAsset API 层字段重命名确认

### 14.1 `src/api/asset.ts` 或 `src/api/outAsset.ts`

需确认 createOutAsset 函数的请求构建逻辑：

后端 OutAssetCreateSerializer 接收的 FK 字段是
`asset_recordcode`（SlugRelatedField，接收 recordcode 值），
前端表单使用 `outasset_code` 作为字段名。

若 API 层未做重命名映射，创建出库记录会因
asset_recordcode 字段缺失而返回 400 错误。

确认后在函数注释中标注映射关系，
若缺失则补充 `outasset_code → asset_recordcode` 的重命名。

---

## 审查修正记录

| 原方案位置 | 问题类型 | 修正内容 |
|---|---|---|
| 第四批 RecycleAsset | 事实错误 | is_broken/is_lost 后端序列化器未声明，标注为跨端依赖 |
| 第六批 WasteAsset | 事实错误 | waste_asset_contract_code 后端接收，不删除 |
| 原无 | 遗漏 | 新增第十二批：mark_broken/lost/found 操作按钮和 API |
| 原无 | 遗漏 | 新增第十三批：AssetSimpleReturn 接口清理 |
| 原无 | 遗漏 | 新增第十四批：OutAsset API 层字段重命名确认 |
| 第五批 | 遗漏 | 补充 DamagedAssetAproveSerializer 审批对齐 |
| 第九批 | 不清晰 | 补充路由路径和侧边栏菜单的具体值 |
| 第十批 | 依赖缺失 | 标注需后端先修改 RecycleAssetCreateSerializer |
