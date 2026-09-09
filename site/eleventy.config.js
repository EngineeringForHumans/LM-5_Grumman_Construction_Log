import { renderTranscript, renderPlainText } from "./_lib/transcript.js";

// GitHub Pages serves a project site from /repo-name/, a user site and a
// custom domain from /. The prefix therefore belongs to the deploy, not the
// repo, so it comes from the environment and defaults to root for local work.
const pathPrefix = process.env.ELEVENTY_PATH_PREFIX ?? "/";

export default function (eleventyConfig) {
  eleventyConfig.setInputDirectory("site");
  eleventyConfig.setOutputDirectory("_site");
  eleventyConfig.setIncludesDirectory("_includes");
  eleventyConfig.setDataDirectory("_data");

  // _lib holds modules the data files import. Eleventy would otherwise try to
  // treat anything under the input directory as content.
  eleventyConfig.ignores.add("site/_lib/**");

  eleventyConfig.addPassthroughCopy({ scans: "scans" });
  eleventyConfig.addPassthroughCopy({ "site/assets": "assets" });

  eleventyConfig.addFilter("transcript", function (record) {
    return renderTranscript(record.text, { sourceFile: record.sourceFile });
  });

  eleventyConfig.addFilter("plaintext", function (record) {
    return renderPlainText(record.text, { sourceFile: record.sourceFile });
  });

  eleventyConfig.addFilter("countStatus", (pages, status) =>
    pages.filter((p) => p.status === status).length,
  );

  // Returned config wins over setter methods, and --pathprefix on the command
  // line wins over both.
  return { pathPrefix };
}
