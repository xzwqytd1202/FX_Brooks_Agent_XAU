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
    # 1. 计算 ATR (必须放在最前面，因为风控需要它)
    current_atr = calculate_atr(data.m5_candles)
    
    # 0. 全局风控 (传入 ATR)
    is_safe, safety_reason = risk_svc.check_safety(data, current_atr)
    if not is_safe:
        return SignalResponse(action="HOLD", reason=f"RISK:{safety_reason}")

    if not data.m5_candles or current_atr is None: 
        return SignalResponse(action="HOLD", reason="NO_DATA")

    # 2. 仓位管理 & 动态减仓
    current_pos_count = len(data.current_positions)
    
    if data.current_positions:
        pos = data.current_positions[0]
        dist_moved = abs(pos.current_price - pos.open_price)
        atr_threshold = current_atr * 1.0
        
        if pos.volume >= 0.02 and dist_moved > atr_threshold and "PARTIAL" not in pos.comment:
             return SignalResponse(
                 action="CLOSE_PARTIAL", 
                 ticket=pos.ticket, 
                 lot=config.PARTIAL_CLOSE_LOT, 
                 reason=f"TP_Partial_1ATR({dist_moved:.1f})"
             )

    # 最大持仓限制
    if current_pos_count >= config.MAX_POSITIONS_COUNT:
         return SignalResponse(action="HOLD", reason="Max_Pos_Reached")
    
    # 3. 分析流程
    m5_bars = data.m5_candles
    
    # [修改] L3 传入 h1_candles 以判断 Always In
    stage, trend_dir = l3_svc.identify_stage(m5_bars, data.h1_candles, current_atr)
    
    structure = l2_svc.update_counter(m5_bars, trend_dir, current_atr)
    
    # Setup 过滤
    if "IGNORE" in structure.get('setup', '') or "TOO_FAR" in structure.get('setup', ''):
        return SignalResponse(action="HOLD", reason=f"Weak_Setup_{structure['setup']}")
    
    action, lot, entry, sl, tp, reason = l5_svc.generate_order(
        stage, trend_dir, structure.get('setup', 'NONE'), m5_bars, current_atr
    )
    
    return SignalResponse(action=action, lot=lot, entry_price=entry, sl=sl, tp=tp, reason=reason)
