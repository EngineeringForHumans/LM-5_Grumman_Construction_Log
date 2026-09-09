#!/usr/bin/env node
/**
 * Inventory every marker in the corpus and say which ones the site can render.
 *
 *   node tools/markers.js              # report on stitched/ and transcripts/
 *   node tools/markers.js --check      # exit 1 if anything is unhandled
 *
 * The build fails on the first page containing a marker the renderer doesn't
 * know. That's the right behavior for a build and a slow way to find out what
 * your corpus contains, because you fix one marker, rebuild, and hit the next.
 * This lists all of them at once, with a page to look at for each.
 *
 * Run it after every stitch run. A new marker showing up is worth knowing
 * about before it stops a deploy.
 */

import fs from "node:fs/promises";
import path from "node:path";
import { classifyMarker } from "../site/_lib/transcript.js";

const ROOT = path.resolve(import.meta.dirname, "..");
const DIRS = ["stitched", "transcripts"];
const MARKER = /<!--[^]*?-->/g;

async function filesIn(dir) {
  try {
    const names = await fs.readdir(path.join(ROOT, dir));
    return names.filter((n) => n.endsWith(".md")).map((n) => path.join(ROOT, dir, n));
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

const found = new Map();

for (const dir of DIRS) {
  for (const file of await filesIn(dir)) {
    const text = await fs.readFile(file, "utf8");
    for (const marker of text.match(MARKER) ?? []) {
      // Collapse the varying part so "seam 0/1" and "seam 3/4" report once.
      const key = marker.replace(/\d+/g, "N").replace(/\s+/g, " ").trim();
      if (!found.has(key)) {
        found.set(key, { count: 0, example: marker, where: path.relative(ROOT, file) });
      }
      found.get(key).count += 1;
    }
  }
}

if (found.size === 0) {
  console.log("No markers found. Check that stitched/ contains your pages.");
  process.exit(0);
}

const rows = [...found.entries()]
  .map(([key, info]) => ({ key, ...info, kind: classifyMarker(info.example) }))
  .sort((a, b) => (a.kind === b.kind ? b.count - a.count : a.kind < b.kind ? -1 : 1));

const width = Math.min(48, Math.max(...rows.map((r) => r.key.length)));
console.log(`${"marker".padEnd(width)}  ${"handled as".padEnd(12)}  count  first seen in`);
console.log("-".repeat(width + 40));
for (const row of rows) {
  const kind = row.kind ?? "UNHANDLED";
  console.log(
    `${row.key.slice(0, width).padEnd(width)}  ${kind.padEnd(12)}  ` +
      `${String(row.count).padStart(5)}  ${row.where}`,
  );
}

const unhandled = rows.filter((r) => !r.kind);
if (unhandled.length) {
  console.log(
    `\n${unhandled.length} marker type(s) have no renderer. The build will fail on them.\n` +
      `Decide for each one whether it's content a reader needs to see, or bookkeeping ` +
      `to drop, then add it to site/_lib/transcript.js.`,
  );
}

process.exit(process.argv.includes("--check") && unhandled.length ? 1 : 0);
