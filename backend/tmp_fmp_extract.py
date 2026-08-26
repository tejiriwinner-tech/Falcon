import requests, json, re

import requests, json, re

# Try the 2024 snapshot to find forex quote response examples
url = "https://web.archive.org/web/2024/https://financialmodelingprep.com/developer/docs/"
try:
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    if resp.status_code == 200:
        text = resp.text
        
        # Search for response examples with bid/ask near forex context
        # Look for patterns like { "symbol": "EURUSD" or { "ticker": "EUR/USD"
        for pattern in [r'"symbol"\s*:\s*"EURUSD"', r'"ticker"\s*:\s*"EUR/USD"', r'"bid"', r'"ask"']:
            for match in re.finditer(pattern, text):
                start = max(0, match.start() - 500)
                end = min(len(text), match.end() + 500)
                context = text[start:end]
                clean = re.sub(r'<[^>]+>', ' ', context)
                clean = re.sub(r'\s+', ' ', clean)
                # Check if this context also mentions forex or EURUSD
                if 'forex' in clean.lower() or 'eurusd' in clean.lower() or 'xauusd' in clean.lower():
                    print(f"=== Pattern '{pattern}' at pos {match.start()} ===")
                    print(clean[:1000])
                    print()
                    break

        # Search for "forex" near response fields
        forex_match = re.search(r'forex.*?response', text, re.IGNORECASE | re.DOTALL)
        if forex_match:
            start = max(0, forex_match.start() - 100)
            end = min(len(text), forex_match.end() + 2000)
            context = text[start:end]
            clean = re.sub(r'<[^>]+>', '\n', context)
            clean = re.sub(r'\n+', '\n', clean)
            print("=== 'forex...response' context ===")
            print(clean[:2000])
            print()

except Exception as e:
    print(f"Error: {e}")

# Try fetching the FMP forex docs page from Wayback Machine
print("\n=== Trying FMP forex docs page ===")
forex_doc_urls = [
    "https://web.archive.org/web/2024/https://site.financialmodeling.net/developer/docs/forex-historical-data-api",
    "https://web.archive.org/web/2024/https://financialmodelingprep.com/api/v3/quote/EURUSD?apikey=demo",
    "https://web.archive.org/web/2024/https://financialmodelingprep.com/api/v3/forex?apikey=demo",
    "https://web.archive.org/web/2024/https://financialmodelingprep.com/api/v3/quotes/forex?apikey=demo",
]
for url in forex_doc_urls:
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        print(f"URL: {url}")
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            text = resp.text
            # Extract JSON-like content
            json_matches = re.findall(r'\{[^{}]+\}', text[:5000])
            for m in json_matches[:5]:
                print(f"  JSON snippet: {m[:300]}")
            # Also check for bid/ask
            for kw in ["bid", "ask", "symbol", "price", "timestamp", "changesPercentage", "changePercent"]:
                idx = text.find(kw)
                if idx >= 0:
                    print(f"  '{kw}' found: {text[max(0,idx-50):idx+100].strip()[:150]}")
        else:
            print(f"  Body: {text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")
    print()