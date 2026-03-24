# 从 Perfetto 转换为其他 trace 格式

Perfetto 的原生 protobuf trace 格式可以使用 `traceconv` 工具转换为其他格式。

![](/docs/images/traceconv-summary.png)

## 前提条件

- 运行 Linux 或 MacOS 的主机
- Perfetto protobuf trace 文件

支持的输出格式有：

- `text` - protobuf 文本格式：基于文本的 proto 表示
- `json` - Chrome JSON 格式：chrome://tracing 使用的格式
- `systrace`：Android systrace 使用的 ftrace 文本格式
- `profile`：[pprof](https://github.com/google/pprof) 格式的聚合配置文件。支持分配器配置文件（heapprofd）、perf 配置文件和 Android Java 堆图。

## 使用方法

使用最新的二进制文件：

```bash
curl -LO https://get.perfetto.dev/traceconv
chmod +x traceconv
./traceconv [text|json|systrace|profile] [input proto file] [output file]
```

对于版本化下载，将 `<tag>` 替换为所需的 git tag：

```bash
curl -LO https://raw.githubusercontent.com/google/perfetto/<tag>/tools/traceconv
chmod +x traceconv
./traceconv [text|json|systrace|profile] [input proto file] [output file]
```

## 在旧版 systrace UI 中打开

如果你只想使用旧版（Catapult）trace 查看器打开 Perfetto trace，可以直接导航到 [ui.perfetto.dev](https://ui.perfetto.dev)，并使用 _"Open with legacy UI"_ 链接。这会在浏览器中使用 WebAssembly 运行 `traceconv`，并将转换后的 trace 无缝传递给 chrome://tracing。
