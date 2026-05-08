# Felix量化

Felix量化（Quant Research Terminal）是一个本地运行的个人量化研究与复盘系统，用于建立“数据更新 -> 策略运行 -> 候选股票池 -> 风险依据 -> 回测 -> 复盘”的辅助决策流程。

> 本系统仅用于个人量化研究和投资复盘，不构成任何投资建议。投资有风险，决策需谨慎。

## MVP 功能

- Dashboard：更新时间、候选数量、市场状态、策略状态、回测指标、风险等级、观察清单、风险预警、复盘记录
- 候选股票池：评分排序、行业/策略/风险筛选、代码/名称搜索、入选原因、风险理由、最近回测表现
- 股票详情：基础信息、价格/均线/成交量图、信号历史、风险因子、回测曲线、复盘记录
- 策略管理：三个内置策略、启停、参数 JSON 编辑、手动运行、创建新策略
- 回测：策略、股票池、时间范围、初始资金、手续费、止损线、仓位上限、收益曲线、回撤曲线、交易明细
- 风控：仓位限制、组合建议、行业集中度、回撤/波动预警、规则阈值维护、高风险股票池
- 复盘：按日期/股票/标签筛选，新增复盘记录，复盘统计
- SQLite：本地数据库与示例股票行情数据

## 技术栈

前端：

- Next.js + React + TypeScript
- Tailwind CSS
- shadcn/ui 风格本地组件
- Recharts
- lucide-react

后端：

- Python FastAPI
- SQLite
- Pandas / NumPy
- AKShare 真实行情数据源
- APScheduler 预留
- 自研 Pandas 回测框架

## 项目结构

```text
.
├── README.md
├── package.json
├── scripts/
│   └── dev.sh
├── data/
│   └── quant_research.sqlite3        # 首次启动后自动生成
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── api/
│       │   ├── backtest.py
│       │   ├── dashboard.py
│       │   ├── data.py
│       │   ├── reviews.py
│       │   ├── risk.py
│       │   ├── signals.py
│       │   ├── stocks.py
│       │   └── strategies.py
│       ├── core/
│       │   └── config.py
│       ├── db/
│       │   └── database.py
│       ├── schemas/
│       │   └── requests.py
│       └── services/
│           ├── analytics.py
│           ├── backtest_service.py
│           ├── dashboard_service.py
│           ├── market_service.py
│           ├── review_service.py
│           ├── risk_service.py
│           ├── strategy_rules.py
│           └── strategy_service.py
└── frontend/
    ├── app/
    │   ├── page.tsx
    │   ├── backtest/page.tsx
    │   ├── candidates/page.tsx
    │   ├── reviews/page.tsx
    │   ├── risk/page.tsx
    │   ├── settings/page.tsx
    │   ├── stocks/[code]/page.tsx
    │   └── strategies/page.tsx
    ├── components/
    │   ├── charts/
    │   └── ui/
    └── lib/
        ├── api.ts
        ├── format.ts
        ├── types.ts
        └── utils.ts
```

## 一键启动

需要本机已安装：

- Python 3.10+
- Node.js 20.9+
- npm

在项目根目录执行：

```bash
npm run dev
```

脚本会执行：

1. 创建 `backend/.venv`
2. 安装后端依赖
3. 启动 FastAPI：`http://127.0.0.1:8000`
4. 安装前端依赖
5. 启动 Next.js：`http://127.0.0.1:3000`

如果端口被占用，可以指定端口：

```bash
WEB_PORT=3002 API_PORT=8000 npm run dev
```

也可以分开启动：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## 示例数据

后端首次启动会自动：

- 创建 SQLite 数据库：`data/quant_research.sqlite3`
- 初始化 `Stock / DailyPrice / Strategy / Signal / BacktestResult / Review / RiskRule`
- 生成 12 只示例股票的历史行情
- 初始化三个内置策略
- 自动运行一次启用策略生成候选池

示例行情是本地模拟数据，只用于功能演示和研究流程验证。

## AKShare 真实数据源

当前已接入 AKShare 作为第一版真实 A 股数据源。手动点击“更新并运行策略”时，后端默认执行：

1. `tracked` 模式读取当前本地股票池；`all` 模式读取 AKShare 东方财富 A 股实时行情列表
2. 同步真实日线历史行情
3. 写入现有 `stocks` 与 `daily_prices`
4. 执行启用策略并生成当天候选池

