---
name: perfetto-docs-zh-cn
description: >
  处理 Perfetto 中文文档翻译项目（perfetto-docs-zh-cn）时使用此技能。
  覆盖：翻译上游 Perfetto 文档更新、按术语标准审查翻译质量、
  浏览器自动化对比校对本地/线上站点渲染效果、同步上游仓库、
  部署到 GitHub Pages 并验证。
  当用户提到"翻译上游更新"、"检查文档过时"、"审查翻译质量"、
  "部署到 GitHub Pages"或本项目内的任何工作时触发。
---

# Perfetto 中文文档翻译项目

## 项目概述

本项目维护 Google Perfetto 官方文档的中文翻译，发布地址：
https://gugu-perf.github.io/perfetto-docs-zh-cn/

上游源为 https://github.com/google/perfetto 的 `docs/` 目录，
通过 `.project/LAST_SYNC` 跟踪同步点。项目使用 Perfetto 自己的
构建系统（`infra/perfetto.dev/build.js`）生成静态站点。

## 核心工作流

### 1. 检查上游更新

检测上游 Perfetto 文档自上次同步以来是否有变更：

```bash
bash .project/workwork.sh sync-check
```

该命令对比 `.project/LAST_SYNC` 中记录的 commit 与上游 perfetto
仓库（克隆于 `../perfetto`）中 `docs/` 目录的最新 commit，
如有更新则输出变更文件列表。

### 2. 翻译上游更新

当上游有新文件或修改文件时，按以下步骤操作：

**步骤 A：识别变更**
获取 LAST_SYNC commit 与上游最新 HEAD 之间的差异：

```bash
cd ../perfetto && git diff <last_sync_commit> HEAD -- docs/ | cat
```

**步骤 B：翻译每个变更文件**
对每个变更的 markdown 文件：

1. 读取上游完整文件内容
2. 严格按照 `.project/TRANSLATION_GUIDE.md` 中的规范进行翻译
   （开始任何翻译前先加载该参考文件）
3. 将译文写入本仓库 `docs/` 目录下的对应路径

关键翻译规则总结：
- 术语表中标记为"否"的术语必须保持英文不翻译（如 Trace、
  Buffer、Track、profiling、hook、SDK、Plugin）
- 标记为"是"的术语必须翻译为中文
- NOTE:、TIP:、WARNING:、Summary: 前缀保持英文
- 代码块、API 名称、命令、版本号：绝不翻译
- URL 和图片路径：绝不修改
- Markdown 结构与原文 100% 一致
- 中文使用全角标点（。而非 .），中英文之间加空格

**步骤 C：处理新增图片**
如果差异中包含 `docs/images/` 下的新图片文件，
从上游 perfetto 仓库复制到本项目的 `docs/images/` 目录。

### 3. 审查翻译质量

审查一个或多个文件的翻译质量：

1. 加载 `.project/TRANSLATION_GUIDE.md` 获取完整术语表
2. 对照上游原文逐字阅读译文
3. 检查以下项目：
   - 术语违规（应保持英文却被翻译，或反之）
   - NOTE:/TIP:/WARNING: 前缀被翻译为中文
   - 代码或 API 名称被错误翻译
   - Markdown 结构缺失或改动
   - 中文标点和空格错误
4. 报告所有发现的问题，包含：文件路径、行号引用、原文、
   当前译文、建议修改

### 4. 本地部署 + 浏览器校对

构建翻译后的站点并启动本地服务器，然后使用浏览器自动化
逐页对比本地站点与 Perfetto 官网（https://perfetto.dev/docs/），
确保渲染效果一致。

**步骤 A：本地部署**

```bash
bash .project/workwork.sh deploy-local
```

脚本会：
- 按需克隆/更新上游 perfetto 仓库
- 用中文翻译替换其 docs/ 目录
- 修补 BUILD.gn 使首页使用 README.md
- 启动 `node infra/perfetto.dev/build.js --serve`

**步骤 B：浏览器自动化校对**

