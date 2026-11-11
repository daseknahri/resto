"""Shared computation + immutable snapshots for the owner commission statement.

Phase 3 (statement point-in-time immutability): the monthly marketplace
commission statement used to be recomputed from live ``Order`` rows on every
fetch, so a later void/cancel silently rewrote a prior month's invoiced total.

This module is now the single home of the statement logic:

  * ``compute_statement(profile, year, month)`` — the ONE computation used by
    both the live preview (GET with no issued snapshot) and the issue flow
    (POST), so the two can never drift.
  * ``render_statement_pdf(...)`` — the ONE PDF renderer, fed the same
    ``orders_data`` / ``per_currency`` dicts whether they were just computed
    or loaded from a frozen snapshot.
  * ``issue_statement(...)`` — persists a frozen snapshot
    (``CommissionStatement`` + ``CommissionStatementLine`` rows). Re-issue is
    an explicit, reasoned act that creates revision N+1 and supersedes N.
  * ``get_issued_statement(year, month)`` — the latest issued snapshot, or
    None when the month has never been issued (GET then serves the live
    preview, flagged provisional).

Out of scope BY DESIGN (owner-decision-gated, register G1/G2): WHICH orders
are billable (COD collected-vs-placement basis) and the commission basis
itself (post-discount, ``menu.commission.commissionable_food_base``). The
snapshot freezes whatever the current policy computes — immutability is
orthogonal to both decisions.
"""
from collections import OrderedDict
from datetime import datetime as _dt
from datetime import timezone as _stdlib_tz
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .commission import COMMISSIONABLE_STATUSES
from .models import CommissionStatement, CommissionStatementLine


class StatementAlreadyIssued(Exception):
    """Raised when issuing a month that already has an issued revision
    without the explicit reissue flag."""


class StatementReissueReasonRequired(Exception):
    """Raised when a reissue is requested without a reason."""


def _order_model():
    """Resolve the Order model through ``menu.views`` at call time.

    Two reasons: (1) ``menu.views`` imports this module, so a top-level
    ``from menu.views import Order`` would be circular; (2) the statement
    unit tests have patched ``menu.views.Order`` for years — resolving
    through that namespace preserves the seam exactly.
    """
    from menu import views as _views

    return _views.Order


