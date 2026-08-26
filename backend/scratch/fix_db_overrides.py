import os
from pathlib import Path

files = [
    'tests/integration/test_ai_decision_api.py',
    'tests/integration/test_analysis_api.py',
    'tests/integration/test_confluence_api.py',
    'tests/integration/test_multi_timeframe_confluence_api.py',
    'tests/integration/test_signal_api.py',
    'tests/integration/test_signal_score_api.py',
    'tests/integration/test_structure_api.py',
    'tests/integration/test_trend_api.py',
]

for f in files:
    p = Path(f)
    if not p.exists():
        print(f"Skipping {f} (does not exist)")
        continue
    
    txt = p.read_text(encoding='utf-8')
    
    # 1. Remove module-level override
    old_override = "app.dependency_overrides[get_db] = override_get_db"
    if old_override in txt:
        # Check if it is at the module level (i.e. start of line, no spaces before it)
        txt = txt.replace("\n" + old_override + "\n", "\n# " + old_override + "\n")
        txt = txt.replace("\n" + old_override, "\n# " + old_override)
    
    # 2. Add override to setUpClass
    setup_target = "    def setUpClass(cls):\n        \"\"\"Set up test database and client.\"\"\""
    setup_replacement = setup_target + "\n        app.dependency_overrides[get_db] = override_get_db"
    
    if setup_target in txt:
        txt = txt.replace(setup_target, setup_replacement)
    else:
        # Try without docstring
        setup_target_no_doc = "    def setUpClass(cls):\n"
        # We need to be careful. Let's find def setUpClass(cls): and insert after it.
        idx = txt.find("    def setUpClass(cls):")
        if idx != -1:
            eol = txt.find("\n", idx)
            # Find next line's indentation
            txt = txt[:eol+1] + "        app.dependency_overrides[get_db] = override_get_db\n" + txt[eol+1:]
    
    # 3. Add overrides cleanup to tearDownClass
    teardown_target = "    def tearDownClass(cls):\n        \"\"\"Clean up test database.\"\"\""
    teardown_replacement = teardown_target + "\n        app.dependency_overrides.clear()"
    
    if teardown_target in txt:
        txt = txt.replace(teardown_target, teardown_replacement)
    else:
        idx = txt.find("    def tearDownClass(cls):")
        if idx != -1:
            eol = txt.find("\n", idx)
            txt = txt[:eol+1] + "        app.dependency_overrides.clear()\n" + txt[eol+1:]

    p.write_text(txt, encoding='utf-8')
    print(f"Successfully updated {f}")
