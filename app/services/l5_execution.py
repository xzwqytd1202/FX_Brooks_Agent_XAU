# app/services/l5_execution.py

from .. import config

class ExecutionService:
    def generate_order(self, stage, trend_dir, setup_type, signal_bar, atr):
        """
        根据 4 个阶段生成不同的 Stop Order 策略
        
        参数:
            stage: 阶段名称 (1-STRONG_TREND, 2-CHANNEL, 3-TRADING_RANGE, 4-BREAKOUT_MODE)
            trend_dir: 趋势方向 (BULL, BEAR, NEUTRAL)
            setup_type: L2结构识别的Setup (H1, H2, L1, L2等)
            signal_bar: 当前信号K线
            atr: 当前ATR值
            
        返回: (action, lot, entry_price, sl, tp, reason)
        """
        action = "HOLD"
        entry_price = 0.0
        sl = 0.0
        tp = 0.0
        lot = config.BASE_LOT_SIZE
        reason = f"Stage:{stage}"
        
        # 定义 1 tick
        tick = config.AB_TICK_SIZE
        
        # ------------------------------------------------------
        # 阶段 1: 强趋势 (Spike)
        # 策略: 激进追单。即使没有回调，只要有新高就做。
        # ------------------------------------------------------
        if "1-STRONG_TREND" in stage:
            if trend_dir == "BULL":
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick
                sl = signal_bar.low - tick # 激进止损
                tp = 0 # 强趋势不设固定止盈，靠移动止损
            elif trend_dir == "BEAR":
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick
                sl = signal_bar.high + tick
                tp = 0
                
        # ------------------------------------------------------
        # 阶段 2: 通道 (Channel)
        # 策略: 标准回调交易 (H1/H2, L1/L2)。只做顺势。
        # ------------------------------------------------------
        elif "2-CHANNEL" in stage:
            if trend_dir == "BULL" and setup_type in ["H1", "H2"]:
                action = "PLACE_BUY_STOP"
                entry_price = signal_bar.high + tick
                # 结构止损: 前一根低点
                sl = signal_bar.low - tick
                tp = entry_price + (entry_price - sl) * 2.0 # 盈亏比 2:1
                
            elif trend_dir == "BEAR" and setup_type in ["L1", "L2"]:
                action = "PLACE_SELL_STOP"
                entry_price = signal_bar.low - tick
                sl = signal_bar.high + tick
                tp = entry_price - (sl - entry_price) * 2.0

        # ------------------------------------------------------
        # 阶段 3: 交易区间 (Trading Range)
        # 策略: 逆势思维 (BLSHS)。不做 H1/L1，只做 "Second Entry Fade"。
        # 也就是: 看到一个向上突破失败 (Bull Trap)，在它下方挂空单。
        # ------------------------------------------------------
        elif "3-TRADING_RANGE" in stage:
            # 区间只做反转。
            # 简单实现: 风险较大，V1版本建议 TRADING_RANGE 保持 HOLD
            action = "HOLD"
            reason = f"{reason}|Range_Wait"

        # ------------------------------------------------------
        # 阶段 4: 突破模式 (Breakout Mode)
        # 策略: 双向挂单 (OCO)。哪边突破做哪边。
        # ------------------------------------------------------
        elif "4-BREAKOUT_MODE" in stage:
            # 这里需要 EA 支持 OCO，或者我们只挂单边的概率高的一侧
            # 目前只做单边: 默认多头突破 (示例)
            action = "PLACE_BUY_STOP" 
            entry_price = signal_bar.high + tick
            sl = signal_bar.low - tick
            tp = entry_price + (entry_price - sl) * 1.5
            reason = f"{reason}|Breakout_Long"
            
        return action, lot, entry_price, sl, tp, reason
