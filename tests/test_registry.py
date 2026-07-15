"""Tests for prereg_cards: id stability, append-only, peek-guard, grading, lint."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from prereg_cards import (
    Card, CardRegistry, Grader, Observation, PeekGuardError, MutationError,
    record_verdict, CONFIRMED, REJECTED, UNDERPOWERED,
)

WINDOW = {"opens_ts": 1000.0}


def make_card(registered_ts: float = 900.0, claim: str = "X raises Y when Z") -> Card:
    return Card(
        claim=claim,
        expected_sign="+",
        expected_magnitude=0.3,
        condition={"entity": "e1", "scope": "test", "trigger": "t1", "window": dict(WINDOW)},
        mechanism="unit test",
        registered_ts=registered_ts,
    )


def test_content_sha_id_stable():
    c1 = make_card()
    c2 = make_card()
    assert c1.card_id == c2.card_id
    assert len(c1.card_id) == 16


def test_different_claim_different_id():
    c1 = make_card(claim="claim A")
    c2 = make_card(claim="claim B")
    assert c1.card_id != c2.card_id


def test_register_and_read_back(tmp_path):
    reg = CardRegistry(tmp_path / "cards.jsonl")
    card = make_card()
    reg.register(card)
    row = reg.get(card.card_id)
    assert row is not None
    assert row["claim"] == card.claim


def test_append_only_reregister_same_content_is_noop(tmp_path):
    reg = CardRegistry(tmp_path / "cards.jsonl")
    card = make_card()
    reg.register(card)
    reg.register(make_card())  # identical content -> same id, idempotent, must not raise
    lines = (tmp_path / "cards.jsonl").read_text(encoding="ascii").splitlines()
    assert len(lines) == 1  # no duplicate row written


def test_mutation_error_on_forged_duplicate_id(tmp_path):
    reg = CardRegistry(tmp_path / "cards.jsonl")
    card = make_card()
    reg.register(card)
    forged = Card(
        claim=card.claim,
        expected_sign=card.expected_sign,
        expected_magnitude=999.0,  # different content
        condition=card.condition,
        mechanism="forged",
        registered_ts=card.registered_ts,
        card_id=card.card_id,  # force the same id
    )
    with pytest.raises(MutationError):
        reg.register(forged)


def test_peek_guard_refuses_late_registration(tmp_path):
    reg = CardRegistry(tmp_path / "cards.jsonl")
    late_card = make_card(registered_ts=1500.0)  # after window opened at 1000
    with pytest.raises(PeekGuardError):
        reg.register(late_card)


def test_peek_guard_allows_registration_before_window():
    card = make_card(registered_ts=999.0)
    assert card.registered_ts <= card.condition["window"]["opens_ts"]


def test_grade_confirmed():
    card = make_card()
    grader = Grader(n_min=30)
    obs = Observation(n=100, observed_sign="+", observed_magnitude=0.5, p_value=0.01)
    verdict = grader.grade(card, obs)
    assert verdict["verdict"] == CONFIRMED


def test_grade_rejected_wrong_sign():
    card = make_card()
    grader = Grader(n_min=30)
    obs = Observation(n=100, observed_sign="-", observed_magnitude=0.5, p_value=0.01)
    verdict = grader.grade(card, obs)
    assert verdict["verdict"] == REJECTED


def test_grade_rejected_too_small_magnitude():
    card = make_card()
    grader = Grader(n_min=30)
    obs = Observation(n=100, observed_sign="+", observed_magnitude=0.05, p_value=0.01)
    verdict = grader.grade(card, obs)
    assert verdict["verdict"] == REJECTED


def test_grade_underpowered():
    card = make_card()
    grader = Grader(n_min=30)
    obs = Observation(n=5, observed_sign="+", observed_magnitude=0.5, p_value=0.01)
    verdict = grader.grade(card, obs)
    assert verdict["verdict"] == UNDERPOWERED


def test_lint_catches_planted_inflation_word(tmp_path):
    from prereg_cards.lint import lint_ledger

    ledger = tmp_path / "ledger.jsonl"
    clean_row = {"card_id": "abc", "verdict": REJECTED, "reason": "sign mismatch", "n": 50, "p": 0.4}
    inflated_row = {"card_id": "def", "verdict": CONFIRMED,
                     "reason": "this proves a guaranteed edge", "n": 50, "p": 0.01}
    with ledger.open("w", encoding="ascii") as f:
        f.write(json.dumps(clean_row) + "\n")
        f.write(json.dumps(inflated_row) + "\n")

    violations = lint_ledger(ledger)
    assert any("guarantee" in v for v in violations) or any("edge" in v for v in violations)


def test_lint_clean_ledger_has_no_violations(tmp_path):
    from prereg_cards.lint import lint_ledger

    ledger = tmp_path / "ledger.jsonl"
    row = {"card_id": "abc", "verdict": CONFIRMED, "reason": "sign and magnitude matched", "n": 50, "p": 0.02}
    with ledger.open("w", encoding="ascii") as f:
        f.write(json.dumps(row) + "\n")
    assert lint_ledger(ledger) == []


def test_lint_flags_confirmed_missing_n(tmp_path):
    from prereg_cards.lint import lint_ledger

    ledger = tmp_path / "ledger.jsonl"
    row = {"card_id": "abc", "verdict": CONFIRMED, "reason": "ok", "p": 0.02}
    with ledger.open("w", encoding="ascii") as f:
        f.write(json.dumps(row) + "\n")
    violations = lint_ledger(ledger)
    assert any("missing 'n'" in v for v in violations)
