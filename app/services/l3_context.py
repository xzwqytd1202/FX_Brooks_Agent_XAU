# app/services/l3_context.py

import pandas as pd
import numpy as np
from .. import config

class ContextService:
    def identify_stage(self, m5_candles):
        """
        识别 Al Brooks 四大阶段 (基于纯技术指标，移除时间判断)
        1. Strong Trend (Spike) - 强趋势
        2. Weak Trend (Channel) - 通道
        3. Trading Range - 交易区间
        4. Breakout Mode - 突破模式
        
        返回: (stage, trend_dir)
        例如: ("1-STRONG_TREND", "BULL") 或 ("3-TRADING_RANGE", "NEUTRAL")
        """
        if len(m5_candles) < 21:
            return "UNKNOWN", "WAIT"
            
        df = pd.DataFrame([c.dict() for c in m5_candles])
        
        # 计算 EMA20
        df['ema20'] = df['close'].rolling(20).mean()
        
        # --- 因子计算 ---
        
        # 1. 斜率 (Slope): 取最近 3 根 EMA 的变化率
        current_ema = df['ema20'].iloc[-1]
        prev_ema_3 = df['ema20'].iloc[-4] # 3根前
        slope = (current_ema - prev_ema_3)
        
        # 2. 穿越次数 (Crossings): 过去 20 根 K 线穿过均线的次数
        # 震荡区间通常反复穿梭
        crossings = 0
        for i in range(len(df)-20, len(df)):
            if i < 0: continue
            row = df.iloc[i]
            if pd.notna(row['ema20']) and (row['high'] > row['ema20'] > row['low']):
                crossings += 1
                
        # 3. 压缩度 (Compression): 用于识别 Breakout Mode
        # 使用简单的近期高低点差
        recent_high = df['high'].tail(10).max()
        recent_low = df['low'].tail(10).min()
        height = recent_high - recent_low
        is_compressed = height < (config.AB_AVG_BODY_SIZE * 5) # 10根K线波幅很小
        
        # 4. 强趋势因子: 连续 Trend Bar
        last_3_bars = df.tail(3)
        strong_momentum = all(abs(last_3_bars['close'] - last_3_bars['open']) > config.AB_AVG_BODY_SIZE)

        # --- 阶段判定逻辑 (优先级: 1 -> 4 -> 3 -> 2) ---
        
        stage = "3-TRADING_RANGE" # 默认
        trend_dir = "NEUTRAL"
        
        # 判定 1: Strong Trend (Spike)
        # 斜率极大，且有连续强K线
        if abs(slope) > 1.0 and strong_momentum:
            stage = "1-STRONG_TREND"
            trend_dir = "BULL" if slope > 0 else "BEAR"
            return stage, trend_dir
            
        # 判定 4: Breakout Mode
        # 极度压缩，均线走平
        if is_compressed and abs(slope) < 0.2:
            stage = "4-BREAKOUT_MODE"
            return stage, "NEUTRAL"
            
        # 判定 3: Trading Range
        # 均线走平 (斜率低)，或者 价格反复穿梭均线
        if abs(slope) < config.AB_RANGE_EMA_SLOPE or crossings >= config.AB_RANGE_CROSSINGS:
            stage = "3-TRADING_RANGE"
            return stage, "NEUTRAL"
            
        # 判定 2: Weak Trend (Channel)
        # 斜率适中，价格在均线一侧运行 (穿越少)
        stage = "2-CHANNEL"
        trend_dir = "BULL" if slope > 0 else "BEAR"
        
        return stage, trend_dir
