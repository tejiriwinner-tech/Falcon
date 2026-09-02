"""
Falcon Automated Learning Scheduler

This script runs the learning cycle automatically at regular intervals
to build historical data and enable continuous learning.

Usage:
    python automated_learning_scheduler.py

The scheduler will:
- Run learning cycles every 15 minutes during trading hours
- Build historical dataset for learning engine
- Generate real-time insights and optimization
- Stop during weekends (optional)
"""
import asyncio
import time
import sys
import os
from datetime import datetime, timezone, timedelta
import threading
import signal


class LearningScheduler:
    """Automated scheduler for Falcon learning cycles."""

    def __init__(self, interval_minutes=15):
        self.interval_minutes = interval_minutes
        self.running = False
        self.thread = None

    def run_cycle(self):
        """Execute a single learning cycle."""
        try:
            import subprocess
            script_path = os.path.join(os.path.dirname(__file__), "run_learning_cycle.py")
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            print(result.stdout)
            if result.stderr:
                print(f"STDERR: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("Learning cycle timed out")
        except Exception as e:
            print(f"Learning cycle failed: {e}")

    def scheduler_loop(self):
        """Main scheduler loop."""
        print(f"Learning Scheduler started (interval: {self.interval_minutes} minutes)")
        print("Press Ctrl+C to stop")

        while self.running:
            try:
                # Check if we should run (trading hours check optional)
                now = datetime.now(timezone.utc)
                hour = now.hour
                day = now.weekday()

                # Skip weekends (Saturday=5, Sunday=6)
                if day >= 5:
                    print(f"Weekend detected, skipping cycle...")
                    time.sleep(self.interval_minutes * 60)
                    continue

                # Run learning cycle
                print(f"\n{now.isoformat()} - Starting learning cycle...")
                self.run_cycle()

                # Wait for next interval
                print(f"Next cycle in {self.interval_minutes} minutes...")
                time.sleep(self.interval_minutes * 60)

            except KeyboardInterrupt:
                print("\nScheduler stopped by user")
                break
            except Exception as e:
                print(f"Scheduler error: {e}")
                time.sleep(60)  # Wait 1 minute before retry

    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self.scheduler_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)


def main():
    """Main entry point."""
    scheduler = LearningScheduler(interval_minutes=15)

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\nStopping scheduler...")
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Start scheduler
    scheduler.start()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()


if __name__ == "__main__":
    main()