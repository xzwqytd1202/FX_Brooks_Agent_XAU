# app/services/global_risk.py
from .. import config

class GlobalRiskService:
    # [修改] 增加 current_atr 参数
    def check_safety(self, data, current_atr):
        """
        L0: 物理/账户硬风控 (引入 ATR 动态点差)
        """
        # 1. 账户熔断
        drawdown = (config.INITIAL_BALANCE - data.account_equity) / config.INITIAL_BALANCE
        if drawdown >= config.MAX_DRAWDOWN_PERCENT:
            return False, f"CIRCUIT_BREAKER:DD_{drawdown*100:.1f}%"
            
        # 2. 保证金保护
        if 0 < data.margin_level < config.MIN_MARGIN_LEVEL:
             return False, f"LOW_MARGIN:{data.margin_level:.0f}%"

        # --- [1] 北京时间换算逻辑 ---
        hour_diff = 6 if config.IS_WINTER_TIME else 5
        current_server_h = data.server_time_hour
        current_bj_h = (current_server_h + hour_diff) % 24
        
        if config.ROLLOVER_START_H_BJ <= current_bj_h < config.ROLLOVER_END_H_BJ:
             return False, f"ROLLOVER_TIME(BJ:{current_bj_h}h)"

        # 3. [修改] 动态点差保护 (ATR Based)
        # 必须有有效的 ATR，否则用保底逻辑
        if current_atr and current_atr > 0:
            # 允许最大点差 = ATR * 10% (例如 10美金ATR -> 允许1美金点差)
            # 换算成微点: USD * 100 * 10 = USD * 1000
            max_spread_points = (current_atr * config.MAX_SPREAD_ATR_RATIO) * 1000
            # 设定一个物理下限 (例如 200 微点)，防止死鱼盘无法开单
            max_spread_points = max(200, max_spread_points)
            
            if data.spread > max_spread_points:
                return False, f"HIGH_SPREAD({data.spread}>{max_spread_points:.0f})"
        else:
            # ATR 无效时的保底 (500微点)
            if data.spread > 500: return False, "HIGH_SPREAD_NO_ATR"

        # 4. 新闻过滤
        if data.news_info.impact_level == 3:
            if abs(data.news_info.minutes_to_news) <= config.NEWS_PADDING_MINUTES:
                return False, f"NEWS:{data.news_info.event_name}"

        return True, "SAFE"
