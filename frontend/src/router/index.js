import { createRouter, createWebHistory } from "vue-router";
import { createMainContentFocusGuard } from "./focusGuard";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";
import { useCustomerStore } from "../stores/customer";
import { useToastStore } from "../stores/toast";
import { translate } from "../i18n/translate";
import {
  currentHostname,
  getPlatformAdminHost,
  hasPublicDemoTenant,
  isPlatformPublicHost,
  isPlatformAdminHost,
  isPublicDemoHost,
} from "../lib/runtimeHost";

const LandingLayout = () => import("../layouts/LandingLayout.vue");
const CustomerLayout = () => import("../layouts/CustomerLayout.vue");
const OwnerLayout = () => import("../layouts/OwnerLayout.vue");
const WaiterLayout = () => import("../layouts/WaiterLayout.vue");
// Chrome-less layout for standalone routes (auth, 404): supplies the
// single focusable <main id="main-content"> + skip-link those pages otherwise
// lack, so the SPA focus guard (focusGuard.js, WCAG 2.4.3) has a landmark to
// land on and keyboard users can skip to content.
const PlainLayout = () => import("../layouts/PlainLayout.vue");
// Admin chrome layout — persistent top nav bar for the 9 platform-admin routes,
// with the same skip-link + focusable <main id="main-content"> a11y pattern.
const AdminLayout = () => import("../layouts/AdminLayout.vue");

const Home = () => import("../pages/Home.vue");
const SuperAppHub = () => import("../pages/SuperAppHub.vue");
const DemoLanding = () => import("../pages/DemoLanding.vue");
const CustomerLeadPage = () => import("../pages/CustomerLeadPage.vue");
const MenuSelect = () => import("../pages/MenuSelect.vue");
const Menu = () => import("../pages/Menu.vue");
const CategoryPage = () => import("../pages/CategoryPage.vue");
const DishPage = () => import("../pages/DishPage.vue");
const Cart = () => import("../pages/Cart.vue");
const ReservationPage = () => import("../pages/ReservationPage.vue");
const ReservationManage = () => import("../pages/ReservationManage.vue");
const LeadCapture = () => import("../pages/LeadCapture.vue");

const WaiterPage = () => import("../pages/WaiterPage.vue");
const FindMyOrder = () => import("../pages/FindMyOrder.vue");

const OwnerHome = () => import("../pages/OwnerHome.vue");
const OwnerAnalytics = () => import("../pages/OwnerAnalytics.vue");
const OwnerLaunchSuccess = () => import("../pages/OwnerLaunchSuccess.vue");
const OwnerMenuBuilder = () => import("../pages/OwnerMenuBuilder.vue");
const OwnerOrders = () => import("../pages/OwnerOrders.vue");
const OwnerNotifications = () => import("../pages/OwnerNotifications.vue");
const OwnerProfile = () => import("../pages/OwnerProfile.vue");
const OwnerReservations = () => import("../pages/OwnerReservations.vue");
const OwnerTables = () => import("../pages/OwnerTables.vue");
const OwnerStaffPage = () => import("../pages/OwnerStaffPage.vue");
const OwnerRatings = () => import("../pages/OwnerRatings.vue");
const OwnerKitchen = () => import("../pages/OwnerKitchen.vue");
const OwnerPromotions = () => import("../pages/OwnerPromotions.vue");
const OwnerLoyalty = () => import("../pages/OwnerLoyalty.vue");
const OwnerWallet = () => import("../pages/OwnerWallet.vue");
const OwnerCustomers = () => import("../pages/OwnerCustomers.vue");
const OwnerZReport = () => import("../pages/OwnerZReport.vue");
const OwnerShiftClose = () => import("../pages/OwnerShiftClose.vue");
const OrderStatus = () => import("../pages/OrderStatus.vue");
const CustomerAccount = () => import("../pages/CustomerAccount.vue");
const RidePage = () => import("../pages/RidePage.vue");
const SendPackagePage = () => import("../pages/SendPackagePage.vue");
const RecipientTrackPage = () => import("../pages/RecipientTrackPage.vue");
const DriverPage = () => import("../pages/DriverPage.vue");
const AdminCustomers = () => import("../pages/AdminCustomers.vue");
const AdminDeliveryJobs = () => import("../pages/AdminDeliveryJobs.vue");
const AdminRides = () => import("../pages/AdminRides.vue");
const AdminFlashSales = () => import("../pages/AdminFlashSales.vue");

