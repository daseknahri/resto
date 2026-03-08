from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory

from menu.views import PublishAccessMixin


class DummyView(PublishAccessMixin):
    pass


class _Roles:
    TENANT_OWNER = "tenant_owner"
    TENANT_STAFF = "tenant_staff"


class FakeUser:
    Roles = _Roles

    def __init__(
        self,
        *,
        is_authenticated=False,
        is_superuser=False,
        is_staff=False,
        is_platform_admin=False,
        tenant_id=None,
        role="tenant_owner",
    ):
        self.is_authenticated = is_authenticated
        self.is_superuser = is_superuser
        self.is_staff = is_staff
        self.is_platform_admin = is_platform_admin
        self.tenant_id = tenant_id
        self.role = role


class PublishPolicyTests(SimpleTestCase):
    def make_view(
        self,
        *,
        published=False,
        temporarily_disabled=False,
        note="",
        user=None,
        tenant_id=1,
    ):
        factory = APIRequestFactory()
        req = factory.get("/api/categories/")
        req.user = user or FakeUser()
        req.tenant = SimpleNamespace(id=tenant_id)
        view = DummyView()
        view.request = req
        profile = SimpleNamespace(menu_disabled_note=note)
        view._menu_is_published = lambda: published
        view._menu_is_temporarily_disabled = lambda: temporarily_disabled
        view._profile = lambda: profile
        return view

    def test_public_unpublished_menu_is_blocked(self):
        view = self.make_view(published=False, temporarily_disabled=False, user=FakeUser(is_authenticated=False))
        response = view._enforce_public_menu_policy()
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_public_temporarily_disabled_menu_returns_503_with_note(self):
        view = self.make_view(
            published=True,
            temporarily_disabled=True,
            note="Kitchen break until 18:00",
            user=FakeUser(is_authenticated=False),
        )
        response = view._enforce_public_menu_policy()
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["code"], "menu_temporarily_disabled")
        self.assertEqual(response.data["note"], "Kitchen break until 18:00")

    def test_tenant_owner_can_preview_unpublished_menu(self):
        owner = FakeUser(is_authenticated=True, tenant_id=1, role="tenant_owner")
        view = self.make_view(published=False, temporarily_disabled=False, user=owner, tenant_id=1)
        response = view._enforce_public_menu_policy()
        self.assertIsNone(response)

    def test_tenant_owner_cannot_preview_other_tenant_menu(self):
        owner = FakeUser(is_authenticated=True, tenant_id=2, role="tenant_owner")
        view = self.make_view(published=False, temporarily_disabled=False, user=owner, tenant_id=1)
        response = view._enforce_public_menu_policy()
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_can_preview_when_temporarily_disabled(self):
        admin = FakeUser(is_authenticated=True, is_platform_admin=True)
        view = self.make_view(published=False, temporarily_disabled=True, user=admin, tenant_id=1)
        response = view._enforce_public_menu_policy()
        self.assertIsNone(response)
