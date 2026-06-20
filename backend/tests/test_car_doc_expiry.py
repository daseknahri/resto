"""
Unit tests for C9 — car-document expiry tracking.

Covers:
  - send_driver_doc_expiry_push_sync: no subs → 0; warning message (>0 days);
    expired message (<=0 days); locale fallback; cleans gone subs; bad doc_kind
  - check_car_doc_expiry management command: dry-run, expire sweep de-approves +
    pushes, warning sweep pushes without de-approving, push exception doesn't
    crash, output contains driver id, no drivers → clean output
  - _MANAGEMENT_COMMAND_ALLOWLIST contains check_car_doc_expiry
  - AdminCarApprovalView: accept licence_expiry / insurance_expiry on approve;
    bad date format → 400; reject ignores expiry fields; response includes expiry
  - DriverDocUploadView: re-upload clears the corresponding expiry field only
"""
from __future__ import annotations

import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory


# ── send_driver_doc_expiry_push_sync ────────────────────────────────────────

class TestSendDriverDocExpiryPushSync(SimpleTestCase):
    def _call(self, driver_id=1, doc_kind="licence", days_remaining=13):
        from accounts.push import send_driver_doc_expiry_push_sync
        return send_driver_doc_expiry_push_sync(driver_id, doc_kind, days_remaining)

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    def test_no_subs_returns_zero(self, mock_cust, mock_subs, mock_ctx):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        mock_subs.objects.filter.return_value = []
        self.assertEqual(self._call(), 0)

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_warning_message_used_when_days_positive(self, mock_send, mock_cust, mock_subs, mock_ctx):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        sub = MagicMock(endpoint="https://e", p256dh="k", auth="a")
        mock_subs.objects.filter.return_value = [sub]
        mock_send.return_value = "ok"
        self._call(days_remaining=13)
        title, body = mock_send.call_args[0][3], mock_send.call_args[0][4]
        self.assertIn("soon", title.lower())
        self.assertIn("13", body)

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_expired_message_used_when_days_zero_or_negative(self, mock_send, mock_cust, mock_subs, mock_ctx):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        sub = MagicMock(endpoint="https://e", p256dh="k", auth="a")
        mock_subs.objects.filter.return_value = [sub]
        mock_send.return_value = "ok"
        self._call(days_remaining=-1)
        title = mock_send.call_args[0][3]
        self.assertIn("expired", title.lower())

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_fr_locale_used(self, mock_send, mock_cust, mock_subs, mock_ctx):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="fr")
        sub = MagicMock(endpoint="https://e", p256dh="k", auth="a")
        mock_subs.objects.filter.return_value = [sub]
        mock_send.return_value = "ok"
        self._call(days_remaining=7)
        self.assertIn("bientot", mock_send.call_args[0][3].lower())

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_ar_locale_used(self, mock_send, mock_cust, mock_subs, mock_ctx):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="ar")
        sub = MagicMock(endpoint="https://e", p256dh="k", auth="a")
        mock_subs.objects.filter.return_value = [sub]
        mock_send.return_value = "ok"
        self._call(days_remaining=7)
        self.assertIn("قريباً", mock_send.call_args[0][3])

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_unknown_locale_falls_back_to_en(self, mock_send, mock_cust, mock_subs, mock_ctx):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="sw")
        sub = MagicMock(endpoint="https://e", p256dh="k", auth="a")
        mock_subs.objects.filter.return_value = [sub]
        mock_send.return_value = "ok"
        self._call(days_remaining=5)
        self.assertIn("soon", mock_send.call_args[0][3].lower())

    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.CustomerPushSubscription")
    @patch("accounts.models.Customer")
    @patch("menu.push._send_one")
    def test_gone_sub_deleted(self, mock_send, mock_cust, mock_subs, mock_ctx):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_cust.objects.filter.return_value.first.return_value = MagicMock(locale="en")
        sub = MagicMock(id=99, endpoint="https://gone", p256dh="k", auth="a")
        # Use a MagicMock queryset (not a plain list) so `.delete()` is available.
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([sub]))
        mock_subs.objects.filter.return_value = mock_qs
        mock_send.return_value = "gone"
        self._call()
        mock_qs.delete.assert_called_once()

    def test_invalid_doc_kind_returns_zero(self):
        result = self._call(doc_kind="passport")
        self.assertEqual(result, 0)


