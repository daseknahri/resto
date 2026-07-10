"""DATA-4: opting into the public directory requires the discoverable fields.

ProfileSerializer.validate now rejects directory_opt_in=True unless the profile has a
city and valid coordinates (the marketplace card + distance sort depend on them). These
run without a DB (SimpleTestCase) by calling validate() directly with a stub instance;
the enforcement fires only when directory_opt_in is part of the update payload.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework import serializers

from tenancy.serializers import ProfileSerializer


def _inst(**over):
    """A minimal stub Profile carrying the attributes ProfileSerializer.validate reads."""
    base = dict(is_menu_temporarily_disabled=False, menu_disabled_note="",
                is_menu_published=False, city="", lat=None, lng=None)
    base.update(over)
    return SimpleNamespace(**base)


class DirectoryOptInValidationTests(SimpleTestCase):
    def test_opt_in_requires_city_and_coords(self):
        with self.assertRaises(serializers.ValidationError):
            ProfileSerializer().validate({"directory_opt_in": True})

    def test_opt_in_requires_coords_even_with_city(self):
        with self.assertRaises(serializers.ValidationError):
            ProfileSerializer().validate({"directory_opt_in": True, "city": "Casablanca"})

    def test_opt_in_with_city_and_valid_coords_passes(self):
        out = ProfileSerializer().validate(
            {"directory_opt_in": True, "city": "Casablanca", "lat": 33.57, "lng": -7.59}
        )
        self.assertTrue(out["directory_opt_in"])

    def test_opt_in_with_null_island_coords_is_rejected(self):
        # (0,0) is normalized to None by the coord guard, so it counts as "no location".
        with self.assertRaises(serializers.ValidationError):
            ProfileSerializer().validate(
                {"directory_opt_in": True, "city": "Casablanca", "lat": 0, "lng": 0}
            )

    def test_opt_out_is_not_blocked(self):
        out = ProfileSerializer().validate({"directory_opt_in": False})
        self.assertFalse(out["directory_opt_in"])

    def test_opt_in_uses_existing_instance_fields(self):
        s = ProfileSerializer(instance=_inst(city="Casablanca", lat=33.57, lng=-7.59))
        out = s.validate({"directory_opt_in": True})   # city/coords come from the instance
        self.assertTrue(out["directory_opt_in"])

    def test_unrelated_update_while_opted_in_is_not_blocked(self):
        # directory_opt_in not in the payload → no enforcement, even if the instance lacks
        # city/coords. Editing an unrelated field on a listed profile must not be blocked.
        s = ProfileSerializer(instance=_inst(directory_opt_in=True))
        out = s.validate({"receipt_message": "thanks"})
        self.assertEqual(out.get("receipt_message"), "thanks")