默认配置适合本地快速验证：

```bash
NEXT_PUBLIC_APP_NAME=Felix量化
MARKET_DATA_SOURCE=akshare
AKSHARE_STOCK_SCOPE=tracked
AKSHARE_HISTORY_DAYS=180
AKSHARE_ADJUST=qfq
AKSHARE_SYNC_INDUSTRY=false
```

配置说明：

- `MARKET_DATA_SOURCE`：`akshare` 或 `sample`。需要回到演示行情时可设为 `sample`。
- `AKSHARE_STOCK_SCOPE`：`tracked` 只更新当前本地股票池并直接拉日线，`all` 尝试同步全 A 股。第一阶段建议使用 `tracked`，避免全市场列表分页和逐只日线同步过慢。
- `AKSHARE_HISTORY_DAYS`：同步最近多少个交易日附近的历史日线。
- `AKSHARE_ADJUST`：传给 AKShare 的复权参数，默认 `qfq` 前复权。
- `AKSHARE_SYNC_INDUSTRY`：是否尝试同步行业成分映射。全行业映射请求较多，默认关闭，优先沿用本地行业字段。

也可以通过接口显式指定：

```bash
curl -X POST "http://127.0.0.1:8000/api/data/update?source=akshare&scope=tracked"
curl -X POST "http://127.0.0.1:8000/api/data/update?source=sample"
```

注意：AKShare 是免费聚合数据源，接口稳定性和字段变化取决于上游网站。本系统会把同步失败的股票记录在接口返回的 `failed` 字段里，便于排查。

如果本机尚未安装 AKShare，默认更新会返回 `fallback_reason` 并继续使用示例行情，避免页面中断；显式请求 `source=akshare` 会返回 503，方便确认真实数据源是否已经就绪。

## 内置策略

策略 A：均线趋势策略

- MA20 > MA60
- 当前价格 > MA20
- 最近 20 日涨幅为正
- 成交量大于 20 日均量

策略 B：低回撤趋势策略

- 近 60 日收益为正
- 近 60 日最大回撤小于阈值
- 波动率低于市场平均附近
- 价格处于中期上升趋势

策略 C：多因子评分策略

- 动量因子
- 波动率因子
- 成交量因子
- 回撤因子
- 趋势因子
- 输出 0-100 综合评分

## API 概览

数据接口：

- `GET /api/stocks`
- `GET /api/stocks/{code}`
- `GET /api/stocks/{code}/prices`
- `POST /api/data/update`

策略接口：

- `GET /api/strategies`
- `POST /api/strategies`
- `PUT /api/strategies/{id}`
- `POST /api/strategies/{id}/run`

信号接口：

- `GET /api/signals/today`
- `GET /api/signals`
- `GET /api/signals/{id}`

回测接口：

- `POST /api/backtest/run`
- `GET /api/backtest/results`
- `GET /api/backtest/results/{id}`

风控接口：

- `GET /api/risk/overview`
- `GET /api/risk/rules`
- `PUT /api/risk/rules/{id}`

复盘接口：

- `GET /api/reviews`
- `POST /api/reviews`
- `PUT /api/reviews/{id}`
- `DELETE /api/reviews/{id}`

## 后续扩展方式

真实行情数据源：

- 已新增 `backend/app/services/akshare_provider.py`
- `market_service.update_market_data` 支持 `akshare` 与 `sample`
- 后续可继续抽象为多数据源 Provider，接入 Tushare / Wind / Choice / iFinD

定时任务：

- 使用 `APScheduler`
- 调度链路为：更新行情 -> 计算指标 -> 执行启用策略 -> 写入信号 -> 生成摘要
- 第一阶段已通过 `POST /api/data/update` 支持手动触发同一流程

PostgreSQL：

- 当前数据访问集中在 `backend/app/db/database.py` 与 service 层 SQL
- 可逐步迁移到 SQLAlchemy 或 SQLModel
- 数据模型字段已按后续迁移预留

多策略组合：

- 在 `signals` 基础上增加组合权重表
- 回测服务中按策略权重聚合每日收益
- 风控页增加策略级回撤、连续亏损和失效观察状态

AI 自动复盘：

- 可在 `reviews` 基础上新增 `ai_summary`
- 输入信号、价格走势、执行结果和标签
- 输出结构化误判原因、纪律问题、市场状态和后续改进建议
