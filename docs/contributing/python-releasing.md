# 制作新的 Python 库发布

本指南展示如何向 PyPI 发布新的 Perfetto Python 库。

包版本自动从 `CHANGELOG` 派生（顶部的 `vX.Y` 条目映射到 PyPI 版本 `0.X.Y`），因此没有单独的版本提升步骤。发布为单一阶段，由 `tools/release/release_python.py` 脚本驱动。

## 前置条件

- 从仓库根目录运行脚本。
- Python 虚拟环境必须存在于 `.venv`（脚本使用 `.venv/bin/python`）。
- 干净的 git 工作目录（没有未提交的更改）。
- PyPI 凭据：用户名为 `__token__`。对于密码（API 令牌），在 http://go/valentine 上查找"Perfetto PyPi API Key"。

## 发布

1. 选择要从中发布的发布提交 —— 通常是 `vX.Y` 标签提交。例如：

```bash
COMMIT=$(git rev-parse v56.0^{commit})
```

2. 运行发布脚本，传入该提交：

```bash
tools/release/release_python.py --publish --commit "$COMMIT"
```

脚本将执行以下步骤：

- **检出**：它将检出指定的提交。
- **构建和发布**：它将临时更新 `python/setup.py` 中的 `download_url` 为该提交的源码归档文件，构建包（版本从 `CHANGELOG` 读取），并在你确认后上传到 PyPI。系统将提示你输入 PyPI 凭据。
- **清理**：它将删除临时构建产物并恢复 `python/setup.py`。
- **最终 URL 更新**：发布后，脚本将提示你输入新分支名称。然后，它将在该分支上创建一个新提交，更新 `python/setup.py` 中的 `download_url` 以指向来自 `--commit` 参数的提交。

3. 脚本完成后，为 `download_url` 更新推送新分支并创建拉取请求。此最终 PR 合并后，发布完成。
