# 扩展服务器协议参考

本文档记录了 extension servers 必须实现的 HTTP 协议。如果你正在构建自定义 extension server，而不是使用 [GitHub template 方法](/docs/visualization/extension-servers.md)，请使用此文档。

## 端点

Extension servers 实现以下 HTTP(S) endpoints：

```
{base_url}/manifest                              GET  (required)
{base_url}/modules/{module_id}/macros            GET  (optional)
{base_url}/modules/{module_id}/sql_modules       GET  (optional)
{base_url}/modules/{module_id}/proto_descriptors GET  (optional)
```

UI 仅对 manifest 中声明的功能获取可选的 endpoints。

## 清单

**Endpoint:** `GET {base_url}/manifest`

返回服务器元数据、支持的功能和可用的模块。

```json
{
  "name": "Acme Corp Extensions",
  "namespace": "com.acme",
  "features": [
    {"name": "macros"},
    {"name": "sql_modules"},
    {"name": "proto_descriptors"}
  ],
  "modules": [
    {"id": "default", "name": "Default"},
    {"id": "android", "name": "Android"},
    {"id": "chrome", "name": "Chrome"}
  ]
}
```

### 字段

| 字段 | 类型 | 必需 | 描述 |
|-------|------|----------|-------------|
| `name` | string | 是 | 人类可读的服务器名称，显示在设置和命令面板源标签中。 |
| `namespace` | string | 是 | 反向域名表示法中的唯一标识符（例如，`com.acme`）。用于强制执行宏和 SQL 模块的命名约束。 |
| `features` | array | 是 | 此服务器支持的功能。每个条目都有一个 `name` 字段。有效名称：`macros`、`sql_modules`、`proto_descriptors`。 |
| `modules` | array | 是 | 可用模块。每个条目都有一个 `id`（用于 URL 路径和设置）和一个 `name`（人类可读的显示名称）。 |

对于单模块服务器，使用 `[{"id": "default", "name": "Default"}]`。

## 宏

**Endpoint:** `GET {base_url}/modules/{module_id}/macros`

仅在 `features` 包含 `{"name": "macros"}` 时获取。

```json
{
  "macros": [
    {
      "id": "com.acme.StartupAnalysis",
      "name": "Startup Analysis",
      "run": [
        {"id": "dev.perfetto.RunQuery", "args": ["SELECT 1"]},
        {"id": "dev.perfetto.PinTracksByRegex", "args": [".*CPU.*"]}
      ]
    }
  ]
}
```

### Macro 字段

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `id` | string | 唯一标识符。必须以服务器的命名空间开头，后跟 `.`（例如，`com.acme.StartupAnalysis`）。 |
| `name` | string | 在命令面板中显示的显示名称。 |
| `run` | array | 按顺序执行的命令。每个条目都有一个命令 `id` 和一个 `args` 数组。 |

请参阅 [Commands Automation Reference](/docs/visualization/commands-automation-reference.md) 获取可用 command IDs 及其参数的完整列表。

## SQL 模块

**Endpoint:** `GET {base_url}/modules/{module_id}/sql_modules`

仅在 `features` 包含 `{"name": "sql_modules"}` 时获取。

```json
{
  "sql_modules": [
    {
      "name": "com.acme.startup",
      "sql": "CREATE PERFETTO TABLE _startup_events AS SELECT ts, dur, name FROM slice WHERE name GLOB 'startup*';"
    },
    {
      "name": "com.acme.memory",
      "sql": "CREATE PERFETTO FUNCTION com_acme_rss_mb(upid INT) RETURNS FLOAT AS SELECT CAST(value AS FLOAT) / 1048576 FROM counter WHERE track_id IN (SELECT id FROM process_counter_track WHERE upid = $upid AND name = 'mem.rss') ORDER BY ts DESC LIMIT 1;"
    }
  ]
}
```

### SQL 模块字段

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `name` | string | Module name. Must start with the server's namespace followed by `.` (e.g., `com.acme.startup`). Users reference this with `INCLUDE PERFETTO MODULE com.acme.startup;`. |
| `sql` | string | SQL text. Can contain `CREATE PERFETTO TABLE`, `CREATE PERFETTO FUNCTION`, `CREATE PERFETTO VIEW`, or any valid PerfettoSQL. |

## Proto 描述符

**Endpoint:** `GET {base_url}/modules/{module_id}/proto_descriptors`

仅在 `features` 包含 `{"name": "proto_descriptors"}` 时获取。

```json
{
  "proto_descriptors": [
    "CgdteV9wcm90bxIHbXlwcm90byI...",
    "Cghhbm90aGVyEghhbm90aGVyIi..."
  ]
}
```

### Proto 描述符字段

