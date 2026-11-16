// Thin seam around the lazy `qrcode` import (S3-A B-10 coordinator fix).
// Vitest externalizes node_modules deps, so vi.mock('qrcode') cannot intercept
// the dynamic import (same observation as the S2 leaflet mock). Tests mock
// this module instead; production behaviour is unchanged.
export const loadQRCode = async () => (await import("qrcode")).default;
