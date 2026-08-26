"""Masked scan of current process logs for configured API keys."""
import os

ROOT = r"c:\Users\ACER\Documents\SCHOOL WORKS\Falcon"
ENV_PATH = os.path.join(ROOT, "backend", ".env")
FILES = [
    os.path.join(ROOT, "scratch", "backend3_out.log"),
    os.path.join(ROOT, "scratch", "backend3_err.log"),
    os.path.join(ROOT, "scratch", "flutter_run2_out.log"),
    os.path.join(ROOT, "scratch", "flutter_run2_err.log"),
]
KEY_NAMES = ["FMP_API_KEY", "TWELVEDATA_API_KEY", "ALPHA_VANTAGE_API_KEY", "FALCON_API_KEY"]


def load_keys():
    keys = {}
    with open(ENV_PATH, "r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            for name in KEY_NAMES:
                if line.startswith(name + "="):
                    keys[name] = line.split("=", 1)[1].strip().strip('"').strip("'")
    return keys


def main():
    keys = load_keys()
    for f in FILES:
        if not os.path.exists(f):
            continue
        with open(f, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
        matched = [n for n, v in keys.items() if v and v in content]
        print(f"{os.path.basename(f)}: CLEAN={str(not matched)}"
              + ("" if not matched else f" MATCHED={matched}"))
    print("SCAN_DONE")


if __name__ == "__main__":
    main()