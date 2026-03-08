from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from menu.views import TableContextView


class DummyTableContextView(TableContextView):
    blocked_response = None

    def _enforce_public_menu_policy(self):
        return self.__class__.blocked_response


class TableContextViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        DummyTableContextView.blocked_response = None

    def _request(self, table_slug="table-1"):
        req = self.factory.get(f"/api/table-context/{table_slug}/")
        req.tenant = SimpleNamespace(id=1, name="Demo")
        return DummyTableContextView.as_view()(req, table_slug=table_slug)

    @patch("menu.views.TableLink.objects")
    def test_returns_context_when_active_table_exists(self, table_objects):
        table_objects.filter.return_value.first.return_value = SimpleNamespace(
            slug="table-1",
            label="Table 1",
            is_active=True,
        )
        response = self._request("table-1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "table-1")
        self.assertEqual(response.data["label"], "Table 1")
        self.assertTrue(response.data["is_active"])

    @patch("menu.views.TableLink.objects")
    def test_returns_404_when_table_unavailable(self, table_objects):
        table_objects.filter.return_value.first.return_value = None
        response = self._request("missing")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data["code"], "table_unavailable")

    @patch("menu.views.TableLink.objects")
    def test_returns_400_when_slug_is_empty(self, table_objects):
        response = self._request("")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "table_slug_required")
        table_objects.filter.assert_not_called()

    @patch("menu.views.TableLink.objects")
    def test_publish_policy_block_takes_precedence(self, table_objects):
        DummyTableContextView.blocked_response = Response(
            {"detail": "blocked", "code": "menu_temporarily_disabled"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        response = self._request("table-1")
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "menu_temporarily_disabled")
        table_objects.filter.assert_not_called()