def compute_statement(profile, year, month, *, branch_id=None):
    """Compute the statement for (year, month) from live Order rows.

    ``profile`` is the tenant's ``tenancy.Profile`` (or None → UTC behaviour),
    used to bucket the month in the tenant's LOCAL timezone. Returns a dict:
    ``orders_data`` / ``per_currency`` / ``summary`` (the exact shapes the API
    serves), ``order_ids`` (aligned with ``orders_data``; internal, for the
    issue flow), and ``tz_name`` (the bucket timezone actually used).

    ``branch_id`` (Phase 3 multi-branch) optionally restricts the computation
    to one branch's orders; the account-level statement passes None.
    """
    Order = _order_model()

    # A5: bucket by the TENANT-LOCAL month, not UTC. Build the local month's
    # [start, next-month-start) range in the tenant tz and filter
    # created_at__gte/__lt on it. created_at is stored tz-aware (UTC), so
    # Django converts these aware bounds correctly for the comparison.
    try:
        tz_name = (getattr(profile, "timezone", "") or "").strip() or getattr(settings, "TIME_ZONE", "") or "UTC"
        _tz = ZoneInfo(tz_name)
    except Exception:
        tz_name = getattr(settings, "TIME_ZONE", "") or "UTC"
        _tz = _stdlib_tz.utc
    month_start = _dt(year, month, 1, 0, 0, 0, tzinfo=_tz)
    _ny, _nm = (year + 1, 1) if month == 12 else (year, month + 1)
    next_month_start = _dt(_ny, _nm, 1, 0, 0, 0, tzinfo=_tz)

    # Query marketplace orders for this local month.
    #
    # Bill only orders that have EARNED commission: the shared COMMISSIONABLE_STATUSES
    # (menu.commission) — CONFIRMED / PREPARING / READY / OUT_FOR_DELIVERY / COMPLETED.
    # Commission is earned once the restaurant confirms the order. PENDING / SCHEDULED
    # orders can still be cancelled before the kitchen commits, so they are NOT yet
    # billable; a CANCELLED order had its food revenue fully refunded and never counts
    # (a fully item-voided order keeps its status but its commission is reduced to 0 at
    # void time). This is the IDENTICAL status set the owner analytics
    # (sales.views billable_statuses) bills on, so the two never disagree. The filter is
    # applied ONCE on the base queryset so the aggregate Sum and the per-order rows agree.
    qs = (
        Order.objects
        .filter(
            source=Order.Source.MARKETPLACE,
            created_at__gte=month_start,
            created_at__lt=next_month_start,
        )
        .filter(status__in=COMMISSIONABLE_STATUSES)
        .order_by("created_at")
        # Only the columns actually read below (orders_data comprehension) —
        # this queryset can span a full month of marketplace orders, and Order
        # has ~50 columns. Verified against every `o.<field>` access in this
        # view, including ones used only in computation (net_payout math).
        .only(
            "order_number", "created_at", "customer_name", "total",
            "delivery_fee", "commission_amount", "commission_rate_applied",
            "currency", "status",
        )
    )
    if branch_id is not None:
        qs = qs.filter(branch_id=branch_id)

    rows = list(qs)

    # ── Commission BASIS note ─────────────────────────────────────────────
    # commission_amount is charged on the POST-discount food base (food_subtotal
    # minus promo + loyalty discounts; see accounts/views.py marketplace checkout
    # and menu.commission.commissionable_food_base). total_revenue below is the sum
    # of Order.total, which is also post-discount but is additionally tip-INCLUSIVE.
    # So net_payout = total_revenue - delivery_fee - total_commission is coherent on
    # the discount dimension; the only remaining spread is the customer tip, which is
    # revenue that belongs to staff, not a commission base.
    orders_data = [
        {
            "order_number": o.order_number,
            "created_at": o.created_at.isoformat(),
            "customer_name": o.customer_name or "",
            "total": float(o.total),
            # Delivery fee is NOT restaurant revenue — it passes through to the driver
            # (minus platform's delivery commission). net_payout subtracts it so the
            # restaurant sees only what it actually earns.
            "delivery_fee": float(o.delivery_fee),
            "commission_amount": float(o.commission_amount),
            # A5: surface the snapshotted rate so each row's commission is auditable.
            "commission_rate_applied": float(o.commission_rate_applied),
            "net_payout": float((o.total - o.delivery_fee - o.commission_amount).quantize(Decimal("0.01"))),
            "currency": o.currency,
            "status": o.status,
        }
        for o in rows
    ]
    # Mock-suite rows (SimpleNamespace) carry no id — the original view
    # never read one. Real rows always have an id; the issue flow zips
    # these with orders_data, so a None here could only come from a mock.
    order_ids = [getattr(o, "id", None) for o in rows]

    # ── A5-followup FIX 3: per-CURRENCY totals ────────────────────────────────
    # A single marketplace tenant can take orders in more than one ISO currency
    # (a multi-locale storefront, a tenant that re-priced mid-month, etc.).
    # Summing Order.total / Order.commission_amount ACROSS currencies produces a
    # meaningless number (10 MAD + 10 USD ≠ 20 of anything) and the old PDF then
    # stamped EVERY row with orders_data[0]['currency'], mislabelling foreign-
    # currency rows. We therefore bucket totals by currency. We aggregate in
    # Python from the already-materialised rows (one pass, no extra query) using
    # Decimal so the money math is exact, then expose floats in the JSON to match
    # the existing row shape. `per_currency` preserves order of first appearance.
    _by_cur: "OrderedDict[str, dict]" = OrderedDict()
    for o in orders_data:
        cur = o["currency"] or ""
        bucket = _by_cur.get(cur)
        if bucket is None:
            bucket = _by_cur[cur] = {
                "currency": cur,
                "order_count": 0,
                "_revenue": Decimal("0"),
                "_delivery_fees": Decimal("0"),
                "_commission": Decimal("0"),
            }
        bucket["order_count"] += 1
        bucket["_revenue"] += Decimal(str(o["total"]))
        bucket["_delivery_fees"] += Decimal(str(o["delivery_fee"]))
        bucket["_commission"] += Decimal(str(o["commission_amount"]))

    per_currency = []
    for bucket in _by_cur.values():
        rev = bucket["_revenue"]
        del_fees = bucket["_delivery_fees"]
        com = bucket["_commission"]
        per_currency.append({
            "currency": bucket["currency"],
            "order_count": bucket["order_count"],
            "total_revenue": float(rev),
            "total_delivery_fees": float(del_fees),
            "total_commission": float(com),
            # net_payout is what the restaurant actually earns: gross revenue minus
            # delivery pass-through (driver's) and the platform food commission.
            "net_payout": float((rev - del_fees - com).quantize(Decimal("0.01"))),
        })

    order_count = len(orders_data)

    # Single-currency case (the common case): keep the historical top-level
    # `summary` shape so existing JSON consumers are unchanged. Mixed-currency
    # months get a summary with currency="" and zeroed cross-currency money to
    # signal that the meaningful breakdown lives in `per_currency` (we refuse to
    # publish a cross-currency sum). `per_currency` is ALWAYS present.
    if len(per_currency) == 1:
        _single = per_currency[0]
        summary = {
            "order_count": order_count,
            "total_revenue": _single["total_revenue"],
            "total_commission": _single["total_commission"],
            "net_payout": _single["net_payout"],
            "currency": _single["currency"],
        }
    else:
        summary = {
            "order_count": order_count,
            "total_revenue": 0.0,
            "total_commission": 0.0,
            "net_payout": 0.0,
            "currency": "",
            "mixed_currency": True,
        }

    return {
        "orders_data": orders_data,
        "order_ids": order_ids,
        "per_currency": per_currency,
        "summary": summary,
        "tz_name": tz_name,
    }


