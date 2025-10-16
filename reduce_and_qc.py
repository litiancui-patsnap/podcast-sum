#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reduce 与质检脚本
功能：整合 Map 结果，生成完整摘要并进行时间戳质检
"""

import sys
import os

# 设置控制台输出编码为 UTF-8
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

import json
from pathlib import Path
from contextlib import ExitStack

import httpx
import yaml
import re
from openai import OpenAI


REDUCE_PROMPT_TEMPLATE = """下面是若干分段总结，请整合为对整期播客的**全量覆盖**总结：

要求输出以下结构：

# 播客总结

## 一屏速览（3-5点）
- [核心观点1]
- [核心观点2]
- ...

## 时间轴目录
- [00:00-05:30] [章节标题1]
- [05:31-15:20] [章节标题2]
- ...

## 深度要点
### [主题1]
- [详细要点]
  > "[关键原话]" [时间戳]
- [详细要点]
  ...

### [主题2]
- ...

## 结论/启示/行动建议
- [结论1]
- [建议1]
- ...

## 人名/组织/术语表
- **[中文名]**（[英文]）- [首次出现时间] - [简短说明]
- ...

---

注意：
1. 严禁编造内容，所有信息必须来自分段总结
2. 引用原话时必须保留时间戳
3. 若信息不确定，标注"待核对"
4. 时间轴应覆盖整期播客，不遗漏重要章节

