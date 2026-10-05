"""Regression tests for activation-token secrecy + admin resend defects.

  1. Raw tokens persisted — ProvisioningJob.log and AdminAuditLog.metadata stored
     the full activation URL and the WhatsApp link (which embeds it), and the
     console serializers returned them verbatim (historical rows included).
  2. Django-admin LeadAdmin.resend_activation was a no-op (``lead.tenant_set`` —
     Lead has an FK ``tenant``) that, had it run, logged the raw token.
  3. Admin resend / onboarding package mailed or re-showed activation links for
     owners who had already activated (#457 rejects those links on click).
  4. Password reset validated, then mark_used() separately — two concurrent
     submits could both pass (same race #457 fixed for activation).
  5. Admin settings import created Category rows without the NOT NULL
     super_category → every categories import died with a misleading 409.

All tests are unit-level (SimpleTestCase + mocks — no real DB).
"""
import inspect
import secrets
from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib import admin as django_admin
from django.contrib import messages
from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import PasswordResetToken
from accounts.serializers import PASSWORD_RESET_TOKEN_EXPIRED_OR_USED, PasswordResetConfirmSerializer
from sales.admin import LeadAdmin
from sales.messaging import build_activation_url, send_activation_whatsapp
from sales.models import AdminAuditLog, Lead
from sales.redaction import mask_secret, mask_token_in, redact_tokens, redact_tokens_in
from sales.serializers import AdminAuditLogSerializer, ProvisioningJobSerializer
from sales.services import (
    OwnerAlreadyActivatedError,
    _log_owner_links,
    onboarding_package_for_lead,
    provision_lead,
    resend_activation_for_lead,
)
from sales.views import (
    LeadOnboardingPackageView,
    LeadResendActivationView,
    _apply_tenant_settings_import,
    _build_tenant_settings_export_payload,
)
from menu.views import get_or_create_default_super_category

TOKEN = secrets.token_hex(24)  # the real format: 48 lowercase hex chars
DOMAIN = "demo.example.com"


@contextmanager
def _noop_ctx(*args, **kwargs):
    yield


def _tenant():
    return SimpleNamespace(id=7, slug="demo", schema_name="demo")


def _activation_url(token=TOKEN):
    with patch("sales.messaging.primary_domain_for_tenant", return_value=DOMAIN):
        return build_activation_url(_tenant(), token)


def _whatsapp_link(token=TOKEN):
    url = _activation_url(token)
    return send_activation_whatsapp(
        "+212600000000", "https://w", "https://s", url, "https://o", "https://m", token,
    )


def _logged_lines(job):
    return [call.args[0] for call in job.append_log.call_args_list]


def _admin_user():
    return SimpleNamespace(pk=1, is_authenticated=True, is_superuser=False, is_staff=False, is_platform_admin=True)


def _resend_result(token=TOKEN):
    return SimpleNamespace(
        tenant=_tenant(),
        tenant_url=f"https://{DOMAIN}",
        workspace_url=f"https://{DOMAIN}/owner",
        signin_url=f"https://{DOMAIN}/signin",
        admin_url=f"https://{DOMAIN}/admin/",
        activation_url=_activation_url(token),
        activation_token=SimpleNamespace(token=token),
        whatsapp_link=_whatsapp_link(token),
        whatsapp_message_template="msg",
    )


# ── Redaction helpers ─────────────────────────────────────────────────────────

