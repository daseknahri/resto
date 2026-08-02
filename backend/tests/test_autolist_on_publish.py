"""Flywheel: auto-list on menu-publish (ProfileSerializer._autolist_on_publish).

Pure-function unit tests (SimpleTestCase, no DB) for the decision that opts a business into the
public marketplace the first time its menu goes live — the owner-approved "auto-list on publish"
default.
"""
from django.test import SimpleTestCase

from tenancy.serializers import _autolist_on_publish


_GOOD = dict(
    is_published_now=True, was_published=False, owner_set_directory=False,
    already_listed=False, city="Casablanca", lat=33.57, lng=-7.59,
)


def _decide(**over):
    return _autolist_on_publish(**{**_GOOD, **over})


class AutolistOnPublishTests(SimpleTestCase):
    def test_fresh_publish_with_full_data_auto_lists(self):
        self.assertTrue(_decide())

    def test_not_a_transition_does_not_list(self):
        # Already published (an unrelated edit while live) → never auto-list.
        self.assertFalse(_decide(was_published=True))

    def test_not_published_now_does_not_list(self):
        self.assertFalse(_decide(is_published_now=False))

    def test_explicit_owner_directory_choice_is_honored(self):
        # Owner set the directory flag in this same update → don't override (opt-out respected).
        self.assertFalse(_decide(owner_set_directory=True))

    def test_already_listed_is_noop(self):
        self.assertFalse(_decide(already_listed=True))

    def test_missing_city_does_not_list(self):
        self.assertFalse(_decide(city=""))
        self.assertFalse(_decide(city="   "))

    def test_invalid_coords_do_not_list(self):
        self.assertFalse(_decide(lat=None, lng=None))
        self.assertFalse(_decide(lat=0, lng=0))           # null island
        self.assertFalse(_decide(lat=999, lng=-7.59))     # out of range
