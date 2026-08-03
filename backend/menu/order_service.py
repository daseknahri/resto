"""Order domain service (RISK STRUCT-1).

`PlaceOrderView.post` is a ~1,100-line method that inlines the whole order pipeline
(pricing, delivery fee, promo, loyalty, wallet, stock, persistence). This module is the
home the register calls for — a tested domain service the view delegates to, mirroring
`accounts/wallet_service.py`. It is being grown one cohesive, behavior-preserving slice at a
time; the view keeps a thin function-local import at each call site (the codebase's standard
menu↔accounts/tenancy cycle-avoidance convention).

Slice 1: delivery-fee computation — a pre-atomic, side-effect-free sub-phase that already
delegated to the tested `tenancy` pricing/routing helpers, so moving it changes no behavior and
breaks no existing mock (no test patched these via `menu.views.*`).
"""
from decimal import Decimal

from menu.models import Order


def compute_order_delivery_fee(profile, *, fulfillment_type, food_subtotal, delivery_lat, delivery_lng):
    """Compute the delivery fee for an order (RISK STRUCT-1, extracted from PlaceOrderView.post).

    Returns ``(fee: Decimal, distance_km: float | None, error_code: str | None)`` where
    ``error_code`` is ``"delivery_out_of_range"`` when the address is outside the delivery area
    (the caller maps this to a 400), else ``None``.

    Behavior is identical to the former inline block:
    * Non-delivery fulfillment → ``(Decimal("0"), None, None)`` (no fee, no computation).
    * Delivery → distance is computed ONLY when BOTH the restaurant and the address have a valid,
      real coordinate (a missing / ``(0,0)`` / out-of-range coord → distance unknown → the flat
      fallback fee, never a false "outside area"), then `tenancy.delivery_pricing.compute_delivery_fee`
      decides the fee and whether the address is out of range.
    """
    if fulfillment_type != Order.FulfillmentType.DELIVERY:
        return Decimal("0"), None, None

    # Function-local (menu↔tenancy cycle-avoidance convention), matching the original call site.
    from tenancy.delivery_pricing import compute_delivery_fee, valid_coord
    from tenancy.routing import road_distance_km

    plat = getattr(profile, "lat", None)
    plng = getattr(profile, "lng", None)
    distance_km = None
    if valid_coord(plat, plng) and valid_coord(delivery_lat, delivery_lng):
        # Road distance (haversine × factor, or a real OSRM route when DELIVERY_OSRM_URL is set).
        distance_km = road_distance_km(plat, plng, delivery_lat, delivery_lng)

    pricing = compute_delivery_fee(profile, distance_km=distance_km, food_subtotal=food_subtotal)
    if pricing["out_of_range"]:
        return Decimal("0"), distance_km, "delivery_out_of_range"
    return pricing["fee"], distance_km, None


