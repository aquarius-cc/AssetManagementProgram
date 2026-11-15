
---

### 📄 文档 5：前端业务规范 `/Rules_Fiels/frontend-business-rules.md` (v1.8)

# 前端业务规范与设计思路 (Frontend Business Rules)
> 版本：v1.8 | 最后更新：2026-11-15
> 适用范围：Vue 3.5 + TypeScript 6.0 + Element Plus 2.10 + Vite

## 一、设计思路（统一与效率）

| 原则 | 说明 |
|:---|:---|
| **设计令牌驱动** | 所有颜色、间距、圆角来源于预定义 Tokens，杜绝视觉碎片化，保证暗色模式无缝切换。 |
| **组合式优于选项式** | 强制 `<script setup>` + Composables，便于逻辑复用与类型推导。 |
| **单向数据流** | 组件不直接修改 Props，通过 Emits 传递事件；API 数据统一由 Pinia 管理。 |
| **样式封装隔离** | 组件样式必须 `scoped`，覆盖 UI 库样式集中处理，防止样式污染。 |

> **测试联动**：本章节所有 F1-F15 规范均有对应的测试用例要求，详见 `frontend-testing-rules.md` T8-T15。

## 二、硬性业务规范（F1-F15）

| ID | 规范项 | 约束内容 | 违规补救 |
|:---|:---|:---|:---|
| F1 | **设计令牌 - 主色** | 品牌主色固定为 `#2B5FD7`，**禁止**使用其他蓝色 | 替换为 `#2B5FD7` |
| F2 | **设计令牌 - 功能色** | 成功 `#52C41A`、警告 `#FAAD14`、危险 `#FF4D4F`、信息 `#1677FF` | 替换标准色 |
| F3 | **设计令牌 - 圆角** | 按钮/卡片 `8px`；标签/输入框 `4px`，**禁止**其他值 | 统一为 4/8px |
| F4 | **设计令牌 - 间距** | 使用 **4px 基数** (4,8,12,16,24,32,48)，**禁止**非 4 倍数 | 调整为 4 倍数 |
| F5 | **设计令牌 - 字体** | 主内容 `14px`，标题 `16px`/`20px`，字体栈系统默认 | 统一字号与栈 |
| F6 | **Vue 组件语法** | **强制** `<script setup lang="ts">`，**禁止** Options API | 重构为组合式 |
| F7 | **组件命名** | 文件用 **PascalCase** (如 `AssetTable.vue`)，页面放 `/views` | 重命名并移动 |
| F8 | **Props 定义** | 必须使用 `defineProps<T>()` + TypeScript 接口校验 | 补充类型 |
| F9 | **Emits 定义** | 必须使用 `defineEmits<{ (e: 'update', v: string): void }>()` | 补充类型声明 |
| F10 | **Pinia Store** | **强制** Setup Store 语法 (`defineStore('id', () => {})`) | 重构语法 |
| F11 | **API 调用位置** | 异步调用**必须**在 Store/Composables，**禁止**组件内直接请求 | 抽取逻辑 |
| F12 | **样式作用域** | 组件样式**必须**加 `scoped`，**禁止**组件内 `:deep()` 随意覆盖全局变量 | 移至全局变量文件 |
| F13 | **暗色模式** | 必须使用 `useDark` + CSS 变量驱动，**禁止**写死 `#fff`/`#000` | 改用 useDark |
| F14 | **TypeScript 严格** | `tsconfig.json` **必须**开启 `strict: true` | 开启严格模式 |
| F15 | **类型定义位置** | 接口/类型统一放 `/src/types` (如 `asset.d.ts`)，**禁止**组件内定义全局接口 | 移至 `/src/types` |