class RedactionHelperTests(SimpleTestCase):
    def test_mask_token_in_masks_activation_url_and_encoded_whatsapp_link(self):
        for text in (_activation_url(), _whatsapp_link()):
            masked = mask_token_in(text, TOKEN)
            self.assertNotIn(TOKEN, masked)
            self.assertIn(mask_secret(TOKEN), masked)

    def test_redact_tokens_masks_every_historical_log_form(self):
        log = (
            f"[t] Activation token: {TOKEN}\n"
            f"[t] Activation URL: {_activation_url()}\n"
            f"[t] WhatsApp link: {_whatsapp_link()}\n"
            f"[t] Activation URL: https://{DOMAIN}/activate/{TOKEN}\n"
        )
        redacted = redact_tokens(log)
        self.assertNotIn(TOKEN, redacted)
        self.assertIn(f"https://{DOMAIN}/activate?token=", redacted)

    def test_redact_tokens_leaves_masked_and_ordinary_text_alone(self):
        text = f"[t] Activation token: {mask_secret(TOKEN)}\n[t] Activation token resent\n[t] Sign-in URL: https://{DOMAIN}/signin\n"
        self.assertEqual(redact_tokens(text), text)

    def test_redact_tokens_in_walks_json_metadata(self):
        meta = {"refresh_token": True, "activation_url": _activation_url(), "nested": [{"u": _activation_url()}]}
        redacted = redact_tokens_in(meta)
        self.assertNotIn(TOKEN, repr(redacted))
        self.assertIs(redacted["refresh_token"], True)


# ── 1. Raw tokens never persisted ─────────────────────────────────────────────

class LogOwnerLinksTests(SimpleTestCase):
    def test_log_lines_never_contain_the_raw_token(self):
        job = MagicMock()
        _log_owner_links(
            job,
            token=TOKEN,
            workspace_url=f"https://{DOMAIN}/owner",
            signin_url=f"https://{DOMAIN}/signin",
            admin_url=f"https://{DOMAIN}/admin/",
            activation_url=_activation_url(),
            whatsapp_link=_whatsapp_link(),
        )
        lines = _logged_lines(job)
        self.assertTrue(any(line.startswith("Activation URL: ") for line in lines))
        self.assertTrue(any(line.startswith("WhatsApp link: ") for line in lines))
        for line in lines:
            self.assertNotIn(TOKEN, line)

    def test_provision_lead_logs_through_the_masking_helper(self):
        src = inspect.getsource(provision_lead)
        self.assertIn("_log_owner_links(", src)
        self.assertNotIn('f"Activation URL: {activation_url}"', src)
        self.assertNotIn('f"WhatsApp link: {whatsapp_link}"', src)


