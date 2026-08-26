#!/usr/bin/env python3
"""
Falcon Phase 7.9.1 - Part 2: Tracemalloc Investigation
Tracks memory allocations at specific cycles to identify continuously growing allocations.
"""

import sys
import json
import time
import os
import gc
import tracemalloc
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator

def run_tracemalloc_investigation():
    print("=" * 80)
    print("FALCON PHASE 7.9.1 - PART 2: TRACEMALLOC INVESTIGATION")
    print("=" * 80)

    tracemalloc.start(25)  # Track 25 frames deep
    orchestrator = PipelineOrchestrator()
    symbols = ["EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "ETHUSD"]

    TOTAL_CYCLES = 100
    SNAPSHOT_CYCLES = [1, 10, 25, 50, 75, 100]

    snapshots = {}
    current_snapshot = tracemalloc.take_snapshot()
    snapshots['startup'] = current_snapshot
    print(f"\n[Snapshot 0] Startup taken")

    for cycle in range(1, TOTAL_CYCLES + 1):
        try:
            report = orchestrator.run_pipeline()
        except Exception as e:
            print(f"  Cycle {cycle} error: {e}")

        if cycle in SNAPSHOT_CYCLES:
            gc.collect()
            current_snapshot = tracemalloc.take_snapshot()
            snapshots[f'cycle_{cycle}'] = current_snapshot
            print(f"  [Snapshot] Cycle {cycle} taken")

    tracemalloc.stop()

    # Compare snapshots to identify growing allocations
    print("\n" + "=" * 80)
    print("SNAPSHOT COMPARISONS")
    print("=" * 80)

    comparison_report = {
        "investigation": "Phase 7.9.1 Part 2 - Tracemalloc Investigation",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "snapshots_taken": list(snapshots.keys()),
        "comparisons": []
    }

    snapshot_keys = list(snapshots.keys())
    for i in range(len(snapshot_keys) - 1):
        prev_key = snapshot_keys[i]
        next_key = snapshot_keys[i + 1]
        
        prev_snapshot = snapshots[prev_key]
        next_snapshot = snapshots[next_key]
        
        stats = next_snapshot.compare_to(prev_snapshot, 'lineno')
        
        # Get top 20 allocations by size
        top_stats = stats[:20]
        
        comparison_data = {
            "from": prev_key,
            "to": next_key,
            "top_allocations": []
        }
        
        print(f"\n{prev_key} -> {next_key}:")
        for stat in top_stats:
            allocation_info = {
                "file": str(stat.traceback[0].filename) if stat.traceback else "unknown",
                "line": stat.traceback[0].lineno if stat.traceback else 0,
                "size_diff_bytes": stat.size_diff,
                "size_diff_kb": round(stat.size_diff / 1024, 2),
                "count_diff": stat.count_diff
            }
            comparison_data["top_allocations"].append(allocation_info)
            print(f"  {stat.traceback[0].filename}:{stat.traceback[0].lineno} "
                  f"+{stat.size_diff / 1024:.2f} KB ({stat.count_diff} blocks)")
        
        comparison_report["comparisons"].append(comparison_data)

    # Identify allocations that consistently grow across multiple intervals
    print("\n" + "=" * 80)
    print("CONSISTENTLY GROWING ALLOCATIONS")
    print("=" * 80)

    growing_locations = {}
    for comp in comparison_report["comparisons"]:
        for alloc in comp["top_allocations"]:
            key = f"{alloc['file']}:{alloc['line']}"
            if key not in growing_locations:
                growing_locations[key] = {
                    "file": alloc["file"],
                    "line": alloc["line"],
                    "growth_intervals": 0,
                    "total_size_kb": 0,
                    "total_blocks": 0
                }
            if alloc["size_diff_bytes"] > 0:
                growing_locations[key]["growth_intervals"] += 1
                growing_locations[key]["total_size_kb"] += alloc["size_diff_kb"]
                growing_locations[key]["total_blocks"] += alloc["count_diff"]

    # Filter for locations that grow in at least 3 intervals
    consistent_leaks = {
        k: v for k, v in growing_locations.items() 
        if v["growth_intervals"] >= 3
    }

    print(f"\nFound {len(consistent_leaks)} locations with consistent growth:")
    for location, data in sorted(consistent_leaks.items(), 
                                  key=lambda x: x[1]["total_size_kb"], 
                                  reverse=True):
        print(f"  {location}: {data['growth_intervals']} intervals, "
              f"+{data['total_size_kb']:.2f} KB total, "
              f"{data['total_blocks']} blocks")

    comparison_report["consistent_growths"] = consistent_leaks

    # Save report
    reports_dir = backend_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "tracemalloc_investigation.json"
    
    with open(report_path, "w") as f:
        json.dump(comparison_report, f, indent=2)

    print(f"\nTracemalloc investigation report saved to: {report_path}")
    print("=" * 80)

    return comparison_report

if __name__ == "__main__":
    run_tracemalloc_investigation()
