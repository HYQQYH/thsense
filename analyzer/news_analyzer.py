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
    # 去除【】等特殊括号，替换空格和路径分隔符
    name = re.sub(r'[【】\[\]（）()\s/\\\\]', '_', name)
    name = re.sub(r'_+', '_', name)
    name = name[:80]  # 限制长度
    return name.strip('_')

def extract_analysis_content(raw_output: str) -> str:
    """
    从 hermes-agent 输出中提取纯分析内容
    - 去除终端UI框线（╭╮╰等字符）
    - 去除ANSI转义序列
    - 只保留Query之后的内容
    """
    # 去除ANSI转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean = ansi_escape.sub('', raw_output)

    # 去除终端UI框线字符（╭╮╰│─等）
    clean = re.sub(r'[╭╮╰│─]', '', clean)

    # 找到 Query: 之后的实际内容
    match = re.search(r'Query:\s*使用SKILL:.*?\n+(.*)$', clean, re.DOTALL)
    if match:
        content = match.group(1).strip()
    else:
        # fallback: 去掉开头的工具列表等元信息，找到实际内容
        lines = clean.split('\n')
        content_lines = []
        capture = False
        for line in lines:
            # Skip lines that look like tool/skill listings
            if re.match(r'^\s*[⠀\s]+', line) and '·' not in line:
                continue
            if line.strip().startswith('Query:'):
                capture = True
                continue
            if capture or any(kw in line for kw in ['分析', '影响', '市场', '利润', '财报', '公司']):
                content_lines.append(line)
        content = '\n'.join(content_lines).strip()

    # 去除多余空行
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content


def analyze_single_news(news_item: dict, date: str, max_retries: int = 3) -> str:
    """
    单独分析一条新闻，返回报告文件路径
    """
    retry_intervals = [30, 60, 120]

    # 确保输出目录存在
    report_dir = Path("reports") / date
    report_dir.mkdir(parents=True, exist_ok=True)

    # 构造文件名
    title = news_item.get('title', 'untitled')
    filename = sanitize_filename(title) + ".md"
    report_path = report_dir / filename

    # 构造查询内容
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
                # 提取纯分析内容，去除UI冗余
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