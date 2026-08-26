import pathlib
q = pathlib.Path("app/core/providers/provider_manager.py").read_text().splitlines()
print("=== core loop 258-420 ===")
for i in range(257, 420):
    print(f"{i+1}|{q[i]}")
