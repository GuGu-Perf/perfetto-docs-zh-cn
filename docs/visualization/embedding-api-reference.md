# Perfetto UI 嵌入 API 参考

本页面是用于在宿主页面的 `<iframe>` 中嵌入 Perfetto UI
（`ui.perfetto.dev`）的 `postMessage` 和 URL 参数接口的参考。

关于面向任务的嵌入流程介绍，参见
[嵌入 Perfetto UI](/docs/visualization/embedding-the-ui.md)。
关于 `window.open()`（新浏览器标签页）变体和共享 / `appStateHash` 详情，
参见[深度链接到 Perfetto UI](/docs/visualization/deep-linking-to-perfetto-ui.md)。

NOTE: 这是一份参考文档，而非教程。此处未列出的字段和消息类型不属于
受支持的接口。

## 消息通道

宿主页面通过 `window.postMessage` 与嵌入的 UI 通信。UI 的消息处理器
仅处理 `event.source` 为以下之一的消息：

| `event.source`            | 何时                                                              |
| ------------------------- | ---------------------------------------------------------------- |
| `window.parent`           | UI 运行在宿主的 `<iframe>` 内（嵌入场景）。                         |
| `window.opener`           | 宿主通过 `window.open()` 启动 UI（新标签页场景）。                  |
| 本 UI 打开的窗口           | `event.source.opener === window`。                                |

对于 iframe 嵌入，UI 的 `window.parent` 即宿主页面，因此宿主向
`iframe.contentWindow` 发送消息，UI 接受它们。

由于通道不是缓冲的，在发送 trace 之前需要进行握手：

1. 宿主重复向 UI 窗口发送字符串 `'PING'`。
2. UI 回复字符串 `'PONG'`。回复发送到 `'*'`，且仅在 UI 的消息监听器
   已注册**且** `document.readyState === 'complete'` 时才发送。
3. 宿主监听 `'message'` 事件；在首次从 UI 窗口收到 `data === 'PONG'`
   时停止 ping 并发送 trace。

健壮的宿主应以间隔（例如每 50-250ms）进行 ping，并在第一个 `PONG` 时
清除该间隔。

带有 `{perfettoIgnore: true}` 的消息会被有意忽略。这允许宿主在同一通道
上复用其他流量。

## 打开 trace

要打开一个 trace，发送一个带有单个 `perfetto` 键的对象：

```js
iframe.contentWindow.postMessage({perfetto: {buffer, title}}, '*');
```

`perfetto` 对象的字段：

| 字段          | 类型                                                      | 必需 | 默认值 | 含义                                                                                                                              |
| -------------- | -------- | ----- | ------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `buffer`       | `ArrayBuffer` | 是   | 无     | trace 文件内容（protobuf、JSON 或其他支持的格式）。                                                                                |
| `title`        | `string` | 否   | `""`   | 在 UI 中显示的标题（已清理）。                                                                                                    |
| `url`          | `string` | 否   | 无     | 用于推断文件名的 URL（已清理）；仅在未提供 `title` 时显示。                                                                         |
| `fileName`     | `string` | 否   | 无     | 用于推断文件名以进行格式检测的字符串；不直接显示。                                                                                  |

## 控制 UI

要控制已打开的 trace，发送带有单个 `perfetto` 键及以下字段的对象
（不要包含 `buffer`）：

| 字段              | 类型       | 含义                                                                                             |
| ----------------- | ---------- | ------------------------------------------------------------------------------------------------ |
| `timeStart`       | `number`   | 以秒为单位的可见范围开始时间。仅当其大于当前 `timeStart` 时生效，这意味着宿主无法缩小范围。           |
| `timeEnd`         | `number`   | 以秒为单位的可见范围结束时间。仅当其小于当前 `timeEnd` 时生效。                                     |
| `sliceId`         | `number`   | 要高亮和选择的 Slice ID。                                                                         |

## URL 参数

将 trace 嵌入为 `<iframe src="https://ui.perfetto.dev/#!/?<params>">` 时，
以下参数可用：

| 参数              | 值                            | 含义                                                                                                                             |
| ----------------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `url`             | `<trace-url>`                 | 从此 URL（CORS 支持或代理后）打开 trace。                                                                                         |
| `local_cache_key` | `<key>`                       | 与配对的 `perfetto.openTrace({localCacheKey})` 调用一起使用。                                                                      |
| `ts`              | `<n>`                         | 以纳秒为单位的切片选择开始时间。                                                                                                   |
| `dur`             | `<n>`                         | 以纳秒为单位的切片选择持续时间。                                                                                                   |
| `pid`             | `<n>`                         | 用于消除切片选择歧义的进程 ID。                                                                                                   |
| `tid`             | `<n>`                         | 用于消除切片选择歧义的线程 ID。                                                                                                   |
| `query`           | `<sql>`                        | 加载时运行一个 SQL 查询（对值进行 URL 编码）。                                                                                     |
| `startupCommands` | `<url-encoded JSON array>`     | 加载后运行 UI 命令，例如 `[{id:'dev.perfetto.PinTracksByRegex', args:['.*CPU [0-3].*']}]`。                                       |
| `enablePlugins`   | `<comma,list>`                 | 按 ID 启用特定 plugin。                                                                                                           |

NOTE: `visStart`/`visEnd` 和 `ts`/`dur` 是原始的**纳秒**值，
而 `timeStart`/`timeEnd` 的 `postMessage` 字段是**秒**。

NOTE: 切片选择通过 `ts`+`dur`（加上可选的 `pid`/`tid`）进行，绝不通过
`id`，因为 ID 在不同运行之间不稳定。

## 来源信任

如果发送消息的来源受信任，trace 会立即打开。受信任集合为：

- 同源请求。
- `localhost`、`127.0.0.1` 和 `[::1]`（因此本地开发嵌入无需提示即可工作）。
- 少数硬编码的 Google 来源。
- 用户之前通过 "Always trust" 保存的来源。

如果来源**不**受信任，UI 会显示一个模态框：

> `<origin>` 正在尝试打开一个 trace 文件。你信任该来源吗？

选项为 **No**、**Yes** 和 **Always trust**。"Always trust" 将来源
持久化在 `localStorage` 中。

因此，从生产域名嵌入会向用户显示一次性同意提示，除非你自行托管 UI
（同源 => 受信任）。

`title` 和 `url` 中的字符串会被清理为字符集
`[A-Za-z0-9.\\-_#:/?=&;%+$ ]`。

## 约束

- 无法从 `file://` URL 工作（浏览器安全限制）。通过 `http(s)` 提供服务。
- 宿主页面**不得**带有 `Cross-Origin-Opener-Policy: same-origin` 头，
  这会破坏 opener 关系。
- UI 仅限客户端。发送的 trace 保留在浏览器内存中，绝不上传。
- `ui.perfetto.dev` 跟随最新版本。如需固定版本，自行托管 UI 构建以锁定它。
  自行托管还会使你的来源成为同源，从而跳过同意模态框。

## 源码

上述行为定义于：

- [/ui/src/frontend/post_message_handler.ts](/ui/src/frontend/post_message_handler.ts)
- [/ui/src/public/route_schema.ts](/ui/src/public/route_schema.ts)
