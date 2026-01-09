# app/config.py

# ==============================================================================
# SECTION A: STATIC / INFRASTRUCTURE (很少变动)
# ==============================================================================
SYMBOL_NAME = "XAUUSD"
MAGIC_NUMBER = 251211979

# [时间设置] 北京时间 (UTC+8)
IS_WINTER_TIME = True
# 平台结算风控 (北京时间)
ROLLOVER_START_H_BJ = 5
ROLLOVER_END_H_BJ = 7
# 交易业务时间 (过滤低流动性/垃圾时间)
NO_TRADE_START_H_BJ = 3
NO_TRADE_END_H_BJ = 9.5

# [数据保护]
MIN_HISTORY_FOR_ATR = 20
NEWS_PADDING_MINUTES = 30
COOLDOWN_AFTER_LOSS_MINUTES = 15

# ==============================================================================
# SECTION B: MONEY MANAGEMENT (资金管理 - 建议动态化)
# ==============================================================================
# 风险模型: "FIXED_USD" (每笔固定金额) 或 "PERCENT" (余额百分比)
RISK_MODEL = "FIXED_USD" 
RISK_PER_TRADE_USD = 30.0   # Fixed 模式使用
RISK_PERCENT = 0.02         # Percent 模式使用 (2%)

# 手数限制
MIN_LOT = 0.01
MAX_LOT = 0.10              # [修改] 放宽上限，由资金管理控制
MAX_POSITIONS_COUNT = 3
PARTIAL_CLOSE_LOT = 0.01

# 账户保护
INITIAL_BALANCE = 1000.0
MAX_DRAWDOWN_PERCENT = 5
MIN_MARGIN_LEVEL = 500.0

# ==============================================================================
# SECTION C: DYNAMIC MARKET PARAMS (基于 ATR 的动态参数)
# ==============================================================================

# [C1] 波动性与点差 (Volatility & Spread)
# ------------------------------------------------------------------------------
# 基础比率: 允许点差 = ATR * Ratio
MAX_SPREAD_ATR_RATIO = 0.3
# 物理底限: 即使 ATR 很小，也允许至少 800 微点 (0.8美金) 的点差
SPREAD_FLOOR_POINTS = 800

# [动态调整因子]
# 亚洲时段 (00:00 - 09:00 BJ): 波动率极低，放宽点差限制，否则无法开单
SESSION_ASIAN_SPREAD_FIX = 0.5   # 0.3 -> 0.5
# 核心/美盘时段 (14:00 - 22:00 BJ): 流动性好，要求更严
SESSION_CORE_SPREAD_FIX = 0.25   # 0.3 -> 0.25

# [C2] 趋势定义 (Trend Definition)
# ------------------------------------------------------------------------------
# 斜率阈值 (Slope Threshold in ATR)
SLOPE_SPIKE_ATR = 0.5  # 强趋势
SLOPE_FLAT_ATR = 0.20  # 震荡/平坦

# [动态调整因子]
# 当市场 Choppy (重叠度高) 时，提高 Flat 阈值，避免假信号
CHOPS_SLOPE_MULTIPLIER = 1.75  # 0.20 * 1.75 = 0.35

# [新增] Context Modifiers (Level 3 Dynamic)
# 从震荡(Range)中突破，需要更强的动力来证明不是假突破
SPIKE_FROM_RANGE_PENALTY = 0.20 # 0.5 + 0.2 = 0.7 ATR Slope required
# 已经在趋势中延续，只需要较小的动力
SPIKE_CONTINUATION_BONUS = 0.10 # 0.5 - 0.1 = 0.4 ATR Slope required

# [C3] K线力度 (Perception)
# ------------------------------------------------------------------------------
AB_TREND_BAR_ATR_RATIO = 0.6
AB_MAGNET_DISTANCE_ATR = 1.0

# [动态调整因子]
# 震荡市 (Stage 3): 假突破多，要求更强的实体才能算突破信号
RANGE_TREND_BAR_ADDON = 0.15   # 0.6 + 0.15 = 0.75
# 强趋势 (Stage 1): 顺势更重要，稍弱的 K 线也算趋势
TREND_S1_BAR_REDUCTION = 0.10  # 0.6 - 0.10 = 0.50

# [C4] 结构阈值 (Structure & Compression)
# ------------------------------------------------------------------------------
COMPRESSION_ATR = 3.0
COMPRESSION_ATR_BARBWIRE = 2.0
AB_RANGE_CROSSINGS = 5

STAGE4_THRESHOLD_ATR = 1.5
# [新增] 相对压缩阈值 (Relative Compression)
# Stage 4 不仅要是小 ATR，还要比最近平均实体小，防止巨震后的"相对平静"被误判
STAGE4_RELATIVE_BODY_RATIO = 2.0 

STAGE3_THRESHOLD_ATR = 4.0
MIN_TICK_SIZE = 0.20

# ==============================================================================
# SECTION D: EXECUTION HELPERS
# ==============================================================================
# 用于计算手数时的保底 ATR，防止 ATR=0 导致除零
MIN_SAFE_ATR = 0.5

