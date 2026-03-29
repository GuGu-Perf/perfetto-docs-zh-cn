# Perfetto UI 的深度链接

本文档描述如何使用 Perfetto UI 打开托管在外部服务器上的 trace。这有助于将 Perfetto UI 与自定义仪表板集成，并实现类似 _'使用 Perfetto UI 打开'_ 的功能。

在本指南中，你将学习如何：

- 通过 URL 直接打开公共 trace（最简单的方法）。
- 使用 postMessage 完全控制打开 trace（用于身份验证、共享等）。

你还将学习如何在打开 trace 时自定义 UI 状态（缩放、选择、查询）。

## 选项 1：公共 trace 的直接 URL

如果你的 trace 通过 HTTPS 公开访问，可以使用 `url` 查询参数直接链接到它：

```
https://ui.perfetto.dev/#!/?url=https://example.com/path/to/trace.pftrace
```

**要求：**

- trace 必须通过 HTTPS 提供。
- URL 必须响应不带查询参数的简单 GET 请求。
- 你的服务器必须设置 CORS 头以允许 Perfetto UI 源，例如
 `Access-Control-Allow-Origin: https://ui.perfetto.dev` 或
 `Access-Control-Allow-Origin: *`。

这是不需要身份验证或自定义共享功能的公共托管 trace 的最简单选项。

**限制：**

- 不支持身份验证（trace 必须可公开访问）。
- 不支持自定义共享 URL。
- 无法控制 UI 中显示的 trace 标题。

