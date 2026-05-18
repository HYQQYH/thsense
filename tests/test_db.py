import pytest
import os
from db.sqlite_client import SQLiteClient

@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    client = SQLiteClient(str(db_path))
    yield client
    client.close()

def test_insert_raw_news(client):
    news = [{
        "title": "测试新闻",
        "time": "2026-05-18 10:00",
        "source": "同花顺",
        "url": "https://example.com/1",
        "content": "测试内容"
    }]
    client.insert_raw_news(news)
    rows = client.get_all_raw_news()
    assert len(rows) == 1
    assert rows[0]["title"] == "测试新闻"

def test_duplicate_url_skipped(client):
    news = [{
        "title": "新闻1",
        "time": "2026-05-18 10:00",
        "source": "同花顺",
        "url": "https://example.com/1",
        "content": "内容1"
    }]
    client.insert_raw_news(news)
    # 相同 url 再插入应被跳过
    client.insert_raw_news(news)
    rows = client.get_all_raw_news()
    assert len(rows) == 1