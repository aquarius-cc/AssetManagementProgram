# BasicAssetDetails 功能补全执行方案

**版本**: v1.0
**日期**: 2026-07-10
**策略**: 按依赖层级分阶段执行（方案 A）

---

## 0. 现状分析

### 0.1 当前 BasicAssetDetails.vue 操作按钮

| 按钮 | 功能 |
|:-----|:-----|
| 编辑 | 跳转 AssetForm 编辑页 |
| 导出 | 导出 Excel |
| 返回 | history.go(-1) |

### 0.2 后端完整资产状态枚举（8 种）

| 枚举值 | 中文 | 前端 `AssetCurrentStatus` 是否定义 | 前端 `assetCurrentStatusMapping` 是否定义 |
|:-------|:-----|:----------------------------------:|:----------------------------------------:|
| `in_store` | 在库 | ✅ | ✅ |
| `in_use` | 在用 | ✅ | ✅ |
| `recycled_pending` | 已回收待发放 | ✅ | ✅ |
| `broken` | 已损坏 | ❌ **缺失** | ❌ **缺失** |
| `repairing` | 维修中 | ❌ **缺失** | ❌ **缺失** |
| `lost` | 已遗失 | ❌ **缺失** | ❌ **缺失** |
| `damaged` | 待报废 | ✅ | ✅ |
| `scrapped` | 已报废 | ✅ | ✅ |

### 0.3 缺失功能清单

| # | 功能 | 对应 AC | 当前状态 |
|:--|:-----|:--------|:---------|
| 1 | 标记损坏 | AC-35, AC-36 | 后端 `mark_broken` ✅ / 前端 API ❌ / 页面 ❌ / 按钮 ❌ |
| 2 | 标记遗失 | AC-37 | 后端 `mark_lost` ✅ / 前端 API ✅ / 页面 ✅ / 按钮 ❌ |
| 3 | 找回遗失资产 | AC-38 | 后端 `found_and_return` ✅ / 前端 API ✅ / 页面 ❌ / 按钮 ❌ |
| 4 | 送修 | AC-39 | 后端 `repair` ✅ / 前端 API ✅ / 页面 ✅ / 按钮 ❌ |
| 5 | 维修完成 | AC-40 | 后端通过 repair 更新 ✅ / 前端 API ✅ / 页面 ❌ / 按钮 ❌ |
| 6 | 维修失败 | AC-41 | 后端通过 repair 更新 ✅ / 前端 API ✅ / 页面 ❌ / 按钮 ❌ |
| 7 | 提交报废申请 | AC-42 | 后端 `change_status` ✅ / 前端 API ✅ / 页面 ✅ / 按钮 ❌ |
| 8 | 查看状态日志 | AC-61 | 后端 `timeline` ✅ / 前端 API ✅ / 页面 ✅ / 按钮 ❌ |

---

## 1. Layer 1：API 层与类型补全

### 1.1 修改文件清单

| # | 文件路径 | 操作 | 改动内容 |
|:--|:---------|:-----|:---------|
| 1 | `src/types/asset.ts` | 修改 | `AssetCurrentStatus` 枚举补充 `BROKEN`, `REPAIRING`, `LOST` |
| 2 | `src/utils/Format.ts` | 修改 | `assetCurrentStatusMapping` 补充 3 条映射 |
| 3 | `src/api/asset.ts` | 修改 | 新增 `markAssetAsBroken` 方法 |
| 4 | `src/api/lostAsset.ts` | 修改 | 修正 `foundAsset` 的 URL 为 `found_and_return` |
| 5 | `src/api/repairAsset.ts` | 修改 | 新增 `repairDone` 和 `repairFailed` 方法（如果不存在） |

### 1.2 详细改动

#### 1.2.1 `src/types/asset.ts` — 补充枚举

```typescript
// 现有
export enum AssetCurrentStatus {
  IN_STORE = 'in_store',
  RECYCLED_PENDING = 'recycled_pending',
  IN_USE = 'in_use',
  DAMAGED = 'damaged',
  SCRAPPED = 'scrapped',
}

// 改为
export enum AssetCurrentStatus {
  IN_STORE = 'in_store',
  RECYCLED_PENDING = 'recycled_pending',
  IN_USE = 'in_use',
  BROKEN = 'broken',
  REPAIRING = 'repairing',
  LOST = 'lost',
  DAMAGED = 'damaged',
  SCRAPPED = 'scrapped',
}
```

