import api from "../lib/api";
import { slugify } from "../lib/slug";
import { translate } from "../i18n/translate";
import { bustCache } from "../lib/staleCache";

// Cache names — must match the constants in the stores.
const META_CACHE = "meta";
const MENU_CACHE = "menu.categories";

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

const extractApiMessage = (err, fallback) => {
  const data = err?.response?.data;
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.non_field_errors) && data.non_field_errors.length) return String(data.non_field_errors[0]);
  if (data && typeof data === "object") {
    const firstList = Object.values(data).find((v) => Array.isArray(v) && v.length);
    if (firstList) return String(firstList[0]);
  }
  if (typeof data === "string" && data.trim()) return data;
  return fallback;
};

const extractFieldErrors = (err) => {
  const data = err?.response?.data;
  if (!data || typeof data !== "object" || Array.isArray(data)) return {};
  const entries = Object.entries(data).filter(([key, value]) => key !== "detail" && Array.isArray(value) && value.length);
  return Object.fromEntries(entries.map(([key, value]) => [key, String(value[0])]));
};

const asValidationError = (err, fallback) => {
  const wrapped = new Error(extractApiMessage(err, fallback));
  wrapped.fieldErrors = extractFieldErrors(err);
  wrapped.status = err?.response?.status;
  wrapped.raw = err;
  return wrapped;
};

const normalizeI18nMap = (value) => {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out = {};
  Object.entries(value).forEach(([rawLocale, rawText]) => {
    const locale = String(rawLocale || "").trim().toLowerCase();
    const text = String(rawText || "").trim();
    if (!locale || !text) return;
    out[locale] = text;
  });
  return out;
};

const localValidationError = (message, field = "image") => {
  const wrapped = new Error(message);
  wrapped.fieldErrors = { [field]: message };
  wrapped.status = 400;
  wrapped.raw = null;
  return wrapped;
};

const normalizeOptionalUrl = (value) => {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (raw.startsWith("/")) return raw;
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) return raw;
  if (raw.startsWith("//")) return `https:${raw}`;
  return `https://${raw}`;
};

const sanitizeProfilePayload = (payload) => {
  const next = { ...(payload || {}) };

  const trimString = (key) => {
    if (typeof next[key] === "string") next[key] = next[key].trim();
  };

  [
    "tagline",
    "description",
    "business_hours",
    "phone",
    "whatsapp",
    "address",
    "menu_disabled_note",
    "language",
    "primary_color",
    "secondary_color",
  ].forEach(trimString);

  ["tagline_i18n", "description_i18n", "address_i18n", "business_hours_i18n"].forEach((key) => {
    next[key] = normalizeI18nMap(next[key]);
  });

  if (!next.business_hours_schedule || typeof next.business_hours_schedule !== "object" || Array.isArray(next.business_hours_schedule)) {
    next.business_hours_schedule = {};
  }

  [
    "google_maps_url",
    "reservation_url",
    "facebook_url",
    "instagram_url",
    "tiktok_url",
    "logo_url",
    "hero_url",
  ].forEach((key) => {
    next[key] = normalizeOptionalUrl(next[key]);
  });

  if (typeof next.language === "string" && next.language) {
    next.language = next.language.toLowerCase().split("-")[0];
  }

  return next;
};

const isSlugConflict = (err) =>
  err?.response?.status === 400 &&
  Array.isArray(err?.response?.data?.slug) &&
  err.response.data.slug.length > 0;

const normalizeCurrency = (value) => {
  const cleaned = String(value || "MAD").trim().toUpperCase();
  if (/^[A-Z]{3}$/.test(cleaned)) return cleaned;
  return "MAD";
};

const withSlugRetry = async ({ requestFn, baseSlug, maxLen }) => {
  const cleanBase = (baseSlug || "item").replace(/^-+|-+$/g, "") || "item";
  let lastErr = null;
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const suffix = attempt === 0 ? "" : `-${attempt + 1}`;
    const slug = `${cleanBase}${suffix}`.slice(0, maxLen);
    try {
      return await requestFn(slug);
    } catch (err) {
      lastErr = err;
      if (!isSlugConflict(err)) throw err;
    }
  }
  throw lastErr;
};

