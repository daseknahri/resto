import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { messages } from "../src/i18n/messages.js";
import rawArabicMessages from "../src/i18n/messages-ar.js";
import rawEnglishMessages from "../src/i18n/messages-en.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = resolve(__filename, "..");
const projectRoot = resolve(__dirname, "..");

const isPlainObject = (value) => Boolean(value) && typeof value === "object" && !Array.isArray(value);

const flatten = (value, prefix = "") => {
  if (!isPlainObject(value)) return [];
  return Object.entries(value).flatMap(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (isPlainObject(item)) return flatten(item, path);
    return [[path, item]];
  });
};

const flattenLocale = (locale) => Object.fromEntries(flatten(locale));

const english = flattenLocale(messages.en);
const french = flattenLocale(messages.fr);

// NOTE: messages.ar (from messages.js) is a merged CLONE of `en` overlaid with
// the sparse messages-ar.js overrides (see mergeLocaleInto below in this same
// file's runtime equivalent) — it therefore ALWAYS contains every EN key by
// construction and is structurally incapable of reporting a missing key. To
// actually detect incomplete Arabic coverage we must diff the RAW hand-
// maintained source files directly: messages-ar.js (the real AR translations)
// against messages-en.js (the real EN source of truth), BEFORE any merge.
const rawEnglish = flattenLocale(rawEnglishMessages);
const rawArabic = flattenLocale(rawArabicMessages);

const missingArabic = Object.keys(rawEnglish).filter((key) => !(key in rawArabic));
// French has NO merge-fallback (unlike Arabic, which is overlaid onto a clone of
// EN) — a missing FR key renders as a raw key token in the UI, so it must fail.
const missingFrench = Object.keys(english).filter((key) => !(key in french));
const brokenArabic = Object.entries(rawArabic).filter(
  ([, value]) =>
    typeof value === "string" &&
    (value.includes("????") || /[ØÙÂ][^\s]*/.test(value)),
);

const sourceFiles = [
  resolve(projectRoot, "src/i18n/messages.js"),
  resolve(projectRoot, "src/i18n/messages-ar.js"),
  resolve(projectRoot, "src/i18n/config.js"),
];

const sourceIssues = sourceFiles.flatMap((filePath) => {
  const text = readFileSync(filePath, "utf8");
  const issues = [];
  if (/\?\?\?\?/.test(text)) {
    issues.push(`${filePath}: contains placeholder question-mark translations`);
  }
  if (/[\u00D8\u00D9\u00C2][^\s]*/.test(text)) {
    issues.push(`${filePath}: contains mojibake-like sequences`);
  }
  return issues;
});

console.log(`French missing keys: ${missingFrench.length}`);
if (missingFrench.length) {
  console.log("Missing French keys:");
  missingFrench.slice(0, 50).forEach((key) => console.log(`- ${key}`));
}
console.log(`Arabic missing keys: ${missingArabic.length}`);
console.log(`Arabic broken strings: ${brokenArabic.length}`);
console.log(`Arabic source issues: ${sourceIssues.length}`);

if (missingArabic.length) {
  console.log("Missing Arabic keys:");
  missingArabic.slice(0, 50).forEach((key) => console.log(`- ${key}`));
}

if (brokenArabic.length) {
  console.log("Broken Arabic strings:");
  brokenArabic.slice(0, 50).forEach(([key, value]) => console.log(`- ${key}: ${value}`));
}

if (sourceIssues.length) {
  console.log("Arabic source issues:");
  sourceIssues.slice(0, 50).forEach((issue) => console.log(`- ${issue}`));
}

if (missingArabic.length || missingFrench.length || brokenArabic.length || sourceIssues.length) {
  process.exitCode = 1;
} else {
  console.log("Locale verification passed (FR complete, AR complete).");
}
