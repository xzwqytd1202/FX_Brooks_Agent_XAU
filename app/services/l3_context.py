# app/services/l3_context.py
import pandas as pd
import numpy as np
from .. import config

class ContextService:
    def identify_stage(self, df_m5, h1_candles, current_atr):
        """
        引入 H1 数据来模拟 Al Brooks 的 "Always In" 大局观
        """
        if len(df_m5) < 21: return "UNKNOWN", "WAIT"
            
        # df_m5 已经包含 ema20
        df = df_m5
        
        # --- 1. M5 基础因子计算 ---
        current_ema = df['ema20'].iloc[-1]
        prev_ema_3 = df['ema20'].iloc[-4]
        raw_slope = current_ema - prev_ema_3
        norm_slope = raw_slope / current_atr 
        
        # 穿越次数 & 压缩度
        crossings = 0
        for i in range(len(df)-20, len(df)):
            if i < 0: continue
            row = df.iloc[i]
            if pd.notna(row['ema20']) and (row['high'] > row['ema20'] > row['low']):
                crossings += 1
                
        recent_high = df['high'].tail(10).max()
        recent_low = df['low'].tail(10).min()
        is_compressed = (recent_high - recent_low) < (current_atr * config.COMPRESSION_ATR)
        
        # ---------------------------------------------------------
        # [新增 1] 重叠度计算 (Choppiness Index) - 震荡的DNA
        # ---------------------------------------------------------
        overlap_count = 0
        chop_lookback = 10
        bars_tail = df.tail(chop_lookback)
        for i in range(1, len(bars_tail)):
            curr = bars_tail.iloc[i]
            prev = bars_tail.iloc[i-1]
            # 计算垂直重叠部分: min(Highs) > max(Lows)
            overlap_h = min(curr['high'], prev['high'])
            overlap_l = max(curr['low'], prev['low'])
            
            # [修正] 必须是显著重叠 (>30% 当根K线幅度) 才算 Choppy
            # 仅仅一点点触碰不算，那是正常的趋势回调
            bar_range = curr['high'] - curr['low']
            if overlap_h > overlap_l:
                overlap_amp = overlap_h - overlap_l
                # 如果重叠幅度超过当根 K 线幅度的 30%，才算有效重叠
                if bar_range > 0 and (overlap_amp / bar_range) > 0.3:
                    overlap_count += 1
                
        # 判定标准: 10根里有6根以上重叠，或者穿越均线次数过多
        is_choppy = overlap_count >= 6 or crossings >= 4

        # [原有] Barbwire 检测 (增强版: 结合 Choppy)
        is_barbwire = False
        if is_choppy and is_compressed:
             is_barbwire = True
        
        # 强趋势因子
        last_3 = df.tail(3)
        bodies = abs(last_3['close'] - last_3['open'])
        strong_momentum = ((bodies > (current_atr * 0.8)).sum() >= 2) or (bodies.iloc[-1] > current_atr * 2.0)

        # --- 2. H1 "Always In" 方向判断 (新增) ---
        # 如果 M5 看不清，就看 H1。H1 EMA 向上 = Always In Long
        always_in_dir = "NEUTRAL"
        if h1_candles and len(h1_candles) > 20:
            df_h1 = pd.DataFrame([c.dict() for c in h1_candles])
            df_h1['ema20'] = df_h1['close'].ewm(span=20, adjust=False).mean()
            
            # [优化] 使用 3 根 K 线的平滑斜率，避免单根 K 线噪音
            # Slope = (EMA[-1] - EMA[-3]) / 2
            ema_now = df_h1['ema20'].iloc[-1]
            ema_prev_2 = df_h1['ema20'].iloc[-3]
            h1_slope = (ema_now - ema_prev_2) / 2
            
            # [关键修正] 引入阈值 (0.2 ATR)，解决"永远不为0"的问题
            # 这里简单用 M5 的 ATR 做参照，更严谨可用 H1 ATR
            h1_threshold = current_atr * 0.2
            
            if h1_slope > h1_threshold: always_in_dir = "BULL"
            elif h1_slope < -h1_threshold: always_in_dir = "BEAR"
            else: always_in_dir = "NEUTRAL" # 只有这样，Stage 3 才有机会触发

        # --- 3. 综合阶段判定 ---
        
        # Stage 1: Spike (必须同时满足不混乱)
        # 如果虽然斜率大，但是K线重叠严重(Broadening)，这通常不是 Stage 1
        # ---------------------------------------------------------
        # [修改] 阶段定义逻辑 (基于 ATR 幅度)
        # ---------------------------------------------------------
        range_10_bar = recent_high - recent_low
        
        # 定义状态
        is_stage_4 = range_10_bar < (current_atr * config.STAGE4_THRESHOLD_ATR)
        is_stage_3 = (current_atr * config.STAGE4_THRESHOLD_ATR) <= range_10_bar < (current_atr * config.STAGE3_THRESHOLD_ATR)
        
        # Stage 1: Spike (强趋势)
        # 必须有斜率 + 动能 + 不混乱
        if abs(norm_slope) > config.SLOPE_SPIKE_ATR and strong_momentum and not is_choppy:
            return "1-STRONG_TREND", ("BULL" if norm_slope > 0 else "BEAR")

        # Barbwire 检测
        if is_barbwire:
            return "0-BARBWIRE", "NEUTRAL"

        # Stage 4: Breakout Mode (极度压缩)
        if is_stage_4:
            # Stage 4 期间倾向于跟随 H1 方向，或者干脆不做 (WAIT)
            return "4-BREAKOUT_MODE", (always_in_dir if always_in_dir != "NEUTRAL" else "BULL")
            
        # Stage 3: Trading Range (宽幅震荡)
        # 如果是 Stage 3，或者之前被判定为 Choppy/Flat，都归为 Stage 3
        is_flat = abs(norm_slope) < 0.25
        
        if is_stage_3 or is_choppy or is_flat:
            return "3-TRADING_RANGE", "NEUTRAL" # 强制 NEUTRAL，迫使 L5 执行高抛低吸
            
        # Stage 2: Channel (默认)
        return "2-CHANNEL", ("BULL" if norm_slope > 0 else "BEAR")
