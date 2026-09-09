#!/usr/bin/env python3
"""Poll a batch, validate every result, and write the raw transcripts.

Output lands at raw/{scan_id}.p{prompt_version}.g{glossary_version}.{pass}.md
and is never edited by hand. Versioned filenames matter: a second run under a
new glossary version must not overwrite the first, because the comparison
between them is exactly what you are paying for. This script refuses to clobber
an existing raw file, and never touches anything under verified/ — machine
output does not overwrite human work.

    python tools/collect.py --batch msgbatch_...

Batch results stay available for 29 days, so run this and commit the output
well before then.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import anthropic

CUSTOM_ID = re.compile(
    r"^(?P<scan>.+)_b(?P<band>\d+)_p(?P<prompt>[^_]+)_g(?P<gloss>[^_]+)_(?P<pass>[^_]+)$"
)

# Opus 5 batch rates, in dollars per million tokens.
RATE_INPUT = 2.50
RATE_OUTPUT = 12.50
RATE_CACHE_WRITE_1H = 5.00
RATE_CACHE_READ = 0.25


def wait_for(client, batch_id: str, poll: int) -> None:
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        if batch.processing_status == "ended":
            print(f"batch ended: {counts}")
            return
        print(
            f"  {batch.processing_status}: {counts.succeeded} done, "
            f"{counts.processing} in flight, {counts.errored} errored",
            file=sys.stderr,
        )
        time.sleep(poll)


def text_of(message) -> str:
    return "".join(b.text for b in message.content if b.type == "text").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--out", type=Path, default=Path("raw"))
    parser.add_argument("--poll", type=int, default=60)
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument(
        "--force", action="store_true", help="allow overwriting an existing raw file"
    )
    args = parser.parse_args()

    client = anthropic.Anthropic()
    if not args.no_wait:
        wait_for(client, args.batch, args.poll)

    bands: dict[tuple[str, str, str, str], dict[int, str]] = defaultdict(dict)
    usage: dict[str, int] = defaultdict(int)
    failures: list[str] = []

    for result in client.messages.batches.results(args.batch):
        cid = result.custom_id
        parsed = CUSTOM_ID.match(cid)
        if not parsed:
            failures.append(f"{cid}: unparseable custom_id")
            continue

        if result.result.type != "succeeded":
            failures.append(f"{cid}: {result.result.type}")
            continue

        message = result.result.message

        # A transcript cut off at max_tokens is indistinguishable from a page
        # that ends early. Refuse it rather than let silent truncation into the
        # corpus.
        if message.stop_reason == "max_tokens":
            failures.append(f"{cid}: truncated at max_tokens, raise the cap and re-run")
            continue

        key = (parsed["scan"], parsed["prompt"], parsed["gloss"], parsed["pass"])
        bands[key][int(parsed["band"])] = text_of(message)

        usage["input"] += message.usage.input_tokens
        usage["output"] += message.usage.output_tokens
        usage["cache_write"] += getattr(message.usage, "cache_creation_input_tokens", 0) or 0
        usage["cache_read"] += getattr(message.usage, "cache_read_input_tokens", 0) or 0

    args.out.mkdir(parents=True, exist_ok=True)
    written = 0
    for (scan_id, pver, gver, pass_id), by_index in sorted(bands.items()):
        path = args.out / f"{scan_id}.p{pver}.g{gver}.{pass_id}.md"
        if path.exists() and not args.force:
            failures.append(f"{path.name}: already exists, refusing to overwrite")
            continue

        # Bands stay separate and labelled. Resolving the overlap is a human
        # decision during verification: silently dropping a duplicated line is
        # an edit, and edits do not belong in raw output.
        body = "\n\n".join(
            f"<!-- band {i} -->\n{by_index[i]}" for i in sorted(by_index)
        )
        header = (
            "---\n"
            f'scan_id: "{scan_id}"\n'
            "status: raw\n"
            f"prompt_version: {pver}\n"
            f"glossary_version: {gver}\n"
            f"pass: {pass_id}\n"
            f"batch_id: {args.batch}\n"
            "---\n"
        )
        path.write_text(header + body + "\n", encoding="utf-8", newline="\n")
        written += 1

    cost = (
        usage["input"] * RATE_INPUT
        + usage["output"] * RATE_OUTPUT
        + usage["cache_write"] * RATE_CACHE_WRITE_1H
        + usage["cache_read"] * RATE_CACHE_READ
    ) / 1e6

    print(f"\nwrote {written} page-passes to {args.out}")
    print(
        f"tokens: {usage['input']:,} in, {usage['output']:,} out, "
        f"{usage['cache_write']:,} cache write, {usage['cache_read']:,} cache read"
    )
    print(f"cost: ${cost:.2f}")

    if failures:
        print(f"\n{len(failures)} FAILURES:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
