/**
 * usePrintTicket — print an 80mm thermal-friendly order receipt that goes out WITH the
 * order. Opens a clean print window, writes the receipt HTML, and triggers the browser
 * print dialog. Shared by OwnerOrders and OwnerKitchen.
 *
 * The order object is the owner/kitchen order payload (items, totals, tip_amount,
 * wallet_amount_paid, vat_*, customer_*, delivery_*). The restaurant thank-you note is
 * pulled from the tenant profile (meta.profile.receipt_message).
 */
import { useI18n } from "./useI18n";
import { useToastStore } from "../stores/toast";
import { useTenantStore } from "../stores/tenant";
import { escapeHtml } from "../lib/escape";

export function usePrintTicket() {
  const { t, formatNumber, currentLocale } = useI18n();
  const toast = useToastStore();
  const tenant = useTenantStore();

  const fmt = (amount, currency = "USD") => {
    try {
      return formatNumber(Number(amount) || 0, { style: "currency", currency });
    } catch {
      return `${currency} ${(Number(amount) || 0).toFixed(2)}`;
    }
  };

  const fulfillmentLabel = (o) => {
    if (o.fulfillment_type === "table") return t("ownerOrders.fulfillmentTable", { table: o.table_label || "?" });
    if (o.fulfillment_type === "delivery") return t("ownerOrders.fulfillmentDelivery");
    if (o.fulfillment_type === "pickup") return t("ownerOrders.fulfillmentPickup");
    return "";
  };

  const _buildHtml = (o) => {
    const cur = o.currency;
    // Voided items are excluded from the printed ticket entirely (nothing to cook).
    // Held-course items (not yet fired) are flagged so the kitchen doesn't start
    // them early — mirrors the is_voided / course-vs-fired_course handling already
    // shown on-screen in OwnerKitchen.vue and OwnerOrders.vue.
    const firedCourse = o.fired_course ?? 1;
    const itemRows = (o.items || []).filter((item) => !item.is_voided).map((item) => {
      const opts = item.options?.length
        ? `<div style="font-size:11px;color:#555">${item.options.map((x) => escapeHtml(x.name)).join(", ")}</div>`
        : "";
      const note = item.note
        ? `<div style="font-size:11px;color:#555;font-style:italic">${escapeHtml(item.note)}</div>`
        : "";
      const comboLines = Array.isArray(item.combo_components) && item.combo_components.length
        ? item.combo_components.map((comp) =>
            `<div style="font-size:10px;color:#888;padding-left:8px">↳ ${escapeHtml(comp.name)} ×${comp.qty * item.qty}</div>`
          ).join("")
        : "";
      const isHeld = (item.course ?? 0) > 0 && item.course > firedCourse;
      const heldChip = isHeld
        ? `<span style="font-size:10px;font-weight:bold;color:#b45309;border:1px solid #b45309;border-radius:8px;padding:0 4px;margin-left:4px">${escapeHtml(t("waiterPage.heldChip"))}</span>`
        : "";
      return `<tr>
        <td style="padding:3px 0;vertical-align:top"><strong>${item.qty}×</strong> ${escapeHtml(item.dish_name)}${heldChip}${opts}${note}${comboLines}</td>
        <td style="padding:3px 0;text-align:right;white-space:nowrap;vertical-align:top">${fmt(item.subtotal, cur)}</td>
      </tr>`;
    }).join("");

    const scheduledLine = o.scheduled_for
      ? `${t("ownerOrders.ticketScheduled")}: ${new Intl.DateTimeFormat(currentLocale.value, { dateStyle: "short", timeStyle: "short" }).format(new Date(o.scheduled_for))}`
      : "";
    const meta = [
      fulfillmentLabel(o),
      scheduledLine,
      o.customer_name ? `${t("ownerOrders.ticketCustomer")}: ${escapeHtml(o.customer_name)}` : "",
      o.customer_phone ? `${t("ownerOrders.ticketPhone")}: ${escapeHtml(o.customer_phone)}` : "",
      o.customer_email ? `${t("ownerOrders.ticketEmail")}: ${escapeHtml(o.customer_email)}` : "",
      o.delivery_address ? `${t("ownerOrders.ticketAddress")}: ${escapeHtml(o.delivery_address)}` : "",
      new Intl.DateTimeFormat(currentLocale.value, { dateStyle: "short", timeStyle: "short" }).format(new Date(o.created_at)),
    ].filter(Boolean).map((line) => `<div>${line}</div>`).join("");

    const note = o.customer_note
      ? `<div style="border-top:1px dashed #000;margin-top:8px;padding-top:6px"><strong>${t("ownerOrders.ticketNote")}:</strong> ${escapeHtml(o.customer_note)}</div>`
      : "";

    const hasFee = Number(o.delivery_fee) > 0;
    const hasVat = Number(o.vat_amount) > 0;
    const hasTip = Number(o.tip_amount) > 0;
    const hasWallet = Number(o.wallet_amount_paid) > 0;
    const hasLoyalty = Number(o.loyalty_discount) > 0;
    // Subtotal = food only. total = subtotal + delivery + tip − loyalty discount, so add
    // the loyalty discount back out to recover the pre-discount food line.
    const subtotal = Number(o.total) - Number(o.delivery_fee || 0) - Number(o.tip_amount || 0) + Number(o.loyalty_discount || 0);
    const line = (label, value, color = "#444") =>
      `<tr><td style="padding:2px 0;font-size:12px;color:${color}">${label}</td><td style="text-align:right;font-size:12px;color:${color}">${value}</td></tr>`;

    // ── Split-payments block (rendered when the order has a payments ledger) ─────
    const payments = Array.isArray(o.payments) ? o.payments : [];
    const hasPayments = payments.length > 0;
    const amountPaid = Number(o.amount_paid) || 0;
    const outstanding = o.outstanding != null ? Number(o.outstanding) : null;
    const isPartial = o.payment_status !== "paid" && amountPaid > 0;

    const methodLabel = (method) => {
      if (method === "cash") return t("ownerOrders.paymentCash");
      if (method === "wallet") return t("ownerOrders.paymentWallet");
      return method || "";
    };

    const paymentsHtml = hasPayments
      ? `<div style="border-top:1px dashed #000;margin-top:8px;padding-top:6px">
          <div style="font-size:11px;font-weight:bold;margin-bottom:4px">${escapeHtml(t("ownerOrders.paymentsTitle"))}</div>
          ${payments.map((p) =>
            `<div style="display:flex;justify-content:space-between;font-size:11px">
              <span>${escapeHtml(methodLabel(p.method))}</span>
              <span>${fmt(p.amount, cur)}</span>
            </div>`
          ).join("")}
          ${isPartial
            ? `<div style="display:flex;justify-content:space-between;font-size:11px;margin-top:2px">
                <span>${escapeHtml(t("ownerOrders.paidLine"))}</span>
                <span>${fmt(amountPaid, cur)}</span>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:11px;color:#b45309">
                <span>${escapeHtml(t("ownerOrders.outstandingLine"))}</span>
                <span>${fmt(outstanding !== null ? outstanding : Math.max(0, Number(o.total) - amountPaid), cur)}</span>
              </div>`
            : `<div style="font-size:11px;color:#16a34a">${escapeHtml(t("ownerOrders.paidLine"))}</div>`
          }
        </div>`
      : "";

    const thankYou = (tenant.meta?.profile?.receipt_message || "").trim();
    const thankYouHtml = thankYou
      ? `<div style="text-align:center;font-size:11px;margin-top:10px;border-top:1px dashed #000;padding-top:8px">${escapeHtml(thankYou)}</div>`
      : "";

    const html = `<!DOCTYPE html><html lang="${currentLocale.value}" dir="${currentLocale.value === 'ar' ? 'rtl' : 'ltr'}"><head>
      <meta charset="utf-8"><title>Order ${escapeHtml(o.order_number)}</title>
      <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family: 'Courier New', monospace; font-size: 13px; width: 300px; padding: 12px; }
        h1 { font-size: 18px; text-align: center; letter-spacing: 1px; border-bottom: 2px dashed #000; padding-bottom: 8px; margin-bottom: 8px; }
        .meta { font-size: 11px; margin-bottom: 8px; line-height: 1.6; }
        table { width: 100%; border-collapse: collapse; }
        .divider { border-top: 1px dashed #000; margin: 8px 0; }
        .total td { font-weight: bold; font-size: 15px; padding: 4px 0; }
        .footer { text-align: center; font-size: 10px; color: #666; margin-top: 12px; border-top: 1px dashed #000; padding-top: 8px; }
        @media print { @page { margin: 0; size: 80mm auto; } }
      </style></head><body>
      <h1>#${escapeHtml(o.order_number)}</h1>
      <div class="meta">${meta}</div>
      <div class="divider"></div>
      <table>${itemRows}</table>
      <div class="divider"></div>
      <table>
        ${(hasFee || hasTip || hasLoyalty) ? line(t("ownerOrders.ticketSubtotal"), fmt(subtotal, cur)) : ""}
        ${hasFee ? line(t("ownerOrders.deliveryFee"), fmt(o.delivery_fee, cur)) : ""}
        ${hasVat ? line(escapeHtml(t("orderStatus.vatIncluded", { label: o.vat_label, rate: Number(o.vat_rate) })), fmt(o.vat_amount, cur)) : ""}
        ${hasLoyalty ? line(t("ownerOrders.loyaltyDiscount"), `−${fmt(o.loyalty_discount, cur)}`, "#d97706") : ""}
        ${hasTip ? line(t("ownerOrders.tip"), fmt(o.tip_amount, cur)) : ""}
        <tr class="total"><td>${t("ownerOrders.ticketTotal")}</td><td style="text-align:right">${fmt(o.total, cur)}</td></tr>
        ${hasWallet ? line(`💰 ${t("ownerOrders.walletPaid")}`, `−${fmt(o.wallet_amount_paid, cur)}`, "#16a34a") : ""}
      </table>
      ${note}
      ${paymentsHtml}
      ${thankYouHtml}
      <div class="footer">${t("ownerOrders.ticketPrinted")} ${new Intl.DateTimeFormat(currentLocale.value, { timeStyle: 'short' }).format(new Date())}</div>
    </body></html>`;

    return html;
  };

  // Manual print: opens a popup window (requires user gesture to avoid popup block).
  const printTicket = (o) => {
    if (!o) return;
    const html = _buildHtml(o);
    const win = window.open("", "_blank", "width=420,height=620");
    if (!win) { toast.show(t("ownerOrders.printBlocked"), "error"); return; }
    win.document.write(html);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); win.close(); }, 300);
  };

  // Auto-print: hidden iframe avoids popup-blocked restriction for non-gesture contexts.
  // The browser still shows the print dialog unless a default printer is configured
  // silently (kiosk/thermal-printer setup). Each call prints one receipt.
  const printTicketSilent = (o) => {
    if (!o) return;
    const html = _buildHtml(o);
    const iframe = document.createElement("iframe");
    iframe.style.cssText = "position:fixed;top:-9999px;left:-9999px;width:0;height:0;border:none;";
    document.body.appendChild(iframe);
    try {
      const doc = iframe.contentDocument || iframe.contentWindow.document;
      doc.open();
      doc.write(html);
      doc.close();
      iframe.contentWindow.focus();
      setTimeout(() => {
        try { iframe.contentWindow.print(); } catch { /* cross-origin guard */ }
        setTimeout(() => { if (document.body.contains(iframe)) document.body.removeChild(iframe); }, 1500);
      }, 300);
    } catch {
      if (document.body.contains(iframe)) document.body.removeChild(iframe);
    }
  };

  // Bulk print: combine N tickets into one print window, separated by page breaks.
  // Requires a user gesture (popup) — use from a button click handler.
  const printBulkTickets = (orders) => {
    if (!orders?.length) return;
    const bodies = orders
      .map((o) => {
        if (!o) return '';
        const full = _buildHtml(o);
        const m = full.match(/<body[^>]*>([\s\S]*)<\/body>/i);
        return m ? m[1] : '';
      })
      .filter(Boolean);
    if (!bodies.length) return;

    const win = window.open('', '_blank', 'width=420,height=680');
    if (!win) { toast.show(t('ownerOrders.printBlocked'), 'error'); return; }

    const combined = `<!DOCTYPE html><html lang="${currentLocale.value}" dir="${currentLocale.value === 'ar' ? 'rtl' : 'ltr'}"><head>
      <meta charset="utf-8"><title>Kitchen Tickets</title>
      <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:'Courier New',monospace; font-size:13px; width:300px; padding:12px; }
        h1 { font-size:18px; text-align:center; letter-spacing:1px; border-bottom:2px dashed #000; padding-bottom:8px; margin-bottom:8px; }
        .meta { font-size:11px; margin-bottom:8px; line-height:1.6; }
        table { width:100%; border-collapse:collapse; }
        .divider { border-top:1px dashed #000; margin:8px 0; }
        .total td { font-weight:bold; font-size:15px; padding:4px 0; }
        .footer { text-align:center; font-size:10px; color:#666; margin-top:12px; border-top:1px dashed #000; padding-top:8px; }
        .ticket { page-break-after:always; }
        .ticket:last-child { page-break-after:avoid; }
        @media print { @page { margin:0; size:80mm auto; } }
      </style></head><body>
      ${bodies.map((b) => `<div class="ticket">${b}</div>`).join('')}
    </body></html>`;

    win.document.write(combined);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); win.close(); }, 300);
  };

  return { printTicket, printTicketSilent, printBulkTickets };
}
