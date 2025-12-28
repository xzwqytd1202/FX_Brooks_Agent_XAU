# app/services/l5_execution.py
from .. import config
import pandas as pd

class ExecutionService:
    # [修改] 增加 candles 参数，传入最近的历史K线用于计算区间
    def generate_order(self, stage, trend_dir, setup_type, candles, atr):
        """
        根据 4 个阶段生成不同的 Stop Order 策略
        candles: M5 K线列表 (最近的)
        """
        signal_bar = candles[-1] # 最后一根
        
        action = "HOLD"
        entry_price = 0.0
        sl = 0.0
        tp = 0.0
        lot = config.BASE_LOT_SIZE
        reason = f"Stage:{stage}"
        
        # [修改] 动态 Tick Size (挂单缓冲距离)
        # 逻辑: 取 0.05倍 ATR 和 0.2 美金 中的较大值
        tick_buffer = max(config.MIN_TICK_SIZE, atr * 0.05)
        
        # --- 巨型 K 线判断逻辑 ---
        # 如果信号棒幅度超过 3倍 ATR，说明这是一根高潮线 (Climax)
        bar_height = signal_bar.high - signal_bar.low
        is_huge_bar = bar_height > (atr * 3.0)
        
        huge_bar_note = ""
        if is_huge_bar:
            huge_bar_note = "(HugeBar_50%SL)"

        # ------------------------------------------------------
        # 阶段 1: 强趋势 (Spike)
        # ------------------------------------------------------
        if "1-STRONG_TREND" in stage:
            if trend_dir == "BULL":
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick_buffer
                # 止损逻辑
                if is_huge_bar:
                    sl = signal_bar.low + (bar_height * 0.5)
                else:
                    sl = signal_bar.low - tick_buffer
                tp = 0 
                
            elif trend_dir == "BEAR":
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick_buffer
                # 止损逻辑
                if is_huge_bar:
                    sl = signal_bar.high - (bar_height * 0.5)
                else:
                    sl = signal_bar.high + tick_buffer
                tp = 0
                
        # ------------------------------------------------------
        # 阶段 2: 通道 (Channel)
        # ------------------------------------------------------
        elif "2-CHANNEL" in stage:
            if trend_dir == "BULL" and setup_type in ["H1", "H2"]:
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick_buffer
                # 止损逻辑
                if is_huge_bar:
                    sl = signal_bar.low + (bar_height * 0.5)
                else:
                    sl = signal_bar.low - tick_buffer
                tp = entry_price + (entry_price - sl) * 2.0 
                
            elif trend_dir == "BEAR" and setup_type in ["L1", "L2"]:
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick_buffer
                # 止损逻辑
                if is_huge_bar:
                    sl = signal_bar.high - (bar_height * 0.5)
                else:
                    sl = signal_bar.high + tick_buffer
                tp = entry_price - (sl - entry_price) * 2.0

        # ------------------------------------------------------
        # 阶段 3: 交易区间 (Trading Range)
        # ------------------------------------------------------
        elif "3-TRADING_RANGE" in stage:
            LOOKBACK_TR = 20
            recent_bars = candles[-LOOKBACK_TR:]
            
            rg_high = max([c.high for c in recent_bars])
            rg_low = min([c.low for c in recent_bars])
            rg_height = rg_high - rg_low
            
            if rg_height == 0: rg_height = 0.001
            
            current_pos = (signal_bar.close - rg_low) / rg_height
            
            if current_pos <= 0.33:
                is_bull_body = signal_bar.close > signal_bar.open
                lower_tail = min(signal_bar.open, signal_bar.close) - signal_bar.low
                is_long_tail = lower_tail > (signal_bar.high - signal_bar.low) * 0.4
                
                if is_bull_body or is_long_tail:
                    action = "PLACE_BUY_STOP"
                    entry_price = signal_bar.high + tick_buffer
                    sl = signal_bar.low - tick_buffer
                    risk = entry_price - sl
                    tp = entry_price + (risk * 1.5)
                    reason += "|TR_Buy_Low_Scalp"

            elif current_pos >= 0.66:
                is_bear_body = signal_bar.close < signal_bar.open
                upper_tail = signal_bar.high - max(signal_bar.open, signal_bar.close)
                is_long_tail = upper_tail > (signal_bar.high - signal_bar.low) * 0.4
                
                if is_bear_body or is_long_tail:
                    action = "PLACE_SELL_STOP"
                    entry_price = signal_bar.low - tick_buffer
                    sl = signal_bar.high + tick_buffer
                    risk = sl - entry_price
                    tp = entry_price - (risk * 1.5)
                    reason += "|TR_Sell_High_Scalp"
            
            else:
                reason += "|TR_Middle_Wait"

        # ------------------------------------------------------
        # 阶段 4: 突破模式 (Breakout Mode)
        # ------------------------------------------------------
        elif "4-BREAKOUT_MODE" in stage:
            LOOKBACK = 10 
            recent_bars = candles[-LOOKBACK:] 
            
            range_high = max([c.high for c in recent_bars])
            range_low = min([c.low for c in recent_bars])
            
            if trend_dir == "BULL":
                action = "PLACE_BUY_STOP"
                entry_price = range_high + tick_buffer
                sl = range_low - tick_buffer
                risk = entry_price - sl
                tp = entry_price + (risk * 2.0)
                reason += "|TTR_Buy_Breakout"

            elif trend_dir == "BEAR":
                action = "PLACE_SELL_STOP"
                entry_price = range_low - tick_buffer
                sl = range_high + tick_buffer
                risk = sl - entry_price
                tp = entry_price - (risk * 2.0)
                reason += "|TTR_Sell_Breakout"
        
        if is_huge_bar:
            reason += huge_bar_note
            
        return action, lot, entry_price, sl, tp, reason
