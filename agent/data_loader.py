"""Data loader module for Decision Graveyard.

Loads & validates data from:
- data/company_context.json
- data/current_proposals.json
- data/historical_decisions.json

Separates pure data access and validation from AI reasoning.
"""

import json
from pathlib import Path
from typing import List, Optional, Union

from agent.models import CompanyContext, HistoricalDecision, Proposal

# Project root directory resolved relative to this file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

COMPANY_CONTEXT_PATH = DATA_DIR / "company_context.json"
CURRENT_PROPOSALS_PATH = DATA_DIR / "current_proposals.json"
HISTORICAL_DECISIONS_PATH = DATA_DIR / "historical_decisions.json"


def _validate_file_exists(file_path: Path) -> None:
    """Validate that the given file exists, raising a clear error if missing."""
    if not file_path.exists():
        raise FileNotFoundError(
            f"Required data file does not exist at: {file_path.resolve()}"
        )
    if not file_path.is_file():
        raise FileNotFoundError(
            f"Expected a file but found directory at: {file_path.resolve()}"
        )


def _read_json_file(file_path: Path) -> dict:
    """Read and parse a JSON file, validating existence and valid syntax."""
    _validate_file_exists(file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as err:
        raise ValueError(
            f"Malformed JSON in file '{file_path.resolve()}': {err}"
        ) from err


def load_historical_decisions(
    filepath: Optional[Union[str, Path]] = None
) -> List[HistoricalDecision]:
    """Load historical decisions from data/historical_decisions.json.

    Args:
        filepath: Optional custom file path. Defaults to data/historical_decisions.json.

    Returns:
        List of HistoricalDecision objects.

    Raises:
        FileNotFoundError: If the data file does not exist.
        ValueError: If JSON is invalid or missing required keys.
    """
    path = Path(filepath) if filepath else HISTORICAL_DECISIONS_PATH
    data = _read_json_file(path)

    raw_decisions = data.get("historical_decisions")
    if raw_decisions is None:
        raise ValueError(
            f"Expected 'historical_decisions' key in '{path.resolve()}'."
        )

    return [HistoricalDecision(**item) for item in raw_decisions]


def load_current_proposals(
    filepath: Optional[Union[str, Path]] = None
) -> List[Proposal]:
    """Load current proposals from data/current_proposals.json.

    Args:
        filepath: Optional custom file path. Defaults to data/current_proposals.json.

    Returns:
        List of Proposal objects.

    Raises:
        FileNotFoundError: If the data file does not exist.
        ValueError: If JSON is invalid or missing required keys.
    """
    path = Path(filepath) if filepath else CURRENT_PROPOSALS_PATH
    data = _read_json_file(path)

    raw_proposals = data.get("current_proposals")
    if raw_proposals is None:
        raise ValueError(
            f"Expected 'current_proposals' key in '{path.resolve()}'."
        )

    return [Proposal(**item) for item in raw_proposals]


def load_company_context(
    filepath: Optional[Union[str, Path]] = None
) -> CompanyContext:
    """Load company context and historical changes from data/company_context.json.

    Args:
        filepath: Optional custom file path. Defaults to data/company_context.json.

    Returns:
        CompanyContext object.

    Raises:
        FileNotFoundError: If the data file does not exist.
        ValueError: If JSON is invalid.
    """
    path = Path(filepath) if filepath else COMPANY_CONTEXT_PATH
    data = _read_json_file(path)
    return CompanyContext(**data)


def get_proposal_by_id(
    proposal_id: str,
    filepath: Optional[Union[str, Path]] = None
) -> Proposal:
    """Retrieve a single proposal by its ID (e.g., 'P001').

    Args:
        proposal_id: The unique identifier of the proposal to find.
        filepath: Optional custom file path.

    Returns:
        Proposal object corresponding to the given proposal_id.

    Raises:
        ValueError: If proposal_id does not exist.
        FileNotFoundError: If the proposals file does not exist.
    """
    if not proposal_id or not proposal_id.strip():
        raise ValueError("A non-empty proposal_id must be provided.")

    target_id = proposal_id.strip().upper()
    proposals = load_current_proposals(filepath)

    for p in proposals:
        if p.proposal_id.strip().upper() == target_id:
            return p

    # Check for component-level proposals (e.g., P005A, P005B, P005C)
    for p in proposals:
        if p.components:
            for c in p.components:
                if c.component_id.strip().upper() == target_id:
                    return Proposal(
                        proposal_id=c.component_id,
                        date=p.date,
                        title=c.title,
                        category=p.category,
                        proposed_by=p.proposed_by,
                        business_problem=f"Part of {p.title} ({p.proposal_id}): {p.business_problem}",
                        proposal=c.description,
                        objectives=p.objectives,
                        current_context=p.current_context,
                        alternatives_considered=p.alternatives_considered,
                        expected_outcome=p.expected_outcome,
                        components=p.components,
                    )

    available_ids = [p.proposal_id for p in proposals]
    component_ids = [
        c.component_id
        for p in proposals
        if p.components
        for c in p.components
    ]
    all_available = available_ids + component_ids
    raise ValueError(
        f"Proposal with ID '{proposal_id}' does not exist. "
        f"Available proposal IDs: {', '.join(all_available)}"
    )


def get_historical_decision_by_id(
    decision_id: str,
    filepath: Optional[Union[str, Path]] = None
) -> HistoricalDecision:
    """Retrieve a single historical decision by its ID (e.g., 'D001').

    Args:
        decision_id: The unique identifier of the decision to find.
        filepath: Optional custom file path.

    Returns:
        HistoricalDecision object corresponding to the given decision_id.

    Raises:
        ValueError: If decision_id does not exist.
        FileNotFoundError: If the historical decisions file does not exist.
    """
    if not decision_id or not decision_id.strip():
        raise ValueError("A non-empty decision_id must be provided.")

    target_id = decision_id.strip().upper()
    decisions = load_historical_decisions(filepath)

    for d in decisions:
        if d.decision_id.strip().upper() == target_id:
            return d

    available_ids = [d.decision_id for d in decisions]
    raise ValueError(
        f"Historical decision with ID '{decision_id}' does not exist. "
        f"Available decision IDs: {', '.join(available_ids)}"
    )


# Convenient alias
get_decision_by_id = get_historical_decision_by_id

