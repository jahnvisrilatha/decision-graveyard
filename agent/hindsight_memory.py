"""Hindsight Memory Integration for Decision Graveyard.

Provides a persistent memory layer using the official hindsight-client:
1. Creating/connecting to a Hindsight memory bank.
2. Retaining organizational decision memories with rich context and metadata.
3. Recalling relevant memories for current proposals.
4. Reflecting on organizational patterns for deeper synthesis.

Configuration is loaded from environment variables:
- HINDSIGHT_API_KEY
- HINDSIGHT_BASE_URL
- HINDSIGHT_BANK_ID

Never hardcodes API keys.
"""

import asyncio
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from agent.data_loader import load_historical_decisions
from agent.models import HistoricalDecision, Proposal

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_BASE_URL = "http://localhost:8888"
DEFAULT_BANK_ID = "decision-graveyard"
DEFAULT_MISSION = (
    "Retain and synthesize organizational decision history, past project outcomes, "
    "constraints, failure causes, and architectural trade-offs to help Product Managers."
)


class _HindsightLoopRunner:
    """Manages a dedicated background thread running a persistent asyncio event loop.

    This ensures that Hindsight SDK's aiohttp ClientSession and connection pools are bound
    to a permanent, non-closing event loop, completely avoiding both 'Timeout context manager
    should be used inside a task' and 'Event loop is closed' errors across repeated API requests.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="HindsightAsyncRunner")
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def run(self, coro_fn, *args, **kwargs):
        async def _wrapper():
            return await coro_fn(*args, **kwargs)
        fut = asyncio.run_coroutine_threadsafe(_wrapper(), self._loop)
        return fut.result(timeout=120)


class HindsightMemory:
    """Wrapper and manager for Hindsight persistent memory operations."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        bank_id: Optional[str] = None,
    ):
        """Initialize the Hindsight Memory Manager.

        Args:
            api_key: Optional Hindsight API key (defaults to HINDSIGHT_API_KEY env var).
            base_url: Optional Hindsight server URL (defaults to HINDSIGHT_BASE_URL env var or localhost).
            bank_id: Optional target memory bank ID (defaults to HINDSIGHT_BANK_ID env var or 'decision-graveyard').
        """
        self.api_key = api_key or os.getenv("HINDSIGHT_API_KEY")
        self.base_url = base_url or os.getenv("HINDSIGHT_BASE_URL", DEFAULT_BASE_URL)
        self.bank_id = bank_id or os.getenv("HINDSIGHT_BANK_ID", DEFAULT_BANK_ID)

        self._client = None
        logger.info(
            f"HindsightMemory initialized for bank '{self.bank_id}' at '{self.base_url}'"
        )

    def get_client(self):
        """Lazily initialize and return the official Hindsight client."""
        if self._client is None:
            try:
                from hindsight_client import Hindsight

                self._client = Hindsight(
                    base_url=self.base_url,
                    api_key=self.api_key if self.api_key and not self._is_placeholder(self.api_key) else None,
                )
            except ImportError as e:
                logger.error("hindsight-client is not installed. Run `pip install hindsight-client`.")
                raise RuntimeError("hindsight-client package is required.") from e
        return self._client

    def _execute_async(self, coro_fn, *args, **kwargs):
        """Execute an asynchronous Hindsight SDK method on the persistent event loop runner."""
        runner = _HindsightLoopRunner.get_instance()
        return runner.run(coro_fn, *args, **kwargs)

    def _is_placeholder(self, key: Optional[str]) -> bool:
        """Check if an API key is just an unset placeholder."""
        if not key:
            return True
        placeholders = ["your_hindsight_api_key_here", "placeholder", "changeme"]
        return any(p in key.lower() for p in placeholders)

    def is_configured(self) -> bool:
        """Check if Hindsight configuration is available."""
        return bool(self.base_url and self.bank_id)

    # -----------------------------------------------------------------------
    # 1. Bank Connection & Setup
    # -----------------------------------------------------------------------

    def ensure_bank_exists(
        self,
        bank_id: Optional[str] = None,
        mission: Optional[str] = None,
    ) -> bool:
        """Ensure the target memory bank exists, creating it if necessary.

        Args:
            bank_id: Target bank ID. Defaults to configured self.bank_id.
            mission: Optional mission statement for the memory bank.

        Returns:
            True if bank exists or was created, False on failure.
        """
        target_bank = bank_id or self.bank_id
        client = self.get_client()
        target_mission = mission or DEFAULT_MISSION

        try:
            # Check if bank already exists
            if hasattr(client, "aget_bank_config"):
                self._execute_async(client.aget_bank_config, bank_id=target_bank)
            else:
                client.get_bank_config(bank_id=target_bank)
            logger.info(f"Hindsight bank '{target_bank}' exists and is ready.")
            return True
        except Exception:
            # Bank does not exist or needs creation
            try:
                logger.info(f"Creating Hindsight memory bank: '{target_bank}'...")
                if hasattr(client, "acreate_bank"):
                    self._execute_async(
                        client.acreate_bank,
                        bank_id=target_bank,
                        name="Decision Graveyard",
                        mission=target_mission,
                    )
                else:
                    client.create_bank(
                        bank_id=target_bank,
                        name="Decision Graveyard",
                        mission=target_mission,
                    )
                logger.info(f"Successfully created Hindsight bank '{target_bank}'.")
                return True
            except Exception as create_err:
                logger.warning(
                    f"Could not connect to or create Hindsight bank '{target_bank}' at {self.base_url}: {create_err}"
                )
                return False

    # -----------------------------------------------------------------------
    # 2. Retain Organizational Decision Memories
    # -----------------------------------------------------------------------

    def format_decision_for_retention(self, decision: HistoricalDecision) -> str:
        """Format a HistoricalDecision into a rich, structured natural-language memory for Hindsight.

        Includes all key attributes: identification, problem, proposal, alternatives,
        rationale, expected and actual outcomes, drivers/failure causes, constraints,
        lessons learned, and related decisions.
        """
        parts = [
            f"Decision ID: {decision.decision_id}",
            f"Date: {decision.date}",
            f"Title: {decision.title}",
            f"Category: {decision.category}",
            f"Status: {decision.status}",
            f"Business Problem: {decision.business_problem}",
            f"Proposal: {decision.proposal}",
        ]

        if decision.alternatives_considered:
            alts = (
                ", ".join(decision.alternatives_considered)
                if isinstance(decision.alternatives_considered, list)
                else str(decision.alternatives_considered)
            )
            parts.append(f"Alternatives Considered: {alts}")

        parts.append(f"Chosen Option: {decision.chosen_option}")

        reasoning_str = (
            ", ".join(decision.reasoning)
            if isinstance(decision.reasoning, list)
            else str(decision.reasoning)
        )
        parts.append(f"Reasoning: {reasoning_str}")

        parts.append(f"Expected Outcome: {decision.expected_outcome}")
        parts.append(f"Actual Outcome: {decision.actual_outcome}")

        if decision.failure_reasons:
            parts.append(f"Failure / Abandonment Reasons: {', '.join(decision.failure_reasons)}")
        if decision.success_factors:
            parts.append(f"Success Factors: {', '.join(decision.success_factors)}")
        if decision.rejection_reasons:
            parts.append(f"Rejection Reasons: {', '.join(decision.rejection_reasons)}")

        if decision.constraints:
            constraints_str = (
                ", ".join(decision.constraints)
                if isinstance(decision.constraints, list)
                else str(decision.constraints)
            )
            parts.append(f"Constraints: {constraints_str}")

        parts.append(f"Lesson Learned: {decision.lesson_learned}")

        if decision.related_decisions:
            parts.append(f"Related Prior Decisions: {', '.join(decision.related_decisions)}")

        return "\n".join(parts)

    def retain_decision(
        self,
        decision: HistoricalDecision,
        bank_id: Optional[str] = None,
        update_mode: str = "replace",
    ) -> Dict[str, Any]:
        """Retain a single historical decision into Hindsight.

        Args:
            decision: HistoricalDecision model to retain.
            bank_id: Target bank ID.
            update_mode: 'replace' (idempotent, default) or 'append'.

        Returns:
            Dict containing retain status and details.
        """
        target_bank = bank_id or self.bank_id
        client = self.get_client()

        content = self.format_decision_for_retention(decision)
        metadata = {
            "decision_id": str(decision.decision_id),
            "title": str(decision.title),
            "category": str(decision.category),
            "status": str(decision.status),
            "date": str(decision.date),
        }
        tags = [
            "historical-decision",
            f"decision-{decision.decision_id.lower()}",
            decision.category.lower().replace(" ", "-"),
            decision.status.lower(),
        ]

        try:
            if hasattr(client, "aretain"):
                response = self._execute_async(
                    client.aretain,
                    bank_id=target_bank,
                    content=content,
                    document_id=decision.decision_id,
                    metadata=metadata,
                    tags=tags,
                )
            else:
                response = client.retain(
                    bank_id=target_bank,
                    content=content,
                    document_id=decision.decision_id,
                    metadata=metadata,
                    tags=tags,
                    update_mode=update_mode,
                )
            logger.info(f"Retained decision {decision.decision_id} into bank '{target_bank}'")
            return {
                "success": getattr(response, "success", True),
                "decision_id": decision.decision_id,
                "bank_id": target_bank,
            }
        except Exception as e:
            logger.warning(f"Failed to retain decision {decision.decision_id} to Hindsight: {e}")
            return {
                "success": False,
                "decision_id": decision.decision_id,
                "error": str(e),
            }

    def retain_decisions_batch(
        self,
        decisions: List[HistoricalDecision],
        bank_id: Optional[str] = None,
        update_mode: str = "replace",
    ) -> Dict[str, Any]:
        """Retain multiple historical decisions into Hindsight memory.

        Args:
            decisions: List of HistoricalDecision objects.
            bank_id: Target bank ID.
            update_mode: 'replace' (idempotent, default) or 'append'.

        Returns:
            Dict with counts of succeeded and failed retain operations.
        """
        target_bank = bank_id or self.bank_id
        self.ensure_bank_exists(target_bank)

        successful = []
        failed = []

        for decision in decisions:
            res = self.retain_decision(decision, bank_id=target_bank, update_mode=update_mode)
            if res.get("success"):
                successful.append(decision.decision_id)
            else:
                failed.append({"id": decision.decision_id, "error": res.get("error")})

        logger.info(
            f"Hindsight batch retain completed. Success: {len(successful)}, Failed: {len(failed)}"
        )
        return {
            "total": len(decisions),
            "retained_count": len(successful),
            "failed_count": len(failed),
            "retained_ids": successful,
            "failures": failed,
        }

    def ingest_historical_decisions(
        self,
        bank_id: Optional[str] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """Load and ingest all historical organizational decisions into Hindsight memory.

        Idempotency:
        Each decision is stored with document_id set to its unique decision_id
        (e.g., 'D001') and update_mode set to 'replace'. Running this function
        repeatedly updates existing memories for that decision rather than
        creating uncontrolled duplicates.

        Args:
            bank_id: Target memory bank ID (defaults to self.bank_id).
            verbose: Whether to print progress messages during ingestion.

        Returns:
            Dictionary with counts and status of ingestion:
            {
                "total_processed": int,
                "retained_count": int,
                "failed_count": int,
                "successful_ids": list,
                "failures": list,
            }
        """
        target_bank = bank_id or self.bank_id
        self.ensure_bank_exists(target_bank)

        # 1. Load historical decisions using data_loader
        decisions = load_historical_decisions()
        total = len(decisions)

        successful_ids = []
        failures = []

        for decision in decisions:
            if verbose:
                print(f"Ingesting {decision.decision_id}...")

            res = self.retain_decision(
                decision=decision,
                bank_id=target_bank,
                update_mode="replace",
            )

            if res.get("success"):
                successful_ids.append(decision.decision_id)
            else:
                failures.append({
                    "decision_id": decision.decision_id,
                    "error": res.get("error"),
                })

        if verbose:
            print("\n" + "=" * 45)
            print("Historical Decisions Ingestion Summary")
            print("=" * 45)
            print(f"Number of decisions processed: {total}")
            print(f"Number successfully retained:  {len(successful_ids)}")
            print(f"Number failed:                 {len(failures)}")
            if failures:
                print("\nFailed decisions:")
                for f in failures:
                    print(f"  - {f['decision_id']}: {f['error']}")
            print("=" * 45)

        return {
            "total_processed": total,
            "retained_count": len(successful_ids),
            "failed_count": len(failures),
            "successful_ids": successful_ids,
            "failures": failures,
        }

    # -----------------------------------------------------------------------
    # 3. Recall Relevant Memories for Proposals
    # -----------------------------------------------------------------------

    def recall_memories(
        self,
        query: str,
        bank_id: Optional[str] = None,
        max_tokens: int = 4096,
        types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Recall relevant memories from Hindsight using semantic query.

        Args:
            query: The query text to search memory against.
            bank_id: Target bank ID.
            max_tokens: Maximum tokens of memory context to retrieve.
            types: Optional list of memory types (e.g. ['observation', 'fact']).

        Returns:
            List of recalled memory units formatted as dictionaries.
        """
        target_bank = bank_id or self.bank_id
        client = self.get_client()

        try:
            if hasattr(client, "arecall"):
                response = self._execute_async(
                    client.arecall,
                    bank_id=target_bank,
                    query=query,
                    max_tokens=max_tokens,
                    types=types,
                )
            else:
                response = client.recall(
                    bank_id=target_bank,
                    query=query,
                    max_tokens=max_tokens,
                    types=types,
                )

            results = []
            for item in getattr(response, "results", []):
                results.append({
                    "id": getattr(item, "id", None),
                    "document_id": getattr(item, "document_id", None),
                    "text": getattr(item, "text", ""),
                    "metadata": getattr(item, "metadata", {}) or {},
                    "tags": getattr(item, "tags", []) or [],
                    "type": getattr(item, "type", None),
                })
            return results

        except Exception as e:
            logger.warning(f"Hindsight recall failed for query '{query[:50]}...': {e}")
            try:
                response = client.recall(
                    bank_id=target_bank,
                    query=query,
                    max_tokens=max_tokens,
                    types=types,
                )
                results = []
                for item in getattr(response, "results", []):
                    results.append({
                        "id": getattr(item, "id", None),
                        "document_id": getattr(item, "document_id", None),
                        "text": getattr(item, "text", ""),
                        "metadata": getattr(item, "metadata", {}) or {},
                        "tags": getattr(item, "tags", []) or [],
                        "type": getattr(item, "type", None),
                    })
                return results
            except Exception as e2:
                logger.warning(f"Hindsight fallback recall also failed: {e2}")
                return []

    def recall_for_proposal(
        self,
        proposal: Proposal,
        bank_id: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> List[Dict[str, Any]]:
        """Formulate a query from a current proposal and recall relevant historical decisions.

        Args:
            proposal: The Proposal object to query memory for.
            bank_id: Target bank ID.
            max_tokens: Maximum tokens to retrieve.

        Returns:
            List of recalled historical memory units.
        """
        query_parts = [
            f"Proposal Title: {proposal.title}",
            f"Category: {proposal.category}",
            f"Problem: {proposal.business_problem}",
            f"Proposed Solution: {proposal.proposal}",
        ]
        if proposal.objectives:
            query_parts.append(f"Objectives: {', '.join(proposal.objectives)}")

        query = "\n".join(query_parts)
        return self.recall_memories(query=query, bank_id=bank_id, max_tokens=max_tokens)

    # -----------------------------------------------------------------------
    # 4. Hindsight Reflect (Analytical Synthesis)
    # -----------------------------------------------------------------------

    def reflect(
        self,
        query: str,
        context: Optional[str] = None,
        bank_id: Optional[str] = None,
        budget: str = "low",
    ) -> Optional[Dict[str, Any]]:
        """Call Hindsight Reflect to synthesize patterns across retained decisions.

        Args:
            query: Question or synthesis prompt for the memory bank.
            context: Additional context to guide reflection.
            bank_id: Target bank ID.
            budget: Computation budget ('low', 'mid', 'high').

        Returns:
            Dictionary containing reflection response and synthesized text.
        """
        target_bank = bank_id or self.bank_id
        client = self.get_client()

        try:
            if hasattr(client, "areflect"):
                response = self._execute_async(
                    client.areflect,
                    bank_id=target_bank,
                    query=query,
                    context=context,
                    budget=budget,
                )
            else:
                response = client.reflect(
                    bank_id=target_bank,
                    query=query,
                    context=context,
                    budget=budget,
                )
            return {
                "text": getattr(response, "text", str(response)),
                "raw": getattr(response, "response", None),
            }
        except Exception as e:
            logger.warning(f"Hindsight reflect failed: {e}")
            return None


def ingest_historical_decisions(
    bank_id: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Module-level convenience function to ingest historical decisions into Hindsight.

    Instantiates HindsightMemory and delegates to ingest_historical_decisions().

    Args:
        bank_id: Optional target memory bank ID.
        api_key: Optional Hindsight API key.
        base_url: Optional Hindsight server URL.
        verbose: Whether to print progress messages during ingestion.

    Returns:
        Dictionary with counts and status of ingestion.
    """
    memory = HindsightMemory(api_key=api_key, base_url=base_url, bank_id=bank_id)
    return memory.ingest_historical_decisions(bank_id=bank_id, verbose=verbose)

