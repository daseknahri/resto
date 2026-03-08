<template>
  <div class="space-y-4 px-4 py-4 pb-32 sm:pb-6 ui-safe-bottom">
    <header class="ui-glass ui-reveal p-4 md:p-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p class="ui-kicker">Your selection</p>
          <h1 class="ui-display text-2xl font-semibold tracking-tight text-white md:text-3xl">Cart</h1>
          <p class="mt-1 text-xs text-slate-400">Plan: {{ planLabel }}</p>
          <p v-if="tableLabelModel" class="mt-1 text-xs text-slate-300">Table: {{ tableLabelModel }}</p>
        </div>
        <button
          v-if="cart.items.length"
          class="ui-btn-outline px-3 py-1.5 text-xs text-red-200 hover:border-red-400/50"
          @click="clearCart"
        >
          Clear
        </button>
      </div>
      <div class="mt-3 ui-divider"></div>
      <p class="mt-2 text-sm text-slate-300">Review items, adjust quantity, then send your order through WhatsApp.</p>
    </header>

    <div v-if="isBrowseOnlyPlan" class="rounded-2xl border border-sky-500/40 bg-sky-500/10 p-6 text-sky-100 space-y-2">
      <p class="text-base font-semibold">Ordering disabled</p>
      <p class="text-sm">This tenant plan allows browsing only right now. Cart and ordering actions are unavailable.</p>
    </div>

    <div v-else-if="!cart.items.length" class="rounded-2xl border border-dashed border-slate-700 p-6 text-slate-300">
      <p class="text-base font-semibold text-slate-100">Cart is empty.</p>
      <p class="mt-1 text-sm text-slate-400">Use navigation to browse the menu and continue your order.</p>
    </div>

    <div v-else class="space-y-3">
      <article
        v-for="(item, index) in cart.items"
        :key="item.key"
        class="ui-panel ui-surface-lift ui-reveal space-y-3 p-4"
        :style="{ '--ui-delay': `${Math.min(index, 9) * 28}ms` }"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="truncate text-base font-semibold text-slate-100">{{ item.name }}</p>
            <p class="text-xs text-slate-400">{{ formatPrice(item.price, item.currency) }} each</p>
            <p v-if="item.note" class="mt-1 text-xs text-slate-400">{{ item.note }}</p>
            <p v-else-if="item.option_labels?.length" class="mt-1 text-xs text-slate-400">
              Options: {{ item.option_labels.join(", ") }}
            </p>
          </div>
          <p class="text-right text-base font-semibold text-[var(--color-secondary)]">
            {{ formatPrice(item.price * item.qty, item.currency) }}
          </p>
        </div>

        <div class="flex items-center justify-between gap-3">
          <div class="inline-flex items-center rounded-full border border-slate-700 bg-slate-950/60 p-1">
            <button
              class="ui-touch-target ui-press h-8 w-8 rounded-full text-sm text-slate-200 hover:bg-slate-800"
              @click="cart.decrement(item.key)"
              aria-label="Decrease quantity"
            >
              -
            </button>
            <input
              :value="item.qty"
              type="number"
              min="1"
              max="99"
              inputmode="numeric"
              class="w-14 border-0 bg-transparent text-center text-sm text-slate-100 focus:outline-none"
              @change="setLineQty(item, $event)"
            />
            <button
              class="ui-touch-target ui-press h-8 w-8 rounded-full text-sm text-slate-200 hover:bg-slate-800"
              @click="cart.increment(item.key)"
              aria-label="Increase quantity"
            >
              +
            </button>
          </div>
          <button class="text-xs text-red-300 hover:text-red-200" @click="cart.remove(item.key)">Remove</button>
        </div>
      </article>
    </div>

    <section v-if="!isBrowseOnlyPlan" class="ui-glass space-y-3 p-5">
      <div v-if="isTableContextOrder" class="rounded-2xl border border-emerald-500/35 bg-emerald-500/10 p-3 text-sm text-emerald-100">
        <p class="font-semibold">Table QR order</p>
        <p class="mt-1">
          Table context detected{{ cart.tableLabel ? `: ${cart.tableLabel}` : "" }}.
          Only an optional note is required before sending to the restaurant.
        </p>
      </div>

      <div v-else class="space-y-3">
        <div class="grid gap-2 md:grid-cols-2">
          <button
            class="ui-btn-outline justify-center text-sm"
            :class="fulfillmentType === 'pickup' ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
            @click="fulfillmentType = 'pickup'"
          >
            Pickup
          </button>
          <button
            class="ui-btn-outline justify-center text-sm"
            :class="fulfillmentType === 'delivery' ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/10 text-[var(--color-secondary)]' : ''"
            @click="fulfillmentType = 'delivery'"
          >
            Delivery
          </button>
        </div>
        <p class="text-xs text-slate-400">Select fulfillment type before sending order.</p>
        <p v-if="fieldErrors.fulfillment_type" class="text-xs text-red-300">{{ fieldErrors.fulfillment_type }}</p>

        <div class="grid gap-3 md:grid-cols-2">
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">Customer name (required)</span>
            <input
              v-model.trim="customerNameModel"
              maxlength="80"
              class="ui-input"
              autocomplete="name"
              placeholder="Example: John"
              @input="clearFieldError('customer_name')"
            />
            <p v-if="fieldErrors.customer_name" class="text-xs text-red-300">{{ fieldErrors.customer_name }}</p>
          </label>
          <label class="block space-y-1">
            <span class="text-xs text-slate-400">Customer phone (required)</span>
            <input
              v-model.trim="customerPhoneModel"
              maxlength="30"
              class="ui-input"
              inputmode="tel"
              autocomplete="tel"
              placeholder="+212..."
              @input="clearFieldError('customer_phone')"
            />
            <p v-if="fieldErrors.customer_phone" class="text-xs text-red-300">{{ fieldErrors.customer_phone }}</p>
          </label>
        </div>

        <div v-if="isDelivery" class="space-y-3 rounded-2xl border border-slate-700/60 bg-slate-950/45 p-3">
          <div class="space-y-1 rounded-xl border border-slate-700/60 bg-slate-900/40 px-3 py-2">
            <p class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Delivery location</p>
            <p class="text-xs text-slate-300">
              Choose one: use current location, paste map link, or enter coordinates manually.
            </p>
          </div>

          <label class="block space-y-1">
            <span class="text-xs text-slate-400">Delivery address (required)</span>
            <textarea
              v-model.trim="deliveryAddress"
              rows="2"
              maxlength="180"
              class="ui-textarea"
              placeholder="Street, building, floor, area..."
              @input="clearFieldError('delivery_address')"
            ></textarea>
            <p v-if="fieldErrors.delivery_address" class="text-xs text-red-300">{{ fieldErrors.delivery_address }}</p>
          </label>

          <div class="grid gap-2 md:grid-cols-[auto,1fr] md:items-center">
            <button class="ui-btn-outline px-3 py-2 text-xs" :disabled="locating" @click="useCurrentLocation">
              {{ locating ? "Locating..." : "Use current location" }}
            </button>
            <p class="text-xs text-slate-400">
              {{
                hasLocationCoords
                  ? `Location ready: ${formatCoordinate(deliveryLat)}, ${formatCoordinate(deliveryLng)}`
                  : "No coordinates yet."
              }}
            </p>
          </div>
          <div class="grid grid-cols-2 gap-2 md:grid-cols-4">
            <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="openInAppMapPicker">
              Pick pin in app
            </button>
            <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="openExternalMap">
              Open external map
            </button>
            <button
              class="ui-btn-outline px-3 py-1.5 text-xs"
              :disabled="!hasLocationCoords && !deliveryLocationUrl"
              @click="clearLocation"
            >
              Clear location
            </button>
            <button
              class="ui-btn-outline px-3 py-1.5 text-xs"
              :disabled="!hasLocationCoords"
              @click="copyCoordinates"
            >
              Copy coordinates
            </button>
          </div>
          <p v-if="locationError" class="text-xs text-red-300">{{ locationError }}</p>

          <label class="block space-y-1">
            <span class="text-xs text-slate-400">Map pin URL (optional if location captured)</span>
            <input
              v-model.trim="deliveryLocationUrl"
              maxlength="500"
              class="ui-input"
              inputmode="url"
              placeholder="https://maps.google.com/..."
              @input="clearFieldError('delivery_location_url')"
            />
            <p v-if="fieldErrors.delivery_location_url" class="text-xs text-red-300">{{ fieldErrors.delivery_location_url }}</p>
          </label>

          <div class="grid gap-3 md:grid-cols-2">
            <label class="block space-y-1">
              <span class="text-xs text-slate-400">Latitude (optional)</span>
              <input
                v-model.number="deliveryLat"
                type="number"
                step="any"
                class="ui-input"
                inputmode="decimal"
                placeholder="33.5731"
                @input="clearFieldError('delivery_lat')"
              />
              <p v-if="fieldErrors.delivery_lat" class="text-xs text-red-300">{{ fieldErrors.delivery_lat }}</p>
            </label>
            <label class="block space-y-1">
              <span class="text-xs text-slate-400">Longitude (optional)</span>
              <input
                v-model.number="deliveryLng"
                type="number"
                step="any"
                class="ui-input"
                inputmode="decimal"
                placeholder="-7.5898"
                @input="clearFieldError('delivery_lng')"
              />
              <p v-if="fieldErrors.delivery_lng" class="text-xs text-red-300">{{ fieldErrors.delivery_lng }}</p>
            </label>
          </div>
        </div>
      </div>

      <label class="block space-y-1">
        <span class="text-xs text-slate-400">Optional note for restaurant</span>
        <textarea
          v-model.trim="customerNote"
          rows="2"
          maxlength="300"
          class="ui-textarea"
          :placeholder="isTableContextOrder ? 'Example: no onion, extra sauce' : 'Example: call on arrival, special instructions'"
        ></textarea>
      </label>

      <div class="rounded-2xl border border-slate-700/60 bg-slate-950/50 px-4 py-3">
        <div class="flex items-center justify-between text-sm text-slate-300">
          <span>Total</span>
          <span class="text-lg font-semibold text-[var(--color-secondary)]">{{ formatPrice(cart.total, currency) }}</span>
        </div>
        <p class="mt-1 text-xs text-slate-500">
          Channel: {{ cart.canCheckout ? "Checkout" : cart.canWhatsapp ? "WhatsApp handoff" : "Ordering disabled" }}
        </p>
      </div>

      <button
        v-if="cart.canCheckout"
        class="ui-btn-primary w-full justify-center"
        :disabled="processingCheckout"
        @click="startCheckout"
      >
        {{ processingCheckout ? "Preparing checkout..." : "Proceed to checkout (Growth/Pro)" }}
      </button>

      <button
        v-else-if="cart.canWhatsapp"
        class="ui-btn-primary w-full justify-center"
        :disabled="sendingWhatsapp"
        @click="openWhatsApp"
      >
        {{ sendingWhatsapp ? "Preparing WhatsApp..." : "Send order via WhatsApp" }}
      </button>

      <button
        v-else
        class="w-full inline-flex items-center justify-center rounded-full border border-slate-700 px-5 py-3 text-slate-50"
        disabled
      >
        Ordering disabled on this plan
      </button>

      <p v-if="!cart.canCheckout" class="text-xs text-slate-400">
        {{ cart.canWhatsapp ? "WhatsApp handoff is enabled on your current plan." : "Ordering is disabled on your current plan." }}
      </p>

      <div v-if="unavailableSlugs.length" class="space-y-2 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-100">
        <p>Unavailable items detected: {{ unavailableSlugs.join(", ") }}</p>
        <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="removeUnavailable">
          Remove unavailable items
        </button>
      </div>

      <p v-if="checkoutError" class="text-xs text-red-300">{{ checkoutError }}</p>
      <p v-if="handoffError" class="text-xs text-red-300">{{ handoffError }}</p>
    </section>

    <div
      v-if="!isBrowseOnlyPlan && cart.items.length"
      class="fixed bottom-20 left-3 right-3 z-20 rounded-2xl border border-slate-700/80 bg-slate-950/92 p-3 shadow-xl shadow-black/40 backdrop-blur sm:hidden"
    >
      <div class="flex items-center justify-between gap-2">
        <div>
          <p class="text-xs text-slate-400">Total</p>
          <p class="text-lg font-semibold text-[var(--color-secondary)]">{{ formatPrice(cart.total, currency) }}</p>
        </div>
        <button
          v-if="cart.canCheckout"
          class="ui-btn-primary px-4 py-2 text-sm"
          :disabled="processingCheckout"
          @click="startCheckout"
        >
          {{ processingCheckout ? "Loading..." : "Checkout" }}
        </button>
        <button
          v-else-if="cart.canWhatsapp"
          class="ui-btn-primary px-4 py-2 text-sm"
          :disabled="sendingWhatsapp"
          @click="openWhatsApp"
        >
          {{ sendingWhatsapp ? "Loading..." : "WhatsApp" }}
        </button>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="showMapModal"
        class="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/85 p-3 sm:items-center sm:p-5"
      >
        <div class="w-full max-w-2xl rounded-2xl border border-slate-700/70 bg-slate-950 shadow-2xl shadow-black/50">
          <header class="flex items-center justify-between gap-3 border-b border-slate-800 px-4 py-3">
            <div>
              <p class="ui-kicker">Map picker</p>
              <h2 class="text-base font-semibold text-slate-100">Tap map to choose delivery pin</h2>
            </div>
            <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeMapModal">Close</button>
          </header>

          <div class="space-y-3 p-3">
            <p class="text-xs text-slate-400">
              Selected:
              {{
                hasTemporaryMapSelection
                  ? `${formatCoordinate(temporaryMapLat)}, ${formatCoordinate(temporaryMapLng)}`
                  : "No pin selected yet."
              }}
            </p>
            <div ref="mapContainerRef" class="h-[52vh] min-h-[280px] w-full overflow-hidden rounded-xl border border-slate-700/80"></div>
            <div class="flex flex-wrap items-center justify-end gap-2">
              <button class="ui-btn-outline px-3 py-1.5 text-xs" @click="closeMapModal">Cancel</button>
              <button class="ui-btn-primary px-4 py-2 text-sm" :disabled="!hasTemporaryMapSelection" @click="applyMapSelection">
                Use selected pin
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useCartStore } from "../stores/cart";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";
import api from "../lib/api";
import { trackEvent } from "../lib/analytics";

