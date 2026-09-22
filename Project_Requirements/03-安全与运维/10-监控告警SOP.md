# 监控告警 SOP

**版本：V1.0**
**日期：2026-07-09**

---

## 1. 告警分级

| 级别 | 定义 | 响应时间 | 升级机制 |
|:---|:---|:---|:---|
| P0 严重 | 服务不可用/数据丢失 | 5 分钟内响应 | 15 分钟无人处理 → 通知技术总监 |
| P1 重要 | 核心功能受损 | 30 分钟内响应 | 1 小时无人处理 → 通知技术总监 |
| P2 一般 | 非核心功能异常 | 4 小时内响应 | 次日未处理 → 知会负责人 |
| P3 提示 | 潜在风险/优化建议 | 下一工作日 | 无需升级 |

---

## 2. 告警规则

| 告警项 | 条件 | 级别 | 接收人 |
|:---|:---|:---:|:---|
| API 响应时间劣化 | P95 > 3秒 | P1 | 后端开发 |
| API 错误率飙升 | 5xx 错误率 > 5% | P0 | 后端开发 + 运维 |
| 数据库连接池耗尽 | 使用率 > 80% | P0 | DBA + 运维 |
| 数据库慢查询 | 单次查询 > 2秒 | P2 | 后端开发 |
| 磁盘使用率 | > 80% | P1 | 运维 |
| 内存使用率 | > 90% | P1 | 运维 |
| 服务健康检查失败 | /health 连续 3 次失败 | P0 | 运维 |
| JWT 令牌异常 | 刷新失败率 > 10% | P1 | 后端开发 |
| 业务操作失败率 | 出库/回收失败率 > 5% | P1 | 后端开发 |

---

## 3. 监控看板

### 3.1 核心指标看板

| 面板 | 指标 | 数据源 |
|:---|:---|:---|
| 请求量 | QPS、总请求数 | Prometheus |
| 响应时间 | P50/P90/P95/P99 | Prometheus |
| 错误率 | 4xx/5xx 比例 | Prometheus |
| 数据库 | 连接数、慢查询数、锁等待 | PostgreSQL metrics |
| 业务 | 出库/回收/报废操作量 | 自定义指标 |

### 3.2 告警通知渠道

| 渠道 | 用途 | 配置 |
|:---|:---|:---|
| 钉钉/飞书 Webhook | P0/P1 实时通知 | 机器人 Webhook URL |
| 邮件 | P2/P3 每日汇总 | 邮件列表 |
| 短信 | P0 紧急通知 | 短信网关 |

### 3.3 Prometheus 告警规则示例

```yaml
# alerting-rules.yml
groups:
  - name: asset-management
    rules:
      # API 响应时间 P95 > 3秒
      - alert: HighLatencyP95
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 3
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "API P95 响应时间超过 3 秒"

      # 5xx 错误率 > 5%
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) > 0.05
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "5xx 错误率超过 5%"

      # 数据库连接池使用率 > 80%
      - alert: DBConnectionPoolHigh
        expr: db_connections_active / db_connections_max > 0.8
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "数据库连接池使用率超过 80%"
```

### 3.4 Grafana Dashboard 关键面板

| 面板 | PromQL 查询 |
|:---|:---|
| QPS | `rate(http_requests_total[5m])` |
| P95 延迟 | `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))` |
| 错误率 | `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])` |
| 活跃数据库连接 | `db_connections_active` |

---

## 4. 常见告警排查手册

### 4.1 API 响应时间劣化

```
1. 检查是否有慢查询 → SELECT pid, state, query FROM pg_stat_activity WHERE state = 'active';
2. 检查数据库连接数 → SELECT numbackends FROM pg_stat_database;
3. 检查是否有大批量操作 → 查看最近的批量导入/导出任务
4. 检查 Redis 是否正常 → redis-cli ping
5. 如无法定位 → 扩容应用实例 / 重启服务
```