export const profileApi = {
  async get() {
    const { data } = await api.get("/profile/");
    return data;
  },
  async save(payload) {
    try {
      const { data } = await api.put("/profile/", sanitizeProfilePayload(payload));
      // Profile is part of tenant meta — bust so next customer load gets fresh data.
      bustCache(META_CACHE);
      return data;
    } catch (err) {
      throw asValidationError(err, translate("onboardingApi.saveProfileFailed"));
    }
  },
};

export const superCategoryApi = {
  async list() {
    const { data } = await api.get("/super-categories/");
    return data;
  },
  async upsert(group) {
    const baseSlug = slugify(group.name || group.slug || "menu");
    const payload = {
      name: group.name || "",
      name_i18n: normalizeI18nMap(group.name_i18n),
      position: Number(group.position) || 0,
      is_published: group.is_published ?? true,
      is_temporarily_disabled: group.is_temporarily_disabled === true,
      disabled_note: String(group.disabled_note || "").trim(),
    };
    try {
      let result;
      if (group.id) {
        const slug = String(group.slug || baseSlug || "").trim();
        const updatePayload = slug ? { ...payload, slug } : payload;
        const { data } = await api.put(`/super-categories/${group.id}/`, updatePayload);
        result = data;
      } else {
        result = await withSlugRetry({
          baseSlug,
          maxLen: 160,
          requestFn: async (slug) => {
            const { data } = await api.post("/super-categories/", { ...payload, slug });
            return data;
          },
        });
      }
      // Bust the menu cache so the customer-facing menu reflects the change.
      // (Previously this ran after the try/catch and was unreachable — the
      // early returns inside try meant the cache was never invalidated.)
      bustCache(MENU_CACHE);
      return result;
    } catch (err) {
      throw asValidationError(err, translate("onboardingApi.saveSuperCategoryFailed"));
    }
  },
  async remove(id) {
    await api.delete(`/super-categories/${id}/`);
    bustCache(MENU_CACHE);
  },
};

export const categoryApi = {
  async list() {
    const { data } = await api.get("/categories/");
    return data;
  },
  async upsert(cat) {
    const baseSlug = slugify(cat.name || cat.slug || "category");
    const payload = {
      name: cat.name || "",
      name_i18n: normalizeI18nMap(cat.name_i18n),
      description: cat.description || "",
      description_i18n: normalizeI18nMap(cat.description_i18n),
      image_url: normalizeOptionalUrl(cat.image_url),
      super_category: Number(cat.super_category) || cat.super_category || null,
      position: Number(cat.position) || 0,
      is_published: cat.is_published ?? true,
    };
    try {
      let result;
      if (cat.id) {
        const slug = String(cat.slug || baseSlug || "").trim();
        const updatePayload = slug ? { ...payload, slug } : payload;
        const { data } = await api.put(`/categories/${cat.id}/`, updatePayload);
        result = data;
      } else {
        result = await withSlugRetry({
          baseSlug,
          maxLen: 160,
          requestFn: async (slug) => {
            const { data } = await api.post("/categories/", { ...payload, slug });
            return data;
          },
        });
      }
      bustCache(MENU_CACHE); // was unreachable after the early returns above
      return result;
    } catch (err) {
      throw asValidationError(err, translate("onboardingApi.saveCategoryFailed"));
    }
  },
  async remove(id) {
    await api.delete(`/categories/${id}/`);
    bustCache(MENU_CACHE);
  },
};

