//+------------------------------------------------------------------+
//|                                          N99_AB_Gold_Agent.mq5   |
//|                                  Copyright 2025, N99 Project     |
//|                                         https://www.mql5.com     |
//+------------------------------------------------------------------+
#property copyright "N99 AI Agent (Al Brooks Logic V8.5)"
#property link      "https://www.mql5.com"
#property version   "8.50"
#property strict

// --- 输入参数 ---
input string ServerUrl = "http://127.0.0.1:8002/signal"; // Python服务器地址
input int    MagicNumber = 999999;                       // 必须与 Python config 保持一致

// --- 全局变量 ---
string g_symbol;
datetime g_last_request_time = 0;

// --- 结构体定义 (新闻) ---
struct NewsStatus {
   bool has_news;
   int impact;        
   int mins_to_news;
   string name;
};

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
int OnInit() {
   g_symbol = _Symbol;
   
   // [修正] WebRequest 不需要 DLL 权限，只需在 MT5 设置中配置 URL 白名单
   // 删除 DLL 检查以避免 EA 图标消失问题
   // 删除 EventSetTimer，逻辑完全由 OnTick 驱动
   
   Print("N99 AB Agent V8.5 Initialized. Target: ", ServerUrl);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Deinitialization                                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   DeleteAllPendingOrders(); // EA 移除时清理挂单
}

//+------------------------------------------------------------------+
//| Timer / Tick Function                                            |
//+------------------------------------------------------------------+
void OnTick() {
   // 限流：每 5 秒请求一次 (加快频率以适应 M5 的快速突破)
   if(TimeCurrent() - g_last_request_time < 5) return;
   
   // 仅在新 K 线产生或 K 线中间关键时刻请求
   SendRequest();
   g_last_request_time = TimeCurrent();
}

//+------------------------------------------------------------------+
//| 核心逻辑: 构建数据并发包                                           |
//+------------------------------------------------------------------+
void SendRequest() {
   string headers = "Content-Type: application/json\r\n";
   char post_data[];
   char result_data[];
   string result_headers;

   string json = BuildJsonPayload();
   
   int len = StringToCharArray(json, post_data, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(post_data, len - 1); 
   
   // [优化] 超时时间设为 5000ms，确保复杂逻辑（Wedge/MTR/ZigZag检测）有足够时间
   int res = WebRequest("POST", ServerUrl, headers, 5000, post_data, result_data, result_headers);
   
   if(res == 200) {
      string response = CharArrayToString(result_data);
      ProcessResponse(response);
   } else {
      // 只有连续错误才打印，避免刷屏
      static int err_count = 0;
      if(res == -1) err_count++;
      if(err_count > 5) {
         Print("Connection Error: ", GetLastError());
         err_count = 0;
      }
   }
}

//+------------------------------------------------------------------+
//| JSON 构建器                                                       |
//+------------------------------------------------------------------+
string BuildJsonPayload() {
   string json = "{";
   
   MqlTick last_tick; SymbolInfoTick(g_symbol, last_tick);
   MqlDateTime dt; TimeCurrent(dt); // 这是服务器时间
   
   json += "\"symbol\":\"" + g_symbol + "\",";
   json += "\"server_time_hour\":" + IntegerToString(dt.hour) + ",";
   json += "\"server_time_minute\":" + IntegerToString(dt.min) + ",";
   json += "\"bid\":" + DoubleToString(last_tick.bid, _Digits) + ",";
   json += "\"ask\":" + DoubleToString(last_tick.ask, _Digits) + ",";
   json += "\"spread\":" + IntegerToString((int)SymbolInfoInteger(g_symbol, SYMBOL_SPREAD)) + ",";
   
   json += "\"account_equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   json += "\"margin_level\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), 2) + ",";
   
   // [V9.0] M5 发送 110 根，H1 发送 50 根 (用于 Always In 判断)
   json += "\"m5_candles\":" + GetCandlesJson(PERIOD_M5, 110) + ",";
   json += "\"h1_candles\":" + GetCandlesJson(PERIOD_H1, 50) + ",";
   json += "\"news_info\":{\"has_news\":false, \"impact_level\":0, \"minutes_to_news\":999, \"event_name\":\"None\"},";
   json += "\"current_positions\":" + GetPositionsJson();
   
   json += "}";
   return json;
}

//+------------------------------------------------------------------+
//| 辅助: 获取 K 线 JSON                                              |
//+------------------------------------------------------------------+
string GetCandlesJson(ENUM_TIMEFRAMES period, int count) {
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(g_symbol, period, 0, count, rates);
   
   string json = "[";
   for(int i=0; i<copied; i++) {
      if(i > 0) json += ",";
      json += "{";
      json += "\"time\":" + IntegerToString(rates[i].time) + ",";
      json += "\"open\":" + DoubleToString(rates[i].open, _Digits) + ",";
      json += "\"high\":" + DoubleToString(rates[i].high, _Digits) + ",";
      json += "\"low\":" + DoubleToString(rates[i].low, _Digits) + ",";
      json += "\"close\":" + DoubleToString(rates[i].close, _Digits) + ",";
      json += "\"tick_vol\":" + IntegerToString(rates[i].tick_volume) + ",";
      json += "\"spread\":" + IntegerToString(rates[i].spread);
      json += "}";
   }
   json += "]";
   return json;
}

//+------------------------------------------------------------------+
//| 辅助: 获取持仓 JSON                                              |
//+------------------------------------------------------------------+
string GetPositionsJson() {
   string json = "[";
   bool first = true;
   for(int i=PositionsTotal()-1; i>=0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket)) {
         if(PositionGetString(POSITION_SYMBOL) == g_symbol && PositionGetInteger(POSITION_MAGIC) == MagicNumber) {
            if(!first) json += ",";
            long type = PositionGetInteger(POSITION_TYPE);
            string typeStr = (type == POSITION_TYPE_BUY) ? "BUY" : "SELL";
            
            json += "{";
            json += "\"ticket\":" + IntegerToString(ticket) + ",";
            json += "\"type\":\"" + typeStr + "\",";
            json += "\"volume\":" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + ",";
            json += "\"open_price\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), _Digits) + ",";
            json += "\"current_price\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT), _Digits) + ",";
            json += "\"sl\":" + DoubleToString(PositionGetDouble(POSITION_SL), _Digits) + ",";
            json += "\"tp\":" + DoubleToString(PositionGetDouble(POSITION_TP), _Digits) + ",";
            json += "\"profit\":" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + ",";
            json += "\"comment\":\"" + PositionGetString(POSITION_COMMENT) + "\"";
            json += "}";
            first = false;
         }
      }
   }
   json += "]";
   return json;
}

