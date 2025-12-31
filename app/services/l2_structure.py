# app/services/l2_structure.py
import pandas as pd
import numpy as np
from .. import config

class StructureService:
    def update_counter(self, df, trend_dir, atr):
        if len(df) < 50:
            return {"setup": "NONE", "reason": "NO_DATA"}
            
        # df 已经在 main 中生成并包含了 ema20
        
        if trend_dir == "NEUTRAL":
             trend_dir = "BULL" if df['ema20'].iloc[-1] > df['ema20'].iloc[-2] else "BEAR"
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        setup = "NONE"
        
        # =========================================================
        # [新增] 楔形反转检测 (Wedge Reversal Detection) - 模糊逻辑
        # =========================================================
        # 这是一个强反转信号，优先级高于 H1/H2
        wedge_score, wedge_type, wedge_pivots = self._detect_wedge_fuzzy(df, atr)
        
        # 阈值 80: 只有形态非常标准时才逆势入场
        if wedge_score >= 80:
            if wedge_type == "BEAR_WEDGE": # 楔形顶 (看空)
                setup = "WEDGE_TOP"
            elif wedge_type == "BULL_WEDGE": # 楔形底 (看多)
                setup = "WEDGE_BOTTOM"
        
        
        # ---------------------------------------------------------
        # [新增] 环境过滤器
        # ---------------------------------------------------------
        # 如果 ATR 很大 (例如 > 3.0 美金)，说明是宽幅震荡/扩散形态
        # 此时微观结构 (Micro Structure) 极易失效
        is_high_volatility = atr > 3.0
        
        # =========================================================
        # [原有] 顺势回调逻辑 (H1/H2) - 作为备选
        # =========================================================
        if setup == "NONE":
            # 定义微观容差 (例如 10% ATR)
            threshold = atr * 0.1 
            
            # 定义强信号棒
            is_bullish_signal = (last['close'] > last['open']) or (last['close'] > prev['high'])
            is_bearish_signal = (last['close'] < last['open']) or (last['close'] < prev['low'])
            
            # 磁力距离 (离 EMA 太远不做第一次回调)
            dist_to_ema = last['close'] - last['ema20']
            
            # --- 多头逻辑 ---
            if trend_dir == "BULL":
                # A. 标准 H1
                if last['high'] > prev['high']:
                    if is_bullish_signal:
                        setup = "H1"
                        # [修正] 弱趋势过滤: 如果斜率不够陡，不要做 H1，只做 H2
                        current_slope = abs(df['ema20'].iloc[-1] - df['ema20'].iloc[-4])
                        if current_slope < (atr * 0.4): 
                            setup = "WEAK_H1_WAIT_FOR_H2"
                        
                        if dist_to_ema > (atr * config.AB_MAGNET_DISTANCE_ATR):
                            setup = "WEAK_H1_TOO_FAR"
                        # H2 逻辑
                        if last['low'] < (last['ema20'] - atr * 0.2):
                            setup = "H2"
                    else:
                        setup = "WEAK_H1_IGNORE"

                # B. [补全] 微观双底 (Micro DB) - 没破前高但结构扎实
                else:
                    # 1. Matching Lows (平底)
                    is_matching_low = abs(last['low'] - prev['low']) < threshold
                    # 2. Inside Bar (内包线且低点抬高)
                    is_inside_bar = (last['high'] < prev['high']) and (last['low'] > prev['low'])
                    # 3. 必须收强阳
                    is_strong_close = (last['close'] > last['open']) and \
                                      ((last['close'] - last['low']) > (last['high'] - last['low']) * 0.6)

                    if (is_matching_low or is_inside_bar) and is_strong_close:
                        # [关键修正] 高波动环境下禁用 Micro DB
                        if is_high_volatility:
                            setup = "MICRO_DB_FILTERED_BY_ATR"
                        else:
                            setup = "H1_MICRO_DB"

            # --- 空头逻辑 (同理) ---
            elif trend_dir == "BEAR":
                # A. 标准突破 (破前低)
                if last['low'] < prev['low']:
                    if is_bearish_signal:
                        setup = "L1"
                        current_slope = abs(df['ema20'].iloc[-1] - df['ema20'].iloc[-4])
                        if current_slope < (atr * 0.4):
                             setup = "WEAK_L1_WAIT_FOR_L2"

                        if dist_to_ema < -(atr * config.AB_MAGNET_DISTANCE_ATR):
                            setup = "WEAK_L1_TOO_FAR"
                        if last['high'] > (last['ema20'] + atr * 0.2):
                            setup = "L2"
                    else:
                        setup = "WEAK_L1_IGNORE"

                # B. [补全] 微观双顶 (Micro DT)
                else:
                    is_matching_high = abs(last['high'] - prev['high']) < threshold
                    is_inside_bar = (last['low'] > prev['low']) and (last['high'] < prev['high'])
                    is_strong_close = (last['close'] < last['open']) and \
                                      ((last['high'] - last['close']) > (last['high'] - last['low']) * 0.6)

                    if (is_matching_high or is_inside_bar) and is_strong_close:
                        # [关键修正] 高波动环境下禁用 Micro DT
                        if is_high_volatility:
                            setup = "MICRO_DT_FILTERED_BY_ATR"
                        else:
                            setup = "L1_MICRO_DT"

        # --- [新增] 破坏性重置逻辑 ---
        # 如果我们正在寻找多头信号 (H1/H2)，但眼前这根是巨大的阴线趋势棒
        # 这说明回调可能变成了反转，之前的计数失效
        is_huge_bear = (last['close'] < last['open']) and \
                       (last['open'] - last['close']) > (atr * 1.5)
        
        if trend_dir == "BULL" and is_huge_bear:
            setup = "RESET_BY_BEAR_SPIKE"
            
        # 空头同理
        is_huge_bull = (last['close'] > last['open']) and \
                       (last['close'] - last['open']) > (atr * 1.5)
        if trend_dir == "BEAR" and is_huge_bull:
            setup = "RESET_BY_BULL_SPIKE"

        # =========================================================
        # 3. [新增] MTR (主要趋势反转) 升级检测
        # =========================================================
        # 逻辑: 如果当前是 H2/L2，且之前发生过"趋势线突破"(EMA Break)，则升级为 MTR
        # 关键修正: MTR 发生在 M5 产生回调信号时，需要检测历史上是否有过 EMA 突破
        # H2 setup = M5 在 BULL 趋势中回调, 如果历史上有 Bear Break EMA, 这可能是 MTR Bottom
        # L2 setup = M5 在 BEAR 趋势中回调, 如果历史上有 Bull Break EMA, 这可能是 MTR Top
        if setup in ["H2", "L2"]:
            is_mtr = self._check_mtr_signal(df, atr, setup)
            if is_mtr:
                if setup == "H2": setup = "MTR_BOTTOM" # 底部反转
                elif setup == "L2": setup = "MTR_TOP"  # 顶部反转

        return {
            "major_trend": trend_dir, 
            "setup": setup, 
            "wedge_start": wedge_pivots[2] if setup.startswith("WEDGE") else 0.0 
        }

    # ------------------------------------------------------------------
    # 辅助: 检测 MTR 前置条件 (趋势线突破)
    # ------------------------------------------------------------------
    def _check_mtr_signal(self, df, atr, current_setup):
        """
        MTR = Break of Trend Line (EMA) + Test of Extreme (H2/L2)
        这里负责检测 'Break' 部分
        
        修正: 
        - H2 setup 意味着 M5 在多头回调, 我们寻找之前是否有过强阴线打破 EMA (Bear Break)
          如果有，说明曾经尝试反转，现在 H2 可能是 MTR Bottom
        - L2 setup 意味着 M5 在空头回调, 我们寻找之前是否有过强阳线打破 EMA (Bull Break)
          如果有，说明曾经尝试反转，现在 L2 可能是 MTR Top
        """
        # 回溯 30 根 K 线寻找"强力突破"
        lookback = 30
        if len(df) < lookback: return False
        
        # 不看最近 5 根(因为那是 Test 过程)，看之前的
        history = df.iloc[-lookback:-5]
        has_break = False
        
        if current_setup == "H2":
            # H2 = 多头回调中的第二腿, 寻找之前是否有 Bear Break (曾经空头占优)
            # 这样 H2 就变成了从空头 -> 多头的 MTR Bottom
            for i in range(len(history)):
                bar = history.iloc[i]
                is_strong_bear = (bar['open'] - bar['close']) > (atr * 0.6)
                break_ema_down = bar['close'] < bar['ema20']
                if is_strong_bear and break_ema_down:
                    has_break = True; break
                    
        elif current_setup == "L2":
            # L2 = 空头回调中的第二腿, 寻找之前是否有 Bull Break (曾经多头占优)
            # 这样 L2 就变成了从多头 -> 空头的 MTR Top
            for i in range(len(history)):
                bar = history.iloc[i]
                is_strong_bull = (bar['close'] - bar['open']) > (atr * 0.6)
                break_ema_up = bar['close'] > bar['ema20']
                if is_strong_bull and break_ema_up:
                    has_break = True; break
                    
        return has_break

    # ------------------------------------------------------------------
    # 核心算法: 基于 Pivot 的模糊楔形评分
    # ------------------------------------------------------------------
    def _detect_wedge_fuzzy(self, df, atr):
        # 定义辅助函数：判断是否为 Pivot
        # 核心逻辑：左侧必须严格(5根)，右侧根据 K 线形态动态决定(1或2根)
        def is_pivot(idx, type='HIGH'):
            if idx < 5 or idx >= len(df) - 1: return False
            
            # 1. 左侧检查 (严格，确保是主要高/低点)
            window_left = 5
            current_val = df['high'].iloc[idx] if type == 'HIGH' else df['low'].iloc[idx]
            
            for k in range(1, window_left + 1):
                if idx - k < 0: break
                compare_val = df['high'].iloc[idx-k] if type == 'HIGH' else df['low'].iloc[idx-k]
                if type == 'HIGH' and compare_val > current_val: return False
                if type == 'LOW' and compare_val < current_val: return False
            
            # 2. 右侧检查 (动态宽松)
            # 默认只需 1 根确认 (最快反应)
            # 但如果这根 Pivot K线本身很弱，我们可能需要第 2 根确认
            window_right = 1 
            
            # 获取这根潜在 Pivot 的形态
            bar = df.iloc[idx]
            body = abs(bar['close'] - bar['open'])
            upper_wick = bar['high'] - max(bar['open'], bar['close'])
            lower_wick = min(bar['open'], bar['close']) - bar['low']
            
            # 判断逻辑:
            if type == 'HIGH':
                # 如果是顶部 Pivot，看是否是强空头K线 (阴线且收盘在低位，或长上影)
                is_strong_reversal = (bar['close'] < bar['open']) or (upper_wick > body)
                # 如果不强，强制要求右边 2 根都比它低，防止误报
                if not is_strong_reversal: window_right = 2
                
                # 执行右侧检查
                for k in range(1, window_right + 1):
                    if idx + k >= len(df): return False # 数据还没出来，不能确认
                    if df['high'].iloc[idx+k] > current_val: return False

            elif type == 'LOW':
                # 如果是底部 Pivot，看是否是强多头K线
                is_strong_reversal = (bar['close'] > bar['open']) or (lower_wick > body)
                if not is_strong_reversal: window_right = 2
                
                for k in range(1, window_right + 1):
                    if idx + k >= len(df): return False
                    if df['low'].iloc[idx+k] < current_val: return False
                    
            return True

        # --- 使用新逻辑寻找 Pivots ---
        pivots_high = []
        pivots_low = []
        
        # 倒序遍历 (找最近的)
        # 范围修正: len(df)-2 是因为至少要留 1 根做右侧确认
        for i in range(len(df)-2, 20, -1):
            if is_pivot(i, 'HIGH'): pivots_high.append((i, df['high'].iloc[i]))
            if is_pivot(i, 'LOW'): pivots_low.append((i, df['low'].iloc[i]))
            
            # 找到 3 个就停
            if len(pivots_high) >= 3 and len(pivots_low) >= 3: break
            
        # ----------------------------------------------------
        # 评分逻辑 A: 楔形顶 (Wedge Top) -> 看空
        # ----------------------------------------------------
        score_bear = 0
        p_bear = [0.0, 0.0, 0.0]
        
        if len(pivots_high) >= 3:
            # P3(最近), P2(中间), P1(最远)
            P3, P2, P1 = pivots_high[0][1], pivots_high[1][1], pivots_high[2][1]
            idx3 = pivots_high[0][0]
            p_bear = [P3, P2, P1]
            
            # [规则 1] 3 Pushes: 必须是 3 个越来越高的高点
            if P3 > P2 and P2 > P1:
                score_bear += 40 # 基础分: 形态成立
                
                # [规则 2] 动能衰竭 (Momentum Decay)
                # 第3推的幅度 < 第2推的幅度
                push1 = P2 - P1
                push2 = P3 - P2
                if push2 < push1:
                    score_bear += 30 # 核心加分: 完美的楔形收敛
                elif push2 < push1 * 1.2: 
                    score_bear += 10 # 勉强合格 (稍微发散或平行通道)
                else:
                    score_bear -= 20 # 惩罚: 加速上涨 (抛物线)，不是楔形
                    
                # [规则 3] 信号棒确认 (Signal Bar)
                # 当前 K 线 (P3附近) 必须表现出反转意图
                last_bar = df.iloc[-1]
                # P3 离当前不能太远 (比如就在最近 5 根内)
                if (len(df) - idx3) <= 5:
                    # 收阴 或者 长上影线
                    is_bear_bar = last_bar['close'] < last_bar['open']
                    has_tail = (last_bar['high'] - max(last_bar['open'], last_bar['close'])) > (atr * 0.3)
                    
                    if is_bear_bar: score_bear += 20
                    if has_tail: score_bear += 10
        
        # ----------------------------------------------------
        # 评分逻辑 B: 楔形底 (Wedge Bottom) -> 看多
        # ----------------------------------------------------
        score_bull = 0
        p_bull = [0.0, 0.0, 0.0]
        
        if len(pivots_low) >= 3:
            P3, P2, P1 = pivots_low[0][1], pivots_low[1][1], pivots_low[2][1]
            idx3 = pivots_low[0][0]
            p_bull = [P3, P2, P1]
            
            # [规则 1] 3 Pushes Down
            if P3 < P2 and P2 < P1:
                score_bull += 40
                
                # [规则 2] Decay
                push1 = P1 - P2
                push2 = P2 - P3
                if push2 < push1:
                    score_bull += 30
                elif push2 < push1 * 1.2:
                    score_bull += 10
                else:
                    score_bull -= 20
                    
                # [规则 3] Signal Bar
                if (len(df) - idx3) <= 5:
                    last_bar = df.iloc[-1]
                    is_bull_bar = last_bar['close'] > last_bar['open']
                    has_tail = (min(last_bar['open'], last_bar['close']) - last_bar['low']) > (atr * 0.3)
                    
                    if is_bull_bar: score_bull += 20
                    if has_tail: score_bull += 10

        # 返回分数最高的一个
        if score_bear > score_bull:
            return score_bear, "BEAR_WEDGE", p_bear
        else:
            return score_bull, "BULL_WEDGE", p_bull
