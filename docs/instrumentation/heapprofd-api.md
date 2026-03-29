# heapprofd Custom Allocator API - Early Access

WARNING: heapprofd Custom Allocator API 目前处于 **beta** 阶段。
 如遇到任何问题，请提交 [bug](https://github.com/google/perfetto/issues/new)。

NOTE: heapprofd Custom Allocator API 需要运行 Android 10 或更高版本的设备。

## 获取 SDK

在为你的应用程序进行插桩之前，你需要获取 heapprofd 库和头文件。

### 选项 1：预构建版本

你可以从 [Google Drive](
https://drive.google.com/drive/folders/15RPlGgAHWRSk7KquBqlQ7fsCaXnNaa6r
) 下载库的二进制文件。
加入我们的 [Google Group](https://groups.google.com/forum/#!forum/perfetto-dev) 以获取访问权限。

### 选项 2：自己构建（在 Linux 上）

或者，你可以从 AOSP 自己构建二进制文件。

首先，[检出 Perfetto](https://perfetto.dev/docs/contributing/build-instructions)：

```
$ git clone https://github.com/google/perfetto.git
```

然后，切换到项目目录，下载并构建额外的依赖项，然后构建独立库：

```
$ cd perfetto
perfetto/ $ tools/install-build-deps --android
perfetto/ $ tools/setup_all_configs.py --android
perfetto/ $ ninja -C out/android_release_incl_heapprofd_arm64 \
libheapprofd_standalone_client.so
```

你将在 `out/android_release_incl_heapprofd_arm64/libheapprofd_standalone_client.so` 中找到构建的库。
API 的头文件可以在 `src/profiling/memory/include/perfetto/heap_profile.h` 中找到。
此库是针对 SDK 版本 29 构建的，因此将在 Android 10 或更高版本上运行。

WARNING: 仅使用你用于构建库的 checkout 中的头文件，
 因为 API 尚不稳定。

为了使未来的调试更容易，请记下你构建时的修订版本。

```
git rev-parse HEAD > perfetto-version.txt
```
请在你提交的任何 bug 中包含此内容。

## 为应用程序插桩

假设你的应用程序有一个非常简单的自定义分配器，如下所示：

```
void* my_malloc(size_t size) {
 void* ptr = [代码以某种方式分配 size 字节];
 return ptr;
}

void my_free(void* ptr) {
 [代码以某种方式释放 ptr]
}
```

要找出程序中这两个函数在何处被调用，我们使用此 API 为分配器进行插桩：

```
#include "path/to/heap_profile.h"

static uint32_t g_heap_id = AHeapProfile_registerHeap(
 AHeapInfo_create("invalid.example"));
void* my_malloc(size_t size) {
 void* ptr = [代码以某种方式分配 size 字节];
 AHeapProfile_reportAllocation(g_heap_id, static_cast<uintptr_t>(ptr), size);
 return ptr;
}

void my_free(void* ptr) {
 AHeapProfile_reportFree(g_heap_id, static_cast<uintptr_t>(ptr));
 [代码以某种方式释放 ptr]
}
```

不要忘记链接 `heapprofd_standalone_client.so` 并将其包含在你的应用程序中。

## 为应用程序分析

然后，使用 [heap_profile](
https://raw.githubusercontent.com/google/perfetto/main/tools/heap_profile)
脚本来获取 profile 以生成配置的 textpb。要转换为二进制 proto，你还需要下载
[`perfetto_trace.proto`](
https://raw.githubusercontent.com/google/perfetto/main/protos/perfetto/trace/perfetto_trace.proto)
并安装最新版本的 protoc 编译器。
[了解如何安装 protoc](https://grpc.io/docs/protoc-installation)。

在 Linux 上，你可以使用以下管道启动 profile（将 `$APP_NAME` 替换为你的应用程序名称，
将 `$HEAP` 替换为你使用 `AHeapProfile_registerHeap` 注册的 heap 名称）：

```
heap_profile -n $APP_NAME --heaps $HEAP --print-config | \
 path/to/protoc --encode=perfetto.protos.TraceConfig perfetto_trace.proto | \
 adb shell perfetto -c - -o /data/misc/perfetto-traces/profile
```

在 Windows 上，你需要 [python 3.6](https://www.python.org/downloads/) 或更高版本。
你可以从命令提示符使用以下管道启动 profile（将 `%APP_NAME%` 替换为你的应用程序名称，
将 `%HEAP%` 替换为你使用 `AHeapProfile_registerHeap` 注册的 heap 名称）：

```
python /path/to/heap_profile -n %APP_NAME% --heaps %HEAP% --print-config | ^
 path/to/protoc --encode=perfetto.protos.TraceConfig perfetto_trace.proto | ^
 adb shell perfetto -c - -o /data/misc/perfetto-traces/profile
```

在应用程序中操作以使其导致自定义分配，然后使用 `adb shell killall perfetto` 停止 profile。
完成后，使用 `adb pull` 从 `/data/misc/perfetto-traces/profile` 拉取 profile。

将 profile 上传到 [Perfetto UI](https://ui.perfetto.dev)。