同步更新 `ASSET_STATUS_DISPLAY_MAPPING` 补充 3 条：
```typescript
broken: '已损坏',
repairing: '维修中',
lost: '已遗失',
```

#### 1.2.2 `src/utils/Format.ts` — 补充状态映射

```typescript
const assetCurrentStatusMapping: Record<string, string> = {
  in_store: '在库',
  recycled_pending: '已回收待发放',
  in_use: '在用',
  broken: '已损坏',      // 新增
  repairing: '维修中',   // 新增
  lost: '已遗失',        // 新增
  damaged: '待报废',
  scrapped: '已报废',
}
```

#### 1.2.3 `src/api/asset.ts` — 新增 markAssetAsBroken

```typescript
/**
 * 标记资产为已损坏
 * POST /api/assets/assets/{asset_code}/mark_broken/
 * 对应后端 AssetViewSet.mark_broken action
 */
markAssetAsBroken: (asset_code: string, data: {
  broken_reason?: string
  broken_description?: string
}): Promise<Asset> => {
  return unwrapResponse(request.post<Asset>(
    `/assets/assets/${asset_code}/mark_broken/`,
    data,
  ))
},
```

#### 1.2.4 `src/api/lostAsset.ts` — 修正 foundAsset URL

```typescript
// 现有（URL 错误）
foundAsset: (asset_code: string): Promise<LostAssetExtended> => {
  return unwrapResponse(request.post<LostAssetExtended>(
    `/assets/assets/${asset_code}/found/`,  // ❌ 后端实际路径是 found_and_return
    data,
  ))
},

// 修正为
foundAsset: (asset_code: string, data: {
  found_location?: string
  found_description?: string
}): Promise<LostAssetExtended> => {
  return unwrapResponse(request.post<LostAssetExtended>(
    `/assets/assets/${asset_code}/found_and_return/`,
    data,
  ))
},
```

#### 1.2.5 `src/api/repairAsset.ts` — 确认 repairDone / repairFailed

经检查，现有 `repairDone` 和 `repairFailed` 已存在，URL 分别为：
- `POST /assets/assets/{asset_code}/repair-done/`
- `POST /assets/assets/{asset_code}/repair-failed/`

**但后端 views.py 中未找到这两个 action 的实现**。需要确认后端是否已实现，若未实现则这两个 API 调用会 404。

> **[TODO_AI_CONFIRM]** 后端 `repair-done` 和 `repair-failed` 端点是否存在？经 `grep` 在 `views.py` 中未找到对应 `@action` 定义，仅在 `check_audit_log.py` 的 `state_change_methods` 列表中出现。需确认：
> 1. 后端是否通过其他方式（如 RepairAssetViewSet 的 update/patch）处理维修完成/失败？
> 2. 若后端未实现，前端需新增对应页面还是改为调用通用 `change_status`？

### 1.3 验证方式

```bash
# 类型检查
vue-tsc --noEmit

# Lint 检查
npm run lint
```

**验收标准**: 0 个类型错误，0 个 lint 错误

---

## 2. Layer 2：缺失独立页面（3 个新文件 + 路由补充）

### 2.1 新建文件清单

| # | 文件路径 | 功能 | 参考模板 |
|:--|:---------|:-----|:---------|
| 1 | `src/views/FoundAssetView.vue` | 找回遗失资产 | `LostAssetView.vue`（反向操作） |
| 2 | `src/views/RepairDoneView.vue` | 维修完成 | `RepairAssetView.vue`（增加物理成色选择） |
| 3 | `src/views/RepairFailedView.vue` | 维修失败 | `RepairAssetView.vue`（简化版） |

### 2.2 路由补充

在 `src/router/index.ts` 的独立页面路由区域（`/assets/:code/*`）追加：

```typescript
{
  path: '/assets/:code/found',
  name: 'FoundAsset',
  component: () => import('@/views/FoundAssetView.vue'),
  meta: { title: '找回遗失资产', requiresAuth: true },
},
{
  path: '/assets/:code/repair-done',
  name: 'RepairDoneAsset',
  component: () => import('@/views/RepairDoneView.vue'),
  meta: { title: '维修完成', requiresAuth: true },
},
{
  path: '/assets/:code/repair-failed',
  name: 'RepairFailedAsset',
  component: () => import('@/views/RepairFailedView.vue'),
  meta: { title: '维修失败', requiresAuth: true },
},
```

### 2.3 各页面详细设计

#### 2.3.1 FoundAssetView.vue（找回遗失资产）

