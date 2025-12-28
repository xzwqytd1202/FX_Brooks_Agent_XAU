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
    description="XAUUSD 智能交易 - Al Brooks Price Action 体系 (4-Stage)"
)

# 实例化所有服务
risk_svc = GlobalRiskService()
l1_svc = PerceptionService()
l2_svc = StructureService()
l3_svc = ContextService()
l4_svc = ProbabilityService()
l5_svc = ExecutionService()

# 辅助: 计算 ATR
def quick_atr(candles):
    if not candles: return 1.0
    df = pd.DataFrame([c.dict() for c in candles])
    df['tr'] = np.maximum(df['high'] - df['low'], 
               np.maximum(abs(df['high'] - df['close'].shift(1)), 
                          abs(df['low'] - df['close'].shift(1))))
    return df['tr'].rolling(14).mean().iloc[-1]

@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy", "version": "2.0.0"}

@app.post("/signal", response_model=SignalResponse)
def analyze_market(data: MarketData):
    # 0. 全局风控 (L0)
    is_safe, safety_reason = risk_svc.check_safety(data)
    if not is_safe:
        # 如果触发熔断，且配置了强平
        if "CIRCUIT_BREAKER" in safety_reason and config.FORCE_CLOSE_ON_DRAWDOWN and data.current_positions:
             return SignalResponse(action="CLOSE_POS", ticket=data.current_positions[0].ticket, reason=safety_reason)
        
        return SignalResponse(action="HOLD", reason=f"RISK:{safety_reason}")

    # 1. 仓位管理 (0.02 / 0.04)
    current_vol = sum([p.volume for p in data.current_positions])
    
    # [减仓逻辑] 如果有持仓，且浮盈很大，可以减仓
    # 简单示范: 如果持仓 >= 0.02 且盈利 > 5美金，减半仓
    if data.current_positions:
        pos = data.current_positions[0]
        profit_usd = pos.profit  # 浮动盈亏 (美金)
        if pos.volume >= 0.02 and profit_usd > 5.0 and "PARTIAL" not in pos.comment:
             return SignalResponse(
                 action="CLOSE_PARTIAL", 
                 ticket=pos.ticket, 
                 lot=config.PARTIAL_CLOSE_LOT, # 平 0.01
                 reason="Take_Partial_Profit"
             )
    
    # 如果持仓已达上限 0.04，禁止开新单
    if current_vol >= config.MAX_TOTAL_VOLUME:
        return SignalResponse(action="HOLD", reason="Max_Volume_Reached")

    # 2. 数据准备
    if not data.m5_candles or len(data.m5_candles) < 2:
        return SignalResponse(action="HOLD", reason="NO_DATA")
    
    m5_bars = data.m5_candles
    
    # 3. 分析流程 (L1 -> L3 -> L2 -> L5)
    
    # L1: 特征 (传入前一根K线用于计算重叠度)
    bar_feat = l1_svc.analyze_bar(m5_bars[-1], m5_bars[-2])
    
    # L3: 识别 4大阶段 (Spike, Channel, TR, Breakout)
    stage, trend_dir = l3_svc.identify_stage(m5_bars)
    
    # L2: 识别 Setup (H1/H2)
    # L2 需要依赖 L3 的 trend_dir 来决定数浪方向
    structure = l2_svc.update_counter(m5_bars)
    
    # L5: 生成挂单
    current_atr = quick_atr(m5_bars)
    action, lot, entry_price, sl, tp, exec_reason = l5_svc.generate_order(
        stage, trend_dir, structure.get('setup', 'NONE'), m5_bars[-1], current_atr
    )
    
    # 组合最终理由
    final_reason = f"{stage}|{structure.get('setup', 'NONE')}|{exec_reason}"
    
    logger.info(f"Decision: {action} | {final_reason}")
    
    return SignalResponse(
        action=action,
        lot=lot,
        entry_price=entry_price,
        sl=sl,
        tp=tp,
        reason=final_reason
    )
