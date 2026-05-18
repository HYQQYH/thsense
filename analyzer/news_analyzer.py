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
    策略：找 "╭─ ⚕ Hermes ─" 标记（⚕ emoji），提取其后的内容到 "╰─" 边框行之前
    """
    # 去除ANSI转义序列
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean = ansi_escape.sub('', raw_output)

    # 去除braille unicode空白
    clean = re.sub(r'[\u2800-\u28FF]', '', clean)

    # 找包含 ⚕ 的行作为起始边界
    # 模式: ╭─ 后跟空格、⚕、空格、Hermes、空格、─
    start_match = re.search(r'╭─\s*⚕\s*Hermes\s*─', clean)

    if start_match:
        # 内容从该行换行后开始
        start_pos = clean.find('\n', start_match.end())
        if start_pos < 0:
            start_pos = start_match.end()
        else:
            start_pos += 1  # 跳过换行符

        # 找结束标记 ╰─ (在 start_pos 之后)
        end_match = re.search(r'\n╰[─\s]', clean[start_pos:])
        if end_match:
            content = clean[start_pos:start_pos + end_match.start()]
        else:
            # 没有找到边框结束，取到session前
            session_pos = clean.find('Session:', start_pos)
            if session_pos > 0:
                content = clean[start_pos:session_pos]
            else:
                content = clean[start_pos:]
    else:
        # Fallback: 找顶部边框行 ╮ 之后的内容（分析内容开始）
        # 框线行模式: 多个 ─ 后跟 ╮
        border_match = re.search(r'\n([─]+╮)\s*\n', clean)
        if border_match:
            content = clean[border_match.end():]
            # 去掉结束边框行
            end_match = re.search(r'\n[─]+╯', content)
            if end_match:
                content = content[:end_match.start()]
        else:
            content = clean

    # 清理多余空行
    content = re.sub(r'\n{3,}', '\n\n', content)
    return content.strip()


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