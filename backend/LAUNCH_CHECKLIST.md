# Launch Checklist

## Celery Beat / Coolify Scheduled Tasks

Run each command periodically. Beat and Coolify scheduled tasks are interchangeable —
do not enable both for the same command or jobs will double-fire.

| Command                   | Interval | Purpose                                                      |
|---------------------------|----------|--------------------------------------------------------------|
| `sweep_delivery_jobs`     | 60 s     | Re-dispatch ranked-offer cascades + recover stuck delivery jobs |
| `sweep_ride_requests`     | 120 s    | Re-push, auto-cancel, and release stale-driver ride requests  |
| `release_scheduled_orders`| 5 min    | Release scheduled orders whose scheduled_for time has passed  |
| `send_review_prompts`     | 15 min   | Send 30-min post-delivery review push notifications           |
| `send_reservation_reminders` | 1 hr  | Send upcoming-reservation reminder notifications              |
| `expire_charge_requests`  | 10 min   | Expire pending wallet charge requests past their TTL          |
| `enforce_subscriptions`   | daily    | Enforce subscription tiers / downgrade overdue tenants        |
| `fetch_currency_rates`    | daily    | Refresh MAD exchange rates                                    |
| `prune_analytics_events`  | daily    | Delete analytics events older than 90 days                    |
