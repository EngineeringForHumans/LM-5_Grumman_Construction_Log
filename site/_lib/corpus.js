import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";

const ROOT = path.resolve(import.meta.dirname, "../..");
const TRANSCRIPTS = path.join(ROOT, "transcripts");
const STITCHED = path.join(ROOT, "stitched");
const MANIFEST = path.join(ROOT, "manifest.csv");

// The manifest is the list of pages that exist. A page with no text yet still
// gets a record, so a scan can never be missing from the site and "how much is
// left" is answerable without counting files by hand.
async function manifestIds() {
  const text = await fs.readFile(MANIFEST, "utf8");
  const [header, ...rows] = text.trim().split(/\r?\n/);
  const column = header.split(",").indexOf("scan_id");
  if (column === -1) throw new Error("manifest.csv has no scan_id column");
  return rows.map((row) => row.split(",")[column].trim()).filter(Boolean);
}

async function readIfPresent(file) {
  try {
    return await fs.readFile(file, "utf8");
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

// Stitched filenames carry the run that produced them: 037.p1.g0-2-0.A.md.
// Sorting by name puts the newest prompt and glossary versions last, which is
// the same rule harvest.py and promote.py use to pick a machine baseline.
async function latestStitched(scanId) {
  let entries;
  try {
    entries = await fs.readdir(STITCHED);
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
  const runs = entries
    .filter((f) => f.startsWith(`${scanId}.`) && f.endsWith(".md"))
    .sort();
  if (runs.length === 0) return null;
  const file = runs[runs.length - 1];
  return { file, text: await fs.readFile(path.join(STITCHED, file), "utf8") };
}

// A published status is a promise to the reader, so it comes from where the
// file lives, not from the frontmatter. A stitched file claiming
// status: reviewed is a bug in the pipeline, not a page to publish as reviewed.
function statusFor(layer, frontmatter) {
  if (layer === "none") return "untranscribed";
  if (layer === "stitched") return "unreviewed";
  const claimed = frontmatter.status;
  return claimed === "verified" ? "verified" : "reviewed";
}

export async function loadCorpus() {
  const ids = await manifestIds();

  return Promise.all(
    ids.map(async (scanId) => {
      const promoted = await readIfPresent(path.join(TRANSCRIPTS, `${scanId}.md`));
      const stitched = promoted ? null : await latestStitched(scanId);

      const layer = promoted ? "transcripts" : stitched ? "stitched" : "none";
      const source = promoted ?? stitched?.text ?? "---\n---\n";
      const { data, content } = matter(source);

      // scan_id comes from the filename, never the frontmatter: YAML reads an
      // all-digit id like 005 as the integer 5, and the mismatch is silent.
      if (data.scan_id !== undefined && String(data.scan_id) !== scanId) {
        const file = promoted ? `transcripts/${scanId}.md` : `stitched/${stitched.file}`;
        throw new Error(`${file}: scan_id "${data.scan_id}" does not match the filename`);
      }

      return {
        scanId,
        layer,
        status: statusFor(layer, data),
        text: content.trim(),
        sourceFile: promoted
          ? `transcripts/${scanId}.md`
          : stitched
            ? `stitched/${stitched.file}`
            : null,
        provenance: {
          promptVersion: data.prompt_version ?? null,
          glossaryVersion: data.glossary_version ?? null,
          conventionsVersion: data.conventions_version ?? null,
          pass: data.pass ?? null,
          reviewedAt: data.reviewed_at ?? null,
          seamConflicts: data.seam_conflicts ?? 0,
          seamsUnaligned: data.seams_unaligned ?? 0,
        },
      };
    }),
  );
}
