# 批次 8【OpenAPI 信封建模】OP-09 执行规格（方案 A 定稿）

> 版本：v1.0 | 日期：2026-11-04
> 范围：OP-09（P0 信封后处理器 + D1 DELETE 204→200 + 方案 A 幽灵路由清理）
> 状态：**方案 A 已按用户指定，待确认后执行**
> 评审结论：方案 A 机制经代码逐条实证成立；P0 清单基本完善，发现 2 处需补入的缺口（见 §0）。

## 0. 评审结论速览（方案 A 是否完善的回答）

| 核实项 | 结论 | 证据 |
|:---|:---|:---|
| 8 个幽灵 operation 真实存在 | ✅ 成立 | `api-schema-baseline.json` 中 `v1_dashboard_list/create/retrieve/update/destroy`（:9797/:9824/:9870/:9904/:9958）、`v1_users_permissions_create/update/destroy`（:12806-12951） |
| 前后端零调用 | ✅ 成立 | 前端 `dashboard.ts` 仅调 `dashboard/overview/` 等 action；`permissions.ts` 仅 GET 列表；后端测试无写调用（grep 双向核实） |
| `http_method_names` 过滤机制 | ✅ 成立 | drf-spectacular 0.29 `generators.py:80-88`：`methods = actions & http_method_names`，设类属性即让 operation 从 schema **消失**（非 405 声明） |
| 移除 ResponseWrapperMixin 后路由行为 | ✅ 成立 | DRF `routers.py get_method_map` 用 `hasattr(viewset, action)` 过滤 → 路由整体不注册，运行时 404（非 405） |
| D1 运行时依据 | ✅ 成立 | `core/mixins.py:206` destroy 返回 `HTTP_200_OK`；全库无任何 `HTTP_204` |
| 幽灵路由 500 根因 | ✅ 成立 | `ResponseWrapperMixin`（`core/mixins.py:91-215`）list/create/retrieve/update/destroy 全实现且 `except Exception` 兜底 500；DashboardViewSet 无 `get_queryset/get_object/get_serializer`，PermissionViewSet 无 `perform_create/perform_destroy` |
| `pagination_class = None` 端点面 | ✅ 恰好 2 处 | `permission_view.py:44`、`role_view.py:209` —— P0 第 5/6 项全覆盖，无遗漏 |

**发现的 2 处完善性缺口（已并入本规格）**：

1. **G-1（方案遗漏）**：`apps/usermanagement/tests/test_openapi_security_schema.py` 文档字符串第 9、18 行写死「267 个 operation」。经核实**仅是注释、非硬编码断言**（`test_operation_security_unchanged` 动态遍历，无计数断言），删 8 个 operation 后注释漂移为 259 —— 需同步注释，**不阻塞、无断言破坏**。
2. **G-2（DR-1 风险）**：`core/schema.py` 已存在 `ENVELOPE_EXT_NAME = "x-envelope"` 常量。新建 `core/envelope_schema.py` 时**必须 import 复用**，禁止重复定义，否则触发 DR-1。

**结论：方案 A 最终方案完善、可执行** —— 机制成立、改动点行号核实无误、调用方零引用、名单生成有 Stage 0 脚本兜底（防 OS-2 手打事故）；补入 G-1/G-2 两项后无遗留缺口。

## 1. 已锁定决策

| 决策 | 状态 | 说明 |
|:---|:---|:---|
| D1 DELETE 204→200 | 已锁定 | 仅「真实 destroy」适用；方案 A 下 `v1_users_permissions_destroy` 随幽灵路由移除，不会被误标 200 |
| D2 P0 机制+占位 / P1 显式 schema / P2 batch-* 另立 | 已锁定 | P1 共 22 个 operation（本批仅清单登记，**不在 P0 执行**——P1 按方案分批另立） |
| 方案 A（用户已指定） | 已锁定 | 2 处小改清理 8 条永远 500 的幽灵路由 + 信封后处理器；本批 = 「schema 纠正 + 8 条不可用路由清理」 |