def compute_order_tip(tip_raw, food_subtotal) -> Decimal:
    """Parse + clamp the customer gratuity (RISK STRUCT-1, extracted from PlaceOrderView.post).

    Behavior is byte-identical to the former inline block: coerce to 2 dp; any parse failure or a
    negative value → ``Decimal("0")``; capped at 100% of the food subtotal when the subtotal is
    positive (a fat-finger runaway guard). When the subtotal is 0 (or negative) the cap does not
    apply, matching the original ``if _food_subtotal > 0 and ...`` guard.
    """
    try:
        tip = Decimal(str(tip_raw)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0")
    if tip < Decimal("0"):
        return Decimal("0")
    if food_subtotal > Decimal("0") and tip > food_subtotal:
        return food_subtotal
    return tip


def resolve_prepay_and_wallet(*, user, linked_customer, profile, fulfillment_type, total,
                              is_scheduled, payment_method, use_wallet_flag):
    """Resolve the prepay / cash-on-handover / wallet money-gate (RISK STRUCT-1, extracted from
    PlaceOrderView.post).

    Returns ``(requires_prepay, cod_order, use_wallet, wallet_deduction, error)`` — the four locals
    the order pipeline consumes downstream, plus ``error`` = a ``(detail_dict, http_status)`` tuple
    the caller returns as a Response, or ``None`` when the gate passes.

    Behavior is byte-identical to the former inline block: staff/owner orders (waiter settles in
    person) are EXEMPT; a customer pickup/delivery order with a positive total must either be a
    COD-eligible cash-on-handover (repeat customer, not a scheduled order) or be fully covered by
    wallet balance — else 403 ``auth_required`` (no signed-in customer) or 402 ``wallet_insufficient``.
    Wallet is used when prepay-required-and-not-COD or the client opted in, deducting
    ``min(balance, total)`` (and disabled if that is ≤ 0).
    """
    from accounts.models import User

    is_staff = bool(
        user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "role", None) in (User.Roles.TENANT_OWNER, User.Roles.TENANT_STAFF)
    )
    requires_prepay = (
        not is_staff
        and fulfillment_type in (Order.FulfillmentType.PICKUP, Order.FulfillmentType.DELIVERY)
    )

    cod_order = False
    if requires_prepay and total > Decimal("0"):
        if linked_customer is None:
            return requires_prepay, cod_order, False, Decimal("0"), (
                {"detail": "Sign in and top up your wallet to place a pickup or delivery order.",
                 "code": "auth_required"},
                403,
            )
        pm = str(payment_method or "").strip().lower()
        # Function-local so the patch target stays `menu.views._cod_eligible` (tests patch it there).
        from menu.views import _cod_eligible
        if pm == "cash" and not is_scheduled and _cod_eligible(profile, linked_customer.id):
            cod_order = True
        else:
            wallet_avail = Decimal(str(linked_customer.wallet_balance or "0"))
            if wallet_avail < total:
                return requires_prepay, cod_order, False, Decimal("0"), (
                    {"detail": "Your wallet balance doesn't cover this order. Please top up your wallet.",
                     "code": "wallet_insufficient",
                     "balance": str(wallet_avail), "amount_due": str(total)},
                    402,
                )

    use_wallet = ((requires_prepay and not cod_order) or bool(use_wallet_flag)) and linked_customer is not None
    wallet_deduction = Decimal("0")
    if use_wallet:
        available = Decimal(str(linked_customer.wallet_balance or "0"))
        wallet_deduction = min(available, total)
        if wallet_deduction <= Decimal("0"):
            use_wallet = False
            wallet_deduction = Decimal("0")
    return requires_prepay, cod_order, use_wallet, wallet_deduction, None


def resolve_available_dishes(slugs):
    """Return ``{slug: Dish}`` for the currently-orderable dishes among ``slugs`` (RISK STRUCT-1,
    slice 2 — item resolution).

    Filters to published + available dishes in a published, non-temporarily-disabled category, with
    the combo-component and option-group relations prefetched (the pipeline needs them downstream).
    This is byte-identical in the storefront (``PlaceOrderView``) and marketplace
    (``MarketplacePlaceOrderView``) order paths. Schema-agnostic — it runs against whatever tenant
    schema the caller has already established (ambient for the storefront, ``schema_context`` for the
    marketplace). The caller compares the returned keys against ``slugs`` to build its own
    ``items_unavailable`` response, keeping the DRF response contract in the view.
    """
    # Function-local import (codebase menu↔accounts cycle-avoidance convention) — also keeps the
    # order paths' existing `menu.models`-patching tests valid after this extraction.
    from menu.models import Dish
    return {
        d.slug: d
        for d in Dish.objects.filter(
            slug__in=slugs,
            is_published=True,
            is_available=True,
            category__is_published=True,
            category__is_temporarily_disabled=False,
        )
        .select_related("category")
        .prefetch_related("combo_components__component", "option_groups__options")
    }


def resolve_option_map(option_ids):
    """Return ``{id: DishOption}`` for ``option_ids`` with each option's ``dish`` select_related
    (RISK STRUCT-1, slice 2).

    The ``select_related("dish")`` is load-bearing security, not a perf nicety: both order paths bind
    every option to its dish and reject a foreign / cross-dish id, so a negative-``price_delta``
    option can't be smuggled onto a cheap dish to drive a wallet-prepaid total down (OPS-5f). Shared
    verbatim by both order paths.
    """
    from menu.models import DishOption  # function-local (see resolve_available_dishes)
    if not option_ids:
        return {}
    return {o.id: o for o in DishOption.objects.filter(id__in=option_ids).select_related("dish")}


