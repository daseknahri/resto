# Order Flow E2E QA (Table QR vs General Menu)

## 1. Start App
Run from repo root:

```powershell
powershell -ExecutionPolicy Bypass -File infra/stop_local.ps1
powershell -ExecutionPolicy Bypass -File infra/run_local.ps1 -TenantHost demo.localhost -ApiPort 8000 -WebPort 5173
```

## 2. URLs to Test
- Customer info page: `http://demo.localhost:5173/menu`
- Menu browse page: `http://demo.localhost:5173/browse`
- Cart page: `http://demo.localhost:5173/cart`
- Reservation page: `http://demo.localhost:5173/reserve`
- Table QR route (example): `http://demo.localhost:5173/t/<table-slug>`
- Owner workspace: `http://demo.localhost:5173/owner`
- Admin console: `http://demo.localhost:5173/admin-console`

## 3. Case A: Table-QR Order (Minimal Form)
1. Open a valid table QR route (`/t/<table-slug>`) or use table context.
2. Add dish to cart and open `/cart`.
3. Confirm cart shows `Table QR order` context.
4. Confirm only optional restaurant note is needed (no required pickup/delivery or customer identity).
5. Click `Send order via WhatsApp`.

Expected:
- WhatsApp opens.
- Message includes `Table: ...`.
- No validation error for missing customer name/phone.

## 4. Case B: General Menu Order (No Table Context)
1. Open `http://demo.localhost:5173/browse`.
2. Add dish to cart and open `/cart`.
3. Confirm fulfillment selector is visible (`Pickup` / `Delivery`).
4. Try sending without required fields.

Expected:
- Validation errors shown for missing required fields.

Then test:
1. Select `Pickup`.
2. Fill customer name and phone.
3. Send order.

Expected:
- WhatsApp opens.
- Message includes customer identity and `Fulfillment: Pickup`.

## 5. Delivery-Specific Validation
From general menu cart:
1. Select `Delivery`.
2. Leave address/location empty and send.

Expected:
- Validation error for missing delivery address/location.

Then:
1. Fill delivery address.
2. Click `Pick pin in app` and tap map, OR click `Use current location`, OR paste map link.
3. Send order.

Expected:
- WhatsApp opens.
- Message includes delivery address and map/coordinates.

## 6. Quick API Smoke (Automated)
Run:

```powershell
powershell -ExecutionPolicy Bypass -File infra/order_flow_api_smoke.ps1 -TenantHost demo.localhost -ApiPort 8000
```

Expected:
- Table output with all checks `pass = True`.
- For Basic plan, checkout check can be `403` (gated) and is considered pass.
