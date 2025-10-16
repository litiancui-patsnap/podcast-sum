#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
转写进度查看脚本
"""

import os
import sys
import json
from pathlib import Path

def check_progress():
    """检查转写进度"""

    print("=" * 60)
    print("转写进度检查")
    print("=" * 60)

    # 检查输出目录
    output_dir = Path("outputs")
    if not output_dir.exists():
        print("\n[X] outputs 目录不存在，转写可能还未开始")
        return

    # 检查转写结果文件
    transcript_file = output_dir / "transcript.json"
    if not transcript_file.exists():
        print("\n[进行中] 转写进行中...")
        print("   transcript.json 尚未生成")
        print("   这可能需要较长时间，请耐心等待")
    else:
        # 读取并显示转写结果信息
        try:
            with open(transcript_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            print("\n[完成] 转写已完成！")
            print(f"   语言: {data.get('language', 'N/A')}")
            print(f"   时长: {data.get('duration', 0):.2f} 秒 ({data.get('duration', 0)/60:.1f} 分钟)")
            print(f"   片段数: {len(data.get('segments', []))}")

            # 显示前几个片段
            segments = data.get('segments', [])
            if segments:
                print("\n前 3 个片段预览:")
                for seg in segments[:3]:
                    print(f"   [{seg.get('start', 0):.2f}s] {seg.get('text', '')[:60]}...")

            print(f"\n[结果] 完整结果保存在: {transcript_file}")
            print("\n下一步:")
            print("   python chunk_and_map.py")

        except Exception as e:
            print(f"\n[警告] 读取转写文件时出错: {e}")

    # 检查日志文件
    log_file = Path("transcribe.log")
    if log_file.exists():
        print(f"\n[日志] 日志文件: {log_file}")
        print("   查看日志: cat transcribe.log")

        # 显示最后几行日志
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                if lines:
                    print("\n最近的日志 (最后 5 行):")
                    for line in lines[-5:]:
                        print(f"   {line.rstrip()}")
        except Exception as e:
            print(f"   读取日志失败: {e}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    check_progress()
