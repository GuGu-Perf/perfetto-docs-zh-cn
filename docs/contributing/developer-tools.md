# Perfetto 开发者工具

Perfetto 团队创建了一些脚本/工具，用于导航和
使用 Perfetto 代码库。本文主要针对 Perfetto 的频繁贡献者（例如团队成员或发送大量 PR 的外部贡献者）。

这些工具有一定的学习曲线，但可以显著
加速开发者体验。

## 持续集成

GitHub Actions 上的 Perfetto CI 覆盖了在大多数平台和工具链上的构建和测试，
大约需要 30 分钟。大多数构建失败和错误都在 Perfetto CI 级别被检测到。

你还可以
[针对 Chrome 的 TryBots 测试挂起的 Perfetto CL](testing.md#chromium)。

## 使用 GitHub 的"堆叠差异"

从我们在 Android 的日子起，Perfetto 长期以来一直在"堆叠差异"模型上工作，
这也是我们在团队内部非常喜欢的一个模型。然而，GitHub 非常
没有针对堆叠差异进行优化。

我们在生态系统中探索了一堆工具(git-town、Graphite、git-spice、
git-stack)，由于各种原因，没有一个符合我们的所有要求。这些
要求是：

1. 使用分支作为"PR"的基本单位 _而不是_ 提交

- 这是我们从 Android 时代习惯的，我们都喜欢它。

2. 不替换正常的 git 命令，而是使使用它们更容易

- 我们不是在寻找一个想要接管 git 所有部分的系统，只是
 某种让事情变得更容易的东西

3. _重要_ 通过合并 _而不是_ 变基来更新堆叠

- 最关键的一个，淘汰了一堆工具。
- 这里主要的问题是，如果你 rebase + force-push,GitHub 对审查者来说会严重破坏。
- 虽然对作者来说好多了，但对审查者的成本太高。

为此，我们开发了一些 Python 脚本，它们存在于我们的工具
文件夹中并实现了上述内容。你可以将它们添加到你的 git 别名中。修改
你的 `.gitconfig` 以包含以下内容：

```
[alias]
 # 基于父分支创建新分支并设置其父配置
 # 用法: git new-branch <new_branch_name> [--parent <parent_branch>]
 new-branch = "!f() { ./tools/git_new_branch.py \"$@\"; }; f"

 # 设置目标分支的父分支(默认:当前)
 # 用法: git set-parent <parent_branch> [--target <branch>]
 set-parent = "!f() { ./tools/git_set_parent.py \"$@\"; }; f"

 # 重命名本地分支并更新子级的父配置
 # 用法: git rename-branch --new <new_name> [--target <old_name>]
 rename-branch = "!f() { ./tools/git_rename_branch.py \"$@\"; }; f"

 # 检出目标分支的配置父分支(默认:当前)
 # 用法: git goto-parent [--target <branch>]
 goto-parent = "!f() { ./tools/git_goto_parent.py \"$@\"; }; f"

 # 查找并检出目标分支的子分支(默认:当前)
 # 用法: git goto-child [--target <branch>]
 goto-child = "!f() { ./tools/git_goto_child.py \"$@\"; }; f"

 # 通过合并更新本地堆叠段(目标+祖先+后代)
 # 用法: git update-stack [--target <branch>]
 update-stack = "!f() { ./tools/git_update_stack.py \"$@\"; }; f"

 # 使用拓扑排序通过合并更新所有本地堆叠
 # 用法: git update-all
 update-all = "!f() { ./tools/git_update_all.py \"$@\"; }; f"

 # 推送完整堆叠段(目标+祖先+后代)并同步 GitHub PR
 # 用法: git sync-stack [--target <branch>] [--remote <name>] [--draft] [--force]
 sync-stack = "!f() { ./tools/git_sync_stack.py \"$@\"; }; f"

 # 删除所有与其有效父分支相同(无差异)的本地分支
 # 用法: git prune-all [--dry-run]
 prune-all = "!f() { ./tools/git_prune_all.py \"$@\"; }; f"
```

所有这些工具都通过在仓库的 gitconfig 中添加一个名为
`branch.{branch_name}.parent` 的条目来工作，该条目跟踪父分支。这
然后用于确定什么是"堆叠"，然后对其进行操作。

使用这些工具的正常工作流程可能如下所示：

```
# 为功能创建分支。
git new-branch dev/${USER}/my-feature

# .... 修改，进行更改

# 提交；将用作 PR 标题
git commit -a -m 'My feature'

# 在功能之上添加内容创建新分支。
git new-branch dev/${USER}/my-feature-2 --current-parent

# ... 修改，进行更改

# 提交；将用作 PR 标题
git commit -a -m 'My feature changes'

# 从上述内容创建 GitHub PR,正确设置基本分支和
# 基于提交消息的 PR 描述。
git sync-stack

# 转到 my-feature 以响应审查
git goto-parent

# ... 为审查进行更改

git commit -a -m 'Respond to review'

# 更新堆叠,以便 my-feature-2 也有此提交。
git update-stack

# 同步到 GitHub。
git sync-all

# ... my-feature 在 GitHub 上获得批准并合并。

# 再次合并以使所有内容保持最新。
git update-stack

# 修剪 my-feature,因为不再需要它
git prune-all
```
