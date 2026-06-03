import { ref, nextTick, onBeforeUnmount } from 'vue';

/**
 * In-app QR pay-code scanner using the native BarcodeDetector API (progressive
 * enhancement). Bind `videoEl` to a <video> element; call start(onDetect) to begin —
 * onDetect(rawValue) fires once when a QR is read, and scanning stops automatically.
 * Falls back gracefully (start() returns an error code) where BarcodeDetector is absent.
 */
export function usePayCodeScanner() {
  const scanning = ref(false);
  const videoEl = ref(null);
  let stream = null;
  let raf = null;

  const stop = () => {
    scanning.value = false;
    if (raf) { cancelAnimationFrame(raf); raf = null; }
    if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; }
  };

  const start = async (onDetect) => {
    if (!('BarcodeDetector' in window)) return 'unsupported';
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      scanning.value = true;
      await nextTick();
      if (!videoEl.value) { stop(); return 'no_video'; }
      videoEl.value.srcObject = stream;
      await videoEl.value.play();
      const detector = new window.BarcodeDetector({ formats: ['qr_code'] });
      const loop = async () => {
        if (!scanning.value || !videoEl.value) return;
        try {
          const codes = await detector.detect(videoEl.value);
          if (codes && codes.length) {
            const value = codes[0].rawValue;
            stop();
            onDetect(value);
            return;
          }
        } catch { /* keep scanning */ }
        raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
      return null;
    } catch {
      stop();
      return 'camera_failed';
    }
  };

  onBeforeUnmount(stop);

  return { scanning, videoEl, start, stop };
}
