"""STEP 7.8 — Test Composite Ghost False Positives.

Tests MultiProposalDetector with:
1. A detected composite ghost combination that DOES recreate D001 (P005A + P005B + P005C).
2. Non-ghost combinations that should NOT recreate D001 or any abandoned decision:
   - P002 (Microservices Architecture) + P003 (Regional Customer Data Center Expansion)
   - P002 (Microservices Architecture) + P004 (Tiered Subscription Pricing)

Verifies:
- Detector does NOT flag every group of proposals as a composite ghost.
- Detector requires meaningful conceptual evidence before flagging a historical decision.
- Qualitative confidence ('High', 'Medium', 'Low', 'None') without fake numeric similarity scores.
- Prints clear comparative reasoning for both detected composite ghost and non-ghost combinations.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.multi_proposal_detector import MultiProposalDetector


def run_false_positive_tests() -> None:
    """Run composite ghost false positive tests."""
    print("=" * 78)
    print("STEP 7.8: COMPOSITE GHOST FALSE POSITIVES & CONCEPTUAL EVIDENCE TEST")
    print("=" * 78)

    detector = MultiProposalDetector()

    # --------------------------------------------------------------------------
    # CASE 1: Meaningful Composite Ghost (P005A + P005B + P005C -> D001)
    # --------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("TEST CASE 1: MEANINGFUL COMPOSITE GHOST COMBINATION")
    print("Proposals: P005A (Mobile Attendance) + P005B (Mobile Leave) + P005C (Mobile Notifications)")
    print("=" * 78)

    result_detected = detector.detect_composite_ghosts(["P005A", "P005B", "P005C"])

    print(f"  * Is Composite Ghost Detected: {result_detected.is_composite_ghost_detected}")
    print(f"  * Headline:                   {result_detected.headline}")
    print(f"  * Qualitative Confidence:      {result_detected.confidence_level}")
    print(f"  * Evaluated Proposals:         {result_detected.evaluated_proposal_ids}")

    if result_detected.composite_ghost_groups:
        group = result_detected.composite_ghost_groups[0]
        print(f"  * Matched Decision:            {group.matched_historical_decision_id} - '{group.matched_historical_decision_title}'")
        print(f"  * Historical Status:           {group.historical_status}")
        print(f"  * Relationship Explanation:    {group.composite_relationship_explanation}")

    print("\n[REASONING FOR DETECTED COMPOSITE GHOST]:")
    print(result_detected.reasoning)

    # Verification assertions for Case 1
    assert result_detected.is_composite_ghost_detected is True, (
        "Case 1 must be flagged as a composite ghost (meaningful conceptual evidence recreates D001)."
    )
    assert result_detected.confidence_level in {"High", "Medium"}, (
        "Case 1 confidence must be High or Medium."
    )
    assert len(result_detected.composite_ghost_groups) > 0, (
        "Case 1 must have at least one composite ghost group."
    )
    assert result_detected.composite_ghost_groups[0].matched_historical_decision_id == "D001", (
        "Case 1 must match historical decision D001."
    )

    # --------------------------------------------------------------------------
    # CASE 2: Non-Ghost Combination (P002 Microservices + P003 Data Center)
    # --------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("TEST CASE 2: NON-GHOST COMBINATION (ARCHITECTURE + INFRASTRUCTURE)")
    print("Proposals: P002 (Microservices Architecture) + P003 (Regional Data Center Expansion)")
    print("=" * 78)

    result_nonghost1 = detector.detect_composite_ghosts(["P002", "P003"])

    print(f"  * Is Composite Ghost Detected: {result_nonghost1.is_composite_ghost_detected}")
    print(f"  * Headline:                   {result_nonghost1.headline}")
    print(f"  * Qualitative Confidence:      {result_nonghost1.confidence_level}")
    print(f"  * Evaluated Proposals:         {result_nonghost1.evaluated_proposal_ids}")
    print(f"  * Composite Groups Count:      {len(result_nonghost1.composite_ghost_groups)}")

    print("\n[REASONING FOR NON-GHOST COMBINATION (P002 + P003)]:")
    print(result_nonghost1.reasoning)

    # Verification assertions for Case 2
    assert result_nonghost1.is_composite_ghost_detected is False, (
        "Case 2 must NOT be flagged as a composite ghost. P002 and P003 do not recreate D001."
    )
    assert result_nonghost1.confidence_level in {"None", "Low"}, (
        "Case 2 confidence must be None or Low."
    )
    assert len(result_nonghost1.composite_ghost_groups) == 0, (
        "Case 2 must not produce any composite ghost groups."
    )

    # --------------------------------------------------------------------------
    # CASE 3: Non-Ghost Combination (P002 Microservices + P004 Tiered Pricing)
    # --------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("TEST CASE 3: NON-GHOST COMBINATION (ENGINEERING + REVENUE STRATEGY)")
    print("Proposals: P002 (Microservices Architecture) + P004 (Tiered Subscription Pricing)")
    print("=" * 78)

    result_nonghost2 = detector.detect_composite_ghosts(["P002", "P004"])

    print(f"  * Is Composite Ghost Detected: {result_nonghost2.is_composite_ghost_detected}")
    print(f"  * Headline:                   {result_nonghost2.headline}")
    print(f"  * Qualitative Confidence:      {result_nonghost2.confidence_level}")
    print(f"  * Evaluated Proposals:         {result_nonghost2.evaluated_proposal_ids}")
    print(f"  * Composite Groups Count:      {len(result_nonghost2.composite_ghost_groups)}")

    print("\n[REASONING FOR NON-GHOST COMBINATION (P002 + P004)]:")
    print(result_nonghost2.reasoning)

    # Verification assertions for Case 3
    assert result_nonghost2.is_composite_ghost_detected is False, (
        "Case 3 must NOT be flagged as a composite ghost. P002 and P004 do not recreate D001."
    )
    assert result_nonghost2.confidence_level in {"None", "Low"}, (
        "Case 3 confidence must be None or Low."
    )
    assert len(result_nonghost2.composite_ghost_groups) == 0, (
        "Case 3 must not produce any composite ghost groups."
    )

    # --------------------------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------------------------
    print("\n" + "=" * 78)
    print("FALSE POSITIVE TEST SUMMARY & VERIFICATION CONFIRMATION")
    print("=" * 78)
    print("1. Meaningful Composite Ghost (P005A + P005B + P005C):")
    print(f"   -> Detected: {result_detected.is_composite_ghost_detected} | Matched: D001 | Confidence: {result_detected.confidence_level}")
    print("2. Unrelated Combination (P002 + P003):")
    print(f"   -> Detected: {result_nonghost1.is_composite_ghost_detected} | Confidence: {result_nonghost1.confidence_level}")
    print("3. Unrelated Combination (P002 + P004):")
    print(f"   -> Detected: {result_nonghost2.is_composite_ghost_detected} | Confidence: {result_nonghost2.confidence_level}")
    print("\nVerification Successful: The MultiProposalDetector correctly discriminates based on")
    print("concrete conceptual evidence and does NOT flag arbitrary proposal combinations as composite ghosts.")
    print("=" * 78)


if __name__ == "__main__":
    run_false_positive_tests()
