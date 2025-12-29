# app/services/global_risk.py
from .. import config

class GlobalRiskService:
    def check_safety(self, data):
        """
        L0: 物理/账户硬风控
        """
        # 1. 账户熔断
        drawdown = (config.INITIAL_BALANCE - data.account_equity) / config.INITIAL_BALANCE
        if drawdown >= config.MAX_DRAWDOWN_PERCENT:
            return False, f"CIRCUIT_BREAKER:DD_{drawdown*100:.1f}%"
            
        # 2. 保证金保护
        if 0 < data.margin_level < config.MIN_MARGIN_LEVEL:
             return False, f"LOW_MARGIN:{data.margin_level:.0f}%"

        # --- [1] 北京时间换算逻辑 ---
        # MT5 Server (冬) = GMT+2, BJ = GMT+8 -> 差 6 小时
        # MT5 Server (夏) = GMT+3, BJ = GMT+8 -> 差 5 小时
        hour_diff = 6 if config.IS_WINTER_TIME else 5
        
        current_server_h = data.server_time_hour
        # 算出当前的北京时间小时数
        current_bj_h = (current_server_h + hour_diff) % 24
        
        # 检查是否在结算高危期
        if config.ROLLOVER_START_H_BJ <= current_bj_h < config.ROLLOVER_END_H_BJ:
             return False, f"ROLLOVER_TIME(BJ:{current_bj_h}h)"

        # 3. 点差保护 (0.5美金)
        if data.spread > config.MAX_SPREAD_ALLOWED:
            return False, f"HIGH_SPREAD:{data.spread}"

        # 4. 新闻过滤
        if data.news_info.impact_level == 3:
            if abs(data.news_info.minutes_to_news) <= config.NEWS_PADDING_MINUTES:
                return False, f"NEWS:{data.news_info.event_name}"

        return True, "SAFE"
