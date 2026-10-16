# CodeGraph 全量审计报告 R2 — 2026-10-15（增补轮）

> 模式：五阶段（增量复核 + 盲区补扫） | Skill：project-all-code-review v1.2.0 | 性质：只读审计（唯一写入为本报告）
>
> 审计对象：`asset_management_backend`（HEAD 9fe6746）+ `vue-assetmanagement`（HEAD 06653d6）。
> 与基线报告 `codegraph-audit-2026-10-15.md` 相比 **HEAD 未动**，但两子仓均有**大量未提交改动**
> （后端 25 文件 +787/-87，前端 63 文件 +1072/-345，含 12 个新测试文件）——本轮重点：
> ① 逐条复核基线 13 条待修项现状；② 未提交改动是否引入新缺陷；③ 基线未覆盖盲区补扫。
> CodeGraph 索引 up-to-date（969 文件 / 17,155 节点 / 38,539 边），未执行 `codegraph generate`。
>
> 路径缩写：后端省略 `asset_management_backend/`，前端省略 `vue-assetmanagement/src/`。
> **终态统计：继承待修 P1×3 / P2×6（其中 P2-04 经自审订正为 9 处）/ P3×3；新增 P2×1（BR-4 超长函数）；
> 不采纳继承 ×6。**

## §一 验证记录（本轮实际执行）

| # | 命令 / 检查 | 结果 | 处置 |
|---|---|---|---|
| 1 | `codegraph status` | up-to-date，无漂移 | 通过 |
| 2 | 两子仓 `git status` / `diff --stat` | 后端 25 文件未提交、前端 63 文件未提交（高危区，与基线一致） | 台账逐条复核前提 |
| 3 | 基线 13 条待修项 file:line 逐条 grep 复核 | 12 条原样命中（未修）；P2-04 由 5 处收窄至 4 处 | 见 §二 |
| 4 | 状态机旁路扫描（`asset_current_status =` / `contract_status =` 直写） | 命中均为 filter/模型字段定义/管理命令，无服务层直写旁路 | 通过（CT-3 旁路维度） |
| 5 | 响应契约入口扫描（`return Response(` 裸用） | 唯一命中 `apps/assetmanagement/urls.py:142` 为 docstring 示例代码，非真实端点 | 通过 |
| 6 | SC-1 密钥硬编码（rg secret/password/api_key/token） | 0 命中（排除测试/空串） | 通过 |
| 7 | SC-3 裸 SQL（`.raw(`/`.extra(`/`cursor.execute`） | 0 命中 | 通过 |
| 8 | SC-5/6 上传安全 | 全后端 `apps/`+`core/` 无文件上传字段/处理器（FileField/InMemoryUploadedFile/upload 均零命中）→ 不适用 | 通过（留痕） |
| 9 | SC-8 依赖漏洞 | 本轮未重跑 pip-audit / npm audit；以基线报告 P2-07 与 CI `security-scan.yml` 为权威门禁 | 继承（未执行+原因：HEAD 未变，advisory DB 复跑无增量意义） |
| 10 | OC-6 健康端点 | `config/urls.py:54 health_check`（DB+Redis，200/503）在位 | 通过 |
| 11 | 分页参数契约（前端 `pageSize` 驼峰混用） | `src/api/*.ts` 0 命中 | 通过 |
| 12 | 日期格式 | notification 序列化器 `DateTimeField(format="iso-8601")`；前端 dayjs/本地解析一致 | 通过 |
| 13 | `python scripts/check_file_length_guard.py` | BR-6 PASS（0 超长文件，最大 asset_view.py 475/500） | 通过 |
| 14 | `python scripts/check_function_length_guard.py` | **BR-4 FAIL**：`repair_asset_service.py complete_repair()` 53 > 50 逻辑行，且未登记超长台账 | **新增 P2-08** |
| 15 | `python scripts/line_metrics.py` | 库模块（被护栏导入），无 CLI 输出属正常；BR-4/BR-6 口径唯一实现 | 通过 |
| 16 | CT-3 资产状态机测试 | `test_state_machine.py` 36 个用例 | 通过（合同状态机缺口继承 P2-06） |

> 覆盖率（CT-2）/ruff/mypy/eslint/vue-tsc：HEAD 未动，本轮不重跑，**以基线报告 §一 结论继承**
> （后端 1916 passed 87.06%；前端 2183 passed；静态门禁 0 错误）。未提交改动规模较大，
> 修复 skill 落盘后应由下一轮审计复跑全部门禁。

