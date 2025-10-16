#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音转写脚本
功能：使用 faster-whisper 将音频转写为带时间戳的文本
"""

import sys
import json
from pathlib import Path
import yaml
from faster_whisper import WhisperModel


def load_config():
    """加载配置文件"""
    config_path = Path("config.yaml")
    if not config_path.exists():
        raise FileNotFoundError("未找到 config.yaml 配置文件")

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def transcribe_audio(audio_path: str, config: dict) -> dict:
    """
    转写音频文件

    Args:
        audio_path: WAV 音频文件路径
        config: 配置字典

    Returns:
        转写结果字典
    """
    audio_file = Path(audio_path)

    if not audio_file.exists():
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    asr_config = config["asr"]

    # 确定使用本地模型还是在线模型
    model_path = asr_config.get("model_path")
    if model_path and Path(model_path).exists():
        model_source = model_path
        print(f"[加载] Whisper 模型（本地）: {model_path}")
    else:
        model_source = asr_config["model_size"]
        print(f"[加载] Whisper 模型: {asr_config['model_size']}")
        if model_path:
            print(f"  警告：指定的本地模型路径不存在，将尝试在线下载")

    print(f"  设备: {asr_config['device']}")
    print(f"  计算类型: {asr_config['compute_type']}")

    # 初始化 Whisper 模型
    model = WhisperModel(
        model_size_or_path=model_source,
        device=asr_config["device"],
        compute_type=asr_config["compute_type"],
        download_root="models"  # 指定下载目录
    )

    print(f"\n[转写] 处理文件: {audio_file.name}")
    print("  这可能需要几分钟，请耐心等待...")

    # 执行转写
    segments, info = model.transcribe(
        str(audio_file),
        language=asr_config.get("language", "zh"),
        vad_filter=asr_config.get("vad_filter", True),
        beam_size=5
    )

    print(f"\n[检测] 语言: {info.language}")
    print(f"  时长: {info.duration:.2f} 秒")

    # 构建结果
    result = {
        "language": info.language,
        "duration": round(info.duration, 2),
        "segments": []
    }

    # 收集所有片段
    print("\n[收集] 转写片段:")
    for seg in segments:
        segment_data = {
            "id": seg.id,
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip()
        }
        result["segments"].append(segment_data)

        # 显示前 5 条和最后 1 条
        if seg.id < 5 or seg.id == result["segments"][-1]["id"]:
            print(f"  [{seg.id}] {seg.start:.2f}s - {seg.end:.2f}s: {seg.text[:50]}...")
        elif seg.id == 5:
            print("  ...")

    print(f"\n  共 {len(result['segments'])} 个片段")

    return result


def save_transcript(transcript: dict, output_path: str):
    """保存转写结果"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)

    print(f"\n[保存] 转写结果: {output_file}")


def main():
    if len(sys.argv) < 2:
        print("用法: python transcribe.py <WAV音频文件>")
        print("示例: python transcribe.py audio/demo_16k.wav")
        sys.exit(1)

    audio_path = sys.argv[1]

    try:
        # 加载配置
        config = load_config()

        # 执行转写
        transcript = transcribe_audio(audio_path, config)

        # 保存结果
        output_path = "outputs/transcript.json"
        save_transcript(transcript, output_path)

        print(f"\n[OK] 转写完成")
        print(f"  总时长: {transcript['duration']:.2f} 秒 ({transcript['duration']/60:.1f} 分钟)")
        print(f"  片段数: {len(transcript['segments'])}")
        print(f"  下一步: python chunk_and_map.py")

    except Exception as e:
        print(f"\n[ERROR] 转写失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
