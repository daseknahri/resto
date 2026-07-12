"""RISK OPS-3: schema-pinned session backend (mock-based, no DB).

``accounts.session_backends.SessionStore`` subclasses Django's stock ``cached_db``
session store and re-points every method that actually touches ``django_session`` at
the ``public`` schema. That table lives only in the public schema (``django.contrib
.sessions`` is in SHARED_APPS), but django-tenants otherwise leaves the connection
pointed at whichever tenant schema is active for the rest of the request — a naive
``cached_db`` swap would 500 (or silently drop sessions) on every authenticated request.

This backend is NOT activated (``SESSION_ENGINE`` in config/settings.py is unchanged).
These tests only verify the dormant component in isolation:

  * it subclasses the right Django store,
  * it overrides *exactly* the methods that need their own wrap — ``load()`` and
    ``create()`` are deliberately left un-overridden because both reach the database
    only via ``self.<one of the overridden methods>(...)``, which ordinary Python
    dynamic dispatch already resolves against this subclass (see the module docstring
    in accounts/session_backends.py for the full call-graph trace),
  * each overridden method opens ``schema_context("public")`` before delegating to the
    parent (DB-touching) implementation, and closes it after.

Everything here is mocked (schema_context, and the parent class's own methods) — no
real ORM/SQL ever runs, so this is a plain SimpleTestCase with no DB dependency.
"""
from unittest import mock

import django
from django.contrib.sessions.backends.cached_db import SessionStore as CachedDBSessionStore
from django.contrib.sessions.backends.db import SessionStore as DBSessionStore
from django.test import SimpleTestCase

from accounts import session_backends


class DjangoVersionPinTests(SimpleTestCase):
    """The override set below (which methods need their own schema_context wrap) was
    derived by reading db.py/cached_db.py for Django 4.2 specifically. Upgrading Django
    means re-reading those two files before trusting the rest of this file — pin the
    version here so an upgrade fails this test loudly instead of silently drifting."""

    def test_pinned_against_django_4_2(self):
        self.assertEqual(django.VERSION[:2], (4, 2))


class SessionStoreResolutionTests(SimpleTestCase):
    """Class-shape checks: right parent, right override set."""

    def test_subclasses_cached_db_store(self):
        self.assertTrue(issubclass(session_backends.SessionStore, CachedDBSessionStore))

    def test_overrides_exactly_the_db_touching_methods_that_need_it(self):
        # load() and create() are intentionally absent: both only ever reach the
        # database through one of these 5, via self.<method>(...) dynamic dispatch,
        # so they already run pinned for free. Asserting the set is exactly these 5
        # catches both a missing override (a live 500 risk) and a redundant one
        # (dead weight / a sign the call-graph assumption above needs re-checking).
        expected = {"_get_session_from_db", "exists", "save", "delete", "clear_expired"}
        own_attrs = {
            name for name in vars(session_backends.SessionStore) if not name.startswith("__")
        }
        self.assertEqual(own_attrs, expected)

    def test_load_and_create_are_inherited_unmodified(self):
        self.assertNotIn("load", vars(session_backends.SessionStore))
        self.assertNotIn("create", vars(session_backends.SessionStore))
        self.assertIs(session_backends.SessionStore.load, CachedDBSessionStore.load)
        self.assertIs(session_backends.SessionStore.create, DBSessionStore.create)

    def test_clear_expired_is_a_classmethod(self):
        self.assertIsInstance(
            session_backends.SessionStore.__dict__["clear_expired"], classmethod
        )


class InstanceMethodSchemaPinningTests(SimpleTestCase):
    """Each overridden instance method must run its parent's (DB-touching) call
    strictly inside schema_context("public"): entered before, exited after."""

    def _new_store(self):
        # __new__ bypasses __init__ (which resolves a real Redis cache backend via
        # settings.SESSION_CACHE_ALIAS) — none of the methods under test touch
        # self._cache directly; they only delegate to the (mocked) parent class.
        return session_backends.SessionStore.__new__(session_backends.SessionStore)

    def test_get_session_from_db_pinned_to_public(self):
        manager = mock.Mock()
        with mock.patch("accounts.session_backends.schema_context") as ctx, \
                mock.patch.object(
                    CachedDBSessionStore, "_get_session_from_db", return_value="row"
                ) as parent:
            manager.attach_mock(ctx, "ctx")
            manager.attach_mock(parent, "parent")

            result = self._new_store()._get_session_from_db()

        self.assertEqual(result, "row")
        self.assertEqual(
            manager.mock_calls,
            [
                mock.call.ctx("public"),
                mock.call.ctx().__enter__(),
                mock.call.parent(),
                mock.call.ctx().__exit__(None, None, None),
            ],
        )

    def test_exists_pinned_to_public(self):
        manager = mock.Mock()
        with mock.patch("accounts.session_backends.schema_context") as ctx, \
                mock.patch.object(
                    CachedDBSessionStore, "exists", return_value=True
                ) as parent:
            manager.attach_mock(ctx, "ctx")
            manager.attach_mock(parent, "parent")

            result = self._new_store().exists("some-session-key")

        self.assertTrue(result)
        self.assertEqual(
            manager.mock_calls,
            [
                mock.call.ctx("public"),
                mock.call.ctx().__enter__(),
                mock.call.parent("some-session-key"),
                mock.call.ctx().__exit__(None, None, None),
            ],
        )

    def test_save_pinned_to_public(self):
        manager = mock.Mock()
        with mock.patch("accounts.session_backends.schema_context") as ctx, \
                mock.patch.object(
                    CachedDBSessionStore, "save", return_value=None
                ) as parent:
            manager.attach_mock(ctx, "ctx")
            manager.attach_mock(parent, "parent")

            self._new_store().save(must_create=True)

        self.assertEqual(
            manager.mock_calls,
            [
                mock.call.ctx("public"),
                mock.call.ctx().__enter__(),
                mock.call.parent(True),
                mock.call.ctx().__exit__(None, None, None),
            ],
        )

    def test_delete_pinned_to_public(self):
        manager = mock.Mock()
        with mock.patch("accounts.session_backends.schema_context") as ctx, \
                mock.patch.object(
                    CachedDBSessionStore, "delete", return_value=None
                ) as parent:
            manager.attach_mock(ctx, "ctx")
            manager.attach_mock(parent, "parent")

            self._new_store().delete("some-session-key")

        self.assertEqual(
            manager.mock_calls,
            [
                mock.call.ctx("public"),
                mock.call.ctx().__enter__(),
                mock.call.parent("some-session-key"),
                mock.call.ctx().__exit__(None, None, None),
            ],
        )


class ClearExpiredSchemaPinningTests(SimpleTestCase):
    """clear_expired is a classmethod invoked directly by the `clearsessions`
    management command — the one method with no instance-method path to inherit
    coverage from, so it needs its own wrap."""

    def test_clear_expired_pinned_to_public(self):
        manager = mock.Mock()
        with mock.patch("accounts.session_backends.schema_context") as ctx, \
                mock.patch.object(DBSessionStore, "clear_expired") as parent:
            manager.attach_mock(ctx, "ctx")
            manager.attach_mock(parent, "parent")

            session_backends.SessionStore.clear_expired()

        self.assertEqual(
            manager.mock_calls,
            [
                mock.call.ctx("public"),
                mock.call.ctx().__enter__(),
                mock.call.parent(),
                mock.call.ctx().__exit__(None, None, None),
            ],
        )