**对应验收标准**: AC-38 — 找回遗失资产

**后端接口**: `POST /api/assets/assets/{asset_code}/found_and_return/`

**请求参数**:
| 字段 | 类型 | 必填 | 说明 |
|:-----|:-----|:----:|:-----|
| `found_location` | string | 否 | 找回地点 |
| `found_description` | string | 否 | 找回描述 |

**表单字段**:
| 字段 | 组件 | 校验 |
|:-----|:-----|:-----|
| 找回地点 | `el-input` | 选填 |
| 找回描述 | `el-input textarea` | 选填 |

**页面流程**:
1. `onMounted` 通过 `route.params.code` 获取 asset_code
2. 调用 `assetAPI.getAssetByCode` 获取资产信息并展示
3. 展示资产基本信息（编码、名称、规格、当前状态）
4. 用户填写找回信息后提交
5. 调用 `lostAssetAPI.foundAsset` 提交
6. 成功后跳转首页

**关键代码逻辑**:
```typescript
import { lostAssetAPI } from '@/api/lostAsset'

const handleSubmit = async () => {
  await lostAssetAPI.foundAsset(assetCode.value, {
    found_location: formData.found_location,
    found_description: formData.found_description,
  })
  ElMessage.success('遗失资产已找回并入库')
  router.push('/main')
}
```

#### 2.3.2 RepairDoneView.vue（维修完成）

**对应验收标准**: AC-40 — 维修完成

**后端接口**: `POST /api/assets/assets/{asset_code}/repair-done/`
（若后端未实现，则改为 `PUT /api/assets/repair-assets/{recordcode}/` 更新 repair_status）

**请求参数**:
| 字段 | 类型 | 必填 | 说明 |
|:-----|:-----|:----:|:-----|
| `physical_grade_after` | string | 是 | 维修后物理成色 |
| `repair_description` | string | 否 | 维修完成描述 |

**物理成色枚举**（来自后端 model）:
| 值 | 中文 |
|:---|:-----|
| `excellent` | 优秀 |
| `good` | 良好 |
| `fair` | 一般 |
| `poor` | 较差 |

**表单字段**:
| 字段 | 组件 | 校验 |
|:-----|:-----|:-----|
| 维修后物理成色 | `el-select` | 必填，4 个选项 |
| 维修完成描述 | `el-input textarea` | 选填 |

**页面流程**:
1. 获取资产信息并展示
2. 用户选择维修后物理成色
3. 提交后调用维修完成 API
4. 成功后跳转首页

**需要确认**: 维修完成操作需要关联到具体的维修记录（repair_asset recordcode）。页面可能需要额外参数或自动查找当前进行中的维修记录。

> **[TODO_AI_CONFIRM]** 维修完成 API 的调用方式：是通过 asset_code 直接调用（后端自动查找当前维修中的记录），还是需要传入 repair_asset 的 recordcode？

#### 2.3.3 RepairFailedView.vue（维修失败）

**对应验收标准**: AC-41 — 维修失败

**后端接口**: `POST /api/assets/assets/{asset_code}/repair-failed/`

**请求参数**:
| 字段 | 类型 | 必填 | 说明 |
|:-----|:-----|:----:|:-----|
| `repair_description` | string | 否 | 维修失败描述 |

**表单字段**:
| 字段 | 组件 | 校验 |
|:-----|:-----|:-----|
| 失败原因/描述 | `el-input textarea` | 选填 |

**页面流程**: 与 RepairDoneView 类似，但更简化。

### 2.4 页面通用模式

所有 3 个页面遵循相同模式（参考现有 `LostAssetView.vue`）：

```
┌─────────────────────────────────┐
│  [图标] 资产XXX                 │
├─────────────────────────────────┤
│  资产编码: xxx                  │
│  资产名称: xxx                  │
│  资产规格: xxx                  │
│  当前状态: xxx                  │
├─────────────────────────────────┤
│  表单字段...                    │
├─────────────────────────────────┤
│        [确认]  [取消]           │
└─────────────────────────────────┘
```

### 2.5 验证方式

```bash
# 类型检查
vue-tsc --noEmit

# Lint 检查
npm run lint
```

**验收标准**: 0 个类型错误，0 个 lint 错误，手动访问各页面路由确认渲染正常

---

## 3. Layer 3：BasicAssetDetails 按钮入口

### 3.1 修改文件

| 文件 | 操作 |
|:-----|:-----|
| `src/components/componentsdetails/detils/BasicAssetDetails.vue` | 修改 |

