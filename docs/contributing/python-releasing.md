# 制作新的 Python 库发布

本指南展示如何向 PyPI 发布新的 Perfetto Python 库。

发布过程分为两个阶段，都由
`tools/release/release_python.py` 脚本编排。

## 阶段 1： 提升版本

第一阶段创建一个拉取请求以更新包版本。

1. 从仓库根目录运行发布脚本。

```bash
tools/release/release_python.py --bump-version
```

脚本将引导你完成以下步骤：

- **版本控制**：它将显示 `python/setup.py` 中的当前版本并提示你输入新版本。
- **分支**：它将提示你输入新分支名称并创建它。
- **提交**：它将更新 `python/setup.py` 中的 `version` 并创建提交。

2. 脚本完成后，推送新分支并创建拉取请求。

3. 拉取请求经过审查和合并后，进入阶段 2。

## 阶段 2： 发布发布和更新下载 URL

第二阶段将包发布到 PyPI，然后创建第二个拉取请求以使用正确的下载 URL 更新源代码。

1. 找到来自阶段 1 的已合并版本提升 CL 的提交哈希。

2. 再次运行发布脚本，提供已合并的提交哈希。

```bash
tools/release/release_python.py --publish --commit <landed-commit-hash>
```

脚本将执行以下步骤：

- **检出**：它将检出指定的提交。
- **构建和发布**：它将临时更新 `python/setup.py` 中的 `download_url`，构建包，并将其上传到 PyPI。系统将提示你输入 PyPI 凭据。对于用户名，使用 `__token__`。对于密码（API 令牌），在 http://go/valentine 上查找"Perfetto PyPi API Key"。
- **清理**：它将删除临时构建产物。
- **最终 URL 更新**：发布后，脚本将提示你输入新分支名称。然后，它将在该分支上创建一个新提交，更新 `python/setup.py` 中的 `download_url` 以指向来自 `--commit` 参数的提交。

3. 脚本完成后，为 `download_url` 更新推送新分支并创建第二个拉取请求。此最终 PR 合并后，发布完成。
