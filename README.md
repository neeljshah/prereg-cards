# prereg-cards

Record hypothesis cards before a supplied evaluation-window timestamp, then
append mechanical verdicts to a JSONL ledger. Writing down direction and
magnitude first makes changes to a claim visible within this workflow.

The library uses only the Python standard library. It provides a local record
and rule-based grader; it does not conduct a statistical significance test.

## Install

Requires Python 3.9 or later.

```bash
git clone https://github.com/neeljshah/prereg-cards.git
cd prereg-cards
python -m pip install -e ".[dev]"
```

The `dev` extra installs pytest; use `-e .` for the library alone.

## Runnable example

```bash
python examples/demo_workflow.py
```

The seeded synthetic demo has two planted effects, two null effects and one
sample below the size floor. Its stable console output is:

```text
Synthetic demo: sign/magnitude grading only; no significance test or p-values.
=== registering 5 cards with supplied pre-window timestamps ===
  registered 6bd380b866f43919  'treatment A raises response vs control'
  registered e654987e7aac0a48  'treatment B lowers response vs control'
  registered 7f0d56b398f6b99f  'treatment C raises response vs control'
  registered 0579dad439977e7b  'treatment D lowers response vs control'
  registered 0c1cd511e1aaf16b  'treatment E raises response, small n'

=== grading synthetic observations ===
  CONFIRMED    n= 200  treatment A raises response vs control
  CONFIRMED    n= 150  treatment B lowers response vs control
  REJECTED     n= 200  treatment C raises response vs control
  REJECTED     n= 150  treatment D lowers response vs control
  UNDERPOWERED n=  10  treatment E raises response, small n

=== honesty lint on the ledger ===
  clean: 0 violations
```

The final two lines print the generated `cards.jsonl` and `ledger.jsonl` paths
in a temporary directory; those paths vary on each run. The files remain there
for inspection. Each observation records `"p": null` because no p-value was
computed. Exit code 0 means the demo completed.

## Workflow and API

1. Construct a `Card` with a claim, expected sign (`+` or `-`), expected
   magnitude, condition, mechanism and registration timestamp. Its default ID
   hashes the claim, sign, magnitude and condition.
2. Call `CardRegistry(path).register(card)`. The supplied registration timestamp
   must be at or before `condition["window"]["opens_ts"]`; later values raise
   `PeekGuardError`. An identical repeated registration is a no-op. Reusing an
   existing ID with different content raises `MutationError`.
3. Call `Grader(n_min=30).grade(card, observation)`. Below the sample-size floor,
   the verdict is `UNDERPOWERED`. Otherwise, matching the expected sign and
   reaching the expected absolute magnitude yields `CONFIRMED`; other outcomes
   are `REJECTED`.
4. Append the result with `record_verdict(path, row)`. Inspect it with
   `lint_ledger(path)` or `python -m prereg_cards.lint <ledger.jsonl>`.

`Observation.p_value` is optional metadata. The grader records it but does not
use it to choose a verdict. `CONFIRMED` means the registered sign/magnitude rules
were met, not that an effect is statistically significant. `UNDERPOWERED` means
only that `n` is below the configured floor; it is not a power calculation.

## Scope and limits

- Timestamps are **caller assertions**, not a trusted external timestamp
  authority. The library does not check the wall clock or prove that a caller
  had not already seen outcomes.
- The registry appends through its API. It does not prevent direct file edits,
  authenticate authors or coordinate concurrent writers. Preserve an external
  audit record when tamper evidence is required.
- The default content ID excludes the mechanism and registration timestamp.
  `mark_peeked` appends a row marking outcomes as viewed; readers return the
  latest row for each ID.
- The linter checks configured wording and required fields. It permits a null
  `p` field and does not validate the underlying experiment, statistical test
  or truth of a claim. A clean lint result is not evidence of an effect.

## Tests

```bash
python -m pytest tests/test_registry.py -q
```

The 14 tests cover content IDs, registration and readback, repeated and forged
registrations, the supplied-timestamp guard, grading and ledger lint. GitHub
Actions runs this file with a two-minute test timeout.

## Context and license

[The CourtVision evidence site](https://neeljshah.github.io/court-vision/)
contains the forecasting results and public retraction record. Its moneyline
models land near the devigged close without beating it; totals and tennis trail.

[MIT](LICENSE), copyright Neel Shah 2026.
