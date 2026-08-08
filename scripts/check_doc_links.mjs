#!/usr/bin/env node
/**
 * Verify relative Markdown links in README + docs resolve to existing paths.
 * Skips http(s), mailto, and pure fragment links.
 */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, normalize, relative, resolve } from "node:path";

const root = resolve(new URL("..", import.meta.url).pathname);
const files = [];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const st = statSync(path);
    if (st.isDirectory()) {
      walk(path);
      continue;
    }
    if (name.endsWith(".md")) files.push(path);
  }
}

files.push(join(root, "README.md"));
walk(join(root, "docs"));
for (const extra of ["config/README.md", "migration/README.md", "semantic/README.md"]) {
  files.push(join(root, extra));
}

const linkRe = /!\[[^\]]*]\(([^)]+)\)|\[[^\]]*]\(([^)]+)\)/g;
let failures = 0;
let checked = 0;

for (const file of files) {
  const text = readFileSync(file, "utf8");
  let match;
  while ((match = linkRe.exec(text)) !== null) {
    const raw = (match[1] || match[2] || "").trim();
    if (!raw || raw.startsWith("http://") || raw.startsWith("https://") || raw.startsWith("mailto:")) {
      continue;
    }
    if (raw.startsWith("#")) continue;
    const [pathPart] = raw.split("#");
    if (!pathPart) continue;
    checked += 1;
    const target = normalize(resolve(dirname(file), pathPart));
    if (!target.startsWith(root)) {
      failures += 1;
      console.error(`Link escapes repo: ${relative(root, file)} -> ${raw}`);
      continue;
    }
    if (!existsSync(target)) {
      failures += 1;
      console.error(`Broken link: ${relative(root, file)} -> ${raw}`);
    }
  }
}

if (failures > 0) {
  console.error(`Failed ${failures} of ${checked} internal link(s).`);
  process.exit(1);
}

console.log(`OK: verified ${checked} internal link(s) across ${files.length} markdown file(s).`);