> 注：本批 P0 执行范围 = 方案 A 的 2 处路由改动 + 信封后处理器全链路 + 基线重导 + 护栏。P1 的 22 个显式 schema 与 P2 另立 BF **不在本次执行**，仅在规格留痕。

## 2. P0 逐项修改规格（14 项 = 原 12 项 + G-1/G-2）

| # | 文件 | 改动 |
|:---|:---|:---|
| 1 | `asset_management_backend/core/envelope_schema.py`（新增，~120 行） | `build_envelope_schema` / `build_paginated_data_schema` / `is_enveloped` / `envelope_postprocessing_hook` / `ENVELOPE_NO_BODY_OPERATIONS` 与 `NON_ENVELOPE_OPERATIONS` 两个名单。**G-2：`from core.schema import ENVELOPE_EXT_NAME` 复用，不重复定义** |
| 2 | `core/pagination.py:94-118` | `get_paginated_response_schema` 改为调用 builder（7 个分页字段 count/next/previous/page/page_size/total/results 原样，新增 x-envelope + required） |
| 3 | `config/settings/base.py:357 起 `SPECTACULAR_SETTINGS`（现无 POSTPROCESSING_HOOKS，方案写 :377 附近属实） | 追加 `"POSTPROCESSING_HOOKS": ["core.envelope_schema.envelope_postprocessing_hook"]` |
| 4 | `apps/assetmanagement/views/asset_view.py:543` `qr_code_image` | 补 `@extend_schema(responses={(200,"image/png"): {"type":"string","format":"binary"}, 4xx/5xx: ...})` |
| 5 | `apps/usermanagement/views/permission_view.py` | list 显式 `data={count, results:[Permission]}`（无分页时 mixin 返回该形状，`mixins.py:111`）；**方案 A：追加 `http_method_names = ["get","head","options"]`** |
| 6 | `apps/usermanagement/views/role_view.py:209` 附近 UserRoleViewSet | list 显式 `data={count, results:[UserRole]}` |
| 7 | `apps/assetmanagement/views/dashboard_view.py:50` | **方案 A：去掉 `ResponseWrapperMixin`（8 个 action 全部直接 `return success_response(...)`）+ 追加 `http_method_names = ["get","head","options"]`** |
| 8 | `core/tests/test_openapi_envelope_contract.py`（新增） | 9 条护栏（见 §4），含 `test_phantom_crud_routes_removed` 反向清理锁 |
| 9 | 根 `conftest.py` + `apps/usermanagement/tests/conftest.py` | `api_schema` fixture 从 `apps/usermanagement/tests/conftest.py:13`（session 级）上提到根，仍只生成一次 |
| 10 | `apps/usermanagement/tests/test_employee_openapi_contract.py:67-79,136-151` | statistics 断言改读 `.data.$ref`；`test_sort_response_is_bare_array` 改断言 `data` 内层 array |
| 11 | `api-schema-baseline.json` | 同批重导 + 双跑一致性（`spectacular --validate` 两次 diff 无输出） |
| 12 | `Rules_Fiels/backend-business-rules.md:282`（方案写 :284，实测 OS-7 在 282） | 改「code/message 不入 schema」条文，补信封护栏要求 |
| 13 | **G-1**：`apps/usermanagement/tests/test_openapi_security_schema.py:9,18` | 文档字符串「267 个 operation」→ 259（仅注释同步；断言为动态遍历，无计数，已核实不破坏） |
| 14 | **G-2**：`core/envelope_schema.py` 导入 | `x-envelope` 常量复用 `core/schema.py:ENVELOPE_EXT_NAME`（DR-1） |

**名单生成纪律（OS-2 教训）**：P0 的 operation 名单**不许手打**。先跑 Stage 0 临时脚本 `scripts/_op09_report.py`（不提交），输出原样粘贴进常量：

- `NO_BODY` 且 `method == delete` → `ENVELOPE_NO_BODY_OPERATIONS`（方案 A 下剔除 dashboard/permissions 两条幽灵 destroy）；
- `NO_BODY` 其余 → P1 或占位登记；
- `NON_JSON` → 确认是 xlsx/png 后不登记。

**方案 A 改动语义（已核实行号与机制）**：
- `dashboard_view.py:50`：`class DashboardViewSet(LoggingMixin, viewsets.ViewSet)` + `http_method_names = ["get","head","options"]`（保留 LoggingMixin；8 个 @action 全部 GET 类 action，http_method_names 不影响它们）。
- `permission_view.py:34`：`class PermissionViewSet(ResponseWrapperMixin, ListModelMixin, RetrieveModelMixin, GenericViewSet)` + `http_method_names = ["get","head","options"]`（保留 mixin 供 list/retrieve 返回信封）。
- 运行时语义：8 条路由由「500」变「404」（路由不注册）；schema 中 8 个 operation 消失。基线 diff 多出这 8 个删除，**属预期落点**。

## 3. 留痕（本批不做）

- **P1（22 个显式 schema，另立批次）**：认证 5（auth_login/auth_register/auth_logout/v1_auth_token_refresh_create/my_permissions）、部门 7、审计 6、操作日志 1、角色 2（role_permissions、role_permissions_2）、维修 1（repair_asset_batch_delete）。要点：审计 4 列表为 APIView 手工分页（`operation_log_views.py` 四处 `paginate_queryset`+`get_paginated_response` 已核实），必须 `build_paginated_data_schema(AuditLogSchema)` 显式声明整信封；13 字段抽一个 `inline_serializer(name="AuditLog")` 复用 6 处（DR-1）。
- **P2（另立 BF 留痕）**：batch-* data 内层形状错误（基线 :2948 vs `core/batch_mixins.py:337-339`）；token/verify 非信封（运行时改动）；人类文档响应示例过时归 OP-11；重复 operationId `_2` 后缀观察项。

## 4. 护栏与验收（先红后绿 + CT-7）

9 条用例（`core/tests/test_openapi_envelope_contract.py`），含方案 A 新增：

```python
def test_phantom_crud_routes_removed(api_schema):
    for oid in {"v1_dashboard_list", "v1_dashboard_create", "v1_dashboard_retrieve",
                "v1_dashboard_update", "v1_dashboard_destroy",
                "v1_users_permissions_create", "v1_users_permissions_update",
                "v1_users_permissions_destroy"}:
        assert oid not in _operation_ids(api_schema), oid
