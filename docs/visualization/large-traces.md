# 可视化大型 trace

浏览器通常限制站点可以使用的内存量。这会在可视化大型 trace 时导致问题，包括[合并的多 trace session](/docs/visualization/merging-traces.md)，这些通常本身就很大。

## 使用 TraceProcessor 作为原生加速器

Perfetto UI 支持将 trace 的解析和处理卸载到在本地机器上以原生方式运行的"服务器" TraceProcessor 实例。此服务器进程可以充分利用你机器的 RAM，并以完整的原生（而不是 WebAssembly）性能运行，在现代 x86_64 机器上利用 SSE。

```bash
curl -LO https://get.perfetto.dev/trace_processor
chmod +x ./trace_processor
./trace_processor server http /path/to/trace.pftrace
```

然后像往常一样打开 https://ui.perfetto.dev。

Perfetto UI 将自动检测 `trace_processor server http` 的存在（通过探测 http://127.0.0.1:9001）。检测到后，它将提示一个对话框，询问你是否希望通过 WebSocket 使用外部加速器或在浏览器中运行的内置 WebAssembly 运行时。

NOTE: 经典的 `./trace_processor --httpd /path/to/trace.pftrace` 调用仍然受支持且行为相同。

## 复用已解析的 trace 而无需重新解析

解析是处理大型 trace 中开销最大的部分。如果同一个 trace 会被加载多次（或交给另一个实例使用），可以先导出一次解析结果，之后直接加载该归档文件：

```bash
./trace_processor export perfetto -o parsed.tar trace.pftrace
./trace_processor query parsed.tar "SELECT count(*) FROM slice"
```

`perfetto` 格式会直接从归档中恢复 trace processor 的静态表，跳过完整解析所需的 packet 摄入和排序过程。它与版本耦合：请使用生成它的同一版本的 trace processor 来加载（其他版本可能可以工作，但不作保证）。

如果是在同一台机器上反复使用，后台 [session](/docs/getting-started/command-line-analysis.md#iterate-without-re-parsing-sessions) 是更轻量的选择；而 `perfetto` 归档则是可移植的方案，例如在不同机器之间迁移已解析的 trace，或将其送入批处理任务。

## 并行使用多个实例

NOTE: 这是一个临时解决方案，直到实现 [b/317076350](http://b/317076350) (Googlers only) 中描述的更好的解决方案。

根据 [r.android.com/2940133](https://r.android.com/2940133)（2024 年 2 月），可以在不同端口上运行不同实例的 trace_processor，并将 UI 指向它们。

**先决条件：** 启用 [Relax CSP 标志](https://ui.perfetto.dev/#!/flags/cspAllowAnyWebsocketPort)。你只需要执行此操作一次。如果未显示该标志，则上面的 CL 尚未进入你使用的发布渠道（尝试 Canary 或 Autopush）

```bash
./trace_processor server http --port 9001 trace1.pftrace
./trace_processor server http --port 9002 trace2.pftrace
./trace_processor server http --port 9003 trace3.pftrace
```

然后在三个标签页中打开 UI，如下所示：
- https://ui.perfetto.dev/#!/?rpc_port=9001
- https://ui.perfetto.dev/#!/?rpc_port=9002
- https://ui.perfetto.dev/#!/?rpc_port=9003

## 多大算太大？

确切的内存限制因浏览器、架构和操作系统而异，但 2GB 是典型值。此限制针对的是运行时使用的总内存，而不是 trace 文件的二进制大小。`trace_processor`（以及 UI）在运行时对 trace 的表示通常大于该 trace 的二进制大小。这是因为该表示针对查询性能而非大小进行了优化。确切的膨胀系数取决于 trace 格式，但对于未压缩的 proto trace 可以达到 2-4 倍。
