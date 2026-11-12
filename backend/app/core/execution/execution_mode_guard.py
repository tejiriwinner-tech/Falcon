"""
Falcon V10 Phase 5F: Canonical Execution Mode Guard & Metadata Parser.

Establishes:
1. Canonical execution modes: PAPER (default), LIVE.
2. Canonical metadata tokens: [MODE:PAPER], [MODE:LIVE].
3. Single authoritative parser for execution-mode metadata.
4. Hard fail-closed safety gate: LIVE requires explicit affirmative configuration.
5. Strict prohibition against automated broker order execution.
"""

from enum import Enum
import logging
import os
import re
from typing import Any, Optional, Union

from app.core.config.settings import settings

logger = logging.getLogger("falcon.execution_mode_guard")

# Exact canonical metadata tokens stored in TradeJournalRecord.notes
TOKEN_PAPER: str = "[MODE:PAPER]"
TOKEN_LIVE: str = "[MODE:LIVE]"

# Strict token matching pattern: exact square brackets, uppercase mode
_TOKEN_PATTERN = re.compile(r"\[MODE:(PAPER|LIVE)\]")


class ExecutionForbiddenError(RuntimeError):
    """Raised whenever unauthorized or automated live broker execution is attempted."""
    pass


class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


def parse_execution_mode(notes: Optional[str]) -> Optional[str]:
    """
    Single canonical parser for trade journal execution-mode metadata.

    Invariants:
    1. If notes is None or empty: returns None (unclassified / historical record).
    2. Uses exact canonical metadata tokens: [MODE:PAPER] and [MODE:LIVE].
    3. Ordinary text (e.g. 'trading live on gold') CANNOT activate LIVE.
    4. Malformed tokens (e.g. '[MODE:LIVEE]', '[mode:live]') fail closed to None.
    5. Conflicting or duplicate tokens (e.g. both [MODE:PAPER] and [MODE:LIVE])
       fail closed to None (never accidentally LIVE).
    6. Returns strictly 'PAPER', 'LIVE', or None.
    """
    if not notes or not isinstance(notes, str):
        return None

    matches = _TOKEN_PATTERN.findall(notes)
    if not matches:
        return None

    # Check for duplicate distinct tokens (ambiguity / tampering)
    unique_modes = set(matches)
    if len(unique_modes) > 1:
        logger.warning(
            f"Ambiguous execution mode tokens detected in notes: {matches}. Failing closed to None."
        )
        return None

    # If exactly one distinct mode was matched
    mode = matches[0].upper()
    if mode in (ExecutionMode.PAPER.value, ExecutionMode.LIVE.value):
        return mode

    return None


