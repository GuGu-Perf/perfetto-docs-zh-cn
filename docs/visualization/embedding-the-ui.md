# 嵌入 Perfetto UI

本指南展示如何通过 `<iframe>` 将 Perfetto trace 查看器嵌入到**你自己的**
工具或 dashboard 中，并以编程方式向其提供 trace。当你希望 trace 视图
存在于你的应用的界面框架内时，这是正确的方法，正如 Dart DevTools 和
各种 profiler 前端等真正的工具所做的那样。如果你只是想在新浏览器标签页
中启动完整的 Perfetto UI（`window.open()` 流程），参见
[深度链接到 Perfetto UI](/docs/visualization/deep-linking-to-perfetto-ui.md)；
该页面还涵盖了分享 URL 和 `appStateHash`，本指南不再重复。

## 开始之前

- 通过 `http(s)` 提供你的宿主页面，而非 `file://`。嵌入协议依赖于
  窗口间的 `postMessage`，浏览器对 `file://` 来源会禁用此功能。
- **不要**使用 `Cross-Origin-Opener-Policy: same-origin` 头提供你的
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

握手完成后，发送带有 `perfetto` 键及 `buffer` 和可选 `title` 的对象：

```js
await waitForReady();

const resp = await fetch('/traces/my-trace.pftrace');
const buffer = await resp.arrayBuffer();

iframe.contentWindow.postMessage({
  perfetto: {
    buffer: buffer,
    title: 'My trace',
  }
}, '*');
```

完整的消息格式和按 `sliceId` 控制 UI 的信息，参见
[嵌入 API 参考](/docs/visualization/embedding-api-reference.md)。

## 步骤 4：配对新打开的 trace

如果宿主在 iframe 加载**之后**获取 trace（例如用户通过宿主 UI
选择一个 trace），你需要一种方式来告知 UI 正在发送一个新的 trace ——
否则 UI 将已打开的 trace 视为"之前的"并推迟它。

模式如下：

1. 在宿主中为此次加载生成一个唯一 key。
2. 将此 key 设置为 `<iframe>` 的 `src` 上的 `local_cache_key` 查询参数
   （或在动态修改 `src` 时）。
3. 发送消息时将同一个 key 作为 `localCacheKey` 设置到 `perfetto` 对象上。
   UI 将这两个 key 配对。

```js
const key = crypto.randomUUID();

// 设置 iframe src 以包含 key 参数。
const url = new URL(iframe.src);
url.searchParams.set('local_cache_key', key);
iframe.src = url.toString();

await waitForReady();
iframe.contentWindow.postMessage({
  perfetto: {
    buffer: buffer,
    title: 'My trace',
    localCacheKey: key,
  },
}, '*');
```

## 信任提示与生产环境 {#trust-prompts-and-going-to-production}

UI 维护一个受信任的客户端来源集合。如果宿主页面的来源在该集合中，
trace 会立即打开。如果不在，用户将看到一个一次性的模态框：

> `<origin>` 正在尝试打开一个 trace 文件。你信任该来源吗？

选项为 **No**、**Yes** 和 **Always trust**。

自动受信任的来源包括 `localhost`、`127.0.0.1`、`[::1]` 以及少数
硬编码的 Google 域名。生产环境中，用户因此会在第一次看到同意提示，
之后就不会再看到了（来源保存在 `localStorage` 中）。

如果你想要用户在嵌入时完全看不到提示，可以自行托管 UI
（参见下方[自行托管 UI](#self-hosting-the-ui)）。自行托管还会带来上述
同源信任的好处。

NOTE: UI 仅限客户端。发送的 trace 保留在浏览器内存中，绝不上传。

## 自行托管 UI

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
