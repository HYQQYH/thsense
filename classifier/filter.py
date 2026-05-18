import anthropic
import json
import time
import os
from typing import Optional

SYSTEM_PROMPT = """你是一个财经新闻分类助手。根据用户的分类条件，从新闻列表中筛选出符合条件的新闻。只返回符合条件的新闻索引列表，格式为JSON数组。"""

def classify_news(news_items: list[dict], criteria: str, max_retries: int = 3, retry_intervals: list = None) -> list[int]:
    """
    调用 MiniMax-M2.7 对新闻进行分类过滤
    返回: 符合条件的新闻索引列表
    """
    if retry_intervals is None:
        retry_intervals = [10, 30, 60]

    client = anthropic.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY", "")
    )

    batch_size = 50
    all_matched = []

    for i in range(0, len(news_items), batch_size):
        batch = news_items[i:i + batch_size]

        for attempt, wait_time in enumerate([0] + retry_intervals[:max_retries]):
            if attempt > 0:
                time.sleep(wait_time)

            try:
                response = client.messages.create(
                    model="MiniMax-M2.7",
                    max_tokens=1000,
                    system=SYSTEM_PROMPT,
                    messages=[{
                        "role": "user",
                        "content": [{
                            "type": "text",
                            "text": f"分类条件：{criteria}\n\n新闻列表：{json.dumps(batch, ensure_ascii=False)}\n\n请返回符合条件的新闻索引列表（JSON数组），例如：[0, 3, 5]"
                        }]
                    }]
                )

                for block in response.content:
                    if block.type == "text":
                        indices = json.loads(block.text)
                        # 偏移量修正（因为是分批处理）
                        all_matched.extend([idx + i for idx in indices])
                        break
                break

            except Exception as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"LLM classification failed after {max_retries} retries: {e}")

    return all_matched