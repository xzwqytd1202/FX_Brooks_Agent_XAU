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
        
        # [8] 动态 Tick Buffer (0.05 ATR 或 0.2 美金)
        tick_buffer = max(config.MIN_TICK_SIZE, atr * 0.05)
        
        # 巨型 K 线判断 (3倍 ATR)
        bar_height = signal_bar.high - signal_bar.low
        is_huge_bar = bar_height > (atr * 3.0)

        # --- Stage 1: Spike ---
        if "1-STRONG_TREND" in stage:
            if trend_dir == "BULL":
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick_buffer
                sl = signal_bar.low + (bar_height * 0.5) if is_huge_bar else signal_bar.low - tick_buffer
                tp = 0 # 趋势不设TP
            elif trend_dir == "BEAR":
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick_buffer
                sl = signal_bar.high - (bar_height * 0.5) if is_huge_bar else signal_bar.high + tick_buffer
                tp = 0

        # --- Stage 2: Channel ---
        elif "2-CHANNEL" in stage:
            if trend_dir == "BULL" and setup_type in ["H1", "H2"]:
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick_buffer
                sl = signal_bar.low - tick_buffer
                tp = entry_price + (entry_price - sl) * 2.0
            elif trend_dir == "BEAR" and setup_type in ["L1", "L2"]:
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick_buffer
                sl = signal_bar.high + tick_buffer
                tp = entry_price - (sl - entry_price) * 2.0

        # --- Stage 3: Trading Range [6] ZigZag逻辑 ---
        elif "3-TRADING_RANGE" in stage:
            # 使用 50 根 K 线的极值来模拟 Major High/Low
            LOOKBACK_EXTENDED = 50
            recent_bars = candles[-LOOKBACK_EXTENDED:]
            
            rg_high = max([c.high for c in recent_bars])
            rg_low = min([c.low for c in recent_bars])
            rg_height = rg_high - rg_low
            
            if rg_height == 0: rg_height = 0.001
            current_pos = (signal_bar.close - rg_low) / rg_height
            
            # 策略: 仅在边缘 1/4 区域操作
            if current_pos <= 0.25: 
                # 底部做多: 必须收阳
                if signal_bar.close > signal_bar.open: 
                    action = "PLACE_BUY_STOP"
                    entry_price = signal_bar.high + tick_buffer
                    sl = signal_bar.low - tick_buffer
                    tp = entry_price + (entry_price - sl) * 1.5
                    reason += "|ZigZag_Buy_Low"
            elif current_pos >= 0.75: 
                # 顶部做空: 必须收阴
                if signal_bar.close < signal_bar.open:
                    action = "PLACE_SELL_STOP"
                    entry_price = signal_bar.low - tick_buffer
                    sl = signal_bar.high + tick_buffer
                    tp = entry_price - (sl - entry_price) * 1.5
                    reason += "|ZigZag_Sell_High"

        # --- Stage 4: Breakout [5] Measured Move TP ---
        elif "4-BREAKOUT_MODE" in stage:
            # 突破模式看最近 10 根的压缩区间
            LOOKBACK = 10
            recent_bars = candles[-LOOKBACK:]
            range_high = max([c.high for c in recent_bars])
            range_low = min([c.low for c in recent_bars])
            
            # 测量目标 = 区间高度 (至少 1 ATR)
            mm_height = max(range_high - range_low, atr)
            target_dist = mm_height * 2.0 

            if trend_dir == "BULL":
                action = "PLACE_BUY_STOP"
                entry_price = range_high + tick_buffer
                sl = range_low - tick_buffer
                tp = entry_price + target_dist # [5] 修改完成
                reason += "|MM_Target"
            elif trend_dir == "BEAR":
                action = "PLACE_SELL_STOP"
                entry_price = range_low - tick_buffer
                sl = range_high + tick_buffer
                tp = entry_price - target_dist # [5] 修改完成
                reason += "|MM_Target"

        # --- [3] 动态手数计算 (Fixed Risk $30) ---
        if action != "HOLD":
            sl_dist = abs(entry_price - sl)
            if sl_dist == 0: sl_dist = atr 
            
            # 1手黄金波动1美金 = 100美金盈亏
            # Risk = Lots * 100 * SL_Dist
            calc_lot = config.RISK_PER_TRADE_USD / (100 * sl_dist)
            
            # 限制范围 [0.01, 0.03]
            lot = max(config.MIN_LOT, min(config.MAX_LOT, calc_lot))
            lot = round(lot, 2)

        return action, lot, entry_price, sl, tp, reason
