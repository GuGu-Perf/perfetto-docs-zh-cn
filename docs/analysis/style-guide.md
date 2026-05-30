# PerfettoSQL 样式指南

_本页面提供了编写 PerfettoSQL 的建议样式指南，该指南在 trace processor 的 PerfettoSQL 标准库中使用。它还提供了关于自动格式化程序的指导。_

## 规则

1. 保持行长度在 80 个字符以下
2. 函数名、宏名和表/视图名都应使用小写 snake_case
3. SQL 关键字都应使用大写
4. 换行 SQL 表达式时，将连接关键字（AND/OR）放在_下一行的开头_，而不是_上一行的末尾_

## 自动格式化程序

PerfettoSQL 带有一个自动格式化程序，由 `tools/format-sql-sources` 驱动。它通过外壳调用 `syntaqlite fmt`，使用与 trace processor 本身相同的 PerfettoSQL 语法（作为共享库加载）进行解析。该脚本可以对任何文件或目录运行，并自动格式化代码以遵守上述规则。

在向标准库贡献时，必须运行此脚本。它在运行 `tools/gen_all` 时自动执行，这是 Perfetto 标准开发工作流程的一部分。预提交检查将确保你已完成此操作。
