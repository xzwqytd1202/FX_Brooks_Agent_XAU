# app/schemas.py

from pydantic import BaseModel
from typing import List, Optional

# --- 基础数据模型 ---

class Candle(BaseModel):
    time: int           # 时间戳
    open: float
    high: float
    low: float
    close: float
    tick_vol: int
    spread: int

class NewsInfo(BaseModel):
    has_news: bool          
    impact_level: int       # 0=无, 1=低, 2=中, 3=高
    minutes_to_news: int    # 正数=未来, 负数=过去
    event_name: str         

class Position(BaseModel):
    ticket: int
    type: str               # "BUY" or "SELL"
    volume: float           # 持仓量 (新增: 用于仓位管理)
    open_price: float
    current_price: float
    sl: float
    tp: float
    profit: float           # 浮动盈亏
    comment: str

# --- 核心请求包 (MT5 -> Python) ---

class MarketData(BaseModel):
    symbol: str
    server_time_hour: int
    server_time_minute: int
    bid: float
    ask: float
    spread: int
    
    # --- 账户硬风控数据 ---
    account_equity: float   # 净值 (用于算回撤)
    margin_level: float     # 保证金比例
    
    # --- K线数据 (Al Brooks 需要长历史) ---
    # M5 发送 100 根 (用于数浪、数 Setup)
    m5_candles: List[Candle] 
    
    # H1 发送 50 根 (用于判断大环境 Context)
    h1_candles: List[Candle] 
    
    # 动态信息
    news_info: NewsInfo
    current_positions: List[Position]

# --- 核心响应包 (Python -> MT5) ---

class SignalResponse(BaseModel):
    # 动作: PLACE_BUY_STOP, PLACE_SELL_STOP, CLOSE_PARTIAL, CLOSE_POS, HOLD
    action: str         
    
    # 订单参数
    ticket: int = 0      # 用于平仓/减仓
    lot: float = 0.0     # 开仓/平仓手数
    entry_price: float = 0.0  # 挂单价格 (新增: 用于Stop Order)
    sl: float = 0.0
    tp: float = 0.0      # 0.0 代表不设 TP (Al Brooks 常用移动止损离场)
    
    # 决策理由  
    # 例: "Stage:1-Spike | Setup:H1"
    reason: str
