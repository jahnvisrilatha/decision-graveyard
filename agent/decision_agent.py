"""DecisionAgent implementation for Decision Graveyard.

Workflow:
1. Receive a proposal_id.
2. Retrieve the proposal from data/current_proposals.json via data_loader.
3. Load historical decisions from data/historical_decisions.json via data_loader.
4. Load current company context from data/company_context.json via data_loader.
5. Construct a structured LLM prompt with this information.
6. Ask the LLM to analyze the proposal against historical decisions.
7. Parse the response into our Pydantic DecisionIntelligenceReport.
8. Return the structured report.

Guiding Principle:
The agent does NOT automatically accept or reject proposals. It equips the
Product Manager with historical evidence, contextual comparisons, and probing
questions so the human can make the informed decision.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

from agent.data_loader import (
    get_proposal_by_id,
    load_company_context,
    load_historical_decisions,
)
from agent.ghost_detector import GhostDetector
from agent.hindsight_memory import HindsightMemory
from agent.llm_client import LLMClient
from agent.models import (
    BlockerComparisonItem,
    CompanyContext,
    CompositeGhostGroup,
    DecisionIntelligenceReport,
    GhostDetectionResult,
    HistoricalDecision,
    HistoricalMatch,
    MultiProposalGhostDetectionResult,
    Proposal,
)
from agent.multi_proposal_detector import MultiProposalDetector

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are "Decision Graveyard", an organizational intelligence assistant helping Product Managers evaluate proposals against company historical memory.

Your mission is to answer:
"Have we tried something like this before?"

CRITICAL PRINCIPLE:
You must NEVER tell the Product Manager to accept or reject the proposal.
Do NOT use directives like "Approve this proposal", "Reject this initiative", or "This should not proceed".
Your role is purely consultative: provide historical evidence, past outcomes, contextual comparisons, active vs changed blockers, and strategic questions so the human PM can make an informed decision.

Your analysis must clearly distinguish between:
1. Historical Memory: What Hindsight recalled regarding past initiatives, constraints, failure causes, and outcomes.
2. Current Facts: What the current company context and metrics say.
3. Analysis: What you conclude from directly comparing historical memory against current facts.

Specific guidelines:
- Identify potentially related historical decisions from recalled organizational memory, including their decision IDs (e.g., D001, D002, D006) whenever available.
- Detail why those past decisions are related to this proposal.
- Detail historical status and outcomes (e.g. Abandoned, Failed, Successful, Rejected).
- Highlight historical blockers (technical, organizational, or market constraints).
- Present relevant current company conditions.
- Contrast differences between historical conditions and current company context.
- Identify which historical blockers may still apply today.
- Identify which historical blockers may have changed or been cleared.
- Formulate insightful questions for the Product Manager to consider.

You must return a valid JSON object matching this schema:
{
  "related_historical_decisions": [
    {
      "decision_id": "string",
      "title": "string",
      "status": "string",
      "category": "string",
      "similarity_reason": "string",
      "actual_outcome": "string",
      "outcome_drivers": ["string"],
      "lesson_learned": "string"
    }
  ],
  "historical_outcomes": ["string"],
  "historical_blockers": ["string"],
  "current_conditions": {
    "key": "value"
  },
  "historical_vs_current_comparison": "string",
  "blockers_that_may_still_apply": ["string"],
  "blockers_that_may_have_changed": ["string"],
  "analysis": "string",
  "questions_for_product_manager": ["string"]
}
"""


