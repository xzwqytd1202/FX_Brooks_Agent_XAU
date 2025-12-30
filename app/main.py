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

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()
risk_svc = GlobalRiskService()
l1_svc = PerceptionService()
l2_svc = StructureService()
l3_svc = ContextService()
l5_svc = ExecutionService()

def prepare_market_data(candles, period=14):
    """
    统一的数据准备函数:
    1. 转 DataFrame
    2. 计算 ATR
    3. 计算 EMA20 (所有服务公用)
    """
    if not candles or len(candles) < config.MIN_HISTORY_FOR_ATR:
        return None, None
    
    df = pd.DataFrame([c.dict() for c in candles])
    
    # 1. 计算 ATR
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    current_atr = df['tr'].rolling(period).mean().iloc[-1]
    
    # 2. 计算 EMA20
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    
    if pd.isna(current_atr): current_atr = 5.0
    
    return df, current_atr

@app.post("/signal", response_model=SignalResponse)
def analyze_market(data: MarketData):
    # 1. 统一数据准备
    df_m5, current_atr = prepare_market_data(data.m5_candles)
    
    if df_m5 is None or current_atr is None:
        return SignalResponse(action="HOLD", reason="NO_DATA_OR_ATR_FAIL")

    # 0. 全局风控 (传入 ATR)
    # [修正] 确保 current_atr 有效后再调用
    is_safe, safety_reason = risk_svc.check_safety(data, current_atr)
    if not is_safe:
        return SignalResponse(action="HOLD", reason=f"RISK:{safety_reason}")

    # 2. 仓位管理 & 动态减仓 (修正版：遍历所有持仓)
    current_pos_count = len(data.current_positions)
    
    if data.current_positions:
        # [修正] 设定 ATR 阈值
        atr_threshold = current_atr * 1.0
        
        # [修正] 遍历所有持仓，而不仅仅是第 0 个
        for pos in data.current_positions:
            dist_moved = abs(pos.current_price - pos.open_price)
            
            # 检查条件:
            # 1. 手数够减 (>0.01)
            # 2. 利润够厚 (>1 ATR)
            # 3. 没减过仓 (Comment无PARTIAL)
            if pos.volume >= 0.02 and dist_moved > atr_threshold and "PARTIAL" not in pos.comment:
                 # 发现一个满足条件的，立即返回指令
                 # 因为一次只能发一个指令，处理完这个，下一次请求会处理下一个
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
    
    # L1: K 线特征分析 (用于增强日志)
    last_bar = m5_bars[-1]
    prev_bar = m5_bars[-2] if len(m5_bars) > 1 else None
    bar_analysis = l1_svc.analyze_bar(last_bar, prev_bar, current_atr)
    
    # [修改] L3 传入 df_m5 和 h1_candles 以判断 Always In
    # ContextService.identify_stage(self, df_m5, h1_candles, current_atr)
    stage, trend_dir = l3_svc.identify_stage(df_m5, data.h1_candles, current_atr)
    
    # [修改] L2 传入 df_m5
    # StructureService.update_counter(self, df, trend_dir, atr)
    structure = l2_svc.update_counter(df_m5, trend_dir, current_atr)
    
    # Setup 过滤
    if "IGNORE" in structure.get('setup', '') or "TOO_FAR" in structure.get('setup', '') or "RESET" in structure.get('setup', ''):
        logger.info(f"[FILTER] Setup={structure['setup']}, Stage={stage}, Trend={trend_dir}")
        return SignalResponse(action="HOLD", reason=f"Weak_Setup_{structure['setup']}")
    
    # [修改] L5 传入 df_m5
    # ExecutionService.generate_order(self, stage, trend_dir, setup_type, df, candles, atr)
    action, lot, entry, sl, tp, reason = l5_svc.generate_order(
        stage, trend_dir, structure.get('setup', 'NONE'), df_m5, m5_bars, current_atr
    )
    
    # 日志记录决策
    if action != "HOLD":
        logger.info(f"[SIGNAL] Action={action}, Stage={stage}, Setup={structure['setup']}, "
                    f"Entry={entry:.2f}, SL={sl:.2f}, TP={tp:.2f}, Lot={lot}, "
                    f"Bar=[Ctrl:{bar_analysis['control']}, Trend:{bar_analysis['is_trend_bar']}, Rej:{bar_analysis['rejection_type']}]")
    
    return SignalResponse(action=action, lot=lot, entry_price=entry, sl=sl, tp=tp, reason=reason)