const AdminConsole = () => import("../pages/AdminConsole.vue");
const AdminDeliveryZones = () => import("../pages/AdminDeliveryZones.vue");
const AdminDrivers = () => import("../pages/AdminDrivers.vue");
const AdminPlatformAnalytics = () => import("../pages/AdminPlatformAnalytics.vue");
const AdminWallet = () => import("../pages/AdminWallet.vue");
const Activate = () => import("../pages/Activate.vue");
const ForgotPassword = () => import("../pages/ForgotPassword.vue");
const ResetPassword = () => import("../pages/ResetPassword.vue");
const SignIn = () => import("../pages/SignIn.vue");
const WaiterJoin = () => import("../pages/WaiterJoin.vue");
const Unauthorized = () => import("../pages/Unauthorized.vue");

const PrivacyPolicy = () => import("../pages/PrivacyPolicy.vue");
const TermsOfService = () => import("../pages/TermsOfService.vue");
const ContactPage = () => import("../pages/ContactPage.vue");
const Directory = () => import("../pages/Directory.vue");
const Marketplace = () => import("../pages/Marketplace.vue");
const MarketplaceMenuPage = () => import("../pages/MarketplaceMenuPage.vue");
const MarketplaceOrderStatus = () => import("../pages/MarketplaceOrderStatus.vue");
const Wizard = () => import("../onboarding/Wizard.vue");
const NotFound = () => import("../pages/NotFound.vue");

