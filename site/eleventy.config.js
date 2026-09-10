import fs from "node:fs/promises";
import path from "node:path";
import markdownIt from "markdown-it";
import sharp from "sharp";

const PATH_PREFIX = "/LM-5_Grumman_Construction_Log/";

const SCANS = "scans";
const THUMBS = "_site/thumbs";
const THUMB_WIDTH = 180;
const TILES = "tiles";
const TILE_SIZE = 512;

const OSD = "node_modules/openseadragon/build/openseadragon";

const md = markdownIt({ html: false, breaks: true, linkify: false });

async function isFresh(source, out) {
  try {
    const [a, b] = await Promise.all([fs.stat(source), fs.stat(out)]);
    return b.mtimeMs >= a.mtimeMs;
  } catch {
    return false;
  }
}

async function buildThumbnails() {
  await fs.mkdir(THUMBS, { recursive: true });
  const files = (await fs.readdir(SCANS)).filter((f) => f.endsWith(".jpg"));
  let made = 0;

  for (const file of files) {
    const out = path.join(THUMBS, file);
    const source = path.join(SCANS, file);

    if (await isFresh(source, out)) continue;

    await sharp(source)
      .resize({ width: THUMB_WIDTH, withoutEnlargement: true })
      .jpeg({ quality: 72, mozjpeg: true })
      .toFile(out);
    made++;
  }

  if (made) console.log(`[thumbs] wrote ${made} of ${files.length}`);
}

async function buildTiles() {
  await fs.mkdir(TILES, { recursive: true });
  const files = (await fs.readdir(SCANS)).filter((f) => f.endsWith(".jpg"));
  let made = 0;

  for (const file of files) {
    const id = path.basename(file, ".jpg");
    const source = path.join(SCANS, file);

    if (await isFresh(source, path.join(TILES, `${id}.dzi`))) continue;

    await fs.rm(path.join(TILES, `${id}_files`), { recursive: true, force: true });
    await sharp(source)
      .jpeg({ quality: 82, mozjpeg: true })
      .tile({ size: TILE_SIZE, overlap: 1, layout: "dz" })
      .toFile(path.join(TILES, id));
    made++;
  }

  if (made) console.log(`[tiles] wrote ${made} of ${files.length} pyramids`);
}

function toCleanText(text) {
  return (text ?? "")
    .replace(/~~[^~]*~~\s*/g, "")
    .replace(/\[\?([^\]]+)\]/g, "$1")
    .replace(/\[illegible\]/g, "…");
}

export default function (eleventyConfig) {
  eleventyConfig.setInputDirectory("site");
  eleventyConfig.setOutputDirectory("_site");
  eleventyConfig.setIncludesDirectory("_includes");
  eleventyConfig.setDataDirectory("_data");

  eleventyConfig.addPassthroughCopy({ scans: "scans" });
  eleventyConfig.addPassthroughCopy({ "site/assets": "assets" });
  eleventyConfig.addPassthroughCopy({ [TILES]: "tiles" });
  eleventyConfig.addPassthroughCopy({
    [`${OSD}/openseadragon.min.js`]: "assets/openseadragon/openseadragon.min.js",
    [`${OSD}/images`]: "assets/openseadragon/images",
  });

  eleventyConfig.addFilter("transcript", (text) => md.render(text ?? ""));
  eleventyConfig.addFilter("clean", (text) => md.render(toCleanText(text)));

  eleventyConfig.addFilter("isodate", (value) => {
    if (!value) return "";
    if (value instanceof Date) return value.toISOString().slice(0, 10);
    return String(value).slice(0, 10);
  });

  eleventyConfig.addFilter("searchRecords", (records) =>
    records.map((record) => {
      const text = (record.text ?? "").replace(/\s+/g, " ").trim();
      return {
        number: record.number,
        url: `${PATH_PREFIX}page/${record.number}/`,
        text,
        haystack: text.toLowerCase(),
      };
    })
  );

  eleventyConfig.on("eleventy.before", buildTiles);
  eleventyConfig.on("eleventy.after", buildThumbnails);
}

export const config = {
  pathPrefix: PATH_PREFIX,
};
