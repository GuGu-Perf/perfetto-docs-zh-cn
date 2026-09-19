# Cookbook: 从命令行分析 Trace

本页面是一组面向任务的配方，介绍如何在 shell 中使用 `trace_processor` 处理 trace：运行查询、免重复解析地迭代、合并、导出和转换。它展示每个任务的常见形式；完整的子命令和标志列表见
[trace_processor CLI 参考](/docs/reference/trace-processor-cli.md)。

## 获取二进制文件

```bash
curl -LO https://get.perfetto.dev/trace_processor
chmod +x ./trace_processor
```

这是一个轻量级 Python 包装器，首次使用时会为你的平台下载并缓存正确的原生二进制文件（Windows 和其他选项见
[reference](/docs/analysis/trace-processor.md#shell)）。

## 运行查询

`query` 会加载一个 trace，运行一条或多条以 `;` 分隔的 SQL 语句，并将每个结果集以 CSV 形式打印（结果集之间以空行分隔）：

```bash
# Inline SQL.
trace_processor query trace.pftrace "SELECT ts, dur, name FROM slice LIMIT 5"

# From a file (`-f -` for stdin): the natural form for scripts.
trace_processor query -f queries.sql trace.pftrace
```

trace 参数也可以是 `http(s)://` URL 或 Perfetto UI 分享链接
（`https://ui.perfetto.dev/#!/?s=<hash>`）；trace 会被下载并缓存在
`~/.cache/perfetto/` 下。

## 免重复解析的迭代：session {#iterate-without-re-parsing-sessions}

解析 trace 是开销最大的部分（大型 trace 需要数十秒），而普通的
`query` 调用每次都要付出这个代价。当你要对同一个 trace 运行多条查询时，可将它一次性加载到一个命名的后台 **session** 中，然后每次调用通过 `--remote` 指向它：

```bash
# 1. Load the trace into a background session (once per trace).
trace_processor server unix --name mysession --daemonize trace.pftrace

# 2. Query the warm session: no trace path, no reparse.
trace_processor query --remote mysession \
  "SELECT ts, dur, name FROM slice LIMIT 10"

# 3. Stop the session when you're done with the trace.
trace_processor server kill mysession
```

session 的状态会在多次 `--remote` 调用之间保留：一次调用中的
`CREATE PERFETTO TABLE` 或 `INCLUDE PERFETTO MODULE` 对下一次调用可见，
就像在单个交互式 shell 中一样，因此物化中间结果可以跨调用受益。空闲的
session 会在 30 分钟后被自动回收。

两点需要了解：

- 配置 trace 加载的标志（`--full-sort`、`--add-sql-package` 等）应放在
  `server unix` 调用上；`query --remote` 会拒绝它们。
- `--remote` 同样适用于 `interactive` 和 `summarize`，因此你可以在一个
  已经预热好的 session 上进入 REPL，或对其进行汇总。

session 命名、socket 路径和空闲超时调整见
[reference](/docs/reference/trace-processor-cli.md#subcommand-server)。

## 合并 trace

要将多个 trace 文件作为一个来分析（例如来自两台设备的 trace，或一个
系统 trace 加一个进程内 trace），可将它们打包到一个归档中。对于常见
情况（时钟已经相关联的 trace），无需任何配置：

```bash
trace_processor util merge -o merged.tar trace1.pftrace trace2.pftrace
trace_processor query merged.tar "SELECT count(*) FROM slice"
```

`util merge` 会写入一个 TAR 文件，Trace Processor 会将其作为单个合并的
trace 打开，并对结果进行 dry-run，以便在 trace 无法干净合并时发出警告
（`--strict` 会将其变为硬错误，适合在 CI 中使用）。任何由 trace 文件
组成的 ZIP 或 TAR 都可以以同样方式打开，因此在不依赖 `trace_processor`
的情况下你也可以自己打包：
`tar cf merged.tar trace1.pftrace trace2.pftrace`。

不要通过用 `cat` 拼接文件的方式来合并；那不是合并，
参见 [Trace merging](/docs/concepts/merging-traces.md)。

当你需要控制 trace 如何组合时（保持各设备的数据分开、对齐未同步的
时钟、为机器命名），可以向 `util merge` 传入 trace manifest
（`--manifest manifest.json`），或者自己将其 tar 进归档。详情参见
[从命令行合并 trace](/docs/analysis/merging-traces.md)，
包括如何验证一次合并正确放置了每个事件。

## 导出 trace 数据 {#export-trace-data}

`export` 将解析后的 trace 数据写入文件。第一个位置参数是格式，
`-o FILE` 是输出路径：

```bash
trace_processor export perfetto -o archive.tar trace.pftrace
trace_processor export arrow_tar -o tables.tar trace.pftrace
trace_processor export sqlite -o trace.db trace.pftrace
```

- **`perfetto`**: 静态表的一个与版本耦合的归档。同一版本的新
  trace processor 实例可以将其作为 trace 加载回来；不同版本或许能加载，
  但不保证。这是唯一可以重新加载的格式。
- **`arrow_tar`**: 每个静态注册的表一个标准
  [Apache Arrow](https://arrow.apache.org/)
  文件，打包在一个 tar 中。在 trace processor 各版本间稳定，适合用
  pandas、Polars 或 pyarrow 进行分析。无法加载回 trace processor。
- **`sqlite`**: 静态注册的表加上该 trace 的视图，作为一个任何 SQLite
  工具都能打开的 SQLite 数据库文件。

这三种格式导出的都是静态注册的表；只有 `sqlite` 还包含视图。session
期间创建的运行时表（例如 `CREATE PERFETTO TABLE`）不会被导出。标志和
格式详情见
[trace_processor CLI 参考](/docs/reference/trace-processor-cli.md#subcommand-export)。

## 转换为其他 trace 格式

`convert` 封装了 traceconv 工具，用于将 Perfetto trace 转换为其他格式，
例如 Chrome JSON（可在 chrome://tracing 或其他 Catapult 工具中加载）
或 pprof：

```bash
trace_processor convert json trace.pftrace trace.json
trace_processor convert text trace.pftrace trace.txt
```

运行 `trace_processor convert --help` 查看完整的格式列表，并参阅
[Converting from Perfetto](/docs/quickstart/traceconv.md) 了解底层
traceconv 工具的更多信息。`convert` 转换的是 trace 本身；如果要导出
解析后的表，请参见上面的[导出 trace 数据](#export-trace-data)。

## 下一步

- 编写查询本身：
  [Getting started with PerfettoSQL](/docs/analysis/perfetto-sql-getting-started.md)。
- 使用 Python 在大量 trace 上自动化分析：
  [Batch Trace Processor](/docs/analysis/batch-trace-processor.md)。
- 所有子命令和标志：
  [trace_processor CLI 参考](/docs/reference/trace-processor-cli.md)。
