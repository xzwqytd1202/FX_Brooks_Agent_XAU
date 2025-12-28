# app/services/l1_perception.py
from .. import config

class PerceptionService:
    # [修改] 增加 atr 参数
    def analyze_bar(self, candle, prev_candle, atr):
        """
        基于 ATR 判断 K 线强弱，不再用固定美金
        """
        body = abs(candle.close - candle.open)
        rng = candle.high - candle.low
        if rng == 0: rng = 0.001
        
        # 1. 动能 (Momentum) - 自适应
        # 如果当前 ATR 是 6.0，那么实体 > 3.6 (0.6倍) 才算趋势K线
        # 如果用以前的 2.0 标准，现在全是趋势K线，那就乱套了
        is_trend_bar = body > (atr * config.AB_TREND_BAR_ATR_RATIO)
        
        # 2. 控制权 (Control)
        close_pos = (candle.close - candle.low) / rng
        control = "NEUTRAL"
        if close_pos > 0.8: control = "BULL"
        elif close_pos < 0.2: control = "BEAR"

        # 3. 拒绝 (Rejection)
        upper_wick = candle.high - max(candle.open, candle.close)
        lower_wick = min(candle.open, candle.close) - candle.low
        
        has_rejection = False
        rejection_type = "NONE"
        
        if upper_wick > body and upper_wick > (rng * 0.4):
            has_rejection = True
            rejection_type = "TOP_TAIL"
        elif lower_wick > body and lower_wick > (rng * 0.4):
            has_rejection = True
            rejection_type = "BOTTOM_TAIL"
            
        # 4. Overlap (重叠度) - 用于判断震荡
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
            "overlap": overlap_pct
        }
