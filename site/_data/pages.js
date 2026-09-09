import fs from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";

const CORPUS = path.resolve(import.meta.dirname, "../../transcripts");

export default async function () {
  const files = (await fs.readdir(CORPUS)).filter(f => f.endsWith(".md")).sort();

  return Promise.all(files.map(async (file) => {
    const raw = await fs.readFile(path.join(CORPUS, file), "utf8");
    const { data, content } = matter(raw);
    const scanId = path.basename(file, ".md");

    if (data.scan_id !== scanId) {
      throw new Error(`${file}: scan_id "${data.scan_id}" does not match filename`);
    }

    return {
      scanId,
      number: scanId.split("-").pop(),
      status: data.status ?? "raw",
      text: content.trim(),
    };
  }));
}