const cart = useCartStore();
const tenant = useTenantStore();
const toast = useToastStore();

const sendingWhatsapp = ref(false);
const processingCheckout = ref(false);
const handoffError = ref("");
const checkoutError = ref("");
const customerNote = ref("");
const unavailableSlugs = ref([]);

const fulfillmentType = ref("");
const deliveryAddress = ref("");
const deliveryLocationUrl = ref("");
const deliveryLat = ref(null);
const deliveryLng = ref(null);
const locating = ref(false);
const locationError = ref("");
const fieldErrors = ref({});
const showMapModal = ref(false);
const mapContainerRef = ref(null);
const leafletMap = ref(null);
const leafletMarker = ref(null);
const leafletModuleRef = ref(null);
const leafletAssetsReady = ref(false);
const temporaryMapLat = ref(null);
const temporaryMapLng = ref(null);

const parseCoordinateValue = (value) => {
  if (value === null || value === undefined) return null;
  const raw = String(value).trim();
  if (!raw) return null;
  const number = Number(raw);
  return Number.isFinite(number) ? number : null;
};

const currency = computed(() => {
  const firstItemCurrency = cart.items.find((item) => item.currency)?.currency;
  return firstItemCurrency || tenant.meta?.plan?.currency || "USD";
});
const planLabel = computed(() => tenant.meta?.plan?.tier_name || tenant.meta?.plan?.name || "Basic");
const isBrowseOnlyPlan = computed(() => tenant.isBrowseOnlyPlan === true);
const tableLabelModel = computed(() => cart.tableLabel || "");
const isTableContextOrder = computed(() => Boolean(cart.tableSlug || cart.tableLabel));
const isDelivery = computed(() => !isTableContextOrder.value && fulfillmentType.value === "delivery");
const hasLocationCoords = computed(() => {
  const lat = parseCoordinateValue(deliveryLat.value);
  const lng = parseCoordinateValue(deliveryLng.value);
  return lat !== null && lng !== null;
});
const hasTemporaryMapSelection = computed(() => {
  const lat = parseCoordinateValue(temporaryMapLat.value);
  const lng = parseCoordinateValue(temporaryMapLng.value);
  return lat !== null && lng !== null;
});

