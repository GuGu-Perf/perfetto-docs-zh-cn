# 可视化大型 trace

浏览器通常限制站点可以使用的内存量。这会在可视化大型 trace 时导致问题。

## 使用 TraceProcessor 作为原生加速器

Perfetto UI 支持将 trace 的解析和处理卸载到在本地机器上以原生方式运行的"服务器" TraceProcessor 实例。此服务器进程可以充分利用你机器的 RAM，并以完整的原生（而不是 WebAssembly）性能运行，在现代 x86_64 机器上利用 SSE。

```bash
curl -LO https://get.perfetto.dev/trace_processor
chmod +x ./trace_processor
./trace_processor --httpd /path/to/trace.pftrace
```

然后像往常一样打开 https://ui.perfetto.dev。

Perfetto UI 将通过探测 http://127.0.0.1:9001 自动检测 `trace_processor --httpd` 的存在。检测到后，它将提示一个对话框，询问你是否希望通过 WebSocket 使用外部加速器或在浏览器中运行的内置 WebAssembly 运行时。

## 并行使用多个实例

NOTE: 这是一个临时解决方案，直到实现 [b/317076350](http://b/317076350) (Googlers only) 中描述的更好的解决方案。

根据 [r.android.com/2940133](https://r.android.com/2940133)（2024 年 2 月），可以在不同端口上运行不同实例的 trace_processor，并将 UI 指向它们。

**先决条件：** 启用 [Relax CSP 标志](https://ui.perfetto.dev/#!/flags/cspAllowAnyWebsocketPort)。你只需要执行此操作一次。如果未显示该标志，则上面的 CL 尚未进入你使用的发布渠道（尝试 Canary 或 Autopush）

```bash
./trace_processor --httpd --http-port 9001 trace1.pftrace
./trace_processor --httpd --http-port 9002 trace2.pftrace
./trace_processor --httpd --http-port 9003 trace3.pftrace
```

然后在三个标签页中打开 UI，如下所示：
- https://ui.perfetto.dev/#!/?rpc_port=9001
- https://ui.perfetto.dev/#!/?rpc_port=9002
- https://ui.perfetto.dev/#!/?rpc_port=9003