# ── check_car_doc_expiry management command ─────────────────────────────────

class TestCheckCarDocExpiryCommand(SimpleTestCase):
    def _run(self, **kwargs):
        from accounts.management.commands.check_car_doc_expiry import Command
        cmd = Command()
        cmd.stdout = StringIO()
        cmd.stderr = StringIO()
        cmd.handle(**{"dry_run": False, **kwargs})
        return cmd.stdout.getvalue()

    @patch("accounts.push.send_driver_doc_expiry_push_sync")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.Customer")
    def test_dry_run_does_not_save(self, mock_cust, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        today = datetime.date.today()
        past = today - datetime.timedelta(days=1)
        driver = MagicMock(id=7, driver_car_approved=True,
                           driver_licence_expiry=past, driver_insurance_expiry=None)
        mock_cust.objects.filter.return_value.filter.side_effect = [[driver], []]
        out = self._run(dry_run=True)
        driver.save.assert_not_called()
        mock_push.assert_not_called()
        self.assertIn("(dry)", out)
        self.assertIn("7", out)

    @patch("accounts.push.send_driver_doc_expiry_push_sync")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.Customer")
    def test_expire_sweep_de_approves_and_pushes(self, mock_cust, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        today = datetime.date.today()
        past = today - datetime.timedelta(days=2)
        driver = MagicMock(id=5, driver_car_approved=True,
                           driver_licence_expiry=past, driver_insurance_expiry=None)
        mock_cust.objects.filter.return_value.filter.side_effect = [[driver], []]
        self._run()
        driver.save.assert_called_once_with(update_fields=["driver_car_approved", "updated_at"])
        self.assertFalse(driver.driver_car_approved)
        mock_push.assert_called_once_with(5, "licence", -1)

    @patch("accounts.push.send_driver_doc_expiry_push_sync")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.Customer")
    def test_warning_sweep_pushes_without_de_approving(self, mock_cust, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        today = datetime.date.today()
        expiry = today + datetime.timedelta(days=13)
        driver = MagicMock(id=9, driver_car_approved=True,
                           driver_licence_expiry=expiry, driver_insurance_expiry=None)
        mock_cust.objects.filter.return_value.filter.side_effect = [[], [driver]]
        self._run()
        driver.save.assert_not_called()
        mock_push.assert_called_once_with(9, "licence", 13)

    @patch("accounts.push.send_driver_doc_expiry_push_sync", side_effect=RuntimeError("boom"))
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.Customer")
    def test_push_exception_does_not_crash_command(self, mock_cust, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        today = datetime.date.today()
        past = today - datetime.timedelta(days=1)
        driver = MagicMock(id=3, driver_car_approved=True,
                           driver_licence_expiry=past, driver_insurance_expiry=None)
        mock_cust.objects.filter.return_value.filter.side_effect = [[driver], []]
        self._run()  # must not raise

    @patch("accounts.push.send_driver_doc_expiry_push_sync")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.Customer")
    def test_output_contains_driver_id(self, mock_cust, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        today = datetime.date.today()
        past = today - datetime.timedelta(days=3)
        driver = MagicMock(id=42, driver_car_approved=True,
                           driver_licence_expiry=past, driver_insurance_expiry=None)
        mock_cust.objects.filter.return_value.filter.side_effect = [[driver], []]
        out = self._run()
        self.assertIn("42", out)

    @patch("accounts.push.send_driver_doc_expiry_push_sync")
    @patch("django_tenants.utils.schema_context")
    @patch("accounts.models.Customer")
    def test_no_expired_drivers_runs_cleanly(self, mock_cust, mock_ctx, mock_push):
        mock_ctx.return_value.__enter__ = lambda s: s
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        mock_cust.objects.filter.return_value.filter.side_effect = [[], []]
        out = self._run()
        self.assertIn("de_approved=0", out)
        self.assertIn("warned=0", out)
        mock_push.assert_not_called()


class TestAllowlistContainsCheckCarDocExpiry(SimpleTestCase):
    def test_command_in_allowlist(self):
        from accounts.tasks import _MANAGEMENT_COMMAND_ALLOWLIST
        self.assertIn("check_car_doc_expiry", _MANAGEMENT_COMMAND_ALLOWLIST)


# ── AdminCarApprovalView expiry date handling ────────────────────────────────
# Customer is a module-level import in ride_views → patch accounts.ride_views.Customer

class TestAdminCarApprovalViewExpiryDates(SimpleTestCase):
    factory = APIRequestFactory()

    def _view(self):
        from accounts.ride_views import AdminCarApprovalView
        return AdminCarApprovalView.as_view()

    @patch("sales.permissions.IsPlatformAdmin.has_permission", return_value=True)
    @patch("accounts.throttles.AdminPIIThrottle.allow_request", return_value=True)
    @patch("sales.audit.log_admin_action")
    @patch("accounts.ride_views.Customer")
    def test_approve_with_expiry_dates_saves_them(
        self, mock_cust_cls, mock_log, mock_throttle, mock_perm
    ):
        lic_exp = datetime.date(2027, 6, 1)
        ins_exp = datetime.date(2027, 12, 31)
        driver = MagicMock(
            id=11, is_driver=True, driver_car_approved=False,
            driver_licence_expiry=None, driver_insurance_expiry=None,
            driver_licence_url="https://cdn/lic.jpg",
            driver_insurance_url="https://cdn/ins.jpg",
            name="Test Driver", phone="+2126000",
        )
        mock_cust_cls.objects.get.return_value = driver

        req = self.factory.post(
            "/api/admin/drivers/11/car-approve/",
            {"licence_expiry": "2027-06-01", "insurance_expiry": "2027-12-31"},
            format="json",
        )
        resp = self._view()(req, driver_id=11)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(driver.driver_licence_expiry, lic_exp)
        self.assertEqual(driver.driver_insurance_expiry, ins_exp)
        saved_fields = driver.save.call_args.kwargs.get("update_fields", [])
        self.assertIn("driver_licence_expiry", saved_fields)
        self.assertIn("driver_insurance_expiry", saved_fields)

    @patch("sales.permissions.IsPlatformAdmin.has_permission", return_value=True)
    @patch("accounts.throttles.AdminPIIThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views.Customer")
    def test_bad_date_format_returns_400(self, mock_cust_cls, mock_throttle, mock_perm):
        driver = MagicMock(
            id=11, is_driver=True, driver_car_approved=False,
            driver_licence_expiry=None, driver_insurance_expiry=None,
            driver_licence_url="https://cdn/lic.jpg", driver_insurance_url="",
            name="", phone="",
        )
        mock_cust_cls.objects.get.return_value = driver

        req = self.factory.post(
            "/api/admin/drivers/11/car-approve/",
            {"licence_expiry": "not-a-date"},
            format="json",
        )
        resp = self._view()(req, driver_id=11)
        self.assertEqual(resp.status_code, 400)

    @patch("sales.permissions.IsPlatformAdmin.has_permission", return_value=True)
    @patch("accounts.throttles.AdminPIIThrottle.allow_request", return_value=True)
    @patch("sales.audit.log_admin_action")
    @patch("accounts.ride_views.Customer")
    def test_reject_does_not_set_expiry_fields(
        self, mock_cust_cls, mock_log, mock_throttle, mock_perm
    ):
        original_expiry = datetime.date(2027, 1, 1)
        driver = MagicMock(
            id=11, is_driver=True, driver_car_approved=True,
            driver_licence_expiry=original_expiry,
            driver_insurance_expiry=None,
            driver_licence_url="", driver_insurance_url="",
            name="", phone="",
        )
        mock_cust_cls.objects.get.return_value = driver

        req = self.factory.post(
            "/api/admin/drivers/11/car-reject/",
            {"licence_expiry": "2028-01-01"},
            format="json",
        )
        resp = self._view()(req, driver_id=11)

        self.assertEqual(resp.status_code, 200)
        # expiry NOT updated on reject
        self.assertEqual(driver.driver_licence_expiry, original_expiry)
        saved_fields = driver.save.call_args.kwargs.get("update_fields", [])
        self.assertNotIn("driver_licence_expiry", saved_fields)


# ── DriverDocUploadView clears expiry on re-upload ───────────────────────────

class TestDriverDocUploadClearsExpiry(SimpleTestCase):
    factory = APIRequestFactory()

    def _view(self):
        from accounts.ride_views import DriverDocUploadView
        return DriverDocUploadView.as_view()

    @patch("accounts.throttles.DriverDocUploadThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._save_driver_doc_image", return_value="https://cdn/new.jpg")
    @patch("accounts.ride_views.Customer")
    def test_licence_reupload_clears_licence_expiry(
        self, mock_cust_cls, mock_save, mock_throttle
    ):
        driver = MagicMock(
            id=7, is_driver=True,
            driver_licence_url="https://cdn/old.jpg",
            driver_insurance_url="https://cdn/ins.jpg",
            driver_licence_expiry=datetime.date(2025, 1, 1),
            driver_insurance_expiry=datetime.date(2026, 6, 1),
        )
        mock_cust_cls.objects.get.return_value = driver

        from django.core.files.uploadedfile import SimpleUploadedFile
        img = SimpleUploadedFile("lic.jpg", b"img", content_type="image/jpeg")
        req = self.factory.post(
            "/api/driver/docs/",
            {"kind": "licence", "image": img},
            format="multipart",
        )
        req.session = {"customer_id": 7}
        self._view()(req)

        self.assertIsNone(driver.driver_licence_expiry)
        saved_fields = driver.save.call_args.kwargs.get("update_fields", [])
        self.assertIn("driver_licence_expiry", saved_fields)
        self.assertNotIn("driver_insurance_expiry", saved_fields)

    @patch("accounts.throttles.DriverDocUploadThrottle.allow_request", return_value=True)
    @patch("accounts.ride_views._save_driver_doc_image", return_value="https://cdn/new.jpg")
    @patch("accounts.ride_views.Customer")
    def test_insurance_reupload_clears_insurance_expiry(
        self, mock_cust_cls, mock_save, mock_throttle
    ):
        driver = MagicMock(
            id=7, is_driver=True,
            driver_licence_url="https://cdn/lic.jpg",
            driver_insurance_url="https://cdn/old-ins.jpg",
            driver_licence_expiry=datetime.date(2026, 1, 1),
            driver_insurance_expiry=datetime.date(2025, 3, 1),
        )
        mock_cust_cls.objects.get.return_value = driver

        from django.core.files.uploadedfile import SimpleUploadedFile
        img = SimpleUploadedFile("ins.jpg", b"img", content_type="image/jpeg")
        req = self.factory.post(
            "/api/driver/docs/",
            {"kind": "insurance", "image": img},
            format="multipart",
        )
        req.session = {"customer_id": 7}
        self._view()(req)

        self.assertIsNone(driver.driver_insurance_expiry)
        saved_fields = driver.save.call_args.kwargs.get("update_fields", [])
        self.assertIn("driver_insurance_expiry", saved_fields)
        self.assertNotIn("driver_licence_expiry", saved_fields)
