# 贡献指南

感谢你对 Perfetto 中文文档翻译项目的关注！本文档将帮助你了解如何参与翻译工作。

## 📋 目录

- [快速开始](#快速开始)
- [翻译流程](#翻译流程)
- [翻译规范](#翻译规范)
- [术语表](#术语表)
- [提交规范](#提交规范)
- [常见问题](#常见问题)

## 快速开始

### 1. Fork 仓库

点击右上角的 "Fork" 按钮，将仓库 fork 到你的 GitHub 账号下。

### 2. 克隆仓库

```bash
git clone https://github.com/YOUR_USERNAME/perfetto-docs-zh-cn.git
cd perfetto-docs-zh-cn
```

### 3. 创建分支

```bash
git checkout -b translate/your-branch-name
```

### 4. 开始翻译

在 `docs/` 目录下找到你要翻译的文件，使用 Markdown 编辑器进行翻译。

### 5. 本地预览

```bash
bash .project/deploy.sh
```

访问 http://localhost:8082/docs/ 预览效果。

### 6. 提交更改

```bash
git add .
git commit -m "translate: 翻译 XXX 文档"
git push origin translate/your-branch-name
```

### 7. 创建 Pull Request

在 GitHub 上创建 Pull Request，等待审核合并。

## 翻译流程

### 选择翻译文件

1. 查看 [翻译进度](#翻译进度) 了解当前状态
2. 在 Issue 中认领未翻译的文件
3. 或者选择标记为 "待改进" 的文件进行优化

### 翻译步骤

1. **阅读原文**：确保理解原文含义
2. **首次翻译**：快速完成初稿，不必追求完美
3. **术语统一**：对照术语表统一关键术语
4. **本地预览**：运行部署脚本查看效果
5. **检查修改**：通读全文，修正不通顺的地方
6. **提交审核**：创建 PR 等待审核

## 翻译规范

详细的翻译规范请参考 **[.project/TRANSLATION_GUIDE.md](.project/TRANSLATION_GUIDE.md)

## 提交规范

### Commit Message 格式

```
<type>: <subject>

<body>
```

### Type 类型

| 类型 | 说明 |
|------|------|
| `translate` | 翻译新文档 |
| `fix` | 修正翻译错误 |
| `improve` | 改进翻译质量 |
| `chore` | 构建/工具相关 |

### 示例

```bash
# 翻译新文档
git commit -m "translate: 完成 concepts/buffers.md 翻译"

# 修正错误
git commit -m "fix: 修正 analysis/metrics.md 中的术语错误"

# 改进翻译
git commit -m "improve: 优化 getting-started.md 的表达"
```

## 常见问题

### Q: 如何知道哪些文件需要翻译？

A: 查看 Issue 列表中标记为 "待翻译" 或 "help wanted" 的 Issue。

### Q: 翻译过程中遇到不理解的术语怎么办？

A: 
1. 首先查看术语表
2. 参考已有翻译文件中的处理方式
3. 在 Issue 中讨论确认

### Q: 可以修改已经翻译好的文件吗？

A: 可以！如果发现翻译错误或有更好的表达方式，欢迎提交改进。

### Q: 如何同步官方最新文档？

A: 项目维护者会定期同步官方文档。如果你想主动同步，可以：

```bash
# 进入 perfetto 目录
cd ../perfetto
git pull origin main

# 对比 docs 目录差异，手动同步更新
cd ../perfetto-docs-zh-cn
```

### Q: 本地预览报错怎么办？

A:
1. 确保 Node.js 已安装（v18+）
2. 确保端口 8082 未被占用
3. 查看日志文件 `/tmp/perfetto-deploy-*.log`
4. 在 Issue 中寻求帮助

## 项目状态

**翻译完成** - 全部 108 个文档已翻译完成

**持续维护** - 定期同步官方文档更新

### 如何参与维护

1. **同步官方更新** - 检查官方文档是否有新增或修改
2. **改进翻译质量** - 优化现有文档的表达
3. **修正错误** - 修复翻译错误或术语不一致

## 联系我们

- 提交 Issue：[GitHub Issues](https://github.com/GuGu-Perf/perfetto-docs-zh-cn/issues)
- 讨论区：[GitHub Discussions](https://github.com/GuGu-Perf/perfetto-docs-zh-cn/discussions)

感谢你的贡献！
