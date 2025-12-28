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
        
        tick = config.AB_TICK_SIZE
        
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
                entry_price = signal_bar.high + tick
                # 止损逻辑
                if is_huge_bar:
                    sl = signal_bar.low + (bar_height * 0.5)
                else:
                    sl = signal_bar.low - tick
                tp = 0 
                
            elif trend_dir == "BEAR":
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick
                # 止损逻辑
                if is_huge_bar:
                    sl = signal_bar.high - (bar_height * 0.5)
                else:
                    sl = signal_bar.high + tick
                tp = 0
                
        # ------------------------------------------------------
        # 阶段 2: 通道 (Channel)
        # ------------------------------------------------------
        elif "2-CHANNEL" in stage:
            if trend_dir == "BULL" and setup_type in ["H1", "H2"]:
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick
                # 止损逻辑
                if is_huge_bar:
                    sl = signal_bar.low + (bar_height * 0.5)
                else:
                    sl = signal_bar.low - tick
                tp = entry_price + (entry_price - sl) * 2.0 
                
            elif trend_dir == "BEAR" and setup_type in ["L1", "L2"]:
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick
                # 止损逻辑
                if is_huge_bar:
                    sl = signal_bar.high - (bar_height * 0.5)
                else:
                    sl = signal_bar.high + tick
                tp = entry_price - (sl - entry_price) * 2.0

        # ------------------------------------------------------
        # 阶段 3: 交易区间 (Trading Range)
        # 策略: BLSHS (Buy Low, Sell High, Scalp)
        # 入场: 必须等待反转K线 (Reversal Bar) 出现，使用 Stop Order 确认入场
        # ------------------------------------------------------
        elif "3-TRADING_RANGE" in stage:
            # 1. 定义区间边界 (Looking back 20 bars)
            LOOKBACK_TR = 20
            recent_bars = candles[-LOOKBACK_TR:]
            
            rg_high = max([c.high for c in recent_bars])
            rg_low = min([c.low for c in recent_bars])
            rg_height = rg_high - rg_low
            
            if rg_height == 0: rg_height = 0.001
            
            # 计算当前价格在区间的位置 (0.0 = Bottom, 1.0 = Top)
            current_pos = (signal_bar.close - rg_low) / rg_height
            
            # 2. 策略分支: 只在边缘逆势操作
            
            # --- [场景 A] 位于区间底部 (下 1/3) -> 寻找做多机会 ---
            if current_pos <= 0.33:
                # 检查信号棒是否为 "多头反转棒" (Bull Reversal Bar)
                is_bull_body = signal_bar.close > signal_bar.open
                lower_tail = min(signal_bar.open, signal_bar.close) - signal_bar.low
                is_long_tail = lower_tail > (signal_bar.high - signal_bar.low) * 0.4
                
                if is_bull_body or is_long_tail:
                    action = "PLACE_BUY_STOP"
                    entry_price = signal_bar.high + tick
                    sl = signal_bar.low - tick
                    # 震荡区间做头皮 (Scalp)，通常 1:1 或者回到区间中部
                    risk = entry_price - sl
                    tp = entry_price + (risk * 1.5)
                    reason += "|TR_Buy_Low_Scalp"

            # --- [场景 B] 位于区间顶部 (上 1/3) -> 寻找做空机会 ---
            elif current_pos >= 0.66:
                # 检查信号棒是否为 "空头反转棒" (Bear Reversal Bar)
                is_bear_body = signal_bar.close < signal_bar.open
                upper_tail = signal_bar.high - max(signal_bar.open, signal_bar.close)
                is_long_tail = upper_tail > (signal_bar.high - signal_bar.low) * 0.4
                
                if is_bear_body or is_long_tail:
                    action = "PLACE_SELL_STOP"
                    entry_price = signal_bar.low - tick
                    sl = signal_bar.high + tick
                    risk = sl - entry_price
                    tp = entry_price - (risk * 1.5)
                    reason += "|TR_Sell_High_Scalp"
            
            # --- [场景 C] 位于中间 (Middle) -> 不交易 ---
            else:
                reason += "|TR_Middle_Wait"

        # ------------------------------------------------------
        # 阶段 4: 突破模式 (Breakout Mode)
        # ------------------------------------------------------
        elif "4-BREAKOUT_MODE" in stage:
            # 1. 定义 TTR (紧凑交易区间) 的范围
            LOOKBACK = 10 
            recent_bars = candles[-LOOKBACK:] # 取最后10根
            
            # 计算区间边界
            range_high = max([c.high for c in recent_bars])
            range_low = min([c.low for c in recent_bars])
            
            # 2. 顺势挂单逻辑
            if trend_dir == "BULL":
                action = "PLACE_BUY_STOP"
                # [入场] 挂在区间上沿 + 1 tick
                entry_price = range_high + tick
                # [止损] 放在区间下沿 - 1 tick
                sl = range_low - tick
                # [止盈] 2:1
                risk = entry_price - sl
                tp = entry_price + (risk * 2.0)
                reason += "|TTR_Buy_Breakout"

            elif trend_dir == "BEAR":
                action = "PLACE_SELL_STOP"
                # [入场] 挂在区间下沿 - 1 tick
                entry_price = range_low - tick
                # [止损] 放在区间上沿 + 1 tick
                sl = range_high + tick
                risk = sl - entry_price
                tp = entry_price - (risk * 2.0)
                reason += "|TTR_Sell_Breakout"
        
        # 将特殊情况写入原因
        if is_huge_bar:
            reason += huge_bar_note
            
        return action, lot, entry_price, sl, tp, reason