## 三、暗色模式实施标准
- **切换机制**：在 `App.vue` 中使用 `useDark` 监听系统偏好或手动切换，在 `<html>` 标签上添加/移除 `dark` class。
- **变量映射**：所有颜色必须通过 CSS 变量（如 `var(--el-color-primary)`）引用，Element Plus 的暗色变量会自动根据 `dark` class 切换。
- **自定义变量**：项目自定义颜色（如 F1-F2）必须在 `src/styles/variables.css` 中同时定义亮色和暗色两套值。
- **滚动条灰阶（批次 4 / M-24）**：`--scrollbar-track-bg` / `--scrollbar-thumb-bg` / `--scrollbar-thumb-hover-bg` 三个自定义色值统一在 `src/styles/variables.css` 的 `:root`（亮）与 `html.dark`（暗）各定义一次；`global-scroll.scss` 只保留尺寸与消费点，禁止再写字面量。值变更须同步 `src/styles/__tests__/scrollbarTokens.spec.ts` 的等值断言。

### 3.1 图表 palette 派生色豁免登记（M-42）

F1-F2 四色令牌仍是**业务语义色唯一来源**；图表 palette 派生色仅在数据可视化域有效，经设计确认豁免登记如下（5 类 13 个，2026-11-10 复证）：

| 类别 | 位置 | 值 | 口径 |
|:--|:--|:--|:--|
| 饼图扩展色（PIE_EXTRA） | `useChartTheme.ts:47` | `#8B5CF6` / `#6B7280` | 第 5/6 扇区区分色，非业务语义色 |
| tooltip 背景 | `useChartTheme.ts:81` | `rgba(29,30,31,0.95)` / `rgba(255,255,255,0.95)` | 亮/暗浮层透明度层 |
| 图表分割线 | `useChartTheme.ts:83` | `#1d1e1f` / `#ffffff` | 与 `--card-background` / `--el-bg-color-overlay` 暗色值同形 |
| 面积渐变 | `useChartTheme.ts:85-86` | 4 个 rgba，亮 = 品牌主色 RGB（43,95,215）/ 暗 = 同色相提亮主色 RGB（85,127,223），alpha 0.25/0.02 | 主色透明度派生；M-07 后 RGB 随 §3.3 色阶表同步（唯一事实源），回归锚 `useChartTheme.spec.ts:64-65,74-75` 与 `primaryTokens.spec.ts` E-6 |
| 状态散点色 | `statusMapping.ts:326,329,330` | `#13C2C2` / `#F759AB` / `#FA8C16` | 8 态需 8 个可区分色，F1-F2 四色不够 |

**防扩散条款**：① 每张图亮/暗两套值必须成对，`useChartTheme.spec.ts:60-76` 与 `dashboard.spec.ts:37-46` 的等值断言是唯一回归锚，改值须同步；② **禁止**在组件/页面内新增裸 hex，新增派生色必须走子引擎 §4.2 `[PATCH-FE]` 审批并补等值断言；③ `useChartTheme.ts` FALLBACK 8 个值（4 个为 F1-F2 令牌等值回退、4 个灰阶回退）按 K3 裁决属 `var()` 缺失回退的合规形态，不计硬违规；④ `statusMapping.ts` 为纯 TS 无 DOM，保留常量形态（收编 variables.css 需令牌镜像等值断言，另行立项）。

### 3.2 业务日期固定渲染口径（M-15）

**产品口径（D1-A 拍板，2026-11-10）**：业务时刻统一按 `Asia/Shanghai`（东八区）渲染，与后端 `TIME_ZONE` 对齐，不随浏览器时区漂移。实现为双入口：`Format.ts::toBusinessDateTimeParts`（绝对时刻 → 东八区年月日时分秒，`formatDate` / `formatDateTime*` / `formatRelativeTime` / `todayLocalISO` 唯一来源）与 `toLocalDateString`（本地日历日期，仅限无时刻语义的调用方：`DashboardAssetTrend.vue`、`readExcelFile.ts`、`parseExcelDate`）。跨时区回归锚：`Format.spec.ts` 4 时区 `describe.each` + `todayLocalISO` 鉴别用例。**后端 ISO 8601 +08:00 序列化契约不变**（跨端契约 §3 零改动）。

### 3.3 主色色阶单一真源（M-07，2026-11-15）

**单一真源（D7=B）**：主色令牌族（亮/暗成对）仅在 `src/styles/variables.css` 定义一次——亮值 `:root`、暗值 `html.dark`；`src/styles/dark.css` 仅保留 variables.css 未覆盖的 `--el-color-*`（功能四色 + `--el-color-primary` 映射），**零 rgb 字面量**。构建期静态 hex（D2=B），无运行时生成、无任意换肤（D4=B：`app.ts::setPrimaryColor` 无参化，收敛品牌色并清旧 `primaryColor` 键与旧内联 `--el-color-primary`）。

