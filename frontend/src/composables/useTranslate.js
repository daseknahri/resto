import { reactive, ref } from "vue";
import api from "../lib/api";

/**
 * Composable for calling the backend AI translation endpoint.
 *
 * Usage:
 *   const { translating, translateError, translateField } = useTranslate();
 *
 *   const result = await translateField("tagline", sourceText, "fr", "en");
 *   // returns translated string, or null on error
 */
export function useTranslate() {
  // key → boolean, tracks in-flight requests per field key
  const translating = reactive({});
  const translateError = ref("");

  async function translateField(fieldKey, text, targetLang, sourceLang = "auto") {
    const source = (text || "").trim();
    if (!source || !targetLang) return null;

    translating[fieldKey] = true;
    translateError.value = "";

    try {
      const res = await api.post("/translate/", {
        text: source,
        target_lang: targetLang,
        source_lang: sourceLang || "auto",
      });
      return String(res.data?.translated || "").trim() || null;
    } catch (err) {
      const code = err?.response?.data?.code;
      if (code === "not_configured") {
        translateError.value = "notConfigured";
      } else {
        translateError.value = err?.response?.data?.detail || "error";
      }
      return null;
    } finally {
      translating[fieldKey] = false;
    }
  }

  return { translating, translateError, translateField };
}
