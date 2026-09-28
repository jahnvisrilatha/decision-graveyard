"""STEP 7.9 — Product Manager Demonstration Script for Multi-Proposal Ghost Detection.

Demonstrates:
Clean, concise, and structured 10-point briefing for a Product Manager when a
Composite Ghost Decision is detected, suitable for executive presentations.

The 10 points:
1. Potential Composite Ghost Decision Detected
2. Current proposals involved
3. Historical decision matched
4. Why they collectively resemble it
5. Historical outcome
6. Historical blockers
7. Current company conditions
8. Blockers that may still apply
9. Blockers that may have changed
10. Human review questions

Guiding Principle:
Purely consultative analysis. Does not automatically recommend approval or rejection.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.decision_agent import DecisionAgent
from agent.multi_proposal_detector import MultiProposalDetector


def main() -> None:
    print("=" * 78)
    print("STEP 7.9: PRODUCT MANAGER BRIEFING FOR COMPOSITE GHOST DECISIONS")
    print("=" * 78)

    # 1. Evaluate composite proposals P005A, P005B, P005C using MultiProposalDetector
    print("\n[SCENARIO 1: Standalone MultiProposalDetector Evaluation]")
    detector = MultiProposalDetector()
    result = detector.detect_composite_ghosts(["P005A", "P005B", "P005C"])

    # Output the clean 10-point PM briefing
    briefing_text = result.format_pm_briefing()
    print(briefing_text)

    # Validate all 10 required items in output
    required_points = [
        "1. Potential Composite Ghost Decision Detected",
        "2. Current Proposals Involved",
        "3. Historical Decision Matched",
        "4. Why They Collectively Resemble It",
        "5. Historical Outcome",
        "6. Historical Blockers",
        "7. Current Company Conditions",
        "8. Blockers That May Still Apply",
        "9. Blockers That May Have Changed",
        "10. Human Review Questions",
    ]

    for pt in required_points:
        assert pt in briefing_text, f"Missing required briefing section: '{pt}'"

    # Validate consultative tone
    lowered = briefing_text.lower()
    assert "approve this proposal" not in lowered, "Must not contain approval directive"
    assert "reject this proposal" not in lowered, "Must not contain rejection directive"

    print("\n>>> Scenario 1 Validation Successful: All 10 PM points formatted cleanly.")

    # 2. Evaluate composite proposal P005 using DecisionAgent
    print("\n" + "=" * 78)
    print("[SCENARIO 2: DecisionAgent Full-Pipeline PM Briefing (Proposal P005)]")
    print("=" * 78)
    agent = DecisionAgent()
    report = agent.analyze_proposal("P005")

    agent_briefing = report.format_pm_briefing()
    print(agent_briefing)

    for pt in required_points:
        assert pt in agent_briefing, f"Missing required briefing section in agent report: '{pt}'"

    print("\n>>> Scenario 2 Validation Successful: DecisionAgent generates 10-point PM briefing.")

    print("\n" + "=" * 78)
    print("ALL STEP 7.9 OUTPUT VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 78)


if __name__ == "__main__":
    main()
