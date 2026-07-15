"""prereg_cards -- pre-registered hypothesis cards + a mechanical verdict ledger.

The anti-p-hacking workflow, distilled to a standalone library:

    register(card)   -- lock claim + expected sign/magnitude BEFORE outcomes exist
    freeze            -- peek-guard + append-only enforcement in CardRegistry
    grade(card, obs)  -- mechanical CONFIRMED / REJECTED / UNDERPOWERED verdict
    lint_ledger(path) -- flag inflated language or incomplete CONFIRMED rows
"""
from prereg_cards.registry import (
    Card,
    CardRegistry,
    Grader,
    Observation,
    PeekGuardError,
    MutationError,
    record_verdict,
    CONFIRMED,
    REJECTED,
    UNDERPOWERED,
)
from prereg_cards.lint import lint_ledger

__all__ = [
    "Card",
    "CardRegistry",
    "Grader",
    "Observation",
    "PeekGuardError",
    "MutationError",
    "record_verdict",
    "lint_ledger",
    "CONFIRMED",
    "REJECTED",
    "UNDERPOWERED",
]
