# workwork.md — Perfetto 中文文档项目：唯一工程文档

> 本文件是项目**唯一的**工程文档（工具手册 + 工作流 + 操作纪律 + 翻译规范）。
> 工具对应 `.project/workwork.py`（唯一命令入口）。
> 历史决策记录见 `.project/plan/`，会话交接见 `.project/HANDOFF.md`（数据文件，非文档）。

## 一、硬约束（最高优先级，任何工作方式不得违反）

1. **提交、推送、部署（deploy-gh-pages）逐次须经人工确认**——本文件描述的是顺序，不是授权
2. **精简原则**：新增能力一律并入现有文件——工具能力 = `workwork.py` 新子命令，
   文档内容 = 本文件新章节，术语/短语 = `glossary.json`/`phrases.json` 新条目。
   **新建任何文件须经人工批准**
3. **超时纪律**：每条外部命令（git/curl/node）必须带超时；耗时预估按悲观值报告；
   预期 >60s 的任务后台执行 + 阶段性汇报；长任务中间产物落盘缓存（`.cache/`）可续跑
4. **网络纪律**：perfetto.dev 走代理（`http://127.0.0.1:7897`）；
   gugu-perf.github.io 与 localhost 直连；单次抓取 `--max-time ≤15s`
5. **规则纪律**：新增 lint/审计规则须先在语料上校准（flags 对照上游确认为真违规）
   才能作为 error 级；规则依据事实来源（如渲染器源码 render.mjs）
6. **上游原文必须用 `git -C ../perfetto show HEAD:<path>` 获取**——
   部署会把中文 docs/ 拷进上游仓库覆盖英文工作树

## 二、快速启动清单（月度会话开工顺序）

0. **先读 `.project/HANDOFF.md`**（上次会话的坑与绕法、术语决策）
1. `python3 .project/workwork.py sync-check` — 检查上游更新
2. `python3 .project/workwork.py audit` — 全量结构审计，**非 0 差异先修欠账再继续**
3. 翻译：按 `.project/prompts/translate-batch.md` 模板派发子代理批次
4. 质量门禁全绿：`audit` + `proofread --all`
5. `python3 .project/workwork.py compare-structure` — 双构建渲染比对（非 hljs 差异须清零）
6. 回译抽查：随机抽 2-3 个本轮翻译文件，让 LLM 把中文译回英文与上游原文比对相似度，
   拦截错译/漏译/幻觉（语义层唯一防线，结构检查对此不可见）
7. **暂停，人工确认后**：提交推送 → `sync-update` → `deploy-gh-pages`
8. `compare-structure --live` 部署抽查（2-3 页，验证部署路径）→ 更新 `.project/HANDOFF.md`

## 三、命令参考（workwork.py）

| 命令 | 作用 |
|------|------|
| `deploy-local` | 复制中文 docs → 首页补丁 → 构建（自动探测 build.mjs/GN 新旧系统）→ fail-closed 首页断言 → 启动 :8082 |
| `deploy-gh-pages` | 同上构建 + 路径修补（fail-closed 产物校验）+ pre-deploy-* 回退 tag + 强推 gh-pages |
| `rollback-gh-pages [tag]` | 回退 gh-pages 到部署前状态（默认最近 tag） |
| `sync-check` | 强制同步上游仓库 → 对比 LAST_SYNC → 列出 docs/ 变更（无变更退出 0） |
| `sync-update` | 更新 LAST_SYNC 为上游最新 docs/ commit |
| `audit [--files ...]` | 全量结构审计 vs 上游 **git HEAD**（检查项见下） |
| `proofread [--all] [--strict]` | 术语/标志/标点 lint（读 glossary.json） |
| `compare-structure [--page X] [--verbose]` | **双构建渲染比对**：同一上游 commit 构建英文站+中文站（out/en-site vs out/zh-site），DOM 签名逐元素一致 + 英文残留；差异分类 hljs/inline/struct |
| `compare-structure --live [--page X]` | 部署抽查：本地中文构建 vs 线上页面（验证部署路径与 CDN） |

### audit 检查项（结构层，剥离代码块后统计）

| 项 | 内容 |
|----|------|
| A1 | 文件清单双向一致（漏翻 / 上游已删未同步） |
| A2/A3 | 标题数 / 代码围栏数 |
| A4/A5 | 表格行 / 图片数（近似） |
| A6 | 链接 URL 集合（相对路径归一化后比对；title 部分可译故剥离） |
| A7 | 提示框（callout）数量：段首大写 `NOTE:/TIP:/WARNING:/TODO:/FIXME:/Summary:` |
| A7b | 幽灵引用：工程文档引用的 `.project/*` 文件必须存在 |
| A8 | 显式锚点 `{#...}`：上游有而本地缺（本地多出为合法适配，不算差异） |
| A9 | 代码块语言标签序列 |
| A10/A11 | 行内代码数 / 加粗斜体数（**段落感知**：剥离列表符后跨行合并计数，`_x_` 归一化为 `*`） |

### proofread 检查项（规则层）

