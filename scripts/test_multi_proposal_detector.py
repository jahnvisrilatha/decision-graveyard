"""Test script for MultiProposalDetector with Hindsight Recall Integration (STEP 7.3).

Validates the full workflow:
P005A + P005B + P005C
        ↓
Build a combined recall query
        ↓
Hindsight Recall
        ↓
Relevant historical memories
        ↓
MultiProposalDetector
        ↓
Potential composite ghost detection

Verifies:
1. The recall query captures the combined concepts of:
   - employee mobile platform/application
   - attendance
   - leave management
   - employee notifications
   - mobile employee services
2. Hindsight Recall retrieves relevant historical memories from bank 'decision-graveyard'.
3. MultiProposalDetector uses the recalled historical memories rather than relying only on hardcoded matches.
4. Correct identification of composite ghost decision D001 (Employee Mobile Application, Abandoned).
5. Contrast against NovaTech 2026 facts (blockers that still apply vs. changed).
6. Human review questions provided for the Product Manager.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.data_loader import (
    get_decision_by_id,
    get_proposal_by_id,
    load_company_context,
)
from agent.hindsight_memory import HindsightMemory
from agent.multi_proposal_detector import MultiProposalDetector


def run_test() -> None:
    """Run Step 7.3 validation of MultiProposalDetector with Hindsight Recall."""
    print("=" * 72)
    print("STEP 7.3: HINDSIGHT RECALL + MULTI-PROPOSAL GHOST DETECTION TEST")
    print("=" * 72)

    # 1. Load P005A, P005B, and P005C from data/current_proposals.json
    print("\n[STEP 1] Loading Proposals P005A, P005B, and P005C...")
    try:
        parent_proposal = get_proposal_by_id("P005")
        components = {c.component_id.upper(): c for c in (parent_proposal.components or [])}

        target_ids = ["P005A", "P005B", "P005C"]
        loaded_components = []
        for cid in target_ids:
            if cid in components:
                c = components[cid]
                loaded_components.append(c)
                print(f"  [FOUND] {c.component_id}: '{c.title}'")
                print(f"          Description: {c.description}")
            else:
                raise ValueError(f"Component '{cid}' not found in proposal P005.")

    except Exception as e:
        print(f"[ERROR] Failed to load proposals P005A, P005B, P005C: {e}")
        sys.exit(1)

    # 2. Build combined recall query capturing the required concepts
    print("\n[STEP 2] Formulating Combined Recall Query...")
    detector = MultiProposalDetector()
    recall_query = detector.build_composite_recall_query(target_ids)
    print("  [GENERATED QUERY]:")
    for line in recall_query.splitlines():
        print(f"    {line}")

    # Verify that the 5 required concepts are captured
    key_concepts = [
        "employee mobile platform/application",
        "attendance",
        "leave management",
        "employee notifications",
        "mobile employee services",
    ]
    print("\n  [VERIFYING REQUIRED CONCEPTS IN QUERY]:")
    for concept in key_concepts:
        assert concept in recall_query, f"Concept '{concept}' is missing from recall query."
        print(f"    [OK] Captured: '{concept}'")

    # 3. Call Hindsight Recall
    print("\n[STEP 3] Calling Hindsight Recall on 'decision-graveyard' Bank...")
    hindsight = HindsightMemory()
    print(f"  Target Bank:     {hindsight.bank_id}")
    print(f"  Hindsight URL:   {hindsight.base_url}")
    try:
        recalled_memories = hindsight.recall_memories(
            query=recall_query,
            max_tokens=3500,
        )
        print(f"  [SUCCESS] Recalled {len(recalled_memories)} historical memories from Hindsight")
    except Exception as e:
        print(f"[ERROR] Hindsight recall failed: {e}")
        sys.exit(1)

    # Inspect evidence extracted from recalled memories
    print("\n[STEP 4] Analyzing Historical Evidence in Recalled Memories...")
    evidence = detector._extract_evidence_from_memories(recalled_memories)
    print(f"  Distinct historical decisions identified in memory: {list(evidence.keys())}")
    for did in ("D001", "D006"):
        if did in evidence:
            dev = evidence[did]
            print(f"  - Decision {did}: '{dev['title']}' (Status: {dev['status']}) [{len(dev['snippets'])} memory snippets]")

    # 4. Pass proposals and recalled memories to MultiProposalDetector
    print("\n[STEP 5] Passing Recalled Memories to MultiProposalDetector...")
    try:
        result = detector.detect_composite_ghosts(
            proposals=target_ids,
            recalled_memories=recalled_memories,
        )
    except Exception as e:
        print(f"[ERROR] MultiProposalDetector encountered an unhandled exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # 5. Print the detector's structured result
    print("\n" + "=" * 72)
    print("DETECTOR STRUCTURED RESULT")
    print("=" * 72)

    print(f"\n* Composite Ghost Detected: {result.is_composite_ghost_detected}")
    print(f"* Headline:                 {result.headline}")
    print(f"* Confidence Level:         {result.confidence_level} (Qualitative assessment; no fake percentages)")
    print(f"* Recalled Memories Count:  {result.recalled_memories_count} (Retrieved via Hindsight Recall)")

    if not result.composite_ghost_groups:
        print("\n[WARNING] No composite ghost groups were identified.")
        sys.exit(1)

    for idx, group in enumerate(result.composite_ghost_groups, 1):
        print("\n" + "-" * 72)
        print(f"COMPOSITE GHOST GROUP #{idx}")
        print("-" * 72)

        print("\n1. Proposals Involved:")
        for pid, title in zip(group.grouped_proposal_ids, group.grouped_proposal_titles):
            print(f"   - [{pid}] {title}")

        print("\n2. Historical Decision Matched:")
        print(f"   - Decision ID: {group.matched_historical_decision_id}")
        print(f"   - Title:       {group.matched_historical_decision_title}")
        print(f"   - Status:      {group.historical_status}")

        print("\n3. Why Proposals Collectively Resemble the Historical Decision:")
        print(f"   {group.composite_relationship_explanation}")

        print("\n4. Historical Blockers / Failure Reasons (from Hindsight Memory):")
        for b in group.historical_blockers:
            print(f"   - {b}")

        print("\n5. Blockers That May Still Apply (Active Risks):")
        for b in group.blockers_that_still_apply:
            print(f"   - {b}")

        print("\n6. Blockers That May Have Changed (Cleared / Favorable):")
        for b in group.blockers_that_may_have_changed:
            print(f"   - {b}")

        print("\n7. Questions for Human Review (Product Manager Guidance):")
        for q in group.human_review_questions:
            print(f"   - {q}")

    print("\n" + "=" * 72)
    print("CONCEPTUAL FLOW VERIFICATION")
    print("=" * 72)
    first_group = result.composite_ghost_groups[0]
    proposals_repr = " + ".join(first_group.grouped_proposal_ids)
    print(f"\n    {proposals_repr}")
    print("            |")
    print("            v (Hindsight Recall Query: 5 Core Concepts)")
    print(f"    Recalled Memories: {result.recalled_memories_count} from 'decision-graveyard'")
    print("            |")
    print("            v")
    print(f"    Potential Composite Ghost Decision (Confidence: {result.confidence_level})")
    print("            |")
    print("            v")
    print(f"    {first_group.matched_historical_decision_id} - {first_group.matched_historical_decision_title} (Status: {first_group.historical_status})")

    # 6. Programmatic Assertions
    print("\n" + "-" * 72)
    print("RUNNING VERIFICATION ASSERTIONS...")
    print("-" * 72)

    assert result.is_composite_ghost_detected is True, (
        f"Expected is_composite_ghost_detected=True, got {result.is_composite_ghost_detected}"
    )
    print("  [PASS] is_composite_ghost_detected == True")

    assert result.confidence_level in {"High", "Medium", "Low"}, (
        f"Expected qualitative confidence level, got {result.confidence_level}"
    )
    print(f"  [PASS] confidence_level is qualitative ('{result.confidence_level}')")

    assert result.recalled_memories_count > 0, (
        f"Expected recalled_memories_count > 0, got {result.recalled_memories_count}"
    )
    print(f"  [PASS] recalled_memories_count > 0 ({result.recalled_memories_count} memories used)")

    matched_ids = [g.matched_historical_decision_id for g in result.composite_ghost_groups]
    assert "D001" in matched_ids, (
        f"Expected historical decision D001 to be matched, got {matched_ids}"
    )
    print("  [PASS] Matched historical decision includes D001")

    all_grouped_ids = [pid for g in result.composite_ghost_groups for pid in g.grouped_proposal_ids]
    for expected_id in ("P005A", "P005B", "P005C"):
        assert expected_id in all_grouped_ids, (
            f"Expected {expected_id} in grouped proposals, got {all_grouped_ids}"
        )
    print("  [PASS] All expected proposals (P005A, P005B, P005C) are grouped together")

    assert len(first_group.blockers_that_still_apply) > 0, "Expected active blockers"
    print("  [PASS] Blockers that still apply are identified")

    assert len(first_group.blockers_that_may_have_changed) > 0, "Expected changed blockers"
    print("  [PASS] Blockers that have changed are identified")

    assert len(first_group.human_review_questions) > 0, "Expected human review questions"
    print("  [PASS] Human review questions are provided for Product Manager")

    print("\n[ALL STEP 7.3 ASSERTIONS PASSED SUCCESSFULLY!]")


if __name__ == "__main__":
    run_test()