【分段总结】
{maps}
"""


def load_config():
    """加载配置文件"""
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_maps():
    """加载 Map 结果"""
    maps_path = Path("outputs/maps.json")
    if not maps_path.exists():
        raise FileNotFoundError("未找到 outputs/maps.json，请先运行 chunk_and_map.py")

    with open(maps_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_transcript():
    """加载转写结果（用于质检）"""
    transcript_path = Path("outputs/transcript.json")
    with open(transcript_path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_maps_for_reduce(maps: list) -> str:
    """将 Map 结果格式化为 Reduce 输入"""
    formatted = ""
    for m in maps:
        formatted += f"\n## Chunk {m['chunk_id']} {m['time_range']}\n\n"
        formatted += m['summary']
        formatted += "\n\n" + "="*60 + "\n"
    return formatted


def generate_reduce_summary(client: OpenAI, maps: list, config: dict) -> str:
    """
    生成 Reduce 摘要

    Args:
        client: OpenAI 客户端
        maps: Map 结果列表
        config: 配置字典

    Returns:
        完整摘要文本
    """
    summarizer_config = config["summarizer"]

    maps_text = format_maps_for_reduce(maps)
    prompt = REDUCE_PROMPT_TEMPLATE.format(maps=maps_text)

    print(f"[Reduce] 整合 {len(maps)} 个分段摘要...")
    print(f"  输入长度: {len(prompt)} 字符")

    try:
        # Reduce 阶段需要更长的超时时间
        reduce_timeout = summarizer_config.get("reduce_timeout", 300)  # 默认 5 分钟
        print(f"  等待 LLM 响应（超时: {reduce_timeout}s）...")

        response = client.chat.completions.create(
            model=summarizer_config["model"],
            messages=[
                {"role": "system", "content": "你是专业的播客内容整合分析助手。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=summarizer_config["reduce_max_tokens"],
            temperature=summarizer_config.get("temperature", 0.3),
            timeout=reduce_timeout
        )

        summary = response.choices[0].message.content.strip()
        print(f"  ✓ 生成成功 ({len(summary)} 字符)")

        return summary

    except Exception as e:
        print(f"  ✗ 生成失败: {e}")
        raise


def quality_check_timestamps(summary: str, transcript: dict) -> list:
    """
    质检时间戳是否越界

    Args:
        summary: 摘要文本
        transcript: 转写结果

    Returns:
        问题列表
    """
    duration = transcript["duration"]
    issues = []

    # 匹配时间戳格式：[MM:SS] 或 [HH:MM:SS]
    timestamp_pattern = r'\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]'
    matches = re.finditer(timestamp_pattern, summary)

    print(f"\n[质检] 检查时间戳（总时长 {duration:.2f}s）...")

    for match in matches:
        hours = int(match.group(1)) if match.group(3) else 0
        minutes = int(match.group(1)) if match.group(3) else int(match.group(1))
        seconds = int(match.group(2))

        # 计算总秒数
        if match.group(3):  # HH:MM:SS 格式
            total_seconds = hours * 3600 + minutes * 60 + int(match.group(3))
        else:  # MM:SS 格式
            total_seconds = minutes * 60 + seconds

        # 检查是否越界
        if total_seconds > duration:
            issue = f"时间戳 {match.group(0)} ({total_seconds}s) 超出音频时长 ({duration:.2f}s)"
            issues.append(issue)
            print(f"  ⚠ {issue}")

    if not issues:
        print("  ✓ 所有时间戳有效")

    return issues


def extract_structured_data(summary: str) -> dict:
    """
    从摘要中提取结构化数据

    Args:
        summary: 摘要文本

    Returns:
        结构化数据字典
    """
    data = {
        "quick_overview": [],
        "timeline": [],
        "key_points": {},
        "conclusions": [],
        "glossary": []
    }

    # 提取一屏速览
    overview_match = re.search(r'## 一屏速览.*?\n(.*?)(?=\n##|\Z)', summary, re.DOTALL)
    if overview_match:
        points = re.findall(r'[-*] (.+)', overview_match.group(1))
        data["quick_overview"] = points

    # 提取时间轴
    timeline_match = re.search(r'## 时间轴目录.*?\n(.*?)(?=\n##|\Z)', summary, re.DOTALL)
    if timeline_match:
        timeline_items = re.findall(r'[-*] \[([^\]]+)\] (.+)', timeline_match.group(1))
        data["timeline"] = [{"time": t[0], "title": t[1]} for t in timeline_items]

    # 提取深度要点（简化版）
    points_match = re.search(r'## 深度要点.*?\n(.*?)(?=\n## [^#]|\Z)', summary, re.DOTALL)
    if points_match:
        sections = re.findall(r'### (.+?)\n(.*?)(?=\n###|\Z)', points_match.group(1), re.DOTALL)
        for section_title, section_content in sections:
            points = re.findall(r'[-*] (.+)', section_content)
            data["key_points"][section_title] = points

    # 提取结论
    conclusion_match = re.search(r'## 结论/启示/行动建议.*?\n(.*?)(?=\n##|\Z)', summary, re.DOTALL)
    if conclusion_match:
        conclusions = re.findall(r'[-*] (.+)', conclusion_match.group(1))
        data["conclusions"] = conclusions

    # 提取术语表
    glossary_match = re.search(r'## 人名/组织/术语表.*?\n(.*?)(?=\n##|\Z)', summary, re.DOTALL)
    if glossary_match:
        terms = re.findall(r'[-*] \*\*([^*]+)\*\*[^-\n]*', glossary_match.group(1))
        data["glossary"] = terms

    return data


def save_results(summary: str, structured_data: dict, qc_issues: list):
    """保存结果"""
    outputs_dir = Path("outputs")

    # 保存 Markdown
    summary_md_path = outputs_dir / "summary.md"
    summary_with_qc = summary
    if qc_issues:
        summary_with_qc += "\n\n---\n\n## ⚠ 质检提醒\n\n"
        for issue in qc_issues:
            summary_with_qc += f"- {issue}\n"

    with open(summary_md_path, "w", encoding="utf-8") as f:
        f.write(summary_with_qc)
    print(f"\n[保存] 完整摘要: {summary_md_path}")

    # 保存结构化 JSON
    summary_json_path = outputs_dir / "summary.json"
    json_data = {
        "structured": structured_data,
        "qc_issues": qc_issues,
        "full_text": summary
    }
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"[保存] 结构化数据: {summary_json_path}")


def main():
    try:
        print("=" * 60)
        print("Reduce 与质检")
        print("=" * 60)

        # 加载数据
        config = load_config()
        maps = load_maps()
        transcript = load_transcript()

        # 初始化客户端
        summarizer_config = config["summarizer"]
        # Reduce 阶段需要更长的超时时间
        reduce_timeout = summarizer_config.get("reduce_timeout", 300)  # 默认 5 分钟
        http_client_kwargs = {
            "base_url": summarizer_config["base_url"],
            "timeout": reduce_timeout,
            "follow_redirects": True
        }
        proxy_url = (
            summarizer_config.get("proxy")
            or summarizer_config.get("http_proxy")
            or summarizer_config.get("https_proxy")
        )
        if proxy_url:
            http_client_kwargs["proxy"] = proxy_url

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

            # 生成 Reduce 摘要
            summary = generate_reduce_summary(client, maps, config)

            # 质检时间戳
            qc_issues = quality_check_timestamps(summary, transcript)

            # 提取结构化数据
            print("\n[提取] 结构化数据...")
            structured_data = extract_structured_data(summary)
            print(f"  速览点: {len(structured_data['quick_overview'])}")
            print(f"  时间轴: {len(structured_data['timeline'])} 项")
            print(f"  主题数: {len(structured_data['key_points'])}")
            print(f"  结论: {len(structured_data['conclusions'])}")
            print(f"  术语: {len(structured_data['glossary'])}")

            # 保存结果
            save_results(summary, structured_data, qc_issues)

        # 总结
        print(f"\n{'=' * 60}")
        print(f"✓ Reduce 阶段完成")
        if qc_issues:
            print(f"  ⚠ 发现 {len(qc_issues)} 个质检问题，已记录在摘要末尾")
        print(f"  下一步: python generate_wechat_html.py")
        print(f"{'=' * 60}")

    except Exception as e:
        print(f"\n✗ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