const customerNameModel = computed({
  get: () => cart.customerName || "",
  set: (value) => cart.setCustomerName(value),
});
const customerPhoneModel = computed({
  get: () => cart.customerPhone || "",
  set: (value) => cart.setCustomerPhone(value),
});

const formatPrice = (value, curr = "USD") =>
  new Intl.NumberFormat("en", { style: "currency", currency: curr }).format(value || 0);
const formatCoordinate = (value) => {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return number.toFixed(6);
};

const clearFieldError = (field) => {
  if (!fieldErrors.value?.[field]) return;
  const next = { ...fieldErrors.value };
  delete next[field];
  fieldErrors.value = next;
};

const setLineQty = (item, event) => {
  const next = Number(event?.target?.value || item.qty);
  cart.setQty(item.key, next);
};

const clearCart = () => {
  cart.clear();
  unavailableSlugs.value = [];
  toast.show("Cart cleared", "info");
};

const parseCoordinatesFromMapUrl = (value) => {
  const raw = String(value || "").trim();
  if (!raw) return null;
  let match = raw.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/);
  if (!match) {
    match = raw.match(/[?&](?:q|query|ll|destination)=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/i);
  }
  if (!match) {
    match = raw.match(/#map=\d+\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)/i);
  }
  if (!match) return null;
  const lat = Number(match[1]);
  const lng = Number(match[2]);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
  return { lat: Number(lat.toFixed(6)), lng: Number(lng.toFixed(6)) };
};

