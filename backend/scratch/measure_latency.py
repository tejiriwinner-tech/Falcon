"""
Falcon Phase 7.8 — BLOCKER 3: Provider Latency Investigation
Measures DNS, TCP, TLS, TTFB (provider processing), Download, and JSON parsing
across multiple samples per provider. Reports mean and standard deviation.
"""
import socket
import ssl
import time
import urllib.parse
import json
import statistics

def measure_url(url):
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    path = parsed.path
    if parsed.query:
        path += "?" + parsed.query

    timings = {}

    # 1. DNS
    t0 = time.perf_counter()
    ip = socket.gethostbyname(host)
    t1 = time.perf_counter()
    timings['dns'] = (t1 - t0) * 1000

    # 2. TCP
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(15.0)
    t2 = time.perf_counter()
    s.connect((ip, port))
    t3 = time.perf_counter()
    timings['tcp'] = (t3 - t2) * 1000

    # 3. TLS
    if parsed.scheme == 'https':
        context = ssl.create_default_context()
        t4 = time.perf_counter()
        conn = context.wrap_socket(s, server_hostname=host)
        t5 = time.perf_counter()
        timings['tls'] = (t5 - t4) * 1000
    else:
        conn = s
        timings['tls'] = 0.0
        t5 = t3

    # 4. HTTP Request + Provider Processing (TTFB)
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "User-Agent: Falcon/7.8 latency-probe\r\n"
        "Accept: application/json\r\n"
        "Connection: close\r\n\r\n"
    )
    t6 = time.perf_counter()
    conn.sendall(req.encode())
    first = conn.read(1)
    t7 = time.perf_counter()
    timings['ttfb'] = (t7 - t6) * 1000

    # 5. Download remaining
    chunks = [first]
    while True:
        chunk = conn.read(8192)
        if not chunk:
            break
        chunks.append(chunk)
    t8 = time.perf_counter()
    timings['download'] = (t8 - t7) * 1000
    conn.close()

    raw = b"".join(chunks).decode('utf-8', errors='ignore')
    body = raw.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in raw else raw

    # 6. JSON parsing
    t9 = time.perf_counter()
    try:
        json.loads(body)
    except Exception:
        pass
    t10 = time.perf_counter()
    timings['json_parse'] = (t10 - t9) * 1000
    timings['total'] = (t10 - t0) * 1000
    return timings


def probe(name, url, n=4):
    print(f"\n{'='*60}")
    print(f"  {name}  ({n} samples)")
    print(f"{'='*60}")
    results = {k: [] for k in ['dns','tcp','tls','ttfb','download','json_parse','total']}
    for i in range(n):
        print(f"  Sample {i+1}/{n}...", end=' ', flush=True)
        try:
            t = measure_url(url)
            for k in results:
                results[k].append(t[k])
            print(f"total={t['total']:.1f}ms  ttfb={t['ttfb']:.1f}ms")
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\n  {'Stage':<22} {'Mean':>9} {'StdDev':>9} {'Min':>9} {'Max':>9}")
    print(f"  {'-'*22} {'-'*9} {'-'*9} {'-'*9} {'-'*9}")
    labels = {
        'dns':        'DNS Resolution',
        'tcp':        'TCP Connect',
        'tls':        'TLS Handshake',
        'ttfb':       'HTTP+SLA (TTFB)',
        'download':   'Response Download',
        'json_parse': 'JSON Parsing',
        'total':      'TOTAL',
    }
    for k, label in labels.items():
        vals = results[k]
        if len(vals) < 2:
            continue
        mean = statistics.mean(vals)
        stdev = statistics.stdev(vals)
        print(f"  {label:<22} {mean:>8.2f}ms {stdev:>8.2f}ms {min(vals):>8.2f}ms {max(vals):>8.2f}ms")

    total_vals = results['total']
    if total_vals:
        overall_mean = statistics.mean(total_vals)
        ttfb_vals   = results['ttfb']
        ttfb_mean   = statistics.mean(ttfb_vals)
        print(f"\n  Falcon overhead (all non-TTFB stages): {overall_mean - ttfb_mean:.2f}ms mean")
        print(f"  External SLA (TTFB):                   {ttfb_mean:.2f}ms mean")
        pct = (ttfb_mean / overall_mean) * 100 if overall_mean else 0
        print(f"  External SLA share:                    {pct:.1f}%")

    return results


if __name__ == '__main__':
    twelve = "https://api.twelvedata.com/quote?symbol=XAU/USD&apikey=1009afe60cf24d72bdd9590e974aef77"
    yahoo  = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d"

    r1 = probe("TwelveData",   twelve, n=4)
    r2 = probe("Yahoo Finance", yahoo,  n=4)

    print("\n" + "="*60)
    print("  BLOCKER 3 SUMMARY")
    print("="*60)
    for name, r in [("TwelveData", r1), ("Yahoo Finance", r2)]:
        t = r['total']
        if len(t) >= 2:
            print(f"  {name:<16}: avg={statistics.mean(t):.1f}ms  max={max(t):.1f}ms  external_pct={statistics.mean(r['ttfb'])/statistics.mean(t)*100:.1f}%")
    print()
