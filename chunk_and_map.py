#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分块与 Map 摘要脚本
功能：将转写文本分块，并对每块调用 LLM 生成结构化摘要
"""

import json
from pathlib import Path
from contextlib import ExitStack

import httpx
import yaml
from openai import OpenAI


MAP_PROMPT_TEMPLATE = """你是中文播客速记与事实型总结助手。仅依据【文本】输出结构化结果，禁止臆测。

要求：
1) 本段标题（≤12字）
2) 本段要点（5-8条；要"事实+观点"）
3) 关键引文（原句；附出现的时间范围，如[12:31-12:50]）
4) 名词/人名/公司（中英对照；若无则空）
5) 若出现问答，请用"问：/答："列出

【文本】
{text}

请以如下格式输出：

## 标题
[本段标题]

## 要点
- [要点1]
- [要点2]
- [要点3]
...

## 关键引文
> "[引文内容]" [时间范围]

## 名词术语
- [中文名]（[英文名]）
- ...

## 问答（如有）
问：[问题]
答：[回答]
"""


def load_config():
    """加载配置文件"""
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_transcript():
    """加载转写结果"""
    transcript_path = Path("outputs/transcript.json")
    if not transcript_path.exists():
        raise FileNotFoundError("未找到 outputs/transcript.json，请先运行 transcribe.py")

    with open(transcript_path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_time(seconds: float) -> str:
    """将秒数转换为 MM:SS 格式"""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def create_chunks(transcript: dict, target_chars: int, overlap_chars: int) -> list:
    """
    将转写结果分块

    Args:
        transcript: 转写结果字典
        target_chars: 目标字符数
        overlap_chars: 重叠字符数

    Returns:
        分块列表，每块包含 {id, text, start_time, end_time, segment_ids}
    """
    segments = transcript["segments"]
    chunks = []
    current_chunk = {
        "text": "",
        "start_time": 0,
        "end_time": 0,
        "segment_ids": []
    }

    print(f"[分块] 目标大小: {target_chars} 字符，重叠: {overlap_chars} 字符")

    for seg in segments:
        # 如果当前 chunk 为空，初始化起始时间
        if not current_chunk["text"]:
            current_chunk["start_time"] = seg["start"]

        current_chunk["text"] += seg["text"]
        current_chunk["end_time"] = seg["end"]
        current_chunk["segment_ids"].append(seg["id"])

        # 检查是否达到目标大小
        if len(current_chunk["text"]) >= target_chars:
            chunks.append(current_chunk.copy())
            print(f"  Chunk {len(chunks)}: {len(current_chunk['text'])} 字符, "
                  f"{format_time(current_chunk['start_time'])} - {format_time(current_chunk['end_time'])}")

            # 创建新 chunk，保留重叠部分
            overlap_text = current_chunk["text"][-overlap_chars:] if overlap_chars > 0 else ""
            current_chunk = {
                "text": overlap_text,
                "start_time": seg["end"],
                "end_time": seg["end"],
                "segment_ids": []
            }

    # 添加最后一个 chunk
    if current_chunk["text"].strip():
        chunks.append(current_chunk)
        print(f"  Chunk {len(chunks)}: {len(current_chunk['text'])} 字符, "
              f"{format_time(current_chunk['start_time'])} - {format_time(current_chunk['end_time'])}")

    print(f"\n  总计: {len(chunks)} 个块")
    return chunks


def summarize_chunk(client: OpenAI, chunk: dict, chunk_id: int, config: dict) -> dict:
    """
    对单个 chunk 生成摘要

    Args:
        client: OpenAI 客户端
        chunk: 分块数据
        chunk_id: 块 ID
        config: 配置字典

    Returns:
        摘要结果
    """
    summarizer_config = config["summarizer"]

    # 添加时间信息到文本中
    time_range = f"[{format_time(chunk['start_time'])} - {format_time(chunk['end_time'])}]"
    text_with_time = f"{time_range}\n\n{chunk['text']}"

    prompt = MAP_PROMPT_TEMPLATE.format(text=text_with_time)

    print(f"\n[Map {chunk_id+1}] 生成摘要 ({len(chunk['text'])} 字符)...")

    try:
        response = client.chat.completions.create(
            model=summarizer_config["model"],
            messages=[
                {"role": "system", "content": "你是专业的播客内容分析助手。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=summarizer_config["map_max_tokens"],
            temperature=summarizer_config.get("temperature", 0.3),
            timeout=summarizer_config.get("timeout", 120)
        )

        summary_text = response.choices[0].message.content.strip()

        result = {
            "chunk_id": chunk_id,
            "time_range": time_range,
            "start_time": chunk["start_time"],
            "end_time": chunk["end_time"],
            "char_count": len(chunk["text"]),
            "summary": summary_text
        }

        # 显示摘要预览
        lines = summary_text.split("\n")
        preview = "\n".join(lines[:5])
        print(f"  生成成功 (预览):\n{preview}\n  ...")

        return result

    except Exception as e:
        print(f"  ✗ 生成失败: {e}")
        return {
            "chunk_id": chunk_id,
            "time_range": time_range,
            "start_time": chunk["start_time"],
            "end_time": chunk["end_time"],
            "char_count": len(chunk["text"]),
            "summary": f"[摘要生成失败: {str(e)}]",
            "error": str(e)
        }


def save_map_results(maps: list):
    """保存 Map 结果"""
    # 保存 JSON
    maps_json_path = Path("outputs/maps.json")
    with open(maps_json_path, "w", encoding="utf-8") as f:
        json.dump(maps, f, ensure_ascii=False, indent=2)
    print(f"\n[保存] Map 汇总: {maps_json_path}")

    # 保存每个 chunk 的 Markdown
    chunks_dir = Path("outputs/chunks")
    chunks_dir.mkdir(parents=True, exist_ok=True)

    for map_result in maps:
        chunk_file = chunks_dir / f"chunk_{map_result['chunk_id']:03d}.md"
        content = f"# Chunk {map_result['chunk_id']} - {map_result['time_range']}\n\n"
        content += f"字符数: {map_result['char_count']}\n\n"
        content += "---\n\n"
        content += map_result['summary']

        with open(chunk_file, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"[保存] 分块摘要: {chunks_dir}/ ({len(maps)} 个文件)")


def main():
    try:
        print("=" * 60)
        print("分块与 Map 摘要")
        print("=" * 60)

        # 加载配置和转写结果
        config = load_config()
        transcript = load_transcript()

        # 创建分块
        chunks = create_chunks(
            transcript,
            config["chunking"]["target_chars"],
            config["chunking"]["overlap_chars"]
        )

        # 初始化 OpenAI 客户端
        summarizer_config = config["summarizer"]
        http_client_kwargs = {
            "base_url": summarizer_config["base_url"],
            "timeout": summarizer_config.get("timeout", 120),
            "follow_redirects": True
        }
        proxy_url = (
            summarizer_config.get("proxy")
            or summarizer_config.get("http_proxy")
            or summarizer_config.get("https_proxy")
        )
        if proxy_url:
            http_client_kwargs["proxy"] = proxy_url

        maps = []
        with ExitStack() as stack:
            http_client = stack.enter_context(httpx.Client(**http_client_kwargs))
            client = stack.enter_context(
                OpenAI(
                    base_url=summarizer_config["base_url"],
                    api_key=summarizer_config["api_key"],
                    http_client=http_client
                )
            )

            print(f"\n[连接] LLM 服务: {summarizer_config['base_url']}")
            print(f"  模型: {summarizer_config['model']}")
            if proxy_url:
                print(f"  代理: {proxy_url}")

            # 对每个 chunk 生成摘要
            for i, chunk in enumerate(chunks):
                map_result = summarize_chunk(client, chunk, i, config)
                maps.append(map_result)

        # 保存结果
        save_map_results(maps)

        # 统计
        success_count = sum(1 for m in maps if "error" not in m)
        print(f"\n{'=' * 60}")
        print(f"✓ Map 阶段完成")
        print(f"  成功: {success_count}/{len(maps)}")
        print(f"  下一步: python reduce_and_qc.py")
        print(f"{'=' * 60}")

    except Exception as e:
        print(f"\n✗ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
