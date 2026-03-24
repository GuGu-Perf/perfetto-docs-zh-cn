# 内核 track 事件：格式和约定

本文描述了一种以这种方式构建 Linux 内核 tracepoint 的约定，使 perfetto 能够自动在 UI 和 SQL 级别将它们呈现为 Slice/Counter Tracks，而无需更改或重建 perfetto 代码。

这是一个 perfetto 约定，不需要（也不需要）任何专用的上游内核代码。在本地内核上黑客攻击或编写不会被上游的自包含模块时，它最能使用。它也没有明确绑定到静态 tracepoint，创建具有相关字段的 `tracefs` 条目的动态 Probe（例如 kprobe）也将起作用。

本文档的结构作为参考，在["使用 ftrace 对 Linux 内核进行仪器化"][ftrace-intro-link]中有带有生成 UI 的**示例和截图**的介绍。

[ftrace-intro-link]: /docs/getting-started/ftrace#part-c-simple-slice-counter-visualisations-without-modifying-perfetto-code-kernel-track-events-

*此约定仍然可塑，如果你最终使用它和/或发现设计问题，请发送电子邮件到我们的邮件列表或提交 github 问题。*

## Slice 和瞬时事件

Perfetto 在事件的数据表示中查找具有特定类型和名称的字段。这在使用 `TRACE_EVENT()` 宏定义tracepoint时由 `TP_STRUCT__entry()` 定义。

对于表示 Slice（开始 + 结束）和瞬时事件（按 Track 分组），知名字段为：

| 必需？ | 类型 | 名称 |
| --- | --- | --- |
| 必需 | char | track\_event\_type |
| 必需 | \_\_string | slice\_name |
| 可选 | intX | scope\_{...} |
| 可选 | \_\_string | track\_name |

其中 `intX` 表示任何整数类型，而 `__string` 是内核类型，用于在 trace event 中存储动态大小的字符串。

在运行时，事件有效负载将解释如下：

- `track_event_type`:
  - `'B'` 打开命名 Slice。
  - `'E'` 结束 Track 中最后打开的 Slice。
  - `'I'` 设置命名瞬时（零持续时间）事件。

- `slice_name`：Slice 的名称（用于开始（'B'）和瞬时（'I'）事件），对于结束事件忽略。

- `track_name`：如果设置，覆盖 Track 的名称。默认值是 tracepoint 的名称。

- `scope_{...}`：如果设置，指定 Track 的作用域 id，它用作 Track 的分组键。字段名称可以具有对你的子系统有意义的任意后缀，但也有一些知名的名称，perfetto 可以在 UI 中呈现 Track 时将其用作提示。id 不必与操作系统级别的概念相关。
  - `scope_tgid`：用于进程范围的 Track，其中值必须是有效进程（尽管调用线程不必在该进程内）。
  - `scope_cpu`：用于 cpu 范围的 Track(发出代码不需要在该 cpu 上运行)。
  - `scope_your_feature_idx`：用于你自己的 Track id 分配。
  - *默认*：线程范围 Track（使用命中 tracepoint 的线程的线程 id，由 ftrace 系统本身记录）。

此外：

tracepoint 名称和子系统可以是任意的。你的头文件可以声明匹配这些模板的任意数量的 tracepoint。每个 tracepoint 将被独立处理。

对具有附加字段、字段顺序或 `TRACE_EVENT()` 声明的其他部分没有约束。请注意，这包括 printk 说明符，因此tracepoint的文本格式可以是任意的（你甚至不需要打印 perfetto 特定的字段）。

## 计数器

对于表示 Counter 值（按 Track 分组），知名字段为：

| 必需？ | 类型 | 名称 |
| --- | --- | --- |
| 必需 | intX | counter\_value |
| 可选 | intX | scope\_{...} |
| 可选 | \_\_string | track\_name |

## 作用域（分组）事件的详细信息

本节解释了记录的事件如何分组到 Track 中的规则，因为通常使用单个 tracepointtrace 记录可能导致 N 个单独的 Track。分组规则对于 Slice 和 Counter Track 是相同的。

**注意：** Slice Track 上的 Slice *必须*具有严格嵌套 - 所有 Slice 必须在它们的父项之前终止（有关更多详细信息，请参阅[异步 Slice][async-slice-link]的概念）。你需要使用 Track 命名或作用域来确保保持该不变量。

如果只指定必填字段，默认行为是线程范围的。事件按命中 tracepoint 的线程的线程 id 分组。每个线程将有一个带有事件的 Track。结束（'E'）事件将终止该线程上最后打开的 Slice。

如果事件具有以 `scope_` 为前缀的字段，则事件将按该字段的值分组，其中一些预定义名称具有特殊含义（见上文）。例如，如果指定 `scope_tgid`，那将 Track 变为进程范围 - 所有共享相同 `scope_tgid` 值的事件将被放在同一个 Track 上。此外，UI 将在进程组中呈现该 Track。

如果你的事件包括 `track_name` 字段，则事件将按该名称作为上述的额外维度进行分组。也就是说，结束（'E'）事件将终止具有该确切 Track 名称的最后打开的 Slice，即使在同一线程/进程/cpu 等作用域中有多个命名 Track。

最终效果是记录的事件按以下唯一组合分组： `{tracepoint} x {track name} x {scope id}`。最后两个分别默认为 tracepoint名称和线程 id。