# 播客转写与摘要系统

完全私有化、可本地运行的中文播客音频全量转写 + 分段摘要(Map) + 汇总(Reduce) + 质检 + 微信公众号图文输出系统。

## 功能特性

- **语音转写**：使用 faster-whisper 实现高质量中文转写，支持 GPU 加速
- **智能分块**：自动将长文本分块，支持块间重叠以保持上下文
- **Map-Reduce 摘要**：分段摘要后整合，确保信息完整性
- **时间戳质检**：自动检测时间戳是否越界
- **微信公众号适配**：生成可直接粘贴的图文稿，含金句、目录、排版
- **完全离线**：所有处理可在本地完成，无需公网依赖

## 输入输出

**输入**：任意中文播客 .m4a 音频文件（40-90 分钟）

**输出**（保存在 `outputs/` 目录）：
- `transcript.json`：完整转写结果（带时间戳）
- `maps.json`：分段摘要汇总
- `chunks/`：每个分块的独立摘要文件
- `summary.md`：完整文字总结
- `summary.json`：结构化摘要数据
- `summary_wechat.html`：微信公众号可用的 HTML 图文稿

## 环境要求

- **Python**：3.10+
- **ffmpeg**：用于音频格式转换
- **GPU**（可选）：用于加速 Whisper 转写
- **本地 LLM 服务**：Ollama / vLLM / OpenWebUI 等 OpenAI 兼容 API

## 快速开始

### 1. 克隆或下载项目

```bash
cd podcast-sum
```

### 2. 安装依赖

```bash
make setup
```

或手动安装：

```bash
pip install -r requirements.txt
pip install httpx[socks]
```

### 3. 安装 ffmpeg

**macOS**:
```bash
brew install ffmpeg
```

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows**:
下载并安装：https://ffmpeg.org/download.html

### 4. 启动本地 LLM 服务

以 Ollama 为例：

```bash
# 安装 Ollama
brew install ollama  # macOS
# 或访问 https://ollama.com 下载其他平台版本

# 启动服务
ollama serve

# 下载中文模型（新终端）
ollama pull qwen2.5:7b-instruct-q4_0
```

其他选项：
- vLLM: https://github.com/vllm-project/vllm
- OpenWebUI: https://github.com/open-webui/open-webui
- LM Studio: https://lmstudio.ai/

### 5. 配置 config.yaml

编辑 `config.yaml`，根据您的硬件和 LLM 服务调整：

```yaml
asr:
  device: cuda              # 有 GPU 用 cuda，否则改为 cpu
  compute_type: float16     # CPU 环境改为 int8_float16

summarizer:
  base_url: "http://localhost:11434/v1"  # LLM 服务地址
  model: "qwen2.5:7b-instruct-q4_0"      # 模型名称
```

### 6. 准备音频

将音频文件放入 `audio/` 目录：

```bash
# 示例
cp ~/Downloads/podcast_episode.m4a audio/demo.m4a
```

### 7. 运行完整流程

```bash
make run AUDIO=audio/demo.m4a
```

或分步执行：

```bash
# 步骤 1: 音频预处理
python prep_audio.py audio/demo.m4a

# 步骤 2: 语音转写
python transcribe.py audio/demo_16k.wav

# 步骤 3: 分块与 Map 摘要
python chunk_and_map.py

# 步骤 4: Reduce 与质检
python reduce_and_qc.py

# 步骤 5: 生成微信 HTML
python generate_wechat_html.py
```

### 8. 查看结果

- **摘要**：`outputs/summary.md`
- **微信图文**：用浏览器打开 `outputs/summary_wechat.html`，全选复制后粘贴到公众号后台

## 项目结构

```
podcast-sum/
├── audio/                      # 输入音频目录
├── outputs/                    # 输出结果目录
│   ├── transcript.json         # 转写结果
│   ├── chunks/                 # 分块摘要
│   ├── maps.json               # Map 阶段汇总
│   ├── summary.md              # 完整摘要（Markdown）
│   ├── summary.json            # 结构化数据
│   └── summary_wechat.html     # 微信公众号 HTML
├── config.yaml                 # 配置文件
├── prep_audio.py               # 音频预处理脚本
├── transcribe.py               # 语音转写脚本
├── chunk_and_map.py            # 分块与 Map 摘要
├── reduce_and_qc.py            # Reduce 与质检
├── generate_wechat_html.py     # 生成微信 HTML
├── requirements.txt            # Python 依赖
├── Makefile                    # 自动化脚本
└── README.md                   # 本文档
```

## 配置说明

### ASR 配置 (config.yaml)

