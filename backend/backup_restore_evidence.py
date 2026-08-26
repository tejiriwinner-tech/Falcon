#!/usr/bin/env python
"""Phase 7.9 Part 3 — Database backup & recovery evidence (fresh, runtime).

Performs, against the live production database referenced by settings.DATABASE_URL:
  1. Backup file creation (sqlite3 online .backup) into backend/reports/
  2. Backup integrity (PRAGMA integrity_check + foreign_key_check)
  3. Restore to a TEMPORARY database (production DB is never overwritten)
  4. Data verification: per-table row counts source == restored; FK integrity

Preserves: missions / signals / decisions / risk assessments / analytics
(wherever the schema stores them — tables are introspected dynamically from
sqlite_master so the verification is schema-agnostic).
Writes backend/reports/phase79_backup_evidence.json.
"""
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(str(ROOT))  # so DATABASE_URL relative path resolves into backend/

sys.path.insert(0, str(ROOT))
from app.core.config.database import engine, Base  # noqa: E402  (no DB side-effects on import)

REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)
backup_ts = time.strftime("%Y%m%d_%H%M%S")
backup_path = REPORTS / f"falcon_prod_backup_{backup_ts}.db"
restore_path = REPORTS / f"falcon_restore_verify_{backup_ts}.db"

# Ensure schema exists (idempotent). If the file is new/empty this creates the
# real tables; if it already has data the call is a no-op.
Base.metadata.create_all(bind=engine)
db_path = str(engine.url.database or (ROOT / "falcon_market_data.db"))
if not db_path or not os.path.exists(db_path):
    db_path = str(ROOT / "falcon_market_data.db")

ev = {"phase": "7.9 Part 3", "db_path": db_path, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
    "AND name NOT LIKE 'alembic%' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

row_counts_before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
schema_version = conn.execute("PRAGMA schema_version").fetchone()[0]

# 1) BACKUP
t0 = time.time()
bconn = sqlite3.connect(str(backup_path))
conn.backup(bconn)
bconn.close()
backup_size = backup_path.stat().st_size
ev["backup"] = {"file": str(backup_path), "size_bytes": backup_size,
                "elapsed_ms": round((time.time()-t0)*1000, 2)}

# 2) INTEGRITY
ic = sqlite3.connect(str(backup_path)).execute("PRAGMA integrity_check").fetchone()[0]
fk_violations = sqlite3.connect(str(backup_path)).execute("PRAGMA foreign_key_check").fetchall()
ev["integrity"] = {"integrity_check": ic, "foreign_key_violations": len(fk_violations),
                   "schema_version": schema_version, "table_count": len(tables)}

# 3) RESTORE to temp (production DB untouched)
shutil.copyfile(str(backup_path), str(restore_path))
rc = sqlite3.connect(str(restore_path))
rc.row_factory = sqlite3.Row
row_counts_after = {t: rc.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
rk = rc.execute("PRAGMA integrity_check").fetchone()[0]
rfk = rc.execute("PRAGMA foreign_key_check").fetchall()
rc.close()
ev["restore"] = {"temp_db": str(restore_path), "integrity_check": rk,
                 "foreign_key_violations": len(rfk)}

# 4) DATA VERIFICATION
counts_match = all(row_counts_before[t] == row_counts_after[t] for t in tables)
ev["data_verification"] = {"counts_match": counts_match,
    "row_counts_before": row_counts_before,
    "row_counts_after":  row_counts_after}
ev["tables"] = tables
ev["verdict"] = "PASS" if (ic == "ok" and counts_match and len(fk_violations) == 0) else "FAIL"

conn.close()
of = REPORTS / "phase79_backup_evidence.json"
of.write_text(json.dumps(ev, indent=2, default=str))
print(json.dumps(ev, indent=2, default=str))
print("verdict:", ev["verdict"], "->", of)
