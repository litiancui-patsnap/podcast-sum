#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成微信公众号 HTML 脚本
功能：将摘要转换为可直接粘贴到公众号后台的格式化 HTML
"""

import re
from pathlib import Path
import yaml
import markdown2
from bs4 import BeautifulSoup


def load_config():
    """加载配置文件"""
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_summary():
    """加载摘要文件"""
    summary_path = Path("outputs/summary.md")
    if not summary_path.exists():
        raise FileNotFoundError("未找到 outputs/summary.md，请先运行 reduce_and_qc.py")

    return summary_path.read_text(encoding="utf-8")


def extract_quotes(md_text: str) -> list:
    """
    提取金句（引文中长度适中且有感染力的句子）

    Args:
        md_text: Markdown 文本

    Returns:
        金句列表
    """
    quotes = []

    # 提取引用块中的内容
    blockquote_pattern = r'> ["\"](.{15,100}?)["\"]'
    matches = re.findall(blockquote_pattern, md_text)

    for match in matches:
        # 过滤：包含感叹号、问号或重要关键词
        if any(char in match for char in ['！', '？', '。']) or \
           any(keyword in match for keyword in ['关键', '重要', '核心', '本质', '启示']):
            quotes.append(match.strip())

    # 去重并限制数量
    quotes = list(dict.fromkeys(quotes))[:5]

    return quotes


def enhance_html(html: str, config: dict) -> BeautifulSoup:
    """
    增强 HTML 样式

    Args:
        html: 原始 HTML
        config: 配置字典

    Returns:
        增强后的 BeautifulSoup 对象
    """
    soup = BeautifulSoup(html, "html.parser")
    wechat_config = config["wechat"]

    # 美化引用块
    for blockquote in soup.find_all("blockquote"):
        blockquote["style"] = (
            f"border-left: 3px solid {wechat_config['quote_color']}; "
            f"padding-left: 12px; "
            f"color: {wechat_config['quote_color']}; "
            f"font-style: italic; "
            f"margin: 1em 0; "
            f"background-color: #f9f9f9; "
            f"padding: 10px 12px; "
            f"border-radius: 4px;"
        )

    # 美化时间戳
    for text_node in soup.find_all(string=re.compile(r'\[\d{1,2}:\d{2}')):
        # 查找包含时间戳的文本节点
        text = str(text_node)
        new_html = re.sub(
            r'(\[\d{1,2}:\d{2}(?::\d{2})?\])',
            r'<span style="color:#888;font-size:0.85em;font-family:monospace;">\1</span>',
            text
        )
        if new_html != text:
            new_soup = BeautifulSoup(new_html, "html.parser")
            text_node.replace_with(new_soup)

    # 美化列表
    for ul in soup.find_all("ul"):
        ul["style"] = "line-height: 1.8; margin: 0.5em 0;"

    for ol in soup.find_all("ol"):
        ol["style"] = "line-height: 1.8; margin: 0.5em 0;"

    return soup


def generate_quote_blocks(quotes: list, config: dict) -> str:
    """
    生成金句区块 HTML

    Args:
        quotes: 金句列表
        config: 配置字典

    Returns:
        金句 HTML 字符串
    """
    if not quotes:
        return ""

    wechat_config = config["wechat"]
    highlight_color = wechat_config["highlight_color"]

    html = '<div style="margin: 2em 0;">\n'
    html += '<h2 style="border-left: 4px solid {0}; padding-left: 8px; margin-bottom: 1em;">💬 金句精选</h2>\n'.format(
        wechat_config["accent_color"]
    )

    for quote in quotes:
        html += (
            f'<div style="'
            f'border: 2px solid {highlight_color}; '
            f'padding: 16px; '
            f'margin: 12px 0; '
            f'border-radius: 8px; '
            f'font-size: 1.1em; '
            f'line-height: 1.6; '
            f'text-align: center; '
            f'background-color: #fff9f9;'
            f'">'
            f'"{quote}"'
            f'</div>\n'
        )

    html += '</div>\n'

    return html


def generate_wechat_html(md_text: str, config: dict) -> str:
    """
    生成完整的微信公众号 HTML

    Args:
        md_text: Markdown 文本
        config: 配置字典

    Returns:
        完整 HTML 字符串
    """
    wechat_config = config["wechat"]

    # 提取标题（第一个 # 标题）
    title_match = re.search(r'^# (.+)$', md_text, re.MULTILINE)
    if title_match:
        raw_title = title_match.group(1).strip()
        # 移除标题行，避免重复
        md_text = md_text.replace(title_match.group(0), '', 1)
    else:
        raw_title = "播客总结"

    title = f"{wechat_config['title_prefix']}{raw_title}"

    # 转换 Markdown 到 HTML
    html = markdown2.markdown(md_text, extras=["tables", "fenced-code-blocks"])

    # 增强样式
    soup = enhance_html(html, config)

    # 提取金句
    print("[金句] 检测中...")
    quotes = extract_quotes(md_text)
    print(f"  发现 {len(quotes)} 条金句")

    # 生成金句区块
    quote_blocks = generate_quote_blocks(quotes, config)

    # 生成封面
    cover_html = ""
    if wechat_config.get("cover_image"):
        cover_html = (
            f'<p style="text-align: center;">'
            f'<img src="{wechat_config["cover_image"]}" '
            f'alt="cover" '
            f'style="width: 100%; max-width: 600px; border-radius: 8px; margin: 1em 0;" />'
            f'</p>\n'
        )

    # CSS 样式
    accent_color = wechat_config["accent_color"]
    style = f"""
