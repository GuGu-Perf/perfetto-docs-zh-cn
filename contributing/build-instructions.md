# Perfetto 构建说明

Perfetto 代码库的权威来源是
https://github.com/google/perfetto。

Android 树中也有一个副本，位于 `/external/perfetto`，并按照常规的 Android 发布节奏进行更新。

Perfetto 可以从 Android 树（AOSP）构建，也可以独立构建。独立构建仅用于本地测试。由于依赖项更少，独立构建的迭代速度更快，是开发 Perfetto 的推荐方式，除非你正在开发具有 Android 内部非 NDK 依赖项的代码。profiler 和内部 HAL/AIDL 依赖项不会在独立构建中构建。

如果你是 Chromium 贡献者，GitHub 是你应该发送 PR 的地方。Chromium 的
[third_party/perfetto](https://source.chromium.org/chromium/chromium/src/+/main:third_party/perfetto/?q=f:third_party%2Fperfetto&ss=chromium)
中的代码是 AOSP 仓库的直接镜像。
[GitHub->Chromium autoroller](https://autoroll.skia.org/r/perfetto-chromium-autoroll)
负责保持 Chromium 的 DEPS 最新。

## 独立构建

#### 获取代码

```bash
git clone https://github.com/google/perfetto
```

#### 拉取依赖库和工具链

```bash
tools/install-build-deps [--android] [--ui] [--linux-arm]
```

`--android` 将拉取 Android NDK、模拟器和构建 `target_os = "android"` 所需的其他依赖项。

`--ui` 将拉取构建 Web UI 所需的 NodeJS 和所有 NPM 模块。有关更多信息，请参阅下方的 [UI 开发](/docs/contributing/ui-getting-started.md) 部分。

`--linux-arm` 将拉取交叉编译 Linux ARM/64 的 sysroots。

WARNING: 请注意，如果你使用 M1 或任何后续的 ARM Mac，你的 Python 版本至少应为 3.9.1，以解决
[此 Python 错误](https://bugs.python.org/issue42704)。

#### 通过 GN 生成构建文件

Perfetto 使用 [GN](https://gn.googlesource.com/gn/+/HEAD/docs/quick_start.md)
作为主要构建系统。有关更多信息，请参阅下方的 [构建文件](#build-files) 部分。

```bash
tools/gn args out/android
```

这将打开一个编辑器来定制 GN 参数。输入：

```python
# 仅在为 Android 构建时设置,在为 linux、mac 或 win 构建时省略。
target_os = "android"
target_cpu = "arm" / "arm64" / "x64"

is_debug = true / false
cc_wrapper = "ccache" # [可选] 使用 ccache 加速重建。
```

有关更多信息，请参阅下方的 [构建配置](#build-configurations) 和
[在 Windows 上构建](#building-on-windows) 部分。

TIP: 如果你是 Chromium 开发者并已安装 depot_tools，你可以避免下方的 `tools/` 前缀，直接使用 depot_tools 中的 gn/ninja。

#### 构建原生 C/C++ 目标

```bash
# 这将构建所有目标。
tools/ninja -C out/android

# 或者,显式列出目标。
tools/ninja -C out/android \
 traced \ # Tracing 服务。
 traced_probes \ # Ftrace 互操作和 /proc 轮询器。
 perfetto \ # 命令行客户端。
 trace_processor_shell \ # Trace 解析。
 traceconv # Trace 转换。
...
```

## Android 树构建

如果你是 AOSP 贡献者，请按照这些说明操作。

源代码位于 [AOSP 树中的 `external/perfetto`](https://cs.android.com/android/platform/superproject/main/+/main:external/perfetto/)。

按照 https://source.android.com/setup/build/building 上的说明操作。

然后：

```bash
mmma external/perfetto
# 或
m traced traced_probes perfetto
```

这将生成 `out/target/product/XXX/system/` 中的产物。

可执行文件和共享库默认由 Android 构建系统剥离。未剥离的产物保存在 `out/target/product/XXX/symbols` 中。

## 构建文件

我们构建文件的权威来源在 BUILD.gn 文件中，这些文件基于 [GN][gn-quickstart]。
Android 构建文件([Android.bp](/Android.bp))通过 `tools/gen_android_bp` 从 GN 文件自动生成，每当更改涉及 GN 文件或引入新文件时都需要调用该脚本。
同样，Bazel 构建文件([BUILD](/BUILD))通过 `tools/gen_bazel` 脚本自动生成。

通过 `git cl upload` 提交 CL 时，预提交检查会检查 Android.bp 是否与 GN 文件一致。

生成器有一个将被翻译到 Android.bp 文件的根目标列表。如果你要添加新目标，请在 [`tools/gen_android_bp`](/tools/gen_android_bp) 的 `default_targets` 变量中添加一个新条目。

## 支持的平台

**Linux 桌面**(Debian Testing/Rodete)

- 封闭的 clang + libcxx 工具链(两者都遵循 Chromium 的版本)
- GCC-7 和 libstdc++ 6
- 为 arm 和 arm64 交叉编译（更多内容见下方）。

**Android**

- Android 的 NDK r15c(使用 NDK 的 libcxx)
- AOSP 的树内 clang(使用树内 libcxx)

**Mac**

- XCode 9 / clang(尽力维护)。

**Windows**

- 带有 MSVC 2019 或 clang-cl 的 Windows 10(尽力维护)。

### 在 Windows 上构建

使用 MSVC 2019 编译器（不需要完整的 IDE，只需要构建工具）或 LLVM clang-cl 编译器可以在 Windows 上构建。

独立构建中的 Windows 支持在 v16 中通过
[r.android.com/1711913](https://r.android.com/1711913) 引入。

clang-cl 支持更稳定，因为该构建配置被 Chromium 项目积极覆盖（Perfetto 滚动进入 Chromium 并支持 chrome://tracing）。MSVC 构建尽力维护。

Windows 上支持以下目标：

- `trace_processor_shell`:trace 导入器和 SQL 查询引擎。
- `traceconv`:trace 转换工具。
- `traced` 和 `perfetto`:tracing 服务和命令行客户端。它们使用基于 TCP 套接字和命名共享内存的 [进程间 tracing 协议](/docs/design-docs/api-and-abi.md#tracing-protocol-abi)
 的替代实现。此配置仅用于测试/基准测试，不会在生产环境中发布。
 Googlers：有关详细信息，请参阅 [go/perfetto-win](http://go/perfetto-win)。
- `perfetto_unittests` / `perfetto_integrationtests`：虽然它们仅支持 Windows 上支持的代码子集（例如没有 ftrace）。

不可能从 Windows 构建 Perfetto UI。

#### 先决条件

对于 MSVC 和 clang-cl，你需要所有这些：

- [Build Tools for Visual Studio 2019](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2019)
- [Windows 10 SDK](https://developer.microsoft.com/en-us/windows/downloads/windows-10-sdk/)
- [Python 3](https://www.python.org/downloads/windows/)

[`win_find_msvc.py`](/gn/standalone/toolchain/win_find_msvc.py) 脚本将从
`C:\Program Files (x86)\Windows Kits\10` 和
`C:\Program Files (x86)\Microsoft Visual Studio\2019` 找到可用的最高版本号。

#### 拉取依赖库和工具链

```bash
# 这也将下载 chromium 使用的 LLVM clang-cl 预构建。
python3 tools/install-build-deps
```

#### 生成构建文件

```bash
python3 tools/gn gen out/win
```

在编辑器中输入：

```bash
is_debug = true | false

is_clang = true # 将使用封闭的 clang-cl 工具链。
# 或
is_clang = false # 将使用 MSVC 2019。
```

#### 构建

```bash
python3 tools/ninja -C out/win perfetto traced trace_processor_shell
```

### 为 Linux ARM/64 交叉编译

为 Linux 交叉编译时，你将需要 sysroot。你有两个选择：

#### 1. 使用基于 Debian Sid 的内置 sysroot

```bash
tools/install-build-deps --linux-arm
```

然后设置以下 GN 参数：

```python
target_os = "linux"
target_cpu = "arm"
# 或
target_cpu = "arm64"
```

#### 2. 使用你自己的 sysroot

在这种情况下，你需要手动指定 sysroot 位置和要使用的工具链前缀三元组。

```python
target_os = "linux"
target_sysroot = "/path/to/sysroot"
target_triplet = "aarch64-linux-gnu" # 或任何其他受支持的三元组。
```

有关更多详细信息，请参阅下方的 [使用自定义工具链](#custom-toolchain) 部分。

## 构建配置

TIP: `tools/setup_all_configs.py` 可用于为大多数支持的配置生成 out/XXX 文件夹。

支持以下 [GN 参数][gn-quickstart]:

`target_os = "android" | "linux" | "mac"`:

默认为当前主机，设置 "android" 以构建 Android。

`target_cpu = "arm" | "arm64" | "x64"`

默认为 `target_os` == `"android"` 时的 `"arm"`，以主机为目标时的 `"x64"`。不支持 32 位主机构建。
NOTE: 这里的 x64 实际上意味着 x86_64。这是为了保持与 Chromium 的选择一致，而 Chromium 又遵循 Windows 命名约定。

`is_debug = true | false`

切换 Debug(默认)/Release 模式。这会影响，除其他外：
(i) `-g` 编译器标志;(ii) 设置/取消设置 `-DNDEBUG`;(iii) 打开/关闭 `DCHECK` 和 `DLOG`。
请注意，Perfetto 的调试版本比发布版本明显更慢。我们强烈鼓励仅在本地开发时使用调试版本。

`is_clang = true | false`

使用 Clang（默认：true）或 GCC(false)。
在 Linux 上，默认使用自托管的 clang(参见 `is_hermetic_clang`)。
在 Android 上，默认使用 NDK 中的 clang(在 `buildtools/ndk` 中)。
在 Mac 上，默认使用系统版本的 clang(需要 Xcode)。
另请参阅下方的 [自定义工具链](#custom-toolchain) 部分。

`is_hermetic_clang = true | false`

使用 `buildtools/` 中的捆绑工具链，而不是系统范围的工具链。

`non_hermetic_clang_stdlib = libc++ | libstdc++`

如果 `is_hermetic_clang` 为 `false`，则为 clang 调用设置 `-stdlib` 标志。`libstdc++` 在 Linux 主机上默认，`libc++` 在其他地方默认。

`cc = "gcc" / cxx = "g++"`

使用不同的编译器二进制文件（默认：根据 is_clang 自动检测）。
另请参阅下方的 [自定义工具链](#custom-toolchain) 部分。

`cc_wrapper = "tool_name"`

使用包装器命令在所有构建命令前添加。在此使用 `"ccache"` 启用 [ccache](https://github.com/ccache/ccache) 缓存编译器，这可以显著加速重复构建。

`is_asan = true`

启用 [地址清理器](https://github.com/google/sanitizers/wiki/AddressSanitizer)

`is_lsan = true`

启用 [泄漏清理器](https://github.com/google/sanitizers/wiki/AddressSanitizerLeakSanitizer)
(仅限 Linux/Mac)

`is_msan = true`

启用 [内存清理器](https://github.com/google/sanitizers/wiki/MemorySanitizer)
(仅限 Linux)

`is_tsan = true`

启用 [线程清理器](https://github.com/google/sanitizers/wiki/ThreadSanitizerCppManual)
(仅限 Linux/Mac)

`is_ubsan = true`

启用 [未定义行为清理器](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html)

### {#custom-toolchain} 使用自定义工具链和 CC / CXX / CFLAGS 环境变量

将 Perfetto 作为其他构建环境的一部分构建时，可能需要关闭所有内置的工具链相关路径猜测脚本并手动指定工具链的路径。

```python
# 禁用猜测工具链路径的脚本。
is_system_compiler = true

ar = "/path/to/ar"
cc = "/path/to/gcc-like-compiler"
cxx = "/path/to/g++-like-compiler"
linker = "" # 这被传递给 -fuse-ld=...
```

如果你使用的构建系统将工具链设置保存在环境变量中，可以设置：

```python
is_system_compiler = true
ar="${AR}"
cc="${CC}"
cxx="${CXX}"
```

`is_system_compiler = true` 也可用于交叉编译。
在交叉编译的情况下，GN 变量具有以下语义：
`ar`、`cc`、`cxx`、`linker` 指的是 _主机_ 工具链（有时也称为 _构建_ 工具链）。此工具链用于构建：(i) 辅助工具（例如 `traceconv` 转换工具）和 (ii) 在目标构建过程的其余部分中使用的可执行文件产物（例如 `protoc` 编译器或 `protozero_plugin` protoc 编译器插件）。

用于构建在设备上运行的产物的交叉工具链以 `target_` 为前缀：`target_ar`、`target_cc`、`target_cxx`、`target_linker`。

```python
# 当这三个变量中至少有一个设置为不等于主机默认值的值时,交叉编译开始。

target_cpu = "x86" | "x64" | "arm" | "arm64"
target_os = "linux" | "android"
target_triplet = "arm-linux-gnueabi" | "x86_64-linux-gnu" | ...
```

与 GNU Makefile 交叉工具链构建环境集成时，相应环境变量的典型映射是：

```python
ar="${BUILD_AR}"
cc="${BUILD_CC}"
cxx="${BUILD_CXX}"
target_ar="${AR}"
target_cc="${CC}"
target_cxx="${CXX}"
```

可以通过 `extra_xxxflags` GN 变量扩展 `CFLAGS` 和 `CXXFLAGS` 集合，如下所示。额外的标志总是附加（因此，优先）到 GN 构建文件生成的标志集。

```python
# 这些适用于主机和目标工具链。
extra_cflags="${CFLAGS}"
extra_cxxflags="${CXXFLAGS}"
extra_ldflags="${LDFLAGS}"

# 这些仅适用于主机工具链。
extra_host_cflags="${BUILD_CFLAGS}"
extra_host_cxxflags="${BUILD_CXXFLAGS}"
extra_host_ldflags="${BUILD_LDFLAGS}"

# 这些仅适用于目标工具链。
extra_target_cflags="${CFLAGS}"
extra_target_cxxflags="${CXXFLAGS} ${debug_flags}"
extra_target_ldflags="${LDFLAGS}"
```

[gn-quickstart]: https://gn.googlesource.com/gn/+/master/docs/quick_start.md

## IDE 设置

在签出目录中使用以下命令来生成编译数据库文件：

```bash
tools/gn gen out/default --export-compile-commands
```

生成后，可以在 CLion(File -> Open -> Open As Project)、带 C/C++ 扩展的 Visual Studio Code 以及任何其他支持编译数据库格式的工具和编辑器中使用它。

#### 有用的扩展

如果你使用 VS Code，我们建议以下扩展：

- [Clang-Format](https://marketplace.visualstudio.com/items?itemName=xaver.clang-format)
- [C/C++](https://marketplace.visualstudio.com/items?itemName=ms-vscode.cpptools)
- [clangd](https://marketplace.visualstudio.com/items?itemName=llvm-vs-code-extensions.vscode-clangd)
- [Native Debug](https://marketplace.visualstudio.com/items?itemName=webfreak.debug)
- [GN Language Server](https://marketplace.visualstudio.com/items?itemName=msedge-dev.gnls)
- [ESlint](https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint)
- [markdownlint](https://marketplace.visualstudio.com/items?itemName=DavidAnson.vscode-markdownlint)
- [Prettier](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode)

#### 有用的设置

在 `.vscode/settings.json` 中：

```json
{
 "C_Cpp.clang_format_path": "${workspaceRoot}/buildtools/mac/clang-format",
 "C_Cpp.clang_format_sortIncludes": true,
 "files.exclude": {
 "out/*/obj": true,
 "out/*/gen": true
 },
 "clangd.arguments": [
 "--compile-commands-dir=${workspaceFolder}/out/mac_debug",
 "--completion-style=detailed",
 "--header-insertion=never"
 ],
 "eslint.workingDirectories": ["./ui"],
 "prettier.configPath": "ui/.prettierrc.yml",
 "typescript.preferences.importModuleSpecifier": "relative",
 "[typescript]": {
 "editor.defaultFormatter": "esbenp.prettier-vscode"
 },
 "[scss]": {
 "editor.defaultFormatter": "esbenp.prettier-vscode"
 }
}
```

在 Linux 上将 `/mac/` 替换为 `/linux64/`。

### 使用 VSCode 调试

编辑 `.vscode/launch.json`:

```json
{
 "version": "0.2.0",
 "configurations": [
 {
 "request": "launch",
 "type": "cppdbg",
 "name": "Perfetto unittests",
 "program": "${workspaceRoot}/out/mac_debug/perfetto_unittests",
 "args": [
 "--gtest_filter=TracingServiceImplTest.StopTracingTriggerRingBuffer"
 ],
 "cwd": "${workspaceFolder}/out/mac_debug",
 "MIMode": "lldb"
 }
 ]
}
```

然后打开命令面板 `Meta`+`Shift`+`P` -> `Debug: Start debugging`。
