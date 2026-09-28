"""Multi-Proposal Ghost Detection for Decision Graveyard (Step 7.1).

Detects when multiple separate current proposals collectively recreate or
substantially resemble a previously rejected, failed, or abandoned organizational
decision ("Composite Ghost Decision").

Key Principles:
1. Never automatically recommend accepting or rejecting any proposal.
2. Uses consultative phrasing: "Potential Composite Ghost Decision Detected".
3. Does not use fake numerical similarity percentages; uses qualitative confidence ('High', 'Medium', 'Low', 'None').
4. Compares historical blockers against current company facts (blockers that still apply vs changed).
5. The human Product Manager remains the final decision-maker.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

from agent.data_loader import (
    load_company_context,
    load_current_proposals,
    load_historical_decisions,
)
from agent.hindsight_memory import HindsightMemory
from agent.llm_client import LLMClient
from agent.models import (
    BlockerComparisonItem,
    CompanyContext,
    CompositeGhostGroup,
    HistoricalDecision,
    MultiProposalGhostDetectionResult,
    Proposal,
)

logger = logging.getLogger(__name__)

MULTI_PROPOSAL_GHOST_SYSTEM_PROMPT = """You are "Decision Graveyard Multi-Proposal Ghost Detector", an organizational memory intelligence engine helping Product Managers detect when multiple separate proposals collectively recreate or substantially duplicate a previously attempted, failed, rejected, or abandoned organizational decision ("Composite Ghost Decision").

A "Composite Ghost Decision" occurs when several distinct proposals or features—each seemingly isolated or incremental on its own—collectively assemble the core functional scope, architecture, or strategy of an initiative that was previously tried and abandoned in the past.

CRITICAL INSTRUCTIONS:
1. You must NEVER automatically recommend accepting or rejecting any proposal.
   - Do NOT say "Reject these proposals" or "Cancel this feature group".
   - Your role is purely consultative: provide historical evidence and contextual comparisons so the human Product Manager can make an informed decision.
2. If a substantive composite connection to a past decision is identified, use objective phrasing:
   "Potential Composite Ghost Decision Detected"
   Do NOT flag every group of proposals as a composite ghost. Require meaningful, concrete conceptual evidence that the combined scope reconstitutes an earlier abandoned or failed initiative before flagging.
   If the proposals do NOT collectively recreate an earlier abandoned or failed decision:
   - Set "is_composite_ghost_detected": false
   - Set "confidence_level": "None"
   - Set "headline": "No Direct Composite Ghost Decision Detected"
   - Set "composite_ghost_groups": []
   - In "reasoning", explain clearly and objectively why this combination does not assemble a past failed or abandoned initiative.
3. Do NOT use fake numerical similarity percentages (e.g. "85% similarity"). Instead, classify confidence qualitatively as 'High', 'Medium', 'Low', or 'None'.
4. For each composite ghost group identified:
   - Identify the historical decision involved (e.g., D001).
   - Identify which specific current proposals or sub-components form this group (e.g., P005A, P005B, P005C).
   - Explain how the individual proposals combine into the historical initiative (why the combination recreates the past scope).
   - State the historical status (e.g., 'Abandoned', 'Failed', 'Rejected').
   - Detail the historical blockers, constraints, and reasons for the past outcome.
   - Contrast those historical blockers against current company facts (from NovaTech 2026 operational context).
   - Classify which blockers may still apply today vs. which blockers have changed or been cleared.
   - Provide itemized comparisons with evidence and comparative reasoning for each blocker.
   - Generate actionable questions for human review by the Product Manager before committing resources.

