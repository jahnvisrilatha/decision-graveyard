"""Pydantic data models for Decision Graveyard.

Based directly on the actual structure of:
- data/current_proposals.json
- data/historical_decisions.json
- data/company_context.json
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# 1. Proposal Input Models (based on data/current_proposals.json)
# ---------------------------------------------------------------------------

class ProposalComponent(BaseModel):
    """Sub-component of a multi-part proposal (e.g., P005)."""
    component_id: str
    title: str
    description: str


class Proposal(BaseModel):
    """A current product or feature proposal submitted for evaluation."""
    proposal_id: str
    date: str
    title: str
    category: str
    proposed_by: str
    business_problem: str
    proposal: str
    objectives: List[str] = Field(default_factory=list)
    current_context: Dict[str, Any] = Field(default_factory=dict)
    alternatives_considered: List[str] = Field(default_factory=list)
    expected_outcome: str
    components: Optional[List[ProposalComponent]] = None


# Alias for explicit semantic naming
ProposalInput = Proposal


class CurrentProposalsContainer(BaseModel):
    """Top-level container for data/current_proposals.json."""
    company: str
    current_proposals: List[Proposal]


# ---------------------------------------------------------------------------
# 2. Historical Decision Models (based on data/historical_decisions.json)
# ---------------------------------------------------------------------------

class HistoricalDecision(BaseModel):
    """A past organizational decision record from historical memory."""
    decision_id: str
    date: str
    title: str
    category: str
    status: str  # 'Abandoned', 'Failed', 'Successful', or 'Rejected'
    business_problem: str
    context: Dict[str, Any] = Field(default_factory=dict)
    proposal: str
    alternatives_considered: List[str] = Field(default_factory=list)
    chosen_option: str
    reasoning: List[str] = Field(default_factory=list)
    expected_outcome: str
    actual_outcome: str
    constraints: List[str] = Field(default_factory=list)
    lesson_learned: str
    related_decisions: List[str] = Field(default_factory=list)

    # Status-specific driver fields present in historical_decisions.json
    failure_reasons: Optional[List[str]] = None      # for 'Abandoned' & 'Failed'
    success_factors: Optional[List[str]] = None      # for 'Successful'
    rejection_reasons: Optional[List[str]] = None    # for 'Rejected'


class HistoricalDecisionsContainer(BaseModel):
    """Top-level container for data/historical_decisions.json."""
    company: str
    historical_decisions: List[HistoricalDecision]


# ---------------------------------------------------------------------------
# Company Context Models (based on data/company_context.json)
# ---------------------------------------------------------------------------

class HistoricalChangeItem(BaseModel):
    """A historical shift metric between past conditions and today."""
    area: str
    historical_value: str
    current_value: str
    change: str


class CompanyContext(BaseModel):
    """NovaTech's current operational profile and historical trajectory."""
    company: str
    last_updated: str
    current_context: Dict[str, Any] = Field(default_factory=dict)
    historical_changes: List[HistoricalChangeItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 3. Historical Match Model
# ---------------------------------------------------------------------------

class HistoricalMatch(BaseModel):
    """A historical decision matched and compared against the current proposal."""
    decision_id: str
    title: str
    status: str  # e.g., 'Abandoned', 'Failed', 'Successful', 'Rejected'
    category: str
    similarity_reason: str = Field(
        description="Explanation of why this past decision relates to the current proposal."
    )
    actual_outcome: str = Field(
        description="The historical outcome of this decision."
    )
    outcome_drivers: List[str] = Field(
        default_factory=list,
        description="Key reasons for failure, success, rejection, or abandonment."
    )
    lesson_learned: Optional[str] = Field(
        default=None,
        description="Historical lesson learned from this initiative."
    )


# Alias for backwards compatibility
RelatedDecisionAnalysis = HistoricalMatch



# ---------------------------------------------------------------------------
# 4. Ghost Decision Detection Models (Step 6)
# ---------------------------------------------------------------------------

class GhostCandidate(BaseModel):
    """A past decision identified as a potential ghost decision."""
    decision_id: str = Field(
        description="ID of the historical decision (e.g., 'D001')."
    )
    title: str = Field(
        description="Title of the historical decision."
    )
    status: str = Field(
        description="Historical status (e.g., 'Abandoned', 'Failed', 'Successful', 'Rejected')."
    )
    category: str = Field(
        description="Domain category of the decision."
    )
    relationship_explanation: str = Field(
        description="Explanation of why this past decision is conceptually related to the current proposal."
    )
    historical_outcome: str = Field(
        description="What happened historically with this decision."
    )
    historical_blockers: List[str] = Field(
        default_factory=list,
        description="Blockers, constraints, or failure reasons encountered in the past."
    )
    lesson_learned: Optional[str] = Field(
        default=None,
        description="Organizational lesson learned from this historical initiative."
    )
    blockers_that_may_still_apply: List[str] = Field(
        default_factory=list,
        description="Historical blockers or risks that remain active in the current context."
    )
    blockers_that_may_have_changed: List[str] = Field(
        default_factory=list,
        description="Historical blockers that have changed favorably or been cleared."
    )


class GhostDetectionResult(BaseModel):
    """Structured Pydantic model evaluating whether a proposal represents a potential Ghost Decision."""

    # 1. Primary requested fields
    is_potential_ghost: bool = Field(
        description="Whether the proposal is flagged as a potential ghost decision."
    )
    confidence_level: str = Field(
        description="Qualitative assessment of relationship strength ('High', 'Medium', or 'Low')."
    )
    current_proposal_id: str = Field(
        description="Identifier of the proposal being evaluated (e.g., 'P001')."
    )
    historical_matches: List[str] = Field(
        default_factory=list,
        description="Historical decisions matched against this proposal (IDs or titles)."
    )
    relationship_explanation: str = Field(
        default="",
        description="Explanation of why this proposal relates to past decisions."
    )
    historical_status: str = Field(
        default="",
        description="Status of the related historical decision(s) (e.g., 'Abandoned', 'Failed', 'Successful')."
    )
    historical_blockers: List[str] = Field(
        default_factory=list,
        description="Historical blockers, constraints, or failure reasons encountered in the past."
    )
    current_conditions: Union[Dict[str, Any], List[str], str] = Field(
        default_factory=dict,
        description="Current organizational, technical, or market conditions."
    )
    blockers_that_still_apply: List[str] = Field(
        default_factory=list,
        description="Historical blockers, challenges, or risks that remain active in the organization today."
    )
    blockers_that_may_have_changed: List[str] = Field(
        default_factory=list,
        description="Historical blockers or conditions that have changed favorably or been cleared."
    )
    reasoning: str = Field(
        default="",
        description="Detailed analytical synthesis explaining the ghost decision determination."
    )
    human_review_questions: List[str] = Field(
        default_factory=list,
        description="Strategic questions and guidance for human Product Managers to investigate before deciding."
    )

    # 2. Metadata & backward-compatible fields
    proposal_title: Optional[str] = Field(
        default=None,
        description="Title of the evaluated proposal."
    )
    headline: Optional[str] = Field(
        default=None,
        description="Summary headline e.g., 'Potential Ghost Decision Detected'."
    )
    ghost_candidates: List[GhostCandidate] = Field(
        default_factory=list,
        description="Detailed list of candidate past decisions if available."
    )
    recalled_memories_count: int = Field(
        default=0,
        description="Number of memories retrieved from Hindsight during evaluation."
    )
    detected_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    @field_validator("confidence_level", mode="before")
    @classmethod
    def validate_confidence_level(cls, v: Any) -> str:
        """Enforce qualitative confidence level as 'High', 'Medium', or 'Low' without numeric scores."""
        if isinstance(v, str):
            clean = v.strip().title()
            if clean in {"High", "Medium", "Low"}:
                return clean
            if clean in {"None", "Zero", "N/A"}:
                return "Low"
        return "Low"

    @model_validator(mode="before")
    @classmethod
    def map_legacy_fields(cls, values: Any) -> Any:
        """Map legacy attribute names and derive convenience fields."""
        if isinstance(values, dict):
            # is_potential_ghost <- ghost_detected
            if "is_potential_ghost" not in values and "ghost_detected" in values:
                values["is_potential_ghost"] = bool(values["ghost_detected"])
            # confidence_level <- confidence
            if "confidence_level" not in values and "confidence" in values:
                values["confidence_level"] = values["confidence"]
            # current_proposal_id <- proposal_id
            if "current_proposal_id" not in values and "proposal_id" in values:
                values["current_proposal_id"] = str(values["proposal_id"])
            # current_conditions <- current_context_summary
            if "current_conditions" not in values and "current_context_summary" in values:
                values["current_conditions"] = values["current_context_summary"]
            # human_review_questions <- guidance_for_product_manager
            if "human_review_questions" not in values and "guidance_for_product_manager" in values:
                values["human_review_questions"] = values["guidance_for_product_manager"]

            # Derive fields from ghost_candidates if provided
            candidates = values.get("ghost_candidates") or []
            if candidates and isinstance(candidates, list):
                if not values.get("historical_matches"):
                    matches = []
                    for c in candidates:
                        if isinstance(c, dict):
                            matches.append(c.get("decision_id", ""))
                        elif hasattr(c, "decision_id"):
                            matches.append(getattr(c, "decision_id"))
                    values["historical_matches"] = [m for m in matches if m]

                first_c = candidates[0]
                if not values.get("relationship_explanation"):
                    if isinstance(first_c, dict):
                        values["relationship_explanation"] = first_c.get("relationship_explanation", "")
                    elif hasattr(first_c, "relationship_explanation"):
                        values["relationship_explanation"] = getattr(first_c, "relationship_explanation")

                if not values.get("historical_status"):
                    statuses = []
                    for c in candidates:
                        did = c.get("decision_id") if isinstance(c, dict) else getattr(c, "decision_id", "")
                        st = c.get("status") if isinstance(c, dict) else getattr(c, "status", "")
                        if did and st:
                            statuses.append(f"{did}: {st}")
                    values["historical_status"] = "; ".join(statuses)

                if not values.get("historical_blockers"):
                    all_b: List[str] = []
                    for c in candidates:
                        hb = c.get("historical_blockers", []) if isinstance(c, dict) else getattr(c, "historical_blockers", [])
                        for item in hb:
                            if item not in all_b:
                                all_b.append(item)
                    values["historical_blockers"] = all_b

                if not values.get("blockers_that_still_apply"):
                    still: List[str] = []
                    for c in candidates:
                        sb = c.get("blockers_that_may_still_apply", []) if isinstance(c, dict) else getattr(c, "blockers_that_may_still_apply", [])
                        for item in sb:
                            if item not in still:
                                still.append(item)
                    values["blockers_that_still_apply"] = still

                if not values.get("blockers_that_may_have_changed"):
                    chg: List[str] = []
                    for c in candidates:
                        cb = c.get("blockers_that_may_have_changed", []) if isinstance(c, dict) else getattr(c, "blockers_that_may_have_changed", [])
                        for item in cb:
                            if item not in chg:
                                chg.append(item)
                    values["blockers_that_may_have_changed"] = chg

        return values

    # Convenience properties for backwards compatibility
    @property
    def ghost_detected(self) -> bool:
        return self.is_potential_ghost

    @property
    def proposal_id(self) -> str:
        return self.current_proposal_id

    @property
    def confidence(self) -> str:
        return self.confidence_level

    @property
    def guidance_for_product_manager(self) -> List[str]:
        return self.human_review_questions

    @property
    def current_context_summary(self) -> Any:
        return self.current_conditions


# Semantic alias
GhostDetectionReport = GhostDetectionResult


# ---------------------------------------------------------------------------
# 5. Decision Intelligence Report Model (with Ghost Detection integration)
# ---------------------------------------------------------------------------

class DecisionIntelligenceReport(BaseModel):
    """Structured report evaluating a proposal against historical organizational memory."""
    proposal_id: str
    proposal_title: str

    # Related historical decisions identified
    related_historical_decisions: List[HistoricalMatch] = Field(
        default_factory=list,
        description="Historical decisions related to this proposal."
    )

    # Raw / synthesized memories recalled from Hindsight
    recalled_historical_memories: List[str] = Field(
        default_factory=list,
        description="Key historical memories retrieved from Hindsight persistent memory."
    )

    # Historical outcomes & blockers
    historical_outcomes: List[str] = Field(
        default_factory=list,
        description="Summary of historical outcomes from related past initiatives."
    )
    historical_blockers: List[str] = Field(
        default_factory=list,
        description="Constraints, bottlenecks, or failure causes encountered in the past."
    )

    # Current conditions & comparison
    current_conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key current organizational conditions relevant to this proposal."
    )
    historical_vs_current_comparison: Union[str, Dict[str, Any], List[str]] = Field(
        description="Direct contrast between past conditions and current company context."
    )

    # Blocker delta analysis
    blockers_that_may_still_apply: List[str] = Field(
        default_factory=list,
        description="Historical blockers or risks that remain active today."
    )
    blockers_that_may_have_changed: List[str] = Field(
        default_factory=list,
        description="Historical blockers that have changed favorably or been cleared."
    )

    # Synthesis & PM Guidance
    analysis: str = Field(
        description="Comprehensive analysis answering 'Have we tried something like this before?'"
    )
    questions_for_product_manager: List[str] = Field(
        default_factory=list,
        description="Strategic questions the Product Manager should answer before proceeding."
    )

    # Ghost Decision Detection Integration (Step 6)
    ghost_detection_result: Optional[GhostDetectionResult] = Field(
        default=None,
        description="Detailed Ghost Detection evaluation outcome."
    )
    is_potential_ghost: bool = Field(
        default=False,
        description="Potential Ghost Decision status: True if proposal resembles past abandoned/failed decisions."
    )
    ghost_confidence_level: Optional[str] = Field(
        default=None,
        description="Confidence level of ghost detection ('High', 'Medium', 'Low')."
    )
    relationship_explanation: Optional[str] = Field(
        default=None,
        description="Why the current proposal resembles historical decisions."
    )
    historical_status: Optional[str] = Field(
        default=None,
        description="Historical status of the matched prior decision(s) (e.g. 'Abandoned', 'Failed', 'Successful')."
    )
    historical_matches: List[str] = Field(
        default_factory=list,
        description="Historical decision IDs or titles involved."
    )

    # Composite / Multi-Proposal Ghost Detection Integration (Step 7.6)
    composite_ghost_detection_result: Optional[MultiProposalGhostDetectionResult] = Field(
        default=None,
        description="Detailed Composite / Multi-Proposal Ghost Detection evaluation outcome."
    )
    is_composite_ghost: bool = Field(
        default=False,
        description="True if proposals or components collectively recreate an abandoned/failed past decision."
    )
    composite_ghost_confidence_level: Optional[str] = Field(
        default=None,
        description="Confidence level of composite ghost detection ('High', 'Medium', 'Low', 'None')."
    )
    composite_relationship_explanation: Optional[str] = Field(
        default=None,
        description="Why the combination of proposals/components resembles a historical decision."
    )
    blocker_comparisons: List[BlockerComparisonItem] = Field(
        default_factory=list,
        description="Detailed itemized comparisons contrasting historical blockers against current conditions with evidence/reasoning."
    )

    # Optional metadata
    generated_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    # Convenience properties
    @property
    def blockers_that_still_apply(self) -> List[str]:
        return self.blockers_that_may_still_apply

    @property
    def human_review_questions(self) -> List[str]:
        return self.questions_for_product_manager

    def format_pm_briefing(self) -> str:
        """Format the report into a clean, concise 10-point briefing for a Product Manager."""
        # 1. Potential Composite Ghost Decision Detected
        is_detected_str = "YES (Potential Composite Ghost Detected)" if self.is_composite_ghost else "No Direct Composite Ghost Detected"
        conf_str = self.composite_ghost_confidence_level or "None"
        section1 = f"{is_detected_str} [Confidence: {conf_str}]"

        # 2. Current proposals involved
        if self.composite_ghost_detection_result and self.composite_ghost_detection_result.composite_ghost_groups:
            grp = self.composite_ghost_detection_result.composite_ghost_groups[0]
            props = ", ".join(grp.grouped_proposal_ids)
        elif self.composite_ghost_detection_result and self.composite_ghost_detection_result.evaluated_proposal_ids:
            props = ", ".join(self.composite_ghost_detection_result.evaluated_proposal_ids)
        else:
            props = self.proposal_id
        section2 = props

        # 3. Historical decision matched
        if self.composite_ghost_detection_result and self.composite_ghost_detection_result.composite_ghost_groups:
            grp = self.composite_ghost_detection_result.composite_ghost_groups[0]
            hist_matched = f"{grp.matched_historical_decision_id} - {grp.matched_historical_decision_title}"
        elif self.historical_matches:
            hist_matched = ", ".join(self.historical_matches)
        else:
            hist_matched = "None"
        section3 = hist_matched

        # 4. Why they collectively resemble it
        section4 = self.composite_relationship_explanation or self.relationship_explanation or "N/A"

        # 5. Historical outcome
        section5 = self.historical_status or ("Abandoned (Past initiative discontinued)" if self.is_composite_ghost else "N/A")

        # 6. Historical blockers
        if self.historical_blockers:
            section6 = "\n".join(f"   - {b}" for b in self.historical_blockers[:4])
        else:
            section6 = "   - None documented"

        # 7. Current company conditions
        cond_lines = []
        for k, v in list(self.current_conditions.items())[:5]:
            clean_k = k.replace("_", " ").title()
            cond_lines.append(f"   - {clean_k}: {v}")
        section7 = "\n".join(cond_lines) if cond_lines else "   - Operational context available"

        # 8. Blockers that may still apply
        if self.blockers_that_may_still_apply:
            section8 = "\n".join(f"   - {b}" for b in self.blockers_that_may_still_apply[:4])
        else:
            section8 = "   - None identified"

        # 9. Blockers that may have changed
        if self.blockers_that_may_have_changed:
            section9 = "\n".join(f"   - {b}" for b in self.blockers_that_may_have_changed[:4])
        else:
            section9 = "   - None identified"

        # 10. Human review questions
        if self.questions_for_product_manager:
            section10 = "\n".join(f"   ? {q}" for q in self.questions_for_product_manager[:3])
        else:
            section10 = "   ? What are the key architectural tradeoffs for this initiative?"

        return (
            f"======================================================================\n"
            f"DECISION GRAVEYARD - PRODUCT MANAGER DECISION BRIEFING\n"
            f"======================================================================\n"
            f"1. Potential Composite Ghost Decision Detected:\n"
            f"   {section1}\n\n"
            f"2. Current Proposals Involved:\n"
            f"   {section2}\n\n"
            f"3. Historical Decision Matched:\n"
            f"   {section3}\n\n"
            f"4. Why They Collectively Resemble It:\n"
            f"   {section4}\n\n"
            f"5. Historical Outcome:\n"
            f"   {section5}\n\n"
            f"6. Historical Blockers:\n"
            f"{section6}\n\n"
            f"7. Current Company Conditions:\n"
            f"{section7}\n\n"
            f"8. Blockers That May Still Apply:\n"
            f"{section8}\n\n"
            f"9. Blockers That May Have Changed:\n"
            f"{section9}\n\n"
            f"10. Human Review Questions (For PM Evaluation):\n"
            f"{section10}\n"
            f"======================================================================\n"
            f"NOTE: Consultative intelligence only. The Product Manager remains the\n"
            f"final decision-maker regarding approval, modification, or rejection."
        )


