import subprocess
import json
import os
import time
from pathlib import Path
from datetime import datetime

SKILL_NAME = "financial-news-analysis"

def analyze_news(news_items: list[dict], date: str, max_retries: int = 3, retry_intervals: list = None) -> str:
    """
    调用 hermes-agent + SKILL.md 对新闻进行深度分析
    返回: 分析报告路径
    """
    if retry_intervals is None:
        retry_intervals = [30, 60, 120]

    # 确保输出目录存在
    report_dir = Path("reports") / date
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "analysis.md"

    # 构造查询内容：新闻列表拼接成字符串
    news_text = "\n".join([
        f"【新闻{i+1}】\n标题：{n.get('title','')}\n时间：{n.get('time','')}\n内容：{n.get('content','')}"
        for i, n in enumerate(news_items)
    ])

    query = f"使用SKILL:{SKILL_NAME}分析如下财经新闻：\n{news_text}"

    for attempt, wait_time in enumerate([0] + retry_intervals[:max_retries]):
        if attempt > 0:
            time.sleep(wait_time)

        try:
            # hermes chat -q "使用SKILL:financial-news-analysis分析如下财经新闻xxxx"
            cmd = [
                "hermes", "chat",
                "-q", query
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10分钟超时
            )

            if result.returncode == 0:
                # 输出写入报告文件
                report_path.write_text(result.stdout, encoding='utf-8')
                return str(report_path)
            else:
                raise RuntimeError(f"hermes-agent failed: {result.stderr}")

        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Analysis failed after {max_retries} retries: {e}")

    return str(report_path)