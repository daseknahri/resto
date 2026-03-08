from __future__ import annotations


PLAN_CODE_CANONICAL = {
    "basic": "starter",
    "starter": "starter",
    "growth": "growth",
    "pro": "pro",
}

PLAN_CODE_EXTERNAL = {
    "starter": "basic",
    "growth": "growth",
    "pro": "pro",
}

PLAN_DISPLAY_NAME = {
    "starter": "Basic",
    "growth": "Growth",
    "pro": "Pro",
}

PLAN_TIER_ORDER = {
    "starter": 1,
    "growth": 2,
    "pro": 3,
}


def canonical_plan_code(code: str | None) -> str:
    raw = (code or "").strip().lower()
    return PLAN_CODE_CANONICAL.get(raw, raw)


def external_plan_code(code: str | None) -> str:
    canonical = canonical_plan_code(code)
    return PLAN_CODE_EXTERNAL.get(canonical, canonical)


def plan_display_name(code: str | None, fallback: str | None = None) -> str:
    canonical = canonical_plan_code(code)
    if canonical in PLAN_DISPLAY_NAME:
        return PLAN_DISPLAY_NAME[canonical]
    return fallback or canonical or "Plan"


def plan_tier_order(code: str | None) -> int:
    canonical = canonical_plan_code(code)
    return int(PLAN_TIER_ORDER.get(canonical, 0))


def is_plan_upgrade(current_code: str | None, target_code: str | None) -> bool:
    return plan_tier_order(target_code) > plan_tier_order(current_code)


def plan_entitlements(plan) -> dict:
    can_checkout = bool(getattr(plan, "can_checkout", False))
    can_whatsapp_order = bool(getattr(plan, "can_whatsapp_order", False))
    if can_checkout:
        ordering_mode = "checkout"
    elif can_whatsapp_order:
        ordering_mode = "whatsapp"
    else:
        ordering_mode = "menu_only"

    canonical = canonical_plan_code(getattr(plan, "code", ""))
    return {
        "tier_code": external_plan_code(canonical),
        "tier_name": plan_display_name(canonical, fallback=getattr(plan, "name", "")),
        "ordering_mode": ordering_mode,
        "can_order": can_checkout or can_whatsapp_order,
        "can_checkout": can_checkout,
        "can_whatsapp_order": can_whatsapp_order,
        "max_languages": int(getattr(plan, "max_languages", 1) or 1),
        "is_active": bool(getattr(plan, "is_active", True)),
    }
