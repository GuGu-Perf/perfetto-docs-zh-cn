# GPU

![](/docs/images/gpu-counters.png)

## GPU 频率

可以通过添加 ftrace 类别将 GPU 频率包含在 trace 中。

```
data_sources: {
 config {
 name: "linux.ftrace"
 ftrace_config {
 ftrace_events: "power/gpu_frequency"
 }
 }
}
```

## GPU 计数器

可以通过将数据源添加到 trace 配置来配置 GPU Counters，如下所示：

```
data_sources: {
 config {
 name: "gpu.counters"
 gpu_counter_config {
 counter_period_ns: 1000000
 counter_ids: 1
 counter_ids: 3
 counter_ids: 106
 counter_ids: 107
 counter_ids: 109
 }
 }
}
```

counter_ids 对应于数据源描述符中 `GpuCounterSpec` 中描述的那些。

有关完整的配置选项，请参见 [gpu\_counter\_config.proto](/protos/perfetto/config/gpu/gpu_counter_config.proto)