export const dishApi = {
  async list() {
    const { data } = await api.get("/dishes/");
    return data;
  },
  async upsert(dish) {
    const baseSlug = slugify(dish.name || dish.slug || "dish");
    const categoryId = Number(dish.category);
    const payload = {
      category: Number.isFinite(categoryId) && categoryId > 0 ? categoryId : dish.category,
      name: String(dish.name || "").trim(),
      name_i18n: normalizeI18nMap(dish.name_i18n),
      description: String(dish.description || "").trim(),
      description_i18n: normalizeI18nMap(dish.description_i18n),
      price: Number(dish.price) || 0,
      currency: normalizeCurrency(dish.currency),
      image_url: normalizeOptionalUrl(dish.image_url),
      tags: Array.isArray(dish.tags) ? dish.tags : [],
      allergens: Array.isArray(dish.allergens) ? dish.allergens : [],
      position: Number(dish.position) || 0,
      is_published: dish.is_published ?? true,
      attributes: dish.attributes && typeof dish.attributes === 'object' ? dish.attributes : {},
    };
    try {
      let result;
      if (dish.id) {
        const slug = String(dish.slug || baseSlug || "").trim();
        const updatePayload = slug ? { ...payload, slug } : payload;
        const { data } = await api.put(`/dishes/${dish.id}/`, updatePayload);
        result = data;
      } else {
        result = await withSlugRetry({
          baseSlug,
          maxLen: 210,
          requestFn: async (slug) => {
            const { data } = await api.post("/dishes/", { ...payload, slug });
            return data;
          },
        });
      }
      bustCache(MENU_CACHE); // was unreachable after the early returns above
      return result;
    } catch (err) {
      throw asValidationError(err, translate("onboardingApi.saveDishFailed"));
    }
  },
  async remove(id) {
    await api.delete(`/dishes/${id}/`);
    bustCache(MENU_CACHE);
  },
};

export const dishOptionApi = {
  async list(dishId = null) {
    const params = {};
    if (dishId) params.dish = dishId;
    const { data } = await api.get("/dish-options/", { params });
    return Array.isArray(data) ? data : [];
  },

  async upsert(option) {
    const payload = {
      dish: Number(option.dish),
      group: option.group != null ? Number(option.group) : null,
      name: String(option.name || "").trim(),
      name_i18n: normalizeI18nMap(option.name_i18n),
      price_delta: Number(option.price_delta) || 0,
      is_required: option.is_required === true,
      max_select: Math.max(1, Number(option.max_select) || 1),
      position: Number(option.position) || 0,
    };
    try {
      if (option.id) {
        const { data } = await api.put(`/dish-options/${option.id}/`, payload);
        return data;
      }
      const { data } = await api.post("/dish-options/", payload);
      return data;
    } catch (err) {
      throw asValidationError(err, translate("onboardingApi.saveDishOptionFailed"));
    }
  },

  async remove(id) {
    await api.delete(`/dish-options/${id}/`);
  },

  async syncForDish(dishId, desiredOptions = []) {
    const remoteOptions = await this.list(dishId);
    const keepIds = new Set();
    const sanitizedDesired = Array.isArray(desiredOptions)
      ? desiredOptions.filter((opt) => String(opt?.name || "").trim())
      : [];

    const savedOptions = [];
    for (const [optIdx, option] of sanitizedDesired.entries()) {
      const saved = await this.upsert({
        id: option.id,
        dish: dishId,
        name: option.name,
        name_i18n: option.name_i18n || {},
        price_delta: option.price_delta,
        is_required: option.is_required,
        max_select: option.max_select,
        position: option.position ?? optIdx,
      });
      if (saved?.id) keepIds.add(saved.id);
      savedOptions.push(saved);
    }

    for (const remote of remoteOptions) {
      if (remote?.id && !keepIds.has(remote.id)) {
        await this.remove(remote.id);
      }
    }

    return savedOptions;
  },
};

