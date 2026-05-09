export type GuideCalloutType = "info" | "warning" | "danger" | "success" | "tip";

export type GuideImageAsset = {
  src: string;
  title: string;
  caption: string;
};

export type GuideStep = {
  title: string;
  text: string;
  bullets?: string[];
};

export type GuideCallout = {
  type: GuideCalloutType;
  title: string;
  text: string;
};

export type GuideFAQItem = {
  question: string;
  answer: string;
};

export type GuideTerm = {
  term: string;
  definition: string;
};

export type GuideSection = {
  id: string;
  title: string;
  description: string;
  scenario: string;
  image?: GuideImageAsset;
  steps: GuideStep[];
  results: string[];
  pitfalls: string[];
  callouts?: GuideCallout[];
  faq?: GuideFAQItem[];
  terms?: GuideTerm[];
};

const tutorialImages = {
  dashboard: {
    src: "/tutorial/dashboard-overview.png",
    title: "Dashboard 总览",
    caption: "每日打开系统后，优先查看今日决策结论、数据更新时间、策略收益雷达和候选分层。"
  },
  taskProgress: {
    src: "/tutorial/task-progress.png",
    title: "异步任务进度",
    caption: "长任务会展示当前阶段、进度、处理数量、成功失败数量和最近状态，不需要一直盯着转圈。"
  },
  candidates: {
    src: "/tutorial/candidates-page.png",
    title: "候选池页面",
    caption: "候选池按主观察、热点观察、防御观察、风险观察和复盘池分层，长原因进入详情查看。"
  },
  stockInspector: {
    src: "/tutorial/stock-inspector.png",
    title: "一键诊股",
    caption: "输入股票代码、名称或行业后打开研报式诊断，查看评级、风险、触发条件和数据可信度。"
  },
  backtest: {
    src: "/tutorial/backtest-page.png",
    title: "回测验证",
    caption: "回测页支持单策略回测和多策略批量回测，参数区包含股票池、周期、交易成本和风控参数。"
  },
  performance: {
    src: "/tutorial/strategy-performance.png",
    title: "策略收益看板",
    caption: "策略收益来自 strategy_nav_daily 与 strategy_performance_summary，用于观察策略近期适配度。"
  },
  risk: {
    src: "/tutorial/risk-center.png",
    title: "风险中枢",
    caption: "风险中枢统一展示基础风控上限、市场状态修正和今日最终仓位口径。"
  },
  data: {
    src: "/tutorial/data-center.png",
    title: "数据中心",
    caption: "数据中心用于同步全市场股票池、查看失败记录、补抓失败股票和任务状态。"
  }
} satisfies Record<string, GuideImageAsset>;