@patch("sales.services.transaction")
@patch("sales.services.schema_context", _noop_ctx)
class ServiceLogMaskingTests(SimpleTestCase):
    def setUp(self):
        self.job = MagicMock()
        self.job.tenant = _tenant()
        self.owner = SimpleNamespace(id=11, email="owner@example.com", last_login=None)
        self.lead = SimpleNamespace(id=3, phone="+212600000000")
        for target, value in (
            ("sales.services._get_latest_provisioning_job", self.job),
            ("sales.services._get_tenant_owner_user", self.owner),
            ("sales.services.account_is_activated", False),
            ("sales.messaging.primary_domain_for_tenant", DOMAIN),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _issued(self):
        return (
            SimpleNamespace(token=TOKEN),
            f"https://{DOMAIN}/admin/",
            f"https://{DOMAIN}/owner",
            f"https://{DOMAIN}/signin",
            f"https://{DOMAIN}",
            _activation_url(),
            _whatsapp_link(),
            "msg",
        )

    def test_resend_logs_only_the_masked_token(self, _tx):
        with patch("sales.services.issue_activation", return_value=self._issued()):
            result = resend_activation_for_lead(self.lead)
        self.assertIn(TOKEN, result.activation_url)  # the admin still gets the live link once
        for line in _logged_lines(self.job):
            self.assertNotIn(TOKEN, line)

    def test_onboarding_package_reshows_unused_token_from_the_row_not_the_log(self, _tx):
        row = SimpleNamespace(token=TOKEN)
        with patch("sales.services._get_reusable_activation_token", return_value=row) as reusable, \
                patch("sales.services.issue_activation") as issue:
            result = onboarding_package_for_lead(self.lead)
        reusable.assert_called_once_with(self.owner, self.job.tenant)
        issue.assert_not_called()
        self.assertIs(result.activation_token, row)
        self.assertEqual(result.activation_url, _activation_url())
        self.assertIn(TOKEN, result.whatsapp_link)
        lines = _logged_lines(self.job)
        self.assertTrue(lines)
        for line in lines:
            self.assertNotIn(TOKEN, line)

    def test_onboarding_package_refresh_logs_only_the_masked_token(self, _tx):
        with patch("sales.services.issue_activation", return_value=self._issued()):
            onboarding_package_for_lead(self.lead, refresh_token=True)
        for line in _logged_lines(self.job):
            self.assertNotIn(TOKEN, line)


class AdminViewAuditMaskingTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        patcher = patch("sales.messaging.primary_domain_for_tenant", return_value=DOMAIN)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _call(self, view_cls, method, path):
        request = getattr(self.factory, method)(path)
        force_authenticate(request, user=_admin_user())
        return view_cls.as_view()(request, lead_id=3)

    @patch("sales.views.log_admin_action")
    @patch("sales.views.resend_activation_for_lead")
    @patch("sales.views.get_object_or_404", return_value=SimpleNamespace(id=3))
    def test_resend_audit_metadata_is_masked(self, _get, resend, log_action):
        resend.return_value = _resend_result()
        response = self._call(LeadResendActivationView, "post", "/api/lead-resend-activation/3/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["activation_token"], TOKEN)  # one-time response keeps it
        metadata = log_action.call_args.kwargs["metadata"]
        self.assertNotIn(TOKEN, repr(metadata))
        self.assertIn(mask_secret(TOKEN), metadata["activation_url"])

    @patch("sales.views.log_admin_action")
    @patch("sales.views.onboarding_package_for_lead")
    @patch("sales.views.get_object_or_404", return_value=SimpleNamespace(id=3))
    def test_onboarding_package_audit_metadata_is_masked(self, _get, package, log_action):
        package.return_value = _resend_result()
        response = self._call(LeadOnboardingPackageView, "get", "/api/lead-onboarding-package/3/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        metadata = log_action.call_args.kwargs["metadata"]
        self.assertNotIn(TOKEN, repr(metadata))


class HistoricalRowSerializationTests(SimpleTestCase):
    def test_provisioning_job_log_is_masked_on_output(self):
        job = SimpleNamespace(
            id=1, lead=SimpleNamespace(name="Cafe"), tenant=_tenant(), status="success",
            log=f"[t] Activation token: {TOKEN}\n[t] Activation URL: {_activation_url()}\n"
                f"[t] WhatsApp link: {_whatsapp_link()}\n[t] Sign-in URL: https://{DOMAIN}/signin\n",
            created_at=timezone.now(), updated_at=timezone.now(),
        )
        data = ProvisioningJobSerializer(job).data
        self.assertNotIn(TOKEN, data["log"])
        self.assertIn(f"Sign-in URL: https://{DOMAIN}/signin", data["log"])

    def test_audit_metadata_is_masked_on_output(self):
        row = SimpleNamespace(
            id=1, action=AdminAuditLog.Actions.ACTIVATION_RESENT, actor=None, tenant=_tenant(), lead=None,
            target_repr="tenant:demo", ip_address=None,
            metadata={"activation_url": _activation_url()}, created_at=timezone.now(),
        )
        data = AdminAuditLogSerializer(row).data
        self.assertNotIn(TOKEN, repr(data["metadata"]))
        self.assertIn(f"https://{DOMAIN}/activate?token=", data["metadata"]["activation_url"])


# ── 2. Django-admin resend uses the shared service ────────────────────────────

class LeadAdminResendActionTests(SimpleTestCase):
    def setUp(self):
        self.model_admin = LeadAdmin(Lead, django_admin.site)
        self.request = RequestFactory().post("/admin/sales/lead/")
        self.request.user = SimpleNamespace(is_authenticated=True, pk=1)
        self.lead = SimpleNamespace(id=3, name="Cafe")

    @patch("sales.admin.log_admin_action")
    @patch("sales.admin.resend_activation_for_lead")
    def test_resends_through_the_shared_service_with_masked_audit(self, resend, log_action):
        resend.return_value = _resend_result()
        with patch.object(self.model_admin, "message_user") as message_user:
            self.model_admin.resend_activation(self.request, [self.lead])
        resend.assert_called_once_with(self.lead)
        log_action.assert_called_once()
        kwargs = log_action.call_args.kwargs
        self.assertEqual(kwargs["action"], AdminAuditLog.Actions.ACTIVATION_RESENT)
        self.assertNotIn(TOKEN, repr(kwargs["metadata"]))
        message_user.assert_called_once()
        self.assertIn("1 lead", message_user.call_args.args[1])

    @patch("sales.admin.log_admin_action")
    @patch("sales.admin.resend_activation_for_lead", side_effect=OwnerAlreadyActivatedError("already activated"))
    def test_activated_owner_is_reported_not_resent(self, _resend, log_action):
        with patch.object(self.model_admin, "message_user") as message_user:
            self.model_admin.resend_activation(self.request, [self.lead])
        log_action.assert_not_called()
        self.assertEqual(message_user.call_args.kwargs["level"], messages.WARNING)
        self.assertIn("already activated", message_user.call_args.args[1])

    @patch("sales.admin.resend_activation_for_lead", side_effect=RuntimeError("smtp down"))
    def test_unexpected_error_is_surfaced(self, _resend):
        with patch.object(self.model_admin, "message_user") as message_user:
            self.model_admin.resend_activation(self.request, [self.lead])
        self.assertEqual(message_user.call_args.kwargs["level"], messages.ERROR)


# ── 3. Refuse links for already-activated owners ──────────────────────────────

@patch("sales.services.transaction")
@patch("sales.services.schema_context", _noop_ctx)
class ActivatedOwnerRefusalTests(SimpleTestCase):
    def setUp(self):
        self.job = MagicMock()
        self.job.tenant = _tenant()
        self.owner = SimpleNamespace(id=11, last_login=timezone.now())
        for target, value in (
            ("sales.services._get_latest_provisioning_job", self.job),
            ("sales.services._get_tenant_owner_user", self.owner),
            ("sales.messaging.primary_domain_for_tenant", DOMAIN),
        ):
            patcher = patch(target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_resend_refuses_an_activated_owner(self, _tx):
        with patch("sales.services.issue_activation") as issue:
            with self.assertRaises(OwnerAlreadyActivatedError) as cm:
                resend_activation_for_lead(SimpleNamespace(id=3, phone=""))
        issue.assert_not_called()
        self.assertIn(f"https://{DOMAIN}/signin", str(cm.exception))
        self.job.append_log.assert_not_called()

    def test_onboarding_package_refuses_an_activated_owner_on_both_paths(self, _tx):
        for refresh in (False, True):
            with patch("sales.services.issue_activation") as issue, \
                    patch("sales.services._get_reusable_activation_token") as reusable:
                with self.assertRaises(OwnerAlreadyActivatedError):
                    onboarding_package_for_lead(SimpleNamespace(id=3, phone=""), refresh_token=refresh)
            issue.assert_not_called()
            reusable.assert_not_called()

    def test_is_a_value_error_for_existing_callers(self, _tx):
        self.assertTrue(issubclass(OwnerAlreadyActivatedError, ValueError))


class ActivatedOwnerViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @patch("sales.views.log_admin_action")
    @patch("sales.views.resend_activation_for_lead", side_effect=OwnerAlreadyActivatedError("Owner already activated."))
    @patch("sales.views.get_object_or_404", return_value=SimpleNamespace(id=3))
    def test_resend_returns_409_with_admin_message(self, _get, _resend, log_action):
        request = self.factory.post("/api/lead-resend-activation/3/")
        force_authenticate(request, user=_admin_user())
        response = LeadResendActivationView.as_view()(request, lead_id=3)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["detail"], "Owner already activated.")
        log_action.assert_not_called()

    @patch("sales.views.log_admin_action")
    @patch("sales.views.onboarding_package_for_lead", side_effect=OwnerAlreadyActivatedError("Owner already activated."))
    @patch("sales.views.get_object_or_404", return_value=SimpleNamespace(id=3))
    def test_onboarding_package_returns_409(self, _get, _package, log_action):
        request = self.factory.get("/api/lead-onboarding-package/3/", {"refresh_token": "1"})
        force_authenticate(request, user=_admin_user())
        response = LeadOnboardingPackageView.as_view()(request, lead_id=3)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        log_action.assert_not_called()

    @patch("sales.views.resend_activation_for_lead", side_effect=ValueError("No provisioned tenant found for this lead yet."))
    @patch("sales.views.get_object_or_404", return_value=SimpleNamespace(id=3))
    def test_other_value_errors_stay_400(self, _get, _resend):
        request = self.factory.post("/api/lead-resend-activation/3/")
        force_authenticate(request, user=_admin_user())
        response = LeadResendActivationView.as_view()(request, lead_id=3)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ── 4. Atomic password-reset consume ──────────────────────────────────────────

class PasswordResetTokenConsumeCasTests(SimpleTestCase):
    def _token(self):
        return PasswordResetToken(id=5, user_id=9, used_at=None, expires_at=timezone.now() + timedelta(hours=1))

    def test_consume_is_a_compare_and_set_then_revokes_siblings(self):
        tok = self._token()
        with patch.object(PasswordResetToken, "objects") as objects:
            objects.filter.return_value.update.return_value = 1
            self.assertTrue(tok.consume())
        cas_filter = objects.filter.call_args_list[0].kwargs
        self.assertEqual(cas_filter["pk"], 5)
        self.assertIs(cas_filter["used_at__isnull"], True)
        self.assertIn("expires_at__gt", cas_filter)
        self.assertEqual(objects.filter.call_args_list[1].kwargs, {"user_id": 9, "used_at__isnull": True})

    def test_losing_the_race_returns_false_and_revokes_nothing(self):
        tok = self._token()
        with patch.object(PasswordResetToken, "objects") as objects:
            objects.filter.return_value.update.return_value = 0  # the other submit won
            self.assertFalse(tok.consume())
        self.assertEqual(objects.filter.call_count, 1)
        self.assertIsNone(tok.used_at)


class PasswordResetConfirmRaceTests(SimpleTestCase):
    def setUp(self):
        self.locked_user = MagicMock(pk=9)
        user_patcher = patch("accounts.serializers.User")
        self.user_cls = user_patcher.start()
        self.addCleanup(user_patcher.stop)
        self.user_cls.objects.select_for_update.return_value.get.return_value = self.locked_user
        tx_patcher = patch("accounts.serializers.transaction")
        self.tx = tx_patcher.start()
        self.addCleanup(tx_patcher.stop)
        sessions_patcher = patch("accounts.serializers._invalidate_user_sessions")
        self.invalidate = sessions_patcher.start()
        self.addCleanup(sessions_patcher.stop)

    def _save(self, reset):
        serializer = PasswordResetConfirmSerializer()
        serializer._validated_data = {"reset": reset, "password": "Zx9kLmop-42qR"}
        serializer._errors = {}
        return serializer.save()

    def test_lost_consume_race_does_not_set_the_password(self):
        reset = MagicMock(user_id=9)
        reset.consume.return_value = False
        with self.assertRaises(ValidationError) as cm:
            self._save(reset)
        self.assertIn(PASSWORD_RESET_TOKEN_EXPIRED_OR_USED, str(cm.exception))
        self.locked_user.set_password.assert_not_called()
        self.locked_user.save.assert_not_called()
        self.invalidate.assert_not_called()

    def test_winner_resets_under_the_user_row_lock_inside_a_transaction(self):
        reset = MagicMock(user_id=9)
        reset.consume.return_value = True
        self.assertIs(self._save(reset), self.locked_user)
        self.tx.atomic.assert_called_once()
        self.user_cls.objects.select_for_update.return_value.get.assert_called_once_with(pk=9)
        self.locked_user.set_password.assert_called_once_with("Zx9kLmop-42qR")
        self.invalidate.assert_called_once_with(self.locked_user)


# ── 5. Settings import attaches categories to a super category ────────────────

@patch("sales.views.transaction")
@patch("sales.views.schema_context", _noop_ctx)
class TenantSettingsImportSuperCategoryTests(SimpleTestCase):
    def setUp(self):
        self.patches = {}
        for name in ("Category", "Dish", "DishOption", "TableLink", "SuperCategory"):
            patcher = patch(f"sales.views.{name}")
            self.patches[name] = patcher.start()
            self.addCleanup(patcher.stop)
        self.default_sc = SimpleNamespace(id=1, slug="menu")
        patcher = patch("sales.views.get_or_create_default_super_category", return_value=self.default_sc)
        self.default_helper = patcher.start()
        self.addCleanup(patcher.stop)

    def _import(self, categories, existing_super_categories=()):
        self.patches["SuperCategory"].objects.all.return_value = list(existing_super_categories)
        return _apply_tenant_settings_import(tenant=_tenant(), payload={"categories": categories})

    def test_every_imported_category_gets_the_default_super_category(self, _tx):
        summary = self._import([{"name": "Starters"}, {"name": "Mains", "super_category": "unknown"}])
        self.assertEqual(summary["categories"], 2)
        create = self.patches["Category"].objects.create
        self.assertEqual(create.call_count, 2)
        for call in create.call_args_list:
            self.assertIs(call.kwargs["super_category"], self.default_sc)
        self.default_helper.assert_called_once_with()

    def test_named_super_category_of_this_tenant_is_kept(self, _tx):
        drinks = SimpleNamespace(id=2, slug="drinks")
        self._import([{"name": "Juices", "super_category": "drinks"}], existing_super_categories=[drinks])
        create = self.patches["Category"].objects.create
        self.assertIs(create.call_args.kwargs["super_category"], drinks)
        self.default_helper.assert_not_called()

    def test_empty_category_list_creates_no_super_category(self, _tx):
        self._import([])
        self.default_helper.assert_not_called()


class DefaultSuperCategoryHelperTests(SimpleTestCase):
    @patch("menu.views.SuperCategory")
    def test_returns_the_first_existing_super_category(self, super_category_cls):
        first = SimpleNamespace(id=4)
        super_category_cls.objects.order_by.return_value.first.return_value = first
        self.assertIs(get_or_create_default_super_category(), first)
        super_category_cls.objects.order_by.assert_called_once_with("position", "id")
        super_category_cls.objects.create.assert_not_called()

    @patch("menu.views.SuperCategory")
    def test_creates_menu_when_tenant_has_none(self, super_category_cls):
        super_category_cls.objects.order_by.return_value.first.return_value = None
        super_category_cls.objects.filter.return_value.exists.return_value = False
        get_or_create_default_super_category()
        kwargs = super_category_cls.objects.create.call_args.kwargs
        self.assertEqual((kwargs["name"], kwargs["slug"], kwargs["position"]), ("Menu", "menu", 0))


class TenantSettingsExportSuperCategoryTests(SimpleTestCase):
    @patch("sales.views.TableLink")
    @patch("sales.views.ProfileSerializer")
    @patch("sales.views.Profile")
    @patch("sales.views.Category")
    @patch("sales.views.schema_context", _noop_ctx)
    def test_export_names_each_categorys_super_category(self, category_cls, profile_cls, profile_ser, table_cls):
        profile_cls.objects.get_or_create.return_value = (MagicMock(), False)
        profile_ser.return_value.data = {}
        table_cls.objects.order_by.return_value = []
        category = SimpleNamespace(
            super_category=SimpleNamespace(slug="drinks"), name="Juices", name_i18n={}, slug="juices",
            description="", description_i18n={}, image_url="", position=0, is_published=True,
            dishes=MagicMock(**{"all.return_value": []}),
        )
        category_cls.objects.select_related.return_value.order_by.return_value.prefetch_related.return_value = [category]
        tenant = MagicMock(id=7, slug="demo", schema_name="demo", is_active=True, lifecycle_status="active")
        tenant.plan = SimpleNamespace(code="growth", name="Growth")
        tenant.domains.order_by.return_value.values_list.return_value = [DOMAIN]
        payload = _build_tenant_settings_export_payload(tenant)
        self.assertEqual(payload["categories"][0]["super_category"], "drinks")
        category_cls.objects.select_related.assert_called_once_with("super_category")
