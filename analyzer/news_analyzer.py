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
    策略：找 "Query:" 标记取其后内容；fallback时跳过初始化日志行
    """
    # 去除ANSI转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean = ansi_escape.sub('', raw_output)

    # 去除braille unicode空白
    clean = re.sub(r'[\u2800-\u28FF]', '', clean)

    # 找 Query: 标记，取其后的所有内容
    match = re.search(r'Query:\s*使用SKILL:', clean)
    if match:
        content = clean[match.end():]
    else:
        content = clean

    # 统一过滤：应用skip_patterns去除初始化日志和工具准备行
    lines = content.split('\n')
    filtered = []
    skip_patterns = [
        r'^Initializing agent',
        r'^.*\s+[📚🔎⚕]\s',  # log lines with emoji prefix
        r'^\s*┊',  # pipe prefix log lines
        r'^\s*─{3,}\s*$',  # separator lines
        r'^\s*[╭╮╰│─╯]\s*$',  # box drawing
    ]
    for line in lines:
        stripped = line.strip()
        if any(re.search(p, line) for p in skip_patterns):
            continue
        # Skip tool/skill list lines (short lines with : but no Chinese)
        if re.match(r'^\s+\w+:\s', stripped) and not re.search(r'[\u4e00-\u9fff]', stripped):
            continue
        # Skip lines that are just paths
        if re.match(r'^\s*/home/|^\s*~/', stripped):
            continue
        # Skip session/metadata lines
        if re.match(r'^(Session:|Duration:|Messages:|Resume this)', stripped):
            break
        filtered.append(line)
    content = '\n'.join(filtered)

    # 去除session尾部
    result_lines = []
    for line in content.split('\n'):
        stripped = line.strip()
        if re.match(r'^(Resume this session|Session:|Duration:|Messages:)', stripped):
            break
        result_lines.append(line)

    content = '\n'.join(result_lines).strip()
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