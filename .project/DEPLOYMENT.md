# Perfetto 中文文档部署指南

本文档介绍如何将翻译完成的中文文档部署到 Perfetto 官方构建系统中。

## 前提条件

- **Node.js** 环境（用于运行构建脚本）
- **Git**（用于克隆仓库）
- **操作系统**: macOS / Linux / Windows (Git Bash / WSL)
- 已完成的中文翻译文档（本仓库 `perfetto-docs-zh-cn/`）

### 平台特定要求

**macOS:**
- 无需额外安装（perl 已内置）

**Linux:**
- 可选安装 `timeout` 命令（通常已内置）
- 或安装 `coreutils` 包

**Windows:**
- 使用 **Git Bash**（推荐）: https://git-scm.com/download/win
- 或使用 **WSL** (Windows Subsystem for Linux)
- 确保 Git Bash 在安装时选择了 "Use Git and optional Unix tools from the Command Prompt"

## 快速开始

在项目根目录执行：

```bash
./perfetto-docs-zh-cn/.project/deploy.sh
```

或手动执行以下步骤：

---

## 手动部署步骤

### 步骤 0: 检查并准备 Perfetto 仓库

```bash
# 检查 perfetto 仓库是否存在
if [ ! -d "perfetto/.git" ]; then
    echo "Perfetto 仓库不存在，正在克隆..."
    git clone https://github.com/google/perfetto.git perfetto
fi

# 进入 perfetto 目录
cd perfetto
```

### 步骤 1: 备份原文档

```bash
# 仅在 docs 目录存在且有内容时备份
if [ -d "docs" ] && [ "$(ls -A docs 2>/dev/null)" ]; then
    BACKUP_FILE="docs-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
    echo "备份原文档到: $BACKUP_FILE"
    tar -czf "$BACKUP_FILE" docs/
fi
```

### 步骤 2: 清空并复制文档

```bash
# 清空 docs 目录（包括隐藏文件）
rm -rf docs/* docs/.[!.]* 2>/dev/null || true

# 复制中文文档的所有内容
# 假设中文文档在 perfetto-docs-zh-cn/ 目录（与 perfetto/ 同级）
cp -r ../perfetto-docs-zh-cn/* docs/
```

### 步骤 3: 清理项目管理文件

```bash
cd docs/
rm -rf .project/        # 删除项目管理目录
rm -rf .git/            # 删除 git 目录（如果存在）
cd ..
```

### 步骤 4: 构建并启动服务器（官方方式）

```bash
# 使用官方命令，无论首次还是增量编译
# 官方命令会自动处理增量编译和 MIME 类型
node infra/perfetto.dev/build.js --serve
```

**构建过程**:
- 第一次构建会下载依赖并编译，耗时较长（约 2-5 分钟）
- 后续构建会自动进行增量编译
- 构建成功后会看到 `Starting HTTP server on http://localhost:8082`

**如何判断是编译还是卡住？**

部署脚本会自动监控编译进度：
- ✅ **编译进行中**：每几秒会看到新的输出（如 `[10/379] ACTION ...`）
- ⚠️ **编译缓慢**：20秒无输出会提示"编译似乎没有进展"
- ❌ **编译卡住**：60秒无输出会判定为卡住并报错

**访问地址**: http://localhost:8082/docs/

---

## 自动化部署脚本

脚本位于 `perfetto-docs-zh-cn/.project/deploy.sh`，它会：

1. 检查并克隆 Perfetto 仓库
2. 备份原文档
3. 清空并复制中文文档
4. 清理管理文件
5. 使用官方命令启动服务器

---

## 目录结构说明

推荐的目录结构：

```
workspace/
├── perfetto/                    # Perfetto 官方仓库（自动克隆）
│   ├── docs/                    # 文档目录（会被中文文档替换）
│   ├── infra/perfetto.dev/      # 构建系统
│   ├── out/perfetto.dev/site/   # 构建输出
│   └── ...
└── perfetto-docs-zh-cn/         # 中文文档仓库
    ├── .project/
    │   ├── DEPLOYMENT.md        # 本文件
    │   └── deploy.sh            # 自动化脚本
    ├── README.md
    ├── toc.md
    └── ...
```

---

## 常见构建错误及解决方案

### 错误 1: 死链错误（Dead link）

**错误信息**:
```
Error: Dead link: /docs/some-file.md in ../../docs/some-document.md
```

