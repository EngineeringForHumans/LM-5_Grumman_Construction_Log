#!/usr/bin/env python3
"""Diff transcripts and emit the review queue.

Two modes:

  passes     Pass A against pass B at the same versions. Where both agree you
             have a decent prior; where they diverge you have a map of the
             spots that need a human eye.

  regression Latest raw run against the verified transcript for the same page.
             This is what a glossary bump buys you: verified pages are ground
             truth, so re-running them measures whether promoted vocabulary
             lowered the model's disagreement with human-checked text or raised
             it. Track the rate per bump, and stop bumping when it stops
             falling — otherwise the loop has no terminus, since there is
             always one more term.

    python tools/diff.py passes --glossary-version 0.2.0
    python tools/diff.py regression

New vocabulary cuts both ways. A term the model used to leave as [illegible] is
a term it can now place confidently on a page that never carried it, so
regression mode reports gains and losses separately. A divergence is a
question, not a correction.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lm5lib import ALNUM, diff_tokens, read_transcript, slug_version, tokenize  # noqa: E402

ILLEGIBLE = ("[illegible", "[?")


def flags_for(a: str, b: str) -> list[dict]:
    out = []
    for op in diff_tokens(a, b):
        if op["tag"] == "equal":
            # Tokens carrying digits get flagged even on agreement. They have
            # no linguistic context to make a wrong reading detectable, which
            # is exactly why agreement means least there.
            for offset, token in enumerate(op["a"]):
                if ALNUM.search(token):
                    out.append(
                        {
                            "kind": "numeric",
                            "token_index": op["a_start"] + offset,
                            "a": token,
                            "b": token,
                            "reason": "both agree, but digits have no context "
                            "that would expose an invention",
                        }
                    )
        else:
            a_text, b_text = " ".join(op["a"]), " ".join(op["b"])
            if any(m in a_text for m in ILLEGIBLE) and not any(
                m in b_text for m in ILLEGIBLE
            ):
                kind = "resolved"  # was unreadable, now confidently placed
            elif any(m in b_text for m in ILLEGIBLE) and not any(
                m in a_text for m in ILLEGIBLE
            ):
                kind = "retreated"  # was placed, now marked unreadable
            else:
                kind = "divergence"
            out.append(
                {
                    "kind": kind,
                    "token_index": op["a_start"],
                    "a": a_text,
                    "b": b_text,
                    "reason": f"sources disagree ({op['tag']})",
                }
            )
    return out


def latest_raw(raw: Path, scan_id: str, gver: str | None, pass_id: str | None) -> Path | None:
    gpart = f"g{slug_version(gver)}" if gver else "*"
    ppart = pass_id or "*"
    runs = sorted(raw.glob(f"{scan_id}.*.{gpart}.{ppart}.md"))
    return runs[-1] if runs else None


def report(rows: list[tuple], label: str) -> None:
    rows.sort(reverse=True)
    print(f"{'page':<24}{label:>12}{'tokens':>9}{'rate':>8}")
    for rate, scan_id, count, total, extra in rows:
        print(f"{scan_id:<24}{count:>12}{total:>9}{rate:>7.1%}   {extra}")
    overall = sum(r[2] for r in rows) / max(1, sum(r[3] for r in rows))
    print(f"\n{len(rows)} pages, {overall:.2%} overall")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["passes", "regression"])
    parser.add_argument("--raw", type=Path, default=Path("raw"))
    parser.add_argument("--verified", type=Path, default=Path("verified"))
    parser.add_argument("--out", type=Path, default=Path("review"))
    parser.add_argument("--glossary-version", dest="gver")
    parser.add_argument("--passes", nargs=2, default=["A", "B"])
    args = parser.parse_args()

    scan_ids = sorted({p.stem.split(".")[0] for p in args.raw.glob("*.md")})
    if not scan_ids:
        raise SystemExit(f"no raw transcripts in {args.raw}")

    rows = []
    for scan_id in scan_ids:
        if args.mode == "passes":
            pa = latest_raw(args.raw, scan_id, args.gver, args.passes[0])
            pb = latest_raw(args.raw, scan_id, args.gver, args.passes[1])
            if not (pa and pb):
                continue
            left, right = read_transcript(pa), read_transcript(pb)
            sources = [pa.name, pb.name]
        else:
            verified = args.verified / f"{scan_id}.md"
            latest = latest_raw(args.raw, scan_id, args.gver, args.passes[0])
            if not (verified.exists() and latest):
                continue
            left, right = read_transcript(latest), read_transcript(verified)
            sources = [latest.name, verified.name]

        flags = flags_for(left.body, right.body)
        total = max(len(tokenize(left.body)), len(tokenize(right.body)))
        counts = {k: sum(1 for f in flags if f["kind"] == k) for k in
                  ("divergence", "resolved", "retreated", "numeric")}
        disagree = counts["divergence"] + counts["resolved"] + counts["retreated"]

        out = args.out / args.mode / f"{scan_id}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "scan_id": scan_id, "mode": args.mode, "sources": sources,
            "glossary_version": left.glossary_version,
            "prompt_version": left.prompt_version,
            "tokens": total, "counts": counts, "flags": flags,
        }, indent=2) + "\n", encoding="utf-8", newline="\n")

        extra = (
            f"+{counts['resolved']} resolved  -{counts['retreated']} retreated"
            if args.mode == "regression" else ""
        )
        rows.append((disagree / total if total else 0.0, scan_id, disagree, total, extra))

    if not rows:
        raise SystemExit("nothing to compare; check --glossary-version and paths")
    report(rows, "disagree")

    if args.mode == "regression":
        print(
            "\nRecord this rate against the glossary_version that produced it. "
            "Falling means the promoted terms helped; flat means stop bumping; "
            "rising means a term is being placed on pages that never carried it."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
