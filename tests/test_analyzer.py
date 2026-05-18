import pytest
from unittest.mock import patch, MagicMock
from analyzer.news_analyzer import analyze_news

def test_analyze_news_returns_report_path(tmp_path):
    news = [{"title": "测试新闻", "time": "2026-05-18", "source": "同花顺", "url": "https://example.com/1", "content": "内容"}]

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        with patch("analyzer.news_analyzer.SKILL_PATH", "skills/SKILL.md"):
            result = analyze_news(news, "2026-05-18")
            assert result == "reports/2026-05-18/analysis.md"
            mock_run.assert_called_once()