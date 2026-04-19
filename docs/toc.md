- [快速入门](#)

  - [什么是 Perfetto？](README.md)
  - [什么是 Tracing？](tracing-101.md)
  - [如何开始使用 Perfetto？](getting-started/start-using-perfetto.md)

  - [教程](#)

  - [全栈 Perfetto](#)

  - [系统 Tracing](getting-started/system-tracing.md)
  - [应用内 Tracing](getting-started/in-app-tracing.md)
  - [Memory Profiling](getting-started/memory-profiling.md)
  - [CPU Profiling](getting-started/cpu-profiling.md)

  - [添加 Tracepoint](#)

  - [Android atrace](getting-started/atrace.md)
  - [Linux ftrace](getting-started/ftrace.md)

  - [非 Perfetto Trace 分析](#)

  - [支持的 trace 格式](getting-started/other-formats.md)
  - [转换为 Perfetto](getting-started/converting.md)

  - [实战指南](#)

  - [分析 Android Trace](getting-started/android-trace-analysis.md)
  - [周期性 Trace 快照](getting-started/periodic-trace-snapshots.md)

  - [案例研究](#)

  - [Android 内存使用](case-studies/memory.md)
  - [调度阻塞](case-studies/scheduling-blockages.md)

- [深入学习](#)

  - [概念](#)

  - [Trace 配置](concepts/config.md)
  - [缓冲区和数据流](concepts/buffers.md)
  - [服务模型](concepts/service-model.md)
  - [时钟同步](concepts/clock-sync.md)

  - [Trace 采集](#)

  - [后台 Tracing](learning-more/tracing-in-background.md)
  - [更多 Android Tracing](learning-more/android.md)
  - [Chrome Tracing](getting-started/chrome-tracing.md)

  - [Trace 插桩](#)

  - [Tracing SDK](instrumentation/tracing-sdk.md)
  - [Track Event](instrumentation/track-events.md)

  - [Trace 分析](#)

  - [快速入门](analysis/getting-started.md)
  - [PerfettoSQL](#)
  - [快速入门](analysis/perfetto-sql-getting-started.md)
  - [标准库](analysis/stdlib-docs.autogen)
  - [语法](analysis/perfetto-sql-syntax.md)
  - [样式指南](analysis/style-guide.md)
  - [向后兼容性](analysis/perfetto-sql-backcompat.md)
  - [Trace Processor](#)
  - [Trace Processor (C++)](analysis/trace-processor.md)
  - [Trace Processor (Python)](analysis/trace-processor-python.md)
  - [Trace 汇总](analysis/trace-summary.md)
  - [从 Perfetto 转换](quickstart/traceconv.md)

  - [Trace 可视化](#)

  - [Perfetto UI](visualization/perfetto-ui.md)
  - [打开大型 trace](visualization/large-traces.md)
  - [深度链接](visualization/deep-linking-to-perfetto-ui.md)
  - [调试 Tracks](analysis/debug-tracks.md)

  - [扩展 UI](#)

  - [概述](visualization/extending-the-ui.md)
  - [命令和宏](visualization/ui-automation.md)
  - [扩展服务器](visualization/extension-servers.md)

  - [贡献](#)

  - [快速入门](contributing/getting-started.md)
  - [常见任务](contributing/common-tasks.md)
  - [成为提交者](contributing/become-a-committer.md)
  - [UI](#)

  - [快速入门](contributing/ui-getting-started.md)
  - [插件](contributing/ui-plugins.md)

  - [FAQ](faq.md)

- [深入探索](#)

  - [数据源](#)

  - [内存数据源](#)

  - [Native Heap Profiler](data-sources/native-heap-profiler.md)
  - [Java 堆转储](data-sources/java-heap-profiler.md)
  - [Counters 和事件](data-sources/memory-counters.md)

  - [Ftrace 数据源](#)

  - [调度事件](data-sources/cpu-scheduling.md)
  - [系统调用](data-sources/syscalls.md)
  - [调频](data-sources/cpu-freq.md)

    - [Android 数据源](#)

      - [Android Aflags](data-sources/android-aflags.md)
       - [Atrace](data-sources/atrace.md)
      - [电池 Counters 和电源轨](data-sources/battery-counters.md)
       - [Frame Timeline](data-sources/frametimeline.md)
      - [Logcat](data-sources/android-log.md)
       - [其他数据源](data-sources/android-game-intervention-list.md)

  - [Trace 格式参考](#)

  - [Trace Packet Proto](reference/trace-packet-proto.autogen)
  - [高级程序化生成](reference/synthetic-track-event.md)

  - [高级 Trace 采集](#)

  - [Trace Config Proto](reference/trace-config-proto.autogen)
  - [并发 Tracing 会话](concepts/concurrent-tracing-sessions.md)
  - [分离模式](concepts/detached-mode.md)

  - [Android](#)

  - [开机 Tracing](case-studies/android-boot-tracing.md)
  - [OutOfMemoryError](case-studies/android-outofmemoryerror.md)
  - [Android 版本说明](reference/android-version-notes.md)

  - [Linux](#)

  - [内核 track 事件](reference/kernel-track-event.md)
  - [跨重启 Tracing](data-sources/previous-boot-trace.md)

  - [命令行参考](#)

  - [perfetto_cmd](reference/perfetto-cli.md)
  - [traced](reference/traced.md)
  - [traced_probes](reference/traced_probes.md)
  - [heap_profile 命令行](reference/heap_profile-cli.md)
  - [tracebox](reference/tracebox.md)

  - [高级 Trace 分析](#)

  - [PerfettoSQL](#)

  - [Prelude 表](analysis/sql-tables.autogen)
  - [内置函数](analysis/builtin.md)
  - [Stats 表参考](analysis/sql-stats.autogen)

  - [单 Trace 分析](#)

  - [旧版（v1）metrics](analysis/metrics.md)

  - [多 Trace 分析](#)

  - [批量 Trace Processor](analysis/batch-trace-processor.md)
  - [Bigtrace](deployment/deploying-bigtrace-on-a-single-machine.md)
  - [Kubernetes 上的 Bigtrace](deployment/deploying-bigtrace-on-kubernetes.md)

  - [高级 Perfetto SDK](#)

  - [拦截器](instrumentation/interceptors.md)

  - [高级 Trace 可视化](#)

  - [命令自动化参考](visualization/commands-automation-reference.md)
  - [扩展服务器协议](visualization/extension-server-protocol.md)

  - [贡献者参考](#)

  - [构建](contributing/build-instructions.md)
  - [测试](contributing/testing.md)
  - [开发者工具](contributing/developer-tools.md)

  - [团队文档](#)

  - [SDK 发布流程](contributing/sdk-releasing.md)
  - [Python 发布流程](contributing/python-releasing.md)
  - [UI 发布流程](visualization/perfetto-ui-release-process.md)
  - [Chrome 分支](contributing/chrome-branches.md)
  - [SQLite 升级指南](contributing/sqlite-upgrade-guide.md)

  - [设计文档](#)
  - [API 和 ABI 表面](design-docs/api-and-abi.md)
  - [Tracing 会话的生命周期](design-docs/life-of-a-tracing-session.md)
  - [ProtoZero](design-docs/protozero.md)
  - [安全模型](design-docs/security-model.md)
  - [Statsd Checkpoint Atom](design-docs/checkpoint-atoms.md)
  - [批量 Trace Processor](design-docs/batch-trace-processor.md)
  - [Trace Processor 架构](design-docs/trace-processor-architecture.md)
  - [Heapprofd 设计](design-docs/heapprofd-design.md)
  - [Heapprofd 线路协议](design-docs/heapprofd-wire-protocol.md)
  - [Heapprofd 采样](design-docs/heapprofd-sampling.md)
  - [Perfetto CI](design-docs/continuous-integration.md)
  - [LockFreeTaskRunner](design-docs/lock-free-task-runner.md)
