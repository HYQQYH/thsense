import pytest
from unittest.mock import patch, MagicMock
from classifier.filter import classify_news

def test_classify_news_returns_indices():
    news = [
        {"title": "A股大涨", "time": "2026-05-18", "source": "同花顺", "url": "https://example.com/1", "content": "内容1"},
        {"title": "天气晴朗", "time": "2026-05-18", "source": "同花顺", "url": "https://example.com/2", "content": "内容2"},
        {"title": "央行降准", "time": "2026-05-18", "source": "同花顺", "url": "https://example.com/3", "content": "内容3"},
    ]

    mock_response = MagicMock()
    mock_response.content = [MagicMock(type="text", text="[0, 2]")]

    with patch("anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = mock_response
        result = classify_news(news, criteria="财经新闻")
        assert result == [0, 2]