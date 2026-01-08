# app/config.py

# --- 基础设置 ---
SYMBOL_NAME = "XAUUSD"
MAGIC_NUMBER = 251211979

# --- [1] 时间设置 (北京时间) ---
IS_WINTER_TIME = True  

# 平台结算风控 (北京时间 05:00 - 07:00)
ROLLOVER_START_H_BJ = 5  
ROLLOVER_END_H_BJ = 7

# --- [新增] 交易时间过滤 (北京时间) ---
# 禁止开单时段: 凌晨 03:00 - 早上 09:30 (低流动性 + 垃圾时间)
NO_TRADE_START_H_BJ = 3
NO_TRADE_END_H_BJ = 9.5  # 9:30 用小数表示    

# --- [3] 资金管理 (固定风险模型) ---
RISK_PER_TRADE_USD = 30.0  
MIN_LOT = 0.01
MAX_LOT = 0.03             
MAX_POSITIONS_COUNT = 3    

# --- 减仓设置 ---
PARTIAL_CLOSE_LOT = 0.01

# --- 风险管理 ---
INITIAL_BALANCE = 1000.0
MAX_DRAWDOWN_PERCENT = 5
MIN_MARGIN_LEVEL = 500.0

# --- [2] 点差限制 (全 ATR 化) ---
# [修改] 不再使用固定值，改为 ATR 的百分比
# 假设 ATR=5美金，允许点差 1.0美金 (20%)。
MAX_SPREAD_ATR_RATIO = 0.3  # 从 0.2 提升到 0.3，增加容错
SPREAD_FLOOR_POINTS = 800   # [修改] 从 400 提升到 800 (0.8美金)，确保 EBC 标准账户能成交

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
SLOPE_FLAT_ATR = 0.20   # [微调] 之前是 0.15，提高一点容错
AB_RANGE_CROSSINGS = 5  
COMPRESSION_ATR_BARBWIRE = 2.0 # [新增] Barbwire 专用阈值
COMPRESSION_ATR = 3.0   

# [新增] 阶段定义阈值 (10根K线幅度)
# Stage 4 (极度压缩): 幅度 < 1.5 ATR
STAGE4_THRESHOLD_ATR = 1.5
# Stage 3 (震荡): 幅度 < 4.0 ATR (且 > 1.5 ATR)
STAGE3_THRESHOLD_ATR = 4.0   

# [L5] 挂单距离
MIN_TICK_SIZE = 0.20 

# 风控时间
NEWS_PADDING_MINUTES = 30
# [新增] 亏损/止损后冷却时间 (分钟)
COOLDOWN_AFTER_LOSS_MINUTES = 15
