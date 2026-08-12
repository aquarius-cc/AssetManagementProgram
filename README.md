# 资产管理系统 (Asset Management System)

> 基于前后端分离架构的企业级资产全生命周期管理平台

---

## 项目概述

本项目为企业提供完整的资产生命周期管理解决方案，覆盖资产从入库、领用、外借、回收、损坏、报废的全流程管理。

### 核心能力

- **全生命周期管理** - 资产入库、领用、外借、回收、损坏、遗失、报废
- **审计留痕** - 所有操作自动记录，满足合规要求
- **细粒度权限** - RBAC + 行级数据隔离
- **事务安全** - 关键操作使用 `@transaction.atomic`
- **RESTful API** - OpenAPI 自动文档

---

## 技术栈

| 层级 | 技术选型 | 版本 |
|------|---------|------|
| **前端框架** | Vue 3 + Element Plus | Vue 3.5+ / Element Plus 2.10+ |
| **前端构建** | Vite + TypeScript | Vite 8.0+ / TypeScript 6.0+ |
| **状态管理** | Pinia | 3.0+ |
| **后端框架** | Django REST Framework | Django 6.0 / DRF 3.16 |
| **数据库** | MySQL | 8.0+ |
| **认证** | JWT (SimpleJWT) | - |
| **API文档** | drf-spectacular | - |

---

## 项目结构

```
AssetManagementProgram/
├── asset_management_backend/     # 后端 (Django REST Framework)
│   ├── apps/                     # 业务应用
│   │   ├── assetmanagement/      # 资产核心模块
│   │   ├── authusermanagement/   # 认证授权模块
│   │   ├── notification/         # 通知服务模块（HTTP + WebSocket）
│   │   ├── usermanagement/       # 用户管理模块
│   │   └── unregisteredasset/    # 未登记资产模块
│   ├── core/                     # 公共基类和工具
│   ├── utils/                    # 通用工具函数
│   ├── config/                   # Django 配置
│   ├── docs/                     # 后端文档
│   └── manage.py
│
├── vue-assetmanagement/          # 前端 (Vue 3 + Element Plus)
│   ├── src/
│   │   ├── components/           # 公共组件
│   │   ├── composables/          # 组合式函数
│   │   ├── views/                # 页面视图
│   │   ├── stores/               # Pinia 状态管理
│   │   ├── router/               # 路由配置
│   │   ├── utils/                # 工具函数
│   │   └── types/                # TypeScript 类型定义
│   └── package.json
│
├── Rules_Fiels/                 # 项目规范文档
├── AGENTS.md                     # AI 执行引擎配置
└── README.md                     # 本文件
```

---

## 快速开始

### 环境要求

- **后端**: Python 3.12+ / MySQL 8.0+
- **前端**: Node.js 20.19+ 或 22.12+ / npm 或 pnpm

### 后端启动

```bash
# 1. 进入后端目录
cd asset_management_backend

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS

# 3. 安装依赖
pip install -r requirements/dev.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填写数据库配置

# 5. 数据库迁移
python manage.py migrate

# 6. 创建超级管理员（可选）
python manage.py createsuperuser

# 7. 启动开发服务器
python manage.py runserver
```

### 前端启动

```bash
# 1. 进入前端目录
cd vue-assetmanagement

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev
```

---

## 文档导航

> 所有需求设计文档统一存放于 `Project_Requirements/` 目录，按类别分文件夹组织。
> **完整索引请查看 [Project_Requirements/INDEX.md](Project_Requirements/INDEX.md)**

### 业务需求 (`Project_Requirements/01-业务需求/`)

| 文档 | 说明 |
|------|------|
| [01-需求规格说明书.md](Project_Requirements/01-业务需求/01-需求规格说明书.md) | 项目概览、架构、RBAC 权限、功能模块清单 |
| [07-功能需求与验收标准.md](Project_Requirements/01-业务需求/07-功能需求与验收标准.md) | 15 模块 84 条 Given/When/Then 验收条件 |
| [08-前端页面与交互设计.md](Project_Requirements/01-业务需求/08-前端页面与交互设计.md) | 页面路由、交互规范、组件规范 |
| [09-数据导入导出规范.md](Project_Requirements/01-业务需求/09-数据导入导出规范.md) | 导入模板、导出规则、脱敏策略 |
| [10-用户培训手册.md](Project_Requirements/01-业务需求/10-用户培训手册.md) | 各角色操作指南、FAQ |

### 技术设计 (`Project_Requirements/02-技术设计/`)

