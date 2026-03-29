# 内存：Java 堆转储

NOTE: 捕获 Java 堆转储需要 Android 11 或更高版本

有关 Java 堆转储的入门，请参见 [内存指南](/docs/case-studies/memory.md#java-hprof)。

与 [Native heap Profiling](native-heap-profiler.md) 相反，Java 堆转储报告托管对象的完整保留图但不报告调用堆栈。在 Java 堆转储中记录的信息的形式为：_对象 X 通过其名为 Z 的类成员保留对象 Y，该对象 Y 大小为 N 字节_。

Java 堆转储不得与 [Java 堆采样器](native-heap-profiler.md#java-heap-sampling) 采集的 Profiling 混淆。

## UI

在单击进程的 _"Heap Profile"_ track 中的菱形后，堆图转储在 UI 中显示为火焰图。每个菱形对应一个堆转储。

![进程 track 中的 Java 堆转储](/docs/images/profile-diamond.png)

![Java 堆转储的火焰图](/docs/images/java-heap-graph.png)

某些对象的 native 大小在火焰图中表示为额外的子节点，前缀为 "[native]"。额外节点算作一个额外对象。这仅在 Android 13 或更高版本上可用。

## SQL

有关 Java 堆的信息写入以下表：

- [`heap_graph_class`](/docs/analysis/sql-tables.autogen#heap_graph_class)
- [`heap_graph_object`](/docs/analysis/sql-tables.autogen#heap_graph_object)
- [`heap_graph_reference`](/docs/analysis/sql-tables.autogen#heap_graph_reference)

`native_size`（仅在 Android T+ 上可用）从相关的 `libcore.util.NativeAllocationRegistry` 提取，不包括在 `self_size` 中。

例如，要获取类名使用的字节，请运行以下查询。按原样，此查询通常会返回不可操作的信息，因为 Java 堆中的大多数字节最终都是基本类型数组或字符串。

```sql
select c.name, sum(o.self_size)
 from heap_graph_object o join heap_graph_class c on (o.type_id = c.id)
 where reachable = 1 group by 1 order by 2 desc;
```

|name |sum(o.self_size) |
|--------------------|--------------------|
|java.lang.String | 2770504|
|long[] | 1500048|
|int[] | 1181164|
|java.lang.Object[] | 624812|
|char[] | 357720|
|byte[] | 350423|

使用标准库，我们可以查询将图规范化为树，始终采用到根的最短路径并获取累积大小。从中我们可以看到每种类型的对象持有多少内存

```sql
INCLUDE PERFETTO MODULE android.memory.heap_graph.class_summary_tree;

SELECT
 -- 类的名称。
 name,
 -- 此节点的 `self_size` 及其后代的所有节点的总和。
 cumulative_size
FROM android_heap_graph_class_summary_tree;
```

| name | cumulative_size |
|------|-----------------|
|java.lang.String|1431688|
|java.lang.Class<android.icu.text.Transliterator>|1120227|
|android.icu.text.TransliteratorRegistry|1119600|
|com.android.systemui.statusbar.phone.StatusBarNotificationPresenter$2|1086209|
|com.android.systemui.statusbar.phone.StatusBarNotificationPresenter|1085593|
|java.util.Collections$SynchronizedMap|1063376|
|java.util.HashMap|1063292|

## TraceConfig

Java 堆转储数据源通过 trace 配置的 [JavaHprofConfig](/docs/reference/trace-config-proto.autogen#JavaHprofConfig) 部分进行配置。

```protobuf
data_sources {
 config {
 name: "android.java_hprof"
 java_hprof_config {
 process_cmdline: "com.google.android.inputmethod.latin"
 dump_smaps: true
 }
 }
}
```
