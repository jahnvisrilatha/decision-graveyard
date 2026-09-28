"""Hindsight Recall Verification Test.

Step 5 Recall Verification:
Runs the 4 key organizational intelligence queries against the
'decision-graveyard' memory bank and prints:
- Query string
- Top relevant memories returned
- Extracted decision IDs
- Memory text
"""

import os
import re
import sys
from dotenv import load_dotenv

# Ensure stdout handles UTF-8 on Windows
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

# Load configuration from .env
load_dotenv()

from agent.hindsight_memory import HindsightMemory

TEST_QUERIES = [
    "Have we previously considered building an employee mobile application?",
    "What happened with the microservices migration?",
    "What happened with the subscription pricing decision?",
    "Which previous decisions involved customer support?",
]


def extract_decision_id(item: dict) -> str:
    """Extract decision ID (e.g. D001) from document_id, metadata, tags, or text."""
    # 1. From document_id
    doc_id = item.get("document_id")
    if doc_id and re.match(r"^D\d{3}$", doc_id, re.IGNORECASE):
        return doc_id.upper()

    # 2. From metadata
    meta = item.get("metadata") or {}
    if "decision_id" in meta and meta["decision_id"]:
        return str(meta["decision_id"]).upper()

    # 3. From tags
    for tag in item.get("tags") or []:
        if tag.lower().startswith("decision-"):
            return tag.split("-")[-1].upper()
        if re.match(r"^d\d{3}$", tag, re.IGNORECASE):
            return tag.upper()

    # 4. From memory text
    text = item.get("text", "")
    match = re.search(r"Decision ID:\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    match_d = re.search(r"\b(D\d{3})\b", text)
    if match_d:
        return match_d.group(1).upper()

    return doc_id or "N/A"


def run_recall_verification():
    print("=" * 80)
    print("Decision Graveyard - Hindsight Recall Verification Test")
    print("=" * 80)

    memory = HindsightMemory()
    base_url = memory.base_url
    bank_id = memory.bank_id

    print(f"Memory Bank : '{bank_id}'")
    print(f"Server URL  : '{base_url}'\n")

    all_passed = True
    try:
        for q_idx, query in enumerate(TEST_QUERIES, 1):
            print("=" * 80)
            print(f"QUERY {q_idx}: \"{query}\"")
            print("=" * 80)

            memories = memory.recall_memories(query=query, bank_id=bank_id, max_tokens=2048)

            if not memories:
                print("[INFO] No memory units returned for this query.\n")
                all_passed = False
                continue

            print(f"Total Relevant Memories Recalled: {len(memories)}\n")

            for m_idx, mem in enumerate(memories[:5], 1):
                decision_id = extract_decision_id(mem)
                mem_type = mem.get("type") or "observation"
                text = mem.get("text", "").strip()

                print(f"  --- [Memory #{m_idx}] ---")
                print(f"  Decision ID : {decision_id}")
                print(f"  Memory Type : {mem_type}")
                if mem.get("tags"):
                    print(f"  Tags        : {', '.join(mem['tags'])}")
                print(f"  Content:\n{text}\n")
    finally:
        try:
            memory.get_client().close()
        except Exception:
            pass

    print("=" * 80)
    print("✓ Recall verification completed for all queries.")
    print("=" * 80)
    return all_passed


if __name__ == "__main__":
    success = run_recall_verification()
    sys.exit(0 if success else 1)
