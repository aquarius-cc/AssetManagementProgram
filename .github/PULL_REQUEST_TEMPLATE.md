<!-- 密钥扫描判读规则（SC-2）：详见 asset_management_backend/CONTRIBUTING.md §3.1 -->

## 密钥扫描失败判读（如 CI「密钥泄露扫描」红灯）

- **引号形态 + tests 路径未登记值**：新测试夹具值需登记 SHA-256 指纹至
  `scripts/secret_fingerprints.json` 的 `allowlist`（登记流程见
  `asset_management_backend/CONTRIBUTING.md` §3.1），并在下方说明用途。
- **已轮换凭据回流（第三道）**：无任何豁免通道，立即删除并确认凭据已轮换。
- **非 tests 路径疑似密钥**：移除后重新推送；如确认误报请在下方说明。

### 扫描判读说明（如有）

<!-- 说明误报依据 / 夹具值用途 / 凭据轮换确认 -->
