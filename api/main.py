"""FastAPI Application for Decision Graveyard.

Exposes RESTful endpoints:
- GET  /health               -> Service health check {"status": "ok"}
- GET  /proposals            -> List active proposals from current_proposals.json
- POST /analyze/{proposal_id}-> Run DecisionAgent analysis and store in session memory
- POST /analyze              -> Run analysis on custom proposal payload or ID
- GET  /reports/{proposal_id}-> Retrieve previously generated report from in-memory store
- GET  /                     -> Serve Decision Graveyard Prototype UI
"""

from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent.data_loader import load_current_proposals, load_historical_decisions
from agent.decision_agent import DecisionAgent
from agent.models import DecisionIntelligenceReport, HistoricalDecision, Proposal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("decision_graveyard_api")

app = FastAPI(
    title="Decision Graveyard API",
    description="AI Agent helping Product Managers evaluate proposals against organizational memory.",
    version="1.0.0",
)

# Enable CORS for cross-origin access and testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent instance
agent = DecisionAgent()

# Simple in-memory report store for the current server session
# Maps normalized proposal_id (e.g., 'P001') -> DecisionIntelligenceReport
report_store: Dict[str, DecisionIntelligenceReport] = {}

# Static Frontend mounting
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", response_class=FileResponse, include_in_schema=False)
def serve_index():
    """Serve the Decision Graveyard prototype user interface."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>Decision Graveyard API</h1><p>Frontend UI files not found.</p>")


@app.get("/health", tags=["Health"])
def health() -> Dict[str, str]:
    """Health check endpoint.

    Returns:
        {"status": "ok"}
    """
    return {"status": "ok"}


@app.get("/proposals", response_model=List[Proposal], tags=["Proposals"])
def get_proposals() -> List[Proposal]:
    """Retrieve all current proposals from data/current_proposals.json.

    Returns:
        List of Proposal objects.
    """
    try:
        return load_current_proposals()
    except Exception as e:
        logger.error(f"Error loading proposals: {e}")
        raise HTTPException(status_code=500, detail="Failed to load proposals.")


@app.get("/historical-decisions", response_model=List[HistoricalDecision], tags=["Decisions"])
def get_historical_decisions() -> List[HistoricalDecision]:
    """Retrieve all historical decisions from data/historical_decisions.json."""
    try:
        return load_historical_decisions()
    except Exception as e:
        logger.error(f"Error loading historical decisions: {e}")
        raise HTTPException(status_code=500, detail="Failed to load historical decisions.")


@app.get("/dashboard-stats", tags=["Dashboard"])
def get_dashboard_stats() -> Dict[str, Any]:
    """Calculate and return organizational memory summary statistics for the dashboard."""
    try:
        decisions = load_historical_decisions()
        proposals = load_current_proposals()

        total = len(decisions)
        successful = sum(1 for d in decisions if d.status.lower() == "successful")
        abandoned = sum(1 for d in decisions if d.status.lower() == "abandoned")
        failed = sum(1 for d in decisions if d.status.lower() == "failed")
        rejected = sum(1 for d in decisions if d.status.lower() == "rejected")

        return {
            "total_historical": total,
            "successful_count": successful,
            "abandoned_count": abandoned,
            "failed_count": failed,
            "rejected_count": rejected,
            "failed_abandoned_rejected_total": abandoned + failed + rejected,
            "active_proposals_count": len(proposals),
            "recent_decisions": [
                {
                    "decision_id": d.decision_id,
                    "title": d.title,
                    "category": d.category,
                    "status": d.status,
                    "date": d.date,
                    "summary": d.lesson_learned or d.expected_outcome,
                }
                for d in decisions[:6]
            ],
        }
    except Exception as e:
        logger.error(f"Error computing dashboard stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute dashboard stats.")


@app.post(
    "/analyze/{proposal_id}",
    response_model=DecisionIntelligenceReport,
    tags=["Analysis"],
    summary="Analyze proposal against organizational memory"
)
def analyze(proposal_id: str) -> DecisionIntelligenceReport:
    """Analyze a proposal using the DecisionAgent and cache the report in session memory.

    Args:
        proposal_id: Unique proposal ID (e.g., 'P001', 'P005', or comma-separated 'P005A,P005B,P005C').

    Returns:
        DecisionIntelligenceReport containing historical evidence and comparison.

    Raises:
        HTTPException 404: If the proposal_id does not exist.
        HTTPException 500: If unexpected agent errors occur.
    """
    normalized_id = proposal_id.strip().upper()
    try:
        if "," in normalized_id:
            ids = [i.strip() for i in normalized_id.split(",") if i.strip()]
            report = agent.analyze_proposal(ids)
        else:
            report = agent.analyze_proposal(normalized_id)
        # Store in session memory for GET /reports/{proposal_id}
        report_store[normalized_id] = report
        return report
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Analysis failed for {proposal_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal agent error while analyzing proposal: {str(e)}"
        )


class AnalyzeProposalPayload(BaseModel):
    """Payload schema for custom proposal analysis."""
    proposal_id: Optional[str] = None
    title: str
    business_problem: str
    proposal: str
    objectives: List[str] = Field(default_factory=list)
    category: str = "Product"
    proposed_by: str = "Product Manager"
    expected_outcome: Optional[str] = ""


@app.post(
    "/analyze",
    response_model=DecisionIntelligenceReport,
    tags=["Analysis"],
    summary="Analyze proposal (by payload or ID) against organizational memory"
)
def analyze_payload(payload: AnalyzeProposalPayload) -> DecisionIntelligenceReport:
    """Analyze a proposal provided via JSON request body.

    Args:
        payload: Proposal fields submitted from the UI form.

    Returns:
        DecisionIntelligenceReport with full intelligence briefing.
    """
    try:
        # Check if proposal_id matches an existing known proposal ID
        if payload.proposal_id:
            norm_id = payload.proposal_id.strip().upper()
            if "," in norm_id:
                ids = [i.strip() for i in norm_id.split(",") if i.strip()]
                report = agent.analyze_proposal(ids)
                report_store[norm_id] = report
                return report
            try:
                report = agent.analyze_proposal(norm_id)
                report_store[norm_id] = report
                return report
            except ValueError:
                pass  # Fall through to custom Proposal creation

        pid = (payload.proposal_id or f"CUSTOM-{len(report_store) + 1}").strip().upper()
        custom_proposal = Proposal(
            proposal_id=pid,
            date=datetime.utcnow().strftime("%Y-%m-%d"),
            title=payload.title,
            category=payload.category,
            proposed_by=payload.proposed_by,
            business_problem=payload.business_problem,
            proposal=payload.proposal,
            objectives=payload.objectives,
            expected_outcome=payload.expected_outcome or payload.title,
        )
        report = agent.analyze_proposal(custom_proposal)
        report_store[pid] = report
        return report
    except Exception as e:
        logger.error(f"Analysis failed for payload: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal agent error while analyzing proposal: {str(e)}"
        )


@app.get(
    "/reports/{proposal_id}",
    response_model=DecisionIntelligenceReport,
    tags=["Reports"],
    summary="Retrieve previously generated report"
)
def get_report(proposal_id: str) -> DecisionIntelligenceReport:
    """Retrieve a previously generated Decision Intelligence Report from session memory.

    Args:
        proposal_id: Unique proposal ID (e.g., 'P001').

    Returns:
        The previously generated DecisionIntelligenceReport.

    Raises:
        HTTPException 404: If no report exists for this proposal in the current session.
    """
    normalized_id = proposal_id.strip().upper()
    report = report_store.get(normalized_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No report found for proposal '{proposal_id}' in the current session. "
                f"Please run POST /analyze/{proposal_id} first."
            )
        )
    return report