_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
]


def render_statement_pdf(year, month, orders_data, per_currency):
    """Render the statement PDF and return its bytes.

    Fed the same ``orders_data`` / ``per_currency`` shapes whether they were
    just computed or loaded from a frozen snapshot — which is the point:
    after a month is issued, the PDF is rendered from frozen rows, so what
    the owner downloads can no longer drift. The rendering itself is the
    view's original A5-followup code (per-currency summary blocks, each
    labelled with its own currency code), moved here verbatim.
    """
    order_count = len(orders_data)
    month_name = _MONTH_NAMES
    # ── PDF ───────────────────────────────────────────────────────────────
    # A5-followup FIX 3: render the summary + totals PER CURRENCY, each labelled
    # with ITS OWN currency code — never orders_data[0]['currency'] for every
    # line (which mislabelled foreign-currency money on a mixed-currency month).

    # Derive the commission label from the per-order snapshotted rates rather
    # than a hardcoded "10%": the platform can set a non-default rate per
    # tenant (Profile.marketplace_commission_pct), so a literal would misstate
    # the rate on an official money document. Show the exact rate only when
    # every order in the month carries the same snapshotted rate; otherwise
    # drop the percentage (mixed rates can't be summarised by one number).
    _distinct_rates = {o["commission_rate_applied"] for o in orders_data}
    if len(_distinct_rates) == 1:
        _pct = next(iter(_distinct_rates)) * 100
        # Trim trailing zeros so 10.00 → "10%" and 12.50 → "12.5%".
        _pct_str = f"{_pct:.2f}".rstrip("0").rstrip(".")
        commission_label = f"Platform commission ({_pct_str}%):"
    else:
        commission_label = "Platform commission:"

    buffer = BytesIO()
    doc = canvas.Canvas(buffer, pagesize=A4)
    page_w, page_h = A4
    margin = 20 * mm

    # Header bar
    doc.setFillColorRGB(0.059, 0.059, 0.314)  # deep indigo
    doc.rect(0, page_h - 38 * mm, page_w, 38 * mm, fill=1, stroke=0)

    doc.setFillColorRGB(1, 1, 1)
    doc.setFont("Helvetica-Bold", 18)
    doc.drawString(margin, page_h - 18 * mm, "Marketplace Commission Statement")
    doc.setFont("Helvetica", 10)
    doc.drawString(margin, page_h - 29 * mm, f"{month_name[month]} {year}")

    y = page_h - 50 * mm

    # Summary box — one sub-block per currency (each labelled with its own code).
    # Height scales with the number of currencies: a header line (order count)
    # plus 4 money lines per currency (gross, delivery pass-through, commission, net),
    # with a blank separator between currencies.
    _n_cur = max(1, len(per_currency))
    _box_h = (3 + _n_cur * 5) * 5 * mm  # rough: count line + 4 money lines × N + spacing
    doc.setFillColorRGB(0.94, 0.95, 0.98)
    doc.rect(margin, y - _box_h, page_w - 2 * margin, _box_h, fill=1, stroke=0)
    doc.setFillColorRGB(0, 0, 0)

    sy = y - 8 * mm
    doc.setFont("Helvetica", 9)
    doc.drawString(margin + 4 * mm, sy, "Orders placed via marketplace:")
    doc.setFont("Helvetica-Bold", 9)
    doc.drawRightString(page_w - margin - 4 * mm, sy, str(order_count))
    sy -= 7 * mm

    for _pc in per_currency:
        _cur = _pc["currency"]
        summary_items = [
            ("Gross order revenue:", f"{_cur} {_pc['total_revenue']:,.2f}"),
            ("  Delivery pass-through:", f"- {_cur} {_pc['total_delivery_fees']:,.2f}"),
            (commission_label, f"- {_cur} {_pc['total_commission']:,.2f}"),
            ("Net payout to restaurant:", f"{_cur} {_pc['net_payout']:,.2f}"),
        ]
        for label, value in summary_items:
            doc.setFont("Helvetica", 9)
            doc.drawString(margin + 4 * mm, sy, label)
            doc.setFont("Helvetica-Bold", 9)
            doc.drawRightString(page_w - margin - 4 * mm, sy, value)
            sy -= 5 * mm
        sy -= 2 * mm  # gap between currency blocks

    y -= _box_h + 7 * mm

    # Table header
    col_widths = [45 * mm, 32 * mm, 35 * mm, 30 * mm, 30 * mm]
    col_labels = ["Order #", "Date", "Revenue", "Commission", "Net Payout"]
    col_x = [margin]
    for w in col_widths[:-1]:
        col_x.append(col_x[-1] + w)

    doc.setFillColorRGB(0.2, 0.2, 0.4)
    doc.rect(margin, y - 7 * mm, page_w - 2 * margin, 7 * mm, fill=1, stroke=0)
    doc.setFillColorRGB(1, 1, 1)
    doc.setFont("Helvetica-Bold", 8)
    for i, label in enumerate(col_labels):
        if i < 2:
            doc.drawString(col_x[i] + 2 * mm, y - 5 * mm, label)
        else:
            doc.drawRightString(col_x[i] + col_widths[i] - 2 * mm, y - 5 * mm, label)
    y -= 7 * mm

    # Table rows
    doc.setFillColorRGB(0, 0, 0)
    row_h = 6 * mm
    for idx, o in enumerate(orders_data):
        if y < 25 * mm:  # new page
            doc.showPage()
            y = page_h - 20 * mm
        bg = 0.97 if idx % 2 == 0 else 1.0
        doc.setFillColorRGB(bg, bg, bg)
        doc.rect(margin, y - row_h, page_w - 2 * margin, row_h, fill=1, stroke=0)
        doc.setFillColorRGB(0, 0, 0)
        doc.setFont("Helvetica", 8)
        date_str = o["created_at"][:10]
        row_vals = [o["order_number"], date_str,
                    f"{o['currency']} {o['total']:,.2f}",
                    f"{o['currency']} {o['commission_amount']:,.2f}",
                    f"{o['currency']} {o['net_payout']:,.2f}"]
        for i, val in enumerate(row_vals):
            if i < 2:
                doc.drawString(col_x[i] + 2 * mm, y - 4.5 * mm, val)
            else:
                doc.drawRightString(col_x[i] + col_widths[i] - 2 * mm, y - 4.5 * mm, val)
        y -= row_h

    # Totals row(s) — one per currency, each labelled with its own code so a
    # mixed-currency month never sums dissimilar currencies into one figure.
    y -= 2 * mm
    doc.line(margin, y, page_w - margin, y)
    y -= 5 * mm
    for _pc in per_currency:
        if y < 20 * mm:  # spill the totals onto a new page if we ran out of room
            doc.showPage()
            y = page_h - 20 * mm
        _cur = _pc["currency"]
        _label = "TOTALS" if len(per_currency) == 1 else f"TOTALS ({_cur})"
        doc.setFont("Helvetica-Bold", 9)
        doc.drawString(margin + 2 * mm, y, _label)
        doc.drawRightString(col_x[2] + col_widths[2] - 2 * mm, y, f"{_cur} {_pc['total_revenue']:,.2f}")
        doc.drawRightString(col_x[3] + col_widths[3] - 2 * mm, y, f"{_cur} {_pc['total_commission']:,.2f}")
        doc.drawRightString(col_x[4] + col_widths[4] - 2 * mm, y, f"{_cur} {_pc['net_payout']:,.2f}")
        y -= 5 * mm

    # Footer
    doc.setFont("Helvetica", 7)
    doc.setFillColorRGB(0.55, 0.55, 0.55)
    doc.drawCentredString(page_w / 2, 12 * mm, "This statement is auto-generated. Contact support for billing queries.")

    doc.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def get_issued_statement(year, month):
    """The currently-issued snapshot for (year, month), or None.

    Defensive by design: the mock-based statement suites exercise the GET
    path with no database behind the snapshot models, so ANY lookup failure
    (no DB, missing table mid-deploy) degrades to the live preview instead
    of erroring the endpoint. In production the lookup is a plain indexed
    query on the tenant schema.
    """
    try:
        return (
            CommissionStatement.objects
            .filter(
                year=year,
                month=month,
                status=CommissionStatement.Status.ISSUED,
            )
            .order_by("-revision")
            .first()
        )
    except Exception:
        return None