```yaml
asr:
  model_size: large-v3        # Whisper 模型：tiny/base/small/medium/large-v3
  device: cuda                # 设备：cuda (GPU) / cpu
  compute_type: float16       # 精度：float16 (GPU) / int8_float16 (CPU)
  vad_filter: true            # 是否启用静音检测
  language: zh                # 语言代码
```

**性能对比**：
- `large-v3` + GPU：准确率最高，速度快
- `medium` + GPU：平衡选择
- `base` + CPU：速度慢但可用

### 摘要器配置

```yaml
summarizer:
  base_url: "http://localhost:11434/v1"  # API 地址
  api_key: "ollama"                       # API Key
  model: "qwen2.5:7b-instruct-q4_0"      # 模型名称
  map_max_tokens: 1000                    # Map 阶段最大 token
  reduce_max_tokens: 1800                 # Reduce 阶段最大 token
  temperature: 0.3                        # 生成温度（0-1）
```

### 分块配置

```yaml
chunking:
  target_chars: 1400          # 每块目标字符数
  overlap_chars: 80           # 块间重叠字符数
```

### 微信公众号配置

```yaml
wechat:
  title_prefix: "42章经精选｜"                      # 标题前缀
  cover_image: "https://example.com/cover.jpg"      # 封面 URL
  author: "AI 播客助手"                             # 作者名
  accent_color: "#d92b2b"                           # 主色调
  quote_color: "#666"                               # 引文颜色
  highlight_color: "#c0392b"                        # 金句边框色
```

## 微信公众号使用

1. 用浏览器打开 `outputs/summary_wechat.html`
2. 全选页面内容（Ctrl+A / Cmd+A）
3. 复制（Ctrl+C / Cmd+C）
4. 粘贴到微信公众号后台编辑器

**自动包含**：
- 红色标题线与主色调
- 灰色引文块（带边框）
- 红框高亮金句区块
- 时间戳小灰字样式
- 自动目录与分隔线

## 常见问题

### 1. Whisper 模型下载慢

首次运行会自动下载 Whisper 模型（约 3GB），如下载慢：

```bash
# 手动下载（可使用代理）
huggingface-cli download openai/whisper-large-v3
```

### 2. 无 GPU 环境

修改 `config.yaml`：

```yaml
asr:
  device: cpu
  compute_type: int8_float16
  model_size: base  # 使用较小模型加速
```

### 3. LLM 服务连接失败

检查服务是否运行：

```bash
# Ollama
curl http://localhost:11434/v1/models

# 确保 base_url 和 model 配置正确
```

### 4. 转写结果为空

- 检查音频文件是否损坏
- 确认 ffmpeg 正常工作：`ffmpeg -version`
- 查看 `audio/*_16k.wav` 是否生成

### 5. 摘要质量不佳

- 尝试更大的模型（如 13B、70B）
- 调整 `temperature`（降低获得更稳定输出）
- 增大 `map_max_tokens` 和 `reduce_max_tokens`

### 6. 时间戳越界警告

这是正常的质检提醒，通常因为：
- LLM 生成的时间戳不准确
- 可手动编辑 `outputs/summary.md` 修正

## 性能参考

**测试环境**：
- CPU: Apple M2 Max
- GPU: NVIDIA RTX 4090
- 音频: 60 分钟中文播客

**处理时间**：
1. 音频预处理：~10 秒
2. 语音转写（large-v3 + GPU）：~5 分钟
3. 分块与 Map 摘要（10 chunks）：~3 分钟
4. Reduce 与质检：~1 分钟
5. 生成 HTML：~5 秒

**总计**：约 10 分钟

## 扩展与定制

### 自定义摘要提示词

编辑脚本中的 `MAP_PROMPT_TEMPLATE` 和 `REDUCE_PROMPT_TEMPLATE`。

### 调整 HTML 样式

修改 `generate_wechat_html.py` 中的 CSS 样式。

### 支持其他语言

修改 `config.yaml` 中的 `asr.language`（如 `en`、`ja`）。

### 批量处理

```bash
for audio in audio/*.m4a; do
    make run AUDIO="$audio"
done
```

## 许可证

MIT License

## 致谢

- [faster-whisper](https://github.com/guillaumekln/faster-whisper) - 高效 Whisper 实现
- [Ollama](https://ollama.com/) - 本地 LLM 服务
- [OpenAI](https://openai.com/) - API 接口标准

## 问题反馈

如有问题或建议，请通过以下方式反馈：
- 提交 GitHub Issue
- 邮件联系项目维护者

---

**祝使用愉快！**
