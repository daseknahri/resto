const HOURS_LOCALES = ["en", "fr", "ar"];

export const WEEKDAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

const DAY_LABELS = {
  en: {
    mon: "Monday",
    tue: "Tuesday",
    wed: "Wednesday",
    thu: "Thursday",
    fri: "Friday",
    sat: "Saturday",
    sun: "Sunday",
  },
  fr: {
    mon: "Lundi",
    tue: "Mardi",
    wed: "Mercredi",
    thu: "Jeudi",
    fri: "Vendredi",
    sat: "Samedi",
    sun: "Dimanche",
  },
  ar: {
    mon: "الاثنين",
    tue: "الثلاثاء",
    wed: "الأربعاء",
    thu: "الخميس",
    fri: "الجمعة",
    sat: "السبت",
    sun: "الأحد",
  },
};

const DAY_SHORT_LABELS = {
  en: {
    mon: "Mon",
    tue: "Tue",
    wed: "Wed",
    thu: "Thu",
    fri: "Fri",
    sat: "Sat",
    sun: "Sun",
  },
  fr: {
    mon: "Lun",
    tue: "Mar",
    wed: "Mer",
    thu: "Jeu",
    fri: "Ven",
    sat: "Sam",
    sun: "Dim",
  },
  ar: {
    mon: "الإثنين",
    tue: "الثلاثاء",
    wed: "الأربعاء",
    thu: "الخميس",
    fri: "الجمعة",
    sat: "السبت",
    sun: "الأحد",
  },
};

const normalizeLocaleCode = (value) => {
  const normalized = String(value || "en").trim().toLowerCase();
  const primary = normalized.split("-", 1)[0];
  return HOURS_LOCALES.includes(primary) ? primary : "en";
};

const isTimeValue = (value) => /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(String(value || "").trim());

export const createDefaultBusinessHoursEntry = (overrides = {}) => ({
  enabled: Boolean(overrides.enabled),
  open: isTimeValue(overrides.open) ? String(overrides.open).trim() : "09:00",
  close: isTimeValue(overrides.close) ? String(overrides.close).trim() : "18:00",
});

export const createEmptyBusinessHoursSchedule = () =>
  Object.fromEntries(WEEKDAY_KEYS.map((day) => [day, createDefaultBusinessHoursEntry()]));

export const normalizeBusinessHoursSchedule = (value) => {
  const base = createEmptyBusinessHoursSchedule();
  if (!value || typeof value !== "object" || Array.isArray(value)) return base;

  WEEKDAY_KEYS.forEach((day) => {
    const raw = value[day];
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return;
    base[day] = createDefaultBusinessHoursEntry(raw);
  });

  return base;
};

export const hasEnabledBusinessHours = (schedule) =>
  WEEKDAY_KEYS.some((day) => Boolean(schedule?.[day]?.enabled));

export const formatBusinessHoursRows = (schedule, locale) => {
  const resolvedLocale = normalizeLocaleCode(locale);
  const normalizedSchedule = normalizeBusinessHoursSchedule(schedule);
  return WEEKDAY_KEYS.map((day) => {
    const entry = normalizedSchedule[day];
    return {
      key: day,
      label: DAY_LABELS[resolvedLocale][day],
      shortLabel: DAY_SHORT_LABELS[resolvedLocale][day],
      enabled: Boolean(entry.enabled),
      value: entry.enabled ? `${entry.open} - ${entry.close}` : "",
    };
  });
};

export const formatBusinessHoursSummary = (schedule, locale) => {
  const resolvedLocale = normalizeLocaleCode(locale);
  const rows = formatBusinessHoursRows(schedule, resolvedLocale).filter((row) => row.enabled && row.value);
  if (!rows.length) return "";

  const groups = [];
  rows.forEach((row) => {
    const previous = groups[groups.length - 1];
    if (previous && previous.value === row.value && previous.endIndex + 1 === WEEKDAY_KEYS.indexOf(row.key)) {
      previous.endKey = row.key;
      previous.endIndex = WEEKDAY_KEYS.indexOf(row.key);
      return;
    }
    groups.push({
      startKey: row.key,
      endKey: row.key,
      endIndex: WEEKDAY_KEYS.indexOf(row.key),
      value: row.value,
    });
  });

  return groups
    .map((group) => {
      const start = DAY_SHORT_LABELS[resolvedLocale][group.startKey];
      const end = DAY_SHORT_LABELS[resolvedLocale][group.endKey];
      const dayLabel = group.startKey === group.endKey ? start : `${start}-${end}`;
      return `${dayLabel} ${group.value}`;
    })
    .join(" | ");
};

export const buildBusinessHoursSummaries = (schedule) =>
  Object.fromEntries(HOURS_LOCALES.map((locale) => [locale, formatBusinessHoursSummary(schedule, locale)]));
