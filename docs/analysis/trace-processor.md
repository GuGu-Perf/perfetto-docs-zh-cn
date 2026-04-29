# Trace Processor (C++)

_Trace Processor 是一个 C++ 库（[/src/trace_processor](/src/trace_processor)），它摄取以多种格式编码的 trace，并公开 SQL 接口来查询存储在一组一致表中的 trace 事件。它还具有其他功能，包括计算 trace 汇总、使用用户友好的描述为 trace 添加注释以及从 trace 的内容派生新事件。_

![Trace processor 框图](/docs/images/trace-processor.png)

大多数用户将通过 [`trace_processor` shell](#shell) 与 Trace Processor 交互，这是一个围绕该库的命令行包装器，可打开交互式 PerfettoSQL 提示符。想要将 Trace Processor 集成到其他 C++ 应用程序中的嵌入者应跳转到[嵌入 C++ 库](#embedding)。Python 用户应参阅 [Python API](trace-processor-python.md)。

## {#shell} trace_processor shell

`trace_processor` shell 是一个命令行二进制文件，它包装 C++ 库，提供一种方便的方法来交互式分析 trace。

### 下载 shell

可以从 Perfetto 网站下载 shell。下载的是一个轻量级 Python 包装器，首次使用时会在 `~/.local/share/perfetto/prebuilts` 下获取并缓存适合你平台的原生二进制文件（包括 Windows 上的 `trace_processor_shell.exe`）。

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

下载后，你可以立即使用它打开 trace 文件：

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

这将打开一个交互式 SQL shell，你可以在其中查询 trace。有关如何编写查询的更多信息，请参阅 [PerfettoSQL 入门指南](perfetto-sql-getting-started.md)。

例如，要查看 trace 中的所有 Slice，你可以运行以下查询：

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

## {#embedding} 嵌入 C++ 库

公共 API 以 [`trace_processor.h`](/include/perfetto/trace_processor/trace_processor.h) 中定义的 `TraceProcessor` 类为中心。所有高级操作 — 解析 trace 字节、执行 SQL 查询、计算汇总 — 都是此类的成员函数。

通过 `CreateInstance` 创建 `TraceProcessor` 实例：

```cpp
#include "perfetto/trace_processor/trace_processor.h"

using namespace perfetto::trace_processor;

Config config;
std::unique_ptr<TraceProcessor> tp = TraceProcessor::CreateInstance(config);
```

### 加载 trace

要摄取 trace，请使用 trace 字节块重复调用 `Parse`，然后在推送完整个 trace 后调用 `NotifyEndOfFile`：

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

通过 `ExecuteQuery` 提交查询，它返回一个 `Iterator`，以流式方式将行返回给调用者：

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

- **Trace 汇总**（`Summarize`）— 计算 trace 的结构化汇总。有关此功能的面向用户描述，请参阅 [Trace 汇总](trace-summary.md)。
- **自定义 SQL 包**（`RegisterSqlPackage`）— 在包名下注册 PerfettoSQL 文件，以便查询可以 `INCLUDE` 它们。
- **带外文件内容**（`RegisterFileContent`）— 将辅助数据传递给导入器，例如用于解码 ETM trace 的二进制文件。
- **元追踪**（`EnableMetatrace` / `DisableAndReadMetatrace`）— 对 Trace Processor 本身进行追踪以进行性能调试。

有关完整的 API 接口，请参阅 [`trace_processor.h`](/include/perfetto/trace_processor/trace_processor.h) 中的注释。
