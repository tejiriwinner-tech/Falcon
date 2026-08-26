"""Masked scan of fresh backend log for any configured API keys."""
import os

ROOT = r"c:\Users\ACER\Documents\SCHOOL WORKS\Falcon"
ENV_PATH = os.path.join(ROOT, "backend", ".env")
LOG = os.path.join(ROOT, "scratch", "backend3_out.log")
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
    with open(LOG, "r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()
    hits = []
    for i, line in enumerate(lines, 1):
        matched = [n for n, v in keys.items() if v and v in line]
        if matched:
            masked = line
            for v in keys.values():
                if v:
                    masked = masked.replace(v, "[REDACTED]")
            hits.append(f"LINE {i} [{','.join(matched)}]: {masked.rstrip()}")
    print("LINES_CHECKED:", len(lines))
    print("KEY_HIT_LINES:", len(hits))
    for h in hits[:6]:
        print(h)
    print("LEAK_IN_FRESH_LOG:", "YES" if hits else "NO")


if __name__ == "__main__":
    main()