# Perfetto UI 发布流程

UI 有三个发布渠道，由 [channels.json](/ui/release/channels.json) 文件配置。渠道包括：

- `stable`，ui.perfetto.dev 上默认提供的版本。每四周更新一次。
- `canary`，一个不太稳定但较新的版本。每 1-2 周更新一次。
- `autopush`，UI 的当前 HEAD 版本。不稳定。

发布流程基于四周的周期。

- 第 1 周：将 `canary` 更新到 `HEAD`。
- 第 2 周：将 `canary` 更新到 `HEAD`。
 Canary 稳定化第 1/2 周从这里开始。
 只有关键错误修复可以被 cherry-pick 到 `canary`。
- 第 3 周：Canary 稳定化第 2/2 周。
- 第 4 周：将 `stable` 更新到当前的 `canary`，将 `canary` 更新到 `HEAD`。

第四周之后，周期从第一周重复。
这样是为了：

- Canary 在升级到 stable 之前有两周的 soak 时间。
- 较新的功能可以在一周内，最多两周（如果在稳定化周）在 Canary 中试用。
- Stable 用户每月不会受到超过一次的干扰。

## 更改发布渠道

NOTE: 渠道设置在页面重新加载之间是持久的。

UI 当前使用的渠道显示在左上角。如果 logo 后面的标签显示 `autopush` 或 `canary`，那就是当前渠道；如果没有显示标签，则当前渠道是 `stable`。

![perfetto-ui-channel.png](/docs/images/perfetto-ui-channel.png)

要更改 UI 在 `stable` 和 `canary` 之间使用的渠道，可以使用 [入口页面](https://ui.perfetto.dev) 上的切换开关。

![perfetto-ui-channel-toggle.png](/docs/images/perfetto-ui-channel-toggle.png)

要更改为 `autopush` 渠道，请打开侧边栏 `Support` 部分中的 `Flags` 屏幕，并在 `Release channel` 中选择 `Autopush`。

![perfetto-ui-channel-autopush-toggle.png](/docs/images/perfetto-ui-channel-autopush-toggle.png)

## 我正在使用哪个版本？

你可以在 UI 的左下角看到你当前使用的 UI 版本。

![perfetto-ui-version.png](/docs/images/perfetto-ui-version.png)

点击版本号将带你到 GitHub，在那里你可以看到哪些提交是该版本的一部分。版本号格式为 `v<maj>.<min>.<Commit SHA1 prefix>`，其中 `<maj>.<min>` 从 [CHANGELOG](/CHANGELOG) 的顶部条目中提取。

## Cherry-picking 更改

如果需要将更改 backport 到 canary 或 stable 分支，请执行以下操作：

```bash
git fetch origin
git co -b ui-canary -t origin/ui-canary
git cherry-pick -x $SHA1_OF_ORIGINAL_CL
git cl upload

# 如果需要，对 origin/ui-stable 分支重复。
```

一旦 cherry-picks 落地，发送一个 CL 来更新 `main` 分支中的 [channels.json](/ui/release/channels.json)。有关示例，请参阅 [r.android.com/1726101](https://r.android.com/1726101)。

```json
{
 "channels": [
 {
 "name": "stable",
 "rev": "6dd6756ffbdff4f845c4db28e1fd5aed9ba77b56"
 // ^ 这应该指向 origin/ui-stable 的 HEAD。
 },
 {
 "name": "canary",
 "rev": "3e21f613f20779c04b0bcc937f2605b9b05556ad"
 // ^ 这应该指向 origin/ui-canary 的 HEAD。
 },
 {
 "name": "autopush",
 "rev": "HEAD"
 // ^ 不要碰这个。
 }
 ]
}
```

其他分支中 `channels.json` 的状态是无关紧要的，发布基础设施只查看 `main` 分支来确定每个渠道的固定版本。

`channels.json` CL 落地后，构建基础设施将在 ~30 分钟内选取它并更新 ui.perfetto.dev。

Googlers：你可以在 [go/perfetto-ui-build-status](http://go/perfetto-ui-build-status) 上检查构建进度和 Log。有关服务基础设施的设计文档，请参阅 [go/perfetto-ui-autopush](http://go/perfetto-ui-autopush) 和 [go/perfetto-ui-channels](http:///go/perfetto-ui-channels)。

## 发布 Perfetto Chrome 扩展
Googlers：请参阅 go/perfetto-release-chrome-extension