## §二 缺陷台账（r2 终态）

### 继承待修 — P1（3 条，本轮逐条复核均未修复）

| ID | 级 | 现状复核证据 | 终态 |
|---|---|---|---|
| P1-01 | P1 | `base_model_serializers.py:223` 仍含 `contract_status` 可写；`contract_view.py:123-133` `perform_update` 仅处理 `settlemented_price`，无 FSM 路由、无审计落库 | 待修（继承） |
| P1-02 | P1 | `apps/notification/views.py:28-38` 仍仅识别 `limit`（默认 20 钳 100），裸数组返回；`page/page_size/type/priority/keyword` 过滤仍缺 | 待修（继承） |
| P1-03 | P1 | `views/RecycleAssetView.vue:163-174` watch 无匹配分支仍不清空 `recyclableRecordcode`（全文件无 `= ''` 重置），`canSubmit` 残留 true | 待修（继承） |

> 三条 P1 的完整描述、修复建议、影响面见基线报告 §二，本表不重复展开；回查命令不变。
> 注意：P1-01/P1-02/P1-03 涉及文件**均在未提交改动中**（contract_view.py / notification/views.py / RecycleAssetView.vue），
> 即改动方向未覆盖这三处缺陷，修复时注意与未提交工作合并。

### 继承待修 — P2（6 条）

| ID | 级 | 现状复核证据 | 终态 |
|---|---|---|---|
| P2-01 | P2 | `apps/unregisteredasset/services.py:195` 仍 `operator_jobcode=approver_employee`（实例落库为姓名） | 待修（继承） |
| P2-02 | P2 | `contract_view.py:201` schema 仍 `choices=["pending","settled"]`，与 8 状态实现漂移 | 待修（继承） |
| P2-03 | P2 | `apps/authusermanagement/urls.py:24` 仍裸注册（未限 actions），create 注册限流绕过仍在 | 待修（继承） |
| P2-04 | P2 | **范围修正（9 处，reviewer 自审订正）**：`componentsdetails/` 下 `page_size: <store>.pagination.total` 残留 9 处 — AssetContentDetails:436、ContractDetails:394、DamagedAssetDetails:421、WasteAssetDetails:224、AuditLogDetails:223、HardDiskSNDetails:408、OutAssetDetails:364、RecycleAssetDetails:373、UnregisteredAssetDetails:351（`max_page_size=100` 静默钳制）。基线报告原列 5 处有遗漏；操作日志/员工两域已改服务端导出（`useOperationLogExcelExport`/`useUserExcelExport`），但上述 9 处无替代证据 | 待修（继承，范围订正为 9 处） |
| P2-05 | P2 | `routes-main-system.ts:16` operationlogdetails 守卫口径未变 | 待修（继承） |
| P2-06 | P2 | 合同 FSM 测试：`tests/` 源码 0 命中 `ContractInvalidTransitionError`（仅 stale `__pycache__` 编译残留，疑为「补测后又删」）；7 条合法转移仍仅 1 条被测 | 待修（继承） |

> P2-07（SC-8 依赖漏洞）本轮未复跑 audit，HEAD 未动、以 CI 为权威门禁，**保留在基线报告跟踪**，不在 r2 重复立账。

### 继承待修 — P3（3 条）

| ID | 级 | 现状复核证据 | 终态 |
|---|---|---|---|
| P3-01 | P3 | `core/excel_export/workbook.py:68` 仍 `coerce_excel_value(value) or ""`（0/False 被转空串） | 待修（继承） |
| P3-02 | P3 | `types/employee.d.ts:62` 死类型 `pageSize` 仍在 | 待修（继承） |
| P3-03 | P3 | `utils/statusMapping.ts:46-54` OUTASSET_STATUS_MAP 仍 4 键 | 待修（继承） |

### 新增 — P2（1 条）

| ID | 级别 | 类型 | file:line | symbol | 描述 | 修复建议 | 回查命令 | 影响面 | 建议验证方式 |
|---|---|---|---|---|---|---|---|---|---|
| P2-08 | P2 | 规模红线（DR-5/BR-4） | `apps/assetmanagement/services/repair_asset_service.py:166` | `RepairAssetService.complete_repair` | 护栏实测 53 逻辑行 > 50 上限（BR-4 FAIL），且未在 `Rules_Fiels/BR4_function_length_ledger.md` 登记豁免 | **必须拆分**（BR4 台账守则 BF-058 教训③：新增超限一律拆分，不得豁免）：将通知构造与操作日志写入抽为私有方法（`_build_complete_notification` / `_write_complete_log`），主函数降至 ≤50 行 | `python scripts/check_function_length_guard.py` | `codegraph impact complete_repair`：约 20 个受影响符号；调用方为 `test_repair_service_gaps.py`（约 15 处）+ `test_asset_lifecycle.py`（3 处）+ 1 个 view 入口，影响面小 | 拆分后重跑 BR-4 护栏 + `pytest apps/assetmanagement/tests/test_repair_service_gaps.py apps/assetmanagement/tests/test_asset_lifecycle.py` 全绿 |