class DecisionAgent:
    """Core AI agent evaluating product proposals against historical decisions using Hindsight memory,
    single-proposal GhostDetector, and MultiProposalDetector.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        hindsight_memory: Optional[HindsightMemory] = None,
        ghost_detector: Optional[GhostDetector] = None,
        multi_proposal_detector: Optional[MultiProposalDetector] = None,
    ):
        """Initialize the agent with an LLM client, Hindsight memory, GhostDetector, and MultiProposalDetector.

        Args:
            llm_client: Optional LLMClient instance. Defaults to a new LLMClient().
            hindsight_memory: Optional HindsightMemory instance. Defaults to a new HindsightMemory().
            ghost_detector: Optional GhostDetector instance. Defaults to a new GhostDetector().
            multi_proposal_detector: Optional MultiProposalDetector instance. Defaults to a new MultiProposalDetector().
        """
        self.llm_client = llm_client or LLMClient()
        self.hindsight_memory = hindsight_memory or HindsightMemory()
        self.ghost_detector = ghost_detector or GhostDetector(
            llm_client=self.llm_client,
            hindsight_memory=self.hindsight_memory,
        )
        self.multi_proposal_detector = multi_proposal_detector or MultiProposalDetector(
            llm_client=self.llm_client,
            hindsight_memory=self.hindsight_memory,
        )

    def analyze_proposal(
        self, proposal_id: Union[str, List[str], Proposal]
    ) -> DecisionIntelligenceReport:
        """Run the full evaluation workflow for a proposal using Hindsight recall,
        single-proposal GhostDetector, and MultiProposalDetector.

        Workflow:
        1. Receive current proposal(s) and load details via data_loader.
        2. Build query and recall relevant memories from Hindsight.
        3. Pass proposal and recalled memories to single-proposal GhostDetector.
        4. Pass proposals/components and recalled memories to MultiProposalDetector.
        5. Load current company context via data_loader.
        6. Send proposal, recalled memories, company context, single ghost assessment,
           and composite ghost assessment to the LLM.
        7. Parse into structured DecisionIntelligenceReport containing both single
           and composite ghost detection results, blocker comparisons, and PM questions.
        8. Return the structured report.

        Args:
            proposal_id: Unique proposal ID (e.g. 'P001', 'P005', 'P005A'), a list
                         of proposal/component IDs (e.g. ['P005A', 'P005B', 'P005C']),
                         or a direct Proposal instance.

        Returns:
            Structured DecisionIntelligenceReport.

        Raises:
            ValueError: If proposal_id does not exist.
            FileNotFoundError: If required data files are missing.
        """
        # 1. Determine evaluated proposals and primary proposal
        if isinstance(proposal_id, Proposal):
            proposal = proposal_id
            primary_id = proposal.proposal_id
            if proposal.components:
                composite_proposals = [c.component_id for c in proposal.components]
            else:
                composite_proposals = [proposal.proposal_id]
        elif isinstance(proposal_id, list):
            if not proposal_id:
                raise ValueError("Must provide at least one proposal ID in list.")
            composite_proposals = [str(pid).strip().upper() for pid in proposal_id]
            primary_id = composite_proposals[0]
            proposal = get_proposal_by_id(primary_id)
        else:
            primary_id = proposal_id.strip().upper()
            proposal = get_proposal_by_id(primary_id)
            if proposal.components:
                composite_proposals = [c.component_id for c in proposal.components]
            else:
                composite_proposals = [proposal.proposal_id]

        logger.info(
            f"Starting Decision Graveyard analysis for proposal: {proposal.proposal_id} "
            f"(composite targets: {composite_proposals})"
        )

        # 2. Build query and recall relevant memories from Hindsight
        recall_query = self._build_recall_query(proposal, composite_proposals)
        recalled_memories = []
        try:
            recalled_memories = self.hindsight_memory.recall_memories(
                query=recall_query,
                max_tokens=3500,
            )
            logger.info(
                f"Recalled {len(recalled_memories)} memories from Hindsight bank "
                f"'{self.hindsight_memory.bank_id}' for proposal {proposal.proposal_id}"
            )
        except Exception as e:
            logger.warning(f"Hindsight recall encountered an issue: {e}")

        # 3. Pass proposal and recalled memories to single-proposal GhostDetector
        ghost_result = self.ghost_detector.detect_ghost(
            proposal=proposal,
            recalled_memories=recalled_memories,
        )
        logger.info(
            f"GhostDetector result for {proposal.proposal_id}: "
            f"is_potential_ghost={ghost_result.is_potential_ghost} "
            f"(confidence={ghost_result.confidence_level})"
        )

        # 4. Pass proposals/components and recalled memories to MultiProposalDetector
        composite_result = self.multi_proposal_detector.detect_composite_ghosts(
            proposals=composite_proposals,
            recalled_memories=recalled_memories,
        )
        logger.info(
            f"MultiProposalDetector result for {composite_proposals}: "
            f"is_composite_ghost_detected={composite_result.is_composite_ghost_detected} "
            f"(confidence={composite_result.confidence_level})"
        )

        # Fallback to local historical decisions if Hindsight is unavailable or empty
        fallback_decisions = None
        if not recalled_memories:
            logger.info("Using local historical decisions archive as fallback evidence.")
            fallback_decisions = load_historical_decisions()

        # 5. Load current company context via data_loader
        company_context = load_company_context()

        # 6. Send proposal, recalled memories, company context, ghost assessment, and composite assessment to LLM
        prompt = self._build_prompt(
            proposal=proposal,
            company_context=company_context,
            recalled_memories=recalled_memories,
            fallback_decisions=fallback_decisions,
            ghost_result=ghost_result,
            composite_result=composite_result,
        )

        raw_response = self.llm_client.generate_analysis(
            prompt=prompt, system_instruction=SYSTEM_PROMPT
        )

        # 7 & 8. Parse into structured report, including both Ghost and Composite Detection results
        memory_texts = []
        for m in recalled_memories:
            raw_t = (m.get("text") or "").strip()
            if not raw_t:
                continue
            doc_id = m.get("document_id") or ""
            meta = m.get("metadata") or {}
            tags = m.get("tags") or []

            # Extract decision ID from tags if missing in doc_id
            if not doc_id:
                for t in tags:
                    if str(t).lower().startswith("decision-d"):
                        doc_id = str(t).split("-")[-1].upper()
                        break
            if not doc_id:
                d_match = re.search(r"\b(D\d{3})\b", raw_t)
                if d_match:
                    doc_id = d_match.group(1).upper()

            title = meta.get("title") or ""
            status = meta.get("status") or ""
            if not status:
                for t in tags:
                    if str(t).lower() in ["abandoned", "failed", "successful", "rejected"]:
                        status = str(t).capitalize()
                        break

            # Map known titles/statuses if missing
            if not title and doc_id == "D001":
                title = "Employee Mobile Application"
                if not status:
                    status = "Abandoned"
            elif not title and doc_id == "D006":
                title = "Progressive Web Application"
                if not status:
                    status = "Successful"
            elif not title and doc_id == "D009":
                title = "Employee Self-Service Portal"
                if not status:
                    status = "Successful"

            header_parts = []
            if doc_id and title:
                header_parts.append(f"{doc_id} — {title}")
            elif doc_id:
                header_parts.append(doc_id)
            elif title:
                header_parts.append(title)

            if status:
                header_parts.append(f"[{status}]")

            if header_parts and not raw_t.startswith(header_parts[0]):
                formatted = f"{' '.join(header_parts)}: {raw_t}"
            else:
                formatted = raw_t
            memory_texts.append(formatted)

        report = self._parse_llm_response(
            raw_text=raw_response,
            proposal=proposal,
            recalled_memories=memory_texts,
            ghost_result=ghost_result,
            composite_result=composite_result,
        )
        logger.info(f"Successfully generated report for {proposal.proposal_id}")
        return report

    def analyze_proposals(
        self, proposal_ids: List[str]
    ) -> DecisionIntelligenceReport:
        """Evaluate a collection of proposals for composite ghost recreation."""
        return self.analyze_proposal(proposal_ids)

    def _build_recall_query(
        self,
        proposal: Proposal,
        composite_proposals: Optional[List[str]] = None,
    ) -> str:
        """Build a meaningful Hindsight recall query from proposal details and composite targets.

        Combines:
        - semantic inquiry question ('Have we previously considered building an employee mobile application or similar platform?')
        - proposal title, category, business problem, description, objectives
        - component titles and descriptions
        - key domain concepts (e.g. employee mobile platform, employee mobile application, attendance, leave management, notifications, employee services)
        - historical decision search targets (abandoned/failed initiatives, root causes, architectural constraints)
        """
        query_parts = [
            f"Question: Have we previously attempted or considered projects related to {proposal.title} ({proposal.category})?",
            f"Title: {proposal.title}",
            f"Category: {proposal.category}",
            f"Business Problem: {proposal.business_problem}",
            f"Proposal: {proposal.proposal}",
        ]
        if proposal.objectives:
            objs = ", ".join(proposal.objectives) if isinstance(proposal.objectives, list) else str(proposal.objectives)
            query_parts.append(f"Objectives: {objs}")

        # Extract semantic search concepts from proposal content and domain
        text_corpus = f"{proposal.title} {proposal.business_problem} {proposal.proposal} {' '.join(proposal.objectives or [])}".lower()
        semantic_terms = []
        if any(w in text_corpus for w in ["mobile", "ios", "android", "app", "native", "attendance", "leave"]):
            semantic_terms.extend([
                "employee mobile platform",
                "employee mobile application",
                "attendance",
                "leave management",
                "notifications",
                "employee services",
                "mobile access",
                "PWA vs native app",
            ])
        if any(w in text_corpus for w in ["microservice", "service", "monolith", "architecture"]):
            semantic_terms.extend([
                "microservices migration",
                "service-oriented architecture",
                "distributed systems",
                "team capacity",
                "operational overhead",
            ])
        if any(w in text_corpus for w in ["pricing", "tier", "subscription", "freemium"]):
            semantic_terms.extend([
                "tiered pricing",
                "freemium model",
                "enterprise tier",
                "churn",
                "customer conversion",
            ])
        if any(w in text_corpus for w in ["datacenter", "data center", "regional", "latency", "cloud"]):
            semantic_terms.extend([
                "regional data center",
                "infrastructure expansion",
                "latency reduction",
                "capital expenditure",
            ])

        if semantic_terms:
            query_parts.append(f"Semantic Concepts: {', '.join(dict.fromkeys(semantic_terms))}")

        if proposal.components:
            comp_descs = [f"{c.title}: {c.description}" for c in proposal.components]
            query_parts.append(f"Components: {'; '.join(comp_descs)}")

        # Include composite concepts when multiple proposals or components are evaluated
        if proposal.components or (composite_proposals and len(composite_proposals) > 1):
            query_parts.append(
                "Composite Recreation Check: Past organizational decisions, prior attempts, failure causes, and architectural constraints relating to combined employee mobile platform/application, attendance, leave management, employee notifications, and mobile employee services."
            )
        else:
            query_parts.append(
                "Target: Past organizational decisions, prior attempts, abandoned or failed initiatives, historical blockers, root causes, and architectural lessons learned."
            )

        return "\n".join(query_parts)

    def _extract_decision_id(self, item: Dict[str, Any]) -> str:
        """Extract historical decision ID from item attributes, metadata, tags, or text."""
        doc_id = item.get("document_id")
        if doc_id and re.match(r"^D\d{3}$", str(doc_id), re.IGNORECASE):
            return str(doc_id).upper()

        meta = item.get("metadata") or {}
        if "decision_id" in meta and meta["decision_id"]:
            return str(meta["decision_id"]).upper()

        for tag in item.get("tags") or []:
            if tag.lower().startswith("decision-"):
                return tag.split("-")[-1].upper()
            if re.match(r"^d\d{3}$", tag, re.IGNORECASE):
                return tag.upper()

        text = item.get("text", "")
        match = re.search(r"Decision ID:\s*([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        match_d = re.search(r"\b(D\d{3})\b", text)
        if match_d:
            return match_d.group(1).upper()

        return str(doc_id) if doc_id else "N/A"

    def _build_prompt(
        self,
        proposal: Proposal,
        company_context: CompanyContext,
        recalled_memories: Optional[List[Dict[str, Any]]] = None,
        fallback_decisions: Optional[List[HistoricalDecision]] = None,
        ghost_result: Optional[GhostDetectionResult] = None,
        composite_result: Optional[MultiProposalGhostDetectionResult] = None,
    ) -> str:
        """Assemble the evaluation prompt with proposal, recalled memories, company context,
        single-proposal ghost result, and composite ghost result."""
        context_dict = company_context.model_dump()

        # Build historical evidence section from Hindsight recall or fallback
        if recalled_memories:
            formatted_memories = []
            for idx, m in enumerate(recalled_memories, 1):
                doc_id = self._extract_decision_id(m)
                text = m.get("text", "").strip()
                tags = m.get("tags", [])
                entry = f"[Memory {idx}] Decision ID: {doc_id}\n"
                if tags:
                    entry += f"Tags: {', '.join(tags)}\n"
                entry += f"Content: {text}"
                formatted_memories.append(entry)
            history_section = "\n\n".join(formatted_memories)
            history_title = "HISTORICAL MEMORY (EVIDENCE RECALLED FROM HINDSIGHT)"
        else:
            # Fallback to local archive if Hindsight is unavailable
            decisions = fallback_decisions or load_historical_decisions()
            decisions_summary = []
            for d in decisions:
                entry = {
                    "decision_id": d.decision_id,
                    "date": d.date,
                    "title": d.title,
                    "category": d.category,
                    "status": d.status,
                    "business_problem": d.business_problem,
                    "proposal": d.proposal,
                    "chosen_option": d.chosen_option,
                    "reasoning": d.reasoning,
                    "actual_outcome": d.actual_outcome,
                    "constraints": d.constraints,
                    "lesson_learned": d.lesson_learned,
                    "failure_reasons": d.failure_reasons,
                    "success_factors": d.success_factors,
                    "rejection_reasons": d.rejection_reasons,
                }
                entry_clean = {k: v for k, v in entry.items() if v is not None}
                decisions_summary.append(entry_clean)
            history_section = json.dumps(decisions_summary, indent=2)
            history_title = "HISTORICAL ARCHIVE (LOCAL REPOSITORIES)"

        ghost_section = ""
        if ghost_result:
            ghost_section = f"""
