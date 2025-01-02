.PHONY: all setup run clean check-deps

# 检测Python命令
PYTHON := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
ifeq ($(PYTHON),)
    $(error "未找到Python。请安装Python 3")
endif

# 默认目标
.DEFAULT_GOAL := all

# 一键安装运行
all: check-deps setup run

check-deps:
	@echo "检查系统依赖..."
	@command -v pandoc >/dev/null 2>&1 || (echo "请安装 pandoc" && exit 1)
	@command -v xelatex >/dev/null 2>&1 || (echo "请安装 texlive-xetex" && exit 1)
	@echo "系统依赖检查完成"

setup:
	@echo "使用 Python: $(PYTHON)"
	@echo "复制 SF Mono 字体..."
	@if [ ! -f ~/Library/Fonts/SF-Mono-Regular.otf ]; then \
		mkdir -p ~/Library/Fonts && \
		cp /Applications/Xcode.app/Contents/SharedFrameworks/DVTUserInterfaceKit.framework/Versions/A/Resources/Fonts/SF-Mono-* ~/Library/Fonts/ || \
		echo "警告: SF Mono 字体复制失败，请确保已安装 Xcode"; \
	fi
	$(PYTHON) -m venv venv
	./venv/bin/pip install --upgrade pip wheel
	./venv/bin/pip install --use-pep517 -r requirements.txt
	mkdir -p output repo
	@echo "环境配置完成"

run:
	@echo "开始运行程序..."
	./venv/bin/python sourcecode_reader.py

clean:
	rm -rf output/*_*.pdf  # 清理带时间戳的PDF文件
	rm -rf output/*_*.epub # 清理带时间戳的EPUB文件
	rm -rf repo/*
	rm -rf venv
	rm -rf __pycache__
	rm -rf *.log
	@echo "清理完成"

help:
	@echo "使用说明:"
	@echo "make          - 执行完整流程(检查依赖、安装环境、运行程序)"
	@echo "make setup    - 创建虚拟环境并安装依赖"
	@echo "make run      - 运行程序"
	@echo "make clean    - 清理生成的文件和虚拟环境"
	@echo "make help     - 显示此帮助信息"