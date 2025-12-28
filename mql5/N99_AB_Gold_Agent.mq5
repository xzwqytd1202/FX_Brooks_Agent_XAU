//+------------------------------------------------------------------+
//|                                          N99_AB_Gold_Agent.mq5   |
//|                                  Copyright 2025, N99 Project     |
//|                                         https://www.mql5.com     |
//+------------------------------------------------------------------+
#property copyright "N99 AI Agent (Al Brooks Logic)"
#property link      "https://www.mql5.com"
#property version   "6.00"
#property strict

// --- 输入参数 ---
input string ServerUrl = "http://127.0.0.1:8002/signal"; // Python服务器地址 (端口 8002)
input int    MagicNumber = 888888;

// --- 全局变量 ---
string g_symbol;
datetime g_last_request_time = 0;

// --- 结构体定义 (新闻) ---
struct NewsStatus {
   bool has_news;
   int impact;        // 0-3
   int mins_to_news;  // 距离分钟
   string name;
};

//+------------------------------------------------------------------+
//| Initialization                                                   |
//+------------------------------------------------------------------+
int OnInit() {
   g_symbol = _Symbol;
   EventSetTimer(1); // 1秒检查一次
   
   // 必须允许 WebRequest
   if(!TerminalInfoInteger(TERMINAL_DLLS_ALLOWED)) {
      Print("Error: DLL imports must be allowed for WebRequest");
   }
   
   Print("N99 AB Agent Initialized. Target: ", ServerUrl);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Deinitialization                                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason) {
   EventKillTimer();
}

//+------------------------------------------------------------------+
//| Timer / Tick Function                                            |
//+------------------------------------------------------------------+
void OnTick() {
   // 限流：每 10 秒请求一次
   if(TimeCurrent() - g_last_request_time < 10) return;
   
   SendRequest();
   g_last_request_time = TimeCurrent();
}

//+------------------------------------------------------------------+
//| 核心逻辑: 构建数据并发包                                           |
//+------------------------------------------------------------------+
void SendRequest() {
   string headers = "Content-Type: application/json\\r\\n";
   char post_data[];
   char result_data[];
   string result_headers;
   
   // 构建 JSON
   string json = BuildJsonPayload();
   
   // 转换 (UTF-8)
   int len = StringToCharArray(json, post_data, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(post_data, len - 1); // 移除 \\0
   
   // 发送
   int res = WebRequest("POST", ServerUrl, headers, 3000, post_data, result_data, result_headers);
   
   if(res == 200) {
      string response = CharArrayToString(result_data);
      ProcessResponse(response);
   } else {
      Print("Error connecting to Python: ", res, " Error: ", GetLastError());
      // 如果 4014 错误，提示用户去 Options 勾选 WebRequest
      if(GetLastError() == 4014) Print("Please add URL to 'Allow WebRequest' list in Tools->Options");
   }
}

//+------------------------------------------------------------------+
//| JSON 构建器 (Schema 对齐)                                         |
//+------------------------------------------------------------------+
string BuildJsonPayload() {
   string json = "{";
   
   // 1. 基础信息
   MqlTick last_tick; SymbolInfoTick(g_symbol, last_tick);
   MqlDateTime dt; TimeCurrent(dt);
   
   json += "\\"symbol\\":\\"" + g_symbol + "\\",";
   json += "\\"server_time_hour\\":" + IntegerToString(dt.hour) + ",";
   json += "\\"server_time_minute\\":" + IntegerToString(dt.min) + ",";
   json += "\\"bid\\":" + DoubleToString(last_tick.bid, _Digits) + ",";
   json += "\\"ask\\":" + DoubleToString(last_tick.ask, _Digits) + ",";
   json += "\\"spread\\":" + IntegerToString((int)SymbolInfoInteger(g_symbol, SYMBOL_SPREAD)) + ",";
   
   // 2. 账户风控信息
   json += "\\"account_equity\\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   double margin_level = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   json += "\\"margin_level\\":" + DoubleToString(margin_level, 2) + ",";
   
   // 3. K 线数据 (Al Brooks 需要长历史)
   // M5 需要 100 根用于数浪 (Leg Counting)
   json += "\\"m5_candles\\":" + GetCandlesJson(PERIOD_M5, 100) + ",";
   // H1 需要 50 根用于环境 (Context)
   json += "\\"h1_candles\\":" + GetCandlesJson(PERIOD_H1, 50) + ",";
   
   // 4. 新闻数据
   NewsStatus news = GetUpcomingNews();
   json += "\\"news_info\\":{";
   json += "\\"has_news\\":" + (news.has_news ? "true" : "false") + ",";
   json += "\\"impact_level\\":" + IntegerToString(news.impact) + ",";
   json += "\\"minutes_to_news\\":" + IntegerToString(news.mins_to_news) + ",";
   json += "\\"event_name\\":\\"" + news.name + "\\"";
   json += "},";
   
   // 5. 持仓数据
   json += "\\"current_positions\\":" + GetPositionsJson();
   
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
      json += "\\"time\\":" + IntegerToString(rates[i].time) + ",";
      json += "\\"open\\":" + DoubleToString(rates[i].open, _Digits) + ",";
      json += "\\"high\\":" + DoubleToString(rates[i].high, _Digits) + ",";
      json += "\\"low\\":" + DoubleToString(rates[i].low, _Digits) + ",";
      json += "\\"close\\":" + DoubleToString(rates[i].close, _Digits) + ",";
      json += "\\"tick_vol\\":" + IntegerToString(rates[i].tick_volume) + ",";
      json += "\\"spread\\":" + IntegerToString(rates[i].spread);
      json += "}";
   }
   json += "]";
   return json;
}

