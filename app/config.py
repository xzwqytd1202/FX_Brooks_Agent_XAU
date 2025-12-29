# app/config.py

# --- 基础设置 ---
SYMBOL_NAME = "XAUUSD"
MAGIC_NUMBER = 999999

# --- [1] 时间设置 (北京时间) ---
# IS_WINTER_TIME: True=冬令时(11月-3月), False=夏令时
# 现在的12月是冬令时，设为 True
IS_WINTER_TIME = True  

# 平台结算风控 (北京时间 05:00 - 07:00 通常是美盘收盘到亚盘开盘前，点差最大)
ROLLOVER_START_H_BJ = 5  
ROLLOVER_END_H_BJ = 7    

# --- [3] 资金管理 (固定风险模型) ---
RISK_PER_TRADE_USD = 30.0  # 单笔亏损限制 30 美金
MIN_LOT = 0.01
MAX_LOT = 0.03             # 限制最大 0.03 手
MAX_POSITIONS_COUNT = 3    # 允许最大持仓 3 单

# --- 减仓设置 ---
PARTIAL_CLOSE_LOT = 0.01

# --- 风险管理 ---
INITIAL_BALANCE = 10000.0
MAX_DRAWDOWN_PERCENT = 0.15
MIN_MARGIN_LEVEL = 1000.0

# --- [2] 点差限制 (适配 EBC 0.2) ---
# 平时0.2，容忍到0.5 (500微点)。超过说明流动性异常。
MAX_SPREAD_ALLOWED = 500 

# --- [7] 数据长度保护 ---
MIN_HISTORY_FOR_ATR = 20  # K线不足20根不计算

# --- [8] Al Brooks 结构参数 (全 ATR 化 - 适配 4500+ 金价) ---

# [L1] K线特征
AB_TREND_BAR_ATR_RATIO = 0.6 

# [L3] 环境定义阈值
SLOPE_SPIKE_ATR = 0.5   
SLOPE_FLAT_ATR = 0.15   
AB_RANGE_CROSSINGS = 5  
COMPRESSION_ATR = 3.0   

# [L5] 挂单距离
# 动态计算缓冲，但在低波幅时保留一个物理最小值 0.2 美金
MIN_TICK_SIZE = 0.20 

# 风控时间
NEWS_PADDING_MINUTES = 30
