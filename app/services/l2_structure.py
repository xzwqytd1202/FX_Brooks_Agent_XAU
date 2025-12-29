# app/services/l2_structure.py
import pandas as pd
from .. import config

class StructureService:
    def update_counter(self, m5_candles, trend_dir, atr):
        if len(m5_candles) < 20:
            return {"setup": "NONE", "reason": "NO_DATA"}
            
        df = pd.DataFrame([c.dict() for c in m5_candles])
        df['ema20'] = df['close'].rolling(20).mean()
        
        if trend_dir == "NEUTRAL":
             trend_dir = "BULL" if df['ema20'].iloc[-1] > df['ema20'].iloc[-2] else "BEAR"
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        setup = "NONE"
        
        # --- [4] H1/H2 增强过滤 (收阳或破前高) ---
        
        # 定义强多头信号: 收阳 OR 收盘价强势突破前高
        is_bullish_signal = (last['close'] > last['open']) or (last['close'] > prev['high'])
        
        # 定义强空头信号: 收阴 OR 收盘价强势跌破前低
        is_bearish_signal = (last['close'] < last['open']) or (last['close'] < prev['low'])

        if trend_dir == "BULL":
            if last['high'] > prev['high']: # 试图恢复趋势
                if is_bullish_signal:
                    setup = "H1"
                    # 深度回调判定 (Low < EMA - 0.2 ATR)
                    if last['low'] < (last['ema20'] - atr * 0.2):
                        setup = "H2" 
                else:
                    setup = "WEAK_H1_IGNORE" # 过滤掉

        elif trend_dir == "BEAR":
            if last['low'] < prev['low']:
                if is_bearish_signal:
                    setup = "L1"
                    if last['high'] > (last['ema20'] + atr * 0.2):
                        setup = "L2"
                else:
                    setup = "WEAK_L1_IGNORE" # 过滤掉

        return {
            "major_trend": trend_dir,
            "setup": setup
        }
