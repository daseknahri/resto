"""OPS-5h — loyalty-redeem idempotency key is namespaced by the TENANT schema.

WalletTransaction lives in the PUBLIC schema (accounts is a SHARED_APP), so its
``idempotency_key`` is a GLOBAL-unique namespace. CustomerLoyaltyRedeemView takes a
CLIENT-supplied idempotency_key; before this fix it wrote that raw value verbatim, so the
SAME customer reusing the SAME client key across tenant A then tenant B got tenant-A's row
back as a "duplicate" and the legitimate tenant-B redemption was silently refused (credited
nothing). The fix server-namespaces the key with connection.schema_name —
``loyalty:{schema}:{raw}`` — exactly like the sibling money paths (order-pay-{schema}-…,
orderpay:{schema}:…, voiditem:{schema}:…, ownercharge:…, ownertopup:…).

This is the cross-tenant idempotency-collision class OPS-5g closed everywhere else; mirrors
test_wallet_service.py::test_transfer_idempotency_key_collision_across_tenants_refused.

DB-backed: needs real WalletTransaction rows + the unique idempotency_key constraint, so it
runs as a TransactionTestCase in CI (it provisions Postgres). It ERRORS locally where no DB
is configured — that is expected, not a regression (same as the other money-ledger tests).

connection.schema_name is patched (rather than a physical schema_context) so the SHARED
accounts tables stay routed to public while the view sees two distinct tenant schema names —
which is the only input the namespacing depends on.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.db import connection
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory


def _auth_user(customer_id):
    u = MagicMock()
    u.is_authenticated = True
    u.customer_id = customer_id
    return u


class LoyaltyRedeemCrossTenantNamespacingTests(TransactionTestCase):
    """One customer redeeming in two different tenant schemas with the SAME client
    idempotency_key: BOTH redemptions must succeed and credit independently."""

    SCHEMA_A = "loyalty_idem_a"
    SCHEMA_B = "loyalty_idem_b"
    RAW_KEY = "client-retry-token-001"

    def setUp(self):
        from accounts.models import Customer
        from menu.views import CustomerLoyaltyRedeemView

        self.factory = APIRequestFactory()
        self.view = CustomerLoyaltyRedeemView.as_view()
        # One platform customer with enough points to redeem twice.
        self.customer = Customer.objects.create(
            name="Loyalty Roamer",
            wallet_balance=Decimal("0.00"),
            loyalty_points=1000,
            phone="+212600009001",
            phone_verified=True,
        )

    def _redeem_in_schema(self, schema_name, points=100):
        """Drive the real view with connection.schema_name pinned to *schema_name*."""
        req = self.factory.post(
            "/api/customer/loyalty/redeem/",
            {"points": points, "idempotency_key": self.RAW_KEY},
            format="json",
        )
        req.user = _auth_user(customer_id=self.customer.id)
        cfg = MagicMock(redeem_threshold=100, points_value=Decimal("0.10"))
        # LoyaltyConfig is a tenant-schema model; patch it so no physical schema is needed.
        # connection.schema_name is the ONLY thing the key-namespacing reads.
        with patch("menu.views.LoyaltyConfig.objects") as mock_cfg, \
                patch.object(connection, "schema_name", schema_name):
            mock_cfg.filter.return_value.first.return_value = cfg
            return self.view(req)

    def _balance(self):
        from accounts.models import Customer
        return Customer.objects.get(pk=self.customer.pk).wallet_balance

    def test_same_client_key_redeems_independently_in_two_tenants(self):
        from accounts.models import WalletTransaction

        # Tenant A: first redemption succeeds (not a duplicate) and credits 100 * 0.10 = 10.00.
        resp_a = self._redeem_in_schema(self.SCHEMA_A, points=100)
        self.assertEqual(resp_a.status_code, status.HTTP_200_OK)
        self.assertNotIn("duplicate", resp_a.data)  # genuine redemption, not a replay
        self.assertEqual(resp_a.data["credit_amount"], "10.00")
        self.assertEqual(self._balance(), Decimal("10.00"))

        # Tenant B: SAME client key — before the fix this was wrongly refused as a duplicate
        # (credited nothing). With schema-namespacing it is a DISTINCT key → real redemption.
        resp_b = self._redeem_in_schema(self.SCHEMA_B, points=100)
        self.assertEqual(resp_b.status_code, status.HTTP_200_OK)
        self.assertNotIn("duplicate", resp_b.data)
        self.assertEqual(resp_b.data["credit_amount"], "10.00")
        # Credited a SECOND time, independently — the whole point of the fix.
        self.assertEqual(self._balance(), Decimal("20.00"))

        # Two distinct ledger rows, each keyed by its own tenant schema.
        rows = WalletTransaction.objects.filter(
            customer_id=self.customer.id, type=WalletTransaction.Type.LOYALTY
        )
        self.assertEqual(rows.count(), 2)
        keys = set(rows.values_list("idempotency_key", flat=True))
        self.assertEqual(
            keys,
            {f"loyalty:{self.SCHEMA_A}:{self.RAW_KEY}", f"loyalty:{self.SCHEMA_B}:{self.RAW_KEY}"},
        )

    def test_same_key_same_tenant_is_still_an_idempotent_replay(self):
        """The namespacing must NOT break in-tenant idempotency: a true retry in the SAME
        tenant with the SAME key replays the prior row (no second credit)."""
        from accounts.models import WalletTransaction

        first = self._redeem_in_schema(self.SCHEMA_A, points=100)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertNotIn("duplicate", first.data)
        self.assertEqual(self._balance(), Decimal("10.00"))

        replay = self._redeem_in_schema(self.SCHEMA_A, points=100)
        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertTrue(replay.data["duplicate"])
        # No double credit; exactly one ledger row for this tenant+key.
        self.assertEqual(self._balance(), Decimal("10.00"))
        self.assertEqual(
            WalletTransaction.objects.filter(
                idempotency_key=f"loyalty:{self.SCHEMA_A}:{self.RAW_KEY}"
            ).count(),
            1,
        )
