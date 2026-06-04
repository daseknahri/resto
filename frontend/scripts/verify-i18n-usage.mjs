/**
 * Verify that every literal i18n key referenced in the app (t('a.b'), $t("a.b"),
 * i18n.t('a.b')) actually exists in the English messages. Catches the class of
 * bug where a template key is misspelled or placed in the wrong namespace and
 * silently renders the raw key path at runtime.
 *
 * Dynamic keys (template literals / variables) can't be checked and are skipped.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { messages } from "../src/i18n/messages.js";

const __dirname = resolve(fileURLToPath(import.meta.url), "..");
const srcRoot = resolve(__dirname, "../src");

const isPlainObject = (v) => Boolean(v) && typeof v === "object" && !Array.isArray(v);
const flatten = (v, prefix = "") =>
  !isPlainObject(v)
    ? []
    : Object.entries(v).flatMap(([k, item]) => {
        const path = prefix ? `${prefix}.${k}` : k;
        return isPlainObject(item) ? flatten(item, path) : [path];
      });

const enKeys = new Set(flatten(messages.en));
// Plural bases: a key used as t('x.count') resolves x.count_one / x.count_other.
const PLURAL_SUFFIXES = ["_zero", "_one", "_two", "_few", "_many", "_other"];
const pluralBases = new Set();
for (const k of enKeys) {
  for (const suf of PLURAL_SUFFIXES) {
    if (k.endsWith(suf)) pluralBases.add(k.slice(0, -suf.length));
  }
}

const keyExists = (key) => enKeys.has(key) || pluralBases.has(key);

// Walk src for .vue/.js, skipping the message catalogues themselves.
const files = [];
const walk = (dir) => {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full);
    else if (/\.(vue|js)$/.test(name) && !/messages(-\w+)?\.js$/.test(name)) files.push(full);
  }
};
walk(srcRoot);

// Match t('a.b'), $t("a.b"), i18n.t('a.b') — literal single/double-quoted keys.
const RE = /(?<![\w$.])\$?t\(\s*(['"])([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)\1/g;

const missing = [];
for (const file of files) {
  const text = readFileSync(file, "utf8");
  const lines = text.split("\n");
  lines.forEach((line, i) => {
    let m;
    RE.lastIndex = 0;
    while ((m = RE.exec(line)) !== null) {
      const key = m[2];
      if (!keyExists(key)) {
        missing.push({ file: file.replace(srcRoot + "/", "src/").replace(srcRoot, "src"), line: i + 1, key });
      }
    }
  });
}

if (missing.length === 0) {
  console.log("i18n usage: all referenced keys exist in English. ✓");
  process.exit(0);
}

console.error(`i18n usage: ${missing.length} referenced key(s) missing from English messages:`);
for (const { file, line, key } of missing) {
  console.error(`  ${file}:${line}  ${key}`);
}
process.exit(1);
