import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import rawArabicMessages from "../src/i18n/messages-ar.js";
import rawEnglishMessages from "../src/i18n/messages-en.js";
import rawFrenchMessages from "../src/i18n/messages-fr.js";

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

// Single source of truth per locale (FE-1): the runtime files ARE the catalogs.
// EN (messages-en.js) is both the runtime EN and the parity source; FR
// (messages-fr.js) and AR (messages-ar.js) are checked for completeness against it.
const rawEnglish = flattenLocale(rawEnglishMessages);
const rawArabic = flattenLocale(rawArabicMessages);
const rawFrench = flattenLocale(rawFrenchMessages);

// AR runtime = clone-of-EN + sparse overrides, so it can never self-report a gap;
// diff the RAW hand-maintained AR source against the EN source of truth directly.
const missingArabic = Object.keys(rawEnglish).filter((key) => !(key in rawArabic));
// French has NO merge-fallback (unlike Arabic, which is overlaid onto a clone of
// EN) — a missing FR key renders as a raw key token in the UI, so it must fail.
const missingFrench = Object.keys(rawEnglish).filter((key) => !(key in rawFrench));
const brokenArabic = Object.entries(rawArabic).filter(
  ([, value]) =>
    typeof value === "string" &&
    (value.includes("????") || /[ØÙÂ][^\s]*/.test(value)),
);

// FR ASCII-only convention (OWNER-DECISION #12): French text is de-accented by
// convention to avoid mojibake. Flag any accented Latin letter (e-acute, a-grave,
// c-cedilla, o-circumflex, oe-ligature ...) or de-accenting typographic
// punctuation (guillemets, curly quotes, ellipsis) that slips into a FR string
// VALUE. Scoped to FR ONLY -- Arabic (messages-ar.js) is legitimately non-ASCII
// and is untouched here -- and deliberately narrow: emoji, em-/en-dashes, arrows,
// bullets, middle dot, degree and math signs are NOT flagged.
const FR_DEACCENT_PUNCT = new Set([
  "«", "»", "‹", "›", // guillemets  << >> < >
  "‘", "’", "“", "”", "‚", "„", // curly quotes
  "…", // ellipsis
]);
const FR_LIGATURES = new Set([
  "œ", "Œ", "æ", "Æ", // oe OE ae AE
  "ø", "Ø", "ß", // o-slash O-slash sharp-s
]);
const isAccentedLatin = (ch) => {
  if (FR_LIGATURES.has(ch)) return true;
  // A precomposed accented Latin letter NFD-decomposes to an ASCII base letter
  // plus one or more combining marks (e-acute -> "e" + U+0301), so the decomposed
  // form is longer than one code unit and starts with [A-Za-z]. Plain ASCII and
  // non-Latin (Arabic, emoji, dashes, symbols) do not match.
  const decomposed = ch.normalize("NFD");
  return decomposed.length > 1 && /^[A-Za-z]/.test(decomposed);
};
const isDeAccentingChar = (ch) => isAccentedLatin(ch) || FR_DEACCENT_PUNCT.has(ch);
const frNonAscii = Object.entries(rawFrench)
  .map(([key, value]) => {
    if (typeof value !== "string") return null;
    const offenders = [...new Set([...value].filter(isDeAccentingChar))];
    return offenders.length ? { key, chars: offenders.join(" "), value } : null;
  })
  .filter(Boolean);

const sourceFiles = [
  resolve(projectRoot, "src/i18n/messages-en.js"),
  resolve(projectRoot, "src/i18n/messages-fr.js"),
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
console.log(`French non-ASCII (accented) values: ${frNonAscii.length}`);
if (frNonAscii.length) {
  console.log(
    "French must be ASCII-only (de-accented) by convention. De-accent these value(s):",
  );
  frNonAscii
    .slice(0, 50)
    .forEach(({ key, chars, value }) => console.log(`- ${key}  [${chars}]  "${value}"`));
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

if (
  missingArabic.length ||
  missingFrench.length ||
  brokenArabic.length ||
  sourceIssues.length ||
  frNonAscii.length
) {
  process.exitCode = 1;
} else {
  console.log("Locale verification passed (FR complete + ASCII-only, AR complete).");
}
