import markdownIt from "markdown-it";

// Markers written by stitch.py. Change these two patterns if your stitch
// output uses a different comment vocabulary; nothing else here depends on
// the exact wording.
const SEAM_OPEN = /^<!--\s*seam\b([^>]*)-->\s*$/;
const SEAM_PART = /^<!--\s*(upper|lower|\/seam|band\b[^>]*)\s*-->\s*$/;

// A shift boundary is content: it says who was on the floor when the entries
// below it were written. Band and seam markers are bookkeeping and get
// dropped; this one gets rendered.
const SHIFT = /^<!--\s*shift:\s*([^>]*?)\s*-->\s*$/;

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/**
 * "night 1968-06-13" becomes "Night shift, 13 June 1968".
 *
 * Anything that doesn't match that shape is shown as written. Guessing at a
 * marker's meaning is worse than showing the reader the raw label.
 */
function formatShift(label) {
  const match = /^(\S+)\s+(\d{4})-(\d{2})-(\d{2})$/.exec(label);
  if (!match) return label.charAt(0).toUpperCase() + label.slice(1);
  const [, name, year, month, day] = match;
  const monthName = MONTHS[Number(month) - 1];
  if (!monthName) return label;
  const shift = name.charAt(0).toUpperCase() + name.slice(1);
  return `${shift} shift, ${Number(day)} ${monthName} ${year}`;
}

const md = markdownIt({ html: false, breaks: true, linkify: false });

const escapeText = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escapeAttr = (s) => escapeText(s).replace(/"/g, "&quot;");

// [?Nielsen] is a proposed reading; [illegible] is a refusal to guess. Both
// are inline rules rather than a pass over rendered HTML, so they can never
// match inside a tag or an attribute.
md.inline.ruler.before("link", "uncertainty", (state, silent) => {
  if (state.src.charCodeAt(state.pos) !== 0x5b /* [ */) return false;
  const close = state.src.indexOf("]", state.pos);
  if (close === -1) return false;

  const inner = state.src.slice(state.pos + 1, close);
  const illegible = inner === "illegible";
  if (!illegible && inner[0] !== "?") return false;
  if (!illegible && inner.length < 2) return false;

  if (!silent) {
    const open = state.push("uncertain_open", "span", 1);
    open.attrs = illegible
      ? [["class", "illegible"], ["title", "Not legible on the scan"]]
      : [["class", "uncertain"], ["title", "Proposed reading, not confirmed"]];

    const text = state.push("text", "", 0);
    text.content = illegible ? "illegible" : inner.slice(1);

    state.push("uncertain_close", "span", -1);
  }

  state.pos = close + 1;
  return true;
});

/**
 * What the renderer does with a marker, or null if it doesn't know it.
 *
 * The block parser and tools/markers.js both go through this, so the inventory
 * can never claim a marker is handled when the build would reject it.
 */
export function classifyMarker(line) {
  const trimmed = line.trim();
  if (SHIFT.test(trimmed)) return "shift";
  const open = SEAM_OPEN.exec(trimmed);
  if (open) return /unaligned/.test(open[1]) ? "seam gap" : "seam";
  const part = SEAM_PART.exec(trimmed);
  if (part) return part[1].startsWith("band") ? "dropped" : "seam";
  return null;
}

function renderLines(lines) {
  return md.render(lines.join("\n").trim());
}

/**
 * Split a stitched body into blocks of plain lines and seam disagreements.
 *
 * A seam block holds two readings of the same physical lines, produced by
 * overlapping scan bands. Publishing them as consecutive lines invents log
 * entries that aren't on the page, so they always render as a pair.
 */
function blocks(body) {
  const out = [];
  let plain = [];
  let seam = null;
  let side = null;

  const flush = () => {
    if (plain.length) out.push({ type: "plain", lines: plain });
    plain = [];
  };

  for (const line of body.split(/\r?\n/)) {
    const shift = SHIFT.exec(line);
    if (shift && !seam) {
      flush();
      out.push({ type: "shift", label: shift[1] });
      continue;
    }

    const open = SEAM_OPEN.exec(line);
    const part = SEAM_PART.exec(line);

    if (open && !seam) {
      // An unaligned seam has no upper/lower pair: the bands overlap somewhere
      // the aligner couldn't find, so lines may be missing or doubled.
      if (/unaligned/.test(open[1])) {
        flush();
        out.push({ type: "unaligned" });
        continue;
      }
      flush();
      seam = { type: "seam", upper: [], lower: [] };
      side = null;
      continue;
    }

    if (part) {
      const keyword = part[1];
      if (keyword === "upper" || keyword === "lower") {
        side = keyword;
        continue;
      }
      if (keyword === "/seam") {
        if (seam) out.push(seam);
        seam = null;
        side = null;
        continue;
      }
      // band markers carry no meaning for a reader once the page is merged.
      continue;
    }

    if (seam && side) seam[side].push(line);
    else if (!seam) plain.push(line);
  }

  if (seam) out.push(seam);
  flush();
  return out;
}

const NOTE = {
  seam: "The two scan bands read these lines differently. Nobody has checked them against the scan yet.",
  unaligned: "The scan bands couldn't be aligned here. Lines may be missing or repeated.",
};

export function renderTranscript(text, { sourceFile = "transcript" } = {}) {
  const html = blocks(text ?? "")
    .map((block) => {
      if (block.type === "plain") return renderLines(block.lines);
      if (block.type === "unaligned") {
        return `<p class="seam-gap">${NOTE.unaligned}</p>`;
      }
      if (block.type === "shift") {
        return (
          `<p class="shift" data-marker="${escapeAttr(block.label)}">` +
          `${escapeText(formatShift(block.label))}</p>`
        );
      }
      return [
        `<div class="seam">`,
        `<p class="seam-note">${NOTE.seam}</p>`,
        `<div class="seam-reading"><h3>Upper band</h3>${renderLines(block.upper)}</div>`,
        `<div class="seam-reading"><h3>Lower band</h3>${renderLines(block.lower)}</div>`,
        `</div>`,
      ].join("");
    })
    .join("\n");

  // A marker that reaches the page is either invisible to the reader or
  // visible as junk, and the first case is the one that publishes a reading
  // nobody chose. Fail the build instead.
  const leaks = [...new Set(html.match(/(?:&lt;|<)!--[^]*?--(?:&gt;|>)/g) ?? [])];
  if (leaks.length) {
    throw new Error(
      `${sourceFile}: ${leaks.length} unhandled marker(s) reached the rendered page:\n` +
        leaks.map((m) => `  ${m}`).join("\n") +
        `\nHandle them in site/_lib/transcript.js, or run tools/markers.js to see ` +
        `every marker in the corpus at once.`,
    );
  }
  return html;
}

/** Plain-text output. Same rule: no marker leaves the build unexplained. */
export function renderPlainText(text, { sourceFile = "transcript" } = {}) {
  return blocks(text ?? "")
    .map((block) => {
      if (block.type === "plain") return block.lines.join("\n").trim();
      if (block.type === "unaligned") return `[bands not aligned here]`;
      if (block.type === "shift") return `\n--- ${formatShift(block.label)} ---\n`;
      return [
        "[bands disagree, unreviewed]",
        "[upper band]",
        block.upper.join("\n").trim(),
        "[lower band]",
        block.lower.join("\n").trim(),
        "[end disagreement]",
      ].join("\n");
    })
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