<style>
body {{
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
    line-height: 1.8;
    color: #333;
    padding: 20px;
    max-width: 800px;
    margin: 0 auto;
    background-color: #fff;
}}

h1 {{
    font-size: 1.8em;
    color: #222;
    border-left: 5px solid {accent_color};
    padding-left: 12px;
    margin: 1em 0 0.5em 0;
    line-height: 1.4;
}}

h2 {{
    font-size: 1.4em;
    color: #333;
    border-left: 4px solid {accent_color};
    padding-left: 10px;
    margin-top: 1.5em;
    margin-bottom: 0.8em;
}}

h3 {{
    font-size: 1.2em;
    color: #444;
    border-left: 3px solid {accent_color};
    padding-left: 8px;
    margin-top: 1.2em;
    margin-bottom: 0.6em;
}}

p {{
    margin: 0.8em 0;
    text-align: justify;
}}

strong {{
    color: {accent_color};
    font-weight: 600;
}}

em {{
    font-style: italic;
    color: #555;
}}

a {{
    color: {accent_color};
    text-decoration: none;
    border-bottom: 1px solid {accent_color};
}}

.separator {{
    border-top: 1px solid #e0e0e0;
    margin: 2em 0;
}}

.author {{
    color: #888;
    font-size: 0.9em;
    margin-bottom: 1em;
}}

.footer {{
    text-align: center;
    color: #999;
    font-size: 0.9em;
    margin-top: 3em;
    padding-top: 1em;
    border-top: 1px solid #eee;
}}
</style>
"""

    # 组装完整 HTML
    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {style}
</head>
<body>

<h1>{title}</h1>
<p class="author">作者：{wechat_config.get('author', 'AI 播客助手')}</p>

{cover_html}

<div class="separator"></div>

{quote_blocks}

{soup.prettify()}

<div class="footer">
    <p>—— 完 ——</p>
    <p style="font-size: 0.85em; color: #aaa;">本文由 AI 自动生成，内容基于播客音频转写</p>
</div>

</body>
</html>
"""

    return full_html


def main():
    try:
        print("=" * 60)
        print("生成微信公众号 HTML")
        print("=" * 60)

        # 加载配置和摘要
        config = load_config()
        md_text = load_summary()

        print(f"\n[加载] 摘要长度: {len(md_text)} 字符")

        # 生成 HTML
        print("[生成] 转换为 HTML...")
        html = generate_wechat_html(md_text, config)

        # 保存
        output_path = Path("outputs/summary_wechat.html")
        output_path.write_text(html, encoding="utf-8")

        print(f"\n[保存] 微信 HTML: {output_path}")
        print(f"  文件大小: {len(html)} 字符")

        # 提示
        print(f"\n{'=' * 60}")
        print("✓ HTML 生成完成")
        print("\n使用方法：")
        print("  1. 用浏览器打开 outputs/summary_wechat.html")
        print("  2. 全选页面内容 (Ctrl+A / Cmd+A)")
        print("  3. 复制 (Ctrl+C / Cmd+C)")
        print("  4. 粘贴到微信公众号后台编辑器")
        print(f"{'=' * 60}")

    except Exception as e:
        print(f"\n✗ 生成失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
