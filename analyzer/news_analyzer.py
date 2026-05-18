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
    去除：ANSI转义、UI框线、braille空白字符、工具列表、session尾部
    """
    # 去除ANSI转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean = ansi_escape.sub('', raw_output)

    # 去除所有braille pattern unicode (U+2800-U+28FF)
    clean = re.sub(r'[\u2800-\u28FF]', '', clean)

    # 去除Box Drawing和Block Elements字符
    clean = re.sub(r'[\u2500-\u257F]', '', clean)  # ─ │ etc.

    lines = clean.split('\n')
    filtered = []

    for line in lines:
        stripped = line.strip()

        # 遇到session尾部，停止
        if re.match(r'^(Resume this session|Session:|Duration:|Messages:)', stripped):
            break

        # 跳过包含 "Tools" "Skills" 标题的行（工具列表区）
        if re.match(r'^Available (Tools|Skills)$', stripped):
            continue

        # 跳过包含 "· Nous Research" 的行（头部横幅）
        if re.search(r'·\s*Nous Research', stripped):
            continue

        # 跳过工具/技能引用行（如 "browser: xxx" 或 "creative: xxx"）
        if re.match(r'^\s+\w+:\s', stripped):
            continue

        # 跳过 "(and \d+ more...)" 行
        if re.match(r'^\s*\(and \d+ more\.\.\.\)', stripped):
            continue

        # 跳过初始化的agent头部横幅行（短行，包含路径）
        if re.match(r'^.*(/home/.*\.md|Session:.*)', stripped):
            continue

        # 跳过空行
        if not stripped:
            continue

        filtered.append(line)

    content = '\n'.join(filtered).strip()

    # 去除多余空行
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