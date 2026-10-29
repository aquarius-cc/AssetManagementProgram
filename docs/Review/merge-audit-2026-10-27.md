# 审核结果融合报告（merge-audit-2026-10-27）

> 融合来源：`opencode-codegraph-audit-2026-10-27.md` + `atmocode-codegraph-audit-2026-10-27.md`
> 审计基准：git `394efce`（同一 commit，工作树干净）；CodeGraph 索引 1,022 文件 / 18,196 节点 / 41,206 边
> 融合原则：两份报告无重叠条目（opencode 聚焦安全/质量/前端体验，atmocode 聚焦文档/注释漂移），按优先级统一排序
> 只读纪律：本融合报告未改动任何业务代码

---

## §一 融合摘要

| 优先级 | opencode | atmocode | 合计 | 说明 |
|:---|:---:|:---:|:---:|:---|
| P1 重要 | 3 | 0 | **3** | 安全越权 / 状态机旁路 / 前端权限面缺口 |
| P2 优化 | 8 | 0 | **8** | 行级隔离窄面、缓存一致性、提示双发、可观测性等 |
| P3 建议 | 6 | 3 | **9** | 审计缺口、竞态窗口、死代码、文档/注释漂移等 |
| 待确认 | 1 | 0 | **1** | RC-17（需核对后端权限码种子数据） |
| 留痕/不采纳 | 2 | 3 | **5** | 语义合理 / 置信度不足 / 误报排除 |

**结论：无 P0 阻断项，可有条件上线；建议修复 3 个 P1 后放量至多部门隔离环境。**

---

## §二 统一问题台账（按优先级排序）

> ID 规则：`M-RC-xx`（opencode 原始）+ `M-AUD-x`（atmocode 原始），保留原始 ID 便于回溯。
> 修复建议来自两份源报告，融合时已合并同类项。

### 2.1 P1（3 条，建议立即修复）

| 融合 ID | 原始 ID | 类型 | 位置 | 问题描述 | 修复建议 | 验证方式 |
|:---|:---|:---|:---|:---|:---|:---|
| **M-RC-01** | RC-01 | 行级隔离绕过（越权写） | `views/hard_disk_sn_view.py:97,109,112` → `services/hard_disk_sn_service.py:65,115` | update/partial_update/destroy 直接取 `kwargs["recordcode"]` 调 Service，无部门过滤；同文件 `get_queryset()`（:67）与 `RecordcodeLookupMixin` 均未被调用 | 三方法改走 `self.get_object()`（作用域内取对象），或 Service 增加 `user=` 参数复用 `get_queryset_for_user` | 新增跨部门用例：deptA admin PATCH/DELETE deptB 的 recordcode → 期望 404 |
| **M-RC-02** | RC-02 | 状态机旁路（维修记录） | `serializers/repair_asset_serializers.py:60-81` + `views/repair_asset_view.py:136-142` | `repair_status` 可客户端写入，绕过 `fail_repair`/`repair_done` 的 Service 前置校验，且可触发唯一约束 → 500 | `repair_status` 移入 `read_only_fields`（或覆写 `perform_update` 走 Service），补 IntegrityError 映射 | PATCH repair_status → 断言被忽略；并发双 in_progress → 4xx 映射消息 |
| **M-RC-07** | RC-07 | RBAC 前端权限面缺口 | `router/routes-main-core.ts:84-101` + `guards.ts:75-82` + `AsideMenu.vue:45` + `BasicAssetDetails.vue:28-30` | 权限矩阵禁止 `regular_user`/`auditor` 新增/编辑/批量导入，但菜单、详情页编辑按钮、直接输 URL 三条路径均未拦截（后端仍 403 拦截，非越权写入） | 3 条路由补 `meta.requiredMinRole: 'asset_admin'`；菜单/编辑按钮补 `v-if`；表单 `onMounted` 走 `useOperationGuard.guardOnMounted()` | guards.spec 新增 deny 断言；regular_user 直达 `/main/assetform` 被 303 拦截 ✅ **已收口（2026-10-28，见 §3.1.3）** |

### 2.2 P2（8 条，建议尽快修复）

| 融合 ID | 原始 ID | 类型 | 位置 | 问题描述 | 修复建议 | 验证方式 |
|:---|:---|:---|:---|:---|:---|:---|
| **M-RC-03** | RC-03 | 行级隔离绕过（窄面） | `views/recycle_asset_view.py:133-146` → `services/recycle_asset_service.py:297-327` | update/partial_update 直查 `RecycleAsset.objects.filter(recordcode=…)` 无 user 过滤（同文件 destroy :214 已正确） | 与 destroy 对齐改 `self.get_object()` | 跨部门 PATCH recycle recordcode → 404 |
| **M-RC-04** | RC-04 | 行级隔离缺失（create） | `views/hard_disk_sn_view.py:83-95` → `services/hard_disk_sn_service.py:29-61` | 单条 create 未对 `asset_recordcode` 做可见性校验（batch 路径有 `_resolve_asset(user=user)`） | 复用 `_resolve_asset(..., user=user)`（DR-1，与 batch 同一实现） | 跨部门 asset_recordcode 创建 → `ASSET_NOT_FOUND` |
| **M-RC-08** | RC-08 | 缓存一致性 | `api/request.ts:367-376` + 全仓 `clearCacheByPattern` 调用点仅 `api/asset.ts` | 以下写端点未失效 `/assets/assets/{recordcode}/` 缓存：repairAsset.ts、lostAsset.ts、damagedAsset.ts、recycleAsset.ts、outAsset.ts、wasteAsset.ts、foundAsset.ts、brokenAsset.ts（共 9 处） | 抽共享 helper（DR-1）：状态类写端点成功后统一 `clearCacheByPattern('/assets/assets/${recordcode}/')` | 用例：repair 成功后 `getAssetByCode` 二次调用实际打网（cache miss） |
| **M-RC-09** | RC-09 | 提示双发（错误） | `api/request.ts:393` + 7 处调用方二次弹窗 | 拦截器非 401 必弹，调用方 catch 再弹；`useAssetOperationForm.ts:123` 还用 `options.errorMessage` **覆盖后端业务消息** | 错误提示收敛为拦截器单一出口（调用方只补上下文） | 抽查用例：mock 400 断言 `ElMessage.error` 只调用 1 次 ✅ **已收口（2026-10-28，见 §3.1.5）**：notifyCallerError 单一实现（DR-4）铺开 composables/utils/components/views ~50 处 C1 站点 + notifySubmitError 三份收敛 + suppressDefaultError 删除 |
| **M-RC-10** | RC-10 | 提示双发（成功） | `stores/createEntityStore.ts:370,388-390,408-410` | 3 个 store 设了 `disableAutoMessage:true` 但仅 create 分支生效 → update/remove 必双弹（已核实 ≥8 处） | 判断上提为 create/update/remove 三处统一守卫；`brokenAssetStore.ts:28 displayName:'Broken Asset'` 改中文 | 用例：disableAutoMessage 时 update/remove 不弹；表单组件自身提示仍 1 条 ✅ **已收口（2026-10-28，见 §3.1.5）**：update/remove 补 disableAutoMessage 守卫；removeBatch 留痕不改行为（双弹实数修正为 3 处）；displayName ×2 改中文（broken→损坏资产、found→找回资产） |
| **M-RC-11** | RC-11 | 可观测性（OC-1 断链） | `utils/logger.ts:21-28` + `api/request.ts:343` | 前端日志 trace_id（会话单值）与发往后端的 `X-Request-ID`（每请求随机）**不同源**，拿后端日志 id 到前端 grep 无结果 | 请求拦截器复用 logger 的 sessionTraceId（或响应回填同步）；登录/登出调 `resetTraceId()` | 双端各发 1 请求，断言前端日志 trace_id == 后端日志 trace_id == 响应头 ✅ **已收口（2026-10-29，见 §3.1.6）**：请求发起时同步方案（syncTraceId 单一写入口 + 拦截器/tokenRefresh 裸 axios 两处/auth reset 三触点）；跨进程单测不可行，拆 FE 断言（logger.spec ×3）+ BE 既有 request_context 信任链 |
| **M-RC-12** | RC-12 | 错误吞没（降级无标识） | `api/request.ts:400-407,494-501` | `_degraded` 全仓零生产消费者：GET 失败时用户收到错误 toast 但页面渲染 5 分钟前旧数据、无任何降级标识 | 视图/store 消费 `_degraded` 统一提示「当前为缓存数据」（或降级时单次 toast） | 用例：mock GET 失败 + 有缓存 → 断言 UI 出现降级提示 ✅ **已收口（2026-10-28，见 §3.1.5）**：envelope 标记不可达视图，改为 degradedCacheKeys 响应式 Set + 布局级 DegradedCacheBanner（MainView 挂载），E-4 ×3 用例 |
| **M-RC-13** | RC-13 | 并发竞态（清空表格） | `stores/createEntityStore.ts:225-227` + 5 处消费端 `res ?? []` | 并发两次 getList 中慢的旧请求被 seq 作废 → 返回 `undefined` → `?? []` 翻译成「权威空集」写入 ref → 表格被清空 | 消费端对 `undefined` 显式跳过写入（`if (res === undefined) return`） | 用例：并发双请求旧响应晚到 → 断言列表数据保持不变 |

### 2.3 P3（9 条，低优先级，可择机处理）

