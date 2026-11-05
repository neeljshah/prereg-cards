"""Demo: register 5 hypothesis cards on synthetic data, freeze, grade, lint.

Two cards have planted effects, two have null effects, and one is too small
for the sample-size floor. Grading uses sign and magnitude only; no statistical
significance test is performed and no p-values are supplied. Run:

    python examples/demo_workflow.py
"""
from __future__ import annotations

import random
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prereg_cards import Card, CardRegistry, Grader, Observation, record_verdict
from prereg_cards.lint import lint_ledger

WINDOW_OPENS = 1_000_000.0  # epoch seconds the evaluation window opens
REGISTERED_AT = WINDOW_OPENS - 3600  # supplied timestamp in the synthetic example


def make_card(claim: str, sign: str, magnitude: float, entity: str, trigger: str) -> Card:
    return Card(
        claim=claim,
        expected_sign=sign,
        expected_magnitude=magnitude,
        condition={
            "entity": entity,
            "scope": "experiment",
            "trigger": trigger,
            "window": {"opens_ts": WINDOW_OPENS},
        },
        mechanism="synthetic demo -- see examples/demo_workflow.py",
        registered_ts=REGISTERED_AT,
    )


def synthetic_observation(true_effect: float, n: int, seed: int) -> Observation:
    rng = random.Random(seed)
    samples = [true_effect + rng.gauss(0, 1.0) for _ in range(n)]
    mean = statistics.mean(samples)
    sign = "+" if mean >= 0 else "-"
    return Observation(n=n, observed_sign=sign, observed_magnitude=abs(mean), p_value=None)


def main() -> None:
    print("Synthetic demo: sign/magnitude grading only; no significance test or p-values.")
    tmp = Path(tempfile.mkdtemp(prefix="prereg_demo_"))
    cards_path = tmp / "cards.jsonl"
    ledger_path = tmp / "ledger.jsonl"
    registry = CardRegistry(cards_path)
    grader = Grader(n_min=30)

    # (claim, expected_sign, expected_magnitude, true_effect, n) -- true_effect
    # is what generates the data; two are planted nulls (0.0).
    specs = [
        ("treatment A raises response vs control", "+", 0.4, 0.5, 200),   # true effect
        ("treatment B lowers response vs control", "-", 0.3, -0.35, 150), # true effect
        ("treatment C raises response vs control", "+", 0.4, 0.0, 200),   # planted null
        ("treatment D lowers response vs control", "-", 0.3, 0.0, 150),   # planted null
        ("treatment E raises response, small n", "+", 0.4, 0.5, 10),      # underpowered
    ]

    print("=== registering 5 cards with supplied pre-window timestamps ===")
    cards = []
    for i, (claim, sign, mag, _, _) in enumerate(specs):
        card = make_card(claim, sign, mag, entity=f"group_{i}", trigger="synthetic_trigger")
        registry.register(card)
        cards.append(card)
        print(f"  registered {card.card_id}  {claim!r}")

    print("\n=== grading synthetic observations ===")
    for i, (card, (_, _, _, true_effect, n)) in enumerate(zip(cards, specs)):
        observed = synthetic_observation(true_effect, n, seed=i)
        verdict_row = grader.grade(card, observed)
        record_verdict(ledger_path, verdict_row)
        print(f"  {verdict_row['verdict']:12s} n={verdict_row['n']:4d}  {card.claim}")

    print("\n=== honesty lint on the ledger ===")
    violations = lint_ledger(ledger_path)
    if violations:
        print(f"  FAILED: {len(violations)} violation(s)")
        for v in violations:
            print(f"    {v}")
    else:
        print("  clean: 0 violations")

    print(f"\ncards:  {cards_path}")
    print(f"ledger: {ledger_path}")


if __name__ == "__main__":
    main()
