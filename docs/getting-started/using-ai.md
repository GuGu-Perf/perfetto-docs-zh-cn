# 实战指南：在 Perfetto 中使用 AI

NOTE: **Googlers**：请使用 [go/perfetto-ai-skills](http://go/perfetto-ai-skills)
和
[go/perfetto-ai-skills-android-memory](http://go/perfetto-ai-skills-android-memory)，
而非此页面。

Perfetto AI 技能是面向 Claude Code、Codex、OpenCode、Antigravity 和 Cursor 等编程 Agent 的 [技能](https://agentskills.io)。将你的 Agent 指向一个 trace 并用自然语言提问：它会将 trace 加载到 `trace_processor`，编写 PerfettoSQL 并报告其发现。它还可以采集 trace，并按照指导工作流进行 Android 内存和 GPU 分析。该技能捆绑了 `trace_processor`，因此无需再安装其他任何东西。

## 快速开始

### 1. 安装技能

| Agent | 安装 |
| ----- | ------- |
| Claude Code | `/plugin marketplace add google/perfetto@ai-agents`，然后 `/plugin install perfetto@perfetto` |
| Codex | `codex plugin marketplace add google/perfetto --ref ai-agents`，然后从插件列表安装 `perfetto` |
| OpenCode | 在 `opencode.json` 中添加：`"skills": { "urls": ["https://raw.githubusercontent.com/google/perfetto/ai-agents/plugins/perfetto/skills"] }` |
| 其他（Antigravity、Cursor……） | 使用下面的后备安装器 |

对于任何其他 Agent，使用后备安装器（需要 Python 3）：

```bash
# macOS / Linux：安装到某个 Agent 的默认目录
curl -fsSL https://get.perfetto.dev/agents-install | python3 - --agent <claude|codex|opencode|antigravity|pi>

# macOS / Linux：安装到任意技能目录，例如提交到仓库中的目录
curl -fsSL https://get.perfetto.dev/agents-install | python3 - --target <path>
```

```powershell
# Windows（使用 curl.exe，而非 PowerShell 的 curl 别名）
curl.exe -fsSL https://get.perfetto.dev/agents-install | python - --target <path>
```

要在团队中共享此设置，将 `--target` 指向仓库中的按 Agent 目录（例如 `.claude/`），并将结果提交。

### 2. 询问 trace

提及一个 trace 文件并提出你的问题：

```
> Investigate object retention and potential leaks in heap_dump.pftrace.
```

还没有 trace？让 Agent 录制一个：

```
> Record a Java heap dump of com.example.app from my connected device and
  find what is keeping memory alive.
```

你无需提及该技能：只要对话涉及 trace 或性能问题，Agent 就会自动调用它。在 Claude Code 中，你还可以通过 `/perfetto:perfetto` 显式调用。

## 示例提示词

### 内存泄漏与 heap dump

针对泄漏、OOM、churn 和分配热路径的指导工作流。

```
> Investigate object retention and potential leaks in heap_dump.pftrace.

> Why does com.example.app's Java heap keep growing? Compare before.pftrace
  and after.pftrace.

> Analyze native heap allocations and find memory growth hot paths in
  native_heap.pftrace.

> Which code paths allocate the most short-lived objects in
  java_alloc.pftrace?

> Here are 40 heap dumps of com.example.app in ~/dumps/. Cluster them and
  find the common root causes.
```

Agent 会运行经过测试的 SQL 来提取 dominator 路径、原生调用栈或分配摘要，然后在你的工作区中搜索可疑类，并指出需要修复的文件。更多信息参见[在 Android 实战指南中使用 AI](android-trace-analysis.md#using-ai)。

### 临时 trace 分析

任何可以用 PerfettoSQL 回答的问题。

```
> Load ~/traces/startup.pftrace and tell me which threads used the most CPU
  in the first two seconds.

> Why is app startup slow in startup.pftrace? Break down the main thread.

> Find the top causes of uninterruptible sleep for com.example.myapp in
  trace.pftrace.

> Which frames were janky in jank.pftrace and what was the UI thread doing?
```

Agent 会探查自己所需的表和标准库模块而非凭空猜测，并在多次查询之间保持 trace 处于加载状态。

### 录制

来自连接的 Android 设备或本地 Linux 机器的 trace。

```
> Record a 10 second trace of com.example.app starting up on my connected
  device, then tell me what took the longest.
```

Agent 会从捆绑的示例中挑选配置，采集 trace 然后对其进行分析。

### GPU 性能

工作负载是 GPU 瓶颈还是主机瓶颈，以及原因。目前对 NVIDIA/CUDA 的 Counter 支持最深入。

```
> Is this workload GPU-bound or host-bound? The trace is at game.pftrace.

> The GPU looks busy but the workload is slow. Was the clock throttled or
  slow to ramp in gpu.pftrace?

> Which kernels dominate this CUDA trace, and are they compute-bound or
  memory-bound?
```

Agent 会将时间线分为繁忙与空闲时间，将空闲间隙归因于主机侧原因，检查 DVFS 升频或热降频，对于计算工作负载还会根据硬件的计算和内存上限对 kernel 进行分类。

## 离线安装 {#offline-install}

无法在安装时访问 github.com 的机器，可以使用 `perfetto-ai-skill.zip` 资产（附属于每个 [GitHub release](https://github.com/google/perfetto/releases)）：在有网络连接的地方下载它，拷贝过去，然后解压到你的 Agent 技能目录（例如 `.claude/skills/`）。它包含一个单独的 `perfetto/` 技能文件夹，其中有 `SKILL.md` —— 无需安装器。

捆绑的 `bin/trace_processor` 包装器会在首次使用时下载原生 `trace_processor` 二进制文件，并将其以
`trace_processor_shell-<其 sha256 的前 16 个十六进制字符>` 为名缓存到
`~/.local/share/perfetto/prebuilts/`。在完全离线的机器上，请自行填充该缓存：从同一 release 页面下载你平台的预构建 zip（例如 `linux-amd64.zip`，其中包含 `trace_processor_shell`），然后运行：

```sh
mkdir -p ~/.local/share/perfetto/prebuilts
SHA=$(sha256sum trace_processor_shell | cut -c1-16)
cp trace_processor_shell ~/.local/share/perfetto/prebuilts/trace_processor_shell-$SHA
```

包装器信任任何已以该名称存在的文件，因此该二进制文件必须来自同一 release。在 Windows 上，缓存目录是
`%USERPROFILE%\.local\share\perfetto\prebuilts`，文件名是
`trace_processor_shell-<sha256 前缀>.exe`。

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

## 设计

其设计在 [RFC-0025](https://github.com/google/perfetto/discussions/5763) 和 [RFC-0026](https://github.com/google/perfetto/discussions/5892) 中有描述。

## 贡献

要编写或修改技能，请参见 [`ai/skills/CONTRIBUTING.md`](https://github.com/google/perfetto/blob/main/ai/skills/CONTRIBUTING.md)。
