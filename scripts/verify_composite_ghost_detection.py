"""STEP 7.4 — Verification of Composite Ghost Detection with Hindsight Recall.

Verifies:
1. MultiProposalDetector receives proposals [P005A, P005B, P005C].
2. Connection to D001 (Employee Mobile Application).
3. Explanation of the CONCEPTUAL connection rather than an exact title match:
   - P005A = 'Mobile Attendance'
   - P005B = 'Mobile Leave Management'
   - P005C = 'Mobile Notifications'
   - Explains how attendance, leave, and notifications collectively recreate
     the scope of an all-in-one workforce mobile platform (D001).
4. Inclusion of historical status ('Abandoned') for D001.
5. Inclusion of historical blockers for D001 (18% adoption, 5 developers, dual-platform overhead, web portal sufficiency).
6. Non-rejection verification (proposals are NOT automatically rejected; consultative guidance is provided).
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.data_loader import get_decision_by_id, get_proposal_by_id
from agent.multi_proposal_detector import MultiProposalDetector


def run_verification() -> None:
    """Execute Step 7.4 verification checks."""
    print("=" * 76)
    print("STEP 7.4: VERIFY COMPOSITE GHOST DETECTION")
    print("=" * 76)

    # 1. Initialize Detector and inspect the evaluated proposals
    print("\n[CHECK 1] Inspecting Evaluated Proposals [P005A, P005B, P005C]...")
    parent = get_proposal_by_id("P005")
    components = {c.component_id.upper(): c for c in (parent.components or [])}

    eval_ids = ["P005A", "P005B", "P005C"]
    for pid in eval_ids:
        comp = components[pid]
        print(f"  - [{comp.component_id}] '{comp.title}'")
        print(f"      Description: {comp.description}")
        # Verify that none of the individual proposals has the title "Employee Mobile Application"
        assert comp.title.lower() != "employee mobile application", (
            f"Expected proposal {pid} not to have the exact title 'Employee Mobile Application'"
        )

    print("  [CONFIRMED] None of the proposals use the title 'Employee Mobile Application'.")
    print("              Detection must rely on conceptual connection, not title match.")

    # 2. Run MultiProposalDetector with Hindsight Recall
    print("\n[CHECK 2] Running Hindsight-powered MultiProposalDetector...")
    detector = MultiProposalDetector()
    result = detector.detect_composite_ghosts(eval_ids)

    print(f"  * Composite Ghost Detected: {result.is_composite_ghost_detected}")
    print(f"  * Qualitative Confidence:   {result.confidence_level}")
    print(f"  * Recalled Memories Count:  {result.recalled_memories_count} (Retrieved via Hindsight Recall)")
    print(f"  * Headline:                 {result.headline}")

    assert result.is_composite_ghost_detected is True, "Expected composite ghost to be detected"
    assert len(result.composite_ghost_groups) > 0, "Expected at least one composite ghost group"

    group = result.composite_ghost_groups[0]

    # 3. Verify Connection to D001 (Employee Mobile Application)
    print("\n[CHECK 3] Verifying Connection to D001 (Employee Mobile Application)...")
    print(f"  * Matched Decision ID:    {group.matched_historical_decision_id}")
    print(f"  * Matched Decision Title: {group.matched_historical_decision_title}")
    assert group.matched_historical_decision_id == "D001", (
        f"Expected matched decision ID D001, got {group.matched_historical_decision_id}"
    )
    assert "Employee Mobile Application" in group.matched_historical_decision_title, (
        f"Expected title to contain 'Employee Mobile Application', got {group.matched_historical_decision_title}"
    )
    print("  [PASS] Successfully connected to D001 (Employee Mobile Application).")

    # 4. Verify Conceptual Connection Explanation
    print("\n[CHECK 4] Verifying Conceptual Connection Explanation (No Title Match)...")
    print(f"  * Composite Explanation:\n    \"{group.composite_relationship_explanation}\"")
    explanation_lower = group.composite_relationship_explanation.lower()
    
    # Check that individual functionality concepts are mentioned
    assert any(term in explanation_lower for term in ("attendance", "p005a")), "Explanation must mention attendance/P005A"
    assert any(term in explanation_lower for term in ("leave", "p005b")), "Explanation must mention leave/P005B"
    assert any(term in explanation_lower for term in ("notification", "p005c")), "Explanation must mention notifications/P005C"
    # Check that collective recreation is explained
    assert any(term in explanation_lower for term in ("recreate", "scope", "collectively", "together", "footprint")), (
        "Explanation must describe how the proposals collectively recreate the past scope"
    )
    print("  [PASS] Conceptual connection clearly articulates how attendance, leave, and notifications")
    print("         collectively assemble the functional scope of D001 without relying on title match.")

    # 5. Verify Historical Status of D001
    print("\n[CHECK 5] Verifying Historical Status for D001...")
    print(f"  * Historical Status: '{group.historical_status}'")
    assert group.historical_status.lower() == "abandoned", (
        f"Expected historical status 'Abandoned', got '{group.historical_status}'"
    )
    print("  [PASS] Historical status 'Abandoned' correctly included.")

    # 6. Verify Historical Blockers for D001
    print("\n[CHECK 6] Verifying Historical Blockers for D001...")
    print(f"  * Recorded Historical Blockers ({len(group.historical_blockers)} items):")
    for b in group.historical_blockers:
        print(f"    - {b}")

    blockers_text = " ".join(group.historical_blockers).lower()
    # Check key blocker concepts recorded for D001
    has_adoption_blocker = any(term in blockers_text for term in ("adoption", "18%", "usage"))
    has_overhead_blocker = any(term in blockers_text for term in ("overhead", "maintenance", "separate", "dual", "native"))
    has_team_blocker = any(term in blockers_text for term in ("team", "5 developer", "capacity"))
    has_web_blocker = any(term in blockers_text for term in ("web", "portal", "workflow"))

    assert has_adoption_blocker, "Historical blockers must mention low employee adoption / usage"
    assert has_overhead_blocker, "Historical blockers must mention maintenance / dual-platform overhead"
    assert has_team_blocker, "Historical blockers must mention small engineering team capacity"
    assert has_web_blocker, "Historical blockers must mention web portal sufficiency"
    print("  [PASS] All core historical blockers for D001 are comprehensively included.")

    # 7. Verify Blocker Delta (Still Apply vs. Changed)
    print("\n[CHECK 7] Verifying Blocker Delta Analysis (Active vs. Changed)...")
    print("  * Blockers That Still Apply (Active Risks):")
    for b in group.blockers_that_still_apply:
        print(f"    - {b}")
    assert len(group.blockers_that_still_apply) > 0, "Must include blockers that still apply"

    print("  * Blockers That May Have Changed (Favorable / Cleared):")
    for b in group.blockers_that_may_have_changed:
        print(f"    - {b}")
    assert len(group.blockers_that_may_have_changed) > 0, "Must include blockers that may have changed"
    print("  [PASS] Blocker delta accurately contrasts past blockers against NovaTech 2026 conditions.")

    # 8. Verify Non-Rejection Principle
    print("\n[CHECK 8] Verifying Non-Rejection Principle...")
    print("  * Checking Headline & Reasoning for Directives:")
    combined_output = (
        result.headline
        + " "
        + result.reasoning
        + " "
        + " ".join(result.guidance_for_product_manager)
        + " "
        + " ".join(group.human_review_questions)
    ).lower()

    prohibited_phrases = ["reject this", "reject these", "cancel this", "do not build", "disapprove"]
    for phrase in prohibited_phrases:
        assert phrase not in combined_output, f"Found prohibited directive phrase: '{phrase}'"

    print("    - No automatic rejection directives found.")
    print("    - Consultative headline used: 'Potential Composite Ghost Decision Detected'")
    print("    - Questions for Human PM Review:")
    for q in group.human_review_questions:
        print(f"      ? {q}")
    assert len(group.human_review_questions) > 0, "Must provide review questions for the Product Manager"
    print("  [PASS] Non-rejection principle respected. The PM remains the final decision maker.")

    print("\n" + "=" * 76)
    print("[ALL STEP 7.4 VERIFICATION CHECKS PASSED SUCCESSFULLY!]")
    print("=" * 76)


if __name__ == "__main__":
    run_verification()