使用 `playwright-cli` 或 `agent-browser` 技能，打开本地站点
（http://localhost:8082/docs/）和官网（https://perfetto.dev/docs/）
进行逐页对比校对。

**校对覆盖范围**：

需要比对的页面包括但不限于：
- 首页（/）
- `/docs/` 下每个子页面
- 导航栏、侧边栏结构

每个页面对比项目：

| 检查项 | 说明 |
|--------|------|
| 导航栏 | 菜单项数量、文字、顺序是否与官网一致 |
| 页面标题（H1） | 是否存在、位置是否正确 |
| 标题层级（H2～H6） | 各级标题数量及锚点链接是否与官网一致 |
| 标志块 | NOTE:/TIP:/WARNING: 块的数量和位置是否匹配 |
| 代码块 | 代码块数量和语言标注是否一致 |
| 链接 | 关键链接数量和目标是否对应 |
| 图片 | 图片数量、alt 文本、是否正常加载 |
| 表格 | 表格数量、行列数是否匹配 |
| 中文标点 | 是否使用了中文全角标点（。、，！？），中英文之间是否有空格 |
| 整体版面 | 页面内容区域宽度、间距、字体层级感是否与官网一致 |

**步骤 C：分析差异并修复**

对每个不一致项：
1. 判断原因：翻译遗漏 / 翻译错误 / Markdown 结构破坏 / 构建问题
2. 修改对应的源文件（`docs/` 下的 .md 文件）
3. 重新执行 `deploy-local` 构建部署
4. 重新用浏览器打开该页面，验证修复效果

重复"修复 → 重新部署 → 重新校对"循环，直到所有页面通过。

### 5. 部署到 GitHub Pages + 上线验证

```bash
bash .project/workwork.sh deploy-gh-pages
```

构建站点、修复 GitHub Pages 路径（仓库名前缀、无扩展名文件
添加 .html 后缀）、强制推送到 `gh-pages` 分支。

推送完成后，等待 1～2 分钟 CDN 刷新，然后使用浏览器自动化
访问线上地址 https://gugu-perf.github.io/perfetto-docs-zh-cn/，
执行与第 4 节相同的校对流程：

1. 打开线上首页和关键子页面
2. 逐项对比官网，检查导航、标题、标志块、图片、链接等
3. 如发现线上部署后才暴露的问题（如路径错误、资源 404），
   立即修复源文件，重新执行 `deploy-gh-pages` 并再次验证
4. 确认所有关键页面渲染正常后，报告"部署完成并验证通过"

### 6. 更新同步记录

翻译完成并验证质量后，更新 LAST_SYNC：

```bash
bash .project/workwork.sh sync-update
```

然后提交并推送：

```bash
git add .project/LAST_SYNC
git commit -m "chore: update LAST_SYNC to <commit_hash>"
```

## 项目结构

| 路径 | 用途 |
|------|------|
| `docs/` | 翻译后的中文文档（镜像上游 `perfetto/docs/`） |
| `.project/workwork.sh` | 统一工具脚本（deploy、sync-check、sync-update） |
| `.project/LAST_SYNC` | 本仓库同步到的上游 commit |
| `.project/TRANSLATION_GUIDE.md` | 完整翻译规则和术语表 |
| `CONTRIBUTING.md` | 贡献工作流和 commit 规范 |
| `README.md` | 项目首页（同时用作站点首页） |

## Commit 规范

| 类型 | 用途 |
|------|------|
| `translate` | 翻译新文档 |
| `fix` | 修复翻译错误 |
| `improve` | 改进翻译质量 |
| `chore` | 构建/工具链变更 |

示例：`translate: sync upstream docs update (da70e558..95328907)`

## 关键参考文件

- `.project/TRANSLATION_GUIDE.md` — 完整翻译规范，含 120+ 术语表。
  翻译或审查前必须先加载。
- `.project/workwork.md` — workwork.sh 脚本的详细使用说明。
- `.project/workwork.sh` — 统一工具（deploy-local、deploy-gh-pages、sync-check、sync-update）。
- `CONTRIBUTING.md` — 贡献工作流和 commit 规范。
