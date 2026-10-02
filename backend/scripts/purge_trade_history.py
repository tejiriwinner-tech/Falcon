"""
Falcon Database Purge Utility
Purges all trade journal, trade history, and signal deduplication signatures
from both PostgreSQL / Supabase and local SQLite databases.
"""
import sys
import os

# Ensure backend root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database.session import database_enabled, get_session
from app.core.database.models import TradeJournalRecord, SignalSignatureRecord
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.repository.signal_signature_repository import signal_signature_repository


def purge_all():
    print("Beginning purge of Falcon trade journal, history, and signal memory...")
    
    # 1. Clear via repository interface (handles active storage mode)
    trade_journal_repository.clear()
    signal_signature_repository.clear()
    print("Cleared repository in-memory structures.")
    
    # 2. Direct database wipe if database connection is configured
    if database_enabled():
        try:
            with get_session() as session:
                deleted_trades = session.query(TradeJournalRecord).delete()
                deleted_signatures = session.query(SignalSignatureRecord).delete()
                session.commit()
                print(f"PostgreSQL Database wiped: {deleted_trades} trade journal records, {deleted_signatures} signal signatures removed.")
        except Exception as ex:
            print(f"Notice during PostgreSQL wipe: {ex}")
    else:
        print("Database not enabled or running in local memory mode.")

    print("Purge completed successfully.")


if __name__ == "__main__":
    purge_all()