| 字段 | 类型 | 描述 |
|-------|------|-------------|
| `proto_descriptors` | array of strings | Base64 编码的 `FileDescriptorSet` protocol buffer 消息。这些允许 UI 解码 trace 中的自定义 protobuf 消息。 |

Proto descriptors are not subject to namespace enforcement since protobuf messages have their own package-based namespacing.

## 命名空间强制执行

All macro IDs and SQL module names must start with the server's `namespace` value from the manifest, followed by a `.`. For example, a server with namespace `com.acme` can only serve:

- Macro IDs like `com.acme.StartupAnalysis`, `com.acme.MemoryCheck`
- SQL module names like `com.acme.startup`, `com.acme.memory.helpers`

The UI validates this and rejects extensions that violate the convention. This prevents naming conflicts when users configure multiple extension servers.

## CORS 要求

All HTTPS extension servers must set CORS headers to allow the Perfetto UI to make cross-origin requests:

```
Access-Control-Allow-Origin: https://ui.perfetto.dev
Access-Control-Allow-Methods: GET
Access-Control-Allow-Headers: Authorization, Content-Type
```

如果您的服务器支持多个 Perfetto UI 部署，您可以反射 `Origin` 请求头而不是硬编码单个 origin。

GitHub-hosted servers do not need CORS configuration — `raw.githubusercontent.com` and the GitHub API already set appropriate headers.

CORS failures appear as network errors in the browser console. The affected server is skipped and other servers continue to load normally.

## 认证 headers

The Perfetto UI constructs authentication headers based on the server's configured auth type:

| 认证类型 | Header |
|-----------|--------|
| `none` | 无认证 headers |
| `github_pat` | `Authorization: token <pat>`（通过 GitHub API） |
| `https_basic` | `Authorization: Basic <base64(username:password)>` |
| `https_apikey` (bearer) | `Authorization: Bearer <key>` |
| `https_apikey` (x_api_key) | `X-API-Key: <key>` |
| `https_apikey` (custom) | `<custom_header_name>: <key>` |
| `https_sso` | 无 header；请求使用 `credentials: 'include'` 发送 |

对于 SSO 认证，如果请求返回 HTTP 403，UI 会在隐藏的 iframe 中加载服务器的 base URL 以刷新 SSO session cookie，然后重试请求一次。

## GitHub 服务器 URL 构造

对于 GitHub-hosted extension servers，UI 自动构造 fetch URLs：

- **Unauthenticated (public repos):** Uses `raw.githubusercontent.com` to avoid GitHub API rate limits.
  ```
  https://raw.githubusercontent.com/{repo}/{ref}/{path}/manifest
  ```
- **已认证（私有仓库）：** 使用 GitHub Contents API。
  ```
  https://api.github.com/repos/{repo}/contents/{path}/manifest?ref={ref}
  ```
  使用 header：`Accept: application/vnd.github.raw+json`

## 示例：最小静态服务器

一个完整的 extension server 可以是一组静态 JSON 文件：

```
my-extensions/
  manifest
  modules/
    default/
      macros
      sql_modules
```

使用任何设置了所需 CORS headers 的静态文件服务器（nginx, Caddy, GCS, S3）提供这些文件。基本用例不需要动态服务器逻辑。

## 示例：动态服务器 (Python/Flask)

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/manifest')
def manifest():
    return jsonify({
        "name": "My Extensions",
        "namespace": "com.example",
        "features": [{"name": "macros"}, {"name": "sql_modules"}],
        "modules": [{"id": "default", "name": "Default"}],
    })

@app.route('/modules/<module>/macros')
def macros(module):
    return jsonify({
        "macros": [
            {
                "id": "com.example.ShowLongSlices",
                "name": "Show Long Slices",
                "run": [
                    {
                        "id": "dev.perfetto.RunQueryAndShowTab",
                        "args": ["SELECT * FROM slice ORDER BY dur DESC LIMIT 20"]
                    }
                ]
            }
        ]
    })

@app.route('/modules/<module>/sql_modules')
def sql_modules(module):
    return jsonify({
        "sql_modules": [
            {"name": "com.example.helpers", "sql": "CREATE PERFETTO TABLE ...;"}
        ]
    })

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = 'https://ui.perfetto.dev'
    response.headers['Access-Control-Allow-Methods'] = 'GET'
    response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
    return response
```

## 另请参阅

- [扩展服务器设置指南](/docs/visualization/extension-servers.md) — 使用 GitHub template 的分步设置
- [扩展服务器](/docs/visualization/extension-servers.md) — Extension servers 是什么以及它们如何工作
- [命令自动化参考](/docs/visualization/commands-automation-reference.md) — Macros 的可用 command IDs