def frozen_orders_data(stmt):
    """Rebuild the served ``orders`` rows from a snapshot's frozen lines —
    the exact dict shape compute_statement produces from live orders."""
    return [
        {
            "order_number": line.order_number,
            "created_at": line.created_at.isoformat(),
            "customer_name": line.customer_name,
            "total": float(line.total),
            "delivery_fee": float(line.delivery_fee),
            "commission_amount": float(line.commission_amount),
            "commission_rate_applied": float(line.commission_rate_applied),
            "net_payout": float(line.net_payout),
            "currency": line.currency,
            "status": line.status,
        }
        for line in stmt.lines.all()
    ]


def issue_statement(profile, year, month, *, issued_by, reissue=False, reason=""):
    """Freeze the (year, month) statement as a persistent snapshot.

    First issue creates revision 1. Re-issuing an already-issued month is
    an explicit, reasoned act: ``reissue`` must be set and ``reason``
    non-empty; the current revision is retained, marked superseded, and
    revision N+1 is computed from live rows and frozen. Raises
    StatementAlreadyIssued / StatementReissueReasonRequired otherwise.

    The snapshot stores the served summary/per_currency dicts verbatim plus
    one CommissionStatementLine per order row, so GET (JSON and PDF) after
    issue is served entirely from frozen data.
    """
    reason = (reason or "").strip()
    with transaction.atomic():
        existing = (
            CommissionStatement.objects
            .select_for_update()
            .filter(
                year=year,
                month=month,
                status=CommissionStatement.Status.ISSUED,
            )
            .order_by("-revision")
            .first()
        )
        revision = 1
        if existing is not None:
            if not reissue:
                raise StatementAlreadyIssued(
                    f"{year}-{month:02d} already has issued revision "
                    f"{existing.revision}; pass reissue with a reason to "
                    "supersede it."
                )
            if not reason:
                raise StatementReissueReasonRequired(
                    "Reissuing a statement requires a reason."
                )
            revision = existing.revision + 1

        computed = compute_statement(profile, year, month)
        stmt = CommissionStatement.objects.create(
            year=year,
            month=month,
            revision=revision,
            issued_by=issued_by,
            reissue_reason=reason if revision > 1 else "",
            tz_name=computed["tz_name"],
            summary=computed["summary"],
            per_currency=computed["per_currency"],
            status=CommissionStatement.Status.ISSUED,
        )
        if existing is not None:
            existing.status = CommissionStatement.Status.SUPERSEDED
            existing.save(update_fields=["status"])

        lines = []
        for idx, (order_id, row) in enumerate(
            zip(computed["order_ids"], computed["orders_data"])
        ):
            lines.append(
                CommissionStatementLine(
                    statement=stmt,
                    order_id=order_id,
                    sort_order=idx,
                    order_number=row["order_number"],
                    created_at=_dt.fromisoformat(row["created_at"]),
                    customer_name=row["customer_name"],
                    total=Decimal(str(row["total"])),
                    delivery_fee=Decimal(str(row["delivery_fee"])),
                    commission_amount=Decimal(str(row["commission_amount"])),
                    commission_rate_applied=Decimal(
                        str(row["commission_rate_applied"])
                    ),
                    net_payout=Decimal(str(row["net_payout"])),
                    currency=row["currency"],
                    status=row["status"],
                )
            )
        CommissionStatementLine.objects.bulk_create(lines)
        return stmt
