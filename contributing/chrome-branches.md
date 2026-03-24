# 为 Chrome 里程碑分支 Perfetto

将一个(或一组)Perfetto 更改合并到 Chrome 里程碑版本需要在 perfetto 仓库中创建一个分支，将更改 cherry-pick 到该分支，并更新 Chrome 里程碑分支中的 `DEPS` 文件以指向新的 perfetto 分支的 HEAD。

## 创建 perfetto 分支 {#branch}

1. 确定分支名称：`chromium/XXXX`，其中 `XXXX` 是里程碑的分支号(参见
 [Chromium Dashboard](https://chromiumdash.appspot.com/branches))。M87 的示例：
 `chromium/4280`。

1. 检查分支是否已存在：如果是，跳到
 [cherry-picking](#cherry-pick)。要检查，你可以在
 https://github.com/google/perfetto/branches 中搜索它。

1. 查找分支的适当基础修订版本。你应该使用
 Chrome 里程碑分支的 `DEPS` 指向的修订版本(在文件中搜索
 `perfetto`)。分支 XXXX 的 `DEPS` 文件位于：

 `https://chromium.googlesource.com/chromium/src.git/+/refs/branch-heads/XXXX/DEPS`

 M87 的示例：
 [`DEPS`](https://chromium.googlesource.com/chromium/src.git/+/refs/branch-heads/4280/DEPS)
 （在撰写时）指向 `f4cf78e052c9427d8b6c49faf39ddf2a2e236069`。

1. 创建分支：
 询问 [perfetto-team](https://github.com/orgs/google/teams/perfetto-team/)
 的成员通过 `git push origin 4cf78e05:chromium/4280` 创建 chromium/XXXX 分支。

## Cherry-picking 更改 {#cherry-pick}

1. 在本地 cherry-pick 提交并针对该分支发送 pull-request
 像往常一样。

 ```
 $ git fetch origin
 $ git checkout -tb cpick origin/chromium/XXXX
 $ git cherry-pick -x <commit hash> # 手动解决冲突。
 $ tools/gen_all out/xxx # 如果必要。
 $ gh pr create
 ```

1. 发送 pull request 进行审查并合并。
 记下提交的修订哈希。

## 在 Chromium 中更新 DEPS 文件

1. 创建，发送审查并合并一个 Chromium 补丁，该补丁编辑 Chrome
 里程碑分支上的顶级 `DEPS` 文件。你还可以将此步骤与任何 chromium 更改的 cherry-picks 结合起来。有关详细信息，请参阅
 [Chromium 的文档](https://www.chromium.org/developers/how-tos/cover)。这相当于：

 ```
 $ gclient sync --with_branch_heads
 $ git fetch
 $ git checkout -tb perfetto_uprev refs/remotes/branch-heads/XXXX
 $ ... # 编辑 DEPS。
 $ git cl upload
 ```
