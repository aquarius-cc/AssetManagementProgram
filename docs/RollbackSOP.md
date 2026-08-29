# 发布回滚 SOP（Runbook）

> 版本：v1.0 | 关联审计项：BF-005（6.5 发布与回滚）
> 适用架构：单副本 Docker Compose 部署；蓝绿/金丝雀决策见 §5

## 1. 核心原则

1. **镜像可任意回滚，数据库只能回滚到"不可逆点下界"之后**（见 §2 回滚下界表）
2. **回滚前必须全量备份**：`docker exec asset-management-backup /backup.sh`（BF-003）
3. **禁止** `migrate <app> zero` 反向验证（根级 CT-6 红线）；预览一律用 `--plan`

## 2. 迁移不可逆点清单（回滚下界）

| App | 迁移 | 类型 | 下界说明 |
|---|---|---|---|
| notification | `0002_notification_is_active_...` | RunPython.noop 反向（已标注 ROLLBACK_NOOP_REASON） | **notification 只能回滚到 0002 之后**；跨 app 整体回滚时，notification 保持在 ≥0002 |
| assetmanagement | 0009/0010 等 | operations 已剥离或含完整 backward 函数 | 无额外限制 |

> 维护规则：新增不可逆点必须在迁移文件内加 `# ROLLBACK_NOOP_REASON:` 注释
> （migration-check.yml 步骤④硬门禁强制），并同步登记本表。

## 3. 标准回滚流程

```sh
# ① 停止 web 层（防止新旧代码与中间态 schema 交互）
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop web

# ② 全量备份（数据安全前置条件，不可跳过）
docker exec asset-management-backup /backup.sh

# ③ 数据库下行到目标版本（<target> 取各 app 回滚下界中的最小者）
docker compose run --rm web python manage.py migrate <app> <target> --plan   # 先预览
docker compose run --rm web python manage.py migrate <app> <target>

# ④ 回退镜像并重启
IMAGE_TAG=<previous-sha> docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d web

# ⑤ 恢复断言（全部通过才算回滚成功）
curl -sf http://localhost:8000/health/            # 期望 code==0
# 登录冒烟 + 核心页面人工抽检
```

若仅代码缺陷、无 schema 变更：跳过步骤③，仅执行 ④⑤。

## 4. 回滚演练

- **决策记录**：staging 环境从未真实落地（原 ci-cd.yml 的 deploy-staging 为 echo 占位，
  BF-005 已将该死配置迁移清理）。回滚演练延后至以下触发条件任一满足：
  - staging 环境落地；
  - 或采用 CI runner 内临时拉起 postgres+web 的无状态演练方案立项。
- 当前替代保障：migration-check.yml 在 PR 阶段对每个迁移做三步验证 + noop 门禁，
  将风险拦截在合并前。

## 5. 蓝绿/金丝雀决策记录

**暂缓立项**。理由：单机 compose 单副本部署，QPS 未达 OC-4 阈值(10)，
灰度基础设施收益不覆盖成本。
重新评估触发条件：多副本部署 / QPS 连续一周 >10 / 迁移 K8s。

## 6. 镜像保留策略

- CD 流水线（根 .github/workflows/ci-cd.yml）每次构建后自动 prune：
  保留最近 5 个 sha 标签 + `latest`（永不删）+ 生产当前运行版本
- 生产当前版本由部署流程写入 repo variable `PROD_IMAGE_SHA`，prune 时排除，
  确保任何时刻至少有"当前 + 前一版本"两个镜像可供回滚
- 前置要求：DOCKERHUB_TOKEN 权限须为 **Read & Delete**（默认 Read Only 无法删除）
