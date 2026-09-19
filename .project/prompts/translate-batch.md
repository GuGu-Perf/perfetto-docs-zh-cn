# 翻译子代理批次任务模板

> 主代理派发翻译批次时，将本模板填入 `{占位符}` 后作为子代理 prompt。
> 目的：公共规范只维护这一份，避免每次手写 prompt 造成规则漂移。

---

你在 Perfetto 中文文档翻译仓库 /Users/vinson/CodeBuddy/Claw/perfetto-docs-zh-cn 中工作，
上游英文仓库在 /Users/vinson/CodeBuddy/Claw/perfetto。

## 重要：上游原文获取方式

上游 `../perfetto` 的 `docs/` 工作树可能被部署脚本覆盖为中文拷贝，
**获取上游英文原文必须使用 `git -C ../perfetto show HEAD:<path>`**，不要直接读工作树文件。

## 任务

将以下文件的上游更新翻译并应用到本地中文文档（diff 来源：{DIFF_SOURCE，如 /tmp/upstream_diff.txt 第 N-M 行}）：

{FILE_LIST（逐文件列出，附 diff 行区间或"全新文件，翻译上游全文"）}

## 步骤

1. 先读以下规范（顺序固定）：
   - `.project/TRANSLATION_GUIDE.md` — 完整翻译规范与术语表
   - `.project/glossary.json` — 机器可读术语表（translate=false 的术语必须保持英文）
   - `.project/phrases.json` — 短语与链接文本定型译法（优先级高于自行斟酌）
2. 对每个文件：读本地中文文件，对照 diff 将改动翻译后用 Edit 应用——
   删除的英文段落对应删除中文，新增段落翻译后插入对应位置，改写段落用新译文替换。
3. 翻译时严格遵守：
   - 代码块、命令、flags、API 名、版本号、URL、图片路径**绝不翻译**
   - `NOTE:` / `TIP:` / `WARNING:` / `Summary:` 前缀保留英文（含冒号用半角）
   - 中文全角标点（。、，！？）；中英文之间加空格（如「使用 Trace 分析」）
   - Markdown 结构（标题层级/列表/表格/围栏）与上游 100% 一致
   - **链接 URL 右括号必须是半角 `)`**，全角 `）` 会破坏 markdown 链接解析（历史高频 bug）
4. 完成后自检并修复，直到通过：
   ```bash
   bash .project/audit.sh --files {FILE_LIST}
   bash .project/proofread.sh {FILE_LIST}
   ```
   两者必须 0 错误（proofread 的 W1 空格警告可留存，不计失败）。

## 完成报告

逐文件报告：修改了什么、自检结果。**不要执行任何 git 操作。**

## 环境备注（如适用）

{ENV_NOTES，如：终端代理 https_proxy=http://127.0.0.1:7897；本地服务器地址；无浏览器环境时的降级校验方式}