### 不采纳（继承基线 6 条，理由见基线报告，本轮无新增线索推翻）

N-01~N-06 维持原裁决。

## §三 分域结论

| 分域 | 结论 | 证据 |
|---|---|---|
| 资产状态机 | **健康**：无服务层直写 `asset_current_status` 旁路（命中均为 filter/模型定义/管理命令）；`test_state_machine.py` 36 用例覆盖路径 | 本轮 §一 #4、#16 |
| 合同状态机 | **缺陷集中区**：P1-01（序列化层旁路）+ P2-02（schema 漂移）+ P2-06（测试缺口）三案同源 —— 合同状态流转缺统一收口。修复建议按同域归并一次清干净（DR-1） | 基线 §二 + 本轮复核 |
| API 响应契约 | **健康**：唯一裸 `Response` 命中为 docstring 示例，非真实端点 | 本轮 §一 #5 |
| 跨端契约 4 项 | 响应根结构 ✅ / 枚举键名 ✅（8 键 in_store/in_use/recycled_pending/broken/repairing/lost/damaged/scrapped 前后端一致）/ 分页参数 ✅（api 层无 pageSize 驼峰）/ 日期格式 ✅（iso-8601） | 本轮 §一 #5、#11、#12 + 基线 |
| 安全红线 | SC-1 ✅ 零命中 / SC-3 ✅ 零命中 / SC-5,6 不适用（无上传链路）/ SC-8 以 CI 权威（继承 P2-07） | 本轮 §一 #6-9 |
| 可观测性 | OC-6 ✅ /health /ready 在位（DB+Redis 探测） | 本轮 §一 #10 |
| 规模红线 | BR-6 文件护栏 ✅（最大 475/500）；BR-4 函数护栏 ❌ 1 处（P2-08）；line_metrics 为口径唯一实现无 CLI 输出属正常 | 本轮 §一 #13-15 |
| 未提交改动 | 高危区：后端 25 文件/前端 63 文件未提交，其中含本轮确认的 P1-01/02/03 缺陷文件。**建议尽快提交或分批落盘**，否则基线门禁结论（覆盖率/静态检查）与工作区实际状态脱节 | 本轮 §一 #2 |

## 评审结论（阶段 5 自审）

- 证据可回查：全部 16 项验证记录均给出命令；台账每条含 file:line + 回查命令。
- 置信度：P2-08 由护栏脚本直接 FAIL 输出支撑（置信度 100）；继承条目以 grep 复核命中为准（置信度 ≥95）。
- 范围声明：本轮为增量复核轮，语义深查（竞态/异常吞没）以基线报告结论为准，未重复全量语义扫描；未提交 diff 仅做了台账相关文件的定向复核，未逐行审阅全部 88 个改动文件——该盲区由下一轮（修复落盘后）全量审计覆盖。

### reviewer 自审结论（阶段 5 实际执行）

- 抽查重放 4 条验证记录（BR-4 护栏、P2-02、P2-04、P2-06）+ 核对 P1×3 / P2-01/02/05 证据：全部 file:line 可回查命中，无虚构命令、无图谱能力越界声称。
- **发现并已订正 3 处**：① P2-04 原判「收窄为 4 处」系 grep 口径不完整（漏 `page_size: <store>.pagination.total` 写法），实际残留 **9 处**，台账已订正（该条置信度自 50% 修正至 ≥95%）；② P2-08 修复建议删除「登记豁免」选项（BR4 台账守则 BF-058 教训③：新增超限一律拆分不得豁免）；③ P2-08 影响面口径补齐 `test_asset_lifecycle.py` 调用方。
- 轻微备注：§一 #13/#14 命令须在**仓库根**执行（skill §5.4 约束，报告已按此口径书写）。
- 终态置信度：继承 P1×3 / P2-01~03/05/06 / P2-08 / P3×3 均 ≥95%；总体自审**通过**。