//+------------------------------------------------------------------+
//| 辅助: 删除所有挂单                                                |
//+------------------------------------------------------------------+
void DeleteAllPendingOrders() {
   for(int i = OrdersTotal() - 1; i >= 0; i--) {
      ulong ticket = OrderGetTicket(i);
      if(OrderSelect(ticket)) {
         if(OrderGetString(ORDER_SYMBOL) == g_symbol && OrderGetInteger(ORDER_MAGIC) == MagicNumber) {
            MqlTradeRequest request; ZeroMemory(request);
            MqlTradeResult result;   ZeroMemory(result);
            request.action = TRADE_ACTION_REMOVE;
            request.order = ticket;
            OrderSend(request, result);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| 响应处理器 (执行交易)                                            |
//+------------------------------------------------------------------+
void ProcessResponse(string json_str) {
   string action = ExtractJsonString(json_str, "action");
   
   if(action == "HOLD") return;
   
   // --- 1. 挂单逻辑 (Stop Order) ---
   if(StringFind(action, "PLACE") >= 0) {
      // 先删旧单 (Strict AB Logic)
      DeleteAllPendingOrders();
      
      string reason = ExtractJsonString(json_str, "reason");
      Print("AI SIGNAL: ", action, " | Reason: ", reason);
      
      double lot = StringToDouble(ExtractJsonValue(json_str, "lot"));
      double entry_price = StringToDouble(ExtractJsonValue(json_str, "entry_price"));
      double sl = StringToDouble(ExtractJsonValue(json_str, "sl"));
      double tp = StringToDouble(ExtractJsonValue(json_str, "tp"));
      
      MqlTradeRequest request; ZeroMemory(request);
      MqlTradeResult result;   ZeroMemory(result);
      
      request.action = TRADE_ACTION_PENDING;
      request.symbol = g_symbol;
      request.volume = lot;
      request.magic = MagicNumber;
      request.comment = reason;
      
      if(action == "PLACE_BUY_STOP") {
         request.type = ORDER_TYPE_BUY_STOP;
         // 价格验证: 防止当前价已经超过挂单价导致报错
         if(SymbolInfoDouble(g_symbol, SYMBOL_ASK) >= entry_price) return;
      } else if(action == "PLACE_SELL_STOP") {
         request.type = ORDER_TYPE_SELL_STOP;
         if(SymbolInfoDouble(g_symbol, SYMBOL_BID) <= entry_price) return;
      }
      // [新增] 支持左侧 Limit 单
      else if(action == "PLACE_BUY_LIMIT") {
         request.type = ORDER_TYPE_BUY_LIMIT;
         // BUY LIMIT: 挂单价必须低于当前价才有效，如果当前价已低于挂单价则拒绝
         if(SymbolInfoDouble(g_symbol, SYMBOL_ASK) <= entry_price) return; 
      }
      else if(action == "PLACE_SELL_LIMIT") {
         request.type = ORDER_TYPE_SELL_LIMIT;
         // Limit 单价格必须高于当前价
         if(SymbolInfoDouble(g_symbol, SYMBOL_BID) >= entry_price) return;
      }
      
      request.price = NormalizeDouble(entry_price, _Digits);
      request.sl = NormalizeDouble(sl, _Digits);
      request.tp = NormalizeDouble(tp, _Digits);
      
      // [优化] 过期时间：对齐到本根 K 线结束
      // 如果当前是 10:02:30，M5 K线将在 10:05:00 结束
      // 我们将过期时间设为 K线结束时间，而不是固定的 +300秒
      long period_seconds = PeriodSeconds(PERIOD_M5);
      datetime bar_start_time = iTime(g_symbol, PERIOD_M5, 0);
      request.expiration = bar_start_time + period_seconds; 
      
      request.type_time = ORDER_TIME_SPECIFIED;
      
      if(!OrderSend(request, result)) {
         Print("Pending order failed: ", result.retcode);
      }
   }
   
   // --- 2. 减仓逻辑 (Close Partial) ---
   if(action == "CLOSE_PARTIAL") {
      ulong ticket = (ulong)StringToInteger(ExtractJsonValue(json_str, "ticket"));
      double close_vol = StringToDouble(ExtractJsonValue(json_str, "lot"));
      
      if(PositionSelectByTicket(ticket)) {
         MqlTradeRequest request; ZeroMemory(request);
         MqlTradeResult result;   ZeroMemory(result);
         
         request.action = TRADE_ACTION_DEAL;
         request.position = ticket;
         request.symbol = g_symbol;
         request.volume = close_vol;
         
         // 自动判断方向：买单 -> 卖出平仓；卖单 -> 买入平仓
         long pos_type = PositionGetInteger(POSITION_TYPE);
         request.type = (pos_type == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         request.price = (request.type == ORDER_TYPE_BUY) ? SymbolInfoDouble(g_symbol, SYMBOL_ASK) : SymbolInfoDouble(g_symbol, SYMBOL_BID);
         request.magic = MagicNumber;
         
         // [修正] 改为全大写，与 Python 端的 "PARTIAL" 匹配，避免重复减仓
         request.comment = "PARTIAL_CLOSE";
         
         if(!OrderSend(request, result)) {
            Print("Partial close failed: ", result.retcode);
         } else {
            Print("Partial close executed: ", close_vol, " lots");
         }
      }
   }
   
   // --- 3. 全平逻辑 (止损/风控触发) ---
   if(action == "CLOSE_POS") {
      ulong ticket = (ulong)StringToInteger(ExtractJsonValue(json_str, "ticket"));
      if(PositionSelectByTicket(ticket)) {
         MqlTradeRequest request; ZeroMemory(request);
         MqlTradeResult result;   ZeroMemory(result);
         
         request.action = TRADE_ACTION_DEAL;
         request.position = ticket;
         request.symbol = g_symbol;
         request.volume = PositionGetDouble(POSITION_VOLUME);
         request.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         request.price = (request.type == ORDER_TYPE_BUY) ? SymbolInfoDouble(g_symbol, SYMBOL_ASK) : SymbolInfoDouble(g_symbol, SYMBOL_BID);
         request.magic = MagicNumber;
         
         OrderSend(request, result);
      }
   }
}

// --- 简易字符串提取 (保持不变) ---
string ExtractJsonString(string json, string key) {
   string search = "\"" + key + "\":\"";
   int start = StringFind(json, search);
   if(start == -1) return "";
   start += StringLen(search);
   int end = StringFind(json, "\"", start);
   return StringSubstr(json, start, end - start);
}

string ExtractJsonValue(string json, string key) {
   string search = "\"" + key + "\":";
   int start = StringFind(json, search);
   if(start == -1) return "0";
   start += StringLen(search);
   int end = StringFind(json, ",", start);
   int end2 = StringFind(json, "}", start);
   if(end2 < end && end2 != -1) end = end2;
   return StringSubstr(json, start, end - start);
}
//+------------------------------------------------------------------+
