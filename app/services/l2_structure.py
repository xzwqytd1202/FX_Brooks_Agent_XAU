# app/services/l2_structure.py

import pandas as pd
from .. import config

class StructureService:
    def update_counter(self, m5_candles):
        """
        核心计数器 (Leg Counter)
        返回: {
            "major_trend": "BULL" or "BEAR",
            "setup": "H1", "H2", "L1", "L2" or "NONE",
            "reason": str
        }
        """
        if len(m5_candles) < 20:
            return {"major_trend": "NEUTRAL", "setup": "NONE", "reason": "NO_DATA"}
            
        # 转换 DataFrame 以便处理
        df = pd.DataFrame([c.dict() for c in m5_candles])
        
        # 1. 识别短期趋势 (EMA 20)
        ema20 = df['close'].rolling(20).mean()
        curr_ema = ema20.iloc[-1]
        prev_ema = ema20.iloc[-2]
        
        trend_direction = "BULL" if curr_ema > prev_ema else "BEAR"
        
        # 2. 识别回调 (Pullback) 与 计数 (Counting)
        # 逻辑简化版: 
        # 在多头趋势中，每一根 High 低于前一根 High 的 K 线，都是回调的一部分
        # 当 High 突破前一根 High 时，触发计数 (H1, H2)
        
        last_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]
        
        setup = "NONE"
        
        # --- 多头计数 (Looking for Buys) ---
        if trend_direction == "BULL":
            # 如果当前收盘强力突破前一根高点
            if last_candle['high'] > prev_candle['high']:
                # 简单回溯: 看看过去 5-10 根有没有类似的突破动作但失败了
                # 这里为了稳健，默认为 H1 (第一次尝试恢复趋势)
                setup = "H1"
                
                # 如果之前的一波回调非常深，升级为 H2
                # 简化判断: 看最近10根的最低点是否明显低于EMA
                recent_low = df['low'].tail(10).min()
                ema_low = ema20.tail(10).min()
                if recent_low < ema_low * 0.998:  # 深度回调
                    setup = "H2"
                
        # --- 空头计数 (Looking for Sells) ---
        elif trend_direction == "BEAR":
            if last_candle['low'] < prev_candle['low']:
                setup = "L1"
                
                # 深度反弹后再次下跌
                recent_high = df['high'].tail(10).max()
                ema_high = ema20.tail(10).max()
                if recent_high > ema_high * 1.002:
                    setup = "L2"
        
        return {
            "major_trend": trend_direction,
            "setup": setup,
            "reason": f"{trend_direction}_{setup}"
        }
