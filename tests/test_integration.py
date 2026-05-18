import pytest
from unittest.mock import patch
from db.sqlite_client import SQLiteClient
import tempfile
import os

def test_full_pipeline(tmp_path):
    """模拟完整流程：插入新闻 → 分类 → 分析标记"""
    db_path = tmp_path / "test.db"
    db = SQLiteClient(str(db_path))

    # 1. 插入原始新闻
    news = [{
        "title": "A股大涨",
        "time": "2026-05-18 10:00",
        "source": "同花顺",
        "url": "https://example.com/1",
        "content": "今日A股大涨"
    }]
    db.insert_raw_news(news)
    assert len(db.get_all_raw_news()) == 1

    # 2. 获取待分类
    pending = db.get_unclassified_news()
    assert len(pending) == 1

    # 3. 模拟分类（直接插入 classified）
    db.insert_classified_news([pending[0]["id"]], ["财经"])

    # 4. 获取待分析
    to_analyze = db.get_pending_analysis()
    assert len(to_analyze) == 1

    # 5. 模拟分析完成
    db.mark_analyzed(to_analyze[0]["id"], "reports/2026-05-18/analysis.md")

    # 6. 验证状态更新
    analyzed = db.get_pending_analysis()
    assert len(analyzed) == 0

    db.close()