//+------------------------------------------------------------------+
//| 辅助: 获取新闻                                                    |
//+------------------------------------------------------------------+
NewsStatus GetUpcomingNews() {
   NewsStatus status;
   status.has_news = false; status.impact = 0; status.mins_to_news = 999; status.name = "None";
   
   MqlCalendarValue values[];
   datetime start = TimeCurrent();
   datetime end = start + 3600 * 4; 
   
   if(CalendarValueHistory(values, start, end, NULL, "USD")) {
      for(int i=0; i<ArraySize(values); i++) {
         MqlCalendarEvent event;
         if(CalendarEventById(values[i].event_id, event)) {
            if(event.importance >= 2) { 
               int mins = (int)((values[i].time - TimeCurrent()) / 60);
               if(mins < status.mins_to_news) {
                  status.has_news = true;
                  status.impact = (int)event.importance; 
                  status.mins_to_news = mins;
                  status.name = "News"; 
               }
            }
         }
      }
   }
   return status;
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
            json += "\\"ticket\\":" + IntegerToString(ticket) + ",";
            json += "\\"type\\":\\"" + typeStr + "\\",";
            json += "\\"volume\\":" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + ",";  // 新增: volume字段
            json += "\\"open_price\\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), _Digits) + ",";
            json += "\\"current_price\\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT), _Digits) + ",";
            json += "\\"sl\\":" + DoubleToString(PositionGetDouble(POSITION_SL), _Digits) + ",";
            json += "\\"tp\\":" + DoubleToString(PositionGetDouble(POSITION_TP), _Digits) + ",";
            json += "\\"profit\\":" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + ",";
            json += "\\"comment\\":\\"" + PositionGetString(POSITION_COMMENT) + "\\"";
            json += "}";
            first = false;
         }
      }
   }
   json += "]";
   return json;
}