### 3.2 按钮显示逻辑

根据 `assetDetail.asset_current_status` 条件渲染：

```typescript
const canMarkBroken = computed(() =>
  ['in_store', 'in_use'].includes(assetDetail.value?.asset_current_status ?? '')
)

const canMarkLost = computed(() =>
  assetDetail.value?.asset_current_status === 'in_use'
)

const canFound = computed(() =>
  assetDetail.value?.asset_current_status === 'lost'
)

const canRepair = computed(() =>
  assetDetail.value?.asset_current_status === 'broken'
)

const canRepairDone = computed(() =>
  assetDetail.value?.asset_current_status === 'repairing'
)

const canRepairFailed = computed(() =>
  assetDetail.value?.asset_current_status === 'repairing'
)

const canScrap = computed(() =>
  assetDetail.value?.asset_current_status === 'broken'
)
```

### 3.3 模板改动

在现有 `action-buttons` 区域追加条件按钮：

```html
<div class="action-buttons">
  <!-- 现有按钮 -->
  <el-button type="primary" :icon="Edit" @click="handleEdit" size="default">编辑</el-button>
  <el-button type="warning" :icon="Download" @click="handleExportExcel" size="default">导出</el-button>

  <!-- 新增：状态流转操作按钮 -->
  <el-button v-if="canMarkBroken" type="danger" @click="handleMarkBroken">标记损坏</el-button>
  <el-button v-if="canMarkLost" type="danger" @click="handleMarkLost">标记遗失</el-button>
  <el-button v-if="canFound" type="success" @click="handleFound">找回</el-button>
  <el-button v-if="canRepair" type="warning" @click="handleRepair">送修</el-button>
  <el-button v-if="canRepairDone" type="success" @click="handleRepairDone">维修完成</el-button>
  <el-button v-if="canRepairFailed" type="danger" @click="handleRepairFailed">维修失败</el-button>
  <el-button v-if="canScrap" type="danger" @click="handleScrap">报废申请</el-button>

  <!-- 新增：查看日志（始终显示） -->
  <el-button :icon="Timer" @click="handleViewLogs">状态日志</el-button>

  <!-- 现有按钮 -->
  <el-button :icon="Back" @click="handleBack" size="default">返回</el-button>
</div>
```

### 3.4 交互方法

```typescript
// 标记损坏 — 弹窗确认后直接调用 API
const handleMarkBroken = () => {
  ElMessageBox.confirm('确定将该资产标记为已损坏？', '确认操作', { type: 'warning' })
    .then(async () => {
      await assetAPI.markAssetAsBroken(assetDetail.value!.asset_code, {})
      ElMessage.success('资产已标记为损坏')
      refreshDetail() // 刷新详情
    })
    .catch(() => {})
}

// 标记遗失 — 跳转独立页面
const handleMarkLost = () => {
  router.push({ name: 'LostAsset', params: { code: assetDetail.value!.asset_code } })
}

// 找回 — 跳转独立页面
const handleFound = () => {
  router.push({ name: 'FoundAsset', params: { code: assetDetail.value!.asset_code } })
}

// 送修 — 跳转独立页面
const handleRepair = () => {
  router.push({ name: 'RepairAsset', params: { code: assetDetail.value!.asset_code } })
}

// 维修完成 — 跳转独立页面
const handleRepairDone = () => {
  router.push({ name: 'RepairDoneAsset', params: { code: assetDetail.value!.asset_code } })
}

// 维修失败 — 跳转独立页面
const handleRepairFailed = () => {
  router.push({ name: 'RepairFailedAsset', params: { code: assetDetail.value!.asset_code } })
}

// 报废申请 — 跳转独立页面
const handleScrap = () => {
  router.push({ name: 'ScrapAsset', params: { code: assetDetail.value!.asset_code } })
}

// 查看状态日志 — 跳转独立页面
const handleViewLogs = () => {
  router.push({ name: 'AssetLogs', params: { code: assetDetail.value!.asset_code } })
}
```

### 3.5 需新增的 import

```typescript
import { computed } from 'vue'
import { Timer } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { assetAPI } from '@/api/asset'
```

### 3.6 refreshDetail 方法

标记操作后需要刷新资产详情以更新状态按钮：

```typescript
const refreshDetail = async () => {
  const assetCode = assetDetail.value?.asset_code
  if (!assetCode) return
  try {
    const data = await assetStore.getById(assetCode)
    if (data) assetDetail.value = data
  } catch (error) {
    console.error('刷新资产详情失败', error)
  }
}
```

