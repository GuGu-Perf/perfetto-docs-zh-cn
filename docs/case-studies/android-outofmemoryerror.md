# 在 Android 上获取 OutOfMemoryError 堆转储

从 Android 14 (U) 开始，可以配置 Perfetto 在任何 Java (ART) 进程因 java.lang.OutOfMemoryError 崩溃时收集堆转储。

## 步骤

你可以使用 `tools/java_heap_dump` 工具并传递
`--wait-for-oom` 参数来配置收集。

或者，一个快速的方法(除了 adb 访问外不需要任何依赖):

```bash
cat << EOF | adb shell perfetto -c - --txt -o /data/misc/perfetto-traces/oome.pftrace
buffers: {
 size_kb: 512288
 fill_policy: DISCARD
}

data_sources: {
 config {
 name: "android.java_hprof.oom"
 java_hprof_config {
 process_cmdline: "*"
 }
 }
}

data_source_stop_timeout_ms: 100000

trigger_config {
 trigger_mode: START_TRACING
 trigger_timeout_ms: 3600000
 triggers {
 name: "com.android.telemetry.art-outofmemory"
 stop_delay_ms: 500
 }
}
data_sources {
 config {
 name: "android.packages_list"
 }
}
EOF
```

这将启动一个 perfetto tracing 会话一个小时（trigger_timeout_ms）,
等待任何运行时实例遇到 OutOfMemoryError。一旦捕获到错误，tracing 将停止：

```text
[862.335] perfetto_cmd.cc:1047 Connected to the Perfetto traced service, TTL: 3601s
[871.335] perfetto_cmd.cc:1210 Wrote 19487866 bytes into /data/misc/perfetto-traces/oome.pftrace
```

然后你可以通过运行
`adb pull /data/misc/perfetto-traces/oome.pftrace` 下载堆转储。
