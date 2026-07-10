# 内核函数图追踪

Linux 内核的 `function_graph` tracer 会记录**每个内核函数的进入和退出**，
让你看到内核在 CPU 上执行的确切调用树，并包含每个函数的耗时。Perfetto
可以通过 `linux.ftrace` 数据源驱动此 tracer，并将产生的调用可视化为时间线
上的嵌套 slice，就像用户空间 slice 一样。

这是一种强大的方式，无需添加自己的插桩即可回答"内核在这里到底在做什么？"。
但这是一个高带宽特性：追踪太多函数会使 trace buffer 溢出，
因此它被设计为与 filter 配合使用。

如果你想要在内核中添加**自己的** tracepoint，请参见
[使用 ftrace 插桩内核](/docs/getting-started/ftrace.md)。

## 要求

- 内核编译时需启用 `CONFIG_FUNCTION_GRAPH_TRACER`。可通过以下命令确认支持：
  ```bash
  cat /sys/kernel/tracing/available_tracers
  ```
  输出必须包含 `function_graph`。
- ftrace 配置中需设置 `symbolize_ksyms: true`。否则每个函数都会显示为
  原始十六进制地址。关于为何内核符号必须在录制时解析而无法事后通过
  `traceconv bundle` 添加，参见
  [符号化：内核符号](/docs/learning-more/symbolization.md#ftrace)。
- 在 **Android** 上，函数图追踪仅在 `debuggable`（userdebug/eng）构建上
  可用，并在 Android U 中引入。
- `traced_probes` 必须以 root 身份运行（或降低 `kptr_restrict`），
  既能读取 `/proc/kallsyms`，也能控制内核 tracer。

## TraceConfig

相关选项位于 `FtraceConfig` 中：

- `enable_function_graph`：打开 `function_graph` tracer。
- `function_filters`：一组 glob 模式；仅匹配的函数被追踪。
- `function_graph_roots`：一组 glob 模式；匹配的函数**及其所有被调用者**
  都被追踪。
- `function_graph_max_depth`：限制从根函数往下追踪的调用层级数。
- `symbolize_ksyms`：必需，以获取函数名而非地址。

WARNING: 始终使用 `function_filters` 和/或 `function_graph_roots` 限制追踪
范围。追踪所有内核函数会产生巨大的事件流，会在毫秒内填满 buffer，且很少有用。

示例：追踪调度器函数及其调用的所有内容，持续 10 秒。

```protobuf
buffers {
  size_kb: 65536
  fill_policy: DISCARD
}

data_sources {
  config {
    name: "linux.ftrace"
    ftrace_config {
      symbolize_ksyms: true
      enable_function_graph: true
      # Trace these functions and all of their callees.
      function_graph_roots: "__schedule"
      # Optionally also keep a flat set of functions of interest.
      function_filters: "handle_mm_fault"
      function_graph_max_depth: 10
    }
  }
}

duration_ms: 10000
```

使用 `tracebox` 录制：

```bash
./tracebox -c funcgraph.cfg --txt -o funcgraph.pftrace
```

关于如何在 Linux 上设置 `tracebox` 和必要权限，参见
[系统追踪指南](/docs/getting-started/system-tracing.md)。

## UI

函数图调用以嵌套 slice 的形式显示。每个内核函数进入/退出对成为一个
slice，其持续时间为在该函数内部（包括被调用者）花费的时间，
因此调用树读起来完全就像用户空间的火焰图。

- 线程运行时发生的调用附加到该线程下的 **Funcgraph** track 上。
- 在空闲 CPU（`swapper` 空闲任务）上发生的调用被分组到
  每个 CPU 的 `swapper<N> -funcgraph` track 上。

你可以选择一个 slice 来查看函数名和持续时间，并使用火焰图/聚合功能，
就像任何其他 slice track 一样。

## SQL

函数图调用是普通的 slice，因此它们位于 `slice` 表中，可以像任何其他
slice 一样查询。例如，找出累计时间最多的内核函数：

```sql
SELECT name, COUNT(*) AS calls, SUM(dur) AS total_dur
FROM slice
JOIN track ON slice.track_id = track.id
WHERE track.name = 'Funcgraph'
GROUP BY name
ORDER BY total_dur DESC
LIMIT 20;
```

## 故障排除

- **函数显示为十六进制地址**（例如 `0xffffffff8108abcd`）：你没有设置
  `symbolize_ksyms: true`，或 `traced_probes` 无法读取
  `/proc/kallsyms`（非 root / `kptr_restrict` 太高）。这必须在录制时修复；
  参见[符号化：内核符号](/docs/learning-more/symbolization.md#ftrace)。
- **完全没有函数图数据**：确认 `function_graph` 在
  `available_tracers` 中，并且你的配置至少设置了
  `function_filters` / `function_graph_roots` 中的一个。
- **数据源被拒绝**：函数图无法与另一个使用不同内核 tracer 的并发
  `linux.ftrace` 数据源同时运行，因为内核 tracer 无法在 trace 中途切换。
