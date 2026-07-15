"""prereg_cards.registry -- pre-registered hypothesis cards + a mechanical grader.

A CARD is one conditional claim ("X happens WHEN condition C holds"),
written down and hashed BEFORE any outcome is looked at. This module enforces
the two invariants that make a card pre-registered rather than a post-hoc
rationalization of data you already saw:

  1. PEEK GUARD -- a card's registered_ts must be at or before the moment its
     evaluation window opens. Register it after the window opened (i.e. after
     outcomes could already be known) and registration is refused.
  2. APPEND-ONLY -- once a card_id exists in the ledger, its claim/condition/
     expected_sign/expected_magnitude can never be changed. The id is a
     content hash, so any real change produces a new id; calling register()
     again with the SAME id and DIFFERENT content is refused outright.

Grading is mechanical: verdict = f(expected_sign, expected_magnitude, n_min,
observed). No free-text judgment call changes a verdict after the fact.

Stdlib only. ASCII only.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

VALID_SIGNS = {"+", "-"}
DEFAULT_N_MIN = 30

CONFIRMED = "CONFIRMED"
REJECTED = "REJECTED"
UNDERPOWERED = "UNDERPOWERED"


class PeekGuardError(ValueError):
    """Raised when a card is registered after its evaluation window opened."""


class MutationError(ValueError):
    """Raised when a register() call would silently change an existing card."""


def _content_hash(claim: str, expected_sign: str, expected_magnitude: float,
                   condition: dict) -> str:
    payload = json.dumps(
        {"claim": claim, "expected_sign": expected_sign,
         "expected_magnitude": expected_magnitude, "condition": condition},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Card:
    """One pre-registered hypothesis.

    condition: {"entity": str, "scope": str, "trigger": str, "window": {...}}
    window must carry "opens_ts" -- the epoch-seconds moment outcomes for this
    card become knowable. registered_ts must be <= window["opens_ts"].
    """
    claim: str
    expected_sign: str
    expected_magnitude: float
    condition: dict
    mechanism: str
    registered_ts: float
    outcomes_peeked: bool = False
    card_id: str = field(default="")

    def __post_init__(self) -> None:
        if self.expected_sign not in VALID_SIGNS:
            raise ValueError(f"expected_sign must be one of {VALID_SIGNS}")
        if not self.claim.strip():
            raise ValueError("claim must be non-empty")
        if "window" not in self.condition or "opens_ts" not in self.condition["window"]:
            raise ValueError("condition.window.opens_ts is required")
        if self.registered_ts is None:
            raise ValueError("registered_ts is required (pre-registration timestamp)")
        if not self.card_id:
            object.__setattr__(
                self, "card_id",
                _content_hash(self.claim, self.expected_sign,
                              self.expected_magnitude, self.condition),
            )

    def to_dict(self) -> dict:
        return asdict(self)


class CardRegistry:
    """Append-only JSONL store of Card rows at *path*.

    Readers take the latest row per card_id; the earlier row is never
    overwritten, so a refused mutation attempt is still auditable on disk
    (the caller's attempted row simply never gets appended).
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _latest_rows(self) -> dict[str, dict]:
        if not self.path.is_file():
            return {}
        latest: dict[str, dict] = {}
        for line in self.path.read_text(encoding="ascii", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            latest[row["card_id"]] = row
        return latest

    def register(self, card: Card) -> Card:
        """Append *card*. Enforces the peek guard and append-only invariant."""
        if card.registered_ts > card.condition["window"]["opens_ts"]:
            raise PeekGuardError(
                f"card {card.card_id}: registered_ts {card.registered_ts} is after "
                f"window opened at {card.condition['window']['opens_ts']} -- "
                "outcomes could already be known, refusing to register"
            )
        existing = self._latest_rows().get(card.card_id)
        if existing is not None:
            # Same content -> same hash -> idempotent no-op is fine. Anything
            # that produced the SAME id but different fields would mean the
            # hash is being spoofed by a caller passing card_id explicitly;
            # refuse rather than silently accept a mutated row under an old id.
            if existing != card.to_dict():
                raise MutationError(
                    f"card {card.card_id} already registered; refusing to overwrite "
                    "with different content -- register a new card instead"
                )
            return card
        with self.path.open("a", encoding="ascii", newline="\n") as f:
            f.write(json.dumps(card.to_dict(), sort_keys=True) + "\n")
        return card

    def mark_peeked(self, card_id: str) -> None:
        """Flip outcomes_peeked=True. The only field mutation permitted post-hoc."""
        rows = self._latest_rows()
        if card_id not in rows:
            raise KeyError(f"unknown card_id: {card_id}")
        row = dict(rows[card_id])
        row["outcomes_peeked"] = True
        with self.path.open("a", encoding="ascii", newline="\n") as f:
            f.write(json.dumps(row, sort_keys=True) + "\n")

    def get(self, card_id: str) -> dict | None:
        return self._latest_rows().get(card_id)

    def all_cards(self) -> list[dict]:
        return list(self._latest_rows().values())


@dataclass
class Observation:
    """What was actually measured, looked at only AFTER the window opened."""
    n: int
    observed_sign: str
    observed_magnitude: float
    p_value: float | None = None


class Grader:
    """Mechanical CONFIRMED / REJECTED / UNDERPOWERED verdicts. No judgment calls."""

    def __init__(self, n_min: int = DEFAULT_N_MIN):
        self.n_min = n_min

    def grade(self, card: Card, observed: Observation) -> dict:
        if observed.n < self.n_min:
            verdict = UNDERPOWERED
            reason = f"n={observed.n} < n_min={self.n_min}"
        elif (observed.observed_sign == card.expected_sign
              and abs(observed.observed_magnitude) >= abs(card.expected_magnitude)):
            verdict = CONFIRMED
            reason = "sign matched and magnitude met expectation"
        else:
            verdict = REJECTED
            reason = "sign mismatch or magnitude fell short of registration"
        return {
            "card_id": card.card_id,
            "claim": card.claim,
            "verdict": verdict,
            "reason": reason,
            "n": observed.n,
            "p": observed.p_value,
            "expected_sign": card.expected_sign,
            "expected_magnitude": card.expected_magnitude,
            "observed_sign": observed.observed_sign,
            "observed_magnitude": observed.observed_magnitude,
        }


def record_verdict(ledger_path: str | Path, verdict_row: dict) -> None:
    """Append one verdict row to the (append-only) ledger JSONL."""
    path = Path(ledger_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="ascii", newline="\n") as f:
        f.write(json.dumps(verdict_row, sort_keys=True) + "\n")
