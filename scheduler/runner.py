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

def fetch_news_job():
    """定时任务：爬取最新新闻"""
    logger.info("=== Starting fetch news job ===")
    config = load_config()

    try:
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

        db.close()
        logger.info("=== Fetch job complete ===\n")

    except Exception as e:
        logger.error(f"Fetch job failed: {e}", exc_info=True)


def classify_job():
    """定时任务：分类过滤"""
    logger.info("=== Starting classify job ===")
    config = load_config()

    try:
        from db import SQLiteClient

        db = SQLiteClient(config["database"]["path"])

        # 分类过滤
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
        else:
            logger.info("No pending news to classify")

        db.close()
        logger.info("=== Classify job complete ===\n")

    except Exception as e:
        logger.error(f"Classify job failed: {e}", exc_info=True)


def start_scheduler():
    # 爬取新闻：每5分钟执行一次
    schedule.every(5).minutes.do(fetch_news_job)
    logger.info("Scheduler started, fetch news every 5 minutes")

    # 分类过滤：每半小时执行一次
    schedule.every(30).minutes.do(classify_job)
    logger.info("Scheduler started, classify every 30 minutes")

    # 立即各执行一次
    fetch_news_job()
    classify_job()

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    start_scheduler()
