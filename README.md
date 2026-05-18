# 财经新闻分析智能体

定时爬取同花顺 7×24 小时财经新闻，通过 LLM 分类过滤后调用 SKILL 深度分析，输出 Markdown 格式的分析报告。

## 功能

- 定时爬取同花顺实时新闻
- LLM 智能分类过滤
- 深度分析（hermes-agent + SKILL.md）
- Markdown 报告按日期归类

## 安装

```bash
pip install -r requirements.txt
```

## 配置

编辑 `config.yaml` 配置分类条件和调度间隔。

## 运行

```bash
python main.py
```

## 项目结构

- `crawler/` - 新闻爬虫
- `classifier/` - LLM 分类过滤
- `analyzer/` - 深度分析
- `scheduler/` - 定时调度
- `db/` - 数据存储
- `reports/` - 分析报告输出目录
