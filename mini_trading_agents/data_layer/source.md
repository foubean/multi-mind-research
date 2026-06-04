## 三类分析师的信息来源

---

### 1️⃣ 情绪分析师 — 信息来源

#### 市场情绪指标
```
CNN Fear & Greed Index     → 综合7个指标的恐惧贪婪指数
CBOE VIX                   → 市场恐慌指数（"恐惧计"）
Put/Call Ratio             → 期权市场多空比
AAII 投资者情绪调查         → 散户每周情绪调查
```

#### 资金流向数据
```
融资融券余额        → 交易所每日公布
ETF 资金净流入/流出  → Bloomberg / ETF.com
大户持仓变化        → 13F 季报（机构必须申报）
```

#### 社交媒体
```
Reddit (WallStreetBets)  → Pushshift API / Reddit API
Twitter/X                → Twitter API（付费）
StockTwits               → StockTwits API（免费）
微博/雪球（A股）          → 雪球 API / 爬虫
```

#### 可用数据接口
```python
# 免费
yfinance          → VIX 数据
AAII 官网         → 每周情绪调查 CSV
StockTwits API    → 股票相关推文情绪

# 付费
Bloomberg Terminal
Refinitiv (Reuters)
SentimentTrader   → 专业情绪数据平台
```

---

### 2️⃣ 新闻分析师 — 信息来源

#### 财经新闻媒体
```
Bloomberg          → 付费API，最权威
Reuters            → Refinitiv API
Financial Times    → 付费订阅
CNBC / MarketWatch → 免费RSS / 爬虫
```

#### 公司官方公告
```
SEC EDGAR          → 美股所有上市公司法定披露
  ├── 10-K  年报
  ├── 10-Q  季报
  ├── 8-K   重大事项公告（并购、CEO变更...）
  └── 13F   机构持仓报告

中国A股
  ├── 上交所 / 深交所公告系统
  └── 巨潮资讯网
```

#### 新闻聚合 API
```python
# 免费
NewsAPI.org              → 多源新闻聚合
Google News RSS          → 免费但不稳定
Yahoo Finance News       → yfinance 可直接获取

# 付费
Alpha Vantage News API   → 含情感分析评分
Benzinga Pro             → 实时财经新闻
TheNewsAPI               → 专业财经新闻

# 示例
import yfinance as yf
ticker = yf.Ticker("AAPL")
news = ticker.news   # 直接拿到相关新闻列表
```

#### 分析师报告
```
Seeking Alpha      → 分析师评级变化
TipRanks           → 汇总华尔街分析师评级
Refinitiv          → 付费，机构级别
```

---

### 3️⃣ 基本面分析师 — 信息来源

#### 财务报表数据
```python
# 免费
yfinance                  → 财务三张表、估值指标
financedatareader (FDR)   → A股+美股财务数据
Macrotrends.net           → 历史财务数据

# 示例
import yfinance as yf
ticker = yf.Ticker("AAPL")
ticker.financials          # 利润表
ticker.balance_sheet       # 资产负债表
ticker.cashflow            # 现金流量表
ticker.info                # P/E、P/B、市值等
```

#### 估值 & 行业数据
```
Damodaran 数据库    → 纽大教授免费公布，行业估值基准
Finviz             → 免费筛选器，含估值指标
Wisesheets         → Excel插件，财务数据
Simplywall.st      → 可视化基本面分析
```

#### 宏观经济数据
```python
# FRED（美联储经济数据库）完全免费
from fredapi import Fred
fred = Fred(api_key="your_key")
gdp     = fred.get_series("GDP")
cpi     = fred.get_series("CPIAUCSL")
rate    = fred.get_series("FEDFUNDS")  # 联邦基金利率

# 世界银行 / IMF
import wbdata    # 世界银行API
```

---

### ✅ 汇总对比

| | 情绪分析师 | 新闻分析师 | 基本面分析师 |
|--|-----------|-----------|------------|
| **核心来源** | 社交媒体、期权市场 | SEC公告、财经媒体 | 财务报表、估值模型 |
| **更新频率** | 实时/每日 | 实时 | 季度/年度 |
| **免费工具** | StockTwits、VIX | NewsAPI、yfinance | yfinance、FRED |
| **付费工具** | SentimentTrader | Bloomberg、Benzinga | Refinitiv、FactSet |
| **A股专属** | 雪球、东方财富 | 巨潮资讯、同花顺 | Wind、东方财富Choice |

---

### 💡 实际工程中的获取方式

```
实时性要求高   →  付费API（Bloomberg / Refinitiv）
成本敏感       →  yfinance + NewsAPI + FRED 组合
A股项目        →  AkShare（全能免费库，覆盖以上全部）
LLM Agent     →  封装成 Tool，让 Agent 按需调用
```

