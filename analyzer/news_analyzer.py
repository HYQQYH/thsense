import subprocess
import json
import os
import re
import time
from pathlib import Path
from datetime import datetime

SKILL_NAME = "financial-news-analysis"

def sanitize_filename(name: str) -> str:
    """将新闻标题转为合法的文件名"""
    name = re.sub(r'[【】\[\]（）()\s/\\\\]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name[:80]
    return name.strip('_')

def extract_analysis_content(raw_output: str) -> str:
    """
    从 hermes-agent 输出中提取纯分析内容
    策略：找到 "Query:" 标记，保留其后的所有内容，去除session尾部
    """
    # 去除ANSI转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean = ansi_escape.sub('', raw_output)

    # 去除braille unicode空白
    clean = re.sub(r'[\u2800-\u28FF]', '', clean)

    # 找 Query: 标记，取其后的所有内容
    match = re.search(r'Query:\s*使用SKILL:', clean)
    if not match:
        # 兜底：去掉头部元信息，保留后半部分
        lines = clean.split('\n')
        # 找到第一个包含实际分析内容的行（中文）
        start_idx = 0
        for i, line in enumerate(lines):
            # 跳过明显的工具列表和元信息行
            if any(kw in line for kw in ['browser:', 'clarify:', 'cronjob:', 'delegation:', 'file:', 'hermes-yuanbao:', 'creative:', 'devops:', 'data-science:', 'github:', 'mcp:', 'media:', 'mlops:', 'note-taking:', 'productivity:', 'research:', 'smart-home:', 'social-media:', 'software-development:']):
                continue
            # 跳过路径行
            if re.match(r'^\s*/home/|^\s*~/', line):
                continue
            # 跳过Session/Messages/Duration行
            if re.match(r'^(Session:|Duration:|Messages:|Resume this)', line.strip()):
                continue
            # 跳过纯装饰行
            if re.match(r'^\s*[╭╮╰│─╯╰╭]\s*$', line):
                continue
            # 如果有中文内容，认为是正文开始
            if re.search(r'[\u4e00-\u9fff]', line):
                start_idx = i
                break

        content = '\n'.join(lines[start_idx:])
    else:
        # 取Query之后的所有内容
        content = clean[match.end():]

    # 去除session尾部
    lines = content.split('\n')
    filtered = []
    for line in lines:
        stripped = line.strip()
        if re.match(r'^(Resume this session|Session:|Duration:|Messages:)', stripped):
            break
        filtered.append(line)

    content = '\n'.join(filtered).strip()

    # 清理多余空行
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content


def analyze_single_news(news_item: dict, date: str, max_retries: int = 3) -> str:
    """
    单独分析一条新闻，返回报告文件路径
    """
    retry_intervals = [30, 60, 120]

    report_dir = Path("reports") / date
    report_dir.mkdir(parents=True, exist_ok=True)

    title = news_item.get('title', 'untitled')
    filename = sanitize_filename(title) + ".md"
    report_path = report_dir / filename

    news_text = f"标题：{title}\n时间：{news_item.get('time','')}\n内容：{news_item.get('content','')}"
    query = f"使用SKILL:{SKILL_NAME}分析如下财经新闻：\n{news_text}"

    for attempt, wait_time in enumerate([0] + retry_intervals[:max_retries]):
        if attempt > 0:
            time.sleep(wait_time)

        try:
            cmd = ["hermes", "chat", "-q", query]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode == 0:
                clean_content = extract_analysis_content(result.stdout)
                report_path.write_text(clean_content, encoding='utf-8')
                return str(report_path)
            else:
                raise RuntimeError(f"hermes-agent failed: {result.stderr}")

        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Analysis failed after {max_retries} retries: {e}")

    return str(report_path)


def analyze_news(news_items: list[dict], date: str) -> list[str]:
    """
    逐条分析新闻，每条生成一个md文件
    返回: 报告文件路径列表
    """
    results = []
    for item in news_items:
        print(f'  分析: {item.get("title", "")[:50]}...')
        try:
            path = analyze_single_news(item, date)
            results.append(path)
        except Exception as e:
            print(f'  失败: {e}')
    return results