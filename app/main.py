# app/main.py
from fastapi import FastAPI
from .schemas import MarketData, SignalResponse
from .services.global_risk import GlobalRiskService
from .services.l1_perception import PerceptionService
from .services.l2_structure import StructureService
from .services.l3_context import ContextService
from .services.l5_execution import ExecutionService
from . import config
import logging
import pandas as pd
import numpy as np

app = FastAPI()
risk_svc = GlobalRiskService()
l1_svc = PerceptionService()
l2_svc = StructureService()
l3_svc = ContextService()
l5_svc = ExecutionService()

def calculate_atr(candles, period=14):
    # [7] ATR 数据长度保护
    if not candles or len(candles) < config.MIN_HISTORY_FOR_ATR:
        return None 
    
    df = pd.DataFrame([c.dict() for c in candles])
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    current_atr = df['tr'].rolling(period).mean().iloc[-1]
    return current_atr if pd.notna(current_atr) else 5.0

@app.post("/signal", response_model=SignalResponse)
def analyze_market(data: MarketData):
    # 0. 全局风控
    is_safe, safety_reason = risk_svc.check_safety(data)
    if not is_safe:
        return SignalResponse(action="HOLD", reason=f"RISK:{safety_reason}")

    # 1. 数据准备 & ATR计算
    if not data.m5_candles: 
        return SignalResponse(action="HOLD", reason="NO_DATA")
    
    current_atr = calculate_atr(data.m5_candles)
    if current_atr is None: # [7] 数据不足
        return SignalResponse(action="HOLD", reason="WAIT_FOR_DATA")

    # 2. 仓位管理 & [9] 动态减仓
    current_pos_count = len(data.current_positions)
    
    if data.current_positions:
        pos = data.current_positions[0]
        # 计算价格位移
        dist_moved = abs(pos.current_price - pos.open_price)
        
        # [9] 减仓条件: 跑赢 1 倍 ATR
        # XAUUSD 4500, ATR~10 => 跑10美金才减仓
        atr_threshold = current_atr * 1.0
        
        if pos.volume >= 0.02 and dist_moved > atr_threshold and "PARTIAL" not in pos.comment:
             return SignalResponse(
                 action="CLOSE_PARTIAL", 
                 ticket=pos.ticket, 
                 lot=config.PARTIAL_CLOSE_LOT, 
                 reason=f"TP_Partial_1ATR({dist_moved:.1f})"
             )

    # [3] 最大持仓限制
    if current_pos_count >= config.MAX_POSITIONS_COUNT:
         return SignalResponse(action="HOLD", reason="Max_Pos_Reached")
    
    # 3. 分析流程
    m5_bars = data.m5_candles
    
    stage, trend_dir = l3_svc.identify_stage(m5_bars, current_atr)
    structure = l2_svc.update_counter(m5_bars, trend_dir, current_atr)
    
    # Setup 过滤
    if "IGNORE" in structure.get('setup', ''):
        return SignalResponse(action="HOLD", reason=f"Weak_Setup_{structure['setup']}")
    
    action, lot, entry, sl, tp, reason = l5_svc.generate_order(
        stage, trend_dir, structure.get('setup', 'NONE'), m5_bars, current_atr
    )
    
    return SignalResponse(action=action, lot=lot, entry_price=entry, sl=sl, tp=tp, reason=reason)
