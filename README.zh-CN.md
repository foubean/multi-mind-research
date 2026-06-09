# Mini Trading Agents

[English](README.md) | 中文

Mini Trading Agents 是一个受 TradingAgents 启发的 LangGraph 多智能体交易研究框架。

本系统将 TradingAgents 风格的单标的研究流程扩展为多标的组合管理流程。用户可以输入目标证券池，并结合资金规模、风险偏好和组合约束，获得仓位管理建议、目标配置方案和组合级执行计划。项目目标不是只给出单只股票的买卖建议，而是逐步演进为面向个人资金管理的智能组合助手。

下一阶段的开发方向是支持长期自动化运行，包括定时分析、持续监控组合、记录模拟交易反馈，以及由 Agents 自动维护投资标的池。未来系统应能够根据市场、基本面、风险和历史结果自动推荐新标的，剔除弱化或不再满足条件的标的，并让组合始终贴合用户的资金目标、风险约束和投资偏好。

系统同时内置面向审计、回溯和恢复的基础设施。LangGraph checkpoint 用于保存图执行进度，自定义 snapshot 用于持久化完整工作流状态，decision memory 用于记录历史决策和组合结果，便于后续复盘和经验沉淀。模拟交易层通过 Alpaca Paper Trading 接入在线模拟账户，使组合策略可以先在券商托管的模拟环境中验证，再考虑任何实盘交易集成。

核心能力包括：

- 多个角色化 Agent 在 LangGraph 工作流中协同运行。
- 所有节点通过统一的状态对象共享信息。
- 后续节点综合分析报告、投研辩论、交易方案和风险审查。
- 分析师节点并行执行，研究辩论和风险辩论支持多轮循环。
- checkpoint、snapshot 和 decision memory 支持运行恢复、审计追踪和历史回溯。
- Alpaca Paper Trading 提供在线模拟交易层，用于验证组合决策和执行计划。

本项目是研究和工程骨架，不构成投资建议，也不是实盘交易系统。

## 运行

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

项目有两种运行模式：

| 模式 | 入口文件 | 默认配置 | 用途 |
|---|---|---|---|
| 单节点 / 单标的 | `run.py` | `config.toml` | 对单个标的运行完整的标的级 Agent 图。默认使用 `[run].tickers` 的第一个值。 |
| Graph / 多标的 | `run_graph.py` | `config.toml` | 运行父图，调度多个单标的子图，并生成组合配置方案。 |

从示例配置创建本地配置：

```powershell
Copy-Item .\config.example.toml .\config.toml
```

运行单标的模式：

```powershell
python .\run.py
```

运行多标的 Graph 模式：

```powershell
python .\run_graph.py
```

指定标的和日期：

```powershell
python .\run.py --ticker NVDA --date 2026-01-15
```

使用 Yahoo Finance 数据适配器：

```powershell
python .\run.py --ticker NVDA --date 2026-01-15 --data-provider yahoo
```

按数据类别指定 provider：

```powershell
python .\run.py --ticker NVDA --date 2026-01-15 --market-provider yahoo --sentiment-provider yahoo --news-provider yahoo --fundamentals-provider yahoo
```

`--data-provider` 是快捷参数，会设置全部四类数据；单独类别参数会覆盖它。

## 配置

运行配置集中在 `config.toml`。密钥不写入 TOML，而是放在本地环境文件：

- `.env.openai`：OpenAI-compatible LLM 连接信息。
- `.env.alpaca`：Alpaca Paper Trading 和 Alpaca Market Data 凭证。

详细策略和偏好对象放在 JSON 文件中：

- `config/portfolio_constraints.default.json`：组合硬约束。
- `config/trade_preferences.default.json`：交易偏好和持仓周期等参数。

### 关键配置项

| 配置区 | 字段 | 说明 |
|---|---|---|
| `[config_files]` | `trade_preferences_path` | 单标的交易建议使用的偏好文件。 |
| `[config_files]` | `constraints_path` | 组合级硬约束文件。 |
| `[persistence]` | `checkpoint_enabled` | 是否启用 LangGraph 原生 checkpoint。 |
| `[persistence]` | `snapshot_enabled` | 是否启用自定义完整状态快照。 |
| `[persistence]` | `decision_memory_enabled` | 是否写入决策记忆和业务审计记录。 |
| `[llm]` | `provider`, `model` | LLM 适配器和模型。 |
| `[paper_trading]` | `enable`, `provider` | 是否启用在线模拟盘，目前 provider 为 `alpaca`。 |
| `[run]` | `tickers` | 多标的模式使用全部列表，单标的模式默认取第一个。 |
| `[run]` | `analysis_date` | 空字符串表示使用当天日期，也可以指定 `YYYY-MM-DD`。 |
| `[run]` | `research_turns`, `risk_turns` | 研究辩论和风险辩论轮数。 |
| `[run]` | `max_parallel_tickers` | 父图中最多并行运行的标的子图数量。 |
| `[data_providers]` | `market`, `sentiment`, `news`, `fundamentals` | 分别指定行情、情绪、新闻和基本面数据来源。 |
| `[logging]` | `enabled`, `log_dir` | JSONL 流式审计日志设置。 |
| `[reporting]` | `report_dir` | HTML 报告输出目录。 |
| `[portfolio]` | `max_revision_count` | 组合计划校验失败后的最大修订次数。 |
| `[portfolio]` | `single_ticker_failure_policy` | 单个标的子图失败时父图的处理策略。 |

## 数据层

当前数据层按数据类别组织，而不是按 API 供应商组织。每一类数据都可以选择 provider：