# ---------------------------------------------------------------------------
# 6. Multi-Proposal Ghost Detection Models (Step 7)
# ---------------------------------------------------------------------------

class BlockerComparisonItem(BaseModel):
    """Detailed comparison between a historical blocker and current company conditions."""
    historical_blocker: str = Field(
        description="The constraint, bottleneck, or failure cause encountered historically."
    )
    current_company_condition: str = Field(
        description="Current organizational, technical, or market condition relevant to this blocker."
    )
    status: str = Field(
        description="Whether the blocker 'Still Applies', 'May Have Changed', or is 'Partially Resolved'."
    )
    evidence_and_reasoning: str = Field(
        description="Factual evidence and comparative reasoning explaining why the blocker still applies or has changed."
    )


class CompositeGhostGroup(BaseModel):
    """A detected group of proposals that collectively recreate a past decision."""
    matched_historical_decision_id: str = Field(
        description="ID of the matched historical decision (e.g., 'D001')."
    )
    matched_historical_decision_title: str = Field(
        description="Title of the matched historical decision (e.g., 'Employee Mobile Application')."
    )
    historical_status: str = Field(
        description="Historical status (e.g., 'Abandoned', 'Failed', 'Rejected')."
    )
    grouped_proposal_ids: List[str] = Field(
        default_factory=list,
        description="IDs of proposals or components in this group (e.g., ['P005A', 'P005B', 'P005C'])."
    )
    grouped_proposal_titles: List[str] = Field(
        default_factory=list,
        description="Titles of current proposals or components in this group."
    )
    composite_relationship_explanation: str = Field(
        description="Explanation of how the individual proposals combine into the historical initiative."
    )
    historical_blockers: List[str] = Field(
        default_factory=list,
        description="Historical blockers, constraints, or reasons for the past outcome."
    )
    lesson_learned: Optional[str] = Field(
        default=None,
        description="Historical lesson learned from the initiative."
    )
    blockers_that_still_apply: List[str] = Field(
        default_factory=list,
        description="Historical blockers or risks that remain active in current company context."
    )
    blockers_that_may_have_changed: List[str] = Field(
        default_factory=list,
        description="Historical blockers that have changed favorably or been cleared."
    )
    blocker_comparisons: List[BlockerComparisonItem] = Field(
        default_factory=list,
        description="Detailed comparison contrasting each historical blocker against current conditions with evidence/reasoning."
    )
    current_company_conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Current company conditions relevant to the matched historical decision's blockers."
    )
    human_review_questions: List[str] = Field(
        default_factory=list,
        description="Probing questions for human Product Managers before proceeding."
    )


