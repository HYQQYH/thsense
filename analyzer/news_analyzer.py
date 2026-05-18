import subprocess
import json
import os
import time
from pathlib import Path

SKILL_PATH = "skills/financial-news-analysis/SKILL.md"

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

    context = {
        "date": date,
        "news_count": len(news_items),
        "news": news_items
    }

    for attempt, wait_time in enumerate([0] + retry_intervals[:max_retries]):
        if attempt > 0:
            time.sleep(wait_time)

        try:
            # TODO: hermes-agent 调用方式待确认后调整
            cmd = [
                "hermes", "analyze",
                "--skill", SKILL_PATH,
                "--context", json.dumps(context, ensure_ascii=False),
                "--output", str(report_dir / "analysis.md")
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                return str(report_dir / "analysis.md")
            else:
                raise RuntimeError(f"hermes-agent failed: {result.stderr}")

        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Analysis failed after {max_retries} retries: {e}")

    return str(report_dir / "analysis.md")