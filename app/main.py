# app/main.py

from fastapi import FastAPI
from .schemas import MarketData, SignalResponse
from .services.global_risk import GlobalRiskService
from .services.l1_perception import PerceptionService
from .services.l2_structure import StructureService
from .services.l3_context import ContextService
from .services.l4_probability import ProbabilityService
from .services.l5_execution import ExecutionService
from . import config
import logging
import pandas as pd
import numpy as np

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AB_Agent")

app = FastAPI(
    title="Al Brooks Gold Agent",
    version="2.0.0",
    description="XAUUSD 智能交易 - Al Brooks Price Action 体系 (4-Stage, ATR-Adaptive)"
)

# 实例化所有服务
risk_svc = GlobalRiskService()
l1_svc = PerceptionService()
l2_svc = StructureService()
l3_svc = ContextService()
l4_svc = ProbabilityService()
l5_svc = ExecutionService()

# 辅助函数: 计算当前 ATR (14)
def calculate_atr(candles, period=14):
    if not candles or len(candles) < period + 1:
        return 5.0 # 默认值，防报错
    
    df = pd.DataFrame([c.dict() for c in candles])
    # 标准 TR 计算
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    
    current_atr = df['tr'].rolling(period).mean().iloc[-1]
    # 处理可能的 NaN
    if pd.isna(current_atr): return 5.0
    return current_atr

@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy", "version": "2.0.0"}

@app.post("/signal", response_model=SignalResponse)
def analyze_market(data: MarketData):
    # 0. 全局风控 (L0)
    is_safe, safety_reason = risk_svc.check_safety(data)
    if not is_safe:
        if "CIRCUIT_BREAKER" in safety_reason and config.FORCE_CLOSE_ON_DRAWDOWN and data.current_positions:
             return SignalResponse(action="CLOSE_POS", ticket=data.current_positions[0].ticket, reason=safety_reason)
        return SignalResponse(action="HOLD", reason=f"RISK:{safety_reason}")

    # 1. 仓位管理
    current_vol = sum([p.volume for p in data.current_positions])
    
    # 减仓逻辑
    if data.current_positions:
        pos = data.current_positions[0]
        profit_usd = pos.profit
        if pos.volume >= 0.02 and profit_usd > 5.0 and "PARTIAL" not in pos.comment:
             return SignalResponse(
                 action="CLOSE_PARTIAL", 
                 ticket=pos.ticket, 
                 lot=config.PARTIAL_CLOSE_LOT, 
                 reason="Take_Partial_Profit"
             )
    
    if current_vol >= config.MAX_TOTAL_VOLUME:
        return SignalResponse(action="HOLD", reason="Max_Volume_Reached")

    # 2. 数据准备
    if not data.m5_candles or len(data.m5_candles) < 2:
        return SignalResponse(action="HOLD", reason="NO_DATA")
    
    m5_bars = data.m5_candles
    
    # [新增] 全局计算 ATR
    current_atr = calculate_atr(m5_bars)
    
    # 3. 分析流程 (全 ATR 化)
    
    # L1: 感知 (传入 atr)
    bar_feat = l1_svc.analyze_bar(m5_bars[-1], m5_bars[-2], current_atr)
    
    # L3: 环境 (传入 atr)
    stage, trend_dir = l3_svc.identify_stage(m5_bars, current_atr)
    
    # L2: 结构 (传入 L3 trend 和 atr)
    structure = l2_svc.update_counter(m5_bars, trend_dir, current_atr)
    
    # L5: 执行 (传入 atr)
    action, lot, entry_price, sl, tp, exec_reason = l5_svc.generate_order(
        stage, trend_dir, structure.get('setup', 'NONE'), m5_bars, current_atr
    )
    
    # 组合最终理由
    final_reason = f"{stage}|{structure.get('setup', 'NONE')}|{exec_reason}"
    
    logger.info(f"Decision: {action} | ATR:{current_atr:.2f} | {final_reason}")
    
    return SignalResponse(
        action=action,
        lot=lot,
        entry_price=entry_price,
        sl=sl,
        tp=tp,
        reason=final_reason
    )
