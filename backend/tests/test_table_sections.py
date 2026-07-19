"""
Tests for floor-section management (OwnerSectionListCreateView / DetailView)
and the StaffOrderListView hard section filter.

Unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User as _AuthUser  # module-level: real class, so _owner()/_staff()
# keep the real role enum even inside tests that patch.dict sys.modules["accounts.models"].
from menu.views import OwnerSectionListCreateView, OwnerSectionDetailView
from menu.waiter_views import _section_slugs_for, OwnerWaiterCallAcknowledgeView


def _owner():
    """A landmine-safe tenant owner (RISK AUTHZ-1: pin is_superuser / is_platform_admin
    False — user_owns_tenant_id short-circuits True on a truthy value, and a MagicMock
    returns a truthy Mock for any unset attribute). Uses the module-level real User enum so
    the role stays real even when a test patch.dict-mocks sys.modules['accounts.models']."""
    u = MagicMock()
    u.id = 9
    u.pk = 9
    u.is_authenticated = True
    u.is_active = True
    u.is_superuser = False
    u.is_staff = False
    u.is_platform_admin = False
    u.role = _AuthUser.Roles.TENANT_OWNER
    u.tenant_id = 1
    u.Roles = _AuthUser.Roles
    return u


def _staff():
    """An authenticated NON-owner (tenant staff), matching tenant."""
    u = _owner()
    u.id = 20
    u.pk = 20
    u.role = _AuthUser.Roles.TENANT_STAFF
    return u


def _req(factory, method, path, data=None, user=None):
    fn = getattr(factory, method)
    req = fn(path, data or {}, format="json") if data is not None else fn(path)
    # RISK AUTHZ-1: the section views now gate via permission_classes=[IsTenantOwner...]
    # (DRF dispatch), so the request must carry a real owner principal + tenant, not a
    # bare mock that only "passed" the old inline guard via a patch.
    req.user = user or _owner()
    req.tenant = SimpleNamespace(id=1)
    return req


class OwnerSectionListCreateTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerSectionListCreateView.as_view()

    def test_non_owner_denied(self):
        # RISK AUTHZ-1: owner check is now permission_classes (DRF dispatch); drive a REAL
        # non-owner (staff) principal — the old _is_tenant_owner=False patch is a no-op now.
        resp = self.view(_req(self.factory, "post", "/api/owner/sections/", {"name": "Terrace"}, user=_staff()))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.TableSection")
    def test_create_requires_name(self, TS, _gate):
        resp = self.view(_req(self.factory, "post", "/api/owner/sections/", {"name": "  "}))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "name_required")
        TS.objects.create.assert_not_called()

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.TableSection")
    def test_create_section(self, TS, _gate):
        section = MagicMock(id=1, color="#f59e0b", position=0, is_active=True)
        section.name = "Terrace"  # set as attribute (MagicMock(name=...) sets the mock's name)
        section.tables.all.return_value = []
        section.servers.all.return_value = []
        TS.objects.create.return_value = section
        TS.objects.count.return_value = 0
        resp = self.view(_req(self.factory, "post", "/api/owner/sections/", {"name": "Terrace", "color": "#f59e0b"}))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["name"], "Terrace")
        self.assertEqual(resp.data["tables"], [])
        self.assertEqual(resp.data["servers"], [])

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.TableSection")
    def test_list_sections_shape(self, TS, _gate):
        section = MagicMock(id=1, name="Main", color="", position=0, is_active=True)
        section.tables.all.return_value = [SimpleNamespace(id=3, label="T3", slug="t3", position=0)]
        section.servers.all.return_value = []  # no servers → no User lookup
        TS.objects.prefetch_related.return_value.order_by.return_value = [section]
        resp = self.view(_req(self.factory, "get", "/api/owner/sections/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data["sections"]), 1)
        self.assertEqual(resp.data["sections"][0]["tables"][0]["slug"], "t3")


class OwnerSectionDetailTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerSectionDetailView.as_view()

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.TableSection")
    def test_unknown_section_404(self, TS, _gate):
        TS.objects.filter.return_value.first.return_value = None
        resp = self.view(_req(self.factory, "patch", "/api/owner/sections/99/", {"name": "X"}), section_id=99)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.SectionServer")
    @patch("menu.views.TableLink")
    @patch("menu.views.TableSection")
    def test_assign_tables_and_servers(self, TS, TL, SS, _gate):
        section = MagicMock(id=1, name="Terrace", color="", position=0, is_active=True)
        section.tables.all.return_value = []
        section.servers.all.return_value = []
        TS.objects.filter.return_value.first.return_value = section
        SS.objects.filter.return_value.values_list.return_value = []
        # OPS-5-C: the whitelist filter now queries accounts.models.User to
        # confirm the requested user_id belongs to this tenant.  Mock it so
        # user 9 is returned as a valid tenant member (no real DB needed).
        mock_user_cls = MagicMock()
        mock_user_cls.objects.filter.return_value.values_list.return_value = [9]
        with patch.dict("sys.modules", {"accounts.models": MagicMock(User=mock_user_cls)}):
            resp = self.view(
                _req(self.factory, "patch", "/api/owner/sections/1/", {"table_ids": [3, 4], "server_user_ids": [9]}),
                section_id=1,
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Tables reassigned to this section; a server row created for user 9.
        TL.objects.filter.return_value.update.assert_called()  # set membership
        SS.objects.create.assert_called_with(section=section, user_id=9)

    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.views.TableSection")
    def test_delete_section(self, TS, _gate):
        section = MagicMock(id=1)
        TS.objects.filter.return_value.first.return_value = section
        resp = self.view(_req(self.factory, "delete", "/api/owner/sections/1/"), section_id=1)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        section.delete.assert_called_once()


class WaiterCallSectionRoutingTests(SimpleTestCase):
    @patch("menu.waiter_views.TableLink")
    @patch("menu.waiter_views.SectionServer")
    def test_section_slugs_for_computes_my_and_claimed(self, SS, TL):
        SS.objects.filter.return_value.values_list.return_value = [1]      # my section ids
        SS.objects.values_list.return_value = [1, 2]                       # all claimed section ids
        TL.objects.filter.return_value.values_list.side_effect = [["t1"], ["t1", "t2"]]
        my, claimed = _section_slugs_for(MagicMock(id=9))
        self.assertEqual(my, {"t1"})
        self.assertEqual(claimed, {"t1", "t2"})

    @patch("menu.waiter_views.TableLink")
    @patch("menu.waiter_views.SectionServer")
    def test_no_assignments_means_no_claims(self, SS, TL):
        SS.objects.filter.return_value.values_list.return_value = []
        SS.objects.values_list.return_value = []
        my, claimed = _section_slugs_for(MagicMock(id=9))
        self.assertEqual(my, set())
        self.assertEqual(claimed, set())  # empty → caller applies no filtering

    def test_routing_predicate(self):
        """The view's visibility rule: own table OR orphan OR non-table."""
        my_slugs, claimed_slugs = {"t1"}, {"t1", "t2"}

        def visible(slug):
            return (not slug) or slug in my_slugs or slug not in claimed_slugs

        self.assertTrue(visible("t1"))    # my section
        self.assertFalse(visible("t2"))   # another waiter's section
        self.assertTrue(visible("t3"))    # orphan (claimed by nobody)
        self.assertTrue(visible(""))      # non-table / no slug


