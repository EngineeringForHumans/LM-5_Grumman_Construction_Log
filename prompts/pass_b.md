# Pass B instructions

This prompt covers the same task as pass A and states it differently on purpose.
Two passes worded the same way make the same mistakes, and a diff between them
shows nothing. Do not try to match a previous transcription. Read the image in
front of you.

## Work through the image in reading order

1. Start at the top-left mark and move across, then down.
2. For each mark that carries text, decide one of three things:
   - You read it. Transcribe the characters you see.
   - You read it but you're unsure. Transcribe it as `[?reading]`.
   - You can't read it. Write `[illegible]`, with an extent estimate when you
     can give one, like `[illegible: 3 words]`.
3. Move to the next mark. Do not revisit an earlier decision to make the page
   read more coherently.

Character-level ambiguity is the normal case in this corpus, not a failure. A
1 and a 7, a 3 and an 8, an O and a 0 — when the strokes don't settle it, the
answer is `[?7]`, not your best guess.

## Copy, do not translate

The output is a record of ink on paper. Preserve spelling as written,
capitalization as written, abbreviations unexpanded, struck-through text marked
as struck, and the line and column layout of the page. Blank fields stay blank.

Numbers deserve particular care. Part numbers, TPS numbers, serial numbers, and
stamp numbers carry no linguistic context, so nothing downstream can catch a
wrong digit. Read them character by character, and mark any character you are
not sure of.

## What the page is

A 1968 Grumman construction log sheet for lunar module LM-5: handwritten entries
on a printed form. Expect technician handwriting, carbon-copy fading, stamps,
and marginal notes. Transcribe the printed form text as well as the handwriting.

## Output

The transcript alone, in the conventions markup above. Nothing before it and
nothing after it.