class MultiProposalGhostDetectionResult(BaseModel):
    """Structured result of multi-proposal / composite ghost decision analysis."""
    is_composite_ghost_detected: bool = Field(
        description="True if one or more groups of proposals collectively recreate a past decision."
    )
    headline: str = Field(
        description="Summary headline e.g. 'Potential Composite Ghost Decision Detected: ...'."
    )
    confidence_level: str = Field(
        description="Qualitative confidence assessment: 'High', 'Medium', 'Low', or 'None'."
    )
    composite_ghost_groups: List[CompositeGhostGroup] = Field(
        default_factory=list,
        description="List of detected composite ghost groups."
    )
    evaluated_proposal_ids: List[str] = Field(
        default_factory=list,
        description="List of all proposal or component IDs evaluated in this analysis."
    )
    current_conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Current company facts relevant to the evaluation."
    )
    reasoning: str = Field(
        description="Detailed analytical explanation of whether and why the proposals form a composite ghost."
    )
    guidance_for_product_manager: List[str] = Field(
        default_factory=list,
        description="Strategic questions and guidance for the Product Manager."
    )
    recalled_memories_count: int = Field(
        default=0,
        description="Number of memories retrieved from Hindsight during evaluation."
    )
    detected_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    @field_validator("confidence_level", mode="before")
    @classmethod
    def validate_confidence_level(cls, v: Any) -> str:
        """Enforce qualitative confidence level as 'High', 'Medium', 'Low', or 'None' without numeric scores."""
        if isinstance(v, str):
            clean = v.strip().title()
            if clean in {"High", "Medium", "Low", "None"}:
                return clean
            if clean in {"Zero", "N/A"}:
                return "None"
        return "Low"

    # Convenience alias
    @property
    def ghost_detected(self) -> bool:
        return self.is_composite_ghost_detected

    def format_pm_briefing(self) -> str:
        """Format the detection result into a clean, concise 10-point briefing for a Product Manager."""
        if not self.is_composite_ghost_detected or not self.composite_ghost_groups:
            return (
                "======================================================================\n"
                "DECISION GRAVEYARD - COMPOSITE GHOST INTELLIGENCE BRIEFING\n"
                "======================================================================\n"
                "1. Potential Composite Ghost Decision Detected:\n"
                f"   NO [Confidence: {self.confidence_level}]\n\n"
                "2. Current Proposals Involved:\n"
                f"   {', '.join(self.evaluated_proposal_ids)}\n\n"
                "3. Assessment Reasoning:\n"
                f"   {self.reasoning}\n"
                "======================================================================\n"
            )

        group = self.composite_ghost_groups[0]
        proposals_str = ", ".join(
            f"{pid} ({title})" if title and title != pid else pid
            for pid, title in zip(group.grouped_proposal_ids, group.grouped_proposal_titles)
        ) if group.grouped_proposal_titles else ", ".join(group.grouped_proposal_ids)

        section1 = f"YES [Confidence: {self.confidence_level}]"
        section2 = proposals_str
        section3 = f"{group.matched_historical_decision_id} - {group.matched_historical_decision_title}"
        section4 = group.composite_relationship_explanation
        section5 = group.historical_status or "Abandoned"

        section6 = "\n".join(f"   - {b}" for b in group.historical_blockers[:4]) if group.historical_blockers else "   - None documented"

        conds = group.current_company_conditions or self.current_conditions
        cond_lines = [f"   - {k.replace('_', ' ').title()}: {v}" for k, v in list(conds.items())[:5]]
        section7 = "\n".join(cond_lines) if cond_lines else "   - Operational context available"

        section8 = "\n".join(f"   - {b}" for b in group.blockers_that_still_apply[:4]) if group.blockers_that_still_apply else "   - None identified"
        section9 = "\n".join(f"   - {b}" for b in group.blockers_that_may_have_changed[:4]) if group.blockers_that_may_have_changed else "   - None identified"

        questions = group.human_review_questions or self.guidance_for_product_manager
        section10 = "\n".join(f"   ? {q}" for q in questions[:3]) if questions else "   ? What are the key architectural tradeoffs for this initiative?"

        return (
            f"======================================================================\n"
            f"DECISION GRAVEYARD - COMPOSITE GHOST INTELLIGENCE BRIEFING\n"
            f"======================================================================\n"
            f"1. Potential Composite Ghost Decision Detected:\n"
            f"   {section1}\n\n"
            f"2. Current Proposals Involved:\n"
            f"   {section2}\n\n"
            f"3. Historical Decision Matched:\n"
            f"   {section3}\n\n"
            f"4. Why They Collectively Resemble It:\n"
            f"   {section4}\n\n"
            f"5. Historical Outcome:\n"
            f"   {section5}\n\n"
            f"6. Historical Blockers:\n"
            f"{section6}\n\n"
            f"7. Current Company Conditions:\n"
            f"{section7}\n\n"
            f"8. Blockers That May Still Apply:\n"
            f"{section8}\n\n"
            f"9. Blockers That May Have Changed:\n"
            f"{section9}\n\n"
            f"10. Human Review Questions (For PM Evaluation):\n"
            f"{section10}\n"
            f"======================================================================\n"
            f"NOTE: Purely consultative intelligence. The Product Manager remains the\n"
            f"final decision-maker regarding approval, modification, or rejection."
        )


# Semantic alias
CompositeGhostDetectionResult = MultiProposalGhostDetectionResult

