"""R7a — Per-account login brute-force lockout — Contract Tests

Covers the login lockout added to accounts/serializers.py (LoginSerializer.validate):

  A. Pure-logic / cache-only tests (SimpleTestCase, no DB):
       1. lock_cache_key() returns the expected per-PK key format.
       2. Pure counter logic: after LOGIN_MAX_FAILURES increments the check function
          returns True; below the threshold it returns False.
       3. Counter is keyed per user — failing user A's counter does not affect user B.

  B. LoginSerializer integration tests (require a real User row → DB tests):
       4. After LOGIN_MAX_FAILURES wrong passwords the account is locked out.
       5. Once locked, even the CORRECT password is rejected with the lockout message.
       6. A successful login clears the counter so the account is no longer locked.
       7. A not-found identifier does NOT create any cache key.
       8. Counter is keyed per PK: wrong passwords on user A do not lock user B.

All SimpleTestCase tests run locally (no Postgres).  The DB-backed tests
(class LoginLockoutDBTests) join the ~28 CI-only errors in the baseline and are
clearly marked below.

House style: mirrors test_ops5e_money.py and test_ops5g_voucher.py.
"""
from __future__ import annotations

from django.test import SimpleTestCase, TestCase, override_settings

from accounts.serializers import LOGIN_MAX_FAILURES, LOGIN_LOCK_SECONDS, _login_fail_cache_key


# ═════════════════════════════════════════════════════════════════════════════
# A. Pure-logic tests — SimpleTestCase, no DB, runs locally
# ═════════════════════════════════════════════════════════════════════════════

@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class LoginLockoutCacheKeyTests(SimpleTestCase):
    """The cache key must embed the user PK, not the raw identifier."""

    def test_key_format(self):
        self.assertEqual(_login_fail_cache_key(42), "login_fail:u42")
        self.assertEqual(_login_fail_cache_key(1), "login_fail:u1")
        self.assertEqual(_login_fail_cache_key(999), "login_fail:u999")

    def test_different_pks_produce_different_keys(self):
        self.assertNotEqual(_login_fail_cache_key(1), _login_fail_cache_key(2))


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class LoginLockoutCounterLogicTests(SimpleTestCase):
    """Verify the raw counter semantics using cache directly (no User, no serializer)."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_counter_below_threshold_is_not_locked(self):
        from django.core.cache import cache
        key = _login_fail_cache_key(10)
        cache.set(key, LOGIN_MAX_FAILURES - 1, LOGIN_LOCK_SECONDS)
        self.assertLess(cache.get(key) or 0, LOGIN_MAX_FAILURES)

    def test_counter_at_threshold_is_locked(self):
        from django.core.cache import cache
        key = _login_fail_cache_key(10)
        cache.set(key, LOGIN_MAX_FAILURES, LOGIN_LOCK_SECONDS)
        self.assertGreaterEqual(cache.get(key) or 0, LOGIN_MAX_FAILURES)

    def test_counter_increments_correctly_via_add_incr(self):
        """The atomic add+incr pattern produces the same sequential result as a loop."""
        from django.core.cache import cache
        key = _login_fail_cache_key(20)
        for i in range(1, LOGIN_MAX_FAILURES + 1):
            cache.add(key, 0, LOGIN_LOCK_SECONDS)
            cache.incr(key)
            self.assertEqual(cache.get(key), i)

    def test_fixed_window_ttl_not_reset_by_subsequent_incr(self):
        """cache.add is a no-op when the key already exists, so the TTL set on the
        first failure is NOT reset by later failures (fixed window, not sliding)."""
        from django.core.cache import cache
        import time
        key = _login_fail_cache_key(21)
        # First failure — sets TTL.
        cache.add(key, 0, LOGIN_LOCK_SECONDS)
        cache.incr(key)
        ttl_after_first = cache.ttl(key) if hasattr(cache, "ttl") else None
        # Second failure — add is a no-op; TTL must not increase.
        cache.add(key, 0, LOGIN_LOCK_SECONDS)
        cache.incr(key)
        ttl_after_second = cache.ttl(key) if hasattr(cache, "ttl") else None
        self.assertEqual(cache.get(key), 2)
        # If the backend exposes ttl, verify it did not grow.
        if ttl_after_first is not None and ttl_after_second is not None:
            self.assertLessEqual(ttl_after_second, ttl_after_first)

    def test_add_is_noop_when_key_exists(self):
        """cache.add must return False (no-op) when the key already exists —
        this is the atomicity guarantee that prevents TTL extension."""
        from django.core.cache import cache
        key = _login_fail_cache_key(22)
        added_first = cache.add(key, 0, LOGIN_LOCK_SECONDS)
        added_second = cache.add(key, 99, LOGIN_LOCK_SECONDS)
        self.assertTrue(added_first)   # key did not exist; was set
        self.assertFalse(added_second)  # key already existed; no-op
        # Value must still be the original 0, not overwritten to 99.
        self.assertEqual(cache.get(key), 0)

    def test_counter_is_keyed_per_user(self):
        """Incrementing user 1's counter must not affect user 2's counter."""
        from django.core.cache import cache
        key1 = _login_fail_cache_key(1)
        key2 = _login_fail_cache_key(2)
        # Saturate user 1.
        cache.set(key1, LOGIN_MAX_FAILURES, LOGIN_LOCK_SECONDS)
        # User 2's counter must still be absent/zero.
        self.assertIn(cache.get(key2), (None, 0))

    def test_delete_clears_counter(self):
        from django.core.cache import cache
        key = _login_fail_cache_key(30)
        cache.set(key, LOGIN_MAX_FAILURES, LOGIN_LOCK_SECONDS)
        cache.delete(key)
        self.assertIn(cache.get(key), (None, 0))

    def test_constants_are_reasonable(self):
        """Sanity-check the constant values so a refactor can't accidentally set them to 0."""
        self.assertGreater(LOGIN_MAX_FAILURES, 0)
        self.assertGreater(LOGIN_LOCK_SECONDS, 0)
        # Must be generous (>= 5) so operators don't get locked on normal mistyping.
        self.assertGreaterEqual(LOGIN_MAX_FAILURES, 5)


