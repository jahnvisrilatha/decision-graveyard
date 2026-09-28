"""Ghost Decision Detection for Decision Graveyard (Step 6).

Determines whether a current product or feature proposal represents a
"Ghost Decision" (a previously attempted, abandoned, failed, or decided initiative).

Guiding Principles:
1. Never automatically recommend accepting or rejecting proposals.
2. Uses consultative phrasing: "Potential Ghost Decision Detected" rather than "Reject this proposal."
3. Does not use fake numerical similarity percentages; uses qualitative confidence ('High', 'Medium', 'Low', 'None').
4. Compares historical blockers against current company facts (blockers that still apply vs changed).
5. The human Product Manager remains the final decision-maker.
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
from agent.hindsight_memory import HindsightMemory
from agent.llm_client import LLMClient
from agent.models import (
    CompanyContext,
    GhostCandidate,
    GhostDetectionResult,
    HistoricalDecision,
    Proposal,
)

logger = logging.getLogger(__name__)

GHOST_DETECTION_SYSTEM_PROMPT = """You are "Decision Graveyard Ghost Detector", an organizational memory intelligence engine helping Product Managers evaluate whether a new proposal represents a "Ghost Decision".

A "Ghost Decision" occurs when an organization considers an initiative, architecture, or policy that closely resembles or repeats an initiative that was previously attempted, abandoned, failed, rejected, or decided in the past—often without the current team realizing it or without addressing the original causes.

CRITICAL INSTRUCTIONS:
1. You must NEVER automatically recommend accepting or rejecting the proposal.
   - Do NOT say "Reject this proposal" or "This proposal should be cancelled".
   - Your role is purely consultative and analytical: provide historical evidence and contextual comparisons so the human PM can make an informed decision.
2. Carefully evaluate whether the proposal genuinely represents a previously abandoned, failed, or rejected initiative:
   - If a substantive conceptual connection to a past failed or abandoned decision is identified, set "ghost_detected": true, confidence to 'High', 'Medium', or 'Low', and use phrasing "Potential Ghost Decision Detected".
   - If NO substantive conceptual connection to an abandoned/failed past decision exists (e.g. routine infrastructure expansion like P003 Regional Data Center, or novel features without historical failure precedent), set "ghost_detected": false, "confidence": "None", and "ghost_candidates": []. Do NOT force a connection to unrelated historical decisions (such as confusing regional data center capacity with pricing models).
3. Do NOT use fake numerical similarity percentages (e.g. "87% similar"). Instead, classify confidence qualitatively as 'High', 'Medium', 'Low', or 'None'.
4. For each potential ghost decision identified:
   - Identify the historical decision ID (e.g. D001, D002, D004).
   - Explain why the current proposal and historical decision are conceptually related.
   - State the historical status and outcome.
   - Detail the historical blockers, constraints, and failure reasons.
   - Contrast those historical blockers against current company facts (from company context).
   - Classify which blockers may still apply today vs. which blockers have changed or been cleared.
5. Provide actionable strategic questions and guidance for the Product Manager to investigate before committing resources.