### 4.2 数据库连接池耗尽

```
1. 检查是否有长事务 → SELECT pid, now() - xact_start AS duration FROM pg_stat_activity WHERE state = 'active';
2. 检查是否有锁等待 → SELECT * FROM pg_locks WHERE NOT granted;
3. 检查应用是否有连接泄漏 → 监控连接数变化趋势
4. 紧急处理 → SELECT pg_terminate_backend(pid); / 重启应用
```

### 4.3 服务健康检查失败

```
1. 检查服务进程是否存在 → systemctl status asset-management
2. 检查端口是否监听 → netstat -tlnp | grep 8000
3. 检查日志 → journalctl -u asset-management --since "10 minutes ago"
4. 紧急处理 → 重启服务
```

---

## 5. On-call 轮值

| 周 | 值班人 | 联系方式 |
|:---|:---|:---|
| 第 1 周 | 开发者 A | 138-xxxx-xxxx |
| 第 2 周 | 开发者 B | 139-xxxx-xxxx |
| 第 3 周 | 开发者 C | 137-xxxx-xxxx |
| 第 4 周 | 开发者 D | 136-xxxx-xxxx |

---

## 6. 备份告警链路验证（BF-003 收口 2026-09-22）

> 目标：验证 textfile 备份指标从 `backup_status_data` 共享卷 → node_exporter → Prometheus → Alertmanager → 飞书的完整链路。

### 6.1 node-exporter 拉起与指标采集

```bash
# 1. 启动 node-exporter（monitoring 栈预备条件：主 compose 已先行 up）
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d node-exporter

# 2. 确认 textfile 指标存在（backup_status.prom 由备份容器 backup_status_write 写入）
curl -s http://127.0.0.1:9100/metrics | grep -E 'backup_last_success_timestamp|backup_failures_total'

# 3. Prometheus 侧确认真实采集（Grafana/PromQL 或直接 HTTP API）
#    http://127.0.0.1:9090/api/v1/query?query=backup_last_success_timestamp
```

预期：两条 `backup_*` 指标在 :9100 与 :9090 均出现且值非空。若缺失，检查：
- 备份容器是否已将 `backup_status.prom` 写入 `/data/backup_status`（docker logs backup）
- 共享卷 `backup_status_data` 是否同时挂载于 backup(:199) 与 node-exporter(:72)

### 6.2 失败注入与告警送达

```bash
# 1. 人为触发一次备份失败（错误 S3 配置使 exit 1 并写 backup_failures_total+1）
docker exec asset-management-backup sh -c 'S3_BUCKET=no-such-bucket-demo /backup.sh' || echo "expected failure"

# 2. 观察告警：约 5m 后 BackupFailed(critical) 应触发并推送到飞书（🔴 红卡）
# 3. 恢复正常（S3_BUCKET 还原后跑一次成功备份）→ BackupFailed 自动 resolve → 飞书 "🟢 告警恢复" 绿卡
```

前置条件已具备：alertmanager.yml:32/:37 `send_resolved: true`；adapter app.py:57-63 渲染 resolved 恢复卡（test_app.py:30 已覆盖）。

### 6.3 去重与静默说明

- 告警按 `group_by: [alertname, severity]` 分组（alertmanager.yml:13），`repeat_interval` 4h(warning)/1h(critical) —— 状态变化才发新通知，静默期不重复轰炸。
- 数据源自活守卫：`BackupMetricsMissing`（alert_rules.yml M-5C 组）监控备份指标本身，链路失效时报 "备份状态指标缺失"，防止 BackupOverdue/BackupFailed 静默休眠。

---

## 修订历史

| 版本 | 日期 | 修订内容 |
|:---|:---|:---|
| V2.0 | 2026-09-22 | 新增 §6 备份告警链路验证（BF-003 收口） |
| V1.0 | 2026-07-09 | 初始版本 |