const setLocationCoordinates = (lat, lng) => {
  deliveryLat.value = Number(Number(lat).toFixed(6));
  deliveryLng.value = Number(Number(lng).toFixed(6));
  clearFieldError("delivery_lat");
  clearFieldError("delivery_lng");
  clearFieldError("delivery_location_url");
};

const resolveMapCenter = () => {
  const lat = parseCoordinateValue(deliveryLat.value);
  const lng = parseCoordinateValue(deliveryLng.value);
  if (lat !== null && lng !== null) {
    return { lat, lng, zoom: 16, hasMarker: true };
  }
  const parsedFromUrl = parseCoordinatesFromMapUrl(deliveryLocationUrl.value);
  if (parsedFromUrl) {
    return { lat: parsedFromUrl.lat, lng: parsedFromUrl.lng, zoom: 16, hasMarker: true };
  }
  return { lat: 33.5731, lng: -7.5898, zoom: 12, hasMarker: false };
};

const ensureLeafletLoaded = async () => {
  if (leafletModuleRef.value) return leafletModuleRef.value;

  const [{ default: Leaflet }, marker2x, marker, shadow] = await Promise.all([
    import("leaflet"),
    import("leaflet/dist/images/marker-icon-2x.png"),
    import("leaflet/dist/images/marker-icon.png"),
    import("leaflet/dist/images/marker-shadow.png"),
  ]);

  if (!leafletAssetsReady.value) {
    await import("leaflet/dist/leaflet.css");
    delete Leaflet.Icon.Default.prototype._getIconUrl;
    Leaflet.Icon.Default.mergeOptions({
      iconRetinaUrl: marker2x.default,
      iconUrl: marker.default,
      shadowUrl: shadow.default,
    });
    leafletAssetsReady.value = true;
  }

  leafletModuleRef.value = Leaflet;
  return Leaflet;
};

