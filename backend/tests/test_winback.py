"""
Tests for win-back automation.

Tests:
  1. Inactivity boundary — exactly N weeks vs N weeks - 1 day
  2. opt-out (notify_promotions=False) excluded
  3. No push subscription excluded
  4. 90-day dedupe blocks resend
  5. Cap 50 enforced
  6. winback_enabled=False skips tenant
  7. Wrong local hour skips
  8. Daily cache marker prevents double-send (audience still built; sends skipped)
  9. Blank message falls back to default containing tenant name
 10. Weeks validation 1–52 (serializer)
 11. Settings serializer round-trips the 3 winback_* fields
 12. _record_nudge called BEFORE _send_nudge (spam-safety ordering)
 13. Suppressed send (returns 0) reclaims the WinbackNudge row

House style: SimpleTestCase + MagicMock, no local DB.
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone as _tz
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.test import SimpleTestCase


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_profile(
    *,
    winback_enabled: bool = True,
    winback_inactive_weeks: int = 4,
    winback_message: str = "",
    timezone: str = "UTC",
):
    p = MagicMock()
    p.winback_enabled = winback_enabled
    p.winback_inactive_weeks = winback_inactive_weeks
    p.winback_message = winback_message
    p.timezone = timezone
    return p


def _make_tenant(*, tid: int = 1, slug: str = "test", name: str = "Test Restaurant"):
    t = MagicMock()
    t.id = tid
    t.slug = slug
    t.name = name
    t.schema_name = f"tenant_{slug}"
    t.profile = _make_profile()
    return t


def _make_command():
    from menu.management.commands.send_winback_nudges import Command
    cmd = Command()
    cmd.stdout = io.StringIO()
    cmd.style = MagicMock()
    cmd.style.MIGRATE_HEADING.side_effect = lambda x: x
    cmd.style.SUCCESS.side_effect = lambda x: x
    return cmd


# ─────────────────────────────────────────────────────────────────────────────
# 1. Inactivity boundary
# ─────────────────────────────────────────────────────────────────────────────

class WinbackInactivityBoundaryTests(SimpleTestCase):
    """_build_audience excludes customers whose last order is within inactive_weeks."""

    def _run_build_audience(self, last_order_dt, inactive_weeks=4, cap=50):
        """
        Patch Order.objects to return a single customer (id=99) whose
        most-recent order was at last_order_dt, then run _build_audience.
        """
        from menu.management.commands.send_winback_nudges import _build_audience

        # Mock Order queryset: values() → annotate() → filter(last_order__lt=cutoff)
        row = {"customer_id": 99, "last_order": last_order_dt}

        # Build the mock chain for the Order query
        mock_order_qs = MagicMock()
        mock_order_qs.values.return_value.annotate.return_value.filter.return_value = [row]

        # Mock Customer (opted-in)
        mock_customer_qs = MagicMock()
        mock_customer_qs.filter.return_value.values_list.return_value = [99]

        # Mock CustomerPushSubscription (has a sub)
        mock_sub_qs = MagicMock()
        mock_sub_qs.filter.return_value.values_list.return_value.distinct.return_value = [99]

        patches = [
            patch("menu.management.commands.send_winback_nudges.schema_context"),
            patch("menu.models.Order.objects", mock_order_qs),
            patch("accounts.models.Customer.objects", mock_customer_qs),
            patch("accounts.models.CustomerPushSubscription.objects", mock_sub_qs),
            patch("menu.management.commands.send_winback_nudges._already_nudged", return_value=False),
        ]
        with patches[0] as mock_ctx, patches[1], patches[2], patches[3], patches[4]:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = _build_audience(tenant_id=1, inactive_weeks=inactive_weeks, cap=cap)
        return result

    def test_customer_last_order_exactly_4_weeks_ago_is_included(self):
        """A customer whose last order was exactly 4 weeks ago should be eligible."""
        # The filter uses `last_order__lt=cutoff` where cutoff = now - 4 weeks.
        # We set last_order to exactly cutoff - 1 second so it is strictly less than cutoff.
        cutoff = datetime.now(_tz.utc) - timedelta(weeks=4)
        last_order = cutoff - timedelta(seconds=1)
        result = self._run_build_audience(last_order, inactive_weeks=4)
        self.assertIn(99, result)

    def test_customer_last_order_less_than_4_weeks_excluded(self):
        """A customer whose last order was 4 weeks - 1 day ago is NOT eligible."""
        # last_order is 4 weeks - 1 day ago → more recent than cutoff → not in filter results.
        # We simulate this by returning an empty queryset.
        from menu.management.commands.send_winback_nudges import _build_audience

        mock_order_qs = MagicMock()
        # The filter returns nothing — customer's order is too recent.
        mock_order_qs.values.return_value.annotate.return_value.filter.return_value = []

        with patch("menu.models.Order.objects", mock_order_qs), \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = _build_audience(tenant_id=1, inactive_weeks=4, cap=50)
        self.assertEqual(result, [])


# ─────────────────────────────────────────────────────────────────────────────
# 2. opt-out excluded
# ─────────────────────────────────────────────────────────────────────────────

class WinbackOptOutTests(SimpleTestCase):
    def test_notify_promotions_false_excluded(self):
        """Customer with notify_promotions=False is filtered out by Customer query."""
        from menu.management.commands.send_winback_nudges import _build_audience

        cutoff = datetime.now(_tz.utc) - timedelta(weeks=4)
        last_order = cutoff - timedelta(days=1)
        row = {"customer_id": 99, "last_order": last_order}

        mock_order_qs = MagicMock()
        mock_order_qs.values.return_value.annotate.return_value.filter.return_value = [row]

        # Customer filtered to empty because notify_promotions=False
        mock_customer_qs = MagicMock()
        mock_customer_qs.filter.return_value.values_list.return_value = []

        with patch("menu.models.Order.objects", mock_order_qs), \
             patch("accounts.models.Customer.objects", mock_customer_qs), \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = _build_audience(tenant_id=1, inactive_weeks=4, cap=50)

        self.assertEqual(result, [])


# ─────────────────────────────────────────────────────────────────────────────
# 3. No push subscription excluded
# ─────────────────────────────────────────────────────────────────────────────

class WinbackNoPushSubTests(SimpleTestCase):
    def test_customer_without_push_sub_excluded(self):
        """Customer with no push subscription is excluded (no sub → not in subscribed set)."""
        from menu.management.commands.send_winback_nudges import _build_audience

        cutoff = datetime.now(_tz.utc) - timedelta(weeks=4)
        last_order = cutoff - timedelta(days=1)
        row = {"customer_id": 99, "last_order": last_order}

        mock_order_qs = MagicMock()
        mock_order_qs.values.return_value.annotate.return_value.filter.return_value = [row]

        mock_customer_qs = MagicMock()
        mock_customer_qs.filter.return_value.values_list.return_value = [99]

        # No push subscriptions
        mock_sub_qs = MagicMock()
        mock_sub_qs.filter.return_value.values_list.return_value.distinct.return_value = []

        with patch("menu.models.Order.objects", mock_order_qs), \
             patch("accounts.models.Customer.objects", mock_customer_qs), \
             patch("accounts.models.CustomerPushSubscription.objects", mock_sub_qs), \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = _build_audience(tenant_id=1, inactive_weeks=4, cap=50)

        self.assertEqual(result, [])


# ─────────────────────────────────────────────────────────────────────────────
# 4. 90-day dedupe blocks resend
# ─────────────────────────────────────────────────────────────────────────────

class WinbackDedupeTests(SimpleTestCase):
    def test_already_nudged_within_90_days_excluded(self):
        """Customer nudged within 90 days is excluded by _already_nudged."""
        from menu.management.commands.send_winback_nudges import _build_audience

        cutoff = datetime.now(_tz.utc) - timedelta(weeks=4)
        last_order = cutoff - timedelta(days=1)
        row = {"customer_id": 99, "last_order": last_order}

        mock_order_qs = MagicMock()
        mock_order_qs.values.return_value.annotate.return_value.filter.return_value = [row]

        mock_customer_qs = MagicMock()
        mock_customer_qs.filter.return_value.values_list.return_value = [99]

        mock_sub_qs = MagicMock()
        mock_sub_qs.filter.return_value.values_list.return_value.distinct.return_value = [99]

        with patch("menu.models.Order.objects", mock_order_qs), \
             patch("accounts.models.Customer.objects", mock_customer_qs), \
             patch("accounts.models.CustomerPushSubscription.objects", mock_sub_qs), \
             patch("menu.management.commands.send_winback_nudges._already_nudged", return_value=True), \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = _build_audience(tenant_id=1, inactive_weeks=4, cap=50)

        self.assertEqual(result, [])

    def test_not_nudged_within_90_days_included(self):
        """Customer not nudged within 90 days is included."""
        from menu.management.commands.send_winback_nudges import _build_audience

        cutoff = datetime.now(_tz.utc) - timedelta(weeks=4)
        last_order = cutoff - timedelta(days=1)
        row = {"customer_id": 99, "last_order": last_order}

        mock_order_qs = MagicMock()
        mock_order_qs.values.return_value.annotate.return_value.filter.return_value = [row]

        mock_customer_qs = MagicMock()
        mock_customer_qs.filter.return_value.values_list.return_value = [99]

        mock_sub_qs = MagicMock()
        mock_sub_qs.filter.return_value.values_list.return_value.distinct.return_value = [99]

        with patch("menu.models.Order.objects", mock_order_qs), \
             patch("accounts.models.Customer.objects", mock_customer_qs), \
             patch("accounts.models.CustomerPushSubscription.objects", mock_sub_qs), \
             patch("menu.management.commands.send_winback_nudges._already_nudged", return_value=False), \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = _build_audience(tenant_id=1, inactive_weeks=4, cap=50)

        self.assertIn(99, result)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Cap 50 enforced
# ─────────────────────────────────────────────────────────────────────────────

class WinbackCapTests(SimpleTestCase):
    def test_cap_limits_audience(self):
        """_build_audience returns at most `cap` customer_ids."""
        from menu.management.commands.send_winback_nudges import _build_audience

        cutoff = datetime.now(_tz.utc) - timedelta(weeks=4)
        last_order = cutoff - timedelta(days=1)
        # 100 customers
        all_rows = [{"customer_id": i, "last_order": last_order} for i in range(1, 101)]
        all_ids = list(range(1, 101))

        mock_order_qs = MagicMock()
        mock_order_qs.values.return_value.annotate.return_value.filter.return_value = all_rows

        mock_customer_qs = MagicMock()
        mock_customer_qs.filter.return_value.values_list.return_value = all_ids

        mock_sub_qs = MagicMock()
        mock_sub_qs.filter.return_value.values_list.return_value.distinct.return_value = all_ids

        with patch("menu.models.Order.objects", mock_order_qs), \
             patch("accounts.models.Customer.objects", mock_customer_qs), \
             patch("accounts.models.CustomerPushSubscription.objects", mock_sub_qs), \
             patch("menu.management.commands.send_winback_nudges._already_nudged", return_value=False), \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx:
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            result = _build_audience(tenant_id=1, inactive_weeks=4, cap=50)

        self.assertLessEqual(len(result), 50)


# ─────────────────────────────────────────────────────────────────────────────
# 6. winback_enabled=False skips tenant
# ─────────────────────────────────────────────────────────────────────────────

class WinbackDisabledFlagTests(SimpleTestCase):
    def test_disabled_tenant_skipped(self):
        """Command skips tenants where profile.winback_enabled=False."""
        tenant = _make_tenant()
        tenant.profile.winback_enabled = False

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour") as mock_hour, \
             patch("menu.management.commands.send_winback_nudges._build_audience") as mock_audience:
            cmd.handle(dry_run=False)

        # _tenant_local_hour and _build_audience should not be called if flag is off
        mock_hour.assert_not_called()
        mock_audience.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 7. Wrong local hour skips
# ─────────────────────────────────────────────────────────────────────────────

class WinbackWrongHourTests(SimpleTestCase):
    def test_wrong_local_hour_skips(self):
        """Command skips tenants not at local hour 11."""
        tenant = _make_tenant()
        tenant.profile.winback_enabled = True

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(9, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges._build_audience") as mock_audience:
            cmd.handle(dry_run=False)

        mock_audience.assert_not_called()

    def test_correct_local_hour_proceeds(self):
        """Command proceeds for tenants at local hour 11."""
        tenant = _make_tenant()
        tenant.profile.winback_enabled = True

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(11, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges.cache") as mock_cache, \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("menu.management.commands.send_winback_nudges._build_audience", return_value=[]) as mock_audience:
            mock_cache.add.return_value = True
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            cmd.handle(dry_run=False)

        mock_audience.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# 8. Daily cache marker prevents double-send
# ─────────────────────────────────────────────────────────────────────────────

class WinbackCacheMarkerTests(SimpleTestCase):
    def test_cache_marker_prevents_double_send(self):
        """If cache.add returns False after audience build, sends are skipped.

        The cache check is now AFTER audience build (so _build_audience IS
        called), but _send_nudge and _record_nudge must NOT be called.
        """
        tenant = _make_tenant()
        tenant.profile.winback_enabled = True

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(11, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges.cache") as mock_cache, \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("menu.management.commands.send_winback_nudges._build_audience", return_value=[42]) as mock_audience, \
             patch("menu.management.commands.send_winback_nudges._record_nudge") as mock_record, \
             patch("menu.management.commands.send_winback_nudges._send_nudge") as mock_send:
            # cache.add returns False → already ran today
            mock_cache.add.return_value = False
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            cmd.handle(dry_run=False)

        # Audience is still built (cache check is after audience build now)
        mock_audience.assert_called_once()
        # But no sends or records happen
        mock_record.assert_not_called()
        mock_send.assert_not_called()

    def test_fresh_cache_marker_allows_run(self):
        """If cache.add returns True (new key), the tenant run proceeds."""
        tenant = _make_tenant()
        tenant.profile.winback_enabled = True

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(11, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges.cache") as mock_cache, \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("menu.management.commands.send_winback_nudges._build_audience", return_value=[]) as mock_audience:
            mock_cache.add.return_value = True
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            cmd.handle(dry_run=False)

        mock_audience.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# 9. Blank message falls back to default containing tenant name
# ─────────────────────────────────────────────────────────────────────────────

class WinbackDefaultMessageTests(SimpleTestCase):
    def test_blank_message_uses_default_with_tenant_name(self):
        """When winback_message is blank, push body contains the tenant name."""
        tenant = _make_tenant(name="Mama's Kitchen")
        tenant.profile.winback_enabled = True
        tenant.profile.winback_message = ""  # blank

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        pushed_bodies = []

        def capture_send(cid, tenant_name, slug, url, title, body):
            pushed_bodies.append(body)
            return 1  # simulate successful send

        mock_nudge_qs = MagicMock()
        mock_nudge_qs.filter.return_value.order_by.return_value.__getitem__ = MagicMock(return_value=MagicMock())

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(11, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges.cache") as mock_cache, \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("menu.management.commands.send_winback_nudges._build_audience", return_value=[42]), \
             patch("menu.management.commands.send_winback_nudges._send_nudge", side_effect=capture_send), \
             patch("menu.management.commands.send_winback_nudges._record_nudge"):
            mock_cache.add.return_value = True
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            cmd.handle(dry_run=False)

        self.assertEqual(len(pushed_bodies), 1)
        self.assertIn("Mama's Kitchen", pushed_bodies[0])

    def test_custom_message_used_when_set(self):
        """When winback_message is set, it is used as the push body."""
        tenant = _make_tenant(name="Mama's Kitchen")
        tenant.profile.winback_enabled = True
        tenant.profile.winback_message = "We miss you! Come back for 10% off."

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        pushed_bodies = []

        def capture_send(cid, tenant_name, slug, url, title, body):
            pushed_bodies.append(body)
            return 1  # simulate successful send

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(11, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges.cache") as mock_cache, \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("menu.management.commands.send_winback_nudges._build_audience", return_value=[42]), \
             patch("menu.management.commands.send_winback_nudges._send_nudge", side_effect=capture_send), \
             patch("menu.management.commands.send_winback_nudges._record_nudge"):
            mock_cache.add.return_value = True
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            cmd.handle(dry_run=False)

        self.assertEqual(pushed_bodies[0], "We miss you! Come back for 10% off.")


# ─────────────────────────────────────────────────────────────────────────────
# 10. Weeks validation 1–52 (ProfileSerializer)
# ─────────────────────────────────────────────────────────────────────────────

class WinbackWeeksValidatorTests(SimpleTestCase):
    def _get_serializer(self, **data):
        from tenancy.serializers import ProfileSerializer
        return ProfileSerializer(data=data, partial=True)

    def test_valid_weeks_1(self):
        s = self._get_serializer(winback_inactive_weeks=1)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["winback_inactive_weeks"], 1)

    def test_valid_weeks_52(self):
        s = self._get_serializer(winback_inactive_weeks=52)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["winback_inactive_weeks"], 52)

    def test_invalid_weeks_0(self):
        s = self._get_serializer(winback_inactive_weeks=0)
        self.assertFalse(s.is_valid())
        self.assertIn("winback_inactive_weeks", s.errors)

    def test_invalid_weeks_53(self):
        s = self._get_serializer(winback_inactive_weeks=53)
        self.assertFalse(s.is_valid())
        self.assertIn("winback_inactive_weeks", s.errors)


# ─────────────────────────────────────────────────────────────────────────────
# 11. Settings serializer round-trips the 3 winback_* fields
# ─────────────────────────────────────────────────────────────────────────────

class WinbackSerializerRoundTripTests(SimpleTestCase):
    """ProfileSerializer exposes all 3 winback_* fields for read and write."""

    def test_winback_fields_in_serializer_fields(self):
        from tenancy.serializers import ProfileSerializer
        s = ProfileSerializer()
        field_names = list(s.fields.keys())
        self.assertIn("winback_enabled", field_names)
        self.assertIn("winback_inactive_weeks", field_names)
        self.assertIn("winback_message", field_names)

    def test_winback_fields_round_trip(self):
        """All 3 fields are accepted and returned correctly by partial serializer."""
        from tenancy.serializers import ProfileSerializer
        data = {
            "winback_enabled": True,
            "winback_inactive_weeks": 6,
            "winback_message": "We miss you!",
        }
        s = ProfileSerializer(data=data, partial=True)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data["winback_enabled"], True)
        self.assertEqual(s.validated_data["winback_inactive_weeks"], 6)
        self.assertEqual(s.validated_data["winback_message"], "We miss you!")

    def test_winback_enabled_default_false(self):
        """winback_enabled defaults to False in the model field."""
        from tenancy.models import Profile
        # Inspect the model field
        field = Profile._meta.get_field("winback_enabled")
        self.assertFalse(field.default)

    def test_winback_inactive_weeks_default_4(self):
        """winback_inactive_weeks defaults to 4."""
        from tenancy.models import Profile
        field = Profile._meta.get_field("winback_inactive_weeks")
        self.assertEqual(field.default, 4)


# ─────────────────────────────────────────────────────────────────────────────
# 12. _record_nudge called BEFORE _send_nudge (spam-safety ordering)
# ─────────────────────────────────────────────────────────────────────────────

class WinbackSendOrderingTests(SimpleTestCase):
    """Verify that the dedupe row is written BEFORE the push is delivered.

    If the DB write succeeds but the push delivery crashes (or the process
    is killed), the WinbackNudge row already exists and prevents a re-send
    on the next run.  A missed nudge is far preferable to a double nudge.
    """

    def test_record_nudge_called_before_send_nudge(self):
        """_record_nudge must be invoked before _send_nudge for every customer."""
        tenant = _make_tenant(name="Order Kitchen")
        tenant.profile.winback_enabled = True
        tenant.profile.winback_message = ""

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        call_order = []

        def record_side_effect(tenant_id, customer_id):
            call_order.append(("record", customer_id))

        def send_side_effect(cid, tenant_name, slug, url, title, body):
            call_order.append(("send", cid))
            return 1  # simulate successful delivery

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(11, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges.cache") as mock_cache, \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("menu.management.commands.send_winback_nudges._build_audience", return_value=[7, 8, 9]), \
             patch("menu.management.commands.send_winback_nudges._record_nudge", side_effect=record_side_effect), \
             patch("menu.management.commands.send_winback_nudges._send_nudge", side_effect=send_side_effect):
            mock_cache.add.return_value = True
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            cmd.handle(dry_run=False)

        # Verify that for every customer, "record" comes immediately before "send".
        self.assertEqual(len(call_order), 6, f"Expected 6 calls (record+send x3), got: {call_order}")
        for i in range(0, 6, 2):
            op1, cid1 = call_order[i]
            op2, cid2 = call_order[i + 1]
            self.assertEqual(op1, "record", f"Step {i}: expected 'record', got '{op1}' (call_order={call_order})")
            self.assertEqual(op2, "send",   f"Step {i+1}: expected 'send', got '{op2}' (call_order={call_order})")
            self.assertEqual(cid1, cid2,    f"Step {i}/{i+1}: customer mismatch ({cid1} vs {cid2})")

    def test_send_failure_does_not_prevent_record_nudge(self):
        """Even if _send_nudge returns 0 (send failed/suppressed), the dedupe row
        was already written — the test confirms _record_nudge was called first.

        (The row will subsequently be deleted by the slot-reclaim path, but the
        ordering guarantee still holds: write first, send second.)
        """
        tenant = _make_tenant(name="Order Kitchen")
        tenant.profile.winback_enabled = True
        tenant.profile.winback_message = ""

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        call_order = []

        def record_side_effect(tenant_id, customer_id):
            call_order.append(("record", customer_id))

        def send_side_effect(cid, tenant_name, slug, url, title, body):
            call_order.append(("send", cid))
            return 0  # simulate suppressed / opt-out at send time

        mock_winback_qs = MagicMock()
        mock_winback_qs.filter.return_value.order_by.return_value.__getitem__ = MagicMock(
            return_value=MagicMock()
        )

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(11, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges.cache") as mock_cache, \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("menu.management.commands.send_winback_nudges._build_audience", return_value=[42]), \
             patch("menu.management.commands.send_winback_nudges._record_nudge", side_effect=record_side_effect), \
             patch("menu.management.commands.send_winback_nudges._send_nudge", side_effect=send_side_effect), \
             patch("accounts.models.WinbackNudge.objects", mock_winback_qs):
            mock_cache.add.return_value = True
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            cmd.handle(dry_run=False)

        # record must come before send
        self.assertEqual(call_order[0], ("record", 42))
        self.assertEqual(call_order[1], ("send", 42))


# ─────────────────────────────────────────────────────────────────────────────
# 13. Suppressed send reclaims the WinbackNudge row
# ─────────────────────────────────────────────────────────────────────────────

class WinbackSuppressedSendReclamationTests(SimpleTestCase):
    """When _send_nudge returns 0, the pre-written WinbackNudge row is deleted
    so the 90-day dedupe slot is not burned for an undelivered message."""

    def test_suppressed_send_triggers_row_deletion(self):
        """When push is suppressed (sent_count==0), the nudge row is deleted."""
        tenant = _make_tenant(name="Suppressed Bistro")
        tenant.profile.winback_enabled = True
        tenant.profile.winback_message = ""

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        # Track WinbackNudge queryset calls.
        # The reclaim MUST use .first() then row.delete() — a sliced queryset
        # ([:1].delete()) raises in real Django ORM ("Cannot use 'limit' or
        # 'offset' with delete"), which mocks would silently allow.
        mock_winback_qs = MagicMock()
        filter_result = MagicMock()
        order_result = MagicMock()
        row = MagicMock()
        mock_winback_qs.filter.return_value = filter_result
        filter_result.order_by.return_value = order_result
        order_result.first.return_value = row
        # Make any sliced-delete attempt blow up like the real ORM would.
        order_result.__getitem__ = MagicMock(
            side_effect=AssertionError("Cannot use 'limit' or 'offset' with delete().")
        )

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(11, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges.cache") as mock_cache, \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("menu.management.commands.send_winback_nudges._build_audience", return_value=[42]), \
             patch("menu.management.commands.send_winback_nudges._record_nudge"), \
             patch("menu.management.commands.send_winback_nudges._send_nudge", return_value=0), \
             patch("accounts.models.WinbackNudge.objects", mock_winback_qs):
            mock_cache.add.return_value = True
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            cmd.handle(dry_run=False)

        # WinbackNudge.objects.filter(...).order_by("-sent_at").first() → row.delete()
        mock_winback_qs.filter.assert_called_once_with(tenant_id=tenant.id, customer_id=42)
        filter_result.order_by.assert_called_once_with("-sent_at")
        order_result.first.assert_called_once_with()
        row.delete.assert_called_once()

    def test_successful_send_does_not_delete_row(self):
        """When push is delivered (sent_count>0), the nudge row is NOT deleted."""
        tenant = _make_tenant(name="Happy Bistro")
        tenant.profile.winback_enabled = True
        tenant.profile.winback_message = ""

        mock_tenant_qs = MagicMock()
        mock_tenant_qs.filter.return_value.exclude.return_value.select_related.return_value = [tenant]

        mock_winback_qs = MagicMock()

        cmd = _make_command()
        with patch("menu.management.commands.send_winback_nudges.Tenant.objects", mock_tenant_qs), \
             patch("menu.management.commands.send_winback_nudges._tenant_local_hour", return_value=(11, "2024-01-01")), \
             patch("menu.management.commands.send_winback_nudges.cache") as mock_cache, \
             patch("menu.management.commands.send_winback_nudges.schema_context") as mock_ctx, \
             patch("menu.management.commands.send_winback_nudges._build_audience", return_value=[42]), \
             patch("menu.management.commands.send_winback_nudges._record_nudge"), \
             patch("menu.management.commands.send_winback_nudges._send_nudge", return_value=1), \
             patch("accounts.models.WinbackNudge.objects", mock_winback_qs):
            mock_cache.add.return_value = True
            mock_ctx.return_value.__enter__ = MagicMock(return_value=None)
            mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
            cmd.handle(dry_run=False)

        # WinbackNudge.objects should NOT be touched for deletion
        mock_winback_qs.filter.assert_not_called()
