# 在 Perfetto 中使用 AI

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