const updateLeafletMarker = (lat, lng) => {
  if (!leafletMap.value) return;
  if (!leafletMarker.value) {
    const Leaflet = leafletModuleRef.value;
    leafletMarker.value = Leaflet.marker([lat, lng]).addTo(leafletMap.value);
    return;
  }
  leafletMarker.value.setLatLng([lat, lng]);
};

const removeLeafletMarker = () => {
  if (!leafletMap.value || !leafletMarker.value) return;
  leafletMap.value.removeLayer(leafletMarker.value);
  leafletMarker.value = null;
};

const initLeafletMap = async () => {
  if (!mapContainerRef.value) return;
  const Leaflet = await ensureLeafletLoaded();
  const center = resolveMapCenter();

  if (!leafletMap.value) {
    leafletMap.value = Leaflet.map(mapContainerRef.value, {
      zoomControl: true,
      attributionControl: true,
    });
    Leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(leafletMap.value);
    leafletMap.value.on("click", (event) => {
      const lat = Number(event?.latlng?.lat);
      const lng = Number(event?.latlng?.lng);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
      temporaryMapLat.value = Number(lat.toFixed(6));
      temporaryMapLng.value = Number(lng.toFixed(6));
      updateLeafletMarker(temporaryMapLat.value, temporaryMapLng.value);
    });
  }

  leafletMap.value.setView([center.lat, center.lng], center.zoom);
  leafletMap.value.invalidateSize();

  if (center.hasMarker) {
    temporaryMapLat.value = Number(center.lat.toFixed(6));
    temporaryMapLng.value = Number(center.lng.toFixed(6));
    updateLeafletMarker(temporaryMapLat.value, temporaryMapLng.value);
  } else {
    temporaryMapLat.value = null;
    temporaryMapLng.value = null;
    removeLeafletMarker();
  }
};

