# ========================================
# AB Gold Agent 配置 (XAUUSD 专用)
# ========================================

# --- 1. 基础设置 ---
SYMBOL_NAME = "XAUUSD"
MAGIC_NUMBER = 888888

# --- 2. 仓位管理 (新增) ---
BASE_LOT_SIZE = 0.02       # 每次开单手数
MAX_TOTAL_VOLUME = 0.04    # 允许最大持仓
PARTIAL_CLOSE_LOT = 0.01   # 减仓手数

# --- 3. 风险管理 ---
INITIAL_BALANCE = 10000.0
MAX_DRAWDOWN_PERCENT = 0.15
MIN_MARGIN_LEVEL_PERCENT = 1000.0
FORCE_CLOSE_ON_DRAWDOWN = True
MAX_SPREAD_ALLOWED = 500  # 500微点 = 5 pips

# --- 4. 硬风控时间 (保留非农/结算，移除亚盘/美盘判断) ---
# 仅保留物理避险，不参与策略判断
# True = 冬令时 (11月-次年3月), False = 夏令时 (3月-11月)
IS_WINTER_TIME = True 
TIME_OFFSET = 6 if IS_WINTER_TIME else 5

NEWS_PADDING_MINUTES = 30 
ROLLOVER_START_H = 6 if IS_WINTER_TIME else 5  # 平台结算开始时间
ROLLOVER_END_H = 7 if IS_WINTER_TIME else 6    # 平台结算结束时间
FRIDAY_CUTOFF_H = 23

# --- 5. Al Brooks 结构参数 (纯技术指标) ---

# [L1] K线特征
AB_AVG_BODY_SIZE = 2.0    # 平均实体大小
AB_STRONG_BAR_RATIO = 1.5 # 强趋势K线倍数
AB_TAIL_RATIO = 0.4       # 影线比例
AB_CLOSE_ZONE = 0.2       # 收盘位置控制

# [L2] 结构参数
AB_MIN_PULLBACK_BARS = 1
AB_SWING_LOOKBACK = 5

# [L3] 环境定义阈值 (新增 - 用于4阶段识别)
AB_RANGE_EMA_SLOPE = 0.1  # EMA斜率绝对值小于此值 -> 震荡/区间
AB_RANGE_CROSSINGS = 5    # 过去20根K线穿过EMA的次数 > 5 -> 震荡
AB_TTR_COMPRESSION = 0.5  # 布林带带宽极度压缩 -> 突破模式

# [L5] 挂单距离
AB_TICK_SIZE = 0.10       # 挂单微调距离 (黄金0.1美金)
MIN_REWARD_RISK_RATIO = 1.0
