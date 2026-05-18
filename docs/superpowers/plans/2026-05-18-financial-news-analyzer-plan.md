# 财经新闻分析智能体 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个定时爬取同花顺财经新闻、经 LLM 分类过滤后调用 SKILL 深度分析、输出 Markdown 报告的自动化智能体

**Architecture:** 采用模块化设计，SQLite 作为数据持久层，调度模块串联爬虫→分类→分析三阶段。hermes-agent 和 SKILL.md 的调用方式待探针脚本确认 DOM 结构后对齐。

**Tech Stack:** Python 3.11+, CloakBrowser, anthropic (MiniMax-M2.7), SQLite, schedule

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `config.yaml` | 分类条件 prompt、调度间隔、API key 等配置 |
| `main.py` | 程序入口 |
| `db/sqlite_client.py` | SQLite 封装：建表、增删改查 |
| `crawler/spider.py` | CloakBrowser 爬虫主逻辑 |
| `crawler/probe.py` | DOM 探针脚本（一次性） |
| `classifier/filter.py` | MiniMax-M2.7 LLM 分类过滤 |
| `analyzer/news_analyzer.py` | hermes-agent 调用封装 |
| `scheduler/runner.py` | 定时调度逻辑 |
| `tests/test_*.py` | 各模块单元测试 |

---

## Task 1: 项目初始化与配置层

**Files:**
- Create: `config.yaml`
- Create: `data/.gitkeep`
- Create: `logs/.gitkeep`
- Create: `reports/.gitkeep`

- [ ] **Step 1: 创建 `config.yaml`**

```yaml
thsense:
  news_url: "https://news.10jqka.com.cn/realtimenews.html"

crawler:
  interval_minutes: 30

classifier:
  model: "MiniMax-M2.7"
  criteria: "请筛选出与以下主题相关的财经新闻：A股市场动态、公司并购重组、宏观经济政策"
  batch_size: 50
  max_retries: 3
  retry_intervals: [10, 30, 60]

analyzer:
  skill_path: "skills/financial-news-analysis/SKILL.md"
  max_retries: 3
  retry_intervals: [30, 60, 120]

database:
  path: "data/news.db"

anthropic:
  api_key: "${ANTHROPIC_API_KEY}"  # 从环境变量读取
```

- [ ] **Step 2: 创建目录占位文件**

```bash
touch data/.gitkeep logs/.gitkeep reports/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add config.yaml data/.gitkeep logs/.gitkeep reports/.gitkeep
git commit -m "feat: 项目初始化，添加配置文件和目录结构"
```

---

## Task 2: 数据层（db/sqlite_client.py）

**Files:**
- Create: `db/__init__.py`
- Create: `db/sqlite_client.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: 创建 `db/__init__.py`**

```python
from .sqlite_client import SQLiteClient

__all__ = ["SQLiteClient"]
```

- [ ] **Step 2: 编写 `tests/test_db.py`**

```python
import pytest
import os
from db.sqlite_client import SQLiteClient

@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    client = SQLiteClient(str(db_path))
    yield client
    client.close()

def test_insert_raw_news(client):
    news = [{
        "title": "测试新闻",
        "time": "2026-05-18 10:00",
        "source": "同花顺",
        "url": "https://example.com/1",
        "content": "测试内容"
    }]
    client.insert_raw_news(news)
    rows = client.get_all_raw_news()
    assert len(rows) == 1
    assert rows[0]["title"] == "测试新闻"

def test_duplicate_url_skipped(client):
    news = [{
        "title": "新闻1",
        "time": "2026-05-18 10:00",
        "source": "同花顺",
        "url": "https://example.com/1",
        "content": "内容1"
    }]
    client.insert_raw_news(news)
    # 相同 url 再插入应被跳过
    client.insert_raw_news(news)
    rows = client.get_all_raw_news()
    assert len(rows) == 1