export const optionGroupApi = {
  async list(dishId = null) {
    const params = dishId ? { dish: dishId } : {};
    const { data } = await api.get("/option-groups/", { params });
    return Array.isArray(data) ? data : [];
  },

  async upsert(group) {
    const payload = {
      dish: Number(group.dish),
      name: String(group.name || "").trim(),
      name_i18n: normalizeI18nMap(group.name_i18n),
      min_select: Math.max(0, Number(group.min_select ?? 1)),
      max_select: Math.max(1, Number(group.max_select ?? 1)),
      position: Number(group.position) || 0,
    };
    try {
      if (group.id) {
        const { data } = await api.put(`/option-groups/${group.id}/`, payload);
        return data;
      }
      const { data } = await api.post("/option-groups/", payload);
      return data;
    } catch (err) {
      throw asValidationError(err, translate("onboardingApi.saveOptionGroupFailed"));
    }
  },

  async remove(id) {
    await api.delete(`/option-groups/${id}/`);
  },

  async syncForDish(dishId, desiredGroups = []) {
    const remoteGroups = await this.list(dishId);
    const keepGroupIds = new Set();
    const savedGroups = [];

    for (const [idx, group] of desiredGroups.entries()) {
      const name = String(group.name || "").trim();
      if (!name) continue;
      const saved = await this.upsert({ ...group, dish: dishId, position: idx });
      keepGroupIds.add(saved.id);

      const remoteGroup = remoteGroups.find((g) => g.id === group.id);
      const remoteOptions = remoteGroup?.options || [];
      const desiredOptions = (group.options || []).filter((o) => String(o.name || "").trim());
      const keepOptionIds = new Set();
      const savedOptions = [];

      for (const [optIdx, opt] of desiredOptions.entries()) {
        const savedOpt = await dishOptionApi.upsert({
          id: opt.id,
          dish: dishId,
          group: saved.id,
          name: opt.name,
          name_i18n: opt.name_i18n || {},
          price_delta: opt.price_delta || 0,
          is_required: false,
          max_select: 1,
          position: optIdx,
        });
        if (savedOpt?.id) keepOptionIds.add(savedOpt.id);
        savedOptions.push(savedOpt);
      }
      for (const remote of remoteOptions) {
        if (remote?.id && !keepOptionIds.has(remote.id)) {
          await dishOptionApi.remove(remote.id);
        }
      }
      savedGroups.push({ ...saved, options: savedOptions });
    }

    for (const remote of remoteGroups) {
      if (remote?.id && !keepGroupIds.has(remote.id)) {
        for (const opt of remote.options || []) {
          if (opt?.id) await dishOptionApi.remove(opt.id);
        }
        await this.remove(remote.id);
      }
    }
    return savedGroups;
  },
};

export const uploadApi = {
  async image(file, options = {}) {
    if (!file) throw localValidationError(translate("onboardingApi.imageRequired"));
    if (!String(file.type || "").startsWith("image/")) {
      throw localValidationError(translate("onboardingApi.imageTypeInvalid"));
    }
    if (Number(file.size || 0) > MAX_IMAGE_BYTES) {
      throw localValidationError(translate("onboardingApi.imageTooLarge"));
    }

    const form = new FormData();
    form.append("image", file);

    const variant = typeof options.variant === "string" ? options.variant.trim().toLowerCase() : "";
    if (variant) form.append("variant", variant);

    const onProgress = typeof options.onProgress === "function" ? options.onProgress : null;
    try {
      const { data } = await api.post("/uploads/image/", form, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (event) => {
          if (!onProgress || !event?.total) return;
          const pct = Math.max(0, Math.min(100, Math.round((event.loaded * 100) / event.total)));
          onProgress(pct);
        },
      });
      if (onProgress) onProgress(100);
      return data;
    } catch (err) {
      throw asValidationError(err, translate("onboardingApi.uploadImageFailed"));
    }
  },

  async removeImage(value) {
    if (!value) return { deleted: false };
    try {
      const { data } = await api.post("/uploads/image-delete/", { value });
      return data;
    } catch (err) {
      throw asValidationError(err, translate("onboardingApi.removeImageFailed"));
    }
  },
};

