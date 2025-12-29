# app/services/l5_execution.py
from .. import config
import math

class ExecutionService:
    def generate_order(self, stage, trend_dir, setup_type, candles, atr):
        signal_bar = candles[-1]
        
        action = "HOLD"
        entry_price = 0.0
        sl = 0.0
        tp = 0.0
        lot = 0.0 
        reason = f"Stage:{stage}"
        
        tick_buffer = max(config.MIN_TICK_SIZE, atr * 0.05)
        bar_height = signal_bar.high - signal_bar.low
        is_huge_bar = bar_height > (atr * 3.0)

        # --- Stage 1: Spike ---
        if "1-STRONG_TREND" in stage:
            if trend_dir == "BULL":
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick_buffer
                sl = signal_bar.low + (bar_height * 0.5) if is_huge_bar else signal_bar.low - tick_buffer
                tp = 0 
            elif trend_dir == "BEAR":
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick_buffer
                sl = signal_bar.high - (bar_height * 0.5) if is_huge_bar else signal_bar.high + tick_buffer
                tp = 0

        # ==========================================================
        # 楔形反转逻辑 (Wedge Reversal) - 插入在 Stage 2/3 之前
        # ==========================================================
        elif "WEDGE" in setup_type:
            # 这是一个高优先级的反转信号
            
            # 1. 楔形顶 (Wedge Top) -> 做空
            if setup_type == "WEDGE_TOP":
                action = "PLACE_SELL_STOP"
                # 入场: 跌破信号 K 线低点
                entry_price = signal_bar.low - tick_buffer
                # 止损: 放在信号 K 线高点上方
                sl = signal_bar.high + tick_buffer
                
                # [Al Brooks 止盈] 楔形起点 (P1) 或 3R
                risk = abs(sl - entry_price)
                tp = entry_price - (risk * 3.0) # 3R 目标
                reason += "|Wedge_Top_Reversal"

            # 2. 楔形底 (Wedge Bottom) -> 做多
            elif setup_type == "WEDGE_BOTTOM":
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick_buffer
                sl = signal_bar.low - tick_buffer
                
                risk = abs(entry_price - sl)
                tp = entry_price + (risk * 3.0)
                reason += "|Wedge_Bottom_Reversal"

        # --- Stage 2: Channel ---
        elif "2-CHANNEL" in stage:
            if trend_dir == "BULL" and setup_type in ["H1", "H2"]:
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick_buffer
                sl = signal_bar.low - tick_buffer
                
                # 磁力止盈
                recent_high = max([c.high for c in candles[-20:]])
                target_dist = max(atr, recent_high - entry_price) 
                
                tp_2r = entry_price + (entry_price - sl) * 2.0
                tp_magnet = entry_price + target_dist
                tp = min(tp_2r, tp_magnet) 

            elif trend_dir == "BEAR" and setup_type in ["L1", "L2"]:
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick_buffer
                sl = signal_bar.high + tick_buffer
                
                recent_low = min([c.low for c in candles[-20:]])
                target_dist = max(atr, entry_price - recent_low)
                
                tp_2r = entry_price - (sl - entry_price) * 2.0
                tp_magnet = entry_price - target_dist
                tp = max(tp_2r, tp_magnet) 

        # --- Stage 3: Trading Range ---
        elif "3-TRADING_RANGE" in stage:
            # --- [内部辅助函数] 寻找最近的主要拐点 ---
            def _find_major_pivots(bars, lookback_limit=100, neighbor_strength=5):
                if len(bars) < lookback_limit: return None, None
                
                major_high = -1.0
                major_low = -1.0
                search_pool = bars[-lookback_limit:]
                pool_len = len(search_pool)
                
                # 寻找 Major High
                for i in range(pool_len - neighbor_strength - 1, neighbor_strength, -1):
                    candidate = search_pool[i]
                    left_wins = all(candidate.high >= search_pool[i-j].high for j in range(1, neighbor_strength+1))
                    right_wins = all(candidate.high >= search_pool[i+j].high for j in range(1, neighbor_strength+1))
                    if left_wins and right_wins:
                        major_high = candidate.high
                        break
                
                # 寻找 Major Low
                for i in range(pool_len - neighbor_strength - 1, neighbor_strength, -1):
                    candidate = search_pool[i]
                    left_wins = all(candidate.low <= search_pool[i-j].low for j in range(1, neighbor_strength+1))
                    right_wins = all(candidate.low <= search_pool[i+j].low for j in range(1, neighbor_strength+1))
                    if left_wins and right_wins:
                        major_low = candidate.low
                        break
                        
                return major_high, major_low

            # --- [主逻辑] ---
            p_high, p_low = _find_major_pivots(candles, lookback_limit=100, neighbor_strength=5)
            
            fallback_lookback = 50
            recent_bars_fallback = candles[-fallback_lookback:]
            
            if p_high == -1.0: 
                rg_high = max([c.high for c in recent_bars_fallback])
            else:
                rg_high = p_high
                
            if p_low == -1.0:
                rg_low = min([c.low for c in recent_bars_fallback])
            else:
                rg_low = p_low
            
            rg_height = rg_high - rg_low
            if rg_height == 0: rg_height = 0.001
            
            current_pos = (signal_bar.close - rg_low) / rg_height
            
            # 入场必须是 "Strong Signal Bar"
            prev_bar = candles[-2]
            is_engulfing_bull = (signal_bar.close > prev_bar.high) and (signal_bar.open < prev_bar.low)
            is_strong_bull = (signal_bar.close - signal_bar.open) > (atr * 0.3) 
            
            is_engulfing_bear = (signal_bar.close < prev_bar.low) and (signal_bar.open > prev_bar.high)
            is_strong_bear = (signal_bar.open - signal_bar.close) > (atr * 0.3)

            if current_pos <= 0.25: 
                # 底部做多: 必须 吞没 OR 强阳线
                if is_engulfing_bull or is_strong_bull: 
                    action = "PLACE_BUY_STOP"
                    entry_price = signal_bar.high + tick_buffer
                    sl = signal_bar.low - tick_buffer
                    tp = entry_price + (entry_price - sl) * 1.5
                    reason += "|Strong_Rev_Buy"
                    
            elif current_pos >= 0.75: 
                if is_engulfing_bear or is_strong_bear:
                    action = "PLACE_SELL_STOP"
                    entry_price = signal_bar.low - tick_buffer
                    sl = signal_bar.high + tick_buffer
                    tp = entry_price - (sl - entry_price) * 1.5
                    reason += "|Strong_Rev_Sell"
            else:
                reason += "|Middle_Wait"

        # --- Stage 4: Breakout ---
        elif "4-BREAKOUT_MODE" in stage:
            LOOKBACK = 10
            recent_bars = candles[-LOOKBACK:]
            range_high = max([c.high for c in recent_bars])
            range_low = min([c.low for c in recent_bars])
            
            mm_height = max(range_high - range_low, atr)
            target_dist = mm_height * 2.0 

            if trend_dir == "BULL":
                action = "PLACE_BUY_STOP"
                entry_price = range_high + tick_buffer
                sl = range_low - tick_buffer
                tp = entry_price + target_dist
                reason += "|MM_Target"
            elif trend_dir == "BEAR":
                action = "PLACE_SELL_STOP"
                entry_price = range_low - tick_buffer
                sl = range_high + tick_buffer
                tp = entry_price - target_dist
                reason += "|MM_Target"

        # --- 动态手数计算 ---
        if action != "HOLD":
            sl_dist = abs(entry_price - sl)
            if sl_dist == 0: sl_dist = atr 
            
            calc_lot = config.RISK_PER_TRADE_USD / (100 * sl_dist)
            lot = max(config.MIN_LOT, min(config.MAX_LOT, calc_lot))
            lot = round(lot, 2)

        return action, lot, entry_price, sl, tp, reason
