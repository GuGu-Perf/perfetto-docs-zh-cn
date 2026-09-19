# 嵌入 Perfetto UI

本指南展示如何将 Perfetto trace 查看器*嵌入你自己的*工具或
 dashboard（通过 `<iframe>`），并以编程方式向其提供 trace。当你希望 trace 视图
存在于你的应用的界面框架内时，这是正确的方法，正如 Dart DevTools 和
各种 profiler 前端等真正的工具所做的那样。如果你只是想在新浏览器标签页
中启动完整的 Perfetto UI（`window.open()` 流程），参见
[深度链接到 Perfetto UI](/docs/visualization/deep-linking-to-perfetto-ui.md)；
该页面还涵盖了分享 URL 和 `appStateHash`，本指南不再重复。

## 开始之前 {#before-you-begin}

- 通过 `http(s)` 提供你的宿主页面，而非 `file://`。嵌入协议依赖于
  窗口间的 `postMessage`，浏览器对 `file://` 来源会禁用此功能。
- 不要使用 `Cross-Origin-Opener-Policy: same-origin` 头提供你的
  宿主页面。它会破坏 UI 所依赖的 parent/iframe 关系。
- 在本地开发期间，从 `localhost` / `127.0.0.1` 提供服务。这些来源被
  UI 信任，因此 trace 打开时无需同意提示（参见
  [信任提示与生产环境](#trust-prompts-and-going-to-production)）。

## 步骤 1：添加 iframe

使用 URL 中的 `mode=embedded` 嵌入 UI。这会完全禁用侧边栏（不仅是隐藏），
这正是嵌入视图所需的效果。路由基于 hash：

```html
<iframe
  id="perfetto"
  src="https://ui.perfetto.dev/#!/?mode=embedded"
  width="100%"
  height="600"
></iframe>
```

在嵌入式模式下，文件拖放处理器也不会被安装，因此 iframe 只加载你
发送给它的 trace。

## 步骤 2：执行 PING/PONG 握手

进入 iframe 的 `postMessage` 通道不是缓冲的：如果你在 UI 注册其消息
监听器之前发送 trace，消息会被静默丢弃。为避免此竞争条件，重复发送
字符串 `'PING'` 直到 UI 回复 `'PONG'`。UI 仅在其监听器已注册且
`document.readyState === 'complete'` 时才发送 `'PONG'`。

```js
const iframe = document.getElementById('perfetto');

function waitForReady() {
  return new Promise((resolve) => {
    const interval = setInterval(() => {
      iframe.contentWindow.postMessage('PING', '*');
    }, 100);

    window.addEventListener('message', function onMsg(evt) {
      if (evt.source === iframe.contentWindow && evt.data === 'PONG') {
        clearInterval(interval);
        window.removeEventListener('message', onMsg);
        resolve();
      }
    });
  });
}
```

## 步骤 3：发送 trace

握手完成后，向 iframe 的 `contentWindow` 发送一个仅含单个 `perfetto` 键的
对象。只有 `buffer`（原始 trace 字节的 `ArrayBuffer`）和 `title` 是必需的：

```js
async function openTrace() {
  await waitForReady();

  const resp = await fetch(
    'https://storage.googleapis.com/perfetto-misc/example_android_trace_15s',
  );
  const buffer = await resp.arrayBuffer();

  iframe.contentWindow.postMessage(
    {
      perfetto: {
        buffer: buffer,
        title: 'My embedded trace',
      },
    },
    '*',
  );
}
```

`perfetto` 对象的完整字段列表：

- `buffer`（必需）：原始 trace 字节的 `ArrayBuffer`。
- `title`（必需）：显示为 trace 标题的字符串。
- `fileName`（可选）：用户下载 trace 时建议的文件名。
- `url`（可选）：分享 URL。参见
  [深度链接](/docs/visualization/deep-linking-to-perfetto-ui.md)了解 `url` 和 `appStateHash` 如何启用分享。
- `appStateHash`（可选）：恢复已保存 UI 状态的 40 字符十六进制哈希。
- `shareable` / `downloadable`（可选）：对于推送的 trace 两者默认为 `false`，
  即禁用分享/下载。设为 `true` 以启用。
- `localOnly`（可选，遗留）：`false` 会将 `shareable` 和 `downloadable`
  都设为 `true`。
- `keepApiOpen`（可选）：若为 `true`，监听器保持活跃，因此你之后可以推送
  更多 trace。若省略，处理器在第一个 trace 之后移除其监听器。
- `pluginArgs`（可选）：`{ [pluginId]: { [key]: unknown } }`，传递给
  plugin 的 `onTraceLoad()`。

NOTE: 如果要在同一 iframe 中更换 trace 而不重新加载它，请在第一次发送时
设置 `keepApiOpen: true`。否则 UI 在第一个 trace 之后会停止监听。

TIP: 裸 `ArrayBuffer` 也会被接受（UI 将其视为名为 "External trace" 的
trace），但推荐发送 `{ perfetto: { buffer, title } }` 对象，以便由你控制
标题。

## 步骤 4（可选）：驱动视图

你可以通过两种方式操控嵌入的视图。

要在 trace 打开时配置 UI，将 `startupCommands` 作为 URL 编码的 JSON 命令
数组添加到 iframe 的 `src`。例如，要 pin 住 CPU track：

```js
const commands = [
  {id: 'dev.perfetto.PinTracksByRegex', args: ['.*CPU [0-3].*']},
];
const src =
  'https://ui.perfetto.dev/#!/?mode=embedded&startupCommands=' +
  encodeURIComponent(JSON.stringify(commands));
```

要在 trace 加载后滚动并缩放到一个时间范围，发送第二条消息。`timeStart` 和
`timeEnd` 是**绝对 trace 时间（秒）**，而非相对于 trace 起点（大多数
trace 不从 0 开始）；超出 trace 的范围会被钳制到其边界。`viewPercentage`
是可选的，是 `(0, 1]` 范围内的比例（例如 `0.5` 填充视口的一半，`1` 恰好
填满）；越界值会被忽略并回退到 `0.5`：

```js
// 例如缩放到一个起点在 261187s 的 trace 的前 2 秒。
iframe.contentWindow.postMessage(
  {perfetto: {timeStart: 261187.0, timeEnd: 261189.0, viewPercentage: 1}},
  '*',
);
```

UI 会在内部重试直到 trace 就绪，因此你可以在发送 trace 后立即发送它，
无需自己的等待循环。

## 整合到一起

将以下内容粘贴到一个文件中（例如 `index.html`），在 `localhost` 上通过
`http(s)` 提供服务，然后在浏览器中打开：

```html
<!doctype html>
<html>
  <body>
    <iframe
      id="perfetto"
      src="https://ui.perfetto.dev/#!/?mode=embedded"
      width="100%"
      height="600"
    ></iframe>

    <script>
      const iframe = document.getElementById('perfetto');
      const SAMPLE =
        'https://storage.googleapis.com/perfetto-misc/example_android_trace_15s';

      function waitForReady() {
        return new Promise((resolve) => {
          const interval = setInterval(() => {
            iframe.contentWindow.postMessage('PING', '*');
          }, 100);
          window.addEventListener('message', function onMsg(evt) {
            if (evt.source === iframe.contentWindow && evt.data === 'PONG') {
              clearInterval(interval);
              window.removeEventListener('message', onMsg);
              resolve();
            }
          });
        });
      }

      (async () => {
        await waitForReady();
        const buffer = await (await fetch(SAMPLE)).arrayBuffer();
        iframe.contentWindow.postMessage(
          {perfetto: {buffer, title: 'My embedded trace'}},
          '*',
        );
      })();
    </script>
  </body>
</html>
```

## 信任提示与生产环境 {#trust-prompts-and-going-to-production}

UI 会限制哪些来源可以推送 trace：

- `localhost`、`127.0.0.1`、`[::1]`、同源以及少数硬编码的 Google 来源是
  受信任的。来自这些来源的 trace 立即打开且无提示，因此本地开发可以直接
  工作。
- 来自任何其他来源（例如你的生产域名）时，UI 会显示一个模态框：
  *"&lt;origin&gt; is trying to open a trace file. Do you trust the origin
  and want to proceed?"* ，选项为 **No / Yes / Always trust**。"Always
  trust" 会将该来源持久化到 `localStorage` 中，因此每个用户最多看到一次
  该提示。

要在生产环境中完全避免同意模态框，请在你的域名上自行托管 Perfetto UI
构建。同源的宿主页面是受信任的，因此不会出现提示。

NOTE: `ui.perfetto.dev` 跟随最新版本，因此此处描述的嵌入协议是稳定的，
但 UI 细节可能随时间变化。如需固定版本，自行托管 UI 构建以锁定它（参见
下方[自行托管 UI](#self-hosting-the-ui)）。自行托管还具有上述同源信任的
好处。

NOTE: UI 仅限客户端。发送的 trace 保留在浏览器内存中，绝不会被上传到
任何地方。

## 自行托管 UI {#self-hosting-the-ui}

每个 [Perfetto 在 GitHub 上的发布版本](https://github.com/google/perfetto/releases/latest)
都附带一个 `perfetto-ui.zip` 资源，其中包含部署到 `ui.perfetto.dev` 的
确切 UI 构建：根 `index.html`、service worker 以及一个包含它所引用的
所有 js/wasm/css 资源的版本化目录。

要自行托管，解压该资源并使用任何静态文件服务器提供结果目录；无需
服务器端逻辑，因为 UI 完全在客户端运行。快速冒烟测试，在解压后的
目录内：

```sh
python3 -m http.server 8080
```

然后打开 `http://localhost:8080`。

在实际部署时需要注意以下几点：

- 在其自己的源站根目录下提供文件（例如 `perfetto.example.com`，
  而非 `example.com/perfetto/`）。处理离线缓存和更快后续加载的
  service worker 仅在 UI 从 `/` 提供时注册；在子目录下不注册，
  UI 仍可工作，只是缺少该优化。
- 确保服务器以 `application/wasm` MIME 类型提供 `.wasm` 文件。
  大多数现代静态文件服务器默认支持此类型。
- 无需特殊的头。特别是，不要在嵌入 UI 的页面上添加
  `Cross-Origin-Opener-Policy: same-origin`（参见上方
  [开始之前](#before-you-begin)）。
- 每个发布版本的 zip 精确锁定该版本的 UI；没有自动更新。
  要升级到新版本，部署新版本的 zip 替换旧版。

由于自行托管的 UI 从你自己的域名提供服务，同一源站上的宿主页面会自动
受信任，因此向嵌入的 iframe 发送 trace 时不会出现信任提示。

## 完整示例

配套的 [`perfetto-embed`](https://github.com/LalitMaganti/perfetto-embed)
仓库是一个可运行的端到端示例：`npm start` 提供一个 "devtool" 宿主页面，
其控制面板嵌入 UI 并驱动它（加载 trace、缩放、固定 track、运行查询）。
它附带一个小型的、框架无关的 `PerfettoEmbed` 包装器，你可以复制到自己的
工具中，还有一个 React 变体。

## 参见

- [深度链接到 Perfetto UI](/docs/visualization/deep-linking-to-perfetto-ui.md)：
  `window.open()`（新标签页）流程，以及分享 URL 和 `appStateHash`。
- [嵌入 API 参考](/docs/visualization/embedding-api-reference.md)：
  UI 接受的完整消息和 URL 参数列表。
