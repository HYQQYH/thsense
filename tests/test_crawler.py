import pytest
from unittest.mock import patch, MagicMock


def test_fetch_today_news_returns_list():
    mock_page_instance = MagicMock()
    mock_page_instance.query_selector_all.return_value = []

    with patch("cloakbrowser.launch") as mock_launch:
        mock_browser_instance = MagicMock()
        mock_launch.return_value = mock_browser_instance
        mock_browser_instance.new_page.return_value = mock_page_instance

        from crawler.spider import fetch_today_news
        result = fetch_today_news()
        assert isinstance(result, list)