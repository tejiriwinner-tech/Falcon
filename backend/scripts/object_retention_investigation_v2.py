#!/usr/bin/env python3
"""
Falcon Phase 7.9.1 - Part 3: Object Retention Investigation (Post-Fix)
Investigates retained objects after the InstrumentValidator fix.
"""

import sys
import json
import time
import gc
from pathlib import Path
from typing import Dict, List, Any

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.core.instruments.instrument_validator import InstrumentValidator
from app.core.providers.provider_analytics import provider_analytics

def count_objects_by_type() -> Dict[str, int]:
    """Count GC objects by type."""
    objects = gc.get_objects()
    type_counts = {}
    for obj in objects:
        type_name = type(obj).__name__
        type_counts[type_name] = type_counts.get(type_name, 0) + 1
    return type_counts

def find_retained_validators() -> List[Dict]:
    """Find InstrumentValidator instances and their validation log sizes."""
    objects = gc.get_objects()
    validators = []
    for obj in objects:
        if isinstance(obj, InstrumentValidator):
            validators.append({
                "validation_log_size": len(obj._validation_log),
                "validation_log_maxlen": obj._validation_log.maxlen if hasattr(obj._validation_log, 'maxlen') else None,
                "registry": str(type(obj._registry).__name__)
            })
    return validators

def find_analytics_timeline_size() -> int:
    """Get ProviderAnalyticsEngine timeline size."""
    return len(provider_analytics._timeline)

def find_dict_growth() -> Dict[str, int]:
    """Count dictionary objects (potential log entries)."""
    objects = gc.get_objects()
    dict_count = sum(1 for obj in objects if isinstance(obj, dict))
    return {"total_dicts": dict_count}

def run_object_retention_investigation():
    print("=" * 80)
    print("FALCON PHASE 7.9.1 - PART 3: OBJECT RETENTION INVESTIGATION (POST-FIX)")
    print("=" * 80)

    orchestrator = PipelineOrchestrator()
    TOTAL_CYCLES = 100
    SNAPSHOT_CYCLES = [1, 10, 25, 50, 75, 100]

    gc.collect()
    baseline_counts = count_objects_by_type()
    baseline_validators = find_retained_validators()
    baseline_timeline = find_analytics_timeline_size()
    baseline_dicts = find_dict_growth()

    print(f"\n[Baseline]")
    print(f"  Total GC Objects: {sum(baseline_counts.values())}")
    print(f"  InstrumentValidator instances: {len(baseline_validators)}")
    if baseline_validators:
        for v in baseline_validators:
            print(f"    Validation Log Size: {v['validation_log_size']}, MaxLen: {v['validation_log_maxlen']}")
    print(f"  Analytics timeline size: {baseline_timeline}")
    print(f"  Total dictionaries: {baseline_dicts['total_dicts']}")

    snapshots = []

    for cycle in range(1, TOTAL_CYCLES + 1):
        try:
            report = orchestrator.run_pipeline()
        except Exception as e:
            print(f"  Cycle {cycle} error: {e}")

        if cycle in SNAPSHOT_CYCLES:
            gc.collect()
            
            current_counts = count_objects_by_type()
            current_validators = find_retained_validators()
            current_timeline = find_analytics_timeline_size()
            current_dicts = find_dict_growth()

            # Calculate growth
            total_objects = sum(current_counts.values())
            total_objects_baseline = sum(baseline_counts.values())
            object_growth = total_objects - total_objects_baseline

            snapshot = {
                "cycle": cycle,
                "total_objects": total_objects,
                "object_growth": object_growth,
                "validator_instances": len(current_validators),
                "validation_log_sizes": [v['validation_log_size'] for v in current_validators],
                "validation_log_maxlens": [v['validation_log_maxlen'] for v in current_validators],
                "timeline_size": current_timeline,
                "total_dicts": current_dicts['total_dicts'],
                "dict_growth": current_dicts['total_dicts'] - baseline_dicts['total_dicts']
            }

            snapshots.append(snapshot)

            print(f"\n[Snapshot Cycle {cycle}]")
            print(f"  Total Objects: {total_objects} (Growth: {object_growth})")
            print(f"  Validator Instances: {len(current_validators)}")
            if current_validators:
                for i, v in enumerate(current_validators):
                    print(f"    Validator {i+1}: Log Size: {v['validation_log_size']}, MaxLen: {v['validation_log_maxlen']}")
            print(f"  Analytics Timeline: {current_timeline}")
            print(f"  Total Dictionaries: {current_dicts['total_dicts']} (Growth: {snapshot['dict_growth']})")

    # Final detailed investigation
    print("\n" + "=" * 80)
    print("FINAL OBJECT RETENTION ANALYSIS (POST-FIX)")
    print("=" * 80)

    gc.collect()
    final_validators = find_retained_validators()
    
    print(f"\nInstrumentValidator Analysis:")
    for i, validator_info in enumerate(final_validators):
        print(f"  Validator {i+1}:")
        print(f"    Validation Log Size: {validator_info['validation_log_size']}")
        print(f"    Validation Log MaxLen: {validator_info['validation_log_maxlen']}")
        print(f"    Registry Type: {validator_info['registry']}")

    final_timeline = find_analytics_timeline_size()
    print(f"\nProviderAnalyticsEngine Timeline Size: {final_timeline}")
    print(f"  (Max allowed: 500)")

    # Identify key growth patterns
    print("\n" + "=" * 80)
    print("GROWTH PATTERN ANALYSIS (POST-FIX)")
    print("=" * 80)

    if len(snapshots) >= 2:
        print("\nValidation Log Growth:")
        for snap in snapshots:
            if snap['validation_log_sizes']:
                avg_log_size = sum(snap['validation_log_sizes']) / len(snap['validation_log_sizes'])
                avg_maxlen = sum([m for m in snap['validation_log_maxlens'] if m]) / len([m for m in snap['validation_log_maxlens'] if m]) if snap['validation_log_maxlens'] else 0
                print(f"  Cycle {snap['cycle']}: Average log size = {avg_log_size:.1f}, MaxLen = {avg_maxlen:.0f}")

        print("\nDictionary Growth:")
        for snap in snapshots:
            print(f"  Cycle {snap['cycle']}: {snap['total_dicts']} dicts (Growth: {snap['dict_growth']})")

    # Save report
    report = {
        "investigation": "Phase 7.9.1 Part 3 - Object Retention Investigation (Post-Fix)",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseline": {
            "total_objects": sum(baseline_counts.values()),
            "validator_instances": len(baseline_validators),
            "validation_log_sizes": [v['validation_log_size'] for v in baseline_validators],
            "validation_log_maxlens": [v['validation_log_maxlen'] for v in baseline_validators],
            "timeline_size": baseline_timeline,
            "total_dicts": baseline_dicts['total_dicts']
        },
        "snapshots": snapshots,
        "final_analysis": {
            "validator_instances": len(final_validators),
            "validation_log_sizes": [v['validation_log_size'] for v in final_validators],
            "validation_log_maxlens": [v['validation_log_maxlen'] for v in final_validators],
            "timeline_size": final_timeline
        }
    }

    reports_dir = backend_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "object_retention_investigation_post_fix.json"
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\nObject retention investigation report saved to: {report_path}")
    print("=" * 80)

    return report

if __name__ == "__main__":
    run_object_retention_investigation()
