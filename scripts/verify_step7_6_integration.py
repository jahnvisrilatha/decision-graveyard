"""STEP 7.6 — Verification Script: MultiProposalDetector Integration Into DecisionAgent.

Verifies:
1. Workflow:
   Current proposals -> Hindsight Recall -> Single Proposal GhostDetector -> MultiProposalDetector -> LLM reasoning -> Decision Intelligence Report.
2. Single-proposal detection is preserved and not broken (e.g., P001).
3. Composite/multi-proposal ghost detection works for composite proposals (e.g., P005 with components P005A, P005B, P005C).
4. Decision Intelligence Report contains all required fields:
   - Historical memories recalled by Hindsight
   - Single-proposal ghost detection status & confidence
   - Composite/multi-proposal ghost detection status & confidence
   - Historical decision involved (e.g. D001)
   - Explanation of the relationship (both single and composite)
   - Historical blockers
   - Current conditions
   - Blockers still applicable
   - Blockers that may have changed
   - Itemized blocker comparisons with evidence and reasoning
   - Human review questions for the Product Manager
5. Non-directive, purely consultative guidance: no automatic rejection or approval.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.decision_agent import DecisionAgent


def test_single_proposal_evaluation(agent: DecisionAgent) -> None:
    """Verify single-proposal evaluation on P001 (Unified Employee Mobile Platform)."""
    print("\n" + "=" * 78)
    print("TEST 1: SINGLE PROPOSAL EVALUATION (P001)")
    print("=" * 78)

    report = agent.analyze_proposal("P001")

    print(f"Proposal ID:           {report.proposal_id}")
    print(f"Proposal Title:        {report.proposal_title}")
    print(f"Recalled Memories:     {len(report.recalled_historical_memories)} retrieved from Hindsight")
    print(f"Single Ghost Detected: {report.is_potential_ghost} (Confidence: {report.ghost_confidence_level})")
    print(f"Composite Detected:    {report.is_composite_ghost} (Confidence: {report.composite_ghost_confidence_level})")
    print(f"Historical Matches:    {report.historical_matches}")
    print(f"Historical Status:     {report.historical_status}")
    print(f"Relationship:          {report.relationship_explanation[:120]}...")
    print(f"Blockers Still Apply:  {len(report.blockers_that_may_still_apply)}")
    print(f"Blockers Changed:      {len(report.blockers_that_may_have_changed)}")
    print(f"PM Questions:          {len(report.questions_for_product_manager)}")

    # Assertions for Single Proposal
    assert report.proposal_id == "P001", "Proposal ID must be P001"
    assert report.is_potential_ghost is True, "P001 should be detected as a single potential ghost (matches D001)"
    assert report.ghost_confidence_level in {"High", "Medium", "Low"}, "Confidence must be qualitative"
    assert any("D001" in m for m in report.historical_matches), "Must match historical decision D001"
    assert len(report.recalled_historical_memories) > 0, "Must recall memories from Hindsight"
    assert len(report.historical_blockers) > 0, "Historical blockers must be populated"
    assert len(report.questions_for_product_manager) > 0, "Questions for PM must be populated"
    assert "approve this proposal" not in report.analysis.lower(), "Must NOT give approval directive"
    assert "reject this proposal" not in report.analysis.lower(), "Must NOT give rejection directive"

    print(">>> TEST 1 PASSED: Single proposal detection preserved perfectly!")


def test_composite_proposal_evaluation(agent: DecisionAgent) -> None:
    """Verify composite/multi-proposal evaluation on P005 (Employee Mobile Feature Expansion)."""
    print("\n" + "=" * 78)
    print("TEST 2: COMPOSITE / MULTI-PROPOSAL EVALUATION (P005 / COMPONENTS)")
    print("=" * 78)

    report = agent.analyze_proposal("P005")

    print(f"Proposal ID:              {report.proposal_id}")
    print(f"Proposal Title:           {report.proposal_title}")
    print(f"Recalled Memories:        {len(report.recalled_historical_memories)} retrieved from Hindsight")
    print(f"Composite Ghost Detected: {report.is_composite_ghost} (Confidence: {report.composite_ghost_confidence_level})")
    print(f"Historical Matches:       {report.historical_matches}")
    print(f"Composite Relationship:   {report.composite_relationship_explanation}")
    print(f"Itemized Comparisons:     {len(report.blocker_comparisons)}")
    print(f"Blockers Still Apply:     {len(report.blockers_that_may_still_apply)}")
    print(f"Blockers Changed:         {len(report.blockers_that_may_have_changed)}")
    print(f"PM Questions:             {len(report.questions_for_product_manager)}")

    # Assertions for Composite Proposal
    assert report.proposal_id == "P005", "Proposal ID must be P005"
    assert report.is_composite_ghost is True, "Composite ghost MUST be detected for P005 (P005A, P005B, P005C)"
    assert report.composite_ghost_confidence_level == "High", "Confidence level for D001 composite recreation must be 'High'"
    assert any("D001" in m for m in report.historical_matches), "Historical matches must include D001"
    assert report.composite_relationship_explanation is not None, "Composite relationship explanation must be present"
    assert len(report.blocker_comparisons) > 0, "Itemized blocker comparisons must be present"
    assert len(report.blockers_that_may_still_apply) > 0, "Blockers that still apply must be populated"
    assert len(report.blockers_that_may_have_changed) > 0, "Blockers that may have changed must be populated"
    assert len(report.questions_for_product_manager) > 0, "PM questions must be populated"
    assert "approve this proposal" not in report.analysis.lower(), "Must NOT give approval directive"
    assert "reject this proposal" not in report.analysis.lower(), "Must NOT give rejection directive"

    # Display sample itemized blocker comparison
    print("\n[Sample Itemized Blocker Comparison]:")
    sample = report.blocker_comparisons[0]
    print(f"  Historical Blocker: {sample.historical_blocker}")
    print(f"  Current Condition:  {sample.current_company_condition}")
    print(f"  Status:             {sample.status}")
    print(f"  Evidence/Reasoning: {sample.evidence_and_reasoning}")

    print("\n>>> TEST 2 PASSED: Composite ghost detection integrated seamlessly into DecisionAgent!")


def test_multi_proposal_list_evaluation(agent: DecisionAgent) -> None:
    """Verify evaluating an explicit list of proposals ['P005A', 'P005B', 'P005C']."""
    print("\n" + "=" * 78)
    print("TEST 3: MULTI-PROPOSAL LIST EVALUATION (['P005A', 'P005B', 'P005C'])")
    print("=" * 78)

    report = agent.analyze_proposals(["P005A", "P005B", "P005C"])

    print(f"Evaluated Scope:          ['P005A', 'P005B', 'P005C']")
    print(f"Composite Ghost Detected: {report.is_composite_ghost} (Confidence: {report.composite_ghost_confidence_level})")
    print(f"Historical Matches:       {report.historical_matches}")
    print(f"Composite Explanation:    {report.composite_relationship_explanation}")
    print(f"Blocker Comparisons:      {len(report.blocker_comparisons)}")

    assert report.is_composite_ghost is True, "Composite ghost must be detected for explicit component list"
    assert report.composite_ghost_confidence_level == "High", "Confidence must be High"
    assert any("D001" in m for m in report.historical_matches), "Matches must include D001"
    assert len(report.blocker_comparisons) > 0, "Must contain itemized blocker comparisons"

    print(">>> TEST 3 PASSED: Direct multi-proposal list evaluation works perfectly!")


def main() -> None:
    """Run all verification tests."""
    print("=" * 78)
    print("STEP 7.6 VERIFICATION: MULTIPROPOSALDETECTOR INTEGRATION INTO DECISIONAGENT")
    print("=" * 78)

    agent = DecisionAgent()

    test_single_proposal_evaluation(agent)
    test_composite_proposal_evaluation(agent)
    test_multi_proposal_list_evaluation(agent)

    print("\n" + "=" * 78)
    print("ALL STEP 7.6 VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 78)


if __name__ == "__main__":
    main()