const routes = [
  {
    path: "/",
    component: LandingLayout,
    children: [
      // Platform-public-host root → super-app consumer hub.
      // Tenant-host root → B2B owner-marketing page (Home).
      // The beforeEach guard below performs the host-based dispatch.
      { path: "", name: "home", component: Home, meta: { interface: "landing" } },
      // Consumer hub — rendered at "/" on the platform public host only.
      { path: "hub", name: "super-app-hub", component: SuperAppHub, meta: { interface: "landing" } },
      // B2B owner-acquisition funnel — moved to /business but fully functional.
      { path: "business", name: "business", component: Home, meta: { interface: "landing" } },
      { path: "demo", name: "demo", component: DemoLanding, meta: { interface: "landing" } },
      { path: "get-started", name: "lead", component: LeadCapture, meta: { interface: "landing" } },
      { path: "privacy", name: "privacy", component: PrivacyPolicy, meta: { interface: "landing" } },
      { path: "terms", name: "terms", component: TermsOfService, meta: { interface: "landing" } },
      { path: "contact", name: "contact", component: ContactPage, meta: { interface: "landing" } },
      { path: "directory", name: "directory", component: Directory, meta: { interface: "landing" } },
      { path: "driver", name: "driver", component: DriverPage, meta: { interface: "landing" } },
      { path: "order", name: "marketplace", component: Marketplace, meta: { interface: "landing" } },
      { path: "order/:slug", name: "marketplace-menu", component: MarketplaceMenuPage, props: true, meta: { interface: "landing" } },
      { path: "order/:slug/status/:orderNumber", name: "marketplace-order-status", component: MarketplaceOrderStatus, props: true, meta: { interface: "landing" } },
      // Consumer-facing pages that include CustomerAuthModal inline and must be
      // reachable on the platform public host (kepoli.app) — kept under
      // LandingLayout so the needsCustomerInterface guard never blocks them.
      { path: "account", name: "customer-account", component: CustomerAccount, meta: { interface: "landing" } },
      { path: "ride", name: "ride", component: RidePage, meta: { interface: "landing", vertical: "rides" } },
      { path: "send-package", name: "send-package", component: SendPackagePage, meta: { interface: "landing", vertical: "courier" } },
      // Public, no-auth recipient package tracking (tokenized link sent by SMS).
      { path: "track/:token", name: "recipient-track", component: RecipientTrackPage, props: true, meta: { interface: "landing", vertical: "courier" } },
    ],
  },
  {
    path: "/",
    component: CustomerLayout,
    children: [
      { path: "t/:tableSlug", name: "table-link", component: Menu, meta: { interface: "customer" } },
      { path: "menu", name: "customer-home", component: CustomerLeadPage, meta: { interface: "customer" } },
      // Menu hub — shows menu selection cards; auto-redirects when only one menu exists
      { path: "browse", name: "menu", component: MenuSelect, meta: { interface: "customer" } },
      // Per-menu browsing view: /m/<super-category-slug>
      // Separate namespace from /browse/:slug (category) to avoid route conflicts
      { path: "m/:menuSlug", name: "menu-browse", component: Menu, props: true, meta: { interface: "customer" } },
      // Category / dish routes stay shallow under /browse/ — unchanged
      { path: "browse/:slug", name: "category", component: CategoryPage, props: true, meta: { interface: "customer" } },
      { path: "browse/:category/:dish", name: "dish", component: DishPage, props: true, meta: { interface: "customer" } },
      { path: "reserve", name: "reserve", component: ReservationPage, meta: { interface: "customer" } },
      { path: "r/:token", name: "reservation-manage", component: ReservationManage, props: true, meta: { interface: "customer" } },
      { path: "cart", name: "cart", component: Cart, meta: { interface: "customer" } },
      // "orders/" (plural) avoids colliding with the LandingLayout "order/:slug"
      // marketplace route which is defined earlier in the routes array and would
      // otherwise win on a hard refresh of /order/ORD-XXXXXX.
      { path: "orders/:orderNumber", name: "order-status", component: OrderStatus, props: true, meta: { interface: "customer" } },
      { path: "find-my-order", name: "find-my-order", component: FindMyOrder, meta: { interface: "customer" } },
      {
        path: "menu/:slug",
        redirect: (to) => ({ name: "category", params: { slug: to.params.slug } }),
      },
      {
        path: "menu/:category/:dish",
        redirect: (to) => ({ name: "dish", params: { category: to.params.category, dish: to.params.dish } }),
      },
    ],
  },
  {
    path: "/owner",
    component: OwnerLayout,
    meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
    children: [
      {
        path: "",
        name: "owner-home",
        component: OwnerHome,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "analytics",
        name: "owner-analytics",
        component: OwnerAnalytics,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "menu-builder",
        name: "owner-menu-builder",
        component: OwnerMenuBuilder,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "onboarding",
        name: "onboarding",
        component: Wizard,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "profile",
        name: "owner-profile",
        component: OwnerProfile,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "tables",
        name: "owner-tables",
        component: OwnerTables,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner", requiresCapability: "tables" },
      },
      {
        path: "reservations",
        name: "owner-reservations",
        component: OwnerReservations,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner", requiresCapability: "reservations" },
      },
      {
        path: "orders",
        name: "owner-orders",
        component: OwnerOrders,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "notifications",
        name: "owner-notifications",
        component: OwnerNotifications,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "launch",
        name: "owner-launch",
        component: OwnerLaunchSuccess,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "staff",
        name: "owner-staff",
        component: OwnerStaffPage,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "ratings",
        name: "owner-ratings",
        component: OwnerRatings,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "kitchen",
        name: "owner-kitchen",
        component: OwnerKitchen,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner", requiresCapability: "kitchen" },
      },
      {
        path: "promotions",
        name: "owner-promotions",
        component: OwnerPromotions,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "loyalty",
        name: "owner-loyalty",
        component: OwnerLoyalty,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "wallet",
        name: "owner-wallet",
        component: OwnerWallet,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "customers",
        name: "owner-customers",
        component: OwnerCustomers,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "z-report",
        name: "owner-z-report",
        component: OwnerZReport,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "shift-close",
        name: "owner-shift-close",
        component: OwnerShiftClose,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
    ],
  },
  {
    path: "/waiter",
    component: WaiterLayout,
    meta: { requiresAuth: true, tenantEditorOnly: true, interface: "waiter" },
    children: [
      {
        path: "",
        name: "waiter",
        component: WaiterPage,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "waiter" },
      },
    ],
  },
  // Backward-compat: old order-status links used /order/ORD-XXXX.
  // Redirect to the new /orders/ path so hard refreshes resolve correctly.
  // The regex ensures this only fires for tenant order numbers (ORD-XXXXXX),
  // not for marketplace restaurant slugs like /order/my-restaurant.
  { path: "/order/:n([A-Z]+-[A-Z0-9]+)", redirect: (to) => ({ name: "order-status", params: { orderNumber: to.params.n } }) },
  { path: "/onboarding", redirect: { name: "onboarding" } },
  // ── Admin routes — persistent nav chrome ──────────────────────────────────────
  // AdminLayout provides the skip-link + focusable <main id="main-content"> a11y
  // pattern AND a top nav bar with links to all 9 admin pages + sign-out. The 9
  // admin routes are children here; auth/admin guards on each child are unchanged.
  {
    path: "/",
    component: AdminLayout,
    children: [
      { path: "admin-console", name: "admin-console", component: AdminConsole, meta: { requiresAuth: true, adminOnly: true } },
      { path: "admin-delivery-zones", name: "admin-delivery-zones", component: AdminDeliveryZones, meta: { requiresAuth: true, adminOnly: true } },
      { path: "admin-drivers", name: "admin-drivers", component: AdminDrivers, meta: { requiresAuth: true, adminOnly: true } },
      { path: "admin-analytics", name: "admin-analytics", component: AdminPlatformAnalytics, meta: { requiresAuth: true, adminOnly: true } },
      { path: "admin-wallets", name: "admin-wallets", component: AdminWallet, meta: { requiresAuth: true, adminOnly: true } },
      { path: "admin-customers", name: "admin-customers", component: AdminCustomers, meta: { requiresAuth: true, adminOnly: true } },
      { path: "admin-delivery-jobs", name: "admin-delivery-jobs", component: AdminDeliveryJobs, meta: { requiresAuth: true, adminOnly: true } },
      { path: "admin-rides", name: "admin-rides", component: AdminRides, meta: { requiresAuth: true, adminOnly: true } },
      { path: "admin-flash-sales", name: "admin-flash-sales", component: AdminFlashSales, meta: { requiresAuth: true, adminOnly: true } },
    ],
  },
  // ── Standalone (chrome-less) routes ─────────────────────────────────────────
  // These render no header/nav, but are wrapped in PlainLayout so each exposes a
  // single focusable <main id="main-content"> landmark + a skip-link, matching
  // the full layouts. This keeps the SPA route-change focus guard (focusGuard.js,
  // WCAG 2.4.3) working uniformly and lets keyboard users skip to content.
  // PlainLayout only adds the landmark + skip-link; auth guards (driven by
  // child-route meta) are unchanged.
  {
    path: "/",
    component: PlainLayout,
    children: [
      { path: "signin", name: "signin", component: SignIn },
      // Public waiter onboarding — linked from staff invite emails; no auth required.
      // Starts PWA install flow then accepts the staff credentials.
      { path: "waiter/join", name: "waiter-join", component: WaiterJoin, meta: { interface: "waiter" } },
      { path: "forgot-password", name: "forgot-password", component: ForgotPassword },
      { path: "reset-password", name: "reset-password", component: ResetPassword },
      { path: "unauthorized", name: "unauthorized", component: Unauthorized },
      { path: "activate", name: "activate", component: Activate },
      // ── Catch-all 404 ─────────────────────────────────────────────────────────
      { path: ":pathMatch(.*)*", name: "not-found", component: NotFound },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    if (savedPosition) {
      return savedPosition;
    }
    return { top: 0 };
  },
});

