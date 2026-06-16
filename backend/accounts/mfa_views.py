"""R7b: TOTP MFA views.

Endpoints
---------
POST /api/mfa/setup/    — Begin enrollment: (re)generate a TOTP secret, return URI.
POST /api/mfa/confirm/  — Finish enrollment: verify first live code, issue backup codes.
POST /api/mfa/verify/   — Second-factor step of the login flow (completes auth).
POST /api/mfa/disable/  — Remove the TOTP device; requires re-auth.

Safety invariant
----------------
LoginView still calls login() immediately for users who have no confirmed device AND
whose role is not in settings.MFA_REQUIRED_ROLES. Only when MFA is required does
LoginView return HTTP 202 and set request.session["_mfa_pending_user_id"]. This module
provides the /api/mfa/verify/ endpoint that completes that deferred auth.

Lockout
-------
MFAVerifyView reuses the same per-account lockout mechanism as LoginSerializer (the
"login_fail:u<pk>" cache key). Bad TOTP OR bad backup_code attempts increment the
same counter under a parallel "mfa_fail:u<pk>" key with identical semantics — a fixed
15-minute window starting at the first failure, using cache.add() + cache.incr().
"""

import hashlib
import logging
import secrets as _secrets
from datetime import timedelta

import pyotp

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserTOTPDevice
from .throttles import (
    MFAConfirmThrottle,
    MFADisableThrottle,
    MFAVerifyBurstThrottle,
    MFAVerifySustainedThrottle,
)
from .views import serialize_user_session
from sales.audit import log_admin_action

User = get_user_model()

logger = logging.getLogger("app.mfa")

# ── Lockout constants (mirror LoginSerializer values) ────────────────────────
MFA_MAX_FAILURES = 10
MFA_LOCK_SECONDS = 900   # 15-minute fixed window

# Number of backup codes to generate at confirm time.
MFA_BACKUP_CODE_COUNT = 10
# Each backup code is 8 random hex bytes → 16 hex chars, grouped as XXXX-XXXX-XXXX-XXXX.
MFA_BACKUP_CODE_BYTES = 8

# How long the pending-MFA session key is considered valid (seconds).
MFA_PENDING_TTL_SECONDS = 600  # 10 minutes


def _mfa_fail_cache_key(user_pk: int) -> str:
    return f"mfa_fail:u{user_pk}"


def _increment_mfa_failure(user_pk: int) -> int:
    """Atomic fixed-window increment; return new count. Never raises."""
    key = _mfa_fail_cache_key(user_pk)
    try:
        cache.add(key, 0, MFA_LOCK_SECONDS)
        return cache.incr(key)
    except Exception:
        return 0


def _check_mfa_lockout(user_pk: int) -> bool:
    """Return True if the account is currently locked out for MFA failures."""
    try:
        count = cache.get(_mfa_fail_cache_key(user_pk)) or 0
        return count >= MFA_MAX_FAILURES
    except Exception:
        return False  # fail open


def _clear_mfa_lockout(user_pk: int) -> None:
    try:
        cache.delete(_mfa_fail_cache_key(user_pk))
    except Exception:
        pass


# ── TOTP replay-within-window prevention ────────────────────────────────────
# RFC 6238 §5.2 recommends tracking the last accepted OTP to prevent an
# adversary from reusing a code within its valid window (~90 s with
# valid_window=1).  We store the last accepted code per user in the cache
# with TTL = 90 s (3 × 30 s TOTP step).

_TOTP_REPLAY_TTL = 90  # seconds — covers valid_window=1 (3 × 30 s)


def _mfa_last_code_cache_key(user_pk: int) -> str:
    return f"mfa_last_code:u{user_pk}"


def _is_totp_replay(user_pk: int, code: str) -> bool:
    """Return True if *code* was the last successfully accepted TOTP for this user."""
    try:
        return cache.get(_mfa_last_code_cache_key(user_pk)) == code
    except Exception:
        return False  # fail open — never block a valid login on cache errors


def _record_totp_used(user_pk: int, code: str) -> None:
    """Record *code* as the last accepted TOTP for this user (TTL = 90 s)."""
    try:
        cache.set(_mfa_last_code_cache_key(user_pk), code, _TOTP_REPLAY_TTL)
    except Exception:
        pass  # best-effort; a cache miss just means the next call verifies via pyotp


def _generate_backup_codes() -> tuple[list[str], list[str]]:
    """Return (plaintext_codes, hashed_codes) for storage + one-time display."""
    plaintexts = []
    hashes = []
    for _ in range(MFA_BACKUP_CODE_COUNT):
        raw = _secrets.token_hex(MFA_BACKUP_CODE_BYTES)
        # Format as XXXX-XXXX-XXXX-XXXX for readability.
        formatted = f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}"
        plaintexts.append(formatted)
        hashes.append(UserTOTPDevice._hash_backup_code(formatted))
    return plaintexts, hashes


