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

        # ------------------------------------------------------
        # Stage 3: Trading Range (区间) - [修改] 动态分形 Pivot 法
        # ------------------------------------------------------
        elif "3-TRADING_RANGE" in stage:
            # --- [内部辅助函数] 寻找最近的主要拐点 (Major Swing Pivot) ---
            def _find_major_pivots(bars, lookback_limit=100, neighbor_strength=5):
                """
                向回搜索最近的一个 Major High 和 Major Low
                neighbor_strength=5: 表示该点必须高于左边5根和右边5根 (经典的 Bill Williams 分形是2，这里用5更严格)
                """
                # 至少需要足够的 K 线
                if len(bars) < lookback_limit: return None, None
                
                # 截取最近 N 根作为搜索池 (倒序: 从最近的往回找)
                # 注意: 我们不能从当前 K 线(index=-1)开始算 Pivot，因为右边还没有 K 线出来
                # 所以我们从 index = -6 (neighbor_strength + 1) 开始往回找
                
                major_high = -1.0
                major_low = -1.0
                
                search_pool = bars[-lookback_limit:]
                pool_len = len(search_pool)
                
                # 1. 寻找最近的 Major High (Swing High)
                # 我们倒着遍历，这样找到的第一个就是"最近"的
                for i in range(pool_len - neighbor_strength - 1, neighbor_strength, -1):
                    candidate = search_pool[i]
                    
                    # 检查左边 N 根
                    left_wins = all(candidate.high >= search_pool[i-j].high for j in range(1, neighbor_strength+1))
                    # 检查右边 N 根
                    right_wins = all(candidate.high >= search_pool[i+j].high for j in range(1, neighbor_strength+1))
                    
                    if left_wins and right_wins:
                        major_high = candidate.high
                        break # 找到了最近的一个，停止搜索
                
                # 2. 寻找最近的 Major Low (Swing Low)
                for i in range(pool_len - neighbor_strength - 1, neighbor_strength, -1):
                    candidate = search_pool[i]
                    
                    left_wins = all(candidate.low <= search_pool[i-j].low for j in range(1, neighbor_strength+1))
                    right_wins = all(candidate.low <= search_pool[i+j].low for j in range(1, neighbor_strength+1))
                    
                    if left_wins and right_wins:
                        major_low = candidate.low
                        break
                        
                return major_high, major_low

            # --- [主逻辑] ---
            
            # 1. 搜索 Pivot (搜索范围 100 根, 强度 5)
            # 强度 5 意味着这个高点是前后 50 分钟内的极值，符合 "Major" 定义
            p_high, p_low = _find_major_pivots(candles, lookback_limit=100, neighbor_strength=5)
            
            # [保底机制] 如果行情是一条直线，可能找不到 Pivot
            # 此时退化为 "最近 50 根的最高最低" (Fail-safe)
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
            
            # 2. 计算区间位置 (逻辑同前，但边界更精准了)
            rg_height = rg_high - rg_low
            if rg_height == 0: rg_height = 0.001
            
            current_pos = (signal_bar.close - rg_low) / rg_height
            
            # 3. 策略: 仅在边缘 1/4 区域操作
            if current_pos <= 0.25: 
                # 底部做多: 必须收阳
                if signal_bar.close > signal_bar.open: 
                    action = "PLACE_BUY_STOP"
                    entry_price = signal_bar.high + tick_buffer
                    sl = signal_bar.low - tick_buffer
                    # 止盈目标可以是回到区间中轴 (Mean Reversion)
                    tp = entry_price + (entry_price - sl) * 1.5
                    reason += "|Fractal_Buy_Low"
                    
            elif current_pos >= 0.75: 
                # 顶部做空: 必须收阴
                if signal_bar.close < signal_bar.open:
                    action = "PLACE_SELL_STOP"
                    entry_price = signal_bar.low - tick_buffer
                    sl = signal_bar.high + tick_buffer
                    tp = entry_price - (sl - entry_price) * 1.5
                    reason += "|Fractal_Sell_High"
            else:
                reason += "|Middle_Wait"


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
