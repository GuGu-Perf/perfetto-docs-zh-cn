# 扩展服务器

Extension servers 是 HTTP(S) 端点，用于向 Perfetto UI 分发共享的
[macros](/docs/visualization/ui-automation.md)、SQL 模块和 proto
descriptors。它们是团队和组织共享可重用 trace 分析工作流的推荐方式。

## 为什么使用 extension servers？

如果没有 extension servers，共享 macros 或 SQL 模块意味着在团队成员之间复制粘贴 JSON。这无法扩展：定义会过时，新团队成员会错过它们，而且没有单一的事实来源。Extension servers 通过让你在一个地方托管扩展并让每个人自动加载它们来解决这个问题。

## 关键属性

Extension servers 是**可选且从不承载负载的**。Perfetto UI 在没有任何配置服务器的情况下完全工作 —— 服务器只提供可选的增强功能。

所有扩展都是**声明式且安全的**：

- **Macros** 是 UI 命令的序列 —— 不执行 JavaScript。
- **SQL 模块**在 trace processor 现有的沙箱中运行。
- **Proto descriptors**是二进制类型定义（仅数据）。

## Extension servers 提供什么

### 宏

从 extension servers 加载的 macros 出现在命令面板
(`Ctrl+Shift+P`) 中，与本地定义的 macros 一起。它们显示服务器和模块名称作为源标签，因此你可以知道每个 macro 来自哪里。

请参阅 [Commands and Macros](/docs/visualization/ui-automation.md) 了解 macros 的工作原理。

### SQL 模块

SQL 模块可在查询编辑器和
[startup commands](/docs/visualization/ui-automation.md) 中使用。使用以下方式使用它们：

```sql
INCLUDE PERFETTO MODULE <namespace>.<module_name>;
```

例如，如果具有命名空间 `com.acme` 的服务器提供了一个名为
`com.acme.startup` 的模块，你可以编写：

```sql
INCLUDE PERFETTO MODULE com.acme.startup;
```

请参阅
[PerfettoSQL Getting Started](/docs/analysis/perfetto-sql-getting-started.md)
了解有关 SQL 模块的更多信息。

### Proto 描述符

Proto descriptors 允许 UI 解码和显示嵌入在 traces 中的自定义 protobuf 消息，而无需将 `.proto` 文件编译到 UI 中。这些在 extension server 加载时自动注册。

## Extension servers 如何工作

每个 extension server 托管一个**manifest**，声明：

- 服务器的 **name** 和 **namespace**（例如，`com.acme`）
- 它支持哪些 **features**（macros、SQL 模块、proto descriptors）
- 哪些 **modules** 可用（扩展的命名集合）

当 Perfetto UI 启动时，它从每个配置的服务器获取 manifest，然后从启用的模块加载扩展。如果服务器无法访问或返回错误，则跳过它 —— 其他服务器和 UI 的其余部分不受影响。

### 模块

Extension servers 将内容组织成 **modules**。例如，公司服务器可能提供：

- `default` —— 通用 macros 和 SQL 模块
- `android` —— Android 特定的分析工作流
- `chrome` —— Chrome 渲染性能工具

当你添加服务器时，会自动选择 `default` 模块。其他模块是可选的。

### 命名空间

来自服务器的所有 macro IDs 和 SQL 模块名称必须以服务器的
namespace（例如，`com.acme.`）开头。这可以防止配置多个 extension servers 时的命名冲突。UI 强制执行此操作并拒绝违反约定的扩展。

### 生命周期

扩展在 **UI 启动时加载一次**。如果你更改 extension server 配置（添加/删除服务器、更改模块），你需要重新加载页面以使更改生效。

## 服务器类型和认证

Extension servers 有两种类型：

