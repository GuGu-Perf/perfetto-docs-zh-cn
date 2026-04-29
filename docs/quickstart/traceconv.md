# 从 Perfetto 转换为其他 trace 格式

Perfetto 的原生 protobuf trace 格式可以使用 `traceconv` 工具转换为其他格式。`traceconv` 同时也是一个用于 trace 符号化/反混淆以及一些小型 trace 编辑工具的工具包。

![](/docs/images/traceconv-summary.png)

## 前提条件

- 运行 Linux、macOS 或 Windows 的主机
- Python 3（仅在使用下面的 `traceconv` 包装脚本时需要；在 Windows 上还需要 `curl`，Windows 10 及更高版本自带）
- Perfetto protobuf trace 文件

`traceconv` 有三组模式：

- **格式转换** — 将 Perfetto protobuf trace 转换为其他 trace 格式（Chrome JSON、systrace、pprof、Firefox profiler 等）。
- **符号化和反混淆** — 将原生符号和 ProGuard/R8 映射附加到 trace。**在大多数情况下，你应该使用 `bundle`**（见下文），它将 trace 及其所有调试产物打包成一个独立的 TAR — 这是分享或归档 trace 的推荐方式。
- **实用工具** — 较小的辅助工具（protobuf 文本 ↔ 二进制转换、Packet 解压缩）。

## 使用方法

使用最新的二进制文件：

<?tabs>

TAB: Linux / macOS

```bash
curl -LO https://get.perfetto.dev/traceconv
chmod +x traceconv
./traceconv MODE [OPTIONS] [input_file] [output_file]
```

TAB: Windows

```powershell
curl.exe -LO https://get.perfetto.dev/traceconv
python traceconv MODE [OPTIONS] [input_file] [output_file]
```

</tabs?>

`traceconv` 脚本是一个轻量级 Python 包装器，首次使用时会在 `~/.local/share/perfetto/prebuilts` 下下载并缓存适合你平台的原生二进制文件（包括 Windows 上的 `traceconv.exe`）。

当省略输入或输出路径（或传递 `-`）时，`traceconv` 从 stdin 读取并写入 stdout。运行 `./traceconv` 不带参数可打印你的版本支持的所有模式和选项的完整列表。

## 格式转换

| 模式       | 输出                                                       |
| ---------- | ------------------------------------------------------------ |
| `text`     | protobuf 文本格式 — proto 的文本表示   |
| `json`     | Chrome JSON 格式，可在 `chrome://tracing` 中查看           |
| `systrace` | Android systrace 使用的 ftrace 文本/HTML 格式             |
| `ctrace`   | 压缩的 systrace 格式                                   |
| `profile`  | 聚合的 pprof profile（heapprofd、perf、Java heap 图） |
| `firefox`  | Firefox profiler 格式                                      |

示例：

```bash
./traceconv json     trace.perfetto-trace trace.json
./traceconv systrace trace.perfetto-trace trace.html
./traceconv text     trace.perfetto-trace trace.textproto
```

`profile` 将一个或多个 `.pb` 文件写入目录（默认为随机临时目录）而不是单个输出文件，因此请使用 `--output-dir` 而不是位置输出路径：

```bash
./traceconv profile --output-dir ./profiles trace.perfetto-trace
./traceconv profile --java-heap --pid 1234 --output-dir ./profiles trace.perfetto-trace
./traceconv profile --perf --timestamps 1000000,2000000 --output-dir ./profiles trace.perfetto-trace
```

常用选项：

- `--truncate start|end`（用于 `systrace`、`json`、`ctrace`）：仅保留 trace 的开头或结尾。
- `--full-sort`（用于 `systrace`、`json`、`ctrace`）：强制对 trace 进行完整排序。
- `--skip-unknown`（用于 `text`）：跳过未知的 proto 字段。
- `--alloc | --perf | --java-heap`（用于 `profile`）：限制为单个 profile 类型（默认：自动检测）。
- `--no-annotations`（用于 `profile`）：不向 Frame 添加派生注释。
- `--pid` / `--timestamps`（用于 `profile`）：按进程或特定样本时间戳过滤。
- `--output-dir DIR`（用于 `profile`）：生成的 pprof 文件的输出目录。

## 符号化和反混淆

这些模式使用原生符号和/或 ProGuard/R8 反混淆映射来丰富 trace。有关 Perfetto 如何发现符号文件和映射文件的背景信息，请参阅[符号化](https://perfetto.dev/docs/learning-more/symbolization)参考。

### `bundle`（推荐）

**`bundle` 是符号化和反混淆的推荐入口点。**它将 trace 及其原生符号和 ProGuard/R8 映射打包成一个独立的 TAR，这是与队友分享、附加到 bug 或归档以供后续分析的正确产物。除非有特定原因，否则请优先使用 `bundle` 而不是 `symbolize`/`deobfuscate`。

```bash
./traceconv bundle trace.perfetto-trace trace.bundle.tar

# 提供额外的符号搜索路径或显式的 ProGuard 映射：
./traceconv bundle \
  --symbol-paths /path/to/symbols1,/path/to/symbols2 \
  --proguard-map com.example.app=/path/to/mapping.txt \
  trace.perfetto-trace trace.bundle.tar
```

`bundle` 专用选项：

- `--symbol-paths PATH1,PATH2,...` — 搜索符号的附加路径（在自动发现之上）。
- `--no-auto-symbol-paths` — 禁用自动符号路径发现。
- `--proguard-map [pkg=]PATH` — 用于 Java/Kotlin 反混淆的 ProGuard/R8 `mapping.txt`。可重复使用；`pkg=` 前缀将映射限定到特定包。
- `--no-auto-proguard-maps` — 禁用自动 ProGuard/R8 映射发现（例如 Gradle 项目布局）。
- `--verbose` — 打印更详细的输出。

NOTE: `bundle` 需要输入和输出的真实文件路径 — 它不接受 stdin/stdout。

### `symbolize` / `deobfuscate`（高级）

用于无法使用 `bundle` 的流水线的底层构建块。每个都将 Packet 流（符号或反混淆映射）发送到单独的输出文件：

```bash
./traceconv symbolize   trace.perfetto-trace symbols.pb
./traceconv deobfuscate trace.perfetto-trace mappings.pb
```

请优先使用 `bundle` — 它生成一个独立的 TAR，而不是留下松散的附属文件需要管理。

## 实用工具

| 模式                 | 功能                                                |
| -------------------- | ----------------------------------------------------------- |
| `binary`             | 将 protobuf 文本格式的 trace 转换回二进制形式。 |
| `decompress_packets` | 解压缩 trace 中压缩的 `TracePacket`。        |

```bash
./traceconv binary             trace.textproto      trace.perfetto-trace
./traceconv decompress_packets trace.perfetto-trace trace.decompressed
```

## 在旧版 systrace UI 中打开

如果你只想使用旧版（Catapult）trace 查看器打开 Perfetto trace，可以直接导航到 [ui.perfetto.dev](https://ui.perfetto.dev)，并使用 _"Open with legacy UI"_ 链接。这会在浏览器中使用 WebAssembly 运行 `traceconv`，并将转换后的 trace 无缝传递给 chrome://tracing。
