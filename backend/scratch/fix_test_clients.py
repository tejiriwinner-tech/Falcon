from pathlib import Path

API_KEY = 'falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e'
files = [
    'tests/integration/test_ai_decision_api.py',
    'tests/integration/test_alpaca_provider_integration.py',
    'tests/integration/test_analysis_api.py',
    'tests/integration/test_confluence_api.py',
    'tests/integration/test_instrument_registry_startup.py',
    'tests/integration/test_multi_timeframe_confluence_api.py',
    'tests/integration/test_risk_api.py',
    'tests/integration/test_runtime_instruments_api_endpoint.py',
    'tests/integration/test_signal_api.py',
    'tests/integration/test_signal_score_api.py',
    'tests/integration/test_structure_api.py',
    'tests/integration/test_trend_api.py',
]
old = 'TestClient(app)'
new = 'TestClient(app, headers={"X-API-Key": "' + API_KEY + '"})'
for rel in files:
    p = Path(rel)
    if not p.exists():
        print(f'SKIP: {rel}')
        continue
    txt = p.read_text(encoding='utf-8')
    if old in txt:
        p.write_text(txt.replace(old, new), encoding='utf-8')
        print(f'FIXED: {rel}')
    else:
        print(f'NO CHANGE: {rel}')