**色阶（8 档，构建期静态 hex；D1=B 同色相提亮单列登记）**：算法 = F1 品牌 `#2B5FD7` 与白/黑按档混合；暗色基准 D0 = mix(#2B5FD7, #fff, 0.2)，暗色各档 = D0 与 `#141414` 按档混合。

| 档 | 亮（:root） | 暗（html.dark） |
|:---|:---|:---|
| primary | `#2b5fd7` | `#557fdf`（D0） |
| interactive（TI/DI，r=0.08 定稿） | `#3c6cda` | `#6389e2` |
| light-3 | `#6b8fe3` | `#425fa2` |
| light-5 | `#95afeb` | `#344a7a` |
| light-7 | `#bfcff3` | `#283451` |
| light-8 | `#d5dff7` | `#21293d` |
| light-9 | `#eaeffb` | `#1a1f28` |
| dark-2 | `#224cac` | `#7799e5` |

**双 dark token 保留（登记，非双源分裂）**：暗 `--color-primary` = `#557fdf`（D0 提亮主色，主视觉）与暗 `--color-primary-dark` = `#2b5fd7`（品牌锚，暗色高对比场景如数量胶囊 `--el-tag-bg-color`）并存，二者为色阶中不同档位的独立 token，是单一真源原则的唯一例外。

**EP 桥**：`--el-color-primary` / `--el-color-primary-rgb` 与交互态 6 档（light-3/5/7/8/9、dark-2）全部 var() 桥接自定义色阶（亮 `:root` + 暗 `html.dark` 成对），EP 默认蓝族值清零。

**对比度口径（D6=B：对比度 + 等值断言）**：交互档 r=0.08 定稿依据为实测硬门槛——分页 active（底=TI/DI、字=card-background）4.83/4.94 ✓、focus 边框（TI/DI vs 输入底色）4.83/5.45 ✓（非文本 3:1 门槛）。**结构性遗留（无达标承诺）**：分页 hover 与登录渐变浅端在任何候选 r 下（含 r→0）结构上无法同时达 4.5:1（hover 上限≈3.5:1、登录浅端白字≈2.19:1）；换值较 EP 旧值单调改善（亮 hover 2.83→4.19、登录浅端 1.86→4.83），登记活账本 C 区观察项（建议未来以「深一档文字或加深 hover 底色」立项，属设计决策），设计签字须确认接受该现状。

**回归锚**：`src/styles/__tests__/primaryTokens.spec.ts`（13 例：真源解析等值 + stripComments 零正则 fail-closed）；`useChartTheme.spec.ts` E-6（面积渐变 RGB = 色阶品牌 RGB）；运行时直证 `docs/compose/reports/batch4/walkthrough/walkthrough.cjs`（12 页明暗 206/206）。改值必须同步 `docs/compose/reports/batch4/primary-scale-table.md` 色阶表与上述断言锚。

**防扩散条款**：① 主色档位新增/变更仅限 variables.css 单点，组件/scss 禁止写主色 hex；② 新图表派生色走 §3.1 豁免登记 + 等值断言；③ SCSS 编译期变量 `$primary-color`（common-forms.scss）仅作 `var(--x, $var)` 回退字面量，不构成第二真源（C-9 口径）。

## 四、前端代码复用与量化规范（DRY 落地）

> 本细则对应宪法级规则 DR-2、DR-4、DR-5、DR-6，所有前端代码必须遵守。

| ID | 规范项 | 约束内容 | 违规补救 |
|:---|:---|:---|:---|
| FR-1 | **组件原子化拆分** | 同一 UI 模式（如带搜索的表格、弹窗表单）在 2 个及以上页面出现时，**必须**封装为公共组件，放置于 `/src/components`。**禁止**在各页面内重复编写相同模板。 | 提取为公共组件，替换所有引用 |
| FR-2 | **组合式函数复用逻辑** | 相同的响应式逻辑（如表单校验、分页加载）在 2 个及以上组件中出现时，**必须**抽取为 Composables（`/src/composables`）。**禁止**在各组件内重复写 `ref`/`watch`/`onMounted` 组合。 | 抽取为 Composable，替换引用 |
| FR-3 | **API 请求收敛至 Store/API 层** | 同一 API 端点（如 `/api/assets/`）的请求**必须**在 `src/api/asset.ts` 中仅定义一次，**禁止**在多个组件或 Store 中重复定义相同路径和方法。 | 统一在 `api/` 定义，各 Store 导入调用 |
| FR-4 | **工具函数统一存放** | 日期格式化、数值精度处理、文件下载等工具函数，**必须**放置在 `/src/utils` 下按模块拆分（如 `format.ts`）。**禁止**在组件内临时编写重复的工具代码。 | 迁移至 `/src/utils`，全局导入 |
| FR-5 | **组件模板/逻辑行数** | 单个 `.vue` 文件的 `<template>` + `<script setup>` **总行数不得超过 500 行**（不含空行和注释）。超过时，必须将子模板拆分为独立组件，或将逻辑抽离到 Composables。 | 拆分组件/抽离逻辑 |
| FR-6 | **Composable 函数规模** | 单个 Composable 函数（`use*.ts`）**不得超过 200 行**（不含空行和注释，逻辑行 = 物理行 − 空行 − 整行注释（行注释 `//` 与块注释 `/* */` 起止行），行内/行尾注释计入代码行；计数语义与 BR-4 `logical_line_count` 对齐）。超过时，必须按职责拆分为两个独立的 Composables。计数最小实现为 `scripts/check_frontend_invariants.py`（`--print` 为权威数值来源）。 | 拆分 Composable |
| FR-7 | **条件与循环嵌套深度** | Vue 模板中的 `v-if`/`v-for` **嵌套不得超过 3 层**（如 `v-if` > `v-for` > `v-if` 为合法，再内嵌第 4 层即违规）。须通过引入计算属性或子组件展平。 | 重构模板结构或引入子组件 |
| FR-8 | **Store 文件规模** | 单个 `stores/*.ts`（目录全量，`__tests__` 目录除外；2026-11-03 起废除 historic「非 `use*.ts`」前缀排除——原口径误排除 `userStore.ts` 致 31/32 假绿盲区，OP-06 收编；composable 规模由 FR-6 按目录独立管理）**不得超过 500 逻辑行**，计数口径与 FR-6 完全一致（逻辑行 = 物理行 − 空行 − 整行注释（行注释 `//` 与块注释 `/* */` 起止行剔除），行内/行尾注释计入代码行；字符串/模板串内 `//`、`/*` 不视为注释；语义与 BR-4 `logical_line_count` 对齐）。超过时，必须按职责拆分为独立模块（类型/缓存/请求控制等）。计数最小实现为 `scripts/check_frontend_invariants.py`（逻辑行 `logical_line_count`，`--print` 为权威数值来源，含 stores 段；严格模式无台账豁免）。 | 拆分 Store 模块 |

## 五、变更日志
- v1.8 (2026-11-15): **[PATCH-FE] 批次 5 / M-07 前端设计令牌收敛**（方案 v2.3 定稿，D1-D7 冻结：D1=B 同色相提亮单列登记 / D2=B 构建期静态 hex / D3=B 全覆盖 / D4=B 取消任意换肤 / D5=A §3.3 新增 / D6=B 对比度+等值断言 / D7=B variables.css 唯一真源）——新增 §3.3 主色色阶单一真源：8 档亮/暗成对（r=0.08 定稿）+ 双 dark token 保留登记（D0 #557fdf / 品牌锚 #2b5fd7）+ EP 桥 var() 化 + 对比度口径（结构性遗留无达标承诺，C 区观察项）+ 回归锚（primaryTokens.spec 13 例 + walkthrough 运行时直证 206/206）。配套：variables.css 11 处编辑 + dark.css 18 行终态（rgb 字面量清零）+ useChartTheme 渐变换源 + app.ts setPrimaryColor 无参化。C-9（complete-patterns.md）销项重锚。登记：BF-192（走查新发现 F-1 另登 BF-193）。**§5.4 不适用**：色阶为既有令牌覆盖面内的取值收敛，不收紧任何阈值、不改变 CI 阻断行为。
- v1.7 (2026-11-10): **[PATCH-FE] 批次 6 一次审批包**（M-42 + M-15 口径合并共用一次子引擎 §4.2 人工审批）——① 新增 §3.1 图表 palette 派生色豁免登记（M-42，D3-A）：5 类 13 个图表专用派生色逐类登记（2026-11-10 复证：PIE_EXTRA 2 / tooltip 2 / 分割线 2 / 面积渐变 4 / 状态散点 3），写明 F1-F2 四色仍为业务语义色唯一来源、等值断言唯一回归锚、禁裸 hex 扩散三条款、FALLBACK 按 K3 裁决合规；② 新增 §3.2 业务日期固定渲染口径（M-15，D1-A）：业务时刻统一按 `Asia/Shanghai` 渲染，`Format.ts` 双入口（`toBusinessDateTimeParts` / `toLocalDateString`）职责边界书面化，后端 ISO +08:00 契约不变。**§5.4 不适用**：两条均为豁免/口径登记，不收紧任何阈值、不改变 CI 阻断行为。批准依据：批次 6 方案 D1-D7 / 用户拍板 2026-11-10。登记：BF-187（原登记号 BF-186 已被批次 4b 占用，顺延）。
- v1.6 (2026-11-10): **[PATCH-FE] 批次 4 / M-24**——新增滚动条灰阶令牌（亮/暗各 3 个，值迁移自 `global-scroll.scss:10-18`，逐字等值、零渲染变更）；同步修正文档 :4 头部版本号残留（v1.4→v1.6，v1.5 变更时漏改）。配套：M-43 清理 4 处 `var()` 回退字面量（AssetTypeChildList.vue:33 / global-reset.scss:25 / common-forms.scss:84,482）、新增 `scrollbarTokens.spec.ts` 等值断言（T6 先红 3 failed 转绿）。依子引擎 §4.2 经人工审批（[HALT] 已确认）后应用。§5.4 适用性：不收紧任何阈值、不改变 CI 阻断行为，属设计令牌覆盖面扩展，不触发沙盒期。
- v1.5 (2026-11-03): FR-8 口径收编（OP-06）——废除「非 `use*.ts`」前缀排除改**目录全量（`__tests__` 除外）**：原口径以 `startswith("use")` 排除致 `userStore.ts`（"userStore" 以 "use" 开头）假绿盲区（护栏 31 / 实际 32），护栏 `is_store_target` 与本条文同步收编；护栏自测 +5 用例先证红（3 failed）后证绿（49 passed）。[HALT] 经人工批准后应用；v1.4 历史记载不回溯。
- v1.4 (2026-09-21): 新增 FR-8——`stores/*.ts`（非 `use*.ts`）规模上限 500 逻辑行，计数口径与 FR-6 完全一致，guard（`scripts/check_frontend_invariants.py`）扩展 stores 段扫描（严格模式，无台账豁免），`--print` 输出 stores 权威计数。依据子引擎 §4 本地自适应流程，经人工审批（[HALT] 已确认）后以 `[PATCH-FE]` 留痕应用；同步修正 v1.3 未升头部版本号残留。
- v1.3 (2026-09-21): FR-6 行数口径基线固化——条文补充"不含空行和注释"及精确计数语义（与 BR-4 `logical_line_count` 对齐，行内/行尾注释计入代码行，块注释整体剔除）；配套门禁 `scripts/check_frontend_invariants.py` + 台账 `Rules_Fiels/FR6_composable_ledger.md` + CI job `fr6-composable-guard`（`duplicate-guard.yml`）。依据子引擎 §4 本地自适应流程，经人工审批（[HALT] 已确认）后以 `[PATCH-FE]` 留痕应用。
- v1.2 (2026-07-07): 增加对根级安全/可观测性契约的引用（已在设计思路中体现），无实质条款变更。
- v1.1 (2026-07-07): 新增第四节"前端代码复用与量化规范"（FR-1~FR-7）。
- v1.0 (2026-07-07): 初始版本，基于项目 README 建立 F1-F15 与暗色模式标准。