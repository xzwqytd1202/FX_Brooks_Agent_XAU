# app/services/l1_perception.py

import pandas as pd
import numpy as np
from .. import config

class PerceptionService:
    def analyze_bar(self, candle, prev_candle=None):
        """
        分析单根 K 线的原子特征
        """
        open_p = candle.open
        close_p = candle.close
        high_p = candle.high
        low_p = candle.low
        
        body_size = abs(close_p - open_p)
        total_range = high_p - low_p
        if total_range == 0: total_range = 0.0001 # 防除零
        
        # 1. Control (控制权)
        # 收盘价在 K 线幅度的位置 (0.0 = Low, 1.0 = High)
        close_position = (close_p - low_p) / total_range
        
        control = "NEUTRAL"
        if close_position >= (1.0 - config.AB_CLOSE_ZONE):
            control = "BULL_CONTROL" # 收在最高处
        elif close_position <= config.AB_CLOSE_ZONE:
            control = "BEAR_CONTROL" # 收在最低处
            
        # 2. Momentum (动能)
        # 实体大小相对于平均值
        is_trend_bar = False
        if body_size > config.AB_AVG_BODY_SIZE * config.AB_STRONG_BAR_RATIO:
            is_trend_bar = True
            
        # 3. Rejection (拒绝/影线)
        # 上影线
        upper_tail = high_p - max(open_p, close_p)
        upper_tail_ratio = upper_tail / total_range
        
        # 下影线
        lower_tail = min(open_p, close_p) - low_p
        lower_tail_ratio = lower_tail / total_range
        
        has_rejection = False
        rejection_type = "NONE"
        
        if upper_tail_ratio > config.AB_TAIL_RATIO:
            has_rejection = True
            rejection_type = "TOP_TAIL" # 上方抛压
        elif lower_tail_ratio > config.AB_TAIL_RATIO:
            has_rejection = True
            rejection_type = "BOTTOM_TAIL" # 下方买盘
        
        # 4. Overlap (重叠度) - 用于判断震荡
        # 计算当前K线 High/Low 与 前一根 High/Low 的重叠部分
        overlap_pct = 0.0
        if prev_candle:
            overlap_max = min(candle.high, prev_candle.high)
            overlap_min = max(candle.low, prev_candle.low)
            if overlap_max > overlap_min:
                overlap_len = overlap_max - overlap_min
                prev_rng = prev_candle.high - prev_candle.low
                if prev_rng > 0:
                    overlap_pct = overlap_len / prev_rng
            
        return {
            "control": control,
            "is_trend_bar": is_trend_bar,
            "has_rejection": has_rejection,
            "rejection_type": rejection_type,
            "close_position": close_position,
            "overlap": overlap_pct  # 新增重叠度
        }

    def analyze_recent_sequence(self, candles_list):
        """
        分析最近的一组 K 线 (用于判断强趋势)
        """
        features = [self.analyze_bar(c) for c in candles_list]
        return features
