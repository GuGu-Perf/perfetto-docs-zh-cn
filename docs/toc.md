- [概述](#)

  - [什么是 Perfetto？](README.md)
  - [什么是 Tracing？](tracing-101.md)
  - [如何开始使用 Perfetto？](getting-started/start-using-perfetto.md)

- [快速入门](#)

  - [教程](#)

    - [系统 Tracing](getting-started/system-tracing.md) {.tag-android .tag-linux}
    - [应用内 Tracing](getting-started/in-app-tracing.md) {.tag-cpp}
    - [Memory Profiling](getting-started/memory-profiling.md) {.tag-android .tag-linux}
    - [CPU Profiling](getting-started/cpu-profiling.md) {.tag-android .tag-linux}
    - [使用 atrace 插桩](getting-started/atrace.md) {.tag-android}
    - [使用 ftrace 插桩](getting-started/ftrace.md) {.tag-linux .tag-android}
    - [录制 Chrome Trace](getting-started/chrome-tracing.md) {.tag-chrome}
    - [导入其他格式](getting-started/other-formats.md) {.tag-perf}
    - [转换为 Perfetto 格式](getting-started/converting.md) {.tag-perf}

  - [实战指南](#)

    - [分析 Android Trace](getting-started/android-trace-analysis.md) {.tag-android}
    - [周期性 Trace 快照](getting-started/periodic-trace-snapshots.md) {.tag-android .tag-linux}
    - [开机 Tracing](case-studies/android-boot-tracing.md) {.tag-android}
    - [OutOfMemoryError](case-studies/android-outofmemoryerror.md) {.tag-android}

  - [案例研究](#)

    - [调试内存使用](case-studies/memory.md) {.tag-android}
    - [调度阻塞](case-studies/scheduling-blockages.md) {.tag-android .tag-linux}

  - [贡献](#)

    - [快速入门](contributing/getting-started.md) {.tag-contrib}
    - [常见任务](contributing/common-tasks.md) {.tag-contrib}

- [深入学习](#)

  - [概念](#)

    - [服务模型](concepts/service-model.md) {.tag-android .tag-linux .tag-cpp}
    - [缓冲区和数据流](concepts/buffers.md) {.tag-android .tag-linux .tag-cpp .tag-chrome}
    - [Trace 配置](concepts/config.md) {.tag-android .tag-linux .tag-cpp .tag-chrome}
    - [时钟同步](concepts/clock-sync.md) {.tag-android .tag-linux .tag-cpp .tag-chrome}
    - [并发 Tracing 会话](concepts/concurrent-tracing-sessions.md) {.tag-android .tag-linux .tag-cpp}

  - [采集](#)

    - [后台 Tracing](learning-more/tracing-in-background.md) {.tag-android .tag-linux}
    - [高级 Android Tracing](learning-more/android.md) {.tag-android}
    - [符号化与反混淆](learning-more/symbolization.md) {.tag-android .tag-linux}
    - [跨重启 Tracing](data-sources/previous-boot-trace.md) {.tag-android .tag-linux}
    - [自定义 Proto Extensions](instrumentation/extensions.md) {.tag-cpp .tag-android .tag-perf}
    - [heapprofd API](instrumentation/heapprofd-api.md) {.tag-cpp}

  - [数据源](#)

    - [系统](#)

      - [CPU 调度](data-sources/cpu-scheduling.md) {.tag-android .tag-linux}
      - [系统调用](data-sources/syscalls.md) {.tag-android .tag-linux}
      - [CPU 调频](data-sources/cpu-freq.md) {.tag-android .tag-linux}
      - [GPU](data-sources/gpu.md) {.tag-android .tag-linux .tag-perf}

    - [内存](#)

      - [内存 Counter](data-sources/memory-counters.md) {.tag-android .tag-linux}
      - [Allocation Profiler](data-sources/native-heap-profiler.md) {.tag-android .tag-linux}
      - [ART Heap Dump](data-sources/java-heap-profiler.md) {.tag-android}

    - [Android](#)

      - [ATrace](data-sources/atrace.md) {.tag-android}
      - [Logcat](data-sources/android-log.md) {.tag-android}
      - [Frame Timeline](data-sources/frametimeline.md) {.tag-android}
      - [电池与功耗](data-sources/battery-counters.md) {.tag-android}
      - [Android Game Interventions](data-sources/android-game-intervention-list.md) {.tag-android}
      - [Android Aflags](data-sources/android-aflags.md) {.tag-android}

  - [Tracing SDK](#)

    - [Tracing SDK](instrumentation/tracing-sdk.md) {.tag-cpp}
    - [Track Event](instrumentation/track-events.md) {.tag-cpp}

  - [可视化](#)

    - [Perfetto UI](visualization/perfetto-ui.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
    - [打开大型 Trace](visualization/large-traces.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
    - [深度链接](visualization/deep-linking-to-perfetto-ui.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
    - [调试 Track](analysis/debug-tracks.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
    - [Heap Dump 浏览器](visualization/heap-dump-explorer.md) {.tag-android}

    - [扩展 UI](#)

      - [概述](visualization/extending-the-ui.md) {.tag-android .tag-linux .tag-cpp .tag-perf}
      - [UI 自动化](visualization/ui-automation.md) {.tag-android .tag-linux .tag-cpp .tag-perf}
      - [命令参考](visualization/commands-automation-reference.md) {.tag-android .tag-linux .tag-cpp .tag-perf}
      - [扩展服务器](visualization/extension-servers.md) {.tag-android .tag-linux .tag-cpp .tag-perf}

  - [Trace 分析](#)

    - [快速入门](analysis/getting-started.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}

    - [PerfettoSQL](#)

      - [快速入门](analysis/perfetto-sql-getting-started.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
      - [语法](analysis/perfetto-sql-syntax.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
      - [标准库](analysis/stdlib-docs.autogen) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
      - [样式指南](analysis/style-guide.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
      - [向后兼容性](analysis/perfetto-sql-backcompat.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}

    - [Trace Processor](#)

      - [C++ 库](analysis/trace-processor.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
      - [Python 库](analysis/trace-processor-python.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
      - [批量 Trace Processor](analysis/batch-trace-processor.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}

    - [Trace 汇总](analysis/trace-summary.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
    - [从 Perfetto 转换](quickstart/traceconv.md) {.tag-android .tag-linux .tag-cpp .tag-chrome}

  - [FAQ](faq.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}

- [深入探索](#)

  - [命令行工具](#)

    - [perfetto](reference/perfetto-cli.md) {.tag-android .tag-linux}
    - [traced](reference/traced.md) {.tag-android .tag-linux}
    - [traced_probes](reference/traced_probes.md) {.tag-android .tag-linux}
    - [heap_profile](reference/heap_profile-cli.md) {.tag-android .tag-linux}
    - [tracebox](reference/tracebox.md) {.tag-android .tag-linux}

  - [参考](#)

    - [Proto](#)

      - [Trace Config](reference/trace-config-proto.autogen) {.tag-android .tag-linux .tag-cpp .tag-chrome}
      - [Trace Packet](reference/trace-packet-proto.autogen) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}

    - [PerfettoSQL](#)

      - [Prelude 表](analysis/sql-tables.autogen) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
      - [内置函数](analysis/builtin.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
      - [Stats 表](analysis/sql-stats.autogen) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}

    - [合成 Track Event](reference/synthetic-track-event.md) {.tag-perf}
    - [内核 Track Event](reference/kernel-track-event.md) {.tag-android .tag-linux}
    - [扩展服务器协议](visualization/extension-server-protocol.md) {.tag-android .tag-linux .tag-cpp .tag-chrome .tag-perf}
    - [Android 版本说明](reference/android-version-notes.md) {.tag-android}

  - [高级主题](#)

    - [分离模式](concepts/detached-mode.md) {.tag-android}
    - [拦截器](instrumentation/interceptors.md) {.tag-cpp}
    - [旧版（v1）指标](analysis/metrics.md) {.tag-android}
    - [BigTrace（单机）](deployment/deploying-bigtrace-on-a-single-machine.md) {.tag-android .tag-perf}
    - [Kubernetes 上的 BigTrace](deployment/deploying-bigtrace-on-kubernetes.md) {.tag-android .tag-perf}

  - [贡献](#)

    - [构建](contributing/build-instructions.md) {.tag-contrib}
    - [测试](contributing/testing.md) {.tag-contrib}
    - [开发者工具](contributing/developer-tools.md) {.tag-contrib}

    - [UI 开发](#)

      - [快速入门](contributing/ui-getting-started.md) {.tag-contrib}
      - [插件](contributing/ui-plugins.md) {.tag-contrib}

    - [发布](#)

      - [SDK 发布](contributing/sdk-releasing.md) {.tag-contrib}
      - [Python 发布](contributing/python-releasing.md) {.tag-contrib}
      - [UI 发布](visualization/perfetto-ui-release-process.md) {.tag-contrib}

    - [成为提交者](contributing/become-a-committer.md) {.tag-contrib}
    - [Chrome 分支](contributing/chrome-branches.md) {.tag-contrib}
    - [SQLite 升级](contributing/sqlite-upgrade-guide.md) {.tag-contrib}

  - [设计文档](#)

    - [核心](#)

      - [API 和 ABI 接口](design-docs/api-and-abi.md) {.tag-contrib}
      - [Tracing 会话的生命周期](design-docs/life-of-a-tracing-session.md) {.tag-contrib}
      - [安全模型](design-docs/security-model.md) {.tag-contrib}
      - [Trace Buffer V2](design-docs/trace-buffer.md) {.tag-contrib}

    - [基础设施](#)

      - [ProtoZero](design-docs/protozero.md) {.tag-contrib}
      - [LockFreeTaskRunner](design-docs/lock-free-task-runner.md) {.tag-contrib}

    - [Trace Processor](#)

      - [架构](design-docs/trace-processor-architecture.md) {.tag-contrib}
      - [批量 Trace Processor](design-docs/batch-trace-processor.md) {.tag-contrib}

    - [UI](#)

      - [数据浏览器架构](design-docs/data-explorer-architecture.md) {.tag-contrib}

    - [Profiling](#)

      - [Heapprofd 设计](design-docs/heapprofd-design.md) {.tag-contrib}
      - [Heapprofd 线路协议](design-docs/heapprofd-wire-protocol.md) {.tag-contrib}
      - [Heapprofd 采样](design-docs/heapprofd-sampling.md) {.tag-contrib}
      - [pprof 支持](design-docs/pprof-support.md) {.tag-contrib}

    - [其他](#)

      - [Statsd Checkpoint Atom](design-docs/checkpoint-atoms.md) {.tag-contrib}
      - [Perfetto CI](design-docs/continuous-integration.md) {.tag-contrib}