======================================================================
4. SINGLE-PROPOSAL GHOST DECISION ASSESSMENT:
======================================================================
Potential Ghost Decision: {"YES (Detected)" if ghost_result.is_potential_ghost else "NO"}
Confidence Level: {ghost_result.confidence_level}
Historical Decisions Involved: {", ".join(ghost_result.historical_matches) if ghost_result.historical_matches else "None"}
Historical Status: {ghost_result.historical_status or "None"}
Why Proposal Resembles Them: {ghost_result.relationship_explanation or "None"}
Historical Blockers: {json.dumps(ghost_result.historical_blockers, indent=2)}
Blockers That Still Apply: {json.dumps(ghost_result.blockers_that_still_apply, indent=2)}
Blockers That May Have Changed: {json.dumps(ghost_result.blockers_that_may_have_changed, indent=2)}
Questions for Product Manager: {json.dumps(ghost_result.human_review_questions, indent=2)}
"""

        composite_section = ""
        if composite_result:
            groups_data = []
            for g in composite_result.composite_ghost_groups:
                groups_data.append({
                    "matched_decision_id": g.matched_historical_decision_id,
                    "matched_decision_title": g.matched_historical_decision_title,
                    "historical_status": g.historical_status,
                    "grouped_proposals": g.grouped_proposal_ids,
                    "composite_relationship_explanation": g.composite_relationship_explanation,
                    "historical_blockers": g.historical_blockers,
                    "blockers_that_still_apply": g.blockers_that_still_apply,
                    "blockers_that_may_have_changed": g.blockers_that_may_have_changed,
                    "human_review_questions": g.human_review_questions,
                })
            composite_section = f"""
