#!/usr/bin/env python3
"""Merge band transcripts into whole pages, keeping the seam disagreements.

Each band overlaps its neighbour, so every seam region was transcribed twice
within the same pass. That second reading is free evidence and this script
spends it: where both bands agree, the lines merge silently; where they differ,
both readings survive in the output for you to settle against the scan.

    python tools/stitch.py

Reads raw/, writes stitched/ with the same filenames, so the rest of the
pipeline continues unchanged:

    python tools/diff.py passes --raw stitched/

Stitched files are drafts, not verified text. The script never picks a winner
between two conflicting readings, because choosing is the part that needs a
human and a scan — automating it would silently discard the signal the overlap
exists to produce.
"""

from __future__ import annotations

import argparse
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from lm5lib import read_transcript  # noqa: E402

BAND_SPLIT = re.compile(r"<!--\s*band\s+(\d+)\s*-->")

# An overlap needs at least this many substantive lines to be believable.
MIN_ANCHOR_LINES = 2
# Ceiling on how much of an incoming band can be claimed as overlap.
MAX_OVERLAP_FRACTION = 0.9
# Mean per-line similarity required to accept a candidate overlap.
OVERLAP_THRESHOLD = 0.55
# Similarity is used only to locate the overlap. Whether two aligned rows
# AGREE is an exact test on normalized text: a near match is a disagreement.
# "42 in-lb" and "47 in-lb" score 0.93 similar and are not the same reading,
# and a fuzzy threshold would silently pick one of them.


def trim(lines: list[str]) -> list[str]:
    """Drop leading and trailing blank lines, keep the ones inside.

    The marker split leaves a blank line at each band boundary. Those are an
    artifact of the file format, not of the page, and leaving them in shifts
    the seam alignment by a line.
    """
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def split_bands(body: str) -> list[list[str]]:
    """Split a raw transcript into per-band line lists."""
    parts = BAND_SPLIT.split(body)
    if len(parts) < 3:
        return [trim(body.splitlines())]
    return [trim(parts[i + 1].splitlines()) for i in range(1, len(parts), 2)]


def normalize(line: str) -> str:
    """Compare on collapsed whitespace and case, but keep the original text."""
    return " ".join(line.split()).casefold()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(a=normalize(a), b=normalize(b), autojunk=False).ratio()


def find_overlap(lines_a: list[str], lines_b: list[str]) -> int | None:
    """How many trailing lines of A are the same page rows as B's first lines.

    Matching on identical lines is not enough. The overlap is the region most
    likely to contain a disagreement — one band caught a digit the other
    misread — and those are the seams worth surfacing, so an exact-match anchor
    fails precisely where the evidence is. This scores candidate overlap
    lengths on average line similarity instead, and takes the longest one that
    clears the threshold.
    """
    limit = min(
        len(lines_a),
        max(MIN_ANCHOR_LINES, int(len(lines_b) * MAX_OVERLAP_FRACTION)),
    )
    for size in range(limit, MIN_ANCHOR_LINES - 1, -1):
        tail, head = lines_a[-size:], lines_b[:size]
        if sum(1 for line in tail if line.strip()) < MIN_ANCHOR_LINES:
            continue
        score = sum(similarity(x, y) for x, y in zip(tail, head)) / size
        if score >= OVERLAP_THRESHOLD:
            return size
    return None


def conflict_block(seam: str, upper: list[str], lower: list[str]) -> list[str]:
    out = [f"<!-- seam {seam}: bands disagree, resolve against the scan -->"]
    out += [f"<!-- upper --> {line}" for line in upper]
    out += [f"<!-- lower --> {line}" for line in lower]
    out.append("<!-- /seam -->")
    return out