> **AkShare 特别推荐（开源免费）：**
> ```python
> import akshare as ak
> # 情绪：融资融券、龙虎榜
> # 新闻：财经新闻、公告
> # 基本面：财务报表、估值
> # 一个库全覆盖
> ```

---

## 工程化补充：三个分析师的数据源落地建议

当前项目已经改成按数据类别拆分 adapter 的模式。后续不要再把一家供应方的四类数据写在一个文件里，而应该按数据横截面组织：

```text
data_layer/
  market/
    sample.py
    yahoo.py
  sentiment/
    sample.py
    yahoo.py
  news/
    sample.py
    yahoo.py
  fundamentals/
    sample.py
    yahoo.py
```

`prepare_data` 负责选择每个类别的 adapter、执行获取/清洗/结构化，并把结果写入 `TradingState`。如果某个类别的数据源失败，只回退该类别，不影响其他类别。

---

### 1. Sentiment Analyst：情绪数据来源

#### 推荐优先级

| 优先级 | 数据源 | 类型 | 用途 | 接入建议 |
| --- | --- | --- | --- | --- |
| P0 | VIX / `^VIX` | 市场恐慌指标 | 判断整体风险偏好 | 可通过 Yahoo/yfinance 先接入 |
| P0 | Put/Call Ratio | 期权多空情绪 | 判断期权市场偏向 | CBOE、Nasdaq、付费行情源 |
| P1 | StockTwits | 股票社交情绪 | 个股 bullish/bearish 讨论 | 可作为美股情绪 MVP 候选，但 API 可用性需要实现前复核 |
| P1 | Reddit | 散户讨论热度 | 讨论量、关键词、极端情绪 | Reddit API，注意噪声过滤 |
| P1 | AAII Sentiment Survey | 投资者周度情绪 | 中期市场情绪 | 周频，适合作为宏观情绪背景 |
| P2 | ETF Fund Flow | 资金流向 | 判断行业/主题资金偏好 | ETF.com、FactSet、Bloomberg |
| P2 | 13F Holdings | 机构持仓变化 | 中长期机构态度 | SEC EDGAR，季度更新 |
| P2 | Twitter/X | 实时舆情 | 突发事件和传播速度 | 成本较高，适合后期接入 |
| A股 | 雪球/东方财富/股吧 | 社交讨论 | A股散户情绪 | 可优先考虑 AkShare/爬虫 |

#### 建议归一化字段

```python
SentimentData = {
    "ticker": "NVDA",
    "as_of": "2026-06-04",
    "source": "stocktwits",
    "sentiment_score": 0.27,          # -1 到 1，负数偏空，正数偏多
    "positive_mentions": 1840,
    "negative_mentions": 910,
    "neutral_mentions": 1260,
    "mention_change_pct_24h": 18.5,
    "top_topics": ["AI demand", "valuation risk"],
    "raw_signals": {
        "vix": 18.4,
        "put_call_ratio": 0.82,
        "message_volume": 4010
    },
    "observations": [...]
}
```

#### MVP 建议

第一阶段建议组合：

```text
yfinance 获取 ^VIX
StockTwits 或其他可用社交源获取个股讨论/情绪
sample fallback 保底
```

原因：VIX 能快速补充市场整体风险偏好，个股社交源更贴近 ticker 情绪；StockTwits 是候选之一，但接入前要确认当前 API 权限和稳定性。

---

### 2. News Analyst：新闻数据来源

#### 推荐优先级

| 优先级 | 数据源 | 类型 | 用途 | 接入建议 |
| --- | --- | --- | --- | --- |
| P0 | Yahoo Finance News | 个股相关新闻 | 快速拿到公司相关新闻 | 可通过 yfinance/ticker news 做 MVP |
| P0 | SEC EDGAR Submissions | 官方披露 | 8-K、10-Q、10-K、重大事项 | 美股新闻分析必须接入 |
| P1 | NewsAPI `/v2/everything` | 新闻聚合 | 按 ticker/company 搜索新闻 | 适合低成本 MVP |
| P1 | Google News RSS | 免费新闻聚合 | 补充覆盖面 | 不稳定，适合 fallback |
| P1 | Alpha Vantage News Sentiment | 新闻 + 情绪 | 新闻情感评分 | 免费额度有限，适合原型 |
| P2 | Benzinga / Bloomberg / Refinitiv | 实时财经新闻 | 高频和机构级新闻 | 付费，适合生产 |
| P2 | Seeking Alpha / TipRanks | 分析师观点 | 评级变化、目标价 | 多数需要订阅或限制访问 |
| A股 | 巨潮资讯/交易所公告 | 官方公告 | 公司公告、监管披露 | A股新闻分析核心来源 |
| A股 | 财联社/同花顺/东方财富 | 财经新闻 | 快讯、行业新闻 | 可结合 AkShare 或商业 API |