======================================================================
5. COMPOSITE / MULTI-PROPOSAL GHOST DETECTION ASSESSMENT:
======================================================================
Potential Composite Ghost Decision: {"YES (Detected)" if composite_result.is_composite_ghost_detected else "NO"}
Confidence Level: {composite_result.confidence_level}
Headline: {composite_result.headline}
Evaluated Proposals / Components: {composite_result.evaluated_proposal_ids}
Detected Composite Groups: {json.dumps(groups_data, indent=2)}
Guidance for Product Manager: {json.dumps(composite_result.guidance_for_product_manager, indent=2)}
"""

        prompt = f"""
======================================================================
1. CURRENT PROPOSAL TO EVALUATE:
======================================================================
PROPOSAL ID: {proposal.proposal_id}
Title: {proposal.title}
Category: {proposal.category}
Proposed By: {proposal.proposed_by}
Business Problem: {proposal.business_problem}
Proposal Details: {proposal.proposal}
Objectives: {json.dumps(proposal.objectives, indent=2)}
Proposal Context: {json.dumps(proposal.current_context, indent=2)}
Alternatives Considered: {json.dumps(proposal.alternatives_considered, indent=2)}
Expected Outcome: {proposal.expected_outcome}
Components: {json.dumps([c.model_dump() for c in proposal.components] if proposal.components else [], indent=2)}

