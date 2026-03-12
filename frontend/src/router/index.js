import { createRouter, createWebHistory } from "vue-router";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";
import { translate } from "../i18n/translate";
import { currentHostname, getPlatformAdminHost, isPlatformAdminHost, isPublicDemoHost } from "../lib/runtimeHost";

const LandingLayout = () => import("../layouts/LandingLayout.vue");
const CustomerLayout = () => import("../layouts/CustomerLayout.vue");
const OwnerLayout = () => import("../layouts/OwnerLayout.vue");

const Home = () => import("../pages/Home.vue");
const CustomerLeadPage = () => import("../pages/CustomerLeadPage.vue");
const Menu = () => import("../pages/Menu.vue");
const CategoryPage = () => import("../pages/CategoryPage.vue");
const DishPage = () => import("../pages/DishPage.vue");
const Cart = () => import("../pages/Cart.vue");
const ReservationPage = () => import("../pages/ReservationPage.vue");
const LeadCapture = () => import("../pages/LeadCapture.vue");

const OwnerHome = () => import("../pages/OwnerHome.vue");
const OwnerTables = () => import("../pages/OwnerTables.vue");
const OwnerLaunchSuccess = () => import("../pages/OwnerLaunchSuccess.vue");
const OwnerReservations = () => import("../pages/OwnerReservations.vue");

const AdminConsole = () => import("../pages/AdminConsole.vue");
const Activate = () => import("../pages/Activate.vue");
const ForgotPassword = () => import("../pages/ForgotPassword.vue");
const ResetPassword = () => import("../pages/ResetPassword.vue");
const SignIn = () => import("../pages/SignIn.vue");
const Unauthorized = () => import("../pages/Unauthorized.vue");

const PrivacyPolicy = () => import("../pages/PrivacyPolicy.vue");
const TermsOfService = () => import("../pages/TermsOfService.vue");
const ContactPage = () => import("../pages/ContactPage.vue");
const Wizard = () => import("../onboarding/Wizard.vue");

const routes = [
  {
    path: "/",
    component: LandingLayout,
    children: [
      { path: "", name: "home", component: Home, meta: { interface: "landing" } },
      { path: "get-started", name: "lead", component: LeadCapture, meta: { interface: "landing" } },
      { path: "privacy", name: "privacy", component: PrivacyPolicy, meta: { interface: "landing" } },
      { path: "terms", name: "terms", component: TermsOfService, meta: { interface: "landing" } },
      { path: "contact", name: "contact", component: ContactPage, meta: { interface: "landing" } },
    ],
  },
  {
    path: "/",
    component: CustomerLayout,
    children: [
      { path: "t/:tableSlug", name: "table-link", component: Menu, meta: { interface: "customer" } },
      { path: "menu", name: "customer-home", component: CustomerLeadPage, meta: { interface: "customer" } },
      { path: "browse", name: "menu", component: Menu, meta: { interface: "customer" } },
      { path: "browse/:slug", name: "category", component: CategoryPage, props: true, meta: { interface: "customer" } },
      { path: "browse/:category/:dish", name: "dish", component: DishPage, props: true, meta: { interface: "customer" } },
      { path: "reserve", name: "reserve", component: ReservationPage, meta: { interface: "customer" } },
      { path: "cart", name: "cart", component: Cart, meta: { interface: "customer" } },
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
        path: "onboarding",
        name: "onboarding",
        component: Wizard,
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
        path: "launch",
        name: "owner-launch",
        component: OwnerLaunchSuccess,
        meta: { requiresAuth: true, tenantEditorOnly: true, interface: "owner" },
      },
    ],
  },
  { path: "/onboarding", redirect: { name: "onboarding" } },
  { path: "/signin", name: "signin", component: SignIn },
  { path: "/forgot-password", name: "forgot-password", component: ForgotPassword },
  { path: "/reset-password", name: "reset-password", component: ResetPassword },
  { path: "/unauthorized", name: "unauthorized", component: Unauthorized },
  { path: "/admin-console", name: "admin-console", component: AdminConsole, meta: { requiresAuth: true, adminOnly: true } },
  { path: "/activate", name: "activate", component: Activate },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

router.beforeEach(async (to) => {
  const toast = useToastStore();
  const needsCustomerInterface = to.matched.some((route) => route.meta?.interface === "customer");
  if (needsCustomerInterface && isPublicDemoHost()) {
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

  const needsTenantEditor = to.matched.some((route) => route.meta?.tenantEditorOnly);
  if (needsTenantEditor && !session.canEditTenantMenu) {
    toast.show(translate("router.editorRequired"), "error");
    return { name: "unauthorized", query: { reason: "editor", next: to.fullPath } };
  }

  return true;
});

export default router;
