#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频预处理脚本
功能：将输入的 .m4a 音频文件转换为 16kHz 单声道 WAV 格式，便于后续 ASR 处理
"""

import sys
import subprocess
from pathlib import Path


def convert_audio(input_path: str) -> str:
    """
    使用 ffmpeg 将音频转换为 16kHz 单声道 WAV

    Args:
        input_path: 输入音频文件路径

    Returns:
        输出 WAV 文件路径
    """
    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(f"输入文件不存在: {input_path}")

    # 生成输出文件名：原文件名_16k.wav
    output_file = input_file.parent / f"{input_file.stem}_16k.wav"

    print(f"[准备] 输入文件: {input_file}")
    print(f"[准备] 输出文件: {output_file}")

    # ffmpeg 命令：转为单声道 16kHz WAV
    cmd = [
        "ffmpeg",
        "-i", str(input_file),
        "-ar", "16000",           # 采样率 16kHz
        "-ac", "1",               # 单声道
        "-c:a", "pcm_s16le",      # PCM 16-bit 编码
        "-y",                     # 覆盖已存在的文件
        str(output_file)
    ]

    print(f"[执行] {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"[完成] 音频转换成功: {output_file}")
        return str(output_file)

    except subprocess.CalledProcessError as e:
        print(f"[错误] ffmpeg 执行失败:")
        print(f"  stdout: {e.stdout}")
        print(f"  stderr: {e.stderr}")
        raise
    except FileNotFoundError:
        print("[错误] 未找到 ffmpeg，请先安装:")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu: sudo apt install ffmpeg")
        print("  Windows: 下载 https://ffmpeg.org/download.html")
        raise


def main():
    if len(sys.argv) < 2:
        print("用法: python prep_audio.py <音频文件路径>")
        print("示例: python prep_audio.py audio/demo.m4a")
        sys.exit(1)

    input_audio = sys.argv[1]

    try:
        output_wav = convert_audio(input_audio)
        print(f"\n✓ 预处理完成: {output_wav}")
        print(f"  下一步可执行: python transcribe.py {output_wav}")

    except Exception as e:
        print(f"\n✗ 处理失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
