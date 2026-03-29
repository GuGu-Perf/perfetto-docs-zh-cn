# Batch Trace Processor

本文档描述了 Batch Trace Processor 的整体设计，并有助于将其集成到其他系统中。

![BTP Overview](/docs/images/perfetto-btp-overview.svg)

## 动机

Perfetto trace processor 是在单个 trace 上执行分析的事实标准方式。使用
[trace processor Python API](/docs/analysis/trace-processor#python-api)，
可以交互式地查询 traces、从这些结果绘制图表等。

虽然对单个 trace 的查询在调试该 trace 中的特定问题或在理解领域的早期阶段很有用，但它很快就会变得受限。一个 trace 不太可能代表
整个群体，而且很容易对查询过度拟合，即花费大量精力分解该 trace 中的问题，而忽视了群体中其他更常见的问题。

因此，我们实际上希望能够查询许多 traces
（通常在 250-10000+ 的量级）并识别在很大一部分中显示的模式。这确保了时间花在影响用户体验的问题上，而不仅仅是 trace 中碰巧出现的随机问题。

解决此问题的一个低工作量选项是简单地要求人们使用
[Executors](https://docs.python.org/3/library/concurrent.futures.html#executor-objects)
等实用程序与 Python API 并行加载多个 traces 并查询它们。不幸的是，这种方法有几个缺点：
- 每次想要查询多个 traces 时，每个用户都必须重新发明轮子。随着时间的推移，可能会有大量稍微修改的代码从每个地方复制。
- 虽然在单台机器上并行查询多个 traces 的基础知识很简单，但有一天，我们可能希望在多台机器上分片处理 traces。一旦发生这种情况，代码的复杂性将显著上升到需要中央实现的程度。因此，在工程师开始构建自己的自定义解决方案之前，最好先拥有 API。
- Perfetto 团队现在的一个大目标是使 trace 分析更易于访问，以减少我们需要参与的地方的数量。为批量 trace 分析等重要用例提供良好支持的 API 直接有助于实现这一目标。

虽然到目前为止我们已经讨论了查询 traces，但从不同 traces 加载 traces 的体验也应该同样好。这在历史上是 Python API 没有得到我们期望的那样多采用的一个大原因。

特别是在 Google 内部，我们不应该依赖工程师
知道 traces 在网络文件系统上的位置以及目录布局。
相反，他们应该能够简单地指定数据源(即
实验室、测试群体)和一些 traces 应该匹配的参数(例如 build id、日期、内核
版本)，并且应该找到并加载符合这些条件的 traces。

将所有这些放在一起，我们想要构建一个可以：
- 在 O(s) 内交互式查询 ~1000- traces(对于简单查询)
- 从 trace processor 公开完整的 SQL 表达能力
- 以最小的仪式从许多来源加载 traces。这应该包括
  Google 内部来源：例如实验室运行和内部测试群体
- 与数据分析库集成，便于图表绘制和可视化

## 设计亮点

在本节中，我们简要讨论了构建 batch trace processor 时做出的一些最有影响力的设计决策及其背后的原因。

### 语言

语言的选择非常简单。Python 已经是广泛领域中数据分析的首选语言，我们的问题还不够独特，不足以做出不同的决定。此外，另一个支持点是 trace processor 的 Python API 的存在。这进一步简化了实现，因为我们不必从头开始。

选择 Python 的主要缺点是性能，但考虑到所有数据 crunching 都发生在 TP 内部的 C++ 中，这不是一个大因素。

### Trace URIs 和 Resolvers

[Trace URIs](/docs/analysis/batch-trace-processor#trace-uris)
是从各种公共和内部来源加载 traces 问题的优雅解决方案。与 web URIs 一样，trace URI 的想法是描述应该从中获取 traces 的协议（即源）以及 traces 应该匹配的参数（即查询参数）。

Batch trace processor 应该与 trace URIs 及其
resolvers 紧密集成。用户应该能够传递 URI（为了最大的灵活性，实际上只是一个字符串）或可以产生 traces 文件路径列表的 resolver 对象。

为了处理 URI 字符串，应该有一些机制来"注册"resolvers
以使它们有资格解析某个"协议"。默认情况下，我们应该
提供一个 resolver 来处理文件系统。我们应该确保 resolver
设计使得 resolvers 可以是闭源的，而 batch trace
processor 的其余部分是开放的。

除了产生 traces 列表的工作之外，resolvers 还应该负责为每个 trace 创建元数据，这些是关于用户可能感兴趣的 trace 的不同信息片段，例如 OS
版本、设备名称、收集日期等。然后，元数据可以在跨多个 traces "flattening"结果时使用，如下所述。

### 持久化加载的 traces

优化 traces 的加载对于我们从 batch trace processor 想要的 O(s) 查询性能至关重要。Traces 通常是通过网络访问的，这意味着获取它们的内容具有高延迟。
Traces 也需要至少几秒钟来解析，在甚至还没有开始查询运行时间之前就吃掉了 O(s) 的预算。

为了解决这个问题，我们决定将所有 traces 完全加载到内存中的 trace processor 实例中。这样，我们不必在每次查询/一组查询时都加载它们，而是可以直接发出查询。

目前，我们将 traces 的加载和查询限制在一台机器上。虽然查询 n 个 traces 是"embarrassingly parallel"并且可以完美地跨多台机器分片，但将分布式系统引入任何解决方案只会使一切变得更加复杂。在"未来计划"部分进一步探讨了向多台机器的迁移。

### Flattening 查询结果

返回查询 n 个 traces 结果的天真方式是返回 n 个元素的列表，每个元素是单个 trace 的结果。然而，在使用 BTP 进行几个案例研究性能调查后，很明显这个显而易见的答案对最终用户来说并不是最方便的。

相反，一个证明非常有用的模式是将结果"flatten"到包含所有 traces 结果的单个表中。然而，简单地 flattening 会导致我们丢失关于行源自哪个 trace 的信息。我们可以通过允许 resolvers 静默添加包含每个 trace 元数据的列来处理这个问题。

因此，假设我们用以下查询查询三个 traces：

```SELECT ts, dur FROM slice```

然后在 flattening 操作中可能会在幕后执行以下操作：
![BTP Flattening](/docs/images/perfetto-btp-flattening.svg)


## 集成点

Batch trace processor 需要是开源的，同时允许与 Google 内部工具深度集成。因此，设计中内置了各种集成点，以允许封闭组件替代默认的开源组件。

第一个点是"平台"代码思想的正式化。自从 Python API 开始以来，总是需要内部代码以与开源代码稍微不同的方式运行。例如，Google 内部 Python 发行版不使用 Pip，而是将依赖项打包到单个二进制文件中。"平台"的概念松散地存在以抽象这种差异，但这非常临时。作为 batch trace processor 实现的一部分，这已经追溯性地正式化了。

Resolvers 是另一个大的可插拔点。通过允许为每个内部 trace 源(例如实验室、测试群体)注册一个"协议"，我们允许 trace 加载被整齐地抽象。

最后，对于 batch trace processor 具体来说，我们抽象了创建线程池以加载 traces 和运行查询。程序内部可用的并行性和内存通常与系统上可用的 CPU/内存不 1:1 对应：需要访问内部 API 才能找到这些信息。

## 未来计划

运行 batch trace processor 时的一个常见问题是，我们受限于单台机器，因此只能加载 O(1000) 个 traces。
对于罕见的问题，即使在如此大的样本中，可能也只有少数 traces 匹配给定的模式。

解决这个问题的一种方法是构建一个"无 trace 限制"模式。这里的想法是，你可以像往常一样使用 batch trace processor 开发查询，在 O(s) 性能下操作 O(1000) 个 traces。一旦查询相对确定，我们就可以"切换"batch trace processor 的模式，使其更接近在 O(10000)+ 个 traces 上操作的"MapReduce"风格管道，一次加载 O(n cpus) 个 traces。

这使我们能够在开发查询时保持快速的迭代速度，同时也允许进行大规模分析，而无需将代码移动到管道模型。然而，这种方法并没有真正解决问题的根本原因，即我们被限制在单台机器上。

这里的"理想"解决方案是，如上所述，在 >1 台机器上分片 batch trace processor。查询 traces 时，每个 trace 完全独立于任何其他 trace，因此跨多台机器并行化可以获得非常接近完美的性能提升，而成本很小。

然而，这将是一个相当复杂的任务。我们需要设计 API，以允许与各种计算平台(例如 GCP、Google 内部、你的自定义基础设施)进行可插拔集成。即使仅限于 Google 基础设施并将其他开放供贡献，内部基础设施的理想工作负载也不匹配"让一堆机器绑定到一个用户等待他们的输入"的方法。在走向这里之前，需要进行大量的研究和设计工作，但这可能是值得的。
