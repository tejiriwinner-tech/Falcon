//+------------------------------------------------------------------+
//|                                              FalconExecutor.mq5  |
//|                        Falcon Intelligence 24/7 Cloud EA Bridge  |
//|                                  https://falcon-api-tejiri.fly.dev |
//+------------------------------------------------------------------+
#property copyright "Falcon Intelligence Platform"
#property link      "https://falcon-api-tejiri.fly.dev"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>

input string   InpApiUrl          = "https://falcon-api-tejiri.fly.dev/api/v1"; // Falcon Cloud API Base URL
input string   InpApiKey          = "";                                         // Optional X-API-Key Header
input int      InpPollSeconds     = 2;                                          // Polling Frequency (Seconds)
input ulong    InpMagicNumber     = 777888;                                     // Magic Number for Falcon Trades
input ulong    InpMaxDeviation    = 20;                                         // Max Slippage (Points)
input bool     InpEnableDemoSafety = true;                                      // Force Max 0.05 lot on Demo

CTrade trade;

// Track executed orders in-memory so temporary /confirm network failures do not re-open duplicate trades
string g_processedOrderIds[];
ulong  g_processedTickets[];
double g_processedFillPrices[];

int FindProcessedOrderIndex(string orderId)
{
   int total = ArraySize(g_processedOrderIds);
   for(int i = 0; i < total; i++)
   {
      if(g_processedOrderIds[i] == orderId) return i;
   }
   return -1;
}

void RecordProcessedOrder(string orderId, ulong ticket, double fillPrice)
{
   int n = ArraySize(g_processedOrderIds);
   ArrayResize(g_processedOrderIds, n + 1);
   ArrayResize(g_processedTickets, n + 1);
   ArrayResize(g_processedFillPrices, n + 1);
   g_processedOrderIds[n] = orderId;
   g_processedTickets[n] = ticket;
   g_processedFillPrices[n] = fillPrice;
}

string BuildHeaders()
{
   string h = "Content-Type: application/json\r\n";
   if(StringLen(InpApiKey) > 0)
      h += "X-API-Key: " + InpApiKey + "\r\n";
   return h;
}

void NotifyOrderConfirm(string orderId, ulong ticket, double fillPrice, string headers, int timeout)
{
   char postData[], result[];
   string resultHeaders;
   string confirmUrl = InpApiUrl + "/execution/orders/" + orderId + "/confirm";
   string confirmBody = StringFormat("{\"ticket_number\":%I64u,\"fill_price\":%f,\"slippage_pips\":0.0,\"broker_name\":\"%s\"}",
                                     ticket, fillPrice, AccountInfoString(ACCOUNT_COMPANY));
   StringToCharArray(confirmBody, postData);
   ArrayResize(postData, StringLen(confirmBody));
   WebRequest("POST", confirmUrl, headers, timeout, postData, result, resultHeaders);
}

void NotifyOrderFail(string orderId, string reason, string headers, int timeout)
{
   char postData[], result[];
   string resultHeaders;
   StringReplace(reason, "\"", "'");
   string failUrl = InpApiUrl + "/execution/orders/" + orderId + "/fail";
   string failBody = StringFormat("{\"reason\":\"%s\"}", reason);
   StringToCharArray(failBody, postData);
   ArrayResize(postData, StringLen(failBody));
   WebRequest("POST", failUrl, headers, timeout, postData, result, resultHeaders);
}

bool ResolveBrokerSymbol(string rawSymbol, string &resolvedSymbol)
{
   string clean = rawSymbol;
   StringReplace(clean, "/", "");
   StringReplace(clean, "_", "");
   StringReplace(clean, "-", "");
   StringTrimLeft(clean);
   StringTrimRight(clean);

   string suffixes[] = {"", "m", "c", ".a", ".raw", ".pro", "pro", "raw", "#", "+", ".ecn"};
   for(int i = 0; i < ArraySize(suffixes); i++)
   {
      string cand = clean + suffixes[i];
      if(SymbolSelect(cand, true))
      {
         resolvedSymbol = cand;
         return true;
      }
   }

   if(StringFind(clean, "XAU") >= 0)
   {
      for(int j = 0; j < ArraySize(suffixes); j++)
      {
         string goldCand = "GOLD" + suffixes[j];
         if(SymbolSelect(goldCand, true))
         {
            resolvedSymbol = goldCand;
            return true;
         }
      }
   }

   return false;
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagicNumber);
   trade.SetDeviationInPoints(InpMaxDeviation);
   trade.SetTypeFillingBySymbol(_Symbol);

   Print("=================================================");
   Print("🦅 Falcon Cloud Executor EA Initialized! 🦅");
   Print("API Endpoint: ", InpApiUrl);
   Print("Account Login: ", AccountInfoInteger(ACCOUNT_LOGIN));
   Print("Broker: ", AccountInfoString(ACCOUNT_COMPANY));
   Print("Trade Mode: ", (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO) ? "DEMO" : "LIVE");
   Print("=================================================");

   EventSetTimer(InpPollSeconds);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("Falcon Cloud Executor EA Stopped.");
}

