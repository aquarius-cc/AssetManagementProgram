# FR-6 Composable 规模台账（唯一豁免源）

> **计数口径**：FR-6 逻辑行 = 物理行 − 空行 − 整行注释（行注释 `//` 与块注释 `/* */` 起止行剔除）；行内/行尾注释计入代码行；字符串/模板串内 `//`、`/*` 不视为注释。语义与 BR-4 `logical_line_count` 对齐。
> **权威数值**：仅以 `python scripts/check_frontend_invariants.py --print` 输出为准，禁止手填。
> **门禁**：`scripts/check_frontend_invariants.py`，双向断言——超限未登记即红、已拆分/删除未移除台账行即红。CI：`.github/workflows/duplicate-guard.yml` 的 `fr6-composable-guard` job（push/PR 到 master 时执行）。
> **红线**：拆分保持原 composable 返回形状不变；孤儿（无 `.vue` 消费方）只登记不拆，删除走独立 PR。

| 批次 | 文件（src/composables/ 相对路径） | 逻辑行 | 处置 | 测试锚 | 消费方证据 | 状态 |
|:---|:---|:---|:---|:---|:---|:---|

> F1 已完结（2026-09-21）：useNotification(218→108) 拆出 useNotificationConnection(138)，useDashboardPage(223→195) 拆出 useDashboardUser(34)，均 ≤200，原 F1 台账行已移除（guard `--print` 复核）；useNotification.spec(32)/useDashboardPage.spec(21) + 全量 composables 603 passed，type-check/lint/format:check 通过。

> 贴线扫描结论（guard `--print` 2026-09-21）：usePaginationSearch(189)、useOutAssetDetailCards(150)、useRecycleAssetDetailCards(139) 均 ≤200，不登记、不拆分。

> 2026-09-22：孤儿 useOutAssetForm.ts（326 逻辑行）已删除（连同自身 spec + 7 处文档头引用，能力由 useAssetFormHelpers/useEmployeeSuggestionFetcher/useAutocompleteField 承接），台账行随之移除。

> 2026-09-22：孤儿批 O 三文件已全部删除——useContractBatchImport.ts(233)/useAssetBatchImport.ts(228)/useDepartmentEmployeeList.ts(215)，连同各自 spec（403/436/372 行）+ 10 处文档头引用（useBatchImport/SubmitBatch/assetStore/contractStore/userStore/api-contract/api-user/errorHandler），台账行随之移除，超限 composable 清零；全 src `.vue` 均使用内联集成实现，能力零依赖，guard 双向红>绿 PASS。