### 3.7 验证方式

```bash
# 类型检查
vue-tsc --noEmit

# Lint 检查
npm run lint
```

**验收标准**: 0 个类型错误，0 个 lint 错误

---

## 4. Layer 4：综合验证

### 4.1 静态检查

```bash
# 类型检查
vue-tsc --noEmit

# Lint 检查
npm run lint
```

### 4.2 手动验证场景

| # | 场景 | 操作 | 预期结果 |
|:--|:-----|:-----|:---------|
| 1 | in_store 资产 | 查看详情 | 显示「标记损坏」按钮 |
| 2 | in_use 资产 | 查看详情 | 显示「标记损坏」「标记遗失」按钮 |
| 3 | broken 资产 | 查看详情 | 显示「送修」「报废申请」按钮 |
| 4 | repairing 资产 | 查看详情 | 显示「维修完成」「维修失败」按钮 |
| 5 | lost 资产 | 查看详情 | 显示「找回」按钮 |
| 6 | damaged 资产 | 查看详情 | 无额外操作按钮 |
| 7 | scrapped 资产 | 查看详情 | 无额外操作按钮 |
| 8 | 任意状态 | 点击「状态日志」 | 跳转 AssetLogs 页面 |
| 9 | in_store 资产 | 点击「标记损坏」 | 弹窗确认 → 标记成功 → 状态刷新为 broken |
| 10 | in_use 资产 | 点击「标记遗失」 | 跳转 LostAssetView → 填写 → 提交成功 |
| 11 | lost 资产 | 点击「找回」 | 跳转 FoundAssetView → 填写 → 提交成功 |
| 12 | broken 资产 | 点击「送修」 | 跳转 RepairAssetView → 填写 → 提交成功 |
| 13 | broken 资产 | 点击「报废申请」 | 跳转 ScrapAssetView → 填写 → 提交成功 |

### 4.3 审计票

```markdown
[审计票-前端 - 必填项]
- 读取规范：已读 AGENTS & Rules
- 组件语法：Setup Script [√]
- 设计令牌：符合 F1-F5 [√]
- 样式隔离：scoped / 未污染全局 [√]
- CT-1[√] CT-3[√] CT-5[√]
- DR-1[√] DR-5[√]
- SC-1[√] SC-3[√]
- 跨端契约：未破坏
- 红线触发：无
- 建议提交：是
```

---

## 5. 文件变更汇总

| 层级 | 文件路径 | 操作 | 预估行数 |
|:-----|:---------|:-----|:---------|
| L1 | `src/types/asset.ts` | 修改 | +8 行 |
| L1 | `src/utils/Format.ts` | 修改 | +3 行 |
| L1 | `src/api/asset.ts` | 修改 | +18 行 |
| L1 | `src/api/lostAsset.ts` | 修改 | +10 行（修正 URL + 补充参数） |
| L2 | `src/views/FoundAssetView.vue` | 新建 | ~130 行 |
| L2 | `src/views/RepairDoneView.vue` | 新建 | ~150 行 |
| L2 | `src/views/RepairFailedView.vue` | 新建 | ~130 行 |
| L2 | `src/router/index.ts` | 修改 | +18 行（3 条路由） |
| L3 | `src/components/.../BasicAssetDetails.vue` | 修改 | +80 行（computed + 按钮 + 方法） |
| **合计** | **9 文件** | **5 修改 + 3 新建** | **~565 行** |

---

## 6. 待确认事项

| # | 问题 | 影响范围 | 需要确认方 |
|:--|:-----|:---------|:-----------|
| 1 | 后端 `repair-done` 和 `repair-failed` 端点是否已实现？grep 未在 views.py 中找到对应 `@action` | Layer 2 维修完成/失败页面 | 后端开发 |
| 2 | 维修完成 API 是否需要传入 `repair_asset_recordcode`，还是后端自动关联当前进行中的维修记录？ | RepairDoneView 表单设计 | 后端开发 |
| 3 | 「标记损坏」按钮点击后是弹窗确认直接调用 API，还是跳转到独立页面填写损坏原因？ | BasicAssetDetails 交互设计 | 产品 |
| 4 | 各操作按钮是否需要按用户角色显隐？（如报废审批仅部门经理可操作） | 按钮权限控制 | 产品 |
| 5 | 找回操作成功后跳转到哪里？首页还是资产详情页？ | 用户体验 | 产品 |