======================================================================
2. {history_title}:
======================================================================
{history_section}

======================================================================
3. CURRENT FACTS (NOVATECH 2026 OPERATIONAL CONTEXT):
======================================================================
Current Capabilities:
{json.dumps(context_dict.get("current_context", {}), indent=2)}

Historical Changes Trajectory:
{json.dumps(context_dict.get("historical_changes", []), indent=2)}
{ghost_section}
{composite_section}
======================================================================
EVALUATION INSTRUCTIONS:
======================================================================
Evaluate proposal '{proposal.proposal_id}' ({proposal.title}) against the recalled historical memories and current facts.

Your final analysis MUST synthesize:
1. Historical memories recalled by Hindsight: Precedents, outcomes, and constraints.
2. Potential Ghost Decision status (single-proposal): Whether a single-proposal ghost decision is detected, with qualitative confidence ("High", "Medium", "Low") and no numeric similarity score.
3. Potential Composite Ghost Decision status (multi-proposal): Whether multiple proposals/components collectively recreate past abandoned initiatives.
4. Historical decision(s) involved: Precedent IDs (e.g. D001, D002, D006) and titles.
5. Why the current proposal(s) resemble them: The conceptual relationship (both individual and collective).
6. Historical blockers: Technical, operational, and organizational bottlenecks.
7. Current conditions: Facts from NovaTech's current context.
8. Which blockers still apply: Active challenges that remain.
9. Which blockers may have changed: Blockers that have changed or been cleared.
10. Questions for the Product Manager: Strategic probing questions to consider before deciding.

