from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from accounts.serializers import LoginSerializer


class LoginSerializerTenantInactiveTests(SimpleTestCase):
    @patch("accounts.serializers.User.objects")
    def test_rejects_login_when_tenant_is_inactive(self, user_objects):
        user = SimpleNamespace(
            check_password=lambda _: True,
            is_active=True,
            tenant_id=11,
            tenant=SimpleNamespace(is_active=False, lifecycle_status="suspended"),
        )
        scope = Mock()
        scope.order_by.return_value = scope
        scope.first.return_value = user
        user_objects.filter.return_value = scope

        serializer = LoginSerializer(data={"identifier": "owner@example.com", "password": "Secret123!"})
        is_valid = serializer.is_valid()

        self.assertFalse(is_valid)
        self.assertIn("Tenant is suspended. Contact support.", str(serializer.errors))
