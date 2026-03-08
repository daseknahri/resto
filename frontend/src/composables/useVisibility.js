import { onMounted, onBeforeUnmount, ref } from "vue";

export const useVisibility = (options = {}) => {
  const isVisible = ref(false);
  const target = ref(null);
  let observer = null;

  const cleanup = () => {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
  };

  const observe = () => {
    if (typeof IntersectionObserver === "undefined") {
      isVisible.value = true; // fallback: always visible
      return;
    }
    cleanup();
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            isVisible.value = true;
            if (!options.multiple) observer.disconnect();
          }
        });
      },
      { rootMargin: "0px 0px 200px 0px", threshold: 0.1, ...(options.observer || {}) }
    );
    if (target.value) observer.observe(target.value);
  };

  onMounted(observe);
  onBeforeUnmount(cleanup);

  return { isVisible, target };
};
