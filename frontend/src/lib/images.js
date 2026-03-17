export const withImageFallback = (event, fallback = "") => {
  const img = event?.target;
  if (!(img instanceof HTMLImageElement)) return;
  img.onerror = null;
  if (fallback) {
    img.src = fallback;
    return;
  }
  img.style.display = "none";
};
