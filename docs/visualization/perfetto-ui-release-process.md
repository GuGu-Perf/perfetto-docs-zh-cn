# Perfetto UI 发布流程

UI 有三个发布渠道。每个渠道从一个长期分支的 HEAD 提供服务：

- `stable`，ui.perfetto.dev 上默认提供的版本。从 `stable` 分支提供服务，每四周更新一次。
- `canary`，一个不太稳定但较新的版本。每 1-2 周更新一次。从 `canary` 分支提供服务。
- `autopush`，UI 的当前 HEAD 版本。不稳定。从 `main` 分支提供服务。

发布流程基于四周的周期。

- 第 1 周：从 `main` 切割 `canary`。
- 第 2 周：从 `main` 切割 `canary`。Canary 稳定化第 1/2 周从这里开始。只有关键错误修复可以被 cherry-pick 到 `canary`。
- 第 3 周：Canary 稳定化第 2/2 周。
- 第 4 周：将当前 `canary` 提升为 `stable`，然后从 `main` 切割 `canary`。

第四周之后，周期从第一周重复。这样是为了：

- Canary 在提升为 stable 之前有两周的 soak 时间。
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

点击版本号将带你到 GitHub，在那里你可以看到哪些提交是该版本的一部分。版本号格式为 `v<maj>.<min>`，其中 `<maj>.<min>` 从 [CHANGELOG](/CHANGELOG) 的顶部条目中提取。

## Cherry-picking 更改

如果需要将更改 backport 到 canary 或 stable 分支，请执行以下操作：

```bash
git fetch origin
git checkout -b cherry-pick-canary origin/canary
git cherry-pick -x $SHA1_OF_ORIGINAL_CL
git cl upload

# 如果需要，从 origin/stable 重复。
```

一旦 cherry-pick 落地到 `canary` 或 `stable`，推送到该分支会触发对应 UI 渠道的 Cloud Build。没有单独的渠道固定文件需要更新。

要进行正常的发布渠道迁移，请使用 GitHub Actions 工作流：

- `Cut canary (open PR merging main -> canary)` 开启一个针对 `canary` 的 PR。当该 PR 被合并时，Cloud Build 会重新部署 canary 渠道。
- `Promote to stable (open PR merging canary -> stable)` 开启一个针对 `stable` 的 PR。当该 PR 被合并时，Cloud Build 会重新部署 stable 渠道，并且 `tag-on-stable-push.yml` 会创建发布标签和草稿发布。

Googlers：你可以在 [go/perfetto-ui-build-status](http://go/perfetto-ui-build-status) 上检查构建进度和 Log。有关服务基础设施的设计文档，请参阅 [go/perfetto-ui-autopush](http://go/perfetto-ui-autopush) 和 [go/perfetto-ui-channels](http://go/perfetto-ui-channels)。

## 发布 Perfetto Chrome 扩展

Googlers：请参阅 go/perfetto-release-chrome-extension