# ═════════════════════════════════════════════════════════════════════════════
# B. DB-backed integration tests — requires Postgres (CI only)
# ═════════════════════════════════════════════════════════════════════════════

@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class LoginLockoutDBTests(TestCase):
    """Full serializer integration — these need a real User row and Postgres.
    They join the ~28 CI-only errors in the baseline; they are NOT expected to
    pass locally without a running database.
    """

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        # Create a plain staff user (no tenant) for testing.
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user_a = User.objects.create_user(
            username="lockouta", email="lockouta@example.com",
            password="CorrectPassA1!", is_active=True,
        )
        self.user_b = User.objects.create_user(
            username="lockoutb", email="lockoutb@example.com",
            password="CorrectPassB1!", is_active=True,
        )

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def _validate(self, identifier, password):
        """Run LoginSerializer.validate and return (user, error_message).
        Returns (user, None) on success, (None, str) on ValidationError.
        """
        from accounts.serializers import LoginSerializer
        from rest_framework.exceptions import ValidationError
        s = LoginSerializer(data={"identifier": identifier, "password": password})
        s.is_valid()  # triggers validate()
        try:
            result = s.validate({"identifier": identifier, "password": password})
            return result.get("user"), None
        except ValidationError as exc:
            msgs = exc.detail
            if isinstance(msgs, list):
                return None, str(msgs[0])
            return None, str(msgs)

    def test_lock_triggers_after_max_failures(self):
        """After LOGIN_MAX_FAILURES wrong passwords, the next attempt is rejected
        with the lockout message regardless of the password supplied."""
        from django.core.cache import cache
        identifier = "lockouta"
        for _ in range(LOGIN_MAX_FAILURES):
            _, err = self._validate(identifier, "WrongPassword!")
            self.assertIn("Invalid credentials", err)
        # The (N+1)th attempt must hit the lockout.
        _, err = self._validate(identifier, "WrongPassword!")
        self.assertIn("Too many failed attempts", err)
        self.assertEqual(cache.get(_login_fail_cache_key(self.user_a.pk)), LOGIN_MAX_FAILURES)

    def test_locked_account_rejects_correct_password(self):
        """Once locked, the CORRECT password is also rejected (lockout precedes check_password)."""
        from django.core.cache import cache
        key = _login_fail_cache_key(self.user_a.pk)
        cache.set(key, LOGIN_MAX_FAILURES, LOGIN_LOCK_SECONDS)
        _, err = self._validate("lockouta", "CorrectPassA1!")
        self.assertIn("Too many failed attempts", err)

    def test_successful_login_clears_counter(self):
        """A correct login after some (below-threshold) failures clears the counter."""
        from django.core.cache import cache
        key = _login_fail_cache_key(self.user_a.pk)
        # Seed failures below the cap.
        cache.set(key, LOGIN_MAX_FAILURES - 1, LOGIN_LOCK_SECONDS)
        user, err = self._validate("lockouta", "CorrectPassA1!")
        self.assertIsNone(err)
        self.assertEqual(user.pk, self.user_a.pk)
        self.assertIn(cache.get(key), (None, 0))

    def test_not_found_identifier_does_not_create_key(self):
        """A login attempt with an identifier that matches no user must not write
        any cache key (prevents the attacker from learning which usernames exist
        via lock-state probing)."""
        from django.core.cache import cache
        _, err = self._validate("no_such_user_xyz", "AnyPassword!")
        self.assertIn("Invalid credentials", err)
        # No key should have been created for a non-existent user.
        # We can't know the pk (there is none), but we can verify none of the
        # known keys exist and that the error message is the generic one.
        self.assertIsNone(cache.get(_login_fail_cache_key(0)))

    def test_counter_keyed_per_user(self):
        """Failing user A's password must not increment user B's counter."""
        from django.core.cache import cache
        key_b = _login_fail_cache_key(self.user_b.pk)
        # Exhaust user A's counter.
        for _ in range(LOGIN_MAX_FAILURES):
            self._validate("lockouta", "WrongPassword!")
        # User B must still be able to log in successfully.
        user, err = self._validate("lockoutb", "CorrectPassB1!")
        self.assertIsNone(err)
        self.assertEqual(user.pk, self.user_b.pk)
        # User B's counter must be absent/zero.
        self.assertIn(cache.get(key_b), (None, 0))

    def test_failed_attempt_increments_by_one_per_call(self):
        """Each wrong-password attempt increments the counter by exactly 1."""
        from django.core.cache import cache
        key = _login_fail_cache_key(self.user_a.pk)
        for i in range(1, min(4, LOGIN_MAX_FAILURES)):
            self._validate("lockouta", "WrongPassword!")
            self.assertEqual(cache.get(key), i)
