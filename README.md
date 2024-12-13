# SourceCode Reader

一个将开源项目代码转换为 PDF 和 EPUB 格式的源码阅读工具。支持代码高亮、目录生成、中文显示等功能。

## 功能特性

- 自动从 GitHub 克隆代码仓库
- 智能识别文件编码
- 生成带目录的 PDF 文档
- 生成 EPUB 电子书
- 代码语法高亮
- 优雅的中文排版
- 自定义 LaTeX 模板

## 安装要求

- Python 3.7+
- pandoc
- XeLaTeX
- macOS 自带字体：
  - Songti SC（宋体）
  - PingFang SC（苹方）
  - Menlo（等宽字体）

## 快速开始

1. 克隆仓库：
   ```bash
   git clone https://github.com/yourusername/sourcecode-reader.git
   cd sourcecode-reader
   ```

2. 安装依赖：
   ```bash
   make setup
   ```

3. 配置：
   编辑 `config.ini` 文件，设置 GitHub 仓库 URL 和其他选项。

4. 运行：
   ```bash
   make run
   ```

## 配置说明

在 `config.ini` 文件中：

```ini
[github]
repo_url = https://github.com/username/repo.git  # 目标仓库地址

[output]
output_dir = output  # 输出目录
supported_extensions = .py,.js,.rs,.md  # 支持的文件类型

[document]
title = 开源项目源码阅读  # 文档标题
author = SourceCode Reader  # 作者
mainfont = Songti SC  # 正文字体
sansfont = PingFang SC  # 标题字体
monofont = Menlo  # 代码字体
```

## 目录结构

```
.
├── sourcecode_reader.py  # 主程序
├── config.ini           # 配置文件
├── requirements.txt     # Python 依赖
├── Makefile            # 构建脚本
└── templates/          # LaTeX 模板
    └── latex/
        ├── main.tex
        └── includes/
            └── packages.tex
```

## 使用说明

1. 一键生成：
   ```bash
   make
   ```

2. 分步执行：
   ```bash
   make setup  # 安装依赖
   make run    # 运行程序
   ```

3. 清理文件：
   ```bash
   make clean
   ```

## 支持的文件类型

- Python (.py)
- JavaScript/TypeScript (.js, .jsx, .ts, .tsx)
- Rust (.rs)
- Markdown (.md)
- JSON (.json)
- Shell (.sh)
- YAML (.yaml, .yml)
- TOML (.toml)
- 更多文件类型见 config.ini

## 许可证

MIT License

## 致谢

- pandoc
- XeLaTeX
- Python 及其相关库
