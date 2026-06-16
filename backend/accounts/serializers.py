from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import serializers

from sales.models import ActivationToken

from .models import PasswordResetToken

User = get_user_model()

# ── Per-account login brute-force lockout ────────────────────────────────────
# Keyed on the user PK (not the submitted identifier) so rotating identifiers
# cannot avoid the cap and a non-existent identifier never creates a key.
#
# Window semantics: FIXED, anchored at the FIRST failure in a window.
#   - cache.add() sets the key + TTL only when the key does not yet exist
#     (no-op if it already exists), so the TTL is set exactly once per window
#     and counts down from the first bad attempt regardless of later attempts.
#   - cache.incr() is an atomic server-side increment on Django's Redis backend;
#     no read-modify-write race.
#
# These two properties fix both R7a findings:
#   1. Atomicity — concurrent wrong-password bursts cannot undercount.
#   2. Fixed window — a slow-drip attacker cannot extend the lock indefinitely
#      by resetting the TTL; the key expires 15 min after the window opened.
LOGIN_MAX_FAILURES = 10        # generous: operators mistype; trip after 10 wrong passwords
LOGIN_LOCK_SECONDS = 900       # 15-minute FIXED window from first failure


def _login_fail_cache_key(user_pk: int) -> str:
    """Cache key for the per-user failed login counter."""
    return f"login_fail:u{user_pk}"


def _check_password_strength(password: str, user=None) -> None:
    """Run AUTH_PASSWORD_VALIDATORS and convert Django ValidationError to DRF."""
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({"password": list(exc.messages)})


class ActivationSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        token = attrs.get("token")
        try:
            activation = ActivationToken.objects.select_related("user", "tenant").get(token=token)
        except ActivationToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token")
        if not activation.is_valid():
            raise serializers.ValidationError("Token expired or used")
        attrs["activation"] = activation
        # Run AUTH_PASSWORD_VALIDATORS now that we have the user object for
        # UserAttributeSimilarityValidator (checks against username/email).
        _check_password_strength(attrs["password"], user=activation.user)
        return attrs

    def save(self, **kwargs):
        activation: ActivationToken = self.validated_data["activation"]
        password = self.validated_data["password"]
        user: User = activation.user
        user.set_password(password)
        user.is_active = True
        user.save()
        activation.mark_used()
        return user


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.core.cache import cache

        identifier = attrs.get("identifier", "").strip()
        password = attrs.get("password", "")

        if not identifier or not password:
            raise serializers.ValidationError("Username/email and password are required")

        # Step 1: resolve the candidate user from the identifier.
        user = (
            User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier))
            .order_by("id")
            .first()
        )

        # Step 2: if a user was found, check the lockout BEFORE check_password.
        # A locked account is rejected even with the correct password (the TTL
        # governs the window; we do NOT increment here — the existing count governs).
        if user is not None:
            fail_key = _login_fail_cache_key(user.pk)
            try:
                fail_count = cache.get(fail_key) or 0
            except Exception:
                # Cache unavailable — fail OPEN so a Redis blip can't lock everyone out.
                fail_count = 0
            if fail_count >= LOGIN_MAX_FAILURES:
                raise serializers.ValidationError(
                    "Too many failed attempts. Please try again in a few minutes."
                )

        # Step 3: validate credentials; on failure increment the per-user counter.
        if user is None or not user.check_password(password):
            if user is not None:
                fail_key = _login_fail_cache_key(user.pk)
                try:
                    # Atomic fixed-window increment (R7a fix):
                    #   cache.add  — sets key to 0 with full TTL only on first call
                    #               in the window; no-op on subsequent calls, so the
                    #               TTL is anchored at the first failure (fixed window).
                    #   cache.incr — atomic server-side increment; no race condition.
                    cache.add(fail_key, 0, LOGIN_LOCK_SECONDS)
                    cache.incr(fail_key)
                except Exception:
                    pass  # best-effort; a cache error must not 500 the login endpoint
            raise serializers.ValidationError("Invalid credentials")

        # Step 4: post-auth checks; on success clear the counter.
        if not user.is_active:
            raise serializers.ValidationError("Account is inactive")
        if getattr(user, "tenant_id", None) and not getattr(getattr(user, "tenant", None), "is_active", True):
            lifecycle = getattr(getattr(user, "tenant", None), "lifecycle_status", "suspended")
            raise serializers.ValidationError(f"Tenant is {lifecycle}. Contact support.")

        try:
            cache.delete(_login_fail_cache_key(user.pk))
        except Exception:
            pass  # best-effort; clearing the counter is not critical

        attrs["user"] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField()

    def validate(self, attrs):
        identifier = attrs.get("identifier", "").strip()
        if not identifier:
            raise serializers.ValidationError("Username or email is required")
        attrs["identifier"] = identifier
        attrs["user"] = (
            User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier), is_active=True)
            .order_by("id")
            .first()
        )
        return attrs

    def save(self, **kwargs):
        user = self.validated_data.get("user")
        if user is None or not user.email:
            return None
        return PasswordResetToken.issue(user=user, hours_valid=2)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, attrs):
        token = attrs.get("token", "").strip()
        try:
            reset = PasswordResetToken.objects.select_related("user").get(token=token)
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token")
        if not reset.is_valid():
            raise serializers.ValidationError("Token expired or used")
        attrs["reset"] = reset
        # Run AUTH_PASSWORD_VALIDATORS with the user so similarity checks work.
        _check_password_strength(attrs["password"], user=reset.user)
        return attrs

    def save(self, **kwargs):
        reset: PasswordResetToken = self.validated_data["reset"]
        password = self.validated_data["password"]
        user = reset.user
        user.set_password(password)
        user.save(update_fields=["password"])
        reset.mark_used()
        # OPS-5f: invalidate the user's OTHER sessions on reset so a stolen/active
        # session dies the moment the password is reset (account-recovery hardening).
        # set_password rotates the password hash; Django's SessionAuthenticationMiddleware
        # already invalidates sessions whose stored auth-hash no longer matches — but we
        # ALSO delete the user's persisted sessions outright so nothing lingers in the
        # store (defence in depth; covers backends that don't re-check on every request).
        _invalidate_user_sessions(user)
        return user


def _invalidate_user_sessions(user) -> None:
    """Delete every active Django session that belongs to ``user``.

    Best-effort: a failure here must never block the password reset itself."""
    try:
        from django.contrib.sessions.models import Session
        from django.utils import timezone

        uid = str(user.pk)
        stale = []
        for session in Session.objects.filter(expire_date__gte=timezone.now()):
            try:
                if session.get_decoded().get("_auth_user_id") == uid:
                    stale.append(session.session_key)
            except Exception:
                continue
        if stale:
            Session.objects.filter(session_key__in=stale).delete()
    except Exception:
        pass
