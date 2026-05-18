"""
DOM 结构探针脚本 - 一次性使用
运行后会打印同花顺页面实际 DOM 结构，用于确认选择器

选择器发现结果 (2026-05-18):
- 列表容器: ul.newsText.all
- 新闻项: li.stock_
- 时间: .newsTimer (span 包含时间文本如 "12:02")
- 标题: .newsDetail a strong
- 描述: .newsDetail a (除 strong 外的文本)
- 链接: .newsDetail a href
"""
import asyncio
from playwright.async_api import async_playwright

async def probe():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://news.10jqka.com.cn/realtimenews.html")

        await page.wait_for_load_state("networkidle")

        title = await page.title()
        print(f"Page title: {title}")

        # 找到 news 列表
        news_list = await page.query_selector("ul.newsText.all")
        if news_list:
            items = await news_list.query_selector_all("li.stock_")
            print(f"\nFound {len(items)} li.stock_ items")

            if items:
                # 打印第一个 item 的完整结构
                first_html = await items[0].inner_html()
                print(f"\nFirst item HTML:\n{first_html}")

                # 提取各个部分
                timer = await items[0].query_selector(".newsTimer")
                if timer:
                    timer_text = await timer.inner_text()
                    print(f"\n.newsTimer: {timer_text}")

                detail = await items[0].query_selector(".newsDetail")
                if detail:
                    detail_html = await detail.inner_html()
                    print(f"\n.newsDetail HTML: {detail_html[:300]}")

                    # 提取链接和标题
                    link = await detail.query_selector("a")
                    if link:
                        href = await link.get_attribute("href")
                        link_text = await link.inner_text()
                        print(f"\nLink href: {href}")
                        print(f"Link text: {link_text}")

                # 尝试 class="setLink"
                setlink = await items[0].query_selector(".setLink")
                if setlink:
                    print(f"\n.setLink exists")

        # 统计总共多少条
        all_items = await page.query_selector_all("li.stock_")
        print(f"\nTotal li.stock_ on page: {len(all_items)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(probe())