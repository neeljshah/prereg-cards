# prereg-cards

Pre-registered hypothesis cards + an honesty-linted verdict ledger -- a small,
standalone implementation of the anti-p-hacking workflow: **write the claim,
the expected direction, and the expected size down BEFORE you look at the
outcome, then let a mechanical grader (not you) decide the verdict.**

This workflow comes from CourtVision, a four-sport forecasting system audited in public; the measured results and the retraction record are in its evidence index: https://github.com/neeljshah/court-vision/blob/master/EVIDENCE.md

No sports, no finance, no ROI numbers. This is a general-purpose forecasting
/ experimentation discipline: it applies equally to a marketing A/B test, a
product growth hypothesis, or a scientific claim.

## Why pre-registration kills p-hacking

The failure mode this defends against is familiar: you run an experiment,
look at the results, notice *something* moved, and retroactively describe
that as "what you expected all along." With enough metrics and enough
slicing, *something* always looks significant -- that is p-hacking / the
multiple-comparisons problem, not a discovery.

The fix is mechanical, not disciplinary:

1. **Register the claim before outcomes exist.** A `Card` locks the claim
   text, the expected sign (`+`/`-`), the expected magnitude, and the
   condition under which it should hold -- all timestamped with
   `registered_ts`. The registry's **peek guard** refuses to register a card
   whose `registered_ts` is after its evaluation window already opened: you
   cannot pre-register something you already had the chance to look at.
2. **Freeze it.** The registry is **append-only JSONL**. A card's id is a
   content hash of its claim/sign/magnitude/condition, so a genuine edit
   produces a new id -- the old row is untouched on disk forever. Attempting
   to reuse an existing id with different content is refused outright
   (`MutationError`).
3. **Grade it mechanically.** `Grader.grade(card, observed)` compares the
   observed sign and magnitude against what was registered and returns
   `CONFIRMED`, `REJECTED`, or `UNDERPOWERED` (below the pre-set sample-size
   floor). There is no free-text field that can override this -- the verdict
   is a pure function of the two things that were locked in step 1 plus what
   was actually measured.
4. **Lint the ledger.** `lint_ledger()` scans every verdict row's free text
   for inflation language ("guarantee", "edge", "roi", "profit", "proven
   beyond", ...) and flags any `CONFIRMED` row missing the `n` / `p` fields a
   reader would need to judge it themselves. A verdict can be mechanically
   correct and still get written up dishonestly -- the lint is the second
   check, not a substitute for the first.

## Workflow

```
register(card)  ->  freeze (peek-guard + append-only)  ->  grade(card, observed)  ->  ledger  ->  lint
```

```python
from prereg_cards import Card, CardRegistry, Grader, Observation, record_verdict
from prereg_cards.lint import lint_ledger

card = Card(
    claim="treatment A raises response vs control",
    expected_sign="+",
    expected_magnitude=0.4,
    condition={"entity": "group_a", "scope": "experiment", "trigger": "signup_flow_v2",
               "window": {"opens_ts": 1_700_000_000.0}},
    mechanism="v2 flow removes a form field, should lift completion",
    registered_ts=1_699_996_000.0,  # BEFORE the window opens
)

registry = CardRegistry("cards.jsonl")
registry.register(card)                      # raises PeekGuardError if registered too late

# ... time passes, the window closes, you measure what actually happened ...

observed = Observation(n=412, observed_sign="+", observed_magnitude=0.31, p_value=0.02)
verdict = Grader(n_min=30).grade(card, observed)
record_verdict("ledger.jsonl", verdict)       # {"verdict": "REJECTED", ...} -- magnitude fell short

print(lint_ledger("ledger.jsonl"))            # [] if the write-up stayed honest
```

Run the end-to-end demo (5 synthetic cards, mixed true/false hypotheses):

```
python examples/demo_workflow.py
```

It registers 5 cards, grades them against synthetic data where 2 have a real
underlying effect and 2 are planted nulls (plus one deliberately
underpowered), and prints honest `REJECTED` / `UNDERPOWERED` verdicts for the
hypotheses that don't hold -- exactly what a pre-registered process is
supposed to produce.

## Where this came from

This library distills a pattern from a larger private system (the CourtVision registry).
No counts from that system are claimed here; this repository ships the workflow and its tests.

This repo contains no proprietary data, code, or domain logic from that
system -- it is a clean-room, generic reimplementation of the one underlying
mechanism (peek-guarded pre-registration + append-only freeze + mechanical
grading + honesty lint) using synthetic data and a domain-neutral example.

## Install / test

```
pip install -e .
python -m pytest tests/test_registry.py -q
```

Stdlib only. No network calls, no external dependencies for the library
itself (`pytest` is a dev-only extra for running the tests).

## Author

Neel Shah -- [neeljshah22@gmail.com](mailto:neeljshah22@gmail.com) --
[github.com/neeljshah](https://github.com/neeljshah)

## License

MIT, see [LICENSE](LICENSE).
