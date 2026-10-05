"""Customer-visibility predicate for menu content: what an anonymous customer actually
sees on the public menu.

These are the exact customer filters the public menu applies in
``CategoryViewSet.get_queryset`` / ``DishViewSet.get_queryset`` (menu/views.py): a
category is visible only when it AND its parent super-category are published and not
temporarily paused; a dish additionally has to be published itself. Kept as plain
``.filter(**kwargs)`` dicts so any caller can reuse them without re-deriving the rule
(the onboarding publish gate in ``tenancy.serializers.ProfileSerializer.validate`` does).

``tests/test_publish_gate_visibility.py`` pins these dicts to the viewsets' inline
filters, so the public menu and its callers can't silently drift apart.
"""

CUSTOMER_VISIBLE_CATEGORY_FILTER = {
    "is_published": True,
    "is_temporarily_disabled": False,
    "super_category__is_published": True,
    "super_category__is_temporarily_disabled": False,
}

CUSTOMER_VISIBLE_DISH_FILTER = {
    "is_published": True,
    "category__is_published": True,
    "category__is_temporarily_disabled": False,
    "category__super_category__is_published": True,
    "category__super_category__is_temporarily_disabled": False,
}
