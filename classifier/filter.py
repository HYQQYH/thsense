import anthropic
import json
import time
import os
from typing import Optional

SYSTEM_PROMPT = """你是一个财经新闻分类助手。根据以下分类体系，判断每条新闻是否属于"影响型财经新闻"。

## 分类体系

### 0.1 核心影响类型（高确定性利润/收入影响）

| 影响类型 | 特征描述 | 利润/收入影响逻辑 |
|---------|---------|-----------------|
| **需求爆发** | 下游客户数量激增、订单爆发、政策强制替换 | 营收直接拉高，量价齐升 |
| **供给短缺** | 产能受限、原材料紧张、许可证限制 | 已有订单的利润率提升 |
| **价格大幅上涨** | 供需缺口、关税、汇率、成本推动 | 毛利率改善，弹性巨大 |
| **重大技术革新** | 新一代产品/工艺/材料替代旧技术 | 市场份额重新分配，先发优势者胜 |
| **重大产品迭代** | 终端产品重大升级、新品发布 | 带动整个供应链业绩释放 |

### 0.2 扩展影响类型（影响经营环境但需进一步判断）

| 影响类型 | 特征描述 | 利润/收入影响逻辑 |
|---------|---------|-----------------|
| **政策/监管变动** | 行业准入放松/收紧、加税/减税、补贴取消/新增、关税调整 | 直接影响成本结构和竞争格局 |
| **竞争格局重塑** | 龙头对手破产/退出、重大并购、联盟形成、价格战 | 市场份额重新分配，赢家通吃 |
| **大订单/合同得失** | 获得或失去核心客户、数亿级以上合同 | 营收直接可预测，业绩确定性提升或下降 |
| **产能扩张/收缩** | 新建工厂、停产限产、设备更新 | 未来供给能力的前瞻指标 |
| **管理层重大变动** | CEO/CFO更换、核心技术人员离职、实控人变更 | 战略方向不确定性或新活力注入 |
| **诉讼/监管调查** | 重大集体诉讼、监管机构调查、处罚决定 | 潜在巨额赔偿、牌照吊销风险 |
| **信用评级调整** | 评级机构下调/上调展望、列入观察名单 | 发债成本、融资能力直接受影响 |
| **宏观数据超预期** | GDP/CPI/PMI等经济数据大幅偏离预期 | 系统性机会/风险，影响所有资产 |
| **ESG/黑天鹅事件** | 重大安全事故、环境污染、高管丑闻 | 估值重塑，永久性品牌损害 |

## 判定规则

- 符合上述任意类型（包括 0.1 和 0.2）的新闻 → 保留
- 不属于上述任何类型的新闻（如：一般性行业动态、泛泛的市场分析、与经营无关的宏观新闻） → 过滤
- 返回保留新闻的索引列表，格式为JSON数组

## 输出格式

只返回符合条件新闻的索引数组，例如：[0, 3, 5]
如无符合条件新闻，返回空数组：[]"""

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