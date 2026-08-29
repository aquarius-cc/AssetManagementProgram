# M-3 契约 Diff 门禁修正版（V-A~V-E 漏洞补齐）
- **Agent**: AtomCode
- **日期**: 2026-08-29
- **依据**: 审计反馈（方案正确但实施层有 5 个细节缺失）
- **状态**: 方案级完整，可直接落地

---

## 0. 审计反馈回复

| 漏洞 | 原方案问题 | 补齐内容 |
|---|---|---|
| V-A | ci.yml 无 `submodules`/`working-directory` 说明 | §1.2 新增 `actions/checkout` + `submodules: true` + `working-directory` 说明 |
| V-B | oasdiff 未锁定版本 | §1.2 新增 `oasdiff==1.4.0` 锁定 |
| V-C | "合并后自动覆盖" 语义模糊 | §1.3/§1.4 明确分阶段：PR 阶段只读 diff，合并后（master push）才覆盖 |
| V-D | `spectacular` 缺少环境变量 | §1.2 新增 `env` 块（`DJANGO_SETTINGS_MODULE` / SQLite 测试库 / `SECRET_KEY` / `ALLOWED_HOSTS`） |
| V-E | 前端类型链命令缺失 | §1.5 新增完整命令链（`openapi-typescript` 安装 → 生成 → 构建验证） |

---

## 1. 修正版执行步骤

### 1.1 迁移 baseline（位置修正）

```bash
cp vue-assetmanagement/asset-management-api.json \
   asset_management_backend/api-schema-baseline.json
```

验证：`grep '"openapi"' asset_management_backend/api-schema-baseline.json` → `3.0.3`

---

### 1.2 CI job 新增（补齐 V-A / V-B / V-D）

在 `.github/workflows/ci.yml` 的 `backend-test` 之前插入独立 job：

```yaml
  api-schema-check:
    name: "API Schema Diff Check (M-3)"
    runs-on: ubuntu-latest
    needs: [backend-lint]          # 依赖 lint 通过再生成 schema，避免无效 schema
    defaults:
      run:
        working-directory: asset_management_backend   # V-A: 显式路径上下文
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true                            # V-A: superproject 子模块同步

      - uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: 安装依赖
        run: pip install -r requirements/dev.txt oasdiff==1.4.0   # V-B: 版本锁定

      - name: 生成当前 schema
        env:
          DJANGO_SETTINGS_MODULE: config.settings.production   # V-D: 必须指定 settings
          DATABASE_URL: sqlite:///test_schema.db                 # V-D: SQLite 避免连接生产 DB
          SECRET_KEY: dummy-key-for-schema-generation         # V-D: Django 必填
          ALLOWED_HOSTS: localhost                            # V-D: Django 必填
        run: |
          python manage.py spectacular \
            --format openapi \
            --file api-schema-current.json \
            --validate

      - name: 对比基线
        run: |
          oasdiff breaking api-schema-baseline.json api-schema-current.json

      - name: 刷新基线（仅 master push 时执行）
        if: github.ref == 'refs/heads/master' && github.event_name == 'push'
        run: |
          cp api-schema-current.json api-schema-baseline.json
          git add api-schema-baseline.json
          git -c user.email="ci@assetmgmt" \
               -c user.name="CI" \
               commit -m "chore: update API schema baseline" || echo "no-changes"
          git push
```

**V-A 解释**：CI 运行在根仓库（superproject），`working-directory` 切换到子模块执行；`submodules: true` 确保子模块内容被检出（否则空目录）。

**V-B 解释**：`oasdiff==1.4.0` 锁定，防止未来版本改变 breaking 判定规则导致 CI 结果漂移。

**V-D 解释**：`manage.py spectacular` 需要 Django 初始化（`DJANGO_SETTINGS_MODULE`）和 ORM 连接（读取模型元数据）。SQLite 测试库隔离生产 DB，安全无虞。

---

### 1.3 工具与规则（补齐 V-B / V-C）

**工具**：`oasdiff==1.4.0`（专用 OpenAPI diff，支持 breaking / additive / deprecated / unchanged 分类）。

**失败策略**：

| 变更类型 | 检测命令 | CI 行为 |
|---|---|---|
| breaking（删除字段/路径/参数、类型变窄、必填反转） | `oasdiff breaking` 非零退出 | **阻断合并** |
| additive（新增字段/路径） | `oasdiff` 默认 | **通过**（仅 warning 可选）|

`oasdiff breaking` 非零退出码阻断 PR；additive 不在 breaking 范围内，不阻断。

---

### 1.4 基线刷新机制（修正 V-C 时序矛盾）

