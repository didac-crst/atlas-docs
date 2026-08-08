#!/usr/bin/env node
/**
 * Parse ```mermaid fences in README + docs (excluding archive) for syntax errors.
 * Does not render images; GitHub already renders Mermaid in the UI.
 *
 * jsdom globals must exist before mermaid is imported (DOMPurify binding).
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!DOCTYPE html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.DOMParser = dom.window.DOMParser;

const mermaid = (await import("mermaid")).default;

const root = new URL("..", import.meta.url).pathname;
const targets = [];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const st = statSync(path);
    if (st.isDirectory()) {
      if (name === "archive" && relative(join(root, "docs"), dir) === "") {
        continue;
      }
      walk(path);
      continue;
    }
    if (name.endsWith(".md")) targets.push(path);
  }
}

targets.push(join(root, "README.md"));
walk(join(root, "docs"));

mermaid.initialize({ startOnLoad: false });

const fence = /```mermaid\s*\n([\s\S]*?)```/gi;
let failures = 0;
let checked = 0;

for (const file of targets) {
  const text = readFileSync(file, "utf8");
  let match;
  let index = 0;
  while ((match = fence.exec(text)) !== null) {
    index += 1;
    checked += 1;
    const code = match[1].trim();
    try {
      await mermaid.parse(code);
    } catch (err) {
      failures += 1;
      const rel = relative(root, file);
      console.error(`Mermaid parse failed: ${rel} fence #${index}`);
      console.error(err instanceof Error ? err.message : err);
    }
  }
}

if (checked === 0) {
  console.error("No mermaid fences found in README/docs (excluding archive).");
  process.exit(1);
}

if (failures > 0) {
  console.error(`Failed ${failures} of ${checked} mermaid fence(s).`);
  process.exit(1);
}

console.log(`OK: parsed ${checked} mermaid fence(s) across ${targets.length} markdown file(s).`);