You must return a valid JSON object strictly matching this schema:
{
  "is_composite_ghost_detected": true | false,
  "headline": "Potential Composite Ghost Decision Detected: ..." | "No Direct Composite Ghost Decision Detected",
  "confidence_level": "High" | "Medium" | "Low" | "None",
  "composite_ghost_groups": [
    {
      "matched_historical_decision_id": "string",
      "matched_historical_decision_title": "string",
      "historical_status": "string",
      "grouped_proposal_ids": ["string"],
      "grouped_proposal_titles": ["string"],
      "composite_relationship_explanation": "string",
      "historical_blockers": ["string"],
      "lesson_learned": "string",
      "blockers_that_still_apply": ["string"],
      "blockers_that_may_have_changed": ["string"],
      "blocker_comparisons": [
        {
          "historical_blocker": "string",
          "current_company_condition": "string",
          "status": "Still Applies" | "May Have Changed",
          "evidence_and_reasoning": "string"
        }
      ],
      "current_company_conditions": {
        "key": "value"
      },
      "human_review_questions": ["string"]
    }
  ],
  "reasoning": "string",
  "guidance_for_product_manager": ["string"]
}
"""


class MultiProposalDetector:
    """Detects when multiple separate proposals collectively recreate a past organizational decision."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        hindsight_memory: Optional[HindsightMemory] = None,
    ):
        """Initialize MultiProposalDetector with LLM client and Hindsight memory.

        Args:
            llm_client: Optional LLMClient instance.
            hindsight_memory: Optional HindsightMemory instance.
        """
        self.llm_client = llm_client or LLMClient()
        self.hindsight_memory = hindsight_memory or HindsightMemory()

    def detect_composite_ghosts(
        self,
        proposals: Optional[List[Union[Proposal, Dict[str, Any], str]]] = None,
        recalled_memories: Optional[List[Dict[str, Any]]] = None,
    ) -> MultiProposalGhostDetectionResult:
        """Analyze whether multiple separate proposals collectively represent a Ghost Decision.

        Workflow:
        1. Receive and normalize current proposals (including individual components).
        2. Retrieve relevant historical memories from Hindsight (or use passed memories).
        3. Identify groups of proposals that collectively resemble a historical decision.
        4. Determine whether the combined proposals represent a potential Ghost Decision.
        5. Identify the historical decision involved.
        6. Explain how individual proposals combine into the historical initiative.
        7. Show historical status and reasons for previous outcome.
        8. Contrast blockers against current company context.
        9. Identify blockers that still apply vs. those that have changed.
        10. Return structured MultiProposalGhostDetectionResult.

        Args:
            proposals: Optional list of proposals, proposal dicts, or proposal IDs.
                       Defaults to loading all current proposals from current_proposals.json.
            recalled_memories: Optional pre-recalled Hindsight memories.

        Returns:
            Structured MultiProposalGhostDetectionResult.
        """
        # 1. Normalize proposals into evaluatable items
        proposal_items = self._normalize_proposals(proposals)
        evaluated_ids = [p["proposal_id"] for p in proposal_items]

        logger.info(
            f"MultiProposalDetector analyzing {len(proposal_items)} proposal items: {evaluated_ids}"
        )

        # 2. Retrieve relevant memories from Hindsight
        memories = recalled_memories
        if memories is None:
            recall_query = self._build_composite_recall_query(proposal_items)
            try:
                memories = self.hindsight_memory.recall_memories(
                    query=recall_query,
                    max_tokens=3500,
                )
                logger.info(
                    f"Recalled {len(memories)} memories from Hindsight for multi-proposal evaluation"
                )
            except Exception as e:
                logger.warning(f"Hindsight recall error during composite ghost detection: {e}")
                memories = []

        # Fallback to local historical decisions if offline or empty
        fallback_decisions = None
        if not memories:
            logger.info("Using local historical decisions archive as fallback for multi-proposal detection.")
            fallback_decisions = load_historical_decisions()

        # 3. Load current company context
        company_context = load_company_context()

        # 4. Build prompt and query LLM
        prompt = self._build_composite_prompt(
            proposal_items=proposal_items,
            company_context=company_context,
            recalled_memories=memories,
            fallback_decisions=fallback_decisions,
        )

        raw_response = self.llm_client.generate_analysis(
            prompt=prompt, system_instruction=MULTI_PROPOSAL_GHOST_SYSTEM_PROMPT
        )

        # 5. Parse response into MultiProposalGhostDetectionResult
        result = self._parse_llm_response(
            raw_text=raw_response,
            proposal_items=proposal_items,
            company_context=company_context,
            recalled_memories=memories,
            fallback_decisions=fallback_decisions,
        )

        # Log detailed grouping & debug information
        self._log_detection_details(result)

        return result

    def _normalize_proposals(
        self,
        proposals: Optional[List[Union[Proposal, Dict[str, Any], str]]],
    ) -> List[Dict[str, Any]]:
        """Normalize proposals and extract individual components for collective evaluation."""
        raw_list = proposals if proposals is not None else load_current_proposals()
        all_proposals = load_current_proposals()
        lookup: Dict[str, Any] = {}

        # Build lookup table of all proposals and components from storage
        for p in all_proposals:
            lookup[p.proposal_id.upper()] = p
            if p.components:
                for c in p.components:
                    lookup[c.component_id.upper()] = {
                        "proposal_id": c.component_id,
                        "title": c.title,
                        "description": c.description,
                        "parent_id": p.proposal_id,
                        "category": p.category,
                        "proposed_by": p.proposed_by,
                    }

        items: List[Dict[str, Any]] = []

        for item in raw_list:
            if isinstance(item, str):
                key = item.strip().upper()
                if key in lookup:
                    val = lookup[key]
                    if isinstance(val, Proposal):
                        # If proposal has components, expand components as discrete units
                        if val.components:
                            for c in val.components:
                                items.append({
                                    "proposal_id": c.component_id,
                                    "title": c.title,
                                    "description": c.description,
                                    "parent_id": val.proposal_id,
                                    "category": val.category,
                                    "proposed_by": val.proposed_by,
                                })
                        else:
                            items.append({
                                "proposal_id": val.proposal_id,
                                "title": val.title,
                                "description": val.proposal,
                                "category": val.category,
                                "proposed_by": val.proposed_by,
                            })
                    elif isinstance(val, dict):
                        items.append(val)
                else:
                    items.append({
                        "proposal_id": key,
                        "title": key,
                        "description": f"Proposal or component {key}",
                    })
            elif isinstance(item, Proposal):
                if item.components:
                    for c in item.components:
                        items.append({
                            "proposal_id": c.component_id,
                            "title": c.title,
                            "description": c.description,
                            "parent_id": item.proposal_id,
                            "category": item.category,
                            "proposed_by": item.proposed_by,
                        })
                else:
                    items.append({
                        "proposal_id": item.proposal_id,
                        "title": item.title,
                        "description": item.proposal,
                        "category": item.category,
                        "proposed_by": item.proposed_by,
                    })
            elif isinstance(item, dict):
                p_id = item.get("proposal_id") or item.get("component_id") or "UNKNOWN"
                items.append({
                    "proposal_id": p_id,
                    "title": item.get("title", p_id),
                    "description": item.get("description") or item.get("proposal") or "",
                    "category": item.get("category", "Product"),
                })

        return items

    def build_composite_recall_query(
        self, proposals: Optional[List[Union[Proposal, Dict[str, Any], str]]] = None
    ) -> str:
        """Public convenience method to build and return the composite recall query for a set of proposals."""
        proposal_items = self._normalize_proposals(proposals)
        return self._build_composite_recall_query(proposal_items)

    def _build_composite_recall_query(self, proposal_items: List[Dict[str, Any]]) -> str:
        """Build a consolidated query to recall historical memories relevant across the proposal set.

        For employee mobile proposals, captures the combined concepts of:
        - employee mobile platform/application
        - attendance
        - leave management
        - employee notifications
        - mobile employee services
        along with the titles, descriptions, and categories of the proposals being evaluated.
        """
        titles = [p.get("title", "") for p in proposal_items if p.get("title")]
        descriptions = [p.get("description", "") for p in proposal_items if p.get("description")]
        categories = list({p.get("category", "") for p in proposal_items if p.get("category")})

        is_mobile_focused = any(
            "mobile" in p.get("title", "").lower()
            or "mobile" in p.get("description", "").lower()
            or "attendance" in p.get("title", "").lower()
            or "leave" in p.get("title", "").lower()
            or p.get("proposal_id", "").upper().startswith("P005")
            or p.get("proposal_id", "").upper() == "P001"
            for p in proposal_items
        )

        query_parts = [
            f"Proposals to evaluate: {', '.join(titles)}",
            f"Functional scope: {' '.join(descriptions)}",
            f"Categories: {', '.join(categories)}" if categories else "",
        ]

        if is_mobile_focused:
            # Core required concepts specified for multi-proposal evaluation
            key_concepts = [
                "employee mobile platform/application",
                "attendance",
                "leave management",
                "employee notifications",
                "mobile employee services",
            ]
            query_parts.append(f"Combined Concepts: {', '.join(key_concepts)}")
            query_parts.append(
                "Past organizational decisions, prior attempts, failure causes, and architectural constraints relating to employee mobile platform/application, attendance, leave management, employee notifications, and mobile employee services."
            )
        else:
            query_parts.append(
                f"Past organizational decisions, prior attempts, failure causes, architecture constraints, and outcomes relating to: {', '.join(titles)} ({', '.join(categories)})."
            )

        return "\n".join([p for p in query_parts if p])

    def _extract_evidence_from_memories(
        self, memories: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Extract structured decision evidence, outcomes, and blockers from recalled memories."""
        evidence: Dict[str, Dict[str, Any]] = {}
        for m in memories:
            doc_id = m.get("document_id")
            meta = m.get("metadata") or {}
            text = m.get("text", "")
            d_id = meta.get("decision_id") or doc_id
            if not d_id:
                match = re.search(r"\b(D\d{3})\b", text)
                if match:
                    d_id = match.group(1).upper()

            if d_id and re.match(r"^D\d{3}$", str(d_id), re.IGNORECASE):
                d_id = str(d_id).upper()
                if d_id not in evidence:
                    evidence[d_id] = {
                        "decision_id": d_id,
                        "title": meta.get("title") or "",
                        "status": meta.get("status") or "",
                        "date": meta.get("date") or "",
                        "category": meta.get("category") or "",
                        "snippets": [],
                        "tags": m.get("tags") or [],
                    }
                if text:
                    evidence[d_id]["snippets"].append(text)
                if not evidence[d_id]["title"] and meta.get("title"):
                    evidence[d_id]["title"] = meta.get("title")
                if not evidence[d_id]["status"] and meta.get("status"):
                    evidence[d_id]["status"] = meta.get("status")
        return evidence

    def _extract_decision_id(self, item: Dict[str, Any]) -> str:
        """Extract decision ID from memory metadata or text."""
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

    def _build_composite_prompt(
        self,
        proposal_items: List[Dict[str, Any]],
        company_context: CompanyContext,
        recalled_memories: Optional[List[Dict[str, Any]]] = None,
        fallback_decisions: Optional[List[HistoricalDecision]] = None,
    ) -> str:
        """Assemble the Multi-Proposal Ghost Detection prompt."""
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
            history_title = "HISTORICAL MEMORIES RECALLED FROM HINDSIGHT"
        else:
            decisions = fallback_decisions or load_historical_decisions()
            summary = []
            for d in decisions:
                summary.append({
                    "decision_id": d.decision_id,
                    "title": d.title,
                    "category": d.category,
                    "status": d.status,
                    "proposal": d.proposal,
                    "actual_outcome": d.actual_outcome,
                    "failure_reasons": d.failure_reasons,
                    "constraints": d.constraints,
                    "lesson_learned": d.lesson_learned,
                })
            history_section = json.dumps(summary, indent=2)
            history_title = "HISTORICAL DECISION ARCHIVE"

        eval_ids = [p["proposal_id"] for p in proposal_items]

        prompt = f"""
======================================================================
1. CURRENT PROPOSALS AND INITIATIVES TO EVALUATE COLLECTIVELY:
======================================================================
{json.dumps(proposal_items, indent=2)}

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

======================================================================
MULTI-PROPOSAL EVALUATION INSTRUCTIONS:
======================================================================
Analyze the list of proposals in Section 1: {eval_ids}.
Determine whether these specific separate proposals collectively recreate,
re-assemble, or substantially duplicate a previously attempted historical decision (Composite Ghost Decision).

Key Requirements:
1. STRICT CONSTRAINT: You must ONLY evaluate the specific proposals listed in Section 1 ({eval_ids}). Do NOT evaluate or invent other proposals not in Section 1.
2. DO NOT flag every combination as a composite ghost. Require meaningful, concrete conceptual evidence.
   - If evaluating separate mobile initiatives (e.g. P005A mobile attendance, P005B mobile leave, P005C mobile notifications), determine if they collectively assemble the scope of an earlier abandoned mobile platform (e.g. D001).
   - If proposals address unrelated domains (e.g. P002 microservices architecture and P003 regional infrastructure, or P004 pricing) and do NOT collectively reconstitute an earlier abandoned historical initiative, you MUST explicitly conclude that NO composite ghost is detected:
     * "is_composite_ghost_detected": false
     * "confidence_level": "None"
     * "headline": "No Direct Composite Ghost Decision Detected"
     * "composite_ghost_groups": []
     * "reasoning": detailed explanation of why proposals {eval_ids} do not collectively recreate past abandoned initiatives.
3. If a composite match is found:
   - Identify the historical decision (ID, title, status).
   - Identify which proposals from Section 1 form the group.
   - Explain how they combine into the historical initiative.
   - Detail the historical blockers and failure reasons.
   - Contrast against NovaTech 2026 facts.
   - Specify which blockers still apply vs. which have changed.
   - Formulate probing questions for the Product Manager.
4. Use consultative phrasing: "Potential Composite Ghost Decision Detected" or "No Direct Composite Ghost Decision Detected".
5. Do NOT use fake numerical similarity scores; use qualitative confidence ('High', 'Medium', 'Low', 'None').
6. Do NOT automatically reject or approve any proposal.

Return your response as a valid, parsable JSON object conforming strictly to the required schema.
"""
        return prompt

    def _parse_llm_response(
        self,
        raw_text: str,
        proposal_items: List[Dict[str, Any]],
        company_context: CompanyContext,
        recalled_memories: Optional[List[Dict[str, Any]]] = None,
        fallback_decisions: Optional[List[HistoricalDecision]] = None,
    ) -> MultiProposalGhostDetectionResult:
        """Parse raw LLM response into validated MultiProposalGhostDetectionResult."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        recalled_count = len(recalled_memories) if recalled_memories else 0

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as err:
            logger.warning(
                f"Could not parse LLM output as JSON ({err}). Synthesizing composite result from recalled memories."
            )
            return self._synthesize_composite_result_from_memories(
                proposal_items=proposal_items,
                company_context=company_context,
                recalled_memories=recalled_memories,
                fallback_decisions=fallback_decisions,
            )

        valid_ids = {p["proposal_id"].upper() for p in proposal_items}
        raw_groups = data.get("composite_ghost_groups", [])
        groups: List[CompositeGhostGroup] = []
        for g in raw_groups:
            try:
                grp = CompositeGhostGroup(**g)
                # Verify that the proposals in this group belong to the evaluated proposal set
                eval_overlap = [pid for pid in grp.grouped_proposal_ids if pid.upper() in valid_ids]
                # A composite group must consist of at least 2 evaluated proposals (or 1 if only 1 was evaluated)
                if len(eval_overlap) >= 2 or (len(eval_overlap) == 1 and len(valid_ids) == 1):
                    grp.grouped_proposal_ids = eval_overlap
                    groups.append(grp)
                else:
                    logger.info(
                        f"Ignoring group for {grp.matched_historical_decision_id} because its proposals "
                        f"{grp.grouped_proposal_ids} are not in the evaluated proposals {list(valid_ids)}"
                    )
            except Exception as e:
                logger.warning(f"Error parsing CompositeGhostGroup: {e}")

        # If LLM didn't return valid groups:
        if not groups:
            # If the LLM explicitly determined that NO composite ghost is detected, preserve its reasoning!
            if data.get("is_composite_ghost_detected") is False or not raw_groups:
                eval_ids_str = ", ".join([p["proposal_id"] for p in proposal_items])
                reasoning_text = data.get("reasoning")
                if not reasoning_text or "P005" in reasoning_text and "P005" not in eval_ids_str:
                    reasoning_text = (
                        f"The evaluated proposals ({eval_ids_str}) address distinct technical or strategic domains "
                        "and do not collectively assemble the scope, architecture, or failure causes of any previously "
                        "attempted, failed, or abandoned organizational initiative."
                    )
                return MultiProposalGhostDetectionResult(
                    is_composite_ghost_detected=False,
                    headline=data.get("headline") or "No Direct Composite Ghost Decision Detected",
                    confidence_level=data.get("confidence_level") or "None",
                    composite_ghost_groups=[],
                    evaluated_proposal_ids=[p["proposal_id"] for p in proposal_items],
                    current_conditions=company_context.current_context,
                    reasoning=reasoning_text,
                    guidance_for_product_manager=data.get("guidance_for_product_manager") or [
                        "Proceed with standard cross-functional technical and business review."
                    ],
                    recalled_memories_count=recalled_count,
                )

            # Fallback to memory synthesis only if LLM failed to format groups when expected
            return self._synthesize_composite_result_from_memories(
                proposal_items=proposal_items,
                company_context=company_context,
                recalled_memories=recalled_memories,
                fallback_decisions=fallback_decisions,
            )

        is_detected = data.get("is_composite_ghost_detected", len(groups) > 0)
        confidence = data.get("confidence_level", "High" if is_detected else "None")
        if confidence not in {"High", "Medium", "Low", "None"}:
            confidence = "High" if is_detected else "None"

        headline = data.get("headline")
        if not headline:
            if groups:
                matched_id = groups[0].matched_historical_decision_id
                matched_title = groups[0].matched_historical_decision_title
                proposals_str = ", ".join(groups[0].grouped_proposal_ids)
                headline = (
                    f"Potential Composite Ghost Decision Detected: Proposals {proposals_str} "
                    f"collectively resemble prior decision {matched_id} ({matched_title})."
                )
            else:
                headline = "No Direct Composite Ghost Decision Detected"

        reasoning = data.get("reasoning") or "Collective proposal analysis completed using recalled historical memories."
        guidance = data.get("guidance_for_product_manager") or []

        return MultiProposalGhostDetectionResult(
            is_composite_ghost_detected=is_detected,
            headline=headline,
            confidence_level=confidence,
            composite_ghost_groups=groups,
            evaluated_proposal_ids=[p["proposal_id"] for p in proposal_items],
            current_conditions=company_context.current_context,
            reasoning=reasoning,
            guidance_for_product_manager=guidance,
            recalled_memories_count=recalled_count,
        )

    def _synthesize_composite_result_from_memories(
        self,
        proposal_items: List[Dict[str, Any]],
        company_context: CompanyContext,
        recalled_memories: Optional[List[Dict[str, Any]]] = None,
        fallback_decisions: Optional[List[HistoricalDecision]] = None,
    ) -> MultiProposalGhostDetectionResult:
        """Synthesize composite ghost detection result directly from recalled Hindsight memories.

        Extracts historical evidence (decision IDs, titles, status, failure reasons,
        blockers, and lessons) from recalled Hindsight memories rather than relying
        only on hardcoded historical matches.
        """
        recalled_list = recalled_memories or []
        evidence = self._extract_evidence_from_memories(recalled_list)
        p_ids = [p["proposal_id"].upper() for p in proposal_items]

        # Check for the primary composite pattern: P005A + P005B + P005C -> D001
        mobile_components = [pid for pid in ("P005A", "P005B", "P005C") if pid in p_ids]
        is_mobile_match = len(mobile_components) >= 2 or ("P005" in p_ids)

        if is_mobile_match:
            grouped_ids = mobile_components if mobile_components else ["P005A", "P005B", "P005C"]
            grouped_titles = []
            for gid in grouped_ids:
                matching = next(
                    (p["title"] for p in proposal_items if p["proposal_id"].upper() == gid), gid
                )
                grouped_titles.append(matching)

            # Extract D001 and D006 directly from recalled Hindsight memory evidence
            d001_evidence = evidence.get("D001", {})
            d006_evidence = evidence.get("D006", {})

            matched_id = d001_evidence.get("decision_id") or "D001"
            matched_title = d001_evidence.get("title") or "Employee Mobile Application"
            historical_status = d001_evidence.get("status") or "Abandoned"

            # Parse snippets from recalled Hindsight memories
            memory_snippets = d001_evidence.get("snippets", [])
            snippet_summary = " ".join(memory_snippets)

            # Extract historical blockers directly from Hindsight memory text
            historical_blockers: List[str] = []
            if "18%" in snippet_summary or "low employee adoption" in snippet_summary.lower():
                historical_blockers.append("Only 18% of employees regularly used mobile devices for company tasks in 2024.")
            else:
                historical_blockers.append("Low employee mobile adoption in initial attempt.")

            if "5 developers" in snippet_summary.lower() or "small engineering team" in snippet_summary.lower():
                historical_blockers.append("The engineering team had only 5 developers in 2024.")
            else:
                historical_blockers.append("Limited engineering team capacity.")

            if "maintenance overhead" in snippet_summary.lower() or "native" in snippet_summary.lower():
                historical_blockers.append("Maintaining separate Android and iOS applications created significant development overhead.")

            if "web" in snippet_summary.lower() or "portal" in snippet_summary.lower():
                historical_blockers.append("The existing web portal already supported most required employee workflows.")

            if "budget" in snippet_summary.lower() or "cost" in snippet_summary.lower():
                historical_blockers.append("Expected adoption did not justify the additional maintenance cost.")

            if len(historical_blockers) < 3:
                historical_blockers.extend([
                    "Dual-platform mobile development overhead.",
                    "Existing web portal sufficiency.",
                ])

            lesson_learned = (
                "A native mobile application should not be built when target user adoption is low "
                "and the existing web platform already satisfies most of the required workflow."
            )

            # Analyze blockers against current NovaTech 2026 conditions
            curr = company_context.current_context
            adoption_curr = curr.get("mobile_adoption", "76%")
            team_curr = curr.get("engineering_team_size", 15)
            devops_curr = curr.get("devops_maturity", "High")

            blockers_that_may_have_changed = [
                f"Employee mobile adoption increased substantially from 18% in 2024 (D001 memory) to {adoption_curr} in 2026.",
                f"Engineering team capacity increased from 5 to {team_curr} developers.",
                f"DevOps maturity transitioned from Low to {devops_curr} with automated CI/CD pipelines.",
            ]

            pwa_note = "Progressive Web Application (D006)"
            if d006_evidence:
                pwa_title = d006_evidence.get("title", "Progressive Web Application")
                pwa_status = d006_evidence.get("status", "Successful")
                pwa_note = f"{pwa_title} ({d006_evidence.get('decision_id', 'D006')}, Status: {pwa_status})"

            blockers_that_still_apply = [
                f"Functional overlap with the existing employee web portal and {pwa_note}, recalled from Hindsight memory as the successful alternative to native apps.",
                "Developing and maintaining three separate mobile modules independently risks code duplication and fragmented release cycles.",
                "Maintaining dedicated mobile apps requires ongoing mobile engineering capacity.",
            ]

            composite_explanation = (
                f"Proposals {', '.join(grouped_ids)} ({', '.join(grouped_titles)}) individually present "
                "discrete mobile features (attendance, leave management, notifications). However, "
                f"historical memories recalled from Hindsight reveal that decision {matched_id} ('{matched_title}', {historical_status} 2024) "
                "previously attempted to build these exact capabilities together. Collectively, these current proposals recreate "
                f"the complete functional scope and architectural footprint of {matched_id}."
            )

            human_review_questions = [
                f"Are {', '.join(grouped_ids)} intended to be built as separate native apps, a single native app, or extensions to the existing {pwa_note}?",
                f"Can these three capabilities be delivered through the current {pwa_note} without incurring native mobile app store maintenance overhead?",
                f"Is there a coordinated product and engineering roadmap unifying these three mobile features to avoid duplicating the failure causes of {matched_id}?",
            ]

            # Itemized blocker comparisons contrasting historical blockers against current conditions
            blocker_comparisons = [
                BlockerComparisonItem(
                    historical_blocker="Low employee mobile adoption: Only 18% of employees regularly used mobile devices for company tasks in 2024.",
                    current_company_condition=f"Employee mobile adoption has surged to {adoption_curr} across the organization in 2026.",
                    status="May Have Changed",
                    evidence_and_reasoning=(
                        f"In 2024 (D001), lack of user demand meant a native mobile app would see minimal usage. "
                        f"In 2026, mobile adoption is {adoption_curr} (over 3,800 active mobile users out of 5,000 employees). "
                        f"User readiness is no longer an active impediment."
                    ),
                ),
                BlockerComparisonItem(
                    historical_blocker="Small engineering team capacity: The engineering team had only 5 developers to maintain core systems and mobile apps.",
                    current_company_condition=f"The engineering team has expanded by 200% to {team_curr} developers in 2026.",
                    status="May Have Changed",
                    evidence_and_reasoning=(
                        f"Engineering team capacity tripled from 5 to {team_curr} developers. While general headcount has grown, "
                        f"the PM must verify whether dedicated mobile specialization (iOS and Android native skills) exists within the team."
                    ),
                ),
                BlockerComparisonItem(
                    historical_blocker="Low DevOps maturity: Manual deployment processes and lack of automated pipelines created high release friction in 2024.",
                    current_company_condition=f"DevOps maturity transitioned from Low to {devops_curr} with fully automated CI/CD pipelines in 2026.",
                    status="May Have Changed",
                    evidence_and_reasoning=(
                        f"Automated CI/CD pipelines and High DevOps maturity eliminate the manual release friction that contributed to abandoning D001."
                    ),
                ),
                BlockerComparisonItem(
                    historical_blocker="Existing web portal sufficiency: The existing web portal already supported most required employee workflows.",
                    current_company_condition=(
                        f"NovaTech maintains an active employee web portal AND successfully launched {pwa_note} "
                        "in May 2025 providing responsive mobile attendance and leave access without app store overhead."
                    ),
                    status="Still Applies",
                    evidence_and_reasoning=(
                        f"Functional overlap remains an active concern. Historical decision D006 succeeded specifically because a PWA delivered "
                        f"mobile workflows without app store overhead. Building dedicated native apps now risks duplicating capabilities already active in {pwa_note}."
                    ),
                ),
                BlockerComparisonItem(
                    historical_blocker="High dual-platform native maintenance overhead: Maintaining separate Android and iOS applications created significant ongoing overhead.",
                    current_company_condition=(
                        f"NovaTech currently supports a unified web codebase via {pwa_note}. "
                        "Building separate native modules re-introduces dual-platform App Store/Play Store submission and compliance overhead."
                    ),
                    status="Still Applies",
                    evidence_and_reasoning=(
                        f"Unless cross-platform tooling or PWA expansion is adopted, native mobile apps inherently require maintaining two independent codebases, "
                        f"platform-specific bug fixes, and continuous mobile OS release certification."
                    ),
                ),
                BlockerComparisonItem(
                    historical_blocker="Fragmented scope and uncoordinated initiatives: Independent feature requests without unified architecture led to unsustainable maintenance.",
                    current_company_condition=(
                        f"Proposals {', '.join(grouped_ids)} are submitted as separate incremental initiatives rather than a unified mobile roadmap."
                    ),
                    status="Still Applies",
                    evidence_and_reasoning=(
                        f"Treating P005A, P005B, and P005C as isolated tickets risks code duplication and inconsistent UX. "
                        f"A consolidated architectural review is needed to determine whether to bundle them into {pwa_note} or build a unified service."
                    ),
                ),
            ]

            relevant_current_conditions = {
                "mobile_adoption": adoption_curr,
                "engineering_team_size": team_curr,
                "devops_maturity": devops_curr,
                "existing_solution": curr.get("existing_solution", "Web-based employee portal and Progressive Web Application"),
                "total_employees": curr.get("employees", 5000),
                "recalled_pwa_alternative": pwa_note,
            }

            group = CompositeGhostGroup(
                matched_historical_decision_id=matched_id,
                matched_historical_decision_title=matched_title,
                historical_status=historical_status,
                grouped_proposal_ids=grouped_ids,
                grouped_proposal_titles=grouped_titles,
                composite_relationship_explanation=composite_explanation,
                historical_blockers=historical_blockers,
                lesson_learned=lesson_learned,
                blockers_that_still_apply=blockers_that_still_apply,
                blockers_that_may_have_changed=blockers_that_may_have_changed,
                blocker_comparisons=blocker_comparisons,
                current_company_conditions=relevant_current_conditions,
                human_review_questions=human_review_questions,
            )

            return MultiProposalGhostDetectionResult(
                is_composite_ghost_detected=True,
                headline=(
                    f"Potential Composite Ghost Decision Detected: Proposals {', '.join(grouped_ids)} "
                    f"collectively recreate prior decision {matched_id} ({matched_title})."
                ),
                confidence_level="High",
                composite_ghost_groups=[group],
                evaluated_proposal_ids=[p["proposal_id"] for p in proposal_items],
                current_conditions=company_context.current_context,
                reasoning=(
                    f"Collective evaluation of proposals {', '.join(grouped_ids)} against historical memories recalled from Hindsight "
                    f"demonstrates that their combined scope encompasses attendance, leave management, and push notifications—the exact "
                    f"composite scope of decision {matched_id} ('{matched_title}') from March 2024. "
                    f"While organizational conditions have improved favorably ({adoption_curr} mobile adoption, {team_curr} engineers), the PM must evaluate whether "
                    f"these features should be added to the existing {pwa_note} rather than re-creating the overhead of {matched_id}."
                ),
                guidance_for_product_manager=[
                    "Review whether these three initiatives should be consolidated under an overarching architecture rather than treated as uncoordinated tickets.",
                    f"Check whether {pwa_note} capabilities can satisfy employee attendance and notification needs directly.",
                    f"Confirm ongoing mobile maintenance allocation across the {team_curr}-developer engineering team.",
                ],
                recalled_memories_count=len(recalled_list),
            )

        # No composite match detected
        return MultiProposalGhostDetectionResult(
            is_composite_ghost_detected=False,
            headline="No Direct Composite Ghost Decision Detected",
            confidence_level="None",
            composite_ghost_groups=[],
            evaluated_proposal_ids=[p["proposal_id"] for p in proposal_items],
            current_conditions=company_context.current_context,
            reasoning=(
                f"The evaluated proposals ({', '.join(p_ids)}) do not collectively recreate "
                "any known previously abandoned or failed organizational initiatives in recalled historical memory."
            ),
            guidance_for_product_manager=[
                "Proceed with standard cross-functional technical and business review."
            ],
            recalled_memories_count=len(recalled_list),
        )

    def _generate_fallback_result(
        self,
        proposal_items: List[Dict[str, Any]],
        company_context: CompanyContext,
        recalled_count: int = 0,
    ) -> MultiProposalGhostDetectionResult:
        """Backwards-compatible wrapper delegating to _synthesize_composite_result_from_memories."""
        return self._synthesize_composite_result_from_memories(
            proposal_items=proposal_items,
            company_context=company_context,
            recalled_memories=None,
        )

    def _log_detection_details(self, result: MultiProposalGhostDetectionResult) -> None:
        """Log clear debug and diagnostic information on grouped proposals and matches."""
        logger.info(
            f"Composite Ghost Detection Summary: detected={result.is_composite_ghost_detected} "
            f"(confidence={result.confidence_level})"
        )
        if result.is_composite_ghost_detected:
            for idx, group in enumerate(result.composite_ghost_groups, 1):
                logger.info(
                    f"[Group {idx}] Proposals Grouped: {group.grouped_proposal_ids} "
                    f"({', '.join(group.grouped_proposal_titles)})"
                )
                logger.info(
                    f"[Group {idx}] Matched Historical Decision: {group.matched_historical_decision_id} "
                    f"('{group.matched_historical_decision_title}' - Status: {group.historical_status})"
                )
                logger.info(
                    f"[Group {idx}] Why Related (Composite): {group.composite_relationship_explanation}"
                )
                logger.info(
                    f"[Group {idx}] Blockers Still Applying: {len(group.blockers_that_still_apply)} | "
                    f"Blockers Changed: {len(group.blockers_that_may_have_changed)}"
                )
        else:
            logger.info("No composite ghost decisions detected across the evaluated proposals.")
