在投资银行及 institutional trading（机构交易）的真实业务场景中，一个交易动作（通常涵盖订单生成、路由、撮合、成交到清算）所包含的字段极其庞大且严密。为了确保交易的合规性、准确性和可追溯性，国际上普遍采用 **FIX 协议（Financial Information eXchange）** 核心标准。

一个真实的交易动作，其数据结构通常可以划分为以下几个核心板块：

## 1. 交易基础属性（What & How Much）

这组字段定义了交易的核心标的和数量，是交易最基本的信息。

* **Symbol / Ticker（标的代码）：** 如 `AAPL`（美股）、`00700`（港股）。
* **Security ID / ISIN / CUSIP（证券唯一标识码）：** 国际通用的证券识别编码，防止因代码重名走错市场。
* **Side（交易方向）：** 买入（Buy）、卖出（Sell）、融券卖出（Sell Short）、备兑开仓（Cover）等。
* **Quantity / OrderQty（交易数量）：** 股数（Equities）、张数（Options/Futures）或面值（Fixed Income）。
* **Price（价格）：** 具体成交价或限价。如果是市价单，此字段在初始订单中可能为空或为主流市场价。

---

## 2. 身份与账户路由（Who）

用于追踪这笔交易是谁做的、资金从哪里来、最终归属到哪个账户。

* **ClientID / Account（客户代码/账户）：** 最终下单的机构客户（如某对冲基金或公募基金）。
* **TraderID / DealerID（交易员代码）：** 投行内部执行该笔交易的交易员（Trader）或销售交易员（Sales Trader）的唯一标识。
* **Executing Broker（执行经纪商）：** 实际在交易所拥有席位并执行交易的实体。
* **Clearing Account / Firm（清算账户/清算机构）：** 负责后续资金和证券交收的托管行或清算所代码。

---

## 3. 时间戳与订单生命周期（When & Lifecycle）

高频和投行交易中，时间就是金钱，时间戳通常精确到微秒（Microseconds）甚至纳秒。

* **ClOrdID（客户端订单ID）：** 投行内部系统为这笔订单生成的唯一流水号。
* **OrderID / ExecID（交易所订单ID/执行ID）：** 交易所接收或成交后返回的官方唯一标识。
* **TransactTime（交易激活时间）：** 订单生成的精确时间。
* **SendingTime / ReceivingTime（发送/接收时间）：** 用于计算网络延迟（Latency）。
* **OrdStatus（订单状态）：** New（新订单）、Partially Filled（部分成交）、Filled（全部成交）、Canceled（已撤单）、Rejected（拒绝）。

---

## 4. 执行策略与指令类型（How）

投行交易很少单纯用“市价/限价”机械执行，往往伴随着复杂的算法和限制条件。

* **OrdType（订单类型）：** Limit（限价）、Market（市价）、Stop（止损）、Pegged（挂钩单）等。
* **TimeInForce（有效时限）：** * `DAY`（当日有效）
* `GTC`（好至取消/Good 'Til Cancelled）
* `IOC`（立即成交否则取消/Immediate Or Cancel）
* `FOK`（全部成交否则取消/Fill Or Kill）


* **HandlingInst（处理指令/算法策略）：** 规定是否使用算法交易。例如使用 `VWAP`（成交量加权平均价）、`TWAP`（时间加权平均价）或 `POV`（比例卷入策略）。
* **Capacity（身份属性）：** * `Agency`（代理：帮客户买卖）
* `Principal`（自营：投行自己出钱和客户做对手盘）
* `Riskless Principal`（无风险自营）



---

## 5. 费用、结算与合规（Money & Compliance）

真实交易必须算清每一笔成本，并满足监管机构（如 SEC, FINRA, SFC）的审计要求。

* **GrossTradeAmt（总成交金额）：** $Price \times Quantity$ 的原始金额。
* **Commission / Fee（佣金/费用）：** 投行向客户收取的服务费，或付给交易所的经手费。
* **Currency（交易币种）：** 如 `USD`, `HKD`, `EUR`。
* **Settlement Date（交割日）：** 资金和股份正式划转的日期（如 `T+1` 或 `T+2`）。
* **ShortSaleRestriction (SSR) Flag（融券限制标记）：** 是否触发卖空限制。
* **LocateReqD（券源定位标识）：** 如果是卖空，必须包含此字段，证明投行已经帮客户“借到了券”（满足合规的 Locate Requirement）。

---

### 💡 真实运行中的数据示例（FIX Protocol 简化版）

当投行系统向交易所发送或记录一个动作时，在底层表现为键值对（Key-Value）：

| FIX Tag | 字段名称 | 示例值 | 业务含义 |
| --- | --- | --- | --- |
| **11** | ClOrdID | `MS_20260607_00982` | 摩根士丹利内部订单号 |
| **55** | Symbol | `NVDA` | 英伟达 |
| **54** | Side | `1` | 买入 (1=Buy, 2=Sell) |
| **38** | OrderQty | `50000` | 购买 50,000 股 |
| **40** | OrdType | `2` | 限价单 (2=Limit) |
| **44** | Price | `125.50` | 限价 $125.50 |
| **60** | TransactTime | `20260607-04:27:15.123456` | 精确到微秒的时间戳 |
| **847** | TargetStrategy | `1` | 使用 VWAP 算法执行 |