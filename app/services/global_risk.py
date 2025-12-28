# app/services/global_risk.py

from .. import config

class GlobalRiskService:
    def check_safety(self, data):
        """
        全系统安全检查 (Hard Limits)
        返回: (is_safe: bool, reason: str)
        """
        
        # 1. 账户熔断检查 (Circuit Breaker)
        # 逻辑: 总回撤超过 15% -> 停止交易
        drawdown = (config.INITIAL_BALANCE - data.account_equity) / config.INITIAL_BALANCE
        if drawdown >= config.MAX_DRAWDOWN_PERCENT:
            return False, f"CIRCUIT_BREAKER:Drawdown_{drawdown*100:.1f}%"
            
        # 2. 保证金健康度 (Margin Health)
        # 逻辑: 保证金比例 < 1000% -> 禁止开新仓
        if 0 < data.margin_level < config.MIN_MARGIN_LEVEL_PERCENT:
            return False, f"LOW_MARGIN:{data.margin_level:.1f}%"

        # 3. 平台结算时间 (Rollover)
        # 逻辑: 此时段点差爆炸，禁止交易
        h = data.server_time_hour
        # 转换北京时间
        bj_h = (h + config.TIME_OFFSET) % 24
        
        if config.ROLLOVER_START_H <= bj_h < config.ROLLOVER_END_H:
            return False, "ROLLOVER_SPREAD_PROTECT"

        # 4. 点差硬限制
        if data.spread > config.MAX_SPREAD_ALLOWED:
            return False, f"HIGH_SPREAD:{data.spread}"
            
        # 5. 重大新闻过滤 (NFP/CPI)
        # 逻辑: 3星新闻前后 30分钟
        if data.news_info.impact_level == 3:
            if abs(data.news_info.minutes_to_news) <= config.NEWS_PADDING_MINUTES:
                return False, f"NEWS_EVENT:{data.news_info.event_name}"
                
        return True, "SAFE"
