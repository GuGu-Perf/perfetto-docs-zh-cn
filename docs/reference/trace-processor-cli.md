# Trace Processor 命令行参考

`trace_processor` 用于加载、查询、转换、丰富和提供 trace。原生可执行文件构建为 `trace_processor_shell`；可下载的 `trace_processor` 包装器以相同的命令行参数运行它。

有关安装和你的第一批查询，请参阅[从命令行分析 Trace](/docs/getting-started/command-line-analysis.md)。有关 C++ 库，请参阅 [Trace Processor](/docs/analysis/trace-processor.md)。

## 概要

```text
trace_processor <command> [flags] [positional args]
trace_processor <trace_file>
trace_processor help <command>
```

只给定 trace 文件而不给定命令时，工具会打开交互式 SQL shell。`--help` 打印顶层帮助；`<command> --help` 和 `help <command>` 打印特定命令的帮助，包括该构建版本支持的标志。

经典的扁平标志接口（`-q`、`-Q`、`--httpd`、`--summary`、`--run-metrics`、`-e`、`--stdiod`）仍受支持。使用 `--help-classic` 查看其标志。

## {#global-flags} 全局标志（适用于每个子命令）

除了下面各子命令的专属标志外，还可以使用这些标志，它们在所有子命令中的行为相同：

- **帮助与版本：**`-h, --help`、`-v, --version`。
- **进度：**`--no-progress` 禁用实时进度输出。
- **安静模式：**`--quiet` 还会抑制常规状态消息和汇总。命令结果、警告和错误仍会打印。
- **Trace 摄取：**`--full-sort`、`--no-ftrace-raw`、`--analyze-trace-proto-content`、`--crop-track-events`。
- **PerfettoSQL 包：**`--add-sql-package PATH[@PKG]`、`--override-sql-package PATH[@PKG]`、`--override-stdlib PATH`（需要 `--dev`）。
- **指标扩展：**`--metric-extension DISK_PATH@VIRTUAL_PATH`。
- **辅助文件内容：**`--register-files-dir PATH` 将 `PATH` 下文件的内容暴露给导入器（例如 ETM 解码器）。
- **开发：**`--dev`、`--dev-flag KEY=VALUE`、`--extra-checks`。
- **元追踪：**`-m, --metatrace FILE`、`--metatrace-buffer-capacity N`、`--metatrace-categories CATEGORIES`。这会生成一个 trace processor 自身的 Perfetto trace，你可以将其加载回 UI 进行性能调试。

## 进度与颜色

诊断信息输出到 stderr。只有在 stderr 是终端且 `TERM` 不是 `dumb` 时才使用实时进度和 ANSI 颜色。`--no-progress` 禁用实时进度；警告和错误不受影响。