def resolve_record_execution_mode(
    execution_mode: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[str]:
    """
    Authoritative, deterministic resolution of trade record execution mode.
    Native execution_mode field is primary; notes token [MODE:PAPER] / [MODE:LIVE] is legacy/secondary.

    Invariants & Fail-Safe Behavior:
    1. If execution_mode is an unknown/malformed string (e.g. 'FOO', 'LIVE_TEST'):
       Fails closed to None.
    2. If execution_mode and notes token both exist and CONFLICT (e.g. LIVE vs [MODE:PAPER]):
       Fails closed to None (ambiguous/tampered record). Never accidentally LIVE.
    3. If execution_mode is valid ('PAPER' or 'LIVE'):
       - If notes token matches or is absent: returns execution_mode.
    4. If execution_mode is absent or None:
       - Falls back to notes token parse_execution_mode(notes).
    5. If notes is None or contains no valid token, and execution_mode is None:
       - Returns None (unclassified historical record).
    6. Returns strictly 'PAPER', 'LIVE', or None.
    """
    if execution_mode is not None:
        if not isinstance(execution_mode, str):
            return None
        clean_field = execution_mode.strip().upper()
        if clean_field not in (ExecutionMode.PAPER.value, ExecutionMode.LIVE.value):
            logger.warning(f"Unknown executionMode field '{execution_mode}'. Failing closed to None.")
            return None
    else:
        clean_field = None

    parsed_token = parse_execution_mode(notes)

    # Conflict check: If both field and token are present but disagree, fail closed to None
    if clean_field is not None and parsed_token is not None and clean_field != parsed_token:
        logger.warning(
            f"Execution mode conflict detected: field='{clean_field}' vs notes token='{parsed_token}'. "
            "Failing closed to None."
        )
        return None

    if clean_field is not None:
        return clean_field

    return parsed_token


def is_live_record(record_or_item: Any) -> bool:
    """True strictly if record is unambiguously classified as LIVE."""
    mode = getattr(record_or_item, "executionMode", getattr(record_or_item, "execution_mode", None))
    notes = getattr(record_or_item, "notes", None)
    return resolve_record_execution_mode(mode, notes) == ExecutionMode.LIVE.value


def is_paper_record(record_or_item: Any) -> bool:
    """True strictly if record is unambiguously classified as PAPER."""
    mode = getattr(record_or_item, "executionMode", getattr(record_or_item, "execution_mode", None))
    notes = getattr(record_or_item, "notes", None)
    return resolve_record_execution_mode(mode, notes) == ExecutionMode.PAPER.value


def format_mode_token(mode: Union[ExecutionMode, str]) -> str:
    """Format canonical execution mode token."""
    mode_str = mode.value if isinstance(mode, ExecutionMode) else str(mode).upper()
    if mode_str == ExecutionMode.LIVE.value:
        return TOKEN_LIVE
    return TOKEN_PAPER


def inject_mode_token(notes: Optional[str], mode: Union[ExecutionMode, str]) -> str:
    """
    Inject canonical execution mode token into notes string.
    Preserves existing text and avoids duplicate injection.
    """
    token = format_mode_token(mode)
    if not notes:
        return token
    if token in notes:
        return notes
    return f"{notes.strip()} {token}".strip()


class ExecutionModeGuard:
    """
    Hard safety guard managing system-wide execution mode and preventing
    automated broker trading.
    """

    @staticmethod
    def get_system_mode() -> ExecutionMode:
        """
        Resolve the authoritative system execution mode.

        Fail-closed rules:
        1. Default is strictly PAPER.
        2. LIVE requires:
           - settings.EXECUTION_MODE == 'LIVE'
           - settings.LIVE_EXECUTION_ACKNOWLEDGED is True
        3. Any missing, malformed, or ambiguous value fails closed to PAPER.
        """
        configured_mode = getattr(settings, "EXECUTION_MODE", "PAPER")
        if not isinstance(configured_mode, str):
            logger.warning("EXECUTION_MODE is not a string. Failing closed to PAPER.")
            return ExecutionMode.PAPER

        mode_clean = configured_mode.strip().upper()
        if mode_clean != ExecutionMode.LIVE.value:
            # Any non-LIVE setting (including 'PAPER', arbitrary strings, empty) is PAPER
            return ExecutionMode.PAPER

        # Mode is configured as LIVE: verify explicit affirmative acknowledgment
        ack = getattr(settings, "LIVE_EXECUTION_ACKNOWLEDGED", False)
        if ack is not True:
            logger.warning(
                "EXECUTION_MODE is LIVE but LIVE_EXECUTION_ACKNOWLEDGED is not True. "
                "Failing closed to PAPER."
            )
            return ExecutionMode.PAPER

        return ExecutionMode.LIVE

    @classmethod
    def is_live_authorized(cls) -> bool:
        """Return True strictly if LIVE execution mode is explicitly authorized."""
        return cls.get_system_mode() == ExecutionMode.LIVE

    @classmethod
    def is_paper_mode(cls) -> bool:
        """Return True if system is in PAPER mode."""
        return cls.get_system_mode() == ExecutionMode.PAPER

    @classmethod
    def is_paper(cls) -> bool:
        """Alias for is_paper_mode."""
        return cls.is_paper_mode()

    @classmethod
    def is_live(cls) -> bool:
        """Alias for is_live_authorized."""
        return cls.is_live_authorized()

    @classmethod
    def is_broker_locked(cls) -> bool:
        """Return True: broker automation is hard-locked / prohibited."""
        return True

    @classmethod
    def assert_live_execution_permitted(cls) -> None:
        """Assert that live broker execution is permitted. Fails closed under PAPER or unacknowledged live."""
        if not cls.is_live_authorized():
            raise ExecutionForbiddenError(
                "ExecutionForbiddenError: Live broker execution is prohibited while in PAPER mode or unacknowledged."
            )
        cls.assert_no_broker_automation("live_execution_check")

    @staticmethod
    def assert_no_broker_automation(context: Optional[str] = None) -> None:
        """
        Hard invariant: Falcon is a decision-support system.
        Automated broker order placement, modification, closure, or cancellation
        is strictly prohibited.
        """
        msg = (
            "AUTOMATED_BROKER_EXECUTION_BLOCKED: Falcon is a decision-support system; "
            "automated broker execution is strictly prohibited. "
            "Automated order placement, modification, cancellation, or management "
            "on MT5 or Exness is strictly prohibited."
        )
        if context:
            msg = f"{msg} Context: {context}"
        raise ExecutionForbiddenError(msg)


def assert_no_broker_automation(context: Optional[str] = None) -> None:
    """Module-level alias for ExecutionModeGuard.assert_no_broker_automation."""
    ExecutionModeGuard.assert_no_broker_automation(context)


execution_mode_guard = ExecutionModeGuard()
