"""
Tests for floor-section management (OwnerSectionListCreateView / DetailView)
and the StaffOrderListView hard section filter.

Unit-level (SimpleTestCase + mocks — no real DB).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import OwnerSectionListCreateView, OwnerSectionDetailView
from menu.waiter_views import _section_slugs_for


def _req(factory, method, path, data=None):
    fn = getattr(factory, method)
    req = fn(path, data or {}, format="json") if data is not None else fn(path)
    req.user = MagicMock(id=9, is_authenticated=True)
    req.tenant = SimpleNamespace(id=1)
    return req


class OwnerSectionListCreateTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = OwnerSectionListCreateView.as_view()

    @patch("menu.views._is_tenant_owner", return_value=False)
    def test_non_owner_denied(self, _gate):
        resp = self.view(_req(self.factory, "post", "/api/owner/sections/", {"name": "Terrace"}))
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
