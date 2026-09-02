"""
Falcon Learning & Signal Generation Automation Script

This script automates the complete learning cycle:
1. Runs the intelligence pipeline to generate new signals
2. Generates learning insights from historical data
3. Optimizes strategies based on performance
4. Stores all artifacts for continuous improvement

Run this script every 15-30 minutes during trading hours to build
historical data and enable real learning.
"""
import asyncio
import time
import requests
from datetime import datetime, timezone

# Backend API base URL
BASE_URL = "http://127.0.0.1:8000/api/v1"


def run_learning_cycle():
    """Execute complete learning cycle using REST API calls."""
    print("=" * 80)
    print(f"FALCON LEARNING CYCLE - {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    start_time = time.time()

    # ── Stage 1: Run Intelligence Pipeline ────────────────────────────────
    print("\n[Stage 1] Running Intelligence Pipeline...")
    try:
        response = requests.post(f"{BASE_URL}/missions/run", timeout=180)
        if response.status_code in [200, 201]:  # Accept both 200 OK and 201 Created
            mission = response.json()
            print(f"[SUCCESS] Pipeline completed: {mission.get('id')}")
            print(f"   Status: {mission.get('status')}")
            print(f"   Duration: {mission.get('performance', {}).get('totalDurationMs', 0)}ms")
            print(f"   Candidates: {mission.get('pipelineSummary', {}).get('candidateCount', 0)}")
            print(f"   Decisions: {mission.get('pipelineSummary', {}).get('decisionCount', 0)}")
        else:
            print(f"[FAILED] Pipeline failed: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return
    except Exception as e:
        print(f"[FAILED] Pipeline failed: {e}")
        return

    # ── Stage 2: Generate Learning Insights ─────────────────────────────────
    print("\n[Stage 2] Generating Learning Insights...")
    try:
        response = requests.get(f"{BASE_URL}/learning-insights", timeout=60)
        if response.status_code == 200:
            insights_data = response.json()
            summary = insights_data.get('summary', {})
            print(f"[SUCCESS] Generated {summary.get('totalInsights', 0)} learning insights")
            print(f"   Market insights: {summary.get('marketInsights', 0)}")
            print(f"   Strategy insights: {summary.get('strategyInsights', 0)}")
            print(f"   Risk insights: {summary.get('riskInsights', 0)}")
            print(f"   Average confidence: {summary.get('averageConfidence', 0)}%")
        else:
            print(f"[FAILED] Learning insights failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"[FAILED] Learning insights failed: {e}")

    # ── Stage 3: Generate Strategy Intelligence ────────────────────────────
    print("\n[Stage 3] Generating Strategy Intelligence...")
    try:
        response = requests.get(f"{BASE_URL}/strategy-intelligence", timeout=120)
        if response.status_code == 200:
            intel_data = response.json()
            print(f"[SUCCESS] Generated {len(intel_data.get('reports', []))} strategy intelligence reports")
        else:
            print(f"[FAILED] Strategy intelligence failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"[FAILED] Strategy intelligence failed: {e}")
        print("[INFO] Stage 3 is optional - continuing...")

    # ── Stage 4: Optimize Strategies ───────────────────────────────────────
    print("\n[Stage 4] Optimizing Strategies...")
    try:
        response = requests.get(f"{BASE_URL}/strategy-optimizer", timeout=120)
        if response.status_code == 200:
            opt_data = response.json()
            summary = opt_data.get('summary', {})
            print(f"[SUCCESS] Generated {len(opt_data.get('reports', []))} optimization reports")
            print(f"   Total strategies: {summary.get('totalStrategies', 0)}")
            print(f"   Prioritize: {summary.get('prioritizeCount', 0)}")
            print(f"   Maintain: {summary.get('maintainCount', 0)}")
            print(f"   Monitor: {summary.get('monitorCount', 0)}")
            print(f"   Best strategy: {summary.get('bestRecommendedStrategy', 'N/A')}")
            print(f"   Highest score: {summary.get('highestOptimizationScore', 0)}")
        else:
            print(f"[FAILED] Strategy optimization failed: HTTP {response.status_code}")
    except Exception as e:
        print(f"[FAILED] Strategy optimization failed: {e}")
        print("[INFO] Stage 4 is optional - continuing...")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_duration = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"LEARNING CYCLE COMPLETED - Duration: {total_duration:.2f}s")
    print("=" * 80)

    # Get mission statistics
    try:
        response = requests.get(f"{BASE_URL}/repository/statistics", timeout=30)
        if response.status_code == 200:
            stats = response.json()
            print(f"Total Missions: {stats.get('totalMissions', 0)}")
            print(f"Total Candidates: {stats.get('totalCandidates', 0)}")
            print(f"Total Validations: {stats.get('totalValidations', 0)}")
    except Exception as e:
        print(f"Could not fetch statistics: {e}")

    print("=" * 80)


if __name__ == "__main__":
    run_learning_cycle()