//+------------------------------------------------------------------+
//| 辅助: 删除所有挂单 (Al Brooks: 一次只做一个Setup)                 |
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
   
   // --- 挂单逻辑 (Stop Order) ---
   if(StringFind(action, "PLACE") >= 0) {
      // 1. 删除旧挂单 (Strict AB Logic: 每次只在当前K线有效)
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
      request.comment = reason; // 将阶段信息写入订单注释
      
      // 判定挂单类型和价格验证
      if(action == "PLACE_BUY_STOP") {
         request.type = ORDER_TYPE_BUY_STOP;
         // 价格验证: Buy Stop 必须在当前Ask之上
         if(SymbolInfoDouble(g_symbol, SYMBOL_ASK) > entry_price) {
            Print("Buy Stop price already crossed, skipping");
            return;
         }
      } else if(action == "PLACE_SELL_STOP") {
         request.type = ORDER_TYPE_SELL_STOP;
         // 价格验证: Sell Stop 必须在当前Bid之下
         if(SymbolInfoDouble(g_symbol, SYMBOL_BID) < entry_price) {
            Print("Sell Stop price already crossed, skipping");
            return;
         }
      } else {
         return; // 未知挂单类型
      }
      
      request.price = NormalizeDouble(entry_price, _Digits);
      request.sl = NormalizeDouble(sl, _Digits);
      request.tp = (tp > 0) ? NormalizeDouble(tp, _Digits) : 0;
      request.type_time = ORDER_TIME_SPECIFIED;
      request.expiration = TimeCurrent() + 300; // 5分钟过期
      
      if(!OrderSend(request, result)) {
         Print("Pending order failed: ", GetLastError());
      }
   }
   
   // --- 减仓逻辑 (Close Partial) ---
   if(action == "CLOSE_PARTIAL") {
      ulong ticket = (ulong)StringToInteger(ExtractJsonValue(json_str, "ticket"));
      double close_vol = StringToDouble(ExtractJsonValue(json_str, "lot"));
      
      if(PositionSelectByTicket(ticket)) {
         MqlTradeRequest request; ZeroMemory(request);
         MqlTradeResult result;   ZeroMemory(result);
         
         request.action = TRADE_ACTION_DEAL;
         request.position = ticket;
         request.symbol = g_symbol;
         request.volume = close_vol; // 平掉部分手数 (例如 0.01)
         request.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         request.price = (request.type == ORDER_TYPE_BUY) ? SymbolInfoDouble(g_symbol, SYMBOL_ASK) : SymbolInfoDouble(g_symbol, SYMBOL_BID);
         request.magic = MagicNumber;
         request.comment = "Partial_Close";
         
         if(!OrderSend(request, result)) {
            Print("Partial close failed: ", GetLastError());
         }
      }
   }
   
   // --- 全平逻辑 ---
   if(action == "CLOSE_POS") {
      ulong ticket = (ulong)StringToInteger(ExtractJsonValue(json_str, "ticket"));
      if(PositionSelectByTicket(ticket)) {
         MqlTradeRequest request; ZeroMemory(request);
         MqlTradeResult result;   ZeroMemory(result);
         
         request.action = TRADE_ACTION_DEAL;
         request.symbol = g_symbol;
         request.position = ticket;
         request.volume = PositionGetDouble(POSITION_VOLUME);
         request.type = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
         request.price = (request.type == ORDER_TYPE_BUY) ? SymbolInfoDouble(g_symbol, SYMBOL_ASK) : SymbolInfoDouble(g_symbol, SYMBOL_BID);
         request.magic = MagicNumber;
         
         if(!OrderSend(request, result)) Print("Close failed: ", GetLastError());
      }
   }
}

// --- 简易字符串提取 ---
string ExtractJsonString(string json, string key) {
   string search = "\\"" + key + "\\":\\"";
   int start = StringFind(json, search);
   if(start == -1) return "";
   start += StringLen(search);
   int end = StringFind(json, "\\"", start);
   return StringSubstr(json, start, end - start);
}

string ExtractJsonValue(string json, string key) {
   string search = "\\"" + key + "\\":";
   int start = StringFind(json, search);
   if(start == -1) return "0";
   start += StringLen(search);
   int end = StringFind(json, ",", start);
   int end2 = StringFind(json, "}", start);
   if(end2 < end && end2 != -1) end = end2;
   return StringSubstr(json, start, end - start);
}
//+------------------------------------------------------------------+
