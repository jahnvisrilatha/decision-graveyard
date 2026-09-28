"""Decision Graveyard Agent Package."""

from agent.data_loader import (
    get_decision_by_id,
    get_proposal_by_id,
    load_company_context,
    load_current_proposals,
    load_historical_decisions,
)
from agent.decision_agent import DecisionAgent
from agent.ghost_detector import GhostDetector
from agent.hindsight_memory import HindsightMemory, ingest_historical_decisions
from agent.llm_client import LLMClient
from agent.models import (
    CompanyContext,
    CompositeGhostDetectionResult,
    CompositeGhostGroup,
    CurrentProposalsContainer,
    DecisionIntelligenceReport,
    GhostCandidate,
    GhostDetectionReport,
    GhostDetectionResult,
    HistoricalDecision,
    HistoricalDecisionsContainer,
    HistoricalMatch,
    MultiProposalGhostDetectionResult,
    Proposal,
    ProposalComponent,
    ProposalInput,
)
from agent.multi_proposal_detector import MultiProposalDetector

__all__ = [
    "DecisionAgent",
    "GhostDetector",
    "GhostCandidate",
    "GhostDetectionResult",
    "GhostDetectionReport",
    "MultiProposalDetector",
    "CompositeGhostGroup",
    "MultiProposalGhostDetectionResult",
    "CompositeGhostDetectionResult",
    "HindsightMemory",
    "ingest_historical_decisions",
    "LLMClient",

    "Proposal",
    "ProposalInput",
    "ProposalComponent",
    "CurrentProposalsContainer",
    "HistoricalDecision",
    "HistoricalDecisionsContainer",
    "HistoricalMatch",
    "CompanyContext",
    "DecisionIntelligenceReport",
    "load_company_context",
    "load_current_proposals",
    "get_proposal_by_id",
    "load_historical_decisions",
    "get_decision_by_id",
]
