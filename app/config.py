# app/config.py

# --- 基础设置 ---
SYMBOL_NAME = "XAUUSD"
MAGIC_NUMBER = 999999
SERVER_PORT = 8002

# --- 仓位管理 ---
BASE_LOT_SIZE = 0.02
MAX_TOTAL_VOLUME = 0.1
PARTIAL_CLOSE_LOT = 0.01

# --- 风险管理 ---
INITIAL_BALANCE = 10000.0
MAX_DRAWDOWN_PERCENT = 0.15
MIN_MARGIN_LEVEL = 1000.0

# [修正] 点差限制需要放宽
# 价格翻倍，点差通常也会放大。假设现在点差允许到 1000 微点 (10 pips = $1.0)
MAX_SPREAD_ALLOWED = 1000 

# --- Al Brooks 结构参数 (全 ATR 化) ---

# [L1] K线特征 (移除绝对值)
# 定义趋势K线: 实体 > 0.6 倍 ATR (自适应)
AB_TREND_BAR_ATR_RATIO = 0.6 
AB_AVG_BODY_SIZE = 2.0  # Keep for backward compatibility if needed, but logic moving to ATR

# [L3] 环境定义阈值 (ATR倍数)
SLOPE_SPIKE_ATR = 0.5   # 强趋势斜率
SLOPE_FLAT_ATR = 0.15   # 震荡斜率
AB_RANGE_CROSSINGS = 5  # Keep
COMPRESSION_ATR = 3.0   # 10根K线波幅 < 3 ATR -> 突破模式
AB_RANGE_EMA_SLOPE = 0.1 # Keep for backward compat? No, Logic uses new consts.

# [L5] 挂单距离 (Tick Buffer)
# 在 4500 的价格下，0.1 美金太近了。建议改为动态计算，或设为 0.2-0.3
# 这里我们采用 "最小 0.2，或 0.05 ATR" 的逻辑，在代码里算
MIN_TICK_SIZE = 0.20 
AB_TICK_SIZE = 0.10 # Keep for backward compatibility if code refers to it

# 风控时间
NEWS_PADDING_MINUTES = 30 
ROLLOVER_START_H = 5
ROLLOVER_END_H = 7
FRIDAY_CUTOFF_H = 23

# System Flags
IS_WINTER_TIME = True
FORCE_CLOSE_ON_DRAWDOWN = True
