---
name: backend-exception-cleanup
description: Drive the asset_management_backend View-layer exception-template cleanup (P1-5). Use when View/Service layer 出现重复 except AppValidationError/except Exception try 块, when asked to 收敛异常模板/清理 try-except/消除重复异常处理, or after docs propose a base-class _handle_service_error that should instead delegate to the existing global exception_handler. Covers AST enumeration of try blocks, pure/paired/batch classification, whole-try deletion rules, import cleanup, grep acceptance, handler test anchoring and the adversarial review report.
---

# Backend 异常模板清理 (P1-5)

> 目标：收敛 View 层重复的 `try: ... except AppValidationError: return error_response(...) / except Exception: return error_response(...)` 模板，统一交由全局异常处理器（`core/exception_handler.py custom_exception_handler`）兜底，避免每个 View 手写一份、且 `except Exception → 400/500` 语义漂移。

## 前置事实（必须核实后开工）

1. 全局异常处理器 `core/exception_handler.py` 已实现以下映射，且有测试锚定（`core/tests/test_exception_handler.py`）：
   - `AppValidationError` → HTTP 400，`message` 透传、`error_code` 不进响应
   - `NotFoundError` → 404；`Http404` → 404
   - `PermissionError` → 403；其余未知异常 → 500（不泄漏内部细节）
2. 响应信封统一出自 `response_utils.error_response/success_response`，删除模板前后格式不变。
3. **删除的前提**：被删 try 块的唯一职责就是"捕获→转 error_response"，且转换语义不劣于全局 handler（例如 `except Exception → 400` 会把 500 级错误误报为 400，必须删）。

## 工作流

### Step 1 — AST 枚举（事实清单，禁止目测）

用 Python `ast` 枚举目标 view 文件全部 `Try` 节点，输出三列：
- 文件:行号（try 起始行）
- 唯一 except 类型列表（`except AppValidationError` / `except Exception` / 具体异常）
- 缩进深度与最近外层函数名

命令参考（Windows 下 PowerShell 需处理 GBK 输出乱码，优先把结果写入文件再 read）：
```python
import ast, sys
for path in sys.argv[1:]:
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            handlers = [h.type.id if h.type else "bare" for h in node.handlers]
            print(f"{path}:{node.lineno} {handlers}")
```

### Step 2 — 分类（pure / paired / batch）

| 类 | 判定 | 处置 |
|:--|:--|:--|
| pure | try 块只含"单业务 + 捕获→error_response"，except 后无 `raise`、无 `pass` | 整块删除，去一层缩进 |
| paired | except 内 `raise <自定义异常>`（依赖层异常转业务异常） | **保留**，只是转换链 |
| batch | 循环/多条子操作，`except` 后 `continue` 继续下一条 | **保留**，是合法批量续跑语义 |
| 其他 | 捕获后 `pass`（如 logout 容忍） | 单独评估，明确理由 |

> 判定清单必须留痕：`文件:行号 | 类 | 删除/保留 | 理由`。

### Step 3 — whole-try 删除规则

- 只删 **pure** 且 `except` 仅含 `AppValidationError` / `Exception` 的块。
- 删除 = 移除 try 与 except 结构 + 去一层缩进；**保留** try 体内的内联逻辑（早期 return、`NotFoundError` 404、嵌套 try）。
- 嵌套场景（try 里套 try）：外层为 pure 而内层承担转换语义时，只删外层，内层保留并重新缩进。
- try 体内若含 `except AppValidationError: pass`（吞咽），确认与全局语义等价后再删。
- 禁止删 batch/paired 块（见 Step 2 表）。

### Step 4 — import 清理

删除被删模板唯一使用的 `import logging`、`logger = logging.getLogger(__name__)`（若已无其他引用）及其他死 import。用 `rg "<符号>" <文件>` 确认零残留引用。

### Step 5 — grep 验收（硬性门禁）

```powershell
# 目标文件不得再有模板型捕获
rg -n "except Exception" apps/usermanagement/views/employee_view.py apps/usermanagement/views/department_view.py apps/authusermanagement/views.py
# 核对保留清单数量（batch/logout）
rg -c "except AppValidationError|except Exception" <目标文件>
```
- 保留清单与实际 grep 计数必须一致。
- `logging` / `logger` 残留为零。

### Step 6 — handler 测试锚点

- 若 `core/tests/test_exception_handler.py` 已覆盖 handler 的 400/404/403/500 映射 → 无需新增 handler 测试，仅在报告中声明"锚点已存在"。
- 若缺失或行为未断言 → 先补 handler 测试，再删 View 模板。

### Step 7 — 对抗性审查报告（自反，必须输出）

逐点自反以下风险，并在报告中给出结论：
- 被删站点是否有**行为差异**：删除前返回的 `message`（如"操作失败,请稍后重试"）与删除后全局 handler 的 detail 是否等效或更优；`error_code` 是否进过响应（删前进 → 删后消失属**契约变化**，需标注）。
- 404 语义是否保留（`Http404`/`NotFoundError` 是否仍由 handler 转 404）。
- 嵌套 try / 早期 return 是否在去缩进后语义不变。
- 批量块的 `continue` 语义未被误删。
- 前端消费的错误信封 `{code,data,message}` 是否未变。

## 验证命令（Windows / 后端根目录）

```powershell
python -m pytest <受影响 app>/tests -q            # 定向回归
python -m pytest --cov=apps.assetmanagement.services --cov-fail-under=90 -q   # Service 层门槛（若涉 Service）
python -m pytest --cov=. --cov-fail-under=80 -q   # 整体覆盖率（若删文件）
ruff check <改动文件>                              # 静态检查
python -m mypy apps config core utils              # 严格类型检查（不应新增错误）
```

## 变更记录

- v1.0 (2026-08-16)：按系统提示描述方法论重建。原 skill 文件不在盘上（加载失败），P1-5 首次执行时按描述重建流程完成 17 删 / 8 留，本文件将流程固化为可复用步骤。
