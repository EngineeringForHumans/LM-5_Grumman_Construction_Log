import markdownIt from "markdown-it";

const md = markdownIt({ html: false, breaks: true, linkify: false });

export default function (eleventyConfig) {
  eleventyConfig.setInputDirectory("site");
  eleventyConfig.setOutputDirectory("_site");
  eleventyConfig.setIncludesDirectory("_includes");
  eleventyConfig.setDataDirectory("_data");

  eleventyConfig.addPassthroughCopy({ "scans": "scans" });

  eleventyConfig.addFilter("transcript", (text) => md.render(text ?? ""));
}

export const config = {
  pathPrefix: "/LM-5_Grumman_Construction_Log/",
};
