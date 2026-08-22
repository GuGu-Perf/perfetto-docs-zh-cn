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

提示：trace 文件也可以是一个包含多个 trace 的 ZIP 或 TAR 归档文件：它们会被合并到一条时间线上。参见[从命令行合并 trace](/docs/analysis/merging-traces.md)。

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

`query`、`interactive`、`metrics` 和 `summarize` 子命令都接受 `--remote`，它通过 Perfetto UI 所用的同一 TraceProcessor RPC 接口与一个 session 通信。参见[从命令行分析 trace](/docs/getting-started/command-line-analysis.md) 了解完整 walkthrough，以及下文的 [`server` 子命令](#subcommand-server)了解模式和标志细节。

### {#subcommands} 子命令接口

除了交互式 REPL，`trace_processor` 还接受一个子命令作为第一个参数，用于非交互式工作流：

```text
trace_processor <command> [flags] [positional args]
```

`trace_processor --help` 会打印下面的顶级摘要。要查看某个子命令的标志，请运行 `trace_processor <command> --help`（等价于 `trace_processor help <command>`）：

```text
Perfetto Trace Processor.
Usage: trace_processor [command] [flags] [trace_file]

If no command is given, opens an interactive SQL shell on the trace file.

Commands:
  query         Load a trace and run a SQL query.
  interactive   Interactive SQL shell (default if no command is given).
  server        Start an RPC server.
  summarize     Compute a trace summary from specs and/or built-in metrics.
  export        Export trace data (sqlite, arrow_tar, perfetto).
  metrics       Run v1 metrics (deprecated; use 'summarize --metrics-v2').
  convert       Convert trace format.

Common flags (apply to all commands):
  -h, --help                  Show help (per-command if after a command).
  -v, --version               Print version.
      --full-sort             Force full sort ignoring windowing.
      --no-ftrace-raw         Prevent ingestion of typed ftrace into raw table.
      --add-sql-package PATH  Register SQL files from a directory as a package.
  -m, --metatrace FILE        Enable metatracing, write to FILE.
```

> **向后兼容。** 经典的扁平标志接口（`-q`、`-Q`、`--httpd`、`--summary`、`--run-metrics`、`-e`、`--stdiod`）仍通过内部转换层支持，因此现有脚本可以继续工作而无需更改。运行 `trace_processor --help-classic` 查看完整的经典标志列表。

#### {#subcommand-query} `query`：运行 SQL

`query` 加载 trace，运行一个或多个以 `;` 分隔的 SQL 语句，将结果打印到标准输出，然后退出。SQL 可以作为参数传递、从文件读取或通过 stdin 管道传入：

```bash
# 将 SQL 作为参数传递。
trace_processor query trace.pftrace "SELECT ts, dur, name FROM slice LIMIT 5"

# 从文件读取 SQL。
trace_processor query -f queries.sql trace.pftrace

# 通过 stdin 管道传入 SQL。
cat queries.sql | trace_processor query trace.pftrace
```

每个语句的结果集都作为 CSV 打印，连续的结果集之间用一个空行分隔。因为所有字符串值都加了引号，所以该分隔符是明确的。

标志：

- `--remote ADDR`：对热身好的 session 运行，而不是加载本地 trace；参见 [session](#sessions)。`ADDR` 是 session 名称、`*.sock` 或绝对 socket 路径，或 `host:port`。在此模式下不传递 trace 文件参数。
- `-f, --query-file FILE`：从 `FILE` 读取 SQL；传递 `-` 表示从 stdin 读取。
- `-i, --interactive`：查询完成后进入交互式 REPL。
- `-W, --wide`：打印结果时使用双倍宽度列。
- `--perf-file FILE`：将 trace 加载和查询计时写入 `FILE`。
- `--structured-query-id ID` 加 `--summary-spec FILE` _(高级)_：从一个或多个 [TraceSummarySpec](trace-summary.md) 文件中按 ID 运行单个结构化查询，替代上述 SQL 源。

#### {#subcommand-interactive} `interactive`：REPL

`interactive` 打开上一节中展示的交互式 PerfettoSQL 提示符。这是默认子命令，因此 `trace_processor trace.pftrace` 和 `trace_processor interactive trace.pftrace` 是等价的。唯一的特定子命令标志是 `-W, --wide`。

#### {#subcommand-server} `server`：HTTP、stdio 或 unix RPC

`server` 通过远程过程调用协议暴露 trace processor：

```bash
# HTTP 服务器，ui.perfetto.dev 使用。默认监听 9001 端口。
trace_processor server http

# 预加载 trace 并通过 HTTP 服务。
trace_processor server http trace.pftrace

# stdio 服务器：长度前缀 RPC，用于将 trace_processor 作为子进程嵌入的工具。
trace_processor server stdio

# 命名 unix-socket session：让 trace 保持热身状态，
# 供重复的 `query --remote <name>` 调用使用（参见上面的 session 一节）。
trace_processor server unix --name mysession --daemonize trace.pftrace

# 按名称或 socket 路径停止一个 unix session。
trace_processor server kill mysession
```

标志：

- `--port PORT`：HTTP 端口（默认 9001）。
- `--ip-address IP`：HTTP 绑定地址。
- `--additional-cors-origins O1,O2,...`：在默认值（`https://ui.perfetto.dev`、`http://localhost:10000`、`http://127.0.0.1:10000`）之外的额外 CORS 允许来源。
- `--name NAME`：unix 模式的 session 名称（默认：自动生成）。
- `--path PATH`：unix 模式的显式 socket 路径（与 `--name` 互斥）。
- `--daemonize`：脱离到后台运行（unix 模式，仅限 POSIX）。
- `--idle-timeout auto|DUR`：在这么长时间不活动后回收服务器（例如 `30m`、`90s`）；`auto` 表示 unix 为 30 分钟、http 为永不；`0`/`never` 禁用。
- `--idle-start auto|orphaned|last-query`：空闲时钟何时开始计时（默认 `auto`：感知所有者）。

在 `http` 和 `unix` 模式下，trace 文件是可选的；客户端也可以远程加载 trace。最常见的客户端是 Perfetto UI，它会自动检测本地服务器并将 trace 解析卸载给它。参见[可视化大型 trace](/docs/visualization/large-traces.md) 了解用户端流程，或 [trace_processor.proto](/protos/perfetto/trace_processor/trace_processor.proto) 了解 RPC 线路架构。

#### {#subcommand-summarize} `summarize`：计算 trace 汇总

`summarize` 计算 [trace 汇总](trace-summary.md)。先传递 trace 文件，再传递任意规范文件；通过 `--metrics-v2` 选择内置 v2 Metric：

```bash
# 运行每一个可用的 v2 Metric。
trace_processor summarize --metrics-v2 all trace.pftrace

# 运行 spec.textproto 中定义的两个特定 Metric。
trace_processor summarize \
  --metrics-v2 startup_metric,memory_metric \
  trace.pftrace spec.textproto
```

标志：

- `--metrics-v2 IDS`：逗号分隔的 metric ID，或字面值 `all`。
- `--metadata-query ID`：用于填充汇总 `metadata` 字段的查询 ID。
- `--format text|binary`：`TraceSummary` proto 的输出格式（默认 `text`）。
- `--post-query FILE`：汇总完成后运行此 SQL 文件。设置后，不打印汇总 proto；而是打印 SQL 输出。
- `--perf-file FILE`：将加载/查询计时写入 `FILE`。
- `-i, --interactive`：汇总完成后进入 REPL。

规范文件根据扩展名（`.pb` 为二进制，`.textproto` 为文本）检测为二进制或文本，并附带内容嗅探回退。

#### {#subcommand-export} `export`：将 trace 数据写入文件

`export` 将解析后的 trace 数据写入文件。格式是第一个位置参数，输出路径通过 `-o` 给出：

```bash
# 版本绑定的归档，可由同一版本的 trace processor 加载。
trace_processor export perfetto -o archive.tar trace.pftrace

# 静态表导出为 tar 中的标准 Arrow 文件。
trace_processor export arrow_tar -o tables.tar trace.pftrace

# 静态表和视图导出为 SQLite 数据库。
trace_processor export sqlite -o trace.db trace.pftrace
```

格式：

- **`perfetto`**：非空静态表组成的版本绑定归档。同一版本的新 trace processor 实例可以将其作为 trace 加载回来；不同版本也许能加载，但不保证。这是唯一可以重新加载的格式。
- **`arrow_tar`**：由标准 [Apache Arrow](https://arrow.apache.org/) 文件组成的 tar，每个静态注册的表一个文件，包括空表和隐式 ID 列。跨版本稳定且向前兼容，适合外部消费者（例如 pandas、Polars、pyarrow）。无法加载回 trace processor。
- **`sqlite`**：静态注册的表加上 trace 的视图，导出为任何 SQLite 工具都可读取的 SQLite 数据库。

标志：

- `-o, --output FILE`：输出文件路径（必填）。

这三种格式都导出静态注册的表；只有 `sqlite` 还包括视图。session 期间创建的运行时表（例如 `CREATE PERFETTO TABLE`）不会被导出。导出以流式写入磁盘，因此在处理大型 trace 时内存使用保持有界。有关面向任务的配方，请参阅[导出 trace 数据](/docs/getting-started/command-line-analysis.md#export-trace-data)。

#### {#global-flags} 全局标志（适用于每个子命令）

除了上面的特定子命令标志外，还接受以下全局标志，在所有子命令中行为相同：

- **Trace 摄取：** `--full-sort`、`--no-ftrace-raw`、`--analyze-trace-proto-content`、`--crop-track-events`。
- **PerfettoSQL 包：** `--add-sql-package PATH[@PKG]`、`--override-sql-package PATH[@PKG]`、`--override-stdlib PATH`(需要 `--dev`)。
- **Metric 扩展：** `--metric-extension DISK_PATH@VIRTUAL_PATH`。
- **辅助文件内容：** `--register-files-dir PATH` 将 `PATH` 下的文件内容暴露给导入器（例如 ETM 解码器）。
- **开发：** `--dev`、`--dev-flag KEY=VALUE`、`--extra-checks`。
- **元追踪：** `-m, --metatrace FILE`、`--metatrace-buffer-capacity N`、`--metatrace-categories CATEGORIES`。这会生成 Trace Processor 自身的 Perfetto trace，你可以将其重新加载到 UI 中进行性能调试。

## {#embedding} 嵌入 C++ 库

公共 API 以 [`trace_processor.h`](/include/perfetto/trace_processor/trace_processor.h) 中的 `TraceProcessor` 类为中心。所有高级操作（解析 trace 字节、执行 SQL 查询、计算汇总）都是此类的成员函数。

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

由于从文件系统读取 trace 是一个常见场景，因此在 [`read_trace.h`](/include/perfetto/trace_processor/read_trace.h) 中提供了辅助函数 `ReadTrace`：

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
