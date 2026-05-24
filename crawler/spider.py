import asyncio
from cloakbrowser import launch_async

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

async def _fetch_today_news_async() -> list[dict]:
    """
    爬取同花顺实时新闻
    返回: [{"title": ..., "time": ..., "source": ..., "url": ..., "content": ...}, ...]
    """
    browser = await launch_async(proxy=None)
    page = await browser.new_page()
    await page.goto("https://news.10jqka.com.cn/realtimenews.html")
    await page.wait_for_selector(SELECTORS["container"])

    items = await page.query_selector_all(SELECTORS["item"])
    news_list = []

    for item in items:
        try:
            news = {
                "title": await item.query_selector(SELECTORS["title"]).inner_text(),
                "time": await item.query_selector(SELECTORS["time"]).inner_text(),
                "source": "同花顺",  # 默认值
                "url": await item.query_selector(SELECTORS["url"]).get_attribute("href"),
                "content": await item.query_selector(SELECTORS["content"]).inner_text(),
            }
            news_list.append(news)
        except Exception:
            continue

    await browser.close()
    return news_list

def fetch_today_news() -> list[dict]:
    """同步入口，供 scheduler 调用"""
    return asyncio.run(_fetch_today_news_async())


if __name__ == "__main__":
    news = fetch_today_news()
    print(f"Fetched {len(news)} news")
    for n in news:
        print(n)