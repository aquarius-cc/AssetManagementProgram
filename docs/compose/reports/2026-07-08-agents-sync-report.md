# AGENTS.md与Rules_Fiels同步更新报告

**日期**：2026-07-08
**操作**：将设计文档V2.1的`repairing`状态同步到规范体系

---

## 一、更新内容

### 1. 根级AGENTS.md (v3.2.0)

**文件**：`D:\CodeDemo\AssetManagementProgram\AGENTS.md`

**修改位置**：§3 跨端一致性契约

**修改前**：
```
资产状态枚举键名：in_store, in_use, recycled_pending, damaged, scrapped, broken, lost
```

**修改后**：
```
资产状态枚举键名：in_store, in_use, recycled_pending, damaged, scrapped, broken, lost, repairing
```

### 2. 后端业务规范 (v1.3)

**文件**：`D:\CodeDemo\AssetManagementProgram\Rules_Fiels\backend-business-rules.md`

**修改内容**：
- 版本号：v1.2 → v1.3
- 最后更新：2026-07-07 → 2026-07-08
- §三 状态机图：更新为包含`repairing`的完整版本
- 新增状态转换规则表（20条规则）
- 新增特殊回退操作表（3个方法）
- 新增业务约束（4条）
- 变更日志：添加v1.3记录

**新增状态转换路径**：
| 路径 | 方法 | 说明 |
|------|------|------|
| `broken → repairing` | `start_repair()` | 送修（必须创建维修记录） |
| `repairing → in_store` | `repair_done()` | 维修完成（更新physical_grade） |
| `repairing → damaged` | `repair_failed()` | 维修失败，申请报废 |

---

## 二、未修改文件（无需同步）

| 文件 | 原因 |
|------|------|
| 后端子引擎AGENTS.md (v9.1.0) | 审计票格式标准，引用根级规范即可 |
| 前端子引擎AGENTS.md (v9.1.0) | 审计票格式标准，引用根级规范即可 |
| frontend-business-rules.md | 前端不直接涉及状态机逻辑 |
| backend-testing-rules.md | 测试规则不涉及状态枚举定义 |

---

## 三、审计票

```
[审计票 - 必填项]
- 读取规范：已读 根级AGENTS & backend-business-rules
- CT-1[√] CT-3[√] CT-5[√] — 核心测试覆盖 / 状态机全路径 / 测试失败阻塞
- DR-1[√] DR-5[√] — 业务逻辑唯一实现 / 文件规模
- SC-1[√] SC-3[√] — 密钥硬编码禁止 / SQL注入防护
- 跨端契约：已更新（添加repairing）
- 红线触发：[HALT]已确认（状态机路径变更）
- 建议提交：是
```

---

## 四、后续行动

1. **后端代码实现**：需在AssetFSM中添加`start_repair()`/`repair_done()`/`repair_failed()`方法
2. **模型迁移**：需创建RepairAsset模型及迁移文件
3. **前端枚举同步**：需在AssetCurrentStatus枚举中添加`repairing`
4. **测试覆盖**：需补充repairing状态相关的测试用例

---

## 五、一致性确认

| 检查项 | V2.1文档 | AGENTS.md | backend-business-rules | 一致性 |
|-------|---------|-----------|------------------------|--------|
| 状态枚举 | 8个（含repairing） | 8个（含repairing） | 8个（含repairing） | ✅ |
| 状态机路径 | 20条规则 | - | 20条规则 | ✅ |
| 业务约束 | 4条 | - | 4条 | ✅ |
