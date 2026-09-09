#!/usr/bin/env python3
"""Harvest candidate glossary terms from verified transcripts.

Reads transcripts with `status: verified`, extracts strings that look like
domain vocabulary, measures how often the model currently gets each one wrong,
and appends them to the candidates queue for you to promote by hand.

    python tools/harvest.py

The direction of flow is the whole point. Candidates come from text a human has
already checked against the scan, so every token in the queue is known to exist
on paper. Nothing the model wrote reaches the prompt without passing through a
person first. Feeding raw output back into the glossary would turn a surname
misread on page 12 into authoritative vocabulary for pages 13 through 130, and
the later pages would agree with it — errors that propagate look like
corroboration, and you lose the inconsistency signal that catches invention.

This script only appends to candidates.yml. It never edits glossary.yml, never
promotes anything, and never writes a definition. You do that.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from ruamel.yaml import YAML

# ruamel, not pyyaml, for candidates.yml. Both files carry a comment header
# that documents the promotion rules, and safe_dump would silently delete it
# on the first write -- taking with it the note that a rejected token without
# a reason gets re-proposed by whoever reads the file next.
_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.width = 100

sys.path.insert(0, str(Path(__file__).parent))
from lm5lib import diff_tokens, load_transcripts, tokenize  # noqa: E402

# Editorial markup and layout scaffolding, not vocabulary.
MARKUP = re.compile(r"^[\[\]<>|#*_\-–—=]+$|^\[(illegible|\?|struck)")
STOPWORDS = {
    "THE", "AND", "FOR", "NOT", "ALL", "PER", "REF", "SEE", "NO", "OF", "TO",
    "IN", "ON", "AT", "BY", "OR", "IS", "AS", "WITH", "FROM", "DATE", "PAGE",
}

PATTERNS = {
    # Runs of capitals: the shape most abbreviations take on these forms.
    "uppercase": re.compile(r"^[A-Z]{2,8}$"),
    # Drawing and sheet numbers: letters, digits, hyphens, at least one of each.
    "part-number": re.compile(r"^(?=.*[A-Z])(?=.*\d)[A-Z0-9][A-Z0-9/-]{3,}$"),
    # Capitalized words that recur — the shape of a surname on a signature line.
    "surname": re.compile(r"^[A-Z][a-z]{2,}(?:[-'][A-Z][a-z]+)*$"),
}


def strip_markup(token: str) -> str:
    return token.strip("[]()<>.,;:|\"'")


def classify(token: str) -> str | None:
    if MARKUP.match(token) or token.upper() in STOPWORDS or len(token) < 3:
        return None
    for kind, pattern in PATTERNS.items():
        if pattern.match(token):
            return kind
    return None


def known_terms(glossary_path: Path) -> set[str]:
    with glossary_path.open(encoding="utf-8") as handle:
        data = _yaml.load(handle) or {}
    known = set()
    for term in data.get("terms", []):
        known.add(str(term["term"]))
        known.update(str(v) for v in (term.get("variants") or []))
        known.update(str(e) for e in (term.get("examples") or []))
    return known


def misread_at(raw_body: str, verified_body: str) -> set[str]:
    """Verified tokens the raw run disagreed with.

    A term the model already reads correctly gains nothing from being added to
    the prompt, so this is the number the promotion trigger keys on rather than
    raw frequency.
    """
    changed = set()
    for op in diff_tokens(raw_body, verified_body):
        if op["tag"] != "equal":
            changed.update(strip_markup(t) for t in op["b"])
    return changed


def latest_machine_run(stitched_dir: Path, raw_dir: Path, scan_id: str) -> Path | None:
    """Most recent machine transcript for a page, preferring stitched output.

    Stitched, not raw. A raw file still holds the band overlap, so a term the
    model misread in one band and got right in the neighbouring band appears in
    both forms; diffing that against verified text finds the correct reading
    and scores the error as zero. That would hide exactly the terms with the
    highest est_pages_fixed, which are the ones worth promoting.
    """
    for directory in (stitched_dir, raw_dir):
        if not directory.exists():
            continue
        runs = sorted(directory.glob(f"{scan_id}.*.md"))
        if runs:
            return runs[-1]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verified", type=Path, default=Path("verified"))
    parser.add_argument("--stitched", type=Path, default=Path("stitched"))
    parser.add_argument("--raw", type=Path, default=Path("raw"))
    parser.add_argument("--glossary", type=Path, default=Path("reference/glossary.yml"))
    parser.add_argument(
        "--candidates", type=Path, default=Path("reference/candidates.yml")
    )
    parser.add_argument(
        "--min-observations",
        type=int,
        default=3,
        help="pages a token needs before est_pages_fixed is computed",
    )
    args = parser.parse_args()

    transcripts = load_transcripts(args.verified, status="verified")
    if not transcripts:
        raise SystemExit(f"no verified transcripts in {args.verified}")

    with args.candidates.open(encoding="utf-8") as handle:
        queue = _yaml.load(handle) or {}
    existing = {c["token"]: c for c in (queue.get("candidates") or [])}
    corpus_pages = queue.get("corpus_pages", len(transcripts))
    known = known_terms(args.glossary)

    pages: dict[str, set[str]] = defaultdict(set)
    misread: dict[str, set[str]] = defaultdict(set)
    kinds: dict[str, str] = {}

    for transcript in transcripts:
        machine = latest_machine_run(args.stitched, args.raw, transcript.scan_id)
        wrong = (
            misread_at(machine.read_text(encoding="utf-8"), transcript.body)
            if machine
            else set()
        )

        for token in tokenize(transcript.body):
            clean = strip_markup(token)
            kind = classify(clean)
            if kind is None or clean in known:
                continue
            kinds.setdefault(clean, kind)
            pages[clean].add(transcript.scan_id)
            if clean in wrong:
                misread[clean].add(transcript.scan_id)

    # A surname is only a surname if it recurs. One capitalized word on one page
    # is more likely a misread than a name, and promoting a misreading is
    # exactly the loop the queue exists to break.
    for token, kind in list(kinds.items()):
        if kind == "surname" and len(pages[token]) < 2:
            del pages[token]

    added, updated = 0, 0
    for token in sorted(pages):
        seen = sorted(pages[token])
        wrong_pages = sorted(misread.get(token, ()))
        est = (
            round(len(wrong_pages) / len(seen) * corpus_pages)
            if len(seen) >= args.min_observations
            else None
        )

        if token in existing:
            entry = existing[token]
            if entry.get("disposition") in {"promoted", "rejected"}:
                continue  # you already ruled on this one
            entry.update(
                pages=len(seen),
                misread_pages=len(wrong_pages),
                est_pages_fixed=est,
                scans=seen,
            )
            updated += 1
        else:
            existing[token] = {
                "token": token,
                "kind_guess": kinds[token],
                "pages": len(seen),
                "misread_pages": len(wrong_pages),
                "est_pages_fixed": est,
                "scans": seen,
                "disposition": "open",
                "note": None,
            }
            added += 1

    ordered = sorted(
        existing.values(),
        key=lambda c: (-(c.get("est_pages_fixed") or 0), -c["pages"], c["token"]),
    )
    queue["candidates"] = ordered
    queue["harvested_through"] = transcripts[-1].scan_id
    # Round-trip in place so the header, inline comments, and any notes you
    # have written by hand survive every harvest.
    with args.candidates.open("w", encoding="utf-8", newline="\n") as handle:
        _yaml.dump(queue, handle)

    open_now = [c for c in ordered if c["disposition"] == "open"]
    solo = [c for c in open_now if (c.get("est_pages_fixed") or 0) >= 15]
    promoted_waiting = sum(1 for c in ordered if c["disposition"] == "promoted")

    print(f"{len(transcripts)} verified pages; {added} new, {updated} updated")
    print(f"{len(open_now)} candidates open\n")
    print(f"{'token':<20}{'kind':<14}{'pages':>7}{'misread':>9}{'est fixed':>11}")
    for c in open_now[:20]:
        est = c["est_pages_fixed"]
        print(
            f"{c['token']:<20}{c['kind_guess']:<14}{c['pages']:>7}"
            f"{c['misread_pages']:>9}{('—' if est is None else est):>11}"
        )

    print()
    if solo:
        print(f"SOLO BUMP: {', '.join(c['token'] for c in solo)} at est_pages_fixed >= 15")
    if promoted_waiting >= 10:
        print(f"BATCH BUMP: {promoted_waiting} promoted terms waiting")
    if not solo and promoted_waiting < 10:
        print(f"No bump. {promoted_waiting}/10 promoted, no term at the solo threshold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
