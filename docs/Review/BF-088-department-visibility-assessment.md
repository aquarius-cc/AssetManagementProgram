# BF-088 立项评估：跨部门部门可见性（`get_department_by_jobcode`）

- **评估日期**：2026-11-19（段 6，账本校准 + 旧账处置批）
- **原状态**：【观察项·未评估】（登记于 BF-048 批次，从未立项）
- **评估结论**：**无缺陷，零代码改动** —— 详见 §四
- **来源**：`test_employee_rbac_scope.py:22` 文档串「跨部门部门可见性另立评估」

## 一、评估对象与调用面

`EmployeeQueryActions.get_department_by_jobcode`（`apps/usermanagement/views/employee_query_actions.py:234`，
`url_path="(?P<employee_jobcode>[^/.]+)/department"`，即 `GET /users/employees/{jobcode}/department/`）：
按工号返回员工所在部门（department_code / department_name / level / parent_code）。

**全仓调用方仅此 1 处**（`rg get_department_by_jobcode` 全量核实：定义 + 两处测试文档串引用，无第二业务调用点）。
该端点非「部门树可见性」面（BF-048 的部门可见性三态语义在 `core/department_scope.py`），
而是「按工号反查所在部门」的点查端点，泄露面 = 单个工号是否存在于调用者可见范围。

## 二、行级语义取证（P3-8/OP-19）

- **现状**：`employee_query_actions.py:247` 已走 `self.get_queryset().filter(employee_jobcode=...)`（行级隔离
  queryset 单一入口），跨部门工号与不存在同形 **404**（不泄露存在性）。
- **来源批次**：P3-8/OP-19（BF-181 批次落地）——替代了原先直调全局
  `EmployeeSelector.get_employee_by_jobcode` 的行级面泄露路径。
- **端点级回归锚**：`test_employee_rbac_scope.py::test_department_by_jobcode_cross_dept_404`
  （本批补齐；先红后绿——临时回退 `get_queryset()` 行证红，恢复转绿，见 BF-170 收口记录）。

## 三、与既有裁决的边界

| 关联项 | 关系 |
|:---|:---|
| BF-048（员工域行级隔离） | 同源语义（三态 `get_department_codes_for_user`）；本端点消费其 queryset，不新增语义 |
| B-24（部门可见性三态） | B-24 管「部门树可见性」（`is_department_visible`）；本端点属「员工可见性 → 传递出部门」，消费行级取数后不额外套部门可见性——与员工域其余 8 端点同构 |
| P3-8/OP-19 | 本端点行级化的落地批；本评估仅确认无回归面 |

## 四、结论

1. **调用方 1 处**且已走 `self.get_queryset()` 行级取数（P3-8/OP-19），跨部门工号 404 有端点级锚（先红后绿）。
2. **零代码缺陷**：无需改动；「另立评估」的悬置状态就此收敛。
3. **文档漂移订正**：`test_employee_rbac_scope.py:22` 的「跨部门部门可见性另立评估」随本评估关闭同步订正。
4. 账本 BF-088 →【已关闭】（评估完成、零代码缺陷）。
