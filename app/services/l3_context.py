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

        # 定义阈值 (可以放入 config)
        SLOPE_SPIKE = 0.8       # 强趋势斜率阈值
        SLOPE_FLAT = 0.15       # 震荡斜率阈值
        CROSSING_LIMIT = 5      # 穿越均线次数阈值
        
        # --- 核心判断逻辑 (优先级漏斗) ---
        
        # 1. [最高优先级] Strong Trend (Spike)
        # 必须具备: 极陡的斜率 AND 强劲的动能
        if abs(slope) > SLOPE_SPIKE and strong_momentum:
            stage = "1-STRONG_TREND"
            trend_dir = "BULL" if slope > 0 else "BEAR"
            return stage, trend_dir

        # 2. [第二优先级] Breakout Mode (TTR)
        # 必须具备: 极度压缩 (均线斜率通常也很小)
        if is_compressed:
            stage = "4-BREAKOUT_MODE"
            # 此时方向不明，但需给出一个微观倾向用于挂单
            trend_dir = "BULL" if df['close'].iloc[-1] > df['ema20'].iloc[-1] else "BEAR"
            return stage, trend_dir
            
        # 3. [第三优先级] Trading Range (区间)
        # 具备: 均线走平 OR 反复穿梭 (混乱)
        if abs(slope) < SLOPE_FLAT or crossings >= CROSSING_LIMIT:
            stage = "3-TRADING_RANGE"
            return stage, "NEUTRAL"
            
        # 4. [默认] Channel (通道/弱趋势)
        # 既然不是强趋势，也不是震荡，那就是有方向的弱趋势
        stage = "2-CHANNEL"
        trend_dir = "BULL" if slope > 0 else "BEAR"
        
        return stage, trend_dir