| 融合 ID | 原始 ID | 类型 | 位置 | 问题描述 | 修复建议 | 验证方式 |
|:---|:---|:---|:---|:---|:---|:---|
| **M-RC-05** | RC-05 | 审计缺口 | `views/_lifecycle_base.py` | `update`/`partial_update` 未覆写走 DRF 默认 `serializer.save()`，日期/原因/描述改动无操作日志（缓解：状态不可写，无状态机风险） | 覆写 update 走 Service+审计（与 create 同范式） | 新增 update 后断言存在 `AssetOperationLog` 行 ✅ **已收口（2026-10-29，见 §3.1.6）**：update_lifecycle_record（select_for_update + BEQ-02 隔离 + OperationLogService 直调同事务）+ 三子类 update_label + 正反用例 ×5（403/404 无审计行） |
| **M-RC-06** | RC-06 | 并发竞态（500 兜底缺失） | `services/asset_service.py:109-164` | `AssetCodeGenerator.generate_with_unique_check` 为 check-then-act，并发双建同码 → 撞 `unique_asset_code_not_deleted` → 未映射 → 500（事务回滚，数据无损） | 接 `core/exceptions.py:147 match_integrity_error_rules`（仓内 7 处先例） | 并发 mock 双写断言映射消息 ✅ **已收口（2026-10-29，见 §3.1.6）**：savepoint + match_integrity_error_rules（DUPLICATE_ASSET_CODE 结构化透传）；定性订正——撞约束现状 400 通用兜底非 500，真 500 为 RuntimeError 路径一并消除（ASSET_CODE_GENERATION_FAILED） |
| **M-RC-14** | RC-14 | 路由加固 | `router/routes-standalone.ts:89-96` | ScrapAsset 路由 meta 仅 title/requiresAuth，同批 7 条均有 `requiredMinRole:'asset_admin'`（实际兜底：提交前 `guardOnMounted()` 拦截） | 补 `requiredMinRole: 'asset_admin'` | regular_user 直达 `/assets/:code/scrap` → 303 ✅ **已收口（2026-10-28，见 §3.1.3）** |
| **M-RC-15** | RC-15 | 死代码 | `services/assetLifecycleService.ts:31,44,62,75` | `handleAssetOut/Recycle/Damaged/Waste` 零生产调用方；内部 `assetStore.getList()` 无参调用会重置分页 | 删除模块及其 spec（或迁移到真实调用点） | 删除后全量 vitest 仍绿 ✅ **已收口（2026-10-29，见 §3.1.6）**：删模块+spec ×10 + 清 7 处残留引用；迁移案不采纳（真实调用点已各有实现）；rg 归零 + 2328 全绿 |
| **M-RC-16** | RC-16 | 死代码/默认值陷阱 | `stores/createEntityStore.ts:69` + `entityStoreRequestControl.ts:51,103` | `enableCache=true` 默认开，但 23 个 store 全部显式 `enableCache:false` → 缓存读写恒不生效、`clearCache` 零调用；风险在默认值：未来新 store 忘设即静默启用 | 默认值翻转为 `false`（或整体移除缓存层与其测试） | 默认值改后全量 store 测试仍绿 ✅ **已收口（2026-10-29，见 §3.1.6）**：默认翻转 false + variants.spec 改写 ×2 + 「默认 false」锁定用例；store 实数 19/19（Fact-1 订正）；缓存层死拆除列后续候选 |
| **M-RC-18** | RC-18 | 并发竞态（窄窗） | `stores/createEntityStore.ts:358-368,398-407,181-194` | 写操作改 `pagination.total` 与 ids 但不 bump `listRequestSeq`：在途旧 getList 返回后整体重写 → 已删行复活/新建行抹除/total 回退 | 写操作成功后 `listRequestSeq++`（作状态版本号） | 用例：写操作期间注入在途旧响应 → 断言列表不回滚 |
| **M-AUD-1** | AUD-1 | 文档漂移 | `apps/assetmanagement/state_machine/transitions.py:9-10` | docstring 标注 unregistered 三处直写为 `:56/:88/:126`，实际 `:56/:89/:128`（M-60 互指注释后行号偏移） | docstring 行号订正为 `:56/:89/:128` | rg 比对实际赋值行 ✅ **已收口（2026-10-29，见 §3.1.7）**：行号标注删除改方法名锚点三连（unregistered.py 实证），永久免疫行号漂移；BF-161 M-60 行脚注订正 |
| **M-AUD-2** | AUD-2 | 注释漂移 | `vue-assetmanagement/src/types/outasset.ts:30-34` | `OutAssetType` 注释仅列 receive/borrow，代码含 `REISSUE='reissue'`（后端 out_asset.py:59 有该枚举，值契约一致） | 注释补 `reissue`；`npx vue-tsc --noEmit` 无影响，纯注释 | ✅ **已收口（2026-10-29，见 §3.1.7）**：注释补 `reissue: 重新发放`（三方同文案）；vue-tsc 零输出 |
| **M-AUD-4** | AUD-4 | 异常吞没 | `apps/assetmanagement/views/_mixins.py:33` | `except DoesNotExist: pass`——get 语义下吞错即 404 可辩护，但无日志留痕（同 M-47 家族） | 补 `logger.debug`（对齐 M-47 三行范式：import+getLogger+调用，caplog 用例同款） | `pytest apps/assetmanagement/ -k mixin` + cov 不回退 ✅ **已收口（2026-10-29，见 §3.1.7）**：debug 留痕（语义「回落」非「未找到」）+ caplog 用例 ×4；cov 68%→90%（:33 分支 miss 清零），42 passed |

### 2.4 待确认（1 条）

| 融合 ID | 原始 ID | 类型 | 位置 | 问题描述 | 下一步 |
|:---|:---|:---|:---|:---|:---|
| **M-RC-17** | RC-17 | 权限判据双轨 | `AsideMenu.vue:166-169` vs `guards.ts:33-51` | 菜单用权限码 `hasPermission`、路由守卫用角色层级 `roleWhitelist`，两套判据来源不同：有码无级→菜单可见进页被拦；有级无码→菜单隐藏但直达可进。**R-3 收口后现状（2026-10-28）**：双轨面已收窄——「资产录入」菜单项已改用 `canOperateAsset`（层级口径）；剩余双轨为 `canManageSystem`/`canApproveDamaged`/`canHandleUnregistered`/`canViewAuditLog` 四项 ✅ **已收口（2026-10-29，见 §3.1.8）**：四判据复用 usePermission 层级实现，权限码双轨归零；方向订正——后端业务端点用层级（IsAuthenticated/IsAssetAdminOrAbove）无权限码校验，**统一到层级口径**而非原建议「权限码为唯一事实来源」（方向反转，见 §3.1.8 留痕②） |

### 2.5 留痕/不采纳（5 条，无需修复）

| 融合 ID | 原始 ID | 类型 | 说明 | 处置理由 |
|:---|:---|:---|:---|:---|
| **M-RC-19** | RC-19 | 置信度不足 | `fail_repair` 的 DamagedAsset insert 无 IntegrityError 映射 | 无法构造可达路径，置信度 <80% 不报告为缺陷，留痕备查。**证据链（2026-10-29 补）**：`uq_damaged_asset_active_asset` 部分唯一约束存在（活跃记录唯一），`violation_error_message` 已挂约束；兜底已由全局 handler 400 通用文案覆盖，本条仅为「无精准映射」。可选对称补法：仿 asset_service create_asset 的 savepoint+matcher（R-6 批5 范式），可达路径证伪前不动 |
| **M-RC-20** | RC-20 | 误报排除 | `urls.py:142 return Response({'status':...})` 疑似响应契约旁路 | 人工核读：位于模块尾部教程 docstring 内，非可执行路径；响应根结构**无旁路**。**取证**：`sed -n '138,145p' apps/assetmanagement/urls.py`（docstring 内） |
| **M-AUD-3** | AUD-3 | 设计差异留痕 | `services/operation_log_service.py:107` vs `core/audit_service.py:63` 双审计链写入口径不同 | 资产域同步（事务内，与业务一致优先）vs 通用域 on_commit 异步（robust=True）——属已声明的分层取舍，非缺陷；R-6 批4 update 审计选同步口径（§3.1.6 留痕⑤）与资产域一致 |
| **M-AUD-5** | AUD-5 | 零残留确认 | 全后端 TODO/FIXME **0 处** | 初扫 8 处命中经复核均为编码格式串 `XXXXXX` 字面量，非待办标记；自审阶段已订正。**取证**：`rg -n "TODO\|FIXME" apps/ core/ --type py` 命中 0 |
| **M-AUD-6** | AUD-6 | 语义合理 | 迁移脚本 `except (JSONDecodeError, TypeError): pass` / consumer `except asyncio.CancelledError: pass` | 一次性数据迁移的类型化吞错 / asyncio 惯例——语义合理，不采纳 |

---

## §三 修复批次与顺序建议

### 3.1 批次划分（融合 opencode R-1~R-6 + atmocode 补充）

