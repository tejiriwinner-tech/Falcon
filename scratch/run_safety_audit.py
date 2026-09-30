import os

checks = [
    ('1-Tap Execute', 'mobile/lib'),
    ('MT5 Demo', 'mobile/lib'),
    ('Dispatch SELL Order', 'mobile/lib'),
    ('Dispatch BUY Order', 'mobile/lib'),
    ('2505.00', 'mobile/lib'),
    ('2475.00', 'mobile/lib'),
    ('2492.00', 'mobile/lib'),
    ('2498.50', 'mobile/lib'),
    ('Lot Size (Demo)', 'mobile/lib'),
    ('executeOrder', 'mobile/lib/screens'),
    ('MetaTrader5', 'mobile/lib'),
    ('order_send', 'mobile/lib'),
    ('order_modify', 'mobile/lib'),
    ('order_close', 'mobile/lib'),
]

for term, path in checks:
    matches = []
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.endswith('.dart'):
                fp = os.path.join(root, f)
                with open(fp, 'r', encoding='utf-8', errors='ignore') as s:
                    for i, line in enumerate(s):
                        if term.lower() in line.lower():
                            matches.append((fp, i+1, line.strip()))
    print(f'"{term}" in {path}: {len(matches)} matches')