def price_line_options(dish, option_ids, options_map, base_unit_price):
    """Bind + validate one order line's selected options and fold in their price (RISK
    STRUCT-1, slice 2 — per-item validation + line building).

    Given a dish, its ``base_unit_price`` (the caller's own happy-hour-adjusted unit price —
    passed in so each order path keeps its distinct happy-hour rule source and its
    ``effective_unit_price`` patch target), this centralizes the two security guards + the
    money math that were byte-identical in ``PlaceOrderView`` and ``MarketplacePlaceOrderView``:

    * **OPS-5f option binding** — every selected option id must resolve to a real option whose
      ``dish`` IS this dish. A foreign / cross-dish / unknown id can't be smuggled in to attach a
      negative ``price_delta`` to a cheap dish (the ``select_related("dish")`` that makes
      ``opt.dish`` cheap lives in `resolve_option_map`). Any invalid id → a ``stale_options`` error.
    * **B2 group-select** — ``OptionGroup.min_select`` / ``max_select`` enforced server-side (via
      `menu.views._validate_option_group_selections`, imported function-locally so its patch target
      and the menu↔accounts cycle-avoidance convention both hold).
    * **Pricing** — ``price_delta`` summed ONLY over the validated, dish-bound options, in selection
      order, and the per-option snapshot list built for the order-line record.

    Returns ``(unit_price, option_snapshots, error)`` where ``error`` is a ready-to-return DRF
    payload dict (the caller wraps it in ``Response(..., 400)``) for the first failing guard, or
    ``None`` on success — in which case ``unit_price`` = ``base_unit_price`` + Σ bound ``price_delta``
    and ``option_snapshots`` = ``[{"id","name","price_delta"}, ...]``.

    Behavior-identical to both former inline loops: the storefront interleaved the price-add with the
    binding loop but early-returned on any invalid id, so on success (all ids valid) the accumulated
    price and snapshot order match this bind-then-price form exactly.
    """
    from menu.views import _validate_option_group_selections  # function-local (cycle + patch target)

    invalid_option_ids = []
    bound_options = []
    for oid in option_ids:
        opt = options_map.get(int(oid)) if str(oid).isdigit() else None
        opt_dish_slug = getattr(getattr(opt, "dish", None), "slug", None) if opt is not None else None
        if opt is None or opt_dish_slug != dish.slug:
            invalid_option_ids.append(oid)
            continue
        bound_options.append(opt)
    if invalid_option_ids:
        return None, None, {
            "detail": f"Some selected options are no longer valid for '{dish.name}'.",
            "code": "stale_options",
            "dish_slug": dish.slug,
            "invalid_option_ids": invalid_option_ids,
        }

    group_err = _validate_option_group_selections(dish, [opt.id for opt in bound_options])
    if group_err:
        return None, None, group_err

    unit_price = base_unit_price
    option_snapshots = []
    for opt in bound_options:
        unit_price += Decimal(str(opt.price_delta))
        option_snapshots.append({"id": opt.id, "name": opt.name, "price_delta": str(opt.price_delta)})
    return unit_price, option_snapshots, None