| 批次 | 优先级 | 融合 ID | 动作摘要 | 预期收益 | 验证门槛 |
|:---|:---|:---|:---|:---|:---|
| **R-1 行级隔离收口** | 最高优 | M-RC-01 → M-RC-03 → M-RC-04 | ① HardDiskSN 三方法改 `get_object()`（同文件 destroy/batch 已有范式，diff 极小）；② RecycleAsset 对齐 destroy；③ HardDiskSN create 复用 `_resolve_asset(user=)` ✅ **已收口（2026-10-28，见 §3.1.1）** | 消除 2 个跨部门越权写入口 | 新增 3 个跨部门 404 用例 + `test_hard_disk_sn_*`/`test_recycle_asset_service` 全绿 + 全量 pytest |
| **R-2 维修状态机外围** | 最高优 | M-RC-02 | `repair_status` → `read_only_fields`（或 update 走 Service）+ 唯一约束 IntegrityError 映射 ✅ **已收口（2026-10-28，见 §3.1.2）** | 消除状态机旁路与 500 | PATCH repair_status 断言被忽略 + 并发双 in_progress 断言 4xx 映射 |
| **R-3 前端权限面** | 高优 | M-RC-07 + M-RC-14 | ① 4 条路由补 `requiredMinRole`；② 菜单/编辑按钮补 `v-if`；③ 表单 guardOnMounted | 受限角色不再看到不可用操作界面 | ✅ **已收口（2026-10-28，见 §3.1.3）**：7 条路由补 `requiredMinRole`；菜单/列表/详情按钮补 `v-if`；表单 `guardOnMounted` 兜底；新增 `guards-rbac-r3.spec.ts` 25 用例全绿 |
| **R-4 缓存与竞态** | 中优 | M-RC-08 + M-RC-13 + M-RC-18 | ① 共享失效 helper 铺开至状态写端点；② `?? []` 消费端改跳过写入；③ 写后 bump seq ✅ **已收口（2026-10-28，见 §3.1.4）** | 消除「操作后详情 5 分钟旧状态」「表格偶发清空」 | 缓存失效用例 + 并发清空用例；全量 vitest |
| **R-5 提示与降级 UX** | 中优 | M-RC-09 + M-RC-10 + M-RC-12 | ① 错误提示单出口；② `disableAutoMessage` 三处统一守卫；③ `_degraded` 消费提示 ✅ **已收口（2026-10-28，见 §3.1.5）**：notifyCallerError 单一实现铺开 ~50 处 C1 站点 + 三份 notifySubmitError 收敛 + A-4 分类弹窗；update/remove 守卫 + removeBatch 留痕；degradedCacheKeys Set + 布局级 Banner | 消除双弹与静默旧数据 | ✅ ElMessage 调用次数断言（E-1~E-4 共 12 用例）+ 降级提示用例；2333 全绿 |
| **R-6 可观测与整洁** | 中优 | M-RC-11 + M-RC-15 + M-RC-16 + M-RC-05 + M-RC-06 | ① trace_id 同源；② 删死代码；③ 缓存默认值翻转；④ lifecycle update 补审计；⑤ create_asset 接 matcher ✅ **已收口（2026-10-29，见 §3.1.6）**：syncTraceId 单一写入口 + 四触点；assetLifecycleService 删除 + 7 处残留清理；enableCache 默认翻转 + 锁定用例；update_lifecycle_record + 契约保形 + 正反用例 ×5；savepoint + matcher + RuntimeError 消除 + 用例 ×3 | 可观测性闭环 + 死代码清零 | ✅ FE logger.spec ×3 + 2328 全绿；后端 lifecycle 34（含契约 8 条保形）+ asset_service 43 + 回归 46 passed；ruff PASS |
| **R-7 文档/注释订正** | 低优 | M-AUD-1 + M-AUD-2 + M-AUD-4 | ① transitions.py docstring 行号；② outasset.ts 注释补 reissue；③ `_mixins.py` 补 logger.debug ✅ **已收口（2026-10-29，见 §3.1.7）**：docstring 锚点化（方法名三连免疫行号漂移）+ 注释补 reissue（三方同文案）+ debug 留痕（语义订正「回落」）+ caplog 用例 ×4；合并台账 BF-162 | 消除文档漂移 + 异常吞没留痕 | ✅ rg 锚点比对三连一致；vue-tsc 零输出；cov 68%→90% 不回退（:33 miss 清零）；42 passed |
| **留痕** | — | ~~M-RC-17（待确认）~~ ✅ **已收口（2026-10-29，见 §3.1.8）** + 5 条不采纳/留痕 | M-RC-17 权限判据双轨归零（四判据复用层级口径，方向订正见 §3.1.8）；其余 5 条无需修复（证据链已补 §2.5） | — | — |
| **M-CACHE-1** | R-4 留痕⑦ | 缓存一致性 | `request.ts` 响应拦截器（既有全局行为，非 R-4 引入） | 子资源删除/批删写 URL（`/assets/{sub}/{rc}/`）匹配不到带 qs 的子资源列表 key（`/assets/{sub}/?page=…`），子资源列表最长 5 分钟残留已删行。**Fact-1 订正（BF-164 实证）**：列表当前未缓存（store 层 enableCache 已翻 false），残留唯一真实显形路径为子资源**详情** key 5 分钟旧数据 | 拦截器失效模式扩展或子资源写端点接列表 pattern（方案随实现定）；排期 R-5~R-7 之后 ✅ **已收口（2026-10-29，BF-164，见 §3.1.9）**：assetCache 内核 invalidateByRoot + invalidateSubResourceCache 双薄壳，7 api 模块 14 处接入（6 模块 success_ids 精确 + damaged 非同源宽失效）；24/37/13 条 spec 全绿 |

#### 3.1.1 R-1 收口记录（2026-10-28）

原批次三条规定动作之外，同文件两处同型入口一并收口（reissue、batch_delete）：

| 项 | 位置 | 改法 |
|:---|:---|:---|
| M-RC-01 | `views/hard_disk_sn_view.py` update/destroy | 改 `self.get_object()` 走 `get_queryset_for_user`，跨部门 404；Service 签名不动 |
| M-RC-03 | `views/recycle_asset_view.py` update | 同上，对齐同文件 destroy/cancel 范式 |
| reissue（批次外并入） | `views/recycle_asset_view.py` reissue | detail action 补 `get_object()`，跨部门重新发放 → 404 |
| M-RC-04 | `services/hard_disk_sn_service.py` create + 视图 | 增 `user` 参数，`asset_recordcode` 归一化（FK 反序列化为 Asset 对象）后复用 `_resolve_asset(user=user)`，跨部门 → 400 `ASSET_NOT_FOUND` |
| batch_delete（批次外并入） | `services/recycle_asset_service.py` batch_delete_recycle_asset + 视图 | 增 `user` 行级校验（不可见按 `NOT_FOUND` 计 fail_count），视图声明 `batch_delete_passes_user = True`（对齐 core/batch_mixins 既有开关） |

**验证结果**：新增 `apps/assetmanagement/tests/test_row_level_isolation_r1.py`（8 用例：6 跨部门拒绝 + 2 部门内正对照）全绿；`test_hard_disk_sn_*`/`test_recycle_asset_*` 78 例全绿；全量 pytest **2218 passed**（2026-10-28 实测，exit 0）。

**保持现状（有意不重构）**：Service 内二次无过滤查询（视图层 get_object 已把关，与既有 destroy 范式一致）；`RecordcodeLookupMixin` 数字 pk 回退（测试用非纯数字 recordcode）。

#### 3.1.2 R-2 收口记录（2026-10-28）

按核实后调整的最小 diff 方案收口（不选"update 走 Service"，避免第二实现，守 DR-1）：

| 项 | 位置 | 改法 |
|:---|:---|:---|
| 状态机旁路 | `serializers/repair_asset_serializers.py` RepairAssetUpdateSerializer | Meta 增 `read_only_fields = ["repair_status"]`（:84），客户端 PATCH/PUT 携带该字段时 DRF 静默忽略；正规流转走 Service 内 ORM 直写，不受影响 |
| 500 兜底 | `services/repair_asset_service.py` create_repair_asset | `RepairAsset.objects.create` 包 IntegrityError → `re_raise_or_map_integrity_error`（token 用约束名 `uniq_active_repair_per_asset`，:202-210），映射 `DUPLICATE_REPAIR_IN_PROGRESS`；主路径已被行锁串行化 + 锁内防重复校验挡住，此为理论漏网防御 |
| 测试 | 新增 `apps/assetmanagement/tests/test_repair_status_readonly.py`（3 用例） | ① PATCH `repair_status` → 200 且 DB 状态不变、可写字段正常更新、资产无 FSM 迁移；② 同资产顺序双 create（view 层）→ 400 `DUPLICATE_REPAIR_IN_PROGRESS`（service 层逐字断言已有 `test_repair_service_gaps.py:204`）；③ 流转链合并用例：PATCH 被忽略后走正规 repair-done 端点 → `repair_status` 被 Service 正常改写为 completed |

**验证结果**：新用例 3/3 全绿；全量 pytest **2221 passed**（2218 基线 + 3，2026-10-28 实测）；ruff / 文件长度护栏 / 重复护栏全过（CT-7：dev.txt 声明版本下取得）。

**登记不实施（已知残留）**：① 维修 update 无审计——viewset 未覆写 update，repair_cost/repair_description 等可编辑字段 PATCH 无 AuditLogger/OperationLogService 留痕（观测性缺口，可并入 R-6 lifecycle update 补审计）；② `physical_grade_after`/`actual_return_date` 仍可独立 PATCH 造成主从字段不一致（正规路径 complete_repair 为联动写），同属登记项。

#### 3.1.3 R-3 收口记录（2026-10-28）

按复核修正后的最小 diff 方案收口：**7 条路由补 meta**；damaged/unregistered 族 4 条**明确禁补**（防扩权，详见留痕②）。

