"""Unit tests for tenant-scoped channel group naming (realtime/groups.py).

The group name is the WebSocket tenant-isolation boundary, so these verify two
different tenants never collapse to the same group and that names stay valid for
Channels (allowed chars, length).
"""
import re

from django.test import SimpleTestCase

from realtime.groups import tenant_group

_ALLOWED = re.compile(r"^[A-Za-z0-9._-]+$")


class TenantGroupTests(SimpleTestCase):
    def test_distinct_schemas_yield_distinct_groups(self):
        self.assertNotEqual(tenant_group("resto_a", "owner"), tenant_group("resto_b", "owner"))

    def test_distinct_channels_yield_distinct_groups(self):
        self.assertNotEqual(tenant_group("resto_a", "owner"), tenant_group("resto_a", "kitchen"))

    def test_stable_for_same_inputs(self):
        self.assertEqual(tenant_group("resto_a", "owner"), tenant_group("resto_a", "owner"))

    def test_only_allowed_characters(self):
        name = tenant_group("weird schema!!/$", "ch@nnel name")
        self.assertRegex(name, _ALLOWED)

    def test_real_schema_names_preserved_verbatim(self):
        # django-tenants schema names are valid SQL identifiers (alnum + underscore),
        # so they pass through sanitisation unchanged — no aliasing between tenants.
        self.assertEqual(tenant_group("resto_a", "owner"), "t.resto_a.owner")
        self.assertEqual(tenant_group("acme_bistro", "kitchen"), "t.acme_bistro.kitchen")

    def test_length_capped(self):
        self.assertLessEqual(len(tenant_group("x" * 200, "owner")), 100)

    def test_blank_inputs_have_safe_defaults(self):
        name = tenant_group("", "")
        self.assertRegex(name, _ALLOWED)
        self.assertTrue(name)