def reconcile(
    overlap_a: list[str], overlap_b: list[str], seam: str
) -> tuple[list[str], int, int]:
    """Merge an aligned overlap, marking disagreements instead of resolving them.

    Where the two bands read the same row the same way, one copy survives.
    Where they differ, both readings survive side by side. This never picks a
    winner: the whole value of the overlap is that a human sees the two
    readings together, and an automatic choice would spend that evidence to
    save a few seconds.
    """
    out: list[str] = []
    conflicts = same = 0

    for upper, lower in zip(overlap_a, overlap_b):
        if not upper.strip() and not lower.strip():
            out.append(upper)
            continue
        if not upper.strip() or not lower.strip():
            # One band read a row the other left blank, typically a line
            # clipped at a band edge.
            out.append(f"<!-- seam {seam}: only one band read this row -->")
            out.append(upper if upper.strip() else lower)
            conflicts += 1
            continue
        if normalize(upper) == normalize(lower):
            out.append(upper)
            same += 1
        else:
            out += conflict_block(seam, [upper], [lower])
            conflicts += 1

    # Alignment is by length, so any ragged remainder belongs to whichever
    # band is longer and is kept rather than dropped.
    for extra in overlap_a[len(overlap_b):] + overlap_b[len(overlap_a):]:
        if extra.strip():
            out.append(f"<!-- seam {seam}: only one band read this row -->")
            out.append(extra)
            conflicts += 1

    return out, conflicts, same


def stitch(bands: list[list[str]]) -> tuple[list[str], int, int, int]:
    """Fold bands into one page. Returns lines, conflicts, agreed, unaligned."""
    merged = list(bands[0])
    conflicts = agreed = unaligned = 0

    for index, lines_b in enumerate(bands[1:], start=1):
        seam = f"{index - 1}/{index}"
        size = find_overlap(merged, lines_b)
        if size is None:
            # No overlap detected. A blank strip between entries will do this,
            # and so will a genuinely missed overlap; concatenating is safe but
            # the seam is unverified, so say so rather than hide it.
            merged.append(f"<!-- seam {seam}: no overlap found, bands concatenated -->")
            merged.extend(lines_b)
            unaligned += 1
            continue

        overlap_a, overlap_b = merged[-size:], lines_b[:size]
        reconciled, found, same = reconcile(overlap_a, overlap_b, seam)
        agreed += same
        conflicts += found
        merged = merged[:-size] + reconciled + lines_b[size:]

    return merged, conflicts, agreed, unaligned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("raw"))
    parser.add_argument("--out", type=Path, default=Path("stitched"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    sources = sorted(args.raw.glob("*.md"))
    if not sources:
        raise SystemExit(f"no raw transcripts in {args.raw}")

    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    total_conflicts = 0

    for source in sources:
        transcript = read_transcript(source)
        bands = split_bands(transcript.body)
        lines, conflicts, agreed, unaligned = stitch(bands)
        total_conflicts += conflicts

        meta = dict(transcript.meta)
        meta.update(
            scan_id=transcript.scan_id,
            status="stitched",
            bands=len(bands),
            seam_conflicts=conflicts,
            seam_lines_agreed=agreed,
            seams_unaligned=unaligned,
        )
        header = (
            "---\n"
            + yaml.safe_dump(meta, sort_keys=False, allow_unicode=True)
            + "---\n"
        )

        target = args.out / source.name
        if target.exists() and not args.force:
            print(f"{source.name}: exists, skipping (use --force)")
            continue
        target.write_text(
            header + "\n".join(lines).rstrip() + "\n",
            encoding="utf-8",
            newline="\n",
        )
        rows.append((conflicts, source.name, len(bands), agreed, unaligned))

    rows.sort(reverse=True)
    print(f"{'file':<34}{'bands':>6}{'agreed':>8}{'conflicts':>11}{'unaligned':>11}")
    for conflicts, name, bands, agreed, unaligned in rows:
        print(f"{name:<34}{bands:>6}{agreed:>8}{conflicts:>11}{unaligned:>11}")

    print(f"\n{len(rows)} pages stitched, {total_conflicts} seam conflicts to resolve")
    if total_conflicts:
        print("grep -n 'seam' stitched/*.md to find them")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