| 项 | 位置 | 改法 |
|:---|:---|:---|
| M-RC-07 路由直达 | `routes-main-system.ts` AssetFormDirect；`routes-main-core.ts` AssetForm / AssetBatchImport；`routes-main-operations.ts` OutAssetForm / OutAssetBatchImport / RecycleAssetForm | 各补 `meta.requiredMinRole: 'asset_admin'`（1 行/条），regular_user / auditor 直达 → `ElMessage.error` + 落点 `/main` |
| M-RC-14 路由加固 | `routes-standalone.ts` ScrapAsset（`/assets/:code/scrap`） | 补 `requiredMinRole: 'asset_admin'`，与同批 7 条独立操作页对齐 |
| 菜单面 | `AsideMenu.vue:45` | 「资产录入」加 `v-if="canOperateAsset"`；:160 解构扩 `canOperateAsset`（不引 useOperationGuard） |
| 列表面 | `AssetContentDetails.vue:77-78` / `:109-119` | 底部新增/批量导入/批量删除加 `v-if`；`enable-edit` / `enable-delete` 改绑 `canOperateAsset`（CommonList 既有 prop，默认 true，零行为变更；导出对 auditor 仍开放） |
| 详情页 | `BasicAssetDetails.vue:34` | 「编辑」加 `v-if="canOperateAsset"`，与同页出库/回收/状态流转按钮同口径 |
| 表单兜底 | `AssetForm.vue:439` / `AssetBatchImport.vue` | `onMounted` 首行 `guardOnMounted()`（AssetBatchImport 原无 onMounted，本次新增） |
| 测试 | 新增 `src/router/__tests__/guards-rbac-r3.spec.ts`（239 行 / 25 用例） | ①7 条真实路由 meta 锚定（配置回改先红）；②regular_user 四路 deny + auditor deny；③只读反向断言（父级/兄弟路由不得连带加固）；④asset_admin / dept_manager / system_admin 正对照 |
| 存量单测修复 | BasicAssetDetails.spec.ts / AssetForm.spec.ts / AssetBatchImport.spec.ts | 编辑契约用例（锚 recordcode 取键，非权限）前置 `canOperateAsset=true` + 新增 1 条 deny 用例；两个表单 spec 各补 1 行 `useOperationGuard` mock |

**验证结果**：新增 spec 25/25 全绿；3 个被改挂的存量 spec 18/18 全绿；全量 vitest **177 文件 / 2306 用例 passed**（2026-10-28 实测，exit 0）；`vue-tsc --build` 零输出；`eslint` 对本次 13 个改动文件零告警；后端零改动，403 兜底不变。

**三处留痕**：

① **M-RC-14 原「实际兜底：提交前 `guardOnMounted()` 拦截」勘误**——复核实证 `guardOnMounted` 仅由 `useAssetOperationForm` 统一封装，消费方为 5 个独立 View（回收/维修/维修完成/维修失败/遗失/找回）；**ScrapAssetView 与表单族（AssetForm / AssetBatchImport）均不在其中**，故原「兜底」不成立，ScrapAsset 的 meta 是唯一防线（本次已补）。表单族的 `guardOnMounted` 亦为本次新增，非既有能力。

② **damaged / unregistered 族 4 条禁补 meta（防扩权）**——`checkRoleAccess`（`guards.ts:69-73`）中 meta 判定优先于 `roleWhitelist` 前缀回退（命中即 return）。该 4 条的父前缀 `/main/damagedassetdetails`、`/main/unregisteredassetdetails` 已在 roleWhitelist（仅 system_admin / dept_manager，即 4/5 级），regular_user / auditor 本就被前缀回退拦截；若补 `asset_admin`（3 级）会把既有门槛降为 3 级 = **授权扩张**。故保持无 meta、由前缀白名单继续拦截，4 条记录内已加禁补注释，并由新 spec 的「保持无 requiredMinRole」断言锁死。

③ **分组模式行操作残留**——`GroupedAssetTable.vue:162-171` 的 Props 仅 `detailColumns` / `initialSnapshot`，无 enable 类 prop；受限角色在分组视图仍可见行内编辑/删除按钮，点击提交仍由后端 403 兜底（**非越权写入**）。按约定不动通用组件，登记为已知残留。

**行数口径说明（BR-6 台账口径 + 根 AGENTS.md §1.9 LT-1~LT-3）**：

- **术语出处**：BR-6 台账（`Rules_Fiels/BR6_file_length_ledger.md:8-11`）定义「逻辑行数 = 物理跨度 − 空行 − 纯 `#` 注释 − 模块 docstring」，阈值 500 行（:26）；根 `AGENTS.md` §1.9（:111-114，LT-1~LT-3，v3.6.1 于 2026-09-30 引入，见 :319）规定行数结论必须绑定口径、禁以物理口径充当结论。二者并存：前者为后端台账口径，后者为全端口径纪律（LT-* 不在 `Rules_Fiels`，勿在该目录检索）。
- **护栏覆盖缺口**：`scripts/check_file_length_guard.py` 扫描范围为后端——`BACKEND = ROOT / "asset_management_backend"`（:49），`SCAN_DIRS`（:55）全部在 `BACKEND` 下迭代，外加 `BACKEND.glob("*.py")`；`scripts/line_metrics.py` 的实现基于 Python `ast`。二者均**无法计量前端 `.vue`**，即前端 500 行红线目前**无自动化护栏**，逻辑行基线不可产出。
- **本次取数**：以**物理行作显式标注的中间量**（LT-2 允许作中间量，**但不充当红线结论**）。数据源为前端子模块内 `git diff --numstat`（较 `wc -l` 可交叉复算）：

| 文件 | 基线（改前） | 新增 / 删除 | 现状（改后） |
|:---|:---|:---|:---|
| `AssetContentDetails.vue` | 535 | +17 / −4 | 548 |
| `AssetForm.vue` | 489 | +5 / −0 | 494 |
| `AssetBatchImport.vue` | 401 | +9 / −1 | 409 |
| `guards-rbac-r3.spec.ts`（新增） | — | +239 | 239 |

- **判定**：三文件净新增 13 / 5 / 8 行，均 <50 行，不触发 DR-5「新增 ≥50 行须拆分」条款；`AssetForm.vue` 实际 +5（import 1 + 解构 1 + 注释 2 + 守卫 1，无删除），满足「≤5」收紧上限。物理行 548 / 494 / 409 **不作为超限结论**——按 LT-2 与逻辑行口径，前端逻辑行无工具可测，超限与否不可判定。补前端行数护栏列为独立后续项。

**登记不实施（已知重复）**：`guards-rbac-r3.spec.ts` 约 60 行 mock 脚手架与 `guards.spec.ts` 重复。未抽取公共 harness 的原因：`guards.spec.ts` 为 978 行存量超限文件（已带 `TECHNICAL_DEBT` 标记），改动会触发 DR-5 拆分义务；以「新文件自足 + 本条留痕」处置（YAGNI，不引入新抽象）。

#### 3.1.4 R-4 收口记录（2026-10-28）

三批提交：批 1 = M-RC-08 helper + 24 处接入；批 2 = M-RC-13/18 竞态收口（B+C+D 同批硬约束：bump 放大 stale 频率，消费端与类型必须同步就位）；批 3 = 本节文档。

| 项 | 位置 | 改法 |
|:---|:---|:---|
| M-RC-08 helper | 新建 `api/assetCache.ts::invalidateAssetCache`（DR-1 单一实现） | 有 recordcode 走精确失效（详情 key `/assets/assets/{rc}/` + 列表 key `/assets/assets/?`），空值降级宽失效（`/assets/assets/` 前缀，仅缓存未命中重取、不返回错数据）；文件头写死逃逸根因（「写 URL 比缓存 key 更深」，拦截器只按写 URL 清缓存）与 24 处接入清单，防无效扩散 |
| M-RC-08 接入 ×24 | 7 个状态 api 文件（17 单条 + 7 批量） | ①action ×5（repair/repair-done/repair-failed/mark-lost/found，URL 内 rc 精确失效）；②集合 create ×7（表单 asset_recordcode，空值降级宽——repair 表单仅 asset_code、recycle 表单仅 outasset_recordcode → 常态宽）；③审批 ×2 + 单删 ×3 + 批量 ×7（URL 为子资源 rc / 多资产 → 宽） |
| M-RC-13 视图级 ×3 | RoleManage.vue:162 / AuthUserManage.vue:197 / ContactsView.vue:179 | `res ?? []` → `if (res === undefined) return`（跳过写回，保留现有表格数据，不把 undefined 翻译成权威空集） |
| M-RC-13 wrapper ×2 | `useSmartListConfig.ts` getList / performSearch 包装 | `?? []` 删除，stale undefined 直传（列表路径由 loadList 既有 response 守卫天然跳过；搜索路径由状态层新守卫跳过） |
| M-RC-18 bump ×5 | `createEntityStore.ts` create/update/remove/removeBatch/clear | 状态写入完成之后 `listRequestSeq++`（作废在途旧 getList，防写后旧响应回滚/已删行复活/新建行抹除/total 回退；clear 同机理防回填） |
| M-RC-18 类型 | `usePaginationSearchState.ts` SearchConfig 两方法 + `usePaginationSearch.ts` store.getList | 返回类型加 `\| undefined`（undefined 语义沿用 M-16 既有范式，非 stale?: boolean 方案），状态层两处补 `!response` 守卫 |
| 测试 | cache.spec M-RC-08 describe ×4；createEntityStore M-RC-18 describe ×5；usePaginationSearchState 新 spec ×2；视图级集成 spec ×3（M-RC-13-stale-list-guard，含正对照） | ①repair 后二次 getAssetByCode 打网；②damaged 空值降级宽失效（防静默跳过）；③写后 bump 在途旧响应不回滚（5 操作全覆盖）；④搜索路径 stale 不清空；⑤三视图 undefined 不清表 |

