# app/services/l3_context.py

import pandas as pd
import numpy as np
from .. import config

class ContextService:
    # [修改] 接收外部传入的 current_atr
    def identify_stage(self, m5_candles, current_atr):
        if len(m5_candles) < 21:
            return "UNKNOWN", "WAIT"
            
        df = pd.DataFrame([c.dict() for c in m5_candles])
        
        # 计算 EMA20
        df['ema20'] = df['close'].rolling(20).mean()
        
        # ATR 已经从外部传入 (current_atr)，无需内部计算
        
        # --- 因子计算 ---
        
        # 1. 归一化斜率 (Normalized Slope)
        current_ema = df['ema20'].iloc[-1]
        prev_ema_3 = df['ema20'].iloc[-4]
        raw_slope = current_ema - prev_ema_3
        # 使用传入的 ATR 进行归一化
        norm_slope = raw_slope / current_atr 
        
        # 2. 穿越次数 (Crossings)
        crossings = 0
        for i in range(len(df)-20, len(df)):
            if i < 0: continue
            row = df.iloc[i]
            if pd.notna(row['ema20']) and (row['high'] > row['ema20'] > row['low']):
                crossings += 1
        
        # 3. 压缩度 (Compression)
        recent_high = df['high'].tail(10).max()
        recent_low = df['low'].tail(10).min()
        height = recent_high - recent_low
        # 使用传入 ATR 作为基准
        is_compressed = height < (current_atr * config.COMPRESSION_ATR) 
        
        # 4. 强趋势因子 (Momentum)
        last_3 = df.tail(3)
        bodies = abs(last_3['close'] - last_3['open'])
        # 动态判断大实体 (> 0.8 ATR)
        big_bars_count = (bodies > (current_atr * 0.8)).sum()
        
        # 超级大单边 (> 2.0 ATR)
        is_climax = bodies.iloc[-1] > (current_atr * 2.0)
        
        strong_momentum = (big_bars_count >= 2) or is_climax

        # --- 核心判断逻辑 (优先级漏斗) ---
        
        # 1. [最高优先级] Strong Trend (Spike)
        if abs(norm_slope) > config.SLOPE_SPIKE_ATR and strong_momentum:
            stage = "1-STRONG_TREND"
            trend_dir = "BULL" if norm_slope > 0 else "BEAR"
            return stage, trend_dir

        # 2. [第二优先级] Breakout Mode (TTR)
        if is_compressed:
            stage = "4-BREAKOUT_MODE"
            # 微观方向判断
            trend_dir = "BULL" if df['close'].iloc[-1] > df['ema20'].iloc[-1] else "BEAR"
            return stage, trend_dir
            
        # 3. [第三优先级] Trading Range (区间)
        if abs(norm_slope) < config.SLOPE_FLAT_ATR or crossings >= config.AB_RANGE_CROSSINGS:
            stage = "3-TRADING_RANGE"
            return stage, "NEUTRAL"
            
        # 4. [默认] Channel (通道/弱趋势)
        stage = "2-CHANNEL"
        trend_dir = "BULL" if norm_slope > 0 else "BEAR"
        
        return stage, trend_dir
