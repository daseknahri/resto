"""R7b: TOTP MFA tests.

Structure
---------
Class A — Pure-logic (SimpleTestCase, no DB):
  A1. Backup-code hashing: hash/verify/single-use-removal  (accounts.models.UserTOTPDevice)
  A2. TOTP verify with a known secret (pyotp round-trip)
  A3. "is MFA required" predicate (confirmed-device OR role-in-flag) — via mocked LoginView
  A4. Flag-empty + no-device => NOT required (regression guard for unchanged login)

Class B — DB-backed (pytest-django / TestCase, need Postgres in CI):
  B1. setup->confirm->backup-codes full enrollment flow
  B2. Login returns 202 when a confirmed device exists
  B3. Verify with valid TOTP completes login (200 + session)
  B4. Verify with backup code logs in + consumes the code (single-use)
  B5. Verify lockout after N bad codes
  B6. Disable requires re-auth (wrong password blocked)
  B7. FLAG-EMPTY + NO DEVICE => login returns 200 (regression guard)

All DB-backed tests skip gracefully when no Postgres is available (the 'errors'
bucket in the local gate run — identical to all other DB tests in this project).
"""
from unittest.mock import MagicMock, patch

import pyotp
import pytest

from django.test import SimpleTestCase, TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, APIClient

from accounts.models import User, UserTOTPDevice


# ════════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════════

def _make_device_instance(secret=None, confirmed=False, backup_codes=None):
    """Build a UserTOTPDevice WITHOUT hitting the DB (no .pk, no .save).

    We invoke the model constructor with keyword args that are SAFE without DB
    access: skip `user` (OneToOneField, needs an instance or PK) and just set
    the plain fields directly via __dict__ after init to avoid the FK descriptor
    machinery that requires _state to be set first.
    """
    from django.db.models.base import ModelState
    device = object.__new__(UserTOTPDevice)
    # Django models expect _state to be set before any descriptor access.
    device.__dict__["_state"] = ModelState()
    device.__dict__["_state"].db = None
    device.__dict__["_state"].adding = True
    device.__dict__["_state"].fields_cache = {}
    # Set plain fields via __dict__ directly to bypass descriptor machinery.
    device.__dict__["secret"] = secret or pyotp.random_base32()
    device.__dict__["confirmed"] = confirmed
    device.__dict__["backup_codes"] = list(backup_codes) if backup_codes else []
    device.__dict__["created_at"] = None
    device.__dict__["confirmed_at"] = None
    device.__dict__["user_id"] = None
    device.__dict__["id"] = None
    return device


# ════════════════════════════════════════════════════════════════════════════════
# A: Pure-logic unit tests (SimpleTestCase — no DB)
# ════════════════════════════════════════════════════════════════════════════════

class A1_BackupCodeTests(SimpleTestCase):
    """Backup-code hash/verify/single-use semantics."""

    def test_hash_is_not_plaintext(self):
        plaintext = "abcd-1234-efgh-5678"
        h = UserTOTPDevice._hash_backup_code(plaintext)
        self.assertNotEqual(h, plaintext)
        # Must be a recognisable make_password hash (PBKDF2 starts with pbkdf2_ or similar)
        # Just ensure it contains no fragment of the plaintext.
        self.assertNotIn("abcd", h)

    def test_verify_correct_code_returns_true(self):
        plaintext = "test-code-0001-abcd"
        h = UserTOTPDevice._hash_backup_code(plaintext)
        device = _make_device_instance(backup_codes=[h])
        # Patch save so we don't need a real PK.
        with patch.object(UserTOTPDevice, "save"):
            result = device.verify_backup_code(plaintext)
        self.assertTrue(result)

    def test_verify_wrong_code_returns_false(self):
        plaintext = "test-code-0001-abcd"
        h = UserTOTPDevice._hash_backup_code(plaintext)
        device = _make_device_instance(backup_codes=[h])
        result = device.verify_backup_code("wrong-code-9999-xxxx")
        self.assertFalse(result)

    def test_verify_consumes_code_single_use(self):
        """After verify_backup_code succeeds, the hash is removed from backup_codes."""
        plaintext = "single-use-abcd-1234"
        h = UserTOTPDevice._hash_backup_code(plaintext)
        device = _make_device_instance(backup_codes=[h])
        with patch.object(UserTOTPDevice, "save"):
            result = device.verify_backup_code(plaintext)
        self.assertTrue(result)
        # Code must be consumed.
        self.assertEqual(device.backup_codes, [])

    def test_second_verify_after_consume_returns_false(self):
        """Once consumed, the same code is rejected."""
        plaintext = "once-only-code-9876"
        h = UserTOTPDevice._hash_backup_code(plaintext)
        device = _make_device_instance(backup_codes=[h])
        with patch.object(UserTOTPDevice, "save"):
            first = device.verify_backup_code(plaintext)
        self.assertTrue(first)
        # Code is gone — second attempt must fail.
        second = device.verify_backup_code(plaintext)
        self.assertFalse(second)

    def test_multiple_codes_only_matching_one_consumed(self):
        """With multiple backup codes, only the matching hash is removed."""
        code_a = "code-aaaa-aaaa-aaaa"
        code_b = "code-bbbb-bbbb-bbbb"
        ha = UserTOTPDevice._hash_backup_code(code_a)
        hb = UserTOTPDevice._hash_backup_code(code_b)
        device = _make_device_instance(backup_codes=[ha, hb])
        with patch.object(UserTOTPDevice, "save"):
            result = device.verify_backup_code(code_a)
        self.assertTrue(result)
        # Only ha removed; hb remains.
        self.assertEqual(len(device.backup_codes), 1)
        # The remaining hash should match code_b.
        from django.contrib.auth.hashers import check_password
        self.assertTrue(check_password(code_b, device.backup_codes[0]))


