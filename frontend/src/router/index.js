import { createRouter, createWebHistory } from "vue-router";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";
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

const Home = () => import("../pages/Home.vue");
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
const OrderStatus = () => import("../pages/OrderStatus.vue");
const CustomerAccount = () => import("../pages/CustomerAccount.vue");
const DriverPage = () => import("../pages/DriverPage.vue");
const AdminCustomers = () => import("../pages/AdminCustomers.vue");
const AdminDeliveryJobs = () => import("../pages/AdminDeliveryJobs.vue");
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
      { path: "", name: "home", component: Home, meta: { interface: "landing" } },
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
      { path: "account", name: "customer-account", component: CustomerAccount, meta: { interface: "customer" } },
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
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
      {
        path: "reservations",
        name: "owner-reservations",
        component: OwnerReservations,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
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
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
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
  { path: "/signin", name: "signin", component: SignIn },
  // Public waiter onboarding — linked from staff invite emails; no auth required.
  // Starts PWA install flow then accepts the staff credentials.
  { path: "/waiter/join", name: "waiter-join", component: WaiterJoin, meta: { interface: "waiter" } },
  { path: "/forgot-password", name: "forgot-password", component: ForgotPassword },
  { path: "/reset-password", name: "reset-password", component: ResetPassword },
  { path: "/unauthorized", name: "unauthorized", component: Unauthorized },
  { path: "/admin-console", name: "admin-console", component: AdminConsole, meta: { requiresAuth: true, adminOnly: true } },
  { path: "/admin-delivery-zones", name: "admin-delivery-zones", component: AdminDeliveryZones, meta: { requiresAuth: true, adminOnly: true } },
  { path: "/admin-drivers", name: "admin-drivers", component: AdminDrivers, meta: { requiresAuth: true, adminOnly: true } },
  { path: "/admin-analytics", name: "admin-analytics", component: AdminPlatformAnalytics, meta: { requiresAuth: true, adminOnly: true } },
  { path: "/admin-wallets", name: "admin-wallets", component: AdminWallet, meta: { requiresAuth: true, adminOnly: true } },
  { path: "/admin-customers", name: "admin-customers", component: AdminCustomers, meta: { requiresAuth: true, adminOnly: true } },
  { path: "/admin-delivery-jobs", name: "admin-delivery-jobs", component: AdminDeliveryJobs, meta: { requiresAuth: true, adminOnly: true } },
  { path: "/admin-flash-sales", name: "admin-flash-sales", component: AdminFlashSales, meta: { requiresAuth: true, adminOnly: true } },
  { path: "/activate", name: "activate", component: Activate },
  // ── Catch-all 404 ───────────────────────────────────────────────────────────
  { path: "/:pathMatch(.*)*", name: "not-found", component: NotFound },
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

export default router;
