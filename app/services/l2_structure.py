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
        
        # 强信号定义
        is_bullish_signal = (last['close'] > last['open']) or (last['close'] > prev['high'])
        is_bearish_signal = (last['close'] < last['open']) or (last['close'] < prev['low'])

        # --- [修改] 磁力距离计算 ---
        # 价格离 EMA 多远?
        dist_to_ema = last['close'] - last['ema20']
        
        if trend_dir == "BULL":
            if last['high'] > prev['high']:
                if is_bullish_signal:
                    setup = "H1"
                    
                    # [新增] 磁力过滤 (Magnet Filter)
                    # 如果 H1 发生时，价格还在 EMA 上方很远 (> 1.0 ATR)，
                    # 说明回调不够深，市场还会去寻找 EMA，这个 H1 容易失败。
                    if dist_to_ema > (atr * config.AB_MAGNET_DISTANCE_ATR):
                        setup = "WEAK_H1_TOO_FAR"
                        
                    # H2 判定 (深度回调)
                    if last['low'] < (last['ema20'] - atr * 0.2):
                        setup = "H2" # H2 不需要过滤距离，因为已经跌穿均线了
                else:
                    setup = "WEAK_H1_IGNORE"

        elif trend_dir == "BEAR":
            if last['low'] < prev['low']:
                if is_bearish_signal:
                    setup = "L1"
                    
                    # [新增] 磁力过滤 (空头同理)
                    # 价格在 EMA 下方很远 -> 太便宜了，不要急着空
                    if dist_to_ema < -(atr * config.AB_MAGNET_DISTANCE_ATR):
                        setup = "WEAK_L1_TOO_FAR"
                        
                    if last['high'] > (last['ema20'] + atr * 0.2):
                        setup = "L2"
                else:
                    setup = "WEAK_L1_IGNORE"

        return {"major_trend": trend_dir, "setup": setup}
