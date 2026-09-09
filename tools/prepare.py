#!/usr/bin/env python3
"""Tile page scans into bands and upload them to the Files API.

Reads master scans, splits each into overlapping horizontal bands that fit
under Claude's per-image visual-token cap at native resolution, uploads each
band once, and records the file_ids in a manifest.

Run this once per corpus. It is idempotent: a scan whose bytes have not
changed is skipped, so re-running after adding pages only does the new work.

    python tools/prepare.py --scans scans/ --out derivatives/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from PIL import Image

# Claude reads images as 28x28 patches. An image costs
# ceil(w/28) * ceil(h/28) visual tokens. Opus 5 is high-resolution tier:
# 2576 px long edge, 4784 visual tokens. Anything over either limit is
# downscaled server-side, so we stay under both and keep native pixels.
PATCH = 28
MAX_LONG_EDGE = 2576
MAX_VISUAL_TOKENS = 4784

# Vertical overlap between bands, in pixels. Wide enough that no line of
# handwriting falls entirely in a seam. Tune to your scan resolution.
DEFAULT_OVERLAP = 160

SUFFIXES = {".png", ".tif", ".tiff", ".jpg", ".jpeg", ".webp"}


def visual_tokens(width: int, height: int) -> int:
    """Token cost of an image at these pixel dimensions."""
    return math.ceil(width / PATCH) * math.ceil(height / PATCH)


def max_band_height(width: int) -> int:
    """Tallest band that fits the token cap and the long-edge cap."""
    patches_wide = math.ceil(width / PATCH)
    by_tokens = PATCH * (MAX_VISUAL_TOKENS // patches_wide)
    return max(PATCH, min(by_tokens, MAX_LONG_EDGE))


def plan_bands(width: int, height: int, overlap: int) -> list[tuple[int, int]]:
    """Return (top, bottom) pixel rows for each band, evenly sized."""
    limit = max_band_height(width)
    if height <= limit:
        return [(0, height)]

    stride_max = limit - overlap
    if stride_max <= 0:
        raise ValueError(
            f"overlap {overlap}px exceeds the {limit}px band height for a "
            f"{width}px-wide page; reduce --overlap or downscale the scan"
        )

    count = math.ceil((height - overlap) / stride_max)
    band_h = math.ceil((height + (count - 1) * overlap) / count)
    stride = band_h - overlap

    bands = []
    for i in range(count):
        top = i * stride
        bottom = min(top + band_h, height)
        bands.append((top, bottom))
        if bottom >= height:
            break
    return bands


def fit_width(image: Image.Image) -> Image.Image:
    """Downscale only if the page is wider than the long-edge cap."""
    if image.width <= MAX_LONG_EDGE:
        return image
    scale = MAX_LONG_EDGE / image.width
    size = (MAX_LONG_EDGE, round(image.height * scale))
    return image.resize(size, Image.LANCZOS)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def prepare_scan(
    scan: Path, out_dir: Path, overlap: int, client, dry_run: bool
) -> dict:
    with Image.open(scan) as raw:
        # Convert to RGB so PNG output is predictable across TIFF variants.
        image = fit_width(raw.convert("RGB"))

        bands = plan_bands(image.width, image.height, overlap)
        band_dir = out_dir / scan.stem
        band_dir.mkdir(parents=True, exist_ok=True)

        records = []
        for index, (top, bottom) in enumerate(bands):
            crop = image.crop((0, top, image.width, bottom))
            # PNG, not JPEG. Compression artifacts are the first thing to
            # destroy a struck-through digit, and the docs warn that stacked
            # lossy passes measurably hurt model performance on text.
            band_path = band_dir / f"band_{index:02d}.png"
            crop.save(band_path, format="PNG", optimize=True)

            file_id = None
            if not dry_run:
                with band_path.open("rb") as handle:
                    uploaded = client.files.upload(
                        file=(band_path.name, handle, "image/png")
                    )
                file_id = uploaded.id

            records.append(
                {
                    "index": index,
                    "path": str(band_path),
                    "file_id": file_id,
                    "box": [0, top, image.width, bottom],
                    "width": crop.width,
                    "height": crop.height,
                    "visual_tokens": visual_tokens(crop.width, crop.height),
                }
            )

    return {
        "source": str(scan),
        "sha256": sha256(scan),
        "page_width": image.width,
        "page_height": image.height,
        "overlap": overlap,
        "bands": records,
    }


def is_complete(record: dict, dry_run: bool) -> bool:
    """A page counts as done only if every band has a file_id.

    A dry run produces bands with no file_id. Without this check, matching
    SHA-256 alone would make the real run skip the page as unchanged and it
    would never upload anything.
    """
    if dry_run:
        return True
    return all(band.get("file_id") for band in record["bands"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scans", type=Path, default=Path("scans"))
    parser.add_argument("--out", type=Path, default=Path("derivatives"))
    parser.add_argument("--manifest", type=Path, default=Path("manifest.json"))
    parser.add_argument("--overlap", type=int, default=DEFAULT_OVERLAP)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="tile and report token cost without uploading anything",
    )
    args = parser.parse_args()

    client = None
    if not args.dry_run:
        import anthropic

        client = anthropic.Anthropic()

    manifest = load_manifest(args.manifest)
    scans = sorted(p for p in args.scans.iterdir() if p.suffix.lower() in SUFFIXES)
    if not scans:
        print(f"no scans found in {args.scans}", file=sys.stderr)
        return 1

    total_tokens = 0
    for scan in scans:
        scan_id = scan.stem
        existing = manifest.get(scan_id)
        if (
            existing
            and existing["sha256"] == sha256(scan)
            and is_complete(existing, args.dry_run)
        ):
            total_tokens += sum(b["visual_tokens"] for b in existing["bands"])
            print(f"{scan_id}: unchanged, skipping")
            continue

        record = prepare_scan(scan, args.out, args.overlap, client, args.dry_run)
        manifest[scan_id] = record
        tokens = sum(b["visual_tokens"] for b in record["bands"])
        total_tokens += tokens
        print(f"{scan_id}: {len(record['bands'])} bands, {tokens:,} visual tokens")

    # A dry run is a report, not a state change. Writing a manifest here would
    # leave file_id null on every band, which is worse than writing nothing.
    if args.dry_run:
        print(
            f"\n{len(scans)} pages, {total_tokens:,} image tokens per pass"
            f" (~${total_tokens * 2.50 / 1e6:.2f} per pass at batch rates)"
        )
        print("dry run: no uploads, manifest not written")
        return 0

    args.manifest.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    # Batch input rate is half the $5/M standard rate.
    print(
        f"\n{len(manifest)} pages, {total_tokens:,} image tokens per pass"
        f" (~${total_tokens * 2.50 / 1e6:.2f} per pass at batch rates)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