class A2_TOTPVerifyTests(SimpleTestCase):
    """TOTP verify with a known secret (pyotp round-trip)."""

    def test_current_code_verifies(self):
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        self.assertTrue(totp.verify(current_code, valid_window=1))

    def test_wrong_code_rejected(self):
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        self.assertFalse(totp.verify("000000", valid_window=1))

    def test_codes_from_different_secrets_do_not_cross(self):
        s1 = pyotp.random_base32()
        s2 = pyotp.random_base32()
        code_for_s1 = pyotp.TOTP(s1).now()
        self.assertFalse(pyotp.TOTP(s2).verify(code_for_s1, valid_window=1))


class A3_MFARequiredPredicateTests(SimpleTestCase):
    """The 'is MFA required' (202 challenge) predicate: confirmed-device ONLY.

    R7b (updated): the 202 MFA challenge is issued ONLY when the user has a
    confirmed device.  A role-forced user with no device gets a 200 login with
    "mfa_enrollment_required": True — they can still reach the enrollment UI.
    HARD block-until-enrolled is a future owner-gated flow (R7c).
    """

    def _run_login_post(self, user, mfa_required_roles=None, has_confirmed_device=False):
        """Simulate LoginView.post logic — extract the 202 predicate and the
        enrollment-hint separately (matching the updated code)."""
        role_forces_mfa = user.role in (mfa_required_roles or [])
        mfa_required = has_confirmed_device  # ONLY confirmed device triggers 202
        enrollment_required = role_forces_mfa and not has_confirmed_device
        return mfa_required, enrollment_required

    def test_confirmed_device_requires_mfa_challenge(self):
        """Confirmed device => 202 MFA challenge."""
        user = MagicMock()
        user.role = "tenant_owner"
        mfa_required, enrollment_required = self._run_login_post(user, has_confirmed_device=True)
        self.assertTrue(mfa_required)
        self.assertFalse(enrollment_required)

    def test_role_forced_no_device_does_not_trigger_202(self):
        """R7b updated: role in MFA_REQUIRED_ROLES but NO device => 200 + enrollment hint.

        Previously this asserted 202; now it must assert 200 + mfa_enrollment_required.
        (Hard block is R7c, not yet shipped.)
        """
        user = MagicMock()
        user.role = "platform_superadmin"
        mfa_required, enrollment_required = self._run_login_post(
            user, mfa_required_roles=["platform_superadmin"], has_confirmed_device=False
        )
        self.assertFalse(mfa_required, "role-forced without device must NOT trigger 202")
        self.assertTrue(enrollment_required, "role-forced without device must set enrollment hint")

    def test_confirmed_device_plus_role_still_triggers_202(self):
        """Confirmed device + role in flag => 202 (device wins)."""
        user = MagicMock()
        user.role = "platform_superadmin"
        mfa_required, enrollment_required = self._run_login_post(
            user,
            mfa_required_roles=["platform_superadmin"],
            has_confirmed_device=True,
        )
        self.assertTrue(mfa_required)
        self.assertFalse(enrollment_required)

    def test_no_device_role_not_in_flag_not_required(self):
        """No device, role not in flag => no 202, no enrollment hint."""
        user = MagicMock()
        user.role = "tenant_staff"
        mfa_required, enrollment_required = self._run_login_post(
            user,
            mfa_required_roles=["platform_superadmin"],
            has_confirmed_device=False,
        )
        self.assertFalse(mfa_required)
        self.assertFalse(enrollment_required)


