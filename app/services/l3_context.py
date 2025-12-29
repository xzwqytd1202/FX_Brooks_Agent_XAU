# app/services/l3_context.py
import pandas as pd
import numpy as np
from .. import config

class ContextService:
    def identify_stage(self, m5_candles, h1_candles, current_atr):
        """
        引入 H1 数据来模拟 Al Brooks 的 "Always In" 大局观
        """
        if len(m5_candles) < 21: return "UNKNOWN", "WAIT"
            
        df = pd.DataFrame([c.dict() for c in m5_candles])
        df['ema20'] = df['close'].rolling(20).mean()
        
        # --- 1. M5 基础因子计算 ---
        current_ema = df['ema20'].iloc[-1]
        prev_ema_3 = df['ema20'].iloc[-4]
        raw_slope = current_ema - prev_ema_3
        norm_slope = raw_slope / current_atr 
        
        # 穿越次数 & 压缩度
        crossings = 0
        for i in range(len(df)-20, len(df)):
            if i < 0: continue
            row = df.iloc[i]
            if pd.notna(row['ema20']) and (row['high'] > row['ema20'] > row['low']):
                crossings += 1
                
        recent_high = df['high'].tail(10).max()
        recent_low = df['low'].tail(10).min()
        is_compressed = (recent_high - recent_low) < (current_atr * config.COMPRESSION_ATR)
        
        # [新增] Barbwire (铁丝网) 检测
        # 特征: 过去 5 根 K 线里，至少 3 根是十字星 (实体 < 0.3 ATR) 且 重叠严重
        recent_5 = df.tail(5)
        doji_count = 0
        for _, row in recent_5.iterrows():
            body = abs(row['close'] - row['open'])
            if body < (current_atr * 0.3):
                doji_count += 1
        
        is_barbwire = False
        if doji_count >= 3 and is_compressed:
            is_barbwire = True
        
        # 强趋势因子
        last_3 = df.tail(3)
        bodies = abs(last_3['close'] - last_3['open'])
        strong_momentum = ((bodies > (current_atr * 0.8)).sum() >= 2) or (bodies.iloc[-1] > current_atr * 2.0)

        # --- 2. H1 "Always In" 方向判断 (新增) ---
        # 如果 M5 看不清，就看 H1。H1 EMA 向上 = Always In Long
        always_in_dir = "NEUTRAL"
        if h1_candles and len(h1_candles) > 20:
            df_h1 = pd.DataFrame([c.dict() for c in h1_candles])
            df_h1['ema20'] = df_h1['close'].rolling(20).mean()
            h1_slope = df_h1['ema20'].iloc[-1] - df_h1['ema20'].iloc[-2]
            
            # H1 斜率判断
            if h1_slope > 0: always_in_dir = "BULL"
            elif h1_slope < 0: always_in_dir = "BEAR"

        # --- 3. 综合阶段判定 ---
        
        # Stage 1: Spike (M5 自己很强) - 最高优先级
        if abs(norm_slope) > config.SLOPE_SPIKE_ATR and strong_momentum:
            return "1-STRONG_TREND", ("BULL" if norm_slope > 0 else "BEAR")

        # Barbwire 检测 - 放在 Spike 之后，避免错过突破
        if is_barbwire:
            return "0-BARBWIRE", "NEUTRAL"

        # Stage 4: Breakout Mode (M5 压缩)
        if is_compressed:
            # 如果 M5 压缩，尽量顺着 H1 的方向做突破
            return "4-BREAKOUT_MODE", (always_in_dir if always_in_dir != "NEUTRAL" else "BULL")
            
        # Stage 3: Trading Range (M5 震荡)
        # [关键修改] 如果 M5 是震荡，但 H1 趋势很强，这其实是 Stage 2 (通道/旗形)
        is_m5_tr = abs(norm_slope) < config.SLOPE_FLAT_ATR or crossings >= config.AB_RANGE_CROSSINGS
        
        if is_m5_tr:
            if always_in_dir != "NEUTRAL":
                # M5 震荡 + H1 有趋势 = 复杂回调 (Complex Pullback / Channel)
                # 强制降级为 Channel，只做顺势
                return "2-CHANNEL", always_in_dir
            else:
                # M5 震荡 + H1 也震荡 = 纯垃圾时间
                return "3-TRADING_RANGE", "NEUTRAL"
            
        # Stage 2: Channel (默认)
        return "2-CHANNEL", ("BULL" if norm_slope > 0 else "BEAR")
