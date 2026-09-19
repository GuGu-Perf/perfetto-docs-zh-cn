# Trace Processor (C++)

Trace Processor 是一个 C++ 库（[src/trace_processor](/src/trace_processor)），它摄取多种格式的 trace，并公开一个 SQL 接口，通过一组一致的表来查询这些 trace。它还会计算 trace 汇总、以人类可读的描述为 trace 添加注释，并从 trace 的内容派生新事件。

![Trace processor 框图](/docs/images/trace-processor.png)

大多数用户通过 [`trace_processor` shell](#shell) 与 Trace Processor 交互，这是一个围绕该库的命令行包装器，可打开交互式 PerfettoSQL 提示符。要将 Trace Processor 嵌入其他 C++ 应用程序，请参阅[嵌入 C++ 库](#embedding)。Python 用户应改用 [Python API](trace-processor-python.md)。

## {#shell} trace_processor shell

`trace_processor` shell 是一个命令行二进制文件，它加载 trace 并在其上打开交互式 SQL 提示符。

### 下载 shell

shell 是一个从 Perfetto 网站下载的轻量级 Python 包装器。首次使用时，它会在 `~/.local/share/perfetto/prebuilts` 下获取并缓存适合你平台的原生二进制文件（包括 Windows 上的 `trace_processor_shell.exe`）。

<?tabs>

TAB: Linux / macOS

```bash
curl -LO https://get.perfetto.dev/trace_processor
chmod +x ./trace_processor
```

TAB: Windows

```powershell
curl.exe -LO https://get.perfetto.dev/trace_processor
```

运行包装脚本需要 Python 3。`curl` 随 Windows 10 及更高版本附带。

</tabs?>

### 运行 shell

下载后，即可对 trace 文件运行它：

<?tabs>

TAB: Linux / macOS

```bash
./trace_processor trace.perfetto-trace
```

TAB: Windows

```powershell
python trace_processor trace.perfetto-trace
```

</tabs?>

这会打开一个交互式 SQL shell，你可以在其中查询 trace。有关如何编写查询，请参阅 [PerfettoSQL 入门指南](perfetto-sql-getting-started.md)。

TIP: trace 文件也可以是包含多个 trace 的 ZIP 或 TAR 归档文件：它们会被合并到单一时间线上。参见[从命令行合并 trace](/docs/analysis/merging-traces.md)。

例如，要查看 trace 中的所有 Slice：

```sql
> SELECT ts, dur, name FROM slice LIMIT 10;
ts                   dur                  name
-------------------- -------------------- ---------------------------
     261187017446933               358594 eglSwapBuffersWithDamageKHR
     261187017518340                  357 onMessageReceived
     261187020825163                 9948 queueBuffer
     261187021345235                  642 bufferLoad
     261187121345235                  153 query
...
```

或者，要查看所有 Counter 的值：

```sql
> SELECT ts, value FROM counter LIMIT 10;
ts                   value
-------------------- --------------------
     261187012149954          1454.000000
     261187012399172          4232.000000
     261187012447402         14304.000000
     261187012535839         15490.000000
     261187012590890         17490.000000
     261187012590890         16590.000000
...
```

### {#sessions} 让 trace 保持热身状态：session

解析大型 trace 需要时间。如果你打算对同一个 trace 运行多个查询，可以将其一次性加载到一个命名的后台 session 中，然后让每次调用都指向该 session：

```bash
# 将 trace 一次性加载到后台 session 中。
trace_processor server unix --name mysession --daemonize trace.pftrace

# 对热身好的 session 运行查询，而不是重新加载 trace。
trace_processor query --remote mysession "SELECT count(*) FROM slice"
```

`query`、`interactive`、`metrics` 和 `summarize` 子命令都接受 `--remote`，它通过 Perfetto UI 所用的同一 TraceProcessor RPC 接口与一个 session 通信。参见[从命令行分析 trace](/docs/getting-started/command-line-analysis.md) 了解完整 walkthrough，以及 [`server` 参考](/docs/reference/trace-processor-cli.md#subcommand-server)了解模式和标志细节。

### {#subcommands} 命令行参考

有关命令、选项、环境变量和输出行为，请参阅 [trace_processor CLI 参考](/docs/reference/trace-processor-cli.md)。

#### {#subcommand-query} query

请参阅 CLI 参考中的 [query](/docs/reference/trace-processor-cli.md#subcommand-query)。

#### {#subcommand-interactive} interactive

请参阅 CLI 参考中的 [interactive](/docs/reference/trace-processor-cli.md#subcommand-interactive)。

#### {#subcommand-server} server

请参阅 CLI 参考中的 [server](/docs/reference/trace-processor-cli.md#subcommand-server)。

#### {#subcommand-summarize} summarize

请参阅 CLI 参考中的 [summarize](/docs/reference/trace-processor-cli.md#subcommand-summarize)。

#### {#subcommand-export} export

请参阅 CLI 参考中的 [export](/docs/reference/trace-processor-cli.md#subcommand-export)。

#### {#global-flags} 全局标志

请参阅 CLI 参考中的[全局标志](/docs/reference/trace-processor-cli.md#global-flags)。

## {#embedding} 嵌入 C++ 库

公共 API 以 `TraceProcessor` 类为中心，该类位于 [`trace_processor.h`](/include/perfetto/trace_processor/trace_processor.h) 中。所有高级操作（解析 trace 字节、执行 SQL 查询、计算汇总）都是此类的成员函数。

使用 `CreateInstance` 创建实例：

```cpp
#include "perfetto/trace_processor/trace_processor.h"

using namespace perfetto::trace_processor;

Config config;
std::unique_ptr<TraceProcessor> tp = TraceProcessor::CreateInstance(config);
```

### 加载 trace

要摄取 trace，请使用 trace 字节块重复调用 `Parse`，然后在推送完整 trace 后调用 `NotifyEndOfFile`：

```cpp
while (/* more data available */) {
  TraceBlobView blob = /* ... */;
  base::Status status = tp->Parse(std::move(blob));
  if (!status.ok()) { /* handle error */ }
}
base::Status status = tp->NotifyEndOfFile();
```

由于从文件系统读取 trace 是一个常见场景，因此提供了辅助函数 `ReadTrace`（位于 [`read_trace.h`](/include/perfetto/trace_processor/read_trace.h) 中）：

```cpp
#include "perfetto/trace_processor/read_trace.h"

base::Status status = ReadTrace(tp.get(), "/path/to/trace.pftrace");
```

`ReadTrace` 从磁盘读取文件，使用内容调用 `Parse`，并为你调用 `NotifyEndOfFile`。

### 执行查询

使用 `ExecuteQuery` 运行查询，它返回一个 `Iterator`，以流式方式将行返回给调用者：

```cpp
auto it = tp->ExecuteQuery("SELECT ts, name FROM slice LIMIT 10");
while (it.Next()) {
  int64_t ts = it.Get(0).AsLong();
  std::string name = it.Get(1).AsString();
  // ...
}
if (!it.Status().ok()) {
  // Query produced an error.
}
```

使用迭代器时的两条重要规则：

- **始终在访问值之前调用 `Next`。**迭代器在返回时定位在第一行之前，因此在 `Next` 返回 `true` 之前不能调用 `Get`。
- **始终在迭代结束后检查 `Status`。**查询可能在执行过程中失败；`Next` 返回 `false` 仅意味着迭代停止，并不意味着成功。检查 `Status()` 以区分 EOF 和错误。

有关完整的迭代器 API，请参阅 [`iterator.h`](/include/perfetto/trace_processor/iterator.h) 中的注释。

### 其他功能

`TraceProcessor` 类还提供：

- **Trace 汇总**（`Summarize`）：计算 trace 的结构化汇总。面向用户的描述请参阅 [Trace 汇总](trace-summary.md)。
- **自定义 SQL 包**（`RegisterSqlPackage`）：在包名下注册 PerfettoSQL 文件，以便查询可以 `INCLUDE` 它们。
- **带外文件内容**（`RegisterFileContent`）：将辅助数据传递给导入器，例如用于解码 ETM trace 的二进制文件。
- **元追踪**（`EnableMetatrace` / `DisableAndReadMetatrace`）：对 Trace Processor 本身进行追踪以进行性能调试。

有关完整的 API 接口，请参阅 [`trace_processor.h`](/include/perfetto/trace_processor/trace_processor.h) 中的注释。