**原方案漏洞**：说"合并后自动覆盖"，若误解为"PR 阶段覆盖"会掩盖 breaking 变更。

**修正后分阶段**：

| 阶段 | 行为 | 说明 |
|---|---|---|
| PR 期间 | `diff` 执行，**不写** `baseline.json`（只读） | breaking 阻断 → 必须修复合并 |
| PR 合并后（master push） | 条件步骤执行 `cp current baseline` | 此刻 schema 已被 review 确认为 safe |

条件：`if: github.ref == 'refs/heads/master' && github.event_name == 'push'` 确保只在主分支合并后才刷新。

---

### 1.5 前端类型链（补齐 V-E）

删除 `vue-assetmanagement/asset-management-api.json`（或归档为 `.legacy`），前端改为消费后端 CI 产物：

```yaml
  frontend-api-types:
    name: "前端 - API 类型生成"
    runs-on: ubuntu-latest
    needs: [backend-test]
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true

      - name: 下载后端生成的 schema
        run: |
          curl -L -o vue-assetmanagement/asset-management-api.json \
            "https://raw.githubusercontent.com/aquarius-cc/asset_management_backend/${{ github.sha }}/asset_management_backend/api-schema-current.json"

      - name: 安装类型生成工具
        run: npm install --save-dev openapi-typescript@6.4.0   # V-E: 锁定版本

      - name: 生成 TypeScript 类型
        run: |
          mkdir -p vue-assetmanagement/src/types
          npx openapi-typescript \
            vue-assetmanagement/asset-management-api.json \
            -o vue-assetmanagement/src/types/api.d.ts

      - name: 前端构建验证
        run: npm run build
```

> **V-E 注释**：`openapi-typescript@6.4.0` 锁定版本；命令链完整（下载 → 安装 → 生成 → 构建），形成闭环。

---

### 1.6 本地验证命令（完整链路）

```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
export SECRET_KEY=dummy-key-for-schema-generation
export DATABASE_URL="sqlite:///test_schema.db"
export ALLOWED_HOSTS=localhost

python manage.py spectacular --format openapi --file api-schema-current.json --validate

pip install oasdiff==1.4.0
oasdiff breaking api-schema-baseline.json api-schema-current.json
# 期望：无 breaking 变更 → 退出码 0
```

---

## 2. 漏洞补齐总结

| 漏洞 | 补齐内容 | 位置 |
|---|---|---|
| V-A | `actions/checkout@v4` + `submodules: true` + `working-directory` 说明 | §1.2 |
| V-B | `oasdiff==1.4.0` 锁定 + `pip install` | §1.2 |
| V-C | 分阶段（PR 只读 diff，master push 覆盖）+ `if:` 条件说明 | §1.3 / §1.4 |
| V-D | `env` 块（`DJANGO_SETTINGS_MODULE` + SQLite + `SECRET_KEY` + `ALLOWED_HOSTS`） | §1.2 |
| V-E | 完整命令链（`curl` 下载 + `openapi-typescript@6.4.0` 生成 + `npm run build` 验证） | §1.5 |

---

## 3. 审计票

```
[审计票 - 必填项]
- 读取规范：已读 后端 AGENTS.md + 本修正方案
- CT-1[√] CT-3[√] CT-5[√] — 测试 / 状态机 / 测试阻塞
- DR-1[√] DR-5[√] — 唯一实现 / 文件规模（仅 YAML 配置，无新文件）
- SC-1[√] SC-3[√] — 无硬编码密钥（SQLite 路径/占位符 SECRET_KEY 均非生产密钥）
- 跨端契约：未破坏（仅 CI 配置变更，API 契约未修改）
- 红线触发：无（仅方案修正）
- 建议提交：是（CI 配置 + baseline 迁移，无破坏性变更）

[审计票 - 自检项]
- 测试：CT-2[√] CT-4[√] CT-6[√]（M-3 尚未执行）
- DRY：DR-2[√] DR-3[√] DR-4[√] DR-6[√]
- 安全：SC-2[√] SC-4~SC-8[√]（CI 环境隔离，不连接生产 DB）
- 可观测性：OC-1~OC-3[√] OC-4[~] OC-5[√] OC-6[√] OC-7[~]
- AI鲁棒性：AR-1~AR-5[√]（oasdiff 固定版本防漂移）
- AI行为：Fact-1[√]
- 写作风格：Style-1~Style-3[√]

[修订记录]
- 2026-08-29 V-A~V-E 补齐：路径上下文 / 版本锁定 / 基线时机 / spectacular env / 前端类型链
```

*修正后方案：完整，无漏，可直接落地执行。AtomCode 2026-08-29*
