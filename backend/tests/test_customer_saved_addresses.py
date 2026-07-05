"""
Tests for customer saved-address views:
  - CustomerSavedAddressListCreateView  GET/POST /api/customer/addresses/
  - CustomerSavedAddressDeleteView      DELETE   /api/customer/addresses/<id>/

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from accounts.views import CustomerSavedAddressDeleteView, CustomerSavedAddressListCreateView


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session(customer_id=None):
    data = {} if customer_id is None else {"customer_id": customer_id}
    sess = MagicMock()
    sess.get = lambda key, default=None: data.get(key, default)
    return sess


def _make_customer(customer_id=1):
    c = MagicMock()
    c.pk = customer_id
    c.id = customer_id
    return c


def _make_address(addr_id=1, label="Home", address="123 Main St",
                  location_url="", lat=None, lng=None):
    a = MagicMock()
    a.pk = addr_id
    a.label = label
    a.address = address
    a.location_url = location_url
    a.lat = lat
    a.lng = lng
    a.created_at = MagicMock()
    a.created_at.isoformat.return_value = "2026-01-01T00:00:00+00:00"
    return a


# ── CustomerSavedAddressListCreateView ────────────────────────────────────────

class CustomerSavedAddressListCreateViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerSavedAddressListCreateView.as_view()

    def _get(self, session=None):
        req = self.factory.get("/api/customer/addresses/")
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        return self.view(req)

    def _post(self, data, session=None):
        req = self.factory.post("/api/customer/addresses/", data, format="json")
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        return self.view(req)

    # ── Auth ──────────────────────────────────────────────────────────────────

    def test_get_no_session_returns_401(self):
        resp = self._get(session=_session(customer_id=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_no_session_returns_401(self):
        resp = self._post({"address": "123 Main St"}, session=_session(customer_id=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── GET list ──────────────────────────────────────────────────────────────

    @patch("accounts.models.Customer.objects")
    def test_get_returns_address_list(self, mock_cust_objs):
        customer = _make_customer()
        mock_cust_objs.get.return_value = customer
        a1 = _make_address(1, "Home", "123 Main St")
        a2 = _make_address(2, "Work", "456 Office Ave")

        with patch("accounts.models.SavedAddress") as mock_sa:
            mock_sa.objects.filter.return_value.__getitem__.return_value = [a1, a2]
            resp = self._get(session=_session(customer_id=1))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIsInstance(resp.data, list)

    @patch("accounts.models.Customer.objects")
    def test_get_empty_list(self, mock_cust_objs):
        customer = _make_customer()
        mock_cust_objs.get.return_value = customer

        with patch("accounts.models.SavedAddress") as mock_sa:
            mock_sa.objects.filter.return_value.__getitem__.return_value = []
            resp = self._get(session=_session(customer_id=1))

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data, [])

    # ── POST validation ───────────────────────────────────────────────────────

    @patch("accounts.models.Customer.objects")
    def test_post_missing_address_returns_400(self, mock_cust_objs):
        customer = _make_customer()
        mock_cust_objs.get.return_value = customer

        with patch("accounts.models.SavedAddress") as mock_sa:
            mock_sa.objects.filter.return_value.count.return_value = 0
            resp = self._post({"label": "Home"}, session=_session(customer_id=1))

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_address")

    @patch("accounts.models.Customer.objects")
    def test_post_address_limit_returns_400(self, mock_cust_objs):
        """Cannot add an 11th address."""
        customer = _make_customer()
        mock_cust_objs.get.return_value = customer

        with patch("accounts.models.SavedAddress") as mock_sa:
            mock_sa.objects.filter.return_value.count.return_value = 10  # at limit
            resp = self._post({"address": "New Address"}, session=_session(customer_id=1))

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "address_limit")

    # ── POST happy path ───────────────────────────────────────────────────────

    @patch("accounts.models.Customer.objects")
    def test_post_creates_address_and_returns_201(self, mock_cust_objs):
        customer = _make_customer()
        mock_cust_objs.get.return_value = customer
        new_addr = _make_address(10, "Home", "123 Main St")

        with patch("accounts.models.SavedAddress") as mock_sa:
            mock_sa.objects.filter.return_value.count.return_value = 2
            mock_sa.objects.create.return_value = new_addr
            resp = self._post(
                {"label": "Home", "address": "123 Main St"},
                session=_session(customer_id=1),
            )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        for field in ("id", "label", "address", "location_url", "lat", "lng", "created_at"):
            self.assertIn(field, resp.data, f"Missing field: {field}")
        self.assertEqual(resp.data["address"], "123 Main St")

    @patch("accounts.models.Customer.objects")
    def test_post_with_lat_lng(self, mock_cust_objs):
        customer = _make_customer()
        mock_cust_objs.get.return_value = customer
        new_addr = _make_address(11, lat=33.5, lng=-7.6)

        with patch("accounts.models.SavedAddress") as mock_sa:
            mock_sa.objects.filter.return_value.count.return_value = 0
            mock_sa.objects.create.return_value = new_addr
            resp = self._post(
                {"address": "GPS Location", "lat": 33.5, "lng": -7.6},
                session=_session(customer_id=1),
            )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        _, kwargs = mock_sa.objects.create.call_args
        self.assertAlmostEqual(kwargs.get("lat"), 33.5)
        self.assertAlmostEqual(kwargs.get("lng"), -7.6)


# ── CustomerSavedAddressDeleteView ────────────────────────────────────────────

class CustomerSavedAddressDeleteViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerSavedAddressDeleteView.as_view()

    def _delete(self, address_id, session=None):
        req = self.factory.delete(f"/api/customer/addresses/{address_id}/")
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        return self.view(req, address_id=address_id)

    def test_no_session_returns_401(self):
        resp = self._delete(1, session=_session(customer_id=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_not_found_returns_404(self, mock_cust_objs):
        customer = _make_customer()
        mock_cust_objs.get.return_value = customer
        from accounts.models import SavedAddress
        with patch("accounts.models.SavedAddress.objects") as mock_sa_objs:
            mock_sa_objs.get.side_effect = SavedAddress.DoesNotExist
            resp = self._delete(999, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    @patch("accounts.models.Customer.objects")
    def test_delete_returns_204(self, mock_cust_objs):
        customer = _make_customer()
        mock_cust_objs.get.return_value = customer
        addr = _make_address(5)
        with patch("accounts.models.SavedAddress.objects") as mock_sa_objs:
            mock_sa_objs.get.return_value = addr
            resp = self._delete(5, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        addr.delete.assert_called_once()


# ── CustomerSavedAddressDeleteView.patch (B4: edit-address) ───────────────────

class CustomerSavedAddressPatchViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = CustomerSavedAddressDeleteView.as_view()

    def _patch(self, address_id, data, session=None):
        req = self.factory.patch(f"/api/customer/addresses/{address_id}/", data, format="json")
        req.user = MagicMock(is_authenticated=False)
        req.session = session or _session()
        return self.view(req, address_id=address_id)

    def test_no_session_returns_401(self):
        resp = self._patch(1, {"address": "New addr"}, session=_session(customer_id=None))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("accounts.models.Customer.objects")
    def test_updates_own_address(self, mock_cust_objs):
        customer = _make_customer(customer_id=1)
        mock_cust_objs.get.return_value = customer
        addr = _make_address(5, label="Home", address="Old address")
        with patch("accounts.models.SavedAddress.objects") as mock_sa_objs:
            mock_sa_objs.get.return_value = addr
            resp = self._patch(
                5,
                {"label": "Work", "address": "456 New Ave", "lat": 33.5, "lng": -7.6},
                session=_session(customer_id=1),
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(addr.label, "Work")
        self.assertEqual(addr.address, "456 New Ave")
        self.assertAlmostEqual(addr.lat, 33.5)
        self.assertAlmostEqual(addr.lng, -7.6)
        addr.save.assert_called_once()
        self.assertEqual(resp.data["address"], "456 New Ave")

    @patch("accounts.models.Customer.objects")
    def test_partial_update_only_touches_provided_fields(self, mock_cust_objs):
        customer = _make_customer(customer_id=1)
        mock_cust_objs.get.return_value = customer
        addr = _make_address(5, label="Home", address="123 Main St", lat=1.0, lng=2.0)
        with patch("accounts.models.SavedAddress.objects") as mock_sa_objs:
            mock_sa_objs.get.return_value = addr
            resp = self._patch(5, {"label": "New Label"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(addr.label, "New Label")
        # Untouched fields remain as-is.
        self.assertEqual(addr.address, "123 Main St")
        self.assertEqual(addr.lat, 1.0)
        self.assertEqual(addr.lng, 2.0)

    @patch("accounts.models.Customer.objects")
    def test_blank_address_rejected_400(self, mock_cust_objs):
        customer = _make_customer(customer_id=1)
        mock_cust_objs.get.return_value = customer
        addr = _make_address(5, address="Old address")
        with patch("accounts.models.SavedAddress.objects") as mock_sa_objs:
            mock_sa_objs.get.return_value = addr
            resp = self._patch(5, {"address": "   "}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "missing_address")
        addr.save.assert_not_called()

    @patch("accounts.models.Customer.objects")
    def test_not_found_returns_404(self, mock_cust_objs):
        """B4: patching another customer's address (or an unknown id) 404s —
        SavedAddress.objects.get is scoped to (pk=address_id, customer=customer)."""
        customer = _make_customer(customer_id=1)
        mock_cust_objs.get.return_value = customer
        from accounts.models import SavedAddress
        with patch("accounts.models.SavedAddress.objects") as mock_sa_objs:
            mock_sa_objs.get.side_effect = SavedAddress.DoesNotExist
            resp = self._patch(999, {"address": "Hijack attempt"}, session=_session(customer_id=1))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
