"""
Run 6 follow-on — public storefront branch list (REAL-DB tests).

GET /api/branches/ feeds the storefront location picker (Phase 3, D3):
the customer picks a branch (location/outlet — the vertical-general seam
shared by restaurant, pharmacy and store tenants), and the chosen slug
rides the place-order payload into resolve_order_branch.

Proven here:
  * only ACTIVE branches are listed, in display order;
  * blank branch display fields fall back to the tenant Profile
    (account-level identity), per the Branch model's documented fallback;
  * the endpoint honours the shared public-menu policy gate
    (PublishAccessMixin): an unpublished menu blocks it with 403,
    exactly like the table-context surface.

Scaffolding mirrors test_statement_immutability.py (production
provisioning path). The request carries the REAL Tenant row because the
policy mixin resolves the Profile from the public schema by tenant.
"""
import os
from unittest import skipUnless

from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import TransactionTestCase
from django_tenants.utils import schema_context
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.models import Branch
from menu.views import StorefrontBranchListView
from tenancy.models import Plan, Profile, Tenant

SCHEMA = "storefront_branches_test"


@skipUnless(os.environ.get("PYTEST_REQUIRE_DB") == "1", "requires the DB stage")
class StorefrontBranchListTests(TransactionTestCase):
    def _fixture_teardown(self):
        # See test_statement_immutability.py — the stock TRUNCATE teardown
        # cannot run while this suite's real tenant schema exists.
        pass

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._plan = Plan.objects.create(
            name="Storefront branches plan", code="storefront-branches"
        )
        tenant = Tenant(
            schema_name=SCHEMA,
            name="Storefront Branch Test Tenant",
            slug="storefront-branches-test",
            plan=cls._plan,
        )
        tenant.auto_create_schema = False
        tenant.save()
        tenant.create_schema(check_if_exists=True, verbosity=0)
        cls.tenant_row = tenant
        profile, _ = Profile.objects.get_or_create(tenant=tenant)
        profile.is_menu_published = True
        profile.address = "1 Profile Street"
        profile.phone = "0600000000"
        profile.timezone = "Africa/Casablanca"
        profile.save()
        cls.profile = profile

    @classmethod
    def tearDownClass(cls):
        try:
            with connection.cursor() as cur:
                cur.execute(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE')
            Profile.objects.filter(tenant=cls.tenant_row).delete()
            cls.tenant_row.delete()
            Plan.objects.filter(code="storefront-branches").delete()
        finally:
            super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()
        self.view = StorefrontBranchListView.as_view()
        with schema_context(SCHEMA):
            Branch.objects.all().delete()
            self.main = Branch.objects.create(
                name="Main Outlet", slug="main", is_default=True, sort_order=0
            )
            self.annex = Branch.objects.create(
                name="Annex",
                slug="annex",
                address="9 Annex Road",
                sort_order=1,
            )
            self.hidden = Branch.objects.create(
                name="Hidden", slug="hidden", is_active=False, sort_order=2
            )

    def _get(self):
        req = self.factory.get("/api/branches/")
        req.user = AnonymousUser()
        req.tenant = self.tenant_row
        with schema_context(SCHEMA):
            return self.view(req)

    # ── the proof ─────────────────────────────────────────────────────────

    def test_lists_active_branches_in_display_order(self):
        resp = self._get()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        slugs = [b["slug"] for b in resp.data["branches"]]
        self.assertEqual(slugs, ["main", "annex"])

    def test_blank_fields_fall_back_to_profile(self):
        resp = self._get()
        by_slug = {b["slug"]: b for b in resp.data["branches"]}
        self.assertEqual(by_slug["main"]["address"], "1 Profile Street")
        self.assertEqual(by_slug["main"]["phone"], "0600000000")
        self.assertEqual(by_slug["main"]["timezone"], "Africa/Casablanca")
        self.assertEqual(by_slug["main"]["is_default"], True)
        # A branch's own values win over the Profile fallback.
        self.assertEqual(by_slug["annex"]["address"], "9 Annex Road")
        self.assertEqual(by_slug["annex"]["is_default"], False)

    def test_unpublished_menu_blocks_the_list(self):
        self.profile.is_menu_published = False
        self.profile.save(update_fields=["is_menu_published"])
        try:
            resp = self._get()
            self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        finally:
            self.profile.is_menu_published = True
            self.profile.save(update_fields=["is_menu_published"])
