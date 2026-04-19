# Perfetto 中文文档工具指南

本文档介绍统一脚本 `bash .project/workwork.sh` 的使用方法。

## 命令总览

| 命令 | 作用 |
|------|------|
| `deploy-local` | 本地部署并启动服务器 |
| `deploy-gh-pages` | 部署到 `gh-pages` |
| `sync-check` | 检查上游 `perfetto/docs` 是否有更新 |
| `sync-update` | 将上游最新 commit 更新到 `.project/LAST_SYNC` |


## 前提条件

- 已安装 **Git**
- 已安装 **Node.js** 和 **npm**
- 推荐使用 **macOS / Linux / WSL / Git Bash**

如果平级目录还没有 `perfetto` 仓库，脚本会自动执行 clone。

## 常用命令

### 1. 检查上游更新

```bash
bash .project/workwork.sh sync-check
```

### 2. 本地预览

```bash
bash .project/workwork.sh deploy-local
```

访问 <http://localhost:8082/docs/> 预览效果。

### 3. 更新同步记录

```bash
bash .project/workwork.sh sync-update
```

### 4. 发布到 GitHub Pages

```bash
bash .project/workwork.sh deploy-gh-pages
```