如果你需要这些功能中的任何一个，请使用
[选项 2](#选项-2-使用-postmessage-进行完全控制)。

## 选项 2：使用 postMessage 进行完全控制

对于需要身份验证、自定义共享 URL 或其他高级功能的 trace，请使用 postMessage 方法。这需要在你控制的基础设施上运行一些 JavaScript 代码。

### 步骤 1：通过 window.open 打开 ui.perfetto.dev

源仪表板（知道如何定位 trace 并处理 ACL 检查、OAuth 身份验证等的那个）创建一个新标签页：

```js
var handle = window.open('https://ui.perfetto.dev');
```

窗口句柄允许使用 `postMessage()` 在你的仪表板和 Perfetto UI 之间进行双向通信。

### 步骤 2：通过 PING/PONG 等待 UI 准备就绪

`window.open()` 消息通道不是缓冲的。如果在打开的页面注册 `onmessage` 监听器之前发送消息，消息将被丢弃。为避免这种竞争条件，请使用 PING/PONG 协议：继续发送 'PING' 消息，直到打开的窗口回复 'PONG'。

### 步骤 3：发布 trace 数据

完成 PING/PONG 握手后，向 Perfetto UI 窗口发布消息。消息应该是一个带有单个 `perfetto` 键的 JavaScript 对象：

```js
{
 'perfetto': {
 buffer: ArrayBuffer;
 title: string;
 fileName?: string; // Optional
 url?: string; // Optional
 appStateHash?: string // Optional
 }
}
```

`perfetto` 对象的属性包括：

- `buffer`：包含原始 trace 数据的 `ArrayBuffer`。你通常通过从后端获取 trace 文件来获得它。
- `title`：将在 UI 中显示为 trace 标题的可读字符串。这有助于用户在打开多个标签页时区分不同的 trace。
- `fileName`（可选）：如果用户决定从 Perfetto UI 下载 trace，则建议的文件名。如果省略，将使用通用名称。
- `url`（可选）：用于共享 trace 的 URL。请参阅下面的"共享"部分。
- `appStateHash`（可选）：用于在共享时恢复 UI 状态的哈希。请参阅下面的"共享"部分。

### 共享 trace 和 UI 状态

当通过 `postMessage` 打开 trace 时，Perfetto 避免存储 trace，因为这可能会违反原始 trace 源的保留策略。trace 不会上传到任何地方。因此，你必须提供一个 URL，该 URL 通过你的基础设施提供到同一 trace 的直接链接，该链接应自动重新打开 Perfetto 并使用 postMessage 提供相同的 trace。

`url` 和 `appStateHash` 属性协同工作，允许用户共享 trace 的链接，当打开时，将 trace 和 UI 恢复到相同的状态（例如，缩放级别、选定的事件）。

当用户在 Perfetto UI 中点击"共享"按钮时，Perfetto 会查看你在打开 trace 时提供的 `url`。如果此 `url` 包含特殊占位符 `perfettoStateHashPlaceholder`，Perfetto 将：

1. 保存当前 UI 状态并为其生成唯一的哈希。
2. 将你的 `url` 中的 `perfettoStateHashPlaceholder` 替换为这个新哈希。
3. 向用户显示此最终 URL 以供共享。

例如，如果你提供了此 `url`：
`'https://my-dashboard.com/trace?id=1234&state=perfettoStateHashPlaceholder'`

Perfetto 可能会生成如下可共享的 URL：
`'https://my-dashboard.com/trace?id=1234&state=a1b2c3d4'`

当另一个用户打开此共享 URL 时，你的应用程序应该：

1. 从 URL 中提取状态哈希（在此示例中为 `a1b2c3d4`）。
2. 像往常一样 `postMessage` trace `buffer`，但这次还包括带有提取的哈希的 `appStateHash` 属性。

Perfetto 然后将加载 trace 并自动恢复与该哈希关联的 UI 状态。

如果省略 `url` 属性，则将禁用共享功能。如果从 `url` 中省略 `perfettoStateHashPlaceholder`，则可以共享 trace，但不会保存 UI 状态。

### 代码示例

请参阅
[此示例调用方](https://bl.ocks.org/chromy/170c11ce30d9084957d7f3aa065e89f8)，
其代码在
[此 GitHub gist](https://gist.github.com/chromy/170c11ce30d9084957d7f3aa065e89f8) 中。

Googlers：请查看
[内部代码搜索中的现有示例](http://go/perfetto-ui-deeplink-cs)。

### 常见陷阱

许多浏览器有时会阻止 `window.open()` 请求，提示用户允许该站点的弹出窗口。这通常发生在：

- `window.open()` 不是由用户手势发起的。
- 用户手势和 `window.open()` 之间经过的时间太长。

如果 trace 文件足够大，`fetch()` 可能需要足够长的时间来超过用户手势阈值。可以通过观察 `window.open()` 返回 `null` 来检测这一点。发生这种情况时，最好的选项是显示另一个可点击元素，并将获取的 trace ArrayBuffer 绑定到新的 onclick 处理程序，就像上面的示例代码那样。

某些浏览器的用户手势超时时间阈值是可变的，这取决于网站参与度分数（用户之前访问页面的程度）。在测试此代码时，通常会在第一次使用新功能时看到弹出窗口阻止程序，然后就不会再看到了。

由于浏览器对 `file://` URL 的安全限制，此方案将无法从 `file://` URL 工作。

源网站不得使用 `Cross-Origin-Opener-Policy: same-origin` 头提供服务。例如，请参阅
[此问题](https://github.com/google/perfetto/issues/525#issuecomment-1625055986)。

### 推送的 trace 去哪里了？

Perfetto UI 仅是客户端的，不需要任何服务器端交互。通过 `postMessage()` 推送的 trace 仅保留在浏览器内存/缓存中，不会发送到任何服务器。

## 使用 URL 参数自定义 UI

除了打开 trace 之外，你还可以使用 URL 片段参数控制初始 UI 状态。这些参数适用于选项 1（直接 URL）和选项 2（postMessage）。

### 缩放到 trace 的区域

传递 `visStart` 和 `visEnd` 来控制初始视口。这些值是 SQL 表中显示的原始时间戳（以纳秒为单位）：

```
https://ui.perfetto.dev/#!/?visStart=261191575272856&visEnd=261191675272856
```

这将在 ~261192s 处以 100ms 宽的查看窗口打开 trace。

### 加载时选择一个 slice

传递 `ts`、`dur`、`pid` 和/或 `tid` 参数。UI 将查询 slice 表并找到与参数匹配的 slice。如果找到，则突出显示该 slice。你不必提供所有参数；通常 `ts` 和 `dur` 就足以唯一标识一个 slice。

NOTE: 我们有意不支持通过 slice ID 链接，因为 slice ID 在 Perfetto 版本之间不稳定。相反，通过传递精确的开始时间戳和持续时间（`ts` 和 `dur`）来链接，如通过发出类似 `SELECT ts, dur FROM slices WHERE id=...` 的查询所见。

### 加载时发出查询

在 `query` 参数中传递查询。

### 示例

尝试这些示例：

- [visStart & visEnd](https://ui.perfetto.dev/#!/?url=https%3A%2F%2Fstorage.googleapis.com%2Fperfetto-misc%2Fexample_android_trace_15s&visStart=261191575272856&visEnd=261191675272856)
- [ts & dur](https://ui.perfetto.dev/#!/?url=https%3A%2F%2Fstorage.googleapis.com%2Fperfetto-misc%2Fexample_android_trace_15s&ts=261192482777530&dur=1667500)
- [query](https://ui.perfetto.dev/#!/?url=https%3A%2F%2Fstorage.googleapis.com%2Fperfetto-misc%2Fexample_android_trace_15s&query=select%20'Hello%2C%20world!'%20as%20msg)

记住在需要的地方对字符串进行 URL 编码。

### 启动命令

你还可以在 trace 打开时通过在 URL 中嵌入启动命令来自动配置 UI 本身。这对于仪表板集成非常有用，你希望为用户提供预配置的分析环境。

以 URL 编码的 JSON 数组的形式在 `startupCommands` 参数中传递启动命令。命令在 trace 加载后自动执行，允许你固定 Track、创建调试 Track 或运行任何其他 UI 自动化。

```js
// 示例：固定 CPU Track 并创建调试 Track
const commands = [
 {id: 'dev.perfetto.PinTracksByRegex', args: ['.*CPU [0-3].*']},
 {
 id: 'dev.perfetto.AddDebugSliceTrack',
 args: [
 "SELECT ts, dur as value FROM slice WHERE name LIKE '%render%'",
 'Render Operations',
 ],
 },
];

const url = `https://ui.perfetto.dev/#!/?startupCommands=${encodeURIComponent(
 JSON.stringify(commands),
)}`;
```

启动命令使用与 [UI 自动化文档](/docs/visualization/perfetto-ui.md#startup-commands) 中描述的相同的 JSON 格式，但在作为参数传递时必须进行 URL 编码。有关具有向后兼容性保证的稳定命令列表，请参阅
[命令自动化参考](/docs/visualization/commands-automation-reference.md)。

## 源链接

处理 Perfetto UI 中 `postMessage()` 的源代码是
[`post_message_handler.ts`](/ui/src/frontend/post_message_handler.ts)。
