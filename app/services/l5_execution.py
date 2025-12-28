# app/services/l5_execution.py
from .. import config

class ExecutionService:
    def generate_order(self, stage, trend_dir, setup_type, signal_bar, atr):
        """
        根据 4 个阶段生成不同的 Stop Order 策略
        包含: 巨型信号棒的风控修正 (Al Brooks Logic)
        """
        action = "HOLD"
        entry_price = 0.0
        sl = 0.0
        tp = 0.0
        lot = config.BASE_LOT_SIZE
        reason = f"Stage:{stage}"
        
        # 定义 1 tick
        tick = config.AB_TICK_SIZE
        
        # --- [新增] 巨型 K 线判断逻辑 ---
        # 如果信号棒幅度超过 3倍 ATR，说明这是一根高潮线 (Climax)
        # 此时放在反向极值会导致止损过大，且容易被深度回调打掉
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
                
                # [修改] 止损逻辑
                if is_huge_bar:
                    # 巨型阳线: 止损放在中点 (50% Retracement)
                    sl = signal_bar.low + (bar_height * 0.5)
                else:
                    # 普通阳线: 止损放在最低点
                    sl = signal_bar.low - tick
                    
                tp = 0 # 强趋势不设固定止盈
                
            elif trend_dir == "BEAR":
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick
                
                # [修改] 止损逻辑
                if is_huge_bar:
                    # 巨型阴线: 止损放在中点
                    sl = signal_bar.high - (bar_height * 0.5)
                else:
                    # 普通阴线: 止损放在最高点
                    sl = signal_bar.high + tick
                    
                tp = 0
                
        # ------------------------------------------------------
        # 阶段 2: 通道 (Channel)
        # ------------------------------------------------------
        elif "2-CHANNEL" in stage:
            if trend_dir == "BULL" and setup_type in ["H1", "H2"]:
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick
                
                # [修改] 止损逻辑
                if is_huge_bar:
                    sl = signal_bar.low + (bar_height * 0.5)
                else:
                    sl = signal_bar.low - tick
                
                tp = entry_price + (entry_price - sl) * 2.0 # 保持 2:1
                
            elif trend_dir == "BEAR" and setup_type in ["L1", "L2"]:
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick
                
                # [修改] 止损逻辑
                if is_huge_bar:
                    sl = signal_bar.high - (bar_height * 0.5)
                else:
                    sl = signal_bar.high + tick
                    
                tp = entry_price - (sl - entry_price) * 2.0

        # ------------------------------------------------------
        # 阶段 3: 交易区间 (Trading Range)
        # ------------------------------------------------------
        elif "3-TRADING_RANGE" in stage:
            pass # 保持空仓

        # ------------------------------------------------------
        # 阶段 4: 突破模式 (Breakout Mode)
        # ------------------------------------------------------
        elif "4-BREAKOUT_MODE" in stage:
            # 突破模式通常 K 线很小，很少触发 Huge Bar 逻辑
            # 但为了安全，同样加上判断
            action = "PLACE_BUY_STOP" 
            entry_price = signal_bar.high + tick
            
            if is_huge_bar:
                sl = signal_bar.low + (bar_height * 0.5)
            else:
                sl = signal_bar.low - tick
        
        # 将特殊情况写入原因
        if is_huge_bar:
            reason += huge_bar_note
            
        return action, lot, entry_price, sl, tp, reason