const openInAppMapPicker = () => {
  showMapModal.value = true;
  trackEvent("contact_click", {
    source: "cart_delivery_location",
    metadata: { action: "open_in_app_map_picker" },
  });
};

const closeMapModal = () => {
  showMapModal.value = false;
};

const applyMapSelection = () => {
  const lat = parseCoordinateValue(temporaryMapLat.value);
  const lng = parseCoordinateValue(temporaryMapLng.value);
  if (lat === null || lng === null) {
    toast.show("Select a pin on the map first.", "error");
    return;
  }
  setLocationCoordinates(lat, lng);
  deliveryLocationUrl.value = `https://maps.google.com/?q=${deliveryLat.value},${deliveryLng.value}`;
  clearFieldError("delivery_location_url");
  locationError.value = "";
  closeMapModal();
  trackEvent("contact_click", {
    source: "cart_delivery_location",
    metadata: { action: "map_pin_selected" },
  });
  toast.show("Delivery pin selected", "success");
};

const clearLocation = () => {
  deliveryLocationUrl.value = "";
  deliveryLat.value = null;
  deliveryLng.value = null;
  temporaryMapLat.value = null;
  temporaryMapLng.value = null;
  removeLeafletMarker();
  locationError.value = "";
  clearFieldError("delivery_location_url");
  clearFieldError("delivery_lat");
  clearFieldError("delivery_lng");
};

const copyCoordinates = async () => {
  const lat = parseCoordinateValue(deliveryLat.value);
  const lng = parseCoordinateValue(deliveryLng.value);
  if (lat === null || lng === null) return;
  try {
    await navigator.clipboard.writeText(`${lat},${lng}`);
    toast.show("Coordinates copied", "success");
  } catch (err) {
    toast.show("Unable to copy coordinates", "error");
  }
};

watch(deliveryLocationUrl, (value) => {
  const parsed = parseCoordinatesFromMapUrl(value);
  if (parsed) {
    setLocationCoordinates(parsed.lat, parsed.lng);
  }
});

watch(isTableContextOrder, (value) => {
  if (!value) return;
  fieldErrors.value = {};
  locationError.value = "";
});

watch(fulfillmentType, (value) => {
  clearFieldError("fulfillment_type");
  if (value !== "delivery") {
    closeMapModal();
    deliveryAddress.value = "";
    deliveryLocationUrl.value = "";
    deliveryLat.value = null;
    deliveryLng.value = null;
    temporaryMapLat.value = null;
    temporaryMapLng.value = null;
    removeLeafletMarker();
    locationError.value = "";
    clearFieldError("delivery_address");
    clearFieldError("delivery_location_url");
    clearFieldError("delivery_lat");
    clearFieldError("delivery_lng");
  }
});

watch(showMapModal, async (value) => {
  if (!value) return;
  await nextTick();
  try {
    await initLeafletMap();
  } catch (err) {
    toast.show("Unable to load map picker. Use external map link.", "error");
    showMapModal.value = false;
  }
});

const useCurrentLocation = () => {
  locationError.value = "";
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    locationError.value = "Location is not supported on this device/browser.";
    return;
  }
  locating.value = true;
  navigator.geolocation.getCurrentPosition(
    (position) => {
      const lat = position?.coords?.latitude;
      const lng = position?.coords?.longitude;
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
        locationError.value = "Unable to read your GPS location.";
        locating.value = false;
        return;
      }
      setLocationCoordinates(lat, lng);
      if (!deliveryLocationUrl.value) {
        deliveryLocationUrl.value = `https://maps.google.com/?q=${deliveryLat.value},${deliveryLng.value}`;
      }
      trackEvent("contact_click", {
        source: "cart_delivery_location",
        metadata: { action: "use_current_location" },
      });
      locationError.value = "";
      locating.value = false;
    },
    (err) => {
      if (err?.code === 1) {
        locationError.value = "Location permission denied.";
      } else if (err?.code === 3) {
        locationError.value = "Location request timed out. Retry.";
      } else {
        locationError.value = "Unable to capture your location.";
      }
      locating.value = false;
    },
    {
      enableHighAccuracy: true,
      timeout: 12000,
      maximumAge: 60000,
    }
  );
};