//+------------------------------------------------------------------+
//| Helper to extract string value from simple JSON                  |
//+------------------------------------------------------------------+
string ExtractJsonString(string json, string key)
{
   string search = "\"" + key + "\":\"";
   int pos = StringFind(json, search);
   if(pos < 0) return "";
   pos += StringLen(search);
   int endPos = StringFind(json, "\"", pos);
   if(endPos < 0) return "";
   return StringSubstr(json, pos, endPos - pos);
}

//+------------------------------------------------------------------+
//| Helper to extract number value from simple JSON                  |
//+------------------------------------------------------------------+
double ExtractJsonNumber(string json, string key)
{
   string search = "\"" + key + "\":";
   int pos = StringFind(json, search);
   if(pos < 0) return 0.0;
   pos += StringLen(search);
   int endPos = StringFind(json, ",", pos);
   int endBracket = StringFind(json, "}", pos);
   if(endPos < 0 || (endBracket > 0 && endBracket < endPos)) endPos = endBracket;
   if(endPos < 0) return 0.0;
   string numStr = StringSubstr(json, pos, endPos - pos);
   StringTrimLeft(numStr);
   StringTrimRight(numStr);
   return StringToDouble(numStr);
}

//+------------------------------------------------------------------+
//| Timer function: Polls Falcon Cloud for pending execution orders   |
//+------------------------------------------------------------------+
void OnTimer()
{
   string url = InpApiUrl + "/execution/orders/pending";
   string headers = BuildHeaders();
   char postData[], result[];
   string resultHeaders;
   int timeout = 3000;

   ResetLastError();
   int res = WebRequest("GET", url, headers, timeout, postData, result, resultHeaders);

   if(res == -1)
   {
      int err = GetLastError();
      if(err == 4014)
      {
         Print("[ERROR] WebRequest not permitted! Please add '", InpApiUrl, "' to Tools -> Options -> Expert Advisors -> Allow WebRequest.");
      }
      return;
   }

   if(res != 200) return;

   string response = CharArrayToString(result);
   StringTrimLeft(response);
   StringTrimRight(response);

   if(response == "[]" || StringLen(response) < 10) return;

   // Process pending order
   string orderId = ExtractJsonString(response, "order_id");
   string symbolStr = ExtractJsonString(response, "symbol");
   string actionStr = ExtractJsonString(response, "action");
   string orderTypeStr = ExtractJsonString(response, "order_type");
   if(orderTypeStr == "") orderTypeStr = "MARKET";
   double lotSize = ExtractJsonNumber(response, "lot_size");
   double sl = ExtractJsonNumber(response, "stop_loss");
   double tp = ExtractJsonNumber(response, "take_profit");
   double entryPrice = ExtractJsonNumber(response, "entry_price");

   if(orderId == "" || symbolStr == "") return;

   // Deduplication check: if already executed in MT5, only retry /confirm
   int existingIdx = FindProcessedOrderIndex(orderId);
   if(existingIdx >= 0)
   {
      Print("Order ", orderId, " already executed (Ticket: ", g_processedTickets[existingIdx], "). Retrying /confirm only.");
      NotifyOrderConfirm(orderId, g_processedTickets[existingIdx], g_processedFillPrices[existingIdx], headers, timeout);
      return;
   }

   Print("Discovered Falcon order: ", orderId, " | ", actionStr, " (", orderTypeStr, ") ", lotSize, " ", symbolStr);

   if(sl <= 0.0)
   {
      Print("[FAIL] Rejecting order ", orderId, ": stop_loss <= 0 (", sl, ")");
      NotifyOrderFail(orderId, "Invalid stop_loss <= 0", headers, timeout);
      return;
   }

   // Resolve Symbol — NEVER fall back to _Symbol
   string targetSymbol = "";
   if(!ResolveBrokerSymbol(symbolStr, targetSymbol))
   {
      Print("[FAIL] Symbol not found in Market Watch: ", symbolStr);
      NotifyOrderFail(orderId, "Symbol " + symbolStr + " not found in broker Market Watch", headers, timeout);
      return;
   }

   trade.SetTypeFillingBySymbol(targetSymbol);

   // Demo safety cap applies ONLY on demo accounts
   bool isDemo = (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO);
   if(InpEnableDemoSafety && isDemo && lotSize > 0.05) lotSize = 0.05;

   // Normalize lotSize to broker volume constraints
   double volMin  = SymbolInfoDouble(targetSymbol, SYMBOL_VOLUME_MIN);
   double volMax  = SymbolInfoDouble(targetSymbol, SYMBOL_VOLUME_MAX);
   double volStep = SymbolInfoDouble(targetSymbol, SYMBOL_VOLUME_STEP);
   if(volMin <= 0.0) volMin = 0.01;
   if(volMax <= 0.0) volMax = 100.0;
   if(volStep <= 0.0) volStep = 0.01;
   if(lotSize < volMin) lotSize = volMin;
   if(lotSize > volMax) lotSize = volMax;
   lotSize = volMin + MathFloor((lotSize - volMin + 1e-9) / volStep) * volStep;
   lotSize = NormalizeDouble(lotSize, 2);

   int digits = (int)SymbolInfoInteger(targetSymbol, SYMBOL_DIGITS);
   sl = NormalizeDouble(sl, digits);
   tp = (tp > 0.0) ? NormalizeDouble(tp, digits) : 0.0;
   entryPrice = (entryPrice > 0.0) ? NormalizeDouble(entryPrice, digits) : 0.0;

   string commentStr = "Falcon:" + StringSubstr(orderId, 0, 16);
   bool success = false;

   if(actionStr == "BUY")
   {
      if(orderTypeStr == "LIMIT" && entryPrice > 0.0)
         success = trade.BuyLimit(lotSize, entryPrice, targetSymbol, sl, tp, ORDER_TIME_GTC, 0, commentStr);
      else if(orderTypeStr == "STOP" && entryPrice > 0.0)
         success = trade.BuyStop(lotSize, entryPrice, targetSymbol, sl, tp, ORDER_TIME_GTC, 0, commentStr);
      else
         success = trade.Buy(lotSize, targetSymbol, 0, sl, tp, commentStr);
   }
   else if(actionStr == "SELL")
   {
      if(orderTypeStr == "LIMIT" && entryPrice > 0.0)
         success = trade.SellLimit(lotSize, entryPrice, targetSymbol, sl, tp, ORDER_TIME_GTC, 0, commentStr);
      else if(orderTypeStr == "STOP" && entryPrice > 0.0)
         success = trade.SellStop(lotSize, entryPrice, targetSymbol, sl, tp, ORDER_TIME_GTC, 0, commentStr);
      else
         success = trade.Sell(lotSize, targetSymbol, 0, sl, tp, commentStr);
   }
   else
   {
      NotifyOrderFail(orderId, "Unsupported action: " + actionStr, headers, timeout);
      return;
   }

   if(success)
   {
      ulong ticket = trade.ResultOrder();
      double fillPrice = trade.ResultPrice();
      if(fillPrice <= 0.0) fillPrice = entryPrice;
      Print("✔ Falcon Order FILLED! Ticket: ", ticket, " @ ", fillPrice);

      RecordProcessedOrder(orderId, ticket, fillPrice);
      NotifyOrderConfirm(orderId, ticket, fillPrice, headers, timeout);
   }
   else
   {
      string errDesc = StringFormat("Retcode %u: %s", trade.ResultRetcode(), trade.ResultComment());
      Print("[FAIL] Execution failed. ", errDesc);
      NotifyOrderFail(orderId, errDesc, headers, timeout);
   }
}
//+------------------------------------------------------------------+