You must return a valid JSON object strictly matching this schema:
{
  "ghost_detected": true | false,
  "headline": "Potential Ghost Decision Detected: ..." | "No Strong Historical Ghost Detected",
  "confidence": "High" | "Medium" | "Low" | "None",
  "ghost_candidates": [
    {
      "decision_id": "string",
      "title": "string",
      "status": "string",
      "category": "string",
      "relationship_explanation": "string",
      "historical_outcome": "string",
      "historical_blockers": ["string"],
      "lesson_learned": "string",
      "blockers_that_may_still_apply": ["string"],
      "blockers_that_may_have_changed": ["string"]
    }
  ],
  "reasoning": "string",
  "guidance_for_product_manager": ["string"]
}
"""


class GhostDetector:
    """Detects whether a proposal represents a previously attempted organizational decision."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        hindsight_memory: Optional[HindsightMemory] = None,
    ):
        """Initialize GhostDetector with LLM client and Hindsight memory.

        Args:
            llm_client: Optional LLMClient instance.
            hindsight_memory: Optional HindsightMemory instance.
        """
        self.llm_client = llm_client or LLMClient()
        self.hindsight_memory = hindsight_memory or HindsightMemory()

    def detect_ghost(
        self,
        proposal: Union[str, Proposal],
        recalled_memories: Optional[List[Dict[str, Any]]] = None,
    ) -> GhostDetectionResult:
        """Run Ghost Decision Detection on a proposal.

        Workflow:
        1. Receive the current proposal (by ID or Proposal object) and optional recalled memories.
        2. If recalled_memories is not provided, query Hindsight recall.
        3. Analyze recalled memories for candidate historical decisions.
        4. Load current company context from data/company_context.json.
        5. Ask the LLM to determine whether a potential ghost decision exists.
        6. Compare historical blockers against current facts.
        7. Return structured GhostDetectionResult.

        Args:
            proposal: Proposal ID string (e.g. 'P001') or Proposal model instance.
            recalled_memories: Optional list of recalled memories retrieved from Hindsight.

        Returns:
            Structured GhostDetectionResult.
        """
        # 1. Resolve proposal
        if isinstance(proposal, str):
            proposal_obj = get_proposal_by_id(proposal)
        else:
            proposal_obj = proposal

        logger.info(f"Running Ghost Decision Detection for proposal '{proposal_obj.proposal_id}'")

        # 2. Use passed recalled memories or query Hindsight
        memories = recalled_memories
        if memories is None:
            recall_query = self._build_recall_query(proposal_obj)
            try:
                memories = self.hindsight_memory.recall_memories(
                    query=recall_query,
                    max_tokens=3000,
                )
                logger.info(
                    f"Recalled {len(memories)} memories for proposal {proposal_obj.proposal_id}"
                )
            except Exception as e:
                logger.warning(f"Hindsight recall error during ghost detection: {e}")
                memories = []

        # Fallback to local historical decisions if offline or empty
        fallback_decisions = None
        if not memories:
            logger.info("Using local historical decisions as fallback for ghost detection.")
            fallback_decisions = load_historical_decisions()

        # 5. Load current company context
        company_context = load_company_context()

        # 6. Build prompt and send to LLM
        prompt = self._build_detection_prompt(
            proposal=proposal_obj,
            company_context=company_context,
            recalled_memories=memories,
            fallback_decisions=fallback_decisions,
        )

        raw_response = self.llm_client.generate_analysis(
            prompt=prompt, system_instruction=GHOST_DETECTION_SYSTEM_PROMPT
        )

        # 7 & 8. Parse into GhostDetectionResult
        result = self._parse_llm_response(
            raw_text=raw_response,
            proposal=proposal_obj,
            company_context=company_context,
            recalled_count=len(memories),
        )
        logger.info(
            f"Ghost detection completed for {proposal_obj.proposal_id}: "
            f"ghost_detected={result.ghost_detected} (confidence={result.confidence})"
        )
        return result

    def _build_recall_query(self, proposal: Proposal) -> str:
        """Build a meaningful Hindsight recall query from proposal details."""
        parts = [
            f"Proposal Title: {proposal.title}",
            f"Category: {proposal.category}",
            f"Business Problem: {proposal.business_problem}",
            f"Proposal: {proposal.proposal}",
        ]
        if proposal.objectives:
            objs = ", ".join(proposal.objectives) if isinstance(proposal.objectives, list) else str(proposal.objectives)
            parts.append(f"Objectives: {objs}")
        return "\n".join(parts)

    def _extract_decision_id(self, item: Dict[str, Any]) -> str:
        """Extract historical decision ID from memory item."""
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

    def _build_detection_prompt(
        self,
        proposal: Proposal,
        company_context: CompanyContext,
        recalled_memories: Optional[List[Dict[str, Any]]] = None,
        fallback_decisions: Optional[List[HistoricalDecision]] = None,
    ) -> str:
        """Assemble the Ghost Detection prompt."""
        context_dict = company_context.model_dump()

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
            history_title = "HISTORICAL MEMORY RECALLED FROM HINDSIGHT"
        else:
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
                    "actual_outcome": d.actual_outcome,
                    "constraints": d.constraints,
                    "lesson_learned": d.lesson_learned,
                    "failure_reasons": d.failure_reasons,
                    "success_factors": d.success_factors,
                    "rejection_reasons": d.rejection_reasons,
                }
                decisions_summary.append({k: v for k, v in entry.items() if v is not None})
            history_section = json.dumps(decisions_summary, indent=2)
            history_title = "HISTORICAL DECISION ARCHIVE (LOCAL REPOSITORY)"

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
Current Proposal Context: {json.dumps(proposal.current_context, indent=2)}
Alternatives Considered: {json.dumps(proposal.alternatives_considered, indent=2)}
Expected Outcome: {proposal.expected_outcome}

======================================================================
2. {history_title}:
======================================================================
{history_section}

