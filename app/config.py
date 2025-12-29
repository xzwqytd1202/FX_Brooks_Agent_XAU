# app/config.py

# --- 基础设置 ---
SYMBOL_NAME = "XAUUSD"
MAGIC_NUMBER = 999999

# --- [1] 时间设置 (北京时间) ---
IS_WINTER_TIME = True  

# 平台结算风控 (北京时间 05:00 - 07:00)
ROLLOVER_START_H_BJ = 5  
ROLLOVER_END_H_BJ = 7    

# --- [3] 资金管理 (固定风险模型) ---
RISK_PER_TRADE_USD = 30.0  
MIN_LOT = 0.01
MAX_LOT = 0.03             
MAX_POSITIONS_COUNT = 3    

# --- 减仓设置 ---
PARTIAL_CLOSE_LOT = 0.01

# --- 风险管理 ---
INITIAL_BALANCE = 10000.0
MAX_DRAWDOWN_PERCENT = 0.15
MIN_MARGIN_LEVEL = 1000.0

# --- [2] 点差限制 (全 ATR 化) ---
# [修改] 不再使用固定值，改为 ATR 的百分比
# 假设 ATR=5美金，允许点差 0.5美金 (10%)。ATR=2美金，允许0.2。
MAX_SPREAD_ATR_RATIO = 0.1 

# --- [7] 数据长度保护 ---
MIN_HISTORY_FOR_ATR = 20  

# --- [8] Al Brooks 结构参数 (全 ATR 化) ---

# [L1] K线特征
AB_TREND_BAR_ATR_RATIO = 0.6 

# [L2] 磁力效应 (Magnets)
# 如果 H1 信号距离 EMA 超过 1.0 倍 ATR，视为"过度延伸"，过滤掉 H1
AB_MAGNET_DISTANCE_ATR = 1.0 

# [L3] 环境定义阈值
SLOPE_SPIKE_ATR = 0.5   
SLOPE_FLAT_ATR = 0.15   
AB_RANGE_CROSSINGS = 5  
COMPRESSION_ATR = 3.0   

# [L5] 挂单距离
MIN_TICK_SIZE = 0.20 

# 风控时间
NEWS_PADDING_MINUTES = 30
