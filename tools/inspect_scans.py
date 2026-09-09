#!/usr/bin/env python3
"""Audit source scan quality before you transcribe anything.

Reports dimensions, DPI, and a JPEG compression estimate for every scan, then
optionally dumps 1:1 crops so you can look at actual pixels rather than trust a
number.

    python tools/inspect_scans.py --scans scans/
    python tools/inspect_scans.py --scans scans/ --crops samples/

The compression estimate reads the JPEG luma quantization table. Lower means
less aggressive compression. Calibrated against Pillow's quality settings:

    ~6 = quality 95    ~29 = quality 75    ~58 = quality 50
    ~17 = quality 85   ~46 = quality 60    ~96 = quality 30

Below about quality 70, expect thin strokes and struck-through digits to start
dissolving into blocking artifacts. No model recovers what compression removed,
so a low number here sets a ceiling on the accuracy of everything downstream.
"""

from __future__ import annotations

import argparse
import statistics
from pathlib import Path

from PIL import Image

SUFFIXES = {".png", ".tif", ".tiff", ".jpg", ".jpeg", ".webp"}

# Rough inverse of the calibration table above.
QUALITY_POINTS = [(5.8, 95), (17.3, 85), (29.0, 75), (46.1, 60), (57.6, 50), (95.7, 30)]


def estimate_quality(mean_q: float) -> int:
    """Interpolate a quality number from the mean luma quantization value."""
    if mean_q <= QUALITY_POINTS[0][0]:
        return QUALITY_POINTS[0][1]
    for (q1, s1), (q2, s2) in zip(QUALITY_POINTS, QUALITY_POINTS[1:]):
        if mean_q <= q2:
            frac = (mean_q - q1) / (q2 - q1)
            return round(s1 + frac * (s2 - s1))
    return QUALITY_POINTS[-1][1]


def inspect(path: Path, crops: Path | None) -> dict:
    with Image.open(path) as image:
        row = {
            "name": path.name,
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "kb": path.stat().st_size / 1024,
            "bits_per_px": path.stat().st_size * 8 / (image.width * image.height),
            "dpi": (image.info.get("dpi") or (None, None))[0],
            "subsampling": image.info.get("subsampling"),
            "quality": None,
        }

        tables = getattr(image, "quantization", None)
        if tables:
            luma = tables[0]
            row["quality"] = estimate_quality(statistics.mean(luma))

        if crops:
            # A band from the vertical middle at full resolution. Open this in
            # an image viewer at 100% zoom and find a struck-through digit. If
            # you can read it, the model has a chance. If it has dissolved,
            # the honest transcription is [illegible] and no prompt fixes that.
            crops.mkdir(parents=True, exist_ok=True)
            top = image.height // 2 - 150
            sample = image.convert("RGB").crop((0, top, image.width, top + 300))
            sample.save(crops / f"{path.stem}_1to1.png")

    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scans", type=Path, default=Path("scans"))
    parser.add_argument(
        "--crops",
        type=Path,
        help="also write a full-resolution 300px crop from each page here",
    )
    parser.add_argument(
        "--page-inches",
        type=float,
        nargs=2,
        default=[8.5, 11.0],
        help="physical page size, for the effective DPI column",
    )
    args = parser.parse_args()

    scans = sorted(p for p in args.scans.iterdir() if p.suffix.lower() in SUFFIXES)
    if not scans:
        raise SystemExit(f"no scans found in {args.scans}")

    rows = [inspect(p, args.crops) for p in scans]

    header = f"{'file':<28}{'size':>12}{'KB':>9}{'bits/px':>9}{'quality':>9}{'eff DPI':>9}"
    print(header)
    print("-" * len(header))
    for row in rows:
        eff = row["width"] / args.page_inches[0]
        quality = row["quality"] if row["quality"] is not None else "lossless"
        print(
            f"{row['name']:<28}"
            f"{row['width']}x{row['height']:>6}"
            f"{row['kb']:>9.0f}"
            f"{row['bits_per_px']:>9.2f}"
            f"{str(quality):>9}"
            f"{eff:>9.0f}"
        )

    qualities = [r["quality"] for r in rows if r["quality"] is not None]
    if qualities:
        worst = min(qualities)
        print(f"\nestimated JPEG quality: {worst}–{max(qualities)} across {len(rows)} pages")
        if worst < 70:
            print(
                "  Below 70. Inspect the crops before committing to these scans, "
                "and go looking for a better master."
            )
    if any(r["mode"] != "L" for r in rows):
        print(
            "  Stored as colour. Harmless for accuracy — on a monochrome page "
            "the chroma channels are flat and all the damage is in luma."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