# ═══════════════════════════════════════════════════════════════════════════════
# U2 — OwnerWaiterCallAcknowledgeView: section-scoped ack
# ═══════════════════════════════════════════════════════════════════════════════

class OwnerWaiterCallAcknowledgeSectionScopeTests(SimpleTestCase):
    """Any authenticated tenant staff may POST ack, but only for their own
    section — mirrors OwnerWaiterCallListView's hard section filter."""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerWaiterCallAcknowledgeView.as_view()
        # Waiter features are enabled for all tests in this class.
        _cap_patcher = patch(
            "tenancy.capabilities.tenant_capability_enabled", return_value=True
        )
        self._cap_mock = _cap_patcher.start()
        self.addCleanup(_cap_patcher.stop)

    def _post(self, call_id=5, user=None):
        req = self.factory.post(f"/api/owner/waiter-calls/{call_id}/acknowledge/")
        force_authenticate(req, user=user or MagicMock(id=9, is_authenticated=True))
        req.tenant = SimpleNamespace(id=1)
        return self.view(req, call_id=call_id)

    @patch("menu.waiter_views._section_slugs_for")
    @patch("menu.views._is_tenant_owner", return_value=False)
    @patch("menu.waiter_views.WaiterCall")
    def test_section_waiter_acks_own_section_call_ok(self, WC, _owner_gate, slugs_mock):
        call = MagicMock(id=5, status="pending", table_slug="t1")
        WC.objects.filter.return_value.first.return_value = call
        WC.Status.ACKNOWLEDGED = "acknowledged"
        slugs_mock.return_value = ({"t1"}, {"t1", "t2"})  # my_slugs, claimed_slugs

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        call.save.assert_called_once()
        self.assertEqual(call.status, "acknowledged")

    @patch("menu.waiter_views._section_slugs_for")
    @patch("menu.views._is_tenant_owner", return_value=False)
    @patch("menu.waiter_views.WaiterCall")
    def test_section_waiter_denied_foreign_section_call(self, WC, _owner_gate, slugs_mock):
        call = MagicMock(id=5, status="pending", table_slug="t2")
        WC.objects.filter.return_value.first.return_value = call
        WC.Status.ACKNOWLEDGED = "acknowledged"
        slugs_mock.return_value = ({"t1"}, {"t1", "t2"})  # t2 belongs to another waiter

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["code"], "section_denied")
        call.save.assert_not_called()

    @patch("menu.waiter_views._section_slugs_for")
    @patch("menu.views._is_tenant_owner", return_value=False)
    @patch("menu.waiter_views.WaiterCall")
    def test_section_waiter_acks_orphan_table_ok(self, WC, _owner_gate, slugs_mock):
        """A table with no assigned section server (not in claimed_slugs) is
        unowned and acknowledgeable by any waiter."""
        call = MagicMock(id=5, status="pending", table_slug="t3")
        WC.objects.filter.return_value.first.return_value = call
        WC.Status.ACKNOWLEDGED = "acknowledged"
        slugs_mock.return_value = ({"t1"}, {"t1", "t2"})  # t3 is unclaimed

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        call.save.assert_called_once()

    @patch("menu.waiter_views._section_slugs_for")
    @patch("menu.views._is_tenant_owner", return_value=True)
    @patch("menu.waiter_views.WaiterCall")
    def test_owner_acks_any_call(self, WC, _owner_gate, slugs_mock):
        call = MagicMock(id=5, status="pending", table_slug="t2")
        WC.objects.filter.return_value.first.return_value = call
        WC.Status.ACKNOWLEDGED = "acknowledged"

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        call.save.assert_called_once()
        # Owner path never needs to consult section slugs.
        slugs_mock.assert_not_called()

    @patch("menu.waiter_views._section_slugs_for")
    @patch("menu.views._is_tenant_owner", return_value=False)
    @patch("menu.waiter_views.WaiterCall")
    def test_undivided_floor_no_filtering(self, WC, _owner_gate, slugs_mock):
        """When no sections are claimed yet (claimed_slugs empty), every waiter
        may ack every call — pre-section behaviour preserved."""
        call = MagicMock(id=5, status="pending", table_slug="t9")
        WC.objects.filter.return_value.first.return_value = call
        WC.Status.ACKNOWLEDGED = "acknowledged"
        slugs_mock.return_value = (set(), set())

        resp = self._post()

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        call.save.assert_called_once()

    @patch("menu.waiter_views._section_slugs_for")
    @patch("menu.views._is_tenant_owner", return_value=False)
    @patch("menu.waiter_views.WaiterCall")
    def test_unauthenticated_ack_is_403(self, WC, _owner_gate, slugs_mock):
        """No IsTenantEditorOrReadOnly gate — but IsAuthenticated must still block
        an anonymous request (regression guard for the permission relaxation)."""
        call = MagicMock(id=5, status="pending", table_slug="t1")
        WC.objects.filter.return_value.first.return_value = call
        req = self.factory.post("/api/owner/waiter-calls/5/acknowledge/")
        req.tenant = SimpleNamespace(id=1)
        # no force_authenticate — anonymous
        resp = self.view(req, call_id=5)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        call.save.assert_not_called()
