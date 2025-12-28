# app/services/l4_probability.py

class ProbabilityService:
    def calculate_win_rate(self, context, structure, l1_features):
        """
        计算胜率 (0.0 - 1.0)
        """
        # 基础胜率
        prob_bull = 0.5
        prob_bear = 0.5
        
        # 1. 环境修正 (Context)
        if context['cycle'] == "BREAKOUT_MODE":
            # 突破模式下，顺势信号胜率大增
            pass 
        elif context['cycle'] == "TRADING_RANGE":
            # 震荡模式下，高抛低吸胜率高，突破胜率低
            pass
            
        # 2. 结构修正 (Structure)
        # H1 通常胜率一般，H2 (第二次机会) 胜率更高
        if structure['major_trend'] == "BULL":
            prob_bull += 0.1 # 顺势基础分
            if structure['setup'] == "H2":
                prob_bull += 0.15 # 黄金 Setup
            elif structure['setup'] == "H1":
                prob_bull += 0.05
                
        elif structure['major_trend'] == "BEAR":
            prob_bear += 0.1
            if structure['setup'] == "L2":
                prob_bear += 0.15
            elif structure['setup'] == "L1":
                prob_bear += 0.05
                
        # 3. 信号 K 线修正 (Signal Bar)
        # 如果 Signal Bar 是个完美的 Trend Bar，胜率加成
        if l1_features['is_trend_bar']:
            if l1_features['control'] == "BULL_CONTROL":
                prob_bull += 0.1
            elif l1_features['control'] == "BEAR_CONTROL":
                prob_bear += 0.1
                
        # 如果 Signal Bar 有巨大的反向影线 (拒绝)，胜率加成
        if l1_features['has_rejection']:
            if l1_features['rejection_type'] == "BOTTOM_TAIL": # 下方买盘
                prob_bull += 0.1
            elif l1_features['rejection_type'] == "TOP_TAIL": # 上方抛压
                prob_bear += 0.1
                
        return prob_bull, prob_bear
