# Trace 分析概述

本页面是使用 Perfetto 进行 trace 分析的入口点。它概述了你可以使用的不同工具和概念，从 traces 中提取有意义的信息，指导你从交互式探索到大规模自动化分析。

## 挑战：理解原始 Trace

trace 中的事件经过优化，可实现快速、低开销的记录。因此，traces 需要大量的数据处理才能从中提取有意义的信息。这种情况由于仍在使用且需要在 trace 分析工具中支持的旧格式数量而变得更加复杂。

## 解决方案：Trace Processor 和 PerfettoSQL

Perfetto 中所有 trace 分析的核心是 **Trace Processor**，这是一个解决此复杂性的 C++ 库。它负责解析、结构化和查询 trace 数据。

Trace Processor 抽象了底层的 trace 格式，并通过 **PerfettoSQL** 暴露数据，PerfettoSQL 是 SQL 的一种方言，允许你查询 trace 内容，就像它们是数据库一样。

Trace Processor 负责：

- **解析 traces**：摄取各种 trace 格式，包括 Perfetto、ftrace 和 Chrome JSON。
- **结构化数据**：将原始 trace 数据整理为结构化格式。
- **暴露查询接口**：提供 PerfettoSQL 接口以查询结构化数据。
- **打包标准库**：包含 PerfettoSQL 标准库，用于开箱即用的分析。

## Trace 分析工作流程

Perfetto 提供了一组灵活的工具，它们相互构建，以支持不同的分析需求。典型的工作流程从广泛的交互式探索到精确的自动化分析。

1. **交互式探索**：首先使用 Perfetto UI 或 `trace_processor` shell 交互式地探索你的 trace。这对于临时调查、调试和了解 trace 中的数据非常有用。

2. **程序化分析**：一旦你更好地了解了你的 trace，就可以使用 Trace Processor 的 Python 和 C++ 库自动化查询并构建更复杂的分析管道。

3. **大规模分析**：对于构建健壮的自动化分析管道，Trace Summarization 是推荐的方法。它允许你为分析定义稳定、结构化的输出，非常适合大规模性能监控和回归检测。

## 下一步

### 学习语言：PerfettoSQL

在深入研究工具之前，对 PerfettoSQL 有基础理解很有帮助。

- **[PerfettoSQL 入门](perfetto-sql-getting-started.md)：**学习 PerfettoSQL 的核心概念以及如何编写查询。
- **[PerfettoSQL 语法](perfetto-sql-syntax.md)：**了解 Perfetto 支持的 SQL 语法，包括创建函数、表和视图的特殊功能。
- **[标准库](stdlib-docs.autogen)：**探索标准库中提供的丰富模块，用于分析常见场景，如 CPU 使用率、内存和功耗。

### 探索工具

一旦熟悉了 PerfettoSQL 的基础知识，就可以探索使用 Trace Processor 的不同方式。

- **[Trace Processor (C++)](trace-processor.md)：**学习如何使用交互式 shell 和底层的 C++ 库。
- **[Trace Processor (Python)](trace-processor-python.md)：**利用 Python API 将 trace 分析与丰富的数据科学和可视化生态系统结合起来。

### 自动化你的分析

对于大规模或自动化分析，Trace Summarization 是推荐的方法。

- **[Trace Summarization](trace-summary.md)：**学习如何定义和运行摘要，以从你的 traces 生成一致的、结构化的 protobuf 输出。
