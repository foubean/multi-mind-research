# 总待办事项清单

## [LG-WORKFLOW] LangGraph 流程增强

- [ ] 将 `global-portfolio-graph` 完善为正式组合父图，明确父图与 `single-ticker-node` 子图的接口边界。
- [x] 增强账户与持仓读取：从本地模拟盘或券商模拟盘读取真实账户状态，而不是只使用初始现金。
- [x] 在组合图中加入 `load_account_context` 的真实实现，输出 cash、equity、positions、portfolio_history。
- [x] 增强 `preflight_validate`：提前检查账户可用性、ticker 合法性、数据源配置、LLM 可用性、约束配置是否合法。
- [x] 增强 `prepare_ticker_tasks`：支持全局参数映射到单体节点，并允许 ticker 级别覆盖。
- [x] 完善多 ticker 并行执行策略：支持 `fail_fast`、`skip_failed`、失败原因保留和局部结果继续汇总。
- [x] 增强 `collect_trade_advices`：生成横截面对比，包括 BUY/HOLD/SELL 分布、confidence 排名、risk/return 排名。
- [x] 增强 `portfolio_context_builder`：加入已有持仓、现金比例、历史结果、近期决策记忆、组合约束。
- [x] 增强 `portfolio_research_summarizer`：识别机会排名、替代关系、主题聚类、重复逻辑和单体建议冲突。
- [ ] 增强 `portfolio_risk_reviewer`：识别行业集中度、主题集中度、相关性、波动率、估值风险叠加和已有持仓风险。
- [x] 强化 LLM portfolio manager prompt：要求解释买入、不买、减仓、保留现金和拒绝候选标的的原因。
- [x] 将 `validation_result` 回灌给 LLM portfolio manager，用于修正违反约束的组合计划。
- [x] 将 `validate_portfolio_plan` 拆成 preflight、portfolio plan、execution plan 三层校验。
- [x] 增加更多硬约束：行业上限、主题上限、相关性集群上限、最大新增仓位数、最小订单金额、换手率上限、亏损后冷却期、禁买标的。
- [ ] 完善修正回路：区分 repairable、fatal、warning，并限制最大修正次数。
- [x] 增强组合 HTML 报告：展示单体节点钻取、组合权重、拒绝候选、风险暴露、约束检查、订单计划和历史对比。
- [x] 给全局组合图加入 checkpoint、snapshot、decision memory/store 的正式持久化支持。
- [x] 补充 README 和 change.md，明确组合图中 LLM 决策层和规则约束层的职责边界。

## [PAPER-TRADING] 模拟交易强化

- [x] 完善 `LocalPaperAdapter.apply_portfolio_plan()`，支持组合目标权重到本地模拟订单的转换。
- [x] 完善 `AlpacaPaperAdapter.submit_portfolio_orders()`，支持组合级模拟盘订单提交。
- [x] 将 execution plan 从目标权重扩展为真实订单计划：side、quantity、notional、order_type、limit_price、time_in_force、reason、risk_note。
- [x] 在模拟盘执行前增加 execution plan validation：最小订单金额、现金不足、是否允许小数股、是否允许卖出、是否超过换手限制。
- [ ] 建立每日/每轮 mark-to-market 脚本，例如 `run_paper_mark_to_market.py`。
- [ ] mark-to-market 读取当前持仓、获取最新价格、重算 market_value、equity、unrealized_pnl，并写入 `portfolio_snapshots`。
- [x] 完善 `trade_outcomes` 表写入逻辑，而不仅仅是建表。
- [x] 买入或开仓时写入 open outcome，记录 run_id、ticker、entry_price、quantity、target_weight、actual_weight。
- [ ] 持仓期间更新 open outcome，记录 unrealized_return_pct、max_drawdown_pct、max_runup_pct、holding_days。
- [ ] 平仓或减仓时写入 closed outcome，记录 realized_pnl、realized_return_pct、closed_at、exit_price、outcome_status。
- [x] 为组合层增加 portfolio_run_id、order_id、fill_id、target_weight、actual_weight 等 outcome 字段关联。
- [ ] 建立 `decision_reviewer_agent`，在 closed outcome 后复盘原始建议、组合计划、实际路径和风险控制是否有效。
- [ ] 将复盘结果写入 LangGraph Store / decision memory，按 ticker 和 portfolio 两种 namespace 保存。
- [ ] 下一轮组合图运行前加载 recent trade outcomes 和 lessons，作为 LLM portfolio manager 的上下文。
- [ ] 区分“经验记忆反馈闭环”和“强化学习”：当前阶段先做结构化结果记忆，不训练模型参数。
- [ ] 后续如果需要强化学习，再基于足够多的模拟盘结果设计 reward、policy、state/action space。
- [ ] 在报告中展示模拟盘时间序列：组合净值、现金比例、持仓权重、单笔交易结果、最大回撤和收益曲线。
- [ ] 支持长期自动化运行：定时分析、模拟下单、收盘 mark-to-market、复盘写 memory。

## [META-ROADMAP] 原始方向保留

- [ ] 实现工作流重新编排和增加 agent。
- [ ] 提高各 agent 的定制化能力。
- [ ] 评估分布式执行必要性，先保持本地/单进程可验证实现。
- [ ] 支持模拟环境交易和策略调整。
- [ ] 增强可回溯、审计和数据血缘。
- [ ] 整理部署方案和后续优化方案。
- [ ] 补充 PRD 和阶段性进度计划。
- [ ] 强化审计能力。
