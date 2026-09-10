import fs from "node:fs/promises";
import path from "node:path";
import { parse } from "yaml";
import loadPages from "./pages.js";

const GLOSSARY = path.resolve(import.meta.dirname, "../../reference/glossary.yml");

// A term must not match inside a longer alphanumeric or hyphenated run, so that
// "LM" does not fire on "LM-5" and "QC" does not fire on "post-QC".
const LEFT = "(?<![A-Za-z0-9-])";
const RIGHT = "(?![A-Za-z0-9-])";

function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
}

function buildMatcher(entry) {
  if (entry.match === "pattern") {
    if (!entry.pattern) {
      throw new Error(`glossary: term "${entry.id}" uses match: pattern but has no pattern`);
    }
    try {
      return new RegExp(entry.pattern, "g");
    } catch (error) {
      throw new Error(`glossary: term "${entry.id}" has an invalid pattern: ${error.message}`);
    }
  }

  const forms = [entry.term, ...(entry.variants ?? [])]
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map(escapeRegExp);

  return new RegExp(`${LEFT}(?:${forms.join("|")})${RIGHT}`, "g");
}

export default async function () {
  let raw;
  try {
    raw = await fs.readFile(GLOSSARY, "utf8");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    return { version: null, conventionsVersion: null, terms: [], byScan: {} };
  }

  const doc = parse(raw) ?? {};
  const entries = doc.terms ?? [];

  const terms = entries.map((entry) => {
    if (!entry.id || !entry.term) {
      throw new Error(`glossary: every term needs an id and a term (near "${entry.id ?? entry.term}")`);
    }
    return {
      id: entry.id,
      term: entry.term,
      kind: entry.kind ?? null,
      expansion: entry.expansion ?? null,
      definition: (entry.definition ?? "").trim(),
      matcher: buildMatcher(entry),
    };
  });

  const pages = await loadPages();
  const byScan = {};

  for (const page of pages) {
    const text = page.text ?? "";
    const hits = [];

    for (const entry of terms) {
      entry.matcher.lastIndex = 0;
      const found = entry.matcher.exec(text);
      if (!found) continue;
      hits.push({ at: found.index, entry });
    }

    byScan[page.scanId] = hits
      .sort((a, b) => a.at - b.at)
      .map(({ entry: { matcher, ...rest } }) => rest);
  }

  return {
    version: doc.version ?? null,
    conventionsVersion: doc.conventions_version ?? null,
    terms: terms.map(({ matcher, ...rest }) => rest),
    byScan,
  };
}
