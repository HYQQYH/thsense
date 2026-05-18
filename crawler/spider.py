from cloakbrowser import launch

# 实际选择器（来自 probe.py 探针结果）
SELECTORS = {
    "container": "ul.newsText.all",
    "item": "li.stock_",
    "title": ".newsDetail a strong",
    "time": ".newsTimer",
    "source": "",  # 页面未提供 source 字段
    "url": ".newsDetail a",
    "content": ".newsDetail a"
}

def fetch_today_news() -> list[dict]:
    """
    爬取同花顺实时新闻
    返回: [{"title": ..., "time": ..., "source": ..., "url": ..., "content": ...}, ...]
    """
    browser = launch()
    page = browser.new_page()
    page.goto("https://news.10jqka.com.cn/realtimenews.html")
    page.wait_for_selector(SELECTORS["container"])

    items = page.query_selector_all(SELECTORS["item"])
    news_list = []

    for item in items:
        try:
            news = {
                "title": item.query_selector(SELECTORS["title"]).inner_text(),
                "time": item.query_selector(SELECTORS["time"]).inner_text(),
                "source": "同花顺",  # 默认值
                "url": item.query_selector(SELECTORS["url"]).get_attribute("href"),
                "content": item.query_selector(SELECTORS["content"]).inner_text(),
            }
            news_list.append(news)
        except Exception:
            continue

    browser.close()
    return news_list


if __name__ == "__main__":
    news = fetch_today_news()
    print(f"Fetched {len(news)} news")
    for n in news:
        print(n)