#### 建议归一化字段

```python
NewsData = {
    "ticker": "NVDA",
    "as_of": "2026-06-04",
    "source": "newsapi",
    "items": [
        {
            "title": "...",
            "source": "Reuters",
            "published_at": "2026-06-04T08:00:00Z",
            "summary": "...",
            "url": "https://...",
            "sentiment": "positive",
            "event_type": "partnership",   # earnings, guidance, litigation, m&a, management, macro
            "importance": 0.8
        }
    ],
    "observations": [...]
}
```

#### MVP 建议

第一阶段建议组合：

```text
Yahoo Finance News 或 NewsAPI
SEC EDGAR 最近 filings
sample fallback 保底
```

原因：新闻分析不能只看媒体新闻。美股项目里 SEC 8-K、10-Q、10-K 是官方事实来源，适合作为新闻真实性校验层。

---

### 3. Fundamentals Analyst：基本面数据来源

#### 推荐优先级

| 优先级 | 数据源 | 类型 | 用途 | 接入建议 |
| --- | --- | --- | --- | --- |
| P0 | yfinance `info` / financials | 估值和财务报表 | 快速拿 PE、收入、利润、现金流 | 当前 Yahoo provider 下一步可优先补 |
| P0 | SEC Company Facts API | XBRL 财务事实 | 官方财务数据 | 美股基本面核心来源 |
| P1 | SEC 10-K / 10-Q 文本 | 管理层讨论、风险因素 | 定性基本面 | 可后续给 LLM 摘要 |
| P1 | FRED | 宏观指标 | 利率、CPI、GDP、信用环境 | 给基本面加入宏观背景 |
| P1 | Damodaran 数据库 | 行业估值基准 | 行业 PE、WACC、ERP | 估值对比层 |
| P2 | Financial Modeling Prep | 财务 API | 财报、估值、财务比率 | 付费/免费额度，字段稳定 |
| P2 | Alpha Vantage Fundamentals | 公司基本面 | 财报和指标 | 免费额度有限 |
| P2 | FactSet / Refinitiv / Bloomberg | 机构级基本面 | 生产级稳定数据 | 付费 |
| A股 | AkShare / Tushare / Wind / Choice | 财报和估值 | A股基本面 | 免费/付费分层 |

#### 建议归一化字段

```python
FundamentalsData = {
    "ticker": "NVDA",
    "as_of": "2026-06-04",
    "source": "sec_company_facts",
    "revenue_growth_yoy": 0.48,
    "gross_margin": 0.72,
    "operating_margin": 0.54,
    "pe_ratio": 58.6,
    "forward_pe": 41.2,
    "debt_to_equity": 0.22,
    "free_cash_flow": 28600000000,
    "cash_and_equivalents": 31400000000,
    "macro_context": {
        "fed_funds_rate": 5.25,
        "cpi_yoy": 3.1,
        "ten_year_yield": 4.2
    },
    "observations": [...]
}
```

#### MVP 建议

第一阶段建议组合：

```text
yfinance 补估值和常用财务字段
SEC Company Facts 补官方财务事实
FRED 补宏观背景
sample fallback 保底
```

原因：yfinance 接入快，但字段可能不稳定；SEC Company Facts 更权威但需要 CIK 映射和 XBRL 字段归一化；FRED 适合提供利率/通胀环境，帮助基本面分析师判断估值压力。

---

## Adapter 实现建议

后续不建议按“一个 API 一个大 provider”的方式扩展，而应该按数据类别增加 adapter：

```python
class NewsApiNewsDataAdapter(NewsDataAdapter):
    source_key = "newsapi"

    def fetch(self, ticker: str, as_of: str) -> dict:
        ...
```

如果一个供应方能覆盖多类数据，也拆到对应类别目录里，例如：

```text
market/yahoo.py
sentiment/yahoo.py
news/yahoo.py
fundamentals/yahoo.py
```

推荐扩展顺序：

1. 在 `fundamentals/` 下新增 SEC Company Facts adapter。
2. 在 `news/` 下新增 SEC EDGAR submissions adapter。
3. 在 `news/` 下新增 NewsAPI adapter。
4. 在 `sentiment/` 下新增 StockTwits 或其他社交情绪 adapter。
5. 在 `fundamentals/` 下新增 FRED macro context adapter。

运行时可以用 `--data-provider` 一键设置四类数据来源，也可以用分类参数分别指定：

```powershell
python .\run_demo.py --data-provider yahoo
python .\run_demo.py --market-provider yahoo --sentiment-provider yahoo --news-provider sample --fundamentals-provider yahoo
```

长期更好的结构是让不同类别选择不同最佳来源：

```text
market_data        -> yahoo
sentiment_data     -> stocktwits + vix
news_data          -> newsapi + sec
fundamentals_data  -> sec + fred + yahoo
```
