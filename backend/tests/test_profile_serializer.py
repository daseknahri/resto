from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase
from rest_framework.exceptions import ValidationError

from tenancy.models import Plan, Profile, Tenant
from tenancy.serializers import ProfileSerializer


class ProfileSerializerTests(SimpleTestCase):
    def test_reservation_url_field_is_exposed(self):
        serializer = ProfileSerializer()
        self.assertIn("reservation_url", serializer.fields)

    def test_reservation_url_accepts_valid_url(self):
        serializer = ProfileSerializer(data={"reservation_url": "https://reserve.example.com/book"})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_reservation_url_rejects_invalid_url(self):
        serializer = ProfileSerializer(data={"reservation_url": "invalid-url"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("reservation_url", serializer.errors)

    def test_language_accepts_supported_codes(self):
        serializer = ProfileSerializer(data={"language": "fr"})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_language_rejects_unsupported_codes(self):
        serializer = ProfileSerializer(data={"language": "es"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("language", serializer.errors)

    def test_tags_rejects_non_list(self):
        # A non-list `tags` would 500 the public marketplace listing (a list comprehension
        # over it) — reject it at the write instead.
        serializer = ProfileSerializer(data={"tags": 5})
        self.assertFalse(serializer.is_valid())
        self.assertIn("tags", serializer.errors)

    def test_tags_normalizes_list_entries(self):
        serializer = ProfileSerializer(data={"tags": ["  Halal ", "", "Vegan"]})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["tags"], ["Halal", "Vegan"])

    def test_logo_url_is_normalized_to_https_for_same_host_media(self):
        request = RequestFactory().get("/", secure=True, HTTP_HOST="badr.menu.ibnbatoutaweb.com")
        tenant = Tenant(name="Badr", slug="badr", plan=Plan(code="basic", name="Basic"))
        profile = Profile(tenant=tenant, logo_url="http://badr.menu.ibnbatoutaweb.com/media/uploads/badr/logo.webp")

        serializer = ProfileSerializer(instance=profile, context={"request": request})

        self.assertEqual(
            serializer.data["logo_url"],
            "https://badr.menu.ibnbatoutaweb.com/media/uploads/badr/logo.webp",
        )

    def test_partial_update_does_not_fail_on_existing_disabled_without_note(self):
        tenant = Tenant(name="Demo", slug="demo", plan=Plan(code="basic", name="Basic"))
        profile = Profile(
            tenant=tenant,
            is_menu_temporarily_disabled=True,
            menu_disabled_note="",
            tagline="Old",
        )
        serializer = ProfileSerializer(instance=profile, data={"tagline": "New"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_disabling_menu_requires_note_when_disable_flag_provided(self):
        serializer = ProfileSerializer(data={"is_menu_temporarily_disabled": True, "menu_disabled_note": ""}, partial=True)
        self.assertFalse(serializer.is_valid())
        self.assertIn("menu_disabled_note", serializer.errors)

    def test_profile_i18n_localizes_for_public_requests(self):
        request = RequestFactory().get("/api/meta/?lang=fr", HTTP_HOST="demo.menu.ibnbatoutaweb.com")
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=3))
        profile = Profile(
            tenant=Tenant(name="Demo", slug="demo", plan=Plan(code="starter", name="Basic")),
            tagline="Fast menu",
            tagline_i18n={"fr": "Menu rapide", "ar": "قائمة سريعة"},
        )
        serializer = ProfileSerializer(instance=profile, context={"request": request})
        self.assertEqual(serializer.data["tagline"], "Menu rapide")

    def test_profile_i18n_keeps_base_fields_for_authenticated_owner(self):
        request = RequestFactory().get("/api/profile/?lang=fr", HTTP_HOST="demo.menu.ibnbatoutaweb.com")
        request.user = SimpleNamespace(is_authenticated=True)
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=3))
        profile = Profile(
            tenant=Tenant(name="Demo", slug="demo", plan=Plan(code="starter", name="Basic")),
            tagline="Fast menu",
            tagline_i18n={"fr": "Menu rapide"},
        )
        serializer = ProfileSerializer(instance=profile, context={"request": request})
        self.assertEqual(serializer.data["tagline"], "Fast menu")

    def test_profile_i18n_can_be_forced_for_authenticated_owner(self):
        request = RequestFactory().get("/api/meta/?lang=fr&force_locale=1", HTTP_HOST="demo.menu.ibnbatoutaweb.com")
        request.user = SimpleNamespace(is_authenticated=True)
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=3))
        profile = Profile(
            tenant=Tenant(name="Demo", slug="demo", plan=Plan(code="starter", name="Basic")),
            tagline="Fast menu",
            tagline_i18n={"fr": "Menu rapide"},
        )
        serializer = ProfileSerializer(instance=profile, context={"request": request})
        self.assertEqual(serializer.data["tagline"], "Menu rapide")

    def test_business_hours_field_is_exposed(self):
        serializer = ProfileSerializer()
        self.assertIn("business_hours", serializer.fields)
        self.assertIn("business_hours_i18n", serializer.fields)
        self.assertIn("business_hours_schedule", serializer.fields)

    def test_profile_business_hours_localizes_for_public_requests(self):
        request = RequestFactory().get("/api/meta/?lang=fr", HTTP_HOST="demo.menu.ibnbatoutaweb.com")
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=3))
        profile = Profile(
            tenant=Tenant(name="Demo", slug="demo", plan=Plan(code="starter", name="Basic")),
            business_hours="Mon-Sat, 11:00-23:00",
            business_hours_i18n={"fr": "Lun-Sam, 11:00-23:00"},
        )
        serializer = ProfileSerializer(instance=profile, context={"request": request})
        self.assertEqual(serializer.data["business_hours"], "Lun-Sam, 11:00-23:00")

    def test_business_hours_schedule_accepts_weekday_slots(self):
        serializer = ProfileSerializer(
            data={
                "business_hours_schedule": {
                    "mon": {"enabled": True, "open": "09:00", "close": "18:00"},
                    "sun": {"enabled": False, "open": "", "close": ""},
                }
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_business_hours_schedule_rejects_invalid_time_format(self):
        serializer = ProfileSerializer(
            data={
                "business_hours_schedule": {
                    "mon": {"enabled": True, "open": "9:00", "close": "18:00"},
                }
            },
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("business_hours_schedule", serializer.errors)

    def test_profile_i18n_enforces_plan_limit(self):
        request = RequestFactory().get("/api/profile/", HTTP_HOST="demo.menu.ibnbatoutaweb.com")
        request.tenant = SimpleNamespace(plan=SimpleNamespace(max_languages=3))
        serializer = ProfileSerializer(context={"request": request})
        cleaned = serializer.validate_tagline_i18n({"fr": "Menu rapide", "ar": "قائمة", "en": "Fast menu"})
        self.assertEqual(cleaned, {"fr": "Menu rapide", "ar": "قائمة", "en": "Fast menu"})
        with self.assertRaisesMessage(
            ValidationError, "Current plan supports up to 3 translated language entries for Tagline."
        ):
            serializer.validate_tagline_i18n(
                {"fr": "Menu rapide", "ar": "قائمة", "en": "Fast menu", "en-us": "Fast menu US"}
            )

# ── R6-16: pending_sla_minutes / pending_auto_cancel_minutes ─────────────
# The sweep only cancels orders that were already escalated, so auto-cancel
# must exceed the escalation SLA (or be 0 = never). The rule fires only when
# one of the two fields is in THIS update, so an unrelated PATCH on a legacy
# profile is never blocked by a stale value.

class ProfileSerializerSlaTests(SimpleTestCase):
    def _profile(self, **kwargs):
        tenant = Tenant(name="Demo", slug="demo", plan=Plan(code="basic", name="Basic"))
        return Profile(tenant=tenant, **kwargs)

    def test_sla_and_auto_cancel_fields_are_exposed(self):
        serializer = ProfileSerializer()
        self.assertIn("pending_sla_minutes", serializer.fields)
        self.assertIn("pending_auto_cancel_minutes", serializer.fields)

    def test_serializer_data_exposes_stored_values(self):
        profile = self._profile(pending_sla_minutes=15, pending_auto_cancel_minutes=90)
        data = ProfileSerializer(instance=profile).data
        self.assertEqual(data["pending_sla_minutes"], 15)
        self.assertEqual(data["pending_auto_cancel_minutes"], 90)

    def test_auto_cancel_above_default_sla_is_valid(self):
        # No instance SLA -> platform default 10; 60 > 10.
        serializer = ProfileSerializer(data={"pending_auto_cancel_minutes": 60})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["pending_auto_cancel_minutes"], 60)

    def test_auto_cancel_200_with_sla_60_is_valid(self):
        # Pack sketch: PATCH 60 -> 200 persisted.
        serializer = ProfileSerializer(
            data={"pending_sla_minutes": 60, "pending_auto_cancel_minutes": 200}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["pending_sla_minutes"], 60)
        self.assertEqual(serializer.validated_data["pending_auto_cancel_minutes"], 200)

    def test_auto_cancel_below_default_sla_is_rejected(self):
        # Pack sketch: PATCH 5 (< SLA 10) -> 400.
        serializer = ProfileSerializer(data={"pending_auto_cancel_minutes": 5})
        self.assertFalse(serializer.is_valid())
        self.assertIn("pending_auto_cancel_minutes", serializer.errors)

    def test_auto_cancel_equal_to_sla_is_rejected(self):
        profile = self._profile(pending_sla_minutes=60)
        serializer = ProfileSerializer(
            instance=profile, data={"pending_auto_cancel_minutes": 60}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("pending_auto_cancel_minutes", serializer.errors)

    def test_auto_cancel_below_instance_sla_is_rejected(self):
        profile = self._profile(pending_sla_minutes=60)
        serializer = ProfileSerializer(
            instance=profile, data={"pending_auto_cancel_minutes": 30}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("pending_auto_cancel_minutes", serializer.errors)

    def test_auto_cancel_zero_never_is_valid(self):
        serializer = ProfileSerializer(data={"pending_auto_cancel_minutes": 0})
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_unrelated_patch_is_not_blocked_by_stale_values(self):
        # Legacy profile already holding a too-small auto-cancel (set before
        # the rule existed): editing an unrelated field must still work.
        profile = self._profile(
            pending_sla_minutes=10, pending_auto_cancel_minutes=5, tagline="Old"
        )
        serializer = ProfileSerializer(
            instance=profile, data={"tagline": "New"}, partial=True
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

# ── R6-26: Profile.timezone defaults to Africa/Casablanca ─────────────────
# The model default covers every Profile creation path (lead provisioning,
# get_or_create on the profile endpoint, admin). Blank stays legal (explicit
# clear) — the UTC fallback covers it on both sides.

class ProfileTimezoneDefaultTests(SimpleTestCase):
    def _profile(self, **kwargs):
        tenant = Tenant(name="Demo", slug="demo", plan=Plan(code="basic", name="Basic"))
        return Profile(tenant=tenant, **kwargs)

    def test_new_profile_defaults_to_casablanca(self):
        self.assertEqual(self._profile().timezone, "Africa/Casablanca")

    def test_explicit_timezone_is_kept(self):
        self.assertEqual(
            self._profile(timezone="Europe/Paris").timezone, "Europe/Paris"
        )

    def test_serializer_accepts_timezone(self):
        serializer = ProfileSerializer(data={"timezone": "Africa/Casablanca"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["timezone"], "Africa/Casablanca")

    def test_serializer_accepts_blank_timezone(self):
        serializer = ProfileSerializer(data={"timezone": ""})
        self.assertTrue(serializer.is_valid(), serializer.errors)
