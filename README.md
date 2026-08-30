# LM-5_Grumman_Construction_Log
The handwritten notes from the Grumman engineers working to assemble LM-5, which would become Eagle, the Apollo 11 Lunar Module carrying the first humans to the surface of the moon.

Grumman ran LM assembly at Bethpage, New York on rotating day and night shifts. The log was the handoff between them: each shift wrote down what it had done, what it had broken, what it was waiting on, and what the next shift needed to pick up. The entries run from mid-1968 through January 1969, when LM-5 shipped to Kennedy Space Center. They cover charred wiring, tripped circuit breakers, false master alarms, parts borrowed from other vehicles, and a November 1968 note recording that this was very likely the lunar module that would land.

This repository holds the scans, a transcription of every page, an annotation layer, and the tools and site that turn all of it into something readable.

## History
This project began in 2012 after Steve Jurvetson [purchased the log at aution](https://historical.ha.com/itm/transportation/space-exploration/grumman-apollo-11-lunar-module-handwritten-construction-and-testing-log-book/a/6075-40118.s) and [published a scan](https://steve.blog/2012/07/20/how-the-eagle-landed-the-grumman-construction-log/comment-page-1/), stating "[m]y hope is that we can collectively decode some of its mysteries". A wiki was started and dozens of volunteers—including yours truly—began transcribing. The project lost steam and the wiki no longer exists.

I recently began thinking about creating an automated knowledge publishing engine to take siloed information from artifacts and use AI tools to build modern interfaces for them. I needed a simple test case to start with and I remembered this scan. Thus, here we are.

## Project status

### 29 August 2026
I made a GitHub repo and uploaded the scanned pages—130 pages as JPGs, extracted from the original PDF scan.

The goal is AI transcription, human verification, and then publishing as a website where scans live alongside transcribed text. 

I am currently working on the conventions and glossary approach that will support accuracy in AI transcription.

## Repository layout

```
scans/         001.jpg
raw/           001.pass-a.md, 001.pass-b.md
transcripts/   001.md
annotations/   001.yml
reference/     glossary.yml, people.yml, manifest.csv, schema/
tools/         transcribe.py, review/, score.py
site/          .eleventy.js, _includes/, assets/
```

Every layer is a flat directory of files named for the same `scan_id`.

- **`scans/`** — The page images, one JPEG per physical page.

- **`raw/`** — Unedited machine output. This directory is append-only. Useful for comparing model accuracy over time and against the corrected transcripts.

- **`transcripts/`** — The core offering, one Markdown file per scan with YAML frontmatter carrying `scan_id`, dates, shifts, `status`, and provenance fields. Transcription is diplomatic: strikethroughs, misspellings, abbreviations, and illegible passages survive as written. `CONVENTIONS.md` (at the root) defines the markup.

- **`annotations/`** — Notes, context, and corrections that aren't on the page. Each annotation anchors to a quoted string plus an occurrence index, and the build merges the layers.

- **`reference/`** — Corpus-wide data. `glossary.yml` defines frequent abbreviations and terms so the build can link every occurrence. `people.yml` tracks the engineers, technicians, and QC staff named in the entries. `manifest.csv` inventories the scans. `schema/` holds the JSON Schema that CI validates frontmatter against.

- **`tools/`** — Things that support the development; nothing here is part of the published site.

- **`site/`** — Eleventy build. It reads the data directories, merges the annotation layer into the transcripts, and produces a static site with a deep-zoom scan viewer and client-side search.


## Build the site

TBD

## Contribute a correction

TBD

## Rights and licensing

**Code** — everything under `tools/` and `site/` is licensed under the MIT License.

**Transcriptions and annotations** — everything under `transcripts/`, `annotations/`, and `reference/` — are released under[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Use them for anything, without
attribution. Attribution is welcome and helps people find the scans, but it isn't required.

**Scans** — everything under `scans/` carries no license assertion from this project. The underlying document is a 1968 Grumman Aircraft Engineering Corporation record produced under NASA contract and is assumed to be public domain.

## Use of AI
Claude is used extensively in thinking through the process, building tools and scripts.

## Acknowledgments

The log survives because someone kept it and someone else scanned it. Steve Jurvetson made the first public scan of the complete book available in 2012 and invited the internet to help decode it; the acronym glossary and several identifications in `reference/` began in the comment thread on that post.

I am grateful to my former collaborators of the now-lost wiki. I hope you'll get in touch.

Future contributors will be named here.