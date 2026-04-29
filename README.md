# Perfetto 中文文档

[![在线阅读](https://img.shields.io/badge/在线阅读-GitHub%20Pages-blue)](https://gugu-perf.github.io/perfetto-docs-zh-cn/)
[![License](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](LICENSE)

## 项目简介

[Perfetto](https://perfetto.dev) 中文文档


## 访问文档

### 在线阅读

https://gugu-perf.github.io/perfetto-docs-zh-cn/

### 本地部署

```bash
# 克隆仓库
git clone https://github.com/GuGu-Perf/perfetto-docs-zh-cn.git
cd perfetto-docs-zh-cn

# 本地预览（自动构建并启动服务器）http://localhost:8082/docs/
bash .project/workwork.sh deploy-local
```


## 项目结构

```
perfetto-docs-zh-cn/
├── docs/                    # 翻译后的中文文档
├── .project/                # 项目工具与配置
│   ├── workwork.sh          # 统一工具入口（预览/发布/同步）
│   ├── workwork.md          # 工具使用说明
│   ├── LAST_SYNC            # 上游同步记录
│   ├── TRANSLATION_GUIDE.md # 翻译规范（术语表、格式要求）
│   └── ...
├── CONTRIBUTING.md          # 贡献指南
├── LICENSE                  # Apache 2.0
└── README.md
```

## 上游同步

上游跟踪：https://github.com/google/perfetto/tree/main/docs

最新同步: [.project/LAST_SYNC](.project/LAST_SYNC)

## 参与贡献

欢迎参与项目！参考 [CONTRIBUTING.md](CONTRIBUTING.md) 进行贡献提交，或提 [Issue](https://github.com/GuGu-Perf/perfetto-docs-zh-cn/issues) 反馈问题。


## 致谢

- voidice@gmail.com
- zhuyong7@honor.com
- xiaolu5@honor.com

## 许可证

[Apache 2.0 License](LICENSE)