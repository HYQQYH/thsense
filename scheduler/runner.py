import schedule
import time
import yaml
import logging
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/runner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)

def job():
    """定时任务：爬取 → 分类 → 分析"""
    logger.info("=== Starting scheduled job ===")
    config = load_config()

    try:
        # 1. 爬取最新新闻
        from crawler import fetch_today_news
        from db import SQLiteClient

        db = SQLiteClient(config["database"]["path"])

        logger.info("Fetching news...")
        news = fetch_today_news()
        if news:
            db.insert_raw_news(news)
            logger.info(f"Inserted {len(news)} news items")
        else:
            logger.warning("No news fetched")

        # 2. 分类过滤
        logger.info("Classifying news...")
        pending = db.get_unclassified_news()
        if pending:
            from classifier import classify_news
            criteria = config["classifier"]["criteria"]
            matched_indices = classify_news(pending, criteria)
            # 更新 classified_news
            for idx in matched_indices:
                db.insert_classified_news([pending[idx]["id"]], ["财经"])
            # 标记已分类
            db.mark_raw_news_classified([pending[idx]["id"] for idx in matched_indices])
            logger.info(f"Matched {len(matched_indices)} news items")

        # # 3. 深度分析（逐条）
        # logger.info("Analyzing news...")
        # to_analyze = db.get_pending_analysis()
        # if to_analyze:
        #     from analyzer import analyze_news
        #     date = datetime.now().strftime("%Y-%m-%d")
        #     report_paths = analyze_news(to_analyze, date)
        #     for i, item in enumerate(to_analyze):
        #         path = report_paths[i] if i < len(report_paths) else ""
        #         db.mark_analyzed(item["id"], path)
        #     logger.info(f"Analysis complete: {len(report_paths)} reports")

        db.close()
        logger.info("=== Job complete ===\n")

    except Exception as e:
        logger.error(f"Job failed: {e}", exc_info=True)


def start_scheduler():
    config = load_config()
    interval = config["crawler"]["interval_minutes"]

    schedule.every(interval).minutes.do(job)
    logger.info(f"Scheduler started, running every {interval} minutes")

    # 立即执行一次
    job()

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    start_scheduler()
