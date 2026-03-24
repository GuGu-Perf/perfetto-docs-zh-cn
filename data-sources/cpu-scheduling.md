# CPU 调度事件

在 Android 和 Linux 上，Perfetto 可以通过 Linux 内核 [ftrace](https://www.kernel.org/doc/Documentation/trace/ftrace.txt) 基础架构收集调度器 trace。

这允许获取细粒度的调度事件，例如：

- 哪些线程在任何时间点调度到哪个 CPU 核心上，具有纳秒级精度。
- 运行线程被取消调度的原因（例如，抢占、在互斥锁上阻塞、阻塞系统调用或任何其他等待队列）。
- 线程有资格执行的时间点，即使它没有立即放在任何 CPU 运行队列上，以及使其可执行的源线程。

## UI

UI 将各个调度事件表示为 Slice：

![](/docs/images/cpu-zoomed.png "CPU 运行队列的详细视图")

单击 CPU Slice 会在详细信息面板中显示相关信息：

![](/docs/images/cpu-sched-details.png "CPU 调度详细信息")

向下滚动时，展开各个进程时，调度事件还为每个线程创建一个 track，允许跟踪单个线程状态的演变：

![](/docs/images/thread-states.png "单个线程的状态")

## SQL

在 SQL 级别，调度数据在 [`sched_slice`](/docs/analysis/sql-tables.autogen#sched_slice) 表中公开。

```sql
select ts, dur, cpu, end_state, priority, process.name, thread.name
from sched_slice left join thread using(utid) left join process using(upid)
```

ts | dur | cpu | end_state | priority | process.name, | thread.name
---|-----|-----|-----------|----------|---------------|------------
261187012170995 | 247188 | 2 | S | 130 | /system/bin/logd | logd.klogd
261187012418183 | 12812 | 2 | D | 120 | /system/bin/traced_probes | traced_probes0
261187012421099 | 220000 | 4 | D | 120 | kthreadd | kworker/u16:2
261187012430995 | 72396 | 2 | D | 120 | /system/bin/traced_probes | traced_probes1
261187012454537 | 13958 | 0 | D | 120 | /system/bin/traced_probes | traced_probes0
261187012460318 | 46354 | 3 | S | 120 | /system/bin/traced_probes | traced_probes2
261187012468495 | 10625 | 0 | R | 120 | [NULL] | swapper/0
261187012479120 | 6459 | 0 | D | 120 | /system/bin/traced_probes | traced_probes0
261187012485579 | 7760 | 0 | R | 120 | [NULL] | swapper/0
261187012493339 | 34896 | 0 | D | 120 | /system/bin/traced_probes | traced_probes0

## TraceConfig

要收集此数据，请包括以下数据源：

```protobuf
# 来自内核的调度数据。
data_sources: {
 config {
 name: "linux.ftrace"
 ftrace_config {
 compact_sched: {
 enabled: true
 }
 ftrace_events: "sched/sched_switch"
 # 可选:精确的线程生命周期跟踪:
 ftrace_events: "sched/sched_process_exit"
 ftrace_events: "sched/sched_process_free"
 ftrace_events: "task/task_newtask"
 ftrace_events: "task/task_rename"
 }
 }
}

# 添加完整的进程名称和线程<>进程关系:
data_sources: {
 config {
 name: "linux.process_stats"
 }
}
```

## 调度唤醒和延迟分析

通过在 TraceConfig 中进一步启用以下内容，ftrace 数据源还将记录调度唤醒事件：

```protobuf
 ftrace_events: "sched/sched_wakeup_new"
 ftrace_events: "sched/sched_waking"
```

虽然 `sched_switch` 事件仅在线程处于 `R(unnable)` 状态并且在 CPU 运行队列上运行时发出，但在任何事件导致线程状态更改时都会发出 `sched_waking` 事件。

考虑以下示例：

```
线程 A
condition_variable.wait()
 线程 B
 condition_variable.notify()
```

当线程 A 在 wait() 上挂起时，它将进入状态 `S(sleeping)` 并从 CPU 运行队列中移除。当线程 B 通知变量时，内核将线程 A 转换为 `R(unnable)` 状态。此时线程 A 有资格放回运行队列。但是，这可能不会立即发生，因为，例如：

- 所有 CPU 可能正忙于运行其他线程，线程 A 需要等待分配运行队列槽位（或者其他线程具有更高的优先级）。
- 有其他 CPU 而不是当前的 CPU，但调度器负载均衡器可能需要一些时间将线程移动到另一个 CPU 上。

除非使用实时线程优先级，否则大多数 Linux 内核调度器配置都不是严格的工作守恒的。例如，调度器可能更喜欢等待一段时间，希望当前 CPU 上运行的线程进入空闲，避免跨 CPU 迁移，这在开销和功耗方面可能更昂贵。

NOTE: `sched_waking` 和 `sched_wakeup` 提供几乎相同的信息。区别在于跨 CPU 的唤醒事件，这涉及处理器间中断。前者始终在源(唤醒)CPU 上发出，后者可能在源或目标(被唤醒)CPU 上执行，具体取决于几个因素。`sched_waking` 通常足以进行延迟分析，除非你正在细分由于调度器唤醒路径导致的延迟，例如处理器间信令。

当启用 `sched_waking` 事件时，在选择 CPU Slice 时，UI 中将显示以下内容：

![](/docs/images/latency.png "UI 中的调度唤醒事件")

### 解码 `end_state`

[sched_slice](/docs/analysis/sql-tables.autogen#sched_slice) 表包含有关系统调度活动的信息：

```
> select * from sched_slice limit 1
id type ts dur cpu utid end_state priority
0 sched_slice 70730062200 125364 0 1 S 130 
```

表的每一行显示给定线程（`utid`）何时开始运行（`ts`）、在哪个核心上运行（`cpu`）、运行了多长时间（`dur`）以及它为什么停止运行：`end_state`。

`end_state` 编码为一个或多个 ASCII 字符。UI 使用以下转换将 `end_state` 转换为人类可读的文本：

| end_state | Translation |
|------------|------------------------|
| R | Runnable |
| R+ | Runnable (Preempted) |
| S | Sleeping |
| D | Uninterruptible Sleep |
| T | Stopped |
| t | Traced |
| X | Exit (Dead) |
| Z | Exit (Zombie) |
| x | Task Dead |
| I | Idle |
| K | Wake Kill |
| W | Waking |
| P | Parked |
| N | No Load |

并非所有字符组合都是有意义的。

如果我们不知道调度何时结束（例如，因为在线程仍在运行时 trace 结束）,`end_state` 将为 `NULL`，并且 `dur` 将为 -1。
