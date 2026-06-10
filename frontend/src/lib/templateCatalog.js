/**
 * templateCatalog — single cached fetch of the starter-template summaries
 * (GET /owner/apply-template/). The list is static per deploy but is consumed
 * by several surfaces (TemplateGallery cards, StepTheme palette presets), so a
 * module-level cache keeps it to one request per page load. Errors are NOT
 * cached — the next caller retries. Concurrent callers share one in-flight
 * request.
 */
import api from "./api";

let cache = null;
let inflight = null;

export const fetchTemplateSummaries = () => {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = api
      .get("/owner/apply-template/")
      .then(({ data }) => {
        cache = Array.isArray(data.templates) ? data.templates : [];
        return cache;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
};

/** Test hook — reset the module cache between unit tests. */
export const __resetTemplateCatalog = () => {
  cache = null;
  inflight = null;
};
