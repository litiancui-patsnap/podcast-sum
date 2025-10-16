# Makefile for Podcast Summarization Pipeline

.PHONY: help setup run clean test

# 默认目标
help:
	@echo "Podcast Summarization Pipeline"
	@echo ""
	@echo "使用方法:"
	@echo "  make setup            - 安装依赖"
	@echo "  make run AUDIO=<file> - 运行完整流程"
	@echo "  make clean            - 清理输出文件"
	@echo ""
	@echo "示例:"
	@echo "  make run AUDIO=audio/demo.m4a"

# 安装依赖
setup:
	@echo "===== 安装依赖 ====="
	pip install -r requirements.txt
	@echo ""
	@echo "✓ 依赖安装完成"
	@echo ""
	@echo "请确保已安装:"
	@echo "  - ffmpeg (音频转换)"
	@echo "  - Ollama 或其他本地 LLM 服务"

# 运行完整流程
run:
	@if [ -z "$(AUDIO)" ]; then \
		echo "错误: 请指定音频文件"; \
		echo "用法: make run AUDIO=audio/demo.m4a"; \
		exit 1; \
	fi
	@echo "===== 开始处理: $(AUDIO) ====="
	@echo ""
	@echo "[1/5] 音频预处理..."
	python prep_audio.py $(AUDIO)
	@echo ""
	@echo "[2/5] 语音转写..."
	python transcribe.py $(basename $(AUDIO))_16k.wav
	@echo ""
	@echo "[3/5] 分块与 Map 摘要..."
	python chunk_and_map.py
	@echo ""
	@echo "[4/5] Reduce 与质检..."
	python reduce_and_qc.py
	@echo ""
	@echo "[5/5] 生成微信 HTML..."
	python generate_wechat_html.py
	@echo ""
	@echo "===== 全部完成 ====="
	@echo "输出文件位于 outputs/ 目录"

# 清理输出
clean:
	@echo "===== 清理输出文件 ====="
	rm -rf outputs/*
	@echo "✓ 清理完成"

# 测试配置
test:
	@echo "===== 测试配置 ====="
	@echo "检查 Python 环境..."
	python --version
	@echo ""
	@echo "检查 ffmpeg..."
	ffmpeg -version | head -n 1
	@echo ""
	@echo "检查 Python 包..."
	pip list | grep -E "(faster-whisper|openai|PyYAML|markdown2)"
	@echo ""
	@echo "✓ 环境检查完成"