router.beforeEach(async (to) => {
  const toast = useToastStore();

  // ── Platform-public-host root dispatch ───────────────────────────────────
  // On the platform consumer domain (e.g. kepoli.app) the root "/" renders the
  // super-app hub. On tenant subdomains it keeps the current B2B home page.
  // Only redirect when actually landing on "home" to avoid infinite loops.
  if (to.name === "home" && isPlatformPublicHost()) {
    return { name: "super-app-hub", replace: true };
  }

  const needsCustomerInterface = to.matched.some((route) => route.meta?.interface === "customer");
  if (needsCustomerInterface && isPlatformPublicHost()) {
    return { name: "demo" };
  }
  if (needsCustomerInterface && isPublicDemoHost() && !hasPublicDemoTenant()) {
    return { name: "home" };
  }

  const needsAdmin = to.matched.some((route) => route.meta?.adminOnly);
  if (needsAdmin) {
    const adminHost = getPlatformAdminHost();
    const currentHost = currentHostname();
    if (typeof window !== "undefined" && adminHost && currentHost && currentHost !== adminHost && !isPlatformAdminHost(currentHost)) {
      window.location.assign(`${window.location.protocol}//${adminHost}${to.fullPath}`);
      return false;
    }
  }
  const requiresOrderFeatures = to.matched.some((route) => route.meta?.requiresOrderFeatures);
  if (requiresOrderFeatures) {
    const tenant = useTenantStore();
    if (!tenant.meta && !tenant.loading) {
      await tenant.fetchMeta();
    }
    if (tenant.isBrowseOnlyPlan) {
      toast.show(translate("router.orderingDisabled"), "info");
      return { name: "menu" };
    }
  }

  // Capability-gated owner routes (tables / reservations / kitchen): a shop tenant
  // (grocery/retail/pharmacy) must not reach a restaurant-only page by DIRECT URL,
  // even though the nav already hides the link. Fail-open: only redirect when meta
  // is loaded and the capability is positively false. Silent → the owner dashboard.
  const requiresCapability = to.matched.map((r) => r.meta?.requiresCapability).find(Boolean);
  if (requiresCapability) {
    const tenant = useTenantStore();
    if (!tenant.meta && !tenant.loading) {
      await tenant.fetchMeta();
    }
    if (tenant.capabilities?.[requiresCapability] === false) {
      return { name: "owner-home", replace: true };
    }
  }

  // P4: gate dedicated-vertical consumer routes (rides/courier) on the platform's
  // enabled set. Fail-open: only redirect when we POSITIVELY know it's disabled
  // (platform loaded + vertical absent), so a failed session fetch never blocks.
  // Silent redirect to the hub, where the service already shows as coming-soon.
  const gatedVertical = to.matched.map((r) => r.meta?.vertical).find(Boolean);
  if (gatedVertical) {
    const customer = useCustomerStore();
    if (!customer.loaded && !customer.loading) {
      try { await customer.fetchCustomer(); } catch { /* fail-open */ }
    }
    const enabled = customer.platform?.enabled_verticals;
    if (Array.isArray(enabled) && !enabled.includes(gatedVertical)) {
      return { name: "super-app-hub", replace: true };
    }
  }

  const requiresAuth = to.matched.some((route) => route.meta?.requiresAuth);
  if (!requiresAuth) return true;

  const session = useSessionStore();
  try {
    await session.fetchSession();
  } catch {
    toast.show(translate("router.verifySessionFailed"), "error");
    return { name: "signin", query: { next: to.fullPath } };
  }

  if (!session.isAuthenticated) {
    if (needsAdmin) {
      toast.show(translate("router.signInAdminFirst"), "error");
    } else {
      toast.show(translate("router.signInBeforeAccess"), "error");
    }
    return { name: "signin", query: { next: to.fullPath } };
  }

  if (needsAdmin && !session.isPlatformAdmin) {
    toast.show(translate("router.adminRequired"), "error");
    return { name: "unauthorized", query: { reason: "admin", next: to.fullPath } };
  }

  // Owner app vs waiter app. Staff (waiters) are confined to the waiter app; the owner
  // app is owner-only (admins/superusers may enter for support). Driven by the route's
  // `interface` meta so we don't have to flag every child route individually.
  const ownerRoute = to.matched.some((route) => route.meta?.interface === "owner");
  const waiterRoute = to.matched.some((route) => route.meta?.interface === "waiter");
  const isAdminLevel =
    session.isPlatformAdmin || session.user?.is_superuser === true || session.user?.is_staff === true;

  if (ownerRoute && !session.isTenantOwner && !isAdminLevel) {
    if (session.isTenantStaff) {
      // Send staff to their own app rather than a dead-end error.
      return { name: "waiter" };
    }
    toast.show(translate("router.ownerRequired"), "error");
    return { name: "unauthorized", query: { reason: "owner", next: to.fullPath } };
  }

  if (waiterRoute && !session.isTenantOwner && !session.isTenantStaff && !isAdminLevel) {
    toast.show(translate("router.staffRequired"), "error");
    return { name: "unauthorized", query: { reason: "staff", next: to.fullPath } };
  }

  return true;
});

// SPA route-change focus management (WCAG 2.4.3) — see ./focusGuard.js.
router.afterEach(createMainContentFocusGuard());

export default router;
