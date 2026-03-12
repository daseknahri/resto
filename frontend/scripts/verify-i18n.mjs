import { messages } from "../src/i18n/messages.js";

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
const arabic = flattenLocale(messages.ar);

const missingArabic = Object.keys(english).filter((key) => !(key in arabic));
const brokenArabic = Object.entries(arabic).filter(
  ([, value]) =>
    typeof value === "string" &&
    (value.includes("????") || /[ØÙÂ][^\s]*/.test(value)),
);

console.log(`Arabic missing keys: ${missingArabic.length}`);
console.log(`Arabic broken strings: ${brokenArabic.length}`);

if (missingArabic.length) {
  console.log("Missing Arabic keys:");
  missingArabic.slice(0, 50).forEach((key) => console.log(`- ${key}`));
}

if (brokenArabic.length) {
  console.log("Broken Arabic strings:");
  brokenArabic.slice(0, 50).forEach(([key, value]) => console.log(`- ${key}: ${value}`));
}

if (missingArabic.length || brokenArabic.length) {
  process.exitCode = 1;
} else {
  console.log("Arabic locale verification passed.");
}