- `market`：行情、成交量、移动均线、RSI 等技术字段。
- `sentiment`：轻量情绪数据。
- `news`：新闻列表和新闻情绪。
- `fundamentals`：收入增速、利润率、估值、负债等基本面字段。

Yahoo 目前可以覆盖四类数据；Alpaca 可用于行情数据和在线模拟盘账户/订单。生产环境中应继续接入 SEC filings、专业新闻 API、真实情绪模型和更完整的基本面数据源。

## 数据血缘

每个规范化数据切片都带有轻量级 `lineage` 字段，用于记录：

- provider 和原始来源。
- adapter 名称。
- 拉取时间。
- 关键转换步骤。
- 下游消费该数据的分析师节点。

当前血缘模型是数据切片级血缘，适合现阶段较浅的工作流。未来如果进入长期回测、多源融合、分布式执行或复杂审计，需要升级为完整的决策 DAG 血缘。

## Alpaca 在线模拟盘

系统只保留在线模拟盘执行层，目前使用 Alpaca Paper Trading：

- 组合图运行前从 Alpaca Paper 读取现金、净值和持仓。
- 组合经理在真实模拟盘账户上下文中生成目标配置。
- 执行计划通过 Alpaca Paper API 提交模拟订单。
- 使用 `client_order_id` 避免同一 run/ticker 重复下单。
- 执行结果写入报告和业务审计表。

启用方式：

```toml
[paper_trading]
enable = true
provider = "alpaca"
```

本地 `.env.alpaca` 示例：

```env
ALPACA_API_KEY=...
ALPACA_API_SECRET=...
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets
```

## 单标的交易建议

单标的图不直接决定组合最终权重。它的职责是分析一个标的，并输出结构化 `trade_advice`，供父级组合图横向比较多个标的。

`trade_advice` 包括：

- `BUY/HOLD/SELL` 动作和 `none/small/medium/large` 信念强度。
- `open/add/reduce/exit/watch/wait` 交易意图。
- 预期收益、预期风险和预期持有天数。
- 风险偏好和交易风格。
- 建仓、加仓、减仓、止损计划。
- 失效条件。

其中 `position_size` 只是单标的信念桶，不是最终组合权重。最终权重由多标的父图在组合约束下决定。

## 多标的组合图

`run_graph.py` 将单标的图作为可复用计算节点：

1. 读取在线模拟盘账户上下文。
2. 执行前置校验。
3. 根据 `[run].tickers` 生成标的任务。
4. 按 `[run].max_parallel_tickers` 分批并行运行单标的子图。
5. 汇总每个标的的 `trade_advice`。
6. 构建组合上下文和横截面对比。
7. 由组合经理 Agent 生成目标权重和组合计划。
8. 进行组合约束校验。
9. 必要时让 LLM 修订组合计划。
10. 生成执行计划并进行订单级校验。
11. 可选提交到 Alpaca Paper Trading。
12. 输出 HTML 报告、snapshot、checkpoint 和 decision memory。

运行示例：

```powershell
python .\run_graph.py --config .\config.toml --tickers NVDA,AAPL,MSFT --date 2026-06-05 --data-provider yahoo --market-provider alpaca
```

也可以完全通过 `config.toml` 控制：

```toml
[run]
tickers = ["NVDA", "AAPL", "MSFT"]
analysis_date = ""
research_turns = 2
risk_turns = 3
max_parallel_tickers = 5
```

```powershell
python .\run_graph.py --config .\config.toml
```

## 持久化

系统目前有三层持久化：

- LangGraph checkpoint：保存图执行状态、channel values、pending sends、next tasks 等运行时信息。
- 自定义 snapshot：保存完整业务 state，便于审计、恢复和人工解释。
- decision memory / store：保存一轮决策后的摘要经验和业务记忆。

这些记录可以用于回溯历史运行、比较不同决策路径，并在中断后从最近一次完整状态恢复或重跑。

这些配置默认开启：

```toml
[persistence]
checkpoint_enabled = true
snapshot_enabled = true
decision_memory_enabled = true
```

## 报告

每次成功运行会生成 HTML 报告，包含：

- 标的或组合概览。
- 关键行情和基本面数据。
- Agent workflow 图示。
- 节点摘要和辩论轮次。
- 交易建议和组合计划。
- 数据血缘。
- LLM 调用记录。
- 在线模拟盘执行结果。

报告输出目录由 `[reporting].report_dir` 控制，默认为 `reports/`。

## 文件结构

- `README.md`：英文说明。
- `README.zh-CN.md`：中文说明。
- `config.example.toml`：安全的示例配置。
- `config/portfolio_constraints.default.json`：组合约束。
- `config/trade_preferences.default.json`：交易偏好。
- `run.py`：单标的入口。
- `run_graph.py`：多标的组合图入口。
- `mini_trading_agents/workflow.py`：单标的 LangGraph 工作流。
- `mini_trading_agents/portfolio_graph/`：多标的父图。
- `mini_trading_agents/data_layer/`：数据获取、清洗和结构化。
- `mini_trading_agents/execution/`：在线模拟盘执行适配器。
- `mini_trading_agents/reporting/`：HTML 报告生成。
- `mini_trading_agents/storage/`：业务存储和 snapshot。

## 扩展方向

后续可以继续增强：

- 长期自动化运行和定时任务。
- 自动选股、剔除标的和维护投资池。
- 模拟盘长期收益记录、复盘和决策记忆更新。
- 更完整的数据源和数据血缘。
- Vue 单页应用，用于运行工作流、查看报告和管理配置。
- 更严格的组合风险模型和资金管理规则。