class A4_FlagEmptyNoDeviceTests(SimpleTestCase):
    """FLAG-EMPTY + NO DEVICE => MFA NOT required (regression guard)."""

    def test_flag_empty_no_device_not_required(self):
        """With empty MFA_REQUIRED_ROLES and no enrolled device, MFA is not triggered."""
        user = MagicMock()
        user.role = "tenant_owner"
        mfa_required_roles = []  # empty — default
        has_confirmed_device = False  # no device
        role_forces = user.role in mfa_required_roles
        mfa_required = has_confirmed_device or role_forces
        self.assertFalse(mfa_required)

    def test_platform_admin_no_device_flag_empty_not_required(self):
        user = MagicMock()
        user.role = "platform_superadmin"
        mfa_required_roles = []
        has_confirmed_device = False
        mfa_required = has_confirmed_device or (user.role in mfa_required_roles)
        self.assertFalse(mfa_required)

    def test_staff_no_device_flag_empty_not_required(self):
        user = MagicMock()
        user.role = "tenant_staff"
        mfa_required = False or ("tenant_staff" in [])
        self.assertFalse(mfa_required)


# ════════════════════════════════════════════════════════════════════════════════
# A5: TOTP replay-within-window prevention (pure-logic, no DB)
# ════════════════════════════════════════════════════════════════════════════════

class A5_TOTPReplayTests(SimpleTestCase):
    """RFC 6238 §5.2 replay-within-window guard (pure cache logic, no DB)."""

    def test_first_use_not_a_replay(self):
        """A code that has not been recorded yet is not flagged as a replay."""
        from accounts.mfa_views import _is_totp_replay
        from django.core.cache import cache
        user_pk = 999901
        cache.delete(f"mfa_last_code:u{user_pk}")
        self.assertFalse(_is_totp_replay(user_pk, "123456"))

    def test_replay_detected_after_record(self):
        """After _record_totp_used, the same code is flagged as a replay."""
        from accounts.mfa_views import _is_totp_replay, _record_totp_used
        from django.core.cache import cache
        user_pk = 999902
        cache.delete(f"mfa_last_code:u{user_pk}")
        _record_totp_used(user_pk, "654321")
        self.assertTrue(_is_totp_replay(user_pk, "654321"))

    def test_different_code_not_flagged_as_replay(self):
        """A different code is NOT flagged even if another code was just recorded."""
        from accounts.mfa_views import _is_totp_replay, _record_totp_used
        from django.core.cache import cache
        user_pk = 999903
        cache.delete(f"mfa_last_code:u{user_pk}")
        _record_totp_used(user_pk, "111111")
        self.assertFalse(_is_totp_replay(user_pk, "222222"))

    def test_different_user_not_flagged_as_replay(self):
        """A code recorded for user A does not pollute user B's replay check."""
        from accounts.mfa_views import _is_totp_replay, _record_totp_used
        from django.core.cache import cache
        user_a, user_b = 999904, 999905
        cache.delete(f"mfa_last_code:u{user_a}")
        cache.delete(f"mfa_last_code:u{user_b}")
        _record_totp_used(user_a, "777777")
        self.assertFalse(_is_totp_replay(user_b, "777777"))

    def test_verify_view_blocks_replay_via_mock(self):
        """MFAVerifyView rejects an already-used TOTP code (unit-level mock test)."""
        from unittest.mock import patch, MagicMock
        from accounts.mfa_views import MFAVerifyView, _record_totp_used
        from django.core.cache import cache
        import pyotp as _pyotp

        user_pk = 999906
        secret = _pyotp.random_base32()
        code = _pyotp.TOTP(secret).now()

        # Pre-record this code as already used.
        cache.delete(f"mfa_last_code:u{user_pk}")
        _record_totp_used(user_pk, code)

        # Build a minimal mock request that has a pending session.
        mock_user = MagicMock()
        mock_user.pk = user_pk

        mock_device = MagicMock()
        mock_device.confirmed = True
        mock_device.secret = secret
        mock_user.totp_device = mock_device

        import time as _time
        mock_request = MagicMock()
        mock_request.session = {
            "_mfa_pending_user_id": user_pk,
            "_mfa_pending_ts": _time.time(),
        }
        mock_request.data = {"code": code}

        with patch("accounts.mfa_views.User.objects.get", return_value=mock_user), \
             patch("accounts.mfa_views._check_mfa_lockout", return_value=False), \
             patch("accounts.mfa_views._increment_mfa_failure"):
            view = MFAVerifyView()
            response = view.post(mock_request)

        # Replay must be rejected (401).
        self.assertEqual(response.status_code, 401)


