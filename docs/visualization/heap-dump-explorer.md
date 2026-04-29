# Heap Dump Explorer

Heap Dump Explorer 是 Perfetto UI 中用于分析 Android Java heap dump 的页面。对于每个可达对象，它显示类、浅大小和保留大小，以及从 GC root 到该对象的引用路径——因此你可以回答堆中有什么、是什么让每个对象存活、以及每个对象保留了多少内存。

本指南涵盖：

- [Heap dump 与 Heap Profile 的对比](#heap-dumps-vs-heap-profiles)以及何时使用哪个。
- [采集 Heap Dump](#capturing-a-heap-dump)，包括轻量级的 Perfetto heap graph 和更完整的 ART HPROF 格式。
- 如何使用 Explorer 的每个标签页，从[检查单个对象](#inspecting-a-single-object)开始——大多数调查最终都会到达的视图。
- 实践[案例研究](#case-studies)：泄漏的 `Activity` 和重复的 Bitmap。

## Heap dump 与 Heap Profile 的对比

<!-- TODO(zezeozue): Move this explanation into the memory guide
     (docs/case-studies/memory.md or docs/getting-started/memory-profiling.md)
     and cross-link from here instead of duplicating. -->

- **Java Heap Profile** 采样_随时间变化的分配_，以调用栈的火焰图呈现。它回答的是在采集 trace 期间哪些代码路径正在分配内存。参见 [Java heap sampler](/docs/data-sources/native-heap-profiler.md#java-heap-sampling)。

- **Java Heap Dump** 是_某一时间点堆的快照_。它采集每个可达对象、对象之间的引用、GC root，以及——取决于格式——字段值、字符串、原始数组字节和 Bitmap 像素缓冲区。

Heap Dump Explorer 用于 dump。如果你需要分配调用路径分析，请改用 Heap Profile。

### Heap Dump 适合的场景

- **内存泄漏。** 一个不应该可达的对象却是可达的。从 GC root 出发的引用路径指向持有者——通常是静态字段、缓存的 Listener 或向已销毁的 Context 发送消息的 `Handler`。
- **保留大小意外。** 一个对象本身很小，但通过其引用保留了许多兆字节。支配者树和 _Immediately dominated objects_ 部分准确显示它持有什么。
- **重复内容。** 同一 Bitmap、字符串或原始数组的多个副本。Overview 按内容哈希对它们分组，并显示浪费的字节数。
- **Bitmap 统计。** 哪些 Bitmap 是存活的、它们有多大以及是什么持有它们。
- **类分解。** 哪些类拥有最大份额的保留内存。

### Heap Dump 不适合的场景

- **分配调用路径。** Heap Dump 是快照，不是录制——它不会告诉你_是哪段代码_分配了一个对象。请使用 [Java Heap Profile](/docs/data-sources/native-heap-profiler.md#java-heap-sampling)。
- **纯 Native 内存。** Dump 覆盖的是 Java 堆。对于 native 分配，请使用 [native heap profiler](/docs/data-sources/native-heap-profiler.md)。
- **时间和性能。** Heap Dump 不涉及对象创建时间或操作耗时。

## 采集 Heap Dump

支持两种格式。

### Perfetto Heap Graph（轻量级）

采集对象图——类、引用、大小、GC root——但不包括字段值、字符串、原始数组字节或 Bitmap 像素。足以进行保留、支配者和类分解分析。

**优点：**

- 隐私安全——没有字符串值、像素缓冲区或字段内容离开设备，因此可以在不泄漏敏感数据的情况下从真实用户采集。
- 不需要 `debuggable` 进程。
- 与其他 Perfetto 工具集成：你可以在单个 trace 中同时采集 heap graph、Heap Profile、内存 Counter 和其他 DataSource。

**缺点：**

- 没有基于内容的分析——Strings、Arrays 和 Bitmaps 标签页以及 Overview 上的重复内容检测不可用。

对于泄漏调查、支配者分析和类分解选择此格式，特别是在从不可调试的生产构建采集时。

```bash
$ tools/java_heap_dump -n com.example.app -o heap.pftrace

Dumping Java Heap.
Wrote profile to heap.pftrace
```

使用 `--wait-for-oom` 在 `OutOfMemoryError` 时触发，或使用 `-c <interval_ms>` 进行连续 dump。完整配置参见 [Java heap dumps](/docs/data-sources/java-heap-profiler.md)，OOM 触发变体参见 [OutOfMemoryError heap dumps](/docs/case-studies/android-outofmemoryerror.md)。

### ART HPROF（完整详情）

包含 heap graph 的一切，外加字段值、原始数组内容、字符串值和 Bitmap 像素缓冲区。Strings、Arrays 和 Bitmaps 标签页以及 Overview 标签页上的重复内容检测需要此格式。

**优点：**

- 完整可见性——字段值、字符串内容、Bitmap 像素和原始数组字节全部可用。
- 启用重复内容检测和 Bitmaps 画廊。
- HPROF 格式也可被 Android Studio 等其他工具识别。

**缺点：**

- 采集速度慢得多，会使目标进程冻结数秒（Perfetto 在 fork 的副本上工作，因此主进程不受影响）。
- 产生更大的文件。
- 包含堆的完整内容，因此不适合从真实用户采集——它将包含内存中的任何敏感数据。
- 需要 `debuggable` 进程。

当你需要内容级别的细节时选择此格式：追踪重复 Bitmap、检查字符串值或导出到其他工具。

```bash
$ adb shell am dumpheap -g -b png com.example.app /data/local/tmp/heap.hprof
$ adb pull /data/local/tmp/heap.hprof

File: /data/local/tmp/heap.hprof
```

`-b` 将 Bitmap 像素缓冲区编码为指定格式（`png`、`jpg` 或 `webp`），Bitmaps 画廊渲染像素需要此选项。`-g` 在 dump 前强制 GC，因此不可达的实例不会出现在结果中——在追踪疑似泄漏时使用它。目标进程必须是 `debuggable` 的（`userdebug`/`eng` 构建，或 APK 设置了 `android:debuggable="true"`）。

NOTE: 下面标记为 _requires HPROF_ 的部分在使用 heap graph 格式采集的 trace 上是隐藏的。

将生成的 trace 拖放到 [ui.perfetto.dev](https://ui.perfetto.dev) 或在侧边栏点击 _"Open trace file"_ 来打开。

## 打开 Explorer

有两个入口：

1. **侧边栏。** 在当前 trace 下点击 _"Heapdump Explorer"_。此条目仅在 trace 包含 heap dump 时出现。

   ![Perfetto UI 加载了 heap dump；侧边栏在"Current Trace"下显示"Heapdump Explorer"。](/docs/images/heap_docs/01-sidebar.png)

2. **从 Heap Graph 火焰图。** 在 _"Heap Profile"_ Track 上点击菱形图标打开 heap graph 火焰图，点击节点选中它，然后点击节点详情弹出窗口中的菜单图标，选择 _"Open in Heapdump Explorer"_。这在[从火焰图跳转](#jumping-from-a-flamegraph)中详细介绍。

   ![Heap graph 火焰图，`java.lang.String` 节点被选中；详情弹出窗口列出其 Cumulative size、Root Type 和 Self Count，溢出菜单已打开并显示"Open in Heapdump Explorer"。](/docs/images/heap_docs/02-flamegraph-menu.png)

Explorer 顶部以标签页形式组织。_Overview_、_Classes_、_Objects_、_Dominators_、_Bitmaps_、_Strings_ 和 _Arrays_ 是固定的。通过钻取特定对象或火焰图选择打开的标签页会附加在右侧，可以关闭。

![标签栏显示七个固定标签页和一个为 `ProfileActivity 0x00032f52` 打开的动态对象标签页。](/docs/images/heap_docs/03-tab-bar.png)

所有标签页共享底层的 `heap_graph_*` 表。蓝色链接——类名、对象 id、_Copies_ 计数——导航到相应标签页并预过滤。

## Overview

NOTE: 重复部分 _requires HPROF_。

Overview 是默认着陆页，汇总 dump 信息：

- **常规信息。** 可达实例数和 dump 中的堆列表（通常是 `app`、`zygote`、`image`）。
- **按堆保留的字节数。** 每个堆的 Java、native 和总大小，顶部有总计行。使用此信息查看问题是在 Java 堆上、native 内存中还是两者都有。
- **重复的 Bitmap / 字符串 / 原始数组。** 按内容哈希分组的重复内容。每行显示副本数量和浪费的字节数；点击 _Copies_ 打开相关标签页并按该组过滤。

![Overview 标签页：General Information（跨 app/image/zygote 堆的 437,681 个可达实例），Bytes Retained by Heap（总计 24.4 MiB，app 堆上 1.5 MiB），以及一个重复 Bitmap 组，同一 128×128 图像的 12 个副本浪费 785.8 KiB。](/docs/images/heap_docs/04-overview.png)

## Classes

Classes 标签页列出 dump 中的每个类，按 _Retained_ 降序排列：

- **Count**——可达实例。
- **Shallow / Shallow Native**——所有实例的自大小合计。
- **Retained / Retained Native**——如果每个实例变为不可达将释放的字节数。
- **Retained #**——将随之释放的对象数。

![Classes 标签页按 Retained 排序；`byte[]` 和 `java.lang.String` 在顶部，`com.heapleak.ProfileActivity` 较下方 Count 为 1。](/docs/images/heap_docs/05-classes.png)

当你有可疑的类，或想要自上而下查看哪些类拥有最多内存时，使用此标签页。点击类名打开按该类过滤的 Objects。

## Objects

Objects 标签页列出可达实例。从 Classes 或重复组打开会自动应用过滤器；直接打开则显示所有对象。

每行有对象标识符（短类名 + 十六进制 id）、其类、浅大小和保留大小，以及其所在堆。`java.lang.String` 行带有值预览徽章，可以一目了然地扫描字符串。

![Objects 标签页过滤到 `java.lang.String`；437,681 个中的 106,474 个实例，按保留字节数排序。](/docs/images/heap_docs/06-objects-string.png)

点击对象打开其[对象标签页](#inspecting-a-single-object)。典型用途：识别泄漏后的过期 `Activity`，或持有最大子图的数据类实例。

## 检查单个对象

**_Shortest Path from GC Root_、_Dominator Tree Path_ 和 _Objects with References to this Object_ 是大多数调查的关键部分。** 最短路径显示保持对象存活的最少引用跳数；支配者树路径显示独占保留它的对象链；反向引用列出每个持有指向它的字段指针的对象。

点击任何标签页中的任何对象都会为该实例打开一个可关闭的标签页。多个对象标签页可以同时打开。

对象标签页包含关于该实例的所有已知信息：

- **标题**带有对象 id，以及当对象本身是 `Class` 时的 _Open in Classes_ 快捷方式。
- **Bitmap 预览**（对于 Bitmap 实例），带有下载按钮。
- **Shortest Path from GC Root**——从 GC root 到此对象的最短引用链。
- **Dominator Tree Path**——保持此对象存活的支配者链，每行一步，显示持有者和字段名。
- **Object info**——类、堆、root 类型。
- **Object size**——按 Java / native / 计数细分的浅大小、保留大小和可达大小。
- **Class hierarchy**——直到 `java.lang.Object` 的完整继承链，加上类对象的实例大小。点击任何类打开按该类及其子类过滤的 **Classes**。
- **Static fields**（类对象）、**instance fields**（普通对象）或 **array elements**（数组）。引用值可点击并跳转到被引用对象。对于 byte 数组，_Download bytes_ 导出原始数据。
- **Objects with references to this object**——反向引用。每个具有指向此对象字段的实例。
- **Immediately dominated objects**——如果此实例变为不可达将释放什么。

![`ProfileActivity 0x0004f1ae` 的对象标签页（顶部）：Sample Path from GC Root 为 `Class<ProfileActivity> → com.heapleak.ProfileActivity.history → ArrayList → Object[0] → ProfileActivity`；保留 117.6 KiB，跨 1,604 个对象。](/docs/images/heap_docs/12-object-tab-top.png)

![对象标签页（底部）：来自 `android.app.Activity` 的实例字段，"Objects with References to this Object"（来自视图和 Context 包装器的反向引用），以及"Immediately Dominated Objects"——如果此实例变为不可达将释放的视图层次结构。](/docs/images/heap_docs/13-object-tab-bottom.png)

两个部分在大对象上自动折叠——点击标题展开。

## Dominators

Dominators 标签页显示堆的[支配者树](https://en.wikipedia.org/wiki/Dominator_(graph_theory))。在有向图中，节点 `a` _支配_ 节点 `b` 当从 root 到 `b` 的每条路径都必须经过 `a`。应用于堆：如果你释放 `a`，它支配的一切——每个_仅_通过 `a` 可达的对象——也会被释放。支配者树将堆分组为这些"一起释放"的子树，使你容易看到哪些单个对象控制着最大的保留内存块。

![Dominators 标签页按 Retained 排序；`Class<ProfileActivity>`（root 类型 `STATIC`）和一个 `ProfileActivity` 实例靠近顶部，各自保留一个大型子图。](/docs/images/heap_docs/07-dominators.png)

_Root Type_（例如 `THREAD`、`STATIC`、`JNI_GLOBAL`）标识每个支配者本身是如何被保持存活的。点击行打开其对象标签页并遍历引用路径。

当没有特定的可疑对象，问题仅仅是内存去了哪里时，使用此标签页。

## Bitmaps

NOTE: 像素预览和重复检测 _requires HPROF_。

Bitmaps 标签页是 dump 中每个 `android.graphics.Bitmap` 的画廊。使用 HPROF 时，每个 Bitmap 的像素会内联渲染。

![Bitmaps 画廊：15 个 Bitmap，971.2 KiB 保留。同一图像的 12 个 128×128 副本内联渲染，每个 64.2 KiB。](/docs/images/heap_docs/08-bitmaps-gallery.png)

每张卡片显示渲染的像素、尺寸（px 和 dp）、DPI、保留内存和打开对象标签页的 _Details_ 按钮。像素缓冲区可能是 RGBA、PNG、JPEG 或 WebP，取决于它们的存储方式。

画廊上方的路径下拉菜单选择要在每张卡片上覆盖的引用路径：_Shortest path_（从 GC root 的最少边数）、_Dominator path_（支配者链）或 _No path_。显示路径是发现持有泄漏 Bitmap 的 `Activity`、`Fragment` 或 `Handler` 的最快方式。

![启用了"Show Paths"的 Bitmaps 画廊；每张卡片下方的引用链为 `Class<FeedAdapter>.cache → ArrayList → Bitmap`，显示唯一的静态持有者。](/docs/images/heap_docs/09-bitmaps-show-paths.png)

底部的两个表列出有和没有像素数据的 Bitmap，带有过滤器、排序和导出控件。通过 Overview 上的 _Copies_ 到达会按缓冲区内容哈希预过滤标签页，只留下该组中视觉上相同的 Bitmap。

## Strings

NOTE: Strings 标签页 _requires HPROF_。

Strings 标签页列出每个 `java.lang.String` 及其值。摘要卡片报告字符串总数、不同值的数量和总保留内存。总数和不同值之间的差距是花在重复上的内存。

![Strings 标签页：105,868 个总字符串，71,176 个唯一，4.9 MiB 保留。总数和不同值之间的差距（约 30k 重复）是花在重复值上的内存。](/docs/images/heap_docs/10-strings.png)

按值过滤以查找预期唯一的数据：用户 id、序列化的配置负载、重复数千次的错误消息。点击行打开其对象标签页，反向引用部分列出持有该字符串的每个对象。

## Arrays

NOTE: Arrays 标签页 _requires HPROF_。

Arrays 标签页列出原始数组（`byte[]`、`int[]`、`long[]`、...）及其稳定的内容哈希。按 _Content Hash_ 过滤返回具有相同字节的每个数组；这是 Overview 检测重复数组的方式。

![Arrays 标签页按 Shallow 排序，Content Hash 列可见；按哈希过滤返回共享相同字节的每个数组。](/docs/images/heap_docs/11-arrays.png)

两个常见用途：找到支持图像或序列化缓冲区的大型重复 `byte[]`，以及从容器对象跳转到持有其数据的原始数组。

## 从火焰图跳转

Heap graph 火焰图有一个 _Open in Heapdump Explorer_ 操作，可以在匹配选定分配路径的对象列表上打开 Explorer。使用它逐对象检查火焰图节点：

1. 在 _"Heap Profile"_ Track 上点击菱形图标打开火焰图。

   ![顶部 Timeline，点击进程 Track 上的 heap dump 菱形后底部面板中的 heap graph 火焰图。](/docs/images/heap_docs/14-flamegraph-bottom-panel.png)

2. 点击节点选中它，然后点击节点详情弹出窗口中的菜单图标。选择 _"Open in Heapdump Explorer"_。

   ![火焰图，`java.lang.String` 被选中。其详情弹出窗口列出 Cumulative size（2.48 MiB, 10.48%）、Root Type（`ROOT_INTERNED_STRING`）、Heap Type 和 Self Count（53,546）。弹出窗口的溢出菜单已打开，"Open in Heapdump Explorer"在"Copy Stack"和"Copy Stack With Details"下方可见。](/docs/images/heap_docs/02-flamegraph-menu.png)

   这会打开一个新的可关闭的 _Flamegraph Objects_ 标签页，列出沿选定路径分配的每个对象。支配者火焰图节点产生基于支配者的选择；常规节点产生基于路径的选择。

   ![在 `java.lang.String` 上选择"Open in Heapdump Explorer"后打开的 Flamegraph Objects 标签页：53,546 行，每行有类、浅/保留大小和堆。标签页附加在固定七标签栏的右侧，右上角有"Back to Timeline"链接。](/docs/images/heap_docs/15-flamegraph-objects-tab.png)

3. 从那里，点击任何对象打开其[对象标签页](#inspecting-a-single-object)，或使用 _Back to Timeline_ 返回火焰图视图。

多个火焰图选择可以同时打开，每个作为自己的标签页——对于并排比较两个调用栈很有用。

## 案例研究

<!-- TODO(zezeozue): Break these case studies out and integrate them into
     the existing memory guides (docs/case-studies/memory.md). Rationalize
     the material so it isn't duplicated across docs. -->

### 查找泄漏的 Activity

一个 Kotlin 应用的开发者报告，旋转个人资料屏幕几次后 Java 堆持续上升且不会回落。这个屏幕很普通——一个 `Activity`、一个视图层次结构、一个头像——旋转_应该_销毁旧实例。但它没有。

快速 grep 发现了一个团队之前为崩溃报告添加的"面包屑"列表。它存储了每个创建的 `ProfileActivity` 实例，并且从未清除：

```kotlin
class ProfileActivity : Activity() {
    companion object {
        val history = mutableListOf<ProfileActivity>()   // never cleared
    }

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        setContentView(R.layout.profile)
        history += this                                   // <-- the bug
    }
}
```

初衷是为崩溃报告保留最近屏幕的轻量轨迹。它实际上做的是固定了每个创建过的 `ProfileActivity`：`onDestroy` 在旧实例上运行，但类的静态 `history` 列表保持着强引用——连同旧 Activity 的整个视图层次结构。

**采集。** Heap graph 格式足以追踪 Activity 泄漏；它承载完整的对象图和 GC root：

```bash
$ tools/java_heap_dump -n com.example.app -o /tmp/profile.pftrace

Dumping Java Heap.
Wrote profile to /tmp/profile.pftrace
```

先旋转设备几次以积累多个实例。将文件拖放到 [ui.perfetto.dev](https://ui.perfetto.dev) 并在侧边栏点击 _Heapdump Explorer_。

**确认泄漏。** 打开 **Classes** 并找到 `com.heapleak.ProfileActivity`。用户导航离开后 `Count` 应该为 0；这里是 5，每次旋转一个：

![Classes 标签页。com.heapleak.ProfileActivity 的 Count 为 5——每次旋转一个实例，没有被回收。](/docs/images/heap_docs/05-classes.png)

点击类名打开过滤到 `ProfileActivity` 的 **Objects**。每行是一个存活实例：

![Objects 标签页过滤到 com.heapleak.ProfileActivity：五个实例，每个保留约 116.6 KiB 和 1,566 个可达对象。](/docs/images/heap_docs/12a-objects-profile-activity.png)

**阅读引用路径。** 点击顶部行打开其对象标签页。_Sample Path from GC Root_ 是保持此实例存活的字段引用链：

![泄漏 ProfileActivity 的对象标签页。Sample Path from GC Root：Class<ProfileActivity> → com.heapleak.ProfileActivity.history → ArrayList.elementData → Object[0] → ProfileActivity。保留 117.6 KiB，约 1,600 个可达对象。](/docs/images/heap_docs/12-object-tab-top.png)

从下往上读：运行时保持 `java.lang.Class<ProfileActivity>` 存活（就像每个已加载的类一样）；该类有一个 companion-object 字段 `history`；该字段指向一个 `ArrayList`，其元素 0 是这个 `ProfileActivity`。从类对象到 `history` 的跳转点出了 bug——一个 Activity 的静态列表。

_Object Size_ 块量化了代价：一个泄漏的 Activity 固定了 117.6&nbsp;KiB 和约 1,600 个可达对象。乘以五（`Count`），泄漏已经是堆中约 600&nbsp;KiB 的 Activity 图。同一标签页更下方是 _Objects with References to this Object_ 和 _Immediately Dominated Objects_ 部分：

![对象标签页底部。来自 android.app.Activity 的实例字段，"Objects with References to this Object"和"Immediately Dominated Objects"。](/docs/images/heap_docs/13-object-tab-bottom.png)

展开 _Immediately Dominated Objects_ 显示随泄漏一起释放的所有内容——`Activity` 的视图层次结构和它传递保留的其余状态。这些都不应该比 Activity 活得更久；但它们都活着，因为一个 companion-object 列表持有 root。

**修复。** 永远不要在 `static` 或 companion-object 容器中存储 `Activity`。如果你想要崩溃报告的面包屑轨迹，请改为存储有界容量的字符串：

```kotlin
object Breadcrumbs {
    private const val CAPACITY = 16
    private val trail = ArrayDeque<String>(CAPACITY)

    @Synchronized
    fun record(event: String) {
        while (trail.size >= CAPACITY) trail.removeFirst()
        trail.addLast("${System.currentTimeMillis()} $event")
    }
}

class ProfileActivity : Activity() {
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        setContentView(R.layout.profile)
        Breadcrumbs.record("ProfileActivity.onCreate")
    }
}
```

重新运行相同的复现步骤并重新 dump。Classes 标签页现在只显示一个 `ProfileActivity`——当前可见的屏幕——而不是每次旋转一个。

这个小演示节省了约 1.5&nbsp;MiB 的 app 堆；具有活跃视图层次结构的真实屏幕会看到数十兆字节的差异。在用户导航离开后采集的 dump 中任何 `Count > 0` 的 `Activity` 子类都是泄漏。

同样的方法可以找到其他常见的 Activity 泄漏形式——延迟消息 `Handler`、未注册的 Listener、超出其作用域的协程。引用路径中 Activity 之前的最后一跳总是指向持有者；修复是在正确的生命周期回调中清除该字段。

### 追踪重复 Bitmap

一个 Kotlin 信息流应用在长时间滚动时内存不足。`dumpsys meminfo com.example.feed` 报告的 `Graphics:` 行比屏幕上实际像素大好几倍，而应用内图片缓存看起来很小。有其他东西在持有像素。

嫌疑对象原来是一个 `RecyclerView` adapter，它在每次绑定时从资源解码每行的缩略图，并将结果附加到 companion-object 列表：

```kotlin
class FeedAdapter(private val res: Resources) : RecyclerView.Adapter<VH>() {
    companion object {
        val cache = mutableListOf<Bitmap>()     // grows without bound
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val bmp = BitmapFactory.decodeResource(res, R.drawable.thumb)
        cache += bmp                            // "cache" — actually just accumulates
        holder.image.setImageBitmap(bmp)
    }
    // ...
}
```

每次绑定都解码同一 PNG 的新副本。每个副本然后被 `cache` 永久持有。像素都哈希到相同的值，但它们是不同的 `Bitmap` 实例，具有不同的后备 `byte[]`。

**采集。** 重复检测需要每个 Bitmap 像素缓冲区的哈希，只有 HPROF 格式才携带。`-b png` 编码像素以便 Bitmaps 画廊渲染预览：

```bash
$ adb shell am dumpheap -g -b png com.example.feed /data/local/tmp/feed.hprof
$ adb pull /data/local/tmp/feed.hprof
```

在 dump 前滚动信息流足够长时间以复现膨胀——adapter 的 `cache` 仅在绑定时增长。

**在 Overview 上分诊。** Overview 按像素缓冲区哈希对 Bitmap 分组。每行显示副本数、所有副本的总字节数和浪费的字节数——去重到单个副本将节省多少：

![Overview 标签页。Duplicate Bitmaps 卡片有一个 128×128 组：12 个副本，770.0 KiB 总计，785.8 KiB 浪费——正是 adapter 缓存列表的形状。](/docs/images/heap_docs/04-overview.png)

该行显示积累的内容：一个 128×128 资产的 12 个副本，都具有相同的内容哈希。下面的 _Duplicate Strings_ 和 _Duplicate Primitive Arrays_ 卡片工作方式相同——相同的分组、相同的大小计算——当浪费的内存是文本（例如重复数千次的配置负载）或原始缓冲区时很有用。所有三个重复检测器都需要 HPROF，因为它们哈希实际内容，而 heap graph 格式不携带这些内容。

**钻入副本。** 点击该行的 _Copies_。**Bitmaps** 打开并预过滤到该内容哈希组，因此只有那些副本渲染为卡片：

![过滤到 128×128 组的 Bitmaps 画廊。12 个副本每个 64.2 KiB，标签页中共 971.2 KiB 保留。](/docs/images/heap_docs/08-bitmaps-gallery.png)

**找到持有者。** 将路径下拉菜单设置为 _Shortest path_。每张卡片下方的引用链是保持该 Bitmap 存活的字段：

![启用了 Show Paths 的 Bitmaps 画廊。每张卡片的链为 Class&lt;FeedAdapter&gt;.cache → ArrayList → Bitmap——companion-object 列表是唯一的持有者。](/docs/images/heap_docs/09-bitmaps-show-paths.png)

画廊中的每条链都是相同的：`Class<FeedAdapter>.cache → ArrayList → Bitmap`。所有 12 个副本共享一个持有者——一个缓存层的 bug，一个需要修复的字段。

链的形状就是诊断。在未来的调查中要注意的另外两种模式：

- _每个副本有不同的链_→调用点 bug。没有缓存，或者调用者绕过了它。
- _链经过一个 `Activity`_→先修复 Activity 泄漏（[上一个案例研究](#finding-a-leaked-activity)）；Bitmap 会随之释放。

**修复。** 完全没有理由保留 `Bitmap` 的旁路列表——Android 已经有 `LruCache<K, Bitmap>`，作用域限定到应用，具有你控制的淘汰策略：

```kotlin
class FeedAdapter(private val res: Resources) : RecyclerView.Adapter<VH>() {
    companion object {
        private val cache = object : LruCache<Int, Bitmap>(4) {
            override fun sizeOf(key: Int, value: Bitmap) = 1
        }
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val key = R.drawable.thumb
        val bmp = cache[key] ?: BitmapFactory.decodeResource(res, key).also { cache.put(key, it) }
        holder.image.setImageBitmap(bmp)
    }
    // ...
}
```

**验证。** 滚动信息流相同距离，重新 dump，重新打开。Overview 应该显示 `No duplicate bitmaps found`，app 堆保留字节数应相应下降：

![修复后 trace 的 Overview 标签页。Duplicate Bitmaps 卡片现在显示"No duplicate bitmaps found"，app 堆保留内存从 2.1 MiB 降至 580.2 KiB。](/docs/images/heap_docs/16-fixed-overview.png)

Overview 上所有组的 _wasted bytes_ 总计是最清晰的单数字记分卡——观察它从一次 dump 到下一次 dump 下降，就是你确认每个修复和捕获回归的方式。

## 另见

- [Java heap dumps](/docs/data-sources/java-heap-profiler.md)——采集配置、故障排除和 SQL schema 参考。
- [Memory 案例研究](/docs/case-studies/memory.md)——调查 Android 内存问题的端到端指南，涵盖 `dumpsys meminfo`、native Heap Profile 和 Java Heap Dump。
- [OutOfMemoryError heap dumps](/docs/case-studies/android-outofmemoryerror.md)——在 OOM 时自动采集 Heap Dump。
- [Native heap profiler](/docs/data-sources/native-heap-profiler.md)——用于分配调用路径分析而非堆内容。
