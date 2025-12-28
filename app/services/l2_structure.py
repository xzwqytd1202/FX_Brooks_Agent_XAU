# app/services/l2_structure.py

import pandas as pd
from .. import config

class StructureService:
    def update_counter(self, m5_candles, trend_dir, atr):
        """
        核心计数器 (Leg Counter)
        参数:
            m5_candles: K线列表
            trend_dir: L3 识别出的趋势方向 (BULL, BEAR, NEUTRAL)
            atr: 当前 ATR
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
        
        # 计算 EMA20
        df['ema20'] = df['close'].rolling(20).mean()
        ema20 = df['ema20']
        
        # 使用传入的 L3 趋势方向，不再内部计算 simpler EMA slope
        trend_direction = trend_dir
        
        # 如果 L3 说是 NEUTRAL，我们还是得自己判断一下微观方向，以免后续逻辑失效
        if trend_direction == "NEUTRAL":
             curr_ema = ema20.iloc[-1]
             prev_ema = ema20.iloc[-2]
             trend_direction = "BULL" if curr_ema > prev_ema else "BEAR"
        
        # 2. 识别回调 (Pullback) 与 计数 (Counting)
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
                # 判据: 最近10根的最低点是否明显低于EMA
                recent_low = df['low'].tail(10).min()
                ema_low = ema20.tail(10).min()
                # 深度回调: 低于 EMA 一定距离 (例如 0.2 ATR)
                if recent_low < ema_low - (atr * 0.2):  
                    setup = "H2"
                
        # --- 空头计数 (Looking for Sells) ---
        elif trend_direction == "BEAR":
            if last_candle['low'] < prev_candle['low']:
                setup = "L1"
                
                # 深度反弹后再次下跌
                recent_high = df['high'].tail(10).max()
                ema_high = ema20.tail(10).max()
                # 深度反弹
                if recent_high > ema_high + (atr * 0.2):
                    setup = "L2"
        
        return {
            "major_trend": trend_direction,
            "setup": setup,
            "reason": f"{trend_direction}_{setup}"
        }
