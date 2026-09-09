#!/usr/bin/env python3
"""Shared helpers for the transcription tools.

Three things live here because more than one script needs them: token-level
comparison, transcript frontmatter parsing, and the glossary-to-prompt
rendering that decides what the model is allowed to see.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from ruamel.yaml import YAML

_yaml = YAML(typ="safe")

TOKEN = re.compile(r"\S+")
ALNUM = re.compile(r"\d")
BAND_MARKER = re.compile(r"<!--\s*band\s+\d+\s*-->")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def slug_version(version: str) -> str:
    """Make a version string safe for a batch custom_id (alnum, _ and - only)."""
    return re.sub(r"[^A-Za-z0-9-]", "-", str(version))


# The Files API moved from client.beta.files to client.files. Older SDKs only
# have the beta namespace, and requests referencing a file_id then need the
# beta header too.
FILES_BETA = "files-api-2025-04-14"


def files_api_is_beta(client) -> bool:
    """True when this SDK only exposes the Files API under .beta."""
    return not hasattr(client, "files")


def upload_file(client, path: Path, media_type: str) -> str:
    """Upload one file and return its file_id, on either SDK layout."""
    with path.open("rb") as handle:
        payload = (path.name, handle, media_type)
        if not files_api_is_beta(client):
            return client.files.upload(file=payload).id

        beta_files = getattr(getattr(client, "beta", None), "files", None)
        if beta_files is None:
            import anthropic

            raise SystemExit(
                f"This SDK (anthropic {anthropic.__version__}) has no Files API.\n"
                "Upgrade it:  python -m pip install --upgrade anthropic"
            )
        return beta_files.upload(file=payload, betas=[FILES_BETA]).id


def tokenize(text: str) -> list[str]:
    return [m.group() for m in TOKEN.finditer(BAND_MARKER.sub("", text))]


@dataclass
class Transcript:
    path: Path
    scan_id: str
    meta: dict
    body: str

    @property
    def status(self) -> str:
        return self.meta.get("status", "unknown")

    @property
    def glossary_version(self) -> str | None:
        return self.meta.get("glossary_version")

    @property
    def prompt_version(self) -> str | None:
        return self.meta.get("prompt_version")


def read_transcript(path: Path) -> Transcript:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER.match(text)
    if match:
        meta = _yaml.load(match.group(1)) or {}
        body = text[match.end() :]
    else:
        meta, body = {}, text
    # scan_id comes from the filename, never the frontmatter: YAML reads an
    # all-digit id like 005 as the integer 5, which then stops matching the
    # manifest key and the scan on disk.
    scan_id = path.stem.split(".")[0]
    meta["scan_id"] = scan_id
    return Transcript(path=path, scan_id=scan_id, meta=meta, body=body)


def load_transcripts(directory: Path, status: str | None = None) -> list[Transcript]:
    if not directory.exists():
        return []
    found = [read_transcript(p) for p in sorted(directory.glob("*.md"))]
    if status:
        found = [t for t in found if t.status == status]
    return found


def diff_tokens(a: str, b: str) -> list[dict]:
    """Token-level opcodes between two transcripts of the same page."""
    ta, tb = tokenize(a), tokenize(b)
    out = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=ta, b=tb, autojunk=False).get_opcodes():
        out.append(
            {
                "tag": tag,
                "a_start": i1,
                "a": ta[i1:i2],
                "b_start": j1,
                "b": tb[j1:j2],
            }
        )
    return out


def render_vocabulary(glossary_path: Path) -> tuple[str, str]:
    """Render the prompt vocabulary block, and return it with the version.

    Only `term`, `variants`, and `examples` cross into the prompt. Expansions
    and definitions stay out on purpose: vocabulary helps the model recognize
    strings that are on the page, while meaning gives it a narrative to
    reconstruct, which is what makes it invent.
    """
    with glossary_path.open(encoding="utf-8") as handle:
        data = _yaml.load(handle)
    version = str(data.get("version", "0"))

    by_kind: dict[str, list[str]] = {}
    for term in data.get("terms", []):
        forms = [term["term"], *(term.get("variants") or [])]
        examples = term.get("examples") or []
        entry = ", ".join(dict.fromkeys(str(f) for f in forms))
        if examples:
            entry += "  (as written: " + "; ".join(str(e) for e in examples) + ")"
        by_kind.setdefault(term.get("kind", "other"), []).append(entry)

    sections = [
        "# Corpus vocabulary",
        "",
        "These strings appear in this corpus. Knowing them helps you recognize",
        "what is on the page. It is never a reason to put one there: an",
        "unreadable mark does not resolve to an entry in this list, and a term",
        "listed here is not evidence that it appears on the page in front of",
        "you. No expansions or definitions are given, because you are copying",
        "marks, not interpreting a document.",
    ]
    for kind in sorted(by_kind):
        sections += ["", f"## {kind.replace('-', ' ').title()}", ""]
        sections += [f"- {entry}" for entry in sorted(by_kind[kind])]

    return "\n".join(sections) + "\n", version