```

- [ ] **Step 3: 运行测试，确认失败（表不存在）**

```bash
pytest tests/test_db.py -v
# Expected: FAIL - no such table: raw_news
```

- [ ] **Step 4: 实现 `db/sqlite_client.py`**

```python
import sqlite3
from datetime import datetime
from typing import Optional

class SQLiteClient:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS raw_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                time TEXT NOT NULL,
                source TEXT,
                url TEXT UNIQUE,
                content TEXT,
                raw_status TEXT DEFAULT 'new',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_raw_status ON raw_news(raw_status);
            CREATE INDEX IF NOT EXISTS idx_raw_time ON raw_news(time);

            CREATE TABLE IF NOT EXISTS classified_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_id INTEGER REFERENCES raw_news(id),
                category TEXT,
                status TEXT DEFAULT 'pending',
                analysis_report TEXT,
                analyzed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_classified_status ON classified_news(status);
            CREATE INDEX IF NOT EXISTS idx_classified_raw_id ON classified_news(raw_id);
        """)
        self.conn.commit()

    def insert_raw_news(self, news_list: list[dict]):
        for news in news_list:
            try:
                self.conn.execute("""
                    INSERT INTO raw_news (title, time, source, url, content, raw_status)
                    VALUES (:title, :time, :source, :url, :content, 'new')
                """, news)
            except sqlite3.IntegrityError:
                pass  # url 重复，跳过
        self.conn.commit()

    def get_all_raw_news(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM raw_news").fetchall()
        return [dict(row) for row in rows]

    def get_unclassified_news(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT * FROM raw_news WHERE raw_status = 'new'
        """).fetchall()
        return [dict(row) for row in rows]

    def mark_raw_news_classified(self, ids: list[int]):
        if not ids:
            return
        placeholders = ",".join("?" * len(ids))
        self.conn.execute(f"""
            UPDATE raw_news SET raw_status = 'classified'
            WHERE id IN ({placeholders})
        """, ids)
        self.conn.commit()

    def insert_classified_news(self, raw_ids: list[int], categories: list[str]):
        for raw_id, category in zip(raw_ids, categories):
            self.conn.execute("""
                INSERT INTO classified_news (raw_id, category, status)
                VALUES (?, ?, 'pending')
            """, (raw_id, category))
        self.conn.commit()

    def get_pending_analysis(self) -> list[dict]:
        rows = self.conn.execute("""
            SELECT cn.*, rn.title, rn.time, rn.source, rn.url, rn.content
            FROM classified_news cn
            JOIN raw_news rn ON cn.raw_id = rn.id
            WHERE cn.status = 'pending'
        """).fetchall()
        return [dict(row) for row in rows]

    def mark_analyzed(self, classified_id: int, report_path: str):
        self.conn.execute("""
            UPDATE classified_news
            SET status = 'analyzed', analysis_report = ?, analyzed_at = ?
            WHERE id = ?
        """, (report_path, datetime.now().isoformat(), classified_id))
        self.conn.commit()

    def mark_error(self, classified_id: int):
        self.conn.execute("""
            UPDATE classified_news SET status = 'error' WHERE id = ?
        """, (classified_id,))
        self.conn.commit()

    def mark_filtered(self, classified_id: int):
        self.conn.execute("""
            UPDATE classified_news SET status = 'filtered' WHERE id = ?
        """, (classified_id,))
        self.conn.commit()

    def get_config(self, key: str) -> str:
        # 从 config.yaml 读取，暂用环境变量或默认值
        import os
        return os.environ.get(key.upper(), "")

    def close(self):
        self.conn.close()
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/test_db.py -v
# Expected: PASS
```

- [ ] **Step 6: Commit**

```bash
git add db/__init__.py db/sqlite_client.py tests/test_db.py
git commit -m "feat: 添加 SQLite 数据层封装"
```

---

## Task 3: 爬虫探针脚本（确认 DOM 结构）

**Files:**
- Create: `crawler/__init__.py`
- Create: `crawler/probe.py`

- [ ] **Step 1: 创建 `crawler/__init__.py`**

```python
from .spider import fetch_today_news

