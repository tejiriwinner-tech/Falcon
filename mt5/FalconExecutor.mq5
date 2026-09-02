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
input int      InpPollSeconds     = 2;                                          // Polling Frequency (Seconds)
input ulong    InpMagicNumber     = 777888;                                     // Magic Number for Falcon Trades
input ulong    InpMaxDeviation    = 20;                                         // Max Slippage (Points)
input bool     InpEnableDemoSafety = true;                                      // Force Max 0.05 lot on Demo

CTrade trade;

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
   string cookie = NULL, headers = "Content-Type: application/json\r\n";
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
   double lotSize = ExtractJsonNumber(response, "lot_size");
   double sl = ExtractJsonNumber(response, "stop_loss");
   double tp = ExtractJsonNumber(response, "take_profit");

   if(orderId == "" || symbolStr == "") return;

   Print("Discovered Falcon order: ", orderId, " | ", actionStr, " ", lotSize, " ", symbolStr);

   // Safety cap
   if(InpEnableDemoSafety && lotSize > 0.05) lotSize = 0.05;
   if(lotSize < 0.01) lotSize = 0.01;

   // Resolve Symbol
   string targetSymbol = symbolStr;
   if(!SymbolSelect(targetSymbol, true))
   {
      targetSymbol = symbolStr + "m"; // Exness check
      if(!SymbolSelect(targetSymbol, true)) targetSymbol = _Symbol;
   }

   bool success = false;
   if(actionStr == "BUY")
   {
      success = trade.Buy(lotSize, targetSymbol, 0, sl, tp, "Falcon AI");
   }
   else if(actionStr == "SELL")
   {
      success = trade.Sell(lotSize, targetSymbol, 0, sl, tp, "Falcon AI");
   }

   if(success)
   {
      ulong ticket = trade.ResultOrder();
      double fillPrice = trade.ResultPrice();
      Print("✔ Falcon Order FILLED! Ticket: ", ticket, " @ ", fillPrice);

      // Confirm to Cloud
      string confirmUrl = InpApiUrl + "/execution/orders/" + orderId + "/confirm";
      string confirmBody = StringFormat("{\"ticket_number\":%d,\"fill_price\":%f,\"slippage_pips\":0.0,\"broker_name\":\"%s\"}", 
                                        ticket, fillPrice, AccountInfoString(ACCOUNT_COMPANY));
      StringToCharArray(confirmBody, postData);
      ArrayResize(postData, StringLen(confirmBody));

      WebRequest("POST", confirmUrl, headers, timeout, postData, result, resultHeaders);
   }
   else
   {
      Print("[FAIL] Execution failed. Code: ", trade.ResultRetcode(), " | Desc: ", trade.ResultComment());
   }
}
//+------------------------------------------------------------------+
