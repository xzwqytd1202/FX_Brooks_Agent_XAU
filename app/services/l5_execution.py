# app/services/l5_execution.py
from .. import config
import math

class ExecutionService:
    def _calculate_dynamic_thresholds(self, df_recent, ema20_val):
        """
        计算动态的高潮阈值
        """
        # 1. 计算过去 50 根 K 线的"价格-EMA距离"的标准差 (SD)
        # 这反映了当前的"乖离率波动范围"
        dists = (df_recent['close'] - ema20_val).abs()
        
        if len(dists) == 0: return 999.0, 999.0
        
        avg_dist = dists.mean()
        std_dev_dist = dists.std()
        
        # 动态乖离阈值: 平均乖离 + 3倍标准差 (99.7% 置信度)
        threshold_extension = avg_dist + (3.0 * std_dev_dist)
        
        # 2. 计算过去 50 根 K 线的"最大实体"
        bodies = (df_recent['close'] - df_recent['open']).abs()
        # 排除当前这根 (因为主要看历史背景)
        max_body_recent = bodies.iloc[:-1].max() if len(bodies) > 1 else bodies.max()
        
        # 动态巨型K线阈值: 必须比过去50根里最大的还要大 10%
        threshold_climax_bar = max_body_recent * 1.1 if max_body_recent > 0 else 999.0
        
        return threshold_extension, threshold_climax_bar

    def generate_order(self, stage, trend_dir, setup_type, df, candles, atr):
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

        # [新增] 铁丝网: 坚决不做
        if stage == "0-BARBWIRE":
            return "HOLD", 0.0, 0.0, 0.0, 0.0, "Barbwire_Chop"

        # ---------------------------------------------------------
        # [新增 1] 普遍风控: 禁止追高潮 (Climax Protection)
        # ---------------------------------------------------------
        # 如果信号棒太巨大 (比如 > 3倍 ATR)，往往是行情的终点而非起点
        # Al Brooks: "Don't buy at the top of a buy climax."
        if is_huge_bar:
             # 除非是极强的 Stage 1 刚启动，否则过滤
             if "1-STRONG_TREND" in stage:
                 return "HOLD", 0.0, 0.0, 0.0, 0.0, "Filter_Climax_Bar_Too_Big"

        # --- Stage 1: Spike (强趋势) ---
        if "1-STRONG_TREND" in stage:
            # A. 顺势逻辑 (原有: Stop Order 追单)
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
            # B. [优化] 左侧接飞刀逻辑 (Adaptive Fade - Limit Order)
            # ==========================================================
            
            # 准备数据
            ema20_val = df['ema20'].iloc[-1]
            
            # [关键] 获取动态阈值
            df_recent = df.iloc[-50:]
            dyn_ext_threshold, dyn_bar_threshold = self._calculate_dynamic_thresholds(df_recent, ema20_val)
            
            # 1. 乖离率判断 (使用动态阈值)
            dist_to_ema = signal_bar.close - ema20_val
            is_extreme_extension = abs(dist_to_ema) > dyn_ext_threshold
            
            # 2. 巨型 K 线判断 (使用动态阈值)
            current_body = abs(signal_bar.close - signal_bar.open)
            is_climax_bar = current_body > dyn_bar_threshold
            
            # 3. 连续加速 (保持不变)
            is_consecutive_bear = all(c.close < c.open for c in candles[-3:])
            is_consecutive_bull = all(c.close > c.open for c in candles[-3:])
            
            # --- 执行逻辑 (左侧 Limit) ---
            # 只有当行情打破了统计学规律 (3倍标准差) 且 创出历史级大K线 时才动手
            
            if trend_dir == "BEAR" and is_extreme_extension and is_climax_bar and is_consecutive_bear:
                action = "PLACE_BUY_LIMIT"
                # 挂单位置: 既然是极度恐慌，我们挂在 K 线低点再往下 10% 实体的地方
                limit_buffer = current_body * 0.1 
                entry_price = signal_bar.low - limit_buffer
                
                sl = entry_price - (atr * 1.5) # 硬止损
                tp = ema20_val # 回归均值
                
                lot = 0.01 
                reason = f"|Fade_Bear_Dyn(Ext:{abs(dist_to_ema):.1f}>SD3,Bar:{current_body:.1f}>Max)"

            elif trend_dir == "BULL" and is_extreme_extension and is_climax_bar and is_consecutive_bull:
                action = "PLACE_SELL_LIMIT"
                
                limit_buffer = current_body * 0.1
                entry_price = signal_bar.high + limit_buffer
                
                sl = entry_price + (atr * 1.5)
                tp = ema20_val
                
                lot = 0.01
                reason = f"|Fade_Bull_Dyn(Ext:{abs(dist_to_ema):.1f}>SD3,Bar:{current_body:.1f}>Max)"

        # --- 特殊反转形态 (Wedge & MTR) ---
        # 插入在 Stage 2/3 之前
        elif "WEDGE" in setup_type or "MTR" in setup_type:
            
            # 1. 顶部反转 (Wedge Top OR MTR Top)
            if setup_type in ["WEDGE_TOP", "MTR_TOP"]:
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick_buffer
                sl = signal_bar.high + tick_buffer
                risk = abs(sl - entry_price)
                
                # MTR/Wedge 都是大反转，目标至少 3R 或 Swing
                tp = entry_price - (risk * 3.0) 
                reason += f"|Reversal_{setup_type}"

            # 2. 底部反转 (Wedge Bottom OR MTR Bottom)
            elif setup_type in ["WEDGE_BOTTOM", "MTR_BOTTOM"]:
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick_buffer
                sl = signal_bar.low - tick_buffer
                risk = abs(entry_price - sl)
                
                tp = entry_price + (risk * 3.0)
                reason += f"|Reversal_{setup_type}"

        # --- Stage 2: Channel ---
        elif "2-CHANNEL" in stage:
            # 处理标准 H1/H2
            if trend_dir == "BULL" and setup_type in ["H1", "H2", "H1_MICRO_DB"]:
                action = "PLACE_BUY_STOP"
                
                # [处理微观双底] 入场价稍有不同
                if setup_type == "H1_MICRO_DB":
                    # 入场点设为两根K线中较高的高点 (Breakout of cluster)
                    prev_bar = candles[-2]
                    breakout_lvl = max(signal_bar.high, prev_bar.high)
                    entry_price = breakout_lvl + tick_buffer
                    # 止损设为两根中较低的低点
                    sl = min(signal_bar.low, prev_bar.low) - tick_buffer
                    reason += "|Micro_DB"
                else:
                    # 标准 H1/H2
                    entry_price = signal_bar.high + tick_buffer
                    sl = signal_bar.low - tick_buffer
                
                # Measured Move (AB=CD) Logic
                # Leg 1 Height = Recent Swing High - Recent Swing Low
                recent_high = max([c.high for c in candles[-20:]])
                recent_low = min([c.low for c in candles[-20:]])
                leg1_height = recent_high - recent_low
                
                # Target = Entry + Leg 1
                tp_mm = entry_price + leg1_height
                tp_2r = entry_price + (entry_price - sl) * 2.0
                
                # Use MM target if reasonable, else 2R
                tp = max(tp_mm, tp_2r) 
                reason += f"|Channel_Buy(MM:{leg1_height:.1f})"

            # 处理标准 L1/L2
            elif trend_dir == "BEAR" and setup_type in ["L1", "L2", "L1_MICRO_DT"]:
                action = "PLACE_SELL_STOP"
                
                if setup_type == "L1_MICRO_DT":
                    prev_bar = candles[-2]
                    breakout_lvl = min(signal_bar.low, prev_bar.low)
                    entry_price = breakout_lvl - tick_buffer
                    sl = max(signal_bar.high, prev_bar.high) + tick_buffer
                    reason += "|Micro_DT"
                else:
                    entry_price = signal_bar.low - tick_buffer
                    sl = signal_bar.high + tick_buffer
                
                # Measured Move (AB=CD) Logic
                recent_high = max([c.high for c in candles[-20:]])
                recent_low = min([c.low for c in candles[-20:]])
                leg1_height = recent_high - recent_low
                
                # Target = Entry - Leg 1
                tp_mm = entry_price - leg1_height
                tp_2r = entry_price - (sl - entry_price) * 2.0
                
                tp = min(tp_mm, tp_2r)
                reason += f"|Channel_Sell(MM:{leg1_height:.1f})" 

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

            p_high, p_low = _find_major_pivots(candles, lookback_limit=100, neighbor_strength=5)
            fallback_lookback = 50
            recent_bars_fallback = candles[-fallback_lookback:]
            
            if p_high == -1.0: rg_high = max([c.high for c in recent_bars_fallback])
            else: rg_high = p_high
            if p_low == -1.0: rg_low = min([c.low for c in recent_bars_fallback])
            else: rg_low = p_low
            
            rg_height = rg_high - rg_low
            if rg_height == 0: rg_height = 0.001
            current_pos = (signal_bar.close - rg_low) / rg_height
            
            prev_bar = candles[-2]
            is_engulfing_bull = (signal_bar.close > prev_bar.high) and (signal_bar.open < prev_bar.low)
            is_strong_bull = (signal_bar.close - signal_bar.open) > (atr * 0.3) 
            is_engulfing_bear = (signal_bar.close < prev_bar.low) and (signal_bar.open > prev_bar.high)
            is_strong_bear = (signal_bar.open - signal_bar.close) > (atr * 0.3)

            if current_pos <= 0.25: 
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

            # ---------------------------------------------------------
            # [新增 2] 假突破过滤 (Breakout Trap Protection)
            # ---------------------------------------------------------
            # 如果 ATR 很大 (> 3.0)，说明处于宽幅震荡/扩散中
            # 此时顺势突破 (MM_Target) 胜率极低，只做反转 (Reversal)
            is_high_volatility = atr > 3.0
            
            # 判断是否是反转 Setup (Wedge / MTR)
            is_reversal_setup = "WEDGE" in setup_type or "MTR" in setup_type
            
            if is_high_volatility and not is_reversal_setup:
                 return "HOLD", 0.0, 0.0, 0.0, 0.0, "Filter_High_ATR_Breakout" 

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
            if "Fade" in reason:
                pass # lot already 0.01
            else:
                sl_dist = abs(entry_price - sl)
                if sl_dist == 0: sl_dist = atr 
                calc_lot = config.RISK_PER_TRADE_USD / (100 * sl_dist)
                lot = max(config.MIN_LOT, min(config.MAX_LOT, calc_lot))
                lot = round(lot, 2)

        # --- [新增] 价格逻辑与合规性检查 ---
        if action in ["PLACE_BUY_STOP", "PLACE_BUY_LIMIT"]:
            if sl >= entry_price:
                return "HOLD", 0.0, 0.0, 0.0, 0.0, "Invalid_Buy:SL>=Entry"
            if tp > 0 and tp <= entry_price:
                return "HOLD", 0.0, 0.0, 0.0, 0.0, "Invalid_Buy:TP<=Entry"
                
        elif action in ["PLACE_SELL_STOP", "PLACE_SELL_LIMIT"]:
            if sl <= entry_price:
                 return "HOLD", 0.0, 0.0, 0.0, 0.0, "Invalid_Sell:SL<=Entry"
            if tp > 0 and tp >= entry_price:
                 return "HOLD", 0.0, 0.0, 0.0, 0.0, "Invalid_Sell:TP>=Entry"

        return action, lot, entry_price, sl, tp, reason