__all__ = ["fetch_today_news"]
```

- [ ] **Step 2: 创建 `crawler/probe.py`**

```python
"""
DOM 结构探针脚本 - 一次性使用
运行后会打印同花顺页面实际 DOM 结构，用于确认选择器
"""
import asyncio
from cloakbrowser import launch

async def probe():
    browser = await launch()
    page = await browser.new_page()
    await page.goto("https://news.10jqka.com.cn/realtimenews.html")

    # 等待页面加载
    await page.wait_for_load_state("networkidle")

    # 打印页面 title 确认访问成功
    title = await page.title()
    print(f"Page title: {title}")

    # 打印所有 .news-item 的结构
    items = await page.query_selector_all(".news-item")
    print(f"\nFound {len(items)} .news-item elements")

    if items:
        # 打印第一个 item 的完整 HTML
        first = await items[0].inner_html()
        print(f"\nFirst item HTML:\n{first[:500]}")

        # 尝试常见选择器
        for sel in [".title", ".time", ".source", ".desc", "a"]:
            el = await items[0].query_selector(sel)
            if el:
                text = await el.inner_text()
                print(f"\nSelector '{sel}': {text[:100]}")

    await browser.close()

if __name__ == "__main__":
    asyncio.run(probe())
```

- [ ] **Step 3: 运行探针脚本（需要网络）**

```bash
python -m crawler.probe
# 记录输出中的选择器结构
```

- [ ] **Step 4: 根据探针结果，更新 spider.py 中的选择器（Task 4 的一部分）**

---

## Task 4: 爬虫模块（crawler/spider.py）

**Files:**
- Modify: `crawler/__init__.py`（更新导出）
- Create: `crawler/spider.py`
- Create: `tests/test_crawler.py`

- [ ] **Step 1: 创建 `tests/test_crawler.py`**

```python
import pytest
from unittest.mock import patch, AsyncMock
from crawler.spider import fetch_today_news

@pytest.fixture
def mock_page():
    with patch("cloakbrowser.launch") as mock_launch:
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        yield mock_page

def test_fetch_today_news_returns_list(mock_page):
    # Mock 页面返回空列表
    mock_page.query_selector_all.return_value = []
    with patch("crawler.spider.launch", mock_page):
        result = fetch_today_news()
        assert isinstance(result, list)
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/test_crawler.py -v
# Expected: FAIL
```

- [ ] **Step 3: 实现 `crawler/spider.py`（选择器待探针确认后调整）**

```python
from cloakbrowser import launch
from db import SQLiteClient