- **GitHub** —— 托管在 GitHub 仓库中的扩展。UI 直接从 `raw.githubusercontent.com`（公共仓库）或 GitHub API（私有仓库）获取文件。这是最简单的选项 —— 不需要服务器基础设施。
- **HTTPS** —— 托管在任何 HTTPS 端点上的扩展：静态文件主机
  （GCS、S3、nginx）、动态服务器（Flask、Express）或公司
  基础设施。服务器必须设置
  [CORS headers](/docs/visualization/extension-server-protocol.md#cors-requirements)
  以允许 Perfetto UI 从中获取。

每种服务器类型支持不同的认证方法：

| 服务器类型 | 认证方法 | 何时使用 |
|-------------|-------------|-------------|
| GitHub | 无 | 公共仓库 |
| GitHub | Personal Access Token | 私有仓库 |
| HTTPS | 无 | 公开可访问的服务器 |
| HTTPS | Basic Auth | 受用户名/密码保护的服务器 |
| HTTPS | API Key | Bearer token、X-API-Key 或自定义 header |
| HTTPS | SSO | 基于 cookie 认证的公司 SSO |

对于大多数用例（公共 GitHub 仓库 + 链接共享），不需要认证。请参阅
[protocol reference](/docs/visualization/extension-server-protocol.md#authentication-headers)
了解 UI 为每种认证类型发送的确切 headers。

## 使用 GitHub 创建扩展

创建 extension server 的最简单方法是使用 GitHub 仓库 —— 不需要自定义服务器基础设施。

### Fork 模板仓库

首先 fork（或导入，用于私有副本）
[perfetto-test-extensions](https://github.com/LalitMaganti/perfetto-test-extensions)
GitHub 上的模板仓库。这为你提供了一个现成的结构，带有 GitHub Action，可在推送时自动构建端点文件。

### 配置你的服务器

编辑 `config.yaml` 以设置扩展的名称和命名空间：

```yaml
name: My Team Extensions
namespace: com.example.myteam
```

**namespace** 必须对你的组织是唯一的，并遵循反向域名
表示法。所有 macro IDs 和 SQL 模块名称必须以这个命名空间开头。

你还可以配置服务器提供的模块。默认情况下，模板
包括一个 `default` 模块。如果你想按团队组织扩展，可以添加更多
或主题：

```yaml
name: My Team Extensions
namespace: com.example.myteam
modules:
  - id: default
    name: Default
  - id: android
    name: Android
  - id: chrome
    name: Chrome
```

### 添加 SQL 模块

在 `src/{module}/sql_modules/` 下添加 `.sql` 文件。文件名根据你的命名空间确定 SQL 模块名称：

- `src/default/sql_modules/helpers.sql` 变为
  `INCLUDE PERFETTO MODULE com.example.myteam.helpers;`
- `src/default/sql_modules/foo/bar.sql` 变为
  `INCLUDE PERFETTO MODULE com.example.myteam.foo.bar;`

你可以将 SQL 文件组织到子目录中 —— 每个路径组件都成为模块名称的点分隔部分。

请参阅
[PerfettoSQL Getting Started](/docs/analysis/perfetto-sql-getting-started.md)
了解如何编写 SQL 模块。

### 添加 macros

在 `src/{module}/macros/` 下添加 `.yaml` 或 `.json` 文件。每个 macro 有一个
`id`、一个显示 `name` 和一个 `run` 命令列表。

YAML 示例 (`src/default/macros/show_long_tasks.yaml`)：

```yaml
id: com.example.myteam.ShowLongTasks
name: Show Long Tasks
run:
  - id: dev.perfetto.RunQueryAndShowTab
    args:
      - "SELECT * FROM slice WHERE dur > 50000000"
```

等效的 JSON (`src/default/macros/show_long_tasks.json`)：

```json
{
  "id": "com.example.myteam.ShowLongTasks",
  "name": "Show Long Tasks",
  "run": [
    {
      "id": "dev.perfetto.RunQueryAndShowTab",
      "args": ["SELECT * FROM slice WHERE dur > 50000000"]
    }
  ]
}
```

Macro IDs 必须以你的命名空间开头（例如，`com.example.myteam.`）。请参阅
[Commands Automation Reference](/docs/visualization/commands-automation-reference.md)
了解 macros 中可用的完整命令列表。

### 推送和部署

将你的更改推送到 `main`。包含的 GitHub Action 构建生成的
端点文件（`manifest`、`modules/*/macros` 等）并自动提交它们。

## 在 Perfetto UI 中添加 extension server

### 添加 GitHub 服务器

1. 转到 **Settings**（侧边栏中的齿轮图标）并滚动到 **Extension
   Servers**，或打开
   [the settings directly](https://ui.perfetto.dev/#!/settings/dev.perfetto.ExtensionServers)。
2. 点击 **Add Server** 并选择 **GitHub**。
3. 以 `owner/repo` 格式输入仓库（例如，
   `my-org/perfetto-extensions`）。
4. 在 **Ref** 字段中输入分支或标签（例如，`main`）。
5. UI 获取 manifest 并显示可用模块。`default` 模块
   自动选择；根据需要启用其他模块。
6. 点击 **Save** 并重新加载页面。

对于 **私有仓库**，在认证下选择 **Personal Access Token (PAT)**：

1. 转到
   [GitHub personal access tokens](https://github.com/settings/personal-access-tokens)
   并点击 **Generate new token**。
2. 在 **Repository access** 下，选择 **Only select repositories** 并选择
   你的扩展 repo。
3. 在 **Permissions > Repository permissions** 下，将 **Contents** 设置为
   **Read-only**。
4. 生成 token 并在添加服务器时在 Perfetto UI 中输入它。

### 添加 HTTPS 服务器

1. 点击 **Add Server** 并选择 **HTTPS**。
2. 输入服务器 URL（例如，`https://perfetto-ext.corp.example.com`）。如果省略，`https://` 前缀会自动添加。
3. 选择模块并配置认证（见下文）。
4. 点击 **Save** 并重新加载页面。

## 共享 extension servers

点击 Settings 中任何服务器上的 **Share** 按钮以复制可共享的 URL。
当有人打开链接时：

- 如果他们没有配置服务器，**Add Server** 对话框会打开
  预填充共享配置。
- 如果他们已经有服务器，**Edit** 对话框会打开，共享的
  模块合并进来。

Secrets（PATs、密码、API keys）会自动从共享 URL 中剥离。
如果服务器需要认证，接收者输入他们自己的凭据。

## 管理服务器

在 Extension Servers 设置部分，使用操作按钮来：

- **Toggle** —— 启用或禁用服务器而不删除它。
- **Edit** —— 更改模块、认证或其他设置。
- **Share** —— 将可共享的 URL 复制到剪贴板。
- **Delete** —— 删除服务器。

更改需要 **页面重新加载** 才能生效。

## 创建 HTTPS extension server

如果你需要比 GitHub 仓库提供的更多控制 —— 动态内容、
公司 SSO 或与内部系统的集成 —— 你可以在任何 HTTPS 端点上托管 extension
server。

Extension server 是一组 JSON 端点。最少你需要：

```
https://your-server.example.com/manifest          → 服务器元数据
https://your-server.example.com/modules/default/macros      → macros（可选）
https://your-server.example.com/modules/default/sql_modules → SQL 模块（可选）
```

你可以将这些作为静态文件（nginx、GCS、S3）或从动态服务器
（Flask、Express 等）提供。服务器必须设置 CORS headers 以允许 Perfetto
UI 发出跨域请求。

请参阅
[Extension Server Protocol Reference](/docs/visualization/extension-server-protocol.md)
了解完整的端点规范、JSON schemas、CORS 要求和示例，包括最小的 Python/Flask 服务器。

## 故障排除

如果扩展加载失败，UI 会显示一个错误对话框，列出出错的地方。
错误是非阻塞的 —— UI 正常工作，来自其他成功加载的服务器的扩展仍然可用。

以下是可能看到的错误消息以及如何修复它们。

### "Failed to fetch \<url\>: \<error\>"

UI 根本无法到达服务器。这通常是网络或 CORS
问题。

- **检查 URL。** 在新浏览器标签页中打开 URL。如果你无法访问它，
  服务器可能已关闭，URL 可能错误，或者你可能需要在 VPN 上。
- **检查 CORS headers。** 如果 URL 在标签页中加载但 UI 显示 fetch
  错误，服务器可能没有设置 CORS headers。打开浏览器控制台
  (`F12`) 并查找 "CORS policy" 错误。请参阅
  [CORS requirements](/docs/visualization/extension-server-protocol.md#cors-requirements)
  了解要设置哪些 headers。GitHub 托管的服务器不需要 CORS 配置。
- **检查混合内容。** Perfetto UI 通过 HTTPS 提供，因此它
  无法从 `http://` URL 获取。为你的服务器使用 `https://`。

### "Fetch failed: \<url\> returned \<status\>"

服务器可以访问但返回了 HTTP 错误。

- **401 或 403** —— 认证失败。对于 GitHub PATs，检查 token
  是否未过期并具有对仓库的读取访问权限（Settings > Personal
  access tokens）。对于带有 SSO 的 HTTPS 服务器，尝试在新标签页中直接登录服务器
  以刷新你的会话，然后重新加载 Perfetto UI。
- **404** —— 端点不存在。检查服务器是否实现了
  预期的 [endpoint paths](/docs/visualization/extension-server-protocol.md#endpoints)
  并且仓库/分支/路径是否正确。

### "Failed to parse JSON from \<url\>: \<error\>"

服务器返回的响应不是有效的 JSON。

- 检查端点是否返回 `Content-Type: application/json` 和有效的
  JSON。如果使用 GitHub 模板，请确保 GitHub Action 在你的最后一次推送后
  已成功运行 —— 检查仓库中的 Actions 标签页。

### "Invalid response from \<url\>: \<error\>"

服务器返回了有效的 JSON，但不符合预期的 schema。

- 将你的响应与
  [protocol reference](/docs/visualization/extension-server-protocol.md) 中的预期格式进行比较。常见的错误包括缺少必需字段（`name`、`namespace`、`features`、
  manifest 中的 `modules`）或使用错误的字段名称。

### "Module '\<name\>' not found on server"

你在设置中启用了服务器 manifest 未列出的模块。

- 在 Settings 中编辑服务器并检查哪些模块已启用。如果模块
  从服务器重命名或删除，请取消选择它并保存。

### "Macro ID '\<id\>' must start with namespace '\<ns\>.'"

Macro 的 `id` 字段与服务器的命名空间不匹配。

- 如果你维护服务器：更新 macro ID 以你的命名空间开头
  （例如，将 `MyMacro` 更改为 `com.acme.Macro`）。请参阅
  [namespace enforcement](/docs/visualization/extension-server-protocol.md#namespace-enforcement)。
- 如果你不维护服务器：联系服务器维护者。

### "SQL module name '\<name\>' must start with namespace '\<ns\>.'"

与上面相同，但针对 SQL 模块。模块的 `name` 字段必须以
服务器的命名空间开头。

## 另请参阅

- [Extending the UI](/docs/visualization/extending-the-ui.md) ——
  所有 Perfetto UI 扩展机制的概述
- [扩展服务器协议参考](/docs/visualization/extension-server-protocol.md) ——
  构建自定义服务器的完整规范
- [Commands and Macros](/docs/visualization/ui-automation.md) —— 如何创建
  macros 和 startup commands
