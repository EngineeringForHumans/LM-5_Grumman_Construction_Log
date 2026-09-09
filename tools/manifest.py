#!/usr/bin/env python3
"""Build manifest.csv from the scans on disk.

    python3 tools/manifest.py                  # write manifest.csv
    python3 tools/manifest.py --check          # exit 1 if it's out of date
    python3 tools/manifest.py --dry-run

The manifest is the authoritative list of pages in the log. Everything else
joins on it: promote.py refuses a scan_id that isn't listed, and the site
renders one page per row, including rows with no transcript yet.

Deriving it from scans/ rather than typing it means the list can't drift from
what you actually photographed. Run --check in CI so a scan added without a
manifest row fails the build instead of quietly vanishing from the site.

Rows you have to fill in yourself
---------------------------------
`sequence` is the reading order, which is just the sorted position unless the
binding disagrees with the filenames. `notes` is empty and stays empty unless a
page needs a caveat that belongs to the page rather than the transcript: a
missing leaf, a photograph taken at an angle, a page numbered twice in 1969.

Editing a generated row by hand is fine. --check compares the scan_id column
only, so your edits to other columns survive a regeneration.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
FIELDS = ("scan_id", "sequence", "scan_file", "notes")


def scan_ids(scans_dir: Path) -> list[tuple[str, str]]:
    """Every image in scans/, as (scan_id, filename), in sorted order."""
    found: dict[str, str] = {}
    for path in sorted(scans_dir.iterdir()):
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        scan_id = path.stem
        if scan_id in found:
            print(
                f"warning: {path.name} and {found[scan_id]} share the id {scan_id!r}; "
                f"keeping {found[scan_id]}",
                file=sys.stderr,
            )
            continue
        found[scan_id] = path.name
    return sorted(found.items())


def existing_rows(manifest: Path) -> dict[str, dict]:
    if not manifest.exists():
        return {}
    with manifest.open(encoding="utf-8", newline="") as handle:
        return {r["scan_id"]: r for r in csv.DictReader(handle) if r.get("scan_id")}


def build(root: Path) -> list[dict]:
    """Merge what's on disk with whatever a previous manifest recorded."""
    pairs = scan_ids(root / "scans")
    previous = existing_rows(root / "manifest.csv")

    rows = []
    for index, (scan_id, filename) in enumerate(pairs, start=1):
        old = previous.get(scan_id, {})
        rows.append(
            {
                "scan_id": scan_id,
                "sequence": old.get("sequence") or str(index),
                "scan_file": filename,
                "notes": old.get("notes", ""),
            }
        )
    return rows


def write(manifest: Path, rows: list[dict]) -> None:
    # newline="" for csv, LF endings to match .gitattributes. Without both, the
    # file flips line endings every time it's regenerated on Windows and every
    # row shows as changed in git.
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    scans = root / "scans"
    if not scans.is_dir():
        print(f"error: no scans directory at {scans}", file=sys.stderr)
        return 1

    rows = build(root)
    if not rows:
        print(f"error: no images found in {scans}", file=sys.stderr)
        return 1

    manifest = root / "manifest.csv"
    on_disk = list(existing_rows(manifest))
    derived = [r["scan_id"] for r in rows]

    if args.check:
        missing = [s for s in derived if s not in on_disk]
        extra = [s for s in on_disk if s not in derived]
        for scan_id in missing:
            print(f"scan present but not in manifest: {scan_id}")
        for scan_id in extra:
            print(f"manifest row with no scan: {scan_id}")
        if missing or extra:
            print(f"\nmanifest.csv is out of date. Run: python3 tools/manifest.py")
            return 1
        print(f"manifest.csv matches {len(derived)} scans")
        return 0

    if args.dry_run:
        print(f"would write {len(rows)} rows to {manifest}")
        for row in rows[:3]:
            print(f"  {row}")
        if len(rows) > 3:
            print(f"  ... and {len(rows) - 3} more")
        return 0

    write(manifest, rows)
    kept = len([r for r in rows if r["scan_id"] in on_disk])
    print(f"wrote {len(rows)} rows to manifest.csv ({kept} already present, edits preserved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
