# 财经新闻分析智能体 — 技术设计文档

## 1. 项目概述

**项目名称**：财经新闻分析智能体（Financial News Analyzer Agent）
**项目目标**：从同花顺 7×24 小时新闻源自动抓取财经新闻，通过 LLM 分类过滤后，使用 SKILL 框架进行深度分析，输出 Markdown 格式的分析报告。
**输出形式**：Markdown 报告，按日期归类到 `reports/YYYY-MM-DD/analysis.md`

---

## 2. 整体架构

```
同花顺 7x24新闻 (https://news.10jqka.com.cn/realtimenews.html)
    ↓ [CloakBrowser 爬虫]
原始新闻库 (SQLite: raw_news 表)
    ↓ [MiniMax-M2.7 LLM API 分类过滤]
分类后新闻库 (SQLite: classified_news 表)
    ↓ [hermes-agent + SKILL.md 深度分析]
Markdown 分析报告 (reports/YYYY-MM-DD/analysis.md)
```

### 模块列表

| 模块 | 目录 | 职责 |
|------|------|------|
| 爬虫模块 | `crawler/` | CloakBrowser 驱动抓取同花顺新闻 |
| 分类模块 | `classifier/` | MiniMax-M2.7 LLM 分类过滤 |
| 分析模块 | `analyzer/` | hermes-agent + SKILL.md 深度分析 |
| 调度模块 | `scheduler/` | 定时任务调度 |
| 数据层 | `db/` | SQLite 存储 |
| 报告输出 | `reports/` | Markdown 报告，按日期归类 |

---

## 3. 数据存储设计

### 数据库：SQLite（`data/news.db`）

```sql
-- 原始新闻表
CREATE TABLE raw_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    time TEXT NOT NULL,
    source TEXT,
    url TEXT UNIQUE,
    content TEXT,
    raw_status TEXT DEFAULT 'new',  -- new | classified
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_raw_status ON raw_news(raw_status);
CREATE INDEX idx_raw_time ON raw_news(time);

-- 分类后新闻表
CREATE TABLE classified_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER REFERENCES raw_news(id),
    category TEXT,
    status TEXT DEFAULT 'pending',  -- pending | analyzed | filtered | error
    analysis_report TEXT,
    analyzed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_classified_status ON classified_news(status);
CREATE INDEX idx_classified_raw_id ON classified_news(raw_id);
```

**设计说明**：
- `url` 作为唯一约束，避免重复爬取
- `raw_status` 标记原始新闻是否已处理
- `classified_news.status`：`pending` = 待分析，`analyzed` = 已分析，`filtered` = 不符合条件，`error` = 失败

---

## 4. 爬虫模块设计（crawler/）

**目标 URL**：`https://news.10jqka.com.cn/realtimenews.html`

**依赖**：
```bash
pip install cloakbrowser
```

**核心逻辑**：

```python
# crawler/spider.py
from cloakbrowser import launch

def fetch_today_news() -> list[dict]:
    browser = launch()
    page = browser.new_page()
    page.goto("https://news.10jqka.com.cn/realtimenews.html")
    page.wait_for_selector(".news-list")
    items = page.query_selector_all(".news-item")
    news_list = []
    for item in items:
        news_list.append({
            "title": item.query_selector(".title").inner_text(),
            "time": item.query_selector(".time").inner_text(),
            "source": item.query_selector(".source").inner_text(),
            "url": item.query_selector("a").get_attribute("href"),
            "content": item.query_selector(".desc").inner_text()
        })
    browser.close()
    return news_list
```

**关键行为**：
- 动态渲染页面，等待 `.news-list` 加载完成后再提取
- 增量爬取：以 `url` 为主键，已存在则跳过
- 每次爬取更新 `raw_status: 'new'`
- 实际 DOM 结构需要探针脚本确认（见下文"待确认事项"）

**探针脚本**（待实现后运行一次确认结构）：
```python
# crawler/probe.py
# 访问页面，打印 DOM 结构，确认选择器
```

---

## 5. 分类模块设计（classifier/）

**依赖**：
```bash
pip install anthropic
```

**调用 MiniMax-M2.7**：

```python
# classifier/filter.py
import anthropic
import json

SYSTEM_PROMPT = """你是一个财经新闻分类助手。根据用户的分类条件，从新闻列表中筛选出符合条件的新闻。只返回符合条件的新闻索引列表，格式为JSON数组。"""

def classify_news(news_items: list[dict], criteria: str) -> list[int]:
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="MiniMax-M2.7",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"分类条件：{criteria}\n\n新闻列表：{json.dumps(news_items, ensure_ascii=False)}\n\n请返回符合条件的新闻索引列表（JSON数组），例如：[0, 3, 5]"
                }
            ]
        }]
    )
    for block in response.content:
        if block.type == "text":
            return json.loads(block.text)
    return []
```