**解决方案**:

1. **检查引用位置**:
   ```bash
   grep -n "some-file" docs/some-document.md
   ```

2. **判断文件是否应该存在**:
   - 如果是必需文件，从英文备份恢复：
     ```bash
     tar -xzf docs-backup-*.tar.gz docs/some-file.md
     ```
   - 如果文件不存在于官方文档中，删除引用：
     ```bash
     vim docs/some-document.md
     ```

### 错误 2: 缺少必需文件

**错误信息**:
```
ERROR at //infra/perfetto.dev/BUILD.gn:342:3: Item not found
rebase_path("../../docs/README.md", root_build_dir)
```

**解决方案**:

检查中文文档根目录是否有这些文件：
```bash
ls perfetto-docs-zh-cn/ | grep -E "README|toc|_coverpage"
```

### 错误 3: 端口被占用

**错误信息**:
```
Error: listen EADDRINUSE: address already in use :::8082
```

**解决方案**:

```bash
# 方法 1: 停止占用端口的进程
lsof -nP -iTCP:8082 -sTCP:LISTEN | awk 'NR>1 {print $2}' | xargs kill -9

# 方法 2: 使用其他端口
node infra/perfetto.dev/build.js --serve --port 8083
```

### 错误 4: 依赖过期

**错误信息**:
```
Dependencies are out of date
```

**解决方案**:
```bash
./tools/install-build-deps --ui
```

### 错误 5: Windows 上命令未找到

**错误信息**:
```
bash: command not found
```

**原因**: 在 Windows CMD/PowerShell 中直接运行 bash 脚本

**解决方案**:
1. **使用 Git Bash**:
   - 右键点击桌面 -> "Git Bash Here"
   - 或在文件资源管理器中右键点击项目文件夹 -> "Git Bash Here"
   - 然后运行: `bash perfetto-docs-zh-cn/.project/deploy.sh`

2. **使用 WSL**:
   ```bash
   wsl
   cd /mnt/c/path/to/your/project
   bash perfetto-docs-zh-cn/.project/deploy.sh
   ```

3. **使用 VS Code**:
   - 安装 "Git Bash" 终端
   - Ctrl+Shift+P -> "Terminal: Select Default Profile" -> "Git Bash"
   - 在终端中运行脚本

### 错误 6: Windows 上端口无法清理

**错误信息**:
```
端口 8082 被占用，无法清理
```

**解决方案**:
```powershell
# 以管理员身份运行 PowerShell
netstat -ano | findstr :8082
taskkill /PID <PID> /F
```

或手动关闭占用 8082 端口的程序。

---

## 构建输出说明

构建成功后，静态文件位于：

```
perfetto/out/perfetto.dev/site/
├── docs/                    # 文档页面
│   ├── getting-started/     # 入门指南
│   ├── analysis/            # 分析文档
│   ├── concepts/            # 概念文档
│   ├── data-sources/        # 数据源文档
│   └── ...
├── index.html               # 主页
└── assets/                  # 静态资源
```

---

## 部署检查清单

- Perfetto 仓库已存在或已克隆
- 中文文档已完整复制到 `docs/` 目录
- 已删除 `.project/` 管理目录
- 构建成功，无死链错误
- 可以正常访问 http://localhost:8082/docs/
- 文档内容显示为中文

---

## 故障排除流程

1. **查看 Error log**
   ```bash
   # Build log 会显示具体的错误信息
   # 关注 "Error: Dead link" 或 "Item not found" 等关键词
   ```

2. **定位缺失文件**
   ```bash
   grep -r "missing-file" perfetto/docs/
   ```

3. **修复问题**
   - 死链：删除或修复引用
   - 缺失文件：从中文文档或英文备份中复制

4. **重新构建**
   ```bash
   # 清理构建目录后重新构建
   rm -rf perfetto/out/perfetto.dev
   cd perfetto && node infra/perfetto.dev/build.js --serve
   ```

---

## 总结

部署成功的关键要点：

1. ✅ **自动检测** - 脚本自动检查仓库和构建状态
2. ✅ **智能编译** - 增量编译加速后续部署
3. ✅ **完整复制** - 确保 docs/ 目录完全替换
4. ✅ **删除管理文件** - `.project/` 目录不属于构建系统
5. ✅ **修复死链** - 删除指向不存在文件的引用