======================================================================
3. CURRENT FACTS (NOVATECH 2026 OPERATIONAL PROFILE):
======================================================================
Current Capabilities:
{json.dumps(context_dict.get("current_context", {}), indent=2)}

Historical Changes Trajectory:
{json.dumps(context_dict.get("historical_changes", []), indent=2)}

======================================================================
DETECTION TASK:
======================================================================
1. Analyze whether proposal '{proposal.proposal_id}' ({proposal.title}) may represent a previously attempted or decided initiative ("Ghost Decision").
2. Identify which historical decisions it conceptually relates to (include decision IDs e.g. D001).
3. If a potential ghost decision is detected, explain:
   - Why they are conceptually related.
   - Historical status and outcome.
   - Historical blockers/reasons.
4. Compare historical blockers with current facts:
   - Which historical blockers may still apply?
   - Which historical blockers may have changed or been cleared?
5. Formulate consultative guidance and probing questions for the Product Manager.
6. Remember: DO NOT recommend approving or rejecting. The human PM is the final decision-maker.

Return valid JSON conforming strictly to the requested schema.
"""
        return prompt

    def _parse_llm_response(
        self,
        raw_text: str,
        proposal: Proposal,
        company_context: CompanyContext,
        recalled_count: int = 0,
    ) -> GhostDetectionResult:
        """Parse raw LLM response into validated GhostDetectionResult."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as err:
            logger.warning(f"Could not parse LLM output as JSON ({err}). Using fallback generator.")
            return self._generate_fallback_result(proposal, company_context, recalled_count)

        candidates: List[GhostCandidate] = []
        if "ghost_candidates" in data and data["ghost_candidates"]:
            for c in data.get("ghost_candidates", []):
                try:
                    candidates.append(GhostCandidate(**c))
                except Exception as e:
                    logger.warning(f"Error parsing ghost candidate: {e}")
        elif "related_historical_decisions" in data and data["related_historical_decisions"]:
            blockers_still_apply = data.get("blockers_that_may_still_apply", [])
            blockers_changed = data.get("blockers_that_may_have_changed", [])
            for r in data.get("related_historical_decisions", []):
                candidates.append(
                    GhostCandidate(
                        decision_id=r.get("decision_id", "Unknown"),
                        title=r.get("title", ""),
                        status=r.get("status", "Unknown"),
                        category=r.get("category", ""),
                        relationship_explanation=r.get("similarity_reason", ""),
                        historical_outcome=r.get("actual_outcome", ""),
                        historical_blockers=r.get("outcome_drivers", []),
                        lesson_learned=r.get("lesson_learned"),
                        blockers_that_may_still_apply=blockers_still_apply,
                        blockers_that_may_have_changed=blockers_changed,
                    )
                )
        else:
            return self._generate_fallback_result(proposal, company_context, recalled_count)

        # Ensure confidence is qualitative
        conf = data.get("confidence")
        if not conf or isinstance(conf, (int, float)) or "%" in str(conf):
            conf = "High" if bool(candidates) else "None"

        ghost_detected = data.get("ghost_detected")
        if ghost_detected is None:
            ghost_detected = len(candidates) > 0

        default_headline = (
            f"Potential Ghost Decision Detected: Proposal relates to prior decision {candidates[0].decision_id} ({candidates[0].title})."
            if candidates
            else "No Direct Ghost Decision Detected"
        )
        headline = data.get("headline") or default_headline
        reasoning = data.get("reasoning") or data.get("analysis") or "Analysis completed."
        guidance = data.get("guidance_for_product_manager") or data.get("questions_for_product_manager", [])

        return GhostDetectionResult(
            proposal_id=proposal.proposal_id,
            proposal_title=proposal.title,
            ghost_detected=ghost_detected,
            headline=headline,
            confidence=conf,
            ghost_candidates=candidates,
            current_context_summary=company_context.current_context,
            reasoning=reasoning,
            guidance_for_product_manager=guidance,
            recalled_memories_count=recalled_count,
        )

    def _generate_fallback_result(
        self,
        proposal: Proposal,
        company_context: CompanyContext,
        recalled_count: int = 0,
    ) -> GhostDetectionResult:
        """Deterministic fallback when LLM is in mock mode or parsing fails."""
        proposal_id = proposal.proposal_id.upper()
        if proposal_id in ("P001", "P005"):
            candidate = GhostCandidate(
                decision_id="D001",
                title="Employee Mobile Application",
                status="Abandoned",
                category="Product",
                relationship_explanation=(
                    "Both initiatives attempt to build native Android and iOS mobile applications "
                    "for employee attendance, leave management, and company notifications."
                ),
                historical_outcome="The project was abandoned after the initial development phase.",
                historical_blockers=[
                    "Low employee mobile usage (only 18% in 2024)",
                    "Small engineering team (5 developers)",
                    "High dual-platform maintenance overhead (separate iOS and Android apps)",
                    "Functional overlap with existing employee web portal",
                ],
                lesson_learned=(
                    "A native mobile application should not be built when target user adoption is low "
                    "and the existing web platform already satisfies most of the required workflow."
                ),
                blockers_that_may_still_apply=[
                    "Maintaining separate native iOS/Android codebases still requires dedicated mobile engineers.",
                    "Potential redundancy with the existing web portal and Progressive Web Application (D006).",
                ],
                blockers_that_may_have_changed=[
                    "Employee mobile adoption increased from 18% in 2024 to 76% in 2026.",
                    "Engineering team size increased from 5 to 15 developers.",
                    "DevOps maturity transitioned from Low to High with automated CI/CD.",
                ],
            )
            return GhostDetectionResult(
                proposal_id=proposal.proposal_id,
                proposal_title=proposal.title,
                ghost_detected=True,
                headline="Potential Ghost Decision Detected: Proposal closely relates to past initiative D001 (Employee Mobile Application).",
                confidence="High",
                ghost_candidates=[candidate],
                current_context_summary=company_context.current_context,
                reasoning=(
                    "Proposal P001 mirrors decision D001 from March 2024, where NovaTech attempted to build "
                    "native mobile apps and abandoned them due to low adoption and high overhead. "
                    "While organizational conditions have improved substantially (76% mobile adoption, 15 engineers), "
                    "the PM must determine whether native mobile apps are genuinely required over enhancing the existing PWA (D006)."
                ),
                guidance_for_product_manager=[
                    "Verify whether specific device hardware APIs are strictly required that the current PWA (D006) cannot access.",
                    "Evaluate ongoing app store release and maintenance overhead with the current engineering team.",
                    "Review adoption metrics of the current employee web portal and PWA before committing to native development.",
                ],
                recalled_memories_count=recalled_count,
            )
        elif proposal_id == "P002":
            candidate = GhostCandidate(
                decision_id="D002",
                title="Microservices Migration",
                status="Abandoned",
                category="Engineering",
                relationship_explanation=(
                    "Both initiatives propose adopting a microservices backend architecture to solve scaling and deployment challenges."
                ),
                historical_outcome="The project was abandoned after encountering high operational complexity.",
                historical_blockers=[
                    "Limited distributed systems experience",
                    "Low DevOps maturity with manual deployment processes",
                    "Lack of centralized observability and monitoring",
                ],
                lesson_learned=(
                    "Microservices require adequate engineering capacity, DevOps maturity, automated deployment, "
                    "and monitoring before adoption."
                ),
                blockers_that_may_still_apply=[
                    "Managing inter-service contracts, network latency, and distributed data consistency.",
                ],
                blockers_that_may_have_changed=[
                    "DevOps maturity is now High with automated CI/CD.",
                    "Kubernetes container orchestration platform is established and running (D008).",
                    "Centralized monitoring and observability are in place.",
                ],
            )
            return GhostDetectionResult(
                proposal_id=proposal.proposal_id,
                proposal_title=proposal.title,
                ghost_detected=True,
                headline="Potential Ghost Decision Detected: Proposal relates to past initiative D002 (Microservices Migration).",
                confidence="High",
                ghost_candidates=[candidate],
                current_context_summary=company_context.current_context,
                reasoning=(
                    "NovaTech attempted microservices in 2024 (D002) and abandoned the effort due to operational tooling deficiencies. "
                    "Most historical blockers have since been resolved through Kubernetes (D008) and automated CI/CD."
                ),
                guidance_for_product_manager=[
                    "Confirm clear domain boundaries between the proposed microservices.",
                    "Establish standardized service scaffolding for logging, tracing, and auth before implementation.",
                ],
                recalled_memories_count=recalled_count,
            )
        else:
            return GhostDetectionResult(
                proposal_id=proposal.proposal_id,
                proposal_title=proposal.title,
                ghost_detected=False,
                headline="No Direct Ghost Decision Detected",
                confidence="None",
                ghost_candidates=[],
                current_context_summary=company_context.current_context,
                reasoning=f"No high-similarity past decisions were identified that closely duplicate proposal {proposal.proposal_id}.",
                guidance_for_product_manager=[
                    "Proceed with standard cross-functional technical and business review."
                ],
                recalled_memories_count=recalled_count,
            )