# 选择器（probe.py 确认后填入实际值）
SELECTORS = {
    "container": ".news-list",
    "item": ".news-item",
    "title": ".title",
    "time": ".time",
    "source": ".source",
    "url": "a",
    "content": ".desc"
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
                "source": item.query_selector(SELECTORS["source"]).inner_text(),
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
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/test_crawler.py -v
```

- [ ] **Step 5: Commit**

```bash
git add crawler/spider.py tests/test_crawler.py
git commit -m "feat: 添加 CloakBrowser 爬虫模块"
```

---

## Task 5: 分类模块（classifier/filter.py）

**Files:**
- Create: `classifier/__init__.py`
- Create: `classifier/filter.py`
- Create: `tests/test_classifier.py`

- [ ] **Step 1: 创建 `classifier/__init__.py`**

```python
from .filter import classify_news

__all__ = ["classify_news"]
```

- [ ] **Step 2: 创建 `tests/test_classifier.py`**

```python
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
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
pytest tests/test_classifier.py -v
# Expected: FAIL
```

- [ ] **Step 4: 实现 `classifier/filter.py`**

```python
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
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/test_classifier.py -v
```

- [ ] **Step 6: Commit**

```bash
git add classifier/__init__.py classifier/filter.py tests/test_classifier.py
git commit -m "feat: 添加 MiniMax-M2.7 LLM 分类过滤模块"
```

---

## Task 6: 分析模块（analyzer/news_analyzer.py）

**Files:**
- Create: `analyzer/__init__.py`
- Create: `analyzer/news_analyzer.py`
- Create: `tests/test_analyzer.py`

**注意**: hermes-agent 的调用方式待确认，此处使用占位符实现，后续对齐

- [ ] **Step 1: 创建 `analyzer/__init__.py`**

```python
from .news_analyzer import analyze_news

__all__ = ["analyze_news"]
```

- [ ] **Step 2: 创建 `tests/test_analyzer.py`**

```python
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
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
pytest tests/test_analyzer.py -v
# Expected: FAIL
```

- [ ] **Step 4: 实现 `analyzer/news_analyzer.py`**

```python
import subprocess
import json
import os
import time
from pathlib import Path

SKILL_PATH = "skills/financial-news-analysis/SKILL.md"

def analyze_news(news_items: list[dict], date: str, max_retries: int = 3, retry_intervals: list = None) -> str:
    """
    调用 hermes-agent + SKILL.md 对新闻进行深度分析
    返回: 分析报告路径
    """
    if retry_intervals is None:
        retry_intervals = [30, 60, 120]

    # 确保输出目录存在
    report_dir = Path("reports") / date
    report_dir.mkdir(parents=True, exist_ok=True)

    context = {
        "date": date,
        "news_count": len(news_items),
        "news": news_items
    }

    for attempt, wait_time in enumerate([0] + retry_intervals[:max_retries]):
        if attempt > 0:
            time.sleep(wait_time)

        try:
            # TODO: hermes-agent 调用方式待确认后调整
            cmd = [
                "hermes", "analyze",
                "--skill", SKILL_PATH,
                "--context", json.dumps(context, ensure_ascii=False),
                "--output", str(report_dir / "analysis.md")
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                return str(report_dir / "analysis.md")
            else:
                raise RuntimeError(f"hermes-agent failed: {result.stderr}")

        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Analysis failed after {max_retries} retries: {e}")

    return str(report_dir / "analysis.md")
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/test_analyzer.py -v
```

- [ ] **Step 6: Commit**

```bash
git add analyzer/__init__.py analyzer/news_analyzer.py tests/test_analyzer.py
git commit -m "feat: 添加深度分析模块（hermes-agent 调用封装）"
```

---

## Task 7: 调度模块（scheduler/runner.py）

**Files:**
- Create: `scheduler/__init__.py`
- Create: `scheduler/runner.py`
- Create: `main.py`

- [ ] **Step 1: 创建 `scheduler/__init__.py`**

```python
from .runner import start_scheduler

__all__ = ["start_scheduler"]
```

- [ ] **Step 2: 创建 `scheduler/runner.py`**

```python
import schedule
import time
import yaml
import logging
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/runner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    with open("config.yaml") as f:
        return yaml.safe_load(f)

def job():
    """定时任务：爬取 → 分类 → 分析"""
    logger.info("=== Starting scheduled job ===")
    config = load_config()

    try:
        # 1. 爬取最新新闻
        from crawler import fetch_today_news
        from db import SQLiteClient

        db = SQLiteClient(config["database"]["path"])

        logger.info("Fetching news...")
        news = fetch_today_news()
        if news:
            db.insert_raw_news(news)
            logger.info(f"Inserted {len(news)} news items")
        else:
            logger.warning("No news fetched")

        # 2. 分类过滤
        logger.info("Classifying news...")
        pending = db.get_unclassified_news()
        if pending:
            from classifier import classify_news
            criteria = config["classifier"]["criteria"]
            matched_indices = classify_news(pending, criteria)
            # 更新 classified_news
            for idx in matched_indices:
                db.insert_classified_news([pending[idx]["id"]], ["财经"])
            # 标记已分类
            db.mark_raw_news_classified([pending[idx]["id"] for idx in matched_indices])
            logger.info(f"Matched {len(matched_indices)} news items")

        # 3. 深度分析
        logger.info("Analyzing news...")
        to_analyze = db.get_pending_analysis()
        if to_analyze:
            from analyzer import analyze_news
            date = datetime.now().strftime("%Y-%m-%d")
            report_path = analyze_news(to_analyze, date)
            for item in to_analyze:
                db.mark_analyzed(item["id"], report_path)
            logger.info(f"Analysis complete: {report_path}")

        db.close()
        logger.info("=== Job complete ===\n")

    except Exception as e:
        logger.error(f"Job failed: {e}", exc_info=True)


def start_scheduler():
    config = load_config()
    interval = config["crawler"]["interval_minutes"]

    schedule.every(interval).minutes.do(job)
    logger.info(f"Scheduler started, running every {interval} minutes")

    # 立即执行一次
    job()

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    start_scheduler()
```

- [ ] **Step 3: 创建 `main.py`**

```python
from scheduler.runner import start_scheduler

if __name__ == "__main__":
    start_scheduler()
```

- [ ] **Step 4: Commit**

```bash
git add scheduler/__init__.py scheduler/runner.py main.py
git commit -m "feat: 添加调度模块和程序入口"
```

---

## Task 8: 端到端集成测试

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: 创建 `tests/test_integration.py`**

```python
import pytest
from unittest.mock import patch
from db.sqlite_client import SQLiteClient
import tempfile
import os

def test_full_pipeline(tmp_path):
    """模拟完整流程：插入新闻 → 分类 → 分析标记"""
    db_path = tmp_path / "test.db"
    db = SQLiteClient(str(db_path))

    # 1. 插入原始新闻
    news = [{
        "title": "A股大涨",
        "time": "2026-05-18 10:00",
        "source": "同花顺",
        "url": "https://example.com/1",
        "content": "今日A股大涨"
    }]
    db.insert_raw_news(news)
    assert len(db.get_all_raw_news()) == 1

    # 2. 获取待分类
    pending = db.get_unclassified_news()
    assert len(pending) == 1

    # 3. 模拟分类（直接插入 classified）
    db.insert_classified_news([pending[0]["id"]], ["财经"])

    # 4. 获取待分析
    to_analyze = db.get_pending_analysis()
    assert len(to_analyze) == 1

    # 5. 模拟分析完成
    db.mark_analyzed(to_analyze[0]["id"], "reports/2026-05-18/analysis.md")

    # 6. 验证状态更新
    analyzed = db.get_pending_analysis()
    assert len(analyzed) == 0

    db.close()
```

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/test_integration.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: 添加端到端集成测试"
```

---

## Task 9: 添加 `requirements.txt` 和 README 占位

**Files:**
- Create: `requirements.txt`
- Create: `README.md`（项目说明，不含实现细节）

- [ ] **Step 1: 创建 `requirements.txt`**

```
cloakbrowser
anthropic
PyYAML
schedule
pytest
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt README.md
git commit -m "chore: 添加依赖文件和项目说明"
```

---

## 计划自检

1. **Spec 覆盖检查**：
   - [x] 爬虫模块（CloakBrowser + 同花顺）→ Task 3, 4
   - [x] 分类模块（MiniMax-M2.7） → Task 5
   - [x] 分析模块（hermes-agent + SKILL.md） → Task 6
   - [x] 调度模块 → Task 7
   - [x] 数据层（SQLite） → Task 2
   - [x] Markdown 报告输出 → Task 6
   - [x] 异常处理与重试 → Task 5, 6

2. **占位符检查**：Task 6 中 `hermes-agent` 调用方式有 TODO 注释，这是预期行为（待确认后调整）

3. **类型一致性**：
   - `db.insert_raw_news()` 接收 `list[dict]` ✓
   - `db.insert_classified_news()` 接收 `list[int]` ✓
   - `classify_news()` 返回 `list[int]` ✓
   - `analyze_news()` 返回 `str`（报告路径）✓

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-18-financial-news-analyzer-plan.md`**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**