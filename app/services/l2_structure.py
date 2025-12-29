# app/services/l2_structure.py
import pandas as pd
import numpy as np
from .. import config

class StructureService:
    def update_counter(self, m5_candles, trend_dir, atr):
        if len(m5_candles) < 50:
            return {"setup": "NONE", "reason": "NO_DATA"}
            
        df = pd.DataFrame([c.dict() for c in m5_candles])
        df['ema20'] = df['close'].rolling(20).mean()
        
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
                # A. 标准突破 (破前高)
                if last['high'] > prev['high']:
                    if is_bullish_signal:
                        setup = "H1"
                        # 过滤: 离均线太远，H1 容易失败
                        if dist_to_ema > (atr * config.AB_MAGNET_DISTANCE_ATR):
                            setup = "WEAK_H1_TOO_FAR"
                        # 深度回调判定 (H2)
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
                        setup = "H1_MICRO_DB"

            # --- 空头逻辑 ---
            elif trend_dir == "BEAR":
                # A. 标准突破 (破前低)
                if last['low'] < prev['low']:
                    if is_bearish_signal:
                        setup = "L1"
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
                        setup = "L1_MICRO_DT"

        # =========================================================
        # 3. [新增] MTR (主要趋势反转) 升级检测
        # =========================================================
        # 逻辑: 如果当前是 H2/L2，且之前发生过"趋势线突破"(EMA Break)，则升级为 MTR
        if setup in ["H2", "L2"]:
            is_mtr = self._check_mtr_signal(df, trend_dir, atr, setup)
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
    def _check_mtr_signal(self, df, trend_dir, atr, current_setup):
        """
        MTR = Break of Trend Line (EMA) + Test of Extreme (H2/L2)
        这里负责检测 'Break' 部分
        """
        # 回溯 30 根 K 线寻找"强力突破"
        lookback = 30
        if len(df) < lookback: return False
        
        # 不看最近 5 根(因为那是 Test 过程)，看之前的
        history = df.iloc[-lookback:-5]
        has_break = False
        
        # 寻找 Break: 实体大(>0.6 ATR) 且 收盘穿越 EMA
        if trend_dir == "BEAR" and current_setup == "H2":
            # 这是一个潜在底部反转 (Bottom MTR)
            # 寻找之前是否有: 强阳线 + 收盘在 EMA 上方
            for i in range(len(history)):
                bar = history.iloc[i]
                is_strong = (bar['close'] - bar['open']) > (atr * 0.6)
                break_ema = bar['close'] > bar['ema20']
                if is_strong and break_ema:
                    has_break = True; break
                    
        elif trend_dir == "BULL" and current_setup == "L2":
            # 这是一个潜在顶部反转 (Top MTR)
            # 寻找之前是否有: 强阴线 + 收盘在 EMA 下方
            for i in range(len(history)):
                bar = history.iloc[i]
                is_strong = (bar['open'] - bar['close']) > (atr * 0.6)
                break_ema = bar['close'] < bar['ema20']
                if is_strong and break_ema:
                    has_break = True; break
                    
        return has_break

    # ------------------------------------------------------------------
    # 核心算法: 基于 Pivot 的模糊楔形评分
    # ------------------------------------------------------------------
    def _detect_wedge_fuzzy(self, df, atr):
        """
        返回: (Score, Type, Pivots_List)
        Type: "BEAR_WEDGE" (Top) / "BULL_WEDGE" (Bottom)
        Pivots: [P3, P2, P1] (价格)
        """
        # 1. 寻找最近的 Pivot (分形高低点)
        # 窗口大小 5: 左右各 5 根 K 线都比它低/高 (Major Pivot)
        window = 5
        pivots_high = [] # 存 (index, price)
        pivots_low = []
        
        # 倒序遍历，找最近的 3 个
        for i in range(len(df)-2, 20, -1):
            # Check High
            if i+window < len(df):
                current_high = df['high'].iloc[i]
                is_pivot_h = True
                for k in range(1, window+1):
                    if df['high'].iloc[i-k] > current_high or df['high'].iloc[i+k] > current_high:
                        is_pivot_h = False; break
                if is_pivot_h: pivots_high.append((i, current_high))
            
            # Check Low
            if i+window < len(df):
                current_low = df['low'].iloc[i]
                is_pivot_l = True
                for k in range(1, window+1):
                    if df['low'].iloc[i-k] < current_low or df['low'].iloc[i+k] < current_low:
                        is_pivot_l = False; break
                if is_pivot_l: pivots_low.append((i, current_low))
                
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
