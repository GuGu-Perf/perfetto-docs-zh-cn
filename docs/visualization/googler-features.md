# Googler 特性与第三方 Cookie

使用 [Perfetto UI](https://ui.perfetto.dev) 时，Googler 可以使用一系列内部特性，
这些特性以 Google 特有的工作流扩展了 UI，包括：

- **内部宏** — 预配置的命令序列和查询，用于分析内部 trace，可在命令面板
  （`Ctrl+Shift+P` / `Cmd+Shift+P`）中使用。
- **内部 SQL 模块** — 以内部方式打包和分发的共享 PerfettoSQL 模块，可通过
  `INCLUDE PERFETTO MODULE` 访问。
- **Proto descriptors** — 自动解码 trace 中内嵌的内部 protobuf 消息。
- **Trace 共享** — 直接集成到 UI 中的内部 trace 上传与共享特性。

这些特性通过连接位于
`https://perfetto-gae-internal.googleplex.com` 的内部 Google extension server
提供。

## 为什么需要第三方 Cookie

Perfetto UI 托管在 `https://ui.perfetto.dev`，而内部 extension server 托管在
`https://perfetto-gae-internal.googleplex.com`。由于这两个 origin 的域名不同，
Perfetto UI 向 extension server 发起的浏览器请求是**跨站（第三方）**请求。

对内部 extension server 的认证依赖企业单点登录（SSO）会话 Cookie。如果你的浏览器
阻止第三方 Cookie，这些认证 Cookie 将不会被发送，导致请求以 HTTP 403 或 CORS
错误失败。其后果是：

1. 内部 extension server 无法加载其 manifest、宏或 SQL 模块。
2. UI 无法验证你的内部用户状态，从而禁用内部 trace 共享等 Googler 专属特性。

## 如何在 Chrome 中启用第三方 Cookie

要启用对内部特性的访问，你需要为内部 extension server 允许第三方 Cookie。

### 方式 1：在 Chrome 设置中添加站点例外（推荐）

你不需要全局允许第三方 Cookie，可以添加特定的站点例外：

1. 打开 Chrome 设置，访问 `chrome://settings/cookies` 或
   `chrome://settings/trackingProtection`（或依次进入 **设置** → **隐私与安全** →
   **第三方 Cookie** / **跟踪保护**）。
2. 在**允许使用第三方 Cookie 的网站**（或**允许使用第三方 Cookie**）下，点击
   **添加**。
3. 输入 `https://ui.perfetto.dev` 并点击**添加**。
4. 重新加载 [https://ui.perfetto.dev](https://ui.perfetto.dev)。

### 方式 2：通过 Chrome 地址栏允许

1. 访问 [https://ui.perfetto.dev](https://ui.perfetto.dev)。
2. 找到表示第三方 Cookie 被阻止的**眼睛图标**（或地址栏旁的站点控制图标）。
3. 点击该图标，将**第三方 Cookie** 切换为**允许**（针对 `ui.perfetto.dev`）。
4. 按提示重新加载页面。

## 验证你的配置

启用第三方 Cookie 后：

1. 打开 [https://ui.perfetto.dev](https://ui.perfetto.dev)。
2. 打开**设置**（侧边栏中的齿轮图标），进入**扩展服务器**。
3. 你应该看到内部 extension server 已启用，并列出已加载的可用模块（例如
   `default`）。
4. 按 `Ctrl+Shift+P`（Mac 上为 `Cmd+Shift+P`）打开命令面板。Google 内部宏应
   出现在命令列表中。
5. 查看 trace 时，内部 trace 共享选项将可用。

## 故障排除

- **服务器仍显示错误：** 在单独的标签页中直接访问
  `https://perfetto-gae-internal.googleplex.com`，确认你的 SSO 会话处于活跃状态，
  然后重新加载 `https://ui.perfetto.dev`。
- **在企业网络/VPN 上仍被阻止：** 确保你已连接企业网络或 VPN，使 `googleplex.com`
  端点可达。
- 关于 extension server 机制与故障排除的更多细节，参见
  [扩展服务器](/docs/visualization/extension-servers.md)。