def deplete_stock(locked_dishes, stock_updates, pk_to_slug, comp_stock_agg, comp_pk_to_name):
    """Validate + decrement dish and combo-component stock under the caller's row locks
    (RISK STRUCT-1, slice 3 — stock depletion).

    MUST be called inside the caller's ``transaction.atomic()`` block, passing the
    ``select_for_update``-locked ``{pk: Dish}`` map (the lock + the ``_OutOfStock`` raise stay
    in the view, with the transaction). Returns the slug/name of the FIRST sold-out item —
    dish slug first, then component name — so the caller raises its own out-of-stock exception
    (which rolls the whole order back), or ``None`` after applying every decrement.

    Byte-identical to the former inline blocks in ``PlaceOrderView`` and
    ``MarketplacePlaceOrderView``, with ``raise _OutOfStock(x)`` replaced by ``return x`` at the
    seam. Equivalent because the caller re-raises inside the same atomic block: a short component
    (found after the dish decrements have run) still rolls those decrements back exactly as before.

    ``stock_updates``: list of ``(dish_pk, ordered_qty)``. ``comp_stock_agg``:
    ``{component_pk: total_qty}`` (already aggregated). ``pk_to_slug`` / ``comp_pk_to_name`` are the
    sold-out message sources. A decrement that reaches 0 also flips ``is_available=False`` +
    ``stock_auto_zeroed=True`` (the marker the 5am auto-reset cron uses to tell auto- from
    owner-zeroed dishes).
    """
    from menu.models import Dish  # function-local (cycle-avoidance + patch-target parity)

    # Dish stock: validate every combo-dish before decrementing any (parity with both views).
    for _pk, _ordered in stock_updates:
        _ld = locked_dishes.get(_pk)
        if _ld and _ld.stock_qty is not None and _ld.stock_qty < _ordered:
            return pk_to_slug.get(_pk, "")
    for _pk, _ordered in stock_updates:
        _ld = locked_dishes.get(_pk)
        if _ld and _ld.stock_qty is not None:
            _new = max(0, _ld.stock_qty - _ordered)
            _fields = {"stock_qty": _new}
            if _new == 0:
                _fields["is_available"] = False
                _fields["stock_auto_zeroed"] = True
            Dish.objects.filter(pk=_pk).update(**_fields)

    # Component stock: validate then decrement.
    for _cpk, _cqty in comp_stock_agg.items():
        _ld = locked_dishes.get(_cpk)
        if _ld and _ld.stock_qty is not None and _ld.stock_qty < _cqty:
            return comp_pk_to_name.get(_cpk, "")
    for _cpk, _cqty in comp_stock_agg.items():
        _ld = locked_dishes.get(_cpk)
        if _ld and _ld.stock_qty is not None:
            _cnew = max(0, _ld.stock_qty - _cqty)
            _cfields = {"stock_qty": _cnew}
            if _cnew == 0:
                _cfields["is_available"] = False
                _cfields["stock_auto_zeroed"] = True
            Dish.objects.filter(pk=_cpk).update(**_cfields)

    return None


def deplete_ingredients(order_items_data, dishes_map):
    """Deplete recipe-linked ingredient stock for a placed order (RISK STRUCT-1, slice 3b —
    B3 Phase 2). Byte-identical in both order paths; MUST run inside the caller's atomic block.

    Aggregates ordered qty per dish (integer pks only), then for every ``RecipeLine`` on those
    dishes decrements ``Ingredient.stock_quantity`` by ``recipe_qty × ordered_qty`` via an ``F()``
    update. Negative stock is allowed by design (it flags variance / under-stocking for the owner);
    no exceptions — a recipe/ingredient issue never blocks checkout.
    """
    from django.db.models import F  # function-local
    from menu.models import Ingredient, RecipeLine

    _dish_qty_map = {}
    for _item_d in order_items_data:
        _d = dishes_map[_item_d["dish_slug"]]
        if isinstance(_d.pk, int):
            _dish_qty_map[_d.pk] = _dish_qty_map.get(_d.pk, 0) + _item_d["qty"]
    if not _dish_qty_map:
        return
    _recipe_lines = RecipeLine.objects.filter(
        dish_id__in=list(_dish_qty_map.keys())
    ).only("dish_id", "ingredient_id", "quantity")
    _ing_depletion = {}
    for _rl in _recipe_lines:
        _delta = _rl.quantity * _dish_qty_map[_rl.dish_id]
        _ing_depletion[_rl.ingredient_id] = _ing_depletion.get(_rl.ingredient_id, Decimal("0")) + _delta
    for _ing_pk, _delta in _ing_depletion.items():
        Ingredient.objects.filter(pk=_ing_pk).update(stock_quantity=F("stock_quantity") - _delta)
