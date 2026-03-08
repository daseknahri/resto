import { createRouter, createWebHistory } from "vue-router";
import LandingLayout from "../layouts/LandingLayout.vue";
import CustomerLayout from "../layouts/CustomerLayout.vue";
import OwnerLayout from "../layouts/OwnerLayout.vue";
import Home from "../pages/Home.vue";
import CustomerLeadPage from "../pages/CustomerLeadPage.vue";
import Menu from "../pages/Menu.vue";
import CategoryPage from "../pages/CategoryPage.vue";
import DishPage from "../pages/DishPage.vue";
import Cart from "../pages/Cart.vue";
import ReservationPage from "../pages/ReservationPage.vue";
import LeadCapture from "../pages/LeadCapture.vue";
import OwnerHome from "../pages/OwnerHome.vue";
import OwnerTables from "../pages/OwnerTables.vue";
import OwnerLaunchSuccess from "../pages/OwnerLaunchSuccess.vue";
import OwnerReservations from "../pages/OwnerReservations.vue";
import AdminConsole from "../pages/AdminConsole.vue";
import Activate from "../pages/Activate.vue";
import ForgotPassword from "../pages/ForgotPassword.vue";
import ResetPassword from "../pages/ResetPassword.vue";
import SignIn from "../pages/SignIn.vue";
import Unauthorized from "../pages/Unauthorized.vue";
import PrivacyPolicy from "../pages/PrivacyPolicy.vue";
import TermsOfService from "../pages/TermsOfService.vue";
import ContactPage from "../pages/ContactPage.vue";
import Wizard from "../onboarding/Wizard.vue";
import { useSessionStore } from "../stores/session";
import { useTenantStore } from "../stores/tenant";
import { useToastStore } from "../stores/toast";

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
  const requiresOrderFeatures = to.matched.some((route) => route.meta?.requiresOrderFeatures);
  if (requiresOrderFeatures) {
    const tenant = useTenantStore();
    if (!tenant.meta && !tenant.loading) {
      await tenant.fetchMeta();
    }
    if (tenant.isBrowseOnlyPlan) {
      toast.show("Ordering features are not enabled for this tenant plan.", "info");
      return { name: "menu" };
    }
  }

  const requiresAuth = to.matched.some((route) => route.meta?.requiresAuth);
  if (!requiresAuth) return true;

  const session = useSessionStore();
  const needsAdmin = to.matched.some((route) => route.meta?.adminOnly);
  try {
    await session.fetchSession();
  } catch (err) {
    toast.show("Unable to verify session. Please sign in.", "error");
    return { name: "signin", query: { next: to.fullPath } };
  }

  if (!session.isAuthenticated) {
    if (needsAdmin) {
      toast.show("Please sign in as platform admin first.", "error");
    } else {
      toast.show("Please sign in before accessing this page.", "error");
    }
    return { name: "signin", query: { next: to.fullPath } };
  }

  if (needsAdmin && !session.isPlatformAdmin) {
    toast.show("Admin access required.", "error");
    return { name: "unauthorized", query: { reason: "admin", next: to.fullPath } };
  }

  const needsTenantEditor = to.matched.some((route) => route.meta?.tenantEditorOnly);
  if (needsTenantEditor && !session.canEditTenantMenu) {
    toast.show("Menu editor access required.", "error");
    return { name: "unauthorized", query: { reason: "editor", next: to.fullPath } };
  }

  return true;
});

export default router;
