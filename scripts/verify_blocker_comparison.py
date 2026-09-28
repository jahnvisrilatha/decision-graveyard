"""STEP 7.5 — Verification Script: Compare Historical Blockers with Current Conditions.

Verifies:
1. Historical blockers for D001 (Employee Mobile Application).
2. Current company conditions relevant to those blockers (NovaTech 2026).
3. Identification of blockers that may still apply.
4. Identification of blockers that may have changed.
5. Evidence and reasoning for each comparison.
6. Non-rejection consultative output designed to assist a Product Manager.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.multi_proposal_detector import MultiProposalDetector


def run_verification() -> None:
    """Run Step 7.5 Blocker Comparison verification."""
    print("=" * 78)
    print("STEP 7.5: HISTORICAL BLOCKERS VS. CURRENT CONDITIONS COMPARISON")
    print("=" * 78)

    # 1. Run MultiProposalDetector for composite proposals P005A, P005B, P005C
    print("\n[STEP 1] Running MultiProposalDetector on [P005A, P005B, P005C]...")
    detector = MultiProposalDetector()
    result = detector.detect_composite_ghosts(["P005A", "P005B", "P005C"])

    assert result.is_composite_ghost_detected is True, "Composite ghost must be detected"
    assert len(result.composite_ghost_groups) > 0, "Must contain at least one composite ghost group"

    group = result.composite_ghost_groups[0]
    assert group.matched_historical_decision_id == "D001", "Must match historical decision D001"

    print(f"  * Detected Composite Ghost: {group.matched_historical_decision_id} - '{group.matched_historical_decision_title}'")
    print(f"  * Historical Status:         {group.historical_status}")
    print(f"  * Qualitative Confidence:    {result.confidence_level}")
    print(f"  * Recalled Memories:         {result.recalled_memories_count} from Hindsight")

    # 2. Display Relevant Current Company Conditions
    print("\n" + "=" * 78)
    print("RELEVANT CURRENT COMPANY CONDITIONS (NOVATECH 2026)")
    print("=" * 78)
    conds = group.current_company_conditions or result.current_conditions
    for k, v in conds.items():
        print(f"  - {k.replace('_', ' ').title()}: {v}")

    # 3. Itemized Blocker Comparisons with Evidence/Reasoning
    print("\n" + "=" * 78)
    print("ITEMIZED BLOCKER COMPARISONS (EVIDENCE & COMPARATIVE REASONING)")
    print("=" * 78)

    assert len(group.blocker_comparisons) > 0, "Expected itemized blocker_comparisons"

    still_apply_count = 0
    changed_count = 0

    for idx, item in enumerate(group.blocker_comparisons, 1):
        status_label = "[STILL APPLIES]" if item.status == "Still Applies" else "[MAY HAVE CHANGED]"
        if item.status == "Still Applies":
            still_apply_count += 1
        else:
            changed_count += 1

        print(f"\n--- Comparison #{idx} {status_label} ---")
        print(f"  1. Historical Blocker (2024):")
        print(f"     {item.historical_blocker}")
        print(f"  2. Current Condition (2026):")
        print(f"     {item.current_company_condition}")
        print(f"  3. Comparison Status:")
        print(f"     {item.status}")
        print(f"  4. Evidence & Comparative Reasoning:")
        print(f"     {item.evidence_and_reasoning}")

    # 4. Summary Lists
    print("\n" + "=" * 78)
    print("SUMMARY FOR PRODUCT MANAGER DECISION-MAKING")
    print("=" * 78)

    print("\n[BLOCKERS THAT MAY STILL APPLY (ACTIVE RISKS)]:")
    for b in group.blockers_that_still_apply:
        print(f"  * {b}")

    print("\n[BLOCKERS THAT MAY HAVE CHANGED (FAVORABLE / CLEARED)]:")
    for b in group.blockers_that_may_have_changed:
        print(f"  * {b}")

    print("\n[STRATEGIC QUESTIONS FOR PM REVIEW (HUMAN-IN-THE-LOOP)]:")
    for q in group.human_review_questions:
        print(f"  ? {q}")

    # 5. Assertions
    print("\n" + "-" * 78)
    print("RUNNING VERIFICATION ASSERTIONS...")
    print("-" * 78)

    assert len(group.historical_blockers) > 0, "Historical blockers must be identified"
    print("  [PASS] 1. Historical blockers identified for D001")

    assert len(conds) > 0, "Current company conditions must be identified"
    print("  [PASS] 2. Current company conditions relevant to those blockers identified")

    assert len(group.blockers_that_still_apply) > 0, "Blockers that still apply must be identified"
    assert still_apply_count > 0, "Itemized comparisons must include blockers that still apply"
    print(f"  [PASS] 3. Blockers that may still apply identified ({still_apply_count} comparisons)")

    assert len(group.blockers_that_may_have_changed) > 0, "Blockers that may have changed must be identified"
    assert changed_count > 0, "Itemized comparisons must include blockers that may have changed"
    print(f"  [PASS] 4. Blockers that may have changed identified ({changed_count} comparisons)")

    for c in group.blocker_comparisons:
        assert c.evidence_and_reasoning, "Every comparison must include evidence and reasoning"
    print("  [PASS] 5. Evidence and comparative reasoning provided for every comparison")

    # Check non-rejection principle
    all_text = (
        result.headline
        + " "
        + result.reasoning
        + " "
        + " ".join(result.guidance_for_product_manager)
    ).lower()
    for bad_phrase in ["reject this", "reject these", "cancel this", "do not build"]:
        assert bad_phrase not in all_text, f"Found directive phrase: {bad_phrase}"
    print("  [PASS] 6. Purely consultative output — PM remains sole decision-maker")

    print("\n[ALL STEP 7.5 ASSERTIONS PASSED SUCCESSFULLY!]")
    print("=" * 78)


if __name__ == "__main__":
    run_verification()