**验证结果**：全量 vitest **179 文件 / 2322 用例 passed**（2026-10-28 实测，exit 0；基线 2306 + 新增 16）；`vue-tsc --build` 零输出；`eslint` / `prettier --check` 全过；`check_frontend_invariants.py` PASS（FR-6/FR-8）。分两批提交（`06a5758` 批1 / `2308c16` 批2）。

**留痕清单**：

① **waste 405 三方法不接入**——`waste_asset_view.py:110-126` create/update/partial_update 均 405，无写路径可失效；delete 系不动资产状态。
② **排除端点证据**——asset.ts 既有 5 处失效（AUD-55/BF-152）不在 helper 接入范围；broken/lost/found/repair 的 delete/batch-delete 仅软删自身（is_deleted）不动资产状态；全部 update 类为字段白名单更新不碰状态。
③ **batch-create ×4 以宽失效接入**（broken:73/lost:104/recycle:115/out:157），与单条同一 helper 每处 1 行。
④ **搜索路径分析**——searchSeq（usePaginationSearchState.ts:97）只防搜索间竞态，不防写诱发 stale；M-RC-18 bump 会放大 wrapper `?? []` 为「写后必清搜索表」，故 wrapper 直传 undefined 为**必修**而非可选（修正原「死数据」判断的搜索路径部分；列表路径死数据判断成立）。
⑤ **useAssetListConfig.ts:122 与 AssetLogsView.vue:100 留痕裁剪**——前者仅服务列表路径（loadList:94 天然守卫，其搜索走 searchAssets/combineSearch 不经 listRequestSeq）；后者消费 getAssetTimeline，不经 seq，不在射程。
⑥ **createEntityStore.ts 行数**——逻辑行 394/500（`check_frontend_invariants.py --print` 实证），bump 后 ~399，无触线；该护栏仅覆盖 stores（FR-8），api/composables 层不在其扫描范围。
⑦ **新发现登记（超出「资产状态」射程，已立项 M-CACHE-1，见批次表，排期 R-5~R-7 后）**——子资源删除/批删的写 URL（`/assets/{sub}/{rc}/`）匹配不到带 qs 的子资源列表 key（`/assets/{sub}/?page=…`），子资源列表最长 5 分钟残留已删行；属既有拦截器全局行为、非 R-4 引入。✅ **已收口（2026-10-29，BF-164，见 §3.1.9）**；Fact-1 订正：列表当前未缓存，唯一真实显形路径为子资源详情 5 分钟残留，列表侧零成本一并覆盖。

#### 3.1.5 R-5 收口记录（2026-10-28）

四批代码 + 本节文档共五批提交（`4f518ae` 批1 / `e3faa20` 批2 / `29b7c0f` 批3 / `3141b3e` 批4 / 本节文档批5）。

| 项 | 位置 | 改法 |
|:---|:---|:---|
| M-RC-10（B 步） | `createEntityStore.ts` update/remove 弹窗 + removeBatch 留痕 + displayName ×2 | update/remove 加 `if (!config.disableAutoMessage)` 守卫（非 disable 弹、disable 留给视图三段文案）；removeBatch **不改行为**只留痕（生产调用方 DamagedAssetDetails:459/RecycleAssetDetails:290 视图不弹、由 notifyBatchDeleteResult 三段文案唯一反馈）；displayName broken→「损坏资产」、found→「找回资产」（MarkBrokenView UI 实证，「故障」全仓仅一行代码注释） |
| M-RC-09 单一实现 | `utils/errorHandler.ts::notifyCallerError`（DR-4） | AxiosError → 只 logError（拦截器已弹）；非 AxiosError（含 unwrapResponse 在 code!==0 时抛出的 `new Error(res.message)`、本地 Error）→ 弹一次且业务消息优先；注释写死判据推导 |
| M-RC-09 A-a 簇 ×20 | composables + utils 层全部 C1 站点 | usePaginationSearch/usePaginationSearchState(×2)/useAssetLifecycleActions(×2)/useDashboardPage(×2)/useExcelExport/useExportableAssets/useGroupedAssetList/useGroupChildrenCache/usePagedList/useNotification(×2)/useRecycleFormAssociations(×2)/useRecycleFormSubmit/useUnregisteredApproval(×2)/useOutAssetAssetSelection/useDepartmentEmployeeActions/useBatchImport/useAssetFormHelpers/utils/excelExporter/utils/batchImport/templateExport |
| M-RC-09 三份收敛 | DamagedAssetForm / ContractForm / UnregisteredAssetForm 的 `notifySubmitError` | 三份 isAxiosError 分类拷贝收敛为 notifyCallerError 单出口，isAxiosError import 随之清理 |
| M-RC-09 A-4 | `useAssetOperationForm.ts` handleSubmit | 分类弹窗改单出口（后端业务消息优先，`options.errorMessage` 仅作非 AxiosError 兜底，不再覆盖后端消息）；删除全仓零消费的 `suppressDefaultError` 字段 |
| M-RC-09 A-b 簇 ×~30 | Details/Form/Dialog/components + views 层 C1 站点 | AssetContentDetails(×3)/AssetTypeDetails(×4)/ContractDetails/DamagedAssetDetails/DepartmentDetails（批量删除类）；AssetForm(×2，resolveSubmitError 定义删除)/AssetBatchImport/ContractBatchImport/BasicAssetDetails/AssetTypeForm(×2)/DepartmentBatchAddDialog/DepartmentFormDialog/DepartmentEmployeeList(×2)/DepartmentManagement(×3)；views：AssetLogsView/ContactsView(×2)/AuthUserManage(×3，getErrorMessage→单出口)/RoleManage(×2，extractSubmitErrorMessage 定义删除) |
| M-RC-12（C 步） | `api/request.ts::degradedCacheKeys` + 新建 `DegradedCacheBanner.vue` + `MainView.vue` 挂载 | **响应式 Set\<cacheKey\>**：tryFallbackCache 置位、get 真实网络响应成功清位（含业务失败体）；Banner 按 size>0 渲染黄条「当前为缓存数据」，单一横幅消费 Set |
| 测试 | E-1~E-4 + 存量断言同步 | E-1 errorHandler.spec 契约 ×3 + E-2 useAssetOperationForm.spec 双轨 ×2 + E-3 variants.spec ×4（批1）+ E-4 request.spec ×3；20+ 处存量断言按单出口口径同步（固定文案 → err.message，mock 均为 new Error 非 Axios） |

**验证结果**：全量 vitest **179 文件 / 2333 用例 passed**（2026-10-28 实测，基线 2322 + 新增 11，E-3 批1 时 2328）；`vue-tsc --build` 零输出；`eslint` / `prettier --check` 全过；`check_frontend_invariants.py` PASS（FR-6/FR-8）。

**留痕清单**：

① **C1/C2/C3 分类口径**——C1 = catch 收到 AxiosError 仍弹（拦截器已弹 → 双弹，单出口必修）；C2 = 需 status 特判的定制文案（超出 helper 契约，保留手工分支）；C3 = 本地校验/本地构造错误（非 API 错误，不双弹，保留）。C2 实例：AssetTypeDetails 三处删除 catch 的 400 定制文案「该资产分类已被使用」（isAxiosError + status===400 特判）；C3 实例：'记录编码不存在'/'请完善必填'/'缺少资产编码'/router 跳转失败/ElMessageBox cancel 分支。
② **removeBatch 排除口径**——store.removeBatch 不加守卫不改行为：生产调用方仅 DamagedAssetDetails:459 / RecycleAssetDetails:290 两处，其视图自身不弹、由 `notifyBatchDeleteResult` 的成功/部分失败/全失败三段文案唯一反馈，store 层再弹即双弹；useAssetLifecycleActions.handleBatchDelete 的调用方弹窗已改单出口（AxiosError 静默、业务 Error 弹一次）。
③ **envelope 不可达 → M-RC-12 走全局信号**——tryFallbackCache 置 `_degraded:true`（request.ts:400-407），但 ApiResponse 经 unwrapResponse 解包后该标记**不可达视图**（M-RC-12 原方案「视图/store 消费 `_degraded`」不可实现）；改为模块级响应式 Set + 布局级 Banner（ DegradedCacheBanner 单一消费方），`_degraded` 标记保留供响应层断言（E-4）。
④ **双弹实数 3 处（修正原 ≥8 估计）**——全仓实证仅 DamagedAssetForm:451 update / DamagedAssetDetails:318 remove / RecycleAssetDetails:245 remove 三处为「视图自有弹窗 + store 自动弹」真双弹，均在批 1 B 步以 disableAutoMessage 守卫收口；其余调用方为单层弹窗（批 2/3 改单出口消灭 AxiosError 双弹）。
⑤ **broken/found 命名依据**——broken 取「损坏资产」（MarkBrokenView 页面 UI 实证用语），found 取「找回资产」；「故障」全仓仅一行代码注释，无 UI 消费。
⑥ **suppressDefaultError 删除依据**——useAssetOperationForm options.suppressDefaultError 全仓零生产消费（仅类型声明），且其语义（抑制默认错误）与单出口互斥；A-4 改单出口后字段失去存在意义，连同 @deprecated 注释一并删除。
⑦ **App.vue 排除依据**——App.vue 仅含 router-view 无布局壳（登录页/404 亦经其渲染），降级提示挂其上会在登录页误显；挂载点取业务布局 MainView.vue 的 el-main 顶部（全部 /main 子页面共享，登录/404 不含）。
⑧ **Set\<cacheKey\> 定案依据**——全局布尔有「跳 B 页清位后回 A 页静默旧数据」缺陷：A 页降级置位 → 用户跳 B 页成功清掉全局位 → 回 A 页（keep-alive）仍渲染旧数据但 Banner 已灭；按 cacheKey 维护使清位精确对应「该 URL 网络已通」，A 页残留降级态在自身刷新成功前持续可见。
⑨ **存量断言同步口径**——单出口后非 AxiosError 场景弹 err.message（业务消息优先）而非固定 fallback，20+ 处存量断言按「mock 均为 new Error(...) → 期望 err.message」同步；AxiosError 静默行为由 E-1/E-2 契约用例覆盖。