export const guideSections: GuideSection[] = [
  {
    id: "quick-start",
    title: "快速开始",
    description: "先理解 Felix量化 是什么、每天先看哪里，以及推荐的操作顺序。",
    scenario: "第一次打开系统，想在 5 分钟内知道从哪里开始。",
    image: tutorialImages.dashboard,
    steps: [
      {
        title: "先看 Dashboard",
        text: "Dashboard 是每日入口，优先看今日决策结论、数据更新时间、市场状态和策略收益雷达。"
      },
      {
        title: "确认数据更新时间",
        text: "顶部 Header 会显示数据更新时间；如果数据较旧，先点击“手动刷新数据与策略”或进入数据中心同步。"
      },
      {
        title: "按流程进入候选和诊股",
        text: "查看候选池后，对重点观察标的使用一键诊股，再用回测验证策略样本和可信度。"
      }
    ],
    results: [
      "能判断今天是等待、防御观察、谨慎观察、小仓试探还是风险关闭。",
      "知道主观察清单、热点观察清单和风险观察池分别怎么用。",
      "知道策略收益和回测结果是否足够可信。"
    ],
    pitfalls: [
      "不要把评级、候选或回测收益当成交易指令。",
      "不要在数据更新时间异常时使用强结论。",
      "不要用样本不足的胜率或夏普比率判断策略有效。"
    ],
    callouts: [
      {
        type: "warning",
        title: "免责声明",
        text: "本系统仅用于个人量化研究和投资复盘，不构成任何投资建议。投资有风险，决策需谨慎。"
      }
    ]
  },
  {
    id: "daily-flow",
    title: "每日使用流程",
    description: "按照固定步骤从数据、策略、候选、诊股、回测到复盘完成每日闭环。",
    scenario: "每天开盘后或收盘后做一次完整研究流程。",
    image: tutorialImages.taskProgress,
    steps: [
      {
        title: "Step 1：确认数据是否已更新",
        text: "查看顶部数据更新时间、Dashboard 数据质量和数据中心同步状态。"
      },
      {
        title: "Step 2：点击“手动刷新数据与策略”",
        text: "等待每日流水线完成；系统会同步快照、构建重点股票池、补抓失败股票、计算因子、运行策略并生成每日决策。"
      },
      {
        title: "Step 3：查看今日决策结论",
        text: "重点看今日模式、建议总仓位、允许动作、禁止动作和等待什么信号。"
      },
      {
        title: "Step 4：查看候选池",
        text: "优先看主观察清单和热点观察清单；风险观察池只用于风险跟踪和复盘。"
      },
      {
        title: "Step 5：一键诊股与回测验证",
        text: "对重点股票打开一键诊股；对策略用单策略或批量回测验证样本、收益、回撤和可信度。"
      },
      {
        title: "Step 6：写入复盘",
        text: "记录市场状态、今日主线、候选变化、人工判断、错过机会和明日跟踪点。"
      }
    ],
    results: [
      "每日研究路径稳定，不会只盯候选股票。",
      "能把系统信号、人工判断和复盘记录串起来。",
      "长任务可通过任务进度条确认是否仍在运行。"
    ],
    pitfalls: [
      "如果任务超过 30 秒，不代表页面卡死，请先看任务进度条。",
      "全市场同步进行中时，暂缓重复点击顶部“手动刷新数据与策略”。",
      "主观察为空时，要先看数据质量、策略状态和市场状态原因。"
    ]
  },
  {
    id: "dashboard",
    title: "Dashboard 怎么看",
    description: "解释首页的今日决策、市场状态、主线识别、策略收益和候选分层。",
    scenario: "想知道今天系统到底给出什么研究结论。",
    image: tutorialImages.dashboard,
    steps: [
      {
        title: "看今日决策结论",
        text: "这是每天最先看的模块，回答今天是否适合行动。字段包括今日模式、市场状态、建议总仓位、允许动作、禁止动作、核心原因和等待信号。"
      },
      {
        title: "看今日行情快照",
        text: "关注指数涨跌、成交额、上涨家数、涨停跌停数量和最强方向，确认市场状态是否有现实依据。"
      },
      {
        title: "看市场状态与今日主线",
        text: "RiskOn、Recovery、Choppy、RiskOff、Panic 代表不同市场环境；今日主线用于判断科技成长、消费、金融、周期、防御等方向是否成立。"
      },
      {
        title: "看策略收益雷达",
        text: "先判断哪些策略近期有效、哪些样本不足或需要复盘，再决定候选信号是否值得深入。"
      },
      {
        title: "看观察清单和风险池",
        text: "主观察清单用于重点跟踪；风险观察池仅用于风险跟踪和复盘，不作为行动依据。"
      }
    ],
    results: [
      "能快速判断系统处于等待、防御观察、谨慎观察、小仓试探还是风险关闭。",
      "能看到候选为空时是市场原因、数据原因还是策略原因。",
      "能理解策略表现对今日信号可信度的影响。"
    ],
    pitfalls: [
      "不要只看候选数量，要看可行动候选、风险比例和策略健康度。",
      "今日主线可信度低时，不要把行业估算线索当成强主线。",
      "风险观察池数量多不一定代表不能研究，但不应作为行动依据。"
    ]
  },
  {
    id: "data-sync",
    title: "如何同步数据",
    description: "说明数据中心、全市场同步、失败补抓、增量日线和任务进度。",
    scenario: "候选股票总是少数几只、策略收益数据不足，或数据更新时间过旧。",
    image: tutorialImages.data,
    steps: [
      {
        title: "进入数据中心",
        text: "左侧点击“数据中心”，查看当前股票池、行业覆盖、同步状态和最近同步结果。"
      },
      {
        title: "同步全市场股票池",
        text: "在“同步参数”输入同步数量上限，例如 800，然后点击“同步全市场股票池”。首次建议先用 500-1000 验证链路。"
      },
      {
        title: "查看同步进度",
        text: "观察当前阶段、进度百分比、成功失败数量、重试次数、已耗时和失败样例。"
      },
      {
        title: "补抓失败股票",
        text: "部分股票受网络或上游接口影响失败时，点击“补抓失败股票”。失败记录会进入队列，成功后标记为 recovered。"
      }
    ],
    results: [
      "股票池从小样本扩展到更广泛市场，减少候选长期集中在少数蓝筹。",
      "失败股票不会阻塞整个同步任务。",
      "同步完成后可返回顶部点击“手动刷新数据与策略”。"
    ],
    pitfalls: [
      "AKShare 免费数据源可能限流或字段变动，单只股票失败并不代表系统整体失败。",
      "不要每次都从很早历史全量重拉，优先使用增量同步和补抓。",
      "全市场日线同步较慢时，先保证今日快照和重点股票池可用。"
    ],
    callouts: [
      {
        type: "tip",
        title: "失败重试机制",
        text: "失败股票最多自动重试 3 次，仍失败会写入失败记录，后续可一键补抓。"
      }
    ]
  },
  {
    id: "run-strategies",
    title: "如何手动刷新数据与策略",
    description: "解释顶部“手动刷新数据与策略”按钮和每日流水线执行阶段。",
    scenario: "数据已经更新，想生成今日决策、候选池和策略结果。",
    image: tutorialImages.taskProgress,
    steps: [
      {
        title: "点击顶部按钮",
        text: "顶部 Header 右侧点击“手动刷新数据与策略”。如果全市场同步正在运行，系统会提示稍后再运行。"
      },
      {
        title: "观察每日流水线",
        text: "流水线包括检查交易日、同步市场快照、构建重点股票池、补抓失败股票、同步重点日线、计算因子、识别市场状态和今日主线。"
      },
      {
        title: "等待候选和决策生成",
        text: "后续阶段会运行策略、风控分层、生成每日决策并写入结果。完成后 Dashboard 自动刷新。"
      }
    ],
    results: [
      "Dashboard 出现最新今日决策结论。",
      "候选池更新为主观察、热点观察、防御观察、风险观察和复盘池。",
      "策略收益、风险中枢和复盘页可读取最新任务结果。"
    ],
    pitfalls: [
      "不要重复点击导致同类任务并发运行。",
      "任务慢时先看当前阶段，判断卡在数据同步、因子计算还是策略运行。",
      "如果数据不足，策略仍可运行，但结论会降级。"
    ]
  },
  {
    id: "candidates",
    title: "如何查看候选池",
    description: "理解候选池分层、筛选、详情抽屉和不同候选类型的用途。",
    scenario: "想查看今日系统筛出的观察标的，并区分主线、趋势、防御和风险池。",
    image: tutorialImages.candidates,
    steps: [
      {
        title: "优先看主观察清单",
        text: "主观察清单要求风险可控、策略条件较完整、finalScore 达标，并且市场状态允许该策略启用。"
      },
      {
        title: "RiskOn / Recovery 看热点观察",
        text: "热点观察清单展示主线相关强势候选，可为中风险，但必须人工确认。"
      },
      {
        title: "RiskOff / Choppy 看防御观察",
        text: "防御观察清单主要来自低波防御、质量动量或低回撤策略。"
      },
      {
        title: "风险池只用于复盘",
        text: "风险观察池包含高风险或暂不参与标的；复盘池包含曾触发但不满足当前条件的标的。"
      }
    ],
    results: [
      "能按策略类型、候选类型、风险等级、建议动作和行业题材筛选。",
      "表格只展示核心字段，长入选原因、风险理由和原始因子在详情中查看。",
      "可从候选跳转一键诊股、回测或复盘。"
    ],
    pitfalls: [
      "不要把风险观察池当作主观察清单。",
      "热点观察候选需要确认数据覆盖和题材可信度。",
      "候选长期重复时，应先检查股票池规模、热点数据和策略收益是否有效。"
    ]
  },
  {
    id: "stock-inspector",
    title: "如何使用一键诊股",
    description: "使用 Stock Inspector 生成个股研报式评级和风险说明。",
    scenario: "想对某一只股票做基本面、技术面、情绪面、资金面和风险面的综合诊断。",
    image: tutorialImages.stockInspector,
    steps: [
      {
        title: "搜索股票",
        text: "左侧点击“一键诊股”，输入股票代码、名称或行业，选择对应标的。"
      },
      {
        title: "查看研报式评级",
        text: "报告顶部展示研究评级、综合评分、风险等级、数据可信度、市场状态和目标价区间是否可估算。"
      },
      {
        title: "拆解五维评分",
        text: "依次查看基本面、技术面、情绪面、资金面和风险面的分项解释。"
      },
      {
        title: "关注评级调整条件",
        text: "重点看评级上调条件、评级下调条件、看多理由、看空风险和数据完整性说明。"
      }
    ],
    results: [
      "可输出买入、增持、持有、减持、卖出或无法评级等研究评级。",
      "买入或卖出评级会展示依据、适用前提、失效条件和主要风险。",
      "数据可信度低时，系统会限制激进评级。"
    ],
    pitfalls: [
      "评级是研究结论表达，不是交易指令。",
      "停牌、ST、上市时间过短或关键数据缺失时可能无法评级。",
      "目标价区间数据不足时，系统不会编造具体价格。"
    ],
    callouts: [
      {
        type: "warning",
        title: "评级边界",
        text: "一键诊股生成的评级仅用于个人量化研究和投资复盘，不构成任何投资建议或交易指令。"
      }
    ]
  },
  {
    id: "single-backtest",
    title: "如何执行单策略回测",
    description: "说明回测验证页的单策略模式、参数、快捷周期和可信度卡片。",
    scenario: "想验证一个策略在某个区间和股票池中的历史表现。",
    image: tutorialImages.backtest,
    steps: [
      {
        title: "选择单策略回测",
        text: "进入“回测”页面，保持模式为“单策略回测”。"
      },
      {
        title: "设置基础参数",
        text: "选择回测策略、回测股票池、开始日期和结束日期。默认周期为近一年。"
      },
      {
        title: "选择快捷周期",
        text: "可点击近一月、近三月、近半年、近一年、近两年或自定义。"
      },
      {
        title: "设置成本和风控",
        text: "填写初始资金、手续费率、滑点率、止损比例、止盈比例、单票最大仓位、最大持仓数量和最大持仓天数。"
      },
      {
        title: "异步执行回测",
        text: "点击执行后会创建 run_backtest 任务，并展示检查参数、数据覆盖、加载行情、生成信号、模拟交易和刷新收益汇总等阶段。"
      }
    ],
    results: [
      "回测结果展示总收益、年化收益、最大回撤、夏普、胜率、盈亏比、交易次数和平均持仓天数。",
      "可信度卡片会标注可信、需谨慎、样本不足、数据不足或仅功能验证。",
      "走势图为空时会提示缺少 strategy_nav_daily。"
    ],
    pitfalls: [
      "示例股票池只用于功能验证，不作为策略有效性依据。",
      "交易次数少于 30 时，不应把胜率、夏普、年化收益当成有效结论。",
      "短区间年化收益属于外推，必须谨慎参考。"
    ]
  },
  {
    id: "batch-backtest",
    title: "如何执行批量回测",
    description: "使用多策略批量回测横向比较策略表现。",
    scenario: "想一次性验证多个策略在同一股票池、区间和风控参数下的表现。",
    image: tutorialImages.backtest,
    steps: [
      {
        title: "切换到多策略批量回测",
        text: "在回测页顶部模式切换中选择“多策略批量回测”。"
      },
      {
        title: "多选策略",
        text: "策略选择器支持全选、只选启用策略、只选有效策略、排除仅复盘 / 暂停策略和搜索策略名称。"
      },
      {
        title: "设置共享参数",
        text: "股票池、周期、交易成本和风控参数会对所有选中策略生效。"
      },
      {
        title: "一键执行批量回测",
        text: "系统创建 batch_backtest 父任务，并为每个策略创建 run_backtest 子任务。默认有限并发，单个策略失败不影响其他策略继续运行。"
      }
    ],
    results: [
      "可查看整体进度、每个策略子任务状态、成功失败数量和最近日志。",
      "完成后展示批量回测结果汇总和多策略净值对比图。",
      "结果会写入 backtest_results、strategy_nav_daily 和 strategy_performance_summary。"
    ],
    pitfalls: [
      "暂停或仅复盘策略可以用于验证，但不应作为主策略依据。",
      "股票池为空时需要先同步数据或切换股票池。",
      "批量回测用于横向比较，不代表未来收益。"
    ]
  },
  {
    id: "strategy-performance",
    title: "如何查看策略收益",
    description: "理解策略收益看板、净值曲线、周期收益和数据不足提示。",
    scenario: "想知道哪些策略近期有效，哪些策略失效或需要复盘。",
    image: tutorialImages.performance,
    steps: [
      {
        title: "查看策略收益表格",
        text: "表格展示近 1 月、近 3 月、近半年、近 1 年收益，1 年回撤、胜率、交易次数、夏普和可信度。"
      },
      {
        title: "查看净值走势图",
        text: "走势图来自 strategy_nav_daily，支持多策略净值曲线、回撤图、每日收益和热力图。"
      },
      {
        title: "用按钮修复数据",
        text: "若提示缺少每日净值或收益汇总，可点击“生成策略净值”“刷新收益汇总”或“执行长期回测”。"
      },
      {
        title: "刷新并回测启用策略",
        text: "可点击“刷新并回测全部启用策略”，用批量回测补齐策略收益链路。"
      }
    ],
    results: [
      "能区分可信、样本不足、数据不足和需谨慎。",
      "能看到当前最强策略、回撤最大策略和建议启用策略。",
      "策略收益用于评估近期适配度，不代表未来收益。"
    ],
    pitfalls: [
      "不要把 0.0% 当成真实收益；页面会标记缺少 NAV 的异常记录。",
      "strategy_nav_daily 为空时，走势图不会绘制假图。",
      "tradeCount 小于 30 的策略不参与有效性排序。"
    ]
  },
  {
    id: "risk-center",
    title: "如何查看风险中枢",
    description: "理解基础风控、市场状态修正和今日最终仓位的统一口径。",
    scenario: "想确认今日仓位口径、行业集中度、高风险股票和风控预警。",
    image: tutorialImages.risk,
    steps: [
      {
        title: "看仓位三层口径",
        text: "风控页展示基础风控上限、市场状态上限、策略质量上限和今日最终仓位。"
      },
      {
        title: "看行业集中度",
        text: "行业集中度用于识别候选池或观察池是否过度集中在单一行业。"
      },
      {
        title: "看风控预警",
        text: "重点查看 Dashboard 与风控仓位是否一致、高风险股票数量、风险观察池数量、数据质量风险和回测可信度风险。"
      },
      {
        title: "检查高风险股票池",
        text: "高风险股票池只用于风险跟踪和复盘，不作为今日行动依据。"
      }
    ],
    results: [
      "清楚基础风控上限不等于今日最终建议仓位。",
      "能解释为什么 Dashboard 和风控页仓位口径一致。",
      "能定位数据质量和回测可信度对风控的影响。"
    ],
    pitfalls: [
      "不要只看基础风控上限，今日最终仓位由 DecisionEngine 修正。",
      "高风险数量多时，应先复盘策略阈值和数据质量。",
      "风控规则修改后要重新运行策略或刷新页面确认结果。"
    ]
  },
  {
    id: "daily-review",
    title: "如何做每日复盘",
    description: "记录系统判断、人工结论、策略有效性和次日跟踪点。",
    scenario: "收盘后复盘今日策略表现，或记录人工确认过程。",
    steps: [
      {
        title: "记录市场状态",
        text: "写下 MarketRegime、今日主线、决策模式、允许动作和禁止动作。"
      },
      {
        title: "记录观察池变化",
        text: "列出主观察、热点观察、防御观察和风险观察股票，以及新进入和退出标的。"
      },
      {
        title: "记录人工判断",
        text: "对系统结论做人工确认，说明接受、保留还是否决的原因。"
      },
      {
        title: "记录明日跟踪点",
        text: "记录市场状态切换条件、评级上调/下调条件、策略是否需要复盘。"
      }
    ],
    results: [
      "形成每日可追溯的研究记录。",
      "能回看哪些风险被验证、哪些机会被错过。",
      "有助于改进策略参数和数据源。"
    ],
    pitfalls: [
      "不要只记录结果，要记录当时的数据质量和策略可信度。",
      "不要把复盘写成事后解释，要保留原始判断依据。",
      "候选为空也要记录原因。"
    ],
    callouts: [
      {
        type: "info",
        title: "复盘模板",
        text: "今日市场状态：；今日主线：；决策模式：；主观察：；风险观察：；人工结论：；策略有效性：；错过机会：；明日跟踪点：。"
      }
    ]
  },
  {
    id: "data-quality",
    title: "如何判断数据是否可信",
    description: "检查行情、题材、涨停、财务、回测和偏差风险。",
    scenario: "页面提示数据不足、样本不足、热点数据缺失或回测可信度低。",
    image: tutorialImages.data,
    steps: [
      {
        title: "检查行情和日线",
        text: "确认行情数据是否更新、日线数据是否完整、失败股票是否已补抓。"
      },
      {
        title: "检查热点相关数据",
        text: "看涨停、炸板、连板、概念题材和板块资金是否接入；缺失时热点策略会降级估算。"
      },
      {
        title: "检查财务和复权数据",
        text: "财务数据未按公告日期处理可能存在前视偏差；复权因子缺失会影响历史收益计算。"
      },
      {
        title: "检查回测可信度",
        text: "确认手续费、滑点、ST/停牌/退市处理、样本数量、数据覆盖率和幸存者偏差。"
      }
    ],
    results: [
      "能判断结论是否可用于研究，还是只能用于功能验证。",
      "能解释为什么热点策略、今日主线或策略收益被标记为数据不足。",
      "能知道下一步是补齐历史数据、生成 NAV、刷新汇总还是扩大回测区间。"
    ],
    pitfalls: [
      "数据可信度低时不要使用强结论。",
      "样本不足和数据不足不是同一个问题：前者是交易次数不够，后者是净值或行情覆盖不够。",
      "上游数据源失败时，先补抓失败股票，不要从头全量重跑。"
    ]
  },
  {
    id: "alpha-lab",
    title: "AlphaLab 与研究报告",
    description: "了解 Alpha 因子实验室和研究报告入口在日常流程中的位置。",
    scenario: "想做公式化 Alpha 研究，或查看策略、数据和回测的研究记录。",
    steps: [
      {
        title: "进入 AlphaLab",
        text: "AlphaLab 用于查看 Alpha 列表、IC、RankIC、分组收益、换手率和是否进入候选研究池。"
      },
      {
        title: "只用于研究和复盘",
        text: "AlphaLab 第一版结果不直接进入主观察清单，主要用于因子有效性研究。"
      },
      {
        title: "查看研究报告",
        text: "研究报告入口用于整理策略来源、回测可信度、数据质量和复盘结果。"
      }
    ],
    results: [
      "能区分主观察信号和研究型 Alpha 结果。",
      "能用研究报告沉淀策略和数据源问题。",
      "避免把实验因子直接当成交易结论。"
    ],
    pitfalls: [
      "Alpha 因子需要长期样本和回测验证。",
      "单日表现不能证明 Alpha 有效。",
      "不要将 AlphaLab 改名或误解为策略推荐区。"
    ]
  },
  {
    id: "faq",
    title: "常见问题",
    description: "回答使用过程中最容易遇到的问题。",
    scenario: "遇到等待、数据不足、候选很少、回测样本不足或诊股无法评级。",
    steps: [
      {
        title: "先定位问题类型",
        text: "多数问题来自市场状态、数据覆盖、任务未完成、策略样本不足或风控阈值。"
      },
      {
        title: "再看修复按钮",
        text: "策略收益看板、数据中心和回测页都有对应的数据修复或任务按钮。"
      }
    ],
    results: [
      "能快速判断是需要同步数据、运行策略、生成 NAV、回测还是补抓失败股票。",
      "能避免重复启动长任务。"
    ],
    pitfalls: [
      "不要同时启动多个同类长任务。",
      "不要忽略页面上的数据不足和样本不足标签。"
    ],
    faq: [
      {
        question: "为什么 Dashboard 显示等待？",
        answer: "通常是市场状态偏弱、主观察清单为空、策略平均分不足或风险候选比例过高。也可能是关键数据缺失导致策略无法参与今日决策。"
      },
      {
        question: "为什么候选股票很少？",
        answer: "可能是风控条件严格、数据不完整、市场没有明确主线、策略被暂停或仅复盘，也可能是股票池规模还没有扩展。"
      },
      {
        question: "为什么策略收益显示数据不足？",
        answer: "说明还没有生成足够的 strategy_nav_daily，或 strategy_performance_summary 没有刷新，也可能是回测交易样本不足。"
      },
      {
        question: "为什么回测胜率很高但系统提示样本不足？",
        answer: "交易次数太少时，胜率、夏普和年化收益统计意义弱。系统用 30 笔交易作为第一版样本阈值。"
      },
      {
        question: "为什么一键诊股显示无法评级？",
        answer: "可能是数据缺失、停牌、ST、上市时间过短、硬风险触发或风险等级过高。"
      },
      {
        question: "手动刷新数据与策略很慢怎么办？",
        answer: "查看任务进度条，确认是否卡在数据同步、补抓失败股票、因子计算或策略运行阶段。全市场同步较慢时可先同步重点股票池。"
      }
    ]
  },
  {
    id: "glossary",
    title: "术语解释",
    description: "解释 Felix量化 中常见市场状态、池子、回测和数据术语。",
    scenario: "看页面标签时不确定具体含义。",
    steps: [
      {
        title: "先理解市场状态",
        text: "MarketRegime 决定策略启停、候选分层和仓位口径。"
      },
      {
        title: "再理解数据和回测术语",
        text: "strategy_nav_daily、strategy_performance_summary、样本不足和数据不足会直接影响策略收益看板。"
      }
    ],
    results: [
      "能读懂 Dashboard、候选池、策略收益和回测页面的关键标签。",
      "能判断页面结论是否可用于研究。"
    ],
    pitfalls: [
      "术语只是系统口径，不代表任何收益承诺。",
      "不同页面看到同一术语时，应以统一口径理解。"
    ],
    terms: [
      { term: "MarketRegime", definition: "市场状态模型，包含 RiskOn、Recovery、Choppy、RiskOff 和 Panic。" },
      { term: "RiskOn", definition: "风险偏好较强，趋势和热点策略权重提高，但仍需风控确认。" },
      { term: "Recovery", definition: "市场从弱势进入修复观察阶段，允许谨慎观察主线持续性。" },
      { term: "Choppy", definition: "震荡环境，质量动量、低波和低回撤策略优先。" },
      { term: "RiskOff", definition: "防御环境，趋势和热点策略降权，低波防御优先。" },
      { term: "Panic", definition: "恐慌环境，系统以观察和复盘为主。" },
      { term: "主观察清单", definition: "风险可控、策略条件较完整、市场状态允许的重点观察标的。" },
      { term: "热点观察清单", definition: "RiskOn / Recovery 下与主线相关的强势候选，需要人工确认。" },
      { term: "防御观察清单", definition: "弱势或震荡环境下的低波、质量和低回撤候选。" },
      { term: "风险观察池", definition: "高风险或暂不参与标的，仅用于风险跟踪和复盘。" },
      { term: "复盘池", definition: "曾触发策略但不满足当前行动条件的标的，用于策略验证。" },
      { term: "strategy_nav_daily", definition: "策略每日净值表，用于绘制净值走势图。" },
      { term: "strategy_performance_summary", definition: "策略周期收益汇总表，用于策略收益表格和 Dashboard 策略收益雷达。" },
      { term: "样本不足", definition: "交易次数过少，通常不宜用胜率、夏普或年化收益做有效性结论。" },
      { term: "数据不足", definition: "行情、净值或汇总覆盖不足，无法支撑完整展示或判断。" },
      { term: "最大回撤", definition: "净值从历史高点回落的最大幅度，衡量策略风险。" },
      { term: "夏普比率", definition: "收益相对波动的指标，样本不足时参考价值有限。" },
      { term: "胜率", definition: "盈利交易占完成交易的比例，交易次数少时不稳定。" },
      { term: "盈亏比", definition: "平均盈利与平均亏损的比例，用于观察收益结构。" },
      { term: "滑点", definition: "模拟成交价格偏差，短线策略尤其需要考虑。" },
      { term: "手续费", definition: "交易成本的一部分，回测不计入会高估收益。" },
      { term: "前视偏差", definition: "回测使用了当时不可获得的数据，导致结果失真。" },
      { term: "幸存者偏差", definition: "历史股票池只包含当前仍存在的股票，忽略退市或异常样本。" }
    ]
  }
];
