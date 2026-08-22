# 实战指南：在 Perfetto 中使用 AI

NOTE: **Googlers**：请使用 [go/perfetto-ai-skills](http://go/perfetto-ai-skills)
和
[go/perfetto-ai-skills-android-memory](http://go/perfetto-ai-skills-android-memory)，
而非此页面。

Perfetto 为编程 Agent 提供了 [agentskills.io](https://agentskills.io) 技能。
它教会 Agent 如何调用 `trace_processor`、编写 PerfettoSQL、
在 Android 上采集 trace，并按照指导工作流进行 Android 内存和
GPU 分析。每个安装包都捆绑了 `trace_processor` 包装器，
因此不需要单独的二进制文件。

其设计在
[RFC-0025](https://github.com/google/perfetto/discussions/5763) 和
[RFC-0026](https://github.com/google/perfetto/discussions/5892) 中有描述。

## 安装

| Agent | 安装命令 |
| ----- | ------- |
| Claude Code | `/plugin marketplace add google/perfetto@ai-agents` |
| Codex | `codex plugin marketplace add google/perfetto --ref ai-agents` |
| OpenCode | 在 `opencode.json` 中添加：`"skills": { "urls": ["https://raw.githubusercontent.com/google/perfetto/ai-agents/plugins/perfetto/skills"] }` |
| 其他（Antigravity、Cursor……） | 使用下面的后备安装器 |

对于任何其他 Agent，使用后备安装器（任何带有 Python 3 的平台）：

```bash
# macOS / Linux
curl -fsSL https://get.perfetto.dev/agents-install | python3 - --target <path>
```

```powershell
# Windows（使用 curl.exe，而非 PowerShell 的 curl 别名）
curl.exe -fsSL https://get.perfetto.dev/agents-install | python - --target <path>
```

传入 `--agent <claude|codex|opencode|antigravity|pi>` 而非 `--target`，
可安装到该 Agent 的默认目录中。

要在团队中共享此设置，将 `--target` 指向仓库中的按 Agent 目录
（例如 `.claude/skills/`），并将结果提交。

### 离线安装

无法在安装时访问 github.com 的机器，可以使用每个
[GitHub release](https://github.com/google/perfetto/releases) 附带的
`perfetto-ai-skill.zip` 资产：在有网络连接的地方下载它，拷贝过去，
然后解压到你的 Agent 技能目录（例如 `.claude/skills/`）。它包含一个
单独的 `perfetto/` 技能文件夹，其中有 `SKILL.md` —— 无需安装器。

捆绑的 `bin/trace_processor` 包装器会在首次使用时下载原生
`trace_processor` 二进制文件，并将其以
`trace_processor_shell-<其 sha256 的前 16 个十六进制字符>` 为名缓存到
`~/.local/share/perfetto/prebuilts/`。在完全离线的机器上，请自行填充
该缓存：从同一 release 页面下载你平台的预构建 zip（例如
`linux-amd64.zip`，其中包含 `trace_processor_shell`），然后运行：

```sh
mkdir -p ~/.local/share/perfetto/prebuilts
SHA=$(sha256sum trace_processor_shell | cut -c1-16)
cp trace_processor_shell ~/.local/share/perfetto/prebuilts/trace_processor_shell-$SHA
```

包装器信任任何已以该名称存在的文件，因此该二进制文件必须来自同一
release。在 Windows 上，缓存目录是
`%USERPROFILE%\.local\share\perfetto\prebuilts`，文件名是
`trace_processor_shell.exe-<sha256 前缀>`。

## 更新

更新使用与安装相同的机制：

| 安装方式 | 更新方式 |
| -------- | -------- |
| Claude Code marketplace | Claude Code 的常规插件更新流程（`/plugin` → manage/update，它会拉取最新的 `ai-agents` 分支）。 |
| Codex marketplace | Codex 的插件更新机制。 |
| OpenCode `skills.urls` | 无需操作 —— 该 URL 始终提供最新发布的技能。 |
| 后备安装器 | 重新运行相同的 `curl ... agents-install` 命令。它会检测到现有安装并在替换前询问（传入 `--yes` 可跳过提示）。 |

每个 Perfetto release 都会发布新的技能版本。后备安装器默认安装最新
release；传入 `--version vX.Y` 可固定到特定版本。

## 临时 trace 分析

提及一个 trace 文件并提出你的问题；Agent 会加载 trace、
探查 schema，并为你编写 PerfettoSQL。

```
> 加载 ~/traces/startup.pftrace，告诉我前两秒内哪些线程
  使用了最多的 CPU。

> 在 trace.pftrace 中找出 com.example.myapp 的不可中断
  睡眠的主要原因。
```

对于 Android 特定的工作流（内存泄漏调试、集群级 heap dump
聚类、trace 采集），参见
[在 Android 实战指南中使用 AI](android-trace-analysis.md#using-ai)。

## 调试 GPU 性能

引导式工作流，回答"这个工作负载是 GPU 瓶颈还是主机瓶颈？"，
然后深入分析问题所在的任一侧。目前最深入的 Counter 支持是
NVIDIA/CUDA。

```
> 这个工作负载是 GPU 瓶颈还是主机瓶颈？trace 文件位于
  ~/traces/game.pftrace。

> GPU 看起来很忙但工作负载很慢。在 gpu.pftrace 中，
  时钟是否被降频或加速缓慢？

> 哪些 kernel 主导了这个 CUDA trace，它们是计算瓶颈还是
  内存瓶颈？
```

Agent 会盘点 GPU、将时间线分为繁忙与空闲时间（将空闲间隙
归因于主机侧原因）、检查 DVFS 升频或热降频，对于计算工作负载
还会根据硬件的计算和内存上限对 kernel 进行分类。

## 贡献

要编写或修改技能，请参见
[`ai/skills/README.md`](https://github.com/google/perfetto/blob/main/ai/skills/README.md)。