#### 3.1.6 R-6 收口记录（2026-10-29）

五批提交（`f831ed7` 批1 / `5999f4d` 批2 / `efea70c` 批3 / `439af5a` 批4 / `4a14878` 批5 / 本节文档批6）。

| 项 | 位置 | 改法 |
|:---|:---|:---|
| M-RC-15（B 步） | `services/assetLifecycleService.ts` 删除 + 7 处残留清理 | 四 handler 零生产调用方（迁移案不采纳：真实调用点已各有实现，迁移会把 getList() 无参重置分页缺陷带进生产代码）；删模块+spec ×10，清 5 个 store @callers 头 + 2 条注释 + Format.ts:26；services/ 目录自然消失 |
| M-RC-16（C 步） | `createEntityStore.ts` enableCache 默认翻转 true→false | 生产 19/19 工厂系 store 全显式 false（报告「23」为 Fact-1 订正：非工厂 store 无关），翻转运行时零变化、属防御性改动；variants.spec 改写 ×2（getById/getByName 显式 true）+ 新增「默认 false」锁定用例；移除案不采纳（牵连 entityStoreCache/requestControl 双门/4 spec 缓存段） |
| M-RC-11（A 步） | `logger.syncTraceId` 单一写入口 + 四触点接入 | request.ts 拦截器 header 生成（或外部注入）后同步；tokenRefresh.ts 裸 axios 两处（bearer/cookie refresh，绕拦截器）经 syncWithTrace() 单一入口；auth.ts resetTraceId 落 resetAuthState（logout/silentLogout 共用单点）+ login 成功分支 |
| M-RC-05（D 步） | `AssetLifecycleMixin.update_lifecycle_record` + `_lifecycle_base.py` 覆写 update | select_for_update + BEQ-02 行级隔离（与 delete_* 同口径）+ UPDATE 审计（before/after 快照 + related_record_code/type）；审计**直调 OperationLogService.log_operation**（与 create 同款同事务同生共死）；响应契约保形（200 +「更新成功」+ UpdateSerializer data，partial kwarg 透传）；三子类注入 update_label |
| M-RC-06（E 步） | `asset_service.create_asset` savepoint + matcher；RuntimeError 消除 | 内层 atomic(savepoint) + IntegrityError → match_integrity_error_rules（镜像 storage_service BF-139）→ 400 + DUPLICATE_ASSET_CODE 结构化透传(#41)；generate_with_unique_check 的 RuntimeError → AppValidationError(ASSET_CODE_GENERATION_FAILED)，消除真 500 路径 |
| 测试 | 前端 logger.spec ×3 + variants 锁定 ×1；后端 lifecycle 正反 ×5 + asset_service ×3 | 前端全量 2328 passed（2333 − 10 删 + 5 增）；后端 test_lifecycle_view_api 34 passed（含契约 8 条 PUT/PATCH 保形 + test_batch_contract_snapshot 全绿）+ test_asset_service 43 + gaps/batch 回归 46 |

**验证结果**：前端全量 vitest **179 文件 / 2328 用例 passed**（2026-10-29 实测）；`vue-tsc --build` 零输出；eslint / prettier 全过；FR 护栏 PASS。后端 ruff PASS、lifecycle/asset_service 全套 34+43+46 passed、test_batch_contract_snapshot 快照保形。覆盖率分层阈值无回吐风险（B 步删的是被 10 用例全覆文件，只会抬高 ts 层均值）；mutmut 本批未跑（E 步新增 try/except 变异点风险留待下次定时全量，跌破 83.2568% 先补杀用例不调阈值）。

**留痕清单**：

① **M-RC-06 定性订正（Fact-1）**——原报告「撞约束 → 未映射 → 500」不成立：AssetViewSet.create 无 try/except → IntegrityError 透传全局 handler → exception_handler.py IntegrityError 分支 → **400 通用文案兜底**（既有），真 500 是 :115 RuntimeError(MAX_RETRY) 路径；碰撞概率前提 _generate_uuid_hex = uuid4().hex[:8]（2⁻³² 低频）；先例实数 **10 处**生产调用点（multi 规则 4 + 单规则包装 6，非报告「7 处」）；本批收益 = 400 通用 → 精准文案 + error_code 结构化。
② **M-RC-11 OC-1 口径说明**——请求发起时同步方案：每请求唯一（✓ 字面合规 OC-1）；会话内前端日志归属最近一次请求；首请求前的日志为前端本地懒生成 id 不回传后端。「响应回填」备选否决：错误路径无响应头、请求期间日志仍不同源。
③ **M-RC-16 死层拆除候选**——enableCache 翻转后缓存层（entityStoreCache.ts + requestControl 读写双门 + clearCache 方法 + 4 spec 缓存段）成为纯死层，后续可独立批次整体拆除；本批不采纳移除案（牵连面大、风险大于收益）。
④ **M-RC-15 清理面实证**——残留引用实数 7 处（5 store @callers + 2 修复双弹注释 + Format.ts:26，原估 8 处含重复计）；coverage/HTML 与 .stryker-tmp 副本未入库（git ls-files 实证），rg 归零验收无假阳性；「迁移到真实调用点」不采纳理由见上表。
⑤ **M-RC-05 审计入口选择**——update 在 @transaction.atomic 内，直调 OperationLogService（异常上抛、审计与业务同生共死）；**不用 AuditLogger._safe_log**（audit.py:93-104 吞异常返回 False，与 delete 路径同款）——吞异常会造成「更新已提交审计静默丢失」，正是 RC-05 要补的洞；delete 保持 AuditLogger 不动（软删已提交后审计缺失可接受，口径差异留痕）。
⑥ **M-RC-05 同构核验与范围边界**——Lost/Found UpdateSerializer 与 Broken 同构（:151-155/:259-264，asset_recordcode read_only）；AssetLifecycleViewSetBase 仅 3 子类（Broken/Lost/Found），RepairAssetViewSet 不继承该基类，同文件维修 PUT/PATCH 不受覆写影响；403/404 反向用例防覆写绕过权限分支/异常分支误写审计。

#### 3.1.7 R-7 收口记录（2026-10-29）

两段提交（提交 1 纯注释：backend `87b17cb` + vue `11ab0c8` + 根仓 `e4dbc76`；提交 2 代码+测试+登记：本批）。合并台账登记：活账本 BF-162（含 BF-161 四、M-60 行脚注订正——`:56/:88/:126` 系登记时快照，实际 `:56/:89/:128`，历史行号保留不改写，归档件红线遵 M-63 支 (ii) 惯例）。

| 项 | 位置 | 改法 |
|:---|:---|:---|
| M-AUD-1 锚点化 | `state_machine/transitions.py` docstring | 行号标注删除，改方法名锚点三连（unregistered.py 实证 :56/:89/:128）：`unregistered_create_and_recycle`→RECYCLED_PENDING / `unregistered_create_and_damaged`→DAMAGED / `force_recycle_from_any`→RECYCLED_PENDING；符号定位永久免疫行号漂移，rg 比对三连一致 |
| M-AUD-2 注释补齐 | `types/outasset.ts` | 注释补 `reissue: 重新发放`（后端 out_asset.py:59 REISSUE 与 Format.ts:366 映射同文案）；纯注释，`npx vue-tsc --noEmit` 零输出 |
| M-AUD-4 留痕补日志 | `views/_mixins.py:33` | `pass` → `logger.debug("pk 未命中, 回落 recordcode 查找: %s", lookup_value)`（lazy %s 对齐 M-47 三行范式；语义为「回落」非「未找到」——真正抛 404 的是 recordcode 也未命中分支，留痕不得成为新误导源） |
| M-AUD-4 测试 | 新建 `test_recordcode_lookup_mixin.py` | Stub View（满足 get_object 成员契约：queryset/get_queryset/kwargs/check_object_permissions）+ AssetType 两字段建行；caplog 用例 ×4：正例（pk 未中回落命中恰一条日志）/反例（pk 直中不日志）/回落 404（留痕后抛）/回归屏障（非 digit 不进 pk 分支不误报） |

**验证结果**：cov 基线不回退实证——_mixins.py 改前 28 语句/9 miss/68%（miss 含 28-33 pk 分支），改后 30 语句/3 miss/**90%**（正例命中清零 :33 分支 miss）；lifecycle/batch_mixin/lookup 回归 42 passed；ruff format/check PASS；_mixins.py 81→86 行（LT-3 口径，远低于 DR-5 上限）。

**留痕清单**：

① **M-AUD-4 日志语义先订正再落地**——:33 的 pass 是「digit 值按 pk 查未中 → 回落 recordcode 查找」，若按原建议写 "not found" 排障时会被误导；文案「pk 未命中, 回落 recordcode 查找」+ debug 级（正常回落路径非异常）。
② **测试替身用 Stub + 真实模型**——get_object 依赖 self.queryset（供 .model.DoesNotExist）与 self.get_queryset()，Mock 无法提供；check_object_permissions 在 pk 命中（:30）与回落成功（:40）均调用，Stub 提供双 no-op；模型选 AssetType 避开 RecycleAsset 三重 FK 建行负担。
③ **正例构造修正**——AssetType recordcode 为生成串非纯数字，digit 值回落查不到；正例将 recordcode 显式置为 digit 串（"9000000001"）以真实命中回落路径，非 mock 绕过。

#### 3.1.8 M-RC-17 收口记录（2026-10-29，留痕批补正）

单批提交（AsideMenu 判据收敛 + usePermission.spec 矩阵/守卫 + 本节与 §2.4/§2.5/留痕行/§五/§四 补正 + 活账本 BF-163 + D-8）。合并台账：活账本 BF-163、重复代码账本 D-8（v2.9.59）。

| 项 | 位置 | 改法 |
|:---|:---|:---|
| M-RC-17 四判据收敛 | `AsideMenu.vue` | 删 :166-169 四个权限码 computed 与 PERMISSION_CODES import，改为解构复用 usePermission 同名层级判据（canManageSystem=isAdmin‖码短路 / canApproveDamaged=canHandleUnregistered=isDeptManagerOrAbove / canViewAuditLog=isAdmin‖isAuditor，:105-117 既有实现，DR-4 单一来源）；R-3 既有 R-3/M-RC-07 注释保留并补「三方同口径」依据 |
| 测试三层 | `usePermission.spec.ts` | ①四判据 × 5 角色矩阵（regular_user/auditor/dept_manager/asset_admin/system_admin，期望值注释在用例头，层级口径不依赖权限码表）；②3 条「有码低角色 → false」锁定（damaged:approve / unregistered:approve / auditlog:read 授予 regular_user 仍 false——第三条原权限码实现为 true，属**行为变更**显式锁定）+ auditor 对 auditlog 的 true 正例；③?raw 源码守卫：AsideMenu 不得再出现 PERMISSION_CODES / hasPermission(（先例 GroupedAssetTable.spec.ts:25） |

**验证结果**：全量 vitest **179 文件 / 2337 用例 passed**（2026-10-29 实测，基线 2328 + 9）；`vue-tsc --build` 零输出；eslint / prettier 全过；FR 护栏 PASS。AsideMenu 净减行（DR-5 不触发；.vue 无自动化行数护栏，LT-1~LT-3 口径人工标注）。

**留痕清单**：

① **方向订正（§2.4 原建议反转）**——原建议「权限码为唯一事实来源」方向反了：业务端点 permission_classes 用 `IsAuthenticated / IsAssetAdminOrAbove`（层级），无权限码校验；权限码仅在种子态覆盖（0016/0017），RolePermDialog 手工授权后菜单（权限码口径）与守卫（层级口径）必分叉。统一到**层级口径**为三方（菜单/守卫/后端）唯一可达的同口径。
② **RolePermDialog 手工授权路径行为边界**——授权他角色权限码后，菜单可见性**不再随之变化**（层级口径为准），与路由守卫行为一致：即「菜单不承诺展示权限码授予的页面可达性」，有码无级场景（种子下不存在，手工授权后存在）表现为码静默无效——该口径由本节与 AsideMenu 注释固化，后续若要「码驱动可达性」须三方（种子/守卫/permission_classes）整体翻案，非菜单单侧可改。
③ **种子核对（0016/0017）**——0016：auditlog:read 全角色有码（canViewAuditLog 行为变更的依据：原权限码实现下菜单对全员可见，白名单仅 [SYSTEM_ADMIN, AUDITOR]，改后菜单对 regular_user 隐藏，与守卫一致）；damaged:approve / unregistered:approve 仅 dept_manager + system_admin（与 isDeptManagerOrAbove = {dept_manager, system_admin} 一致，ROLE_HIERARCHY 实证 dept_manager:4 > asset_admin:3，复用不引入 asset_admin「见菜单被拦」反向双轨）；0017：system_config:manage 仅 system_admin（canManageSystem 的 ‖hasPermission 短路项现状恒 false，保留为实现原样、消重不消语义；「收紧为纯 isAdmin」列为留痕决策项未采纳——usePermission 内部保留码依赖不影响 AsideMenu 双轨归零）。
④ **canViewAuditLog 行为变更显式锁定**——regular_user 持 auditlog:read 码时菜单由可见转隐藏（与守卫白名单一致），spec 第三条锁定用例防日后被当作回归改回权限码口径。
⑤ **?raw 守卫注释适配**——AsideMenu R-3 注释含 `hasPermission(` 字面（「不用 hasPermission(asset:create)」说明文字）会误触守卫，注释改写为「不用细粒度权限码（如 asset:create 的 hasPermission 判定）」去括号字面，守卫保持严格（禁 PERMISSION_CODES 与 hasPermission( 两形态）。
⑥ **mount 冒烟不做**——AsideMenu mount 需 stub EP 菜单全族 + router + 三个子组件（DarkModeToggle/NotificationBell/AssetQuickScan），成本高于收益；层级逻辑已由 usePermission.spec 矩阵全覆盖 + ?raw 守卫锁定源码形态，理由留痕。

#### 3.1.9 M-CACHE-1 收口记录（2026-10-29）

单批提交（assetCache 内核重构 + subResourceCache.spec 24 条 + 7 api 模块 14 处接入 + 本节与 :96/R-4 留痕⑦/§四 补正 + 活账本 BF-164）。方案选型：**不动拦截器、不动 cache.ts**，assetCache 内核 `invalidateByRoot`（不导出，DR-1）+ 双薄壳（`invalidateAssetCache` 签名不变薄壳化 / `invalidateSubResourceCache` 新入口）——否决「拦截器失效模式扩展」（拦截器无法区分同源/非同源，damaged 批删需宽、其余需精确，内核按 codes 语义分发为唯一可达方案）；否决「子资源写端点接列表 pattern」（同效果但散落 14 处，公共核更 DR-1）。

| 项 | 位置 | 改法 |
|:---|:---|:---|
| 内核 + 双薄壳 | `api/assetCache.ts`（73→132 行） | `invalidateByRoot(root, codes?)`：root 归一化补首尾斜杠；codes=null → 宽 `${root}`；数组 → 逐条 `${root}${code}/` + `${root}?`；**P0-3**：空数组只清列表 `${root}?` 不得退化宽清（批删全失败不降级为清集合详情）；空串过滤防 `${root}/` 自伤。`invalidateAssetCache` 薄壳化（精确=核([rc])、宽=核(null)，**既有 cache.spec 13 条断言一字不改全绿**——P0 等价性实证）；`invalidateSubResourceCache` 为子资源入口 |
| 14 处接入 | 7 api 模块 | 单删 ×7 精确 `[rc]`；批删 ×6 精确（**success_ids 优先，运行时缺失回退 ids** 保守过清）；damaged 批删**非同源宽失效**（ids/success_ids 均为资产 recordcode，够不到损坏单详情 key，禁止逐条）。damaged/recycle/out 的 6 处既有 `invalidateAssetCache()` 保持并存（职责不重叠） |
| 注释改写（§8） | assetCache.ts 头注释 | 旧结论「子资源写 URL 就是缓存 key 前缀，拦截器已覆盖——不要补失效」改为：**单删命中自身详情、命中不了列表；批删两者都命中不了**（对详情 key 部分正确、对列表 key 与批删 URL 不成立）；既有 24 处清单原样保留，另起「子资源侧 14 处」段 |
| 测试 | 新建 `subResourceCache.spec.ts` 24 条（先红后绿实测 18 failed→0） | 核归一化/P0-3/空串过滤/宽失效 ×6；单删 ×7 契约表驱动；批删 ×7（6 精确 success_ids + damaged 负断言「不产生任何逐条 pattern」）；success_ids 混合失败/全失败；deferred await 时序（resolve 前零失效/resolve 后/reject 零）；打网语义 MemoryCache 实证（四 key 清谁不清谁）；update 豁免留痕 |

**验证结果**：全量 vitest **179 文件 / 2361 用例 passed**（2026-10-29 实测，基线 2337 + 24）；`vue-tsc --build` 零输出；eslint / prettier / FR 护栏全过；coverage：assetCache.ts **100%**（整体分层阈值不回退）；规模 assetCache.ts 132 行（DR-5 内，.ts 阈值 src/**≥80 不回退）。

**留痕清单**：

① **有意收紧（登记防「顺手改」误判）**——damaged/recycle/out 6 处既有 `invalidateAssetCache()` 由 fire-and-forget 收紧为 await 后失效：写失败（reject）时不再失效资产侧缓存（行为更正确——失败不应清缓存），返回类型不变对 store 透明；范围声明：仅本次 14 处成立，其余 18 处资产侧 fire-and-forget 接入点未收口，不对外宣称全仓。
② **效果边界**——显著降低但不消除「写在途 → 并发 GET 回填旧数据」窗口（GET 响应晚于失效仍回填）；根治需缓存代际/seq（M-RC-18 范畴），本条不做。
③ **Fact-1 订正**——原描述「子资源列表残留已删行」当前不显形：store 层 enableCache 已由 M-RC-16 全翻 false（createEntityStore.ts:69-72），17 处缓存 GET 全为详情、无列表；唯一真实显形路径为 damaged 等子资源**详情** 5 分钟残留；列表侧按「将来可能启用」零成本一并覆盖（API 层 `request.get(..., true)` 能力仍在）。
④ **update 豁免**——各模块 update 系列不接入（列表未缓存故无害），spec 用例 13 锁定 + assetCache.ts 豁免注释写明「启用列表缓存时须同步接入」。
⑤ **成功路径零冗余**——薄壳每次调用产 1 次（宽）或 2 次（精确）`clearCacheByPattern`，核内无重复调用；cache.spec:136-144 次数断言零改动通过。
⑥ **残余风险（已知、不在本条）**——①其余 18 处 fire-and-forget 窗口；②GET 回填窗口需代际/seq；③列表缓存启用时 update 系列 7×1 须同步接入。

### 3.2 推荐执行顺序

```
R-1（行级隔离，安全相关） → R-2（状态机旁路，安全相关）
    ↓
R-3（前端权限面，与 R-1/R-2 同属权限域，可并行评审）
    ↓
R-4（缓存与竞态） → R-5（提示与降级 UX）
    ↓
R-6（可观测与整洁） → R-7（文档/注释订正）
```

**关键约束**：
- ~~R-1 完成前不建议对外暴露写接口给多部门隔离部署环境~~ ✅ **R-1 已收口（2026-10-28，见 §3.1.1），该约束解除**
- ~~R-2 完成前不建议开放 asset_admin 角色给非核心运维人员~~ ✅ **R-2 已收口（2026-10-28，见 §3.1.2），该约束解除**
- ~~R-3 可与已收口的 R-1/R-2 独立排期（前端权限面为独立修复域）~~ ✅ **R-3 已收口（2026-10-28，见 §3.1.3）**，菜单/详情页按钮/直达 URL 三条路径均已拦截
- R-4~R-7 为质量/体验/整洁类，可在安全项落定后排期

### 3.3 修复优先级矩阵

| 影响面 \ 紧迫性 | 高（安全/数据正确性） | 中（体验/一致性） | 低（整洁/文档） |
|:---|:---|:---|:---|
| **广（多角色/多部门）** | M-RC-01, M-RC-07 | M-RC-08, M-RC-13 | M-RC-16 |
| **中（特定功能路径）** | M-RC-02, M-RC-03 | ~~M-RC-09, M-RC-10, M-RC-12~~ ✅ 已收口（R-5，2026-10-28，见 §3.1.5）；~~M-RC-05, M-RC-06~~ ✅ 已收口（R-6，2026-10-29，见 §3.1.6）；~~M-RC-11, M-RC-15, M-RC-16~~ ✅ 已收口（R-6，2026-10-29，见 §3.1.6） | M-RC-18 |
| **窄（单点/边缘）** | M-RC-04 | M-RC-14 | ~~M-AUD-1, M-AUD-2, M-AUD-4~~ ✅ 已收口（R-7，2026-10-29，见 §3.1.7） |

---

## §四 上线判定（融合版）

| 维度 | 状态 | 证据/说明 |
|:---|:---|:---|
| 功能回归 | ✅ 全绿 | 本地后端 2,210/0 + 前端 2,280/0（2026-10-27 实测） |
| 静态门禁 | ✅ 全绿 | ruff check/format 0、BR-4/BR-6/重复护栏 PASS |
| 覆盖率 | ✅（CI 权威） | CI Pipeline `40466576631` → 90.09% ≥ 80%；本地本轮未取得完整结论（CT-7：以 CI 为准） |
| 依赖安全 | ⚠️ 条件绿 | head 上 security-scan/CD 全绿；但最近一次**完整** pip-audit 红于 twisted 5 项（BF-159，等 26.10.0），下次依赖变更或每周定时全量扫描会再次红——属已知遗留非新发现 |
| 安全越权 | ✅ 0（原 2×P1） | ~~M-RC-01（跨部门硬盘改删）~~ ✅ **已收口（R-1，2026-10-28，见 §3.1.1，连带 reissue/batch_delete 同型入口）**；~~M-RC-02（维修状态可写）~~ ✅ **已收口（R-2，2026-10-28，见 §3.1.2，read_only_fields + IntegrityError 兜底）**；后端越权写入口清零 |
| 前端权限面 | ✅ 0（原 1×P1） | ~~M-RC-07（受限角色可从菜单/详情页/直接输 URL 进入录入/编辑/批量导入页）~~ ✅ **已收口（R-3，2026-10-28，见 §3.1.3）**：7 条路由补 `meta.requiredMinRole` + 菜单/列表/详情按钮补 `v-if` + 表单 `guardOnMounted` 兜底；M-RC-14 ScrapAsset 同批加固；~~M-RC-17 权限判据双轨~~ ✅ **已收口（留痕批，2026-10-29，见 §3.1.8）**：菜单四判据复用层级口径，菜单/守卫/后端三方同口径 |
| 跨端契约 | ✅ | 4 项全通过（响应根结构/状态枚举/分页参数/日期格式） |
| 状态机完整性 | ✅ | 资产 FSM 旁路 0 处（声明例外 3 处有留痕）；合同 FSM 单闸 |
| 文档/注释一致性 | ✅（原 2×P3） | ~~M-AUD-1/M-AUD-2 文档漂移~~ ✅ **已收口（R-7，2026-10-29，见 §3.1.7）**：docstring 锚点化 + outasset.ts 补 reissue；M-AUD-4 吞没点 debug 留痕同批落地 |

**综合结论：有条件可上线（无 P0/P1 阻断项；R-1~R-7 与 M-RC-17 留痕批、M-CACHE-1 已于 2026-10-28/29 全部收口——后端越权写入口清零、前端权限面三条可达路径均已拦截且菜单/守卫/后端三方同口径、提示域收口至单一出口 + 降级标识 Banner、可观测性 trace_id 双端同源闭环 + 审计缺口补齐 + 死代码清零、文档漂移与异常吞没留痕订正完毕、子资源缓存残留已按同源精确/非同源宽失效两型收口；剩余仅 1 项依赖遗留（twisted pip-audit，等 26.10.0），不影响运行时行为；建议可放量至多部门隔离环境）。**

---

## §五 可复核命令（融合报告全部结论的取证入口）

```bash
# 索引与结构
codegraph status
codegraph explore "资产状态机 AssetState VALID_TRANSITIONS AssetFSM" --max-files 8
codegraph node VALID_TRANSITIONS; codegraph node success_response

# M-RC-01/03/04 取证（行级隔离）
codegraph node HardDiskSNService.update
rg -n "def update|get_object" asset_management_backend/apps/assetmanagement/views/recycle_asset_view.py
rg -n "_resolve_asset" asset_management_backend/apps/assetmanagement/services/hard_disk_sn_service.py

# M-RC-02 取证（维修状态机旁路）
rg -n "repair_status|read_only_fields" asset_management_backend/apps/assetmanagement/serializers/repair_asset_serializers.py

# M-RC-07/14 取证（前端权限面）
rg -n "requiredMinRole" vue-assetmanagement/src/router/routes-main-core.ts vue-assetmanagement/src/router/routes-standalone.ts
sed -n '59,83p' vue-assetmanagement/src/router/guards.ts        # 默认放行 return true
rg -n "v-if" vue-assetmanagement/src/components/AsideMenu.vue

# M-RC-08 取证（缓存一致性）
rg -n "clearCacheByPattern" vue-assetmanagement/src

# M-AUD-1/2 取证（文档/注释漂移）
rg -n "unregistered.py:" asset_management_backend/apps/assetmanagement/state_machine/transitions.py
rg -n "reissue" vue-assetmanagement/src/types/outasset.ts

# 留痕 6 条取证（M-RC-17 已收口 + M-RC-19/20/AUD-3/5/6）
rg -n "canManageSystem|canApproveDamaged|canHandleUnregistered|canViewAuditLog" vue-assetmanagement/src/components/AsideMenu.vue   # 四判据复用层实现（无 PERMISSION_CODES/hasPermission 消费）
rg -n "isDeptManagerOrAbove|isAdmin|isAuditor" vue-assetmanagement/src/composables/usePermission.ts                                # 层级判据单一来源（:105-117）
sed -n '33,51p' vue-assetmanagement/src/router/guards.ts                                                                           # roleWhitelist 与层级判据一致性对照
rg -n "uq_damaged_asset_active_asset|violation_error_message" asset_management_backend/apps/assetmanagement                        # M-RC-19 证据链（约束存在）
sed -n '138,145p' asset_management_backend/apps/assetmanagement/urls.py                                                            # M-RC-20（docstring 内，非可执行路径）
rg -n "TODO|FIXME" asset_management_backend/apps asset_management_backend/core --type py                                           # M-AUD-5（期望命中 0）

# 门禁
cd asset_management_backend && python -m pytest -q --no-cov        # 期望 2210 passed
python scripts/check_file_length_guard.py --print                  # exit 0
python scripts/check_duplicate_invariants.py                       # PASS
cd vue-assetmanagement && npx vitest run && npm audit --omit=dev   # 期望 2280 passed / 0 vulns
gh run list --limit 6                                             # CI/CD 直证
```

---

## §六 融合自审

| 检查项 | 结论 |
|:---|:---|
| 来源完整性 | ✅ 两份源报告全部条目均已纳入（opencode 20 条 + atmocode 6 条 = 26 条，其中 5 条留痕/不采纳） |
| 去重校验 | ✅ 无重叠：opencode 聚焦安全/质量/前端体验（RC-01~RC-20），atmocode 聚焦文档/注释漂移（AUD-1~AUD-6） |
| 优先级合并 | ✅ 按 P1/P2/P3 统一排序，保留原始 ID 便于回溯 |
| 修复建议完整性 | ✅ 20 条待修项均具备 file:line + symbol + 修复建议 + 验证方式 |
| 批次可执行性 | ✅ R-1~R-7 批次可直接交接 `bug-surgical-fix` / `rigorous-dev` skill |
| 上线判定一致性 | ✅ 两份源报告均判定「可上线（有条件）」，融合版补充多部门隔离场景的 R-1/R-2 前置约束 |

---

*融合生成时间：2026-10-27 | 融合工具：opencode · mimo-v2.6-flash-free*