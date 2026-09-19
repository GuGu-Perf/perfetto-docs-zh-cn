# 制作新的 Python 库发布

本指南展示如何向 PyPI 发布新的 Perfetto Python 库。

包版本自动从 `CHANGELOG` 派生（顶部的 `vX.Y` 条目映射到 PyPI 版本 `0.X.Y`），因此没有单独的版本提升步骤。

正常路径是 `finalize-release.yml` GitHub 工作流的 `publish-pypi` 作业，它作为完成发布的一部分运行。下方的手动路径由 `tools/release/release_python.py` 驱动，是备用方案。

## 预构建文件锁定

该包在 `python/perfetto/prebuilts/manifests` 下附带预构建清单，`TraceProcessor` 会下载其中锁定的 `trace_processor`。这些清单只在发布打标签之后才会滚动到 `main`，因为它们对 LUCI 从该标签构建的二进制文件进行了哈希。因此，标签 `vX.Y` 处的代码树仍然锁定上一个版本，直接从该标签朴素构建的包会附带错误的 `trace_processor`。

因此，两条发布路径都会在构建之前为 `vX.Y` 重新生成清单；并且当设置了 `PERFETTO_PYPI_RELEASE` 而 `python/perfetto/prebuilts/manifests/version.py` 中的锁定版本与包版本不匹配时，`python/setup.py` 会拒绝构建。绝不发布在没有设置该变量的情况下构建的包。

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
- **滚动清单**：它将运行 `tools/release/roll-prebuilts --manifests-only vX.Y`，使包锁定到正在发布的版本的预构建文件。该标签的 LUCI 构建必须已完成，否则下载会失败。
- **构建和发布**：它将临时更新 `python/setup.py` 中的 `download_url` 为该提交的源码归档文件，构建包（版本从 `CHANGELOG` 读取），并在你确认后上传到 PyPI。系统将提示你输入 PyPI 凭据。
- **清理**：它将删除临时构建产物并恢复 `python/setup.py` 和清单。
- **最终 URL 更新**：发布后，脚本将提示你输入新分支名称。然后，它将在该分支上创建一个新提交，更新 `python/setup.py` 中的 `download_url` 以指向来自 `--commit` 参数的提交。

3. 脚本完成后，为 `download_url` 更新推送新分支并创建拉取请求。此最终 PR 合并后，发布完成。
