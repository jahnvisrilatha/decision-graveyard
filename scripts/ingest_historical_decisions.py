"""Script to ingest historical organizational decisions into Hindsight memory.

Step 5.4:
Loads decisions from data/historical_decisions.json via data_loader.py,
formats rich natural-language memories, and idempotently retains each decision
into the target Hindsight memory bank.

Usage:
    python scripts/ingest_historical_decisions.py
"""

import os
import sys
from dotenv import load_dotenv

# Ensure stdout handles UTF-8 safely on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load environment configuration (.env)
load_dotenv()

from agent.hindsight_memory import ingest_historical_decisions


def main():
    print("=" * 70)
    print("Decision Graveyard - Historical Decisions Ingestion (Step 5.4)")
    print("=" * 70)

    summary = ingest_historical_decisions(verbose=True)

    if summary.get("failed_count", 0) > 0:
        print("\n[WARNING] Ingestion finished with errors.")
        sys.exit(1)
    else:
        print("\n[SUCCESS] All historical decisions successfully ingested into Hindsight!")
        sys.exit(0)


if __name__ == "__main__":
    main()
