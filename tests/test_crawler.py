import pytest
from unittest.mock import patch, MagicMock
from crawler.spider import fetch_today_news

@pytest.fixture
def mock_page():
    mock_page_instance = MagicMock()
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page_instance
    mock_page_instance.query_selector_all.return_value = []
    return mock_page_instance

def test_fetch_today_news_returns_list(mock_page):
    with patch("crawler.spider.launch") as mock_launch:
        mock_launch.return_value.new_page.return_value = mock_page
        result = fetch_today_news()
        assert isinstance(result, list)