- **E1** 术语违规：glossary.json 中 translate=false 的禁用中文译法出现在散文中
- **E2** 标志误用全角冒号（段首大写 callout 标志后跟全角冒号）
- **E3** 标点：中文语句半角句号结尾 / 中文间半角逗号
- **W1** 中英文之间缺空格（警告）
- **W2** 段首中文标志词——上游为大写 callout 则违规、纯文本 `Note:` 则正确，需对照（A7 兜底）
- **W3** 英文引导词+中文内容（混合大小写非 callout，应翻译）

### compare-structure 检测（渲染层）

- **[S]** DOM 结构签名：内容区 `(tag, 结构类)` 序列逐元素一致——提示框/选项卡/表格/
  高亮块的数量与位置差异都会暴露
- **[T]** 英文残留：自建页面整段无 CJK 的散文文本（白名单过滤代码/短标识，人工复核）

## 四、翻译规范

### 4.1 基本原则（冲突时按优先级）

1. **技术正确性**：不确定时保留英文；参数/API/配置字段名/数值单位严禁翻译
2. **术语一致性**：以 `.project/glossary.json` 为唯一依据（120+ 术语，
   translate=false 保持英文，true 译为中文；单复数/大小写等变种遵循同规则）
3. **中文通顺性**：全角标点（句末 `。`）；中英文之间加空格；50 字以上长句拆分；
   被动优先转主动；If→"如果...则"，When→"当...时"

### 4.2 动词与格式

- `capture/record trace` → **采集 trace**；`to profile` → **进行 profile/profiling**
- Markdown 结构与原文 100% 一致：加粗/斜体/代码保留标记替换内容；列表类型层级数量不变；
  表格行列数严格一致；代码块语言标记不变；URL 与图片路径不变
- **代码块内容三层约束**（政策 B，2026-09-19）：
  1. 代码本体（命令/标识符/输出）永不翻译
  2. 有语言标注的代码块内**注释可以翻译**——由此产生的 hljs 高亮差异已被
     compare-structure 容忍（`--strict-hljs` 可严查）
  3. **无语言标注的代码块整块保持英文**（含注释）——hljs autoDetect 会被中文
     翻转语言判定（如 livecodeserver→node-repl），属结构性差异；语法敏感前缀
     （SQL `-- Note:` 等）同样保持英文
- **链接 URL 右括号必须半角 `)`**（全角 `）` 会破坏 markdown 解析，历史高频 bug）
- 短语级定型译法见 `.project/phrases.json`（优先级高于自行斟酌）

### 4.3 提示框（callout）判定——依据上游 render.mjs，大小写敏感

- **段首大写** `NOTE:` / `TIP:` / `WARNING:` / `TODO:` / `FIXME:` / `Summary:`
  渲染为带图标提示框（列表内缩进会被解析器剥离，同样生效）→ **必须保留英文**
- **混合大小写** `Note:` 是纯文本 → **必须翻译成中文**（如「注意:」）

### 4.5 本站渲染器（markdown-it 系）的 CJK 已知坑

1. **`_中文_` 下划线斜体不可靠**（CJK 相邻时定界符常不闭合）→ 中文斜体一律用 `*…*`
2. **闭合 `**`/`_` 紧邻全角标点在特定前驱字符（]/`/）等）下可能失效**，页面出现字面星号
   ——以 `compare-structure --page` 的真实渲染为权威判定，发现字面星号即修（闭合符后加空格）
3. **链接 URL 右括号必须半角 `)`**，全角 `）` 会吞掉后续文本（历史高频 bug）
4. 列表续行/嵌套代码围栏的缩进不足会脱出列表项（镜像上游缩进）
5. 硬换行（行尾双空格）丢失会改变段落结构

### 4.4 翻译后必做

```bash
python3 .project/workwork.py audit --files docs/你翻译的文件.md
python3 .project/workwork.py proofread docs/你翻译的文件.md
python3 .project/workwork.py deploy-local   # 本地预览
```

## 五、项目结构

| 路径 | 用途 |
|------|------|
| `docs/` | 翻译后的中文文档（镜像上游 `perfetto/docs/`） |
| `AGENTS.md` / `CLAUDE.md` | 根目录发现指针（各 agent 工具自动读取，指向本文件与 HANDOFF） |
| `.project/workwork.py` | **唯一工具**（第三节全部命令） |
| `.project/workwork.md` | **唯一工程文档**（本文件） |
| `.project/glossary.json` | 机器可读术语表（proofread 校验 + 翻译注入，唯一事实来源） |
| `.project/phrases.json` | 短语/链接文本定型译法（轻量翻译记忆） |
| `.project/prompts/translate-batch.md` | 翻译子代理批次任务模板 |
| `.project/HANDOFF.md` | 会话交接纪要（开工先读、收尾必更） |
| `.project/LAST_SYNC` | 上游同步点 |
| `.project/plan/` | 架构决策与路线图（历史记录） |
| `.cache/` | 工具运行缓存（gitignore） |

## 六、Commit 规范

`translate`（翻译）/ `fix`（修错）/ `improve`（改进）/ `chore`（工具链），
示例：`translate: sync upstream docs update (a1b2c3..d4e5f6)`
