# 制作新的 SDK 发布

本指南展示如何制作新的 Perfetto SDK 发布。

在快照发布之前，检查没有打开的[发布阻止项](http://b/savedsearches/5776355)。

签出代码，然后为新发布决定版本号（vX.Y）。
主版本号（X）在每次发布时递增（每月）。
次要版本号仅在每月发布之上的次要更改/修复时递增（在 releases/vN.x 分支上的 cherry-pick）。

继续下面的适当部分。

## a) 创建新的主版本

确保当前的 main 分支在
[LUCI](https://luci-scheduler.appspot.com/jobs/perfetto) 上构建，方法是触发所有
构建并等待它们成功。如果任何构建失败，请在继续之前在 main 上修复失败。

在 CHANGELOG 中创建一个新主版本的条目：这通常涉及
将"Unreleased"条目重命名为你之前选择的版本号
([示例](https://r.android.com/2417175))。

测试 perfetto 构建工具可以解析 CHANGELOG：构建后，
运行 `perfetto --version` 应该显示你的新版本号。

上传 CHANGELOG 更改并在 main 分支上提交它。

为新主版本创建发布分支(这里是"v16.x"):

```bash
git fetch origin
git push origin origin/main:refs/heads/releases/v16.x
git fetch origin
git checkout -b releases/v16.x -t origin/releases/v16.x
```

继续[构建发布](#building-and-tagging-the-release)。

## b) 提升次要版本

签出现有发布分支（这里是"5.x"）并合并新发布所需的
修订，解决你可能遇到的任何冲突。

```bash
git checkout -b releases/v16.x -t origin/releases/v16.x
```

如果你只想在新发布中引入一个或两个补丁，请考虑
单独 cherry-pick 它们：

```bash
git cherry-pick <sha1>
```

否则，你可以进行完整合并：

```bash
git merge <sha1>
```

使用新次要版本的专用条目更新 CHANGELOG。
这很重要，因为
由构建系统调用的 [write_version_header.py](/tools/write_version_header.py) 脚本
查看 CHANGELOG 以找出最新的
v${maj}.${min} 版本。

有关示例，请参阅 [r.android.com/1730332](https://r.android.com/1730332)

```txt
v16.1 - 2021-06-08:
 Tracing service and probes:
  - Cherry-pick of r.android.com/1716718 which missed to v16 branch ... .


v16.0 - 2021-06-01:
 ...
```

## 标记发布

1. 一旦发布的所有更改都已合并到发布分支中，
 为其创建并推送标记（"vX.Y"是新版本）。

```bash
# 确保分支是最新的
git pull

git status
# 应该打印:Your branch is up to date with 'origin/releases/v16.x'。
# 如果你的分支与 origin/releases/vX.X 分歧，请勿继续

git tag -a -m "Perfetto vX.Y" vX.Y
git push origin vX.Y
```

2. 更新文档以指向最新发布。

  - [docs/instrumentation/tracing-sdk.md](/docs/instrumentation/tracing-sdk.md)
  - [examples/sdk/README.md](/examples/sdk/README.md)

6. 发送一封带有 CHANGELOG 的电子邮件到 perfetto-dev@，抄送 perfetto-announce@
 （内部 - 执行前请确保你有权限）和
 [公开 perfetto-dev](https://groups.google.com/forum/#!forum/perfetto-dev)。

## 使用预构建和 SDK 源代码创建 GitHub 发布

3. 几分钟内，LUCI 调度器将触发 https://luci-scheduler.appspot.com/jobs/perfetto 上的预构建二进制文件构建。
 等待所有机器人成功完成并返回到 WAITING 状态。

4. 在运行打包脚本之前签出发布标记：

```bash
git checkout vX.Y
```

5. 运行 `tools/release/package-github-release-artifacts vX.Y`。这将：
  - 验证工作目录是干净的(没有未提交的更改)
  - 验证你在正确的 git 标记（vX.Y）上
  - 从 LUCI 下载预构建二进制文件
  - 从当前检出生成合并的 SDK 源文件
  - 将所有内容打包到 `/tmp/perfetto-vX.Y-github-release/`

  - 必须总共有 12 个 zip 文件：
  - 10 个预构建二进制文件：linux-{arm,arm64,amd64},
 android-{arm,arm64,x86,x64}, mac-{amd64,arm64}, win-amd64
  - 2 个 SDK 源代码 zip:perfetto-cpp-sdk-src.zip, perfetto-c-sdk-src.zip
  - 如果一个或多个预构建 zip 缺失，这意味着 LUCI 机器人之一失败，
 检查 Log(遵循调用 Log 中的"Task URL: "链接)。
  - 如果发生这种情况，你需要使用修复重新生成 vX.(Y+1) 发布
 (查看历史 v20.1，其中 Windows 失败需要重新生成)。

6. 打开 https://github.com/google/perfetto/releases/new 并
  - 选择"Choose Tag" -> vX.Y
  - "Release title" -> "Perfetto vX.Y"
  - "Describe release" -> 复制 CHANGELOG，将其包装在三重反引号中。
  - "Attach binaries" -> 附加上一步中的所有十二个 .zip 文件
 (10 个预构建二进制文件 + 2 个 SDK 源代码 zip)。

7. 运行 `tools/roll-prebuilts vX.Y`。它将更新 `tools/` 下各种脚本中的 SHA256。
 上传带有更改的 CL。

8. 发送一封带有 CHANGELOG 的电子邮件到 perfetto-dev@（内部）和
 [公开 perfetto-dev](https://groups.google.com/forum/#!forum/perfetto-dev)。

9. 呼，你完成了！
