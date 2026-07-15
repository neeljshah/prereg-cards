"""prereg_cards.lint -- honesty linter for a verdict ledger.

Pre-registration only kills p-hacking if the WRITE-UP stays honest too. This
lint catches the two most common ways a ledger gets quietly inflated:

  1. Result-inflation language in free-text fields ("guarantee", "edge",
     "roi", "profit", "proven beyond", ...).
  2. A CONFIRMED verdict missing the n/p fields a reader would need to judge
     it themselves.

Stdlib only. Exit 0 = clean, exit 1 = violations found (also printed).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

INFLATION_WORDS = (
    "guarantee", "guaranteed", "edge", "roi", "profit", "proven beyond",
    "definitely", "no doubt", "risk-free",
)
_word_res = [re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE) for w in INFLATION_WORDS]

_TEXT_FIELDS = ("reason", "claim", "notes")


def _free_text(row: dict) -> str:
    return " ".join(str(row.get(f, "")) for f in _TEXT_FIELDS)


def lint_ledger(path: str | Path) -> list[str]:
    """Return a list of violation strings for the ledger JSONL at *path*."""
    path = Path(path)
    violations: list[str] = []
    if not path.is_file():
        return [f"{path}: not a file"]

    for lineno, line in enumerate(path.read_text(encoding="ascii", errors="replace").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            violations.append(f"{path}:{lineno}: invalid JSON ({exc})")
            continue

        text = _free_text(row)
        for word, rx in zip(INFLATION_WORDS, _word_res):
            if rx.search(text):
                violations.append(
                    f"{path}:{lineno}: inflation word '{word}' in card {row.get('card_id', '?')}"
                )

        if row.get("verdict") == "CONFIRMED":
            if row.get("n") in (None, "") or "n" not in row:
                violations.append(f"{path}:{lineno}: CONFIRMED row missing 'n' field")
            if "p" not in row:
                violations.append(f"{path}:{lineno}: CONFIRMED row missing 'p' field")

    return violations


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m prereg_cards.lint <ledger.jsonl>")
        return 2
    violations = lint_ledger(argv[0])
    if not violations:
        print("lint clean: 0 violations")
        return 0
    print(f"lint FAILED: {len(violations)} violation(s)")
    for v in violations:
        print(f"  {v}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