| 文档 | 说明 |
|------|------|
| [02-数据模型设计.md](Project_Requirements/02-技术设计/02-数据模型设计.md) | 17 张表字段、外键、索引、枚举 |
| [03-业务规则与状态机.md](Project_Requirements/02-技术设计/03-业务规则与状态机.md) | 状态机 FSM 代码、转换规则、异常处理 |
| [04-API接口规范.md](Project_Requirements/02-技术设计/04-API接口规范.md) | 12 模块全端点、幂等性、版本策略 |
| [05-服务层设计.md](Project_Requirements/02-技术设计/05-服务层设计.md) | Selector/Service 完整实现代码 |
| [08-部署与环境配置.md](Project_Requirements/02-技术设计/08-部署与环境配置.md) | Docker 编排、环境变量、初始化脚本 |
| [09-数据字典.md](Project_Requirements/02-技术设计/09-数据字典.md) | 全部 17 张表字段级校验规则 |
| [10-前后端联调规范.md](Project_Requirements/02-技术设计/10-前后端联调规范.md) | Mock 方案、联调流程 |

### 安全与运维 (`Project_Requirements/03-安全与运维/`)

| 文档 | 说明 |
|------|------|
| [06-非功能需求与运维.md](Project_Requirements/03-安全与运维/06-非功能需求与运维.md) | 性能指标、索引清单、安全要求 |
| [07-安全威胁模型.md](Project_Requirements/03-安全与运维/07-安全威胁模型.md) | OWASP 评估、脱敏规则、安全基线 |
| [08-数据备份恢复方案.md](Project_Requirements/03-安全与运维/08-数据备份恢复方案.md) | 备份策略、恢复流程、RTO/RPO |
| [09-变更管理与发布流程.md](Project_Requirements/03-安全与运维/09-变更管理与发布流程.md) | 分支策略、PR 规范、发布流程 |
| [10-监控告警SOP.md](Project_Requirements/03-安全与运维/10-监控告警SOP.md) | 告警分级、排查手册、On-call |

### 开发规范 (`Rules_Fiels/`)

| 文档 | 说明 |
|------|------|
| [backend-business-rules.md](Rules_Fiels/backend-business-rules.md) | 后端业务规范 B1-B10、BR-1~BR-7 |
| [backend-testing-rules.md](Rules_Fiels/backend-testing-rules.md) | 后端测试规范 T1-T8、变异测试 |
| [frontend-business-rules.md](Rules_Fiels/frontend-business-rules.md) | 前端设计令牌 F1-F15、FR-1~FR-7 |
| [frontend-testing-rules.md](Rules_Fiels/frontend-testing-rules.md) | 前端测试规范 T8-T15 |

---

## 开发规范

### 代码质量门禁

#### 后端

```bash
ruff check .           # 代码规范检查
mypy . --strict        # 类型检查
python manage.py test  # 单元测试
```

#### 前端

```bash
npm run type-check     # TypeScript 类型检查
npm run lint           # ESLint 代码规范
npm run test           # Vitest 单元测试
```

### 分层架构（后端）

```
Model → Serializer → Service → Selector → View
```

- **Model**: 数据模型定义
- **Serializer**: 数据序列化/反序列化
- **Service**: 业务逻辑层（事务控制）
- **Selector**: 数据查询层（QuerySet 封装）
- **View**: API 端点（权限控制、参数校验）

### 状态流转（资产）

```
                              ┌─────────────────────────────────────┐
                              │                                     │
in_store ──outasset──→ in_use ──recycle──→ recycled_pending        │
    │                    │                    │                     │
    │ mark_broken        │ mark_broken        │ mark_broken         │
    │ mark_lost          │ mark_lost          │ mark_lost           │
    ▼                    ▼                    ▼                     │
 broken/lost         broken/lost          broken/lost              │
    │                    │                    │                     │
    │ repair             │                    │                     │
    ▼                    │                    │                     │
 repairing ──repair_done──┘                    │                     │
    │                                         │                     │
    │ repair_failed                           │                     │
    └─────────────────────────────────────────┘                     │
              │                                                    │
              ▼                                                    │
           damaged ──approve──→ scrapped                           │
              │                                                    │
              └──reject──→ broken/lost ────────────────────────────┘

找回: lost ──found_and_return──→ recycled_pending（重新进入发放池）
```

> 语义约定：维修完成/找回的资产（已使用过）回到 `recycled_pending` 待发放池；`in_store` 仅表示首次入库的新资产。

---

## 安全边界

| 场景 | 动作 |
|------|------|
| 跨目录修改 | 触发 `[HALT]`，请求确认 |
| 敏感配置变更 | 触发 `[HALT]`，请求确认 |
| 数据库结构变更 | 触发 `[HALT]`，请求确认 |

---

## 许可证

本项目采用 Apache License 2.0 开源许可证。

---

> **重要**: AI 代理在任务开始前必须阅读 `AGENTS.md` 文件，遵循项目开发规范。
