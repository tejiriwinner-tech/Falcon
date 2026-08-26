"""Locate credential-bearing lines in the backend stdout log with keys MASKED.
NEVER prints a real key value."""
import os

ROOT = r"c:\Users\ACER\Documents\SCHOOL WORKS\Falcon"
ENV_PATH = os.path.join(ROOT, "backend", ".env")
LOG = os.path.join(ROOT, "scratch", "backend_run_out.log")
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


def mask(text, keys):
    for val in keys.values():
        if val:
            text = text.replace(val, "[REDACTED]")
    return text


def main():
    keys = load_keys()
    with open(LOG, "r", encoding="utf-8", errors="ignore") as fh:
        lines = fh.readlines()
    for i, line in enumerate(lines, 1):
        hits = [name for name, val in keys.items() if val and val in line]
        if hits:
            masked = mask(line.rstrip("\n"), keys)
            print(f"LINE {i} [{','.join(hits)}]: {masked}")
    print("LOCATE_DONE")


if __name__ == "__main__":
    main()