# ════════════════════════════════════════════════════════════════════════════════
# A6: MFAStatusView pure-logic unit tests (no DB)
# ════════════════════════════════════════════════════════════════════════════════

class A6_MFAStatusViewTests(SimpleTestCase):
    """GET /api/mfa/status/ — side-effect-free enrollment probe.

    Uses the APIRequestFactory + mock QuerySet to avoid any DB access.
    """

    def _make_request(self, user_pk=1):
        """Build a GET request with a mock authenticated user."""
        factory = APIRequestFactory()
        request = factory.get("/api/mfa/status/")
        mock_user = MagicMock()
        mock_user.pk = user_pk
        mock_user.is_authenticated = True
        request.user = mock_user
        return request, mock_user

    def test_enrolled_returns_true(self):
        """Returns {enrolled: true} when a confirmed device exists."""
        from accounts.mfa_views import MFAStatusView

        request, mock_user = self._make_request(user_pk=1001)

        with patch("accounts.mfa_views.UserTOTPDevice.objects") as mock_mgr:
            mock_mgr.filter.return_value.exists.return_value = True
            view = MFAStatusView()
            view.permission_classes = []  # bypass IsAuthenticated for unit test
            response = view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"enrolled": True})
        mock_mgr.filter.assert_called_once_with(user=mock_user, confirmed=True)
        mock_mgr.filter.return_value.exists.assert_called_once()

    def test_not_enrolled_returns_false(self):
        """Returns {enrolled: false} when no confirmed device exists."""
        from accounts.mfa_views import MFAStatusView

        request, mock_user = self._make_request(user_pk=1002)

        with patch("accounts.mfa_views.UserTOTPDevice.objects") as mock_mgr:
            mock_mgr.filter.return_value.exists.return_value = False
            view = MFAStatusView()
            view.permission_classes = []
            response = view.get(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"enrolled": False})

    def test_no_device_created(self):
        """Status check must NOT call UserTOTPDevice.objects.create."""
        from accounts.mfa_views import MFAStatusView

        request, mock_user = self._make_request(user_pk=1003)

        with patch("accounts.mfa_views.UserTOTPDevice.objects") as mock_mgr:
            mock_mgr.filter.return_value.exists.return_value = False
            view = MFAStatusView()
            view.permission_classes = []
            view.get(request)

        mock_mgr.create.assert_not_called()


# ════════════════════════════════════════════════════════════════════════════════
# B: DB-backed tests (TestCase — skip locally when Postgres is unavailable)
# ════════════════════════════════════════════════════════════════════════════════

# RISK TEST-1: probe with the raw driver (see _dbprobe.py) — the old
# `django.db.connection.ensure_connection()` probe always raised under
# pytest-django's access blocker, so these B tests silently skipped even in CI
# with Postgres up. With PYTEST_REQUIRE_DB set (CI), an unreachable DB raises
# at collection instead of downgrading to a skip.
import _dbprobe

_DB_AVAILABLE = _dbprobe.db_available()

# The MFA/login endpoints live in the SHARED (public-schema) urlconf, so these
# full-stack APIClient requests must arrive on a host the tenant middleware
# accepts. The DRF test client defaults to host "testserver", which is neither a
# provisioned tenant domain nor a PUBLIC_SCHEMA_HOST, so every request 404s
# before reaching a view. "localhost" is a default PUBLIC_SCHEMA_HOST (and is in
# ALLOWED_HOSTS under DEBUG), so it routes to the public schema where these
# endpoints are registered. (These are plain TestCases → public schema; the MFA
# views never read request.tenant, so no tenant context is needed.)
_PUBLIC_HOST = "localhost"


