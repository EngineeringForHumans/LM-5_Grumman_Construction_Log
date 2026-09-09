#!/usr/bin/env python3
"""Submit the transcription batch.

Builds one request per (page, band, pass) and submits them as a single Message
Batch. Batch usage bills at 50% of standard rates, and the two passes use
differently worded prompts so their errors correlate less than two samples from
one prompt would.

    python tools/transcribe.py --prompt-version 3

Vocabulary comes from reference/glossary.yml, and its `version` is recorded as
`glossary_version` — a separate axis from `prompt_version`. Vocabulary changes
often, transcription rules should not, and conflating them makes
`prompt_version` churn until it stops meaning anything.

By default this submits only pages that are stale against the current glossary
version. A page already transcribed under this vocabulary is skipped, so a bump
costs a re-run of what changed rather than the whole corpus. Verified pages are
re-run too: they are your only ground truth, and re-running them is what turns
the verified corpus into a regression suite that measures whether the promoted
terms actually helped.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent))
from lm5lib import load_transcripts, render_vocabulary, slug_version  # noqa: E402

MODEL = "claude-opus-5"

# Set well above your longest expected page. A transcript truncated at
# max_tokens looks exactly like a page that ends early, so collect.py treats
# any truncation as a hard failure rather than a warning.
MAX_TOKENS = 8000


def stale_pages(manifest: dict, raw_dir: Path, verified_dir: Path, gver: str) -> list[str]:
    """Pages with no run at the current glossary version."""
    fresh = {
        t.scan_id
        for t in load_transcripts(verified_dir)
        if t.glossary_version is not None and str(t.glossary_version) == gver
    }
    for path in raw_dir.glob(f"*.g{slug_version(gver)}.*.md"):
        fresh.add(path.stem.split(".")[0])
    return [scan_id for scan_id in sorted(manifest) if scan_id not in fresh]


def build_system(conventions: Path, vocabulary: str, prompt: Path, versions: str) -> list:
    """Assemble the cached system prefix.

    Conventions, vocabulary, and pass instructions are identical across every
    request in the batch, so they cache. Batches run longer than five minutes,
    which is why this uses the one-hour cache duration.
    """
    parts = [
        f"You are transcribing pages of the LM-5 construction log. {versions}",
        conventions.read_text(encoding="utf-8"),
        vocabulary,
        prompt.read_text(encoding="utf-8"),
    ]
    return [
        {
            "type": "text",
            "text": "\n\n---\n\n".join(parts),
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }
    ]


def build_requests(
    manifest: dict, scan_ids: list[str], system: list, pver: str, gver: str, pass_id: str
) -> list:
    requests = []
    for scan_id in scan_ids:
        page = manifest[scan_id]
        for band in page["bands"]:
            if band["file_id"] is None:
                raise ValueError(
                    f"{scan_id} band {band['index']} has no file_id; "
                    "run prepare.py without --dry-run first"
                )
            requests.append(
                {
                    # Results come back keyed by custom_id, not in order. The
                    # glossary version rides along so collect.py can name the
                    # output file without consulting anything else.
                    "custom_id": (
                        f"{scan_id}_b{band['index']:02d}"
                        f"_p{slug_version(pver)}_g{slug_version(gver)}_{pass_id}"
                    ),
                    "params": {
                        "model": MODEL,
                        "max_tokens": MAX_TOKENS,
                        "system": system,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    # Image before text. Claude performs best
                                    # when the image precedes the instruction.
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "file",
                                            "file_id": band["file_id"],
                                        },
                                    },
                                    {
                                        "type": "text",
                                        "text": (
                                            f"This is horizontal band "
                                            f"{band['index'] + 1} of "
                                            f"{len(page['bands'])} from page "
                                            f"{scan_id}. Transcribe only what "
                                            f"is visible in this band. Bands "
                                            f"overlap, so lines at the top or "
                                            f"bottom edge may be partially cut "
                                            f"off; transcribe a partially "
                                            f"visible line only if you can read "
                                            f"it, and never complete it from "
                                            f"inference."
                                        ),
                                    },
                                ],
                            }
                        ],
                    },
                }
            )
    return requests


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("manifest.json"))
    parser.add_argument("--conventions", type=Path, default=Path("CONVENTIONS.md"))
    parser.add_argument("--glossary", type=Path, default=Path("reference/glossary.yml"))
    parser.add_argument("--prompts", type=Path, default=Path("prompts"))
    parser.add_argument("--raw", type=Path, default=Path("raw"))
    parser.add_argument("--verified", type=Path, default=Path("verified"))
    parser.add_argument("--prompt-version", required=True)
    parser.add_argument("--passes", nargs="+", default=["A", "B"])
    parser.add_argument("--only", nargs="*", help="restrict to these scan_ids")
    parser.add_argument(
        "--all",
        action="store_true",
        help="submit every page, not just those stale against the glossary version",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Check every input up front. Discovering a missing prompt file after the
    # manifest and glossary have loaded wastes your time and tells you about
    # one problem when there may be three.
    required = [
        (args.manifest, "page manifest, written by prepare.py"),
        (args.conventions, "transcription conventions"),
        (args.glossary, "glossary, source of prompt vocabulary"),
        *(
            (args.prompts / f"pass_{p.lower()}.md", f"pass {p} instructions")
            for p in args.passes
        ),
    ]
    missing = [(path, what) for path, what in required if not path.exists()]
    if missing:
        print(f"Missing {len(missing)} required file(s), from {Path.cwd()}:\n")
        for path, what in missing:
            print(f"  {path}  — {what}")
        print("\nRun this from the project root, not from inside tools/.")
        return 1

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    vocabulary, gver = render_vocabulary(args.glossary)

    if args.only:
        missing = set(args.only) - set(manifest)
        if missing:
            raise SystemExit(f"not in manifest: {', '.join(sorted(missing))}")
        scan_ids = sorted(args.only)
    elif args.all:
        scan_ids = sorted(manifest)
    else:
        scan_ids = stale_pages(manifest, args.raw, args.verified, gver)

    if not scan_ids:
        print(f"every page is current at glossary_version {gver}; nothing to submit")
        return 0

    versions = f"prompt_version {args.prompt_version}, glossary_version {gver}."
    requests = []
    for pass_id in args.passes:
        system = build_system(
            args.conventions,
            vocabulary,
            args.prompts / f"pass_{pass_id.lower()}.md",
            versions,
        )
        requests += build_requests(
            manifest, scan_ids, system, args.prompt_version, gver, pass_id
        )

    print(f"glossary_version {gver}, prompt_version {args.prompt_version}")
    print(f"{len(scan_ids)} stale pages, {len(requests)} requests")
    if args.dry_run:
        print("dry run; nothing submitted")
        print("\n".join(f"  {r['custom_id']}" for r in requests[:6]))
        return 0

    client = anthropic.Anthropic()
    batch = client.messages.batches.create(requests=requests)

    out = Path("batches") / f"{batch.id}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "batch_id": batch.id,
                "model": MODEL,
                "prompt_version": args.prompt_version,
                "glossary_version": gver,
                "passes": args.passes,
                "pages": scan_ids,
                "custom_ids": [r["custom_id"] for r in requests],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"batch {batch.id} -> {out}")
    print("most batches finish within an hour; the guarantee is 24")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