def _is_enrollment_role(user) -> bool:
    """Return True if the user is allowed to self-enrol (owner or platform admin)."""
    return user.role in (
        User.Roles.PLATFORM_SUPERADMIN,
        User.Roles.TENANT_OWNER,
    )


class MFASetupView(APIView):
    """POST /api/mfa/setup/

    Begin (or re-initiate) TOTP enrollment.  Creates/resets an unconfirmed device
    and returns the provisioning URI + raw secret.  Only PLATFORM_SUPERADMIN and
    TENANT_OWNER may enrol; staff must ask their owner.

    If a CONFIRMED device already exists, returns 409 — caller must disable first.
    The secret is never written to application logs.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not _is_enrollment_role(user):
            return Response(
                {"detail": "MFA enrollment is restricted to platform admins and tenant owners."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            existing = user.totp_device
            if existing.confirmed:
                return Response(
                    {"detail": "A confirmed MFA device already exists. Disable it first."},
                    status=status.HTTP_409_CONFLICT,
                )
            # Unconfirmed — regenerate the secret so a stale QR scan can't be used.
            existing.secret = pyotp.random_base32()
            existing.save(update_fields=["secret"])
            device = existing
        except UserTOTPDevice.DoesNotExist:
            device = UserTOTPDevice.objects.create(
                user=user,
                secret=pyotp.random_base32(),
                confirmed=False,
            )

        platform_name = getattr(settings, "PLATFORM_NAME", "Kepoli")
        account_name = user.email or user.username
        totp = pyotp.TOTP(device.secret)
        uri = totp.provisioning_uri(name=account_name, issuer_name=platform_name)

        # secret is returned for manual entry in authenticators that don't scan QR codes.
        # NOTE: never log `uri` or `secret` — they are credential material.
        return Response(
            {
                "provisioning_uri": uri,
                "secret": device.secret,  # base32, for manual entry
                "account_name": account_name,
                "issuer": platform_name,
            },
            status=status.HTTP_200_OK,
        )


class MFAConfirmView(APIView):
    """POST /api/mfa/confirm/

    Verify the first live TOTP code against the pending device.  On success:
      - Set confirmed=True + confirmed_at.
      - Generate N=10 backup codes, store their hashes, return plaintext ONCE.

    Body: {code: "123456"}
    Response: {backup_codes: ["xxxx-xxxx-xxxx-xxxx", ...]}

    Throttled: 10/hour per IP (mfa_confirm scope).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [MFAConfirmThrottle]

    def post(self, request):
        user = request.user
        if not _is_enrollment_role(user):
            return Response(
                {"detail": "MFA enrollment is restricted to platform admins and tenant owners."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            device = user.totp_device
        except UserTOTPDevice.DoesNotExist:
            return Response(
                {"detail": "No pending MFA setup found. Call /api/mfa/setup/ first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if device.confirmed:
            return Response(
                {"detail": "MFA is already confirmed."},
                status=status.HTTP_409_CONFLICT,
            )

        code = (request.data.get("code") or "").strip()
        if not code:
            return Response({"detail": "code is required."}, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(device.secret)
        if not totp.verify(code, valid_window=1):
            return Response(
                {"detail": "Invalid or expired TOTP code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plaintext_codes, hashed_codes = _generate_backup_codes()
        device.confirmed = True
        device.confirmed_at = timezone.now()
        device.backup_codes = hashed_codes
        device.save(update_fields=["confirmed", "confirmed_at", "backup_codes"])

        logger.info("MFA confirmed for user %s", user.pk)

        return Response(
            {
                "detail": "MFA confirmed. Save these backup codes — they will not be shown again.",
                "backup_codes": plaintext_codes,
            },
            status=status.HTTP_200_OK,
        )


class MFAVerifyView(APIView):
    """POST /api/mfa/verify/

    Second-factor step of the login flow.  Called ONLY when LoginView returned 202.

    The caller sends EITHER a TOTP code or a backup code:
      {code: "123456"}       — 6-digit TOTP
      {backup_code: "xxxx-xxxx-xxxx-xxxx"}   — single-use backup code

    On success:
      - Calls login(request, user) — session is now fully authenticated.
      - Clears the pending key from the session.
      - Returns the same user session payload as LoginView (200).

    On failure:
      - Increments the per-account mfa_fail counter (same semantics as login_fail).
      - Returns 401.

    Security:
      - The pending session key carries a timestamp; stale (> 10 min) pending sessions
        are rejected even with a valid code.
      - The user object is fetched fresh from the DB on every call; a forged session key
        with a non-existent PK is rejected.
    """

    permission_classes = [AllowAny]
    throttle_classes = [MFAVerifyBurstThrottle, MFAVerifySustainedThrottle]

    def post(self, request):
        pending_pk = request.session.get("_mfa_pending_user_id")
        pending_ts = request.session.get("_mfa_pending_ts")

        if not pending_pk:
            return Response(
                {"detail": "No pending MFA challenge. Please log in first."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Guard against stale / malformed pending sessions. A challenge with NO
        # timestamp is treated as expired (fail closed) rather than silently allowed.
        if not pending_ts or (timezone.now().timestamp() - pending_ts) > MFA_PENDING_TTL_SECONDS:
            request.session.pop("_mfa_pending_user_id", None)
            request.session.pop("_mfa_pending_ts", None)
            return Response(
                {"detail": "MFA challenge expired. Please log in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Fetch user fresh — a forged PK must not authenticate.
        try:
            user = User.objects.get(pk=pending_pk)
        except User.DoesNotExist:
            request.session.pop("_mfa_pending_user_id", None)
            request.session.pop("_mfa_pending_ts", None)
            return Response(
                {"detail": "Invalid session. Please log in again."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Per-account lockout check (mirrors LoginSerializer).
        if _check_mfa_lockout(user.pk):
            return Response(
                {"detail": "Too many failed MFA attempts. Please try again in a few minutes."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        code = (request.data.get("code") or "").strip()
        backup_code = (request.data.get("backup_code") or "").strip()

        if not code and not backup_code:
            return Response(
                {"detail": "Provide either 'code' (TOTP) or 'backup_code'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        verified = False

        if code:
            try:
                device = user.totp_device
                if device.confirmed:
                    # Replay-within-window guard (RFC 6238 §5.2): reject a TOTP
                    # code that was already accepted within the current 90-second
                    # window, even though pyotp would still accept it.
                    if _is_totp_replay(user.pk, code):
                        # Treat replay exactly like a wrong code — don't reveal why.
                        pass
                    else:
                        totp = pyotp.TOTP(device.secret)
                        verified = totp.verify(code, valid_window=1)
                        if verified:
                            _record_totp_used(user.pk, code)
            except UserTOTPDevice.DoesNotExist:
                pass

        if not verified and backup_code:
            try:
                device = user.totp_device
                if device.confirmed:
                    # verify_backup_code is atomic: removes the hash on success.
                    verified = device.verify_backup_code(backup_code)
            except UserTOTPDevice.DoesNotExist:
                pass

        if not verified:
            _increment_mfa_failure(user.pk)
            return Response(
                {"detail": "Invalid MFA code."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Success: clear lockout, clear pending session keys, complete auth.
        _clear_mfa_lockout(user.pk)
        request.session.pop("_mfa_pending_user_id", None)
        request.session.pop("_mfa_pending_ts", None)

        login(request, user)

        return Response(
            {"detail": "Signed in", "user": serialize_user_session(user)},
            status=status.HTTP_200_OK,
        )


class MFADisableView(APIView):
    """POST /api/mfa/disable/

    Remove the TOTP device.  Requires EITHER:
      - {password: "..."} — current password (re-auth)
      - {code: "..."}     — a currently valid TOTP code

    Audit-logged.  Throttled at 10/hour per user.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [MFADisableThrottle]

    def post(self, request):
        user = request.user

        try:
            device = user.totp_device
        except UserTOTPDevice.DoesNotExist:
            return Response(
                {"detail": "No MFA device found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        password = (request.data.get("password") or "").strip()
        code = (request.data.get("code") or "").strip()

        if not password and not code:
            return Response(
                {"detail": "Provide 'password' or 'code' to confirm disable."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        authed = False
        if password:
            authed = user.check_password(password)
        if not authed and code and device.confirmed:
            totp = pyotp.TOTP(device.secret)
            authed = totp.verify(code, valid_window=1)

        if not authed:
            return Response(
                {"detail": "Re-authentication failed. Provide a valid current password or TOTP code."},
                status=status.HTTP_403_FORBIDDEN,
            )

        device.delete()

        # Audit log (best-effort; must not raise).
        try:
            from sales.models import AdminAuditLog
            log_admin_action(
                actor=user,
                action="mfa_device_disabled",
                target_repr=f"User#{user.pk}",
                detail={"user_id": user.pk, "username": user.username},
            )
        except Exception:
            pass

        logger.info("MFA device disabled for user %s", user.pk)

        return Response({"detail": "MFA device removed."}, status=status.HTTP_200_OK)
