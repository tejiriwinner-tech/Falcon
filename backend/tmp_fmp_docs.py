import requests, json, sys

# Fetch FMP docs from Wayback Machine (2020 snapshot with most content)
url = "https://web.archive.org/web/20200612043221/https://financialmodelingprep.com/developer/docs/"
try:
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    text = resp.text.lower()
    print(f"Status: {resp.status_code}, Length: {len(resp.text)}")
    if resp.status_code == 200 and len(resp.text) > 500:
        for term in ["changespercentage", "changepercent", "timestamp", "dayhigh", "daylow", "volume", "forex", "xauusd", "quote", "price", "symbol", "name", "exchange", "apikey", "bid", "ask"]:
            idx = text.find(term)
            if idx >= 0:
                context = resp.text[max(0, idx-100):idx+200].replace("\n", " ")
                print(f'  "{term}" @ {idx}: ...{context}...')
except Exception as e:
    print(f"Error: {e}")

# Also try a newer snapshot
for wb_url in [
    "https://web.archive.org/web/2024/https://financialmodelingprep.com/developer/docs/",
    "https://web.archive.org/web/2023/https://financialmodelingprep.com/developer/docs/",
]:
    try:
        resp = requests.get(wb_url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        text = resp.text.lower()
        print(f"\n=== {wb_url} ===")
        print(f"Status: {resp.status_code}, Length: {len(resp.text)}")
        if resp.status_code == 200 and len(resp.text) > 500:
            for term in ["changespercentage", "changepercent", "timestamp", "quote"]:
                idx = text.find(term)
                if idx >= 0:
                    context = resp.text[max(0, idx-100):idx+200].replace("\n", " ")
                    print(f'  "{term}" @ {idx}: ...{context}...')
                    break
    except Exception as e:
        print(f"Error: {e}")