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
| -------------- | -------------------------------------------------------- | -------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `buffer`       | `ArrayBuffer`                                             | 是      | -       | 原始 trace 字节，例如来自 `fetch(...).then(r => r.arrayBuffer())`。                                                                  |
| `title`        | `string`                                                 | 是      | -       | 在 UI 中显示的 trace 标题。                                                                                                          |
| `fileName`     | `string`                                                 | 否      | -       | 用户下载 trace 时建议的文件名。                                                                                                      |
| `url`          | `string`                                                 | 否      | -       | 分享 URL。分享详情参见[深度链接到 Perfetto UI](/docs/visualization/deep-linking-to-perfetto-ui.md)。                                                          |
| `appStateHash` | `string`                                                 | 否      | -       | 40 字符十六进制哈希；从 GCS 恢复已保存的 UI 状态。参见[深度链接到 Perfetto UI](/docs/visualization/deep-linking-to-perfetto-ui.md)。 |
| `shareable`    | `boolean`                                                | 否      | `false` | 若为 `true`，UI 可以共享该 trace（例如上传以生成永久链接）。                                                                          |
| `downloadable` | `boolean`                                                | 否      | `false` | 若为 `true`，用户可以下载该 trace。                                                                                                  |
| `localOnly`    | `boolean`                                                | 否      | `true`  | 遗留字段。设为 `false` 会将 `shareable` 和 `downloadable` 都设为 `true`。显式指定的 `shareable`/`downloadable` 优先。                    |
| `keepApiOpen`  | `boolean`                                                | 否      | `false` | 若为 `true`，监听器保持活跃，宿主之后可以发送更多 trace。若为 `false`/省略，处理器在第一个 trace 之后移除自己的消息监听器（避免重复发送，b/182502595）。 |
| `pluginArgs`   | `{[pluginId: string]: {[key: string]: unknown}}`         | 否      | -       | 传递给 plugin 的 `onTraceLoad()`。                                                                                                  |

### 裸 ArrayBuffer 简写

裸 `ArrayBuffer`（`event.data instanceof ArrayBuffer`）也会被接受。它
会被视为 `{title: 'External trace', buffer}`。

## 滚动到时间范围

trace 加载后发送以下消息，将视口滚动/缩放到一个时间范围：

```js
iframe.contentWindow.postMessage(
    {perfetto: {timeStart, timeEnd, viewPercentage}}, '*');
```

| 字段            | 类型     | 必需 | 含义                                          |
| ---------------- | -------- | -------- | ------------------------------------------------ |
| `timeStart`      | `number` | 是      | 范围开始，**绝对 trace 时间（秒）**（非相对于 trace 起点；会被钳制到 trace 边界）。 |
| `timeEnd`        | `number` | 是      | 范围结束，**绝对 trace 时间（秒）**。   |
| `viewPercentage` | `number` | 否      | 该范围应填充的视口比例，取值 `(0.0, 1.0]`。越界值会被忽略并以 `0.5` 替代。 |

处理器会在内部重试（大约每 200ms 一次，共约 20 次）直到 trace 就绪，因此
这条消息可以在发送 trace 后不久发出，无需等待显式的"已加载"信号。

## 字符串命令

处理器可理解以下字符串消息：

| 消息                 | 效果                                  |
| ----------------------- | --------------------------------------- |
| `'PING'`                | 回复 `'PONG'`（发送到 `'*'`）。  |
| `'SHOW-HELP'`           | 打开帮助对话框。                  |
| `'RELOAD-CSS-CONSTANTS'`| 重新加载 CSS 常量。                  |

## URL 参数

在 iframe 的 `src` 上设置这些参数。路由基于 hash：
`https://ui.perfetto.dev/#!/?key=val&...`。

| 参数         | 值                          | 效果                                                                                                                              |
| ----------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `mode`            | `embedded`                     | 启用嵌入模式：侧边栏被**完全禁用**（而非仅隐藏），且不安装文件拖放处理器。嵌入时使用此项。 |
| `hideSidebar`     | `true`                         | 在视觉上隐藏侧边栏，但不完全禁用它。                                                                             |
| `url`             | `<https url>`                  | UI 自行获取公开 trace（要求 CORS 允许 UI 源）。公开 trace 场景下可作为 `postMessage` 的替代方案。           |
| `s`               | `<hash>`                       | 加载一个 permalink（已保存状态）。                                                                                                   |
| `visStart`        | `<ns>`                         | 初始视口起点，原始**纳秒**时间戳（与 SQL 表中一致）。与 `visEnd` 配对使用。                                       |
| `visEnd`          | `<ns>`                         | 初始视口终点，原始**纳秒**时间戳。                                                                               |
| `ts`              | `<ns>`                         | 加载时要选择的 slice 的时间戳，单位**纳秒**。链接依据是 `ts`+`dur`，**而非** `id`（id 不稳定）。        |
| `dur`             | `<ns>`                         | 加载时要选择的 slice 的持续时间，单位**纳秒**。                                                                       |
| `query`           | `<sql>`                        | 加载时运行一个 SQL 查询（对值进行 URL 编码）。                                                                                  |
| `startupCommands` | `<url-encoded JSON array>`     | 加载后运行 UI 命令，例如 `[{id:'dev.perfetto.PinTracksByRegex', args:['.*CPU [0-3].*']}]`。                                |
| `enablePlugins`   | `<comma,list>`                 | 按 id 启用特定 plugin。                                                                                                    |

NOTE: `visStart`/`visEnd` 和 `ts`/`dur` 是原始的**纳秒**值，
而 `timeStart`/`timeEnd` 的 `postMessage` 字段是**秒**。

NOTE: 切片选择通过 `ts`+`dur` 进行，绝不通过 `id`，因为 ID 在不同运行之间不稳定。

## 来源信任

如果发送消息的来源受信任，trace 会立即打开。受信任集合为：

- 同源请求。
- `localhost`、`127.0.0.1` 和 `[::1]`（因此本地开发嵌入无需提示即可工作）。
- 少数硬编码的 Google 来源。
- 用户之前通过 "Always trust" 保存的来源。

如果来源**不**受信任，UI 会显示一个模态框：

> `<origin>` 正在尝试打开一个 trace 文件。你信任该来源并想继续吗？

选项为 **No**、**Yes** 和 **Always trust**。"Always trust" 将来源
持久化在 `localStorage` 中。

因此，从生产域名嵌入会向用户显示一次性同意提示，除非你自行托管 UI
（同源 => 受信任）。

`title` 和 `url` 中的字符串会被清理为字符集
`[A-Za-z0-9.\-_#:/?=&;%+$ ]`。

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
