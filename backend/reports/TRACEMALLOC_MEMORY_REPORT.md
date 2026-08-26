# TRACEMALLOC MEMORY REPORT
## Phase 7.9.1 - Part 2: Tracemalloc Investigation

**Timestamp:** 2026-08-08T17:44:55Z  
**Investigation:** Phase 7.9.1 Part 2 - Tracemalloc Investigation  
**Snapshots Taken:** startup, cycle_1, cycle_10, cycle_25, cycle_50, cycle_75, cycle_100

---

## CONSISTENTLY GROWING ALLOCATIONS

Found 14 locations with consistent growth across multiple snapshot intervals:

### Top Memory Growth Locations:

1. **provider_analytics.py:413** - 4 intervals, +46.11 KB total, 492 blocks
   - File: `app/core/providers/provider_analytics.py`
   - Line 413: `self._timeline.append(ev)` in `_push_event` method
   - This adds TimelineEvent objects to the event timeline

2. **instrument_validator.py:223** - 5 intervals, +39.31 KB total, 296 blocks
   - File: `app/core/instruments/instrument_validator.py`
   - Line 223: `log_entry = {...}` in `_log_validation` method
   - This creates dictionary entries for validation log

3. **provider_analytics.py:73** - 4 intervals, +23.06 KB total, 492 blocks
   - File: `app/core/providers/provider_analytics.py`
   - Line 73: `self.timestamp = datetime.now(timezone.utc)` in TimelineEvent.__init__
   - Timestamp creation for each timeline event

4. **sqlalchemy/pool/base.py:1494** - 4 intervals, +14.03 KB total, 162 blocks
   - SQLAlchemy connection pool (expected behavior)

5. **instrument_validator.py:229** - 5 intervals, +10.94 KB total, 156 blocks
   - File: `app/core/instruments/instrument_validator.py`
   - Line 229: `"timestamp": datetime.now(timezone.utc).isoformat()` in validation log entry
   - Timestamp string creation for validation log

---

## KEY FINDINGS

### Primary Suspect: InstrumentValidator._validation_log

**Location:** `app/core/instruments/instrument_validator.py:45`  
**Code:** `self._validation_log: List[Dict] = []`  
**Issue:** Unbounded list that grows indefinitely with every validation call  
**Growth Pattern:** Present in 5 out of 5 snapshot intervals, +39.31 KB total  
**Evidence:** Continuous dictionary and timestamp allocations at lines 223 and 229

### Secondary Suspect: ProviderAnalyticsEngine timeline

**Location:** `app/core/providers/provider_analytics.py:215`  
**Code:** `self._timeline: Deque[TimelineEvent] = deque(maxlen=MAX_TIMELINE_EVENTS)`  
**Status:** Bounded to 500 events (MAX_TIMELINE_EVENTS) - this is actually OK  
**Growth Pattern:** Still shows growth due to event churn within the bounded window

---

## ROOT CAUSE HYPOTHESIS

The **InstrumentValidator._validation_log** is an unbounded list that accumulates validation entries without any eviction policy. With 100 cycles and multiple validations per cycle, this list grows continuously, causing the observed memory growth.

**Expected Behavior:** Validation log should have a bounded retention policy similar to the provider analytics timeline.  
**Actual Behavior:** Validation log grows indefinitely, never removing old entries.

---

## NEXT STEPS

1. Confirm root cause by examining object retention (Part 3)
2. Investigate cache lifecycle (Part 4) 
3. Verify if there are other unbounded collections
4. Implement bounded retention for InstrumentValidator._validation_log