const openExternalMap = () => {
  const lat = parseCoordinateValue(deliveryLat.value);
  const lng = parseCoordinateValue(deliveryLng.value);
  const url = lat !== null && lng !== null
    ? `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`
    : "https://www.google.com/maps";
  window.open(url, "_blank", "noopener,noreferrer");
  trackEvent("contact_click", {
    source: "cart_delivery_location",
    metadata: { action: "open_external_map" },
  });
  toast.show("Open map and share location link back if needed.", "info");
};

const validateForm = () => {
  if (isTableContextOrder.value) {
    fieldErrors.value = {};
    return true;
  }

  const errors = {};
  if (!fulfillmentType.value) {
    errors.fulfillment_type = "Select pickup or delivery.";
  }
  if (!cart.customerName) {
    errors.customer_name = "Customer name is required.";
  }
  if (!cart.customerPhone) {
    errors.customer_phone = "Customer phone is required.";
  }
  if (fulfillmentType.value === "delivery") {
    if (!deliveryAddress.value) {
      errors.delivery_address = "Delivery address is required.";
    }
    const latValue = parseCoordinateValue(deliveryLat.value);
    const lngValue = parseCoordinateValue(deliveryLng.value);
    const hasLat = latValue !== null;
    const hasLng = lngValue !== null;
    if (hasLat && (latValue < -90 || latValue > 90)) {
      errors.delivery_lat = "Latitude must be between -90 and 90.";
    }
    if (hasLng && (lngValue < -180 || lngValue > 180)) {
      errors.delivery_lng = "Longitude must be between -180 and 180.";
    }
    if (hasLat !== hasLng) {
      errors.delivery_lat = "Latitude and longitude must be provided together.";
      errors.delivery_lng = "Latitude and longitude must be provided together.";
    }
    if (!hasLocationCoords.value && !deliveryLocationUrl.value.trim()) {
      errors.delivery_location_url = "Provide map link or use current location.";
    }
  }

  fieldErrors.value = errors;
  if (Object.keys(errors).length) {
    toast.show("Please complete required order details.", "error");
    return false;
  }
  return true;
};

const buildPayload = () => {
  const payload = {
    items: cart.items.map((item) => ({
      slug: item.slug,
      qty: item.qty,
      ...(Array.isArray(item.option_ids) && item.option_ids.length ? { option_ids: item.option_ids } : {}),
      ...(item.note ? { note: item.note } : {}),
    })),
  };

  if (customerNote.value) payload.customer_note = customerNote.value;
  if (cart.tableLabel) payload.table_label = cart.tableLabel;
  if (cart.tableSlug) payload.table_slug = cart.tableSlug;

  if (!isTableContextOrder.value) {
    if (fulfillmentType.value) payload.fulfillment_type = fulfillmentType.value;
    if (cart.customerName) payload.customer_name = cart.customerName;
    if (cart.customerPhone) payload.customer_phone = cart.customerPhone;
    if (isDelivery.value) {
      const latValue = parseCoordinateValue(deliveryLat.value);
      const lngValue = parseCoordinateValue(deliveryLng.value);
      if (deliveryAddress.value) payload.delivery_address = deliveryAddress.value;
      if (deliveryLocationUrl.value) payload.delivery_location_url = deliveryLocationUrl.value;
      if (latValue !== null && lngValue !== null) {
        payload.delivery_lat = Number(latValue.toFixed(6));
        payload.delivery_lng = Number(lngValue.toFixed(6));
      }
    }
  }
  return payload;
};

const assignFieldErrors = (data) => {
  if (!data || typeof data !== "object") return;
  const mapped = {};
  const keys = [
    "fulfillment_type",
    "customer_name",
    "customer_phone",
    "delivery_address",
    "delivery_location_url",
    "delivery_lat",
    "delivery_lng",
  ];
  keys.forEach((key) => {
    const value = data[key];
    if (Array.isArray(value) && value.length) {
      mapped[key] = String(value[0]);
    } else if (typeof value === "string" && value.trim()) {
      mapped[key] = value.trim();
    }
  });
  if (Object.keys(mapped).length) {
    fieldErrors.value = { ...fieldErrors.value, ...mapped };
  }
};