**关键行为**：
- 每个批次最多处理 50 条新闻
- 分类条件 `criteria` 从 `config.yaml` 读取
- 不符合条件的新闻标记 `status: 'filtered'`，不删除
- 失败重试：最多 3 次，间隔 10s/30s/60s

---

## 6. 分析模块设计（analyzer/）

**依赖**：hermes-agent（外部，已存在）

```python
# analyzer/news_analyzer.py
import subprocess
import json
from datetime import datetime

SKILL_PATH = "skills/financial-news-analysis/SKILL.md"

def analyze_news(news_items: list[dict], date: str) -> str:
    context = {
        "date": date,
        "news_count": len(news_items),
        "news": news_items
    }

    # 调用 hermes-agent 执行分析
    cmd = [
        "hermes", "analyze",
        "--skill", SKILL_PATH,
        "--context", json.dumps(context, ensure_ascii=False),
        "--output", f"reports/{date}/analysis.md"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Analysis failed: {result.stderr}")

    return f"reports/{date}/analysis.md"
```

**关键行为**：
- 报告输出到 `reports/{date}/analysis.md`
- 分析完成后更新 `classified_news.status: 'analyzed'`
- 失败重试：最多 3 次，间隔 30s/60s/120s
- hermes-agent 调用方式待确认（见"待确认事项"）

---

## 7. 调度模块设计（scheduler/）

**依赖**：
```bash
pip install schedule
```

```python
# scheduler/runner.py
import schedule, time
from datetime import datetime
from crawler.spider import fetch_today_news
from classifier.filter import classify_news
from analyzer.news_analyzer import analyze_news
from db import sqlite_client

# 配置
CRITERIA = sqlite_client.get_config("classifier_criteria")

def job():
    # 1. 爬取最新新闻
    news = fetch_today_news()
    sqlite_client.insert_raw_news(news)

    # 2. 分类过滤
    pending = sqlite_client.get_unclassified_news()
    if pending:
        classified = classify_news(pending, criteria=CRITERIA)
        sqlite_client.update_classified_news(classified)

    # 3. 深度分析
    to_analyze = sqlite_client.get_pending_analysis()
    if to_analyze:
        date = datetime.now().strftime("%Y-%m-%d")
        analyze_news(to_analyze, date)

schedule.every(30).minutes.do(job)
while True:
    schedule.run_pending()
    time.sleep(1)
```

---

## 8. 异常处理与重试机制

| 模块 | 失败动作 | 重试策略 |
|------|---------|---------|
| 爬虫 | 记录日志，跳过本次 | 30分钟后下次调度自动重试 |
| LLM分类 | 重试3次，间隔10s/30s/60s | 仍失败标记 `status: 'error'` |
| 分析 | 重试3次，间隔30s/60s/120s | 仍失败标记 `status: 'error'` |

- 所有模块写日志到 `logs/` 目录
- 断点续传：通过 `status` 字段控制，失败记录保留供下次重试

---

## 9. 目录结构

```
thsense/
├── crawler/
│   ├── __init__.py
│   ├── spider.py       # CloakBrowser 爬虫
│   └── probe.py        # DOM 结构探针（一次性使用）
├── classifier/
│   ├── __init__.py
│   └── filter.py       # MiniMax-M2.7 分类
├── analyzer/
│   ├── __init__.py
│   └── news_analyzer.py  # hermes-agent 调用
├── scheduler/
│   ├── __init__.py
│   └── runner.py       # 定时调度
├── db/
│   ├── __init__.py
│   └── sqlite_client.py
├── skills/
│   └── financial-news-analysis/
│       └── SKILL.md    # 深度分析框架（用户编写）
├── reports/            # 输出目录
│   └── YYYY-MM-DD/
│       └── analysis.md
├── config.yaml          # 分类条件等配置
├── data/                # SQLite 数据库目录
├── logs/                # 日志目录
└── main.py              # 入口
```

---

## 10. 待确认事项

1. **CloakBrowser 实际 DOM 结构**：需要运行 `crawler/probe.py` 确认同花顺页面的新闻列表 CSS 选择器
2. **hermes-agent 调用方式**：`analyzer/news_analyzer.py` 中的调用方式需要与 hermes-agent 实际接口对齐后调整
3. **SKILL.md 内容**：深度分析的框架由用户提供，需确认输入输出格式
4. **分类条件 prompt 模板**：是否需要 Few-shot 示例来提升分类准确率

---

## 11. 实现顺序

1. 配置项和数据层（`config.yaml`、`db/`）
2. 爬虫探针脚本 → 确认 DOM 结构 → 爬虫完整实现
3. 分类模块（LLM 调用 + 重试）
4. 分析模块（hermes-agent 调用，待确认）
5. 调度模块串联
6. 端到端测试

---

*文档版本：2026-05-18*