可以通过 [FORCE_COLOR](https://force-color.org/) 和 [NO_COLOR](https://no-color.org/) 环境变量覆盖颜色行为。非空的 `FORCE_COLOR` 强制开启颜色，并优先于强制关闭颜色的非空 `NO_COLOR`。

`--quiet` 禁用进度并丢弃常规状态消息、耗时信息和成功汇总。SQL 行、转换后的 trace 等命令结果、警告和错误不受影响。

## Debuginfod {#debuginfod}

使用 `--debuginfod` 时，native 符号化会按 build ID 从 [debuginfod](https://sourceware.org/elfutils/Debuginfod.html) 服务器下载调试文件，因此不需要本地二进制文件。它适用于运行 native 符号化的所有场景：trace 加载、`bundle`、`util symbolize` 和 `convert profile`。它需要 `PATH` 上有 `curl` 和 `llvm-symbolizer`。远程 session 使用服务器端的配置，因此请在启动服务器时传入 `--debuginfod`。

| 标志 | 含义 | 默认值 |
| --- | --- | --- |
| `--debuginfod` | 启用缓存查找和下载。 | 禁用 |
| `--debuginfod-urls URLS` | 以空白分隔的 HTTP(S) 服务器根地址。 | `DEBUGINFOD_URLS` |
| `--debuginfod-cache-path PATH` | 已下载文件的存放目录。 | `DEBUGINFOD_CACHE_PATH`，否则 `$XDG_CACHE_HOME/debuginfod_client`、`~/.cache/debuginfod_client` 或 `%LOCALAPPDATA%\debuginfod_client` |
| `--debuginfod-connect-timeout SECONDS` | 每个请求的连接超时。 | `5` |
| `--debuginfod-stall-timeout SECONDS` | 传输速度低于每秒一字节并持续此时长时中止传输。 | `10` |

仅设置 URL 并不会启用下载；配置了 `DEBUGINFOD_URLS` 但没有 `--debuginfod` 时会产生警告。本地符号路径和 Breakpad 文件会先被搜索，只有仍未解析的 build ID 才会被获取——先从缓存，再依次从每个服务器。下载的文件会与请求的 build ID 核对，并以原子方式发布到缓存。没有自动清除机制。`DEBUGINFOD_URLS` 和 `LLVM_SYMBOLIZER_OPTS` 会从 `llvm-symbolizer` 的环境中移除，使其无法自行下载。汇总信息会统计下载数、缓存命中数、没有服务器持有的 build ID 数和失败的查找数，并列出无法访问的服务器；`--verbose` 会列出为每个 mapping 尝试的每个服务器及未生效的原因。

## {#subcommands} 命令

| 命令 | 用途 |
| --- | --- |
| [`query`](#subcommand-query) | 运行 SQL 并打印结果。 |
| [`interactive`](#subcommand-interactive) | 打开 SQL 提示符。 |
| [`server`](#subcommand-server) | 通过 RPC 提供 trace 服务或管理 session。 |
| [`summarize`](#subcommand-summarize) | 计算 trace 汇总。 |
| [`export`](#subcommand-export) | 导出解析后的 trace 数据。 |
| [`convert`](#subcommand-convert) | 将 trace 转换为其他格式。 |
| [`bundle`](#subcommand-bundle) | 将 trace 与符号及反混淆数据打包。 |
| [`util`](#subcommand-util) | 运行底层 trace 实用工具。 |
| [`metrics`](#subcommand-metrics) | 运行旧版 v1 指标。 |

### {#subcommand-query} `query`：运行 SQL

`query` 加载一个 trace，运行一条或多条以 `;` 分隔的 SQL 语句，将结果打印到 stdout 并退出。SQL 可以作为参数传入、从文件读取或通过 stdin 管道输入：

```bash
# Pass SQL as an argument.
trace_processor query trace.pftrace "SELECT ts, dur, name FROM slice LIMIT 5"

# Read SQL from a file.
trace_processor query -f queries.sql trace.pftrace

# Pipe SQL on stdin.
cat queries.sql | trace_processor query trace.pftrace
```

每条语句的结果集以 CSV 形式打印，连续的结果集之间以单个空行分隔。由于每个字符串值都带引号，该分隔符不会有歧义。

标志：

- `--remote ADDR`：在已预热的 session 上运行，而不是加载本地 trace；参见 [sessions](/docs/analysis/trace-processor.md#sessions)。`ADDR` 是 session 名称、`*.sock` 或绝对 socket 路径，或 `host:port`。此模式下不传递 trace 文件参数。
- `-f, --query-file FILE`：从 `FILE` 读取 SQL；传入 `-` 表示从 stdin 读取。
- `-i, --interactive`：查询结束后进入交互式 REPL。
- `-W, --wide`：打印结果时使用双倍宽度的列。
- `--perf-file FILE`：将 trace 加载和查询的耗时写入 `FILE`。
- `--structured-query-id ID` 加 `--summary-spec FILE` *（高级）*：按 ID 运行来自一个或多个 [TraceSummarySpec](/docs/analysis/trace-summary.md) 文件的单个结构化查询，而不是使用上面的 SQL 来源。

### {#subcommand-interactive} `interactive`：REPL

`interactive` 打开 [shell 指南](/docs/analysis/trace-processor.md#shell)中描述的同一个交互式 PerfettoSQL 提示符。它是默认子命令，因此 `trace_processor trace.pftrace` 与 `trace_processor interactive trace.pftrace` 等价。唯一的子命令专属标志是 `-W, --wide`。

### {#subcommand-server} `server`：HTTP、stdio 或 unix RPC

`server` 通过远程过程调用协议暴露 trace processor：

```bash
# HTTP server, used by ui.perfetto.dev. Listens on port 9001 by default.
trace_processor server http

# Pre-load a trace and serve it over HTTP.
trace_processor server http trace.pftrace

# stdio server: length-prefixed RPC for tooling that embeds
# trace_processor as a subprocess.
trace_processor server stdio

# Named unix-socket session: keeps the trace warm for repeated
# `query --remote <name>` calls (see the shell guide).
trace_processor server unix --name mysession --daemonize trace.pftrace

# Stop a unix session by name or socket path.
trace_processor server kill mysession
```

标志：

- `--port PORT`：HTTP 端口（默认 9001）。
- `--ip-address IP`：HTTP 绑定地址。
- `--additional-cors-origins O1,O2,...`：在默认值（`https://ui.perfetto.dev`、`http://localhost:10000`、`http://127.0.0.1:10000`）之外额外允许的 CORS 来源。
- `--name NAME`：unix 模式的 session 名称（默认：自动生成）。
- `--path PATH`：unix 模式的显式 socket 路径（与 `--name` 互斥）。
- `--daemonize`：分离到后台运行（unix 模式，仅限 POSIX）。
- `--idle-timeout auto|DUR`：在此空闲时长后回收服务器（例如 `30m`、`90s`）；`auto` 表示 unix 模式 30 分钟、http 模式永不回收，`0`/`never` 禁用。
- `--idle-start auto|orphaned|last-query`：空闲时钟何时起算（默认 `auto`：感知所有者）。

在 `http` 和 `unix` 模式下 trace 文件是可选的；客户端也可以远程加载 trace。最常见的客户端是 Perfetto UI，它会自动检测本地服务器并将 trace 解析卸载给它。终端用户流程参见[可视化大型 trace](/docs/visualization/large-traces.md)，RPC 线路格式参见 [trace_processor.proto](/protos/perfetto/trace_processor/trace_processor.proto)。

### {#subcommand-summarize} `summarize`：计算 trace 汇总

`summarize` 计算 [trace 汇总](/docs/analysis/trace-summary.md)。先传递 trace 文件，再传递任意 spec 文件；使用 `--metrics-v2` 选择内建 v2 指标：

```bash
# Run every available v2 metric.
trace_processor summarize --metrics-v2 all trace.pftrace

# Run two specific metrics defined in spec.textproto.
trace_processor summarize \
  --metrics-v2 startup_metric,memory_metric \
  trace.pftrace spec.textproto
```

标志：

- `--metrics-v2 IDS`：逗号分隔的指标 id，或字面量 `all`。
- `--metadata-query ID`：用于填充汇总 `metadata` 字段的查询 id。
- `--format text|binary`：`TraceSummary` proto 的输出格式（默认 `text`）。
- `--post-query FILE`：汇总完成后运行此 SQL 文件。设置后不打印汇总 proto，而是打印 SQL 输出。
- `--perf-file FILE`：将加载/查询耗时写入 `FILE`。
- `-i, --interactive`：汇总完成后进入 REPL。

Spec 文件按扩展名（`.pb` 为二进制，`.textproto` 为文本）检测是二进制还是文本，并以内容嗅探作为兜底。

### {#subcommand-export} `export`：将 trace 数据写入文件

`export` 将解析后的 trace 数据写入文件。第一个位置参数是格式，输出路径通过 `-o` 给出：

```bash
# Version-coupled archive, loadable by the same version of trace processor.
trace_processor export perfetto -o archive.tar trace.pftrace

# Static tables as standard Arrow files in a tar.
trace_processor export arrow_tar -o tables.tar trace.pftrace

# Static tables and views as a SQLite database.
trace_processor export sqlite -o trace.db trace.pftrace
```

格式：

- **`perfetto`** ：非空静态表的一个与版本耦合的归档。同一版本的新 trace processor 实例可以将其作为 trace 加载回来；不同版本或许能加载，但不保证。这是唯一可以重新加载的格式。
- **`arrow_tar`** ：一个由标准 [Apache Arrow](https://arrow.apache.org/) 文件组成的 tar，每个静态注册的表一个文件，包括空表和隐式 ID 列。跨版本稳定且向前兼容，适合外部消费者（例如 pandas、Polars、pyarrow）。无法加载回 trace processor。
- **`sqlite`** ：静态注册的表加上该 trace 的视图，作为一个任何 SQLite 工具都能读取的 SQLite 数据库。

标志：

- `-o, --output FILE`：输出文件路径（必需）。

这三种格式导出的都是静态注册的表；只有 `sqlite` 还包含视图。session 期间创建的运行时表（例如 `CREATE PERFETTO TABLE`）不会被导出。导出以流式写入磁盘，因此即使 trace 很大，内存使用也保持有界。面向任务的配方参见[导出 trace 数据](/docs/getting-started/command-line-analysis.md#export-trace-data)。

### {#subcommand-convert} `convert`：更改 trace 格式

```text
trace_processor convert <format> [flags] [input] [output]
```

格式包括 `systrace`、`json`、`ctrace`、`text`、`profile` 和 `firefox`。省略的输入和输出路径使用 stdin 和 stdout。对于 `profile`，请使用 `--output-dir` 而不是输出文件参数。运行 `help convert` 查看特定格式的选项。

### {#subcommand-util} `util`：底层 trace 实用工具

```text
trace_processor util <utility> [flags] [positional args]
```

实用工具包括 `merge`、`symbolize`、`deobfuscate`、`decompress_packets` 和 `text_to_binary`。运行 `help util` 查看它们的参数。工作流参见[合并指南](/docs/analysis/merging-traces.md)和[符号化指南](/docs/learning-more/symbolization.md)。

### {#subcommand-metrics} `metrics`：旧版 v1 指标

运行 v1 指标。对于新的工作流，请使用 `summarize --metrics-v2`。运行 `help metrics` 查看支持的标志，旧版工作流参见[基于 Trace 的 metrics](/docs/analysis/metrics.md)。

### {#subcommand-bundle} `bundle`：丰富 trace

#### 概要

```text
trace_processor bundle [options] <input> <output>
```

生成一个丰富化的 trace：在 TAR 归档中包含输入 trace、native 符号 Packet 和 Java/Kotlin 反混淆 Packet。Perfetto UI 和 Trace Processor 可以直接打开此归档。

前提条件和完整示例参见[符号化指南](/docs/learning-more/symbolization.md#option-1-traceconv-bundle)。运行 `trace_processor help bundle` 查看接受的完整标志列表，包括 Trace Processor 的常用选项。

#### 参数

| 参数 | 含义 |
| --- | --- |
| `input` | 已存在的常规 trace 文件。不支持 stdin。 |
| `output` | 目标文件路径。不支持 stdout。其父目录必须存在且可写。 |

输入和输出必须指向不同的文件，包括通过硬链接指向同一文件的情况。已存在的输出必须是常规文件。输出为符号链接会被拒绝；请直接指定目标路径。

#### 选项

- `--symbol-paths PATH1,PATH2,...`：搜索 native 符号的额外目录（除了自动发现的路径）。
- `--no-auto-symbol-paths`：禁用 native 符号路径的自动发现。`--symbol-paths` 和 `PERFETTO_BINARY_PATH` 仍然生效。
- `--proguard-map [pkg=]PATH`：用于 Java/Kotlin 反混淆的额外 ProGuard/R8 `mapping.txt`。对多个 mapping 重复此标志。可选的 `pkg=` 前缀将 mapping 限定到特定的 Java 包。
- `--no-auto-proguard-maps`：禁用 ProGuard/R8 mapping 文件的自动发现（例如标准 Android Gradle 布局）。仅应用通过 `--proguard-map` 给出的 mapping。
- `--verbose`：打印尝试的每个路径和查找的每个库 &mdash; 在调试"could not find"错误时很有用。

#### {#symbol-paths} Native 符号路径

符号路径是一个包含带符号的 native 二进制文件、单独的 native 调试文件或 Breakpad 符号文件的目录。它不是源代码目录，也不是 ProGuard/R8 mapping 文件。Native 二进制文件必须与 trace 中记录的 build ID 匹配；重新构建相同的源代码不一定能产生匹配。

`bundle` 会递归索引所配置目录下的 native 二进制文件，并按 build ID 匹配。它们的目录布局和文件名不需要与 trace 中记录的路径匹配。对于 Breakpad，会在每个配置的目录中搜索 `<build-id>.breakpad`（build ID 以小写十六进制编码）。

目录列表由以下来源组成：

1. 逗号分隔的 `--symbol-paths` 参数。
2. `PERFETTO_BINARY_PATH`，POSIX 上以 `:` 分隔，Windows 上以 `;` 分隔。
3. 自动发现的目录（除非设置了 `--no-auto-symbol-paths`）。

自动目录按以下顺序添加（当它们存在时）：

| 目录 | 来源 |
| --- | --- |
| `/usr/lib/debug` | 系统调试文件。 |
| `$HOME/.debug` | 每用户调试文件。 |
| `$ANDROID_PRODUCT_OUT/symbols` | AOSP 构建输出。 |
| `./app/build/intermediates/cmake` | Gradle CMake 输出，相对于工作目录。 |
| `./app/build/intermediates/merged_native_libs` | Gradle native 库，相对于工作目录。 |
| `./.build-id` | 本地 build-ID 目录，相对于工作目录。 |

启用自动发现时，`stack_profile_mapping` 中记录的绝对 Unix 风格二进制路径也会被视为主机上的单个文件。`--no-auto-symbol-paths` 会同时禁用这些文件和自动目录；它不会禁用 `PERFETTO_BINARY_PATH`。

上面的顺序描述的是路径如何被收集，并不保证递归索引时同一 build ID 的重复副本之间的优先级。优先选择包含匹配的未剥离或调试二进制文件的目录，而不是混合已剥离和未剥离的副本。使用 `--verbose` 检查查找细节。

#### 符号化结果

汇总会报告多少帧记录已解析、多少仍未解析。未解析的帧按原因分组，每组下方列出受影响的 mapping：未找到的二进制文件、找到但不含该地址符号的二进制文件、没有 vmlinux 的内核帧、没有 build ID 的 mapping，以及匿名或 JIT 内存。每种原因有一个提示。只有当符号源返回可用的函数名时，一帧才算已解析。第一个解析出某地址的源胜出；后面的源只会被询问仍未解析的地址。`--verbose` 会列出每个 mapping 及其 build ID、所使用的符号文件，以及每个被搜索的路径及其被拒绝的原因。

#### 输出替换与清理

该命令在目标文件旁写入一个临时文件。只有在成功写入并刷新完整的 bundle 之后才会替换目标文件。如果读取、丰富化或写入失败，已有的输出会被保留。

普通失败会在清理时删除临时文件。突然终止（包括 Ctrl-C）或清理失败可能留下名为 `<output>.tmp.<uuid>` 的同级文件。清理是尽力而为的；不完整的数据永远不会被发布为目标文件。进程停止后即可删除遗留的临时文件。

#### 退出状态

成功写入的 bundle 以状态 0 退出，包括某些符号不可用的情况。符号化汇总会报告缺失的符号。无效参数和生成 bundle 失败以非零状态退出。