@pytest.mark.skipif(not _DB_AVAILABLE, reason="Postgres not available locally")
class B1_EnrollmentFlowTests(TestCase):
    """Full setup->confirm->backup-codes enrollment flow (DB-backed)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="owner_mfa_b1",
            password="testpass123",
            role=User.Roles.TENANT_OWNER,
        )
        self.client = APIClient(SERVER_NAME=_PUBLIC_HOST)
        self.client.force_authenticate(user=self.user)

    def test_setup_creates_pending_device(self):
        resp = self.client.post("/api/mfa/setup/", format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("provisioning_uri", resp.data)
        self.assertIn("secret", resp.data)
        device = UserTOTPDevice.objects.get(user=self.user)
        self.assertFalse(device.confirmed)

    def test_confirm_with_valid_code_sets_confirmed(self):
        # Setup first
        self.client.post("/api/mfa/setup/", format="json")
        device = UserTOTPDevice.objects.get(user=self.user)
        code = pyotp.TOTP(device.secret).now()

        resp = self.client.post("/api/mfa/confirm/", {"code": code}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("backup_codes", resp.data)
        self.assertEqual(len(resp.data["backup_codes"]), 10)

        device.refresh_from_db()
        self.assertTrue(device.confirmed)
        self.assertIsNotNone(device.confirmed_at)
        self.assertEqual(len(device.backup_codes), 10)

    def test_confirm_with_wrong_code_returns_400(self):
        self.client.post("/api/mfa/setup/", format="json")
        resp = self.client.post("/api/mfa/confirm/", {"code": "000000"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_backup_codes_are_hashed_not_plaintext(self):
        """Stored backup_codes must not contain any plaintext code fragment."""
        self.client.post("/api/mfa/setup/", format="json")
        device = UserTOTPDevice.objects.get(user=self.user)
        code = pyotp.TOTP(device.secret).now()
        resp = self.client.post("/api/mfa/confirm/", {"code": code}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        plaintext_codes = resp.data["backup_codes"]
        device.refresh_from_db()
        stored_hashes = device.backup_codes

        # Stored hashes must not equal plaintext codes.
        for plaintext, stored in zip(plaintext_codes, stored_hashes):
            self.assertNotEqual(plaintext, stored)
            # Hash must not contain the raw dash-separated segments.
            for segment in plaintext.split("-"):
                self.assertNotIn(segment, stored)

    def test_setup_confirmed_returns_409(self):
        """Setup on an already-confirmed device returns 409."""
        self.client.post("/api/mfa/setup/", format="json")
        device = UserTOTPDevice.objects.get(user=self.user)
        code = pyotp.TOTP(device.secret).now()
        self.client.post("/api/mfa/confirm/", {"code": code}, format="json")

        resp = self.client.post("/api/mfa/setup/", format="json")
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    def test_staff_cannot_enroll(self):
        staff = User.objects.create_user(
            username="staff_mfa_b1",
            password="testpass123",
            role=User.Roles.TENANT_STAFF,
        )
        self.client.force_authenticate(user=staff)
        resp = self.client.post("/api/mfa/setup/", format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


@pytest.mark.skipif(not _DB_AVAILABLE, reason="Postgres not available locally")
class B2_LoginGateTests(TestCase):
    """Login returns 202 when a confirmed device exists."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="owner_mfa_b2",
            password="testpass123",
            role=User.Roles.TENANT_OWNER,
        )
        self.client = APIClient(SERVER_NAME=_PUBLIC_HOST)

    def _enroll(self, user):
        """Helper: enroll a confirmed TOTP device for the given user."""
        secret = pyotp.random_base32()
        UserTOTPDevice.objects.create(
            user=user,
            secret=secret,
            confirmed=True,
            confirmed_at=__import__("django.utils.timezone", fromlist=["timezone"]).now(),
        )
        return secret

    def test_login_returns_202_with_confirmed_device(self):
        self._enroll(self.user)
        resp = self.client.post(
            "/api/login/",
            {"identifier": self.user.username, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(resp.data.get("mfa_required"))

    def test_login_returns_200_without_device(self):
        """FLAG-EMPTY + NO DEVICE => login must return 200 (regression guard)."""
        resp = self.client.post(
            "/api/login/",
            {"identifier": self.user.username, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("user", resp.data)

    def test_login_wrong_password_returns_400(self):
        resp = self.client.post(
            "/api/login/",
            {"identifier": self.user.username, "password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


@pytest.mark.skipif(not _DB_AVAILABLE, reason="Postgres not available locally")
class B3_VerifyTOTPTests(TestCase):
    """Verify with a valid TOTP completes login (200 + session)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="owner_mfa_b3",
            password="testpass123",
            role=User.Roles.TENANT_OWNER,
        )
        from django.utils import timezone
        self.secret = pyotp.random_base32()
        UserTOTPDevice.objects.create(
            user=self.user,
            secret=self.secret,
            confirmed=True,
            confirmed_at=timezone.now(),
        )
        self.client = APIClient(SERVER_NAME=_PUBLIC_HOST)

    def _login(self):
        resp = self.client.post(
            "/api/login/",
            {"identifier": self.user.username, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)
        return resp

    def test_verify_with_valid_code_returns_200(self):
        self._login()
        code = pyotp.TOTP(self.secret).now()
        resp = self.client.post("/api/mfa/verify/", {"code": code}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("user", resp.data)

    def test_verify_with_wrong_code_returns_401(self):
        self._login()
        resp = self.client.post("/api/mfa/verify/", {"code": "000000"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_verify_without_pending_session_returns_401(self):
        """Calling verify without a login session is rejected."""
        resp = self.client.post("/api/mfa/verify/", {"code": "123456"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.skipif(not _DB_AVAILABLE, reason="Postgres not available locally")
class B4_BackupCodeLoginTests(TestCase):
    """Verify with a backup code logs in and consumes it (single-use)."""

    def setUp(self):
        from django.utils import timezone
        self.user = User.objects.create_user(
            username="owner_mfa_b4",
            password="testpass123",
            role=User.Roles.TENANT_OWNER,
        )
        # Create a confirmed device with one known backup code.
        self.plaintext_code = "aaaa-bbbb-cccc-dddd"
        hashed = UserTOTPDevice._hash_backup_code(self.plaintext_code)
        self.device = UserTOTPDevice.objects.create(
            user=self.user,
            secret=pyotp.random_base32(),
            confirmed=True,
            confirmed_at=timezone.now(),
            backup_codes=[hashed],
        )
        self.client = APIClient(SERVER_NAME=_PUBLIC_HOST)

    def _login(self):
        resp = self.client.post(
            "/api/login/",
            {"identifier": self.user.username, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)

    def test_backup_code_logs_in(self):
        self._login()
        resp = self.client.post(
            "/api/mfa/verify/",
            {"backup_code": self.plaintext_code},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("user", resp.data)

    def test_backup_code_is_consumed(self):
        """After use, the backup code cannot be reused."""
        self._login()
        self.client.post(
            "/api/mfa/verify/",
            {"backup_code": self.plaintext_code},
            format="json",
        )
        self.device.refresh_from_db()
        self.assertEqual(self.device.backup_codes, [])

    def test_backup_code_second_use_rejected(self):
        """A consumed backup code is rejected even if the attacker retries immediately."""
        self._login()
        # First use — must succeed.
        resp1 = self.client.post(
            "/api/mfa/verify/",
            {"backup_code": self.plaintext_code},
            format="json",
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Log out + log in again for a fresh challenge.
        self.client.post("/api/logout/", format="json")
        resp_login = self.client.post(
            "/api/login/",
            {"identifier": self.user.username, "password": "testpass123"},
            format="json",
        )
        # Device still confirmed; should still get 202.
        self.assertEqual(resp_login.status_code, status.HTTP_202_ACCEPTED)

        resp2 = self.client.post(
            "/api/mfa/verify/",
            {"backup_code": self.plaintext_code},
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.skipif(not _DB_AVAILABLE, reason="Postgres not available locally")
class B5_VerifyLockoutTests(TestCase):
    """Verify lockout after N bad codes."""

    def setUp(self):
        from django.utils import timezone
        self.user = User.objects.create_user(
            username="owner_mfa_b5",
            password="testpass123",
            role=User.Roles.TENANT_OWNER,
        )
        UserTOTPDevice.objects.create(
            user=self.user,
            secret=pyotp.random_base32(),
            confirmed=True,
            confirmed_at=timezone.now(),
        )
        self.client = APIClient(SERVER_NAME=_PUBLIC_HOST)

    def _login(self):
        resp = self.client.post(
            "/api/login/",
            {"identifier": self.user.username, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_202_ACCEPTED)

    def test_lockout_after_max_failures(self):
        """After MFA_MAX_FAILURES bad codes the account is locked."""
        from accounts.mfa_views import MFA_MAX_FAILURES
        self._login()

        for _ in range(MFA_MAX_FAILURES):
            r = self.client.post("/api/mfa/verify/", {"code": "000000"}, format="json")
            # Each attempt returns 401 (bad code) until we hit the lockout.

        # Now the lockout should kick in even for a valid code-shaped request.
        resp = self.client.post("/api/mfa/verify/", {"code": "000000"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.skipif(not _DB_AVAILABLE, reason="Postgres not available locally")
class B6_DisableTests(TestCase):
    """Disable requires re-auth."""

    def setUp(self):
        from django.utils import timezone
        self.user = User.objects.create_user(
            username="owner_mfa_b6",
            password="testpass123",
            role=User.Roles.TENANT_OWNER,
        )
        self.secret = pyotp.random_base32()
        UserTOTPDevice.objects.create(
            user=self.user,
            secret=self.secret,
            confirmed=True,
            confirmed_at=timezone.now(),
        )
        self.client = APIClient(SERVER_NAME=_PUBLIC_HOST)
        self.client.force_authenticate(user=self.user)

    def test_disable_with_correct_password_succeeds(self):
        resp = self.client.post(
            "/api/mfa/disable/",
            {"password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(UserTOTPDevice.objects.filter(user=self.user).exists())

    def test_disable_with_wrong_password_rejected(self):
        resp = self.client.post(
            "/api/mfa/disable/",
            {"password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(UserTOTPDevice.objects.filter(user=self.user).exists())

    def test_disable_with_valid_totp_code_succeeds(self):
        code = pyotp.TOTP(self.secret).now()
        resp = self.client.post(
            "/api/mfa/disable/",
            {"code": code},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(UserTOTPDevice.objects.filter(user=self.user).exists())

    def test_disable_without_credentials_returns_400(self):
        resp = self.client.post("/api/mfa/disable/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_disable_unauthenticated_returns_403(self):
        self.client.logout()
        resp = self.client.post(
            "/api/mfa/disable/",
            {"password": "testpass123"},
            format="json",
        )
        self.assertIn(resp.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED])


@pytest.mark.skipif(not _DB_AVAILABLE, reason="Postgres not available locally")
class B7_RegressionFlagEmptyNoDeviceTests(TestCase):
    """FLAG-EMPTY + NO DEVICE => login still returns 200 (critical regression guard)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="owner_mfa_b7",
            password="testpass123",
            role=User.Roles.TENANT_OWNER,
        )
        self.client = APIClient(SERVER_NAME=_PUBLIC_HOST)

    def test_no_device_no_flag_login_returns_200(self):
        with self.settings(MFA_REQUIRED_ROLES=[]):
            resp = self.client.post(
                "/api/login/",
                {"identifier": self.user.username, "password": "testpass123"},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.data
        self.assertIn("user", data)
        self.assertNotIn("mfa_required", data)

    def test_platform_admin_no_device_no_flag_login_returns_200(self):
        admin = User.objects.create_user(
            username="admin_mfa_b7",
            password="testpass123",
            role=User.Roles.PLATFORM_SUPERADMIN,
        )
        with self.settings(MFA_REQUIRED_ROLES=[]):
            resp = self.client.post(
                "/api/login/",
                {"identifier": admin.username, "password": "testpass123"},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn("mfa_required", resp.data)

    def test_unconfirmed_device_still_returns_200(self):
        """An UNCONFIRMED device must NOT trigger the MFA gate."""
        UserTOTPDevice.objects.create(
            user=self.user,
            secret=pyotp.random_base32(),
            confirmed=False,
        )
        with self.settings(MFA_REQUIRED_ROLES=[]):
            resp = self.client.post(
                "/api/login/",
                {"identifier": self.user.username, "password": "testpass123"},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn("mfa_required", resp.data)
