"""
Falcon Signal Lifecycle

Defines the complete lifecycle states of a trading signal.
"""
from enum import Enum
from typing import Literal


class SignalStatus(str, Enum):
    """Signal lifecycle status enumeration."""
    
    # Initial state - signal has been generated but not yet activated
    GENERATED = "GENERATED"
    
    # Signal is active and waiting for entry trigger
    ACTIVE = "ACTIVE"
    
    # Entry has been triggered, position is open
    TRIGGERED = "TRIGGERED"
    
    # Take Profit 1 has been hit
    TP1_HIT = "TP1_HIT"
    
    # Take Profit 2 has been hit
    TP2_HIT = "TP2_HIT"
    
    # Take Profit 3 has been hit
    TP3_HIT = "TP3_HIT"
    
    # Stop Loss has been hit
    SL_HIT = "SL_HIT"
    
    # Signal has expired without being triggered
    EXPIRED = "EXPIRED"
    
    # Signal has been manually closed
    CLOSED = "CLOSED"
    
    # Signal was cancelled before execution
    CANCELLED = "CANCELLED"


# Valid status transitions
VALID_TRANSITIONS = {
    SignalStatus.GENERATED: [SignalStatus.ACTIVE, SignalStatus.CANCELLED],
    SignalStatus.ACTIVE: [SignalStatus.TRIGGERED, SignalStatus.EXPIRED, SignalStatus.CANCELLED, SignalStatus.CLOSED],
    SignalStatus.TRIGGERED: [SignalStatus.TP1_HIT, SignalStatus.TP2_HIT, SignalStatus.TP3_HIT, SignalStatus.SL_HIT, SignalStatus.CLOSED, SignalStatus.CANCELLED],
    SignalStatus.TP1_HIT: [SignalStatus.TP2_HIT, SignalStatus.TP3_HIT, SignalStatus.SL_HIT, SignalStatus.CLOSED],
    SignalStatus.TP2_HIT: [SignalStatus.TP3_HIT, SignalStatus.SL_HIT, SignalStatus.CLOSED],
    SignalStatus.TP3_HIT: [SignalStatus.CLOSED],
    SignalStatus.SL_HIT: [SignalStatus.CLOSED],
    SignalStatus.EXPIRED: [SignalStatus.CLOSED],
    SignalStatus.CANCELLED: [],
    SignalStatus.CLOSED: [],
}


def is_valid_transition(current_status: SignalStatus, new_status: SignalStatus) -> bool:
    """
    Check if a status transition is valid.
    
    Args:
        current_status: Current signal status
        new_status: Desired new status
        
    Returns:
        True if the transition is valid
    """
    valid_next_statuses = VALID_TRANSITIONS.get(current_status, [])
    return new_status in valid_next_statuses


def get_terminal_statuses() -> list[SignalStatus]:
    """Get all terminal statuses that cannot transition further."""
    return [SignalStatus.CANCELLED, SignalStatus.CLOSED]


def is_terminal_status(status: SignalStatus) -> bool:
    """Check if a status is terminal (no further transitions possible)."""
    return status in get_terminal_statuses()


def get_active_statuses() -> list[SignalStatus]:
    """Get all statuses that represent an active or potentially active signal."""
    return [
        SignalStatus.GENERATED,
        SignalStatus.ACTIVE,
        SignalStatus.TRIGGERED,
        SignalStatus.TP1_HIT,
        SignalStatus.TP2_HIT,
    ]
