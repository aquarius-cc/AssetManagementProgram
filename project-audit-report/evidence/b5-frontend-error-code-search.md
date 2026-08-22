# B-5 契约变更前置取证：前端 error_code 消费情况（2026-08-24）

## 搜索命令与结果（vue-assetmanagement/src）
1. `grep -rn "VALIDATION_ERROR" src --include="*.ts" --include="*.vue"` → **0 命中**
2. `grep -rn "INTERNAL_ERROR" src --include="*.ts" --include="*.vue"` → **0 命中**
3. `grep -rn "CREATE_FAILED" src --include="*.ts" --include="*.vue"` → **0 命中**
4. `grep -rln "fail_items\|error_code" src` → 仅 API 层类型声明与透传：
   - `error_code: string` / `error_code?: string` 类型字段声明
   - AssetBatchImport.vue 等批量导入页直接展示后端返回的 error_message 文本
5. `damagedAsset.ts / wasteAsset.ts / unregisteredAsset.ts` 中无任何 error_code 特殊分支

## 结论
前端对 fail_items[].error_code 无任何字符串匹配/分支逻辑，仅展示 error_message。
因此后端统一错误码体系（VALIDATION_ERROR→透传 e.error_code、消除 CREATE_FAILED）
不会破坏前端契约。

## 批准
用户已确认采用"修正漂移而非冻结漂移"方向（2026-08-24 对话）。