const mapOrderApiError = (err, fallback) => {
  const data = err?.response?.data || {};
  const code = data?.code || "";
  const unavailable = Array.isArray(data?.unavailable_slugs) ? data.unavailable_slugs : [];
  unavailableSlugs.value = unavailable;
  const note = typeof data?.note === "string" && data.note.trim() ? data.note.trim() : "";

  assignFieldErrors(data);

  if (code === "items_unavailable" && unavailable.length) {
    return `Some items are unavailable: ${unavailable.join(", ")}. Remove them and retry.`;
  }
  if (code === "plan_forbidden" || code === "plan_forbidden_checkout") {
    return "This action is not available on your current plan.";
  }
  if (code === "menu_unpublished") {
    return "Menu is not published yet.";
  }
  if (code === "restaurant_closed") {
    return "Restaurant is currently closed.";
  }
  if (code === "contact_missing") {
    return "Restaurant contact is not configured yet.";
  }
  if (code === "table_unavailable") {
    return "This table QR link is unavailable. Please rescan or ask staff for a new QR.";
  }
  if (code === "mixed_currency") {
    return "Cart has mixed currencies. Please keep one currency per order.";
  }
  if (code === "menu_temporarily_disabled") {
    return note ? `Menu is temporarily unavailable. ${note}` : "Menu is temporarily unavailable.";
  }
  if (data && typeof data === "object") {
    const firstList = Object.values(data).find((v) => Array.isArray(v) && v.length);
    if (firstList) return String(firstList[0]);
  }
  if (typeof data?.detail === "string" && data.detail.trim()) {
    return data.detail;
  }
  return fallback;
};

const removeUnavailable = () => {
  if (!unavailableSlugs.value.length) return;
  const blocked = new Set(unavailableSlugs.value);
  const toRemove = cart.items.filter((item) => blocked.has(item.slug)).map((item) => item.key);
  toRemove.forEach((key) => cart.remove(key));
  unavailableSlugs.value = [];
  toast.show("Unavailable items removed", "success");
};

const startCheckout = async () => {
  checkoutError.value = "";
  handoffError.value = "";
  unavailableSlugs.value = [];
  fieldErrors.value = {};
  if (!cart.canCheckout) return;
  if (!cart.items.length) {
    toast.show("Cart is empty.", "error");
    return;
  }
  if (!validateForm()) return;

  processingCheckout.value = true;
  try {
    trackEvent("checkout_click", {
      source: "cart_checkout",
      metadata: { items_count: cart.count, total: cart.total, currency: currency.value },
    });
    const res = await api.post("/checkout-intent/", buildPayload());
    const data = res?.data || {};
    if (data.checkout_url) {
      window.open(data.checkout_url, "_blank", "noopener,noreferrer");
      toast.show("Opening checkout", "success");
      return;
    }
    const detail = data.detail || "Checkout is not configured yet for this tenant.";
    checkoutError.value = detail;
    toast.show(detail, "info");
  } catch (err) {
    const detail = mapOrderApiError(err, "Unable to start checkout.");
    checkoutError.value = detail;
    toast.show(detail, "error");
  } finally {
    processingCheckout.value = false;
  }
};

const openWhatsApp = async () => {
  handoffError.value = "";
  checkoutError.value = "";
  unavailableSlugs.value = [];
  fieldErrors.value = {};
  if (!cart.canWhatsapp) return;
  if (!cart.items.length) {
    toast.show("Cart is empty.", "error");
    return;
  }
  if (!validateForm()) return;

  sendingWhatsapp.value = true;
  try {
    trackEvent("order_handoff_click", {
      source: "cart_whatsapp",
      metadata: { items_count: cart.count, total: cart.total, currency: currency.value },
    });
    const res = await api.post("/order-handoff/", buildPayload());
    const url = res?.data?.url;
    if (!url) throw new Error("Missing WhatsApp handoff URL");
    window.open(url, "_blank", "noopener,noreferrer");
    toast.show("Opening WhatsApp", "success");
  } catch (err) {
    const detail = mapOrderApiError(err, "Unable to prepare WhatsApp order.");
    handoffError.value = detail;
    toast.show(detail, "error");
  } finally {
    sendingWhatsapp.value = false;
  }
};

const handleEscapeKey = (event) => {
  if (!showMapModal.value) return;
  if (event?.key !== "Escape") return;
  closeMapModal();
};

onMounted(() => {
  trackEvent("cart_view", { source: "customer_cart" }, { onceKey: "cart:view" });
  if (typeof window !== "undefined") {
    window.addEventListener("keydown", handleEscapeKey);
  }
});

onBeforeUnmount(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener("keydown", handleEscapeKey);
  }
  if (leafletMap.value) {
    leafletMap.value.remove();
    leafletMap.value = null;
    leafletMarker.value = null;
  }
  leafletModuleRef.value = null;
});
</script>
