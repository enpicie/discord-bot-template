// Template CI: build a starter zip exactly the way the page does, so CI can
// unzip it and run the generated bot's own checks.
//
//   node site/test/make_zip.mjs <site dir> <combination key> <bot name> <out.zip>
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { applyName, buildZip, validateName } from "../generator.js";

const [siteDir, key, name, outPath] = process.argv.slice(2);
if (!outPath) {
  console.error("usage: node site/test/make_zip.mjs <site dir> <combination key> <bot name> <out.zip>");
  process.exit(2);
}

const manifest = JSON.parse(await readFile(join(siteDir, "manifest.json"), "utf8"));
const nameError = validateName(name, manifest);
if (nameError) {
  console.error(`invalid name: ${nameError}`);
  process.exit(1);
}

const bundle = JSON.parse(await readFile(join(siteDir, "bundles", `${key}.json`), "utf8"));
const files = applyName(bundle, name, manifest);
await writeFile(outPath, buildZip(files, name));
console.log(`wrote ${outPath}: ${Object.keys(files).length} files (${key})`);