```

验收命令与预期（从 `asset_management_backend` 执行）：

```powershell
python manage.py spectacular --format openapi-json --file api-schema-baseline.json --validate
python manage.py spectacular --format openapi-json --file $env:TEMP/second.json --validate
# diff 两者 → 无输出
pytest core/tests/test_openapi_envelope_contract.py apps/usermanagement/tests/test_employee_openapi_contract.py -v
pytest --cov=. --cov-fail-under=80
ruff check . && ruff format --check . && mypy . --strict
```

量化预期：裸 JSON 响应 = 0；二次信封 = 0；非 JSON 被包 = 0；未分类 2xx 无 body = 0。断言值取自 schema 与模型枚举，不硬编码（OS-7）。每条护栏须有先红后绿记录（临时关 hook / 回归 QR / 移出名单各取一次红）。

CT-7：门禁结论须在 `requirements/dev.txt` 声明版本下取得；版本漂移时显式标注。

## 5. 回退方案（一次只烧一艘船）

- 方案 A 的 2 处路由改动与后处理器改动**分两个原子提交**：先路由清理（含护栏），再信封后处理器（含护栏）；任一失败单独 revert。
- 基线重导放在最后一步，与后处理器同提交，revert 即回到旧基线。

## 6. 审计票（执行完成后输出）

按根级 AGENTS §4 必填项 + 自检项，含 CT-1~CT-7、DR-1~DR-6、SC、跨端契约、红线触发结论。
