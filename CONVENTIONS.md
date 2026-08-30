# Transcription conventions

**Version:** 0.8.0-draft — not yet normative. See [Open decisions](#open-decisions).

This document defines the markup for every file under `transcripts/`. It is normative: a
transcript that disagrees with this document is wrong, and CI enforces the parts that can be
checked mechanically.

Every transcript records the version of this document it was written against, in the
`conventions_version` frontmatter field. The transcription prompt in `tools/transcribe.py`
cites the same version. When a rule here changes, both bump together, so you can always tell
which pages predate a change.

## The governing principle

The transcription records what is on the page. It does not repair, complete, normalize, or
explain it. If an entry misspells a technician's name, the misspelling stands. If two items
carry the same number, they both keep it.

One rule outranks the rest: **an omission is acceptable, an invention is not.** A passage
marked `[illegible]` is honest and someone can fix it later. A plausible-looking serial number
that nobody actually read is undetectable, and in five years somebody cites it.

Everything you know that the page doesn't say — what a part number refers to, which vehicle a
borrowed component went to, that the name is actually spelled *Kowalczyk* — goes in
`annotations/`, anchored to the transcript. Nothing corrective goes in the transcript itself.

The dividing line, applied to every rule below: **the transcript records what a reader can see.
It does not record what a reader can conclude.** A box drawn around three entries is visible.
That the box means those entries were disputed is a conclusion, and it belongs in
`annotations/`.

## Relationship to TEI

This markup is a **lossless serialization of a restricted TEI P5 profile**. That claim is
precise, and each half of it is enforced:

- **Restricted profile.** `reference/schema/lm5.odd` declares exactly the TEI elements and
  attribute values this edition uses, and nothing else. It is a pure restriction: no new
  elements, no redefined semantics, no extensions. A pure restriction of TEI is TEI-conformant
  by the definition in chapter 24 of the Guidelines, so the export needs no disclaimer. The ODD
  compiles to a RELAX NG schema in the same directory.
- **Lossless.** `tools/to_tei.py` converts a transcript to TEI; `tools/from_tei.py` converts it
  back. CI runs the round trip on every file and fails on any difference. Markdown → TEI →
  Markdown is the identity function. The reverse direction is not required to be total: TEI can
  express things this spec deliberately can't, such as `<unclear>` spanning a phrase.

The ODD pins a specific TEI release in its `@source`. TEI ships maintenance releases every few
months, and an unpinned schema means a release can change what your CI accepts without anybody
touching this repository.

**The round trip is the gate for new markup.** A proposed marker that doesn't round-trip
doesn't ship. In practice a marker fails for one of two reasons: it has no TEI element, which
usually means it conflates two distinct things; or it has one but loses information on the way
back, which usually means the marker is underspecified. Both are worth knowing before the
marker is in 130 files.

### Document model

The export target is `<sourceDoc>`, not `<text><body>`. `<sourceDoc>` encodes a document as a
physical object — surfaces, zones, and lines — rather than as a reading text, which is what this
edition is. It also collapses a layer: the page image and the transcription live on the same
`<surface>`, so there is no parallel `<facsimile>` tree and no `@facs` pointers to keep in sync.

One file is one `<surface>`, carrying the page image and a zone per entry:

```xml
<surface xml:id="lm5-log-0042">
  <graphic url="../scans/lm5-log-0042.jpg"/>
  <zone type="entry">
    <line>0340  Removed R-4 harness, cont. check w/o fault</line>
    <line>0355  Reinstalled, TPS 8841 signed</line>
  </zone>
  <zone type="figure" ulx="18" uly="42" lrx="64" lry="62"/>
</surface>
```

Coordinates are optional on a zone, which is what makes this affordable: entry zones carry none,
and only the zones that came from a `region` annotation are placed. Surface coordinates are
declared in percent so they match the region syntax.

The cost of `<sourceDoc>` is that logical text structures aren't available inside it, so a
hand-drawn table becomes nested `<zone type="row">` and `<zone type="cell">` rather than a
`<table>`. That's the honest encoding regardless: a drawn table is a shape on the paper, and
zones describe shapes. Everything else on the page is free-form text between drawn rules, which
is what zones and lines are for.

The mapping itself is in the [appendix](#appendix-tei-mapping), and it's normative.

## Inline markers

All editorial marks are square brackets. Any character that carries markup meaning is
backslash-escaped when it appears literally on the page: `\[`, `\]`, `\~~`, `\→`, `\|`. CI
rejects an unescaped one that isn't part of a valid marker.

**Markers nest outermost-first by evidence type.** A word that is both struck and uncertain is
`~~[?x]~~`, never `[?~~x~~]`. The strike is a fact about the page; the uncertainty is a fact
about your reading, and the page-level fact goes outside.

| Marker | Use |
| --- | --- |
| `[illegible: 3 words]` | Text is present and you can't read it. The extent is **required** whenever you can estimate it; use `[illegible: 1 line]` or `[illegible: 1 word]` as the unit fits. |
| `[illegible]` | Only when the extent is genuinely unguessable. |
| `[?reading]` | You read it as *reading* but you aren't confident. **One marker per word** — write `[?tank] [?vent]`, never `[?tank vent]`. Never on digits; see [Numbers](#numbers). |
| `[?reading\|alternate]` | Two candidate readings of one word, best first. |
| `~~struck~~` | Struck through, with nothing written to replace it. |
| `[14→16]` | Struck and replaced. Original left of the arrow, replacement right. Covers overwriting, crossing out with a correction above, and erasure with a rewrite. |
| `[[illegible: 1 word]→16]` | Markers nest inside a substitution. |
| `[+inserted]` | Added above the line or with a caret, and *not* replacing anything. |
| `[margin: text]` | Written in the margin, outside the entry flow. |
| `[stamp: INSPECTED 14 NOV 68]` | Rubber stamp. Transcribe its text in caps. |
| `[initials: RJK]` | Initials you can read; `[initials: ?]` if not. |
| `[signature]` | A signature, legible or not. Never guess a name. |
| `[checkmark]` | Check, tick, or similar approval mark. |
| `[blank]` | A field the form expects to be filled, left empty. |
| `[torn]`, `[cut off]`, `[obscured]` | Text lost to damage, scan edge, or something on top of the page. |
| `[diagram]` | A hand-drawn sketch. Transcribe any text *inside* it; describe nothing. Give it a region in `annotations/` so the site can show it. |
| `[rule]` | A hand-drawn horizontal divider. On its own line. Delimits entries; see [Entries](#entries). |
| `[sic]` | **Not used.** The whole transcript is *sic*. |

Do not expand abbreviations. `w/o`, `assy`, `TPS`, `ea`, and `#` stay as written;
`reference/glossary.yml` handles expansion at build time.

### Numbers

**`[?…]` is never used on digits.** A number you can only partly read is `[illegible: 1 word]`,
or `[8[illegible: 2 words]]` if some digits are certain and their position is clear.

Prose tolerates a marked guess because a reader can tell when a word doesn't fit its sentence. A
serial, part, or TPS number can't be checked that way — a wrong one reads exactly like a right
one, forever. The brackets also don't survive: somebody copies the number into an email, the
markup goes, and a guess becomes a fact. This is the governing principle applied where it
matters most.

## Block markers

Four things wrap other content rather than sitting inside it. Block markers open and close on
their own lines and nest.

```
[box]
0340  Removed R-4 harness, cont. check w/o fault
0355  Reinstalled, TPS 8841 signed
[/box]
```

- **`[box]`** — a hand-drawn box, bracket, or circle enclosing a block of text. Records the
  enclosure only. What it means goes in `annotations/`.
- **`[yellow note]`** — a yellow note or slip physically laid on the page. See below.
- **`[addendum]`** — a block written into space left by an earlier entry, or below it after a
  divider, that continues or amends it. See D7 in the notes on scope.
- **`[table]`** — a hand-drawn table. See below.

### Yellow notes

A yellow note is a separate piece of paper resting on the page. It is transcribed as its own
block, placed where it physically sits, never merged into the entry beneath it:

```
[yellow note]
CHECK AGAINST TDR 4412
[/yellow note]
```

The marker names the object, not its function, and deliberately doesn't collide with an entry
that begins `Note:`. Text on the page that merely reads as a note is body text.

The block records the object, not its date. When a note was written, and by whom, is a
provenance question the transcript doesn't answer. The edition's position on that, and the
evidence for it, goes in `scans/PROVENANCE.md`.

If a note covers text, mark what it hides with `[obscured by yellow note: 2 lines]`. There is
one scan per page, so covered text stays covered — the marker is permanent, not a placeholder.

### Hand-drawn tables

The body has no printed columns, but engineers draw tables. Transcribe one as a Markdown table
inside a `[table]` block:

```
[table]
| Conn | Cont | Insp |
| --- | --- | --- |
| J-1 | OK | [initials: RJK] |
| J-2 | [?OK] | [blank] |
[/table]
```

- The header row is whatever is written in the top row of the drawn table. It is content, not
  a `form` label, because the engineer wrote it.
- Cells take the full marker set. A literal pipe inside a cell is `\|`.
- A cell left empty is `[blank]`. A drawn table has an expectation about its cells the way a
  printed field does.
- A drawn table is also a drawn object. If it's worth showing the reader, give it a region in
  `annotations/`, the same as a diagram.

Table formatting is canonical, not preserved: one space inside each delimiter, no alignment
padding. The converter emits this form and CI reformats to it. Alignment whitespace is a
rendering artifact, not something the page says.

### Arrows

Drawn arrows connect or reorder content, and the transcript records them without obeying them.
**Transcript order always follows page order.** An arrow moving an entry to the top of the page
does not move it in the file.

Anchor both ends with a lowercase letter, unique within the file:

```
0410  Vent valve reseated  [arrow→a]
...
[arrow←a] 0455  Retest of vent valve, pass
```

If the target isn't on this page, name the direction only: `[arrow: to next page]`,
`[arrow: to margin]`, `[arrow: off page]`. Renumbering arrows — the ones that reorder a numbered
list — use the same anchors; the numbers themselves stay exactly as written, including the
duplicates the renumbering was meant to fix.

## Regions

Some things on the page can't be represented as text — a sketch, a stamp, a signature, a
passage nobody can read. The transcript marks that they exist. The *annotation* says where
they are on the scan, so the site can show the reader the thing itself.

A region is a W3C media fragment in percentage units, so it survives rescanning at a different
resolution:

```yaml
# annotations/lm5-log-0042.yml
- anchor:
    quote: "[diagram]"
    occurrence: 1
  region: "xywh=percent:18,42,46,20"
  note: >
    Routing sketch for the R-4 harness. The three numbered leads correspond to the
    connectors listed in the 0340 entry.
```

`region` is available on any annotation, not just diagram ones. Percentages are of the full
image, measured from the top left.

Regions are optional and additive: an annotation without one still works, and adding one later
changes nothing else. Nothing in `transcripts/` holds coordinates, so a rescan invalidates
annotations at worst, never the edition.

The build reads `region`, crops a derivative from the scan, and places it inline in the
transcript at the marker. It also hands the rectangle to OpenSeadragon so a **Show on scan**
control zooms the viewer to it. Crops are generated output; don't commit them.

Draw the rectangles in the review interface rather than by hand. Reading four numbers off an
image editor 30 times is worse than an afternoon spent adding a drag-to-select to
`tools/review/`.

## Symbols

The log uses `Ω`, `µ`, `Δ`, `⌀`, `°`, `±`, and others. Two rules govern all of them:

- Transcribe the Unicode character, never a spelled-out name and never an ASCII approximation.
- Use the letter, never the compatibility codepoint. `Ω` is U+03A9 greek capital omega, not
  U+2126 ohm sign; `µ` is U+03BC greek small mu, not U+00B5 micro sign. The glyphs are
  identical and search matches only one of them.

The list of permitted symbols lives in `reference/glossary.yml` under `symbols:`, alongside the
acronyms, because it's the same kind of thing and it's the file CI already reads. Each entry
gives the codepoint, a name, and what the log uses it for.

A symbol gets added to the glossary before it gets used in a transcript. CI fails any file
containing a non-ASCII character that isn't listed — that check is the whole point of keeping
the list in a data file rather than in this document.

## Page structure

Each file transcribes exactly one scan, matching `scan_id`. A two-page spread photographed as
one image is one file.

- **Printed form labels** — column headers, field captions, the rules themselves — are
  transcribed once in the frontmatter `form` block, not in the body.
- **Handwritten fill-ins in printed fields** — the date, the vehicle, the shift lead's name —
  go in the frontmatter `header` block, keyed by the printed label they sit next to. They carry
  the same markers as body text.
- **Line breaks on the page are preserved.** End every transcribed line with a hard break (two
  spaces). Don't reflow. A word broken across a line end keeps its hyphen and its break.
- **The body has no printed column structure.** Only the header fields are preprinted; below
  them the page is open and the engineers organize it themselves. See D29.

## Entries

**An entry is delimited by a hand-drawn rule.** The engineers drew the dividers, so entry
boundaries are evidence on the page rather than an editorial judgment, and the transcript
inherits that for free.

- A `[rule]` on its own line both records the drawn divider and closes the entry above it.
- The top and bottom of the page are implicit boundaries. A page opens an entry and closes one
  without needing a rule at either edge.
- **Blank lines don't delimit anything.** Vertical space inside an entry is preserved as written
  and carries no structural meaning.
- Each entry becomes one `<zone type="entry">` in the TEI export, and one anchor target for
  annotations.

An entry that starts on one page and continues on the next has no rule between its halves.
Mark both ends:

```
0410  Vent valve reseated, awaiting  [entry continues]
```

```
[entry continued]  retest per TPS 8841
```

`[entry continues]` closes the body of one file; `[entry continued]` opens the next. Pairing is
positional — the continuation is always the next `scan_id` — so no anchors are needed and CI can
check that every `continues` is answered by a `continued` on the following page.

Each half counts as one entry in its own file's `entries` list. A time belongs to the first
half. The build joins the halves for display; the files stay page-shaped, because the page is
the unit of record.

## Shift boundaries

Shift pages on the site are derived, never stored. The transcript carries the boundary as an
HTML comment at the point in the body where the handoff happens:

```
<!-- shift: night 1968-11-14 -->
```

A `[rule]` usually sits at the same place, since a handoff ends an entry. Record both: the rule
is what's on the page, the comment is your reading of it. A shift comment that doesn't fall on
an entry boundary is a CI error.

## What is and isn't normalized

Nothing about the content is normalized. No spelling, spacing, capitalization, punctuation,
number format, or word order is altered, ever, silently or otherwise.

Encoding is a different question, and a file has to make some choice, so these are fixed:

- **Unicode NFC.** Two files that look identical must not differ in bytes.
- **LF line endings**, enforced by `.gitattributes`.
- **No trailing whitespace**, except the two-space hard break at end of line.
- **Straight quotes and apostrophes.** Handwriting does not distinguish straight from curly, so
  choosing one is a rendering decision, not a change to the text.

If a rule here would change what the page says, it's wrong and needs an issue.

## Frontmatter

```yaml
scan_id: lm5-log-0042
date: 1968-11-14          # normalized; derived from header.DATE
date_inferred: false
shift: day                # day | night | unknown
status: raw               # raw | reviewed | verified
conventions_version: 0.7.0
prompt_version: 0.7.0
transcribed_by: model     # model | human
reviewed_by: []
form:
  labels: [VEHICLE, DATE, SHIFT, LEAD, SHEET]
header:
  VEHICLE: "LM-5"
  DATE: "11/14/68"
  SHIFT: "[?2nd]"
  LEAD: "[signature]"
  SHEET: "A-1147"
entries:
  - n: 1
    time: "03:40"
    time_literal: "0340"
  - n: 2
    time: null
    time_literal: null
```

`form` holds printed labels and is identical across pages of the same form. `header` holds what
somebody wrote in those fields and varies per page. `date` is the normalized value; `header.DATE`
is the literal one. When they disagree, `header` is the evidence and `date` is the reading.

`entries` is produced by the extraction pass, which runs against verified text only, and its
length must equal the number of rule-delimited entries in the body. `time_literal` is what the
page says; `time` is the normalized value, and it's `null` when an entry carries no time. The
pair exists because normalization isn't deterministic — `0340`, `3:40`, and `abt 4` all appear —
so the reading has to be recorded rather than recomputed.

`header.SHEET` is the sheet's own printed serial. It is content, not identity: `scan_id` is
assigned by position in the binder and never skips, while the printed serials do. The gaps in
`SHEET` are a fact about the document. They belong in `manifest.csv` and in
`scans/PROVENANCE.md`, together with the evidence that no content is missing across them, and
never in a filename.

### Dates and status

- `date_inferred: true` requires an annotation stating the basis for the inference. An
  unexplained inferred date is a schema error. The basis is usually continuity with an adjacent
  page, and that reasoning is exactly what a later reader needs to disagree with.
- `verified` requires two distinct names in `reviewed_by`. One person cannot verify their own
  review.
- **Any change to the body of a verified transcript resets `status` to `reviewed`.** CI enforces
  this. Otherwise a pull request from a stranger silently inherits your verification.

`reference/schema/transcript.json` validates this. A field this document doesn't define is a
schema error, not a free-form extension point.

## Measuring accuracy

There is no gold set and no sampling rule, because there is nothing to sample for. A scoring set
exists to compare one prompt or model against another, and this edition transcribes each page
once, with a human verifying every page against the scan.

The error rate is still measurable, and better than a sample would give: `raw/` is append-only,
so at the end of the project you diff every `raw/*.pass-a.md` against its verified transcript and
get a census of machine error across the whole corpus. That number belongs in the README. It
measures the pipeline that was actually run, not a comparison between alternatives — if you ever
change model or prompt mid-corpus, hold out a set of already-verified pages *before* the change
and score against those.

## Appendix: TEI mapping

This table is normative and it is the specification `tools/to_tei.py` implements. Every marker
has exactly one target; every target round-trips. A marker absent from this table is not valid
markup, whatever the rest of this document says.

| Marker | TEI P5 |
| --- | --- |
| `[?reading]` | `<unclear cert="low">` |
| `[?a\|b]` | `<choice><unclear>a</unclear><unclear>b</unclear></choice>` |
| `[illegible: 3 words]` | `<gap reason="illegible" quantity="3" unit="word"/>` |
| `~~struck~~` | `<del>` |
| `[14→16]` | `<subst><del>14</del><add>16</add></subst>` |
| `[+inserted]` | `<add place="above">` |
| `[margin: text]` | `<add place="margin">` |
| `[stamp: TEXT]` | `<stamp>` |
| `[initials: RJK]` | `<seg type="initials">` |
| `[signature]` | `<signed>` |
| `[checkmark]` | `<metamark function="checked"/>` |
| `[blank]` | `<space dim="horizontal"/>` |
| `[torn]`, `[cut off]` | `<gap reason="torn"/>`, `<damage>` |
| `[obscured by yellow note: 2 lines]` | `<gap reason="covered" quantity="2" unit="line"/>` |
| `[diagram]` | `<zone type="figure">`, placed if the annotation gives a region |
| `[rule]` | `<milestone unit="rule"/>` between entry zones |
| `[box]` … `[/box]` | `<metamark function="box" spanTo="#x"/>` |
| `[yellow note]` … `[/yellow note]` | nested `<surface type="yellowNote">` |
| `[addendum]` … `[/addendum]` | `<add place="inline" type="addendum">` |
| `[arrow→a]`, `[arrow←a]` | `<metamark function="reorder" target="#a"/>` |
| hard line break | one `<line>` per transcribed line |
| `<!-- shift: … -->` | `<milestone unit="shift"/>` |
| rule-delimited entry | `<zone type="entry">` |
| `[entry continues]`, `[entry continued]` | `@next` and `@prev` on the entry zones |
| `[table]` … `[/table]` | nested `<zone type="row">` and `<zone type="cell">` |
| `region: xywh=percent:…` | `@ulx`/`@uly`/`@lrx`/`@lry` on the corresponding `<zone>` |
| frontmatter | `<teiHeader>` |
| whole file | one `<surface>` in `<sourceDoc>` |

Two elements above exist for exactly this document's problems: `<metamark>` covers marks that
instruct rather than say — boxes, carets, reordering arrows — and `<handShift/>` records a
change of hand, if D7 is ever revisited.

### Frontmatter mapping

`<teiHeader>` has a home for most of the frontmatter, and using it beats inventing fields:

| Frontmatter | TEI P5 |
| --- | --- |
| `status` | `<revisionDesc status="raw">` |
| `reviewed_by`, dates of review | `<change>` inside `<revisionDesc>` |
| `prompt_version`, `transcribed_by` | `<application>` inside `<encodingDesc><appInfo>` |
| `conventions_version` | `<encodingDesc><editorialDecl>`, pointing at this document |
| `scan_id` | `<idno>` in `<msIdentifier>`, and `@xml:id` on the `<surface>` |
| `date`, `date_inferred` | `<origDate when="1968-11-14" cert="low">` |
| `header.DATE` and other fill-ins | `<docDate>` and `<label>`/`<item>` pairs in `<sourceDoc>` |
| `form.labels` | `<fw>` |
| `header.SHEET` | `<idno type="sheet">` |
| `entries[].time` | `@when` on the entry zone |

### Anchors and identifiers

`[box]`, `[addendum]`, and the arrow anchors become TEI pointers, which means they need
`@xml:id` values. Derive them from `scan_id` plus a counter — `lm5-log-0042-a` — so
regenerating the export produces a byte-identical file. Random or hash-derived ids make every
regeneration a diff, and a diff nobody can read is a diff nobody checks.

## Open decisions

Both remaining items are settled in design and unbuilt in code.

- **D11 — Region authoring.** TBD. Regions are specified; the drag-to-select in
  `tools/review/` isn't built. Hand-authored coordinates work in the meantime.
- **D14 — TEI export.** TBD. The mapping, the document model, and the canonical Markdown form
  are specified; `tools/to_tei.py` and `tools/from_tei.py` aren't written, so the round-trip
  guarantee is a claim rather than a check until they are. Until then this document stays at
  `-draft` and `conventions_version` stays below 1.0.