CRITICAL PRINCIPLES:
- DO NOT automatically reject or approve the proposal.
- Provide objective, consultative reasoning so the human Product Manager can make the final informed decision.

Return your response as a valid, parsable JSON object conforming strictly to the required schema.
"""
        return prompt

    def _parse_llm_response(
        self,
        raw_text: str,
        proposal: Proposal,
        recalled_memories: Optional[List[str]] = None,
        ghost_result: Optional[GhostDetectionResult] = None,
        composite_result: Optional[MultiProposalGhostDetectionResult] = None,
    ) -> DecisionIntelligenceReport:
        """Parse raw LLM string into a validated DecisionIntelligenceReport Pydantic object."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        # Extract composite fields for fallback and default assignment
        is_composite = composite_result.is_composite_ghost_detected if composite_result else False
        composite_confidence = composite_result.confidence_level if composite_result else None
        composite_explanation = (
            composite_result.composite_ghost_groups[0].composite_relationship_explanation
            if composite_result and composite_result.composite_ghost_groups
            else None
        )
        blocker_comparisons = (
            composite_result.composite_ghost_groups[0].blocker_comparisons
            if composite_result and composite_result.composite_ghost_groups
            else []
        )

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as err:
            logger.error(f"Failed to parse LLM response as JSON: {err}\nRaw text: {raw_text[:300]}")
            # Construct a safe fallback report containing raw text in analysis, ghost result, and composite result
            return DecisionIntelligenceReport(
                proposal_id=proposal.proposal_id,
                proposal_title=proposal.title,
                recalled_historical_memories=recalled_memories or [],
                analysis=f"Analysis completed. (Note: Output parsed in fallback mode due to: {err})\n\n{raw_text}",
                historical_vs_current_comparison="Unable to structure JSON comparison.",
                questions_for_product_manager=(
                    ghost_result.human_review_questions if ghost_result and ghost_result.human_review_questions
                    else (
                        composite_result.guidance_for_product_manager if composite_result and composite_result.guidance_for_product_manager
                        else ["What are the primary operational risks based on past precedent?"]
                    )
                ),
                ghost_detection_result=ghost_result,
                is_potential_ghost=ghost_result.is_potential_ghost if ghost_result else False,
                ghost_confidence_level=ghost_result.confidence_level if ghost_result else None,
                relationship_explanation=ghost_result.relationship_explanation if ghost_result else None,
                historical_status=ghost_result.historical_status if ghost_result else None,
                historical_matches=ghost_result.historical_matches if ghost_result else [],
                historical_blockers=ghost_result.historical_blockers if ghost_result else [],
                blockers_that_may_still_apply=ghost_result.blockers_that_still_apply if ghost_result else [],
                blockers_that_may_have_changed=ghost_result.blockers_that_may_have_changed if ghost_result else [],
                # Composite ghost detection integration fields
                composite_ghost_detection_result=composite_result,
                is_composite_ghost=is_composite,
                composite_ghost_confidence_level=composite_confidence,
                composite_relationship_explanation=composite_explanation,
                blocker_comparisons=blocker_comparisons,
            )

        # Parse related decisions into HistoricalMatch objects
        related_matches: List[HistoricalMatch] = []
        for item in data.get("related_historical_decisions", []):
            try:
                related_matches.append(HistoricalMatch(**item))
            except Exception as e:
                logger.warning(f"Could not parse individual historical match: {e}")

        # If related_matches is empty, populate from ghost_result candidates
        if not related_matches and ghost_result and ghost_result.ghost_candidates:
            for c in ghost_result.ghost_candidates:
                related_matches.append(
                    HistoricalMatch(
                        decision_id=c.decision_id,
                        title=c.title,
                        status=c.status,
                        category=c.category,
                        similarity_reason=c.relationship_explanation,
                        actual_outcome=c.historical_outcome,
                        outcome_drivers=c.historical_blockers,
                        lesson_learned=c.lesson_learned,
                    )
                )

        # If related_matches is still empty and composite group exists, populate from composite group
        if not related_matches and composite_result and composite_result.composite_ghost_groups:
            for g in composite_result.composite_ghost_groups:
                related_matches.append(
                    HistoricalMatch(
                        decision_id=g.matched_historical_decision_id,
                        title=g.matched_historical_decision_title,
                        status=g.historical_status,
                        category="Product",
                        similarity_reason=g.composite_relationship_explanation,
                        actual_outcome=f"{g.historical_status}: Initiative was previously abandoned.",
                        outcome_drivers=g.historical_blockers,
                        lesson_learned=g.lesson_learned,
                    )
                )

        # Single Ghost Detection values
        is_potential_ghost = ghost_result.is_potential_ghost if ghost_result else data.get("is_potential_ghost", False)
        ghost_confidence = ghost_result.confidence_level if ghost_result else (data.get("ghost_confidence_level") or data.get("confidence_level"))
        relationship_explanation = ghost_result.relationship_explanation if ghost_result else data.get("relationship_explanation")
        historical_status = ghost_result.historical_status if ghost_result else data.get("historical_status")

        # Compile historical matches from single and composite
        historical_matches = list(ghost_result.historical_matches) if ghost_result and ghost_result.historical_matches else []
        if composite_result and composite_result.composite_ghost_groups:
            for g in composite_result.composite_ghost_groups:
                if g.matched_historical_decision_id and g.matched_historical_decision_id not in historical_matches:
                    historical_matches.append(g.matched_historical_decision_id)
        if not historical_matches:
            historical_matches = data.get("historical_matches", [m.decision_id for m in related_matches])

        if not historical_status and composite_result and composite_result.composite_ghost_groups:
            historical_status = composite_result.composite_ghost_groups[0].historical_status

        # Merge historical blockers across single ghost, composite groups, and LLM output
        historical_blockers = list(data.get("historical_blockers") or [])
        if ghost_result:
            for b in ghost_result.historical_blockers:
                if b not in historical_blockers:
                    historical_blockers.append(b)
        if composite_result and composite_result.composite_ghost_groups:
            for g in composite_result.composite_ghost_groups:
                for b in g.historical_blockers:
                    if b not in historical_blockers:
                        historical_blockers.append(b)

        # Merge blockers that still apply
        blockers_that_may_still_apply = list(data.get("blockers_that_may_still_apply") or [])
        if ghost_result:
            for b in ghost_result.blockers_that_still_apply:
                if b not in blockers_that_may_still_apply:
                    blockers_that_may_still_apply.append(b)
        if composite_result and composite_result.composite_ghost_groups:
            for g in composite_result.composite_ghost_groups:
                for b in g.blockers_that_still_apply:
                    if b not in blockers_that_may_still_apply:
                        blockers_that_may_still_apply.append(b)

        # Merge blockers that may have changed
        blockers_that_may_have_changed = list(data.get("blockers_that_may_have_changed") or [])
        if ghost_result:
            for b in ghost_result.blockers_that_may_have_changed:
                if b not in blockers_that_may_have_changed:
                    blockers_that_may_have_changed.append(b)
        if composite_result and composite_result.composite_ghost_groups:
            for g in composite_result.composite_ghost_groups:
                for b in g.blockers_that_may_have_changed:
                    if b not in blockers_that_may_have_changed:
                        blockers_that_may_have_changed.append(b)

        # Merge questions for product manager
        questions_for_pm = list(data.get("questions_for_product_manager") or [])
        if ghost_result:
            for q in ghost_result.human_review_questions:
                if q not in questions_for_pm:
                    questions_for_pm.append(q)
        if composite_result and composite_result.composite_ghost_groups:
            for g in composite_result.composite_ghost_groups:
                for q in g.human_review_questions:
                    if q not in questions_for_pm:
                        questions_for_pm.append(q)
        if composite_result and composite_result.guidance_for_product_manager:
            for q in composite_result.guidance_for_product_manager:
                if q not in questions_for_pm:
                    questions_for_pm.append(q)

        raw_analysis = data.get("analysis", "") if isinstance(data, dict) else ""

        # Build comprehensive analysis narrative articulating both single and composite assessments
        analysis_parts = []
        if raw_analysis:
            analysis_parts.append(raw_analysis)

        ghost_summary_text = (
            f"### Ghost Decision Assessment (Single Proposal)\n"
            f"- **Potential Ghost Status**: {'Potential Ghost Decision Detected' if is_potential_ghost else 'No Direct Ghost Decision Detected'} (Confidence: {ghost_confidence or 'N/A'})\n"
            f"- **Historical Decisions Involved**: {', '.join(historical_matches) if historical_matches else 'None'}\n"
            f"- **Resemblance Explanation**: {relationship_explanation or 'N/A'}\n"
            f"- **Historical Status**: {historical_status or 'N/A'}\n"
            f"- **Historical Blockers**: {'; '.join(historical_blockers) if historical_blockers else 'None'}\n"
            f"- **Blockers That Still Apply**: {'; '.join(blockers_that_may_still_apply) if blockers_that_may_still_apply else 'None'}\n"
            f"- **Blockers That May Have Changed**: {'; '.join(blockers_that_may_have_changed) if blockers_that_may_have_changed else 'None'}\n"
            f"- **Questions for the Product Manager**: {'; '.join(questions_for_pm) if questions_for_pm else 'None'}"
        )

        if composite_result and composite_result.is_composite_ghost_detected:
            comp_group = composite_result.composite_ghost_groups[0] if composite_result.composite_ghost_groups else None
            matched_info = (
                f"{comp_group.matched_historical_decision_id} ('{comp_group.matched_historical_decision_title}')"
                if comp_group
                else "Historical Precedent"
            )
            comp_props = (
                ", ".join(comp_group.grouped_proposal_ids)
                if comp_group
                else ", ".join(composite_result.evaluated_proposal_ids)
            )
            # Format current company conditions concisely
            cond_map = comp_group.current_company_conditions if comp_group else company_context.current_context
            cond_summary = "; ".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in list(cond_map.items())[:5]) if isinstance(cond_map, dict) else str(cond_map)

            composite_questions = comp_group.human_review_questions if comp_group else questions_for_pm
            questions_str = "; ".join(composite_questions[:3]) if composite_questions else "None"

            composite_summary_text = (
                f"\n\n### Composite Ghost Decision Intelligence Briefing\n"
                f"1. **Potential Composite Ghost Decision Detected**: YES (Confidence: {composite_result.confidence_level})\n"
                f"2. **Current Proposals Involved**: {comp_props}\n"
                f"3. **Historical Decision Matched**: {matched_info}\n"
                f"4. **Why They Collectively Resemble It**: {comp_group.composite_relationship_explanation if comp_group else 'The combination of these proposals recreates the scope of a previously attempted decision.'}\n"
                f"5. **Historical Outcome**: {comp_group.historical_status if comp_group else 'Abandoned'}\n"
                f"6. **Historical Blockers**: {'; '.join(comp_group.historical_blockers[:4]) if comp_group else 'None'}\n"
                f"7. **Current Company Conditions**: {cond_summary}\n"
                f"8. **Blockers That May Still Apply**: {'; '.join(comp_group.blockers_that_still_apply[:4]) if comp_group else 'None'}\n"
                f"9. **Blockers That May Have Changed**: {'; '.join(comp_group.blockers_that_may_have_changed[:4]) if comp_group else 'None'}\n"
                f"10. **Human Review Questions**: {questions_str}"
            )
            ghost_summary_text += composite_summary_text

        if "ghost" not in raw_analysis.lower():
            analysis_parts.append(ghost_summary_text)

        full_analysis = "\n\n".join(analysis_parts) if analysis_parts else f"Analysis completed for proposal {proposal.proposal_id}."

        return DecisionIntelligenceReport(
            proposal_id=proposal.proposal_id,
            proposal_title=proposal.title,
            related_historical_decisions=related_matches,
            recalled_historical_memories=recalled_memories or [],
            historical_outcomes=data.get("historical_outcomes", [historical_status] if historical_status else []),
            historical_blockers=historical_blockers,
            current_conditions=data.get("current_conditions", proposal.current_context),
            historical_vs_current_comparison=data.get(
                "historical_vs_current_comparison",
                "Comparison of historical conditions with current context.",
            ),
            blockers_that_may_still_apply=blockers_that_may_still_apply,
            blockers_that_may_have_changed=blockers_that_may_have_changed,
            analysis=full_analysis,
            questions_for_product_manager=questions_for_pm,
            # Single ghost detection integration fields
            ghost_detection_result=ghost_result,
            is_potential_ghost=is_potential_ghost,
            ghost_confidence_level=ghost_confidence,
            relationship_explanation=relationship_explanation,
            historical_status=historical_status,
            historical_matches=historical_matches,
            # Composite ghost detection integration fields
            composite_ghost_detection_result=composite_result,
            is_composite_ghost=is_composite,
            composite_ghost_confidence_level=composite_confidence,
            composite_relationship_explanation=composite_explanation,
            blocker_comparisons=blocker_comparisons,
        )
